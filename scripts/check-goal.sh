#!/usr/bin/env bash
# Check a goal issue against docs/GOAL_RULES.md before it is activated.
#
# Usage: scripts/check-goal.sh <issue-number> [--rules <path>] [--no-comment] [--bare]
#
#   --rules <path>   measure against an alternate rule file (default docs/GOAL_RULES.md).
#                    Used by scripts/replay-goal-check.sh to show that a verdict comes
#                    from the rule rather than from the checker's disposition.
#   --no-comment     print the verdict without posting it to the issue. Replaying the
#                    corpus must not comment on closed goals.
#   --bare           run the checker from a scratch directory, so the repository's own
#                    CLAUDE.md is not loaded into its context. Only useful for asking
#                    whether a verdict came from the rule file or from the repository's
#                    standing instructions; never use it for a real activation check.
#
# The checker is a separate headless Claude Code process. It receives the goal issue and
# the rules, never the reasoning of the session that wrote the goal.
#
# Exits 0 only on an explicit pass, as scripts/validate-goal.sh does.
set -euo pipefail

root=$(git rev-parse --show-toplevel)

issue=""
rules="$root/docs/GOAL_RULES.md"
comment=1
bare=0

while [ $# -gt 0 ]; do
  case "$1" in
    --rules)      rules="${2:?--rules needs a path}"; shift 2 ;;
    --no-comment) comment=0; shift ;;
    --bare)       bare=1; shift ;;
    -h|--help)    sed -n '2,18p' "$0"; exit 0 ;;
    -*)           echo "unknown option: $1" >&2; exit 2 ;;
    *)
      if [ -n "$issue" ]; then
        echo "unexpected argument: $1" >&2
        exit 2
      fi
      issue="$1"; shift ;;
  esac
done

[ -n "$issue" ] || { echo "usage: scripts/check-goal.sh <issue-number> [--rules <path>] [--no-comment] [--bare]" >&2; exit 2; }
[ -f "$rules" ] || { echo "rule file not found: $rules" >&2; exit 2; }

# Absolute from here on. The rule file is read inside the subshell that --bare moves to a
# scratch directory, so a path relative to the caller's directory would resolve there and
# not where the caller meant. Relative paths stay relative to the caller, which is what a
# caller expects; they are only pinned before the directory changes underneath them.
rules=$(cd "$(dirname "$rules")" && pwd)/$(basename "$rules")

body_hash=$("$root/scripts/goal-body-hash.sh" "$issue")

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

gh issue view "$issue" --json title,body,labels,milestone > "$workdir/goal.json"

# No tools: the prompt is the goal, the rules and the brief, and the checker cannot go
# reading the repository to answer a different question from the one it was asked.
#
# The prompt is not the whole context. Running from the repository root loads CLAUDE.md,
# so the standing instructions are present as well -- correct for a real check, and the
# reason --bare exists for the one question that needs them absent. D-017.
cwd="$root"
if [ "$bare" -eq 1 ]; then
  cwd="$workdir"
fi

verdict=$(cd "$cwd" && claude -p \
  --append-system-prompt "$(cat "$root/agents/goal-checker.md")" \
  --allowedTools "" \
  --output-format text \
  <<PROMPT
You are the goal checker. Apply the criteria in your instructions to the material below
and emit only the JSON verdict object. No preamble, no code fences.

Rules a goal may not authorise a violation of:
$(cat "$rules")

Goal issue:
$(cat "$workdir/goal.json")
PROMPT
)

if [ "$comment" -eq 1 ]; then
  {
    echo "<!-- goal-checker body:${body_hash} -->"
    echo '```json'
    printf '%s\n' "$verdict"
    echo '```'
  } > "$workdir/comment.md"
  gh issue comment "$issue" --body-file "$workdir/comment.md"
fi

printf '%s\n' "$verdict"

# Fail closed: only an explicit top-level pass exits 0. Parsed rather than grepped,
# because the checker quotes the goal's own text into its findings and a goal that
# discusses verdict JSON -- a governance goal about this very check, say -- would put the
# pass substring inside a blocking verdict. Malformed output parses to nothing and fails.
if [ "$(printf '%s' "$verdict" | jq -er '.verdict' 2>/dev/null || true)" = "pass" ]; then
  exit 0
fi
exit 1
