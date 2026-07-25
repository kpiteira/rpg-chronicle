"""Resumable first vertical slice.

Stage control flow is provider-agnostic: the pipeline never reads the fixture directly.
Swapping a fixture provider for a real engine is a wiring change in the CLI, not an edit
here.
"""

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
from .providers import AnalysisProvider, TranscriptProvider

SCHEMA_VERSION = "0.1"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


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


def _build_review_package(session: CanonicalSession) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session.session_id,
        "provenance": dict(session.provenance),
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


def run_pipeline(
    source: Path,
    output_dir: Path,
    transcript_provider: TranscriptProvider,
    analysis_provider: AnalysisProvider,
    session_id: str | None = None,
) -> CanonicalSession:
    """Run or resume the vertical slice and return the canonical session."""
    session_id = session_id or source.stem
    session_dir = output_dir / session_id
    canonical_path = session_dir / "canonical-session.json"

    if canonical_path.exists():
        session = _load_session(canonical_path)
    else:
        session = CanonicalSession(
            schema_version=SCHEMA_VERSION,
            session_id=session_id,
            source={"kind": source.suffix.lstrip(".") or "unknown", "path": str(source.resolve())},
            status="imported",
        )
        _write_json(canonical_path, session.to_dict())

    if not session.turns:
        result = transcript_provider.transcribe(source)
        native_path = session_dir / "processor-native" / "transcript.json"
        _write_json(native_path, result.native_artifact)
        session.turns = result.turns
        session.processor_artifacts["transcript"] = str(native_path.relative_to(session_dir))
        session.provenance["transcript_provider"] = getattr(
            transcript_provider, "name", type(transcript_provider).__name__
        )
        session.status = "transcribed"
        _write_json(canonical_path, session.to_dict())

    if not session.scenes or not session.summary:
        analysis = analysis_provider.analyze(session.turns)
        if analysis.native_artifact:
            native_path = session_dir / "processor-native" / "analysis.json"
            _write_json(native_path, analysis.native_artifact)
            session.processor_artifacts["analysis"] = str(native_path.relative_to(session_dir))
        session.summary = analysis.summary
        session.scenes = analysis.scenes
        session.review_questions = analysis.review_questions
        session.provenance["analysis_provider"] = getattr(
            analysis_provider, "name", type(analysis_provider).__name__
        )
        session.provenance["analysis_is_declared_truth"] = bool(
            getattr(analysis_provider, "is_declared_truth", False)
        )
        session.status = "analyzed"
        _write_json(canonical_path, session.to_dict())

    _write_json(session_dir / "review-package.json", _build_review_package(session))
    session.status = "review_ready"
    _write_json(canonical_path, session.to_dict())
    return session
