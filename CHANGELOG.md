# Changelog

## Unreleased
- scan, plan, per-pak cache, Steam detection (read-only).

- fixids / revert: give clashing anim paks a unique IoStore container id (backup + byte-exact revert, tested on synthetic containers).

- Auto-detected slot ceiling (AToolSlotLimit), reserved.txt, double-click SlotOrganizer.exe report.

## Verified in game
- moveslots: BBS_P moved 982 -> 983 next to the Leito test pak at 982; both clips play (2026-11-25).
- Limit: packs with partner tables / package names over 64 bytes are refused (CityHash64 long branch unverified).

## CityHash64 long branch
- Fixed: the long (>64 B) branch seeded w with z + y; the reference uses z + w.second. Now 3793/3793 stored hashes (65-232 B, 205 containers) match, so partner-table packs and long package names can be moved.
- Fixed: chained moves of one pak overwrote its .orig backup; now .orig, .orig1, ... (test added).
- Known limit: slot-keyed files (wav, PEFA names, PELA) stay with the pak that keeps the slot; if the moved pak owns them, rename by hand or re-slot via the port pipeline.
