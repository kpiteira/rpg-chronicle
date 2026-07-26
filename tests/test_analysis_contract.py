"""The contract every AnalysisProvider must satisfy.

When a real model-backed provider is added, register it in PROVIDERS and it inherits this
suite. A provider that cannot pass these tests cannot be trusted to feed the review
package, regardless of how good its prose looks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rpg_chronicle.analysis.provider import ModelAnalysisProvider
from rpg_chronicle.model import TranscriptTurn, UnsupportedEvidenceError, evidence_for
from rpg_chronicle.providers import FixtureAnalysisProvider, FixtureTranscriptProvider

from .fake_backend import FakeBackend

FIXTURE = Path(__file__).parents[1] / "benchmarks" / "fixtures" / "r0_synthetic_session.json"

PROVIDERS = [
    pytest.param(lambda: FixtureAnalysisProvider(FIXTURE), id="fixture-analysis"),
    # The model-backed provider inherits this suite, driven through a fake backend so
    # the contract is checked without a vendor. A real backend changes what the model
    # says, not which of these properties must hold.
    pytest.param(lambda: ModelAnalysisProvider(FakeBackend()), id="model-analysis"),
]


@pytest.fixture
def turns() -> list[TranscriptTurn]:
    return FixtureTranscriptProvider().transcribe(FIXTURE).turns


@pytest.mark.parametrize("make_provider", PROVIDERS)
def test_provider_returns_a_summary_and_at_least_one_scene(make_provider, turns):
    result = make_provider().analyze(turns)
    assert result.summary.strip()
    assert result.scenes


@pytest.mark.parametrize("make_provider", PROVIDERS)
def test_provider_cites_only_turns_it_was_given(make_provider, turns):
    result = make_provider().analyze(turns)
    known = {turn.id for turn in turns}
    for claim in list(result.scenes) + list(result.review_questions):
        assert set(claim.evidence.turn_ids) <= known


@pytest.mark.parametrize("make_provider", PROVIDERS)
def test_provider_declares_confidence_and_consequence_on_questions(make_provider, turns):
    result = make_provider().analyze(turns)
    for question in result.review_questions:
        assert 0.0 <= question.confidence <= 1.0
        assert question.consequence in {"low", "medium", "high"}


@pytest.mark.parametrize("make_provider", PROVIDERS)
def test_provider_adds_no_nondeterminism_of_its_own(make_provider, turns):
    """Same input, same *provider* behaviour — which is not the same as same output.

    Read this carefully for each provider, because the two cases prove different
    things and conflating them would overstate the second:

    - For the fixture provider this is end-to-end determinism. It replays a file.
    - For the model provider it is determinism **of the provider layer only**, because
      the backend underneath is a deterministic double. A real backend is not
      deterministic and `docs/DECISIONS.md` D-009 says so, which is why no test in
      this repository asserts generated text. What this pins is narrower and still
      worth pinning: the provider does not shuffle claims, does not depend on set or
      dict iteration order, and does not vary with the clock. If it did, two runs over
      one transcript would order the review queue differently and the operator would
      have no way to tell that from the model changing its mind.
    """
    first = make_provider().analyze(turns)
    second = make_provider().analyze(turns)
    assert [scene.evidence.turn_ids for scene in first.scenes] == [
        scene.evidence.turn_ids for scene in second.scenes
    ]
    assert [question.issue for question in first.review_questions] == [
        question.issue for question in second.review_questions
    ]


def test_evidence_construction_rejects_hallucinated_turn_ids(turns):
    turns_by_id = {turn.id: turn for turn in turns}
    with pytest.raises(UnsupportedEvidenceError):
        evidence_for(turns_by_id, ["turn-999"])


def test_evidence_construction_rejects_uncited_claims(turns):
    turns_by_id = {turn.id: turn for turn in turns}
    with pytest.raises(UnsupportedEvidenceError):
        evidence_for(turns_by_id, [])
