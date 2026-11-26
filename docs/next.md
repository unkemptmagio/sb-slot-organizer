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
5. AToolSlotLimit is shipped for ONE UE4SS only: RevOG SB-UE4SS 1.3 (tested in game). A second build for the Chrisr0 3.1.0 line was written and removed (2026-11-25): its first in-game run showed the mod loaded but never patched, and a rerun with a diagnostic DLL crashed during loading (cause not analysed). Other UE4SS builds stay unsupported until someone tests them.
