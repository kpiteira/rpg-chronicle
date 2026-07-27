# Decision log

## D-001: Public software repository

The software, public research, manifests, synthetic fixtures, and reproducible aggregate results live in a public GitHub repository. Private recordings, voices, campaign data, downloaded copyrighted audio, and vault contents remain external.

## D-002: Codex as primary workspace — SUPERSEDED by D-016

*Historical. This records what was decided, not what to do now; D-016 replaces it.*

This decision held that after bootstrap, Codex would be the primary environment for research, implementation, review, and integration, with repository role files providing persistent agent context. The role-files half of that survives in D-016; the choice of environment does not.

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

## D-016: Claude Code is primary, and the protocol assumes no tool

D-002 made Codex the primary environment after bootstrap. It is not, and has not been:
every goal executed so far ran in Claude Code, and D-013 built the goal loop on a Claude
Code primitive. The operator's intent is Claude Code as the primary environment with
other tools used selectively where they fit.

The repository had encoded the stale decision in the one place it is hardest to change
later — the branch prefix, `codex/`, in three documents (`AGENTS.md`, `CONTRIBUTING.md`,
`docs/PARALLEL_EXECUTION.md`) and the worktree setup script.
The prefix becomes `agent/<role-id>/<issue-number>-<slug>`: tool-neutral, because work
will genuinely come from more than one environment and a prefix naming either is wrong
for the other. The three scratch branches that exist — reuse research, benchmark
research and review analysis — were renamed to `agent/<role-id>/scratch` with
`git branch -m`, which leaves their worktrees undisturbed. Vault discovery's appears in
the setup recipe but has never been created, since no vault goal has run. In-flight goal
branches keep the old prefix until they merge, because renaming a branch under a running
session buys nothing. Nothing enforces the prefix, so this is a documentation change and
not a migration.

One consequence is left open rather than closed, and `docs/PARALLEL_EXECUTION.md` states
it where a session bootstraps: D-013's native `/goal` loop has no equivalent outside
Claude Code, so a goal executed elsewhere runs without the independent per-turn
completion check the operating model depends on. Naming the gap is this decision's
obligation; closing it is not, because nobody has yet tried to run a goal that way and a
mechanism built before the first attempt would be built against a guess.

Rule going forward: a decision that names a vendor should be re-read whenever the work
stops matching it, and the places it leaked into should be listed when it is recorded.

## D-017: The goal is checked before it becomes a mandate

Every control this repository had pointed at a *diff*. `scripts/validate-goal.sh` measures
a pull request against its goal issue, the merge gate refuses a merge without a verdict
bound to the head commit, and CI runs the privacy guard over the tree. All three assume
the goal is sound, and all three correctly pass work that did what a defective goal asked.
Goal #21 asked for a committed human-corrected reference transcript, reasoning from CC BY
3.0; the specialist delivered it, the validator passed the pull request, and 1,178 words of
a real recording's speech entered a public repository. Removing it took two further goals.

`scripts/check-goal.sh` adds the missing reader. It runs a fresh headless process over the
goal issue against `docs/GOAL_RULES.md` — R1 to R7, each carrying the source that governs
it — and posts a JSON verdict bound to a hash of the goal body, so a goal edited after
being checked no longer carries a matching verdict. `docs/GOALS.md` puts it before the
`goal:active` label; `AGENTS.md` has the specialist confirm it before starting.

### What the replay measured

`scripts/replay-goal-check.sh` runs the checker over goals whose outcome is known, with the
corpus chosen by a stated criterion rather than by which goals give the wanted answer.
Goals whose durable outputs committed material about a real recording must block; goals
whose durable outputs were software or governance must pass.

- **#21, #11, #14 block.** #21's verdict quotes its own licence argument back at it. #11
  and #14 block on committed per-recording manifests, answer keys and rights
  determinations — exactly the artifacts `docs/CONTENT_AUDIT.md` later removed.
- **#12 and #17 pass**, with advisories about internal inconsistency and nothing else.
- **#11 and #14 were expected to pass, and did not.** Both were sound under the rules in
  force when they were written; both violate R1 as it now stands. The expectation was
  wrong, not the checker, and the corpus records the mis-prediction rather than being
  refitted around it.

Two goals sit in neither list, because including them either way would be fitting the
corpus to the result:

- **#20** blocks on R5: a reuse-research goal claiming `src/rpg_chronicle/providers.py`, a
  TPM-owned shared contract, with no cross-role request named. That goal merged.
- **#25** blocks on R7, for listing "Two schemas" as a durable output after its own
  amendment withdrew the split. The goal validator raised the same defect as an advisory on
  PR #29 — *after* the work was done. The checker found it in the goal text, before it.

### Whether the rule file does anything

Removing R1 from the rules and re-running #21 was not conclusive at first: it still
blocked, and its verdict named `CLAUDE.md` as the source. The checker runs inside the
repository, where `CLAUDE.md` is loaded automatically and states the content rule as a
non-negotiable, so the mutation had not removed the rule from its reach.

Re-run with `--bare`, which runs the checker from a scratch directory, the answer is
clean: **without R1 the content violation passes unremarked.** The verdict says so
outright — *"no R1 is present, so this verdict covers R2–R7 and says nothing about
whatever R1 governs"* — and blocks instead on an unrelated R5 finding. R1 is load-bearing;
in normal operation it is also duplicated by `CLAUDE.md`, which is why it took removing
the repository context to see.

### Stated limits

- **The block rate on real goals is high** — five of the seven goals replayed block. Each
  block names a rule and quotes the offending text, and each is defensible, but a control
  that blocks most goals is one a session under time pressure will route around. The
  answer is that a block before activation is cheap: #25's would have been one line.
- **Reliability is not demonstrated.** Each goal was checked once or twice, which is
  evidence of capability, not of consistency. Across the runs of #21, the blocking finding
  was R1 whenever R1 was present, and R5 when it was not.
- **The TPM writes the goal, the checker, and the rules** (D-014). A blocking verdict is
  overridable by the operator only, recorded as a `goal-check-override body:<hash>` comment
  with a reason.
- **It reports, it does not prevent.** The `require-goal-check` job fails on an issue event;
  nothing removes the label. Same class as the merge gate, and D-015 says why that is
  accepted.

Rule going forward: when a control passes work that turned out to be wrong, check whether
it was measuring the right artifact before hardening it.
