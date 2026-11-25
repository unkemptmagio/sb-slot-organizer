# sb-slot-organizer

Pregame tool for Stellar Blade anim paks: finds every ATOOL slot (`/Game/Mods/HD-ATOOL_P/anim/<slot>`) your installed packs use,
reports clashes, and proposes a conflict-free layout. Python 3.10, stdlib only.

## Status (2026-11-25)
Built: `scan` and `plan` (read-only), per-pak cache, Steam game-folder detection. Verified on a real install: 16 paks, 351 slots, 0.98 s cold, 0.26 s cached.
Also reports IoStore container-ID clashes (u64 at TOC offset 56): when two paks share an id only one mounts and the other's clips never load. Verified 2026-11-25 on a real install: ESAP (slots 700-709) clashes with Death Expression and OldDroid (307-311) with GildedRoseDress Part2, which is why their clips were missing from ATOOL's list. That, not the slot number, is the real cause of most 'clip unavailable' cases.
NOT built yet: `apply` / `revert` and the `.exe` packaging. Why: slot numbers are baked into IoStore pak asset paths, so moving a third-party
clip needs a rewrite we have not proven safe. See `docs/next.md`.

## Use
```
python slots.py scan [--game <...>\SB] [--no-cache]
python slots.py plan [--ceiling 1000]
python tests/slots_test.py
```
Exit code 1 when clashes exist. Cache: `slot_cache.json` (pak path, size, mtime -> slots); a corrupt cache is rebuilt.
