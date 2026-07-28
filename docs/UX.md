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

## Answering, as built

`rpg-chronicle review <session-dir>` walks the `needs_attention` queue. The four actions
above are what it offers, and they now do something: until A02 they were a field in a JSON
file that nothing read.

A question arrives as one screen. Its consequence and confidence, the issue, why it
matters, the recommendation when there is one, the turns the claim cites, and the named
things that evidence points at:

```
[1/4] high consequence · confidence 0.45
  Two names may be the same person: 'the Tallow Warden' and 'Ormunt'.
  Why it matters: He holds the only crypt key, so a split record would lose track of
                  who the party has to deal with.
  Suggested: Treat them as one character, canonically 'the Tallow Warden'.
  Evidence 42.0s–70.0s:
      [turn-006] (speaker-1) The Tallow Warden keeps it. He has kept it since the fire…
      [turn-007] (speaker-2) Ormunt still has that key? I thought the council took it…
      [turn-008] (speaker-1) They tried. Ormunt kept it anyway, and the council has not…
  Named things in this evidence:
    1) the Tallow Warden (character)
    2) Ormunt (character)
  [a]ccept  [c]orrect  [d]efer  [i]rrelevant  [s]kip  [q]uit >
```

There is no way from this screen to the rest of the transcript, and that is the point.
The excerpt is the cited turns, capped at four; the entities offered are the ones this
question's own evidence names. The reviewer sees what the claim rests on and nothing else,
which is what `docs/PRODUCT.md`'s "never assign proofreading homework" means in practice.
D-005 is the standing rule and this surface is the shape of it.

`--answers <file>` takes the same decisions as JSON instead of interactively. It is the
same code path, so the scripted and the typed answer cannot drift apart.

Concretely, on `benchmarks/fixtures/r0_correction_session_1.json`: **four decisions** for a
session of ten turns. Each arrives with the turns it cites — three, two, one and one
respectively, eleven lines of excerpt in total — and each names the entities that evidence
points at. Nothing else is displayed, and there is no command that displays more. A run
that produced eighty of these screens would have failed the attention budget above even if
every one were correct.

### What a correction reaches

Two operations, and no more:

- **revise** — this entity's canonical name and/or kind is wrong. The displaced name
  becomes an alias rather than disappearing, because it is still a spelling the session
  contained.
- **merge** — these two records are one thing. The absorbed names become aliases and the
  evidence widens to cover both.

That is the whole editing vocabulary, deliberately. What a reviewer settles in seconds is
which name is canonical and whether two names are one thing; an operation set that could
rewrite arbitrary text would make this a transcript editor.

### What a correction deliberately does not reach

- **Transcript turns.** Correcting a spelling does not rewrite the turns that contained
  the wrong one. A turn is what the recognizer heard, `docs/PRODUCT.md` says preserve
  original inputs, and one approved spelling loose in a matcher rewrites places nobody
  looked at. The campaign record changes; the recording's transcript does not.
- **Scenes, threads, and the summary.** They are prose the analysis produced. Nothing yet
  restates them after a name changes, so a merged entity can still be named the old way
  inside a scene summary. This is a known gap, not a design position.
- **Earlier sessions.** An approved name reaches sessions analysed *after* it was
  approved. Whether it should reach back into ones already written is a product question
  about what the operator's record means, and it is open.
- **Speaker attribution.** `uncertain_attribution` is reported and cannot be answered.
  Nothing in the queue corrects who spoke a turn.

### What survives an answer

Every answer is appended to `corrections.json` beside the canonical session: the action,
who gave it, when, the question as it was asked, and what each change was *from*. The
engine's original value is the `before` of the first entry that touched a thing, so it is
recoverable rather than merely promised.

An answer that would change what a different person already settled is **refused**, and
nothing is written. `--override` records the disagreement and supersedes it; the earlier
decision stays in the file either way.

### What reaches the next session

An approved name joins `vocabulary.json` beside the session directories, with who approved
it and when. The next run uses it twice: the settled spellings go into the analysis prompt
so a model spells them right in the first place, and any entity that still came back with
an old spelling is renamed deterministically afterwards — which works for any provider,
including one that reads no prompt at all.

Two restraints. Only the canonical name moves: aliases the store knows but this session
never used are not imported, because an alias sits on a claim carrying evidence and
attaching a spelling to turns that never contained it would manufacture support for it.
And a name two people have approved differently is **contested**, so it stops being
applied and stops appearing in prompts until a person settles it.

Every carried-forward change is written to the new session's own `corrections.json`,
attributed to the store rather than to a person. A change in the campaign record with
nothing saying where it came from is the silent edit `AGENTS.md` rule 12 forbids, even
when the change is right.
