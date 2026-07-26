"""The fetch procedure is only worth committing if it fails loudly on the wrong bytes.

These tests never reach the network: they exercise the verification and quarantine
behaviour against a cache the test builds itself.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/fetch_benchmark_media.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("fetch_benchmark_media", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The script defines a dataclass, which resolves its own module by name at class
    # creation time, so it has to be importable before the body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fetch = _load_script_module()

MEDIA = b"not really an mp3, but it has a digest like one"
MEDIA_SHA256 = hashlib.sha256(MEDIA).hexdigest()


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    manifest = {
        "id": "probe-item",
        "source": {
            "media_url": "https://example.invalid/podcast/probe.mp3",
            "media_bytes": len(MEDIA),
            "media_sha256": MEDIA_SHA256,
        },
    }
    path = tmp_path / "probe-item.json"
    path.write_text(json.dumps(manifest))
    return path


def _cache_media(cache: Path, payload: bytes) -> Path:
    target = cache / "probe-item" / "probe.mp3"
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    return target


def test_digest_file_reports_what_the_file_actually_is(tmp_path: Path) -> None:
    path = tmp_path / "media.bin"
    path.write_bytes(MEDIA)

    digest = fetch.digest_file(path)

    assert digest.sha256 == MEDIA_SHA256
    assert digest.size_bytes == len(MEDIA)


def test_matching_bytes_verify(tmp_path: Path, manifest_path: Path) -> None:
    cache = tmp_path / "cache"
    target = _cache_media(cache, MEDIA)

    exit_code = fetch.main([str(manifest_path), "--cache", str(cache), "--verify-only"])

    assert exit_code == 0
    assert target.exists()


def test_changed_bytes_are_quarantined_rather_than_accepted(
    tmp_path: Path, manifest_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A re-encoded source invalidates every time anchor, so it must not pass quietly."""
    cache = tmp_path / "cache"
    target = _cache_media(cache, MEDIA + b" re-encoded in 2027")

    exit_code = fetch.main([str(manifest_path), "--cache", str(cache), "--verify-only"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert not target.exists()
    assert target.with_suffix(".mp3.mismatch").exists()
    assert "MISMATCH: sha256 is " in output
    assert "MISMATCH: size is " in output
    assert "report this on the benchmark goal issue" in output


def test_a_manifest_without_a_digest_cannot_be_verified(
    tmp_path: Path, manifest_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unverifiable manifest is a gap in the manifest, not evidence against the bytes.

    So it fails, but it does not quarantine: the download may be exactly right, and
    destroying it would punish the wrong thing.
    """
    manifest = json.loads(manifest_path.read_text())
    del manifest["source"]["media_sha256"]
    manifest_path.write_text(json.dumps(manifest))
    cache = tmp_path / "cache"
    target = _cache_media(cache, MEDIA)

    exit_code = fetch.main([str(manifest_path), "--cache", str(cache), "--verify-only"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "UNVERIFIABLE: manifest records no source.media_sha256" in output
    assert "MISMATCH" not in output
    assert target.exists()
    assert not target.with_suffix(".mp3.mismatch").exists()


def test_verify_only_never_fetches_a_missing_file(
    tmp_path: Path, manifest_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = fetch.main([str(manifest_path), "--cache", str(tmp_path / "cache"), "--verify-only"])

    assert exit_code == 1
    assert "missing: " in capsys.readouterr().out


@pytest.mark.parametrize("identifier", ["../escape", "probe/item", "probe item", "Probe-Item"])
def test_an_id_that_could_climb_out_of_the_cache_is_refused(
    tmp_path: Path, manifest_path: Path, capsys: pytest.CaptureFixture[str], identifier: str
) -> None:
    """The script reads a manifest from wherever it is pointed, so the id is not trusted."""
    manifest = json.loads(manifest_path.read_text())
    manifest["id"] = identifier
    manifest_path.write_text(json.dumps(manifest))
    cache = tmp_path / "cache"

    exit_code = fetch.main([str(manifest_path), "--cache", str(cache)])

    assert exit_code == 1
    assert "REFUSED: manifest id" in capsys.readouterr().out
    assert not cache.exists()


def test_a_second_mismatch_does_not_overwrite_the_first_quarantine(tmp_path: Path) -> None:
    """Quarantine exists to preserve evidence, so it must not land on earlier evidence."""
    target = tmp_path / "probe.mp3"
    target.write_bytes(MEDIA)
    first = fetch.quarantine_path(target)
    first.write_bytes(b"an earlier mismatch")

    second = fetch.quarantine_path(target)

    assert second != first
    assert not second.exists()
    assert first.read_bytes() == b"an earlier mismatch"


def test_the_request_identifies_itself_as_a_client_the_publisher_will_serve() -> None:
    """The publisher's host answers urllib's default agent with 406, so this is load-bearing."""
    request = fetch.build_request("https://example.invalid/probe.mp3")

    agent = request.get_header("User-agent")
    assert agent and "Python-urllib" not in agent


def test_a_failed_transfer_leaves_no_partial_file(tmp_path: Path, monkeypatch) -> None:
    """A half-written file in the cache would later be digested and reported as a mismatch."""

    class _Failing:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def read(self, _size):
            raise TimeoutError("connection dropped")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda _request: _Failing())
    destination = tmp_path / "media" / "probe.mp3"

    with pytest.raises(TimeoutError):
        fetch.download("https://example.invalid/probe.mp3", destination)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_the_committed_hiddengrid_manifest_carries_what_the_procedure_needs() -> None:
    """Reproducibility is a property of the manifest, not of the operator's memory.

    This asserts only that the fields the procedure reads are present and well formed.
    Feeding them back into ``compare`` would compare them with themselves and could not
    fail; whether the real bytes match is decided by running the script, not by a test.
    """
    manifest = json.loads(
        (ROOT / "benchmarks/manifests/hiddengrid-swc-ep044-tower-play.json").read_text()
    )
    source = manifest["source"]

    assert len(source["media_sha256"]) == 64
    assert set(source["media_sha256"]) <= set("0123456789abcdef")
    assert int(source["media_bytes"]) > 0
