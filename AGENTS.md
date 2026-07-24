# Agent operating guide

This repository is run by one Technical Program Manager (TPM) and long-lived specialist
Codex agents. GitHub Issues hold goals; pull requests hold implementation and review;
the repository holds durable product and technical truth.

## Roles and startup

When the user says `You are the <role> agent. Get started.` or equivalent:

1. Normalize the role to one of the IDs below.
2. Read this file and `agents/<role-id>.md` fully.
3. Read every document in that role's `Read first` list.
4. Inspect the current branch/worktree and GitHub state before changing anything.
5. Continue in that role until the user explicitly changes it.

Supported role IDs:

- `technical-program-manager`
- `reuse-research`
- `benchmark-research`
- `review-analysis`
- `vault-discovery`

“TPM” maps to `technical-program-manager`; “review and analysis” maps to
`review-analysis`; “benchmark,” “reuse,” and “vault” map to their corresponding role.

## Instruction inheritance

This file applies repository-wide. A nested `AGENTS.md` may refine instructions only
below its directory. Role briefs add responsibilities but cannot relax product intent,
privacy rules, ownership boundaries, the `/goal` protocol, or the prohibition on direct
changes to `main`.

## Authority and ownership

The TPM owns milestones, architecture coherence, prioritization, dependencies, and
coarse specialist goals. The TPM assesses outcomes and creates goals; it does not relay
messages between specialists or review every implementation detail.

Specialists own autonomous execution and their complete pull-request lifecycle. A
specialist goal should be substantial enough to produce a meaningful product,
evaluation, research, or integration outcome—not a stream of small assigned tasks.

No agent may commit or merge directly to local or remote `main`. All repository changes,
including TPM governance changes, go through a branch and GitHub pull request.

## `/goal` protocol

When the user tells a specialist `/goal`, the specialist must:

1. Confirm GitHub CLI authentication and repository identity.
2. Find open issues carrying both labels:
   - `agent:<role-id>`
   - `goal:active`
3. Require exactly one active goal for its role.
   - If none or more than one exists, report the operational configuration problem;
     do not invent or choose a goal.
4. Read the issue, linked decisions, milestone, comments, and acceptance evidence.
5. Inspect relevant repository state and existing pull requests.
6. Post a concise start note on the issue and execute autonomously.
7. Ask the user only when genuine product input is required—meaning the repository,
   issue, evidence, and safe reversible choices cannot resolve a consequential product
   decision. Do not ask for routine implementation, tool, or workflow choices.
8. Keep durable findings in commits, issue/PR discussion, research artifacts, decision
   records, or risk records rather than relying on chat.
9. Complete the specialist PR lifecycle below.
10. After GitHub merges the PR and closes the goal, report the outcome to the user.

Operational failures such as authentication, unavailable infrastructure, or an invalid
goal configuration are blockers to report, not product questions. Exhaust safe,
in-scope alternatives before stopping.

## Specialist pull-request lifecycle

For every active goal, the specialist owns:

1. creating `codex/<role-id>/<issue-number>-<slug>` from current remote `main`;
2. making focused commits and keeping the branch current;
3. running acceptance evidence and repository checks;
4. pushing the branch and opening a PR that closes the goal issue;
5. requesting GitHub Copilot Code Review;
6. waiting for review completion without treating silence as approval;
7. critically triaging every review comment:
   - implement justified feedback;
   - reply with evidence when rejecting feedback;
   - explicitly defer sound out-of-scope feedback to a follow-up issue;
8. rerunning relevant verification and requesting another review when changes are
   material or the reviewer requested changes;
9. resolving review threads only after code or an evidence-backed reply addresses them;
10. merging through GitHub only when acceptance evidence passes, review is handled,
    required checks pass, and the PR is mergeable;
11. confirming remote `main` contains the merge and the goal issue is closed.

The specialist must never use a local merge into `main` as a substitute for GitHub.
Detailed commands and review expectations live in `CONTRIBUTING.md`.

## Shared product rules

1. Preserve `docs/PRODUCT.md`.
2. Work toward visible end-to-end product increments.
3. Keep private and copyrighted inputs outside Git.
4. Store reproducible manifests, scripts, synthetic fixtures, and derived aggregate
   results in Git.
5. Document new foundational abstractions in `docs/DECISIONS.md`.
6. Treat the canonical session model as the stable product boundary.
7. Prefer benchmark evidence over reputation or architectural elegance.
8. Never require manual audio cutting or full-transcript proofreading normally.
9. Surface uncertainty according to consequence and confidence.
10. Never silently overwrite authored vault content.

## Definition of goal completion

A specialist goal is complete only when:

- the issue's outcome and acceptance evidence are satisfied;
- durable artifacts and verification are in the repository;
- privacy, licensing, decisions, risks, and follow-ups are explicit;
- all review feedback is implemented, rejected with evidence, or deferred explicitly;
- the PR is merged through GitHub and the goal issue is closed;
- the specialist has reported the completed outcome to the user.

The user then notifies the TPM. The TPM assesses milestone and architecture impact and
creates the next substantial goal when appropriate.

See `docs/OPERATING_MODEL.md` and `docs/GOALS.md` for the full governance model.
