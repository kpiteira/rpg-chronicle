"""The single reader both merge-guarding scripts use to decide what a verdict says.

`scripts/validate-goal.sh` and `scripts/hooks/pre-merge-gate.sh` decided it by grepping the
whole output for `"verdict": "pass"` until #38. This file holds the divergence measurement:
for each input, what the old grep concluded and what the reader concludes. The grep is
reproduced here rather than described, so the comparison is run rather than asserted.

The inputs are not hypothetical. The validator quotes the pull request's own text into its
findings, so a pull request that touches the merge gate, the validator, or the goal rules
puts verdict JSON inside the validator's own reply -- which is how a *blocking* verdict
comes to contain the pass substring.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "scripts/verdict_state.py"

# The exact expression both scripts carried before #38.
OLD_GREP = re.compile(r'"verdict": *"pass"')


def _load_reader():
    spec = importlib.util.spec_from_file_location("verdict_state", READER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = _load_reader()


PASSING_COMMENT = (
    "<!-- goal-validator sha:1111111111111111111111111111111111111111 -->\n"
    "```json\n"
    '{"verdict": "pass", "blocking": [], "advisory": []}\n'
    "```"
)

# Every one of these is a case where the grep says pass and the verdict does not.
#
# One case that was expected to be here is not, and saying so is worth more than quietly
# dropping it: a *well-formed* blocking verdict that quotes `"verdict": "pass"` inside a
# finding string does **not** fool the grep, because JSON escapes the inner quotes and
# `\"verdict\": \"pass\"` does not match. The exposure is narrower than "the validator
# quotes the diff back": it needs the substring to reach the comment unescaped, which is
# what the nested-object and outside-the-fence cases below do.
DIVERGENT = {
    "a blocking verdict carrying a nested prior verdict": (
        "<!-- goal-validator sha:1111111111111111111111111111111111111111 -->\n"
        "```json\n"
        '{"verdict": "block", "blocking": ["Acceptance item 2 has no reproduction."], '
        '"superseded": {"sha": "0000000", "verdict": "pass"}}\n'
        "```"
    ),
    "a prose preamble in front of the object": (
        'The pull request looks sound to me, so this is a "verdict": "pass" as far as I\n'
        "am concerned.\n"
        '{"verdict": "block", "blocking": ["Acceptance item 3 has no reproduction."]}'
    ),
    "a second object after a blocking one": (
        '{"verdict": "block", "blocking": ["No evidence for item 1."]}\n'
        '{"verdict": "pass", "blocking": []}'
    ),
    "output that is not JSON at all": (
        "I could not read the diff. If I had been able to, my verdict would probably\n"
        'have been {"verdict": "pass"}.'
    ),
}


@pytest.mark.parametrize("case", sorted(DIVERGENT))
def test_the_grep_reads_a_pass_where_the_verdict_is_not_one(case: str) -> None:
    """Half of the measurement: these are inputs the old logic cleared."""
    assert OLD_GREP.search(DIVERGENT[case]) is not None


@pytest.mark.parametrize("case", sorted(DIVERGENT))
def test_the_reader_does_not(case: str) -> None:
    """The other half. Not-a-pass covers both a block and unreadable output."""
    assert reader.verdict_state(DIVERGENT[case]) != "pass"


def test_a_real_passing_verdict_still_reads_as_a_pass() -> None:
    """The refusals above are worth nothing if the gate now refuses everything."""
    assert reader.verdict_state(PASSING_COMMENT) == "pass"


def test_a_bare_object_reads_as_a_pass_too() -> None:
    """`scripts/validate-goal.sh` reads raw model output, which carries no fence."""
    assert reader.verdict_state('{"verdict": "pass", "blocking": []}') == "pass"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n\n",
        '["pass"]',
        '"pass"',
        '{"blocking": []}',
        '{"verdict": null}',
        '{"verdict": ["pass"]}',
        '{"verdict": "pass"',
        "```json\nnot json at all\n```",
    ],
)
def test_unreadable_input_is_not_a_verdict(text: str) -> None:
    assert reader.verdict_state(text) is None


def _run(text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(READER)],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_script_prints_the_verdict_and_exits_zero() -> None:
    result = _run(PASSING_COMMENT)
    assert result.returncode == 0
    assert result.stdout.strip() == "pass"


def test_the_script_prints_nothing_and_exits_non_zero_on_unreadable_input() -> None:
    """The callers test the printed word, so silence has to be the refusal."""
    result = _run("no verdict here")
    assert result.returncode == 1
    assert result.stdout.strip() == ""
