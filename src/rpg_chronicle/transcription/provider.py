"""A speech-backed `TranscriptProvider`, assembled from engines that do not know each other.

This is the only module that holds a recognizer and a diarizer at once, and the only
place audio-derived output becomes canonical. `docs/ARCHITECTURE_BOUNDARIES.md` requires
that borrowed processors be normalized immediately and never treated as sources of
truth; that requirement is discharged here.

What normalization must not do is quietly improve the evidence. Three habits enforce it:

* A segment that cannot become a `TranscriptTurn` is *reported*, not dropped. R01 saw
  one engine emit 104 unusable units out of 450 on real audio; a provider that silently
  discarded them would have turned a loud engine failure into a shorter transcript.
* Speaker labels arrive marked unreliable and stay marked. They are cluster identifiers,
  not people.
* The confidence figure carries a description of what it measures. A Whisper decoder
  log-probability and a native model confidence occupy the same 0-1 range and mean
  different things; nothing here flattens them into one comparable number.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..model import TranscriptTurn
from ..providers import TranscriptResult
from .engine import (
    DiarizationEngine,
    DiarizationResult,
    RecognitionEngine,
    RecognizedSegment,
    SpeakerSpan,
)

UNRELIABLE_SPEAKERS = "unreliable"


@dataclass(frozen=True)
class Attribution:
    """How well a speaker label describes the turn it was attached to.

    Both numbers now reach the canonical turn as `speaker_coverage` and `speaker_purity`
    (D-018), which is what R01 asked for and what #20 could not do while `model.py` was
    unchanged. They stay in the engine-native artifact as well: that artifact is the
    debugging record, and D-006 gives it that job.

    `coverage` is the share of the turn any speaker covers at all; `purity` is the share
    the winning speaker covers *of what was covered*. Reported separately because they
    fail differently -- low coverage means the diarizer heard silence or missed speech,
    low purity means the turn straddles a speaker change.
    """

    label: str | None
    coverage: float
    purity: float


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def attribute(segment: RecognizedSegment, spans: list[SpeakerSpan]) -> Attribution:
    """Choose the speaker label for one recognized segment.

    By *total* overlap per speaker, not by the single longest-overlapping span. A
    diarizer routinely emits several short spans for one speaker inside a long segment,
    and picking the largest single span can hand the turn to a speaker who interjected
    once while the actual speaker held it across three spans. R01's probe used the
    single-span rule; this is the corrected form.
    """
    if not spans:
        return Attribution(label=None, coverage=0.0, purity=0.0)

    per_speaker: dict[str, int] = defaultdict(int)
    for span in spans:
        overlap = _overlap_ms(segment.start_ms, segment.end_ms, span.start_ms, span.end_ms)
        if overlap:
            per_speaker[span.label] += overlap

    span_ms = max(1, segment.end_ms - segment.start_ms)
    if not per_speaker:
        return Attribution(label=None, coverage=0.0, purity=0.0)

    label, winning = max(per_speaker.items(), key=lambda item: item[1])
    # Spans can overlap each other where the model hears two people at once, so the sum
    # can exceed the segment. Clamping keeps coverage a share rather than a ratio that
    # can pass 1.0, and the clamp is why coverage is an upper bound on how much of the
    # turn was really attributable.
    covered = min(sum(per_speaker.values()), span_ms)
    # `winning` is a sum too, so two overlapping spans carrying the same label can push
    # it past the segment and yield a purity above 1.0 -- a ratio that would quietly
    # discredit every other number in the artifact. Clamp both, and clamp the ratio to
    # the share it is supposed to be.
    winning = min(winning, covered)
    return Attribution(
        label=label,
        coverage=round(covered / span_ms, 3),
        purity=round(winning / covered, 3) if covered else 0.0,
    )


class SpeechTranscriptProvider:
    """Recognition plus optional diarization, normalized into canonical turns."""

    def __init__(
        self,
        recognizer: RecognitionEngine,
        diarizer: DiarizationEngine | None = None,
    ) -> None:
        self._recognizer = recognizer
        self._diarizer = diarizer

    @property
    def name(self) -> str:
        if self._diarizer is None:
            return f"{self._recognizer.name} (no diarization)"
        return f"{self._recognizer.name}+{self._diarizer.name}"

    def preflight(self) -> None:
        """Fail before the pipeline creates a session directory.

        Both engines are checked, so a run that would die at the diarization step after
        twenty minutes of recognition dies immediately instead.
        """
        self._recognizer.preflight()
        if self._diarizer is not None:
            self._diarizer.preflight()

    def transcribe(self, source: Path) -> TranscriptResult:
        recognition = self._recognizer.recognize(source)
        diarization: DiarizationResult | None = None
        if self._diarizer is not None:
            diarization = self._diarizer.diarize(source)
        spans = list(diarization.spans) if diarization else []

        turns: list[TranscriptTurn] = []
        attributions: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for index, segment in enumerate(recognition.segments):
            text = segment.text.strip()
            reason = None
            if not text:
                reason = "empty text"
            elif segment.start_ms < 0 or segment.end_ms <= segment.start_ms:
                reason = "non-positive span"
            if reason is not None:
                # Counted and characterised, never quietly dropped. The text is omitted:
                # the reason and the span are what diagnose the engine, and the words are
                # what the licence on a restricted input forbids carrying around.
                rejected.append(
                    {
                        "index": index,
                        "reason": reason,
                        "start_ms": segment.start_ms,
                        "end_ms": segment.end_ms,
                        "characters": len(segment.text),
                    }
                )
                continue

            attribution = attribute(segment, spans)
            turns.append(
                TranscriptTurn(
                    id=f"t{len(turns):05d}",
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=text,
                    physical_speaker=attribution.label,
                    confidence=segment.confidence,
                    confidence_kind=(
                        recognition.confidence_kind if segment.confidence is not None else None
                    ),
                    speaker_coverage=attribution.coverage,
                    speaker_purity=attribution.purity,
                )
            )
            attributions.append(
                {
                    "turn_id": turns[-1].id,
                    "label": attribution.label,
                    "coverage": attribution.coverage,
                    "purity": attribution.purity,
                }
            )

        native: dict[str, Any] = {
            "provider": self.name,
            "output_kind": "model output",
            "recognition": recognition.native,
            "confidence": {
                "kind": recognition.confidence_kind,
                "turns_with_confidence": sum(1 for turn in turns if turn.confidence is not None),
                "caution": (
                    "Not calibrated and not comparable across engines. R01 measured "
                    "turns that mangled an invented proper noun scoring within 0.02 of "
                    "a typical turn, so this figure does not find entity errors."
                ),
            },
            "speakers": {
                "reliability": diarization.reliability if diarization else "absent",
                "distinct_labels": len(diarization.speaker_labels) if diarization else 0,
                "caution": (
                    "Cluster identifiers, not people, and not stable across runs or "
                    "sessions. Physical speakers are not fictional characters."
                ),
                "attribution": attributions,
                "diarization": diarization.native if diarization else None,
            },
            "normalization": {
                "recognized_segments": len(recognition.segments),
                "canonical_turns": len(turns),
                "rejected_segments": len(rejected),
                "rejected": rejected,
            },
        }
        return TranscriptResult(turns=turns, native_artifact=native)
