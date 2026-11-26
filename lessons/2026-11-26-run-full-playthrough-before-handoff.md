target: fighter
role: implement
step: verify-0
seen: 1
first_run: fighter-1-20261126-1652
---
**What happened:** The implement step verify-0 failed the holdout gate with 12 of 16 hidden acceptance tests passing. The smoke test (AC13) timed out with exit 1 before stage 5 reached the ending, name-entry and scores screenshots (23 of 26 captured). Stage 5 had slam_charge with a hit box where the spec requires none (AC11). Slam waves 21 and 22 were still present at S+33 in phase 2 at 50% hp, seed 6, S=1770 (AC6). In phase 3, a slam at S=1759 missed the player and no slam_charge started within 90 ticks (AC10).

**Cause:** unknown. The evidence shows which checks failed but not why the implementation missed them. The stdout and stderr tails are empty, so it does not show whether the smoke timeout was a hang, a slow path or a crash.

**Rule:** Before reporting the implement step done, run the smoke playthrough from stage 1 through the ending and score table and confirm it exits 0 with all 26 screenshots, and check the slam wave despawn at S+33 and slam_charge within 90 ticks in every phase against the spec's values.
