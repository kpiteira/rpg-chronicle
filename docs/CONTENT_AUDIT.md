# Content audit

Plan written 2026-07-27 before the audit; findings appended after. All 138 tracked files
at `504acb9`, examined individually.

## Why

`CLAUDE.md` bars committing recordings, transcripts, voice profiles, vault content and
secrets. `README.md` bars private campaign data, session recordings and downloaded
copyrighted audio. Goal #21 committed 1,178 words of verbatim machine transcript of a real
recording anyway, because the goal asked for it on a licence argument the rule does not
recognise. That was found by accident; this is the systematic version.

## The test

Applied to every file, in order:

1. **Is it software, or does it describe software?** Code, tests, configuration,
   documentation, governance. Legitimate.
2. **Is it a measurement or a decision *about* content, rather than content?** Legitimate —
   `D-001` names "reproducible aggregate results".
3. **Is it content?** Legitimate **only** as input to a repeatedly-run test, and only if
   synthetic or anonymised. Otherwise out, regardless of licence.

**Borderline cases decide on: would this be acceptable if it were the operator's own game?**
A name the system must get right is campaign vocabulary. A sentence somebody said at the
table is content. That draws the line by kind, so it cannot be negotiated down word by word.

**A qualifying test must exercise software.** A test that only asserts a data file's own
metadata would pass with `src/` deleted; it is evidence of the file's presence, not of its
usefulness.

**Two tests that were mistaken for each other and are not the criterion:** "does it need the
audio to be useful?" (`fetch_benchmark_media.py` needs audio and is obviously software) and
"does its licence permit it?" (the rule does not mention licence). Both were used during this
work and both were wrong.

---

## Findings by directory

### Root — 8 files, all keep

`.gitignore`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md` — configuration and
governance. `LICENSE` — MIT; required for a public repository to be usable at all.
`pyproject.toml` — build and dependency declaration. `uv.lock` (96 KB, second largest file)
— pins exact dependency versions; without it "it worked on my machine" is unfalsifiable, and
R02 found a resolver bug that only a lockfile makes reproducible.

### `.claude/` — 2 files, all keep

`commands/validate-goal.md` defines the `/validate-goal` slash command. `settings.json` holds
the permission allow/deny list, including the denials that keep `config/paths.yaml` and
`.env` unreadable. Both are tooling.

### `.github/` — 6 files, all keep

`workflows/checks.yml` (the `verify` and `privacy` jobs that branch protection requires),
`workflows/goal-lifecycle.yml` (fails when a role holds more than one active goal),
`ISSUE_TEMPLATE/specialist-goal.yml` and `config.yml`, `pull_request_template.md`,
`copilot-instructions.md`. Process automation.

### `agents/` — 6 files, all keep

Role briefs, 40–81 lines each. These are the instructions a session executes; in this
repository they are as load-bearing as code.

### `config/` — 1 file, keep

`paths.example.yaml`. Worth naming explicitly: this file is the **mechanism that keeps content
out**. It points recordings, session data, vaults and caches at external paths, and the real
copy is gitignored.

### `docs/` — 15 files, all keep

`PRODUCT`, `UX`, `CAPTURE`, `ARCHITECTURE_BOUNDARIES`, `EVALUATION` — product intent.
`OPERATING_MODEL`, `GOALS`, `PARALLEL_EXECUTION`, `EXECUTION`, `MILESTONES`, `DECISIONS`,
`RISKS`, `STATUS` — how the work is run and what was decided. `ANALYSIS` — the analysis
architecture and its cost measurement; its quoted model output is of the *synthetic* fixture,
so it carries no recorded speech. `VAULT_INTEGRATION` — design only; no vault content.

### `src/` — 16 files, all keep

Every module is referenced from at least two other files; there is no dead code. No string
literal in `src/` contains recorded speech — every long literal is a docstring or an error
message.

### `tests/` — 20 files, 19 keep, 1 remove, 1 needs rework

- **Remove: `test_benchmark_transcripts.py`.** It asserts the transcript files' own metadata —
  fingerprint digest, the `usable_for_word_error_rate` flag, attribution fields. Every
  assertion passes with `src/` deleted, and line 27 asserts the transcript directory is
  *non-empty*, so the test is built to fail when the content is removed. It exists because the
  files exist.
- **Rework: `test_benchmark_manifests.py`.** Its 31 tests genuinely exercise
  `validate_benchmark_manifests.py`, which is software — but they run it against the committed
  manifests. When those move out, it must run against purpose-built fixtures instead.
- The other 17 exercise software: the pipeline, the analysis contract, decomposition, vendor
  neutrality, the CLI, transcription and resumption, the merge-gate classifier, the fetch
  script's verification and quarantine, CI configuration, role-name consistency.
  `test_long_fixture.py` imports nothing from `rpg_chronicle` but loads and executes
  `scripts/generate_long_session.py`, testing determinism and the generator's rejection of an
  unknown speaker or filler theme.

### `scripts/` — 9 files, all keep

`validate-goal.sh`, `hooks/classify_command.py`, `hooks/pre-merge-gate.sh`,
`setup-role-worktree.sh`, `install-bootstrap.sh` — the operating model's machinery.
`audio_identity.py`, `fetch_benchmark_media.py`, `generate_long_session.py`,
`validate_benchmark_manifests.py` — tools that operate on external data. Being a tool for
external content is not a reason to exclude the tool.

### `research/` — 32 files, 30 keep, 2 reduce

- **Keep — code (5):** `probes/speech_stack_probe.py`, `score_synthetic.py`,
  `sweep_diarization.py`, `make_synthetic_clip.py`, `run_probe_battery.sh`.
- **Keep — measurements (16):** `probes/results/hiddengrid-*.json` and `scaling-*.json` each
  carry an explicit `redaction` field withholding transcript text; counts and timings only.
  `diarization-threshold-sweep.json` likewise. `runs/*.json` both assert
  `contains_recognized_text: false`. R01 and R02 applied the rule correctly, unprompted.
- **Keep — synthetic (6):** `probes/results/synthetic-*.json` contain full text, of speech no
  person ever said. Noted honestly: nothing executes these; they are research records, which
  is a legitimate category, not a test.
- **Keep — prose (3):** `speech-stack-scorecard.md`, `probes/README.md`, `README.md`.
- **Keep, correcting an earlier finding in this document (2):** `real-audio-run.md` and
  `benchmark-candidates.md` were first recorded here as needing reduction, on a count of
  "~8" and "~14" quoted words. That count was wrong. It came from a regular expression
  treating apostrophes as quote delimiters, so it scored ordinary possessives — "the
  product's own pipeline", "R01's probe" — as quoted speech, along with shell paths.
  Re-read directly: `real-audio-run.md` contains no quotation at all, and
  `benchmark-candidates.md`'s single instance is the **published episode title** taken from
  the source's own metadata, which is a citation and not something anybody said.

  Recorded rather than quietly amended, because a measurement in an audit is exactly the
  kind of number that gets inherited. The criterion is unchanged; the finding under it was
  wrong.

### `benchmarks/` — 23 files, 3 keep, 20 leave or reduce

- **Keep: `fixtures/r0_synthetic_session.json`.** Fake engine output plus expected analysis.
  Consumed by four test files and run twice in CI. Entirely invented.
- **Keep: `fixtures/long_session_plan.json`.** Not a transcript — a *recipe*: 12 beats, 4
  speakers, themed filler pools, and `planted_structure` naming callbacks placed in beat-02 to
  pay off in beat-11. `scripts/generate_long_session.py` expands it; the expansion is
  gitignored. **Commit the recipe, generate the artifact, ignore the output** — the pattern
  this whole audit was groping toward.
- **Keep: `schema/benchmark-manifest.schema.json`.** A contract, not
  data: `redistribution` must be one of three values, `accessed_at` is required, `license_url`
  must be a URI or explicitly null. It forces an annotator to answer what they would skip.
  An earlier draft of this audit required splitting it in two — a catalogue and an answer
  key — reasoning that they would live in different places. They do not: both move to the
  content directory, so the justification does not hold and the requirement was withdrawn on
  the goal before any work was done against it. One schema, staying here as the contract for
  external files.
- **Leave: `manifests/` (6 manifests + README).** Nothing in `src/` reads a manifest — not one
  line. Their only consumers are the validator (which exists because they exist) and
  `fetch_benchmark_media.py`, a tool that downloads audio to an external cache. A manifest is
  input configuration for an operation that happens entirely outside the repository.
- **Leave: `notes/` (6 files).** Per-recording annotation and measurement notes. The
  *generalisations* in them are worth keeping and belong in `research/` prose: channel
  amateur items being single mixed tracks with an L-R residual 34 dB below programme; fantasy names defeating both engines;
  audio level anti-predicting recognition reliability, so measure overlap; 14% of a real
  session yielding no words while containing no silence. The per-item narration follows the
  recordings out.
- **Leave: `fingerprints/` (2).** 14,239 coarse and 6,000 fine dBFS frames. **Not content** —
  no spectral information, nothing reconstructable — so no rule ejects it. It leaves because
  its only job is making a time anchor meaningful to someone holding the audio, and once truth
  sets go it has no remaining purpose here. Tidiness, not the rule; recorded separately so the
  two are not confused.
- **Remove: `transcripts/` (5).** 1,178 words of verbatim machine transcript over 9 minutes of
  a real recording, plus a README and the correction worksheet. A transcript. Deleted rather
  than moved — it is regenerable machine output.

---

## What leaves, and where the capability goes

| Leaves | Goes to | Capability preserved by |
|---|---|---|
| `benchmarks/transcripts/` | deleted | regenerable from the audio at any time |
| `truth` blocks in manifests | `~/.rpg-chronicle/benchmarks/<item>/` | scored locally; the **score** is committed, which `D-001` already permits |
| catalogue manifests | same | `fetch_benchmark_media.py` reads them from there |
| `benchmarks/notes/` per-item narration | same | generalisations lifted into `research/` first |
| `benchmarks/fingerprints/` | same | serves the truth sets it moves with |

Word error rate is not lost. A reference held outside the repository, scored locally, with the
number committed, costs only that a stranger cannot re-derive it — the identical cost already
accepted for the audio itself.

## What this changes about the project's stated blocker

`docs/STATUS.md` says no reference transcript exists, therefore quality is unmeasurable. That
is too strong. `long_session_plan.json` carries **known planted structure**, so "did the
analysis notice a callback planted in beat-02 and paid off in beat-11, across four hours" is
measurable today — no recording, no listener, no rights question. That is the first evaluation
dimension `docs/EVALUATION.md` lists. What synthetic input cannot measure is recognition on
real voices in a real room, which is narrower than "every quality claim", and which the
operator's own sessions will supply once the product runs on them.
