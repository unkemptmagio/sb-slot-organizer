# Next steps (in order)
1. **Spike 0 done**: the 1000 limit is three `IntConst 1000` in ATOOL `ModActor` (`DataGet1-3`), see `docs/spike0-atool-limit.md`. Pick a patch route (runtime UE4SS patch preferred, no redistribution).
2. **Spike, applying a move**: options are (A) PEFA metadata only, (B) re-slot our own ported paks via the port repo's registry, (C) rewrite/override third-party paks. C is unproven and may crash the game.
3. `apply` (backup, dry-run first, refuse while game runs) and `revert`, then PyInstaller `.exe`, CHANGELOG, release zip.
4. Reserved slots file (`reserved.txt`, seed 901-907 Tachy face) wired into the CLI (`plan(reserved=)` exists).
