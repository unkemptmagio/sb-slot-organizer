# Spike 0: where does the ATOOL slot limit live? (2026-11-25, partial)

Verified:
- `LogicMods/HD-ATOOL_P` ships only 85 assets (ModActor, `data/` blueprints `NewBlueprint1-3`, `NewAnimBlueprint`, `ATOOL`, widgets, pics). No clips: every clip comes from other paks at `/Game/Mods/HD-ATOOL_P/anim/<slot>`.
- PEFA (the library window we use) loads clips by path string, `"/Game/Mods/HD-ATOOL_P/anim/" .. slot .. "." .. slot` (PEFA `Scripts/main.lua` lines 581, 604). Nothing in PEFA caps the slot at 1000.
- So the "<= 1000" rule in the port repo comes from ATOOL's own blueprints (its slot picker), not from the engine and not from PEFA.

Not verified:
- Whether a clip at slot 1001+ loads and plays through PEFA. Needs one clip built at e.g. 1001 (port repo: `PORT_ONLY=<id>` test build with `SLOT_RANGES` overridden), then PEFA in game.
- What ATOOL itself does with slots > 1000 (needs its blueprint bytecode: export `data/ATOOL`, `NewBlueprint1-3`, `ModActor` as JSON from FModel; none are exported yet in `D:\Modding\FModel\Output`).

Conclusion so far: likely not an engine limit. If the PEFA test passes, users who play through PEFA can use slots above 1000 and the planner ceiling can be raised; ATOOL's own UI would still not list them.
