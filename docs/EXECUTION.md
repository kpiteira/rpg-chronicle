# Execution model

## Workspace

The public GitHub repository is the software and durable knowledge home. Claude Code is the primary execution environment after bootstrap, with other tools used selectively; the operating model itself assumes no particular one (`docs/DECISIONS.md` D-016).

## Parallel roles

- Technical Program Manager: owns milestones, architecture coherence, priorities,
  dependencies, and substantial specialist goals.
- Reuse research: inspects and probes reusable projects and engines.
- Benchmark research: builds the reproducible public-audio evaluation corpus.
- Review and analysis: builds hierarchical RPG understanding and summary-first review.
- Vault discovery: studies an external reference vault and defines safe integration contracts.
- Goal validator: verifies, in a fresh context, that a pull request delivers its goal.

Specialists are long-lived agents with one active GitHub goal each. They autonomously
own implementation and the complete reviewed pull-request lifecycle. The user notifies
the TPM after a specialist goal merges; the TPM assesses milestone progress and creates
the next substantial goal when appropriate.

## Product maturity

### R0: vertical slice

A public recording travels through import, borrowed processing, canonical transcript, rough scene analysis, summary, and review package.

### R1: useful prototype

Longer recordings, hierarchical summaries, important-name uncertainty, vocabulary correction, and summary-only review.

### R2: personal alpha

Persistent campaigns, corrections, speaker profiles, resumability, capped review queue, and a campaign-change package.

### R3: live-game candidate

Four-hour reliability, fallbacks, partial-result preservation, external-path support, diagnostics, and safe vault preview.

### North star

Automatic ingestion, robust known-speaker recognition, minimal high-value review, safe vault maintenance, campaign search, thread tracking, and next-session preparation.

## Near-term target

**August 11, 2026 targets R1, not R3.** Four milestones cannot be crossed in the
remaining window, and a plan that assumes otherwise will be paid for in unverified
merges rather than in delivered capability.

The August 11 scope is: a real four-hour recording produces a hierarchical summary and a
summary-first review package, reviewed in under three minutes per recorded hour. Vault
writes are explicitly out of scope; campaign notes are copied by hand until the pipeline
has earned trust on real audio.

R2 and R3 remain the direction. They are dated after the first live sessions have
produced evidence, not before.

## Integration rule

Research and implementation run concurrently. Each specialist produces durable outputs
through a GitHub pull request that closes its active goal. The product must remain
runnable as capabilities replace fixtures or borrowed components. No agent commits or
merges directly to `main`.

## Initial convergence point

Select a public RPG excerpt, fetch it locally, process it with a provisional engine, normalize it into the canonical session model, generate a hierarchical summary, and produce a summary-first review package.
