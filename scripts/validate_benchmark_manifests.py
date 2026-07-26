"""Validate committed benchmark manifests against the versioned JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "benchmarks/schema/benchmark-manifest.schema.json"
MANIFEST_DIR = ROOT / "benchmarks/manifests"


def _display(path: Path) -> str:
    """Name a manifest relative to the repository when it lives inside it."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _one_line(message: str) -> str:
    """Collapse an exception message so one manifest never spans several report lines."""
    return " ".join(str(message).split())


def validate_manifest_dir(
    manifest_dir: Path = MANIFEST_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> tuple[int, list[str]]:
    """Validate every ``*.json`` manifest in ``manifest_dir``.

    Returns the process exit code and the report lines, one line per finding. An
    unreadable or unparseable manifest is a reported failure for that file, not an
    aborted run: the remaining manifests are still validated.
    """
    schema = json.loads(schema_path.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted(manifest_dir.glob("*.json"))
    lines: list[str] = []
    failures = 0

    for path in paths:
        try:
            instance = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            failures += 1
            lines.append(f"{_display(path)}:<parse>: not valid JSON: {_one_line(str(error))}")
            continue
        except (OSError, UnicodeDecodeError) as error:
            failures += 1
            lines.append(f"{_display(path)}:<read>: cannot be read: {_one_line(str(error))}")
            continue

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
                lines.append(f"{_display(path)}:{location}: {error.message}")
        elif semantic_errors:
            failures += 1
            for error in semantic_errors:
                lines.append(f"{_display(path)}:<semantic>: {error}")
        else:
            lines.append(f"valid: {_display(path)}")

    if not paths:
        return 1, ["No benchmark manifests found."]
    return int(bool(failures)), lines


def main() -> int:
    exit_code, lines = validate_manifest_dir()
    for line in lines:
        print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
