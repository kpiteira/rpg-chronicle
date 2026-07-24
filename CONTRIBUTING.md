# Contributing

## Non-negotiable branch rule

No agent commits or merges directly to local or remote `main`. Every change uses a
branch and a GitHub pull request, including documentation, governance, and TPM changes.

Specialist goal branches use:

```text
codex/<role-id>/<goal-issue-number>-<short-slug>
```

Create them from current remote `main`, not a stale local branch:

```bash
git fetch origin
git switch -c codex/<role-id>/<goal-issue-number>-<slug> origin/main
```

## Before implementation

For a specialist `/goal`:

1. resolve exactly one open active goal issue for the role;
2. read the issue, milestone, linked context, and discussion;
3. check existing branches and PRs for duplicate work;
4. comment on the issue that execution has started;
5. inspect the repository and choose an autonomous internal plan.

Keep private recordings, transcripts, vaults, downloaded copyrighted media, models,
secrets, caches, and machine configuration outside Git.

## Commits and verification

Make focused commits that trace to the goal outcome. Update decisions, risks, schemas,
fixtures, and docs with the implementation they explain.

Baseline checks:

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
git diff --check
```

Add proportional product, benchmark, schema, privacy, or recovery evidence required by
the goal. Implementer assertions are not acceptance evidence.

## Open the pull request

Push the branch and open a PR against `main`. The PR must:

- use `Closes #<goal-number>`;
- describe the outcome in product/program terms;
- map evidence to goal acceptance criteria;
- identify architecture, privacy, license, risk, and follow-up implications;
- contain only the active goal's coherent scope.

Do not merge yet.

## Copilot Code Review loop

The specialist owns the complete loop:

1. request GitHub Copilot Code Review on the PR;
2. wait for the review to finish;
3. inspect every top-level and inline comment, including unresolved-thread state;
4. classify each comment as:
   - **implement** — correct and in scope;
   - **reject** — incorrect or harmful, answered with concrete evidence;
   - **defer** — valid but independently scoped, answered with a linked follow-up issue
     or explicit TPM-goal candidate;
   - **already addressed/duplicate** — answer with the relevant code or thread;
5. implement justified feedback and rerun relevant checks;
6. reply to every rejected, deferred, or non-obvious resolution;
7. request another Copilot review when material code changed, the review requested
   changes, or confidence otherwise requires it;
8. resolve threads only after the implementation or response actually addresses them.

Never apply a reviewer suggestion mechanically when it conflicts with product intent,
architecture, evidence, safety, or goal scope.

With GitHub CLI, request the initial review or a re-review using:

```bash
gh pr edit <pr-number> --add-reviewer @copilot
```

This requires a GitHub CLI release that supports the `@copilot` reviewer on GitHub.com.
Check `gh --version` during startup; if the command reports an unsupported reviewer,
update GitHub CLI before continuing the review loop.

Copilot leaves a comment review rather than an approval. Its completion is review
evidence, not proof that the PR is correct or permission to skip independent checks.

## Merge through GitHub

The specialist may merge only when:

- goal acceptance evidence passes;
- required checks pass;
- every review comment has been triaged and addressed;
- any required re-review is complete;
- the PR is current and GitHub reports it mergeable;
- privacy and licensing checks are satisfied.

Merge using GitHub, not local `git merge`. Then verify:

- remote `main` contains the merge;
- the goal issue closed;
- no active label remains on another open goal for the same specialist;
- the merged outcome and important follow-ups are durable.

Finally, report completion to the user. The user decides when to notify the TPM.

## Pull-request review record

The PR description or comments should preserve:

- goal and milestone;
- outcome and changed contracts;
- exact verification;
- Copilot review request and completion;
- implemented, rejected, and deferred feedback;
- architecture/decision/risk impact;
- follow-up goal candidates.
