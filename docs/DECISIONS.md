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

### The reliability measurement, and what was changed after it

A third run of the corpus reversed #11 and #14 to **pass**. Their passing rationales named
the goals' own prohibitions as the reason — #14 *"forbids committing media, clips,
derivatives, or full transcripts under any rights position"* — while the manifests, truth
items and rights determinations in their durable outputs went unremarked. The checker was
reading the prohibitions and not the outputs.

R1 was rewritten against that specific miss: two named kinds of material rather than one
sentence with a subordinate clause, the instruction **read the durable outputs, not the
prohibitions**, and #11 and #14 as the worked example of a goal that honours the first kind
while committing the second. Two runs after the change, all five goals classify correctly.

Under the shipped configuration, per goal: #21 blocks 5 of 5; #12 and #17 pass in every
run; #11 and #14 block in 4 of 5, the miss being the run that motivated the rewrite. In
three runs with R1 removed and `--bare`, #21 never blocks on content.

This is tuning against the corpus and should be read as such. What makes it defensible is
that the change clarifies an existing rule from real history rather than inventing one to
catch these two issues, and that the failure it names generalises. What it does not
establish is reliability on a borderline goal the corpus has never seen. N is five runs.

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
- **Reliability is measured and it is not one.** The section above gives the numbers. The
  blatant case is stable; the borderline cases moved once and moved back after the rule was
  rewritten, on N of five runs. A verdict is a reading, not a measurement.
- **The TPM writes the goal, the checker, and the rules** (D-014). A blocking verdict is
  overridable by a `goal-check-override body:<hash>` comment with a reason. That the
  override is the operator's is a **convention, not a control**: the workflow checks no
  author and requires no reason, and an author check would not help, since
  `scripts/check-goal.sh` already posts under the repository owner's token.
- **A goal edited after being checked was not caught automatically.** Corrected in #38;
  see the amendment below. The limit as originally recorded: the workflow did not trigger
  on `edited`, so the hash binding was sound and unreachable, and a mismatch was reported
  only at the next label event.
- **It reports, it does not prevent.** The `require-goal-check` job fails on an issue event;
  nothing removes the label. Same class as the merge gate, and D-015 says why that is
  accepted.

Rule going forward: when a control passes work that turned out to be wrong, check whether
it was measuring the right artifact before hardening it.

### Amendment (#38): the `edited` trigger

`edited` is now in `.github/workflows/goal-lifecycle.yml`. The limit above stands as a
record of what was shipped and why; this is what it cost and what changed.

What it cost is that the binding was **unreachable for the whole of its first week**. Five
goals were activated in that window. Any of them could have been edited after its passing
check and the workflow would have said nothing until the next label event — which, for a
goal that is activated once and then worked, is no event at all. The control was not weak
there; it was absent, while `docs/GOALS.md` described it as present. That is the shape D-017
is about, one layer up: a control that reports a pass it has not established.

What made the trigger acceptable is that its cost was measured rather than assumed. The
constraint it breached was "no new CI minutes", and the honest reading is that an edit to a
*non-goal* issue still starts the workflow. What it does not do is spend a job:
`enforce-single-active-goal` now excludes `edited` outright, because a body change cannot
alter how many goals a role holds, and `require-goal-check` was already gated on
`goal:active`. An edit to anything else evaluates two `if` conditions and runs nothing.

The residual is that the label is still not removed. `require-goal-check` fails the run and
reports; a session that ignores a red check on its own goal issue is not stopped. Same class
as D-015, and the answer is the same: this is a report, and branch protection is the only
boundary.

## D-018: The canonical model carries what its consumers had evidence for

D-006 drew the canonical boundary narrow and said it would grow only when a visible
product increment required it. Three consumers had asked, each with a measurement, and
none had been granted. The cost was no longer theoretical: #20 measured per-turn
attribution quality and had to record it in the engine-native artifact, which
`AnalysisProvider` explicitly forbids a consumer from reading — *"Implementations receive
only canonical turns -- never the original fixture or the engine-native artifact"*. The
producer knew how shaky a speaker label was and the consumer structurally could not.

Three additions, each with a named consumer and a measurement rather than an anticipated
need:

- **`TranscriptTurn.confidence_kind`.** R01 measured that a Whisper decoder
  log-probability and a native token confidence occupy the same 0–1 range and are not the
  same quantity. A confidence with no stated kind is now refused at construction, because
  the ambiguity the field removes can otherwise be reintroduced by omitting it. A
  fixture's confidence is named `declared`, which is D-009's distinction applied to the
  one field where an unnamed number looks exactly like a measured one.
- **`TranscriptTurn.speaker_coverage` and `speaker_purity`.** R01 measured two thirds of
  turns from some stacks carrying a label describing only part of the turn. Two numbers
  rather than one because they fail differently: low coverage means the diarizer heard
  silence, low purity means the turn straddles a speaker change.
- **`CanonicalSession.entities` and `threads`.** A01 recovered them from every window and
  they stopped at the native artifact. Entities merge across overlapping windows **by
  name**, the opposite of how scenes deduplicate by span, because a scene is its span
  while an entity is the same entity wherever it appears. Aliases accumulate and the
  canonical spelling is not resolved: deciding that two spellings are one name is what
  `docs/UX.md` puts in front of a person, and both spellings must survive to be asked.

### What this costs

Entities and threads are now claims, so a fabricated citation aborts the run exactly as it
does for a scene. `rpg_chronicle.analysis.provider` previously validated them loosely on
the stated grounds that *"A four-hour run should not abort over a field nothing consumes"*.
Something consumes them now, and the loose validation went with the reason for it. That is
a real change in failure behaviour on long runs and it is the deliberate side of the same
trade the module already made for every other claim.

### What was refused

- **Per-speaker channel handling.** `research/what-real-recordings-do.md` records that a
  recording carrying per-speaker channels *"would need handling nobody has designed"*, and
  no corpus item has met the case. A canonical representation designed against a guess is
  worse than the diarizer's current refusal.
- **The union of what `docs/VAULT_INTEGRATION.md` and `docs/UX.md` imagine.** Both describe
  entity-shaped data in more detail than any producer emits — relationship changes, quest
  changes, timeline events. Adding them would create fields nothing fills, which is the
  failure this decision's own rule exists to prevent.

### Schema versioning

`0.1` → `0.2`. A `0.1` session loads and resumes, but **not** by defaulting every added
field to empty, which is what this decision first claimed and what a goal-validator run
disproved by producing a real `0.1` session and resuming it. Every `0.1` turn the fixture
and audio paths ever wrote carries a `confidence` and no `confidence_kind` — precisely the
shape `0.2` refuses to construct — so "load with the new fields empty" meant an unhandled
`ValueError` on resumption for every session anyone actually had.

Loading a `0.1` turn therefore keeps the number and marks its provenance
`unstated (recorded before schema 0.2)`. That is the honest answer available: the quantity
was never recorded, and naming it `declared` or guessing an engine would invent provenance
for a number whose provenance is gone. A consumer can see it must not compare that turn
against one from a named engine, which is the field doing its job on the case where nobody
wrote the answer down. The migration applies to `0.1` files only; a `0.2` file that omits
the kind is still refused.

A migrated session is rewritten declaring `0.2`, because it now contains a `0.2` field and
a version that recorded where a file came from rather than what is in it would mislead the
next reader. A session declaring a version this build does not know is refused rather than
loaded, because resuming from a file you have partly understood is worse than stopping.

The general lesson is worth more than the fix: an invariant added to a live type is a
migration whether or not anyone calls it one, and the test that claimed to cover it
hand-wrote the one input shape that survived the invariant by accident.

Rule going forward: a shared contract grows when a consumer can show it cannot act
correctly without the field — not when a consumer would find the field convenient, and not
when a document describes data no producer emits.

## D-019: A control that reports a false pass is worse than no control

Three of this repository's tools claimed more than they did, in the same shape: each had a
path where it produced a confident answer about something it had not checked. They are
recorded together because the shape is the finding, not any one of them.

- **The merge gate and the goal validator decided a verdict by grepping for
  `"verdict": "pass"` anywhere in the output.** That is not the same question as *what is
  the verdict*. Both now read `scripts/verdict_state.py`, one implementation for both, which
  parses exactly one JSON object and returns nothing on anything else. The divergence is
  measured in `tests/test_verdict_state.py` against the grep it replaced: a blocking verdict
  carrying a nested prior verdict, prose around the object, a second object, and non-JSON
  output all cleared the grep and none clear the reader. One case that was *expected* to
  diverge does not, and the test says so: a well-formed finding that quotes `"verdict":
  "pass"` has its quotes escaped by JSON and never matched the grep either. The exposure was
  narrower than the argument for fixing it assumed, and the fix is still right, because
  "narrower" is not "absent" and the grep also cleared unparseable output.
- **`scripts/validate_benchmark_manifests.py` discarded its arguments.** A positional path
  or a `--content-root` was accepted by the shell and dropped, so someone pointing it at a
  second content directory got a clean report about the first one. It now parses both and
  exits non-zero on an argument it does not understand. Silence was the defect; refusing is
  the fix.
- **Two distinct threads citing the same turns collapsed to the first.**
  `_merge_entities_and_threads` keyed threads on the set of cited turn ids alone, so a turn
  opening two obligations at once yielded one thread and the other disappeared with no trace
  for a reader to notice. The key now includes the description.

The last one has a residual worth naming, because it is a trade and not a clean win: two
windows *paraphrasing* one obligation now produce two threads. Nothing available at that
point can tell a paraphrase from a second obligation, so the merge takes the error a
reviewer can see over the error nobody can. A near-duplicate is in the review package; a
dropped thread is nowhere. This is the same reasoning that already governs a disputed entity
kind, and it is the same reasoning D-006 uses about the canonical boundary — the reviewer is
the resolver, and a merge rule that resolves silently is making a product decision it has no
evidence for.

A scene is deliberately left keyed on its span alone. A scene *is* its span, so two scenes
over the same turns are one scene; a thread is a claim about turns, and two claims about the
same turns are two claims.

Rule going forward: when a control cannot answer, it says so. Producing the reassuring
answer instead is the failure mode all three of these shared.
