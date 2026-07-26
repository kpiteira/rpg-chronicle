"""Establish that two copies of a recording are the same recording, and how far apart.

Some sources cannot be byte-reproduced. A streaming platform re-encodes, so two people who
download the same video get different files, and `scripts/fetch_benchmark_media.py` -- which
compares a digest against published bytes -- has nothing to compare. That is a problem for
truth, not just for tidiness: an annotation anchored at 2 h 41 m 03 s means nothing if the
reader's copy starts a second earlier, because every anchor silently points at the wrong
moment.

This module answers two questions a digest cannot:

    Is this the same recording?   -- by correlating a loudness envelope, which survives
                                     re-encoding because it describes the sound rather than
                                     the bytes.
    Where does it start?          -- by finding the lag at which the two envelopes agree,
                                     so a reader can correct their offsets instead of
                                     trusting that they match.

The envelope is RMS level per frame over the decoded audio, after a stated normalization to
mono 16 kHz. It is measurement, not media: at one frame per second it is a few thousand
numbers describing how loud the room was, and no speech can be recovered from it.

Two resolutions, because they answer different questions. The coarse pass, one frame per
second across the whole recording, identifies it and catches gross misalignment. The fine
pass, one frame per 10 ms over a short probe window, locates the offset closely enough for
millisecond anchors.

Usage:

    uv run python scripts/audio_identity.py fingerprint <audio> --out <file>
    uv run python scripts/audio_identity.py verify <audio> --against <file>

`verify` prints the correlation, the lag, and a verdict; it exits non-zero when the copy
does not match, so it can gate an annotation run.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Identity is decided on the fine pass, not the coarse one, and the reason is worth stating
# because getting it wrong makes the tool reject copies that are perfectly good. Coarse
# frames are a second long, so a copy shifted by a fractional second has every frame
# averaging a different slice of the sound than the reference did: a genuine copy trimmed
# by 12.347 s scores 0.78 coarsely, which would fail any threshold worth setting. At 10 ms
# the same misalignment is under one frame and the same copy scores above 0.99. So the
# coarse pass only locates the lag; the fine pass judges.
SAME_RECORDING_R = 0.90
# Below this the coarse pass has not found a peak worth refining, and the recordings are
# unrelated rather than merely offset.
COARSE_PEAK_FLOOR_R = 0.30
# Beyond this the copies are too far apart to be a delay; something has been cut or added.
MAX_PLAUSIBLE_LAG_SECONDS = 60.0
# How far the fine pass searches around the coarse estimate. Coarse lag is accurate to
# about a second, so this only has to cover its rounding plus a margin.
FINE_SEARCH_SECONDS = 3.0
SILENCE_FLOOR_DB = -120.0


@dataclass(frozen=True)
class Alignment:
    """How two copies of a recording relate."""

    correlation: float
    lag_seconds: float
    frames_compared: int

    @property
    def same_recording(self) -> bool:
        """Only meaningful on a fine alignment; see SAME_RECORDING_R for why."""
        return self.correlation >= SAME_RECORDING_R

    @property
    def peak_found(self) -> bool:
        """Whether a coarse pass located something worth refining."""
        return self.correlation >= COARSE_PEAK_FLOOR_R


def envelope(
    path: Path,
    frame_ms: int = 1000,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
) -> list[float]:
    """RMS level per frame, in dBFS, over the decoded audio.

    Decoding to mono 16 kHz first is what makes the result comparable across containers:
    the number describes the sound, so an AAC copy and an Opus copy of one recording agree
    even though their bytes share nothing.
    """
    samples_per_frame = max(1, int(16000 * frame_ms / 1000))
    command = ["ffmpeg", "-hide_banner", "-nostats"]
    if start_seconds is not None:
        command += ["-ss", f"{start_seconds:.3f}"]
    if duration_seconds is not None:
        command += ["-t", f"{duration_seconds:.3f}"]
    command += [
        "-i",
        str(path),
        "-af",
        (
            "aresample=16000,aformat=channel_layouts=mono,"
            f"asetnsamples=n={samples_per_frame}:p=0,"
            "astats=metadata=1:reset=1:measure_perchannel=RMS_level:measure_overall=none,"
            "ametadata=print:key=lavfi.astats.1.RMS_level:file=-"
        ),
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return parse_rms_levels(result.stdout)


def parse_rms_levels(output: str) -> list[float]:
    """Read per-frame RMS levels out of ffmpeg's ametadata output.

    Split from ``envelope`` so the part with a decision in it can be checked without a
    decoder present: how silence is handled is the decision, and running ffmpeg to reach it
    would make the check depend on a tool the test does not care about.
    """
    values: list[float] = []
    for match in re.finditer(r"lavfi\.astats\.1\.RMS_level=(-?[\d.]+|-?inf|nan)", output):
        token = match.group(1)
        # Digital silence reports as -inf, which no arithmetic survives; floor it instead,
        # because a silent frame is information about the recording, not a missing value.
        values.append(SILENCE_FLOOR_DB if token in {"-inf", "nan"} else float(token))
    return values


def _pearson(a: list[float], b: list[float]) -> float:
    """Correlation of two equal-length series, or 0.0 when either is flat."""
    n = len(a)
    if n == 0:
        return 0.0
    mean_a, mean_b = sum(a) / n, sum(b) / n
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a <= 0 or var_b <= 0:
        return 0.0
    return num / math.sqrt(var_a * var_b)


def align(reference: list[float], candidate: list[float], max_lag_frames: int) -> Alignment:
    """Find the lag at which the candidate best reproduces the reference.

    A positive lag means the candidate is later than the reference: its content at time t
    corresponds to the reference at t minus lag.
    """
    best = Alignment(-1.0, 0.0, 0)
    for lag in range(-max_lag_frames, max_lag_frames + 1):
        if lag >= 0:
            left, right = reference[: len(reference) - lag], candidate[lag:]
        else:
            left, right = reference[-lag:], candidate[: len(candidate) + lag]
        overlap = min(len(left), len(right))
        if overlap < 30:
            continue
        r = _pearson(left[:overlap], right[:overlap])
        if r > best.correlation:
            best = Alignment(r, float(lag), overlap)
    return best


def write_fingerprint(path: Path, audio: Path, probe_start: float, probe_seconds: float) -> dict:
    """Record what a later reader needs to recognise this recording and align to it."""
    coarse = envelope(audio, frame_ms=1000)
    fine = envelope(
        audio, frame_ms=10, start_seconds=probe_start, duration_seconds=probe_seconds
    )
    document = {
        "method": "rms_envelope_v1",
        "normalization": "ffmpeg aresample=16000, mono, RMS level per frame in dBFS",
        "coarse_frame_ms": 1000,
        "fine_frame_ms": 10,
        "fine_probe_start_seconds": probe_start,
        "fine_probe_seconds": probe_seconds,
        "silence_floor_db": SILENCE_FLOOR_DB,
        "same_recording_correlation": SAME_RECORDING_R,
        "coarse": [round(v, 1) for v in coarse],
        "fine": [round(v, 1) for v in fine],
    }
    path.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
    return document


def verify(audio: Path, fingerprint_path: Path) -> tuple[Alignment, Alignment | None]:
    """Compare a local copy against a committed fingerprint, coarsely then finely."""
    document = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    coarse_reference = [float(v) for v in document["coarse"]]
    coarse = align(
        coarse_reference,
        envelope(audio, frame_ms=document["coarse_frame_ms"]),
        max_lag_frames=int(MAX_PLAUSIBLE_LAG_SECONDS),
    )
    if not coarse.peak_found:
        return coarse, None

    # Fine pass: probe the same span of content, shifted by whatever the coarse pass found,
    # so the two windows describe the same moment before the offset is measured precisely.
    # The candidate window is widened by the search range on both sides, because a probe cut
    # to exactly the reference's length cannot be slid against it.
    frame_seconds = float(document["fine_frame_ms"]) / 1000.0
    # The candidate window starts FINE_SEARCH_SECONDS early, so the expected lag is exactly
    # that much. Searching only that far puts the answer on the boundary, where a decoder
    # that seeks a few frames differently pushes the true peak outside the range and the
    # copy is wrongly rejected -- which is what happened to the 22 kHz copy before this
    # doubled. Searching twice as far leaves slack on both sides of the expected lag.
    max_lag_frames = int(2 * FINE_SEARCH_SECONDS / frame_seconds)
    probe_start = float(document["fine_probe_start_seconds"]) + coarse.lag_seconds
    fine_reference = [float(v) for v in document["fine"]]
    fine_candidate = envelope(
        audio,
        frame_ms=document["fine_frame_ms"],
        start_seconds=max(0.0, probe_start - FINE_SEARCH_SECONDS),
        duration_seconds=float(document["fine_probe_seconds"]) + 2 * FINE_SEARCH_SECONDS,
    )
    fine = align(fine_reference, fine_candidate, max_lag_frames=max_lag_frames)
    # The candidate window began FINE_SEARCH_SECONDS early, so the lag it reports is
    # measured from there rather than from the probe start.
    offset = coarse.lag_seconds - FINE_SEARCH_SECONDS + fine.lag_seconds * frame_seconds
    return coarse, Alignment(fine.correlation, offset, fine.frames_compared)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    make = sub.add_parser("fingerprint", help="record a fingerprint for a reference copy")
    make.add_argument("audio")
    make.add_argument("--out", required=True)
    make.add_argument("--probe-start", type=float, default=300.0)
    make.add_argument("--probe-seconds", type=float, default=60.0)

    check = sub.add_parser("verify", help="check a local copy against a committed fingerprint")
    check.add_argument("audio")
    check.add_argument("--against", required=True)

    args = parser.parse_args(argv)

    if args.command == "fingerprint":
        document = write_fingerprint(
            Path(args.out), Path(args.audio), args.probe_start, args.probe_seconds
        )
        print(f"wrote: {args.out}")
        print(f"coarse frames: {len(document['coarse'])} at {document['coarse_frame_ms']} ms")
        print(f"fine frames: {len(document['fine'])} at {document['fine_frame_ms']} ms")
        return 0

    coarse, fine = verify(Path(args.audio), Path(args.against))
    print(f"coarse correlation: {coarse.correlation:.4f} over {coarse.frames_compared} frames")
    print(f"coarse lag: {coarse.lag_seconds:+.0f} s (locates the fine pass; does not judge)")
    if fine is None:
        print(f"DIFFERENT RECORDING: no alignment above {COARSE_PEAK_FLOOR_R} to refine")
        print("This copy does not follow the same loudness envelope. Committed anchors do")
        print("not apply to it, and no offset can make them apply.")
        return 1
    print(f"fine correlation: {fine.correlation:.4f} over {fine.frames_compared} frames")
    if not fine.same_recording:
        print(f"DIFFERENT RECORDING: fine correlation below {SAME_RECORDING_R}")
        print("A coarse peak was found but the recordings do not agree closely once")
        print("aligned, so committed anchors cannot be trusted against this copy.")
        return 1
    print(f"offset to apply: {fine.lag_seconds:+.3f} s")
    print("SAME RECORDING")
    if abs(fine.lag_seconds) < 0.05:
        print("Anchors apply as committed; the offset is below the annotation's precision.")
    else:
        print(f"Add {-fine.lag_seconds:+.3f} s to committed anchors to locate them in this copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
