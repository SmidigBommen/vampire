target: aiventure3d
role: implement
step: verify-1
seen: 1
first_run: aiventure3d-9-20261128-0144
---
**What happened:** In the pending state, the title screen shows New game and Load game, but clicking either does nothing. apply() sets screen = 'pending' (client/src/main.ts:462), while openCreation() (line 1465) and openSaves() (lines 1595/1598) only act when screen === 'title'. In Chromium, __aiv.creation and __aiv.saves stay null after the click, and Continue and #classic-link are hidden, so the player cannot start a game, load a save, or reach the classic interface. Spec 1.3 requires both buttons to work whenever the server answered.

**Cause:** Likely: the 'pending' screen value was added to apply() and showTitle() without updating the screen guards in openCreation() and openSaves(), which still compare only against 'title'. The evidence does not show whether the implementer checked those guards.

**Rule:** When you add or change a screen/state value, grep every comparison against the screen variable (for example `screen === 'title'`) and update each one, then click every visible button in each state in Chromium and confirm each opens its panel (__aiv.creation and __aiv.saves are non-null).
