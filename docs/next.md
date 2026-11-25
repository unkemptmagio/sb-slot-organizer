# Next steps (in order)
1. **Spike 0 done**: the 1000 limit is three `IntConst 1000` in ATOOL `ModActor` (`DataGet1-3`), see `docs/spike0-atool-limit.md`. Pick a patch route (runtime UE4SS patch preferred, no redistribution).
2. **Spike, applying a move**: options are (A) PEFA metadata only, (B) re-slot our own ported paks via the port repo's registry, (C) rewrite/override third-party paks. C is unproven and may crash the game.
3. `apply` (backup, dry-run first, refuse while game runs) and `revert`, then PyInstaller `.exe`, CHANGELOG, release zip.
4. Reserved slots file (`reserved.txt`, seed 901-907 Tachy face) wired into the CLI (`plan(reserved=)` exists).

5. Container-id clashes are the real 'clip unavailable' cause (scan reports them). `apply` could re-chunk OUR paks (new container id) but cannot fix third-party clashes; report them and tell the user which pak to disable.
6. Slot 660 test pak loads and plays; slot 6666 (same scene, same pak name) does not, so something slot-number specific remains. Find the real threshold (build 1001 / 2000) before promising >1000 slots.

7. fixids: apply it on the real install (ESAP, OldDroid) and confirm in game that slots 700-709 / 307-311 now appear in ATOOL's list (`anim3`); then PyInstaller exe, ceiling auto-detect (9999 when AToolSlotLimit is installed), reserved.txt.
