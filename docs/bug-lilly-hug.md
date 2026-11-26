# Bug: Lilly Hug (Nexus 2088) loses Lily + mecha after SlotOrganizer moves its slot

Report: "After changing the animation slot, HD-EVE-Lilly-Hug's mounting character (Lily and her mecha) disappears."
Status: fixed in 1.0.1 (2026-11-26). Reproduced offline and in the real install, fixed after four independent review rounds, verified in game (Lily and her mecha appear after the move; Eve/Lily looked overlapped, animation data is byte-identical to the original so the tool did not change positions). Journals carry `unit`, not the `members` list that the design below mentions.

## What the mod ships (HD-EVE-Lilly-Hug-2088-1-0, ATOOL 3.0+ required)
One mod, THREE IoStore containers in one folder, all for ONE slot (201):

| container | packages | mount point |
|---|---|---|
| `HD-EVE-Lilly-Hug_P` | `anim/201.uasset` (main clip, Eve) | `.../anim/` |
| `HD-EVE-Lilly-Hug_ConfigAnim_P` | `anim/201a/1..4.uasset` (partner clips: Lily + mecha) | **`.../anim/201a/`** (the slot folder is baked into the mount point) |
| `HD-EVE-Lilly-Hug_Config_P` | `anim/201a.uasset` (partner table that points at 201a/*) | `.../anim/` |

The "a" suffix is the partner namespace: a main clip at slot N finds its partner at `Na`. Main, partner table and partner clips must always share N.

## Root causes (three, found in this order)
1. **No notion of "one mod = several containers".** The tool treats each container as independent. For Hug it reports the mod's own containers as clashing with each other and moves ONE container (newest, `_P`, 201 -> 202) while the other two stay on `201a`. Nothing exists at `202a`, so the engine finds no partner: Lily and the mecha do not spawn. Seen in the real run: `Hug_P: 201 -> 202` and the conflict mod `201 -> 200`, nothing else moved.
2. **The partner table is invisible.** `pak_slots` matches `anim/201a/...` and `anim/201.`, but not `anim/201a.uasset`, so `Config_P` is never inventoried (and never a move candidate).
3. **Hidden second bug, found while designing: `ConfigAnim_P` cannot be re-slotted at all.** `iostore._rename_dirindex` only renames directory entries below the mount point and files at `anim/`. When the slot folder is baked into the mount point (`.../anim/201a/`), package ids are renamed but the directory index still says `201a/N`, so `check_container` refuses ("chunk 4: id is not the hash of its path ...201a/4"). So even with perfect grouping the move would be refused for this mod. Verified: `_P` OK, `Config_P` OK (becomes `202a`), `ConfigAnim_P` REFUSED.
   Feasibility check (scratch copy only): rewriting the mount point (`anim/201a/` -> `anim/202a/`, same length so every offset stays) makes all three containers rename, re-read from bytes and pass `check_container`, sizes unchanged.

## Fix design

### A. `iostore.py`: mount-point slot folder
- In `_rename_dirindex`, first `di["mount"] = re.sub(r"(?i)(/hd-atool_p/anim/)<old>(a?)(/|$)", ...)`. Exactly the folder segment, never a substring of another number. The digit-count guard in `try_rename` already guarantees equal length, so the TOC size and offsets do not change.
- `slots_in` / `path_names` already use `mount + path`, so detection keeps working.
- Tests: synthetic container with the slot in the mount; renamed result re-read from bytes passes `check_container`; `old` gone, `new` present; the same for `N` (not `Na`) mounts.

### B. `slots.py`: see the table
- `pak_slots`: also match a top-level `anim/<N>a.uasset` (and `<N>a.` bulk). Add a regression test on the real Hug file layout (synthetic names).
- **Scan cache version bump.** `slot_cache.json` is keyed by size+mtime, so a cached empty result for `Config_P` would survive the upgrade and the table would stay invisible. Add `"v": 2` to the cache file; any other version -> rebuild. (Same for users upgrading from 1.0.0.)

### C. `slots.py`: units
- **Unit** = the mod a container belongs to: Vortex deployment manifest source if known (`sources(paks)`), else the container's parent folder when that folder is not `~mods` itself (flat installs fall back to the container's own name stem group, see risk below).
- Build `units = {unit: {containers}}` and `unit_slots = {unit: {slot: [containers]}}`.
- **Clash** = a slot held by 2+ DIFFERENT units. Containers of one unit never clash with each other. `scan`, the `clash slot N:` lines and the exit code use units; the printed holder list shows the unit with its container count (`HD-EVE-Lilly-Hug (3 containers)`).
- Container-id clashes stay per container (unchanged).

### D. Moving a unit atomically
- `plan_moves` works on units: for the clash on slot N, candidates are units (newest first, never LogicMods, last holder keeps the slot). Free slot M must be free for the whole unit (all its slots), same digit count.
- Before touching disk: `try_rename` (dry run in memory) for EVERY container of the unit that holds N. Any refusal -> the whole unit is not moved, reason reported per container (`Hug: ConfigAnim_P refused: ...`), next candidate unit is tried.
- `apply_move` becomes `apply_unit_move`: applies the containers one after another under one run, each with its own journal as today, but:
  - if container k fails, the earlier containers of THIS unit are reverted immediately (`revert_move` on their journals) so the unit is never left half moved;
  - external slot-keyed files (audio wav, PEFA names, PELA json) are moved ONCE per unit, with the first container, not once per container (otherwise names.txt lines are edited twice);
  - the journal `manifest.json` gets `"unit": <name>` and `"members": [...]` so `revert` and the log show the grouping.
- `--pak` (manual move): accept any container of the unit and move the whole unit; print which containers went along.
- Refuse, with a reason, when the unit is split across mods: another unit holds the same slot's other half in an unrelated container (e.g. `Na` only). No half moves.

### E. Self-check and observability (AGENTS.md rule)
- After apply, re-scan the touched containers: every container of the unit reports M and none reports N. If not: print the log path, revert the unit, exit non-zero.
- One log/console line per unit: `unit HD-EVE-Lilly-Hug: 3 containers slot 201 -> 202 (ConfigAnim_P, Config_P, _P)`; refusals log numbers and reasons.
- README gets a short "what counts as one mod" paragraph in the "If something goes wrong" section; CHANGELOG 1.0.1 entry.

### F. Tests (extend `tests/slots_test.py`, `tests/iostore_test.py`)
1. Synthetic Hug-shaped unit (3 containers, mount-point folder, table) + a second mod on 201: no self clash, table counted, all three move to the same M, consistent afterwards, `revert` restores all three byte for byte.
2. One container of the unit unrewritable -> nothing changes, reason names the container.
3. Failure injected on container 2 of 3 -> container 1 is rolled back.
4. Cache v1 file with a stale empty `Config_P` entry -> rebuilt, table seen.
5. External files moved once per unit (names.txt line moved once, not twice).
6. Flat install (all three containers directly in `~mods`) still groups (see risk).
7. Existing single-container behaviour unchanged (all current tests pass untouched).

### Risks and open choices
- **Flat installs** (three containers directly in `~mods`, no subfolder): folder gives no unit. Plan: group containers whose packages are `N`, `Na`, `Na/*` for the same N AND whose file names share a stem prefix up to the last `_` suffix group (`HD-EVE-Lilly-Hug_`). If the stem rule is not unambiguous the tool does not move and reports "cannot tell which containers belong together" (safe). Decide whether the stem rule is worth it or flat installs just report.
- A mod where the main clip is at N but the partner set is at a different number (not seen; ATOOL docs say `Na`): left as separate units.
- ATOOL slot above 1000 stays gated by the AToolSlotLimit rule, unchanged.
- Release: 1.0.1 with the fixed zip, hashes, GitHub release, Nexus file update. In game test needed before release (see below).

### Order of work
1. A + tests (smallest, proves the Hug container can move).
2. B (+ cache bump) + tests.
3. C + D + E + tests.
4. Dry run on the real install, you re-test (steps below), then docs and 1.0.1.

## Manual test path (you, before and after the fix)
Files: `D:\Projects\sb-slot-organizer\tmp\hug-test\ZZ-SlotConflict-Test-v1.zip` (conflict mod: a copy of Hug's clip on slot 201, own container id, dated 2024) and the Hug zip in `D:\Modding\downloads\stellarblade`.
1. Vortex: install the conflict mod FIRST, then Hug (Hug must be newer). Deploy with the game closed.
2. Run SlotOrganizer. Before the fix: only `Hug_P: 201 -> 202` (bug). After the fix: one unit move, 3 containers together.
3. Start the game, trigger the Hug animation: before the fix Lily and the mecha are missing; after the fix they must appear.
4. Cleanup: `Undo-last-run.bat`, uninstall both mods in Vortex, deploy.
