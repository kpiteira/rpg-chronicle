"""The durable record of what was answered, what it changed, by whom-or-what, and when.

It sits beside the canonical session rather than inside it. That is not a filing
preference: the canonical session is the current state of the campaign record, and the
question this file answers is what the state used to be. Folding one into the other would
mean either growing the shared contract (`docs/DECISIONS.md` D-018 says that needs a
consumer with evidence) or letting a corrected value overwrite the engine's without trace,
which `AGENTS.md` rule 12 and `docs/PRODUCT.md`'s "preserve original inputs and
provenance" both forbid.

The record is append-only. Each entry states what it changed *from*, so the engine's
original value is the `before` of the first entry that touched a thing -- replayable, not
merely asserted somewhere. A later entry's `before` is the value the earlier entry left,
which is the truthful thing to write down when a person changes their mind twice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """An answer's timestamp, in UTC, to the second.

    Passed in explicitly everywhere it is used rather than called deep in the call stack,
    so a test can assert on a record without freezing the clock globally.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class UnreadableRecordError(ValueError):
    """The correction record on disk is not one this build may append to.

    Its own error class so the CLI can say so as a usage error. A bare `ValueError` from
    three modules down reaches a person as a traceback, and the two cases this covers --
    a record from a schema this build does not know, and a record belonging to another
    session -- are both things an operator can fix once they are told which.
    """


RECORD_FILENAME = "corrections.json"
RECORD_SCHEMA_VERSION = "0.1"
"""Versioned independently of the canonical session.

This file is new and nothing has ever written another shape of it, so starting at 0.1 says
what is true. Tying it to the session's 0.2 would claim a history it does not have.
"""


@dataclass(frozen=True)
class Change:
    """One thing that changed, and what it was before."""

    target: str
    operation: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "operation": self.operation,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class Entry:
    sequence: int
    action: str
    answered_by: str
    answered_at: str
    question_id: str | None = None
    question: dict[str, Any] | None = None
    note: str | None = None
    changes: tuple[Change, ...] = ()
    declined: str | None = None
    """Why nothing was changed, when something was proposed and refused.

    A refusal that leaves no trace is indistinguishable from a refusal that never
    happened, and the case this exists for -- a carried-forward correction meeting a value
    a person set -- is precisely one a reader must be able to see.
    """

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "action": self.action,
            "answered_by": self.answered_by,
            "answered_at": self.answered_at,
            "question_id": self.question_id,
            "question": self.question,
            "note": self.note,
            "changes": [change.to_dict() for change in self.changes],
            "declined": self.declined,
        }


@dataclass
class CorrectionRecord:
    session_id: str
    entries: list[Entry] = field(default_factory=list)
    schema_version: str = RECORD_SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path, *, session_id: str) -> CorrectionRecord:
        if not path.exists():
            return cls(session_id=session_id)
        payload = json.loads(path.read_text())
        stored = payload.get("schema_version")
        if stored != RECORD_SCHEMA_VERSION:
            raise UnreadableRecordError(
                f"{path} declares correction-record schema {stored!r}; this build knows "
                f"{RECORD_SCHEMA_VERSION!r}. Appending to a record you have partly "
                "understood would corrupt the history it exists to preserve."
            )
        recorded = payload.get("session_id")
        if recorded != session_id:
            raise UnreadableRecordError(
                f"{path} records session {recorded!r}, not {session_id!r}. A correction "
                "record belongs to one session; appending across sessions would attribute "
                "one table's decisions to another."
            )
        entries = [
            Entry(
                sequence=item["sequence"],
                action=item["action"],
                answered_by=item["answered_by"],
                answered_at=item["answered_at"],
                question_id=item.get("question_id"),
                question=item.get("question"),
                note=item.get("note"),
                changes=tuple(
                    Change(
                        target=change["target"],
                        operation=change["operation"],
                        before=change.get("before"),
                        after=change.get("after"),
                    )
                    for change in item.get("changes", [])
                ),
                declined=item.get("declined"),
            )
            for item in payload.get("entries", [])
        ]
        return cls(session_id=session_id, entries=entries)

    def append(
        self,
        *,
        action: str,
        answered_by: str,
        answered_at: str,
        question_id: str | None = None,
        question: dict[str, Any] | None = None,
        note: str | None = None,
        changes: tuple[Change, ...] = (),
        declined: str | None = None,
    ) -> Entry:
        entry = Entry(
            sequence=len(self.entries) + 1,
            action=action,
            answered_by=answered_by,
            answered_at=answered_at,
            question_id=question_id,
            question=question,
            note=note,
            changes=changes,
            declined=declined,
        )
        self.entries.append(entry)
        return entry

    def original(self, target: str) -> dict[str, Any] | None:
        """What the engine produced, before any answer touched this target.

        The first entry that changed it holds it. Later entries record later states,
        which is why this reads forwards and stops.
        """
        for entry in self.entries:
            for change in entry.changes:
                if change.target == target:
                    return change.before
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        temporary.replace(path)
