# AToolSlotLimit mod page / SlotOrganizer release text (draft)

> ## TESTED VERSIONS - READ FIRST
> **SlotOrganizer 1.0.0** was tested on one setup: **Windows 11 - Stellar Blade (Steam) - mods installed with Vortex - UE4SS "RevOG SB-UE4SS 1.3"**.
>
> **The optional AToolSlotLimit mod (slots above 1000) works ONLY with `RevOG SB-UE4SS 1.3`:**
> - `UE4SS.dll` SHA-256 `E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE`
> - a line near the top of `ue4ss\UE4SS.log` (line 2, after a timestamp): `UE4SS - v3.0.1 Beta #0 - Git SHA #08a0733`
>
> **Any other UE4SS build is unsupported and untested.** A test on Chrisr0/RE-UE4SS 3.1.0-5 ended in a game crash while loading. The installer refuses other builds. If you are not on RevOG SB-UE4SS 1.3, do not install the optional mod - SlotOrganizer itself works without it (it keeps everything within slots 1..1000).
> Not tested on a real game folder: installs without Vortex (synthetic folders only), Epic / GOG copies.

## What it is
Animation mods that use the ATOOL / PEFA / PELA system claim numbered slots. When two mods claim the same slot, or two paks share the same internal container id, one silently stops working. **SlotOrganizer** finds those clashes and fixes them, asking first, keeping every original, and able to undo everything. The optional **AToolSlotLimit** mod lifts ATOOL's 1000-slot limit.

## Requirements
| | Required |
|---|---|
| SlotOrganizer | Windows, Stellar Blade. No UE4SS needed. |
| AToolSlotLimit (optional) | **RevOG SB-UE4SS 1.3** (see the box above) and **ATOOL (HD-ATOOL_P)** installed - the mod has never been run without ATOOL |

## Install / use / undo
1. Close the game, double-click `SlotOrganizer.exe`, read the list, answer `y`.
2. Undo: `Undo-last-run.bat`. Logs: `%LOCALAPPDATA%\SlotOrganizer\logs\slotorganizer.log`.
3. Optional mod: only on RevOG SB-UE4SS 1.3 - run `install-atool-limit.bat`.

## Verified in game
Container-id fixes (ESAP 700-709, OldDroid 307-311), slot moves (BeepBeep sheep 982 to 983 and 985, Feet's Whisper alongside, Leito test clip), clips at slots 1001 and 2000 with AToolSlotLimit, a 982 to 1001 clip with partner tables (Adam visible).

## Limits
Legacy `.pak`-only mods, compressed containers and slot moves that change the digit count are reported, not changed. Slots above 1000 need AToolSlotLimit on RevOG SB-UE4SS 1.3.

## Credits and license
MIT. Independent community tools, not affiliated with Shift Up, ATOOL, PEFA, PELA, UE4SS or any mod author; never uploads or redistributes anyone's mod.