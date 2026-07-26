#!/usr/bin/env python3
"""Classify a Bash tool call for the pre-merge gate.

Reads a PreToolUse payload on stdin and prints exactly one decision line:

    allow                    no guarded command in this call
    push-main                a `git push` whose destination ref is main
    merge <target>           a `gh pr merge`, with the pull request it names
    merge <target> <repo>    the same, with the repository it names
    merge -                  a `gh pr merge` naming no pull request
    merge-multiple           more than one `gh pr merge` in a single call
    unparseable              the command could not be resolved, and its text
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
covered: shell separators, line breaks and continued lines, command
substitution, quoting, redirections and the file descriptors written against
them, heredoc bodies (and herestrings, which are not heredocs and carry no
terminator), assignments, wrappers with or without their own options,
end-of-options markers, invocation by path, `git`'s own options between `git`
and `push`, and a shell command nested
inside another to three levels.

Where a command cannot be read, it is refused on a mention instead of parsed:
code handed to a non-shell interpreter, since
`python3 -c 'os.system("git push origin main")'` is Python and reading it as
shell finds a quoted string rather than three words; and a script an
interpreter takes from stdin or a file, as in `bash <<'EOF'` or
`echo '...' | bash`, where nothing in the command names what will run.

What remains uncovered: a guarded command written to a script file and run by
name, and one reconstructed at runtime. The gate is a guardrail against an
unvalidated merge happening by accident, not a barrier against one pursued
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

# Characters that end one command and begin another. `shlex` returns a run of
# them as a single token -- `);` and `)&&` are one token each -- so a token is a
# separator when every character in it is one of these, rather than when it
# equals a listed operator. Matching exact operators let `(… gh pr merge 7);
# gh pr merge 8` read as one command, hiding the second merge behind the first.
#
# Redirections are NOT separators, and listing `<` and `>` here once meant a
# redirection split a command mid-arguments: `git push >/dev/null origin main`
# lost `origin main` to a second segment and classified as allowed. They are
# removed in normalize_shell_text instead.
SEPARATOR_CHARACTERS = set("();|&")

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

# Interpreters whose `-c` argument is itself a shell command, and so can be
# classified in its own right. The old substring match caught
# `sh -c "git push origin main"` by accident; this catches it on purpose.
INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh"}

# Interpreters whose `-c` argument is code in another language. It cannot be
# read as shell -- `python3 -c 'os.system("git push origin main")'` yields a
# quoted string, not three words -- so such an argument is refused when it so
# much as mentions a guarded command, rather than parsed.
CODE_INTERPRETERS = {"python", "python3", "perl", "ruby", "node"}

# `-c`, and combined short flags ending in it: `bash -lc '...'`.
COMMAND_FLAG = re.compile(r"^-[A-Za-z]*c$")

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
            # A backslash before a newline continues the line; the pair is not
            # part of the command. Keeping it left a target of "\n7".
            if character != "\n":
                out.append(character)
            elif out and out[-1] == "\\":
                out.pop()
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
        elif command.startswith("<<<", index):
            # A herestring, not a heredoc: its payload is on this line and
            # there is no terminator to look for. Matching it as a heredoc
            # registered a terminator that never arrived, and every following
            # line was swallowed while searching for one.
            out.append("<<<")
            index += 3
        elif character == "<" and (heredoc := HEREDOC.match(command, index)):
            out.append(heredoc.group(0))
            pending.append(heredoc.group(2))
            index = heredoc.end()
        elif character in "<>":
            # A redirection and its target are not part of the command's
            # arguments. The file descriptor, if written, is attached to the
            # operator with no space -- which is how `2>` is told apart from a
            # `7` that happens to precede a redirection.
            while out and out[-1].isdigit():
                out.pop()
            index = skip_redirection(command, index)
        elif character == "\n":
            out.append(";")
            index += 1
            index = skip_heredoc_bodies(command, index, pending)
        else:
            out.append(character)
            index += 1

    return "".join(out)


def skip_redirection(command: str, index: int) -> int:
    """Advance past a redirection operator and whatever it redirects to."""
    length = len(command)
    while index < length and command[index] in "<>&":
        index += 1
    while index < length and command[index] in " \t":
        index += 1

    if index < length and command[index] in "'\"":
        quote = command[index]
        index += 1
        while index < length and command[index] != quote:
            index += 1
        return min(index + 1, length)

    while index < length and command[index] not in " \t\n;|&()":
        index += 1
    return index


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


def collapse(text: str) -> str:
    """Whitespace-insensitive text, so `gh  pr merge` reads as one phrase."""
    return "\n".join(" ".join(line.split()) for line in text.splitlines())


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

    `git -C /path push origin main` puts an argument between them. The distance
    is unbounded, so `git log --grep push origin main` is refused as though it
    pushed. That over-refusal is left standing: bounding the gap means deciding
    which arguments to stop reading at, and a bypass hides wherever this stops
    reading.
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
    """What a `gh pr merge` names: its pull request, and its repository.

    Returned as `<target>` or `<target> <repo>`, with `-` for a pull request the
    command does not name. The repository has to travel with the target: the
    gate resolves what the command named, and resolving `7` against the wrong
    repository is the same wrong-pull-request defect in a new place.
    """
    arguments = segment[start + 3 :]
    target = "-"
    repo = ""
    index = 0
    options_ended = False
    while index < len(arguments):
        argument = arguments[index]
        # `gh` supports `--` so that a branch beginning with a dash can be
        # named. Reading it as an option would leave the gate resolving the
        # current branch instead, which is the hazard this goal is about.
        if argument == "--" and not options_ended:
            options_ended = True
            index += 1
            continue
        if argument.startswith("-") and not options_ended:
            # `-R owner/repo`, `--repo=owner/repo` and `-Rowner/repo` all name
            # one. Missing the attached forms drops the repository, and the
            # gate then resolves the number against whichever repository the
            # session stands in.
            if argument in ("-R", "--repo") and index + 1 < len(arguments):
                repo = arguments[index + 1]
            elif argument.startswith("--repo="):
                repo = argument[len("--repo=") :]
            elif argument.startswith("-R") and len(argument) > 2:
                repo = argument[2:]
            index += 2 if argument in VALUE_FLAGS else 1
            continue
        if target == "-":
            target = argument
        index += 1
    return f"{target} {repo}" if repo else target


def command_argument(segment: list[str], start: int) -> int | None:
    """Index of the argument following an interpreter's `-c`, if present."""
    for index in range(start + 1, len(segment)):
        if COMMAND_FLAG.match(segment[index]) and index + 1 < len(segment):
            return index + 1
    return None


def reads_a_script_it_was_given(segment: list[str]) -> bool:
    """True when an interpreter takes its script from somewhere unreadable.

    A shell with no `-c` reads from stdin or from a file: `bash <<'EOF'`, or
    `echo '...' | bash`. There is no argument to classify in either case -- the
    heredoc body has already been dropped as data, and the piped string belongs
    to a different command -- so the text is scanned for a mention instead.
    """
    words = [base_name(word) for word in segment]
    return any(
        word in INTERPRETERS | CODE_INTERPRETERS
        and command_argument(segment, index) is None
        for index, word in enumerate(words)
    )


def interpreted_scripts(segment: list[str]) -> tuple[list[str], list[str]]:
    """Arguments this command will itself run.

    Returns shell text to classify in its own right, and foreign code that can
    only be scanned for a mention. Both arrive as a single token once quoting is
    resolved, so neither can be seen by scanning words.
    """
    words = [base_name(word) for word in segment]
    shell: list[str] = []
    foreign: list[str] = []
    for index, word in enumerate(words):
        if word in INTERPRETERS and (at := command_argument(segment, index)):
            shell.append(segment[at])
        elif word in CODE_INTERPRETERS and (at := command_argument(segment, index)):
            foreign.append(segment[at])
        elif word == "eval" and (at := first_operand(segment, index)):
            shell.append(segment[at])
    return shell, foreign


def first_operand(segment: list[str], start: int) -> int | None:
    """Index of the first token after `start` that is not an option.

    `eval -- "gh pr merge 7"` puts an end-of-options marker in the way.
    """
    for index in range(start + 1, len(segment)):
        if segment[index] == "--":
            return index + 1 if index + 1 < len(segment) else None
        if not segment[index].startswith("-"):
            return index
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
        # remove rather than relocate. Whitespace is collapsed first, so a tab
        # or a double space between the words does not slip the check.
        readable = collapse(
            "\n".join(
                line for line in body.splitlines() if not line.lstrip().startswith("#")
            )
        )
        return "unparseable" if any(h in readable for h in GUARDED_HINTS) else "allow"

    # An interpreter fed from stdin or a file hides whatever it will run. The
    # raw text is searched rather than the normalized text, since the script may
    # be in a heredoc body that normalization dropped, or in another command's
    # quoted argument. Refusing on a mention is what the substring match did.
    if any(reads_a_script_it_was_given(segment) for segment in parsed) and any(
        hint in collapse(command) for hint in GUARDED_HINTS
    ):
        return "unparseable"

    merges: list[str] = []
    for segment in parsed:
        if any(pushes_to_main(segment[push:]) for push in find_pushes(segment)):
            return "push-main"

        merges.extend(merge_target(segment, merge) for merge in find_merges(segment))

        shell, foreign = interpreted_scripts(segment)
        if any(hint in code for code in foreign for hint in GUARDED_HINTS):
            return "unparseable"

        if depth >= 3:
            continue
        for script in shell:
            nested = classify(script, depth + 1)
            if nested in ("push-main", "merge-multiple", "unparseable"):
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
