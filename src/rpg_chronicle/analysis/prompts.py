"""What the model is asked, in words no vendor owns.

Every instruction here is about tabletop role-playing sessions and the product's
attention contract. Nothing here knows which model answers, or how it is reached.

`agents/review-analysis.md` names the standing risk for this file: a generic meeting
summariser dressed as RPG understanding. The instructions below are written against
that, which is why they insist on the fiction/table distinction, on unresolved
threads, and on callbacks to earlier events rather than on "key takeaways".
"""

from __future__ import annotations

import json

from ..model import TranscriptTurn
from .decompose import render_turns

_EVIDENCE_RULE = """
Every claim you make must cite the ids of the transcript turns that support it, using
the ids exactly as they appear in brackets at the start of each line. Copy them
character for character, including any leading zeros: `turn-00740` is not `turn-740`.
Cite only ids present in the excerpt you were given. If you cannot support a claim
with a turn id, leave the claim out. An invented id is a failure, not an
approximation, and it will stop the run rather than quietly shorten the summary.
""".strip()

_SPEAKER_RULE = """
Physical speakers and fictional characters are different things and must never be
merged. A label such as `speaker-2` denotes a person at the table; a name spoken in
the story denotes a character in the fiction. One speaker voices several characters,
and the game master usually voices most non-player characters, so speaker labels and
character names are not in one-to-one correspondence. Never present a speaker label as
a character, or a character as a speaker.
""".strip()

_CROSS_CUTTING_RULE = """
Two kinds of finding are worth more than any other, and both come from holding the
whole of what you can see in mind at once rather than reading it in order:

1. **Callbacks.** When something later pays off, contradicts, or answers something
   much earlier, say so explicitly in the summary. An object acquired or lost early
   that turns out to matter late is the clearest case. Naming the two events
   separately is not the same as connecting them, and the connection is the part a
   reader cannot reconstruct for themselves.

2. **One thing under two names.** A person, place, or power is often named one way
   early and another way later: by title and then by name, by reputation and then in
   person, or simply transcribed differently. When two names plausibly denote one
   thing, raise a question asking whether they are the same, and say what the
   evidence is. Do this even when nothing in the transcript states the connection --
   especially then, because that is the case a reader will otherwise never be asked
   about. Listing them as two unrelated entities is a silent error.
""".strip()

_WINDOW_SYSTEM = f"""
You are analysing a transcript excerpt from a session of a tabletop role-playing game
that was played in person around a table. The transcript is automatic and imperfect:
fantasy names are often misheard, and speech is interleaved with table chatter, rules
discussion, and dice.

Your job is to recover what happened in the *story*, and to flag the few things a
human should confirm.

{_EVIDENCE_RULE}

{_SPEAKER_RULE}

{_CROSS_CUTTING_RULE}

Distinguish three registers and do not blend them:
- in-fiction narration and character speech, which is the story;
- table talk about rules, dice, snacks, and scheduling, which is not;
- the game master describing the world, which is story told out of character.

Reply with a single JSON object and nothing else. No prose before or after it, no code
fences. The object has exactly these keys:

{{
  "window_summary": "A paragraph on what happened in this excerpt, in story terms.",
  "scenes": [
    {{
      "title": "Short scene title",
      "summary": "What happened in this scene and what it changed.",
      "turn_ids": ["turn-001", "turn-002"]
    }}
  ],
  "entities": [
    {{
      "name": "Canonical name as best you can tell",
      "kind": "character | place | faction | item | quest",
      "aliases": ["other spellings or names used for the same thing"],
      "turn_ids": ["turn-003"]
    }}
  ],
  "threads": [
    {{
      "description": "An unresolved thread, question, or obligation left open.",
      "turn_ids": ["turn-004"]
    }}
  ],
  "questions": [
    {{
      "issue": "One sentence naming exactly what is uncertain.",
      "recommendation": "Your best answer, or null if you have none.",
      "why_it_matters": "The downstream consequence of getting this wrong.",
      "turn_ids": ["turn-005"],
      "confidence": 0.0,
      "consequence": "low | medium | high"
    }}
  ]
}}

`confidence` is your confidence in the recommendation, between 0 and 1. `consequence`
is how much damage a wrong answer does to the campaign record.

Raise a question only when uncertainty, story importance, and downstream impact
combine to make a wrong answer consequential: the spelling of a central name, whether
a mission was accepted, whether two names are the same entity, who made a decision
that binds the party. Do not raise questions about filler words, table chatter, minor
grammar, or speaker confusion during a joke. Do not raise a question about something
the session deliberately left open: a cliffhanger is the story working, not an error
to be confirmed.
""".strip()

_SYNTHESIS_SYSTEM = f"""
You are assembling one session-level account of a tabletop role-playing game session
from ordered summaries of consecutive excerpts of it. You are not seeing the raw
transcript, only what was recovered from each excerpt in order.

You are the only stage positioned to catch a finding whose two halves fell in
different excerpts, so the following matters more here than anywhere else:

{_CROSS_CUTTING_RULE}

{_EVIDENCE_RULE}

The only turn ids available to you are the ones attached to the material below. Reuse
them; do not construct new ones.

{_SPEAKER_RULE}

Reply with a single JSON object and nothing else. No prose before or after it, no code
fences:

{{
  "summary": "Several paragraphs telling the session as one continuous story, naming
              what changed, what was decided, and what remains open. State callbacks
              between early and late parts of the session explicitly.",
  "questions": [
    {{
      "issue": "One sentence naming exactly what is uncertain.",
      "recommendation": "Your best answer, or null if you have none.",
      "why_it_matters": "The downstream consequence of getting this wrong.",
      "turn_ids": ["turn-005"],
      "confidence": 0.0,
      "consequence": "low | medium | high"
    }}
  ]
}}

Order the questions most important first, and merge duplicates that arrived from
different excerpts.
""".strip()


def _question_budget(max_questions: int) -> str:
    """The attention budget, stated to the model in the same terms the code enforces.

    The number is interpolated here rather than embedded in the templates, because a
    placeholder inside a template that is never substituted is a silent prompt bug --
    it would reach the model as literal braces and nothing would visibly fail.
    """
    return (
        f"You have room for up to {max_questions} questions and no more. That is a "
        "budget to spend, not a target to hit: three questions that matter is a better "
        "outcome than ten, and none at all is right only if nothing here would damage "
        "the campaign record by being recorded wrongly. You are spending a person's "
        "attention, and a reader given eighty questions answers none. Ask the same "
        "thing once."
    )


def window_system_prompt(*, max_questions: int) -> str:
    return f"{_WINDOW_SYSTEM}\n\n{_question_budget(max_questions)}"


def window_user_prompt(turns: list[TranscriptTurn], *, index: int, total: int) -> str:
    """Render one excerpt for analysis.

    The excerpt is positioned within the session because "this is the final stretch"
    changes what is worth recording -- late excerpts are where callbacks land.
    """
    if total == 1:
        header = "This is the complete transcript of the session."
    else:
        header = (
            f"This is excerpt {index + 1} of {total}, in order. "
            "Earlier and later excerpts exist and you cannot see them, so do not "
            "speculate about what happens outside this one."
        )
    return f"{header}\n\nTranscript:\n\n{render_turns(turns)}"


def synthesis_system_prompt(*, max_questions: int) -> str:
    return f"{_SYNTHESIS_SYSTEM}\n\n{_question_budget(max_questions)}"


def synthesis_user_prompt(window_payloads: list[dict[str, object]]) -> str:
    """Render the per-excerpt findings for assembly into one session account."""
    parts = [
        "Ordered findings from each excerpt of the session:",
        "",
        json.dumps(window_payloads, indent=2, ensure_ascii=False),
    ]
    return "\n".join(parts)
