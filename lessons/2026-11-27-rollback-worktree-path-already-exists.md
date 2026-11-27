target: aiventure3d
role: driver
step: deploy
seen: 1
first_run: aiventure3d-1-20261127-1144
---
**What happened:** The deploy step failed with exit 128 because `git worktree add --detach /var/home/neo/.local/share/vampire/work/aiventure3d-1-20261127-1144/rollback origin/main` found that the rollback directory already existed. Git stopped with "fatal: '.../rollback' already exists" before creating the worktree.

**Cause:** unknown. The evidence does not show why the rollback directory was already present, such as whether an earlier run or rollback left a worktree behind or whether a stale path was never pruned.

**Rule:** Before running `git worktree add` for the rollback path, run `git worktree list` and remove or prune any existing worktree at that path, or use a fresh unique path, and only then create the worktree.
