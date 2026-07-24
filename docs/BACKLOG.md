# Bootstrap backlog

This file seeds the first GitHub issues. Once an issue exists, add its URL beside the
stable ID and use the issue—not this file—for live assignment and discussion.

Priority order is top to bottom within each workstream. All items below are `ready`
unless their dependency says otherwise.

## Reuse research

### R01 — Compare provisional processing stacks

**Milestone:** M1 · **Priority:** P0

Produce a comparable scorecard for the initial subjects in the role brief, covering
capabilities, platform fit, local/privacy behavior, license, maintenance, integration
surface, native artifacts, and known long-audio limitations.

**Outputs:** `research/reuse-scorecard.md` plus machine-readable source metadata if
useful.

**Acceptance evidence:** Every factual claim has a primary-source link and access date;
criteria map to `docs/EVALUATION.md`; shortlist and rejected options are explicit.

### R02 — Probe the leading processor

**Milestone:** M1 · **Priority:** P0 · **Depends on:** R01 shortlist, B01 manifest

Build the smallest reproducible probe for the leading processor and document how its
output maps to the canonical session boundary.

**Outputs:** probe script/config, sanitized sample output shape, run instructions,
license/runtime notes, replacement triggers.

**Acceptance evidence:** A repeatable run or a precisely documented blocker; no
downloaded restricted media or model artifact committed.

## Benchmark research

### B01 — Define manifest schema and select R0 candidates

**Milestone:** M1 · **Priority:** P0

Define a machine-readable benchmark manifest and identify at least two legally usable
candidate excerpts with contrasting recording conditions.

**Outputs:** schema, populated manifests, source/license notes, selection recommendation.

**Acceptance evidence:** URLs and timestamps resolve; redistribution status is explicit;
no media is committed; fields cover evaluation and reproducibility needs.

### B02 — Add reproducible fetch/preparation workflow

**Milestone:** M1 · **Priority:** P0 · **Depends on:** B01

Create local-only fetch, extraction, and preparation tooling for the selected excerpt.

**Outputs:** scripts and documented commands; generated paths remain ignored.

**Acceptance evidence:** Fresh-cache run produces the expected local artifact and a
recorded checksum/metadata report without modifying source media.

### B03 — Define benchmark result schema

**Milestone:** M1 · **Priority:** P1

Define machine-readable product-level results for plot/entity capture, unsupported
claims, speaker attribution, review burden, runtime, memory, and failures.

**Outputs:** schema plus a synthetic example.

**Acceptance evidence:** Example validates and can represent partial/failed runs.

## Review and analysis

### A01 — Define the R0 analysis and review contract

**Milestone:** M1 · **Priority:** P0

Using the canonical synthetic fixture, specify scenes, important events/entities,
uncertain claims, ranked questions, evidence, and review actions without assuming a
particular LLM.

**Outputs:** versioned schema/contract, example review package, ranking rationale.

**Acceptance evidence:** Every important claim is evidence-linked; physical speaker and
fictional character are not conflated; review questions explain consequence and
confidence.

### A02 — Establish attention-budget evaluation

**Milestone:** M1 · **Priority:** P1 · **Depends on:** A01

Define how question count, evidence-listening time, interaction time, and important
unsurfaced errors are measured.

**Outputs:** rubric and machine-readable result example.

**Acceptance evidence:** The rubric can reject a high-quality summary that requires
excessive review.

## Vault discovery

### V01 — Inventory the reference vault safely

**Milestone:** M2 · **Priority:** P0 · **Dependency:** configured read-only private path

Inspect note types, conventions, authored/generated boundaries, metadata, links, and
prior successful patterns without modifying or copying private content.

**Outputs:** aggregate structural report and sanitized representative fixtures.

**Acceptance evidence:** Privacy review confirms no names, prose, secrets, or unique
campaign content leaked; source vault remains unchanged.

### V02 — Define campaign-change and safety contracts

**Milestone:** M2 · **Priority:** P0 · **Can run if V01 is blocked**

Propose a vault-neutral change package with evidence, confidence, review state,
ownership, preview, idempotency, conflict, rollback, and failure behavior.

**Outputs:** contract/schema, sanitized examples, safe application policy.

**Acceptance evidence:** No action can silently overwrite authored content; ambiguous
updates remain proposals; repeated application behavior is explicit.

## Integration

### I01 — Converge the public R0 vertical slice

**Milestone:** M1 · **Priority:** P0 · **Depends on:** B01, R01, A01

Select one public excerpt and provisional processor from accepted evidence, normalize
its output, integrate the review contract, and preserve a one-command resumable path.

**Acceptance evidence:** All M1 exit criteria relevant to the excerpt pass independently.

### I02 — Integrate campaign-change package preview

**Milestone:** M2 · **Priority:** P1 · **Depends on:** V02, A01

Transform approved review output into a vault-neutral preview without writing a vault.

**Acceptance evidence:** Schema validation, provenance, conflicts, and deterministic
replay are demonstrated with sanitized fixtures.
