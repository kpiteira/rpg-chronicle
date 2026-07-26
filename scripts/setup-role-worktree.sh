#!/usr/bin/env bash
# One-time setup for a specialist role: worktree, environment, bootstrap lines.
#
# Usage: scripts/setup-role-worktree.sh <role-id>
set -euo pipefail

role="${1:?usage: scripts/setup-role-worktree.sh <role-id>}"

case "$role" in
  reuse-research)     dir="../rpg-reuse" ;;
  benchmark-research) dir="../rpg-benchmark" ;;
  review-analysis)    dir="../rpg-review" ;;
  vault-discovery)    dir="../rpg-vault" ;;
  *)
    echo "Unknown role '${role}'. Specialist roles:" >&2
    echo "  reuse-research benchmark-research review-analysis vault-discovery" >&2
    exit 1
    ;;
esac

root=$(git rev-parse --show-toplevel)
cd "$root"

abs_dir="$(cd "$(dirname "$dir")" && pwd)/$(basename "$dir")"
branch="codex/${role}/scratch"

if git worktree list --porcelain | grep -qxF "worktree ${abs_dir}"; then
  echo "Worktree ${dir} already exists; skipping creation."
else
  git fetch origin
  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    git worktree add "$dir" "$branch"
  else
    git worktree add "$dir" -b "$branch" origin/main
  fi
fi

(cd "$dir" && uv sync -q --dev)

cat <<BOOTSTRAP

Worktree ready: ${dir}

Start the session:

  cd ${dir}
  claude
  > You are the ${role} agent.
  > /goal Per the goal protocol in AGENTS.md, the single open issue labelled
    agent:${role} and goal:active is implemented, its pull request validated
    and merged, and the issue closed — or the goal is labelled goal:blocked,
    or a consequential product question is awaiting the user.

/goal is Claude Code's native goal loop; see docs/PARALLEL_EXECUTION.md.
BOOTSTRAP
