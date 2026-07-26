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
- `agent:tpm` — program and infrastructure work owned by the TPM itself

`agent:tpm` exists so that TPM changes travel the same path as specialist changes: one
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
5. applies exactly one `agent:*` label and `goal:active`;
6. removes `goal:proposed` or `goal:blocked`;
7. confirms the specialist now has exactly one active open goal.

The TPM may keep future ideas as `goal:proposed`, but should avoid building a detailed
task inventory that becomes stale.

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
