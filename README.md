# sb-slot-organizer

Pregame tool for Stellar Blade anim paks: finds every ATOOL slot (`/Game/Mods/HD-ATOOL_P/anim/<slot>`) your installed packs use,
reports clashes, and proposes a conflict-free layout. Python 3.10, stdlib only.

## Status (2026-11-25)
Built: `scan` and `plan` (read-only), per-pak cache, Steam game-folder detection. Verified on a real install: 16 paks, 351 slots, 0.98 s cold, 0.26 s cached.
Also reports IoStore container-ID clashes (u64 at TOC offset 56): when two paks share an id only one mounts and the other's clips never load. Verified 2026-11-25 on a real install: ESAP (slots 700-709) clashes with Death Expression and OldDroid (307-311) with GildedRoseDress Part2, which is why their clips were missing from ATOOL's list. That, not the slot number, is the real cause of most 'clip unavailable' cases.
NOT built yet: `apply` / `revert` and the `.exe` packaging. Why: slot numbers are baked into IoStore pak asset paths, so moving a third-party
clip needs a rewrite we have not proven safe. See `docs/next.md`.

## fixids (2026-11-25, built, dry run verified on the real install, applied 2026-11-25)
`python slots.py fixids` lists container-id clashes that stop an anim pak from mounting and the new unique id it would get; `--apply` writes it (game closed), `python slots.py revert` restores the last backup (`slot_backups/ids-*/manifest.json` keeps the old ids and byte offsets). Only anim paks are patched, never the other mod of a clash. Patches the id in all three places it lives (utoc header +56, the ContainerHeader chunk id in the TOC, first 8 bytes of that chunk in the .ucas); refuses when the three disagree or the chunk is compressed. Note: Vortex hard-links mod files (ESAP has 2 links), so the staged copy changes too; a Vortex re-deploy keeps the patch, a re-download of the mod restores the clash.

## Exe (built 2026-11-25)
`dist/SlotOrganizer.exe` (PyInstaller one-file, 5.5 MB, not committed): double-click = find the game, report clashes, show what `fixids` would change, wait for Enter. For changes use a terminal: `SlotOrganizer.exe fixids --apply` (game closed), `SlotOrganizer.exe revert`. Rebuild: `python -m PyInstaller --onefile --name SlotOrganizer --distpath dist --workpath build --specpath build slots.py` (`pip install pyinstaller` first). Some antivirus tools flag unsigned one-file exes.
Slot ceiling is automatic: 1000, or the `limit=` of the AToolSlotLimit mod when it is installed and enabled (`--ceiling N` overrides). `reserved.txt` (one slot or range per line, `#` comments; default 901-907) keeps slots out of `plan`.

## Use
```
python slots.py scan [--game <...>\SB] [--no-cache]
python slots.py plan [--ceiling 1000]       # 9999 when AToolSlotLimit is installed
python slots.py fixids [--apply]
python slots.py revert
python tests/slots_test.py
```
Exit code 1 when clashes exist. Cache: `slot_cache.json` (pak path, size, mtime -> slots); a corrupt cache is rebuilt.

## fixids verified in game (2026-11-25 09:44)
After `fixids --apply` (ESAP 0xcda35a93... -> 0x57925699..., OldDroid 0xfb3161d2... -> 0x37782ade...): ATOOL's `anim3` grew from 338 to 353 clips and ESAP's slots 700, 705 and 709 are now in it (before: absent), so the clash was the cause. OldDroid (307-311) lives under `Monster/CH_M_NA_49/Animation/DO_*` and is not loaded through `anim/<n>`; a name sweep finds none resident, so it is NOT confirmed (play an OldDroid scene to check).
Lesson: a probe that called `StaticFindObject` on a non-resident path crashed the game at 09:43:39 (a known trigger, see sb-live/docs/live-pak.md). Probe only with `FindAllOf` + name match; never `StaticFindObject`/`LoadAsset` on paths that may not be loaded.


## Moving slots (moveslots)

python slots.py moveslots plans a move for every slot held by two or more anim paks (the newest pak moves; LogicMods paks never do), --apply rewrites the pak's IoStore container to the new slot (game closed, same digit count only). Originals stay beside the pak as *.orig, *.orig1, ... and python slots.py revert puts them back; every step is journaled before it happens and a failure rolls back.

**Slot-keyed files** (udio/<slot>.wav, PEFA 
ames.txt, PELA json) follow their owner. Owner comes from Vortex's deployment manifests when present; manual / mod-manager installs have none, so the tool keeps a first-sight ledger (slot_owners.json, filled on every run while a slot has a single pak). Known owner = renamed; other mod's = left; unknown on a shared slot = wav and PEFA name are copied, PELA left. A manually installed mod that overwrites another mod's wav before the first run cannot be told apart: run the tool once on a clean install, then after each install.

Not supported (reported, not guessed): moved packages with bulk chunks, digit-count changes, compressed containers.

## Release

.\release.ps1 runs the tests, builds the exe and writes elease\SlotOrganizer-<version>.zip (exe, README-USER.txt, optional AToolSlotLimit with install-atool-limit.ps1). Double-clicking the exe runs uto: scan, show what would change, ask, apply. --yes skips the question; --version prints the version.
