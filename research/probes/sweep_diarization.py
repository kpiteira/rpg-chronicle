#!/usr/bin/env python3
"""Sweep sherpa-onnx's clustering settings and score what each one produces.

This generates `results/diarization-threshold-sweep.json`, which backs the two
diarization findings the scorecard calls product-shaping:

1. no clustering threshold recovers the true speaker count on a clip where that count
   is known by construction;
2. supplying the true count with ``num_clusters`` makes it worse, by merging distinct
   speakers rather than splitting one.

Both are only worth as much as their reproducibility, so the sweep is a script rather
than something assembled by hand.

The two inputs answer different questions. The synthetic clip has declared truth, so
its runs are *scored*: fragmentation and collision can be told apart. The Hiddengrid
window has no verified speaker count -- its manifest records
``expected_physical_speakers: null`` -- so only the label count is observable, and this
script deliberately reports nothing more for it.

Usage:
    sweep_diarization.py --cache ~/.cache/rpg-chronicle/benchmark \
        --out research/probes/results/diarization-threshold-sweep.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from score_synthetic import score_speakers

THRESHOLDS = ["0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
PROBE = Path(__file__).with_name("speech_stack_probe.py")


def run(audio: Path, out: Path, env: dict[str, str], label: str) -> dict[str, Any]:
    python = os.environ.get("RPG_PROBE_PYTHON", sys.executable)
    subprocess.run(
        [python, str(PROBE), "--stack", "sherpa-diarization", "--audio", str(audio),
         "--out", str(out), "--input-label", label],
        check=True,
        env={**os.environ, **env},
        capture_output=True,
    )
    return json.loads(out.read_text())


def spans(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "start_ms": round(s["start"] * 1000),
            "end_ms": round(s["end"] * 1000),
            "physical_speaker": s["speaker"],
        }
        for s in result["native_artifact"]["segments"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path, help="directory holding the audio")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--synthetic", default="synthetic-table-talk.wav")
    parser.add_argument("--truth", default="synthetic-table-talk-truth.json")
    parser.add_argument("--restricted", default="hiddengrid-ep044-000-600.wav")
    args = parser.parse_args()

    truth_turns = json.loads((args.cache / args.truth).read_text())["turns"]
    work = Path(tempfile.mkdtemp(prefix="rpg-diar-sweep-"))

    synthetic: dict[str, Any] = {}
    for threshold in THRESHOLDS:
        result = run(
            args.cache / args.synthetic,
            work / f"syn-th{threshold}.json",
            {"RPG_PROBE_CLUSTER_THRESHOLD": threshold},
            f"synthetic-th{threshold}",
        )
        synthetic[threshold] = {
            **score_speakers(truth_turns, spans(result)),
            "wall_clock_s": result["metrics"]["wall_clock_s"],
        }

    forced = score_speakers(
        truth_turns,
        spans(
            run(
                args.cache / args.synthetic,
                work / "syn-k4.json",
                {"RPG_PROBE_NUM_CLUSTERS": "4"},
                "synthetic-k4",
            )
        ),
    )

    restricted: dict[str, Any] = {}
    for threshold in THRESHOLDS:
        result = run(
            args.cache / args.restricted,
            work / f"hg-th{threshold}.json",
            {"RPG_PROBE_CLUSTER_THRESHOLD": threshold},
            f"hiddengrid-th{threshold}",
        )
        # Label counts only. The spans themselves stay in the temp directory and out of
        # the repository: the source is CC BY-NC-ND.
        restricted[threshold] = {
            "labels": result["shape"]["distinct_physical_speakers"],
            "speaker_spans": result["shape"]["speaker_span_count"],
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "probe": "sherpa-onnx offline speaker diarization, clustering sweep",
                "output_kind": "model output",
                "provider_of_record": "sherpa-onnx pyannote-segmentation-3.0 + wespeaker CAM++",
                "generated_by": "research/probes/sweep_diarization.py",
                "why": "Fragmentation (one person, several labels) is recoverable; "
                "collision (several people, one label) fabricates attribution. Tuning "
                "trades one for the other, so which one a setting produces matters more "
                "than how close the count looks.",
                "synthetic_clip": {
                    "truth_kind": "declared truth, generated locally; no engine saw it",
                    "expected_speakers": len({t["physical_speaker"] for t in truth_turns}),
                    "by_threshold": synthetic,
                    "forced_num_clusters_4": forced,
                },
                "restricted_clip": {
                    "input": args.restricted,
                    "truth_kind": "unknown -- the manifest records "
                    "expected_physical_speakers: null",
                    "caveat": "label counts only; there is nothing to score against, and "
                    "the licence forbids committing the spans",
                    "by_threshold": restricted,
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(f"synthetic labels by threshold: "
          f"{ {k: v['predicted_speaker_labels'] for k, v in synthetic.items()} }")
    print(f"forced num_clusters=4 -> {forced['predicted_speaker_labels']} labels, "
          f"collisions {forced['colliding_labels']}")
    print(f"restricted labels by threshold: { {k: v['labels'] for k, v in restricted.items()} }")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
