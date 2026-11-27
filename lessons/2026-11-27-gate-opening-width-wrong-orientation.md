target: aiventure3d
role: implement
step: verify-0
seen: 1
first_run: aiventure3d-1-20261127-1144
---
**What happened:** In client/src/world/areaScene.ts (lines 280-282), north/south boundary runs are drawn at `length + WALL_THICKNESS * 2` while east/west runs use `length`. Each north/south run reaches 0.6 m into the gate opening, so the visible opening is 1.8 m instead of the specified 3 m, and the arch posts are buried. This affects 45 of the 90 campaign gates. The trigger zone stays 3 m wide, so players can be moved through a gate while facing what looks like solid wall.

**Cause:** unknown. The evidence shows the asymmetric code path and the resulting geometry, but not why the implementer applied the thickness offset to one orientation only, or whether the rendered gap was checked for both orientations before the change was reported.

**Rule:** Before reporting a gate change as done, measure the rendered opening width for both north/south and east/west gates and confirm each is 3 m, fixing any orientation that differs.
