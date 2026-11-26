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

## Slot-keyed files by owner
- moveslots reads Vortex deployment manifests to learn which mod owns each wav / PELA file. Same source mod as the moved pak: renamed/rewritten even if the slot is shared. Another mod: left alone. Unknown owner on a shared slot: wav and PEFA name are copied to the new slot (PELA left alone). Unshared slot: renamed as before.
- journal gained a copy step (reverted by deleting the copy); backup slots for saved files are unique per journal.

## Review fixes
- Journal written before each step, atomic manifest, rollback on any failure, revert is idempotent and tolerant of steps that never happened; revert picks the newest run and undoes its moves in numeric order; reverted manifests are renamed.
- revert_fix works per site (half-patched containers); apply_fix checks locks and rolls back.
- Temp *.new.* pairs are cleaned up and ignored by scan; free-space check; --pak/--to validated (must be a scanned pak, free slot within ceiling); LogicMods check is case-insensitive; explicit --game never falls back; backups/cache default next to the tool; game folder printed before applying.
- Moves refuse digit-count changes and packages with bulk chunks tied to a moved package.
- First-sight ownership ledger for installs without Vortex.

## Second review fixes
- revert never overwrites a file that changed since the tool wrote it (size+mtime recorded per step); such steps are reported and the run is kept as manifest.partial.json.
- ledger entries carry file size+mtime and drop when the file changed or the owner left; garbage/old-format ledgers are ignored; ledger written atomically.
- free_slot only offers slots with the same digit count (clashes at 9/99/999 resolve); wav rename/copy and file edits are journaled before they happen; names.txt edited as bytes (CRLF and odd bytes survive); PELA read with BOM tolerance.
- revert needs no game folder, refuses while the game runs, and handles odd backup paths; a failed batch says how many moves were applied; --pak dry run shows why a move is refused; all-skipped fixids leaves no journal; relative --game is resolved.
