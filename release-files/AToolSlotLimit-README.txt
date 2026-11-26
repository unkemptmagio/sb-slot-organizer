AToolSlotLimit - raises ATOOL's 1000-slot limit at runtime
==========================================================

REQUIRES:  RevOG SB-UE4SS 1.3  -  and nothing else.
           UE4SS.dll SHA-256  E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE
           ue4ss\UE4SS.log has a line near the top (line 2, after a timestamp) reading:
           UE4SS - v3.0.1 Beta #0 - Git SHA #08a0733
           (the SHA-256 above is the reliable check)

ALSO REQUIRES: ATOOL (HD-ATOOL_P) installed. The mod waits for ATOOL's class and has never been run without it.
Settings: limit=1000 leaves ATOOL unchanged; values below 1000 are not supported.

This is a native UE4SS mod (a DLL). It was built against, and tested only with, that exact UE4SS build.
On any other UE4SS (including Chrisr0/RE-UE4SS 3.1.x, where a test ended in a crash while loading)
it is unsupported and may crash the game at launch. Do not install it there.

Install: run install-atool-limit.bat from the SlotOrganizer package (it refuses other UE4SS builds),
or copy this folder to  SB\Binaries\Win64\ue4ss\Mods\AToolSlotLimit  yourself ONLY if your UE4SS is the build above.
Settings: config.txt (limit=9999), enabled.txt (1 = on, 0 = off). Uninstall: delete the folder.
Log lines to look for: "[AToolSlotLimit] v0.2 loaded" and "done: 3 constant(s) now 9999" (see the end of this file).
This version (0.2) main.dll SHA-256: C42C8EF0AB1B1EBC16DBE62927F65CB6C600A12071D73CDC1DE15C325B7AFD76
MIT licensed. Independent community mod, not affiliated with Shift Up, ATOOL or UE4SS.

IF THE OPTIONAL MOD DOES NOT WORK (AToolSlotLimit)
It writes the same lines to two places: the UE4SS log  <game>\SB\Binaries\Win64\ue4ss\UE4SS.log  (search for "AToolSlotLimit")
and its own timestamped file  Mods\AToolSlotLimit\AToolSlotLimit.log  (next to config.txt, rotated at 256 KB).
  * Working:  "[AToolSlotLimit] v0.2 loaded, limit 9999", "host UE4SS: ... - the tested build (RevOG SB-UE4SS 1.3)",
              "engine tick callback is running", then "done: 3 constant(s) now 9999 (3 expected)".
  * "host UE4SS: ... NOT the tested build": you are not on RevOG SB-UE4SS 1.3 - unsupported.
  * No "v0.2 loaded" line: the mod was not loaded - wrong UE4SS build, mod folder in the wrong place, or enabled.txt is 0.
  * "waiting for ATOOL" then "still waiting for ATOOL after N s" (every 30 s): ATOOL's class is not loaded - ATOOL is not
    installed or not loaded. "ATOOL found after N s" follows when it appears.
  * "odd Script array" / "no 1000 constant" (logged once): ATOOL's data looks different from the version the mod was made for.
  * "config: limit=... is below 1000": fix config.txt (1000 leaves ATOOL unchanged; the mod raises lower values to 1000).
Attach AToolSlotLimit.log (or the UE4SS.log lines containing AToolSlotLimit) when you ask for help. They contain your game folder path.
