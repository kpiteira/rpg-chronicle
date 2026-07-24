# Agent operating guide

This repository is designed for parallel AI-assisted execution in Codex.

## Starting a role

When the user says `You are the <role> agent. Get started.` or equivalent:

1. Normalize the role name to one of the supported role IDs below.
2. Read this file and `agents/<role-id>.md` fully.
3. Read every file in that role's `Read first` list.
4. Inspect `docs/STATUS.md` and `docs/BACKLOG.md` for current state and the role's
   next unblocked work item.
5. Inspect the current branch/worktree and existing changes before editing.
6. Start the work; do not ask the user to restate repository context.

Supported role IDs and natural-language aliases:

- `integration-lead`
- `reuse-research`
- `benchmark-research`
- `review-analysis`
- `vault-discovery`

“Review and analysis” maps to `review-analysis`; “benchmark,” “reuse,” and “vault”
agents map to their corresponding role IDs.

## Instruction inheritance

This file applies repository-wide. A nested `AGENTS.md`, if one is later added,
may refine instructions only for files below its directory. Role briefs add
responsibilities but do not override product intent, privacy rules, ownership
boundaries, or the definition of done here.

## Shared rules

1. Preserve the product intent in `docs/PRODUCT.md`.
2. Work toward visible end-to-end product increments.
3. Keep private and copyrighted inputs outside Git.
4. Store reproducible manifests, scripts, synthetic fixtures, and derived aggregate results in Git.
5. Do not create a new foundational abstraction without documenting the decision in `docs/DECISIONS.md`.
6. Treat the canonical session model as the stable boundary between replaceable engines and the product.
7. Prefer evidence from benchmark runs over model reputation or architectural elegance.
8. Never require manual audio cutting or full-transcript proofreading as a normal workflow.
9. Surface uncertainty according to consequence and confidence.
10. Do not silently overwrite authored vault content.

## Required operating loop

1. **Orient:** read role context, status, backlog item, and relevant prior artifacts.
2. **Declare:** state the selected backlog ID and intended durable outputs.
3. **Work narrowly:** stay inside role ownership; document cross-boundary needs.
4. **Verify:** run the acceptance evidence named by the backlog item.
5. **Hand off:** update durable artifacts and provide the integration lead with the
   backlog ID, commit/branch, findings, verification, risks, and recommended next step.

If the assigned item is blocked, record the blocker in `docs/STATUS.md` and move to
the next unblocked item for that role. Never wait silently for another agent when
useful fixture-, contract-, or research-based work is available.

## Contribution rules

- Work in an isolated branch/worktree named `codex/<role-id>/<backlog-id>-<slug>`.
- One branch should address one primary backlog item.
- Do not edit another role's owned artifact merely to make it convenient; propose
  the change in the handoff or coordinate through a shared contract.
- Add significant new architectural choices to `docs/DECISIONS.md`.
- Add newly discovered material risks to `docs/RISKS.md`.
- Update `docs/STATUS.md` only with facts that another agent needs to coordinate.
- Follow `CONTRIBUTING.md` for tests, commits, and pull-request evidence.
- Never commit private/copyrighted inputs, secrets, caches, or generated runtime data.

## Definition of done

Work is done only when:

- the promised durable artifact exists in the repository;
- its evidence or verification is reproducible;
- relevant docs/manifests/tests are updated together;
- uncertainties, rejected options, and follow-up work are explicit;
- the result is ready for integration review without relying on chat history.

## Collaboration model

Specialist agents work in isolated Codex worktrees or branches. They commit durable findings and bounded changes. The integration lead reviews and converges work into the runnable product.

The repository is shared memory. Important findings belong in code, tests, manifests, research notes, decision records, or issue/PR descriptions, not only in chat.

See `docs/OPERATING_MODEL.md` for ownership, dependencies, handoff format, and
conflict resolution.
