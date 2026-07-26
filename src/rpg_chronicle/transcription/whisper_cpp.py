"""whisper.cpp behind the recognition seam.

Selected provisionally by R01 (`research/speech-stack-scorecard.md`). It was not the
fastest engine probed -- parakeet-mlx ran 1.8x quicker on a fifth of the memory -- and
the scorecard records why it won anyway: it handles long audio without a chunking
parameter, degrades to plain CPU, and is MIT throughout. The replacement triggers live
in the scorecard, not here.

Two details from that probe shape this module:

* `-ojf`, never `-oj`. The plain JSON writer emits no scores at all, which would have
  recorded "this engine has no confidence" when in fact it has per-token probabilities
  and only the default writer drops them.
* Output goes to a scratch directory, never beside the input. The input may be
  restriction-bound audio sitting anywhere, and whisper.cpp writes its transcript next
  to whatever it was pointed at.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path, PurePath
from typing import Any

from .engine import (
    EngineResponseError,
    RecognitionResult,
    RecognizedSegment,
    require_executable,
    require_model_file,
)

DEFAULT_EXECUTABLE = "whisper-cli"
DEFAULT_MODEL_FILENAME = "ggml-large-v3-turbo.bin"

CONFIDENCE_KIND = "mean whisper.cpp token probability, excluding special tokens"
"""What this engine's confidence is, stated so nothing treats it as calibrated.

It is the decoder's certainty about the tokens it emitted, not about the transcription
being right. R01 measured turns that mangled an invented proper noun scoring within
0.02 of a typical turn -- and above typical on one stack -- so this number does not
find entity errors and must not be relied on to.
"""

INSTALL_HINT = (
    "Install it with `brew install whisper-cpp` (macOS) or build whisper.cpp from "
    "source; see research/probes/README.md for the setup used to select it."
)
MODEL_HINT = (
    "Download it with `curl -sSL -O "
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin` "
    "into the model directory, or point --whisper-model at an existing ggml model."
)


def _basename(part: str) -> str:
    """Reduce a command argument to a basename if it looks like a path.

    The engine-native artifact is retained for debugging and may travel; absolute paths
    in it would carry the operator's home directory and the location of restricted audio
    along with them.
    """
    candidate = PurePath(part)
    return candidate.name if len(candidate.parts) > 1 else part


def _segment_confidence(segment: dict[str, Any]) -> float | None:
    """Mean probability over the segment's real tokens.

    Special tokens carry their own probabilities and would drag the score toward the
    decoder's certainty about punctuation and timestamps rather than about words.
    """
    scores = [
        token["p"]
        for token in segment.get("tokens", [])
        if "p" in token and not str(token.get("text", "")).startswith("[_")
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 6)


class WhisperCppEngine:
    """Recognition through the whisper.cpp CLI."""

    name = "whisper.cpp"

    def __init__(
        self,
        *,
        model: Path,
        executable: str = DEFAULT_EXECUTABLE,
        threads: int | None = None,
        language: str | None = None,
    ) -> None:
        self._model = Path(model)
        self._executable = executable
        self._threads = threads or os.cpu_count() or 4
        self._language = language

    @property
    def model_name(self) -> str:
        return self._model.name

    def preflight(self) -> None:
        require_executable(self._executable, engine_name=self.name, install_hint=INSTALL_HINT)
        require_model_file(self._model, engine_name=self.name, install_hint=MODEL_HINT)

    def recognize(self, audio: Path) -> RecognitionResult:
        self.preflight()
        # Never beside the input: whisper.cpp writes its output file next to whatever
        # `-of` names, and the input here is audio whose transcript must not be left
        # lying in a directory somebody might later commit.
        with tempfile.TemporaryDirectory(prefix="rpg-whisper-cpp-") as scratch:
            prefix = Path(scratch) / audio.stem
            command = [
                self._executable,
                "-m",
                str(self._model),
                "-f",
                str(audio),
                "-ojf",
                "-of",
                str(prefix),
                "-t",
                str(self._threads),
            ]
            if self._language:
                command += ["-l", self._language]
            try:
                process = subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as error:
                tail = (error.stderr or "").strip().splitlines()
                raise EngineResponseError(
                    f"{self.name} exited {error.returncode}. Last output: "
                    f"{tail[-1] if tail else '(none)'}"
                ) from error

            output = Path(f"{prefix}.json")
            if not output.is_file():
                raise EngineResponseError(
                    f"{self.name} reported success but wrote no JSON at {output.name}"
                )
            payload = json.loads(output.read_text())

        transcription = payload.get("transcription")
        if not isinstance(transcription, list):
            raise EngineResponseError(
                f"{self.name} JSON has no 'transcription' list; got "
                f"{sorted(payload)[:6]}"
            )

        segments = [
            RecognizedSegment(
                start_ms=int(item["offsets"]["from"]),
                end_ms=int(item["offsets"]["to"]),
                text=str(item.get("text", "")).strip(),
                confidence=_segment_confidence(item),
            )
            for item in transcription
        ]

        # The engine-native artifact is retained per D-006, but the command is recorded
        # by basename: absolute paths here would carry the operator's home directory
        # and the location of restricted audio into whatever consumes this.
        native = {
            "engine": self.name,
            "model_file": self._model.name,
            "threads": self._threads,
            "language": self._language,
            # PurePath handles the separator for whatever platform this ran on; the
            # earlier "/" test would have recorded full operator paths on Windows.
            "cli": [_basename(part) for part in command],
            "segment_count": len(segments),
            "result": payload.get("result", {}),
            "systeminfo": payload.get("systeminfo"),
            "stderr_tail": [
                line
                for line in (process.stderr or "").strip().splitlines()[-8:]
                if scratch not in line
            ],
        }
        return RecognitionResult(
            segments=segments,
            native=native,
            confidence_kind=CONFIDENCE_KIND,
        )
