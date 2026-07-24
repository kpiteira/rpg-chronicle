# Contributing

## Before starting

Read `AGENTS.md`, your role brief, `docs/STATUS.md`, and the selected item in
`docs/BACKLOG.md`. Confirm the item is unblocked and does not duplicate work visible
in another branch or worktree.

Use a focused branch:

```text
codex/<role-id>/<backlog-id>-<short-slug>
```

Examples:

```text
codex/benchmark-research/B01-corpus-manifest
codex/review-analysis/A01-review-contract
```

## Scope and repository safety

- Preserve product and architecture boundaries.
- Keep downloaded recordings, private transcripts, real vault contents, model files,
  secrets, and machine-specific configuration out of Git.
- Commit source URLs, licensing notes, scripts, schemas, sanitized fixtures, and
  aggregate results when reproducible.
- Do not mix drive-by cleanup with the assigned backlog item.
- Do not introduce a foundational abstraction without a decision record.

## Verification

Run checks proportional to the change. The baseline repository checks are:

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
```

Research-only changes must still validate structured files and run any probe or
manifest checks they introduce. Documentation changes must leave links, role names,
backlog IDs, and commands internally consistent.

## Commit and pull request

Prefer a small number of intentional commits. A pull request should state:

- primary backlog ID and milestone;
- outcome in user/product terms;
- files or contracts changed;
- reproducible verification;
- privacy/license review where applicable;
- risks, uncertainty, and rejected alternatives;
- cross-role follow-ups;
- screenshots or sample output when the user-visible result changes.

Implementing-agent claims are not acceptance evidence. The integration lead verifies
the artifact or reruns the evidence before integration.

## Handoff format

```text
Backlog:
Branch/commit:
Outcome:
Artifacts:
Verification:
Risks/uncertainty:
Integration notes:
Recommended next step:
```
