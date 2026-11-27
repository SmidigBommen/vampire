target: aiventure3d
role: implement
step: verify-0
seen: 1
first_run: aiventure3d-2-20261127-1243
---
**What happened:** The holdout gate failed 25 of 26 hidden acceptance tests. The failing test, test_AC1_existing_server_tests_pass, reports that the existing server suite exited 1. Its test_battle case POSTs to /battle/boss with act_num=1, location_name="Whispering Woods", and area_id="grove", then expects battle.is_active to be True. It was False.

**Cause:** unknown. The evidence shows the existing test_battle assertion failing after the change, but not which edit caused it or whether the implementer ran the existing test suite before reporting done.

**Rule:** Before reporting done, run the full existing test suite (test/, including test/test_api_world.py) and fix every failure, including test_battle, which requires POST /battle/boss to set battle.is_active to True.
