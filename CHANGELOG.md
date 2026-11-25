# Changelog

## Unreleased
- scan, plan, per-pak cache, Steam detection (read-only).

- fixids / revert: give clashing anim paks a unique IoStore container id (backup + byte-exact revert, tested on synthetic containers).

- Auto-detected slot ceiling (AToolSlotLimit), reserved.txt, double-click SlotOrganizer.exe report.

## Verified in game
- moveslots: BBS_P moved 982 -> 983 next to the Leito test pak at 982; both clips play (2026-11-25).
- Limit: packs with partner tables / package names over 64 bytes are refused (CityHash64 long branch unverified).
