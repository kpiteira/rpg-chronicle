#!/usr/bin/env bash
# PreToolUse hook: refuse `gh pr merge` until an independent validator verdict passes.
#
# Exit 0  -> allow the tool call.
# Exit 2  -> block the tool call; stderr is returned to the agent as the reason.
set -uo pipefail

payload=$(cat)
command=$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)

case "$command" in
  *"gh pr merge"*) ;;
  *) exit 0 ;;
esac

pr=$(gh pr view --json number --jq .number 2>/dev/null || true)
if [ -z "$pr" ]; then
  echo "Cannot identify the pull request for this branch; refusing to merge." >&2
  exit 2
fi

verdict=$(gh pr view "$pr" --json comments \
  --jq '[.comments[] | select(.body | test("^<!-- goal-validator -->"))] | last | .body // ""' \
  2>/dev/null || true)

if [ -z "$verdict" ]; then
  echo "No goal-validator verdict on PR #${pr}. Run: scripts/validate-goal.sh ${pr}" >&2
  exit 2
fi

if printf '%s' "$verdict" | grep -q '"verdict": *"block"'; then
  echo "The goal validator blocked PR #${pr}:" >&2
  printf '%s\n' "$verdict" >&2
  echo "Address the blocking findings and re-run scripts/validate-goal.sh ${pr}." >&2
  exit 2
fi

exit 0
