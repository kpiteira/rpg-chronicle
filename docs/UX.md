# Review UX vision

## Core surface

The user reviews the session summary, not the full transcript.

A completed session should show:

- Main story summary
- Key scenes
- Protagonists and NPCs
- Places and factions
- Important actions and decisions
- Quest changes and unresolved threads
- A small `Needs attention` queue

## Question policy

A question is worth human attention when uncertainty, story importance, recurrence, and downstream impact combine to make a wrong answer consequential.

Examples worth asking:

- The spelling of a central NPC or place
- Whether a mission was accepted
- Whether two names refer to the same entity
- Who made a consequential character decision

Examples not worth asking:

- Filler-word uncertainty
- Casual table chatter
- Minor grammar errors
- Speaker confusion during an irrelevant joke

## Attention budget

The queue is capped, and the cap is a number rather than an intention.

`docs/PRODUCT.md` puts the north star at around five minutes of review for a typical
four-hour session. At roughly thirty seconds to read a question, weigh a recommendation,
and act on it, that is **ten questions for a full session**. Ten is therefore the default
bound.

Three properties follow, and all three are load-bearing:

- The bound is enforced in code, not requested of a model. A generator asked for at most
  ten questions usually returns at most ten, and "usually" is not a bound.
- It is a budget, not a target. Three questions that matter is a better outcome than ten.
  An analysis pass that emits eighty questions has failed even if every one is correct.
- What gets kept when the bound binds is the most consequential first, and among equally
  consequential questions the least confident first. A high-consequence claim the system
  is sure about is worth less human attention than one it is guessing at.

A question about something the session deliberately left open — a cliffhanger, an
unresolved thread the table intends to resolve next time — is not a review question. It
is the story working. See `docs/ANALYSIS.md` for a measured case where that distinction
was got wrong.

## Interaction pattern

Each question should include:

- The concise issue
- A recommended answer when possible
- Why it matters
- A short relevant audio excerpt
- Accept, correct, defer, or mark irrelevant actions

Corrections propagate throughout the session and become future vocabulary/context.
