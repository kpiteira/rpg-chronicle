"""The long-form fixture is committed as a plan plus a generator, so both are tested.

What these tests assert is that the fixture is reproducible, is the size it claims to
be, and still contains the long-range structure it was authored to contain. What they
deliberately do not assert is anything about a model's output on it: whether the
planted callback was captured is a measurement reported in `docs/ANALYSIS.md`, not a
test. A test asserting that a summary mentions a bell clapper would pass by restating
the fixture and would prove nothing, which is the tautology `agents/goal-validator.md`
rejects.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PLAN_PATH = ROOT / "benchmarks" / "fixtures" / "long_session_plan.json"
GENERATOR_PATH = ROOT / "scripts" / "generate_long_session.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_long_session", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator()


@pytest.fixture(scope="module")
def plan() -> dict:
    return json.loads(PLAN_PATH.read_text())


@pytest.fixture(scope="module")
def fixture(generator, plan) -> dict:
    return generator.generate(plan)


def test_generation_is_deterministic(generator, plan):
    """Reproducibility is the whole reason the fixture is not committed literally."""
    first = json.dumps(generator.generate(plan), sort_keys=True)
    second = json.dumps(generator.generate(plan), sort_keys=True)
    assert first == second


def test_the_fixture_reaches_four_hour_scale(generator, fixture):
    stats = generator.summarize(fixture)
    assert 3.75 <= stats["duration_hours"] <= 4.25, stats
    # Thirty-odd thousand words is a real session's worth of speech. A fixture that
    # merely claimed four hours of timestamps over a page of text would measure
    # nothing about cost.
    assert stats["words"] > 25_000, stats
    assert stats["turns"] > 1_000, stats


def test_turns_are_ordered_non_overlapping_and_uniquely_identified(fixture):
    turns = fixture["engine_output"]["turns"]
    ids = [turn["id"] for turn in turns]
    assert len(ids) == len(set(ids))
    for previous, following in itertools.pairwise(turns):
        assert previous["end_ms"] <= following["start_ms"]
        assert following["end_ms"] > following["start_ms"]


def test_every_turn_is_attributed_to_a_declared_speaker(fixture, plan):
    declared = set(plan["speakers"])
    speakers = {turn["physical_speaker"] for turn in fixture["engine_output"]["turns"]}
    assert speakers <= declared, speakers - declared


def test_the_fixture_carries_no_declared_analysis_truth(fixture):
    """There is nothing to replay, which is the point.

    A long fixture with an `expected_analysis` block would invite exactly the
    tautology this repository has already been caught by once.
    """
    assert "expected_analysis" not in fixture
    assert fixture["provenance"]["is_declared_truth"] is False


def test_the_fixture_declares_itself_synthetic(fixture):
    assert fixture["provenance"]["kind"] == "synthetic"
    assert fixture["session"]["recording"].startswith("synthetic://")


def test_the_planted_callback_spans_most_of_the_session(fixture):
    """The plant is only a test of long-range structure if it is actually long-range.

    A callback planted twenty minutes before its payoff would be caught by a model
    that never looks further back than one window, and would prove nothing.
    """
    turns = fixture["engine_output"]["turns"]
    total = turns[-1]["end_ms"]
    planted = [turn for turn in turns if "shaped like one" in turn["text"]]
    payoff = [turn for turn in turns if "That was the clapper" in turn["text"]]
    assert planted and payoff, "the clapper plant and its payoff must both be present"
    gap = payoff[0]["start_ms"] - planted[0]["end_ms"]
    assert gap > total * 0.7, f"only {gap / 3_600_000:.2f}h between plant and payoff"


def test_the_two_names_for_one_entity_are_never_linked_in_the_transcript(fixture):
    """If any single turn named both, the fixture would test string matching.

    The alias is discoverable only by noticing that both are owed a tithe at the same
    ford for the same sixty years. That is the inference worth measuring.
    """
    turns = fixture["engine_output"]["turns"]
    early = [turn for turn in turns if "Weir Mother" in turn["text"]]
    late = [turn for turn in turns if "Anhalla" in turn["text"]]
    assert early and late

    for turn in turns:
        both = "Weir Mother" in turn["text"] and "Anhalla" in turn["text"]
        assert not both, f"{turn['id']} names both aliases, which gives the answer away"

    assert max(turn["end_ms"] for turn in early) < min(turn["start_ms"] for turn in late)


def test_one_speaker_voices_more_than_one_character(fixture, plan):
    """Speaker/character separation needs a case where the mapping is not one to one."""
    assert "Tovald" in json.dumps(plan["beats"])
    assert "Piet" in json.dumps(plan["beats"])
    turns = fixture["engine_output"]["turns"]
    assert any("Piet" in turn["text"] for turn in turns)


def test_the_planted_structure_travels_with_the_fixture(fixture):
    """Whoever measures against this fixture needs to know what was planted in it."""
    planted = {item["id"] for item in fixture["planted_structure"]}
    assert {"callback-clapper", "alias-weir-mother"} <= planted
    for item in fixture["planted_structure"]:
        assert item["description"] and item["kind"]


def test_a_plan_naming_an_unknown_speaker_is_rejected(generator, plan):
    broken = json.loads(json.dumps(plan))
    broken["beats"][0]["lines"][0][0] = "speaker-99"
    with pytest.raises(generator.PlanError, match="unknown speaker"):
        generator.generate(broken)


def test_a_plan_naming_an_unknown_filler_theme_is_rejected(generator, plan):
    broken = json.loads(json.dumps(plan))
    broken["beats"][0]["filler_theme"] = "nonexistent"
    with pytest.raises(generator.PlanError, match="unknown filler theme"):
        generator.generate(broken)


def test_filler_variation_never_alters_words(generator):
    """Only digits move. A variation that changed words would rewrite the story."""
    original = "That's a 19 to hit for 12 damage at 60 feet in the year 1874."
    varied = generator._vary(original, step=3)
    assert varied != original
    words = [token for token in varied.split() if not any(ch.isdigit() for ch in token)]
    baseline = [token for token in original.split() if not any(ch.isdigit() for ch in token)]
    assert words == baseline
    # Distances and years are left alone; only small numbers move.
    assert "60" in varied and "1874" in varied
