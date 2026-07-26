# R02: the canonical path over real audio

First run of the product's own pipeline against a real recording. Machine: Apple M4 Pro,
24 GB, macOS 26.3.1. Date: 2026-07-26.

> **What this is.** Evidence that the path carries real audio end to end and resumes.
>
> **What this is not.** Evidence that it carries it *well*. There is no word error rate
> here, no diarization error rate, and no quality claim of any kind. B02's truth targets
> are machine-assisted and name the engines they came from as contaminated for scoring,
> so scoring against them would be circular. The first real-audio artifact this project
> has produced is not the same thing as a good one.

## The command

```bash
# 1. fetch and verify the media against the manifest (nothing enters the repository)
export RPG_CHRONICLE_BENCHMARK_CACHE=~/.cache/rpg-chronicle/benchmark
uv run python scripts/fetch_benchmark_media.py hiddengrid-swc-ep044-tower-play

# 2. the manifest's excerpt window, as 16 kHz mono. run-audio will not resample: the
#    conversion cost belongs to ffmpeg, not to the recognizer being measured.
ffmpeg -v error -ss 0 -t 600 \
    -i "$RPG_CHRONICLE_BENCHMARK_CACHE/hiddengrid-swc-ep044-tower-play/HIDDENGRID_EP044_S028_P01_140524.mp3" \
    -ac 1 -ar 16000 -c:a pcm_s16le "$RPG_CHRONICLE_BENCHMARK_CACHE/hiddengrid-excerpt-16k-mono.wav"

# 3. the run itself. --group speech installs sherpa-onnx and friends; whisper-cli comes
#    from `brew install whisper-cpp`. See research/probes/README.md for the models.
uv run --group speech rpg-chronicle run-audio \
    "$RPG_CHRONICLE_BENCHMARK_CACHE/hiddengrid-excerpt-16k-mono.wav" \
    --output ~/.cache/rpg-chronicle/runs/r02 \
    --session-id hiddengrid-swc-ep044-000-600 \
    --run-report ~/.cache/rpg-chronicle/runs/r02/run-report.json
```

The output directory is outside the repository on purpose. It holds a transcript of
CC BY-NC-SA 3.0 audio whose redistribution is restricted on Topps grounds independent of
the licence; the only thing that comes back here is the run report, which carries counts
and no words.

## What it produced

`research/runs/hiddengrid-600s-first-run.json` is the committed report.

| | |
|---|---|
| Input | Hiddengrid Ep. 044, 0–600 s, 16 kHz mono |
| Wall clock | **162 s** for 600 s of audio |
| Recognized segments | 302 |
| Canonical turns | **301** |
| Segments that could not become turns | 1, reported not dropped |
| Turns with timestamps | 301 of 301 |
| Turns with confidence | 301 of 301 |
| Turns with a speaker label | 292 of 301 |
| Distinct speaker labels | 23 |
| Total turn span | 389,060 ms |
| Scenes | 6 |
| Review questions | 4 |

The turn count, total span and label count reproduce R01's probe figures on the same
window exactly (301 turns, 389,060 ms, 23 labels). The probe and the product now agree,
which is the narrow thing this run was for.

### Evidence integrity

The 10 claims in the review package cite 87 distinct turn ids. Every one resolves to a
turn the session contains — checked after the run, and enforced during it by
`model.evidence_for`, which raises rather than dropping a claim that cites a turn the
session does not have. A run that had produced an unsupported claim would have failed
loudly; this one did not produce any.

## Resumption

Not asserted from the code. Demonstrated by interrupting a run at a stage boundary and
timing the resume.

| Run | What happened | Wall clock |
|---|---|---|
| 1 | transcription completed, analysis failed (deliberately invalid model) | 96 s |
| 2 | resumed: transcription reused, analysis ran | 93 s |
| — | full path from scratch, for comparison | 162 s |

The arithmetic reconciles: 162 s of full run minus 93 s of analysis leaves ~69 s of
transcription, which run 2 did not pay again. Re-running an already-complete session
costs **1 s** — it rebuilds the review package and stops.

`tests/test_transcription.py` proves the mechanism rather than the timing: two tests
count recognizer invocations across a resumed run, and both fail if the `if not
session.turns:` guard in `pipeline.py` is removed. Verified by mutation, not by
inspection.

## What the artifact is worth

Three cautions travel with every number above, and they are properties of the stack R01
selected rather than of this integration.

**The speaker labels are cluster identifiers, not people.** 23 labels on a ten-minute
excerpt of a podcast with seven speaking roles. R01 measured that no clustering threshold
recovers a known speaker count and that supplying the true count merges distinct
speakers; the manifest's `proven_distinct_speakers: 2` says the audio itself barely
settles the question. The labels are carried because `docs/PRODUCT.md` prefers a useful
anonymous transcript to failed perfect diarization, and they are marked `unreliable` in
the engine-native artifact so nothing downstream mistakes them for identity.

**The confidence figure is not calibrated and not comparable.** Mean whisper.cpp token
probability, which is the decoder's certainty about its own tokens. R01 measured turns
that mangled an invented proper noun scoring within 0.02 of a typical turn. Mean here is
0.931 and minimum 0.508; neither number licenses an inference about correctness, and the
canonical model carries no field saying which quantity it holds — that request is
recorded for the TPM in the R01 scorecard and repeated below.

**Nothing here is a quality measurement.** The scenes and questions are model output over
a transcript with unknown error, from a ten-minute excerpt. R01's four-hour projection is
a projection; this is ten minutes and does not generalise to it.

## Carried forward

- `TranscriptTurn` still cannot say what its `confidence` measures or how well its
  `physical_speaker` covers the turn. Both requests stand from R01. This integration
  works around the gap by recording `kind`, per-turn `coverage` and `purity` in the
  engine-native artifact, which is the honest place for it while `model.py` is
  TPM-owned — but a review layer reading only canonical turns still cannot tell a
  0.6-coverage attribution from a certain one.
- The `attribute()` rule here fixes a flaw in R01's probe: it chooses the speaker with
  the greatest *total* overlap, not the single longest overlapping span. A diarizer
  emitting several short spans for one speaker inside a long turn would otherwise hand
  that turn to whoever interjected once.
- `run-audio` requires 16 kHz mono and refuses anything else rather than downmixing.
  B02 measured this recording's two channels differing by 34 dB, so "the first channel"
  and "the audio" are not the same signal and a silent choice between them would make
  the measurement describe something nobody selected.
