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

head_sha=$(gh pr view "$pr" --json headRefOid --jq .headRefOid)

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

diff_bytes=$(wc -c < "$workdir/pr.diff")
if [ "$diff_bytes" -gt 400000 ]; then
  echo "PR #${pr} diff is ${diff_bytes} bytes; too large for one validator context." >&2
  echo "Split the PR. A verdict on a truncated diff would be theatre." >&2
  exit 1
fi

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
  echo "<!-- goal-validator sha:${head_sha} -->"
  echo '```json'
  printf '%s\n' "$verdict"
  echo '```'
} > "$workdir/comment.md"

gh pr comment "$pr" --body-file "$workdir/comment.md"
printf '%s\n' "$verdict"

# Fail closed: only an explicit pass exits 0. The merge-gate hook applies the same rule
# through the same reader, so a malformed verdict cannot drift through either layer.
#
# This was a grep for the substring `"verdict": "pass"` anywhere in the output, which is
# not the same question. The validator quotes the pull request's own text into its
# findings, so a change to this script -- or to the gate, or to the goal rules -- puts that
# substring inside a *blocking* verdict, and the grep reads it as a pass. See
# scripts/verdict_state.py for the cases and #38 for the measurement.
state=$(printf '%s' "$verdict" | python3 "$root/scripts/verdict_state.py" || true)

if [ -z "$state" ]; then
  echo "The validator's output could not be read as a verdict; treating it as a block." >&2
  exit 1
fi
[ "$state" = "pass" ] && exit 0
echo "The goal validator recorded \"${state}\" for PR #${pr}." >&2
exit 1
