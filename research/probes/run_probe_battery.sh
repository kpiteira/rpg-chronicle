#!/usr/bin/env bash
# Run every candidate stack over one input, sequentially.
#
# Sequentially is the point. Wall-clock and peak RSS are the numbers the four-hour
# projection rests on, and two engines competing for the same GPU and memory bandwidth
# produce figures that describe the contention rather than the engine.
#
# Usage:
#   run_probe_battery.sh <audio.wav> <label> <results-dir> [--redact-text]
#
# Environment (all optional, defaults shown in speech_stack_probe.py):
#   RPG_PROBE_MODELS   directory holding the sherpa-onnx and ggml model files
#   RPG_PROBE_PYTHON   interpreter with the probe dependencies installed
#
# See research/probes/README.md for setup.

set -euo pipefail

AUDIO="${1:?usage: run_probe_battery.sh <audio.wav> <label> <results-dir> [--redact-text]}"
LABEL="${2:?missing label}"
RESULTS="${3:?missing results dir}"
REDACT="${4:-}"

PYTHON="${RPG_PROBE_PYTHON:-$HOME/.cache/rpg-chronicle/probe-venv/bin/python}"
PROBE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/speech_stack_probe.py"

mkdir -p "$RESULTS"

# Unredacted copies stay next to the audio, outside the checkout. They exist so the
# fusion step has speaker segments to work with even when the committed result is
# redacted; nothing here is ever added to Git.
WORK="$(cd "$(dirname "$AUDIO")" && pwd)/probe-full"
mkdir -p "$WORK"

run() {
  local stack="$1"; shift
  echo "--- $LABEL / $stack"
  "$PYTHON" "$PROBE" --stack "$stack" --audio "$AUDIO" \
    --out "$RESULTS/$LABEL-$stack.json" --input-label "$LABEL" \
    --full-out "$WORK/$LABEL-$stack.json" \
    ${REDACT:+"$REDACT"} "$@"
}

# Diarization first: the ASR runs fuse its result, so it has to exist before they run.
run sherpa-diarization

DIAR="$WORK/$LABEL-sherpa-diarization.json"

run parakeet-mlx --diarization "$DIAR"
run mlx-whisper --diarization "$DIAR"
run whisper-cpp-metal --diarization "$DIAR"
run faster-whisper-cpu --diarization "$DIAR"

echo "--- $LABEL complete"
