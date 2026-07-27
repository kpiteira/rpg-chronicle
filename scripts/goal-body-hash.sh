#!/usr/bin/env bash
# Print the hash a goal-check verdict is bound to, for one issue.
#
# Usage: scripts/goal-body-hash.sh <issue-number>
#
# The check binds its verdict to this hash the way scripts/validate-goal.sh binds its
# verdict to a head SHA: an issue edited after being checked no longer carries a matching
# verdict, and the mismatch is visible rather than silent.
#
# One implementation, called by both scripts/check-goal.sh and the goal-lifecycle
# workflow. Two would drift, and a drifted hash reports every goal as unchecked.
set -euo pipefail

issue="${1:?usage: scripts/goal-body-hash.sh <issue-number>}"

if command -v sha256sum >/dev/null 2>&1; then
  digest() { sha256sum; }
elif command -v shasum >/dev/null 2>&1; then
  digest() { shasum -a 256; }
else
  echo "neither sha256sum nor shasum is available" >&2
  exit 1
fi

# GitHub stores issue bodies with CRLF line endings; strip them so the hash does not
# depend on which client last edited the issue.
gh issue view "$issue" --json body --jq '.body' \
  | tr -d '\r' \
  | digest \
  | cut -d' ' -f1
