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
    """One canonical turn, and everything a consumer may know about how good it is.

    Three fields beyond the text exist because a consumer reading only canonical turns
    was otherwise unable to tell a shaky value from a solid one, while the producer knew
    perfectly well (D-006, D-018).

    `confidence_kind` says what `confidence` measures. A Whisper decoder
    log-probability and a native model confidence occupy the same 0-1 range and are not
    the same quantity, so a consumer that thresholds across engines without reading this
    is comparing incomparable numbers. Naming the quantity does not calibrate it: R01
    measured turns that mangled an invented proper noun scoring within 0.02 of a typical
    turn, so neither kind finds entity errors.

    `speaker_coverage` is the share of the turn any speaker was heard on at all, and
    `speaker_purity` the share the winning speaker covers *of what was covered*. They
    fail differently, which is why they are two numbers: low coverage means the diarizer
    heard silence or missed speech, low purity means the turn straddles a speaker change.
    A `physical_speaker` with low purity is an attribution, not an observation.
    """

    id: str
    start_ms: int
    end_ms: int
    text: str
    physical_speaker: str | None = None
    confidence: float | None = None
    confidence_kind: str | None = None
    speaker_coverage: float | None = None
    speaker_purity: float | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError(f"Invalid timestamps for turn {self.id}")
        if not self.text.strip():
            raise ValueError(f"Turn {self.id} has no text")
        if self.confidence is not None and not (self.confidence_kind or "").strip():
            raise ValueError(
                f"Turn {self.id} carries a confidence with no confidence_kind. "
                "An unnamed confidence is the ambiguity this field exists to remove, and "
                "a blank name is an unnamed one."
            )
        for name in ("speaker_coverage", "speaker_purity"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"Turn {self.id} has {name}={value}, which is not a share")


@dataclass(frozen=True)
class Scene:
    id: str
    title: str
    summary: str
    evidence: Evidence


@dataclass(frozen=True)
class Entity:
    """A person, place, faction, item or quest the session talked about.

    `aliases` is the point of the type rather than a decoration. A four-hour recording
    spells an invented name several ways, and which spelling is canonical is exactly what
    a reviewer can settle in seconds and a recognizer cannot settle at all.

    Carrying `evidence` makes an entity a claim rather than a note, which means a citation
    the session does not contain aborts the run like any other claim. That is the same
    trade `rpg_chronicle.analysis.provider` already states for scenes and questions.
    """

    id: str
    name: str
    kind: str
    aliases: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class Thread:
    """Something the session left open: a question, an obligation, a debt, a threat."""

    id: str
    description: str
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
    entities: list[Entity] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)
    summary: str | None = None
    review_questions: list[ReviewQuestion] = field(default_factory=list)
    processor_artifacts: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
