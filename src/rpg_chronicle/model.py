"""Canonical, engine-neutral session representation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class UnsupportedEvidenceError(ValueError):
    """Raised when a claim cites transcript turns that do not exist in the session."""


@dataclass(frozen=True)
class Evidence:
    turn_ids: list[str]
    start_ms: int
    end_ms: int


def evidence_for(
    turns_by_id: dict[str, TranscriptTurn],
    turn_ids: list[str],
) -> Evidence:
    """Build evidence, failing closed if a claim cites turns the session does not contain.

    Provider output is untrusted. A model that hallucinates a turn id must produce a
    loud error here rather than an unsupported claim in the review package.
    """
    if not turn_ids:
        raise UnsupportedEvidenceError("a claim must cite at least one transcript turn")
    missing = [turn_id for turn_id in turn_ids if turn_id not in turns_by_id]
    if missing:
        raise UnsupportedEvidenceError(f"claim cites unknown transcript turns: {missing}")
    cited = [turns_by_id[turn_id] for turn_id in turn_ids]
    return Evidence(
        turn_ids=list(turn_ids),
        start_ms=min(turn.start_ms for turn in cited),
        end_ms=max(turn.end_ms for turn in cited),
    )


@dataclass(frozen=True)
class TranscriptTurn:
    id: str
    start_ms: int
    end_ms: int
    text: str
    physical_speaker: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError(f"Invalid timestamps for turn {self.id}")
        if not self.text.strip():
            raise ValueError(f"Turn {self.id} has no text")


@dataclass(frozen=True)
class Scene:
    id: str
    title: str
    summary: str
    evidence: Evidence


@dataclass(frozen=True)
class ReviewQuestion:
    id: str
    issue: str
    recommendation: str | None
    why_it_matters: str
    evidence: Evidence
    confidence: float
    consequence: str
    status: str = "open"


@dataclass
class CanonicalSession:
    schema_version: str
    session_id: str
    source: dict[str, Any]
    status: str
    turns: list[TranscriptTurn] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    summary: str | None = None
    review_questions: list[ReviewQuestion] = field(default_factory=list)
    processor_artifacts: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
