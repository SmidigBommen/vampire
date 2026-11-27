target: aiventure3d
role: implement
step: verify-0
seen: 1
first_run: aiventure3d-4-20261127-1643
---
**What happened:** The holdout gate failed at verify-0 with 31 of 33 hidden acceptance tests passing. test_ac08_parity_vocabulary raised AttributeError: 'NoneType' object has no attribute 'get', and test_ac06_api_only_rejections failed because a refused malformed ability request changed the session file.

**Cause:** unknown. The evidence shows the two symptoms but not the code path behind either one.

**Rule:** Before reporting done, send each malformed or refused ability request from AC6 to the API and confirm the session file is byte-identical afterward, and confirm every vocabulary key that AC8 looks up returns a non-null entry.
