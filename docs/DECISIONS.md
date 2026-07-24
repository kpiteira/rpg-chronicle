# Decision log

## D-001: Public software repository

The software, public research, manifests, synthetic fixtures, and reproducible aggregate results live in a public GitHub repository. Private recordings, voices, campaign data, downloaded copyrighted audio, and vault contents remain external.

## D-002: Codex as primary workspace

After bootstrap, Codex is the primary environment for research, implementation, review, and integration. Repository role files provide persistent agent context.

## D-003: Hybrid Path 3 to Path 2

Begin with wrapped reusable components behind stable interfaces, then replace measured bottlenecks progressively.

## D-004: Flexible external storage

Audio, vaults, caches, models, and generated private outputs may live anywhere on local disks or a NAS. Configuration uses explicit paths; symlinks are optional conveniences, not requirements.

## D-005: Summary-first review

The normal workflow never requires manual audio cutting or full-transcript proofreading.

## D-006: Canonical session JSON at processor boundaries

The first vertical slice persists a versioned, engine-neutral canonical session after each
stage. Borrowed processors return their native artifact for debugging, but downstream
analysis and review consume only canonical transcript turns with stable IDs, timestamps,
physical-speaker labels, and confidence. This boundary is deliberately narrow and will
grow only when a visible product increment requires it.

## D-007: Goal-driven long-lived specialist agents

The TPM owns milestone, architecture, priority, and dependency coherence. Each
long-lived specialist receives exactly one substantial active goal through a labeled
GitHub Issue and owns autonomous execution through a Copilot-reviewed pull request and
GitHub merge. No agent commits or merges directly to `main`. After a specialist reports
completion to the user, the user notifies the TPM for outcome assessment and creation of
the next goal when appropriate. This replaces the static repository task backlog and
manual cross-agent handoffs.
