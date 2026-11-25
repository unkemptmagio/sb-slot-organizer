# Spike 0: where does the ATOOL slot limit live? (2026-11-25, partial)

Verified:
- `LogicMods/HD-ATOOL_P` ships only 85 assets (ModActor, `data/` blueprints `NewBlueprint1-3`, `NewAnimBlueprint`, `ATOOL`, widgets, pics). No clips: every clip comes from other paks at `/Game/Mods/HD-ATOOL_P/anim/<slot>`.
- PEFA (the library window we use) loads clips by path string, `"/Game/Mods/HD-ATOOL_P/anim/" .. slot .. "." .. slot` (PEFA `Scripts/main.lua` lines 581, 604). Nothing in PEFA caps the slot at 1000.
- So the "<= 1000" rule in the port repo comes from ATOOL's own blueprints (its slot picker), not from the engine and not from PEFA.

Not verified:
- Whether a clip at slot 1001+ loads and plays through PEFA. Needs one clip built at e.g. 1001 (port repo: `PORT_ONLY=<id>` test build with `SLOT_RANGES` overridden), then PEFA in game.
- What ATOOL itself does with slots > 1000 (needs its blueprint bytecode: export `data/ATOOL`, `NewBlueprint1-3`, `ModActor` as JSON from FModel; none are exported yet in `D:\Modding\FModel\Output`).

Conclusion so far: likely not an engine limit. If the PEFA test passes, users who play through PEFA can use slots above 1000 and the planner ceiling can be raised; ATOOL's own UI would still not list them.

## Update 2026-11-25: FModel JSON export
Exported with FModel (right-click > Export > Properties .json; output `D:\Modding\FModel\Output\Exports\SB\Content\Mods\HD-ATOOL_P\`): `ModActor.json` (800 KB), `data/a1.json`, `data/NewWidgetBlueprint1.json`, `data/NewWidgetBlueprint2.json`.
Not exported yet: `a2`, `ATOOL`, `NewBlueprint1-3`, `NewAnimBlueprint`, `NewWidgetBlueprint3` (the last export did not land).
FModel quirk: after each export the explorer is replaced by the JSON tab; re-select another folder then `data` to bring the tiles back.

Findings:
- The JSON has structure and default values only, **no Kismet bytecode** (195 functions listed, no script). A hard-coded clamp inside a blueprint graph cannot be read this way.
- ModActor defaults build the clip path from a prefix plus a number: `os3 = AnimSequence'/Game/Mods/HD-ATOOL_P/anim/` (also `os1 = .../pose/`, `os2 = .../expr/`), indexes `j1..j3` (default 1) and limits `jl1..jl3` (default -1). Functions `DataGet1-3`, `AnimOut1-3`, `JlGet1-3`, `JSet` handle them.
- No `1000`, `1001` or `999` constant anywhere in ModActor, `a1`, `NewWidgetBlueprint1/2` (grep of all exported JSON).
- So the limit, if it is ATOOL's, is in bytecode (or in the picker UI widget 3), not in any data value we can edit.
- Product owner: slots above 1000 were already tested in other sessions, so no new in-game test is planned here. Record the result of that test in this file when known.

Next if the exact limit location still matters: decode the bytecode of `ModActor` / `NewBlueprint1-3` with a Kismet-aware tool (UAssetGUI / KismetAnalyzer on the raw `.uasset`), which needs the `.uasset` extracted from the pak (FModel: Export > Raw Data).
