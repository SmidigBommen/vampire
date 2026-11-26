Implement the specification below in this repository. You are working in a git worktree on a branch made for this change.

## Specification

{{spec}}

## How your work is judged

1. These commands must pass; run them yourself before you finish:
{{checks}}
2. A browser smoke test is run for you afterwards (see the repository's `execution/` folder). Keep it working and update it where the specification changes what it walks through.
3. An independent verifier has written hidden acceptance tests from this same specification. They import and observe exactly what the interface contract names. A name, path, signature or value that differs from the contract fails them, so follow it to the letter. You will not see these tests, only their failure messages.
4. The verifier then reads your diff. Code that treats a bot, a seed or a test differently from a real player is rejected.

Where the specification sets measurable targets, write your own measurement (a test or a script) and tune until you meet them with margin: the hidden tests measure the same thing with their own helper code, which will not behave exactly like yours.

## Rules

- Stay inside the specification's scope. Do not change behaviour it tells you to leave alone.
- Follow the conventions of the surrounding code. Add tests for what you build, next to the existing ones.
- Do not commit; the factory commits for you.
- If the specification is impossible or contradicts the code, implement the closest correct thing and explain in your summary.

## Lessons from earlier runs

{{lessons}}

When done, return a `summary` for the pull request: what you built, the choices you made and the measurements you took. Leave `disputes` empty.
