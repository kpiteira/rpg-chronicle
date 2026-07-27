# Claude Code session guide

This repository is run by long-lived role agents in separate sessions. Before doing
anything else in a session:

1. Read `AGENTS.md` in full. It is authoritative for roles, ownership, the goal
   protocol, and the pull-request lifecycle.
2. Read `agents/<role-id>.md` for the role you were given, and every document in its
   `Read first` list.
3. Read `docs/PARALLEL_EXECUTION.md` for worktree layout, file ownership, and the merge
   gate.

## Non-negotiable

- Never commit or merge to `main`, locally or remotely.
- Never commit recordings, transcripts, voice profiles, vault content, or secrets. Nor
  per-recording manifests, answer keys or annotation notes: content lives in
  `~/.rpg-chronicle`, and a permissive licence does not make it repository material. See
  `docs/CONTENT_AUDIT.md`.
- Never assert declared fixture truth in a test and present it as capability. See the
  tautology check in `agents/goal-validator.md`.
- Ask the user only for consequential product decisions, per the goal protocol.

## Commands

- Session bootstrap — Claude Code's **native** `/goal` loop with this role's condition;
  the canonical line per role is in `docs/PARALLEL_EXECUTION.md`. There is no custom
  `/goal` command in this repository.
- `/validate-goal <pr>` — run the independent goal validator against a pull request.
- `uv run pytest -q` — test suite.
- `uv run ruff check .` — lint.
- `uv run rpg-chronicle run-fixture benchmarks/fixtures/r0_synthetic_session.json --output /tmp/slice`
  — end-to-end vertical slice.

## Session hygiene

One role per session, one worktree per role. Do not switch roles inside a session; start
a new one so the context stays clean.
