from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


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
