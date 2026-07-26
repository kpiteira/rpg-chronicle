"""The pre-merge gate's command classifier.

These tests exercise the classifier through its real interface -- a PreToolUse
payload on stdin -- because that is the contract the hook depends on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CLASSIFIER = Path(__file__).resolve().parents[1] / "scripts/hooks/classify_command.py"


def classify(command: str) -> str:
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git push origin HEAD:main",
        "git push origin refs/heads/main",
        "git push -u origin main",
        "git status && git push origin main",
    ],
)
def test_pushes_to_main_are_refused(command: str) -> None:
    assert classify(command) == "push-main"


@pytest.mark.parametrize(
    "command",
    [
        "git push origin codex/tpm/scratch",
        "git push origin HEAD:codex/tpm/scratch",
        "git push origin maintenance",
        "git log --oneline -5",
        "uv run pytest -q",
    ],
)
def test_ordinary_commands_are_allowed(command: str) -> None:
    assert classify(command) == "allow"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("gh pr merge 7 --rebase --delete-branch", "merge 7"),
        ("gh pr merge --rebase 7", "merge 7"),
        ("gh pr merge https://github.com/o/r/pull/12 --squash", "merge 12"),
        ("gh pr merge --rebase", "merge -"),
        ("gh pr merge codex/tpm/scratch --rebase", "merge -"),
    ],
)
def test_merge_targets_are_extracted(command: str, expected: str) -> None:
    assert classify(command) == expected


def test_a_flag_value_is_not_read_as_a_pr_number() -> None:
    assert classify("gh pr merge --subject 7 --rebase") == "merge -"


@pytest.mark.parametrize(
    "command",
    [
        'gh issue comment 4 --body "the gate blocks gh pr merge without a verdict"',
        "gh issue comment 4 --body 'run gh pr merge only after validation'",
        'gh pr comment 7 --body "do not git push origin main"',
        'printf "%s" "gh pr merge 7"',
    ],
)
def test_guarded_commands_quoted_as_data_are_inert(command: str) -> None:
    """The defect that motivated this classifier.

    A substring match blocked an issue comment that merely described the merge
    command. Quoted text is data, not a command.
    """
    assert classify(command) == "allow"


@pytest.mark.parametrize(
    "command",
    [
        "$(gh pr merge 7 --rebase)",
        "echo start; gh pr merge 7 --rebase",
        "gh pr view 7 && gh pr merge 7 --rebase",
    ],
)
def test_merges_reached_through_shell_constructs_are_caught(command: str) -> None:
    assert classify(command) == "merge 7"


def test_a_heredoc_body_is_data_not_commands() -> None:
    """The defect that blocked this change's own commit.

    The message describes the merge command and contains an apostrophe, so the
    body is simultaneously untokenizable and guarded-looking.
    """
    command = (
        "git commit -q -F - <<'MSG'\n"
        "Match guarded commands by token rather than substring\n"
        "\n"
        "It would have checked a different PR's verdict, and `gh pr merge 7`\n"
        "was refused from an unrelated branch.\n"
        "MSG"
    )
    assert classify(command) == "allow"


def test_a_command_after_a_heredoc_is_still_classified() -> None:
    command = "git commit -F - <<'MSG'\nmessage body\nMSG\ngh pr merge 7 --rebase"
    assert classify(command) == "merge 7"


def test_a_merge_on_a_later_line_of_a_script_is_caught() -> None:
    command = "set -e\nuv run pytest -q\ngh pr merge 7 --rebase --delete-branch"
    assert classify(command) == "merge 7"


def test_a_push_to_main_on_a_later_line_of_a_script_is_caught() -> None:
    command = "git fetch origin\ngit push origin HEAD:main"
    assert classify(command) == "push-main"


def test_a_comment_mentioning_a_guarded_command_is_inert() -> None:
    command = "# remember: gh pr merge needs a verdict first\nuv run pytest -q"
    assert classify(command) == "allow"


def test_a_comment_does_not_swallow_the_command_that_follows_it() -> None:
    command = "# merge it\ngh pr merge 7 --rebase"
    assert classify(command) == "merge 7"


def test_a_newline_inside_a_quoted_body_is_not_a_separator() -> None:
    command = 'gh issue comment 4 --body "first line\ngh pr merge 7 is only described"'
    assert classify(command) == "allow"


def test_unbalanced_quotes_around_a_guarded_command_fail_closed() -> None:
    assert classify("gh pr merge 7 --body \"unterminated") == "unparseable"


def test_unbalanced_quotes_elsewhere_do_not_block_the_session() -> None:
    assert classify("echo \"unterminated") == "allow"


def test_an_unreadable_payload_fails_closed() -> None:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="not json",
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "unparseable"
