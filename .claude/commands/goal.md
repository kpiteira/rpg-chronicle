---
description: Resolve and execute this role's single active GitHub goal
allowed-tools: Bash(gh:*), Bash(git:*), Bash(uv:*), Read, Edit, Write, Grep, Glob
---

Execute the `/goal` protocol defined in `AGENTS.md`. Do not summarise it back to me;
carry it out.

1. Confirm `gh auth status` and that the repository is `kpiteira/rpg-chronicle`.
2. Resolve your single active goal:

   !`gh issue list --state open --label "agent:$CLAUDE_ROLE_ID" --label "goal:active" --json number,title,url,milestone,body`

   If the result does not contain exactly one issue, stop and report an operational
   configuration problem. Do not choose or invent a goal.
3. Read the issue body, its comments, the linked milestone, and any referenced decision
   or risk records.
4. Inspect current repository and pull-request state before changing anything.
5. Post a short start note on the issue.
6. Create `codex/$CLAUDE_ROLE_ID/<issue-number>-<slug>` from current `origin/main` and
   execute autonomously through the pull-request lifecycle in `AGENTS.md`.

Interrupt me only for a consequential product decision as defined in
`docs/OPERATING_MODEL.md`. Tool choice, decomposition, and test design are yours.
