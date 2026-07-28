# Specialist goal protocol

## Source of truth

GitHub Issues are the only live specialist goal queue. Do not mirror issue state in a
static repository backlog. `docs/STATUS.md` summarizes milestone outcomes and blockers,
not per-agent task assignment.

## Labels

Role labels:

- `agent:reuse-research`
- `agent:benchmark-research`
- `agent:review-analysis`
- `agent:vault-discovery`
- `agent:technical-program-manager` — program and infrastructure work owned by the TPM

Every role label names the role exactly as `agents/<role-id>.md` does.

The TPM label exists so that TPM changes travel the same path as specialist changes: one
active goal, a pull request that closes it, a validator verdict, and the merge gate. Its
independence is weaker, and that limit is recorded in D-014.

Lifecycle labels:

- `goal:proposed` — plausible future outcome, not authorized for execution;
- `goal:active` — the specialist's single current mandate;
- `goal:blocked` — execution cannot progress after safe alternatives are exhausted.

An open issue must never carry more than one role label or more than one lifecycle
label. `.github/workflows/goal-lifecycle.yml` fails the check when a role holds more than
one `goal:active` issue, so a misconfiguration is caught at labelling time rather than at
the next goal resolution. Closing the issue represents completion or cancellation; do not add a redundant
`goal:complete` label.

## Substantial-goal test

A goal is appropriately coarse when:

- it produces one coherent product, research, evaluation, or integration outcome;
- the specialist can choose and sequence its own internal work;
- acceptance can be assessed independently;
- completing it materially advances a milestone;
- splitting it further would mostly prescribe implementation rather than clarify
  ownership or outcomes.

Avoid goals that are single file edits, isolated helper functions, generic “research,”
or a list of unrelated deliverables.

## Required issue content

Use the specialist-goal issue form. Every active goal states:

- specialist and milestone;
- outcome and why it matters now;
- scope boundaries and architecture constraints;
- durable outputs;
- independently reproducible acceptance evidence that tests behaviour rather than
  restating declared truth;
- dependencies and known risks;
- genuine product questions that would justify interrupting the user;
- completion requirement: merged GitHub PR that closes the issue.

## Activation

The TPM:

1. confirms the previous active goal is closed or explicitly deactivated;
2. checks milestone priority and cross-workstream dependencies;
3. creates or refines one issue;
4. assigns the GitHub milestone;
5. runs `scripts/check-goal.sh <issue>` and obtains a passing verdict;
6. applies exactly one `agent:*` label and `goal:active`;
7. removes `goal:proposed` or `goal:blocked`;
8. confirms the specialist now has exactly one active open goal.

The TPM may keep future ideas as `goal:proposed`, but should avoid building a detailed
task inventory that becomes stale.

## The pre-activation check

Step 5 exists because every other control in this repository points at the diff. The goal
validator measures a pull request against its goal issue and the merge gate refuses a
merge without a verdict; both assume the goal is sound, and both correctly pass work that
did what a defective goal asked. Goal #21 asked for a committed reference transcript on a
licence argument, and the transcript merged. See `docs/DECISIONS.md` D-017.

`scripts/check-goal.sh` reads the issue in a fresh headless process against
`docs/GOAL_RULES.md`, which gathers the rules a goal may not authorise a violation of.
It posts its verdict as an issue comment bound to a hash of the goal body, so a goal
edited after being checked no longer carries a matching verdict. The `require-goal-check`
job in `.github/workflows/goal-lifecycle.yml` looks for that comment when an issue
carrying `goal:active` is opened, edited, labelled, unlabelled or reopened. It invokes no
model, and like every other control here it reports rather than prevents.

Editing an active goal's body is a trigger, so an edit after a passing check is reported
immediately rather than at the next label event. Until #38 it was not, which left the
hash binding sound and unreachable — D-017 records what that cost and why the trigger is
now paid for. `AGENTS.md` still has a session confirm the verdict matches the body as it
now reads before starting, because the workflow reports and does not prevent.

A blocking verdict is answered by fixing the goal and re-running the check. It is
**overridable by the operator, not by the TPM**: a comment on the issue containing
`goal-check-override body:<hash>` and the reason. The TPM writing its own override would
make the control worthless, since the TPM writes the goal.

Goals activated before this check existed carry no verdict, and nothing retroactively
demands one. The obligation begins at the next activation.

## Amending a goal already in execution

The goal text is the contract the validator measures the diff against, and it measures
it as the text stands at validation time — not as it stood when the specialist picked it
up. An edit therefore moves the target under work already done.

An amendment to an active goal is safe when it:

- **removes** a requirement;
- **corrects a factual error** in the goal text;
- **resolves an ambiguity** the specialist is blocked on.

Adding an outcome is not. The goal text and the delivered work diverge, and the
specialist is blocked by a gate for something it was never asked to do. Additions wait
for the next goal, unless the specialist is idle or blocked and confirms it has not
started.

This is recorded because it happened. Four Hiddengrid truth items were added to goal #14
while it was being executed, and the validator blocked PR #19 for work that was not in
the goal when execution began. The gate was right; the amendment was the defect.

## Specialist lookup

On `/goal`, a specialist queries open issues for its role and `goal:active`. Exactly one
result is required. The specialist reads the entire issue and discussion, posts a start
note, and owns execution through merge.

Example discovery command:

```bash
gh issue list \
  --state open \
  --label "agent:<role-id>" \
  --label "goal:active" \
  --json number,title,url,milestone
```

## Completion and next goal

The specialist PR includes `Closes #<goal-number>`. After review and checks, the
specialist merges through GitHub and verifies that the issue closed. It reports the
outcome to the user.

The user then notifies the TPM. The TPM assesses milestone and architecture impact and
decides whether to create the next substantial goal. Specialists do not self-assign
follow-up goals, and the TPM does not rely on agents to relay completion to one another.
