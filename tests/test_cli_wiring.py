"""What the CLI guarantees, as opposed to what the provider guarantees.

The "no partial artifact" property is a property of *ordering*, and the ordering lives
here rather than in the provider: `run_pipeline` writes `canonical-session.json` the
moment it is called, so the only thing that keeps an unusable backend from leaving a
half-written session on disk is the CLI checking the backend first.

A test that asserted an empty directory without ever invoking the pipeline would pass
whatever the CLI did, which is worth saying out loud in a repository that has already
shipped one green and meaningless test.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from rpg_chronicle import cli
from rpg_chronicle.analysis.backend import BackendCredentialError, BackendUnavailableError
from rpg_chronicle.analysis.provider import ModelAnalysisProvider

from .fake_backend import FakeBackend

FIXTURE = Path(__file__).parents[1] / "benchmarks" / "fixtures" / "r0_synthetic_session.json"


def _args(output: Path, **overrides) -> argparse.Namespace:
    defaults = {
        "command": "run-fixture",
        "fixture": FIXTURE,
        "output": output,
        "analysis": "model",
        "model": "irrelevant",
        "max_input_tokens": 180_000,
        "overlap_turns": 8,
        "max_questions": 10,
        "cost_report": None,
    }
    return argparse.Namespace(**{**defaults, **overrides})


@pytest.mark.parametrize(
    ("backend", "expected"),
    [
        (
            FakeBackend(required_env_var="RPG_CHRONICLE_ABSENT_KEY"),
            BackendCredentialError,
        ),
        (FakeBackend(available=False), BackendUnavailableError),
    ],
    ids=["missing-credential", "unavailable-backend"],
)
def test_an_unusable_backend_leaves_the_output_directory_untouched(
    tmp_path, monkeypatch, backend, expected
):
    """This goes red if the CLI ever calls run_pipeline before preflight.

    Which is the whole point: the session directory does not exist afterwards, and it
    would exist if the ordering were reversed.
    """
    monkeypatch.delenv("RPG_CHRONICLE_ABSENT_KEY", raising=False)
    monkeypatch.setattr(cli, "_model_provider", lambda args: ModelAnalysisProvider(backend))

    output = tmp_path / "out"
    with pytest.raises(expected):
        cli._run_fixture(_args(output))

    assert not output.exists(), "an unusable backend must write nothing at all"


def test_the_ordering_is_what_makes_that_true(tmp_path, monkeypatch):
    """Demonstrates the failure the test above is guarding against.

    Running the pipeline with the same doomed provider -- skipping the CLI's preflight
    -- does leave a session directory behind. If that were not so, the test above
    would be passing for free.
    """
    from rpg_chronicle.pipeline import run_pipeline
    from rpg_chronicle.providers import FixtureTranscriptProvider

    output = tmp_path / "out"
    provider = ModelAnalysisProvider(FakeBackend(available=False))
    with pytest.raises(BackendUnavailableError):
        run_pipeline(FIXTURE, output, FixtureTranscriptProvider(), provider, session_id="s")

    assert (output / "s" / "canonical-session.json").exists()
    assert not (output / "s" / "review-package.json").exists()


def test_a_successful_model_run_writes_a_cost_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "_model_provider", lambda args: ModelAnalysisProvider(FakeBackend())
    )
    report = tmp_path / "cost.json"
    cli._run_fixture(_args(tmp_path / "out", cost_report=report))

    payload = json.loads(report.read_text())
    assert payload["is_declared_truth"] is False
    assert payload["requests"] >= 1
    assert payload["backend"] == "fake-backend"
    # The operator must be able to tell a measured figure from a declared one at a
    # glance, in the artifact and on the terminal.
    assert "not declared truth" in capsys.readouterr().out


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_input_tokens": 100},
        {"overlap_turns": -1},
        {"max_questions": 0},
    ],
    ids=["budget-below-overhead", "negative-overlap", "zero-question-cap"],
)
def test_invalid_analysis_options_are_reported_rather_than_traced(tmp_path, overrides):
    """A bad flag is a usage error, not a crash.

    These reach `TokenBudget` and `ModelAnalysisProvider` as `ValueError`, which would
    otherwise escape as a stack trace past the backend-error handling in `main`.
    """
    with pytest.raises(SystemExit) as caught:
        cli._run_fixture(_args(tmp_path / "out", **overrides))
    assert "invalid analysis options" in str(caught.value)
    assert not (tmp_path / "out").exists()


def test_a_fixture_without_declared_truth_is_refused_with_an_explanation(tmp_path):
    """Long-form fixtures ship without an `expected_analysis` block on purpose."""
    fixture = tmp_path / "long.json"
    fixture.write_text(
        json.dumps(
            {
                "session": {"id": "x"},
                "engine_output": {"engine": "e", "engine_version": "1", "turns": []},
            }
        )
    )
    with pytest.raises(SystemExit, match="no 'expected_analysis' block"):
        cli._run_fixture(_args(tmp_path / "out", fixture=fixture, analysis="fixture"))
