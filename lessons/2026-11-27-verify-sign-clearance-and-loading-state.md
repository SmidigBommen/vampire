target: aiventure3d
role: implement
step: verify-1
seen: 1
first_run: aiventure3d-2-20261127-1243
---
**What happened:** The independent reviewer rejected the verify-1 change on two spec violations. In client/src/world/areaScene.ts, buildGate (line 111) sets the sign bottom to Math.min(top + 0.02, layout.ceiling - SIGN_HEIGHT - 0.02), so at ceilings of 3.5 m and 4.0 m (Sunken Temple of Dariel/coastal_approach, Abandoned Watchtower/approach) the sign hangs across the 3.3 m gateway arch instead of sitting above it. In client/src/main.ts (lines 104-123), a gate-to-gate enterArea sets loading=true but leaves the old layout and player in place, so window.__aiv.player and window.__aiv.layout return the previous area's values during loading, which spec 2.7 forbids. The smoke test checked only the title-to-world load, which behaves correctly, so it missed both.

**Cause:** unknown. The evidence shows that the smoke test did not assert sign placement at low ceilings or the state during a gate-to-gate transition. It does not show why the implementer did not check those cases.

**Rule:** Before reporting done, test each spec clause that sets a visible or state requirement at its extreme inputs (the lowest ceiling in the dungeon data and a gate-to-gate transition), and fix any failure before reporting.
