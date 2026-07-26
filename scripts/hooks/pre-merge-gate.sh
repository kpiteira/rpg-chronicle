#!/usr/bin/env bash
# PreToolUse hook: mechanical guards on Bash tool calls.
#
# Exit 0  -> allow the tool call.
# Exit 2  -> block the tool call; stderr is returned to the agent as the reason.
#
# Command recognition is delegated to scripts/hooks/classify_command.py, which
# tokenizes with shlex so that a guarded command quoted as data stays data.
#
# A classifier that cannot run leaves every command unclassified, so the hook
# refuses all of them rather than clearing them. That is the correct direction,
# and the blast radius is worth stating plainly: a missing or broken python3
# stops the session from running any Bash command, not merely guarded ones.
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
  merge-multiple)
    echo "This command merges more than one pull request; refusing to merge." >&2
    echo "Run one merge per command, so each is checked against its own verdict." >&2
    exit 2
    ;;
  "merge "*)
    target=${decision#merge }
    ;;
  *)
    # Anything else means the classifier and this gate disagree about their own
    # contract. Refusing is the only safe reading; falling through would have
    # handed unrecognized output to `gh pr view` as though it named a PR.
    echo "Unrecognized decision from the command classifier; refusing to merge." >&2
    exit 2
    ;;
esac

case "$target" in
  "" | *[[:space:]]*)
    echo "The command classifier named no usable pull request; refusing to merge." >&2
    exit 2
    ;;
esac

# `gh pr view` accepts a number, a URL, or a branch name, so whatever the merge
# command named is resolved directly. Only a merge that names nothing falls back
# to the current branch; resolving a named branch that way would check one pull
# request's verdict while merging another.
if [ "$target" = "-" ]; then
  pr=$(gh pr view --json number --jq .number 2>/dev/null || true)
else
  pr=$(gh pr view "$target" --json number --jq .number 2>/dev/null || true)
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
