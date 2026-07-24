"""Validate committed benchmark manifests against the versioned JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "benchmarks/schema/benchmark-manifest.schema.json"
MANIFEST_DIR = ROOT / "benchmarks/manifests"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted(MANIFEST_DIR.glob("*.json"))
    failures = 0

    for path in paths:
        instance = json.loads(path.read_text())
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
        semantic_errors = []
        if not errors:
            start_ms = instance["excerpt"]["start_ms"]
            end_ms = instance["excerpt"]["end_ms"]
            if end_ms <= start_ms:
                semantic_errors.append("excerpt.end_ms must be greater than excerpt.start_ms")
            duration_ms = instance["source"].get("episode_duration_ms")
            if duration_ms is not None and end_ms > duration_ms:
                semantic_errors.append("excerpt.end_ms exceeds source.episode_duration_ms")
        if errors:
            failures += 1
            for error in errors:
                location = ".".join(str(part) for part in error.absolute_path) or "<root>"
                print(f"{path.relative_to(ROOT)}:{location}: {error.message}")
        elif semantic_errors:
            failures += 1
            for error in semantic_errors:
                print(f"{path.relative_to(ROOT)}:<semantic>: {error}")
        else:
            print(f"valid: {path.relative_to(ROOT)}")

    if not paths:
        print("No benchmark manifests found.")
        return 1
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
