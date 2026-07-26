"""Speech processors behind a seam, normalized into the canonical transcript.

`engine.py` defines what a recognizer and a diarizer are. `whisper_cpp.py` and
`sherpa_diarization.py` are the implementations R01 selected. `provider.py` composes
them into a `TranscriptProvider` and is the only place audio-derived output becomes
canonical.
"""

from .engine import (
    DiarizationEngine,
    DiarizationResult,
    EngineError,
    EngineResponseError,
    EngineUnavailableError,
    RecognitionEngine,
    RecognitionResult,
    RecognizedSegment,
    SpeakerSpan,
)
from .provider import Attribution, SpeechTranscriptProvider, attribute

__all__ = [
    "Attribution",
    "DiarizationEngine",
    "DiarizationResult",
    "EngineError",
    "EngineResponseError",
    "EngineUnavailableError",
    "RecognitionEngine",
    "RecognitionResult",
    "RecognizedSegment",
    "SpeakerSpan",
    "SpeechTranscriptProvider",
    "attribute",
]
