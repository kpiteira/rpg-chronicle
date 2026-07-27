"""Checks that CI still runs what it is relied upon to run.

These assert on workflow configuration rather than behaviour, which is a shape
worth using sparingly. It earns its place here because the evidence for these
steps is the workflow's own green run: nothing else notices if an edit drops
one.

The workflow is split into steps rather than searched as text, so a mention in
a comment does not count, a step switched off with `if: false` does not count,
and a `run: |` block is read in full. Parsing YAML properly would be stronger
still; it is not worth a runtime dependency the project does not otherwise
carry, and the shapes that would fool this are shapes nobody writes by accident.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/checks.yml"

STEP = re.compile(r"^(\s*)- ")
DISABLED = re.compile(r"^\s*if:\s*false\s*$", re.MULTILINE)


def steps() -> list[str]:
    """The workflow's step blocks, as text."""
    blocks: list[list[str]] = []
    indent: int | None = None
    for line in WORKFLOW.read_text().splitlines():
        start = STEP.match(line)
        if start and (indent is None or len(start.group(1)) == indent):
            indent = len(start.group(1))
            blocks.append([line])
        elif indent is None or not blocks:
            continue
        elif not line.strip() or len(line) - len(line.lstrip()) > indent:
            blocks[-1].append(line)
        else:
            # Dedented back out of the step list: a new job or a new key.
            indent = None
    return ["\n".join(block) for block in blocks]


def commands() -> list[str]:
    """Every command an enabled step would run."""
    found = []
    for step in steps():
        if DISABLED.search(step):
            continue
        after = step.split("run:", 1)
        if len(after) == 2:
            found.append(after[1])
    return found


def test_ci_does_not_try_to_validate_manifests_it_cannot_see() -> None:
    """Manifests and answer keys live beside the recordings, outside this repository.

    CI has no content directory, so a manifest-validation step here would either fail or,
    worse, pass by finding nothing. The validator is a tool the operator runs; this asserts
    the step stays gone, because re-adding it would look like restoring a check.
    """
    assert not any("validate_benchmark_manifests" in run for run in commands())


def test_ci_runs_the_test_suite() -> None:
    assert any("uv run pytest" in run for run in commands())


def test_a_disabled_step_does_not_count() -> None:
    """The guard has to fail when the step it guards stops running."""
    disabled = "      - name: Test\n        if: false\n        run: uv run pytest -q\n"
    assert not DISABLED.search("      - name: Test\n        run: uv run pytest -q\n")
    assert DISABLED.search(disabled)
