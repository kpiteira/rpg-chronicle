"""The identity procedure is a claim about other people's copies, so it has to be checkable.

These tests never touch the network and never need the recording. They build synthetic
envelopes whose relationship is known by construction — same shape, same shape shifted,
different shape — and assert the procedure reports it. The real recording is exercised
separately, and that run is written up in the notes; what is pinned here is the logic that
turns two envelopes into a verdict.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audio_identity.py"


def _load():
    spec = importlib.util.spec_from_file_location("audio_identity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


identity = _load()


def _speechlike(n: int, seed: int = 0) -> list[float]:
    """An envelope with the shape real speech produces: locally smooth, globally aperiodic.

    A smoothed random walk rather than a sum of sinusoids, because two sinusoid sums built
    from one basis still correlate at 0.94 at some lag — which made an earlier version of
    this file's negative case pass for the wrong reason. Two walks from different seeds are
    genuinely unrelated, as two different recordings are.
    """
    rng = random.Random(seed)
    raw = [rng.gauss(0.0, 1.0) for _ in range(n + 8)]
    smoothed = [sum(raw[i : i + 8]) / 8 for i in range(n)]
    return [-30 + 25 * v for v in smoothed]


def test_a_copy_of_the_same_envelope_aligns_at_zero() -> None:
    series = _speechlike(600)

    result = identity.align(series, list(series), max_lag_frames=50)

    assert result.correlation > 0.999
    assert result.lag_seconds == 0.0
    assert result.same_recording


def test_a_shifted_copy_reports_the_shift() -> None:
    """Recovering the offset is the half of the claim that makes anchors usable."""
    series = _speechlike(600)
    shifted = series[40:]

    result = identity.align(series, shifted, max_lag_frames=80)

    assert result.lag_seconds == -40.0
    assert result.correlation > 0.999


def test_a_different_recording_does_not_align() -> None:
    """The verdict has to be capable of coming out negative, or it says nothing."""
    result = identity.align(_speechlike(600), _speechlike(600, seed=7), max_lag_frames=50)

    assert result.correlation < identity.SAME_RECORDING_R
    assert not result.same_recording


def test_lossy_degradation_still_counts_as_the_same_recording() -> None:
    """A re-encode moves every frame a little; that must not read as a different recording."""
    series = _speechlike(600)
    degraded = [v + 0.8 * math.sin(9.1 * i) for i, v in enumerate(series)]

    result = identity.align(series, degraded, max_lag_frames=50)

    assert result.same_recording


def test_correlation_of_a_flat_series_is_zero_rather_than_an_error() -> None:
    """Digital silence has no shape to correlate, and must not raise or claim a match."""
    assert identity._pearson([-120.0] * 50, _speechlike(50)) == 0.0


def test_silence_is_floored_rather_than_dropped(tmp_path: Path) -> None:
    """-inf frames are information about the recording; dropping them would shift every
    later frame and silently corrupt the alignment."""
    silent = tmp_path / "silent.wav"
    identity.subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
         "-t", "3", str(silent)],
        check=True,
    )

    values = identity.envelope(silent, frame_ms=1000)

    assert len(values) >= 3
    assert all(v == identity.SILENCE_FLOOR_DB for v in values[:3])


def test_verify_reports_a_different_recording_without_refining_it(tmp_path: Path) -> None:
    fingerprint = tmp_path / "fp.json"
    fingerprint.write_text(
        json.dumps(
            {
                "method": "rms_envelope_v1",
                "coarse_frame_ms": 1000,
                "fine_frame_ms": 10,
                "fine_probe_start_seconds": 0.0,
                "fine_probe_seconds": 1.0,
                "coarse": _speechlike(300),
                "fine": _speechlike(100),
            }
        )
    )
    tone = tmp_path / "tone.wav"
    identity.subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:r=16000",
         "-t", "300", str(tone)],
        check=True,
    )

    coarse, fine = identity.verify(tone, fingerprint)

    assert fine is None, "a steady tone shares no envelope with speech and must not refine"
    assert not coarse.peak_found


# Measured on the real recording; every run is in benchmarks/notes/recording-identity.md.
# Each threshold is bounded by the worst a genuine copy scored on the pass it governs, and by
# the best a different recording scored. The two passes get different bounds because they see
# different numbers: a genuine copy trimmed by 12.347 s scores 0.7769 coarsely and 0.9989
# finely, so a single band for both would be wrong in one direction or the other.
OBSERVED_GAP = {
    "SAME_RECORDING_R": (0.0465, 0.9931),
    "COARSE_PEAK_FLOOR_R": (0.0465, 0.7769),
}


@pytest.mark.parametrize("name", sorted(OBSERVED_GAP))
def test_thresholds_sit_between_the_observed_extremes(name: str) -> None:
    """The thresholds are measurements, not preferences, and this pins the measurement.

    The upper bound of each gap is the worst a genuine copy managed on that pass. The lower
    bound is the best either different recording managed, and one of those two was a different
    episode of the same campaign with the same cast, room and encoder. A threshold outside its
    gap has stopped deciding anything the recording demonstrated.
    """
    low, high = OBSERVED_GAP[name]

    assert low < getattr(identity, name) < high
