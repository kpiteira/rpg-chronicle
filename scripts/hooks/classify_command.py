#!/usr/bin/env python3
"""Classify a Bash tool call for the pre-merge gate.

Reads a PreToolUse payload on stdin and prints exactly one decision line:

    allow             no guarded command in this call
    push-main         a `git push` whose destination ref is main
    merge <target>    a `gh pr merge`, with the pull request it names
    merge -           a `gh pr merge` naming no pull request
    merge-multiple    more than one `gh pr merge` in a single call
    unparseable       the command could not be tokenized and its raw text
                      mentions a guarded command

`<target>` is passed through exactly as written -- a number, a pull URL, or a
branch name -- because `gh pr view` accepts all three. The gate resolves it.
Reporting a branch as "no target" is what let an earlier version of this hook
check the current branch's verdict while merging a different pull request.

Shell metacharacters are resolved with `shlex`, so a guarded command that
appears inside a quoted string is inert text and classifies as `allow`. That
distinction is the point of this module: a substring match blocks an issue
comment that merely mentions `gh pr merge`, which is exactly what happened when
the goal loop was first exercised.

Parse failures are reported rather than swallowed. The gate treats an
unresolved command as a block, so a tokenizer that cannot make sense of the
input fails closed instead of waving it through.

An interpreter's `-c` argument is classified in turn, since the substring match
this replaces caught `sh -c "git push origin main"` and losing that would be a
narrowing rather than a fix. Commands are compared by base name, so a pathed or
wrapped invocation reaches the same guards.

Known limit, stated precisely because the goal behind this module asked for
every prior refusal to survive. A substring match refused *any* occurrence of
the guarded text, including occurrences it had no business refusing -- that
overreach is the defect being fixed, so the two cannot both hold. What is
covered: shell separators, line breaks, command substitution, quoting, heredoc
bodies, leading assignments, the wrappers in COMMAND_WRAPPERS, the interpreters
in INTERPRETERS, and invocation by path. What is not: indirection this module
does not model -- a script file, a heredoc piped to a shell, `python3 -c`,
`xargs`, a `timeout`-style wrapper that takes its own arguments. The gate is a
guardrail against an unvalidated merge happening by accident, not a barrier
against one pursued deliberately, which no PreToolUse hook could be.
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
SEPARATORS = {";", "&", "&&", "|", "||", "(", ")"}

# Leading characters that introduce a command without being part of its name,
# so `$(gh pr merge 7)` and a backticked variant still resolve to `gh`.
COMMAND_PREFIX = "`$("

# Words that precede the real command without changing it. Without these,
# `env FOO=1 git push origin main` reads as a command named `env`.
COMMAND_WRAPPERS = {
    "builtin",
    "command",
    "env",
    "eval",
    "exec",
    "nice",
    "nohup",
    "sudo",
    "time",
}

# Flags that consume the following token, so a value is never mistaken for a
# positional pull request argument.
VALUE_FLAGS = {
    "-b",
    "--body",
    "-t",
    "--subject",
    "--body-file",
    "-F",
    "--field",
    "--match-head-commit",
    "--author-email",
    "-R",
    "--repo",
}

# Interpreters whose `-c` argument is itself a command. The old substring match
# caught `sh -c "git push origin main"` by accident; this catches it on purpose.
INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh"}

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def normalize_shell_text(command: str) -> str:
    """Resolve line structure while respecting quotes.

    Two jobs, done in one pass because both need to know whether the cursor is
    inside a quoted string:

    * heredoc bodies are dropped, since text fed to a program's stdin is data;
    * a line break between commands becomes a separator, because `shlex` emits
      no token for a newline under any setting, so without this a merge on the
      third line of a script joins the segment begun on the first.

    Doing the heredoc pass on raw text instead would let `echo "a <<WORD b"`
    swallow every following line.
    """
    out: list[str] = []
    pending: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    length = len(command)

    while index < length:
        character = command[index]

        if escaped:
            out.append(character)
            escaped = False
            index += 1
        elif character == "\\" and quote != "'":
            out.append(character)
            escaped = True
            index += 1
        elif quote:
            out.append(character)
            if character == quote:
                quote = None
            index += 1
        elif character in "'\"":
            out.append(character)
            quote = character
            index += 1
        elif character == "<" and (heredoc := HEREDOC.match(command, index)):
            out.append(heredoc.group(0))
            pending.append(heredoc.group(2))
            index = heredoc.end()
        elif character == "\n":
            out.append(";")
            index += 1
            index = skip_heredoc_bodies(command, index, pending)
        else:
            out.append(character)
            index += 1

    return "".join(out)


def skip_heredoc_bodies(command: str, index: int, pending: list[str]) -> int:
    """Advance past the bodies of heredocs opened on the line just ended."""
    while pending:
        terminator = pending.pop(0)
        while index < len(command):
            break_at = command.find("\n", index)
            line = command[index:] if break_at == -1 else command[index:break_at]
            index = len(command) if break_at == -1 else break_at + 1
            if line.strip() == terminator:
                break
    return index


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
    return [stripped for segment in found if (stripped := normalize(segment))]


def normalize(segment: list[str]) -> list[str]:
    """Reduce a command to the words that name it.

    A command is compared by its base name, so an absolute or relative path
    reaches the same guards: `/usr/bin/git push origin main` names `git`.
    """
    head = segment[0].lstrip(COMMAND_PREFIX)
    rest = [head, *segment[1:]] if head else segment[1:]

    index = 0
    while index < len(rest) and (
        ASSIGNMENT.match(rest[index]) or base_name(rest[index]) in COMMAND_WRAPPERS
    ):
        index += 1

    if index >= len(rest):
        return []
    return [base_name(rest[index]), *rest[index + 1 :]]


def base_name(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def pushes_to_main(segment: list[str]) -> bool:
    """True when any argument of a `git push` resolves to main.

    Permission prefix rules cannot see refspecs -- `git push origin HEAD:main`
    satisfies an allow rule for `git push origin` -- so the destination is
    matched here instead.

    Every positional is checked, including the one naming the remote, so a
    remote literally named `main` would be refused as though it were the branch.
    That is a deliberate over-refusal: distinguishing the two means treating the
    first positional as a remote, and a bypass hides behind any argument this
    function decides not to inspect.
    """
    for argument in segment[2:]:
        if argument.startswith("-"):
            continue
        destination = argument.rsplit(":", 1)[-1]
        if destination.removeprefix("refs/heads/") == "main":
            return True
    return False


def merge_target(segment: list[str]) -> str:
    """The pull request a `gh pr merge` names, or `-` when it names none."""
    arguments = segment[3:]
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("-"):
            index += 2 if argument in VALUE_FLAGS else 1
            continue
        return argument
    return "-"


def interpreted_script(segment: list[str]) -> str | None:
    """The script an interpreter was asked to run, if any."""
    if segment and segment[0] in INTERPRETERS and "-c" in segment:
        index = segment.index("-c") + 1
        if index < len(segment):
            return segment[index]
    return None


def classify(command: str, depth: int = 0) -> str:
    if not command.strip():
        return "allow"

    body = normalize_shell_text(command)

    try:
        parsed = segments(tokenize(body))
    except ValueError:
        # Quoting could not be resolved, so fall back to raw text -- minus
        # whole-line comments, which are never commands. Without that, a stray
        # apostrophe in a comment that merely mentions a guarded command
        # refuses the whole call, which is the annoyance this module exists to
        # remove rather than relocate.
        readable = "\n".join(
            line for line in body.splitlines() if not line.lstrip().startswith("#")
        )
        return "unparseable" if any(h in readable for h in GUARDED_HINTS) else "allow"

    merges: list[str] = []
    for segment in parsed:
        if segment[:2] == ["git", "push"] and pushes_to_main(segment):
            return "push-main"
        if segment[:3] == ["gh", "pr", "merge"]:
            merges.append(merge_target(segment))
        if depth < 3 and (script := interpreted_script(segment)):
            nested = classify(script, depth + 1)
            if nested in ("push-main", "merge-multiple"):
                return nested
            if nested.startswith("merge "):
                merges.append(nested[len("merge ") :])

    if not merges:
        return "allow"
    if len(merges) > 1:
        # One verdict is checked per call, so a call that merges twice would
        # clear the second on the first one's evidence.
        return "merge-multiple"
    return f"merge {merges[0]}"


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
