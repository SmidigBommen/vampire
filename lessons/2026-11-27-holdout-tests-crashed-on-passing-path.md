target: aiventure3d
role: holdout
step: amend-1
seen: 1
first_run: aiventure3d-4-20261127-1643
---
**What happened:** In amend-1 the verifier changed two hidden tests after the implementer disputed them. test_ac08_parity_vocabulary raised AttributeError: 'NoneType' object has no attribute 'get' on the passing case, because its failure messages called .get() on bad_kind, bad_outcome and bad_fx even when no bad event existed. test_ac06_api_only_rejections compared the session file against snapshots taken before H.write() replaced the session for the no_battle cases, so its "refused request changed the file" checks used a stale baseline.

**Cause:** The defects were in the holdout's own test code: eager evaluation of failure-message lookups and a snapshot taken too early. The evidence does not show why the tests were issued without their passing paths being run against a correct implementation, so the reason for that gap is unknown.

**Rule:** Before issuing any hidden test, run it against a known-passing implementation, including the no-violation case, and take each file snapshot immediately before the request it is compared against.
