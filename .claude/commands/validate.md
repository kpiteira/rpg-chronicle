---
description: Run the independent goal validator against a pull request
allowed-tools: Bash(scripts/validate-goal.sh:*), Bash(gh pr view:*)
---

Run the goal validator against PR $1 and report its verdict verbatim.

!`scripts/validate-goal.sh $1`

Do not argue with the verdict in this session. If it blocks, fix the finding or reply on
the PR with evidence, then re-run the validator as a fresh process.
