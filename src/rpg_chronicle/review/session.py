"""Answering a session: read what the pipeline wrote, apply, write it all back.

The loop closes here. A session directory holds the canonical session, the review package
a person answered against, and -- once anyone has answered -- the correction record. This
module is the only place that knows all three, so `apply.py` stays a pure transformation
and the CLI stays argument parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..model import CanonicalSession
from ..pipeline import build_review_package, load_session, write_json
from .answers import AnswerSheet
from .apply import ApplyOutcome, apply_answers
from .record import RECORD_FILENAME, CorrectionRecord, utc_now
from .vocabulary import STORE_FILENAME, Vocabulary

CANONICAL_FILENAME = "canonical-session.json"
REVIEW_PACKAGE_FILENAME = "review-package.json"


def default_vocabulary_path(session_dir: Path) -> Path:
    """Beside the session directories rather than inside one.

    A vocabulary belonging to a single session could not carry anything forward, which is
    the half of this goal that exists to not be deferred.
    """
    return session_dir.parent / STORE_FILENAME


@dataclass(frozen=True)
class ReviewedSession:
    session: CanonicalSession
    record: CorrectionRecord
    outcome: ApplyOutcome
    vocabulary_path: Path


def answer_session(
    session_dir: Path,
    sheet: AnswerSheet,
    *,
    vocabulary_path: Path | None = None,
    now: str | None = None,
    override: bool = False,
    dry_run: bool = False,
) -> ReviewedSession:
    """Apply a sheet of answers to a session on disk.

    Nothing is written until every answer has been applied in memory. `apply_answers`
    already refuses a sheet it cannot apply whole; this keeps that promise as far as the
    filesystem, so a refused sheet leaves a session directory it never touched.
    """
    canonical_path = session_dir / CANONICAL_FILENAME
    if not canonical_path.exists():
        raise FileNotFoundError(
            f"{canonical_path} does not exist. Answer a session the pipeline has already "
            "carried to review_ready."
        )
    session = load_session(canonical_path)
    record_path = session_dir / RECORD_FILENAME
    record = CorrectionRecord.load(record_path, session_id=session.session_id)
    resolved_vocabulary = vocabulary_path or default_vocabulary_path(session_dir)
    vocabulary = Vocabulary.load(resolved_vocabulary)

    outcome = apply_answers(
        session,
        sheet,
        record=record,
        vocabulary=vocabulary,
        now=now or utc_now(),
        override=override,
    )

    if not dry_run:
        session.provenance["corrections"] = {
            "record": RECORD_FILENAME,
            "entries": len(record.entries),
            "last_answered_at": record.entries[-1].answered_at if record.entries else None,
        }
        write_json(canonical_path, session.to_dict())
        record.write(record_path)
        # Only when there is something to store. A review of four deferrals settles no
        # name, and an empty vocabulary.json would make the file's existence mean
        # "somebody ran review here" rather than "somebody approved a name here" --
        # a weaker signal than the rest of this module's refusal to write on nothing.
        if vocabulary.entries:
            vocabulary.write(resolved_vocabulary)
        # The package a person answers against must describe the session they now have.
        # Leaving the old one would show the pre-correction names next time it is opened,
        # and the second reviewer would answer a question that no longer exists.
        write_json(session_dir / REVIEW_PACKAGE_FILENAME, build_review_package(session))

    return ReviewedSession(
        session=session,
        record=record,
        outcome=outcome,
        vocabulary_path=resolved_vocabulary,
    )
