"""Resumable first vertical slice."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from .model import (
    CanonicalSession,
    Evidence,
    ReviewQuestion,
    Scene,
    TranscriptTurn,
)
from .providers import TranscriptProvider

SCHEMA_VERSION = "0.1"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def _evidence(turns: list[TranscriptTurn]) -> Evidence:
    return Evidence(
        turn_ids=[turn.id for turn in turns],
        start_ms=turns[0].start_ms,
        end_ms=turns[-1].end_ms,
    )


def _load_session(path: Path) -> CanonicalSession:
    data = json.loads(path.read_text())
    data["turns"] = [TranscriptTurn(**item) for item in data.get("turns", [])]
    data["scenes"] = [
        Scene(**{**item, "evidence": Evidence(**item["evidence"])})
        for item in data.get("scenes", [])
    ]
    data["review_questions"] = [
        ReviewQuestion(**{**item, "evidence": Evidence(**item["evidence"])})
        for item in data.get("review_questions", [])
    ]
    allowed = {item.name for item in fields(CanonicalSession)}
    return CanonicalSession(**{key: value for key, value in data.items() if key in allowed})


def _analyze(session: CanonicalSession, fixture: dict[str, Any]) -> None:
    analysis = fixture["expected_analysis"]
    turns_by_id = {turn.id: turn for turn in session.turns}
    session.scenes = []
    for item in analysis["scenes"]:
        supporting_turns = [turns_by_id[turn_id] for turn_id in item["turn_ids"]]
        session.scenes.append(
            Scene(
                id=item["id"],
                title=item["title"],
                summary=item["summary"],
                evidence=_evidence(supporting_turns),
            )
        )
    session.summary = analysis["summary"]
    session.review_questions = []
    for item in analysis["review_questions"]:
        supporting_turns = [turns_by_id[turn_id] for turn_id in item["turn_ids"]]
        session.review_questions.append(
            ReviewQuestion(
                id=item["id"],
                issue=item["issue"],
                recommendation=item.get("recommendation"),
                why_it_matters=item["why_it_matters"],
                evidence=_evidence(supporting_turns),
                confidence=item["confidence"],
                consequence=item["consequence"],
            )
        )


def run_fixture_pipeline(
    source: Path,
    output_dir: Path,
    provider: TranscriptProvider,
) -> CanonicalSession:
    """Run or resume the fixture vertical slice and return the canonical session."""
    fixture = json.loads(source.read_text())
    session_id = fixture["session"]["id"]
    session_dir = output_dir / session_id
    canonical_path = session_dir / "canonical-session.json"

    if canonical_path.exists():
        session = _load_session(canonical_path)
    else:
        session = CanonicalSession(
            schema_version=SCHEMA_VERSION,
            session_id=session_id,
            source={
                "kind": "synthetic-fixture",
                "path": str(source.resolve()),
                "original_recording": fixture["session"]["recording"],
            },
            status="imported",
        )
        _write_json(canonical_path, session.to_dict())

    native_path = session_dir / "processor-native" / "transcript.json"
    if not session.turns:
        result = provider.transcribe(source)
        _write_json(native_path, result.native_artifact)
        session.turns = result.turns
        session.processor_artifacts["transcript"] = str(native_path.relative_to(session_dir))
        session.status = "transcribed"
        _write_json(canonical_path, session.to_dict())

    if not session.scenes or not session.summary:
        _analyze(session, fixture)
        session.status = "analyzed"
        _write_json(canonical_path, session.to_dict())

    review_package = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session.session_id,
        "summary": session.summary,
        "scenes": [
            {
                "title": scene.title,
                "summary": scene.summary,
                "evidence": scene.evidence.__dict__,
            }
            for scene in session.scenes
        ],
        "needs_attention": [
            {
                "issue": question.issue,
                "recommendation": question.recommendation,
                "why_it_matters": question.why_it_matters,
                "evidence": question.evidence.__dict__,
                "confidence": question.confidence,
                "consequence": question.consequence,
                "actions": ["accept", "correct", "defer", "irrelevant"],
            }
            for question in session.review_questions
        ],
    }
    _write_json(session_dir / "review-package.json", review_package)
    session.status = "review_ready"
    _write_json(canonical_path, session.to_dict())
    return session
