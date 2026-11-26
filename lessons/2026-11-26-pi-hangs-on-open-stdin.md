target: any
role: driver
step: holdout
seen: 1
first_run: setup
---
**What happened:** `pi -p --mode json @prompt.md "..."` started from a script produced no output and never exited; it was stopped after 180 s.

**Cause:** Pi waits on standard input when it is left open. The same command with `< /dev/null` finished in seconds.

**Rule:** Start every headless agent with standard input closed or fed explicitly, and give every agent call a timeout.
