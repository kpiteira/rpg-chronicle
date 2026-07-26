from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = ROOT / "scripts/validate_benchmark_manifests.py"
MANIFEST_DIR = ROOT / "benchmarks/manifests"


def _load_validator_module():
    """Import the standalone validator script, which is tooling rather than a package."""
    spec = importlib.util.spec_from_file_location("validate_benchmark_manifests", VALIDATOR_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator_script = _load_validator_module()


def test_committed_benchmark_manifests_validate() -> None:
    schema = json.loads(
        (ROOT / "benchmarks/schema/benchmark-manifest.schema.json").read_text()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    manifests = sorted((ROOT / "benchmarks/manifests").glob("*.json"))

    assert len(manifests) >= 2
    for manifest in manifests:
        errors = list(validator.iter_errors(json.loads(manifest.read_text())))
        assert not errors, f"{manifest}: {errors}"


def test_manifest_corpus_is_diverse_and_rights_explicit() -> None:
    manifests = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "benchmarks/manifests").glob("*.json"))
    ]

    assert len({manifest["corpus_tier"] for manifest in manifests}) >= 2
    assert sum(manifest["selection"]["r0_status"] == "recommended" for manifest in manifests) == 1
    for manifest in manifests:
        assert manifest["excerpt"]["end_ms"] > manifest["excerpt"]["start_ms"]
        if duration_ms := manifest["source"].get("episode_duration_ms"):
            assert manifest["excerpt"]["end_ms"] <= duration_ms
        assert manifest["rights"]["local_processing"] in {"permitted", "restricted", "unknown"}
        assert manifest["rights"]["redistribution"] in {"permitted", "restricted", "unknown"}


def _hiddengrid() -> dict:
    return json.loads((MANIFEST_DIR / "hiddengrid-swc-ep044-tower-play.json").read_text())


def _write(tmp_path: Path, manifest: dict) -> Path:
    (tmp_path / "candidate.json").write_text(json.dumps(manifest))
    return tmp_path / "candidate.json"


# A test walking the committed manifests and re-asserting the anchor, basis, and evidence
# rules used to live here. `test_validator_script_passes_on_the_committed_corpus` already
# runs the validator over the same directory, and CI runs it again, so the only thing the
# walk added was a second copy of the rules that stayed green when the rules were gutted.
# The mutation tests below are what hold the behaviour.


def test_an_anchor_outside_the_window_is_rejected(tmp_path: Path) -> None:
    manifest = _hiddengrid()
    manifest["truth"]["important_entities"][0]["anchor_ms"] = manifest["excerpt"]["end_ms"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("outside the excerpt window" in line for line in lines), lines


def test_a_target_verified_without_an_anchor_is_rejected(tmp_path: Path) -> None:
    manifest = _hiddengrid()
    del manifest["truth"]["important_entities"][0]["anchor_ms"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("verified but carries no anchor_ms" in line for line in lines), lines


def test_a_target_inferred_from_metadata_cannot_be_verified(tmp_path: Path) -> None:
    """The defect this repository keeps guarding against: a title-derived claim sold as truth."""
    manifest = _hiddengrid()
    manifest["truth"]["important_entities"][0]["basis"] = "metadata_inferred"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("its basis is not one of" in line for line in lines), lines


@pytest.mark.parametrize("basis", ["audio_observed", "audio_machine_assisted"])
def test_a_target_read_from_the_recording_can_be_verified_either_way(
    tmp_path: Path, basis: str
) -> None:
    """Tooling can verify a target; it may not pass itself off as a human ear.

    Both bases pass, so upgrading a target by listening to it never fails validation.
    Keeping them separate is what lets a consumer reading only the enum tell them apart.
    """
    manifest = _hiddengrid()
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["basis"] = basis

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_claiming_a_licence_permits_processing_requires_naming_the_licence(
    tmp_path: Path,
) -> None:
    """The corpus is only usable if its permissions are checkable, not asserted."""
    manifest = _hiddengrid()
    manifest["rights"]["license_url"] = None

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("point at the licence that says so" in line for line in lines), lines


def test_a_restricted_candidate_may_record_no_licence_url(tmp_path: Path) -> None:
    """An all-rights-reserved source has no licence document, and saying so is the point."""
    manifest = _hiddengrid()
    manifest["rights"]["license_url"] = None
    manifest["rights"]["local_processing"] = "restricted"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_verified_truth_requires_a_digest_for_the_bytes_it_is_anchored_in(
    tmp_path: Path,
) -> None:
    """An anchor is an offset into particular bytes, so verified truth needs those bytes pinned."""
    manifest = _hiddengrid()
    del manifest["source"]["media_sha256"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("source.media_sha256 is required" in line for line in lines), lines


def test_a_provisional_candidate_needs_no_digest_yet(tmp_path: Path) -> None:
    """A candidate is still being assessed; the digest is owed when its truth is verified.

    The contamination list stays in place here: it is keyed on how a target was read, not
    on whether it is verified, so naming the provider is owed as soon as one was used.
    """
    manifest = _hiddengrid()
    del manifest["source"]["media_sha256"]
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["status"] = "provisional"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_machine_assisted_truth_must_name_the_providers_it_cannot_score(tmp_path: Path) -> None:
    """The contamination guard has to be checkable, not a sentence in a notes file."""
    manifest = _hiddengrid()
    del manifest["truth"]["contaminating_providers"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("truth.contaminating_providers is required" in line for line in lines), lines


def test_truth_read_by_ear_alone_needs_no_contamination_list(tmp_path: Path) -> None:
    """Nothing is contaminated when no provider was involved, so the rule stays off."""
    manifest = _hiddengrid()
    del manifest["truth"]["contaminating_providers"]
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["basis"] = "audio_observed"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_a_proven_speaker_count_above_the_estimate_is_rejected(tmp_path: Path) -> None:
    """The proven count is a floor under the estimate; above it, one of the two is wrong."""
    manifest = _hiddengrid()
    manifest["recording_conditions"]["proven_distinct_speakers"] = (
        manifest["recording_conditions"]["expected_physical_speakers"] + 1
    )

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("the proven count is a floor" in line for line in lines), lines


def test_verified_truth_requires_a_recorded_method(tmp_path: Path) -> None:
    manifest = _hiddengrid()
    del manifest["truth"]["method"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("truth.method is required" in line for line in lines), lines


def test_a_provisional_target_needs_neither_anchor_nor_method(tmp_path: Path) -> None:
    """Provisional targets are candidates, not evidence; the rules bite only on verified ones."""
    manifest = _hiddengrid()
    del manifest["truth"]["method"]
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["status"] = "provisional"
            target.pop("anchor_ms", None)

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_validator_reports_malformed_json_rather_than_raising(tmp_path: Path) -> None:
    (tmp_path / "truncated.json").write_text('{"schema_version": "0.1", "id": "truncated"')

    exit_code, lines = validator_script.validate_manifest_dir(tmp_path)

    assert exit_code == 1
    assert len(lines) == 1
    assert lines[0].startswith(f"{tmp_path / 'truncated.json'}:<parse>: not valid JSON: ")


def test_validator_reports_an_undecodable_manifest_rather_than_raising(tmp_path: Path) -> None:
    (tmp_path / "utf16.json").write_bytes(b"\xff\xfe{\x00\n\x00")

    exit_code, lines = validator_script.validate_manifest_dir(tmp_path)

    assert exit_code == 1
    assert len(lines) == 1
    assert lines[0].startswith(f"{tmp_path / 'utf16.json'}:<read>: cannot be read: ")


def test_one_malformed_manifest_does_not_hide_the_remaining_manifests(tmp_path: Path) -> None:
    good = MANIFEST_DIR / "hiddengrid-swc-ep044-tower-play.json"
    (tmp_path / good.name).write_text(good.read_text())
    (tmp_path / "a-truncated.json").write_text("{")

    exit_code, lines = validator_script.validate_manifest_dir(tmp_path)

    assert exit_code == 1
    assert any(line.startswith("valid: ") and line.endswith(good.name) for line in lines), lines


def test_validator_still_reports_schema_violations_per_field(tmp_path: Path) -> None:
    (tmp_path / "wrong-version.json").write_text(json.dumps({"schema_version": "9.9"}))

    exit_code, lines = validator_script.validate_manifest_dir(tmp_path)

    assert exit_code == 1
    assert any(":schema_version: " in line for line in lines), lines


@pytest.fixture
def malformed_manifest_in_repo() -> Iterator[Path]:
    """Place a malformed manifest in the committed directory, then always remove it."""
    probe = MANIFEST_DIR / "zz-malformed-probe.json"
    probe.write_text('{"schema_version": "0.1", "id": "truncated"')
    try:
        yield probe
    finally:
        probe.unlink(missing_ok=True)


def _run_validator_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validator_script_fails_cleanly_on_a_malformed_manifest(
    malformed_manifest_in_repo: Path,
) -> None:
    result = _run_validator_script()

    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr
    assert result.stderr == ""
    offending = [
        line for line in result.stdout.splitlines() if malformed_manifest_in_repo.name in line
    ]
    assert len(offending) == 1
    assert offending[0].startswith(
        f"{malformed_manifest_in_repo.relative_to(ROOT)}:<parse>: not valid JSON: "
    )


def test_validator_script_passes_on_the_committed_corpus() -> None:
    result = _run_validator_script()

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        f"valid: {path.relative_to(ROOT)}" for path in sorted(MANIFEST_DIR.glob("*.json"))
    ]
