#!/usr/bin/env bash
# Run the goal validator against a pull request in a fresh, uncontaminated context.
#
# Usage: scripts/validate-goal.sh <pr-number>
#
# The validator is a separate headless Claude Code process. It receives the goal issue,
# the diff, and the product boundaries -- never the implementing session's reasoning.
set -euo pipefail

pr="${1:?usage: scripts/validate-goal.sh <pr-number>}"
root=$(git rev-parse --show-toplevel)

issue=$(gh pr view "$pr" --json body --jq '.body' \
  | grep -oE '(Closes|closes) #[0-9]+' | head -1 | grep -oE '[0-9]+' || true)

if [ -z "$issue" ]; then
  echo "PR #${pr} does not close a goal issue; the validator has nothing to check." >&2
  exit 1
fi

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

gh issue view "$issue" --json title,body,labels,milestone,comments > "$workdir/goal.json"
gh pr diff "$pr" > "$workdir/pr.diff"
gh pr checks "$pr" --json name,state > "$workdir/checks.json" || true

verdict=$(claude -p \
  --append-system-prompt "$(cat "$root/agents/goal-validator.md")" \
  --allowedTools "Read" \
  --output-format text \
  <<PROMPT
You are the goal validator. Apply the criteria in your instructions to the material
below and emit only the JSON verdict object. No preamble, no code fences.

Product boundaries:
$(cat "$root/docs/PRODUCT.md")
$(cat "$root/docs/ARCHITECTURE_BOUNDARIES.md")

Goal issue:
$(cat "$workdir/goal.json")

CI checks:
$(cat "$workdir/checks.json")

Pull request diff:
$(cat "$workdir/pr.diff")
PROMPT
)

{
  echo "<!-- goal-validator -->"
  echo '```json'
  printf '%s\n' "$verdict"
  echo '```'
} > "$workdir/comment.md"

gh pr comment "$pr" --body-file "$workdir/comment.md"
printf '%s\n' "$verdict"

printf '%s' "$verdict" | grep -q '"verdict": *"block"' && exit 1
exit 0
