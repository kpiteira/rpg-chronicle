# Decision log

## D-001: Public software repository

The software, public research, manifests, synthetic fixtures, and reproducible aggregate results live in a public GitHub repository. Private recordings, voices, campaign data, downloaded copyrighted audio, and vault contents remain external.

## D-002: Codex as primary workspace

After bootstrap, Codex is the primary environment for research, implementation, review, and integration. Repository role files provide persistent agent context.

## D-003: Hybrid Path 3 to Path 2

Begin with wrapped reusable components behind stable interfaces, then replace measured bottlenecks progressively.

## D-004: Flexible external storage

Audio, vaults, caches, models, and generated private outputs may live anywhere on local disks or a NAS. Configuration uses explicit paths; symlinks are optional conveniences, not requirements.

## D-005: Summary-first review

The normal workflow never requires manual audio cutting or full-transcript proofreading.

## D-006: Canonical session JSON at processor boundaries

The first vertical slice persists a versioned, engine-neutral canonical session after each
stage. Borrowed processors return their native artifact for debugging, but downstream
analysis and review consume only canonical transcript turns with stable IDs, timestamps,
physical-speaker labels, and confidence. This boundary is deliberately narrow and will
grow only when a visible product increment requires it.

## D-007: Goal-driven long-lived specialist agents

The TPM owns milestone, architecture, priority, and dependency coherence. Each
long-lived specialist receives exactly one substantial active goal through a labeled
GitHub Issue and owns autonomous execution through a Copilot-reviewed pull request and
GitHub merge. No agent commits or merges directly to `main`. After a specialist reports
completion to the user, the user notifies the TPM for outcome assessment and creation of
the next goal when appropriate. This replaces the static repository task backlog and
manual cross-agent handoffs.

## D-008: Analysis is a replaceable provider

Scene, summary, and review-question generation sits behind `AnalysisProvider`, exactly as
transcription sits behind `TranscriptProvider`. The fixture analyzer is an implementation
of that interface rather than a branch inside the pipeline, so a model-backed analyzer is
a wiring change. Providers receive only canonical turns, which makes fixture and model
providers comparable on identical input. Every artifact records which provider produced
it and whether its analysis is declared truth.

## D-009: Tests assert invariants, benchmarks assert quality

Pipeline tests assert properties that must hold for any provider: claims cite turns that
exist, evidence spans match cited turns, completed stages are not repeated. Tests never
assert fixture summary text, because with a fixture provider that proves only that JSON
was copied through and would still pass if the stage were deleted. Analysis quality is
measured in `docs/EVALUATION.md` benchmarks against real audio.

## D-010: Merge is gated by an independent validator

A specialist may not merge its own pull request on its own assessment. A goal validator
runs in a fresh context with only the goal issue, the diff, and the product boundaries,
and posts a verdict to the pull request, bound to the PR's head commit. A `PreToolUse`
hook refuses `gh pr merge` unless the latest verdict is an explicit pass for the current
head. Copilot review is retained for defect detection; it is not a
goal-satisfaction check. See `agents/goal-validator.md`.

## D-011: August 11 targets R1

The near-term deadline is scoped to a useful prototype on real audio with summary-first
review, not to a live-game-ready system with vault writes. Vault application is the
highest-risk and lowest early-value surface, and manual copying is an acceptable interim.
Deadline pressure must never become a reason to relax the merge gate.

## D-012: Capture is part of the product

A permanently placed table microphone and one-time per-player voice enrollment are within
the product constraint, because neither adds a step to game night. Recording consent and
a deletion path are stated obligations. See `docs/CAPTURE.md`.

## D-013: Specialist sessions run on the native goal loop

Claude Code ships a native `/goal` command (v2.1.139+): it sets a completion condition
and an independent evaluator model re-checks it after every turn, keeping the session
working until the condition holds. That is the same independent-evaluator principle as
the goal validator, provided by the platform. The repository's custom `/goal` command
duplicated none of this, shadowed the built-in through undocumented precedence, and
carried two defects precisely because it had never executed. It is deleted. The goal
protocol lives in `AGENTS.md` alone; sessions bootstrap with the native loop using the
per-role condition in `docs/PARALLEL_EXECUTION.md`. Rule going forward: prefer platform
primitives over bespoke mechanisms, and give bespoke commands collision-resistant names
(`/validate` is now `/validate-goal`).

## D-014: The TPM merges through the gate it maintains

The first live run of the goal loop found that a TPM change could not merge at all:
`scripts/validate-goal.sh` requires the pull request to close a goal issue, and TPM
housekeeping closed none, so no verdict could exist and the merge gate refused the merge
forever. The fix is an `agent:technical-program-manager` role label rather than an
exemption in the validator or the hook. TPM work now carries a goal issue, a pull request that closes it, a verdict, and
the same gate as specialist work.

Self-validation is weaker than specialist validation, because the TPM writes both the goal
and the diff. It is accepted with that stated limit: a fresh-context read of the diff and
the tautology check still apply, and the alternative -- the role that maintains the gate
being the only role permitted around it -- is worse. Rule going forward: a control that
cannot be applied to its own maintainer is not yet finished.

## D-015: The merge gate is best-effort by construction

Hardening the gate produced five validator blocks in a row, each naming a shell construct
the classifier did not model. The pattern is worth recording, because the natural response
-- keep enumerating -- was right for some of them and wrong for others.

Where the guarded words could be located directly, enumeration was the defect: listing
command wrappers dropped every wrapper not listed, and scanning for the words themselves
removed the need for a list. Where the question is whether a command treats its argument
as code, no such move exists, because that requires knowing the command. Recognizing
interpreters is therefore a list, and an interpreter absent from it is not guarded.

The goal for that work asked that every refusal the previous gate made must survive. That
was unachievable and it was ours to correct: the old gate refused any occurrence of the
guarded text anywhere in a command, which is precisely the behaviour being fixed -- it
blocked a comment describing the merge command, the test harness for the fix, and a commit
message. A classifier that stops refusing text about commands necessarily stops making
some refusals a text match made.

The gate is a guardrail against an unvalidated merge happening by accident. It is not a
barrier against one pursued deliberately, and no PreToolUse hook could be, since the hook
runs inside the session it constrains. Branch protection is the boundary that holds
without depending on the classifier being clever. Rule going forward: when a control's
stated guarantee cannot be met, correct the statement rather than the evidence, and name
the layer that does hold.
