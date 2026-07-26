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

The path is resumable and preserves the processor-native artifact. What it has never
done is carry real audio: no transcription engine is wired behind `TranscriptProvider`,
so the front of the pipeline is still a fixture. Goal #20 is closing that.

## Active milestone

`M1 — R0 public vertical slice`. Three of its six exit criteria are met outright: the
selected source's provenance, the reproducible fetch, and the evidence-backed engine
choice. The other three — canonical output retaining timestamps, speaker distinction,
confidence and native artifacts; every important summary and review assertion linking to
transcript evidence; one resumable command producing the review package — are satisfied
on synthetic input and unsatisfied on the public excerpt the milestone names.

## Accepted facts

### Lifecycle

- Four specialist goals have completed the full issue → Copilot-reviewed PR → validated
  → merged lifecycle: #11, #10, #12, #14. The validator blocked three of them at least
  once, and each block named a defect that would otherwise have merged.

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
- Nothing in `src/rpg_chronicle/` transcribes audio yet. R01's goal excluded
  integration.

### Analysis

- Analysis is a real model-backed provider behind a vendor-neutral seam
  (`docs/ANALYSIS.md`, `src/rpg_chronicle/analysis/`). A vendor is named in one backend
  module and at the point where a backend is selected, and nowhere else;
  `tests/test_vendor_neutrality.py` fails the commit that leaks one further.
- `--analysis fixture` remains the default. The model backend reaches Claude through a
  headless process using the operator's subscription, and CI holds no credential.
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
- Three candidates carry multi-hour excerpts: `mystic-horizon` (3 h 57 m),
  `kix-dnd-amateurs-first-session` (3 h 25 m) and `dice-and-die-lmop-e01` (2 h 37 m).
  Two of those are CC BY 3.0 — `mystic-horizon` and `dice-and-die` — so either licence
  would permit a committed reference transcript for annotated windows.
  `mystic-horizon` is the longest, is the only one tiered `multi_hour_stress`, and is
  the closest in duration to a real session; goal #21 is annotating it. `dice-and-die`
  is the fallback if that annotation proves impractical, not a rejected candidate.
- Truth in the corpus so far is machine-assisted or human-heard on short windows, and
  the Hiddengrid manifest names the engines its targets derive from as contaminated for
  scoring those same engines.

### Boundaries and process

- The canonical schema is version `0.1` and intentionally narrow. Two consumers have now
  asked it to grow — confidence provenance and speaker-attribution quality from #10,
  somewhere for entities, aliases, and unresolved threads from #12. Both requests carry
  consumer evidence and neither has been granted; extending the shared boundary is a
  TPM goal of its own.
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

The convergence point is unchanged and now has one wire missing: a public excerpt
travelling from audio through the canonical boundary to a review package. Three merged
artifacts meet there — a selected engine, a fetchable excerpt, a real analyser — and
until that command exists, every quality claim the project can make rests on synthetic
input.

## Known blockers

- No reference transcript exists, so accuracy is unmeasurable. Every quality claim —
  word error rate, diarization error rate, analysis quality on real play — is blocked
  behind this and nothing else.
- Diarization does not recover speaker counts. The product principle is a useful
  anonymous transcript over failed perfect diarization, so this constrains what the
  review package can assert rather than stopping the pipeline.
- Vault discovery may lack a configured private path. This does not block the
  vault-neutral campaign-change contract and safety policy.
