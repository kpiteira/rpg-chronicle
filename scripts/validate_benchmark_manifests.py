"""Validate committed benchmark manifests against the versioned JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "benchmarks/schema/benchmark-manifest.schema.json"
MANIFEST_DIR = ROOT / "benchmarks/manifests"

# A target can be verified from the recording by ear or through tooling. It can never be
# verified from a title, a description, or an index, however plausible the guess.
VERIFIABLE_BASES = {"audio_observed", "audio_machine_assisted"}


def _display(path: Path) -> str:
    """Name a manifest relative to the repository when it lives inside it."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _one_line(message: str) -> str:
    """Collapse an exception message so one manifest never spans several report lines."""
    return " ".join(str(message).split())


def _truth_targets(instance: dict) -> list[tuple[str, dict]]:
    """Pair every truth target with the field path a reader would look under."""
    truth = instance.get("truth", {})
    return [
        (f"truth.{group}[{index}]", target)
        for group in ("important_entities", "important_events")
        for index, target in enumerate(truth.get(group, []))
    ]


def _semantic_errors(instance: dict) -> list[str]:
    """Check the rules the schema cannot express, which are the ones that carry the meaning.

    A time anchor outside the excerpt window points at audio nobody scores, and a target
    marked ``verified`` without an anchor, without evidence, or inferred from metadata is
    the defect this project keeps guarding against: a claim that could have been written
    from the episode title and then presented as observation.
    """
    errors: list[str] = []
    start_ms = instance["excerpt"]["start_ms"]
    end_ms = instance["excerpt"]["end_ms"]

    if end_ms <= start_ms:
        errors.append("excerpt.end_ms must be greater than excerpt.start_ms")
    duration_ms = instance["source"].get("episode_duration_ms")
    if duration_ms is not None and end_ms > duration_ms:
        errors.append("excerpt.end_ms exceeds source.episode_duration_ms")

    rights = instance["rights"]
    if rights["local_processing"] == "permitted" and not rights.get("license_url"):
        errors.append(
            "rights.local_processing is permitted but rights.license_url is null or empty; a claim "
            "that a licence allows processing has to point at the licence that says so"
        )

    conditions = instance["recording_conditions"]
    expected_speakers = conditions.get("expected_physical_speakers")
    proven_speakers = conditions.get("proven_distinct_speakers")
    if (
        proven_speakers is not None
        and expected_speakers is not None
        and proven_speakers > expected_speakers
    ):
        errors.append(
            f"recording_conditions.proven_distinct_speakers {proven_speakers} exceeds "
            f"expected_physical_speakers {expected_speakers}; the proven count is a floor"
        )

    verified = False
    machine_assisted = False
    for path, target in _truth_targets(instance):
        anchor_ms = target.get("anchor_ms")
        if anchor_ms is not None and not start_ms <= anchor_ms < end_ms:
            errors.append(
                f"{path}.anchor_ms {anchor_ms} is outside the excerpt window "
                f"[{start_ms}, {end_ms})"
            )
        if target.get("basis") == "audio_machine_assisted":
            machine_assisted = True
        if target.get("status") != "verified":
            continue
        verified = True
        if anchor_ms is None:
            errors.append(f"{path} is verified but carries no anchor_ms")
        if target.get("basis") not in VERIFIABLE_BASES:
            errors.append(
                f"{path} is verified but its basis is not one of {sorted(VERIFIABLE_BASES)}; "
                "only an observation of the recording can be verified"
            )
        if not target.get("evidence", "").strip():
            errors.append(f"{path} is verified but carries no evidence")

    if verified and not instance["truth"].get("method", "").strip():
        errors.append(
            "truth.method is required once a target is verified, so a score is never "
            "read without knowing how the truth was established"
        )
    if verified and not instance["source"].get("media_sha256"):
        errors.append(
            "source.media_sha256 is required once a target is verified; an anchor is an "
            "offset into particular bytes, and without a digest nobody can tell whether "
            "they still have those bytes"
        )
    if machine_assisted and not instance["truth"].get("contaminating_providers"):
        errors.append(
            "truth.contaminating_providers is required once a target is machine-assisted; "
            "a provider that helped build the truth cannot be scored against it, and that "
            "has to be checkable rather than left to whoever reads the notes"
        )
    return errors


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
        semantic_errors = [] if errors else _semantic_errors(instance)
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
