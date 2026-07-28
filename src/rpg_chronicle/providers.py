"""Replaceable processing provider interfaces.

Every stage that will eventually be performed by a model sits behind a Protocol here.
Fixture implementations are ordinary providers, not special cases inside the pipeline,
so that swapping in a real engine never requires editing pipeline control flow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .model import Entity, ReviewQuestion, Scene, Thread, TranscriptTurn, evidence_for


def _declared_aliases(item: dict[str, Any]) -> list[str]:
    """Read a fixture's alias list, refusing anything that is not one.

    `list("Kayleth")` is a list of seven characters and no exception, which is the worst
    available outcome: the fixture would appear to declare seven aliases.
    """
    value = item.get("aliases", [])
    if not isinstance(value, list) or not all(isinstance(alias, str) for alias in value):
        raise ValueError(
            f"fixture entity {item.get('name')!r} declares aliases {value!r}; "
            "'aliases' must be a list of strings"
        )
    return list(value)


@dataclass(frozen=True)
class TranscriptResult:
    turns: list[TranscriptTurn]
    native_artifact: dict[str, object]


@dataclass(frozen=True)
class AnalysisResult:
    summary: str
    scenes: list[Scene]
    review_questions: list[ReviewQuestion]
    entities: list[Entity] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)
    native_artifact: dict[str, object] = field(default_factory=dict)


class TranscriptProvider(Protocol):
    """A borrowed engine that is normalized immediately after processing."""

    name: str

    def transcribe(self, source: Path) -> TranscriptResult: ...


class AnalysisProvider(Protocol):
    """Turns canonical transcript turns into scenes, a summary, and review questions.

    Implementations receive only canonical turns -- never the original fixture or the
    engine-native artifact -- so a fixture provider and a model provider are
    interchangeable and comparable on identical input.
    """

    name: str

    def analyze(self, turns: list[TranscriptTurn]) -> AnalysisResult: ...


class FixtureTranscriptProvider:
    """Deterministic provider used before a real speech engine is integrated."""

    name = "fixture-transcriber"

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
                # A fixture's confidence is a number somebody wrote down, not a
                # measurement any engine produced. Naming it "declared" is the same
                # distinction D-009 draws everywhere else, applied to the one field
                # where an unnamed number would look exactly like a measured one.
                confidence_kind=(
                    item.get("confidence_kind", "declared")
                    if item.get("confidence") is not None
                    else None
                ),
                speaker_coverage=item.get("speaker_coverage"),
                speaker_purity=item.get("speaker_purity"),
            )
            for item in payload["engine_output"]["turns"]
        ]
        return TranscriptResult(turns=turns, native_artifact=payload["engine_output"])


class FixtureAnalysisProvider:
    """Replays declared analysis truth from a fixture.

    This provider asserts nothing about analysis quality. It exists so the review and
    campaign-change stages downstream of it can be built and measured before any model
    is selected. Benchmarks must never report fixture-provider output as a result.
    """

    name = "fixture-analysis"
    is_declared_truth = True

    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = fixture_path

    def analyze(self, turns: list[TranscriptTurn]) -> AnalysisResult:
        declared = json.loads(self._fixture_path.read_text())["expected_analysis"]
        turns_by_id = {turn.id: turn for turn in turns}

        scenes = [
            Scene(
                id=item["id"],
                title=item["title"],
                summary=item["summary"],
                evidence=evidence_for(turns_by_id, item["turn_ids"]),
            )
            for item in declared["scenes"]
        ]
        questions = [
            ReviewQuestion(
                id=item["id"],
                issue=item["issue"],
                recommendation=item.get("recommendation"),
                why_it_matters=item["why_it_matters"],
                evidence=evidence_for(turns_by_id, item["turn_ids"]),
                confidence=item["confidence"],
                consequence=item["consequence"],
            )
            for item in declared["review_questions"]
        ]
        entities = [
            Entity(
                id=item["id"],
                name=item["name"],
                kind=item["kind"],
                aliases=_declared_aliases(item),
                evidence=evidence_for(turns_by_id, item["turn_ids"]),
            )
            for item in declared.get("entities", [])
        ]
        threads = [
            Thread(
                id=item["id"],
                description=item["description"],
                evidence=evidence_for(turns_by_id, item["turn_ids"]),
            )
            for item in declared.get("threads", [])
        ]
        return AnalysisResult(
            summary=declared["summary"],
            scenes=scenes,
            review_questions=questions,
            entities=entities,
            threads=threads,
            native_artifact={"provider": self.name, "source": str(self._fixture_path)},
        )
