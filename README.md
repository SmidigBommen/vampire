# vampire

A software factory: one command takes a GitHub issue to production with no person in between.
Successor to `leo-task-flow`.

## How a run goes

| Step | Who | What |
|---|---|---|
| intake | driver | Reads the issue from the target repository. |
| workspace | driver | Makes a worktree and branch for the implementer and a separate checkout for the verifier. |
| spec | Claude Code, read-only | Turns the issue into a specification with an exact interface contract and numbered acceptance criteria. |
| holdout | Pi + DeepSeek | Writes the acceptance tests from the specification alone, before any implementation exists. |
| implement | Claude Code | Builds the change. It never sees the holdout tests. |
| verify | driver, Pi | Runs the gates (build, tests, browser smoke test, holdout tests), then Pi reviews the diff. On failure Claude Code gets the failure messages, without test source, for at most two fix rounds. |
| ship | driver | Pushes the branch, opens the pull request, squash-merges it. |
| deploy | driver | Deploys through Coolify and checks production in a browser. On failure it reverts the merge, redeploys and stops. |
| report | driver | Comments on the issue and commits the run summary to `runs/`. |

When the factory cannot go on (fix rounds used up, a crash, a rollback) it opens an issue labelled
`needs-human` on the target repository and stops. `factory run <target> --resume <run>` continues
from the last finished step.

Every error becomes a file in `lessons/`. Later runs get the rules of the lessons that match their
target and role in their prompts. A lesson seen twice is listed in the report as a candidate for a
check in code.

## Keeping the holdout tests hidden

The tests live in `~/.local/share/vampire/hidden/<run>/`, outside both repositories. While the
implementer runs, that directory has mode 000 and Claude Code has a deny rule on it. The
implementer and the verifier run as the same user, so this stops accidents and casual reading,
not a determined process. The diff review is the second check.

If the implementer disputes a holdout test, the verifier gets one chance to correct its own tests.
It may fix a faulty test but not lower a threshold. The pull request says when this happened.

## Running it

```bash
execution/factory.py run fighter --issue 1           # WRITES: pushes, merges, deploys
execution/factory.py run fighter --issue 1 --until verify
execution/factory.py run --resume fighter-1-20261126-1700
execution/factory.py status [--all]
execution/factory.py lessons [--target fighter] [--role implement]
```

Needs `claude`, `pi`, `gh`, `coolify`, `git` and `uv` on PATH, all logged in. Claude Code runs on
the subscription; Pi bills the provider in the target file.

## Layout

```
execution/factory.py        the driver
execution/browser_check.mjs production check: loads the site, fails on any error
targets/<name>.toml         one file per target repository: commands, gates, models, deployment
prompts/                    one prompt per agent role
lessons/                    one file per recorded error
runs/                       one summary per run: time and cost per step, fix rounds, human touches
```

Working state, logs and worktrees are in `~/.local/share/vampire/` and are not committed.

## Adding a target

Copy `targets/fighter.toml`. The target needs a build command, a test command, a smoke test that
runs against a local server, a test runner that writes JSON in Jest's result format (Vitest does),
and a Coolify application.
