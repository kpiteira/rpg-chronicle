"""sherpa-onnx speaker diarization behind the diarization seam.

Adopted by R01 as a placeholder, not as a solved component, and the distinction is
load-bearing. `research/speech-stack-scorecard.md` records that no clustering threshold
recovered a known speaker count on a clip with four speakers -- the label count jumped
from six to three with nothing in between -- and that supplying the true count with
`num_clusters` produced *two merged speaker pairs*, which is the failure mode that
fabricates attribution rather than the recoverable one.

It is here because it is the only local diarizer probed that needs no Hugging Face
account and no gated model acceptance, it runs at roughly 20x realtime, and
`docs/PRODUCT.md` prefers a useful anonymous transcript over failed perfect diarization.
Its replacement trigger is already satisfied; `reliability` says so in every artifact
this produces.

The threshold default stays low on purpose. Low thresholds fragment one speaker into
several labels, which a later merge or a single human correction can undo. High
thresholds merge distinct speakers into one label, which silently attributes one
person's words to another and no downstream correction can find.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .engine import (
    DiarizationResult,
    EngineResponseError,
    EngineUnavailableError,
    SpeakerSpan,
    require_model_file,
)

DEFAULT_SEGMENTATION = "sherpa-onnx-pyannote-segmentation-3-0/model.onnx"
DEFAULT_EMBEDDING = "wespeaker_en_voxceleb_CAMPP.onnx"

DEFAULT_CLUSTER_THRESHOLD = 0.5
"""Low by design; see the module docstring. Raising it trades a recoverable failure for
an unrecoverable one, and R01 measured exactly that trade at 0.7 and above."""

RELIABILITY = "unreliable"
INSTALL_HINT = (
    "Install it with `uv pip install sherpa-onnx`; see research/probes/README.md for "
    "the model downloads used to select it."
)
MODEL_HINT = (
    "Fetch the segmentation and embedding models as described in "
    "research/probes/README.md, or point --model-dir at the directory holding them."
)


class SherpaDiarizationEngine:
    """Speaker spans through sherpa-onnx's offline diarizer."""

    name = "sherpa-onnx-offline-speaker-diarization"

    def __init__(
        self,
        *,
        model_dir: Path,
        segmentation: str = DEFAULT_SEGMENTATION,
        embedding: str = DEFAULT_EMBEDDING,
        cluster_threshold: float = DEFAULT_CLUSTER_THRESHOLD,
        num_clusters: int = -1,
        threads: int | None = None,
    ) -> None:
        import os

        self._segmentation = Path(model_dir) / segmentation
        self._embedding = Path(model_dir) / embedding
        self._cluster_threshold = cluster_threshold
        self._num_clusters = num_clusters
        self._threads = threads or os.cpu_count() or 4

    def preflight(self) -> None:
        # Every module `diarize` imports, not just the headline one. soundfile in
        # particular fails at import when libsndfile is absent, and discovering that
        # after recognition has already run is exactly the failure preflight exists to
        # prevent.
        for module in ("sherpa_onnx", "numpy", "soundfile"):
            try:
                __import__(module)
            except ImportError as error:
                raise EngineUnavailableError(
                    f"engine {self.name!r} requires the {module!r} package, which is "
                    f"not importable. {INSTALL_HINT}"
                ) from error
        require_model_file(self._segmentation, engine_name=self.name, install_hint=MODEL_HINT)
        require_model_file(self._embedding, engine_name=self.name, install_hint=MODEL_HINT)

    def diarize(self, audio: Path) -> DiarizationResult:
        self.preflight()
        import numpy as np
        import sherpa_onnx
        import soundfile as sf

        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(self._segmentation)
                ),
                num_threads=self._threads,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(self._embedding), num_threads=self._threads
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=self._num_clusters, threshold=self._cluster_threshold
            ),
            min_duration_on=0.3,
            min_duration_off=0.5,
        )
        if not config.validate():
            raise EngineResponseError(f"{self.name} rejected the diarization configuration")

        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        samples, sample_rate = sf.read(str(audio), dtype="float32", always_2d=True)
        if samples.shape[1] != 1:
            # Refusing rather than picking channel zero, which R01's probe did silently.
            # Not because channel zero is the wrong signal: every benchmark item measured
            # is a single mixed track on near-identical channels, an L-R residual 34 dB
            # below programme. It is because a recording that genuinely carried
            # per-speaker channels would need handling nobody has designed, and silently
            # discarding channels is the wrong default for a case not yet met. An earlier
            # version of this comment said the channels differed by 34 dB, inverting the
            # measurement; see research/what-real-recordings-do.md.
            raise EngineResponseError(
                f"{audio.name} has {samples.shape[1]} channels; {self.name} needs mono. "
                "Downmix it first so the signal that was diarized is the signal that "
                "was measured."
            )
        if sample_rate != diarizer.sample_rate:
            raise EngineResponseError(
                f"{audio.name} is {sample_rate} Hz; {self.name} needs "
                f"{diarizer.sample_rate} Hz. Resample it first, so the resampler's cost "
                "is not charged to the diarizer."
            )

        result = diarizer.process(np.ascontiguousarray(samples[:, 0])).sort_by_start_time()
        spans = [
            SpeakerSpan(
                start_ms=round(segment.start * 1000),
                end_ms=round(segment.end * 1000),
                label=f"SPEAKER_{segment.speaker:02d}",
            )
            for segment in result
        ]
        labels = sorted({span.label for span in spans})

        native: dict[str, Any] = {
            "engine": self.name,
            "segmentation_model": self._segmentation.name,
            "embedding_model": self._embedding.name,
            "clustering": {
                "num_clusters": self._num_clusters,
                "threshold": self._cluster_threshold,
            },
            "span_count": len(spans),
            "distinct_labels": len(labels),
            "reliability": RELIABILITY,
            "reliability_basis": (
                "R01 measured no clustering threshold recovering a known speaker count, "
                "and constraining the count merged distinct speakers. Labels are "
                "cluster identifiers, not people. See research/speech-stack-scorecard.md."
            ),
            "spans": [
                {"start_ms": span.start_ms, "end_ms": span.end_ms, "label": span.label}
                for span in spans
            ],
        }
        return DiarizationResult(
            spans=spans,
            native=native,
            reliability=RELIABILITY,
            speaker_labels=labels,
        )
