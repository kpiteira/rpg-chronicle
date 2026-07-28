"""What a consumer can know from canonical turns alone.

D-006 says downstream reads canonical turns and nothing else, and `AnalysisProvider`
enforces it. Before D-018 the transcription provider knew how well a speaker label
covered its turn and what quantity its confidence was, and recorded both in the
engine-native artifact -- which is precisely where a consumer bound by D-006 cannot look.

Every test here is written so that it fails if the field it names is removed from
`TranscriptTurn`. A test that merely asserted a field exists would pass with the whole
boundary broken, which is the failure `agents/goal-validator.md` rejects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpg_chronicle.analysis.provider import ModelAnalysisProvider, _merge_entities_and_threads
from rpg_chronicle.model import CanonicalSession, TranscriptTurn, UnsupportedEvidenceError
from rpg_chronicle.pipeline import SCHEMA_VERSION, UnreadableSessionError, run_pipeline
from rpg_chronicle.providers import (
    AnalysisResult,
    FixtureAnalysisProvider,
    FixtureTranscriptProvider,
)
from rpg_chronicle.transcription.engine import (
    DiarizationResult,
    RecognitionResult,
    RecognizedSegment,
    SpeakerSpan,
)
from rpg_chronicle.transcription.provider import SpeechTranscriptProvider

from .fake_backend import FakeBackend


class StubRecognizer:
    name = "stub-recognizer"

    def __init__(self, segments: list[RecognizedSegment], confidence_kind: str) -> None:
        self._segments = segments
        self._confidence_kind = confidence_kind

    def preflight(self) -> None:
        return None

    def recognize(self, audio: Path) -> RecognitionResult:
        return RecognitionResult(
            segments=self._segments,
            native={"engine": self.name},
            confidence_kind=self._confidence_kind,
        )


class StubDiarizer:
    name = "stub-diarizer"

    def __init__(self, spans: list[SpeakerSpan]) -> None:
        self._spans = spans

    def preflight(self) -> None:
        return None

    def diarize(self, audio: Path) -> DiarizationResult:
        return DiarizationResult(
            spans=self._spans,
            native={"engine": self.name},
            speaker_labels=sorted({span.label for span in self._spans}),
            reliability="unreliable",
        )


def _transcribe(tmp_path, *, confidence_kind: str) -> list[TranscriptTurn]:
    """One clean turn and one that straddles a speaker change, through the real provider."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    audio = tmp_path / "session.wav"
    audio.write_bytes(b"not really audio; the engines are stubbed")
    segments = [
        RecognizedSegment(start_ms=0, end_ms=1000, text="A clean turn.", confidence=0.9),
        RecognizedSegment(start_ms=1000, end_ms=2000, text="A straddling turn.", confidence=0.9),
    ]
    spans = [
        SpeakerSpan(start_ms=0, end_ms=1000, label="speaker-1"),
        SpeakerSpan(start_ms=1000, end_ms=1500, label="speaker-1"),
        SpeakerSpan(start_ms=1500, end_ms=2000, label="speaker-2"),
    ]
    provider = SpeechTranscriptProvider(
        recognizer=StubRecognizer(segments, confidence_kind),
        diarizer=StubDiarizer(spans),
    )
    return provider.transcribe(audio).turns


class RecordingAnalysisProvider:
    """An `AnalysisProvider` that sees only what D-006 lets it see.

    It is given canonical turns and nothing else -- no engine-native artifact, no
    recognizer, no diarizer -- which is the whole point: whatever it can decide here, a
    real review layer can decide too.
    """

    name = "attribution-reader"

    def __init__(self) -> None:
        self.shaky: list[str] = []

    def analyze(self, turns: list[TranscriptTurn]) -> AnalysisResult:
        for turn in turns:
            if turn.speaker_purity is not None and turn.speaker_purity < 0.75:
                self.shaky.append(turn.id)
        return AnalysisResult(summary="", scenes=[], review_questions=[])


def test_a_consumer_reading_only_canonical_turns_can_tell_a_straddling_turn_apart(tmp_path):
    turns = _transcribe(tmp_path, confidence_kind="stub probability")
    consumer = RecordingAnalysisProvider()
    consumer.analyze(turns)

    # Both turns carry a speaker label, and by the label alone they are indistinguishable.
    assert [turn.physical_speaker for turn in turns] == ["speaker-1", "speaker-1"]
    # The second is half one speaker and half another. Only the second is reported.
    assert consumer.shaky == [turns[1].id]


def test_the_straddling_turn_is_the_one_whose_purity_is_low(tmp_path):
    """The distinction above is a real measurement, not an artefact of turn order."""
    turns = _transcribe(tmp_path, confidence_kind="stub probability")
    assert turns[0].speaker_coverage == pytest.approx(1.0)
    assert turns[0].speaker_purity == pytest.approx(1.0)
    assert turns[1].speaker_coverage == pytest.approx(1.0)
    assert turns[1].speaker_purity == pytest.approx(0.5)


def test_two_turns_carrying_the_same_number_from_different_engines_are_distinguishable(tmp_path):
    """0.9 from a log-probability and 0.9 from a native confidence are not one quantity."""
    whisper_like = _transcribe(tmp_path / "a", confidence_kind="decoder log-probability")
    parakeet_like = _transcribe(tmp_path / "b", confidence_kind="native token confidence")

    assert whisper_like[0].confidence == parakeet_like[0].confidence == pytest.approx(0.9)
    assert whisper_like[0].confidence_kind == "decoder log-probability"
    assert parakeet_like[0].confidence_kind == "native token confidence"
    assert whisper_like[0].confidence_kind != parakeet_like[0].confidence_kind


def test_a_confidence_with_no_stated_quantity_is_refused():
    """The ambiguity the field removes cannot be reintroduced by omitting it."""
    with pytest.raises(ValueError, match="confidence_kind"):
        TranscriptTurn(id="t1", start_ms=0, end_ms=10, text="Words.", confidence=0.9)


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_confidence_named_with_whitespace_is_still_unnamed(blank):
    """Omission is not the only way to leave the quantity unstated."""
    with pytest.raises(ValueError, match="confidence_kind"):
        TranscriptTurn(
            id="t1", start_ms=0, end_ms=10, text="Words.", confidence=0.9, confidence_kind=blank
        )


def test_a_turn_with_no_confidence_needs_no_quantity():
    turn = TranscriptTurn(id="t1", start_ms=0, end_ms=10, text="Words.")
    assert turn.confidence is None
    assert turn.confidence_kind is None


@pytest.mark.parametrize("field_name", ["speaker_coverage", "speaker_purity"])
def test_an_attribution_share_outside_zero_to_one_is_refused(field_name):
    with pytest.raises(ValueError, match=field_name):
        TranscriptTurn(id="t1", start_ms=0, end_ms=10, text="Words.", **{field_name: 1.4})


@pytest.mark.parametrize("field_name", ["speaker_coverage", "speaker_purity"])
@pytest.mark.parametrize("bad", ["0.8", True, [0.8]])
def test_an_attribution_share_that_is_not_a_number_is_refused(field_name, bad):
    """A stored session is JSON, so a string reaches here; `True` is an `int` and is not a share."""
    with pytest.raises(TypeError, match=field_name):
        TranscriptTurn(id="t1", start_ms=0, end_ms=10, text="Words.", **{field_name: bad})


class TestEntityMerging:
    """What happens when two overlapping windows describe the same name."""

    @staticmethod
    def _turns() -> list[TranscriptTurn]:
        return [
            TranscriptTurn(
                id=f"turn-{index:03d}",
                start_ms=index * 10,
                end_ms=index * 10 + 9,
                text=f"Line {index}.",
            )
            for index in range(1, 4)
        ]

    @staticmethod
    def _window(name: str, kind: str, aliases: list[str], turn_ids: list[str]) -> dict:
        return {
            "entities": [{"name": name, "kind": kind, "aliases": aliases, "turn_ids": turn_ids}],
            "threads": [],
        }

    def test_one_name_in_two_windows_becomes_one_entity_with_both_spellings(self):
        turns = self._turns()
        merged, _ = _merge_entities_and_threads(
            [
                self._window("Kaelith", "character", ["Kayleth"], ["turn-001"]),
                self._window("Kaelith", "character", ["Kaeleth"], ["turn-003"]),
            ],
            {turn.id: turn for turn in turns},
        )
        assert len(merged) == 1
        assert sorted(merged[0].aliases) == ["Kaeleth", "Kayleth"]
        # Evidence accumulates rather than splitting into two near-identical records.
        assert merged[0].evidence.turn_ids == ["turn-001", "turn-003"]

    def test_a_name_two_windows_disagree_about_is_not_silently_resolved(self):
        """First-mention-wins would hide the disagreement behind window ordering."""
        turns = self._turns()
        merged, _ = _merge_entities_and_threads(
            [
                self._window("The Ashen Hand", "faction", [], ["turn-001"]),
                self._window("The Ashen Hand", "character", [], ["turn-002"]),
            ],
            {turn.id: turn for turn in turns},
        )
        assert sorted(entity.kind for entity in merged) == ["character", "faction"]

    @pytest.mark.parametrize("bad", ["Kayleth", {"0": "Kayleth"}, [1]])
    def test_a_fixture_alias_field_that_is_not_a_list_of_strings_is_refused(self, bad, tmp_path):
        """`list("Kayleth")` is seven aliases and no exception, which is the worst outcome."""
        fixture = tmp_path / "fixture.json"
        fixture.write_text(
            json.dumps(
                {
                    "expected_analysis": {
                        "summary": "s",
                        "scenes": [],
                        "review_questions": [],
                        "entities": [
                            {
                                "id": "e1",
                                "name": "Kaelith",
                                "kind": "character",
                                "aliases": bad,
                                "turn_ids": ["turn-001"],
                            }
                        ],
                    }
                }
            )
        )
        with pytest.raises(ValueError, match="aliases"):
            FixtureAnalysisProvider(fixture).analyze(self._turns())

    def test_a_fabricated_citation_on_an_entity_aborts_like_any_other_claim(self):
        turns = self._turns()
        with pytest.raises(UnsupportedEvidenceError):
            _merge_entities_and_threads(
                [self._window("Nobody", "character", [], ["turn-999"])],
                {turn.id: turn for turn in turns},
            )


def _session_payload(schema_version: str) -> dict:
    """A stored session with the turn shape 0.1 actually wrote.

    The keys and the confidence value are copied from a `canonical-session.json` produced
    by `run-fixture` at c57bd0f, the commit before this change. That matters: an earlier
    version of this test hand-wrote a turn with no `confidence`, which is the one shape
    that survives the 0.2 invariant by accident, so it passed while every real 0.1 session
    failed to load. The goal validator caught it. The payload here is the failing case.
    """
    return {
        "schema_version": schema_version,
        "session_id": "s1",
        "source": {"path": "somewhere.json"},
        "status": "transcribed",
        "turns": [
            {
                "id": "turn-001",
                "start_ms": 0,
                "end_ms": 10,
                "text": "Words.",
                "physical_speaker": "speaker-1",
                "confidence": 0.98,
            }
        ],
        "scenes": [],
        "review_questions": [],
        "processor_artifacts": {},
        "provenance": {},
    }


def test_a_session_written_before_these_fields_existed_still_loads(tmp_path):
    """0.1 files predate every field added here, and resumption must survive them."""
    path = tmp_path / "canonical-session.json"
    path.write_text(json.dumps(_session_payload("0.1")))

    from rpg_chronicle.pipeline import UNSTATED_CONFIDENCE_KIND, _load_session

    session = _load_session(path)
    assert isinstance(session, CanonicalSession)
    turn = session.turns[0]
    # The number is kept and its provenance is marked as what it is: never recorded.
    assert turn.confidence == pytest.approx(0.98)
    assert turn.confidence_kind == UNSTATED_CONFIDENCE_KIND
    # Absent, not invented: nothing here fabricates an attribution nobody measured.
    assert turn.speaker_coverage is None
    assert turn.speaker_purity is None
    assert session.entities == []
    assert session.threads == []


def test_a_0_2_turn_still_may_not_omit_the_quantity(tmp_path):
    """The migration is for 0.1 files only; it must not become a way in for new ones."""
    path = tmp_path / "canonical-session.json"
    path.write_text(json.dumps(_session_payload("0.2")))

    from rpg_chronicle.pipeline import _load_session

    with pytest.raises(ValueError, match="confidence_kind"):
        _load_session(path)


def test_a_resumed_0_1_session_runs_to_review_ready(tmp_path):
    """The failure the validator reproduced was resumption, not loading in isolation."""
    session_dir = tmp_path / "s1"
    session_dir.mkdir()
    (session_dir / "canonical-session.json").write_text(json.dumps(_session_payload("0.1")))

    session = run_pipeline(
        source=Path("benchmarks/fixtures/r0_synthetic_session.json"),
        output_dir=tmp_path,
        transcript_provider=FixtureTranscriptProvider(),
        analysis_provider=ModelAnalysisProvider(FakeBackend()),
        session_id="s1",
    )
    assert session.status == "review_ready"
    # The rewritten file declares what it now holds, not where it came from.
    stored = json.loads((session_dir / "canonical-session.json").read_text())
    assert stored["schema_version"] == SCHEMA_VERSION
    assert stored["turns"][0]["confidence_kind"]


def test_a_session_from_a_schema_this_build_does_not_know_is_refused(tmp_path):
    path = tmp_path / "canonical-session.json"
    path.write_text(json.dumps(_session_payload("9.9")))

    from rpg_chronicle.pipeline import _load_session

    with pytest.raises(UnreadableSessionError, match="9.9"):
        _load_session(path)


def test_entities_and_threads_reach_the_review_package(tmp_path):
    """Through the model-backed provider, so this is merged output and not fixture truth."""
    session = run_pipeline(
        source=Path("benchmarks/fixtures/r0_synthetic_session.json"),
        output_dir=tmp_path,
        transcript_provider=FixtureTranscriptProvider(),
        analysis_provider=ModelAnalysisProvider(FakeBackend()),
    )
    package = json.loads((tmp_path / session.session_id / "review-package.json").read_text())

    assert package["entities"], "a reviewer sees no named thing at all"
    assert any(entity["aliases"] for entity in package["entities"]), (
        "aliases are the point of carrying entities: the spellings a person can settle"
    )
    assert package["open_threads"], "a reviewer sees nothing left open"
    assert session.entities and session.threads
    # Referencable by id rather than by name: the name is the model's proposal, and a
    # reviewer settling two spellings into one is expected to change it.
    assert all(entity["id"] for entity in package["entities"])
    assert all(thread["id"] for thread in package["open_threads"])
