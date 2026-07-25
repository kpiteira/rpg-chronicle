#!/usr/bin/env bash
# PreToolUse hook: mechanical guards on Bash tool calls.
#
# Exit 0  -> allow the tool call.
# Exit 2  -> block the tool call; stderr is returned to the agent as the reason.
#
# Guard 1: any `git push` whose destination ref is main is refused. Permission
# prefix rules cannot see refspecs -- `git push origin HEAD:main` satisfies an
# allow rule for `git push origin` -- so the destination is matched here.
#
# Guard 2: `gh pr merge` is refused unless the latest goal-validator verdict is
# an explicit pass recorded against the PR's current head commit. No verdict,
# a malformed verdict, or a verdict for a superseded commit all fail closed.
set -uo pipefail

payload=$(cat)
command=$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)

if printf '%s' "$command" | grep -qE 'git push[^;|&]*[ :](refs/heads/)?main([^[:alnum:]/_-]|$)'; then
  echo "Refusing to push to main. Land changes through a pull request." >&2
  exit 2
fi

case "$command" in
  *"gh pr merge"*) ;;
  *) exit 0 ;;
esac

pr=$(gh pr view --json number --jq .number 2>/dev/null || true)
if [ -z "$pr" ]; then
  echo "Cannot identify the pull request for this branch; refusing to merge." >&2
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
