target: aiventure3d
role: implement
step: verify-0
seen: 1
first_run: aiventure3d-10-20261128-0345
---
**What happened:** Gate `smoke` failed at verify-0 even though all four frame-time checks passed (p95 50.1 ms in town, wilderness, dungeon and fight, each under its 60.x ms limit). The failure came from the loading indicator, which displayed the raw value `[null,"Loading the area…",null]` instead of the text "Loading the area…".

**Cause:** unknown. The evidence shows the serialized array reaching the loading indicator, but not the code path that produced it, so the cause is not established.

**Rule:** Before reporting done, load the app in Chromium, trigger an area load, and confirm the loading indicator's rendered text is a plain sentence (not a serialized array or object such as `[null,...]`).
