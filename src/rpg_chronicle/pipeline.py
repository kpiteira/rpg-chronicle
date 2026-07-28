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
    Entity,
    Evidence,
    ReviewQuestion,
    Scene,
    Thread,
    TranscriptTurn,
)
from .providers import AnalysisProvider, TranscriptProvider
from .review.apply import carry_forward
from .review.record import RECORD_FILENAME, CorrectionRecord, utc_now
from .review.vocabulary import Vocabulary

SCHEMA_VERSION = "0.2"

# 0.1 sessions are readable, but not by defaulting every added field to empty. A 0.1 turn
# carries a `confidence` and no `confidence_kind`, which is exactly what 0.2 refuses to
# construct, so loading one needs an answer rather than a default: the quantity was never
# recorded, and saying so is the only honest thing available. Naming it "declared" or
# guessing an engine would invent provenance for a number whose provenance is gone.
#
# The reverse direction is refused outright: a file written by a newer version may contain
# a field this code would silently drop, and resuming from a session you have partly
# understood is worse than stopping.
KNOWN_SCHEMA_VERSIONS = ("0.1", "0.2")

UNSTATED_CONFIDENCE_KIND = "unstated (recorded before schema 0.2)"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


class UnreadableSessionError(ValueError):
    """Raised when a stored session was written by a schema this code does not know."""


def _migrated_turn(item: dict[str, Any], stored: str) -> dict[str, Any]:
    """Make a stored turn constructible under the current schema.

    Only one field needs it. A 0.1 turn recorded a confidence without recording what the
    number was, which 0.2 refuses; the number is kept and its provenance is marked
    unstated, because it genuinely is. A consumer thresholding on confidence can now see
    that it must not compare this turn against a turn from a named engine -- which is the
    whole reason the field exists, applied to the case where the answer is "nobody wrote
    it down".
    """
    if stored != "0.1":
        return item
    if item.get("confidence") is None or item.get("confidence_kind"):
        return item
    return {**item, "confidence_kind": UNSTATED_CONFIDENCE_KIND}


def load_session(path: Path) -> CanonicalSession:
    data = json.loads(path.read_text())
    stored = data.get("schema_version")
    if stored not in KNOWN_SCHEMA_VERSIONS:
        raise UnreadableSessionError(
            f"{path} declares schema_version {stored!r}; this build knows "
            f"{', '.join(KNOWN_SCHEMA_VERSIONS)}. Resuming from a session that may carry "
            "fields this code would drop is worse than stopping."
        )
    data["turns"] = [
        TranscriptTurn(**_migrated_turn(item, stored)) for item in data.get("turns", [])
    ]
    data["scenes"] = [
        Scene(**{**item, "evidence": Evidence(**item["evidence"])})
        for item in data.get("scenes", [])
    ]
    data["entities"] = [
        Entity(**{**item, "evidence": Evidence(**item["evidence"])})
        for item in data.get("entities", [])
    ]
    data["threads"] = [
        Thread(**{**item, "evidence": Evidence(**item["evidence"])})
        for item in data.get("threads", [])
    ]
    data["review_questions"] = [
        ReviewQuestion(**{**item, "evidence": Evidence(**item["evidence"])})
        for item in data.get("review_questions", [])
    ]
    # A migrated session is rewritten at every stage boundary, so it must declare what it
    # now contains. Leaving 0.1 on a file that has gained a 0.2 field would make the
    # version a record of where the file came from rather than of what is in it, and the
    # next reader would trust the wrong one.
    data["schema_version"] = SCHEMA_VERSION
    allowed = {item.name for item in fields(CanonicalSession)}
    return CanonicalSession(**{key: value for key, value in data.items() if key in allowed})


# The share of a turn a speaker must cover before the label is reported without comment.
# Not a measured threshold and not presented as one: R01 found two thirds of turns from
# some stacks carrying a label that describes only part of the turn, so anything short of
# a clear majority is worth surfacing until a benchmark says otherwise.
ATTRIBUTION_REPORTING_FLOOR = 0.75


def _attribution_is_uncertain(turn: TranscriptTurn) -> bool:
    """Whether a consumer should be told this speaker label is shaky.

    A turn carrying no attribution numbers at all is not uncertain, it is unmeasured, and
    saying otherwise would flag every fixture turn as a problem.
    """
    measured = [
        value
        for value in (turn.speaker_coverage, turn.speaker_purity)
        if value is not None
    ]
    return bool(measured) and min(measured) < ATTRIBUTION_REPORTING_FLOOR


def build_review_package(session: CanonicalSession) -> dict[str, Any]:
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
        # Named things and open threads reach the reviewer, which is what `docs/UX.md`
        # asks the core surface to show. Aliases travel with the entity: the spellings a
        # recognizer disagreed about are the thing a person can settle in seconds.
        # The id travels with each. Keying on the name would be wrong for the reason the
        # name is carried at all: it is the model's proposal, not a resolved identity, and
        # a reviewer settling two spellings into one changes it.
        "entities": [
            {
                "id": entity.id,
                "name": entity.name,
                "kind": entity.kind,
                "aliases": list(entity.aliases),
                "evidence": entity.evidence.__dict__,
            }
            for entity in session.entities
        ],
        "open_threads": [
            {
                "id": thread.id,
                "description": thread.description,
                "evidence": thread.evidence.__dict__,
            }
            for thread in session.threads
        ],
        # Attribution is stated where it is weak, not everywhere. A reviewer does not
        # need to be told about every certain turn, and a summary-first review
        # (D-005) should not become a list of five hundred confidence numbers.
        "uncertain_attribution": [
            {
                "turn_id": turn.id,
                "physical_speaker": turn.physical_speaker,
                "speaker_coverage": turn.speaker_coverage,
                "speaker_purity": turn.speaker_purity,
            }
            for turn in session.turns
            if _attribution_is_uncertain(turn)
        ],
        # The id and the status travel with each question because an answer has to name
        # what it is answering, and a second visit has to be able to tell what is still
        # open. A queue that could only be read was the shape of the promise the four
        # actions made and nothing kept.
        "needs_attention": [
            {
                "id": question.id,
                "status": question.status,
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
    vocabulary: Vocabulary | None = None,
    now: str | None = None,
) -> CanonicalSession:
    """Run or resume the vertical slice and return the canonical session.

    `vocabulary` carries names a person approved in an earlier session into this one. It
    is applied where the entities are produced and nowhere else, so a session already
    analysed is never revised behind the operator's back by an approval made after the
    fact -- whether it should be is a product question, not one this code answers quietly.
    """
    session_id = session_id or source.stem
    session_dir = output_dir / session_id
    canonical_path = session_dir / "canonical-session.json"

    if canonical_path.exists():
        session = load_session(canonical_path)
    else:
        session = CanonicalSession(
            schema_version=SCHEMA_VERSION,
            session_id=session_id,
            source={"kind": source.suffix.lstrip(".") or "unknown", "path": str(source.resolve())},
            status="imported",
        )
        write_json(canonical_path, session.to_dict())

    if not session.turns:
        result = transcript_provider.transcribe(source)
        native_path = session_dir / "processor-native" / "transcript.json"
        write_json(native_path, result.native_artifact)
        session.turns = result.turns
        session.processor_artifacts["transcript"] = str(native_path.relative_to(session_dir))
        session.provenance["transcript_provider"] = getattr(
            transcript_provider, "name", type(transcript_provider).__name__
        )
        session.status = "transcribed"
        write_json(canonical_path, session.to_dict())

    if not session.scenes or not session.summary:
        analysis = analysis_provider.analyze(session.turns)
        if analysis.native_artifact:
            native_path = session_dir / "processor-native" / "analysis.json"
            write_json(native_path, analysis.native_artifact)
            session.processor_artifacts["analysis"] = str(native_path.relative_to(session_dir))
        session.summary = analysis.summary
        session.scenes = analysis.scenes
        session.entities = analysis.entities
        session.threads = analysis.threads
        session.review_questions = analysis.review_questions
        session.provenance["analysis_provider"] = getattr(
            analysis_provider, "name", type(analysis_provider).__name__
        )
        session.provenance["analysis_is_declared_truth"] = bool(
            getattr(analysis_provider, "is_declared_truth", False)
        )
        if vocabulary is not None and vocabulary.entries:
            record_path = session_dir / RECORD_FILENAME
            record = CorrectionRecord.load(record_path, session_id=session.session_id)
            carry_forward(session, vocabulary, record=record, now=now or utc_now())
            if record.entries:
                record.write(record_path)
                session.provenance["corrections"] = {
                    "record": RECORD_FILENAME,
                    "entries": len(record.entries),
                    "last_answered_at": record.entries[-1].answered_at,
                }
        session.status = "analyzed"
        write_json(canonical_path, session.to_dict())

    write_json(session_dir / "review-package.json", build_review_package(session))
    session.status = "review_ready"
    write_json(canonical_path, session.to_dict())
    return session
