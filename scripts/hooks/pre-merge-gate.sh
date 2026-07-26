#!/usr/bin/env bash
# PreToolUse hook: mechanical guards on Bash tool calls.
#
# Exit 0  -> allow the tool call.
# Exit 2  -> block the tool call; stderr is returned to the agent as the reason.
#
# Command recognition is delegated to scripts/hooks/classify_command.py, which
# tokenizes with shlex so that a guarded command quoted as data stays data.
#
# Guard 1: any `git push` whose destination ref is main is refused.
# Guard 2: `gh pr merge` is refused unless the latest goal-validator verdict is
# an explicit pass recorded against the PR's current head commit. No verdict, a
# malformed verdict, or a verdict for a superseded commit all fail closed.
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

decision=$(python3 "${here}/classify_command.py" 2>/dev/null) || decision="unparseable"
[ -n "$decision" ] || decision="unparseable"

case "$decision" in
  allow)
    exit 0
    ;;
  push-main)
    echo "Refusing to push to main. Land changes through a pull request." >&2
    exit 2
    ;;
  unparseable)
    echo "Could not parse this command well enough to clear it past the merge gate." >&2
    echo "Simplify the command, or quote its arguments, and try again." >&2
    exit 2
    ;;
esac

pr=${decision#merge }

# `gh pr merge` accepts a branch name as well as a number. When the command
# names no PR the gate resolves one from the current branch, as before.
if [ "$pr" = "-" ]; then
  pr=$(gh pr view --json number --jq .number 2>/dev/null || true)
fi

if [ -z "$pr" ]; then
  echo "Cannot identify the pull request for this merge; refusing to merge." >&2
  exit 2
fi

head_sha=$(gh pr view "$pr" --json headRefOid --jq .headRefOid 2>/dev/null || true)
if [ -z "$head_sha" ]; then
  echo "Cannot read the head commit of PR #${pr}; refusing to merge." >&2
  exit 2
fi

verdict=$(gh pr view "$pr" --json comments \
  --jq '[.comments[] | select(.body | test("^<!-- goal-validator "))] | last | .body // ""' \
  2>/dev/null || true)

if [ -z "$verdict" ]; then
  echo "No goal-validator verdict on PR #${pr}. Run: scripts/validate-goal.sh ${pr}" >&2
  exit 2
fi

if ! printf '%s' "$verdict" | grep -q "<!-- goal-validator sha:${head_sha} -->"; then
  echo "The latest goal-validator verdict on PR #${pr} predates its current head commit." >&2
  echo "Re-run: scripts/validate-goal.sh ${pr}" >&2
  exit 2
fi

if ! printf '%s' "$verdict" | grep -qE '"verdict": *"pass"'; then
  echo "The goal validator did not record an explicit pass for PR #${pr}:" >&2
  printf '%s\n' "$verdict" >&2
  echo "Address the findings and re-run scripts/validate-goal.sh ${pr}." >&2
  exit 2
fi

exit 0
