# Role: Review and Analysis

## Mission

Build the hierarchical RPG analysis and summary-first correction workflow that minimizes human attention.

## Read first

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/UX.md`
- `docs/EVALUATION.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/OPERATING_MODEL.md`
- `docs/STATUS.md`
- `docs/BACKLOG.md`
- `CONTRIBUTING.md`

## Ownership

You own the RPG-specific analysis and human-attention contract: scenes, entities,
events, uncertainty, evidence, prioritization, and review actions. The integration
lead owns the canonical session boundary; propose changes with fixtures and consumer
needs rather than editing it speculatively.

## Start now

Take `A01` from `docs/BACKLOG.md`.

1. Work from the existing canonical synthetic fixture rather than waiting for final ASR.
2. Define scene segmentation, scene extraction, session synthesis, entities/events,
   and uncertainty outputs.
3. Produce a versioned review contract and example with ranked questions.
4. Make every important assertion traceable to transcript turns.
5. Record schema changes the integration lead must make, rather than coupling the
   contract to the fixture analysis implementation.

Do not let a generic meeting summary become the product model.

## Handoff gate

- Important claims and questions carry evidence, confidence, and consequence.
- Physical speakers and fictional characters are modeled separately.
- Unsupported important claims can be represented and surfaced.
- The example stays within a bounded attention queue.
- Follow-up measurement needs are explicit for `A02` and `B03`.
