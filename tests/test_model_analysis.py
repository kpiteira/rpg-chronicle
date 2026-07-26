"""Behaviour of the model-backed provider, driven through a fake backend.

Nothing here reaches a model. These tests assert the invariants that must hold for
*any* backend, per D-009: evidence resolves, the queue is bounded, decomposition
engages on budget, a missing credential stops the run before anything is written. The
quality of a real model's prose is measured in `docs/ANALYSIS.md`, not asserted here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpg_chronicle.analysis.backend import (
    BackendCredentialError,
    BackendUnavailableError,
    ModelResponse,
    TokenUsage,
)
from rpg_chronicle.analysis.decompose import TokenBudget
from rpg_chronicle.analysis.provider import (
    AnalysisFormatError,
    ModelAnalysisProvider,
    TurnIdResolver,
)
from rpg_chronicle.model import TranscriptTurn, UnsupportedEvidenceError
from rpg_chronicle.pipeline import run_pipeline
from rpg_chronicle.providers import FixtureTranscriptProvider

from .fake_backend import FakeBackend, ScriptedBackend

FIXTURE = Path(__file__).parents[1] / "benchmarks" / "fixtures" / "r0_synthetic_session.json"


@pytest.fixture
def turns() -> list[TranscriptTurn]:
    return FixtureTranscriptProvider().transcribe(FIXTURE).turns


def _long_turns(count: int) -> list[TranscriptTurn]:
    return [
        TranscriptTurn(
            id=f"turn-{index + 1:05d}",
            start_ms=index * 5000,
            end_ms=index * 5000 + 4000,
            text=f"Turn {index + 1}. " + "The party continues to do something. " * 12,
            physical_speaker=f"speaker-{index % 4 + 1}",
        )
        for index in range(count)
    ]


def test_provider_produces_a_review_package_through_the_pipeline(tmp_path, turns):
    provider = ModelAnalysisProvider(FakeBackend())
    session = run_pipeline(
        FIXTURE, tmp_path, FixtureTranscriptProvider(), provider, session_id="model"
    )
    package = json.loads((tmp_path / "model" / "review-package.json").read_text())

    assert session.status == "review_ready"
    assert session.summary and session.scenes
    assert package["provenance"]["analysis_provider"] == "model-analysis"
    assert package["provenance"]["analysis_is_declared_truth"] is False


def test_every_claim_resolves_and_its_span_matches_the_cited_turns(tmp_path, turns):
    """The evidence contract, asserted against generated rather than declared output.

    This fails if `evidence_for` stops resolving ids, and it fails if it stops
    computing the span from the cited turns. Deleting either check turns this test
    red, which is the property the goal asked for.
    """
    session = run_pipeline(
        FIXTURE,
        tmp_path,
        FixtureTranscriptProvider(),
        ModelAnalysisProvider(FakeBackend()),
        session_id="evidence",
    )
    turns_by_id = {turn.id: turn for turn in session.turns}
    claims = list(session.scenes) + list(session.review_questions)
    assert claims

    for claim in claims:
        assert claim.evidence.turn_ids, f"{claim.id} cites no evidence"
        cited = [turns_by_id[turn_id] for turn_id in claim.evidence.turn_ids]
        assert claim.evidence.start_ms == min(turn.start_ms for turn in cited)
        assert claim.evidence.end_ms == max(turn.end_ms for turn in cited)


def test_a_hallucinated_turn_id_fails_loudly_rather_than_being_dropped(turns):
    """A model that invents a citation must break the run, not shrink the summary.

    Skipping the offending claim would convert a diagnosable hallucination into a
    quietly incomplete record, which is the unsupported-claim failure mode
    `docs/PRODUCT.md` exists to prevent.
    """
    reply = json.dumps(
        {
            "window_summary": "A summary.",
            "scenes": [
                {
                    "title": "Invented",
                    "summary": "Cites a turn that was never in the session.",
                    "turn_ids": ["turn-404"],
                }
            ],
            "questions": [],
        }
    )
    provider = ModelAnalysisProvider(ScriptedBackend(replies=[reply]))
    with pytest.raises((AnalysisFormatError, UnsupportedEvidenceError)) as caught:
        provider.analyze(turns)
    assert "turn-404" in str(caught.value)


def test_a_window_may_not_cite_turns_from_a_different_window():
    """An id that exists elsewhere in the session is still not evidence here.

    `evidence_for` can only tell that an id exists somewhere. A window that cites a
    turn it was never shown has guessed, and the provider is stricter than the model
    layer on purpose.
    """
    turns = _long_turns(60)
    last_id = turns[-1].id
    reply = json.dumps(
        {
            "window_summary": "A summary.",
            "scenes": [
                {"title": "Reaching forward", "summary": "Cites the end.", "turn_ids": [last_id]}
            ],
            "questions": [],
        }
    )
    provider = ModelAnalysisProvider(
        ScriptedBackend(replies=[reply]),
        budget=TokenBudget(max_input_tokens=3_000, prompt_overhead_tokens=500, overlap_turns=0),
    )
    with pytest.raises(AnalysisFormatError) as caught:
        provider.analyze(turns)
    assert "absent from its excerpt" in str(caught.value)


class TestTurnIdResolution:
    """Zero-padding is tolerated; invention is not.

    Measured on the four-hour fixture: when the transcript is decomposed, Sonnet cites
    `turn-740` for a turn rendered as `turn-00740`. These tests pin the exact boundary
    between "named the right turn in the wrong format" and "made a turn up", because
    that boundary is the whole evidence contract.
    """

    def test_an_exact_id_resolves_to_itself(self):
        resolver = TurnIdResolver({"turn-00740", "turn-00741"})
        assert resolver.resolve(["turn-00740"], where="w", what="a scene") == ["turn-00740"]

    def test_a_differently_padded_id_resolves_to_the_real_one(self):
        resolver = TurnIdResolver({"turn-00740"})
        assert resolver.resolve(["turn-740"], where="w", what="a scene") == ["turn-00740"]

    def test_an_id_for_a_turn_that_does_not_exist_still_raises(self):
        resolver = TurnIdResolver({"turn-00740"})
        with pytest.raises(AnalysisFormatError, match="turn-99999"):
            resolver.resolve(["turn-99999"], where="w", what="a scene")

    def test_a_padding_variant_of_a_nonexistent_turn_still_raises(self):
        """The fallback resolves formats, never existence."""
        resolver = TurnIdResolver({"turn-00740"})
        with pytest.raises(AnalysisFormatError, match="turn-741"):
            resolver.resolve(["turn-741"], where="w", what="a scene")

    def test_an_ambiguous_canonical_form_resolves_to_nothing(self):
        """If two real ids differ only in padding, a padded citation is a coin flip."""
        resolver = TurnIdResolver({"turn-740", "turn-00740"})
        assert resolver.resolve(["turn-740"], where="w", what="a scene") == ["turn-740"]
        with pytest.raises(AnalysisFormatError):
            resolver.resolve(["turn-0740"], where="w", what="a scene")

    def test_a_non_numeric_id_is_matched_exactly_or_not_at_all(self):
        resolver = TurnIdResolver({"turn-abc"})
        assert resolver.resolve(["turn-abc"], where="w", what="a scene") == ["turn-abc"]
        with pytest.raises(AnalysisFormatError):
            resolver.resolve(["turn-abd"], where="w", what="a scene")

    def test_resolution_does_not_reach_across_window_boundaries(self):
        """A resolver built from one window cannot reach a turn in another."""
        resolver = TurnIdResolver({"turn-00001", "turn-00002"})
        with pytest.raises(AnalysisFormatError, match="turn-500"):
            resolver.resolve(["turn-500"], where="w", what="a scene")


def test_a_repadded_citation_survives_the_pipeline_and_lands_on_the_right_turn(turns):
    """End to end: the claim is kept, and its evidence points at the turn it named."""
    reply = json.dumps(
        {
            "window_summary": "A summary.",
            "scenes": [
                {"title": "A scene", "summary": "It happened.", "turn_ids": ["turn-1"]}
            ],
            "questions": [],
        }
    )
    provider = ModelAnalysisProvider(ScriptedBackend(replies=[reply]))
    result = provider.analyze(turns)
    assert result.scenes[0].evidence.turn_ids == ["turn-001"]
    assert result.scenes[0].evidence.start_ms == turns[0].start_ms


def test_the_review_queue_is_bounded_however_many_questions_come_back(turns):
    """The cap is enforced in code, not requested in the prompt.

    A model asked for at most ten questions usually returns at most ten. "Usually" is
    not a bound, and `docs/PRODUCT.md` makes capped attention a product principle.
    """
    provider = ModelAnalysisProvider(
        FakeBackend(questions_per_window=40),
        max_questions=6,
    )
    result = provider.analyze(turns)
    assert len(result.review_questions) == 6
    assert result.native_artifact["questions_before_bound"] > 6


def test_the_queue_keeps_the_most_consequential_questions_first(turns):
    provider = ModelAnalysisProvider(FakeBackend(questions_per_window=9), max_questions=3)
    result = provider.analyze(turns)
    weights = {"high": 3, "medium": 2, "low": 1}
    ordered = [weights[question.consequence] for question in result.review_questions]
    assert ordered == sorted(ordered, reverse=True)


def test_a_transcript_within_budget_is_one_request(turns):
    provider = ModelAnalysisProvider(FakeBackend())
    provider.analyze(turns)
    assert provider.cost.windows == 1
    assert provider.cost.fit_in_one_request is True
    assert provider.cost.requests == 1


def test_a_transcript_over_budget_is_decomposed_and_recombined():
    """Decomposition engages on the budget, and synthesis runs once over the windows."""
    backend = FakeBackend()
    provider = ModelAnalysisProvider(
        backend,
        budget=TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=2),
    )
    result = provider.analyze(_long_turns(200))

    assert provider.cost.windows > 1
    assert provider.cost.fit_in_one_request is False
    # One request per window, plus exactly one synthesis pass over all of them.
    assert provider.cost.requests == provider.cost.windows + 1
    assert result.summary


def test_overlapping_windows_do_not_produce_duplicate_scenes():
    provider = ModelAnalysisProvider(
        FakeBackend(),
        budget=TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=6),
    )
    result = provider.analyze(_long_turns(200))
    spans = [frozenset(scene.evidence.turn_ids) for scene in result.scenes]
    assert len(spans) == len(set(spans))


def test_the_same_scene_cited_in_a_different_order_is_still_one_scene(turns):
    """Overlap dedupe keys off the set of cited turns, not the order they were listed.

    The model re-reads the same material in the next window and has no obligation to
    sequence the ids the same way. Keying off order would let the identical scene
    through twice and put it in the review package twice.
    """
    forwards = json.dumps(
        {
            "window_summary": "A summary.",
            "scenes": [
                {
                    "title": "A scene",
                    "summary": "It happened.",
                    "turn_ids": ["turn-001", "turn-002", "turn-003"],
                },
                {
                    "title": "The same scene, listed backwards",
                    "summary": "It happened.",
                    "turn_ids": ["turn-003", "turn-002", "turn-001"],
                },
            ],
            "questions": [],
        }
    )
    result = ModelAnalysisProvider(ScriptedBackend(replies=[forwards])).analyze(turns)
    assert len(result.scenes) == 1
    # The surviving scene keeps the order it was first cited in.
    assert result.scenes[0].evidence.turn_ids == ["turn-001", "turn-002", "turn-003"]


def test_cost_is_accumulated_from_the_backend_not_estimated():
    backend = FakeBackend(input_tokens_per_request=1234, output_tokens_per_request=56)
    provider = ModelAnalysisProvider(
        backend,
        budget=TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=0),
    )
    provider.analyze(_long_turns(120))

    requests = provider.cost.requests
    assert requests > 1
    assert provider.cost.usage.input_tokens == 1234 * requests
    assert provider.cost.usage.output_tokens == 56 * requests
    assert provider.cost.wall_ms == 7 * requests


def test_a_missing_credential_produces_a_clear_error_naming_the_variable(monkeypatch):
    """The credential-absent path, exercised through the shared resolver.

    The one working backend is subscription-mediated and holds no key in the
    environment, so this is where the env-key path every future backend will reuse is
    proved.
    """
    monkeypatch.delenv("RPG_CHRONICLE_TEST_KEY", raising=False)
    provider = ModelAnalysisProvider(FakeBackend(required_env_var="RPG_CHRONICLE_TEST_KEY"))

    with pytest.raises(BackendCredentialError) as caught:
        provider.preflight()

    message = str(caught.value)
    assert "RPG_CHRONICLE_TEST_KEY" in message
    assert "not set" in message


def test_an_empty_credential_is_treated_as_missing_and_never_echoed(monkeypatch):
    monkeypatch.setenv("RPG_CHRONICLE_TEST_KEY", "   ")
    provider = ModelAnalysisProvider(FakeBackend(required_env_var="RPG_CHRONICLE_TEST_KEY"))
    with pytest.raises(BackendCredentialError) as caught:
        provider.preflight()
    assert "RPG_CHRONICLE_TEST_KEY" in str(caught.value)


def test_a_credential_value_never_appears_in_the_failure_message(monkeypatch):
    """Set-but-unusable must not become a channel for printing the secret."""
    secret = "sk-do-not-print-this-value"
    monkeypatch.setenv("RPG_CHRONICLE_TEST_KEY", secret)
    backend = FakeBackend(required_env_var="RPG_CHRONICLE_TEST_KEY", available=False)
    with pytest.raises(BackendUnavailableError) as caught:
        ModelAnalysisProvider(backend).preflight()
    assert secret not in str(caught.value)


def test_an_unavailable_backend_produces_no_review_package(tmp_path):
    """The run may get as far as transcription, but never as far as a product artifact."""
    provider = ModelAnalysisProvider(FakeBackend(available=False))
    with pytest.raises(BackendUnavailableError):
        run_pipeline(
            FIXTURE, tmp_path, FixtureTranscriptProvider(), provider, session_id="dead"
        )
    assert not (tmp_path / "dead" / "review-package.json").exists()


def test_analysis_of_an_empty_transcript_is_refused(turns):
    provider = ModelAnalysisProvider(FakeBackend())
    with pytest.raises(ValueError, match="at least one transcript turn"):
        provider.analyze([])


def _reply(scenes: list[dict], questions: list[dict] | None = None) -> str:
    return json.dumps(
        {
            "window_summary": "A summary of the excerpt.",
            "scenes": scenes,
            "questions": questions or [],
        }
    )


def _question(**overrides) -> dict:
    return {
        "issue": "Something uncertain.",
        "why_it_matters": "It reaches the campaign record.",
        "turn_ids": ["turn-001"],
        "confidence": 0.5,
        "consequence": "high",
        **overrides,
    }


_GOOD_SCENE = {"title": "A scene", "summary": "It happened.", "turn_ids": ["turn-001"]}

MALFORMED_REPLIES = {
    "not-json": "not json at all",
    # A session in which no window found a scene is a failed analysis. A single
    # *window* without one is legitimate and is tested separately below.
    "no-scenes-anywhere": _reply([]),
    "scene-without-citation": _reply([{"title": "t", "summary": "s"}]),
    "scene-without-title": _reply([{"summary": "s", "turn_ids": ["turn-001"]}]),
    "confidence-out-of-range": _reply([_GOOD_SCENE], [_question(confidence=5)]),
    "confidence-not-a-number": _reply([_GOOD_SCENE], [_question(confidence="high")]),
    "bad-consequence": _reply([_GOOD_SCENE], [_question(consequence="catastrophic")]),
    "question-without-citation": _reply([_GOOD_SCENE], [_question(turn_ids=[])]),
    "recommendation-not-a-string": _reply([_GOOD_SCENE], [_question(recommendation=7)]),
    # A malformed `questions` field must raise rather than be skipped. Iterating a
    # stray string yields characters and silently drops every question in the reply,
    # which is the "quietly shorter review queue" failure this module refuses.
    "questions-a-string": json.dumps(
        {"window_summary": "ok", "scenes": [_GOOD_SCENE], "questions": "none"}
    ),
    "questions-an-object": json.dumps(
        {"window_summary": "ok", "scenes": [_GOOD_SCENE], "questions": {"a": 1}}
    ),
    "questions-holding-a-string": json.dumps(
        {"window_summary": "ok", "scenes": [_GOOD_SCENE], "questions": ["nothing to ask"]}
    ),
    "scenes-a-string": json.dumps({"window_summary": "ok", "scenes": "one scene"}),
    "scenes-holding-a-string": json.dumps({"window_summary": "ok", "scenes": ["a scene"]}),
    "entities-a-string": json.dumps(
        {"window_summary": "ok", "scenes": [_GOOD_SCENE], "entities": "none"}
    ),
}


@pytest.mark.parametrize("reply", MALFORMED_REPLIES.values(), ids=MALFORMED_REPLIES.keys())
def test_malformed_model_output_is_rejected_rather_than_repaired(reply, turns):
    """Nothing here is patched up, defaulted, or dropped. Bad output is an error."""
    provider = ModelAnalysisProvider(ScriptedBackend(replies=[reply]))
    with pytest.raises(AnalysisFormatError):
        provider.analyze(turns)


def test_a_window_with_no_scene_does_not_abort_the_session():
    """Twenty minutes of rules argument is a real thing a recording contains.

    Demanding a story-bearing scene from every window would abort a four-hour run
    over a meal break, or invite the model to invent a scene to satisfy the schema.
    The invariant belongs at session level.
    """

    class SceneInFirstWindowOnly(FakeBackend):
        seen = 0

        def complete(self, request):
            type(self).seen += 1
            if type(self).seen == 2:
                return ModelResponse(
                    text=json.dumps(
                        {
                            "window_summary": "Rules argument and a meal break.",
                            "scenes": [],
                            "questions": [],
                        }
                    ),
                    usage=TokenUsage(input_tokens=10, output_tokens=10),
                    wall_ms=1,
                )
            return super().complete(request)

    provider = ModelAnalysisProvider(
        SceneInFirstWindowOnly(),
        budget=TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=0),
    )
    result = provider.analyze(_long_turns(120))
    assert provider.cost.windows > 2
    assert result.scenes, "scenes from the other windows must survive"


@pytest.mark.parametrize("questions", [None, []], ids=["absent", "empty"])
def test_asking_nothing_is_a_legitimate_answer(questions, turns):
    """Zero questions is a result, not malformed output.

    The strictness above must not make "I have nothing worth asking" impossible to
    say, or the queue fills with questions asked to satisfy a schema.
    """
    payload = {"window_summary": "A summary.", "scenes": [_GOOD_SCENE]}
    if questions is not None:
        payload["questions"] = questions
    provider = ModelAnalysisProvider(ScriptedBackend(replies=[json.dumps(payload)]))
    result = provider.analyze(turns)
    assert result.review_questions == []
    assert result.scenes


def test_literal_newlines_inside_a_string_are_accepted(turns):
    """Multi-paragraph summaries arrive with raw newlines in them. That is syntax.

    Tolerating it changes what counts as well-formed JSON, not what counts as a
    supported claim.
    """
    reply = (
        '{"window_summary": "First paragraph.\n\nSecond paragraph.", '
        '"scenes": [{"title": "t", "summary": "s", "turn_ids": ["turn-001"]}], '
        '"questions": []}'
    )
    provider = ModelAnalysisProvider(ScriptedBackend(replies=[reply]))
    result = provider.analyze(turns)
    assert "Second paragraph." in result.summary


class TestFormatRetry:
    """Unparseable replies are retried; unsupported claims never are."""

    _GOOD = json.dumps(
        {
            "window_summary": "A summary.",
            "scenes": [{"title": "t", "summary": "s", "turn_ids": ["turn-001"]}],
            "questions": [],
        }
    )

    def test_an_unparseable_reply_is_asked_again_and_the_retry_is_counted(self, turns):
        backend = ScriptedBackend(replies=["not json", self._GOOD])
        provider = ModelAnalysisProvider(backend)
        result = provider.analyze(turns)
        assert result.summary == "A summary."
        assert backend.calls == 2
        assert provider.cost.format_retries == 1
        # The retry was paid for, so it appears in the cost like any other request.
        assert provider.cost.requests == 2

    def test_retries_are_bounded_and_the_last_error_is_raised(self, turns):
        backend = ScriptedBackend(replies=["not json"])
        provider = ModelAnalysisProvider(backend, format_retries=2)
        with pytest.raises(AnalysisFormatError):
            provider.analyze(turns)
        assert backend.calls == 3

    def test_retrying_can_be_switched_off(self, turns):
        backend = ScriptedBackend(replies=["not json"])
        with pytest.raises(AnalysisFormatError):
            ModelAnalysisProvider(backend, format_retries=0).analyze(turns)
        assert backend.calls == 1

    def test_an_invented_citation_is_never_retried(self, turns):
        """Retrying a hallucination would be sampling until it is not caught."""
        bad = json.dumps(
            {
                "window_summary": "A summary.",
                "scenes": [{"title": "t", "summary": "s", "turn_ids": ["turn-99999"]}],
                "questions": [],
            }
        )
        backend = ScriptedBackend(replies=[bad, self._GOOD])
        provider = ModelAnalysisProvider(backend, format_retries=3)
        with pytest.raises(AnalysisFormatError, match="turn-99999"):
            provider.analyze(turns)
        assert backend.calls == 1, "an unsupported claim must abort on the first reply"
        assert provider.cost.format_retries == 0


def test_json_wrapped_in_a_code_fence_is_still_accepted(turns):
    """Tolerating a formatting habit is not the same as tolerating wrong content."""
    body = json.dumps(
        {
            "window_summary": "A summary of the excerpt.",
            "scenes": [
                {"title": "A scene", "summary": "It happened.", "turn_ids": ["turn-001"]}
            ],
            "questions": [],
        }
    )
    provider = ModelAnalysisProvider(ScriptedBackend(replies=[f"Sure!\n```json\n{body}\n```"]))
    result = provider.analyze(turns)
    assert result.summary == "A summary of the excerpt."
    assert len(result.scenes) == 1


def test_the_provider_declares_itself_as_model_output(turns):
    provider = ModelAnalysisProvider(FakeBackend())
    assert provider.is_declared_truth is False
    result = provider.analyze(turns)
    assert result.native_artifact["is_declared_truth"] is False
    assert result.native_artifact["backend"] == "fake-backend"
    assert result.native_artifact["model"] == "fake-model-1"
