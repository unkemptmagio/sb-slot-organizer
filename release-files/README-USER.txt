SlotOrganizer - Stellar Blade anim slot organizer
=================================================

WHAT IT DOES
Animation mods that use the ATOOL / PEFA / PELA system each claim numbered "slots".
When two mods claim the same slot, or two mod files share the same internal container id,
one of them silently stops working. SlotOrganizer finds those clashes and fixes them:

  * slot clash        -> the newer mod's clip is moved to a free slot (same digit count)
  * container-id clash -> the clashing pak gets a new unique container id
  * the files that belong to a moved slot (audio, PEFA names, PELA patches) follow it

It never edits a mod's files in place: originals stay beside the pak as *.orig, and every
change can be undone.

QUICK START
 1. Close Stellar Blade.
 2. Double-click SlotOrganizer.exe. It scans your install, shows what it would change and
    asks before doing anything.
 3. Answer y to apply. Start the game.
 Run it again after you install or update animation mods.

UNDO
  SlotOrganizer.exe revert        (undoes the newest run; game closed)
Files you changed after the run (e.g. a re-installed mod) are NOT overwritten; they are
reported and left alone.

COMMANDS (run from a terminal)
  SlotOrganizer.exe scan          report only
  SlotOrganizer.exe moveslots     show planned slot moves   (+ --apply, --yes)
  SlotOrganizer.exe fixids        show planned container-id fixes (+ --apply, --yes)
  SlotOrganizer.exe auto          what double-click does
  SlotOrganizer.exe revert
  options: --game <path to ...\StellarBlade\SB>   --reserved <file with slots to avoid>

VORTEX AND MANUAL INSTALLS
Vortex records which mod each file came from, so the tool knows whose audio/PELA files
belong to which pak. Without Vortex (manual or other managers) the tool keeps a first-sight
ledger (slot_owners.json next to the exe). Run it once on a clean install, then after each
new install, and ownership stays exact. When ownership is unknown on a shared slot, audio
and PEFA names are copied (harmless) and PELA files are left alone; the tool tells you.

OPTIONAL: MORE THAN 1000 SLOTS
ATOOL stops at slot 1000. The AToolSlotLimit mod (folder AToolSlotLimit, run
install-atool-limit.ps1) lifts that limit at runtime. It needs UE4SS and is built for the
UE4SS build the author uses; if it fails to load, skip it - SlotOrganizer then keeps
everything within 1..1000.

WHAT IT WILL NOT DO (it tells you instead of guessing)
  * legacy .pak-only mods (slot is stored inside the pak) - ask the author for an IoStore build
  * compressed containers, or moving a slot to a different digit count (98 -> 100)
  * touch mods that are not animation packs
If no free slot is left, or a pak cannot be rewritten safely, the clash is reported and left.

SAFETY NOTES
  * Close the game first; the tool refuses to write while it runs.
  * Backups and ledger live next to the exe (slot_backups, slot_owners.json, slot_cache.json).
  * Windows SmartScreen / antivirus may warn about unsigned one-file exes.
  * Vortex may show the *.orig files as external changes; do not delete them until you are
    happy with the result.
