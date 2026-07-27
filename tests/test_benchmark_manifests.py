from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = ROOT / "scripts/validate_benchmark_manifests.py"
EXAMPLE_MANIFEST = ROOT / "benchmarks/fixtures/example_manifest.json"


def _load_validator_module():
    """Import the standalone validator script, which is tooling rather than a package."""
    spec = importlib.util.spec_from_file_location("validate_benchmark_manifests", VALIDATOR_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator_script = _load_validator_module()


# Two tests here walked the committed manifests: one validated each against the schema, one
# asserted the corpus was diverse and its rights explicit. Both tested *data* rather than the
# validator, and the data now lives beside the recordings it describes, outside this
# repository. `uv run python scripts/validate_benchmark_manifests.py` is how that directory is
# checked; it is a tool the operator runs, because CI has no content directory and giving it
# one would mean committing what this arrangement exists to keep out.


def _example() -> dict:
    """A schema-valid manifest describing a recording that does not exist.

    These tests are about the validator, not about any recording, so the seed is invented.
    It used to be a real item's manifest, which meant every mutation test depended on
    content that has since moved out of the repository with the audio it describes.
    """
    return json.loads(EXAMPLE_MANIFEST.read_text())


def _write(tmp_path: Path, manifest: dict) -> Path:
    (tmp_path / "candidate.json").write_text(json.dumps(manifest))
    return tmp_path / "candidate.json"


# A test walking the committed manifests and re-asserting the anchor, basis, and evidence
# rules used to live here. It was a second copy of the rules that stayed green when the
# rules were gutted; the mutation tests below are what hold the behaviour.
#
# The manifests it walked are no longer committed at all, and CI no longer validates any -
# it has no content directory. What checks a real content directory is
# `uv run python scripts/validate_benchmark_manifests.py`, which the operator runs.


def test_an_anchor_outside_the_window_is_rejected(tmp_path: Path) -> None:
    manifest = _example()
    manifest["truth"]["important_entities"][0]["anchor_ms"] = manifest["excerpt"]["end_ms"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("outside the excerpt window" in line for line in lines), lines


def test_a_target_verified_without_an_anchor_is_rejected(tmp_path: Path) -> None:
    manifest = _example()
    del manifest["truth"]["important_entities"][0]["anchor_ms"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("verified but carries no anchor_ms" in line for line in lines), lines


def test_a_target_inferred_from_metadata_cannot_be_verified(tmp_path: Path) -> None:
    """The defect this repository keeps guarding against: a title-derived claim sold as truth."""
    manifest = _example()
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
    manifest = _example()
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["basis"] = basis

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_music_or_effects_may_be_left_unanswered(tmp_path: Path) -> None:
    """A candidate nobody listened to has nothing to report, and false would invent it.

    The nullable relaxation is what lets a rights-rejected or only-sampled candidate stay
    honest, so it needs a test of its own rather than riding on the manifests that use it.
    """
    manifest = _example()
    manifest["recording_conditions"]["music_or_effects"] = None

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_music_or_effects_still_rejects_a_non_boolean_answer(tmp_path: Path) -> None:
    """Nullable is not free-form: 'unknown' as a string would slip past a reader's eye."""
    manifest = _example()
    manifest["recording_conditions"]["music_or_effects"] = "unknown"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("music_or_effects" in line for line in lines), lines


def test_claiming_a_licence_permits_processing_requires_naming_the_licence(
    tmp_path: Path,
) -> None:
    """The corpus is only usable if its permissions are checkable, not asserted."""
    manifest = _example()
    manifest["rights"]["license_url"] = None

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("point at the licence that says so" in line for line in lines), lines


def test_a_restricted_candidate_may_record_no_licence_url(tmp_path: Path) -> None:
    """An all-rights-reserved source has no licence document, and saying so is the point."""
    manifest = _example()
    manifest["rights"]["license_url"] = None
    manifest["rights"]["local_processing"] = "restricted"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_verified_truth_requires_a_way_to_establish_identity(tmp_path: Path) -> None:
    """An anchor is an offset into a particular recording, so identity has to be checkable."""
    manifest = _example()
    del manifest["source"]["media_sha256"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("verified truth needs a way to establish identity" in line for line in lines), lines


def _fingerprint_in(content_root: Path) -> dict:
    """Write a fingerprint file into a content root and describe it as a manifest would.

    Fingerprints live beside the recordings they identify, outside this repository, so the
    test builds one rather than pointing at a committed artefact.
    """
    relative = "benchmarks/fingerprints/example.json"
    path = content_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"method": "rms_envelope_v1", "coarse": [-20.0, -21.0]}))
    return {
        "path": relative,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "method": "rms_envelope_v1",
    }


def test_a_fingerprint_satisfies_identity_where_bytes_cannot(tmp_path: Path) -> None:
    """A source that re-encodes gives every downloader different bytes, so a digest pins
    nothing. The fingerprint describes the sound and is the honest substitute."""
    content_root = tmp_path / "content"
    manifests = content_root / "benchmarks" / "manifests"
    manifests.mkdir(parents=True)
    manifest = _example()
    del manifest["source"]["media_sha256"]
    manifest["source"]["content_fingerprint"] = _fingerprint_in(content_root)

    exit_code, lines = validator_script.validate_manifest_dir(_write(manifests, manifest).parent)

    assert exit_code == 0, lines


def test_a_fingerprint_pointing_at_no_file_is_rejected(tmp_path: Path) -> None:
    """Presence satisfies the schema and establishes nothing; the reader has to be able to
    open it, or the identity claim is a sentence rather than a procedure."""
    content_root = tmp_path / "content"
    manifests = content_root / "benchmarks" / "manifests"
    manifests.mkdir(parents=True)
    manifest = _example()
    manifest["source"]["content_fingerprint"] = {
        **_fingerprint_in(content_root),
        "path": "benchmarks/fingerprints/does-not-exist.json",
    }

    exit_code, lines = validator_script.validate_manifest_dir(_write(manifests, manifest).parent)

    assert exit_code == 1
    assert any("is not a file in the content directory" in line for line in lines), lines


@pytest.mark.parametrize(
    "declared",
    ["/etc/passwd", "../outside.json", "benchmarks/../../outside.json"],
)
def test_a_fingerprint_path_may_not_escape_the_content_directory(
    declared: str, tmp_path: Path
) -> None:
    """The validator follows a path a manifest supplies, so the path is untrusted input.

    The schema pattern rejects these too, and this checks the validator's own guard rather
    than that pattern: two layers, because the one that reads the file is the one that must
    refuse. Called directly for exactly that reason - going through the schema would never
    reach this code and the test would pass without exercising it.
    """
    errors = validator_script._fingerprint_errors(
        {"method": "rms_envelope_v1", "path": declared, "sha256": "0" * 64}, tmp_path
    )

    assert any("resolves outside the content directory" in error for error in errors), errors


def test_a_fingerprint_whose_digest_stopped_matching_is_rejected(tmp_path: Path) -> None:
    """This is the one digest in a manifest that can be checked outright, because the file it
    names sits beside the manifest. Regenerating the fingerprint without updating the manifest
    is the realistic way it goes wrong, and it has to fail rather than pass quietly."""
    content_root = tmp_path / "content"
    manifests = content_root / "benchmarks" / "manifests"
    manifests.mkdir(parents=True)
    manifest = _example()
    manifest["source"]["content_fingerprint"] = {
        **_fingerprint_in(content_root),
        "sha256": "0" * 64,
    }

    exit_code, lines = validator_script.validate_manifest_dir(_write(manifests, manifest).parent)

    assert exit_code == 1
    assert any("content_fingerprint.sha256 does not match" in line for line in lines), lines


def test_a_provisional_candidate_needs_no_digest_yet(tmp_path: Path) -> None:
    """A candidate is still being assessed; the digest is owed when its truth is verified.

    The contamination list stays in place here: it is keyed on how a target was read, not
    on whether it is verified, so naming the provider is owed as soon as one was used.
    """
    manifest = _example()
    del manifest["source"]["media_sha256"]
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["status"] = "provisional"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def _anchors() -> tuple[int, int]:
    """The fixture's own first and last target anchors.

    Read from the fixture rather than written out, so a thread test never carries a number
    that has to be kept in step with a file by hand. An earlier version stated exactly this
    in a comment while hardcoding the values underneath it.
    """
    anchors = sorted(
        target["anchor_ms"]
        for group in ("important_entities", "important_events")
        for target in _example()["truth"][group]
        if target.get("anchor_ms") is not None
    )
    return anchors[0], anchors[-1]


FIRST_ANCHOR, LAST_ANCHOR = _anchors()


def _threaded(first: int, last: int) -> dict:
    """A manifest carrying one thread between two of its own target anchors."""
    manifest = _example()
    manifest["truth"]["threads"] = [
        {
            "label": "example",
            "first_anchor_ms": first,
            "last_anchor_ms": last,
            "evidence": "the later moment is about the earlier one",
        }
    ]
    return manifest


def test_a_thread_between_two_target_anchors_is_accepted(tmp_path: Path) -> None:
    """The positive case, so the rejections below are not passing for want of any thread."""
    manifest = _threaded(FIRST_ANCHOR, LAST_ANCHOR)

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_a_thread_end_that_anchors_no_target_is_rejected(tmp_path: Path) -> None:
    """A thread claims a subject was still live, and the targets at its ends are what show it.

    One millisecond off a real anchor is the interesting mutation: the number still lands in
    the window and still looks like a citation, and there is nothing at it.
    """
    manifest = _threaded(FIRST_ANCHOR + 1, LAST_ANCHOR)

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("is not the anchor of any truth target" in line for line in lines), lines


def test_a_thread_that_ends_before_it_starts_is_rejected(tmp_path: Path) -> None:
    manifest = _threaded(LAST_ANCHOR, FIRST_ANCHOR)

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("must be later than first_anchor_ms" in line for line in lines), lines


def test_a_thread_reaching_outside_the_excerpt_is_rejected(tmp_path: Path) -> None:
    """Outside the window is audio nobody scores, so a span across it measures nothing."""
    manifest = _threaded(FIRST_ANCHOR, manifest_end := _example()["excerpt"]["end_ms"] + 1)
    assert manifest_end > 0

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("outside the excerpt window" in line for line in lines), lines


def test_machine_assisted_truth_must_name_the_providers_it_cannot_score(tmp_path: Path) -> None:
    """The contamination guard has to be checkable, not a sentence in a notes file.

    The machine-assisted basis is set here rather than inherited from the fixture, because
    that is the precondition the rule keys on and a reader should not have to open another
    file to see it. The fixture reads everything by ear, which is what the test below needs.
    """
    manifest = _example()
    manifest["truth"]["important_entities"][0]["basis"] = "audio_machine_assisted"
    del manifest["truth"]["contaminating_providers"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("truth.contaminating_providers is required" in line for line in lines), lines


def test_truth_read_by_ear_alone_needs_no_contamination_list(tmp_path: Path) -> None:
    """Nothing is contaminated when no provider was involved, so the rule stays off."""
    manifest = _example()
    del manifest["truth"]["contaminating_providers"]
    for group in ("important_entities", "important_events"):
        for target in manifest["truth"][group]:
            target["basis"] = "audio_observed"

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 0, lines


def test_a_proven_speaker_count_above_the_estimate_is_rejected(tmp_path: Path) -> None:
    """The proven count is a floor under the estimate; above it, one of the two is wrong."""
    manifest = _example()
    manifest["recording_conditions"]["proven_distinct_speakers"] = (
        manifest["recording_conditions"]["expected_physical_speakers"] + 1
    )

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("the proven count is a floor" in line for line in lines), lines


def test_verified_truth_requires_a_recorded_method(tmp_path: Path) -> None:
    manifest = _example()
    del manifest["truth"]["method"]

    exit_code, lines = validator_script.validate_manifest_dir(_write(tmp_path, manifest).parent)

    assert exit_code == 1
    assert any("truth.method is required" in line for line in lines), lines


def test_a_provisional_target_needs_neither_anchor_nor_method(tmp_path: Path) -> None:
    """Provisional targets are candidates, not evidence; the rules bite only on verified ones."""
    manifest = _example()
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
    (tmp_path / "b-good.json").write_text(json.dumps(_example()))
    (tmp_path / "a-truncated.json").write_text("{")

    exit_code, lines = validator_script.validate_manifest_dir(tmp_path)

    assert exit_code == 1
    assert any(line.startswith("valid: ") and line.endswith("b-good.json") for line in lines), lines


def test_validator_still_reports_schema_violations_per_field(tmp_path: Path) -> None:
    (tmp_path / "wrong-version.json").write_text(json.dumps({"schema_version": "9.9"}))

    exit_code, lines = validator_script.validate_manifest_dir(tmp_path)

    assert exit_code == 1
    assert any(":schema_version: " in line for line in lines), lines


def _content_root_with(tmp_path: Path, **manifests: dict) -> Path:
    """Build a content directory the script can be pointed at.

    The script defaults to the operator's `~/.rpg-chronicle`, which a test must never read:
    it would pass or fail on whatever recordings that machine happens to hold.
    """
    directory = tmp_path / "benchmarks" / "manifests"
    directory.mkdir(parents=True)
    for name, manifest in manifests.items():
        (directory / f"{name}.json").write_text(
            manifest if isinstance(manifest, str) else json.dumps(manifest)
        )
    return tmp_path


def _run_validator_script(content_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "RPG_CHRONICLE_HOME": str(content_root)},
    )


def test_validator_script_fails_cleanly_on_a_malformed_manifest(tmp_path: Path) -> None:
    """A parse failure has to read as a finding, not as the tool falling over."""
    content_root = _content_root_with(
        tmp_path, truncated='{"schema_version": "0.1", "id": "truncated"'
    )

    result = _run_validator_script(content_root)

    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr
    assert result.stderr == ""
    offending = [line for line in result.stdout.splitlines() if "truncated.json" in line]
    assert len(offending) == 1
    assert offending[0].startswith("benchmarks/manifests/truncated.json:<parse>: not valid JSON: ")


def test_validator_script_passes_on_a_sound_content_directory(tmp_path: Path) -> None:
    content_root = _content_root_with(tmp_path, example=_example())

    result = _run_validator_script(content_root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["valid: benchmarks/manifests/example.json"]


def test_validator_script_says_where_it_looked_when_it_finds_nothing(tmp_path: Path) -> None:
    """The likeliest failure is now a missing content directory rather than a bad manifest,
    and 'no manifests found' without a path sends the reader looking in the repository."""
    (tmp_path / "benchmarks" / "manifests").mkdir(parents=True)

    result = _run_validator_script(tmp_path)

    assert result.returncode == 1
    assert "RPG_CHRONICLE_HOME" in result.stdout
    assert str(tmp_path) in result.stdout


def test_a_relative_content_root_still_accepts_its_own_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RPG_CHRONICLE_HOME may be relative, and a comparison has to resolve both sides.

    The fingerprint path is resolved before the containment check. Comparing a resolved
    absolute path against an unresolved relative root never matches, so every valid
    fingerprint would be reported as escaping the content directory - a rejection that
    looks like a path-traversal finding and is really a bug in the check.
    """
    content_root = tmp_path / "content"
    manifests = content_root / "benchmarks" / "manifests"
    manifests.mkdir(parents=True)
    manifest = _example()
    del manifest["source"]["media_sha256"]
    manifest["source"]["content_fingerprint"] = _fingerprint_in(content_root)
    _write(manifests, manifest)

    monkeypatch.chdir(tmp_path)
    # Called directly, with a relative root. Going through validate_manifest_dir would not
    # exercise this: it resolves the root before _fingerprint_errors sees it, so the test
    # would pass whether or not the guard below resolves its own side.
    errors = validator_script._fingerprint_errors(
        manifest["source"]["content_fingerprint"], Path("content")
    )

    assert errors == [], errors
