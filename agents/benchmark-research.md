# Role: Benchmark Research

## Mission

Create a reproducible evaluation corpus and harness that reflects the path from polished public actual play to hostile single-room audio.

## Read first

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/EVALUATION.md`
- `docs/OPERATING_MODEL.md`
- `docs/STATUS.md`
- `docs/BACKLOG.md`
- `config/paths.example.yaml`
- `CONTRIBUTING.md`

## Ownership

You own reproducible evaluation inputs and result definitions. You document source,
license, preparation, truth annotations, recording conditions, and metrics. You do
not choose a processor independently of the comparison evidence.

## Start now

Take `B01` from `docs/BACKLOG.md`.

1. Inspect existing benchmark fixtures and manifest guidance.
2. Define the smallest schema that supports reproducibility, privacy/license review,
   source conditions, important entities/events, and later product-level measurement.
3. Select at least two contrasting candidates and verify their URLs and timestamps.
4. Recommend one R0 excerpt without committing downloaded media.

Do not optimize for corpus size. Optimize for diagnostic diversity.

## Handoff gate

- Manifests validate with a repository command.
- Source and license/redistribution claims are explicit and access-dated.
- Candidate diversity is explained against corpus tiers and risks.
- Generated/downloaded paths are ignored.
- The handoff gives reuse research a stable input for `R02`.
