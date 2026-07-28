"""The terminal surface a person answers through.

Two properties it is built to keep, both from `docs/PRODUCT.md`.

**No proofreading.** A question is shown with its own evidence and nothing else. The
excerpt is the turns the claim cites, capped, and there is no way from here to page
through the transcript -- not because it would be hard to add, but because adding it would
turn a bounded queue into a document review, which is the failure mode D-005 names.

**Nothing is applied without being said.** Every operation a person can reach is one they
chose from a list of things this question's own evidence points at. The surface never
offers an edit to something the question was not about, so the "one approved spelling
propagates everywhere it matches" risk has no route through this screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TextIO

from ..model import CanonicalSession, Entity, ReviewQuestion
from .answers import Answer, AnswerSheet, MergeEntities, ReviseEntity

EVIDENCE_TURNS_SHOWN = 4
EVIDENCE_CHARS_SHOWN = 220

_ACTIONS = {
    "a": "accept",
    "c": "correct",
    "d": "defer",
    "i": "irrelevant",
}


class ReviewAborted(RuntimeError):
    """The person quit before answering. Nothing is applied."""


@dataclass(frozen=True)
class Console:
    stdin: TextIO
    stdout: TextIO

    def write(self, text: str = "") -> None:
        self.stdout.write(text + "\n")

    def ask(self, prompt: str) -> str:
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            # End of input is not an answer. Treating it as one would apply a default
            # nobody chose, on a queue whose whole point is that a person chose.
            raise ReviewAborted("input ended before the queue was answered")
        return line.strip()


def entities_in_evidence(session: CanonicalSession, question: ReviewQuestion) -> list[Entity]:
    """The entities this question's own evidence points at.

    The link already exists -- both a question and an entity cite transcript turns -- and
    it is what makes a question actionable without the model having to emit a structured
    proposal. An entity the question does not touch is never offered.
    """
    cited = set(question.evidence.turn_ids)
    return [
        entity for entity in session.entities if cited & set(entity.evidence.turn_ids)
    ]


def _excerpt(session: CanonicalSession, question: ReviewQuestion) -> list[str]:
    turns_by_id = {turn.id: turn for turn in session.turns}
    lines = []
    for turn_id in question.evidence.turn_ids[:EVIDENCE_TURNS_SHOWN]:
        turn = turns_by_id.get(turn_id)
        if turn is None:
            continue
        text = turn.text.strip()
        if len(text) > EVIDENCE_CHARS_SHOWN:
            text = text[: EVIDENCE_CHARS_SHOWN - 1].rstrip() + "…"
        speaker = turn.physical_speaker or "unattributed"
        lines.append(f"      [{turn.id}] ({speaker}) {text}")
    remaining = len(question.evidence.turn_ids) - EVIDENCE_TURNS_SHOWN
    if remaining > 0:
        lines.append(f"      … and {remaining} more cited turn(s)")
    return lines


def _show_question(
    console: Console,
    session: CanonicalSession,
    question: ReviewQuestion,
    *,
    position: int,
    total: int,
) -> list[Entity]:
    console.write()
    console.write(
        f"[{position}/{total}] {question.consequence} consequence · "
        f"confidence {question.confidence:.2f}"
    )
    console.write(f"  {question.issue}")
    console.write(f"  Why it matters: {question.why_it_matters}")
    if question.recommendation:
        console.write(f"  Suggested: {question.recommendation}")
    start = question.evidence.start_ms / 1000
    end = question.evidence.end_ms / 1000
    console.write(f"  Evidence {start:.1f}s–{end:.1f}s:")
    for line in _excerpt(session, question):
        console.write(line)
    candidates = entities_in_evidence(session, question)
    if candidates:
        console.write("  Named things in this evidence:")
        for index, entity in enumerate(candidates, start=1):
            aliases = f"  also heard as {', '.join(entity.aliases)}" if entity.aliases else ""
            console.write(f"    {index}) {entity.name} ({entity.kind}){aliases}")
    return candidates


def _pick_entity(console: Console, candidates: list[Entity], prompt: str) -> Entity | None:
    while True:
        raw = console.ask(prompt)
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(candidates):
            return candidates[int(raw) - 1]
        console.write("  Not one of the listed numbers. Press enter to change nothing.")


def _operation(console: Console, candidates: list[Entity]) -> Any:
    if not candidates:
        return None
    console.write(
        "  Change a name? [enter] nothing · [r] rename one · [m] merge two into one"
    )
    choice = console.ask("  > ").lower()
    if choice == "r":
        entity = _pick_entity(console, candidates, "  Which one (number)? ")
        if entity is None:
            return None
        name = console.ask(f"  Correct name for {entity.name!r} (enter to keep): ")
        if not name:
            return None
        return ReviseEntity(entity_id=entity.id, name=name)
    if choice == "m":
        survivor = _pick_entity(console, candidates, "  Which name is the right one (number)? ")
        if survivor is None:
            return None
        absorbed = _pick_entity(console, candidates, "  Which one is the same thing (number)? ")
        if absorbed is None or absorbed.id == survivor.id:
            console.write("  Nothing merged.")
            return None
        return MergeEntities(entity_id=survivor.id, absorbs=(absorbed.id,))
    return None


def collect_answers(
    session: CanonicalSession,
    *,
    console: Console,
    answered_by: str,
    include_answered: bool = False,
) -> AnswerSheet:
    """Walk the queue and return what the person said. Nothing is written here."""
    queue = [
        question
        for question in session.review_questions
        if include_answered or question.status == "open"
    ]
    console.write(f"{session.session_id}: {len(queue)} question(s) need attention.")
    if not queue:
        console.write("Nothing to answer.")
        return AnswerSheet(answered_by=answered_by)

    answers: list[Answer] = []
    for position, question in enumerate(queue, start=1):
        candidates = _show_question(
            console, session, question, position=position, total=len(queue)
        )
        while True:
            choice = console.ask(
                "  [a]ccept  [c]orrect  [d]efer  [i]rrelevant  [s]kip  [q]uit > "
            ).lower()
            if choice == "q":
                raise ReviewAborted("stopped before the queue was answered")
            if choice == "s":
                break
            action = _ACTIONS.get(choice)
            if action is None:
                console.write("  Not one of the offered actions.")
                continue
            operation = None
            if action in ("accept", "correct"):
                operation = _operation(console, candidates)
            note = console.ask("  Note (enter for none): ") or None
            answers.append(
                Answer(
                    question_id=question.id,
                    action=action,
                    operation=operation,
                    note=note,
                )
            )
            break

    return AnswerSheet(answered_by=answered_by, answers=tuple(answers))
