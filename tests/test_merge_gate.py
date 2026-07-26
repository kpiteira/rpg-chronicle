"""The pre-merge gate hook.

`tests/test_hook_classifier.py` covers command recognition. This file covers the
shell wiring around it: decision parsing, how a pull request is resolved, and
each refusal. The goal validator's finding on the pull request that introduced
these tests was that the wiring had none, and that the surviving defect lived
there rather than in the classifier.

`gh` is stubbed on PATH, so the gate is exercised without network access. The
stub records its arguments, which is how the branch-resolution test proves the
gate asks about the branch the merge names rather than the current one.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/hooks/pre-merge-gate.sh"

HEAD = "1111111111111111111111111111111111111111"
STALE = "2222222222222222222222222222222222222222"

GH_STUB = """#!/usr/bin/env python3
import json, os, sys

argv = sys.argv[1:]
with open(os.environ["GH_CALL_LOG"], "a") as log:
    log.write(" ".join(argv) + "\\n")

if os.environ.get("GH_FAIL_VIEW") and argv[:2] == ["pr", "view"]:
    sys.exit(1)

if "--json" in argv:
    field = argv[argv.index("--json") + 1]
    if field == "number":
        print(os.environ.get("GH_PR_NUMBER", "7"))
    elif field == "headRefOid":
        print(os.environ.get("GH_HEAD_SHA", ""))
    elif field == "comments":
        print(os.environ.get("GH_VERDICT", ""))
sys.exit(0)
"""


@pytest.fixture
def gate(tmp_path: Path):
    """Run the gate with a stubbed `gh`.

    Returns `(exit code, stderr, recorded gh calls)`.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "gh"
    stub.write_text(GH_STUB)
    stub.chmod(0o755)
    call_log = tmp_path / "gh-calls.log"
    call_log.touch()

    def run(command: str, **environment: str):
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_CALL_LOG": str(call_log),
            "GH_HEAD_SHA": HEAD,
            **environment,
        }
        result = subprocess.run(
            ["bash", str(GATE)],
            input=json.dumps({"tool_input": {"command": command}}),
            capture_output=True,
            text=True,
            env=env,
            check=False,  # a refusal is exit 2, and that is the thing under test
        )
        return result.returncode, result.stderr, call_log.read_text()

    return run


def verdict(sha: str, value: str = "pass") -> str:
    return f'<!-- goal-validator sha:{sha} -->\n```json\n{{"verdict": "{value}"}}\n```'


def test_an_ordinary_command_is_allowed(gate) -> None:
    code, _, calls = gate("uv run pytest -q")
    assert code == 0
    assert calls == ""  # no reason to ask GitHub anything


def test_a_push_to_main_is_refused(gate) -> None:
    code, stderr, _ = gate("git push origin HEAD:main")
    assert code == 2
    assert "Refusing to push to main" in stderr


def test_an_environment_prefix_does_not_hide_a_push_to_main(gate) -> None:
    code, stderr, _ = gate("GIT_TRACE=1 git push origin main")
    assert code == 2
    assert "Refusing to push to main" in stderr


def test_a_merge_with_a_passing_verdict_for_the_head_is_allowed(gate) -> None:
    code, stderr, _ = gate("gh pr merge 7 --rebase", GH_VERDICT=verdict(HEAD))
    assert code == 0, stderr


def test_a_merge_without_a_verdict_is_refused(gate) -> None:
    code, stderr, _ = gate("gh pr merge 7 --rebase", GH_VERDICT="")
    assert code == 2
    assert "No goal-validator verdict" in stderr


def test_a_verdict_for_a_superseded_commit_is_refused(gate) -> None:
    code, stderr, _ = gate("gh pr merge 7 --rebase", GH_VERDICT=verdict(STALE))
    assert code == 2
    assert "predates its current head commit" in stderr


def test_a_blocking_verdict_is_refused(gate) -> None:
    code, stderr, _ = gate(
        "gh pr merge 7 --rebase", GH_VERDICT=verdict(HEAD, "block")
    )
    assert code == 2
    assert "did not record an explicit pass" in stderr


def test_an_unreadable_head_commit_is_refused(gate) -> None:
    code, stderr, _ = gate("gh pr merge 7 --rebase", GH_HEAD_SHA="")
    assert code == 2
    assert "Cannot read the head commit" in stderr


def test_an_unresolvable_pull_request_is_refused(gate) -> None:
    code, stderr, _ = gate("gh pr merge 7 --rebase", GH_FAIL_VIEW="1")
    assert code == 2
    assert "Cannot identify the pull request" in stderr


def test_a_merge_naming_a_branch_resolves_that_branch(gate) -> None:
    """The defect the goal validator caught.

    A branch-named merge was reported as naming nothing, so the gate resolved
    the *current* branch and would have checked one pull request's verdict while
    merging another.
    """
    code, stderr, calls = gate(
        "gh pr merge codex/other/branch --rebase", GH_VERDICT=verdict(HEAD)
    )
    assert code == 0, stderr
    assert "pr view codex/other/branch --json number" in calls


def test_a_merge_naming_nothing_falls_back_to_the_current_branch(gate) -> None:
    code, stderr, calls = gate("gh pr merge --rebase", GH_VERDICT=verdict(HEAD))
    assert code == 0, stderr
    assert "pr view --json number" in calls


def test_missing_tooling_refuses_everything(tmp_path: Path) -> None:
    """The stated blast radius of failing closed.

    With its tooling unavailable the hook cannot classify anything, so it clears
    nothing -- including commands that are not guarded at all. That is the right
    direction and an expensive one, so it is pinned here rather than left to be
    discovered during a session.
    """
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    result = subprocess.run(
        ["/bin/bash", str(GATE)],
        input=json.dumps({"tool_input": {"command": "uv run pytest -q"}}),
        capture_output=True,
        text=True,
        env={"PATH": str(empty)},
        check=False,
    )
    assert result.returncode == 2
    assert "Could not parse this command" in result.stderr


@pytest.mark.parametrize(
    "decision",
    [
        "Traceback (most recent call last):",
        "allow\nmerge 7",
        "merge ",
        "",
    ],
)
def test_an_unrecognized_classifier_decision_is_refused(
    tmp_path: Path, decision: str
) -> None:
    """Raised by Copilot on this pull request.

    Only three decisions were handled by name and everything else fell through
    to be read as a merge target. It failed closed by accident, because
    `gh pr view` rejects nonsense; this pins it as intent.
    """
    sandbox = tmp_path / "hooks"
    sandbox.mkdir()
    (sandbox / "pre-merge-gate.sh").write_text(GATE.read_text())
    stub = sandbox / "classify_command.py"
    stub.write_text(f"print({decision!r})\n")

    result = subprocess.run(
        ["/bin/bash", str(sandbox / "pre-merge-gate.sh")],
        input=json.dumps({"tool_input": {"command": "gh pr merge 7 --rebase"}}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    # Empty output trips the earlier unparseable guard; the rest trip the
    # contract check. Both are refusals, which is the property being pinned.
    assert "refusing to merge" in result.stderr or "Could not parse" in result.stderr


def test_merging_two_pull_requests_in_one_call_is_refused(gate) -> None:
    code, stderr, _ = gate(
        "gh pr merge 7 --rebase && gh pr merge 8 --rebase", GH_VERDICT=verdict(HEAD)
    )
    assert code == 2
    assert "more than one pull request" in stderr


def test_an_unparseable_guarded_command_is_refused(gate) -> None:
    code, stderr, _ = gate('gh pr merge 7 --body "unterminated')
    assert code == 2
    assert "Could not parse this command" in stderr
