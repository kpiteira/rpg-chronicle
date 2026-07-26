"""Checks that CI still runs what it is relied upon to run.

These assert on workflow configuration rather than behaviour, which is a shape
worth using sparingly. It earns its place here because the evidence for the step
is the workflow's own green run: nothing else notices if an edit drops it.

The assertion is on a `run:` line rather than on the file's text, so a mention
in a comment or a disabled step would not satisfy it. Parsing the YAML would be
stronger still; it is not worth a runtime dependency the project does not
otherwise carry.
"""

from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/checks.yml"


def run_steps() -> list[str]:
    return [
        line.split("run:", 1)[1].strip()
        for line in WORKFLOW.read_text().splitlines()
        if line.lstrip().startswith("run:")
    ]


def test_ci_runs_the_benchmark_manifest_validator() -> None:
    assert any("scripts/validate_benchmark_manifests.py" in step for step in run_steps())


def test_ci_runs_the_test_suite() -> None:
    assert any(step.startswith("uv run pytest") for step in run_steps())
