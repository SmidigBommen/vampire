target: any
role: spec
step: spec
seen: 1
first_run: fighter-1-20261126-1652
---
**What happened:** The first specification for the ground-slam boss told the implementer to add `dodgeBotIntent` to `src/sim/bot.ts`, and measured the 80% win-rate criterion with it.

**Cause:** The spec prompt said nothing about who owns helpers that measure acceptance, so the spec writer put the bot next to the existing one.

**Rule:** Never ask the implementer to ship a helper that measures an acceptance criterion; describe its strategy and have the verifier write it in the hidden tests.
