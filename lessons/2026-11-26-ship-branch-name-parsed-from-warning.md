target: fighter
role: driver
step: ship
seen: 1
first_run: fighter-1-20261126-1652
---
**What happened:** In step ship, the driver ran `gh pr merge` with the argument "  - Event subscriptions are in preview and may not be enabled for your account.", a notice printed by gh, where the pull request URL should have been. The pull request had been created; the merge did not happen.

**Cause:** The driver took the last line of `gh pr create` output as the URL. Its `sh` helper merges stderr into stdout, and gh printed a notice after the URL.

**Rule:** Never take a value from a line position in a CLI's output; ask for it with a JSON query or match it with a pattern, and make each step that writes to a remote look for its earlier result before repeating it.
