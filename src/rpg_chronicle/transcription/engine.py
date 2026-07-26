"""The processor seam: how audio becomes timed text and speaker spans.

Two engines, kept apart because they are different problems with different maturity.
Recognition is a solved borrowing problem; speaker identity is not, and
`research/speech-stack-scorecard.md` records that the diarizer selected for R01 already
satisfies its own replacement trigger. Fusing them into one interface would make
swapping the unreliable half require touching the reliable one.

Neither engine knows what a `TranscriptTurn` is. They return what they observed, in
their own terms; `provider.py` is the single place that normalizes, and
`docs/ARCHITECTURE_BOUNDARIES.md` requires that normalization happen immediately and the
engine-native artifact be retained.

Adding a different recognizer later means writing one class here that satisfies
`RecognitionEngine`. It must not require touching the provider, the pipeline, or the
canonical model.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class EngineError(RuntimeError):
    """Base class for every failure originating in a speech processor."""


class EngineUnavailableError(EngineError):
    """The engine cannot run at all: missing binary, missing model file.

    Raised by `preflight()` before any work begins, so a misconfigured run fails before
    it writes a partial session rather than halfway through a four-hour file.
    """


class EngineResponseError(EngineError):
    """The engine ran but did not return output this code can use."""


@dataclass(frozen=True)
class RecognizedSegment:
    """One span of recognized speech, in the engine's own terms.

    `confidence` is deliberately optional and its meaning is *not* fixed by this type.
    A Whisper-family decoder yields token log-probabilities, which measure the model's
    certainty about the next token rather than about the transcription being correct; a
    Parakeet-family model emits a native confidence. R01 measured both and found neither
    able to flag a mangled proper noun. `confidence_kind` on the result records which
    quantity this is so that nothing downstream compares two of them as if they were
    the same number.
    """

    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class SpeakerSpan:
    """A stretch of audio one speaker label covers.

    Labels are engine-local: `SPEAKER_03` means "the third cluster this run formed",
    not a person. Nothing may treat them as identities across runs or across sessions.
    """

    start_ms: int
    end_ms: int
    label: str


@dataclass(frozen=True)
class RecognitionResult:
    segments: list[RecognizedSegment]
    native: dict[str, Any]
    confidence_kind: str
    """What `RecognizedSegment.confidence` actually measures, in words.

    Carried rather than assumed. `docs/PRODUCT.md` makes confidence a driver of review
    intervention, and a review layer that thresholds across engines without knowing
    which quantity it holds is comparing incomparable things.
    """


@dataclass(frozen=True)
class DiarizationResult:
    spans: list[SpeakerSpan]
    native: dict[str, Any]
    reliability: str = "unreliable"
    """How much weight the labels carry.

    Defaults to `unreliable` because that is what the evidence supports: R01 found no
    clustering threshold recovered a known speaker count, and constraining the count
    made it worse by merging distinct speakers. A future diarizer that earns a better
    word can set one; nothing should have to opt *in* to caution.
    """

    speaker_labels: list[str] = field(default_factory=list)


class RecognitionEngine(Protocol):
    """Audio in, timed text out. The only place a recognizer's name may appear."""

    name: str

    def preflight(self) -> None:
        """Fail before any work begins if this engine cannot run."""
        ...

    def recognize(self, audio: Path) -> RecognitionResult: ...


class DiarizationEngine(Protocol):
    """Audio in, speaker spans out. Never text."""

    name: str

    def preflight(self) -> None: ...

    def diarize(self, audio: Path) -> DiarizationResult: ...


def require_executable(executable: str, *, engine_name: str, install_hint: str) -> str:
    """Resolve a required binary, or fail with a message that says how to get it.

    Shared rather than reimplemented per engine so the failure reads the same whichever
    processor is missing, and so it names the install step instead of leaving an
    operator to work out why a `FileNotFoundError` mentions a program they never
    invoked directly.
    """
    resolved = shutil.which(executable)
    if resolved is None:
        raise EngineUnavailableError(
            f"engine {engine_name!r} requires the executable {executable!r}, which is "
            f"not on PATH. {install_hint}"
        )
    return resolved


def require_model_file(path: Path, *, engine_name: str, install_hint: str) -> Path:
    """Resolve a required model file, or fail with a message that says how to get it."""
    if not path.is_file():
        raise EngineUnavailableError(
            f"engine {engine_name!r} requires the model file {path}, which does not "
            f"exist. {install_hint}"
        )
    return path
