#!/usr/bin/env python3
"""Build a rights-clear multi-speaker clip with known truth, from a committed script.

The Hiddengrid benchmark input is CC BY-NC-ND: its transcript cannot be committed, so
probe evidence drawn from it has to stay aggregate. That is the right constraint but a
poor artifact -- a reader cannot see what a stack's output actually looks like.

This generator solves that by synthesizing the clip locally with macOS ``say``. The
audio is never committed; the script that produces it is, so the probe stays
reproducible while the repository holds no restricted media.

What this clip is: a controlled sample with declared truth (``docs/EVALUATION.md``
corpus tier 4), useful for checking output shape, timestamp sanity, speaker-count
behaviour, and fantasy-name handling.

What this clip is NOT: evidence about room audio. Synthetic voices are noiseless,
non-overlapping, and acoustically far apart, which is the easy end of every axis that
makes real diarization hard. A stack that scores well here has proven nothing about a
four-hour iPad recording. Read the Hiddengrid aggregates for that.

Usage:
    make_synthetic_clip.py --out-dir ~/.cache/rpg-chronicle/benchmark
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

SAMPLE_RATE = 16_000
GAP_MS = 350

# Four macOS system voices, chosen to be clearly distinct. Fantasy nouns are deliberate:
# invented proper nouns are a known weak spot for general-purpose ASR and this is the
# only input in the probe set whose spelling truth we are allowed to publish.
SCRIPT: list[tuple[str, str, str]] = [
    ("GM", "Daniel", "The road out of Vaelthorn narrows as it climbs toward the Ashen Spire."),
    ("PLAYER_A", "Samantha", "Ilyra draws her hood up and checks the sigil on her palm again."),
    ("PLAYER_B", "Karen", "Does Brann see anything moving on the ridge? I want a perception check."),
    ("GM", "Daniel", "Roll it. The wind is loud enough that you are at disadvantage."),
    ("PLAYER_B", "Karen", "That is a fourteen. Not great."),
    ("PLAYER_C", "Ralph", "Korrigan keeps walking. He has no patience for ridgelines today."),
    ("GM", "Daniel", "Then you three reach the gate before the light goes. It is already open."),
    ("PLAYER_A", "Samantha", "Ilyra stops. Open how? Forced open, or left open?"),
    ("GM", "Daniel", "Left open. The bar is set neatly against the wall, as if by someone unhurried."),
    ("PLAYER_C", "Ralph", "Korrigan says what everyone is thinking. That is worse."),
    ("PLAYER_B", "Karen", "Brann wants to know if the Warden of the Spire is expecting us."),
    ("GM", "Daniel", "You will find out. Something inside the courtyard says your name first."),
]


def _duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(out.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--name", default="synthetic-table-talk")
    args = parser.parse_args()

    work = args.out_dir / f"{args.name}-parts"
    work.mkdir(parents=True, exist_ok=True)

    truth, offset_ms, pieces = [], 0, []
    for index, (speaker, voice, line) in enumerate(SCRIPT):
        raw = work / f"{index:02d}.aiff"
        wav = work / f"{index:02d}.wav"
        subprocess.run(["say", "-v", voice, "-o", str(raw), line], check=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-c:a", "pcm_s16le", str(wav)],
            check=True,
        )
        length_ms = round(_duration_s(wav) * 1000)
        truth.append(
            {
                "index": index,
                "physical_speaker": speaker,
                "voice": voice,
                "text": line,
                "start_ms": offset_ms,
                "end_ms": offset_ms + length_ms,
            }
        )
        pieces.append(wav)
        offset_ms += length_ms + GAP_MS

    # Concatenate with a fixed silent gap so the recorded offsets are exact rather than
    # approximate. anullsrc is generated at the same rate to avoid a resample seam.
    silence = work / "gap.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", f"{GAP_MS / 1000}",
         "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-c:a", "pcm_s16le", str(silence)],
        check=True,
    )
    listing = work / "concat.txt"
    lines = []
    for position, piece in enumerate(pieces):
        lines.append(f"file '{piece.name}'")
        if position != len(pieces) - 1:
            lines.append(f"file '{silence.name}'")
    listing.write_text("\n".join(lines) + "\n")

    audio = args.out_dir / f"{args.name}.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(audio)],
        check=True,
    )

    manifest = args.out_dir / f"{args.name}-truth.json"
    manifest.write_text(
        json.dumps(
            {
                "id": args.name,
                "corpus_tier": "controlled_synthetic",
                "generated_by": "research/probes/make_synthetic_clip.py",
                "provider_of_record": "macOS say (system text-to-speech)",
                "output_kind": "declared truth",
                "rights": {
                    "copyright_holder": "this repository",
                    "license": "MIT, as the repository",
                    "redistribution": "permitted",
                    "note": "Lines are original; the audio is synthesized locally and is "
                    "not committed. No third-party media is involved.",
                },
                "conditions": {
                    "capture_layout": "synthesized, one voice per line",
                    "overlap": "none",
                    "background_noise": "none",
                    "music_or_effects": False,
                    "caveat": "Acoustically far easier than the target single-room iPad "
                    "condition. Use for output shape and sanity, never for capability "
                    "claims about real play.",
                },
                "sample_rate": SAMPLE_RATE,
                "gap_ms": GAP_MS,
                "duration_ms": truth[-1]["end_ms"],
                "expected_physical_speakers": len({row["physical_speaker"] for row in truth}),
                "turns": truth,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {audio} ({truth[-1]['end_ms'] / 1000:.1f}s) and {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
