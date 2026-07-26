# Current project status

Last updated: 2026-07-26

Claims that changed in this round cite the merged artifact or the goal that established
them. Pull-request descriptions are not sources: several figures in this round's
descriptions did not survive validation, and this document tracks what was verified.
Longer-standing facts are inherited and are not individually sourced here.

## Current outcome

The repository has a verified synthetic R0 skeleton, now with a real analysis provider
behind it:

```text
fixture processor output
→ canonical transcript turns
→ scene/session analysis, from a fixture or from a model
→ evidence-backed summary-first review package
```

The path is resumable, preserves the processor-native artifact, and — since #20 merged —
carries real audio. `run-audio` takes the Hiddengrid excerpt from a verified media file
to a review package, with `whisper.cpp` and `sherpa-onnx` behind `TranscriptProvider`.

## Active milestone

`M2 — R1 useful prototype`.

**`M1 — R0 public vertical slice` is met.** All six exit criteria in
`docs/MILESTONES.md` hold against the merged artifacts, the last three on real audio
rather than on the fixture:

- source provenance, reproducible fetch, and evidence-backed engine choice — #11 and #10;
- canonical output retaining timestamps, speaker distinction, confidence and the
  processor-native artifact — 301 of 301 turns carry timestamps and confidence, 292
  carry a speaker label, both native artifacts are retained
  (`research/runs/hiddengrid-600s-first-run.json`);
- every important assertion linking to transcript evidence — 6 claims citing 72 distinct
  turn ids, none citing a turn that does not exist, enforced in code rather than asserted;
- one resumable command — `run-audio`, with resumption demonstrated by removing the
  guard and showing the tests fail.

What that milestone does **not** say, and what nobody should read into it: nothing here
measures how *well* the path carries audio. It ran on ten minutes, not four hours.

## Accepted facts

### Lifecycle

- Five specialist goals have completed the full issue → Copilot-reviewed PR → validated
  → merged lifecycle: #11, #10, #12, #14, #20. The validator blocked three of them at
  least once, and each block named a defect that would otherwise have merged.

### Transcription

- A provisional engine is selected on measured evidence:
  **`whisper.cpp` with Metal, running `ggml-large-v3-turbo`**
  (`research/speech-stack-scorecard.md`). It was not the fastest thing probed; it was
  chosen because a faster option failed outright on long audio without an explicit
  chunk parameter, and because it is the only probed recognizer that is not
  Apple-Silicon-only.
- **Diarization is the unsolved half.** `sherpa-onnx` is adopted as the best available
  local placeholder and does not recover the true speaker count at any clustering
  threshold probed (`research/probes/results/diarization-threshold-sweep.json`). Its
  labels are carried through and marked unreliable rather than trusted.
- Those probes measure cost and output shape, not accuracy. No word error rate has been
  computed by anything in this repository, because no reference transcript exists.
- Both engines are wired in behind `TranscriptProvider` as two separate components
  (#20), so the unreliable half can be replaced without touching the reliable one. A
  600-second excerpt produced 301 turns in 159.7 s of wall clock on the operator's
  machine, and 23 distinct speaker labels for a recording with far fewer speakers —
  diarization behaving exactly as the probes measured it.

### Analysis

- Analysis is a real model-backed provider behind a vendor-neutral seam
  (`docs/ANALYSIS.md`, `src/rpg_chronicle/analysis/`). A vendor is named in one backend
  module and at the point where a backend is selected, and nowhere else;
  `tests/test_vendor_neutrality.py` fails the commit that leaks one further.
- `--analysis fixture` remains the default **for `run-fixture`**, which is what CI runs
  and CI holds no credential. `run-audio` defaults to the model instead, deliberately:
  CI cannot run it at all, since the audio is not and cannot be in the repository, and
  recognized audio has no declared truth to replay. Running `run-audio` therefore spends
  the operator's subscription, which the model backend reaches through a headless
  process.
- The measurement behind it is of **scale and structure on a synthetic transcript with
  deliberately planted long-range structure**, not of quality on recorded play. No real
  session has been recorded, transcribed, or analysed.

### Benchmark corpus

- Six candidates carry manifests with a versioned validating schema, explicit rights
  states read from source markup with access dates, and reproducible source evidence.
- Rights states differ and the differences matter more than the count. Two candidates
  are Creative Commons Attribution 3.0 with local processing permitted; two are
  Standard YouTube Licence with local processing recorded as restricted; Critical Role
  is reference-only because no redistribution permission was identified.
- The Hiddengrid excerpt is the recommended R0 processing input. Its licence is
  **CC BY-NC-SA 3.0**, corrected at #11 from an earlier record of CC BY-NC-ND 4.0, and
  its redistribution is restricted independently of the licence because Shadowrun
  rights sit with a third party. A 2026-07-26 fetch verified the excerpt reproducibly
  without committing the media.
- Four candidates carry multi-hour excerpts: `mystic-horizon` (3 h 57 m),
  `kix-dnd-amateurs-first-session` (3 h 25 m), `dice-and-die-lmop-e01` (2 h 37 m) and
  `oxventure-wyrdwood-campaign` chapter 1 (2 h 05 m). Only two are CC BY 3.0 —
  `mystic-horizon` and `dice-and-die` — so only those two licences would permit a
  committed reference transcript for annotated windows. The other two are Standard
  YouTube Licence with local processing recorded as restricted.
  `mystic-horizon` is the longest, is the only one tiered `multi_hour_stress`, and is
  the closest in duration to a real session; goal #21 is open against it. `dice-and-die`
  is the fallback if that annotation proves impractical, not a rejected candidate.
- Truth in the corpus so far is machine-assisted or human-heard on short windows, and
  the Hiddengrid manifest names the engines its targets derive from as contaminated for
  scoring those same engines.

### Boundaries and process

- The canonical schema is version `0.1` and intentionally narrow. Three consumers have
  now asked it to grow — confidence provenance and speaker-attribution quality from #10,
  somewhere for entities, aliases, and unresolved threads from #12, and #20 recording
  per-turn attribution `coverage` and `purity` in the engine-native artifact because
  canonical turns have nowhere to hold them. That last one is the boundary leaking:
  D-006 says downstream consumes canonical turns only, and a consumer reading only
  canonical turns cannot tell an uncertain speaker attribution from a certain one. All
  three carry consumer evidence, none has been granted, and extending the shared
  contract is a TPM goal of its own.
- The external reference vault must remain read-only during discovery.
- The initial bootstrap establishes the shared product, operating, and executable
  foundation; agents must preserve it and never assume unfamiliar files are disposable.
- The bootstrap installer excludes Git metadata and local caches and never overwrites
  files already present in a target checkout.

## Goal portfolio

GitHub Issues labeled `goal:active` are the live source of specialist assignments.
`docs/GOALS.md` defines discovery, activation, and what may be amended mid-execution.
This status document intentionally does not mirror issue-by-issue assignment state.

## Integration focus

The R0 convergence point is reached: a public excerpt travels from audio through the
canonical boundary to a review package, and four merged artifacts meet there — a
selected engine, a fetchable excerpt, a real analyser, and the command that joins them.

The next one is measurement. Everything the project has produced describes cost and
shape; nothing describes quality, and nothing can until a reference transcript exists.
Goal #21 is open against the longest of the two candidates whose licence permits
committing one.

## Known blockers

- No reference transcript exists, so accuracy is unmeasurable. Every quality claim —
  word error rate, diarization error rate, analysis quality on real play — is blocked
  behind this and nothing else.
- Diarization does not recover speaker counts. The product principle is a useful
  anonymous transcript over failed perfect diarization, so this constrains what the
  review package can assert rather than stopping the pipeline.
- Vault discovery may lack a configured private path. This does not block the
  vault-neutral campaign-change contract and safety policy.
