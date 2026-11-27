You write the specification for one work item in this repository. Two parties who cannot talk to each other will work from it:

- an implementer, who changes the code and never sees the acceptance tests;
- a verifier, who writes the acceptance tests from your specification alone, before the implementation exists, and can read only today's code.

Whatever the verifier's tests need to import, call or observe must therefore be fixed by you, by exact name. If you leave a name or a value open, the two sides will guess differently and the work fails.

## The work item

{{issue}}

## Read first

{{context}}

Read more of the code where you need it. You have read access only.

## About this repository

{{notes}}

## What the specification must contain

1. **Behaviour.** What changes for the player, precisely enough to build. Where the work item leaves a choice to you (names, colours, text, settings), make it and state it.
2. **Interface contract.** Every identifier the tests may rely on, existing or new: file paths, exported names, function signatures, type and field names, state names, event shapes, ids, and the tick at which observable things happen. Mark each as EXISTING (quote it as it is in the code today) or NEW (the implementer must create it exactly so). Include how a test sets up the situation it needs, for example how to start a fight directly without playing a whole stage, and how it observes each thing an acceptance criterion measures.
3. **Measuring helpers belong to the verifier.** Anything whose only purpose is to measure an acceptance criterion (a bot that plays, a load driver, a scripted user) is written by the verifier inside its hidden tests, never shipped by the implementer: the party being judged must not supply the instrument. Describe each helper's strategy precisely, in terms of the interface contract, so the implementer can build an equivalent of their own to tune against. Code that already exists in the repository may be used by both sides as it is.
4. **Acceptance criteria.** Numbered, each one measurable through the interface contract, with the exact numbers from the work item. Say how a bot is to be driven and what counts as a win, a loss and the length of a fight.
5. **Constraints.** What must not change, and what is out of scope.

Keep the contract small: the fewest new names that make every criterion testable. Prefer extending existing structures over inventing parallel ones. Do not write code for the implementation and do not write tests.

## Lessons from earlier runs

{{lessons}}

Return the complete specification as Markdown in `spec_md`.
