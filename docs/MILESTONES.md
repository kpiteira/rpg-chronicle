# Delivery milestones

Milestones are outcome gates, not collections of unrelated tasks. Dates are planning
targets from `docs/EXECUTION.md`; quality gates remain required.

The TPM owns milestone scope, sequencing, and exit assessment. Substantial specialist
goal issues advance one milestone each. Goals may produce evidence for several exit
criteria, but milestones must not become detailed specialist task lists.

## M0 — Team-ready bootstrap

**Outcome:** Each long-lived specialist can resolve one active GitHub goal from `/goal`
and autonomously complete a reviewed PR through GitHub merge.

Exit criteria:

- inherited agent instructions and role-specific ownership are explicit;
- goal labels, issue forms, milestones, contribution flow, and PR templates exist;
- `/goal` resolves exactly one substantial active goal per specialist;
- the specialist-owned Copilot review and GitHub merge loop is documented;
- privacy and copyright boundaries appear in research workflows;
- CI enforces lint, tests, an end-to-end slice run, and the media/privacy guard;
- goal completion notifies the TPM without the user relaying it;
- an independent validator gates merge, failing closed in the implementing session;
  branch protection on `main` is the enforcement layer outside the implementer's
  identity.

## M1 — R0 public vertical slice

**Outcome:** A reproducible public RPG excerpt travels through a provisional processor,
canonical session normalization, scene/session analysis, and summary-first review.

Exit criteria:

- selected source has URL, timestamps, conditions, and licensing notes;
- fetch/preparation steps are reproducible without committing restricted media;
- provisional engine choice is evidence-backed;
- canonical output retains timestamps, physical-speaker distinction, confidence, and
  native processor artifacts;
- every important summary/review assertion links to transcript evidence;
- one command produces the review package and can resume after interruption.

## M2 — R1 useful prototype

**Target:** August 11, 2026. This is the live-game scope; see `docs/EXECUTION.md`.

**Outcome:** Longer inputs produce hierarchical RPG summaries, important-name
uncertainty, vocabulary correction, and summary-only review.

Exit criteria:

- representative corpus covers polished, amateur, room-mic, long, and degraded audio;
- evaluation measures plot/entity capture, unsupported claims, surfaced errors, time,
  memory, question count, and review burden;
- corrections update canonical session outputs and future vocabulary/context;
- review does not require full-transcript proofreading.

## M3 — R2 personal alpha

**Outcome:** Persistent campaigns support corrections, speaker profiles, resumability,
a capped review queue, and campaign-change packages.

Exit criteria:

- interrupted long jobs preserve useful partial results;
- campaign changes are schema-validated, evidence-backed, and previewable;
- authored and generated vault content have explicit ownership rules;
- personal-alpha review target is under three minutes per recorded hour.

## M4 — R3 live-game candidate

**Target:** undated. Scheduled after M2 produces evidence on real four-hour audio.

**Outcome:** The system is reliable enough for a four-hour single-iPad recording and a
safe vault-preview workflow.

Exit criteria:

- multi-hour stress case completes with fallbacks and diagnostics;
- external local/NAS paths work without symlink requirements;
- poor and overlapping speech degrade gracefully;
- important unsupported claims are warned or withheld;
- vault application is previewed, traceable, non-destructive, and recoverable.
