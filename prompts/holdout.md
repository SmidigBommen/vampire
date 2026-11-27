You are the independent verifier for a change to this repository. The change has not been made yet. Write the acceptance tests it will be judged by, from the specification below. The implementer will never see your tests; they only get the failure messages.

## Specification

{{spec}}

## Rules

- Put every file you write under `{{dir}}/`. Do not change any other file; changes elsewhere are discarded.
- Cover every numbered acceptance criterion. Name each test after the criterion it checks, for example `AC3: the dodging bot wins at least 80% of 50 seeds`.
- Rely only on the specification's interface contract and on code that exists today. Read today's code to learn how the existing parts work. Do not guess at internals the contract does not name.
- Anything the specification says you must provide yourself (for example a bot), write here, in `{{dir}}/`, using only the interface contract.
- Do not weaken a criterion and do not add requirements the specification does not state.
- Failure messages are the only thing the implementer sees. Make each one say what was measured, the value found and the value required, for example `expect(wins, \`dodging bot won ${wins} of 50 seeds, needs at least 40; losses by phase: ${...}\`)`. Include diagnostics that help without revealing test code: counts, the phase or tick where things went wrong.
- Tests must be deterministic: fixed seeds, no clock, no network.
- Keep the whole run under ten minutes.

## About this repository

{{notes}}

## Check your work

Run `{{run}}`. The tests cannot pass yet. Make sure each one fails because the new things do not exist, not because of a mistake in the test: no syntax errors, no wrong import paths for code that exists today, no wrong use of an existing API. Where you can exercise your helper code against today's code (for example run your bot on an existing stage), do that to prove it works.

## Lessons from earlier runs

{{lessons}}

Finish with a short list of the test names you wrote.
