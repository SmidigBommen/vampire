You wrote the acceptance tests in `{{dir}}/` from the specification below, before the implementation existed. The implementation is now in the working directory. Some of your tests fail and the implementer, who cannot see them, disputes them. Decide whether your tests are wrong. You get this one chance to correct them.

## Specification

{{spec}}

## The implementer's disputes

{{disputes}}

## Output of your tests against the implementation

```
{{output}}
```

## Rules

- Change a test only where the test is at fault: it contradicts the specification, relies on something the interface contract does not name, misuses an API, or a helper you wrote (for example a bot) has a defect of its own.
- Do not lower a threshold, drop a criterion or loosen an assertion to make the implementation pass. If the implementation misses a target the specification sets, the test is right and stays.
- You may read the implementation and run `{{run}}`.
- Change only files under `{{dir}}/`.

Then write `amend.json` in the working directory:

```json
{"changed": true, "reason": "which tests you changed and what was wrong with them, or why you changed nothing"}
```
