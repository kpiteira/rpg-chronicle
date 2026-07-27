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
| Wall clock | **160 s** for 600 s of audio |
| Recognized segments | 302 |
| Canonical turns | **301** |
| Segments that could not become turns | 1, reported not dropped |
| Turns with timestamps | 301 of 301 |
| Turns with confidence | 301 of 301 |
| Turns with a speaker label | 292 of 301 |
| Claims, and distinct turn ids they cite | 6, citing 72 |
| Claims citing a turn that does not exist | 0 |
| Distinct speaker labels | 23 |
| Total turn span | 389,060 ms |
| Scenes | 3 |
| Review questions | 3 |

Three figures reproduce R01's probe on the same window exactly — 301 turns, 389,060 ms
of total span, 23 distinct labels. That is the narrow thing this run was for: the probe
and the product agree about what the engines produced.

One figure differs and the difference is the point. The scorecard recorded 10 turns with
no speaker label; this run has 9. Same audio, same engines, same settings — the
attribution *rule* changed. R01's probe gave each turn the label of the single
longest-overlapping span; this uses the greatest total overlap per speaker, so one turn
that the old rule left unlabelled now resolves. "Exactly" applies to what the engines
emitted, not to what normalization did with it.

### Evidence integrity

The committed report carries this as counts rather than as a claim in prose:
`claims: 6`, `distinct_cited_turn_ids: 72`, `claims_citing_missing_turns: 0`, and
`turns_with_timestamps: 301` of 301. Enforced during the run by `model.evidence_for`,
which raises rather than dropping a claim citing a turn the session lacks — so a run that
produced an unsupported claim would have failed loudly instead of finishing quietly
shorter.

## Resumption

Not asserted from the code. Demonstrated by interrupting a run at a stage boundary and
timing the resume.

| Run | What happened | Wall clock |
|---|---|---|
| 1 | transcription completed, analysis failed (deliberately invalid model) | 84 s |
| 2 | resumed: transcription reused, analysis ran | 135 s |
| — | full path from scratch, for comparison | 160 s |

Run 1 paid for transcription and lost only the analysis. Run 2 did not pay for
transcription again: it started from 301 turns already on disk. Re-running an
*already complete* session costs **1 s** — it rebuilds the review package and stops.

Wall clock is the weaker half of this evidence, because the analysis call is a network
round trip whose duration varies by more than the transcription stage costs. The
`research/runs/*.json` pair is the stronger half: identical `turns`, `turns_with_speaker`
and `turns_with_timestamps` across both runs, from a transcript that was computed once.

Scene and question counts differ between the two runs — 3 and 3 against 4 and 3 — and
they differ between repeats of the *same unresumed* command too. That is the analysis
model being non-deterministic, not the resume losing anything; the transcript underneath
is identical. Nothing downstream should read a scene count as a stable property of a
recording.

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
  B02 measured this recording as a single mixed track on two near-identical channels — an
  L−R residual 34 dB *below* programme — so downmixing is safe here and is still the
  caller's explicit choice, because a recording that did carry per-speaker channels would
  need handling nobody has designed. An earlier wording of this line said the channels
  *differed* by 34 dB, which inverts the measurement.
