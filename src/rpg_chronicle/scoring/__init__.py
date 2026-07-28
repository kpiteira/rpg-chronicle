"""Scoring a run against a benchmark manifest.

The instrument M2's exit criterion is judged by. It reads a completed session directory
and an answer key, and reports each dimension `docs/MILESTONES.md` names -- with a stated
basis, or with a stated reason it cannot be measured yet.

It never improves a score. A component that both measures and tunes cannot be trusted
about either, which is why this package reads sessions and writes reports and touches
nothing in the pipeline.
"""

from __future__ import annotations

from .contamination import ContaminationVerdict, assess, engine_identity
from .harness import (
    HARNESS_VERSION,
    Dimension,
    SessionNotFoundError,
    load_session,
    score,
    time_basis,
)
from .manifest import Manifest, ManifestNotFoundError, load_manifest, resolve_manifest
from .report import render, render_json

__all__ = [
    "HARNESS_VERSION",
    "ContaminationVerdict",
    "Dimension",
    "Manifest",
    "ManifestNotFoundError",
    "SessionNotFoundError",
    "assess",
    "engine_identity",
    "load_manifest",
    "load_session",
    "render",
    "render_json",
    "resolve_manifest",
    "score",
    "time_basis",
]
