#!/usr/bin/env bash
# Replay the goal checker over goals whose outcome is already known.
#
# Usage: scripts/replay-goal-check.sh
#
# The checker's whole value is whether it discriminates, so the corpus is chosen by a
# stated criterion rather than by which goals happen to give the wanted answer:
#
#   MUST BLOCK — goals whose durable outputs put material about a real recording into the
#   repository. All three are goals whose output docs/CONTENT_AUDIT.md later removed.
#     #21  a committed human-corrected reference transcript, on a CC BY 3.0 argument.
#     #11  a per-recording manifest and answer key, plus attributed quotation.
#     #14  per-recording manifests and rights determinations for each candidate.
#
#   MUST PASS — goals whose durable outputs are software or governance and that committed
#   nothing about a real recording.
#     #12  a model-backed AnalysisProvider behind a vendor-neutral seam.
#     #17  governance documents describing the repository as it is.
#
#   MUST BLOCK on structure rather than content.
#     #31  a goal authored for this corpus with four required sections absent, closed
#          immediately, never labelled, never a real goal.
#
# Two goals are deliberately absent from both lists, because the checker found real
# defects in them and putting them in either list would be fitting the corpus to the
# result. They are recorded in docs/DECISIONS.md D-017 instead:
#     #20  claims `src/rpg_chronicle/providers.py`, a TPM-owned shared contract, without
#          naming the cross-role request — a genuine R5 breach in a goal that merged.
#     #25  lists "Two schemas" as a durable output after its own amendment withdrew the
#          split — the same defect the goal validator raised as an advisory on PR #29,
#          found here from the goal text alone, before any code was written.
#
# The first run of this corpus expected #11 and #14 to pass. They blocked, and the block
# is correct: both were sound under the rules in force when they were written, and both
# authorise committed per-recording artifacts under R1 as it now stands. The expectation
# was wrong, not the checker. That is left recorded here rather than quietly refitted.
#
# It then runs #21 again with R1 removed and with --bare, which keeps the repository's
# CLAUDE.md out of the checker's context. That answers a question the pass/block results
# cannot: does the verdict come from the rule file, or would the checker have refused
# anyway? See D-017 for what was observed.
#
# Nothing here comments on an issue. The corpus is closed goals.
set -euo pipefail

root=$(git rev-parse --show-toplevel)
rules="$root/docs/GOAL_RULES.md"

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

run() { # run <issue> <expected>
  local issue="$1" expected="$2" verdict actual
  verdict=$("$root/scripts/check-goal.sh" "$issue" --no-comment || true)
  # Parsed, not grepped: the checker quotes goal text into its findings, so a substring
  # match could read a quoted verdict as this run's own and silently invalidate the
  # evidence. Malformed output yields "none", which matches no expectation.
  actual=$(printf '%s' "$verdict" | jq -er '.verdict' 2>/dev/null || true)
  printf '=== #%s expected:%s actual:%s\n%s\n\n' "$issue" "$expected" "${actual:-none}" "$verdict"
  [ "${actual:-none}" = "$expected" ]
}

status=0
run 21 block || status=1
run 11 block || status=1
run 14 block || status=1
run 12 pass  || status=1
run 17 pass  || status=1
# Structural completeness, R7. #31 is a closed issue created for this purpose: a goal with
# four required sections absent and acceptance evidence that reads "the work is done well
# and the specialist is satisfied with the result".
run 31 block || status=1

# R1 removed: the section from its heading up to the next rule heading.
awk '/^## R1 —/{skip=1} /^## R2 —/{skip=0} !skip' "$rules" > "$workdir/rules-no-r1.md"
if ! grep -q '^## R2 —' "$workdir/rules-no-r1.md"; then
  echo "mutation produced a rule file with no R2; the awk range is wrong" >&2
  exit 1
fi
if grep -q '^## R1 —' "$workdir/rules-no-r1.md"; then
  echo "mutation did not remove R1; the awk range is wrong" >&2
  exit 1
fi

echo "=== mutation: #21 with R1 removed, --bare (result is evidence, not pass/fail)"
"$root/scripts/check-goal.sh" 21 --rules "$workdir/rules-no-r1.md" --no-comment --bare || true

exit "$status"
