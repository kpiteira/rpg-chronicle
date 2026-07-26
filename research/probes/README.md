# R01 speech-stack probes

Instrumentation for goal R01. It answers three questions and refuses to answer a fourth.

1. What does each candidate stack actually emit on this machine?
2. Does that output project onto `TranscriptTurn` without losing timestamps, physical
   speaker, or confidence?
3. What does it cost in wall-clock and peak memory, per second of audio?

It does not answer *how accurate is this stack*. Word error rate needs reference
transcripts that `benchmarks/` does not have yet — B02 owns that. Treat every number
here as cost and shape evidence, never as quality evidence.

## Inputs

Two, deliberately different.

| Input | Rights | What it is good for | What it cannot show |
|---|---|---|---|
| `synthetic-table-talk.wav` | generated locally by this repository; MIT | output shape, timestamp sanity, invented-proper-noun handling, speaker-count behaviour against known truth | anything about real acoustics — no noise, no overlap, no room |
| Hiddengrid Episode 044, 0–600 s | CC BY-NC-ND 4.0, redistribution restricted | cost and behaviour on genuine multi-speaker recorded play | nothing may be committed but aggregates |

The Hiddengrid probe therefore runs with `--redact-text`, which withholds transcript
text and the engine-native artifact and keeps only metrics and shape counts. The audio
is never committed either; `.gitignore` already excludes audio formats, and the cache
lives outside the checkout.

## Setup

Roughly 4 GB of models and about ten minutes of downloads. Nothing lands in the
repository.

```bash
# 1. dependencies, in a venv outside the checkout
uv venv --python 3.12 ~/.cache/rpg-chronicle/probe-venv
uv pip install --python ~/.cache/rpg-chronicle/probe-venv/bin/python \
    mlx-whisper parakeet-mlx sherpa-onnx faster-whisper soundfile numpy

# 2. whisper.cpp with Metal
brew install whisper-cpp

# 3. models that are not fetched automatically
mkdir -p ~/.cache/rpg-chronicle/models && cd ~/.cache/rpg-chronicle/models
curl -sSL -O https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
tar xjf sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
# "recongition" is not a typo in this file -- it is the upstream release tag, misspelled
# by k2-fsa. Verified 2026-07-26: the misspelling returns 206, the correct spelling 404s.
# Do not "fix" it.
curl -sSL -o wespeaker_en_voxceleb_CAMPP.onnx \
    'https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_CAM%2B%2B.onnx'
curl -sSL -O https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
```

The MLX and faster-whisper model weights download on first use into the default
Hugging Face cache. None of the four stacks needs a Hugging Face token or a gated model
acceptance — that absence is itself a finding, recorded in
`research/speech-stack-scorecard.md`.

## Reproducing

Run every block from the repository root. `REPO` is spelled out because two of the
commands below `cd` into the audio cache, and the battery script needs an absolute path
to write its results back into the checkout.

```bash
REPO=$(git rev-parse --show-toplevel)
CACHE=~/.cache/rpg-chronicle/benchmark
mkdir -p "$CACHE"

# Every command below runs the probe scripts directly rather than through
# run_probe_battery.sh, which is the only one that finds the venv on its own. Set this
# first or the first script fails on `import mlx_whisper`.
export RPG_PROBE_PYTHON=~/.cache/rpg-chronicle/probe-venv/bin/python
PROBE="$RPG_PROBE_PYTHON $REPO/research/probes/speech_stack_probe.py"

# rights-clear input, generated locally, full output committed.
#
# Needs macOS and four system voices: Daniel, Samantha, Karen, Ralph. Check first --
# `say` fails per line if one is missing, and the clip comes out short rather than
# erroring:
#     for v in Daniel Samantha Karen Ralph; do say -v "$v" -o /tmp/probe-voice-check.aiff \
#         "check" 2>&1 && echo "$v ok"; done; rm -f /tmp/probe-voice-check.aiff
# Missing voices install from System Settings › Accessibility › Spoken Content ›
# System Voice › Manage Voices. Substituting other voices is fine for output shape, but
# the committed synthetic results will no longer be byte-comparable.
$RPG_PROBE_PYTHON "$REPO"/research/probes/make_synthetic_clip.py --out-dir "$CACHE"
(cd "$CACHE" && "$REPO"/research/probes/run_probe_battery.sh \
    synthetic-table-talk.wav synthetic "$REPO"/research/probes/results)

# restricted input, aggregates only
curl -sSL -o "$CACHE/hiddengrid-ep044.mp3" \
    https://www.hiddengrid.com/wp-content/Podcast/HIDDENGRID_EP044_S028_P01_140524.mp3
shasum -a 256 "$CACHE/hiddengrid-ep044.mp3"   # must match the benchmark manifest
ffmpeg -v error -ss 0 -t 600 -i "$CACHE/hiddengrid-ep044.mp3" \
    -ac 1 -ar 16000 -c:a pcm_s16le "$CACHE/hiddengrid-ep044-000-600.wav"
(cd "$CACHE" && "$REPO"/research/probes/run_probe_battery.sh \
    hiddengrid-ep044-000-600.wav hiddengrid-600s \
    "$REPO"/research/probes/results --redact-text)
```

The battery also writes an unredacted copy of every result into `probe-full/` beside the
audio, outside the checkout. That copy exists so the speaker-fusion step has segments to
work with when the committed result is redacted; never move it into the repository.

Run the battery on an otherwise idle machine. Each result records the one-minute load
average before and after its run; a result taken under load describes the load. The
figures committed here were taken on a machine also running a second agent session, so
the wall-clock numbers are upper bounds — peak memory is unaffected by contention.

### Scaling and tuning runs

These back the four-hour projection and the diarization findings. Every committed
`scaling-*.json` comes from one of the commands below; the recognition realtime factors
the wall-clock projection is taken from come from the `whispercpp` runs specifically.

These continue from the block above and reuse its `$CACHE`, `$RPG_PROBE_PYTHON` and
`$PROBE`.

```bash
# the windows every scaling run uses
for T in 1200 1800 2400; do
  ffmpeg -v error -ss 0 -t $T -i "$CACHE/hiddengrid-ep044.mp3" \
      -ac 1 -ar 16000 -c:a pcm_s16le "$CACHE/scale-$T.wav" -y
done

# diarization memory against input length -- measured, not assumed
for T in 1200 1800 2400; do
  $PROBE --stack sherpa-diarization \
      --audio "$CACHE/scale-$T.wav" --redact-text \
      --out "$REPO"/research/probes/results/scaling-diarization-${T}s.json \
      --input-label "hiddengrid-${T}s"
done

# recognition at the same lengths, so the comparison is like for like
for T in 1200 2400; do
  $PROBE --stack whisper-cpp-metal \
      --audio "$CACHE/scale-$T.wav" --redact-text \
      --out "$REPO"/research/probes/results/scaling-whispercpp-${T}s.json \
      --input-label "hiddengrid-${T}s"

  # RPG_PROBE_PARAKEET_CHUNK sets parakeet-mlx's chunk_duration in seconds. It is
  # required above ~10 minutes of audio and is recorded in each result's
  # `configuration` block, which survives redaction for exactly this reason.
  RPG_PROBE_PARAKEET_CHUNK=120 $PROBE --stack parakeet-mlx \
      --audio "$CACHE/scale-$T.wav" --redact-text \
      --out "$REPO"/research/probes/results/scaling-parakeet-chunked-${T}s.json \
      --input-label "hiddengrid-${T}s"
done

# the failure the scorecard cites: parakeet-mlx with no chunk duration at 20 minutes.
# Expected to exit non-zero and write a result with "outcome": "failed".
$PROBE --stack parakeet-mlx \
    --audio "$CACHE/scale-1200.wav" --redact-text \
    --out "$REPO"/research/probes/results/scaling-parakeet-unchunked-1200s.json \
    --input-label "hiddengrid-1200s" || true

# the diarization clustering sweep, which produces results/diarization-threshold-sweep.json
# in one command: six thresholds against the synthetic clip's known speaker count, six
# against the restricted window, and the forced num_clusters=4 run.
$RPG_PROBE_PYTHON "$REPO"/research/probes/sweep_diarization.py --cache "$CACHE" \
    --out "$REPO"/research/probes/results/diarization-threshold-sweep.json
```

`sweep_diarization.py` drives `speech_stack_probe.py` through
`RPG_PROBE_CLUSTER_THRESHOLD` and `RPG_PROBE_NUM_CLUSTERS`; both are also usable
directly if you want a single run. Its per-run outputs stay in a temp directory — only
the scored summary is committed, because the restricted clip's speaker spans must not
enter the repository.

### Scoring against known truth

```bash
$RPG_PROBE_PYTHON "$REPO"/research/probes/score_synthetic.py \
    --truth "$CACHE/synthetic-table-talk-truth.json" \
    --result "$REPO"/research/probes/results/synthetic-*.json \
    --out "$REPO"/research/probes/results/synthetic-scores.json
```

The truth file is the generator's own script. No engine ever sees it, so the comparison
is an observation about the engines rather than a fixture replay — the distinction
`agents/goal-validator.md` polices.

## Reading a result file

- `canonical_turns` is complete; `native_artifact` is an **excerpt**. The committed copy
  keeps the first four entries of each native list and records the true count under
  `<key>_excerpted`. A whisper.cpp `-ojf` dump of a 50-second clip is 60 kB of token
  probabilities that show nothing the first few do not, and it makes the diff
  unreviewable. The complete artifact is written beside the audio by `--full-out`,
  which is what `docs/ARCHITECTURE_BOUNDARIES.md` asks be retained.
- `metrics.model_load_s` versus `metrics.inference_s` — a fixed load cost is most of a
  one-minute probe and nothing across four hours. Project from `inference_s`.
- `metrics.peak_rss_mb` versus `peak_child_rss_mb` — `whisper-cpp-metal` does its work
  in a subprocess, so its memory is the child figure; the others are the self figure.
  Every stack shows a small non-zero child figure regardless, because `ffprobe` runs as
  a child to read the input duration. Roughly 13–16 MB of child RSS is that, not the
  engine.
- `shape.turns_with_confidence` and `confidence_mean` — confidence is not comparable
  *in meaning* across engines. Parakeet emits a native token confidence; Whisper-family
  stacks do not, and what is recorded for them is `exp(avg_logprob)` or a mean token
  probability. Same range, different thing.
- `shape.rejected_units` — units that could not become a `TranscriptTurn`. A real
  provider hits exactly these, so they are reported rather than dropped.
- `canonical_turns[].speaker_overlap_ratio` — how much of the turn the assigned speaker
  actually covers. Below about 0.8 the label is an attribution, not an observation.

## Files

- `speech_stack_probe.py` — runs one stack, normalizes, measures. One stack per process.
- `run_probe_battery.sh` — runs every stack over one input, sequentially.
- `make_synthetic_clip.py` — builds the rights-clear input and its declared truth.
- `score_synthetic.py` — scores a result against that declared truth.
- `sweep_diarization.py` — the clustering sweep behind the diarization findings.
- `results/` — committed results. Hiddengrid results are redacted by construction.

A run that fails is still a result: the probe writes `"outcome": "failed"` with the
error and the configuration that produced it, and exits non-zero.
`results/scaling-parakeet-unchunked-1200s.json` is one, and it is deliberate.

## Known limitations of this instrumentation

Two fields are weaker than they look. Both were found in validation and are recorded
rather than quietly left, because a metric that cannot fail is worse than no metric.

- **`shape.has_timestamps` cannot be false.** It is `bool(turns) or bool(units)`, so any
  stack that emits anything at all passes it. Read it as "this run produced output", not
  as a capability check — the real timestamp evidence is the millisecond values on each
  entry of `canonical_turns`. It should be derived from those or dropped; doing so means
  regenerating every result, so it is left as a follow-up rather than changed in a way
  that would leave the committed code and the committed numbers out of step.
- **`speaker_coverage_ratio` overstates coverage where diarization spans overlap.** It
  sums per-span overlaps and clamps at the unit span, so a unit spanned by two
  simultaneous speakers counts that time twice before clamping. `overlap_given_coverage`
  is correspondingly deflated. The direction of the comparison it supports holds, but its
  third decimal does not, and the scorecard says so where it uses it.
