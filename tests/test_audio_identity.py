"""The identity procedure is a claim about other people's copies, so it has to be checkable.

These tests never touch the network, never need the recording, and - with one skipped
exception - never need a decoder. They build synthetic envelopes whose relationship is known
by construction: same shape, same shape shifted, different shape. What is pinned here is the
logic that turns two envelopes into a verdict, which is where every decision in this module
lives. The real recording is exercised separately and that run is written up in
benchmarks/notes/recording-identity.md, with the numbers those runs produced.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import shutil
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


def test_silence_is_floored_rather_than_dropped() -> None:
    """-inf frames are information about the recording; dropping them would shift every
    later frame and silently corrupt the alignment.

    Read against ffmpeg's own output text rather than by decoding a silent file, so the
    decision this pins is checked wherever the tests run and not only where ffmpeg is
    installed. The literal below is what ffmpeg prints for digital silence.
    """
    values = identity.parse_rms_levels(
        "frame:0 pts:0 pts_time:0\n"
        "lavfi.astats.1.RMS_level=-inf\n"
        "frame:1 pts:16000 pts_time:1\n"
        "lavfi.astats.1.RMS_level=-23.4\n"
        "frame:2 pts:32000 pts_time:2\n"
        "lavfi.astats.1.RMS_level=nan\n"
    )

    assert values == [identity.SILENCE_FLOOR_DB, -23.4, identity.SILENCE_FLOOR_DB]


def test_verify_reports_a_different_recording_without_refining_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy that shares no envelope must be rejected before the fine pass runs at all.

    The candidate's envelope is supplied directly rather than decoded, because what is under
    test is the decision verify() makes about two envelopes. Feeding it a real file would
    test ffmpeg as well, and would leave the refusal unchecked anywhere ffmpeg is absent.
    """
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
    calls: list[dict] = []

    def unrelated(path, frame_ms=1000, start_seconds=None, duration_seconds=None):
        calls.append({"frame_ms": frame_ms})
        return _speechlike(300, seed=7)

    monkeypatch.setattr(identity, "envelope", unrelated)

    coarse, fine = identity.verify(tmp_path / "whatever.webm", fingerprint)

    assert fine is None, "an unrelated envelope shares no shape and must not refine"
    assert not coarse.peak_found
    assert [call["frame_ms"] for call in calls] == [1000], "the fine pass must not have run"


# Measured on the real recording; every run is in benchmarks/notes/recording-identity.md.
# Each threshold is bounded by the worst a genuine copy scored on the pass it governs, and by
# the best a different recording scored. The two passes get different bounds because they see
# different numbers: a genuine copy trimmed by 12.347 s scores 0.7769 coarsely and 0.9989
# finely, so a single band for both would be wrong in one direction or the other.
OBSERVED_GAP = {
    "SAME_RECORDING_R": (0.0465, 0.9931),
    "COARSE_PEAK_FLOOR_R": (0.0465, 0.7769),
}


def test_the_filter_chain_actually_decodes(tmp_path: Path) -> None:
    """One end-to-end check that the ffmpeg invocation in envelope() is well formed.

    Skipped where ffmpeg is absent, which includes CI, so this is not what holds the
    behaviour - it is a local guard against a typo in the filter chain, which nothing else
    would catch until someone ran the tool against four hours of audio. Everything the
    module decides is tested above without a decoder.
    """
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    tone = tmp_path / "tone.wav"
    identity.subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:r=16000",
         "-t", "3", str(tone)],
        check=True,
    )

    values = identity.envelope(tone, frame_ms=1000)

    # A steady tone has a constant RMS, so a correctly framed chain returns the same finite
    # level for every second. Its actual value depends on the source's amplitude and is not
    # the point; that the frames agree is.
    assert len(values) >= 3
    assert all(identity.SILENCE_FLOOR_DB < v < 0 for v in values[:3]), values
    assert max(values[:3]) - min(values[:3]) < 0.1, values


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
