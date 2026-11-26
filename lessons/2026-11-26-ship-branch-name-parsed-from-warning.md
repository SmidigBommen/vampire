target: fighter
role: driver
step: ship
seen: 1
first_run: fighter-1-20261126-1652
---
**What happened:** In step ship, the driver ran `gh pr merge` with the branch argument set to "  - Event subscriptions are in preview and may not be enabled for your account.", a CLI warning line, not a branch name. gh reported `no pull requests found for branch` and the merge did not happen.

**Cause:** unknown. The evidence shows the warning text was used as the branch name, but not which command's output it came from or how the driver extracted it. The likely cause is that the branch name was parsed from combined command output that included a warning line.

**Rule:** Before running `gh pr merge`, get the branch name from `git rev-parse --abbrev-ref HEAD` (or the branch the implement step pushed), and abort if it contains spaces or newlines.
