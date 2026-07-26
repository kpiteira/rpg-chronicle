"""What the speech providers must do, tested without a model file or a recording.

The engines are stubbed. That is the point of the seam: normalization, attribution and
resumption are this project's code and must be provable in CI, while whisper.cpp and
sherpa-onnx are borrowed processors whose own correctness is not this suite's business.
Tests that needed a 1.6 GB model and restricted audio would not run in CI at all, and a
test that does not run proves nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpg_chronicle.pipeline import run_pipeline
from rpg_chronicle.providers import AnalysisResult
from rpg_chronicle.transcription.engine import (
    DiarizationResult,
    RecognitionResult,
    RecognizedSegment,
    SpeakerSpan,
)
from rpg_chronicle.transcription.provider import SpeechTranscriptProvider, attribute


class StubRecognizer:
    name = "stub-recognizer"

    def __init__(self, segments: list[RecognizedSegment]) -> None:
        self._segments = segments
        self.calls = 0

    def preflight(self) -> None:
        return None

    def recognize(self, audio: Path) -> RecognitionResult:
        self.calls += 1
        return RecognitionResult(
            segments=self._segments,
            native={"engine": self.name},
            confidence_kind="stub probability",
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
        )


class StubAnalysis:
    name = "stub-analysis"
    is_declared_truth = False

    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, turns):  # type: ignore[no-untyped-def]
        self.calls += 1
        return AnalysisResult(summary="s", scenes=[], review_questions=[])


def test_attribution_uses_total_overlap_not_the_longest_single_span() -> None:
    """A speaker who holds the turn across several spans must beat one long interjection.

    This is the corrected form of the rule R01's probe used. With the single-span rule
    B wins on its 500 ms span; by total overlap A wins with 600 ms across three.
    """
    segment = RecognizedSegment(start_ms=0, end_ms=1000, text="x")
    spans = [
        SpeakerSpan(0, 200, "A"),
        SpeakerSpan(200, 700, "B"),
        SpeakerSpan(700, 900, "A"),
        SpeakerSpan(900, 1100, "A"),
    ]
    assert attribute(segment, spans).label == "A"


def test_attribution_reports_coverage_and_purity_separately() -> None:
    segment = RecognizedSegment(start_ms=0, end_ms=1000, text="x")
    result = attribute(segment, [SpeakerSpan(0, 400, "A")])
    assert result.coverage == pytest.approx(0.4)
    # Of the 400 ms anybody covered, A covered all of it.
    assert result.purity == pytest.approx(1.0)


def test_attribution_without_spans_yields_no_speaker() -> None:
    result = attribute(RecognizedSegment(0, 100, "x"), [])
    assert result.label is None and result.coverage == 0.0


def test_unusable_segments_are_reported_rather_than_dropped(tmp_path: Path) -> None:
    """An engine emitting empty segments must leave a trace, not a shorter transcript."""
    provider = SpeechTranscriptProvider(
        StubRecognizer(
            [
                RecognizedSegment(0, 1000, "real words"),
                RecognizedSegment(1000, 2000, "   "),
                RecognizedSegment(3000, 3000, "zero length"),
            ]
        )
    )
    result = provider.transcribe(tmp_path / "a.wav")
    assert len(result.turns) == 1
    normalization = result.native_artifact["normalization"]
    assert normalization["recognized_segments"] == 3
    assert normalization["rejected_segments"] == 2
    assert {item["reason"] for item in normalization["rejected"]} == {
        "empty text",
        "non-positive span",
    }


def test_rejected_segments_record_shape_but_not_words(tmp_path: Path) -> None:
    """The diagnosis is the reason and the span; the words are what a licence restricts."""
    provider = SpeechTranscriptProvider(
        StubRecognizer([RecognizedSegment(0, 0, "secret words that must not travel")])
    )
    rejected = provider.transcribe(tmp_path / "a.wav").native_artifact["normalization"][
        "rejected"
    ]
    assert "secret" not in json.dumps(rejected)
    assert rejected[0]["characters"] == len("secret words that must not travel")


def test_turn_ids_are_stable_and_ordered(tmp_path: Path) -> None:
    provider = SpeechTranscriptProvider(
        StubRecognizer(
            [RecognizedSegment(i * 1000, i * 1000 + 500, f"w{i}") for i in range(3)]
        )
    )
    turns = provider.transcribe(tmp_path / "a.wav").turns
    assert [turn.id for turn in turns] == ["t00000", "t00001", "t00002"]


def test_speaker_labels_are_carried_and_marked_unreliable(tmp_path: Path) -> None:
    provider = SpeechTranscriptProvider(
        StubRecognizer([RecognizedSegment(0, 1000, "hello")]),
        StubDiarizer([SpeakerSpan(0, 1000, "SPEAKER_00")]),
    )
    result = provider.transcribe(tmp_path / "a.wav")
    assert result.turns[0].physical_speaker == "SPEAKER_00"
    assert result.native_artifact["speakers"]["reliability"] == "unreliable"


def test_confidence_carries_a_description_of_what_it_measures(tmp_path: Path) -> None:
    """Two engines' confidences occupy the same range and mean different things."""
    provider = SpeechTranscriptProvider(
        StubRecognizer([RecognizedSegment(0, 1000, "hello", confidence=0.9)])
    )
    confidence = provider.transcribe(tmp_path / "a.wav").native_artifact["confidence"]
    assert confidence["kind"] == "stub probability"
    assert confidence["turns_with_confidence"] == 1


def test_preflight_checks_both_engines() -> None:
    class Failing:
        name = "failing"

        def preflight(self) -> None:
            raise RuntimeError("no model")

        def diarize(self, audio: Path) -> DiarizationResult:  # pragma: no cover
            raise AssertionError("must not be reached")

    provider = SpeechTranscriptProvider(StubRecognizer([]), Failing())
    with pytest.raises(RuntimeError, match="no model"):
        provider.preflight()


def test_resume_does_not_re_recognize_a_completed_transcript(tmp_path: Path) -> None:
    """The expensive stage must not run twice.

    This fails if `pipeline.run_pipeline` stops guarding the transcription stage on
    `session.turns`: the recognizer counts its calls, and a pipeline that re-transcribes
    an already-transcribed session makes two. Recognition is the multi-minute stage on a
    real recording, so re-running it is the difference between resuming and restarting.
    """
    audio = tmp_path / "session.wav"
    audio.write_bytes(b"")
    recognizer = StubRecognizer([RecognizedSegment(0, 1000, "hello")])
    provider = SpeechTranscriptProvider(recognizer)

    run_pipeline(
        source=audio,
        output_dir=tmp_path / "out",
        transcript_provider=provider,
        analysis_provider=StubAnalysis(),
    )
    assert recognizer.calls == 1

    run_pipeline(
        source=audio,
        output_dir=tmp_path / "out",
        transcript_provider=provider,
        analysis_provider=StubAnalysis(),
    )
    assert recognizer.calls == 1, "resumed run re-ran recognition instead of reusing turns"


def test_resume_after_interruption_keeps_the_transcript(tmp_path: Path) -> None:
    """Interrupt during analysis; the resumed run reuses the transcript it already had."""
    audio = tmp_path / "session.wav"
    audio.write_bytes(b"")
    recognizer = StubRecognizer([RecognizedSegment(0, 1000, "hello")])
    provider = SpeechTranscriptProvider(recognizer)

    class Exploding:
        name = "exploding"

        def analyze(self, turns):  # type: ignore[no-untyped-def]
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_pipeline(
            source=audio,
            output_dir=tmp_path / "out",
            transcript_provider=provider,
            analysis_provider=Exploding(),
        )
    assert recognizer.calls == 1

    session = run_pipeline(
        source=audio,
        output_dir=tmp_path / "out",
        transcript_provider=provider,
        analysis_provider=StubAnalysis(),
    )
    assert recognizer.calls == 1, "resume re-ran the stage that had already completed"
    assert session.status == "review_ready"
    assert len(session.turns) == 1
