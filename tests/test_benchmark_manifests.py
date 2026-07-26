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
