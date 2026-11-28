target: aiventure3d
role: implement
step: verify-0
seen: 1
first_run: aiventure3d-9-20261128-0144
---
**What happened:** The implementer's client change let a late preview answer call drawCreation(), which replaces #creation-body and destroys the focused #creation-name input while the name step is open, so typing is swallowed and Enter submits a truncated name. It also let closeSaves() run while a save, load or delete was in flight (slotsLocked not checked, Escape and Close active), so slotSend() discards the answer; for a load the server has moved to the new session but the client keeps the old world. The smoke test only waited for the preview on the class step.

**Cause:** unknown. The evidence shows the smoke test never produced a preview answer during the name step or a close during an in-flight request, but it does not show why the implementer did not check those cases.

**Rule:** Before reporting a client UI change done, trigger each async answer (preview, save, load, delete) while the user is on a later step with a focused input and while the panel is being closed, and confirm the input keeps focus and the answer is still applied.
