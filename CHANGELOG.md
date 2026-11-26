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

## 1.0.0 - release hardening
- Bulk data (.ubulk) of a moved package follows it (chunk id, directory entry, check); legacy .pak mods get a clear message.
- CityHash64 known-answer vectors (real stored hashes, 65..232 B incl. 128/192) in the tests.
- `auto` command (double-click): moves slots and fixes container ids, asking first; --yes, --version; first-run note when no mod manager manifest exists.
- End-to-end test: auto + revert on a fake game folder.
- release.ps1, README-USER.txt, install-atool-limit.ps1.

## 1.0.0 - pre-release review fixes
- auto applies container-id fixes first, then slot moves, under ONE run stamp; revert undoes both (moves newest first, then ids) and exits non-zero with a clear message if any file could not be restored.
- Double-click: errors and SystemExit messages are printed and the window waits; journals/ledger/cache go to %LOCALAPPDATA%\SlotOrganizer for the exe, read-only locations no longer crash scan; asks for the game folder once when it is not on Steam (remembered in game.txt); accepts the StellarBlade root as well as SB.
- Temp containers are named x.utoc.new / x.ucas.new (never mountable) and swept before applying; journals mark done, an unfinished one (crash) blocks applying until revert.
- Game-running check repeats after the prompt; auto passes --ceiling/--no-cache; reserved.txt default is next to the exe; cache of the wrong shape is ignored.
- Bulk data of other kinds (.uptnl, .m.ubulk) follows its package and is checked; renamed bulk chunks keep their stored hash.
- Known-answer CityHash64 vectors for every branch (1..64 B and 65..232 B), unconditional.
- install-atool-limit: never overwrites config/enabled, both UE4SS layouts, verifies the copy, .bat wrapper; release.ps1 ships canonical config, checks the built exe version and the dll.

## 1.0.0 - round 4 review fixes
- The temp sweep only removes this tool's own names (x.utoc.new / x.ucas.new); a mod literally named X.new.utoc is never touched or hidden from scan.
- Patching a container id keeps the files' modified times, so reverting an earlier slot move of the same pak still recognises the file (chained runs revert cleanly).
- id journals carry a done flag and an interrupted id patch is flagged like an interrupted move; apply_fix rolls back on Ctrl-C too; orphan or truncated paks are skipped instead of crashing.
- An interrupted run can be undone from the double-click window (offered by auto) or with Undo-last-run.bat.
- .m.ubulk is parsed correctly (longest extension first); printing paths with odd characters cannot crash; Steam library paths are read as UTF-8.
- install-atool-limit uses -LiteralPath; release.ps1 now throws on any failed step, smoke-tests the built exe, removes stale zips and verifies the zip contents.
## 1.0.0 - support log and license
- Every run writes a support log (%LOCALAPPDATA%\SlotOrganizer\logs\slotorganizer.log, rotated at 512 KB); failures print its path; `SlotOrganizer.exe log` shows it.
- MIT LICENSE, NOTICE.txt (CityHash MIT notice, bundled runtime, not-affiliated statement), credits in README-USER; zip ships LICENSE and NOTICE.txt.

## 1.0.0 - UE4SS compatibility check
- Symbol comparison of AToolSlotLimit's 20 UE4SS imports: RevOG SB-UE4SS 1.3 (the installed build, UE4SS.log 'v3.0.1 Beta, Git SHA 08a0733') resolves all; SB-UE4SS 3.1.6 and Chrisr0/RE-UE4SS 3.1.0-5 each miss 5 CppUserModBase exports (on_lua_start/on_lua_stop/on_cpp_mods_loaded), so the DLL cannot load there.
- detect_ceiling only raises the ceiling above 1000 when the installed UE4SS.dll hash is a verified build; install-atool-limit.ps1 warns on unverified builds (-Force to skip).

## 1.0.0 - review of the UE4SS check
- install-atool-limit.ps1 now fails closed without a console (empty answer = no).
- A forced --ceiling above what will work warns that those clips would not show up; the unverified-build note prints once per run (auto calls main twice).
- `log` prints to the real stdout so it no longer appends itself to the log; the unexpected-error message includes the log path.
- Docs: privacy wording (paths can include your Windows user name), not-tested-in-game wording for other UE4SS builds, Chrisr0 3.1.0-5 check now cites its source and hash, PSF/bundled runtime notice, uploads-not-copies wording.

## 1.0.0 - Chrisr0 build in the package
- The package carries two AToolSlotLimit builds (builds/revog-1.3, builds/chrisr0-3.1.0); install-atool-limit picks one by the UE4SS.dll hash (Chrisr0 line: asks first, untested). slots.py knows the three Chrisr0 hashes as UNTESTED_UE4SS: it names them and keeps the ceiling at 1000 until an in-game test moves them to KNOWN_UE4SS. release.ps1 packages both DLLs and checks the zip.

## tools/make_test_clip.py
- Makes a test copy of an anim pak at another slot (digit count may change) with a fresh container id; source only read. Used by the Chrisr0 in-game test plan.

## 1.0.0 - review of the Chrisr0 build
- install-atool-limit: an unknown UE4SS is refused (no more silent RevOG fallback); -InstallUnverified is required and the text says it may crash the game; -Force only skips the untested-Chrisr0 question. Wording fixed everywhere: a DLL on the wrong UE4SS may fail to load or crash (the names can resolve while the function table differs). Never mix builds.
- release.ps1 asserts the RevOG DLL imports on_cpp_mods_loaded and the Chrisr0 DLL does not, so a stale or swapped DLL cannot ship; the Chrisr0 build script deletes stale outputs first.
- Test: the installer's hash table must equal KNOWN_UE4SS + UNTESTED_UE4SS. NOTICE names the UE4SS copyright and the Chrisr0 fork. 'would NOT show up' is now 'may not show up'.

## Digit-count re-slot: partner table fix (found in the Chrisr0 test, Run A)
- A clip re-slotted 982 -> 1001 played, but Adam was missing: PEFA read 1 row in the 1001 partner table instead of 2. Cause: the slot string inside the DataTable rows grew by one character, but the enclosing StrProperty tag Size did not, so the engine lost its place and dropped the second (Adam) row. Same-digit moves never change string lengths, which is why moveslots (which refuses digit changes) was not affected.
- iostore._fix_strings now patches the StrProperty tag Size when a string changes length and raises Unsupported if it cannot find that tag (never writes a stale Size). Tests: tagged-row walk, untagged refusal, same-digit layout unchanged.
- try_rename still refuses digit-count changes until a corrected 1001 clip is verified in game (Adam visible).
