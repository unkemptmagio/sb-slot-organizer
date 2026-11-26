# Status and next steps (2026-11-25)

## Done and verified in game
- ATOOL 1000 limit located (three IntConst 1000 in ModActor DataGet1-3) and lifted at runtime by AToolSlotLimit (slots 1001/2000 play).
- Container-id clashes (ESAP 700-709, OldDroid 307-311) fixed with `fixids`, both confirmed in game.
- `moveslots`: IoStore rewrite (ids, name hashes incl. CityHash64 long branch, header, directory index, bulk data), journaled with rollback, guarded revert. Moved BBS_P (sheep), Feet's Whisper clash test and the Leito test pak, all play.
- Slot-keyed files follow their owner (Vortex manifests, else the first-sight ledger).
- Two independent code reviews done and fixed (see CHANGELOG).
- Release: `release.ps1` -> `release/SlotOrganizer-<version>.zip` (exe, user README, AToolSlotLimit + installer).

## Open
1. Digit-count changes (98 -> 100) are refused: not verified in game (string lengths inside blobs).
2. Compressed containers and legacy .pak mods are reported, not moved.
3. Own-pak re-slotting through the port repo (port.py assigns slots, writes wav/names/PELA and the owner together) so the tool never has to guess for our packs.
4. Code signing / SmartScreen, a license for public release, Nexus page text.
5. AToolSlotLimit has two builds: RevOG SB-UE4SS 1.3 (tested in game) and Chrisr0 3.1.0-4/5/6 (= SB-UE4SS 3.1.6): built, every import resolves, NOT tested in game. To finish: run it on a Chrisr0 3.1.0-x UE4SS (back up dwmapi.dll + the ue4ss folder first), read UE4SS.log and ATOOL's list at slot 1001+, then move the three hashes from UNTESTED_UE4SS to KNOWN_UE4SS in slots.py and the installer text.
