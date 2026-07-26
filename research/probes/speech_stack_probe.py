#!/usr/bin/env python3
"""Run one speech stack over one audio file and record what it actually produced.

This is research instrumentation for goal R01, not production code. It deliberately
lives outside ``src/rpg_chronicle`` because integrating an engine behind
``TranscriptProvider`` is a separate outcome; the job here is to show that a stack's
native output normalizes into the canonical turn shape without losing timestamps,
physical-speaker distinction, or confidence -- and to measure what it costs.

One stack per process, on purpose. Peak resident set size is read from
``resource.getrusage(RUSAGE_SELF)``, so a process that hosts two engines reports one
number for both and tells us nothing about either.

Usage:
    speech_stack_probe.py --stack parakeet-mlx --audio in.wav --out results/x.json
    speech_stack_probe.py --stack sherpa-diarization --audio in.wav --out results/d.json
    speech_stack_probe.py --stack parakeet-mlx --audio in.wav --out results/x.json \
        --diarization results/d.json

``--diarization`` fuses a previously recorded diarization run into the normalized
turns. It is the composition step a real provider would perform, exercised here so the
cost and the failure modes are visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# A runner calls ``ready()`` once its model is loaded and before it touches audio, so
# model load and inference are timed separately. That split decides the four-hour
# projection: a fixed 20-second load is most of a one-minute probe and nothing at all
# across a full session, and a projection that cannot tell them apart is wrong at one
# end or the other.
Ready = Callable[[], None]
Probe = tuple[dict[str, Any], list[dict[str, Any]]]

# Settings a runner chose that a reader needs in order to re-run it. These are kept
# out of the engine-native artifact on purpose: redaction strips that artifact for
# restricted inputs, and a redacted result that cannot be reproduced is not evidence.
CONFIGURATION: dict[str, Any] = {}

MODELS = Path(os.environ.get("RPG_PROBE_MODELS", Path.home() / ".cache/rpg-chronicle/models"))

STACKS = (
    "parakeet-mlx",
    "mlx-whisper",
    "whisper-cpp-metal",
    "faster-whisper-cpu",
    "sherpa-diarization",
)


# --------------------------------------------------------------------------- helpers


def _peak_rss_bytes() -> int:
    """Peak RSS of this process. macOS reports bytes; Linux reports kilobytes."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024


def _audio_duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(out.stdout.strip())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats with null, recursively.

    Whisper returns ``-inf`` or ``nan`` for ``avg_logprob`` on some segments, and
    ``json.dumps`` happily writes those as bare ``NaN``/``Infinity`` literals, which no
    strict JSON parser accepts -- the file looks fine until ``jq`` refuses it. Writing
    with ``allow_nan=False`` afterwards turns any case this misses into a loud error
    instead of a quietly invalid artifact.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


# ------------------------------------------------------------------------ ASR stacks
#
# Every stack returns (native_artifact, units). A unit is the smallest thing the engine
# timestamps and, where it can, scores:
#   {"start_ms": int, "end_ms": int, "text": str, "confidence": float | None}


def run_parakeet_mlx(audio: Path, ready: Ready) -> Probe:
    from parakeet_mlx import from_pretrained

    repo = os.environ.get("RPG_PROBE_PARAKEET", "mlx-community/parakeet-tdt-0.6b-v3")
    model = from_pretrained(repo)
    ready()
    # Without chunking, parakeet-mlx builds one mel tensor for the whole file and dies
    # on Metal's maximum buffer size somewhere between 10 and 20 minutes of audio. Long
    # sessions therefore require an explicit chunk_duration, which is a real integration
    # obligation rather than a default -- so it is exposed here and recorded in the
    # result instead of being hidden inside a default value.
    chunk = os.environ.get("RPG_PROBE_PARAKEET_CHUNK")
    extra = {"chunk_duration": float(chunk)} if chunk else {}
    CONFIGURATION.update(
        {
            "model": repo,
            "chunk_duration_s": extra.get("chunk_duration"),
            "chunk_env": "RPG_PROBE_PARAKEET_CHUNK",
        }
    )
    result = model.transcribe(audio, **extra)

    sentences = [
        {
            "text": sentence.text,
            "start": sentence.start,
            "end": sentence.end,
            "confidence": sentence.confidence,
            "tokens": [
                {
                    "text": token.text,
                    "start": token.start,
                    "end": token.end,
                    "confidence": token.confidence,
                }
                for token in sentence.tokens
            ],
        }
        for sentence in result.sentences
    ]
    native = {
        "engine": "parakeet-mlx",
        "model": repo,
        "chunk_duration_s": extra.get("chunk_duration"),
        "text": result.text,
        "sentences": sentences,
    }
    units = [
        {
            "start_ms": _ms(s["start"]),
            "end_ms": _ms(s["end"]),
            "text": s["text"].strip(),
            "confidence": s["confidence"],
        }
        for s in sentences
    ]
    return native, units


def run_mlx_whisper(audio: Path, ready: Ready) -> Probe:
    import mlx_whisper

    repo = os.environ.get("RPG_PROBE_MLX_WHISPER", "mlx-community/whisper-large-v3-turbo")
    # mlx-whisper loads lazily inside transcribe(); there is no separable load step,
    # so the ready mark sits at the call and load time lands inside inference.
    ready()
    result = mlx_whisper.transcribe(
        str(audio), path_or_hf_repo=repo, word_timestamps=True, verbose=None
    )
    native = {"engine": "mlx-whisper", "model": repo, **result}
    units = [
        {
            "start_ms": _ms(seg["start"]),
            "end_ms": _ms(seg["end"]),
            "text": seg["text"].strip(),
            # Whisper has no calibrated per-segment confidence. avg_logprob is the
            # closest native signal; exp() puts it on 0..1 so it is comparable in shape
            # to Parakeet's confidence, NOT so it is comparable in meaning.
            "confidence": math.exp(seg["avg_logprob"]),
            "no_speech_prob": seg.get("no_speech_prob"),
        }
        for seg in result["segments"]
    ]
    return native, units


def run_faster_whisper_cpu(audio: Path, ready: Ready) -> Probe:
    from faster_whisper import WhisperModel

    name = os.environ.get("RPG_PROBE_FASTER_WHISPER", "large-v3-turbo")
    model = WhisperModel(name, device="cpu", compute_type="int8")
    ready()
    segments, info = model.transcribe(str(audio), word_timestamps=True)

    collected = [
        {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "avg_logprob": seg.avg_logprob,
            "no_speech_prob": seg.no_speech_prob,
            "words": [
                {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                for w in (seg.words or [])
            ],
        }
        for seg in segments
    ]
    native = {
        "engine": "faster-whisper",
        "model": name,
        "device": "cpu",
        "compute_type": "int8",
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": collected,
    }
    units = [
        {
            "start_ms": _ms(s["start"]),
            "end_ms": _ms(s["end"]),
            "text": s["text"].strip(),
            "confidence": math.exp(s["avg_logprob"]),
            "no_speech_prob": s["no_speech_prob"],
        }
        for s in collected
    ]
    return native, units


def run_whisper_cpp_metal(audio: Path, ready: Ready) -> Probe:
    """whisper.cpp through its CLI. Subprocess cost is inside the measured window.

    Peak RSS here is this process's, which does NOT include the child. The reported
    memory for this stack therefore comes from ``ru_maxrss`` of children, recorded
    separately below.
    """
    model = Path(os.environ.get("RPG_PROBE_WHISPER_CPP_MODEL", MODELS / "ggml-large-v3-turbo.bin"))
    # Never beside the input. The input may live inside the checkout, and whisper-cli
    # would then drop an unredacted transcript into the working tree where it could be
    # committed by accident -- which for a CC BY-NC-ND source is the one outcome this
    # probe exists to avoid.
    scratch_dir = tempfile.TemporaryDirectory(prefix="rpg-whispercpp-")
    scratch = scratch_dir.name
    out_prefix = Path(scratch) / audio.stem
    cmd = [
        "whisper-cli",
        "-m",
        str(model),
        "-f",
        str(audio),
        # -ojf, not -oj: the plain JSON writer emits no scores at all, which would have
        # recorded "this engine has no confidence" when in fact it has per-token
        # probabilities and only the default writer drops them.
        "-ojf",
        "-of",
        str(out_prefix),
        "-t",
        str(os.cpu_count() or 8),
    ]
    # The CLI loads its own model, so load and inference are inseparable here.
    ready()
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload = json.loads(Path(f"{out_prefix}.json").read_text())
    except BaseException:
        # An engine failure must not leave a transcript of restricted audio behind.
        scratch_dir.cleanup()
        raise

    # Absolute paths here would commit the operator's home directory and username into
    # a public repository. The command is recorded by basename so it stays readable
    # without carrying machine identity into the diff.
    redacted_cmd = [Path(part).name if "/" in part else part for part in cmd]
    payload.pop("params", None)
    native = {"engine": "whisper.cpp", "model": model.name, "cli": redacted_cmd, **payload}
    units = []
    for seg in payload.get("transcription", []):
        offsets = seg["offsets"]
        # Special tokens carry their own probabilities and would drag a segment score
        # toward the decoder's certainty about punctuation rather than about words.
        scores = [
            token["p"]
            for token in seg.get("tokens", [])
            if "p" in token and not token.get("text", "").startswith("[_")
        ]
        units.append(
            {
                "start_ms": int(offsets["from"]),
                "end_ms": int(offsets["to"]),
                "text": seg["text"].strip(),
                "confidence": round(sum(scores) / len(scores), 6) if scores else None,
            }
        )
    native["stderr_tail"] = [
        line.replace(scratch, "<scratch>").replace(str(audio.parent), "<audio-dir>")
        for line in proc.stderr.strip().splitlines()[-12:]
    ]
    scratch_dir.cleanup()
    return native, units


# ---------------------------------------------------------------------- diarization


def run_sherpa_diarization(audio: Path, ready: Ready) -> Probe:
    import numpy as np
    import sherpa_onnx
    import soundfile as sf

    segmentation = Path(
        os.environ.get(
            "RPG_PROBE_SEGMENTATION",
            MODELS / "sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
        )
    )
    embedding = Path(
        os.environ.get("RPG_PROBE_EMBEDDING", MODELS / "wespeaker_en_voxceleb_CAMPP.onnx")
    )
    threshold = float(os.environ.get("RPG_PROBE_CLUSTER_THRESHOLD", "0.5"))
    num_clusters = int(os.environ.get("RPG_PROBE_NUM_CLUSTERS", "-1"))
    threads = int(os.environ.get("RPG_PROBE_THREADS", str(os.cpu_count() or 8)))

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(segmentation)
            ),
            num_threads=threads,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(embedding), num_threads=threads
        ),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=num_clusters, threshold=threshold
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise SystemExit("sherpa-onnx rejected the diarization configuration")

    diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
    ready()
    samples, sample_rate = sf.read(str(audio), dtype="float32", always_2d=True)
    samples = samples[:, 0]
    if sample_rate != diarizer.sample_rate:
        raise SystemExit(
            f"{audio} is {sample_rate} Hz; this model needs {diarizer.sample_rate} Hz. "
            "Resample with ffmpeg before probing so the resampler is not measured here."
        )

    result = diarizer.process(np.ascontiguousarray(samples)).sort_by_start_time()
    segments = [
        {"start": seg.start, "end": seg.end, "speaker": f"SPEAKER_{seg.speaker:02d}"}
        for seg in result
    ]
    native = {
        "engine": "sherpa-onnx-offline-speaker-diarization",
        "segmentation_model": segmentation.name,
        "embedding_model": embedding.name,
        "clustering": {"num_clusters": num_clusters, "threshold": threshold},
        "segments": segments,
    }
    units = [
        {
            "start_ms": _ms(s["start"]),
            "end_ms": _ms(s["end"]),
            "text": "",
            "confidence": None,
            "physical_speaker": s["speaker"],
        }
        for s in segments
    ]
    return native, units


# ------------------------------------------------------------------------ normalize


def fuse_speakers(
    units: list[dict[str, Any]], diarization_segments: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach a physical speaker to each ASR unit by maximum temporal overlap.

    This is the whole composition question in one function. An ASR unit that spans a
    speaker change gets the speaker it overlaps most, and the loss is real -- it is
    recorded per unit as ``speaker_overlap_ratio`` so the review layer can see which
    turns are attributions rather than observations.
    """
    # Converted once, not once per unit: this loop is O(units x segments) and the
    # repeated rounding was both wasted work and a chance for two iterations to disagree.
    spans = [(_ms(seg["start"]), _ms(seg["end"]), seg["speaker"]) for seg in diarization_segments]

    fused = []
    for unit in units:
        best_speaker, best_overlap = None, 0
        total = 0
        for seg_start, seg_end, speaker in spans:
            start = max(unit["start_ms"], seg_start)
            end = min(unit["end_ms"], seg_end)
            overlap = max(0, end - start)
            total += overlap
            if overlap > best_overlap:
                best_speaker, best_overlap = speaker, overlap
        span = max(1, unit["end_ms"] - unit["start_ms"])
        fused.append(
            {
                **unit,
                "physical_speaker": best_speaker,
                "speaker_overlap_ratio": round(best_overlap / span, 3),
                "speaker_coverage_ratio": round(min(total, span) / span, 3),
            }
        )
    return fused


def to_canonical_turns(
    units: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project engine units onto the ``TranscriptTurn`` field set.

    ``src/rpg_chronicle/model.py`` rejects a turn with empty text or a non-positive
    span, so a projection that silently dropped those would hide exactly the defect a
    provider would hit. Units that cannot become a turn are reported, not discarded.
    """
    turns, rejected = [], []
    for index, unit in enumerate(units):
        text = unit.get("text", "").strip()
        start, end = unit["start_ms"], unit["end_ms"]
        if not text:
            rejected.append({"index": index, "reason": "empty text", "unit": unit})
            continue
        if start < 0 or end <= start:
            rejected.append({"index": index, "reason": "non-positive span", "unit": unit})
            continue
        turn = {
            "id": f"t{index:04d}",
            "start_ms": start,
            "end_ms": end,
            "text": text,
            "physical_speaker": unit.get("physical_speaker"),
            "confidence": unit.get("confidence"),
        }
        # Attribution quality travels with the turn it describes. Aggregates alone hide
        # which turns are attributions rather than observations, and that is exactly
        # what a review layer needs per turn.
        for extra in ("speaker_overlap_ratio", "speaker_coverage_ratio"):
            if extra in unit:
                turn[extra] = unit[extra]
        turns.append(turn)
    return turns, rejected


# ----------------------------------------------------------------------------- main

RUNNERS = {
    "parakeet-mlx": run_parakeet_mlx,
    "mlx-whisper": run_mlx_whisper,
    "whisper-cpp-metal": run_whisper_cpp_metal,
    "faster-whisper-cpu": run_faster_whisper_cpu,
    "sherpa-diarization": run_sherpa_diarization,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", required=True, choices=sorted(STACKS))
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--diarization",
        type=Path,
        help="a previous sherpa-diarization result to fuse into these turns",
    )
    parser.add_argument(
        "--redact-text",
        action="store_true",
        help="omit transcript text and the engine-native artifact; keep shape and metrics. "
        "Required for any input whose licence forbids distributing a derivative.",
    )
    parser.add_argument(
        "--full-out",
        type=Path,
        help="also write the unredacted result here. Point this OUTSIDE the repository: "
        "it is how a redacted diarization run can still be fused into a later ASR run "
        "without the speaker timeline of restricted media entering the diff.",
    )
    parser.add_argument("--input-label", default=None, help="how the input is named in the result")
    args = parser.parse_args()

    duration_s = _audio_duration_s(args.audio)
    load_before = os.getloadavg()
    started = time.monotonic()
    ready_at: list[float] = []
    # A stack that cannot process an input is a result about that stack, not an absence
    # of one. Recording the failure keeps "this engine refuses audio of this length"
    # inside the committed evidence instead of only in a console someone once watched.
    try:
        native, units = RUNNERS[args.stack](args.audio, lambda: ready_at.append(time.monotonic()))
    except Exception as failure:  # noqa: BLE001 - any engine failure is the finding
        elapsed = time.monotonic() - started
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "probe_version": "1",
                    "stack": args.stack,
                    "outcome": "failed",
                    "input": {
                        "label": args.input_label or args.audio.name,
                        "duration_s": round(duration_s, 3),
                    },
                    "configuration": dict(CONFIGURATION),
                    "environment": {
                        "machine": platform.machine(),
                        "platform": platform.platform(),
                    },
                    "failed_after_s": round(elapsed, 3),
                    "error_type": type(failure).__name__,
                    "error": str(failure).replace(str(Path.home()), "~"),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"{args.stack}: FAILED after {elapsed:.1f}s -> {args.out}\n  {failure}")
        return 1
    elapsed = time.monotonic() - started
    load_after = os.getloadavg()
    model_load_s = (ready_at[0] - started) if ready_at else None
    inference_s = elapsed - model_load_s if model_load_s is not None else elapsed

    child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    child_bytes = child if sys.platform == "darwin" else child * 1024

    diarization_source = None
    if args.diarization:
        loaded = json.loads(args.diarization.read_text())
        if "native_artifact" not in loaded:
            raise SystemExit(
                f"{args.diarization} is a redacted result and carries no speaker segments. "
                "Fuse from the unredacted copy the diarization run wrote via --full-out."
            )
        diarization_source = {
            "path": args.diarization.name,
            "engine": loaded["native_artifact"]["engine"],
        }
        units = fuse_speakers(units, loaded["native_artifact"]["segments"])

    # A diarization-only stack produces spans without text. Those are not failed turns
    # and must not be reported as rejections; they are the speaker half of a pair that
    # only becomes canonical once an ASR run is fused into it.
    diarization_only = bool(units) and all(not u.get("text") for u in units)
    if diarization_only:
        turns, rejected = [], []
        speakers = sorted({u["physical_speaker"] for u in units if u.get("physical_speaker")})
        scored: list[float] = []
    else:
        turns, rejected = to_canonical_turns(units)
        speakers = sorted({t["physical_speaker"] for t in turns if t["physical_speaker"]})
        scored = [
            t["confidence"]
            for t in turns
            if t["confidence"] is not None and math.isfinite(t["confidence"])
        ]

    result: dict[str, Any] = {
        "probe_version": "1",
        "stack": args.stack,
        "provider_of_record": native.get("engine"),
        "output_kind": "model output",
        "input": {
            "label": args.input_label or args.audio.name,
            "duration_s": round(duration_s, 3),
            "sha256": _sha256(args.audio),
        },
        "environment": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "metrics": {
            "wall_clock_s": round(elapsed, 3),
            "model_load_s": round(model_load_s, 3) if model_load_s is not None else None,
            "inference_s": round(inference_s, 3),
            "realtime_factor": round(duration_s / elapsed, 2) if elapsed else None,
            "inference_realtime_factor": (
                round(duration_s / inference_s, 2) if inference_s > 0 else None
            ),
            "peak_rss_mb": round(_peak_rss_bytes() / 1e6, 1),
            "peak_child_rss_mb": round(child_bytes / 1e6, 1),
            # A timing figure taken on a busy laptop describes the laptop. Recording the
            # one-minute load average on both sides of the run lets a reader discard a
            # measurement instead of trusting it blindly.
            "load_avg_1m_before": round(load_before[0], 2),
            "load_avg_1m_after": round(load_after[0], 2),
        },
        "shape": {
            "produces_text": not diarization_only,
            "unit_count": len(units),
            "canonical_turn_count": len(turns),
            "speaker_span_count": len(units) if diarization_only else None,
            "speaker_span_ms": (
                sum(u["end_ms"] - u["start_ms"] for u in units) if diarization_only else None
            ),
            "rejected_unit_count": len(rejected),
            "rejected_units": rejected if not args.redact_text else len(rejected),
            # True whenever the stack timestamped anything, which a diarizer does even
            # though it produces no turns. Deriving this from `turns` alone described
            # the projection rather than the engine.
            "has_timestamps": bool(turns) or bool(units),
            "distinct_physical_speakers": len(speakers),
            "physical_speakers": speakers,
            "turns_with_confidence": len(scored),
            "confidence_min": round(min(scored), 4) if scored else None,
            "confidence_mean": round(sum(scored) / len(scored), 4) if scored else None,
            "total_speech_ms": sum(t["end_ms"] - t["start_ms"] for t in turns),
            "characters_of_text": sum(len(t["text"]) for t in turns),
        },
        "diarization_source": diarization_source,
        "configuration": dict(CONFIGURATION),
    }

    # How confidently the fused speaker label describes its turn. This survives
    # redaction because it is an aggregate about attribution quality and contains
    # nothing anyone said.
    overlaps = [t["speaker_overlap_ratio"] for t in units if "speaker_overlap_ratio" in t]
    coverages = [t["speaker_coverage_ratio"] for t in units if "speaker_coverage_ratio" in t]
    if overlaps:
        mean_overlap = sum(overlaps) / len(overlaps)
        mean_coverage = sum(coverages) / len(coverages)
        unit_span = sum(t["end_ms"] - t["start_ms"] for t in units)
        result["shape"]["speaker_attribution"] = {
            "mean_overlap_ratio": round(mean_overlap, 3),
            "min_overlap_ratio": round(min(overlaps), 3),
            "turns_below_0_8_overlap": sum(1 for o in overlaps if o < 0.8),
            "turns_with_no_speaker": sum(1 for t in units if not t.get("physical_speaker")),
            # Overlap alone confounds two different things. A stack whose units span more
            # time than the diarizer called speech cannot reach an overlap of 1.0 however
            # well it attributes, so coverage -- the share of a unit any speaker covers --
            # has to be reported beside it. The ratio of the two is attribution purity
            # given what was diarized at all, which is the comparable quantity.
            "mean_coverage_ratio": round(mean_coverage, 3),
            "overlap_given_coverage": (
                round(mean_overlap / mean_coverage, 3) if mean_coverage else None
            ),
            "total_unit_span_ms": unit_span,
        }

    if args.redact_text:
        result["redaction"] = (
            "Transcript text and the engine-native artifact are withheld: the input's "
            "licence restricts derivatives. Metrics and output shape are aggregate."
        )
    else:
        result["native_artifact"] = native
        result["canonical_turns"] = turns

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(_json_safe(result), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )

    if args.full_out:
        args.full_out.parent.mkdir(parents=True, exist_ok=True)
        args.full_out.write_text(
            json.dumps(
                _json_safe({**result, "native_artifact": native, "canonical_turns": turns}),
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )
    print(
        f"{args.stack}: {elapsed:.1f}s for {duration_s:.0f}s audio "
        f"({result['metrics']['realtime_factor']}x realtime), "
        f"peak {result['metrics']['peak_rss_mb']} MB self / "
        f"{result['metrics']['peak_child_rss_mb']} MB child, "
        f"{len(turns)} turns -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
