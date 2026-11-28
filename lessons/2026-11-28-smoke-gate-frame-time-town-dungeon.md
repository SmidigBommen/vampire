target: aiventure3d
role: implement
step: verify-0
seen: 3
first_run: aiventure3d-12-20261128-1141
---
**What happened:** Step verify-0 failed the smoke gate. Frame-time p95 in town was 66.6 ms and in dungeon 66.6 ms, both against a baseline of 50.1 ms (4fbc1f5) and a limit of 60.1 ms. Wilderness (50.0 ms) and fight (50.1 ms) stayed within limit. The gate then timed out after 900 s.

**Cause:** unknown. The evidence shows which two scenes regressed but not what in the change added per-frame cost to them.

**Rule:** Before reporting done, run the smoke frame-time scenes for town and dungeon yourself and confirm each p95 is under its limit, and if either is over, profile that scene and fix the cost before reporting.
- Seen again in aiventure3d-12-20261128-1141, step verify-1: The smoke gate failed at verify-1 because the town and dungeon scenes exceeded their frame-time limit: p95 66.7 ms against a 60.1 ms limit, versus a 50.1 ms baseline at 4fbc1f5. Wilderness (50.1 ms) and fight (50.1 ms) passed.
- Seen again in aiventure3d-12-20261128-1141, step verify-2: The smoke gate failed at verify-2 because town p95 frame time was 66.7 ms against a 60.1 ms limit (baseline 50.1 ms at 4fbc1f5). Wilderness (50.0 ms), dungeon (50.1 ms) and fight (50.1 ms) were within their limits.
