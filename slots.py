"""Scan installed Stellar Blade anim paks for ATOOL slot use. Stdlib only."""
import struct, re, pathlib, collections, sys, os
HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))

SLOT_RE = re.compile(r"/Game/Mods/HD-ATOOL_P/anim/(\d+)(?:a)?[/.]", re.I)

def fstr(b, o):
    n = struct.unpack_from("<i", b, o)[0]; o += 4
    if n == 0: return "", o
    if n < 0:
        n = -n; return b[o:o + 2 * n].decode("utf-16-le", "replace").rstrip("\0"), o + 2 * n
    return b[o:o + n].decode("latin-1").rstrip("\0"), o + n

def utoc_paths(b):
    # ponytail: mount-point search instead of a full TOC header parser (same trick as the port repo's _utoc.py)
    for m in re.finditer(rb"\.\./\.\./\.\./", b):
        o = m.start() - 4
        try:
            mount, o = fstr(b, o)
            nd = struct.unpack_from("<I", b, o)[0]; o += 4
            if not 0 < nd < 200000: continue
            dirs = [struct.unpack_from("<IIII", b, o + 16 * i) for i in range(nd)]; o += 16 * nd
            nf = struct.unpack_from("<I", b, o)[0]; o += 4
            if not 0 <= nf < 500000: continue
            files = [struct.unpack_from("<III", b, o + 12 * i) for i in range(nf)]; o += 12 * nf
            ns = struct.unpack_from("<I", b, o)[0]; o += 4
            if not 0 < ns < 500000: continue
            strs = []
            for _ in range(ns):
                s, o = fstr(b, o); strs.append(s)
        except (struct.error, IndexError, UnicodeDecodeError):
            continue
        NONE = 0xFFFFFFFF; out = []
        def walk(di, prefix, depth=0):
            while di != NONE and depth < 64:
                name, child, sib, ff = dirs[di]
                path = prefix + (strs[name] + "/" if name != NONE else "")
                f = ff
                while f != NONE:
                    out.append(mount + path + strs[files[f][0]]); f = files[f][1]
                walk(child, path, depth + 1); di = sib
        try: walk(0, ""); return out
        except IndexError: continue
    return None

def pak_slots(path):
    """slots a .utoc/.pak ships under anim/<slot>"""
    b = pathlib.Path(path).read_bytes()
    paths = utoc_paths(b) if str(path).lower().endswith(".utoc") else None
    if paths is None: paths = [s.decode("latin-1") for s in re.findall(rb"[\x21-\x7e]{8,300}", b)]
    out = set()
    for p in paths:
        p = p.replace("\\", "/")
        m = re.search(r"Mods/HD-ATOOL_P/anim/(\d+)a?/", p + "/", re.I) or re.search(r"Mods/HD-ATOOL_P/anim/(\d+)\.", p, re.I)
        if m: out.add(int(m.group(1)))
    return out

def find_game(arg=None):
    """game's SB folder: --game, $SB_GAME, then Steam libraries. ponytail: no Epic/GOG detection"""
    import os, json
    if arg: return pathlib.Path(arg) if (pathlib.Path(arg) / "Content" / "Paks").is_dir() else None     # an explicit --game never falls back to another install
    for c in [os.environ.get("SB_GAME")]:
        if c and (pathlib.Path(c) / "Content" / "Paks").is_dir(): return pathlib.Path(c)
    roots = []
    try:
        import winreg
        roots.append(winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"), "SteamPath")[0])
    except Exception: pass
    roots += [r"C:\Program Files (x86)\Steam"]
    libs = []
    for r in roots:
        v = pathlib.Path(r) / "steamapps" / "libraryfolders.vdf"
        libs.append(r)
        if v.exists(): libs += [m.replace("\\\\", "\\") for m in re.findall(r'"path"\s+"([^"]+)"', v.read_text(errors="replace"))]
    for l in libs:
        g = pathlib.Path(l) / "steamapps" / "common" / "StellarBlade" / "SB"
        if (g / "Content" / "Paks").is_dir(): return g
    return None

def scan(root, cache_file=None):
    """{pak path rel to root: sorted slots}. cache: a pak is re-read only when its size or mtime changed"""
    import json
    cache = {}
    if cache_file and pathlib.Path(cache_file).exists():
        try: cache = json.loads(pathlib.Path(cache_file).read_text())
        except ValueError: cache = {}          # corrupt cache: rebuild, never fatal
    inv, new, hits = {}, {}, 0
    for p in sorted(pathlib.Path(root).rglob("*")):
        e = p.suffix.lower()
        if p.stem.endswith(".new") or e not in (".utoc", ".pak") or not p.is_file() or (e == ".pak" and p.with_suffix(".utoc").exists()): continue
        st = p.stat(); key = str(p.relative_to(root)).replace("\\", "/"); sig = [st.st_size, int(st.st_mtime)]
        c = cache.get(key)
        if c and c["sig"] == sig: slots = c["slots"]; hits += 1
        else: slots = sorted(pak_slots(p))
        new[key] = {"sig": sig, "slots": slots}
        if slots: inv[key] = slots
    if cache_file: pathlib.Path(cache_file).write_text(json.dumps(new))
    scan.hits = hits
    return inv

def container_ids(root):
    """{utoc path rel to root: IoStore container id}: u64 at offset 56 of the TOC header. Two containers with the same id: only one mounts."""
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*.utoc")):
        if p.stem.endswith(".new"): continue
        with open(p, "rb") as f: h = f.read(64)
        if len(h) == 64 and h[:16] == b"-==--==--==--==-": out[str(p.relative_to(root)).replace("\\", "/")] = struct.unpack_from("<Q", h, 56)[0]
    return out

def id_clashes(root):
    by = collections.defaultdict(list)
    for k, v in container_ids(root).items(): by[v].append(k)
    return {v: ks for v, ks in by.items() if len(ks) > 1}

def detect_ceiling(game):
    """highest usable slot: 1000 (ATOOL's own loop bound), or the `limit=` of the AToolSlotLimit mod when it is installed and enabled"""
    d = pathlib.Path(game) / "Binaries" / "Win64" / "ue4ss" / "Mods" / "AToolSlotLimit"
    en = d / "enabled.txt"
    if not (d / "dlls" / "main.dll").is_file() or (en.is_file() and en.read_text(errors="replace").strip() == "0"): return 1000
    lim = 9999
    try:
        for l in (d / "config.txt").read_text(errors="replace").splitlines():
            if l.strip().startswith("limit="): lim = int(l.split("=", 1)[1])
    except (OSError, ValueError): pass
    return max(1000, lim)                            # limit=1000 means "leave ATOOL as is"

def load_reserved(path):
    """reserved.txt: one slot or range (901-907) per line, # comments. Missing file -> the known fixed slots (Tachy face scenes)."""
    p = pathlib.Path(path)
    if not p.is_file(): return set(range(901, 908))
    out = set()
    for l in p.read_text(errors="replace").splitlines():
        l = l.split("#")[0].strip()
        if not l: continue
        a, _, b = l.partition("-")
        try: out |= set(range(int(a), int(b or a) + 1))
        except ValueError: pass
    return out

def clashes(inv):
    by = collections.defaultdict(list)
    for k, v in inv.items():
        for s in v: by[s].append(k)
    return {s: p for s, p in by.items() if len(p) > 1}

def plan(inv, ceiling=1000, pinned=lambda k: k.lower().startswith("logicmods/"), reserved=()):
    """proposed moves [(pak, old, new)]: a pak loses a clashing/out-of-range slot unless pinned. Deterministic (pak name order)."""
    used = {s for v in inv.values() for s in v} | set(reserved)
    owner = {}; moves = []; free = (s for s in range(1, ceiling + 1) if s not in used); lost = []
    for k in sorted(inv, key=lambda k: (not pinned(k), k)):
        for s in inv[k]:
            if s > ceiling or s in owner: lost.append((k, s))
            else: owner[s] = k
    for k, s in lost:
        n = next(free, None)
        if n is None: raise SystemExit("no free slot <= %d left (%d clips cannot be placed)" % (ceiling, len(lost)))
        moves.append((k, s, n))
    return moves

# ---- fix container-id clashes (only anim paks are touched; third-party non-anim paks never are)
def id_sites(utoc):
    """where one container id lives: utoc header (+56), the ContainerHeader chunk id in the TOC, and the first 8 bytes of that chunk in the .ucas.
    Returns None unless all three agree and the chunk is stored uncompressed (compression block method 0)."""
    b = pathlib.Path(utoc).read_bytes()
    if b[:16] != b"-==--==--==--==-": return None
    ec, cbc = struct.unpack_from("<2I", b, 24); bs = struct.unpack_from("<I", b, 44)[0]
    cid = struct.unpack_from("<Q", b, 56)[0]
    o_ids = 144; o_off = o_ids + ec * 12; o_blk = o_off + ec * 10
    for i in range(ec):
        cidc, _, _, typ = struct.unpack_from("<QHBB", b, o_ids + 12 * i)
        if typ != 10: continue                                  # 10 = ContainerHeader
        off = int.from_bytes(b[o_off + 10 * i:o_off + 10 * i + 5], "big")
        pb = o_blk + 12 * (off // bs)
        method = b[pb + 11]; po = int.from_bytes(b[pb:pb + 5], "little") + off % bs
        u = pathlib.Path(str(utoc)[:-5] + ".ucas")
        with open(u, "rb") as f: f.seek(po); head = f.read(8)
        if cidc == cid and struct.unpack("<Q", head)[0] == cid and method == 0:
            return {"utoc": str(utoc), "ucas": str(u), "id": cid, "toc_chunk_off": o_ids + 12 * i, "ucas_off": po}
    return None

def new_id(path, taken):
    import hashlib
    n = 0
    while True:
        v = int.from_bytes(hashlib.sha1((path + str(n)).encode()).digest()[:8], "little")
        if v not in taken and v: return v
        n += 1

def plan_fix(root, inv):
    """[(pak rel, old id, new id)]: for every clash group, anim paks that are not the first of the group get a new unique id"""
    ids = container_ids(root); taken = set(ids.values()); out = []
    anim = {k.replace("\\", "/") for k in inv}
    for cid, ks in sorted(id_clashes(root).items()):
        ks = sorted(ks); an = [k for k in ks if k in anim]
        mov = an if len(an) < len(ks) else ks[1:]       # a non-anim pak is in the group: leave it, move the anim ones; all anim: keep the first
        for k in mov:
            n = new_id(k, taken); taken.add(n); out.append((k, cid, n))
    return out

def apply_fix(root, fixes, backup):
    """patch the three sites; keep the old bytes in backup/manifest.json. Returns (done, skipped[(pak, why)]). Rolls back on any error."""
    import json
    root = pathlib.Path(root); backup = pathlib.Path(backup); backup.mkdir(parents=True, exist_ok=True)
    man, skipped = [], []
    for k, old, new in fixes:
        sites = id_sites(root / k)
        if not sites or sites["id"] != old: skipped.append((k, "id sites differ or chunk is compressed")); continue
        if not (_lock_ok(sites["utoc"]) and _lock_ok(sites["ucas"])): skipped.append((k, "locked (game running?)")); continue
        man.append({"pak": k, "old": old, "new": new, **{x: sites[x] for x in ("utoc", "ucas", "toc_chunk_off", "ucas_off")}})
    _save_manifest(backup / "manifest.json", man)
    try:
        for m in man:
            with open(m["utoc"], "r+b") as f:
                f.seek(56); f.write(struct.pack("<Q", m["new"])); f.seek(m["toc_chunk_off"]); f.write(struct.pack("<Q", m["new"]))
            with open(m["ucas"], "r+b") as f: f.seek(m["ucas_off"]); f.write(struct.pack("<Q", m["new"]))
            s2 = id_sites(m["utoc"])
            if not s2 or s2["id"] != m["new"]: raise OSError("verify failed for %s" % m["pak"])
    except OSError as e:
        revert_fix(backup); raise SystemExit("container id patch failed (%s); everything written so far was rolled back" % e)
    return man, skipped

def revert_fix(backup):
    """put the old id back at each of the three sites that still holds our new id (works on half-patched containers); idempotent"""
    import json
    mp = pathlib.Path(backup) / "manifest.json"
    if not mp.exists(): return 0
    man = json.loads(mp.read_text()); n = 0
    for m in man:
        hit = False
        for path, off in ((m["utoc"], 56), (m["utoc"], m["toc_chunk_off"]), (m["ucas"], m["ucas_off"])):
            if not os.path.exists(path): continue
            with open(path, "r+b") as f:
                f.seek(off)
                if struct.unpack("<Q", f.read(8))[0] == m["new"]: f.seek(off); f.write(struct.pack("<Q", m["old"])); hit = True
        n += hit
    os.replace(mp, pathlib.Path(backup) / "manifest.reverted.json")
    return n

# ---- move a pak's clip to another slot (rewrites the IoStore container, see iostore.py)
def _save_manifest(path, j):
    import json
    t = str(path) + ".tmp"
    with open(t, "w", encoding="utf-8") as f: json.dump(j, f, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(t, path)

class _Steps(list):
    """journal steps: every append is flushed to the manifest immediately"""
    def __init__(self, j, path): super().__init__(); self.j, self.path = j, path
    def append(self, x): super().append(x); self.j["steps"] = list(self); _save_manifest(self.path, self.j)

def _lock_ok(p):
    try:
        with open(p, "r+b"): return True
    except OSError: return False

def try_rename(root, key, old, new):
    """dry run on an in-memory copy -> (container, None) or (None, reason)"""
    import iostore
    try:
        c = iostore.read_container(pathlib.Path(root) / key)
        if old not in iostore.slots_in(c): return None, "slot %d is not a clip package of this pak" % old
        if len(str(new)) != len(str(old)): return None, "changing the digit count (%d -> %d) is not verified in game" % (old, new)
        iostore.rename_slot(c, old, new)
        bad = iostore.check_container(c)
        if bad: return None, "consistency check failed: " + bad[0]
        return c, None
    except iostore.Unsupported as e: return None, str(e)
    except (OSError, struct.error, IndexError, ValueError) as e: return None, "unreadable: %s" % e

def free_slot(old, used, ceiling, reserved):
    """nearest free slot above `old`, then below, within 1..ceiling"""
    for d in range(1, ceiling + 1):
        for s in (old + d, old - d):
            if 1 <= s <= ceiling and s not in used and s not in reserved: return s
    return None

def plan_moves(root, inv, ceiling=1000, reserved=(), mtimes=None):
    """-> (moves [(pak, old, new)], unresolved [(slot, paks, reasons)]). Per clash: never LogicMods; try the newer pak first, then the other; first one whose rewrite verifies wins."""
    used = {s for v in inv.values() for s in v} | set(reserved); moves = []; unresolved = []
    mt = mtimes or {k: (pathlib.Path(root) / k).stat().st_mtime for k in inv}
    for slot, paks in sorted(clashes(inv).items()):
        cand = sorted([k for k in paks if not k.lower().startswith("logicmods/")], key=lambda k: -mt.get(k, 0)); reasons = []; remaining = list(paks)
        for k in cand:                                   # newest first; the last holder left keeps the slot
            if len(remaining) == 1: break
            new = free_slot(slot, used, ceiling, reserved)
            if new is None: reasons.append("%s: no free slot <= %d" % (k, ceiling)); continue
            c, why = try_rename(root, k, slot, new)
            if c is None: reasons.append("%s: %s" % (k, why)); continue
            moves.append((k, slot, new)); used.add(new); remaining.remove(k)
        if len(remaining) > 1: unresolved.append((slot, remaining, reasons or ["only LogicMods packs involved"]))
    return moves, unresolved

def sources(paks):
    """{normalized absolute path: source mod} from Vortex deployment manifests under Paks (empty if Vortex is not used)"""
    import json
    out = {}
    for m in pathlib.Path(paks).rglob("vortex.deployment.*.json"):
        try: j = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, ValueError): continue
        base = pathlib.Path(j.get("targetPath") or m.parent)
        for f in j.get("files", []):
            if f.get("relPath") and f.get("source"): out[os.path.normcase(str(base / (f.get("target") or "") / f["relPath"]))] = f["source"]
    return out

def owner(path, mover, srcs, shared):
    """who a slot-keyed file belongs to, as seen from the pak being moved: 'mine' | 'theirs' | 'unknown'.
    Known from Vortex's manifest (same source mod as the pak = mine); without it a slot used by only this pak is mine, a shared one is unknown."""
    own = srcs.get(os.path.normcase(str(path)))
    if own and mover:
        if own.startswith("pak:") != mover.startswith("pak:"): return "unknown"     # one side from Vortex, the other from the ledger: not comparable
        return "mine" if own == mover else "theirs"
    return "unknown" if shared else "mine"

def _pela_slots(doc):
    out = set()
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "clip" and isinstance(v, int): out.add(v)
                elif k == "singles" and isinstance(v, list): out.update(x for x in v if isinstance(x, int))
                else: walk(v)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(doc); return out

def ledger_update(game, inv, path):
    """First-sight ownership for installs without Vortex: while a slot is held by ONE pak, remember that pak as the owner of the slot's wav /
    PELA file. Later, when another pak claims the slot, the ledger still says who the files belonged to. Returns {normalized path: 'pak:<key>'}."""
    import json
    game = pathlib.Path(game); path = pathlib.Path(path)
    try: old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError): old = {}
    holders = collections.defaultdict(list)
    for k, v in inv.items():
        for sl in v: holders[sl].append(k)
    led = {}
    for pth, who in old.items():                        # keep what is still true: file exists, owner still in the install
        if os.path.exists(pth) and who[4:] in inv: led[pth] = who
    audio = game / "Content" / "Paks" / "LogicMods" / "HD-ATOOL_P" / "audio"
    for f in (audio.iterdir() if audio.is_dir() else []):
        if f.suffix.lower() == ".wav" and f.stem.isdigit() and len(holders.get(int(f.stem), [])) == 1:
            led.setdefault(os.path.normcase(str(f)), "pak:" + holders[int(f.stem)][0])
    pela = game / "Content" / "Paks" / "~mods" / "PELA Patches"
    for f in sorted(pela.glob("*.json")) if pela.is_dir() else []:
        try: sl = _pela_slots(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError): continue
        h = {holders[x][0] for x in sl if len(holders.get(x, [])) == 1}
        if len(h) == 1: led.setdefault(os.path.normcase(str(f)), "pak:" + next(iter(h)))
    if led != old: path.write_text(json.dumps(led, indent=1), encoding="utf-8")
    return led

def external_files(game, old, new, apply_to=None, backup=None, shared=False, mover=None, srcs=None):
    """slot-keyed files outside the pak. Returns a list of (what, path); with backup set, edits them (originals saved).
    mine -> renamed/rewritten; theirs -> left alone; unknown -> wav and PEFA name are COPIED to the new slot (harmless), PELA left alone."""
    import json, shutil
    game = pathlib.Path(game); out = []; srcs = srcs or {}
    def save(p):
        fd = pathlib.Path(backup) / "files"; fd.mkdir(parents=True, exist_ok=True)
        d = fd / ("%d" % len(list(fd.iterdir()))); d.mkdir()                # unique per saved file, even across calls into one journal
        shutil.copy2(p, d / p.name); return d / p.name
    audio = game / "Content" / "Paks" / "LogicMods" / "HD-ATOOL_P" / "audio"
    for p in (audio.glob("%d.*" % old) if audio.is_dir() else []):
        if p.suffix.lower() == ".wav" and p.stem == str(old):
            dst = p.with_name("%d%s" % (new, p.suffix)); who = owner(p, mover, srcs, shared)
            if who == "theirs": out.append(("note: %s kept (belongs to another mod)" % p.name, p)); continue
            if dst.exists(): out.append(("wav not moved: %s exists" % dst.name, p)); continue
            if who == "mine":
                out.append(("wav %s -> %s" % (p.name, dst.name), p))
                if backup: p.rename(dst); apply_to is not None and apply_to.append({"kind": "rename", "from": str(p), "to": str(dst)})
            else:
                out.append(("wav %s copied to %s (owner unknown, slot shared)" % (p.name, dst.name), p))
                if backup: shutil.copy2(p, dst); apply_to is not None and apply_to.append({"kind": "copy", "to": str(dst)})
    pefa = game / "Binaries" / "Win64" / "ue4ss" / "Mods" / "PEFA"
    names = pefa / "names.txt"
    if names.is_file():
        txt = names.read_text(encoding="utf-8", errors="replace"); m = re.search(r"(?m)^%d(\s*=.*)$" % old, txt)
        if m and not re.search(r"(?m)^%d\s*=" % new, txt):
            if shared:                                              # PEFA's names.txt has no owner: keep the old line, add one for the new slot
                out.append(("PEFA names.txt: line %d copied to %d (slot shared)" % (old, new), names)); edit = lambda t: re.sub(r"(?m)^(%d)(\s*=.*)$" % old, lambda mm: mm.group(0) + "\n" + str(new) + mm.group(2), t, count=1)
            else:
                out.append(("PEFA names.txt line %d -> %d" % (old, new), names)); edit = lambda t: re.sub(r"(?m)^%d(\s*=)" % old, lambda mm: str(new) + mm.group(1), t)
            if backup:
                b = save(names); apply_to.append({"kind": "file", "path": str(names), "backup": str(b)}); names.write_text(edit(txt), encoding="utf-8", newline="")
    for nm in ("packs_rows.txt", "packs_cache.txt"):
        p = pefa / nm
        if p.is_file():
            out.append(("PEFA cache %s deleted (PEFA rebuilds it)" % nm, p))
            if backup: b = save(p); apply_to.append({"kind": "file", "path": str(p), "backup": str(b)}); p.unlink()
    pela = game / "Content" / "Paks" / "~mods" / "PELA Patches"
    for p in sorted(pela.glob("*.json")) if pela.is_dir() else []:
        try: doc = json.loads(p.read_text(encoding="utf-8"))
        except ValueError: continue
        hit = [0]
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "clip" and v == old: o[k] = new; hit[0] += 1
                    elif k == "singles" and isinstance(v, list):
                        for i, x in enumerate(v):
                            if x == old: v[i] = new; hit[0] += 1
                    else: walk(v)
            elif isinstance(o, list):
                for x in o: walk(x)
        walk(doc)
        if not hit[0]: continue
        who = owner(p, mover, srcs, shared)
        if who != "mine": out.append(("note: PELA %s keeps %d reference(s) to slot %d (%s)" % (p.name, hit[0], old, "belongs to another mod" if who == "theirs" else "owner unknown, slot shared"), p)); continue
        out.append(("PELA %s: %d reference(s)" % (p.name, hit[0]), p))
        if backup:
            b = save(p); apply_to.append({"kind": "file", "path": str(p), "backup": str(b)})
            p.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return out

def apply_move(root, game, key, old, new, backup, shared=False, srcs=None):
    """rewrite the container of `key` (slot old -> new), swap it in, edit slot-keyed files. Every step is journaled BEFORE it happens
    (manifest rewritten atomically); any failure rolls back what was done. Returns the journal dict."""
    import iostore, shutil
    root = pathlib.Path(root); backup = pathlib.Path(backup); backup.mkdir(parents=True, exist_ok=True)
    c, why = try_rename(root, key, old, new)
    if c is None: raise SystemExit("cannot move %s: %s" % (key, why))
    utoc = root / key; ucas = pathlib.Path(str(utoc)[:-5] + ".ucas")
    for p in (utoc, ucas):
        if not _lock_ok(p): raise SystemExit("%s is locked (game running?)" % p.name)
    t, u = iostore.container_bytes(c)
    if shutil.disk_usage(root).free < len(t) + len(u) + (1 << 20): raise SystemExit("not enough free disk space for the rewritten container")
    nt = utoc.with_name(utoc.stem + ".new.utoc"); nu = utoc.with_name(utoc.stem + ".new.ucas")
    j = {"kind": "move", "pak": key, "old": old, "new": new, "steps": []}; mp = backup / "manifest.json"
    try:
        nt.write_bytes(t); nu.write_bytes(u)
        c2 = iostore.read_container(nt)                                 # verify what was written, not what we meant to write
        if iostore.check_container(c2) or new not in iostore.slots_in(c2) or old in iostore.slots_in(c2):
            raise SystemExit("verification of the rewritten container failed, nothing changed")
        _save_manifest(mp, j)
        sfx = ".orig"; k = 0
        while utoc.with_name(utoc.name + sfx).exists() or ucas.with_name(ucas.name + sfx).exists(): k += 1; sfx = ".orig%d" % k   # never overwrite an earlier backup (chained moves)
        bt = utoc.with_name(utoc.name + sfx); bu = ucas.with_name(ucas.name + sfx); steps = _Steps(j, mp)
        steps.append({"kind": "swap", "path": str(utoc), "backup": str(bt)}); os.replace(utoc, bt)      # originals renamed to *.orig next to the pak (same volume, instant, not mountable; a hard link to Vortex staging stays intact)
        steps.append({"kind": "swap", "path": str(ucas), "backup": str(bu)}); os.replace(ucas, bu)
        os.replace(nt, utoc); os.replace(nu, ucas)
        srcs = srcs if srcs is not None else sources(root)
        j["notes"] = [w for w, _p in external_files(game, old, new, steps, backup, shared, srcs.get(os.path.normcase(str(utoc))) or "pak:" + key, srcs)]
        _save_manifest(mp, j)
    except BaseException:
        for x in (nt, nu):
            try: x.unlink()
            except OSError: pass
        if mp.exists(): revert_move(backup)                             # roll back whatever was already done
        raise
    return j

def revert_move(backup):
    """undo a move journal: put the original files back, newest step first. Tolerates steps that never happened and repeated calls.
    Returns the number of steps undone."""
    import json, shutil
    backup = pathlib.Path(backup); mp = backup / "manifest.json"
    if not mp.exists(): return 0
    j = json.loads(mp.read_text()); n = 0
    for st in reversed(j["steps"]):
        if st["kind"] == "swap":
            if os.path.exists(st["backup"]): os.replace(st["backup"], st["path"]); n += 1
        elif st["kind"] == "rename":
            if pathlib.Path(st["to"]).exists() and not pathlib.Path(st["from"]).exists(): os.replace(st["to"], st["from"]); n += 1
        elif st["kind"] == "copy":
            if pathlib.Path(st["to"]).exists(): os.unlink(st["to"]); n += 1
        elif st["kind"] == "file":
            if os.path.exists(st["backup"]): shutil.copy2(st["backup"], st["path"]); n += 1
    os.replace(mp, backup / "manifest.reverted.json")
    return n

def main(argv):
    import argparse, time
    ap = argparse.ArgumentParser(prog="slots", description="Stellar Blade anim slot organizer (scan/plan only so far)")
    ap.add_argument("cmd", choices=["scan", "plan", "fixids", "moveslots", "revert"]); ap.add_argument("--game"); ap.add_argument("--ceiling", type=int, default=None, help="default: auto (1000, or the AToolSlotLimit limit)"); ap.add_argument("--reserved", default="reserved.txt")
    ap.add_argument("--apply", action="store_true", help="fixids/moveslots: really write (default: dry run)"); ap.add_argument("--pak", help="moveslots: move this pak (path relative to Paks, e.g. ~mods/BBS_P.utoc)"); ap.add_argument("--slot", type=int, help="moveslots --pak: the slot to move"); ap.add_argument("--to", type=int, help="moveslots --pak: the target slot"); ap.add_argument("--backup", default=os.path.join(HERE, "slot_backups")); ap.add_argument("--cache", default=os.path.join(HERE, "slot_cache.json")); ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args(argv); g = find_game(a.game)
    if not g: print("Stellar Blade not found; pass --game <...>\SB or set SB_GAME"); return 2
    if a.cmd == "revert":
        import glob
        ds = [d for d in glob.glob(a.backup + "/ids-*") + glob.glob(a.backup + "/move-*") if os.path.exists(d + "/manifest.json")]
        if not ds: print("nothing to revert in", a.backup); return 2
        ts = lambda d: re.search(r"(\d{8}-\d{6})", os.path.basename(d)).group(1)
        last = max(ts(d) for d in ds); grp = [d for d in ds if ts(d) == last]       # the newest run, its steps newest first
        grp.sort(key=lambda d: int(d.rsplit("-", 1)[1]) if os.path.basename(d).startswith("move-") else 0, reverse=True)
        for d in grp:
            if os.path.basename(d).startswith("move-"): print("undid %d step(s) of %s" % (revert_move(d), d))
            else: print("restored %d container id(s) from %s" % (revert_fix(d), d))
        return 0
    if a.ceiling is None: a.ceiling = detect_ceiling(g)
    t = time.time(); inv = scan(g / "Content" / "Paks", None if a.no_cache else a.cache)
    ledger = ledger_update(g, inv, os.path.join(os.path.dirname(os.path.abspath(a.cache)), "slot_owners.json"))
    ss = {s for v in inv.values() for s in v}; cl = clashes(inv)
    print("%d paks, %d slots, %d clashes, %d above %d, %d free <= %d  (%d cached, %.2fs)" % (len(inv), len(ss), len(cl), sum(s > a.ceiling for s in ss), a.ceiling, a.ceiling - len([s for s in ss if s <= a.ceiling]), a.ceiling, scan.hits, time.time() - t))
    for s, p in sorted(cl.items()): print("  clash slot %d: %s" % (s, " | ".join(p)))
    idc = id_clashes(g / "Content" / "Paks"); anim = {k.replace("\\", "/") for k in inv}
    hit = {v: ks for v, ks in idc.items() if any(k in anim for k in ks)}
    print("%d container-id clashes (%d involve anim paks: only one pak per id mounts, the other one's clips are unavailable)" % (len(idc), len(hit)))
    for v, ks in hit.items(): print("  id %#x: %s" % (v, " | ".join(ks)))
    cl = {**cl, **{("id", v): ks for v, ks in hit.items()}}
    if a.cmd == "fixids":
        import subprocess, time as _t
        fx = plan_fix(g / "Content" / "Paks", inv)
        for k, o, n in fx: print("  %s: id %#x -> %#x" % (k, o, n))
        if not fx: print("nothing to fix"); return 0
        if not a.apply: print("dry run: %d container id(s) would change (add --apply, close the game first)" % len(fx)); return 1
        if "SB-Win64-Shipping.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout: print("Stellar Blade is running: close it first"); return 2
        bk = "%s/ids-%s" % (a.backup, _t.strftime("%Y%m%d-%H%M%S")); print("game folder:", g)
        done, skipped = apply_fix(g / "Content" / "Paks", fx, bk)
        for k, why in skipped: print("  skipped %s: %s" % (k, why))
        print("changed %d container id(s); undo with: python slots.py revert (backup %s)" % (len(done), bk)); return 0
    if a.cmd == "moveslots":
        import subprocess, time as _t
        paks = g / "Content" / "Paks"; rs = load_reserved(a.reserved)
        if a.pak:
            if a.slot is None or a.to is None: print("--pak needs --slot and --to"); return 2
            kk = a.pak.replace(chr(92), "/")
            if kk not in inv: print("--pak %s is not an anim pak under %s (use the path shown by scan)" % (a.pak, paks)); return 2
            used = {x for v in inv.values() for x in v}
            if not (1 <= a.to <= a.ceiling) or a.to in rs or a.to in used: print("--to %d is not a free slot within 1..%d" % (a.to, a.ceiling)); return 2
            moves, unresolved = [(kk, a.slot, a.to)], []
        else: moves, unresolved = plan_moves(paks, inv, a.ceiling, rs)
        for slot, ps, why in unresolved:
            print("  slot %d cannot be fixed automatically (%s):" % (slot, " | ".join(ps)))
            for w in why: print("      " + w)
        srcs = {**ledger, **sources(paks)}                      # Vortex's word beats the ledger
        def shared(k, o): return any(o in v for kk, v in inv.items() if kk != k)
        def mover(k): return srcs.get(os.path.normcase(str(paks / k))) or "pak:" + k
        for k, o, n in moves:
            print("  %s: slot %d -> %d" % (k, o, n))
            for what, _p in external_files(g, o, n, shared=shared(k, o), mover=mover(k), srcs=srcs): print("      " + what)
        if not moves: print("nothing to move"); return 1 if unresolved else 0
        if not a.apply: print("dry run: %d move(s) (add --apply, close the game first)" % len(moves)); return 1
        if "SB-Win64-Shipping.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout: print("Stellar Blade is running: close it first"); return 2
        bk = "%s/move-%s" % (a.backup, _t.strftime("%Y%m%d-%H%M%S")); print("game folder:", g)
        for i, (k, o, n_) in enumerate(moves):
            jn = apply_move(paks, g, k, o, n_, "%s-%d" % (bk, i), shared=shared(k, o), srcs=srcs)
            for w in jn.get("notes", []): print("      " + w)
        print("moved %d slot(s); undo with: python slots.py revert (backup %s-*)" % (len(moves), bk)); return 0
    if a.cmd == "plan":
        mv = plan(inv, a.ceiling, reserved=load_reserved(a.reserved))
        for k, o, n in mv: print("  %s: %d -> %d" % (k, o, n))
        print("%d moves proposed (nothing is changed on disk yet)" % len(mv))
    return 1 if cl else 0

if __name__ == "__main__":
    dbl = len(sys.argv) == 1                         # double-clicked exe: show the report (fixids dry run) and wait
    rc = main(sys.argv[1:] or ["fixids"])
    if dbl and getattr(sys, "frozen", False):
        print()
        print("To apply the fix run in a terminal: SlotOrganizer.exe fixids --apply  (game closed). Undo: SlotOrganizer.exe revert")
        input("Press Enter to close")
    sys.exit(rc)
