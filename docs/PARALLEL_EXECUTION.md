# Parallel execution

`docs/OPERATING_MODEL.md` defines *what* the roles own. This document defines *how* they
run concurrently as separate agent sessions, and how work is kept from colliding.

Claude Code is the primary environment (`docs/DECISIONS.md` D-016) and the bootstrap
below is written for it. The protocol itself — issues, labels, branches, the validator,
the merge gate — assumes no particular tool.

## Why separate sessions rather than subagents

Each role needs an uncontaminated context. A subagent invoked from a specialist's session
inherits that session's framing, which is precisely the contamination the operating model
tries to avoid. One role, one process, one context window, one worktree.

## Worktree layout

One long-lived worktree per role. Roles never share a checkout, so parallel sessions
never fight over the index or a dirty tree.

```bash
git worktree add ../rpg-tpm              main
git worktree add ../rpg-reuse            -b agent/reuse-research/scratch      origin/main
git worktree add ../rpg-benchmark        -b agent/benchmark-research/scratch  origin/main
git worktree add ../rpg-review           -b agent/review-analysis/scratch     origin/main
git worktree add ../rpg-vault            -b agent/vault-discovery/scratch     origin/main
```

At the start of each goal the specialist rebranches from current `origin/main` onto
`agent/<role-id>/<issue-number>-<slug>` as `AGENTS.md` already requires.

The prefix is `agent/` and not the name of a tool. Work will come from more than one
(D-016), and a prefix naming one of them is wrong for the other. Branches created under
the earlier `codex/` prefix are valid until they merge; nothing enforces the prefix.

## Starting a session

One-time per specialist role (the TPM and goal validator do not use worktrees this way), from the repository root:

```bash
scripts/setup-role-worktree.sh review-analysis
```

Then, in the worktree it created:

```bash
cd ../rpg-review
claude
> You are the review-analysis agent.
> /goal Per the goal protocol in AGENTS.md, the single open issue labelled
  agent:review-analysis and goal:active is implemented, its pull request validated
  and merged, and the issue closed — or the goal is labelled goal:blocked, or a
  consequential product question is awaiting the user.
```

`/goal` here is Claude Code's **native** goal loop, not a repository command: an
independent evaluator re-checks the condition after every turn and keeps the session
working until it holds. The escape clauses are what return control to the user — a
blocked goal or a pending product question ends the loop instead of grinding on. The
repository previously shipped a custom `/goal` command that shadowed this built-in;
it was deleted (see `docs/DECISIONS.md` D-013), and the setup script prints each
role's exact bootstrap lines.

`CLAUDE.md` routes every session through `AGENTS.md`, the role brief, and the role's
`Read first` list, so the bootstrap stays this short.

### Open question: a goal executed outside Claude Code

This bootstrap is the one Claude Code specific part of the operating model, and it is
load-bearing. D-013 chose the native loop precisely because an independent evaluator
re-checks the completion condition after every turn, which is what keeps a session
working to the goal rather than to its own sense of being finished.

Another environment has no equivalent. A goal run there would execute without that
mechanism: the merge gate, the validator, and the labels all still apply, but nothing
holds the session to the condition between turns. That is a real gap and it is not yet
closed. The first person to run a goal outside Claude Code meets it here as a stated
limitation, and should either supply the missing check or accept — in the pull request,
explicitly — that the goal ran without it.

## File ownership

Concurrent PRs collide when two roles edit the same file. Ownership is therefore
declared, and a role that needs a change outside its territory requests it in the owning
role's goal rather than editing across the line.

### The rule that decides an unlisted path

The table below cannot list every path, and a table that tried would be wrong by the
next merge. Decide unlisted paths with this, in order:

1. **A path belongs to the role whose outcomes it serves.** Not the role that happens to
   create it, and not the directory it sits in. A test file belongs to the role that
   owns the code it exercises.
2. **A path that serves the operating model itself** — how roles run, merge, or are
   governed — belongs to the TPM.
3. **A shared *contract* is TPM-owned.** A type, schema, or protocol that other roles
   depend on cannot be split, and changing it changes work the TPM did not see. Changes
   carry consumer evidence.
4. **A shared *composition point* is not.** `cli.py` and `pipeline.py` are where roles
   wire their own work into the product. Any role may add its own wiring there without
   asking. Changing another role's wiring, or the order of the stages, goes through the
   TPM — that is a contract change wearing a wiring change's clothes.
5. **A single file every role must append to** is declared shared-append, with a stated
   convention, and listed as such below. There is exactly one.

A test that exercises a shared contract belongs to the consumer that needed the
guarantee, not to the TPM. A path no rule claims — package plumbing, a shared test fake
— belongs to whoever needs it first, additively, and is recorded here only if a second
role turns out to need it too.

Collisions happen between *files*, not between directories. Two roles adding different
files to the same directory do not conflict, and a rule that stops them is a cost with
no benefit.

### The table

| Path | Owner |
|---|---|
| `docs/` governance, `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `agents/`, `.github/` | TPM |
| `scripts/validate-goal.sh`, `scripts/hooks/`, `scripts/setup-role-worktree.sh`, `scripts/install-bootstrap.sh` | TPM |
| `research/`, transcription provider implementations | Reuse research |
| `benchmarks/manifests/`, `benchmarks/schema/`, `benchmarks/notes/`, `docs/EVALUATION.md`, `scripts/fetch_benchmark_media.py`, `scripts/validate_benchmark_manifests.py` | Benchmark research |
| `src/rpg_chronicle/analysis/` and review code, `benchmarks/fixtures/`, `docs/UX.md`, `docs/ANALYSIS.md`, `scripts/generate_long_session.py` | Review and analysis |
| `docs/VAULT_INTEGRATION.md`, vault adapter contracts | Vault discovery |
| `src/rpg_chronicle/model.py`, `src/rpg_chronicle/providers.py`, `docs/ARCHITECTURE_BOUNDARIES.md` | TPM (shared contract) |
| `src/rpg_chronicle/cli.py`, `src/rpg_chronicle/pipeline.py` | Shared composition — rule 4 |
| `tests/` | Follows the code under test — rule 1 |
| `.gitignore` | Shared-append — see below |

`benchmarks/fixtures/` holds synthetic input authored to exercise the pipeline, not
corpus material: goal #12 added `long_session_plan.json` there for an analysis
measurement, and `r0_synthetic_session.json` drives the vertical slice. Neither serves
the evaluation corpus, so by rule 1 the directory follows the pipeline it feeds while
the rest of `benchmarks/` stays with benchmark research.

The canonical session model is the one file everyone depends on. Changes to it go through
the TPM with consumer evidence, exactly as the operating model states.

### `scripts/`

The directory is split by consumer, not owned as a unit: governance tooling to the TPM,
subsystem tooling to whoever owns the subsystem. Two shapes were considered and
rejected, so that the next reader need not re-derive them:

- **TPM ownership of the whole directory.** Goal #11 added
  `scripts/fetch_benchmark_media.py`, which serves the benchmark corpus and interests no
  other role. Whole-directory ownership would have made that a cross-role request for a
  file nobody else will ever open, and the ownership model exists to prevent collisions
  rather than to centralise. Rule 1 decides it: the script serves benchmark research's
  outcomes.
- **Ownership per subtree, with governance and subsystem tooling separated into
  directories.** This is the same answer as the split above, plus a directory move that
  breaks every existing reference — `CLAUDE.md`, `AGENTS.md`, the hook configuration —
  to encode a boundary the table already states. The cost is real and the benefit is
  naming.

Shared-append was never a candidate here. Scripts are whole files; there is nothing to
append to, and two roles adding different files to one directory do not conflict.

### Protocol definitions and their implementations

`src/rpg_chronicle/providers.py` holds protocol definitions that every role downstream
depends on, which by rule 3 makes it a shared boundary alongside `model.py`. It was
previously assigned to reuse research, which fitted while transcription was the only
provider and stopped fitting the moment a second role needed one: writing an
`AnalysisProvider` is review and analysis's work, and the protocol it implements is not.

An implementation lives in the package of the role that writes it —
`src/rpg_chronicle/analysis/` for the analysis provider, as goal #12 arranged, and the
transcription package for the transcription provider. Only the protocol is shared.

**Transition.** Goal #20 was activated with `providers.py` assigned to reuse research and
completes under that assignment; changing a goal's scope mid-execution is the defect
recorded in `docs/GOALS.md`. The shared-boundary rule applies from the next goal onward.

### `.gitignore`

One root file that every role has reason to append to, which is the concurrent-append
collision this model exists to prevent. It is declared **shared-append** rather than
owned, under one convention:

> Add at the end of the file, under a comment naming the role and the goal issue that
> needed the pattern. Never edit, reorder, or absorb another role's block.

Distinct blocks at distinct offsets merge cleanly, and the comment makes a conflict that
does occur resolvable by keeping both sides.

Two shapes were considered and rejected:

- **A `.gitignore` per owned directory.** This relocates the ownership question instead
  of answering it: goal #12 (review and analysis) needed to ignore
  `benchmarks/fixtures/generated/`, a path owned by benchmark research. The pattern's
  owner is frequently not the directory's owner.
- **TPM ownership of the file.** Both real appends so far — `*.part` and `*.mismatch`
  from goal #11, `benchmarks/fixtures/generated/` from goal #12 — served only the role
  that added them and interested nobody else. Routing a two-line append through a
  cross-role request buys nothing and costs a goal cycle.

## Merge discipline

Four specialists merging into `main` in the same afternoon will produce stale branches.

- Branches must be current with `origin/main` before merge; CI enforces it.
- Merge one PR at a time; the specialist rebases and re-runs checks after a conflict.
- Prefer small, frequent merges over a week-long branch, even when a goal is substantial.

## The merge gate

`AGENTS.md` allows a specialist to merge its own PR after Copilot review. Copilot review
catches defects; it does not catch a PR that quietly delivers less than its goal, and it
did not catch the tautological test in the first slice. A specialist evaluating its own
goal satisfaction after a long implementation context is the rationalization risk the
operating model was written to prevent.

The gate is therefore mechanical, not procedural:

1. The specialist opens the PR and requests Copilot review as today.
2. `scripts/validate-goal.sh` runs the goal validator (`agents/goal-validator.md`) as a
   fresh headless Claude Code process with only the issue, the diff, and the product
   docs in context.
3. The validator posts its verdict as a PR comment, bound to the PR's head commit at
   validation time.
4. A `PreToolUse` hook blocks `gh pr merge` unless the latest verdict is an explicit
   `pass` recorded against the PR's *current* head commit. No verdict, a malformed
   verdict, and a verdict for a superseded commit all fail closed. The same hook
   refuses any `git push` whose destination is `main`, whatever the refspec spelling.

The hook runs inside sessions that share one GitHub identity, so it deters drift
rather than adversaries; the layer that cannot be talked past is branch protection on
`main` requiring the `verify` and `privacy` checks and branch currency. The gate is
best-effort by construction and D-015 records why: it guards against an unvalidated
merge happening by accident, not against one pursued deliberately.

A blocked verdict is not an authority to override. The specialist fixes the finding or
argues it in a PR comment and re-runs the validator, which is a new process with a new
context.

## Attention budget

Running five sessions does not mean five times the throughput if all five ask questions.
The goal protocol's product-input test already limits interruptions; the operating
model's automation removes the rest of the polling. Expect to spend attention on goal
definition and validator escalations, not on relaying messages.

Start with two concurrent specialists. Add the third and fourth only after a full
goal → PR → validated merge cycle has completed without manual intervention.
