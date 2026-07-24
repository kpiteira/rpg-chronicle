"""Replaceable processing provider interfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .model import TranscriptTurn


@dataclass(frozen=True)
class TranscriptResult:
    turns: list[TranscriptTurn]
    native_artifact: dict[str, object]


class TranscriptProvider(Protocol):
    """A borrowed engine that is normalized immediately after processing."""

    def transcribe(self, source: Path) -> TranscriptResult: ...


class FixtureTranscriptProvider:
    """Deterministic provider used before a real speech engine is integrated."""

    def transcribe(self, source: Path) -> TranscriptResult:
        payload = json.loads(source.read_text())
        turns = [
            TranscriptTurn(
                id=item["id"],
                start_ms=item["start_ms"],
                end_ms=item["end_ms"],
                text=item["text"],
                physical_speaker=item.get("physical_speaker"),
                confidence=item.get("confidence"),
            )
            for item in payload["engine_output"]["turns"]
        ]
        return TranscriptResult(turns=turns, native_artifact=payload["engine_output"])
