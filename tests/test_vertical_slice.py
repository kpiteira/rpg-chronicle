"""Structural tests for the vertical slice.

These assert pipeline invariants that must hold for *any* provider. They deliberately do
not assert fixture summary text: with a fixture analysis provider that would only prove
that JSON was copied through, and would still pass if the analysis stage were deleted.
Analysis quality is measured in benchmarks, not asserted here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpg_chronicle.pipeline import run_pipeline
from rpg_chronicle.providers import FixtureAnalysisProvider, FixtureTranscriptProvider

FIXTURE = Path(__file__).parents[1] / "benchmarks" / "fixtures" / "r0_synthetic_session.json"


@pytest.fixture
def session_and_package(tmp_path):
    session = run_pipeline(
        FIXTURE,
        tmp_path,
        FixtureTranscriptProvider(),
        FixtureAnalysisProvider(FIXTURE),
        session_id="test-session",
    )
    package = json.loads((tmp_path / "test-session" / "review-package.json").read_text())
    return session, package


def test_slice_reaches_review_ready(session_and_package):
    session, package = session_and_package
    assert session.status == "review_ready"
    assert session.turns and session.scenes and session.summary
    assert package["summary"] == session.summary


def test_every_claim_cites_turns_present_in_the_session(session_and_package):
    session, _ = session_and_package
    known = {turn.id for turn in session.turns}
    claims = list(session.scenes) + list(session.review_questions)
    assert claims, "the slice must produce at least one evidence-bearing claim"
    for claim in claims:
        assert claim.evidence.turn_ids, f"{claim.id} cites no evidence"
        assert set(claim.evidence.turn_ids) <= known, f"{claim.id} cites unknown turns"


def test_evidence_spans_match_the_cited_turns(session_and_package):
    session, _ = session_and_package
    turns_by_id = {turn.id: turn for turn in session.turns}
    for claim in list(session.scenes) + list(session.review_questions):
        cited = [turns_by_id[turn_id] for turn_id in claim.evidence.turn_ids]
        assert claim.evidence.start_ms == min(turn.start_ms for turn in cited)
        assert claim.evidence.end_ms == max(turn.end_ms for turn in cited)


def test_review_package_records_that_analysis_is_declared_truth(session_and_package):
    _, package = session_and_package
    assert package["provenance"]["analysis_is_declared_truth"] is True
    assert package["provenance"]["analysis_provider"] == "fixture-analysis"


def test_attention_queue_offers_a_bounded_action_set(session_and_package):
    _, package = session_and_package
    for item in package["needs_attention"]:
        assert item["actions"] == ["accept", "correct", "defer", "irrelevant"]
        assert 0.0 <= item["confidence"] <= 1.0
        assert item["why_it_matters"]


def test_resume_does_not_repeat_completed_stages(tmp_path):
    class CountingTranscriber(FixtureTranscriptProvider):
        calls = 0

        def transcribe(self, source):
            type(self).calls += 1
            return super().transcribe(source)

    class CountingAnalyzer(FixtureAnalysisProvider):
        calls = 0

        def analyze(self, turns):
            type(self).calls += 1
            return super().analyze(turns)

    transcriber = CountingTranscriber()
    analyzer = CountingAnalyzer(FIXTURE)

    run_pipeline(FIXTURE, tmp_path, transcriber, analyzer, session_id="resume")
    resumed = run_pipeline(FIXTURE, tmp_path, transcriber, analyzer, session_id="resume")

    assert resumed.status == "review_ready"
    assert CountingTranscriber.calls == 1
    assert CountingAnalyzer.calls == 1
