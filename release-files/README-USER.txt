SlotOrganizer - Stellar Blade anim slot organizer
=================================================

+------------------------------------------------------------------------------------------
|  TESTED VERSIONS - READ THIS FIRST
|
|  Tested on ONE setup: Windows 11 - Stellar Blade on Steam - mods installed with Vortex
|  - UE4SS = "RevOG SB-UE4SS 1.3".
|
|  * SlotOrganizer itself (clash fixes + undo) does not use UE4SS at all.
|  * The OPTIONAL AToolSlotLimit mod (slots above 1000) works ONLY with
|        RevOG SB-UE4SS 1.3
|        UE4SS.dll SHA-256  E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE
|        near the top of ue4ss\UE4SS.log: "UE4SS - v3.0.1 Beta #0 - Git SHA #08a0733"
|    Every other UE4SS build is UNSUPPORTED and untested - the installer refuses it. A
|    test on Chrisr0/RE-UE4SS 3.1.0-5 ended in a game crash during loading. Do not install
|    the optional mod on any other UE4SS.
|  * Not tested on a real game folder: installs without Vortex (only on synthetic test
|    folders), Epic / GOG copies of the game.
|  * 1.0.1 verified in game: a mod with THREE containers on one slot (HD-EVE-Lilly-Hug) moved
|    together, Lily and her mecha appear. In that test Eve and Lily looked overlapped; the
|    animation data is identical to the original, so the tool did not change positions, but
|    it was not compared at the original slot in game.
+------------------------------------------------------------------------------------------

WHAT IT DOES
Animation mods that use the ATOOL / PEFA / PELA system each claim numbered "slots".
When two mods claim the same slot, or two mod files share the same internal container id,
one of them silently stops working. SlotOrganizer finds those clashes and fixes them:

  * container-id clash -> the clashing pak gets a new unique container id
  * slot clash         -> the newer mod's clip is moved to a free slot (same digit count)
  * a mod that ships several containers for one slot (main clip, partner clips, partner table;
    e.g. HD-EVE-Lilly-Hug) counts as ONE mod: its containers move together, or not at all
  * the files that belong to a moved slot (audio, PEFA names, PELA patches) follow it

QUICK START
 1. Close Stellar Blade.
 2. Double-click SlotOrganizer.exe. It scans your install, lists what it would change and
    asks before doing anything. (If your game is not on Steam it asks for the folder once.)
 3. Answer y to apply. Start the game.
 Run it again after you install or update animation mods.

WHAT CHANGES ON DISK (and how it is undone)
  * slot move: the mod's container(s) are rewritten (all of a mod's containers or none). Each
    original is kept beside it as <name>.utoc.orig / <name>.ucas.orig (then .orig1 ... for later moves).
  * container-id fix: the new id is written into the pak in place (three small spots); the
    old ids are kept in the journal. With Vortex the staged copy is a hard link, so it
    changes too.
  * audio / PEFA names / PELA files: edited or copied; the originals are saved in the journal.
  * journals, the ledger and the cache live in  %LOCALAPPDATA%\SlotOrganizer  (they survive
    re-extracting a new release). The exact paths are printed when you apply.
UNDO:  double-click Undo-last-run.bat (or run SlotOrganizer.exe revert) with the game closed. It undoes the newest run - everything one
double-click did, container ids and slot moves together. A file you changed after the run
(a re-installed mod, an edited names.txt) is NOT overwritten: it is listed, the tool exits
with an error, and the original is kept (paks: beside it as *.orig; other files: in the journal folder). Vortex may show the *.orig
files as external changes; do not delete them until you are happy with the result.

COMMANDS (terminal)
  SlotOrganizer.exe scan | plan | moveslots | fixids | auto | revert | log | --version
  moveslots / fixids only show a plan; add --apply to write (asks first; --yes skips asking)
  options: --game <StellarBlade or its SB folder>   --reserved <file of slots to avoid>
           moveslots --pak <~mods/x.utoc> --slot N --to M   moves that whole mod's containers
  Slots 901-907 are never used as targets by default (they belong to the Tachy face scenes); put your own
  list in reserved.txt next to the exe (one slot or a range such as 901-907 per line, # for comments).

VORTEX AND MANUAL INSTALLS
Vortex records which mod each file came from, so the tool knows whose audio/PELA files
belong to which pak. Without Vortex (manual installs, other managers) the tool keeps a
first-sight ledger: while a slot has a single pak it remembers that pak as the owner of the
slot's audio/PELA files. Run it once on a clean install, then after each new install. If
ownership is unknown on a shared slot, audio and PEFA names are copied (harmless) and PELA
files are left alone; the tool says so. A mod installed by hand that overwrites another
mod's audio file before the first run cannot be told apart.

OPTIONAL: MORE THAN 1000 SLOTS (advanced) - RevOG SB-UE4SS 1.3 ONLY
ATOOL stops at slot 1000. The AToolSlotLimit mod lifts that at runtime. It is a native UE4SS mod,
and a native mod only works with the exact UE4SS it was built for: RevOG SB-UE4SS 1.3 (see the box
at the top for how to recognise it: SHA-256 of ue4ss\UE4SS.dll, or the banner line near the top of UE4SS.log).
  * Install with install-atool-limit.bat. It checks your UE4SS.dll and REFUSES anything but
    RevOG SB-UE4SS 1.3. (-InstallUnverified overrides it; that may crash the game at launch.)
  * If you do not use RevOG SB-UE4SS 1.3, do not use this mod: SlotOrganizer then keeps everything
    within slots 1..1000 and tells you.
  * SlotOrganizer only uses slots above 1000 when the mod is installed, enabled AND your UE4SS is
    that build. If you force a higher --ceiling it warns that those clips may not show up in game.
  * Requires ATOOL (HD-ATOOL_P) to be installed: the mod waits for ATOOL's class and has never been run
    without it. (limit=1000 in config.txt leaves ATOOL unchanged; values below 1000 are not supported.)
  * It never overwrites your config.txt / enabled.txt. To remove it, delete Mods\AToolSlotLimit.
    If the game crashes at launch after installing it, delete that folder.
  * Only the current UE4SS folder layout (Win64\ue4ss\Mods) is detected by SlotOrganizer.
WHAT IT WILL NOT DO (it reports instead of guessing)
  * legacy .pak-only mods (slot stored inside the pak) - ask the author for an IoStore build
  * compressed containers, or moving a slot to a different digit count (98 -> 100)
  * touch mods that are not animation packs
  * move a main clip away from its partner parts: if they are in different mods or folders (or a
    container only holds partner data), or one container of a mod cannot be rewritten, the whole
    clash is reported and nothing moves. Install such parts as one mod, then run it again.
If no free slot is left, or a pak cannot be rewritten safely, the clash is reported and left.

SAFETY NOTES
  * Close the game first; the tool refuses to write while it runs, and checks again after you answer.
  * If a previous run was interrupted (crash, power loss) the tool says so and offers to undo it
    (or use Undo-last-run.bat); it changes nothing until that is done.
  * If a failed move could not be undone completely the tool says "NOT fully rolled back" and tells
    you NOT to run revert: the originals are in the journal folder (path printed) and as *.orig
    beside the paks. Send the log; delete that journal folder once the files are checked.
  * Windows SmartScreen / antivirus may warn about unsigned one-file exes.

IF SOMETHING GOES WRONG
Every run writes a plain-text log: %LOCALAPPDATA%\SlotOrganizer\logs\slotorganizer.log
(previous one: slotorganizer.log.1). The tool prints its path when a run fails. To see the path
and the last lines:  SlotOrganizer.exe log
When you ask for help, attach that file. It contains what the tool printed: the paths of your game and mod folders (which can include your Windows user name) and the file names of your mods - read it first if that matters to you. It contains no passwords.
First try Undo-last-run.bat, then ask.
Lines to look for with a mod that has several containers (e.g. Lilly-Hug):
  * working:  "mod X = a, b, c", "X: slot 201 -> 202 (3 containers moved together: ...)", "verified: X now on slot 202"
  * "slot N cannot be fixed automatically ... holds only the partner part": a main clip and its partner parts are in
    different mods/folders; install them as one mod
  * "note: ... split by mod name": a folder holds several mods; harmless
  * "move of X failed and was rolled back completely" or "NOT fully rolled back": attach the log (and say which)
PEFA may list an extra group "<mod> ConfigAnim (N)" for such a mod: harmless, it is the same before the move.

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

CREDITS AND LICENSE
SlotOrganizer is free software (MIT License, see LICENSE) and an independent community tool: it is
not affiliated with Shift Up, ATOOL, PEFA, PELA, UE4SS or any mod author. It works with their
formats and never uploads or redistributes their files. Third-party notices: NOTICE.txt.