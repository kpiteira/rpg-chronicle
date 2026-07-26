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
        (
            "gh pr merge https://github.com/o/r/pull/12 --squash",
            "merge https://github.com/o/r/pull/12",
        ),
        ("gh pr merge --rebase", "merge -"),
        # A branch is passed through, not reported as absent: `gh pr view`
        # accepts it, and calling it absent made the gate resolve the current
        # branch and check the wrong pull request's verdict.
        ("gh pr merge codex/tpm/scratch --rebase", "merge codex/tpm/scratch"),
    ],
)
def test_merge_targets_are_extracted(command: str, expected: str) -> None:
    assert classify(command) == expected


def test_a_flag_value_is_not_read_as_a_pr_number() -> None:
    assert classify("gh pr merge --subject 7 --rebase") == "merge -"


def test_an_end_of_options_marker_reveals_the_target() -> None:
    """Raised by Copilot.

    `gh` accepts `--` so a branch beginning with a dash can be named. Reading
    it as an option left the gate resolving the current branch instead.
    """
    assert classify("gh pr merge --rebase -- -odd-branch") == "merge -odd-branch"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # Assignments and flagless wrappers.
        ("GIT_TRACE=1 git push origin main", "push-main"),
        ("env GIT_TRACE=1 git push origin main", "push-main"),
        ("sudo git push origin HEAD:main", "push-main"),
        ("command gh pr merge 7 --rebase", "merge 7"),
        ("nohup gh pr merge 7 --rebase", "merge 7"),
        # Wrappers carrying their own options, which anchoring on the first
        # word missed. Every one of these was refused by the substring match.
        ("nice -n 5 gh pr merge 7 --rebase", "merge 7"),
        ("sudo -u karl git push origin main", "push-main"),
        ("env -i git push origin main", "push-main"),
        ("command -p gh pr merge 7 --rebase", "merge 7"),
        ("time -p gh pr merge 7 --rebase", "merge 7"),
        ("timeout 60 git push origin main", "push-main"),
        ("xargs gh pr merge 7 --rebase", "merge 7"),
        # A command collapsed into a single token by quoting.
        ('eval "gh pr merge 7 --rebase"', "merge 7"),
        ('eval "git push origin main"', "push-main"),
        # git's own options sit between the two words.
        ("git -C /tmp/repo push origin main", "push-main"),
    ],
)
def test_wrappers_and_assignments_do_not_hide_a_command(
    command: str, expected: str
) -> None:
    """Fail-closed regressions the goal validator caught, in two rounds.

    The substring match this classifier replaced refused every one of these.
    The first attempt anchored on the command's first word and enumerated the
    wrappers to skip, which silently dropped each wrapper not on the list; the
    words are now located anywhere in the command, so no list is needed.
    """
    assert classify(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("sh -c 'git push origin main'", "push-main"),
        ('bash -c "git push origin HEAD:main"', "push-main"),
        ("sh -c 'gh pr merge 7 --rebase'", "merge 7"),
        ("sh -c 'uv run pytest -q'", "allow"),
    ],
)
def test_an_interpreted_script_is_classified_too(command: str, expected: str) -> None:
    """Keeping a refusal the substring match made by accident.

    The goal constrains this change so that every refusal that fired before
    still fires; `sh -c` on a guarded command was one of them.
    """
    assert classify(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("/usr/bin/git push origin main", "push-main"),
        ("./git push origin HEAD:main", "push-main"),
        ("/usr/local/bin/gh pr merge 7 --rebase", "merge 7"),
        ("/usr/bin/env /usr/bin/git push origin main", "push-main"),
    ],
)
def test_a_command_invoked_by_path_is_still_recognized(
    command: str, expected: str
) -> None:
    """Raised by Copilot: matching on the bare word missed pathed invocations."""
    assert classify(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge -R owner/repo 7 --rebase",
        "gh pr merge --repo owner/repo 7 --rebase",
        "gh pr merge 7 -R owner/repo --rebase",
    ],
)
def test_a_repo_flag_travels_with_the_merge_target(command: str) -> None:
    """Copilot's, then the goal validator's.

    `-R owner/repo` was first misread as the pull request itself, and then
    parsed but dropped -- so the gate resolved `7` against whichever repository
    it happened to be standing in. That is the wrong-pull-request defect again.
    """
    assert classify(command) == "merge 7 owner/repo"


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 7 --rebase && gh pr merge 8 --rebase",
        "gh pr merge 7 --rebase\ngh pr merge 8 --rebase",
        "sh -c 'gh pr merge 7 --rebase; gh pr merge 8 --rebase'",
    ],
)
def test_merging_twice_in_one_call_is_refused(command: str) -> None:
    """Defect 1's hazard in compound form, raised by the goal validator.

    One verdict is checked per call, so classifying only the first merge would
    clear the second on the first one's evidence.
    """
    assert classify(command) == "merge-multiple"


@pytest.mark.parametrize(
    "command",
    [
        "(cd /tmp && gh pr merge 7 --rebase); gh pr merge 8 --rebase",
        "(gh pr merge 7 --rebase)&&(gh pr merge 8 --rebase)",
        "{ gh pr merge 7 --rebase; }; gh pr merge 8 --rebase",
    ],
)
def test_a_subshell_does_not_hide_a_second_merge(command: str) -> None:
    """A confirmed bypass, caught by the goal validator.

    `shlex` returns a run of punctuation as one token, so `);` matched no
    listed operator, the segment never split, and the second merge was cleared
    on the first pull request's verdict.
    """
    assert classify(command) == "merge-multiple"


@pytest.mark.parametrize(
    "command",
    [
        "git push origin +main",
        "git push origin +refs/heads/main",
        "git push --all origin",
        "git push --mirror origin",
    ],
)
def test_refspec_forms_that_reach_main_are_refused(command: str) -> None:
    """Holes the previous regex had too, named by the goal validator."""
    assert classify(command) == "push-main"


def test_nesting_beyond_one_level_is_classified() -> None:
    """The docstring claims three levels; this exercises more than one."""
    assert classify("""sh -c 'sh -c "gh pr merge 7 --rebase"'""") == "merge 7"


def test_an_author_email_is_not_read_as_the_merge_target() -> None:
    assert classify("gh pr merge --author-email a@b.c --rebase") == "merge -"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("bash -lc 'gh pr merge 7 --rebase'", "merge 7"),
        ("sh -ec 'git push origin main'", "push-main"),
        ("""python3 -c 'import os; os.system("git push origin main")'""", "unparseable"),
        ("""python -c 'os.system("gh pr merge 7")'""", "unparseable"),
        ("python3 -c 'print(1)'", "allow"),
        ("""eval -- "gh pr merge 7 --rebase" """, "merge 7"),
    ],
)
def test_interpreter_arguments_are_not_a_way_through(
    command: str, expected: str
) -> None:
    """Raised by the goal validator.

    A combined short flag hid a shell command, and code in another language
    cannot be read as shell at all -- so foreign code that mentions a guarded
    command is refused rather than parsed, which is what the substring match
    did and what the goal requires be kept.
    """
    assert classify(command) == expected


def test_a_heredoc_marker_inside_quotes_does_not_swallow_later_lines() -> None:
    """Also from the validator: heredoc detection must respect quoting.

    Stripping heredocs from raw text let a quoted `<<WORD` consume the rest of
    the script, hiding any guarded command below it.
    """
    command = 'echo "a <<WORD b"\ngh pr merge 7 --rebase'
    assert classify(command) == "merge 7"


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


@pytest.mark.parametrize(
    "command",
    [
        "read x <<<hello\ngit push origin main",
        'read x <<<"bar"\ngit push origin main',
        "read x <<<abc\ngit push origin main",
        "read x <<<$VALUE\ngit push origin main",
    ],
)
def test_a_herestring_does_not_swallow_the_lines_after_it(command: str) -> None:
    """A reproducible fail-open, caught by the goal validator.

    The heredoc pattern matched at the second `<` of `<<<`, taking the payload
    for a terminator that never arrived, so everything below it was consumed
    while searching for one.
    """
    assert classify(command) == "push-main"


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


def test_a_guarded_phrase_in_a_comment_does_not_block_an_unparseable_call() -> None:
    """Raised by Copilot.

    A comment's stray apostrophe defeats the tokenizer, and the guarded phrase
    beside it then refused the whole call -- relocating the annoyance this
    module exists to remove rather than fixing it.
    """
    assert classify("# don't run \"gh pr merge\" yet\nuv run pytest -q") == "allow"


def test_an_unparseable_call_with_a_real_guarded_command_still_fails_closed() -> None:
    assert classify("# don't\ngh pr merge 7 --body \"unterminated") == "unparseable"


@pytest.mark.parametrize(
    "command",
    [
        'gh  pr   merge 7 --body "unterminated',
        'git\tpush origin main --body "unterminated',
    ],
)
def test_odd_spacing_does_not_slip_the_unparseable_check(command: str) -> None:
    """Raised by Copilot: the fallback matched exact substrings only."""
    assert classify(command) == "unparseable"


def test_an_unreadable_payload_fails_closed() -> None:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="not json",
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "unparseable"
