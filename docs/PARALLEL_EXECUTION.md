# Parallel execution with Claude Code

`docs/OPERATING_MODEL.md` defines *what* the roles own. This document defines *how* they
run concurrently as separate Claude Code sessions, and how work is kept from colliding.

## Why separate sessions rather than subagents

Each role needs an uncontaminated context. A subagent invoked from a specialist's session
inherits that session's framing, which is precisely the contamination the operating model
tries to avoid. One role, one process, one context window, one worktree.

## Worktree layout

One long-lived worktree per role. Roles never share a checkout, so parallel sessions
never fight over the index or a dirty tree.

```bash
git worktree add ../rpg-tpm              main
git worktree add ../rpg-reuse            -b codex/reuse-research/scratch      origin/main
git worktree add ../rpg-benchmark        -b codex/benchmark-research/scratch  origin/main
git worktree add ../rpg-review           -b codex/review-analysis/scratch     origin/main
git worktree add ../rpg-vault            -b codex/vault-discovery/scratch     origin/main
```

At the start of each goal the specialist rebranches from current `origin/main` onto
`codex/<role-id>/<issue-number>-<slug>` as `AGENTS.md` already requires.

## Starting a session

```bash
cd ../rpg-review
claude
> You are the review-analysis agent. Get started.
> /goal
```

`CLAUDE.md` routes every session through `AGENTS.md`, the role brief, and the role's
`Read first` list, so the bootstrap prompt stays one line.

## File ownership

Concurrent PRs collide when two roles edit the same file. Ownership is therefore
declared, and a role that needs a change outside its territory requests it in the owning
role's goal rather than editing across the line.

| Path | Owner |
|---|---|
| `docs/` governance, `AGENTS.md`, `agents/`, `.github/` | TPM |
| `research/`, provider implementations in `src/rpg_chronicle/providers.py` | Reuse research |
| `benchmarks/`, `docs/EVALUATION.md` | Benchmark research |
| `src/rpg_chronicle/` analysis and review code, `docs/UX.md` | Review and analysis |
| `docs/VAULT_INTEGRATION.md`, vault adapter contracts | Vault discovery |
| `src/rpg_chronicle/model.py`, `docs/ARCHITECTURE_BOUNDARIES.md` | TPM (shared boundary) |

The canonical session model is the one file everyone depends on. Changes to it go through
the TPM with consumer evidence, exactly as the operating model states.

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
`main` requiring the `verify` and `privacy` checks and branch currency.

A blocked verdict is not an authority to override. The specialist fixes the finding or
argues it in a PR comment and re-runs the validator, which is a new process with a new
context.

## Attention budget

Running five sessions does not mean five times the throughput if all five ask questions.
The `/goal` protocol's product-input test already limits interruptions; the operating
model's automation removes the rest of the polling. Expect to spend attention on goal
definition and validator escalations, not on relaying messages.

Start with two concurrent specialists. Add the third and fourth only after a full
goal → PR → validated merge cycle has completed without manual intervention.
