"""The `run-audio` wiring: selection, preflight ordering, and what the report may carry.

No audio and no models here either. What is being tested is the CLI's own behaviour --
which providers it constructs, that it fails before writing anything, and that the
report it offers as committable evidence contains no recognized text.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpg_chronicle import cli
from rpg_chronicle.providers import AnalysisResult
from rpg_chronicle.transcription.engine import (
    EngineUnavailableError,
    RecognitionResult,
    RecognizedSegment,
)
from rpg_chronicle.transcription.provider import SpeechTranscriptProvider

SECRET = "Vaelthorn and the Ashen Spire"


class StubRecognizer:
    name = "stub-recognizer"

    def preflight(self) -> None:
        return None

    def recognize(self, audio: Path) -> RecognitionResult:
        return RecognitionResult(
            segments=[RecognizedSegment(0, 1500, SECRET, confidence=0.91)],
            native={"engine": self.name},
            confidence_kind="stub probability",
        )


class StubAnalysis:
    name = "stub-analysis"
    is_declared_truth = False

    def analyze(self, turns):  # type: ignore[no-untyped-def]
        return AnalysisResult(summary="a summary", scenes=[], review_questions=[])


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *extra: str) -> Path:
    audio = tmp_path / "excerpt.wav"
    audio.write_bytes(b"")
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        cli, "_transcript_provider", lambda args: SpeechTranscriptProvider(StubRecognizer())
    )
    monkeypatch.setattr(cli, "_model_provider", lambda args: StubAnalysis())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rpg-chronicle",
            "run-audio",
            str(audio),
            "--output",
            str(tmp_path / "out"),
            "--run-report",
            str(report),
            *extra,
        ],
    )
    cli.main()
    return report


def test_run_audio_produces_a_review_package(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _run(monkeypatch, tmp_path)
    package = tmp_path / "out" / "excerpt" / "review-package.json"
    assert package.is_file()
    assert json.loads(package.read_text())["summary"] == "a summary"


def test_run_report_carries_counts_and_no_recognized_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """This file is the evidence a restricted recording is allowed to leave behind."""
    report = json.loads(_run(monkeypatch, tmp_path).read_text())
    assert report["turns"] == 1
    assert report["turns_with_confidence"] == 1
    assert report["contains_recognized_text"] is False
    assert SECRET not in json.dumps(report)
    assert "Vaelthorn" not in json.dumps(report)


def test_analysis_fixture_without_a_fixture_path_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Recognized audio has no declared truth of its own, so the flag needs a source."""
    with pytest.raises(SystemExit, match="--analysis-fixture"):
        _run(monkeypatch, tmp_path, "--analysis", "fixture")


def test_engine_preflight_failure_is_a_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing model file should cost a second and say how to fix it."""

    class Missing:
        name = "missing-engine"

        def preflight(self) -> None:
            raise EngineUnavailableError("requires the model file /nope/model.bin")

        def recognize(self, audio: Path) -> RecognitionResult:  # pragma: no cover
            raise AssertionError("must not be reached")

    audio = tmp_path / "excerpt.wav"
    audio.write_bytes(b"")
    monkeypatch.setattr(
        cli, "_transcript_provider", lambda args: SpeechTranscriptProvider(Missing())
    )
    monkeypatch.setattr(cli, "_model_provider", lambda args: StubAnalysis())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rpg-chronicle",
            "run-audio",
            str(audio),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(SystemExit, match="speech engine unavailable"):
        cli.main()
    # Nothing was written: preflight runs before the pipeline creates a session.
    assert not (tmp_path / "out").exists()


def test_no_diarize_drops_labels_rather_than_carrying_unwanted_ones(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = json.loads(_run(monkeypatch, tmp_path, "--no-diarize").read_text())
    assert report["turns_with_speaker"] == 0
    assert report["distinct_speaker_labels"] == 0
