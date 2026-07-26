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

The guarded words are located anywhere in a command rather than at its head,
which is what makes wrappers a non-issue: `nice -n 5`, `sudo -u karl`,
`timeout 60`, `xargs` and anything else need no enumeration, because none of
them can hide words the lexer has already separated. Commands are compared by
base name, so invocation by path reaches the same guards. What a wrapper *can*
hide is a command collapsed into one token, so an interpreter's `-c` argument
and `eval`'s argument are classified in their own right.

Known limit, stated precisely because the goal behind this module asked that
every prior refusal survive. A substring match refused *any* occurrence of the
guarded text, including occurrences it had no business refusing -- that
overreach is the defect being fixed, so the two cannot hold in full. What is
covered: shell separators, line breaks, command substitution, quoting, heredoc
bodies, assignments, wrappers with or without their own options, invocation by
path, `git`'s own options between `git` and `push`, and a shell command nested
inside another to three levels. What is not: a guarded command written to a
script file and run; one reconstructed at runtime; and one carried inside a
*non-shell* interpreter, since `python3 -c 'os.system("git push origin main")'`
is Python, not shell, and reading it as shell finds a quoted string rather than
three words. The gate is a guardrail against an unvalidated merge happening by
accident, not a barrier against one pursued deliberately, which no PreToolUse
hook could be.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# Raw-text markers used only to decide whether an untokenizable command is
# worth blocking. They are deliberately loose; precision comes from the lexer.
GUARDED_HINTS = ("gh pr merge", "git push")

# Characters that end one command and begin another. `shlex` returns a run of
# them as a single token -- `);` and `)&&` are one token each -- so a token is a
# separator when every character in it is one of these, rather than when it
# equals a listed operator. Matching exact operators let `(… gh pr merge 7);
# gh pr merge 8` read as one command, hiding the second merge behind the first.
SEPARATOR_CHARACTERS = set("();<>|&")

# Leading characters that introduce a command without being part of its name,
# so `$(gh pr merge 7)` and a backticked variant still resolve to `gh`.
COMMAND_PREFIX = "`$("

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

HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# Characters after which a `#` begins a comment rather than continuing a word.
WORD_BREAK = " \t\n;&|("


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
        elif character == "#" and (not out or out[-1] in WORD_BREAK):
            # A comment reaches the end of its line. The words in it are not
            # commands, and since guarded words are matched wherever they
            # appear, leaving them in would refuse a call for describing one.
            break_at = command.find("\n", index)
            index = len(command) if break_at == -1 else break_at
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
        if token and set(token) <= SEPARATOR_CHARACTERS:
            if current:
                found.append(current)
            current = []
        else:
            current.append(token)
    if current:
        found.append(current)
    return [stripped for segment in found if (stripped := normalize(segment))]


def normalize(segment: list[str]) -> list[str]:
    """Strip the punctuation that introduces a command without naming it."""
    head = segment[0].lstrip(COMMAND_PREFIX)
    return [head, *segment[1:]] if head else segment[1:]


def base_name(word: str) -> str:
    """`/usr/bin/git` and `git` are the same command."""
    return word.rsplit("/", 1)[-1]


def find_merges(segment: list[str]) -> list[int]:
    """Every `gh pr merge` in a command, at any position.

    Anchoring on the first word required every wrapper to be enumerated, and
    each one that was not -- `nice -n 5`, `sudo -u karl`, `timeout 60`, `xargs`
    -- silently dropped a refusal. Scanning for the words themselves needs no
    such list. Quoting is already resolved, so a mention inside a string is a
    single token and cannot match three adjacent words.

    All of them are reported, not the first: a segment that somehow holds two
    merges must not have the second cleared by the first one's verdict.
    """
    words = [base_name(word) for word in segment]
    return [
        index
        for index in range(max(len(words) - 2, 0))
        if words[index : index + 3] == ["gh", "pr", "merge"]
    ]


def find_pushes(segment: list[str]) -> list[int]:
    """Every `git push`, allowing git's own options between the two words.

    `git -C /path push origin main` puts an argument between them.
    """
    words = [base_name(word) for word in segment]
    found = []
    for start, word in enumerate(words):
        if word != "git":
            continue
        found.extend(
            index for index in range(start + 1, len(words)) if words[index] == "push"
        )
    return found


def pushes_to_main(segment: list[str]) -> bool:
    """True when any argument of a `git push` resolves to main.

    Permission prefix rules cannot see refspecs -- `git push origin HEAD:main`
    satisfies an allow rule for `git push origin` -- so the destination is
    matched here instead.

    Every positional after `push` is checked, including the one naming the
    remote, so a remote literally named `main` would be refused as though it
    were the branch. That is a deliberate over-refusal: distinguishing the two
    means treating the first positional as a remote, and a bypass hides behind
    any argument this function decides not to inspect.
    """
    for argument in segment:
        # `--all` and `--mirror` push every branch, main among them.
        if argument in ("--all", "--mirror"):
            return True
        if argument.startswith("-"):
            continue
        destination = argument.rsplit(":", 1)[-1].removeprefix("+")
        if destination.removeprefix("refs/heads/") == "main":
            return True
    return False


def merge_target(segment: list[str], start: int) -> str:
    """The pull request a `gh pr merge` names, or `-` when it names none."""
    arguments = segment[start + 3 :]
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("-"):
            index += 2 if argument in VALUE_FLAGS else 1
            continue
        return argument
    return "-"


def interpreted_scripts(segment: list[str]) -> list[str]:
    """Arguments this command will itself run as a command.

    An interpreter's `-c` argument, and whatever `eval` was handed. Both arrive
    as a single token once quoting is resolved, so they cannot be seen by
    scanning words and have to be classified in their own right.
    """
    words = [base_name(word) for word in segment]
    scripts = []
    for index, word in enumerate(words):
        if word in INTERPRETERS and "-c" in words[index:]:
            target = words[index:].index("-c") + index + 1
            if target < len(segment):
                scripts.append(segment[target])
        elif word == "eval" and index + 1 < len(segment):
            scripts.append(segment[index + 1])
    return scripts


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
        if any(pushes_to_main(segment[push:]) for push in find_pushes(segment)):
            return "push-main"

        merges.extend(merge_target(segment, merge) for merge in find_merges(segment))

        if depth >= 3:
            continue
        for script in interpreted_scripts(segment):
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
