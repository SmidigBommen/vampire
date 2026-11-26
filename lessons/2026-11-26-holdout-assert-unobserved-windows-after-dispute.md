target: fighter
role: holdout
step: amend-1
seen: 1
first_run: fighter-1-20261126-1652
---
**What happened:** The holdout's hidden tests for the slam criteria were wrong and had to be changed after a dispute. AC6 failed a wave as still present at S+33 for the phase 2, seed 6 slam (S=1770), but the 1800-tick run ended before S+33, so the removal row was never observed. AC10 reported a missing slam_charge for the phase 0.2, seed 2 slam (S=1759), but the run covered only 11 of the 90 ticks the spec grants. AC11 banned hit boxes on slam_charge for its whole move, while the spec bans them only before move tick 20.

**Cause:** Unknown from the evidence. The likely contributor is that the holdout's assertions did not check whether the run's last tick covered each criterion's observation window, and read the spec's "before move tick 20" qualifier as applying to the whole move. The evidence does not show why the holdout skipped those checks.

**Rule:** Before asserting a spec criterion as failed, confirm the run's final tick reaches the last tick of that criterion's observation window (for example S+33 or S+90); if it does not, mark that row unobserved and do not count it as a failure.
