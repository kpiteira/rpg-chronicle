"""What a person can say back, and the small set of changes a saying-back can cause.

The review package has always advertised four actions -- accept, correct, defer,
irrelevant -- and nothing consumed them. This module is the vocabulary of an answer, and
it is deliberately narrow.

Two decisions shape it.

**An action is a disposition; a change is separate and optional.** "Accept" means the
recommendation stands, and a recommendation is free prose that no software can apply. So
an answer records what the person decided about the *question*, and may additionally
carry an operation naming exactly what should change. Fusing the two would either force
every answer to be machine-applicable -- which "defer" never is -- or invite the software
to guess an edit out of a sentence.

**There are two operations, not a general editor.** `docs/PRODUCT.md` promises a few
minutes of targeted review and lists "never assign proofreading homework" as a principle;
D-005 says the normal workflow never requires full-transcript proofreading. An operation
set that could rewrite turn text would make this a transcript editor, which is the thing
the product is not. What a reviewer settles in seconds is which name is canonical and
whether two names are one thing, and those are the two operations here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HUMAN_ACTIONS = ("accept", "correct", "defer", "irrelevant")
"""The four the review package advertises. Nothing else may arrive from a person."""

CARRY_FORWARD_ACTION = "carry_forward"
"""Recorded when the software, not a person, applied a previously approved correction.

It shares the record with human answers on purpose: the goal asks for a record of what was
corrected *by whom-or-what*, and a machine-applied change that lived somewhere else would
be exactly the invisible edit `AGENTS.md` rule 12 forbids.
"""

QUESTION_STATUS = {
    "accept": "accepted",
    "correct": "corrected",
    "defer": "deferred",
    "irrelevant": "irrelevant",
}


class AnswerError(ValueError):
    """An answer the software refuses to act on."""


@dataclass(frozen=True)
class ReviseEntity:
    """Set the canonical name and/or the kind of one entity.

    The displaced name is not discarded, it becomes an alias. A reviewer choosing between
    two spellings is choosing which one leads; the one they did not choose is still a
    spelling the session contained, and dropping it would lose the evidence that the
    disagreement ever happened.
    """

    entity_id: str
    name: str | None = None
    entity_kind: str | None = None

    op = "revise_entity"

    def targets(self) -> tuple[str, ...]:
        return (self.entity_id,)


@dataclass(frozen=True)
class MergeEntities:
    """Fold entities into one, because they were one thing all along.

    The analysis provider deliberately refuses to make this call: `docs/DECISIONS.md`
    D-018 records that two spellings both survive so a person can be asked. This is the
    person answering.
    """

    entity_id: str
    absorbs: tuple[str, ...]
    name: str | None = None
    entity_kind: str | None = None

    op = "merge_entities"

    def targets(self) -> tuple[str, ...]:
        return (self.entity_id, *self.absorbs)


Operation = ReviseEntity | MergeEntities


@dataclass(frozen=True)
class Answer:
    question_id: str | None
    action: str
    operation: Operation | None = None
    note: str | None = None
    answered_by: str | None = None


@dataclass(frozen=True)
class AnswerSheet:
    answered_by: str
    answers: tuple[Answer, ...] = field(default_factory=tuple)


def _operation(payload: Any, *, where: str) -> Operation:
    if not isinstance(payload, dict):
        raise AnswerError(f"{where}: 'operation' must be an object")
    op = payload.get("op")
    entity_id = payload.get("entity_id")
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise AnswerError(f"{where}: 'entity_id' must be a non-empty string")
    name = payload.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise AnswerError(f"{where}: 'name' must be a non-empty string when present")
    entity_kind = payload.get("entity_kind")
    if entity_kind is not None and (not isinstance(entity_kind, str) or not entity_kind.strip()):
        raise AnswerError(f"{where}: 'entity_kind' must be a non-empty string when present")

    if op == ReviseEntity.op:
        if name is None and entity_kind is None:
            raise AnswerError(
                f"{where}: a {ReviseEntity.op!r} that sets neither a name nor a kind "
                "changes nothing; say what it should become or use a different action"
            )
        return ReviseEntity(
            entity_id=entity_id.strip(),
            name=name.strip() if name else None,
            entity_kind=entity_kind.strip() if entity_kind else None,
        )
    if op == MergeEntities.op:
        absorbs = payload.get("absorbs")
        if not isinstance(absorbs, list) or not absorbs:
            raise AnswerError(f"{where}: 'absorbs' must be a non-empty list of entity ids")
        if not all(isinstance(item, str) and item.strip() for item in absorbs):
            raise AnswerError(f"{where}: 'absorbs' must hold non-empty entity ids")
        folded = tuple(dict.fromkeys(item.strip() for item in absorbs))
        if entity_id.strip() in folded:
            raise AnswerError(
                f"{where}: {entity_id!r} cannot absorb itself"
            )
        return MergeEntities(
            entity_id=entity_id.strip(),
            absorbs=folded,
            name=name.strip() if name else None,
            entity_kind=entity_kind.strip() if entity_kind else None,
        )
    raise AnswerError(
        f"{where}: unknown operation {op!r}; this build applies "
        f"{ReviseEntity.op!r} and {MergeEntities.op!r}"
    )


def _answer(payload: Any, *, index: int) -> Answer:
    where = f"answers[{index}]"
    if not isinstance(payload, dict):
        raise AnswerError(f"{where}: each answer must be an object")
    question_id = payload.get("question_id")
    if not isinstance(question_id, str) or not question_id.strip():
        raise AnswerError(f"{where}: 'question_id' must be a non-empty string")
    action = payload.get("action")
    if action not in HUMAN_ACTIONS:
        raise AnswerError(
            f"{where}: 'action' must be one of {list(HUMAN_ACTIONS)}, got {action!r}"
        )
    operation_payload = payload.get("operation")
    operation = None
    if operation_payload is not None:
        if action in ("defer", "irrelevant"):
            # Refused rather than ignored. An answer that says "not now" and also carries
            # an edit is two different intentions in one entry, and picking either one
            # would act on something the person may not have meant.
            raise AnswerError(
                f"{where}: action {action!r} cannot carry an operation. Deferring or "
                "dismissing a question leaves the session unchanged by definition."
            )
        operation = _operation(operation_payload, where=where)
    note = payload.get("note")
    if note is not None and not isinstance(note, str):
        raise AnswerError(f"{where}: 'note' must be a string when present")
    answered_by = payload.get("answered_by")
    if answered_by is not None and (not isinstance(answered_by, str) or not answered_by.strip()):
        raise AnswerError(f"{where}: 'answered_by' must be a non-empty string when present")
    return Answer(
        question_id=question_id.strip(),
        action=action,
        operation=operation,
        note=note.strip() if isinstance(note, str) and note.strip() else None,
        answered_by=answered_by.strip() if answered_by else None,
    )


def parse_answer_sheet(payload: Any, *, default_answered_by: str) -> AnswerSheet:
    """Read a sheet of answers, refusing anything ambiguous.

    Nothing here is repaired or defaulted into a change. An unreadable sheet stops the
    run before a single entity is touched, because a partially applied batch of
    corrections is worse than none: the person would have to work out which of their
    answers landed.
    """
    if not isinstance(payload, dict):
        raise AnswerError("an answer sheet must be a JSON object")
    answered_by = payload.get("answered_by", default_answered_by)
    if not isinstance(answered_by, str) or not answered_by.strip():
        raise AnswerError("'answered_by' must be a non-empty string")
    raw = payload.get("answers")
    if not isinstance(raw, list):
        raise AnswerError("'answers' must be a list")
    answers = tuple(_answer(item, index=index) for index, item in enumerate(raw))
    seen: set[str] = set()
    for answer in answers:
        assert answer.question_id is not None
        if answer.question_id in seen:
            raise AnswerError(
                f"{answer.question_id!r} is answered more than once in the same sheet. "
                "Applying one of two answers to the same question would be a coin flip."
            )
        seen.add(answer.question_id)
    return AnswerSheet(answered_by=answered_by.strip(), answers=answers)


def load_answer_sheet(path: Path, *, default_answered_by: str) -> AnswerSheet:
    return parse_answer_sheet(
        json.loads(path.read_text()), default_answered_by=default_answered_by
    )
