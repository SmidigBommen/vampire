target: aiventure3d
role: implement
step: verify-0
seen: 1
first_run: aiventure3d-11-20261128-0653
---
**What happened:** The implement step left `web/routes` on disk after the classic-UI removal. The holdout gate reported 43 of 45 hidden tests passing; `test_AC4_removed_paths_modules_and_dependencies` failed with "these removed paths still exist: ['web/routes']", and `test_AC13_repository_tests_pass_and_keep_their_number` failed in `test_the_classic_files_are_gone`, which checks the same removal list.

**Cause:** unknown. The evidence shows that `web/routes` still exists but not whether it held files or was an empty directory, and it does not show why the removal step skipped it. The other listed paths passed.

**Rule:** Before reporting a removal done, run `test -e` on every path the spec lists for removal, directories included, and delete any that remain, starting with `web/routes`.
