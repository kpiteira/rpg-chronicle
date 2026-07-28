"""Tests for the scoring harness.

Two things these tests deliberately do not do.

They do not assert that the fixture manifest contains what the fixture manifest contains.
`docs/GOAL_RULES.md` R2 and the goal validator's tautology check both name that as the
failure mode, and a harness is the worst place for it: a scorer that returned a constant
would satisfy every such assertion.

They do not need a content directory. `benchmarks/fixtures/scoring/` is invented material
with nobody's speech in it, which is what lets the suite run in CI under the rule that
keeps real manifests and answer keys out of the repository.

The load-bearing test is `test_degradations_move_only_the_dimensions_they_damage`. It
compares scores across sessions that differ in one deliberate way each, and asserts both
directions: the damaged dimension moves, and the undamaged ones do not. A harness that
returned a plausible number for any input fails it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rpg_chronicle.scoring import (
    ManifestNotFoundError,
    SessionNotFoundError,
    contamination,
    load_manifest,
    load_session,
    render,
    score,
)
from rpg_chronicle.scoring.match import label_matches, mentions

FIXTURES = Path(__file__).resolve().parents[1] / "benchmarks/fixtures/scoring"
MANIFEST = FIXTURES / "manifest.json"

VARIANTS = ("baseline", "turns-removed", "entity-renamed", "unsupported-claim")

#: The seven things `docs/MILESTONES.md` makes M2 conditional on. Written out here rather
#: than imported from the harness, so that dropping a dimension from the harness fails
#: this test instead of quietly redefining what M2 asked for.
M2_CRITERIA = {
    "plot/entity capture",
    "unsupported claims",
    "surfaced errors",
    "time",
    "memory",
    "question count",
    "review burden",
}


def run(variant: str, run_report: dict | None = None) -> dict:
    session_dir = FIXTURES / f"session-{variant}"
    return score(load_manifest(str(MANIFEST)), session_dir, load_session(session_dir), run_report)


def metric(report: dict, dimension: str, key: str):
    for entry in report["dimensions"]:
        if entry["name"] == dimension:
            return entry.get("value", {}).get(key)
    raise AssertionError(f"no dimension {dimension} in report")


def dimension(report: dict, name: str) -> dict:
    return next(entry for entry in report["dimensions"] if entry["name"] == name)


# --------------------------------------------------------------------------- coverage


def test_every_criterion_m2_names_is_addressed():
    report = run("baseline")
    assert {entry["criterion"] for entry in report["dimensions"]} == M2_CRITERIA


def test_an_unmeasurable_dimension_names_the_input_it_is_missing():
    """A dimension that cannot be scored is a first-class outcome, not a zero.

    The assertion is on substance rather than presence: a `missing` field saying "not
    available" would satisfy a check that the key exists, and would tell the next agent
    nothing about what to build.
    """
    report = run("baseline")
    unmeasurable = [entry for entry in report["dimensions"] if not entry["measured"]]
    assert unmeasurable, "the fixture run has no run report, so time and memory cannot be measured"
    for entry in unmeasurable:
        assert "value" not in entry, f"{entry['name']} is unmeasured and must carry no value"
        assert len(entry["missing"]) > 80, f"{entry['name']} does not say what is missing"


def test_memory_stays_unmeasurable_and_time_becomes_measurable_with_a_run_report():
    """Supplying the input a dimension named must actually close it.

    Otherwise `missing` is a decoration: it would name something that changes nothing.
    """
    without = run("baseline")
    assert dimension(without, "processing_time")["measured"] is False

    with_report = run("baseline", {"wall_clock_s": 120.0, "max_questions": 12})
    assert dimension(with_report, "processing_time")["measured"] is True
    assert metric(with_report, "processing_time", "realtime_factor") == 5.0
    assert metric(with_report, "question_count", "cap_in_force") == 12
    # Time arrived; memory did not, because no report this repository writes carries it.
    assert dimension(with_report, "peak_memory")["measured"] is False

    with_memory = run("baseline", {"wall_clock_s": 120.0, "peak_rss_bytes": 2 * 1048576})
    assert dimension(with_memory, "peak_memory")["measured"] is True
    assert metric(with_memory, "peak_memory", "peak_rss_mib") == 2.0


# ---------------------------------------------------------------------- discrimination


def test_degradations_move_only_the_dimensions_they_damage():
    """The tautology check applied to a measurement.

    Each variant differs from the baseline in exactly one deliberate way. If the harness
    measured nothing, every column would be identical; if it measured indiscriminately,
    every column would move together. Both the moves and the non-moves are asserted.
    """
    reports = {variant: run(variant) for variant in VARIANTS}
    base = reports["baseline"]

    # Turns removed, with the scene and entity that came from them: capture falls on
    # both axes, and nothing about fabricated or unsupported claims changes.
    lost = reports["turns-removed"]
    assert metric(lost, "entity_capture", "recall_by_name") < metric(base, "entity_capture", "recall_by_name")
    assert metric(lost, "plot_capture", "coverage_upper_bound") < metric(base, "plot_capture", "coverage_upper_bound")
    assert metric(lost, "unsupported_claims", "negative_control_hits") == metric(base, "unsupported_claims", "negative_control_hits")
    assert metric(lost, "unsupported_claims", "entities_absent_from_cited_turns") == 0

    # One entity renamed: entity capture falls and the renamed entity is also detected as
    # unsupported, because its name is in none of the turns it cites. Plot capture must
    # not move -- no scene was touched -- and neither must the negative controls.
    renamed = reports["entity-renamed"]
    assert metric(renamed, "entity_capture", "recall_by_name") < metric(base, "entity_capture", "recall_by_name")
    assert metric(renamed, "unsupported_claims", "entities_absent_from_cited_turns") == 1
    assert metric(renamed, "plot_capture", "coverage_upper_bound") == metric(base, "plot_capture", "coverage_upper_bound")
    assert metric(renamed, "unsupported_claims", "negative_control_hits") == 0
    assert metric(renamed, "question_count", "review_questions") == metric(base, "question_count", "review_questions")

    # A claim added that the excerpt does not support: the negative control fires, and
    # capture does not move, because nothing that was captured stopped being captured.
    claimed = reports["unsupported-claim"]
    assert metric(claimed, "unsupported_claims", "negative_control_hits") == 1
    assert metric(claimed, "entity_capture", "recall_by_name") == metric(base, "entity_capture", "recall_by_name")
    assert metric(claimed, "plot_capture", "coverage_upper_bound") == metric(base, "plot_capture", "coverage_upper_bound")

    # Every degradation is an error the harness detected, and in every case the run said
    # nothing about it -- which is the dimension M2 calls "surfaced errors" doing its job.
    for variant in ("turns-removed", "entity-renamed", "unsupported-claim"):
        report = reports[variant]
        assert metric(report, "surfaced_errors", "detected_errors") > metric(base, "surfaced_errors", "detected_errors")
        assert metric(report, "surfaced_errors", "unsurfaced") > metric(base, "surfaced_errors", "unsurfaced")


def test_the_baseline_is_neither_perfect_nor_empty():
    """A fixture that scores 0 or 1 everywhere cannot show a degradation moving.

    This guards the fixture rather than the harness, and it is the reason the fixture has
    a genuine miss and a genuine gap built into it.
    """
    recall = metric(run("baseline"), "entity_capture", "recall_by_name")
    coverage = metric(run("baseline"), "plot_capture", "coverage_upper_bound")
    assert 0 < recall < 1
    assert 0 < coverage < 1


def test_a_question_covering_a_missed_target_counts_as_surfaced():
    """The baseline's one miss is asked about, so the run is credited for surfacing it.

    Paired with the degradation test above, where the new errors are not asked about,
    this shows the dimension moving in both directions rather than reporting a constant.
    """
    base = run("baseline")
    assert metric(base, "surfaced_errors", "detected_errors") == 1
    assert metric(base, "surfaced_errors", "unsurfaced") == 0


# ---------------------------------------------------------------------- contamination


def test_a_contaminated_run_is_withheld_and_its_numbers_do_not_appear():
    """`refuse or mark` is implemented as refuse, and the refusal has to be complete.

    A value printed beside a warning is still a value somebody quotes, so the test looks
    for the number in the rendered text, not merely for the presence of a warning.
    """
    report = run("contaminated")
    assert report["verdict"] == "withheld"
    assert report["contamination"]["state"] == "contaminated"
    assert report["contamination"]["matched"] == ["example-engine-v1"]

    withheld = [entry for entry in report["dimensions"] if entry.get("contaminated")]
    assert {entry["name"] for entry in withheld} == {
        "entity_capture",
        "plot_capture",
        "unsupported_claims",
        "surfaced_errors",
    }
    for entry in withheld:
        assert "value" not in entry
        assert entry["withheld_because"]

    clean_value = metric(run("baseline"), "entity_capture", "recall_by_name")
    text = render(report)
    assert str(clean_value) not in text
    # The dimensions that never read the answer key are unaffected and still reported.
    assert metric(report, "question_count", "review_questions") == 1


def test_an_unidentifiable_engine_is_refused_rather_than_assumed_clean():
    """The direction of failure that matters.

    Treating "I could not tell which engine ran" as "not contaminated" produces exactly
    the clean-looking contaminated score the rule exists to stop.
    """
    session_dir = FIXTURES / "session-baseline"
    session = copy.deepcopy(load_session(session_dir))
    session["provenance"] = {}
    session["processor_artifacts"] = {}

    report = score(load_manifest(str(MANIFEST)), session_dir, session)
    assert report["contamination"]["state"] == "undetermined"
    assert report["verdict"] == "withheld"


def test_declared_truth_is_refused_for_a_different_reason_than_contamination():
    """Fixture-provider output is never reported as a result.

    It is not contamination in the annotation sense -- no engine wrote the answer key --
    so it gets its own state, and the explanation has to say which failure this is.
    """
    session_dir = FIXTURES / "session-baseline"
    session = copy.deepcopy(load_session(session_dir))
    session["provenance"]["analysis_is_declared_truth"] = True

    report = score(load_manifest(str(MANIFEST)), session_dir, session)
    assert report["contamination"]["state"] == "declared_truth"
    assert report["verdict"] == "withheld"
    assert "fixture" in report["contamination"]["explanation"]


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        # The real shape: a manifest names engine and model, a session records the engine
        # in one field and the model file in another, and the two strings never match.
        ("whisper.cpp large-v3-turbo", "contaminated"),
        # A different implementation is not caught. `cpp` contradicts `openai`.
        ("openai-whisper medium.en", "clean"),
        # A different size of the same implementation is refused rather than cleared, and
        # this is over-refusal by design: the session records the bare string `whisper.cpp`
        # alongside its model, and that string alone is consistent with any whisper.cpp
        # model. The consequence is worth knowing -- no whisper.cpp run is ever cleared
        # against a manifest naming any whisper.cpp model -- and the safe direction.
        ("whisper.cpp small.en", "undetermined"),
        # Container format, not an engine, and filtered as noise. Left in, a manifest
        # entry of `ggml` would condemn every whisper.cpp run ever made.
        ("ggml", "clean"),
    ],
)
def test_contamination_matching_separates_engines_that_differ(tmp_path, declared, expected):
    """Exercised through `assess`, so it describes the harness rather than a copy of it.

    An earlier version of this test re-derived the subset expression inside the test body
    and asserted that against itself, which would have passed with `assess` deleted.
    """
    session = write_session(tmp_path, real_artifact())
    assert contamination.assess(session, tmp_path, [declared]).state == expected


def real_artifact(with_model: bool = True) -> dict:
    """The shape `SpeechTranscriptProvider` actually writes.

    Reproduced from the artifact of a real whisper.cpp run rather than invented, because
    the nesting is the whole point: the provider records its own composed name at the top
    level and the recognizer's engine and model one level down, under `recognition`.
    """
    recognition = {"engine": "whisper.cpp", "threads": 12, "segment_count": 302}
    if with_model:
        recognition["model_file"] = "ggml-large-v3-turbo.bin"
    return {
        "provider": "whisper.cpp (no diarization)",
        "output_kind": "model output",
        "recognition": recognition,
    }


def write_session(tmp_path: Path, artifact: dict) -> dict:
    (tmp_path / "processor-native").mkdir(exist_ok=True)
    (tmp_path / "processor-native/transcript.json").write_text(json.dumps(artifact))
    return {
        "provenance": {"transcript_provider": "whisper.cpp (no diarization)"},
        "processor_artifacts": {"transcript": "processor-native/transcript.json"},
    }


def test_engine_identity_reads_a_model_nested_inside_the_native_artifact(tmp_path):
    """Provenance alone is not enough, and neither is the artifact's top level.

    Canonical provenance records the provider's composed name and never which whisper
    model ran; the model sits two levels into the artifact. This is not hypothetical --
    a top-level-only read reported the first real run against this harness as clean while
    it was being scored against truth its own engine had written.
    """
    session = write_session(tmp_path, real_artifact())
    identity = contamination.engine_identity(session, tmp_path)
    assert "turbo" in identity.tokens

    verdict = contamination.assess(session, tmp_path, ["whisper.cpp large-v3-turbo"])
    assert verdict.state == "contaminated"
    assert verdict.matched == ["whisper.cpp large-v3-turbo"]


def test_an_engine_known_to_family_but_not_to_model_is_refused(tmp_path):
    """The failure this harness must not have: agreeing so far as it can see, and cleared.

    Everything the session records -- `whisper.cpp` -- is consistent with the declared
    `whisper.cpp large-v3-turbo`. What is missing is the model, which is the only thing
    that could rule the contamination out.
    """
    session = write_session(tmp_path, real_artifact(with_model=False))
    verdict = contamination.assess(session, tmp_path, ["whisper.cpp large-v3-turbo"])
    assert verdict.state == "undetermined"
    assert "settle which model ran" in verdict.explanation


def test_a_different_engine_is_not_swept_up_by_that_refusal(tmp_path):
    """Over-refusal is a real cost: a check that fires on everything gets ignored.

    `whisper.cpp` is not consistent with `openai-whisper medium.en` -- the implementation
    token contradicts it -- so this stays clean rather than becoming undetermined.
    """
    session = write_session(tmp_path, real_artifact(with_model=False))
    verdict = contamination.assess(session, tmp_path, ["openai-whisper medium.en"])
    assert verdict.state == "clean"


# ------------------------------------------------------------------------- time basis


def test_anchors_are_read_against_a_clipped_run_rather_than_scored_as_misses():
    """A session over a clipped excerpt has a clock offset from the manifest's.

    Reading anchors on the wrong hypothesis would report a confident zero, which looks
    exactly like a run that captured nothing.
    """
    session_dir = FIXTURES / "session-baseline"
    session = copy.deepcopy(load_session(session_dir))
    manifest = load_manifest(str(MANIFEST))
    shifted = copy.deepcopy(manifest.document)
    shifted["excerpt"]["start_ms"] = 1_000_000
    shifted["excerpt"]["end_ms"] = 1_600_000
    shifted["source"]["episode_duration_ms"] = 2_000_000
    for group in ("important_entities", "important_events"):
        for target in shifted["truth"][group]:
            target["anchor_ms"] += 1_000_000
    for thread in shifted["truth"]["threads"]:
        thread["first_anchor_ms"] += 1_000_000
        thread["last_anchor_ms"] += 1_000_000

    from rpg_chronicle.scoring.manifest import Manifest

    report = score(Manifest(path=MANIFEST, document=shifted), session_dir, session)
    assert report["time_basis"]["hypothesis"] == "excerpt_relative"
    assert report["time_basis"]["offset_ms"] == 1_000_000
    # And the scores match the unshifted run, because the same audio was described.
    assert metric(report, "entity_capture", "recall_anchor_corroborated") == metric(
        run("baseline"), "entity_capture", "recall_anchor_corroborated"
    )


def misaligned_session() -> dict:
    """The baseline run, moved to a clock the manifest's anchors do not address."""
    session = copy.deepcopy(load_session(FIXTURES / "session-baseline"))
    for turn in session["turns"]:
        turn["start_ms"] += 9_000_000
        turn["end_ms"] += 9_000_000
    for group in ("scenes", "entities", "threads", "review_questions"):
        for item in session[group]:
            item["evidence"]["start_ms"] += 9_000_000
            item["evidence"]["end_ms"] += 9_000_000
    return session


def test_no_anchor_derived_figure_survives_a_clock_the_anchors_do_not_address():
    """Every anchor-derived figure, not just the first one that needed the guard.

    An anchor read against the wrong clock returns zero rather than failing, and a zero
    here is indistinguishable from a run that captured nothing. This asserts each of the
    three computations that read an anchor -- event coverage, entity anchor corroboration,
    and whether a review question covers a missed target -- rather than one of them, which
    is how the gap got shipped the first time.
    """
    session_dir = FIXTURES / "session-baseline"
    report = score(load_manifest(str(MANIFEST)), session_dir, misaligned_session())
    assert report["time_basis"]["anchors_inside_session"] == 0

    plot = dimension(report, "plot_capture")
    assert plot["measured"] is False
    assert "not describing the same span" in plot["missing"]

    # Accusing the run of not surfacing an error, on evidence that cannot be read, is
    # worse than saying nothing.
    errors = dimension(report, "surfaced_errors")
    assert errors["measured"] is False
    assert "not describing the same span" in errors["missing"]

    # Entity capture keeps the half of itself that reads no clock, and the anchored half
    # is absent rather than zero.
    entities = dimension(report, "entity_capture")
    assert entities["measured"] is True
    assert entities["value"]["recall_by_name"] == metric(
        run("baseline"), "entity_capture", "recall_by_name"
    )
    assert "recall_anchor_corroborated" not in entities["value"]
    assert "anchor_corroborated" not in entities["value"]
    assert "not describing the same span" in entities["value"]["anchor_corroboration_unavailable"]
    for bucket in entities["value"]["by_basis"].values():
        assert "anchor_corroborated" not in bucket


def test_the_aligned_case_still_reports_every_anchor_derived_figure():
    """The guard must not be a blanket suppression that quietly hides working numbers."""
    report = run("baseline")
    entities = dimension(report, "entity_capture")
    assert entities["value"]["recall_anchor_corroborated"] is not None
    assert "anchor_corroboration_unavailable" not in entities["value"]
    assert dimension(report, "plot_capture")["measured"] is True
    assert dimension(report, "surfaced_errors")["measured"] is True


# ---------------------------------------------------------------------------- matching


@pytest.mark.parametrize(
    ("label", "candidate", "expected"),
    [
        ("Brindle", "Brindle", True),
        # A name wrapped in a description, which is how annotators write labels.
        ("Corvath, the ferryman the debt is owed to", "Corvath", True),
        # And the reverse: a model that attaches a role to the name.
        ("Alder", "Alder the cartwright", True),
        ("The Sunken Mill", "Sunken Mill", True),
        # Articles are noise on both sides.
        ("The tower", "tower", True),
        # A different name is a different name.
        ("Brindle", "Bramble", False),
        # Too short to distinguish; matching on it would inflate every recall.
        ("Alder", "Al", False),
        # A shared word is not a shared referent.
        ("The Sunken Mill", "The Sunken Ship", False),
    ],
)
def test_label_matching_accepts_the_shapes_annotators_write_and_rejects_near_misses(
    label, candidate, expected
):
    assert label_matches(label, candidate) is expected


def test_a_negative_control_matches_whole_words_only():
    assert mentions("They spoke to Kaervek at dusk", "Kaervek") is True
    assert mentions("The blade moved mercurially", "Mercurial") is False
    # Two tokens of a control appearing apart do not satisfy it.
    assert mentions("Maria left. Later, mercurial weather set in.", "Maria Mercurial") is False


# ------------------------------------------------------------------------- resolution


def test_a_missing_content_directory_produces_an_instruction_not_a_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_CHRONICLE_HOME", str(tmp_path))
    with pytest.raises(ManifestNotFoundError) as error:
        load_manifest("hiddengrid-swc-ep044-tower-play")
    assert "RPG_CHRONICLE_HOME" in str(error.value)


def test_a_directory_that_is_not_a_session_says_what_to_point_at(tmp_path):
    with pytest.raises(SessionNotFoundError) as error:
        load_session(tmp_path)
    assert "canonical-session.json" in str(error.value)


def test_the_rendered_report_carries_a_basis_for_every_number_it_prints():
    """The report is built so a number cannot be read alone.

    `docs/EVALUATION.md` states that a number with no stated basis is worse than no
    number; this is that rule as a check on the artifact rather than as a paragraph.
    """
    report = run("baseline", {"wall_clock_s": 90.0})
    # Compared with whitespace collapsed, because the renderer wraps to a terminal width
    # and the check is that the sentence survives, not how it was broken across lines.
    text = " ".join(render(report).split())
    measured = [entry for entry in report["dimensions"] if entry["measured"]]
    assert measured
    for entry in measured:
        assert " ".join(entry["basis"].split()) in text
        assert " ".join(entry["caveat"].split()) in text
