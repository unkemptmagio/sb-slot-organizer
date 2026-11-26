AToolSlotLimit - raises ATOOL's 1000-slot limit at runtime
==========================================================

REQUIRES:  RevOG SB-UE4SS 1.3  -  and nothing else.
           UE4SS.dll SHA-256  E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE
           ue4ss\UE4SS.log starts with:  UE4SS - v3.0.1 Beta #0 - Git SHA #08a0733

This is a native UE4SS mod (a DLL). It was built against, and tested only with, that exact UE4SS build.
On any other UE4SS (including Chrisr0/RE-UE4SS 3.1.x, where a test ended in a crash while loading)
it is unsupported and may crash the game at launch. Do not install it there.

Install: run install-atool-limit.bat from the SlotOrganizer package (it refuses other UE4SS builds),
or copy this folder to  SB\Binaries\Win64\ue4ss\Mods\AToolSlotLimit  yourself ONLY if your UE4SS is the build above.
Settings: config.txt (limit=9999), enabled.txt (1 = on, 0 = off). Uninstall: delete the folder.
Log lines to look for in UE4SS.log: "[AToolSlotLimit] v0.1 loaded" and "done: 3 constant(s) now 9999".
MIT licensed. Independent community mod, not affiliated with Shift Up, ATOOL or UE4SS.
