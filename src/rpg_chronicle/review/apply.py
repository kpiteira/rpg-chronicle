"""Turning an answer into a change to the canonical session, and refusing when it should.

Everything here is deliberate about one thing: a correction changes the campaign record,
not the transcript. Turn text is what the recognizer heard and stays exactly as it was --
`docs/PRODUCT.md` says "preserve original inputs and provenance", and a loop that rewrote
turns to match an approved spelling would be both a transcript editor (which D-005 says
this is not) and the over-application the goal names as a risk, since one approved name
matches in places nobody looked at. What changes is the entity: the thing a vault adapter
will eventually write, and the thing a person actually settled.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..model import CanonicalSession, Entity, TranscriptTurn, evidence_for
from .answers import (
    CARRY_FORWARD_ACTION,
    QUESTION_STATUS,
    Answer,
    AnswerError,
    AnswerSheet,
    MergeEntities,
    Operation,
    ReviseEntity,
)
from .record import Change, CorrectionRecord
from .vocabulary import Vocabulary, fold_surface


def entity_snapshot(entity: Entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "name": entity.name,
        "kind": entity.kind,
        "aliases": list(entity.aliases),
        "turn_ids": list(entity.evidence.turn_ids),
    }


def _dedupe(values: list[str], *, excluding: str) -> list[str]:
    """Keep the surface forms worth keeping, in the order they were first seen.

    The canonical name is excluded because it is carried separately, and a name that is
    also its own alias reads as a duplicate spelling that was never in dispute.
    """
    kept: list[str] = []
    for value in values:
        folded = fold_surface(value)
        if folded == fold_surface(excluding):
            continue
        if any(folded == fold_surface(item) for item in kept):
            continue
        kept.append(value)
    return kept


def _by_id(entities: list[Entity], entity_id: str, *, where: str) -> Entity:
    for entity in entities:
        if entity.id == entity_id:
            return entity
    raise AnswerError(
        f"{where}: no entity {entity_id!r} in this session. An operation on something "
        "that is not there would change nothing while appearing to have worked."
    )


def _apply_operation(
    entities: list[Entity],
    operation: Operation,
    turns_by_id: dict[str, TranscriptTurn],
    *,
    where: str,
) -> tuple[list[Entity], Change, bool]:
    """Rewrite the entity list, and report what changed and whether a name was settled.

    Returns the new list, the change to record, and whether the operation resolved which
    surface form of a name is canonical -- which is what may enter the vocabulary. A
    revision that only fixes a kind settles no naming question and must not teach the
    store anything about spelling.
    """
    if isinstance(operation, ReviseEntity):
        target = _by_id(entities, operation.entity_id, where=where)
        before = entity_snapshot(target)
        name = operation.name or target.name
        kind = operation.entity_kind or target.kind
        aliases = _dedupe([*target.aliases, target.name], excluding=name)
        revised = replace(target, name=name, kind=kind, aliases=aliases)
        updated = [revised if item.id == target.id else item for item in entities]
        change = Change(
            target=target.id,
            operation=ReviseEntity.op,
            before={"entities": [before]},
            after={"entities": [entity_snapshot(revised)]},
        )
        return updated, change, operation.name is not None

    if isinstance(operation, MergeEntities):
        survivor = _by_id(entities, operation.entity_id, where=where)
        absorbed = [
            _by_id(entities, entity_id, where=where) for entity_id in operation.absorbs
        ]
        kinds = {item.kind.casefold() for item in [survivor, *absorbed]}
        if len(kinds) > 1 and operation.entity_kind is None:
            # The analysis provider keeps both records precisely when two windows
            # disagree about what kind of thing a name is (D-018). Letting the survivor's
            # kind win by position would resolve that disagreement by accident, in
            # whichever order the model happened to emit them.
            raise AnswerError(
                f"{where}: merging entities of different kinds "
                f"({sorted(kinds)}) needs 'entity_kind' saying which one survives."
            )
        name = operation.name or survivor.name
        kind = operation.entity_kind or survivor.kind
        aliases = _dedupe(
            [
                *survivor.aliases,
                survivor.name,
                *[surface for item in absorbed for surface in (item.name, *item.aliases)],
            ],
            excluding=name,
        )
        turn_ids: list[str] = []
        for item in [survivor, *absorbed]:
            for turn_id in item.evidence.turn_ids:
                if turn_id not in turn_ids:
                    turn_ids.append(turn_id)
        merged = replace(
            survivor,
            name=name,
            kind=kind,
            aliases=aliases,
            # Rebuilt rather than widened by hand: the merged entity is a claim about a
            # larger span, and it goes through the same check every other claim does.
            evidence=evidence_for(turns_by_id, turn_ids),
        )
        absorbed_ids = {item.id for item in absorbed}
        updated = [
            merged if item.id == survivor.id else item
            for item in entities
            if item.id not in absorbed_ids
        ]
        change = Change(
            target=survivor.id,
            operation=MergeEntities.op,
            before={"entities": [entity_snapshot(item) for item in [survivor, *absorbed]]},
            after={"entities": [entity_snapshot(merged)]},
        )
        return updated, change, True

    raise AnswerError(f"{where}: unsupported operation {operation!r}")


def _decisions_by_person(record: CorrectionRecord) -> dict[str, str]:
    """Everything a person has already settled in this session, and who settled it.

    Keys are question ids and entity ids, both namespaced, so one lookup covers "you are
    re-answering somebody's question" and "you are changing something somebody set".
    """
    decided: dict[str, str] = {}
    for entry in record.entries:
        if entry.action not in ("accept", "correct", "defer", "irrelevant"):
            continue
        if entry.question_id:
            decided[f"question:{entry.question_id}"] = entry.answered_by
        for change in entry.changes:
            decided[f"entity:{change.target}"] = entry.answered_by
            for snapshot in (change.before or {}).get("entities", []):
                decided[f"entity:{snapshot['id']}"] = entry.answered_by
    return decided


def _keys_touched(answer: Answer) -> list[str]:
    keys = [f"question:{answer.question_id}"]
    if answer.operation is not None:
        keys.extend(f"entity:{target}" for target in answer.operation.targets())
    return keys


@dataclass(frozen=True)
class ApplyOutcome:
    """What a batch of answers did, in enough detail to print or assert on."""

    applied: tuple[str, ...] = ()
    changed_entities: tuple[str, ...] = ()
    dispositions: dict[str, str] = field(default_factory=dict)
    vocabulary_entries: tuple[str, ...] = ()


def apply_answers(
    session: CanonicalSession,
    sheet: AnswerSheet,
    *,
    record: CorrectionRecord,
    vocabulary: Vocabulary | None,
    now: str,
    override: bool = False,
) -> ApplyOutcome:
    """Apply a sheet of answers to the session, or apply none of it.

    Validation happens for the whole sheet before anything is touched. A half-applied
    batch would leave the person working out which of their answers landed, and the
    review package they answered against would no longer describe the session.
    """
    questions_by_id = {question.id: question for question in session.review_questions}
    for index, answer in enumerate(sheet.answers):
        where = f"answers[{index}]"
        if answer.question_id not in questions_by_id:
            raise AnswerError(
                f"{where}: no question {answer.question_id!r} in this session. The review "
                f"package offers {sorted(questions_by_id)}."
            )

    # Two answers reaching for the same entity in one sheet is not a conflict the software
    # can resolve by ordering: whichever ran second would silently win.
    claimed: dict[str, str] = {}
    for index, answer in enumerate(sheet.answers):
        if answer.operation is None:
            continue
        for target in answer.operation.targets():
            if target in claimed:
                raise AnswerError(
                    f"answers[{index}] and {claimed[target]} both change entity "
                    f"{target!r}. Applying one of them would be an arbitrary choice."
                )
            claimed[target] = f"answers[{index}]"

    decided = _decisions_by_person(record)
    if not override:
        for index, answer in enumerate(sheet.answers):
            for key in _keys_touched(answer):
                owner = decided.get(key)
                if owner is not None and owner != sheet.answered_by:
                    kind, _, name = key.partition(":")
                    raise AnswerError(
                        f"answers[{index}]: {kind} {name!r} was already settled by "
                        f"{owner!r}, and {sheet.answered_by!r} disagrees. Nothing has "
                        "been changed. Re-run with override to record the disagreement "
                        "and supersede it; the earlier decision stays in "
                        "corrections.json either way."
                    )

    entities = list(session.entities)
    turns_by_id = {turn.id: turn for turn in session.turns}
    applied: list[str] = []
    changed: list[str] = []
    dispositions: dict[str, str] = {}
    learned: list[str] = []

    for index, answer in enumerate(sheet.answers):
        where = f"answers[{index}]"
        assert answer.question_id is not None
        question = questions_by_id[answer.question_id]
        answered_by = answer.answered_by or sheet.answered_by

        changes: tuple[Change, ...] = ()
        settles_a_name = False
        if answer.operation is not None:
            entities, change, settles_a_name = _apply_operation(
                entities, answer.operation, turns_by_id, where=where
            )
            changes = (change,)
            changed.append(change.target)

        record.append(
            action=answer.action,
            answered_by=answered_by,
            answered_at=now,
            question_id=answer.question_id,
            # The question travels with the answer. A reader of the record a year later
            # should not have to reconstruct what was being asked from a review package
            # that has since been rewritten.
            question={
                "issue": question.issue,
                "recommendation": question.recommendation,
                "confidence": question.confidence,
                "consequence": question.consequence,
            },
            note=answer.note,
            changes=changes,
        )
        dispositions[answer.question_id] = QUESTION_STATUS[answer.action]
        applied.append(answer.question_id)

        if vocabulary is not None and settles_a_name and changes:
            after = (changes[0].after or {}).get("entities", [])
            if after:
                final = after[0]
                vocabulary.approve(
                    kind=final["kind"],
                    canonical=final["name"],
                    aliases=list(final["aliases"]),
                    approved_by=answered_by,
                    approved_at=now,
                    session_id=session.session_id,
                    question_id=answer.question_id,
                )
                learned.append(final["name"])

    session.entities = entities
    session.review_questions = [
        replace(question, status=dispositions[question.id])
        if question.id in dispositions
        else question
        for question in session.review_questions
    ]
    return ApplyOutcome(
        applied=tuple(applied),
        changed_entities=tuple(changed),
        dispositions=dispositions,
        vocabulary_entries=tuple(learned),
    )


def carry_forward(
    session: CanonicalSession,
    vocabulary: Vocabulary,
    *,
    record: CorrectionRecord,
    now: str,
) -> ApplyOutcome:
    """Apply names a person already approved, to entities this session just produced.

    This is the half of "corrections become future vocabulary" that usually gets
    deferred: storing an approval is easy, and a store nothing reads improves nothing.

    Three restraints, each answering a way this could go wrong.

    *Only the canonical name moves.* Aliases the store knows but this session never used
    are not imported. An alias on an entity is part of a claim carrying evidence, and
    attaching a spelling to turns that never contained it would manufacture support.

    *A contested entry is left alone*, and the fact that it was left alone is written
    down. Two people disagreeing about a name is not something to resolve by timestamp.

    *Every application is recorded* in the same file a person's answers go to, attributed
    to the store rather than to a person. A change that appears in the campaign record
    with nothing saying where it came from is the silent edit rule 12 names, even when
    the edit is right.
    """
    entities: list[Entity] = []
    changed: list[str] = []
    for entity in session.entities:
        entry = None
        for surface in (entity.name, *entity.aliases):
            entry = vocabulary.resolve(entity.kind, surface)
            if entry is not None:
                break
        if entry is None:
            entities.append(entity)
            continue
        if fold_surface(entry.canonical) == fold_surface(entity.name):
            entities.append(entity)
            continue
        if entry.contested:
            record.append(
                action=CARRY_FORWARD_ACTION,
                answered_by="vocabulary",
                answered_at=now,
                note=f"entity {entity.id} ({entity.name!r})",
                declined=(
                    f"{entry.canonical!r} and the spelling this session used are both "
                    "approved, by different people. The name is left as the analysis "
                    "produced it until a person settles it."
                ),
            )
            entities.append(entity)
            continue

        before = entity_snapshot(entity)
        renamed = replace(
            entity,
            name=entry.canonical,
            aliases=_dedupe([*entity.aliases, entity.name], excluding=entry.canonical),
        )
        entities.append(renamed)
        changed.append(entity.id)
        approval = entry.approvals[-1] if entry.approvals else {}
        record.append(
            action=CARRY_FORWARD_ACTION,
            answered_by="vocabulary",
            answered_at=now,
            note=(
                f"approved by {approval.get('by')!r} in session "
                f"{approval.get('session_id')!r} at {approval.get('at')}"
            ),
            changes=(
                Change(
                    target=entity.id,
                    operation="carry_forward_name",
                    before={"entities": [before]},
                    after={"entities": [entity_snapshot(renamed)]},
                ),
            ),
        )

    session.entities = entities
    return ApplyOutcome(changed_entities=tuple(changed))
