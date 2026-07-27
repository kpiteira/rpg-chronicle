# Rules a goal may not authorise a violation of

This file is the input to `scripts/check-goal.sh`, which reads a goal issue before it is
activated and blocks one that tells a specialist to do something the project forbids.

It is a **gathering, not a rewrite**. Every rule below already exists somewhere else, and
that source governs. If the two ever disagree, the source is right and this file is stale.
Each rule therefore carries its source, and states what a *violating goal* looks like —
because a checker that only knows the rule catches the blatant case, and every case that
has actually happened here was phrased as a reasonable exception.

## R1 — Content stays out of the repository

Two kinds of material, and a goal has to clear both.

**The recording and anything derived from its sound.** No recording, clip, derivative,
transcript, voice profile, vault content, or secret is committed.

**Anything that describes one particular recording.** Per-recording manifests, answer
keys, truth items, annotation notes, rights determinations, fingerprints. These are
meaningless without the recording they describe, nothing in `src/rpg_chronicle/` has ever
read one, and they were never software. A goal clears the first kind and fails the second
whenever it says *no media, no clip, no transcript* and then makes a manifest or an answer
key for a real recording a durable output. **Read the durable outputs, not the
prohibitions.** The prohibitions are usually correct and they are not what to check.

Source: `CLAUDE.md` (non-negotiable), `docs/CONTENT_AUDIT.md` (the audit and the test).

A licence is **not** the test. A licence answers whether the project *may* publish
something; it never answers whether it *should*. Recorded speech belongs to the people who
spoke it. The deciding question is: *would this be acceptable if it were the operator's own
game?*

Synthetic material is different. Invented sessions under `benchmarks/fixtures/` are test
inputs that `uv run pytest` needs, nobody's speech is in them, and a qualifying test must
exercise the software rather than the data file.

A violating goal looks like: *"the first candidate whose licence permits a committed
reference transcript"* — goal #21, which produced 1,178 words of a real recording's speech
in a public repository. It reads as diligent. It cites the correct licence. It is the
exact failure this rule exists to stop.

A violating goal also looks like goals #11 and #14, which are harder and which a checker
has read both ways. Both forbid committed media outright — #14 says *"No media, clip,
derivative, or full transcript is committed, for any candidate, under any rights
position"* — and both then require, as durable outputs, a per-recording manifest with its
truth items, and a source-linked rights determination per candidate. The prohibition is
honoured and the second kind of material is committed anyway. Those artifacts were removed
from the repository by `docs/CONTENT_AUDIT.md`.

## R2 — Demonstrated capability is never declared truth

A goal's acceptance evidence must test behaviour. Evidence that restates what a fixture
declares is not evidence, and a test that would still pass with the behaviour it names
deleted must not be accepted as one.

Source: `docs/PRODUCT.md` product principles (*"Distinguish demonstrated capability from
declared truth in every artifact and result"*), `agents/goal-validator.md` (tautology
check), `CLAUDE.md` (non-negotiable).

A violating goal looks like: acceptance phrased as *"a test asserts that the manifest's
answer key is present and well-formed"*. Green, meaningless, and load-bearing for the next
agent's confidence.

## R3 — Work the software can do is not assigned to the operator

Repeatable preparation and maintenance are automated. The operator is asked focused
questions with the evidence attached, never given proofreading homework or a manual
preparation ritual.

Source: `docs/PRODUCT.md` product principles (*"Automate repeatable preparation and
maintenance"*, *"Ask focused questions, never assign proofreading homework"*),
`docs/DECISIONS.md` D-005 (summary-first review; the normal workflow never requires manual
audio cutting or full-transcript proofreading).

A violating goal looks like: acceptance that requires the operator to transcribe, to
listen through an unbounded span, or to perform a step the goal could have specified
precisely. Asking the operator to *confirm* something at a named timestamp for a stated
duration is fine; asking them to *find* it is the violation.

## R4 — No agent commits or merges to `main`

Every change, including TPM governance changes, goes through a branch, a pull request, an
independent validator verdict, and the merge gate.

Source: `AGENTS.md`, `CLAUDE.md` (non-negotiable), `docs/DECISIONS.md` D-014.

A violating goal looks like: durable outputs that name a commit on `main`, or acceptance
that would be satisfied without a merged pull request closing the issue.

## R5 — A goal stays inside its role's ownership

A goal assigns work only on paths its role owns, or names the cross-role request
explicitly. Shared contracts (`src/rpg_chronicle/model.py`, `providers.py`,
`docs/ARCHITECTURE_BOUNDARIES.md`) are TPM-owned and change with consumer evidence.

Source: `docs/PARALLEL_EXECUTION.md` (file ownership, and the rule that decides an
unlisted path).

A violating goal looks like: a specialist goal whose durable outputs edit a shared
contract in passing, described as a small addition.

## R6 — The operator is interrupted for product decisions only

Genuine product-input triggers are consequential product decisions the repository, the
issue, and safe reversible choices cannot resolve. Tool choices, implementation choices,
and workflow mechanics are not triggers, and an operational failure is a blocker to
report rather than a question to ask.

Source: `AGENTS.md` goal protocol step 7, `CLAUDE.md`, `docs/GOALS.md`.

A violating goal looks like: a triggers section listing four decisions the goal could have
made itself, which converts an autonomous goal into a queue of interruptions.

## R7 — The goal is structurally complete

The issue states, in the specialist-goal form's own sections: the specialist and
milestone; the outcome and why it matters now; scope, boundaries and constraints; durable
outputs; independently reproducible acceptance evidence; dependencies and risks; and
genuine product-input triggers.

Source: `docs/GOALS.md` (required issue content), `.github/ISSUE_TEMPLATE/specialist-goal.yml`.

A missing section is a block. A section present but empty of content — *"acceptance: the
work is done well"* — is the same block, because the section exists to make the goal
checkable by someone who did not write it.

## What this file is not for

It is not a style guide, and the checker built on it is not a reviewer of goal writing. A
goal that is verbose, or that could have been split, or whose prose could be tightened,
violates nothing here. Noise trains the next session to skip the check, which costs more
than every stylistic improvement it could ever produce.
