"""Checks that CI still runs what it is relied upon to run.

These assert on workflow configuration rather than behaviour, which is a shape
worth using sparingly. It earns its place here because the evidence for the step
is the workflow's own green run: nothing else notices if an edit drops it.
"""

from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/checks.yml"


def test_ci_runs_the_benchmark_manifest_validator() -> None:
    assert "scripts/validate_benchmark_manifests.py" in WORKFLOW.read_text()
