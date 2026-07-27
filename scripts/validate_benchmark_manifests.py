"""Validate benchmark manifests against the versioned JSON Schema.

The schema is committed here; the manifests it validates are not. A manifest describes one
recording and carries the answer key for it, and an answer key is meaningless without the
recording it answers for, so both live beside the audio in the content directory. See
`docs/CONTENT_AUDIT.md`.

That makes this a tool the operator runs rather than a CI step: CI has no content directory,
and giving it one would mean committing the thing this arrangement exists to keep out.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "benchmarks/schema/benchmark-manifest.schema.json"

#: Where recordings, manifests, answer keys and fingerprints live. Overridable so a second
#: machine, or a test, can point somewhere else without editing this file.
CONTENT_ROOT = Path(
    os.environ.get("RPG_CHRONICLE_HOME", Path.home() / ".rpg-chronicle")
).expanduser().resolve()
MANIFEST_DIR = CONTENT_ROOT / "benchmarks/manifests"

# A target can be verified from the recording by ear or through tooling. It can never be
# verified from a title, a description, or an index, however plausible the guess.
VERIFIABLE_BASES = {"audio_observed", "audio_machine_assisted"}


def _display(path: Path) -> str:
    """Name a manifest relative to the content directory when it lives inside it."""
    for base in (CONTENT_ROOT, ROOT):
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
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


def _semantic_errors(instance: dict, content_root: Path) -> list[str]:
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

    anchors = {
        target["anchor_ms"]
        for _, target in _truth_targets(instance)
        if target.get("anchor_ms") is not None
    }
    for index, thread in enumerate(instance.get("truth", {}).get("threads", [])):
        path = f"truth.threads[{index}]"
        first, last = thread["first_anchor_ms"], thread["last_anchor_ms"]
        if last <= first:
            errors.append(f"{path}.last_anchor_ms must be later than first_anchor_ms")
        for name, value in (("first_anchor_ms", first), ("last_anchor_ms", last)):
            if not start_ms <= value < end_ms:
                errors.append(
                    f"{path}.{name} {value} is outside the excerpt window "
                    f"[{start_ms}, {end_ms})"
                )
            elif value not in anchors:
                errors.append(
                    f"{path}.{name} {value} is not the anchor of any truth target; a thread "
                    "has to be held up by the observations at its ends, or it is an assertion "
                    "that something was still live with nothing showing that it was"
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
    source = instance["source"]
    fingerprint = source.get("content_fingerprint")
    if verified and not (source.get("media_sha256") or fingerprint):
        errors.append(
            "verified truth needs a way to establish identity: source.media_sha256 for a "
            "source that serves stable bytes, or source.content_fingerprint for one that "
            "re-encodes. An anchor is an offset into a particular recording, and without "
            "either a reader cannot tell whether they are holding it"
        )
    errors.extend(_fingerprint_errors(fingerprint, content_root))
    if machine_assisted and not instance["truth"].get("contaminating_providers"):
        errors.append(
            "truth.contaminating_providers is required once a target is machine-assisted; "
            "a provider that helped build the truth cannot be scored against it, and that "
            "has to be checkable rather than left to whoever reads the notes"
        )
    return errors


def _fingerprint_errors(fingerprint: dict | None, content_root: Path) -> list[str]:
    """Check that a declared fingerprint is one a reader can actually use.

    Presence satisfies the schema and proves nothing. The whole point of the field is that a
    reader runs the fingerprint against their own copy, so a typoed path or a digest that
    stopped matching leaves a manifest passing validation while its anchors are unusable -
    which is the exact failure the field was added to close. Unlike media_sha256, this digest
    is checkable, because the file it names sits beside the manifest in the content directory.
    """
    if not fingerprint:
        return []
    errors: list[str] = []
    declared = fingerprint["path"]
    content_root = content_root.resolve()
    # Resolved on both sides or the comparison below is meaningless: a relative content root
    # -- which RPG_CHRONICLE_HOME may well be -- would never contain an absolute resolved
    # path, and every valid fingerprint would be reported as escaping the directory.
    path = (content_root / declared).resolve()
    # A manifest is data, and the validator reads what it names, so the name has to be
    # constrained before it is followed. An absolute path or a ".." segment would have this
    # hashing a file anywhere on the disk and calling it the fingerprint - which both reads
    # what it should not and voids the guarantee that a fingerprint sits with its recording.
    if not path.is_relative_to(content_root):
        return [
            (
                f"source.content_fingerprint.path {declared!r} resolves outside the content "
                "directory; a fingerprint has to sit beside the recording it identifies or "
                "it guarantees nothing"
            )
        ]
    if not path.is_file():
        errors.append(
            f"source.content_fingerprint.path {fingerprint['path']!r} is not a file in the "
            "content directory; a fingerprint a reader cannot open establishes nothing"
        )
        return errors
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != fingerprint["sha256"]:
        errors.append(
            f"source.content_fingerprint.sha256 does not match {fingerprint['path']}: "
            f"recorded {fingerprint['sha256']}, file is {digest}. This digest is the one "
            "thing about identity that can be checked outright, and it has to be right"
        )
    return errors


def validate_manifest_dir(
    manifest_dir: Path = MANIFEST_DIR,
    schema_path: Path = SCHEMA_PATH,
    content_root: Path | None = None,
) -> tuple[int, list[str]]:
    """Validate every ``*.json`` manifest in ``manifest_dir``.

    Returns the process exit code and the report lines, one line per finding. An
    unreadable or unparseable manifest is a reported failure for that file, not an
    aborted run: the remaining manifests are still validated.
    """
    root = (content_root if content_root is not None else manifest_dir.parent.parent).resolve()
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
        semantic_errors = [] if errors else _semantic_errors(instance, root)
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
        return 1, [
            (
                f"No benchmark manifests found in {manifest_dir}. Manifests and answer "
                "keys live beside the recordings, outside this repository; set "
                "RPG_CHRONICLE_HOME if the content directory is not ~/.rpg-chronicle."
            )
        ]
    return int(bool(failures)), lines


def main() -> int:
    exit_code, lines = validate_manifest_dir()
    for line in lines:
        print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
