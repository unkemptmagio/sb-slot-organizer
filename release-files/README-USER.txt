SlotOrganizer - Stellar Blade anim slot organizer
=================================================

WHAT IT DOES
Animation mods that use the ATOOL / PEFA / PELA system each claim numbered "slots".
When two mods claim the same slot, or two mod files share the same internal container id,
one of them silently stops working. SlotOrganizer finds those clashes and fixes them:

  * container-id clash -> the clashing pak gets a new unique container id
  * slot clash         -> the newer mod's clip is moved to a free slot (same digit count)
  * the files that belong to a moved slot (audio, PEFA names, PELA patches) follow it

QUICK START
 1. Close Stellar Blade.
 2. Double-click SlotOrganizer.exe. It scans your install, lists what it would change and
    asks before doing anything. (If your game is not on Steam it asks for the folder once.)
 3. Answer y to apply. Start the game.
 Run it again after you install or update animation mods.

WHAT CHANGES ON DISK (and how it is undone)
  * slot move: the pak is rewritten. The original is kept beside it as <name>.utoc.orig /
    <name>.ucas.orig (then .orig1 ... for later moves).
  * container-id fix: the new id is written into the pak in place (three small spots); the
    old ids are kept in the journal. With Vortex the staged copy is a hard link, so it
    changes too.
  * audio / PEFA names / PELA files: edited or copied; the originals are saved in the journal.
  * journals, the ledger and the cache live in  %LOCALAPPDATA%\SlotOrganizer  (they survive
    re-extracting a new release). The exact paths are printed when you apply.
UNDO:  double-click Undo-last-run.bat (or run SlotOrganizer.exe revert) with the game closed. It undoes the newest run - everything one
double-click did, container ids and slot moves together. A file you changed after the run
(a re-installed mod, an edited names.txt) is NOT overwritten: it is listed, the tool exits
with an error, and the original is still beside it as *.orig. Vortex may show the *.orig
files as external changes; do not delete them until you are happy with the result.

COMMANDS (terminal)
  SlotOrganizer.exe scan | moveslots | fixids | auto | revert | --version
  moveslots / fixids only show a plan; add --apply to write (asks first; --yes skips asking)
  options: --game <StellarBlade or its SB folder>   --reserved <file of slots to avoid>

VORTEX AND MANUAL INSTALLS
Vortex records which mod each file came from, so the tool knows whose audio/PELA files
belong to which pak. Without Vortex (manual installs, other managers) the tool keeps a
first-sight ledger: while a slot has a single pak it remembers that pak as the owner of the
slot's audio/PELA files. Run it once on a clean install, then after each new install. If
ownership is unknown on a shared slot, audio and PEFA names are copied (harmless) and PELA
files are left alone; the tool says so. A mod installed by hand that overwrites another
mod's audio file before the first run cannot be told apart.

OPTIONAL: MORE THAN 1000 SLOTS (advanced)
ATOOL stops at slot 1000. The AToolSlotLimit mod lifts that at runtime. It is a native UE4SS mod and
is verified ONLY with  RevOG SB-UE4SS 1.3  (Nexus; UE4SS.dll SHA-256 E0CC51CE...DABE, the build
whose UE4SS.log says "v3.0.1 Beta ... Git SHA #08a0733").
It does NOT load on the older 3.1.x Stellar Blade builds (Chrisr0/RE-UE4SS 3.1.0-x, the one PEFA
lists as tested, or SB-UE4SS 3.1.6): the DLL needs C++ hooks those builds do not have. On those
builds nothing breaks - UE4SS just skips the mod - but slots above 1000 will not work.
  * install-atool-limit.bat checks your UE4SS and warns if it is not the verified build.
  * SlotOrganizer only uses slots above 1000 when the mod is installed, enabled AND your UE4SS is
    the verified build; otherwise it keeps everything within 1..1000 and tells you.
  * It never overwrites your config.txt / enabled.txt. To remove it, delete Mods\AToolSlotLimit.
WHAT IT WILL NOT DO (it reports instead of guessing)
  * legacy .pak-only mods (slot stored inside the pak) - ask the author for an IoStore build
  * compressed containers, or moving a slot to a different digit count (98 -> 100)
  * touch mods that are not animation packs
If no free slot is left, or a pak cannot be rewritten safely, the clash is reported and left.

SAFETY NOTES
  * Close the game first; the tool refuses to write while it runs, and checks again after you answer.
  * If a previous run was interrupted (crash, power loss) the tool says so and offers to undo it
    (or use Undo-last-run.bat); it changes nothing until that is done.
  * Windows SmartScreen / antivirus may warn about unsigned one-file exes.

IF SOMETHING GOES WRONG
Every run writes a plain-text log: %LOCALAPPDATA%\SlotOrganizer\logs\slotorganizer.log
(previous one: slotorganizer.log.1). The tool prints its path when a run fails. To see the path
and the last lines:  SlotOrganizer.exe log
When you ask for help, attach that file. It contains the paths of your game and mod folders and
what the tool printed - read it first if that matters to you - and no passwords or personal data.
First try Undo-last-run.bat, then ask.

CREDITS AND LICENSE
SlotOrganizer is free software (MIT License, see LICENSE) and an independent community tool: it is
not affiliated with Shift Up, ATOOL, PEFA, PELA, UE4SS or any mod author. It works with their
formats and never copies or redistributes their files. Third-party notices: NOTICE.txt.