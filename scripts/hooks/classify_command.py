#!/usr/bin/env python3
"""Classify a Bash tool call for the pre-merge gate.

Reads a PreToolUse payload on stdin and prints exactly one decision line:

    allow           no guarded command in this call
    push-main       a `git push` whose destination ref is main
    merge <pr>      a `gh pr merge`, with its explicit PR argument
    merge -         a `gh pr merge` with no explicit PR argument
    unparseable     the command could not be tokenized and its raw text
                    mentions a guarded command

Shell metacharacters are resolved with `shlex`, so a guarded command that
appears inside a quoted string is inert text and classifies as `allow`. That
distinction is the point of this module: a substring match blocks an issue
comment that merely mentions `gh pr merge`, which is exactly what happened when
the goal loop was first exercised.

Heredoc bodies are stripped before tokenizing, for the same reason: text fed
to a program's stdin is data. A commit message that describes `gh pr merge`,
and contains an apostrophe, is otherwise both untokenizable and guarded-looking.

Parse failures are reported rather than swallowed. The gate treats an
unresolved command as a block, so a tokenizer that cannot make sense of the
input fails closed instead of waving it through.

Known limit: this classifies commands, it does not sandbox them. A guarded
command reached through an interpreter -- `bash <<EOF`, `sh -c`, a script --
is not detected, exactly as it was not before. The gate is a guardrail against
an unvalidated merge happening by accident, not a barrier against one pursued
deliberately, which no PreToolUse hook could be.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# Raw-text markers used only to decide whether an untokenizable command is
# worth blocking. They are deliberately loose; precision comes from the lexer.
GUARDED_HINTS = ("gh pr merge", "git push")

# Tokens that end one command and begin another.
SEPARATORS = {";", "&", "&&", "|", "||", "(", ")", "\n"}

# Leading characters that introduce a command without being part of its name,
# so `$(gh pr merge 7)` and a backticked variant still resolve to `gh`.
COMMAND_PREFIX = "`$("

# Flags that consume the following token, so a value is never mistaken for a
# positional PR argument.
VALUE_FLAGS = {
    "-b",
    "--body",
    "-t",
    "--subject",
    "--body-file",
    "-F",
    "--field",
    "--match-head-commit",
}

PULL_URL = re.compile(r"/pull/(\d+)")

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies, keeping the line that introduces them.

    The redirection itself stays visible to the lexer; only the text being fed
    to the command is removed.
    """
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for match in HEREDOC.finditer(line):
            terminator = match.group(2)
            while index < len(lines) and lines[index].strip() != terminator:
                index += 1
            index += 1  # the terminator line itself
    return "\n".join(kept)


def newlines_to_separators(command: str) -> str:
    """Turn line breaks between commands into separators.

    `shlex` emits no token for a newline under any setting, so without this a
    merge on the third line of a script joins the segment begun on the first
    and is never recognized. Line breaks inside quotes are left alone.
    """
    out: list[str] = []
    quote: str | None = None
    escaped = False
    for character in command:
        if escaped:
            out.append(character)
            escaped = False
        elif character == "\\" and quote != "'":
            out.append(character)
            escaped = True
        elif quote:
            out.append(character)
            if character == quote:
                quote = None
        elif character in "'\"":
            out.append(character)
            quote = character
        else:
            out.append(";" if character == "\n" else character)
    return "".join(out)


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    # Comments are not stripped: a `#` line that survives to here is tokenized
    # as ordinary words, and its first token is the `#`, so it never looks like
    # a command. Leaving comment handling on would instead swallow everything
    # after a `#` once newlines have become separators.
    lexer.commenters = ""
    return list(lexer)


def segments(tokens: list[str]) -> list[list[str]]:
    """Split a token stream into individual commands."""
    found: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SEPARATORS:
            if current:
                found.append(current)
            current = []
        else:
            current.append(token)
    if current:
        found.append(current)
    return [normalize(segment) for segment in found if segment]


def normalize(segment: list[str]) -> list[str]:
    head = segment[0].lstrip(COMMAND_PREFIX)
    if not head:
        return segment[1:]
    return [head, *segment[1:]]


def pushes_to_main(segment: list[str]) -> bool:
    """True when any refspec in a `git push` resolves to main.

    Permission prefix rules cannot see refspecs -- `git push origin HEAD:main`
    satisfies an allow rule for `git push origin` -- so the destination is
    matched here instead.
    """
    for argument in segment[2:]:
        if argument.startswith("-"):
            continue
        destination = argument.rsplit(":", 1)[-1]
        if destination.removeprefix("refs/heads/") == "main":
            return True
    return False


def merge_target(segment: list[str]) -> str:
    """The PR argument of a `gh pr merge`, or `-` when it names none.

    `gh pr merge` also accepts a branch name. Resolving a branch to its PR is
    the gate's job, not the lexer's, so anything that is not a number or a pull
    URL is reported as absent.
    """
    arguments = segment[3:]
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("-"):
            index += 2 if argument in VALUE_FLAGS else 1
            continue
        if argument.isdigit():
            return argument
        url = PULL_URL.search(argument)
        return url.group(1) if url else "-"
    return "-"


def classify(command: str) -> str:
    if not command.strip():
        return "allow"

    body = newlines_to_separators(strip_heredocs(command))

    try:
        parsed = segments(tokenize(body))
    except ValueError:
        return "unparseable" if any(h in body for h in GUARDED_HINTS) else "allow"

    merge = None
    for segment in parsed:
        if segment[:2] == ["git", "push"] and pushes_to_main(segment):
            return "push-main"
        if segment[:3] == ["gh", "pr", "merge"] and merge is None:
            merge = merge_target(segment)

    return f"merge {merge}" if merge is not None else "allow"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, AttributeError):
        # A payload this hook cannot read is not a payload it can clear.
        print("unparseable")
        return 0

    print(classify(command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
