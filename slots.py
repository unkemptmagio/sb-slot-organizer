"""Scan installed Stellar Blade anim paks for ATOOL slot use. Stdlib only."""
import struct, re, pathlib, collections, sys, os
VERSION = "1.0.1"
HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
# journals, ledger and cache live where they survive re-extracting a new release: %LOCALAPPDATA%\SlotOrganizer for the exe, the repo folder from source
DATA = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "SlotOrganizer") if getattr(sys, "frozen", False) else HERE


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
        m = re.search(r"Mods/HD-ATOOL_P/anim/(\d+)a?/", p + "/", re.I) or re.search(r"Mods/HD-ATOOL_P/anim/(\d+)a?\.", p, re.I)    # 201/..., 201a/..., 201.uasset and the partner TABLE 201a.uasset (Lilly-Hug's Config pak)
        if m: out.add(int(m.group(1)))
    return out

def _sb(p):
    """accept the SB folder or the StellarBlade root"""
    p = pathlib.Path(p)
    if (p / "Content" / "Paks").is_dir(): return p.resolve()
    if (p / "SB" / "Content" / "Paks").is_dir(): return (p / "SB").resolve()
    return None

def find_game(arg=None):
    """game's SB folder: --game, $SB_GAME, the remembered path (game.txt), then Steam libraries. ponytail: no Epic/GOG detection (the double-click flow asks once)"""
    import os, json
    if arg: return _sb(arg)                               # an explicit --game never falls back to another install
    c = os.environ.get("SB_GAME")
    if c:
        if _sb(c): return _sb(c)
        print("warning: SB_GAME=%s is not a Stellar Blade folder, ignored" % c)
    try: r = open(os.path.join(DATA, "game.txt"), encoding="utf-8").read().strip()
    except OSError: r = ""
    if r and _sb(r): return _sb(r)
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
        if v.exists(): libs += [m.replace("\\\\", "\\") for m in re.findall(r'"path"\s+"([^"]+)"', v.read_text(encoding="utf-8", errors="replace"))]
    for l in libs:
        g = pathlib.Path(l) / "steamapps" / "common" / "StellarBlade" / "SB"
        if (g / "Content" / "Paks").is_dir(): return g
    return None

CACHE_V = 2

def scan(root, cache_file=None):
    """{pak path rel to root: sorted slots}. cache: a pak is re-read only when its size or mtime changed"""
    import json
    cache = {}
    if cache_file and pathlib.Path(cache_file).exists():
        try: cache = json.loads(pathlib.Path(cache_file).read_text())
        except (OSError, ValueError): cache = {}          # corrupt cache: rebuild, never fatal
    if not isinstance(cache, dict) or cache.get("__v") != CACHE_V: cache = {}          # older cache = older slot detection (1.0.0 could not see 201a.uasset): rebuild
    inv, new, hits = {}, {"__v": CACHE_V}, 0
    for p in sorted(pathlib.Path(root).rglob("*")):
        e = p.suffix.lower()
        if e not in (".utoc", ".pak") or not p.is_file() or (e == ".pak" and p.with_suffix(".utoc").exists()): continue
        st = p.stat(); key = str(p.relative_to(root)).replace("\\", "/"); sig = [st.st_size, int(st.st_mtime)]
        c = cache.get(key)
        if isinstance(c, dict) and c.get("sig") == sig and isinstance(c.get("slots"), list): slots = c["slots"]; hits += 1
        else: slots = sorted(pak_slots(p))
        new[key] = {"sig": sig, "slots": slots}
        if slots: inv[key] = slots
    if cache_file:
        try: os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True); pathlib.Path(cache_file).write_text(json.dumps(new))
        except OSError: pass                              # read-only location: the cache is optional
    scan.hits = hits
    return inv

def container_ids(root):
    """{utoc path rel to root: IoStore container id}: u64 at offset 56 of the TOC header. Two containers with the same id: only one mounts."""
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*.utoc")):
        with open(p, "rb") as f: h = f.read(64)
        if len(h) == 64 and h[:16] == b"-==--==--==--==-": out[str(p.relative_to(root)).replace("\\", "/")] = struct.unpack_from("<Q", h, 56)[0]
    return out

def id_clashes(root):
    by = collections.defaultdict(list)
    for k, v in container_ids(root).items(): by[v].append(k)
    return {v: ks for v, ks in by.items() if len(ks) > 1}

# The ONE UE4SS build AToolSlotLimit's DLL was built for and tested with in game (2026-11-25): RevOG SB-UE4SS 1.3. Nothing else is supported.
KNOWN_UE4SS = {"E0CC51CE5B47D5BE82194510B0B4B4054DD15CE0322A983655A022F92D27DABE": "RevOG SB-UE4SS 1.3"}

def _ue4ss_hash(game):
    import hashlib
    w = pathlib.Path(game) / "Binaries" / "Win64"
    for c in (w / "ue4ss" / "UE4SS.dll", w / "UE4SS.dll"):
        if c.is_file():
            try: return hashlib.sha256(c.read_bytes()).hexdigest().upper()
            except OSError: return None
    return None

def ue4ss_build(game, known=None):
    """name of the installed UE4SS if it is one AToolSlotLimit is verified with in game, else None"""
    return (KNOWN_UE4SS if known is None else known).get(_ue4ss_hash(game))

def detect_ceiling(game, known=None):
    """highest usable slot: 1000 (ATOOL's own loop bound), or the `limit=` of the AToolSlotLimit mod when it is installed, enabled AND the
    installed UE4SS is a build it is verified with (otherwise the mod would not load and slots above 1000 would be invisible)"""
    d = pathlib.Path(game) / "Binaries" / "Win64" / "ue4ss" / "Mods" / "AToolSlotLimit"
    en = d / "enabled.txt"
    if not (d / "dlls" / "main.dll").is_file() or (en.is_file() and en.read_text(errors="replace").strip() == "0"): return 1000
    if not ue4ss_build(game, known): return 1000
    lim = 9999
    try:
        for l in (d / "config.txt").read_text(errors="replace").splitlines():
            if l.strip().startswith("limit="): lim = int(l.split("=", 1)[1])
    except (OSError, ValueError): pass
    return max(1000, lim)                            # limit=1000 means "leave ATOOL as is"

_NOTED = []; _IDENT = []

def identity_line(game, ceiling, explicit):
    """one line for the log: what this run is looking at (so a log from a 'nothing happened' run can be told from a wrong-install run)"""
    h = _ue4ss_hash(game); name = KNOWN_UE4SS.get(h) if h else None
    ue = "%s (the tested build)" % name if name else ("not the tested build, sha256 %s..." % h[:12] if h else "UE4SS.dll not found")
    d = pathlib.Path(game) / "Binaries" / "Win64" / "ue4ss" / "Mods" / "AToolSlotLimit"
    if (d / "dlls" / "main.dll").is_file():
        en = d / "enabled.txt"; mod = "installed, " + ("disabled" if en.is_file() and en.read_text(errors="replace").strip() == "0" else "enabled")
    else: mod = "not installed"
    return "game: %s | UE4SS: %s | AToolSlotLimit: %s | slot ceiling %d (%s)" % (game, ue, mod, ceiling, "--ceiling" if explicit else "auto")

def ceiling_warning(game, ceiling):
    """a note when the ceiling in use is higher than what will work in game, or when the mod is installed but cannot be trusted"""
    auto = detect_ceiling(game)
    if ceiling > auto: return "warning: slots above %d only work with AToolSlotLimit on RevOG SB-UE4SS 1.3 (the only tested UE4SS); on your setup clips moved there may not show up in game." % auto
    mod = (pathlib.Path(game) / "Binaries" / "Win64" / "ue4ss" / "Mods" / "AToolSlotLimit" / "dlls" / "main.dll").is_file()
    if ceiling == 1000 and mod and not ue4ss_build(game):
        return "note: AToolSlotLimit is installed but your UE4SS is not the one it was tested with (RevOG SB-UE4SS 1.3; or its DLL could not be read), so slots stay within 1..1000."
    return None

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
    try: return _id_sites(utoc)
    except (OSError, struct.error, IndexError, ZeroDivisionError): return None            # orphan or truncated pak: reported as skipped, never a crash

def _id_sites(utoc):
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
    """patch the three sites; journal in backup/manifest.json (done flag). Returns (done, skipped[(pak, why)]). Rolls back on any error or interrupt.
    The files' modified times are put back so a later revert of an earlier slot move still recognises them."""
    root = pathlib.Path(root); backup = pathlib.Path(backup)
    man, skipped = [], []
    for k, old, new in fixes:
        sites = id_sites(root / k)
        if not sites or sites["id"] != old: skipped.append((k, "id sites differ, files unreadable or chunk is compressed")); continue
        if not (_lock_ok(sites["utoc"]) and _lock_ok(sites["ucas"])): skipped.append((k, "locked (game running?)")); continue
        man.append({"pak": k, "old": old, "new": new, "mt_utoc": os.stat(sites["utoc"]).st_mtime_ns, "mt_ucas": os.stat(sites["ucas"]).st_mtime_ns, **{x: sites[x] for x in ("utoc", "ucas", "toc_chunk_off", "ucas_off")}})
    if not man: return man, skipped                          # nothing patched: no journal, no empty "newest run"
    backup.mkdir(parents=True, exist_ok=True); j = {"kind": "ids", "items": man, "done": False}; _save_manifest(backup / "manifest.json", j)
    try:
        for m in man:
            with open(m["utoc"], "r+b") as f:
                f.seek(56); f.write(struct.pack("<Q", m["new"])); f.seek(m["toc_chunk_off"]); f.write(struct.pack("<Q", m["new"]))
            with open(m["ucas"], "r+b") as f: f.seek(m["ucas_off"]); f.write(struct.pack("<Q", m["new"]))
            _keep_mtime(m)
            s2 = id_sites(m["utoc"])
            if not s2 or s2["id"] != m["new"]: raise OSError("verify failed for %s" % m["pak"])
        j["done"] = True; _save_manifest(backup / "manifest.json", j)
    except (OSError, struct.error) as e:
        revert_fix(backup); raise SystemExit("container id patch failed (%s); everything written so far was rolled back" % e)
    except BaseException:
        revert_fix(backup); raise
    return man, skipped

def _keep_mtime(m):
    for k, mt in (("utoc", m.get("mt_utoc")), ("ucas", m.get("mt_ucas"))):
        if mt is not None and os.path.exists(m[k]):
            try: os.utime(m[k], ns=(os.stat(m[k]).st_atime_ns, mt))
            except OSError: pass

def revert_fix(backup):
    """put the old id back at each of the three sites that still holds our new id (works on half-patched containers); idempotent"""
    import json
    mp = pathlib.Path(backup) / "manifest.json"
    if not mp.exists(): return 0
    j = json.loads(mp.read_text()); man = j["items"] if isinstance(j, dict) else j; n = 0     # older journals are a bare list
    for m in man:
        hit = False
        for path, off in ((m["utoc"], 56), (m["utoc"], m["toc_chunk_off"]), (m["ucas"], m["ucas_off"])):
            if not os.path.exists(path): continue
            with open(path, "r+b") as f:
                f.seek(off)
                if struct.unpack("<Q", f.read(8))[0] == m["new"]: f.seek(off); f.write(struct.pack("<Q", m["old"])); hit = True
        if hit: _keep_mtime(m)
        n += hit
    os.replace(mp, pathlib.Path(backup) / "manifest.reverted.json")
    return n

# ---- move a pak's clip to another slot (rewrites the IoStore container, see iostore.py)
def _save_manifest(path, j):
    import json
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True); t = str(path) + ".tmp"
    with open(t, "w", encoding="utf-8") as f: json.dump(j, f, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(t, path)

def _sig(p):
    try: st = os.stat(p); return [st.st_size, st.st_mtime_ns]
    except OSError: return None

def _commit(steps):
    """flush the journal after a step dict was updated in place (no-op for a plain list)"""
    if hasattr(steps, "path"): steps.j["steps"] = list(steps); _save_manifest(steps.path, steps.j)

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
    if str(key).lower().endswith(".pak"): return None, "legacy .pak mod: its slot is stored inside the pak; only IoStore (.utoc/.ucas) mods can be moved - ask the author for an IoStore build"
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
    """nearest free slot above `old`, then below, within 1..ceiling, with the same digit count (other lengths are not verified in game)"""
    for d in range(1, ceiling + 1):
        for s in (old + d, old - d):
            if 1 <= s <= ceiling and len(str(s)) == len(str(old)) and s not in used and s not in reserved: return s
    return None

def pak_pkgs(path):
    """lower-case package names below anim/ in an IoStore container ('201', '201a', '201a/1'); None when they cannot be listed (legacy .pak, unreadable)"""
    try: paths = utoc_paths(pathlib.Path(path).read_bytes()) if str(path).lower().endswith(".utoc") else None
    except OSError: return None
    if paths is None: return None
    out = set()
    for p in paths:
        m = re.search(r"Mods/HD-ATOOL_P/anim/(.+?)(?:\.[A-Za-z.]+)?$", p.replace("\\", "/"), re.I)
        if m: out.add(m.group(1).lower())
    return out

def _mod_stem(name):
    """container file name -> the mod's name: 'HD-EVE-Lilly-Hug_ConfigAnim_P.utoc' -> 'hd-eve-lilly-hug'"""
    s = re.sub(r"(?i)\.(utoc|pak)$", "", name); s = re.sub(r"(?i)_p$", "", s)
    return re.sub(r"(?i)[_ -]?config(anim)?$", "", s).lower()

def group_units(paks, inv, srcs=None):
    """{unit: [container keys]}. A MOD can ship several containers for ONE slot (Lilly-Hug: main clip 201, partner clips 201a/*, partner table 201a);
    they must move together. Unit = the Vortex source mod; else the mod's own folder (~mods/<folder>/...); else, for containers loose in ~mods,
    the same dir + mod name with the _Config/_ConfigAnim/_P suffixes removed. A group is only trusted when its containers are complementary (no two
    hold the same package); otherwise every container is its own unit, which is the old behaviour. Never groups legacy .pak or LogicMods with ~mods."""
    paks = pathlib.Path(paks); srcs = sources(paks) if srcs is None else srcs; by = collections.defaultdict(list)
    for k in sorted(inv):
        v = srcs.get(os.path.normcase(str(paks / k))); parts = k.split("/")
        if k.lower().endswith(".pak"): u = "pak:" + k                                      # legacy: slot inside the pak, never grouped
        elif v: u = "vortex:%s|%s" % (v, parts[0].lower())                                  # one mod, but never across ~mods / LogicMods
        elif len(parts) >= 3: u = "dir:" + "/".join(parts[:-1])
        else: u = "flat:%s|%s" % ("/".join(parts[:-1]), _mod_stem(parts[-1]))
        by[u].append(k)
    out = {}; group_units.notes = []
    def complementary(ks):
        seen = set()
        for k in ks:
            ps = pak_pkgs(paks / k)
            if ps is None or seen & ps: return False
            seen |= ps
        return True
    for u, ks in by.items():
        if len(ks) == 1: out["single:" + ks[0]] = ks; continue
        # containers of one folder / Vortex mod belong together only when they share a SLOT (main 201 + partner 201a/* + table 201a); a mod pack holding
        # unrelated clips (Hug + something on 305) is not one mod. Connected components over "holds a common slot".
        comp = []
        for k in ks:
            hit = [c for c in comp if any(set(inv[k]) & set(inv[x]) for x in c)]
            merged = [k] + [x for c in hit for x in c]; comp = [c for c in comp if c not in hit] + [merged]
        for n, c0 in enumerate(comp):
            c = sorted(c0); suffix = "" if len(comp) == 1 else "#%s~%d" % (_mod_stem(c[0].rsplit("/", 1)[-1]), n)
            if len(c) == 1: out["single:" + c[0]] = c
            elif complementary(c): out[u + suffix] = c
            else:                                          # share a package (or unreadable): a mod + a rival in one folder -> split by mod name, trust a name group only if complementary
                sub = collections.defaultdict(list)
                for k in c: sub[_mod_stem(k.rsplit("/", 1)[-1])].append(k)
                for m_, (stem, sk) in enumerate(sub.items()):
                    if len(sk) > 1 and complementary(sk): out["%s#%s~%d.%d" % (u, stem, n, m_)] = sk       # n.m: never collides with another component / stem of the same folder
                    else: out.update({"single:" + k: [k] for k in sk})
                group_units.notes.append("%s: %d containers share a package or cannot be read, split by mod name into %d group(s)" % (u.split(":", 1)[1], len(c), len(sub)))
    miss = [k for k in sorted(inv) if not any(k in ks for ks in out.values())]        # every container is in exactly one unit; never drop one silently
    for k in miss: out["single:" + k] = [k]; group_units.notes.append("internal: %s was in no group, treated alone" % k)
    return out

def unit_label(unit, keys):
    if len(keys) == 1: return keys[0]
    if unit.startswith("flat:"): d = keys[0].rsplit("/", 1)[0] if "/" in keys[0] else ""; base = (d + "/" if d else "") + unit.split("|")[1].split("#")[0]
    else: base = unit.split(":", 1)[1].split("|")[0].split("#")[0] + ("#" + unit.split("#", 1)[1].rsplit("~", 1)[0] if "#" in unit else "")
    return "%s (%d containers)" % (base, len(keys))

def unit_inv(inv, units):
    """{representative container key: slots held by the whole unit} - what clash detection and the ownership ledger work on"""
    return {ks[0]: sorted({s for k in ks for s in inv[k]}) for ks in units.values()}

def slot_refusal(root, inv, units, slot, us):
    """None when the holders `us` (units) of `slot` may be separated, else the reason. Used by the automatic plan AND by --pak, so no path can strand a pair.
    Every holder must own the MAIN clip (package `<slot>`): a holder with only `<slot>a` / `<slot>a/*` is the partner part of some other mod's clip (an
    addon, or half a mod that could not be grouped); moving it or its neighbour would strand the pair. A holder whose packages cannot be listed (legacy
    .pak, unreadable) next to a holder with partner packages cannot be told apart from a partner either: refused as well."""
    pk = {}
    for u in us:
        out = set()
        for k in units[u]:
            if slot not in inv[k]: continue
            ps = pak_pkgs(pathlib.Path(root) / k)
            if ps is None: out = None; break
            out |= {p for p in ps if re.match(r"^%d(a)?(/.*)?$" % slot, p)}
        pk[u] = out
    lb = lambda u: unit_label(u, units[u])
    nomain = [u for u in us if pk[u] is not None and not any(p == str(slot) or p.startswith("%d/" % slot) for p in pk[u])]
    if nomain: return "%s holds only the partner part of slot %d (%s) without its main clip: a main clip and its partner parts are split across mods or containers, nothing moved" % (lb(nomain[0]), slot, ", ".join(sorted(pk[nomain[0]])) or "-")
    unknown = [u for u in us if pk[u] is None]
    if unknown and any(pk[u] and any(re.match(r"^%da" % slot, p) for p in pk[u]) for u in us if pk[u] is not None):
        return "%s cannot be read (legacy .pak or unreadable) while another holder of slot %d has partner packages: cannot tell whether it is the partner's main clip, nothing moved" % (lb(unknown[0]), slot)
    return None

def plan_unit_moves(root, inv, ceiling=1000, reserved=(), mtimes=None, units=None):
    """-> (moves [{unit, keys, old, new}], unresolved [(slot, [unit labels], reasons)]). A clash is between different units. Per clash: never LogicMods;
    try the newer unit first, then the other; a unit moves only if EVERY one of its containers holding the slot rewrites and verifies (all or nothing)."""
    units = units or {"single:" + k: [k] for k in inv}; used = {s for v in inv.values() for s in v} | set(reserved); moves = []; unresolved = []
    mt = mtimes or {k: (pathlib.Path(root) / k).stat().st_mtime for k in inv}
    holds = {u: sorted({s for k in ks for s in inv[k]}) for u, ks in units.items()}
    for slot, us in sorted(clashes(holds).items()):
        why0 = slot_refusal(root, inv, units, slot, us)
        if why0: unresolved.append((slot, [unit_label(u, units[u]) for u in us], [why0])); continue
        cand = sorted([u for u in us if not any(k.lower().startswith("logicmods/") for k in units[u])], key=lambda u: (-max(mt.get(k, 0) for k in units[u] if slot in inv[k]), u))
        reasons = []; remaining = list(us)
        for u in cand:                                   # newest first; the last holder left keeps the slot
            if len(remaining) == 1: break
            new = free_slot(slot, used, ceiling, reserved)
            if new is None: reasons.append("%s: no free slot <= %d" % (unit_label(u, units[u]), ceiling)); continue
            ks = [k for k in units[u] if slot in inv[k]]; why = None
            for k in ks:                                 # dry run of every container before anything is written
                c, w = try_rename(root, k, slot, new)
                if c is None: why = "%s: %s" % (k, w); break
            if why: reasons.append("%s not moved, %s" % (unit_label(u, units[u]), why)); continue
            moves.append({"unit": u, "keys": ks, "old": slot, "new": new}); used.add(new); remaining.remove(u)
        if len(remaining) > 1: unresolved.append((slot, [unit_label(u, units[u]) for u in remaining], reasons or ["only LogicMods packs involved"]))
    return moves, unresolved

def plan_moves(root, inv, ceiling=1000, reserved=(), mtimes=None):
    """-> (moves [(pak, old, new)], unresolved [(slot, paks, reasons)]): the same plan with every container its own unit (no grouping)."""
    mv, un = plan_unit_moves(root, inv, ceiling, reserved, mtimes)
    return [(m["keys"][0], m["old"], m["new"]) for m in mv], un

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

_SAID = set()
def _once(msg):
    """print a line once per process (auto runs main twice)"""
    if msg not in _SAID: _SAID.add(msg); print(msg)

def ledger_update(game, inv, path, alias=None):
    """First-sight ownership for installs without Vortex: while a slot is held by ONE pak, remember that pak as the owner of the slot's wav /
    PELA file (with the file's size+mtime). An entry is dropped when the file changed or its owner left the install; a changed file is
    re-recorded if its slot has a single holder. Returns {normalized path: 'pak:<key>'}."""
    import json
    game = pathlib.Path(game); path = pathlib.Path(path)
    try: old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError): old = {}
    if not isinstance(old, dict): old = {}
    holders = collections.defaultdict(list)
    for k, v in inv.items():
        for sl in v: holders[sl].append(k)
    led = {}
    alias = alias or {}                                  # 1.0.0 named an owner by its container; a mod's containers are now named by the first one
    for pth, e in old.items():                           # keep only what is still true
        if isinstance(e, dict) and isinstance(e.get("o"), str) and e["o"][:4] == "pak:" and alias.get(e["o"][4:], e["o"][4:]) in inv and e.get("s") == _sig(pth): led[pth] = {**e, "o": "pak:" + alias.get(e["o"][4:], e["o"][4:])}
    def rec(f, who): led.setdefault(os.path.normcase(str(f)), {"o": "pak:" + who, "s": _sig(f)})
    audio = game / "Content" / "Paks" / "LogicMods" / "HD-ATOOL_P" / "audio"
    for f in (audio.iterdir() if audio.is_dir() else []):
        if f.suffix.lower() == ".wav" and f.stem.isdigit() and len(holders.get(int(f.stem), [])) == 1: rec(f, holders[int(f.stem)][0])
    pela = game / "Content" / "Paks" / "~mods" / "PELA Patches"
    for f in sorted(pela.glob("*.json")) if pela.is_dir() else []:
        try: sl = _pela_slots(json.loads(f.read_text(encoding="utf-8-sig")))
        except (OSError, ValueError): continue
        h = {holders[x][0] for x in sl if len(holders.get(x, [])) == 1}
        if len(h) == 1: rec(f, next(iter(h)))
    if led != old:
        try: _save_manifest(path, led)
        except OSError: pass                              # cannot persist the ledger: still usable this run
    return {k: e["o"] for k, e in led.items()}

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
                if backup: apply_to.append({"kind": "rename", "from": str(p), "to": str(dst)}); p.rename(dst)
            else:
                out.append(("wav %s copied to %s (owner unknown, slot shared)" % (p.name, dst.name), p))
                if backup:
                    stp = {"kind": "copy", "to": str(dst)}; apply_to.append(stp); shutil.copy2(p, dst); stp["sig"] = _sig(dst); _commit(apply_to)
    pefa = game / "Binaries" / "Win64" / "ue4ss" / "Mods" / "PEFA"
    names = pefa / "names.txt"
    if names.is_file():
        txt = names.read_bytes().decode("utf-8", "surrogateescape"); m = re.search(r"(?m)^%d(\s*=.*)$" % old, txt)       # lossless: bytes and line endings survive
        if m and re.search(r"(?m)^%d\s*=" % new, txt): out.append(("note: PEFA names.txt already names slot %d: the name of slot %d was left as it is" % (new, old), names))
        if m and not re.search(r"(?m)^%d\s*=" % new, txt):
            if shared:                                              # PEFA's names.txt has no owner: keep the old line, add one for the new slot
                out.append(("PEFA names.txt: line %d copied to %d (slot shared)" % (old, new), names)); edit = lambda t: re.sub(r"(?m)^(%d)(\s*=.*)$" % old, lambda mm: mm.group(0) + "\n" + str(new) + mm.group(2), t, count=1)
            else:
                out.append(("PEFA names.txt line %d -> %d" % (old, new), names)); edit = lambda t: re.sub(r"(?m)^%d(\s*=)" % old, lambda mm: str(new) + mm.group(1), t)
            if backup:
                b = save(names); stp = {"kind": "file", "path": str(names), "backup": str(b), "sig": None}; apply_to.append(stp)
                names.write_bytes(edit(txt).encode("utf-8", "surrogateescape")); stp["sig"] = _sig(names); _commit(apply_to)
    for nm in ("packs_rows.txt", "packs_cache.txt"):
        p = pefa / nm
        if p.is_file():
            out.append(("PEFA cache %s deleted (PEFA rebuilds it)" % nm, p))
            if backup: b = save(p); apply_to.append({"kind": "file", "path": str(p), "backup": str(b), "sig": None, "deleted": True}); p.unlink()
    pela = game / "Content" / "Paks" / "~mods" / "PELA Patches"
    for p in sorted(pela.glob("*.json")) if pela.is_dir() else []:
        try: doc = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError): continue
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
            b = save(p); stp = {"kind": "file", "path": str(p), "backup": str(b), "sig": None}; apply_to.append(stp)
            p.write_text(json.dumps(doc, indent=1), encoding="utf-8"); stp["sig"] = _sig(p); _commit(apply_to)
    return out

def apply_move(root, game, key, old, new, backup, shared=False, srcs=None, ext=True, unit=None, mover=None):
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
    nt = utoc.with_name(utoc.name + ".new"); nu = ucas.with_name(ucas.name + ".new")        # not mountable names
    j = {"kind": "move", "pak": key, "old": old, "new": new, "steps": [], "done": False}; mp = backup / "manifest.json"
    if unit: j["unit"] = unit
    try:
        nt.write_bytes(t); nu.write_bytes(u)
        c2 = iostore.read_container(nt, nu)                                 # verify what was written, not what we meant to write
        if iostore.check_container(c2) or new not in iostore.slots_in(c2) or old in iostore.slots_in(c2):
            raise SystemExit("verification of the rewritten container failed, nothing changed")
        _save_manifest(mp, j)
        sfx = ".orig"; k = 0
        while utoc.with_name(utoc.name + sfx).exists() or ucas.with_name(ucas.name + sfx).exists(): k += 1; sfx = ".orig%d" % k   # never overwrite an earlier backup (chained moves)
        bt = utoc.with_name(utoc.name + sfx); bu = ucas.with_name(ucas.name + sfx); steps = _Steps(j, mp)
        steps.append({"kind": "swap", "path": str(utoc), "backup": str(bt)}); os.replace(utoc, bt)      # originals renamed to *.orig next to the pak (same volume, instant, not mountable; a hard link to Vortex staging stays intact)
        steps.append({"kind": "swap", "path": str(ucas), "backup": str(bu)}); os.replace(ucas, bu)
        os.replace(nt, utoc); os.replace(nu, ucas)
        steps[-2]["sig"] = _sig(utoc); steps[-1]["sig"] = _sig(ucas); _commit(steps)
        srcs = srcs if srcs is not None else sources(root)
        if ext: j["notes"] = [w for w, _p in external_files(game, old, new, steps, backup, shared, mover or srcs.get(os.path.normcase(str(utoc))) or "pak:" + key, srcs)]
        j["done"] = True; _save_manifest(mp, j)
    except BaseException:
        for x in (nt, nu):
            try: x.unlink()
            except OSError: pass
        if mp.exists(): revert_move(backup)                             # roll back whatever was already done
        raise
    return j

def apply_unit_move(root, game, keys, old, new, backups, shared=False, srcs=None, unit=None, mover=None):
    """move every container of one mod (slot old -> new) as ONE unit: each container is journaled and verified like a single move; the slot-keyed
    files (wav / PEFA names / PELA) are handled once, with the first container (owner = `mover`, the same identity the preview used); if any container
    fails, the ones already moved are reverted, so the mod is never left half moved (main clip on the new slot, partner on the old one = the mod's
    second character disappears). A crash or kill between containers is covered by START MARKERS: every container's journal exists, unfinished
    (done=false), before the first byte is written, so interrupted() sees the whole unit and `revert` undoes what was done. After the last move every
    container is re-read: all must report `new` and none `old`. apply_unit_move.clean says whether a failure was rolled back completely."""
    root = pathlib.Path(root); js = []; apply_unit_move.clean = True
    try:
        for k, bk in zip(keys, backups):               # inside the try: a marker that cannot be written must not leave the earlier ones behind
            pathlib.Path(bk).mkdir(parents=True, exist_ok=True)
            _save_manifest(pathlib.Path(bk) / "manifest.json", {"kind": "move", "pak": k, "old": old, "new": new, "steps": [], "done": False, **({"unit": unit} if unit else {})})
        for i, (k, bk) in enumerate(zip(keys, backups)):
            js.append(apply_move(root, game, k, old, new, bk, shared=shared, srcs=srcs, ext=(i == 0), unit=unit, mover=mover))
        for k in keys:
            s = pak_slots(root / k)
            if new not in s or old in s: raise SystemExit("verification failed: %s reports slots %s after the move (expected %d, not %d)" % (k, sorted(s), new, old))
    except BaseException:
        for bk in reversed(backups):                    # the failing container rolled itself back already; reverting it (and the untouched markers) again is harmless
            try:
                revert_move.kept = 0; revert_move(bk)
                if revert_move.kept: apply_unit_move.clean = False; print("  NOT fully undone: %d step(s) of %s were kept (files changed since)" % (revert_move.kept, bk))
                if (pathlib.Path(bk) / "manifest.partial.json").exists(): apply_unit_move.clean = False; print("  NOT fully undone: %s was kept as manifest.partial.json (apply_move's own rollback could not undo everything)" % bk)
            except Exception as e: apply_unit_move.clean = False; print("  could not revert %s: %s" % (bk, e))
        raise
    return js

def revert_move(backup):
    """undo a move journal: put the original files back, newest step first. Tolerates steps that never happened and repeated calls.
    A file that changed since the tool wrote it (re-deployed mod, edited names.txt) is NOT overwritten. Every step is isolated: one that
    cannot be undone (folder gone, original deleted) is reported and counted as kept, and the others still run. Returns the steps undone;
    revert_move.kept = steps that could not be undone (the journal is then kept as manifest.partial.json)."""
    import json, shutil
    backup = pathlib.Path(backup); mp = backup / "manifest.json"
    if not mp.exists(): return 0
    j = json.loads(mp.read_text()); n = 0; kept = 0
    def changed(st, path):
        if st.get("sig") is not None and os.path.exists(path) and _sig(path) != st["sig"]:
            print("  not restored (changed since the move): %s" % path); return True
        return False
    for st in reversed(j["steps"]):
        try:
            if st["kind"] == "swap":
                if os.path.exists(st["backup"]):
                    if changed(st, st["path"]): kept += 1; continue
                    os.replace(st["backup"], st["path"]); n += 1
                elif st.get("sig") is not None:                         # the swap was completed, but the saved original is gone
                    print("  cannot restore %s: the saved original %s is missing" % (st["path"], st["backup"])); kept += 1
            elif st["kind"] == "rename":
                if pathlib.Path(st["to"]).exists() and not pathlib.Path(st["from"]).exists(): os.replace(st["to"], st["from"]); n += 1
            elif st["kind"] == "copy":
                if pathlib.Path(st["to"]).exists():
                    if changed(st, st["to"]): kept += 1; continue
                    os.unlink(st["to"]); n += 1
            elif st["kind"] == "file":
                if st.get("deleted"):                                   # a cache the tool removed: the game rebuilt it for the moved layout - remove it again, the game rebuilds it
                    if os.path.exists(st["path"]): os.unlink(st["path"]); n += 1
                    continue
                if not os.path.exists(st["backup"]): continue
                if not os.path.isdir(os.path.dirname(st["path"])): print("  not restored (its folder no longer exists): %s" % st["path"]); kept += 1; continue
                if st.get("sig") is None and os.path.exists(st["path"]): print("  not restored (recreated since the move): %s" % st["path"]); kept += 1; continue
                if changed(st, st["path"]): kept += 1; continue
                shutil.copy2(st["backup"], st["path"]); n += 1
        except OSError as e:
            print("  could not undo %s: %s" % (st.get("path") or st.get("to") or st.get("from"), e)); kept += 1
    revert_move.kept = kept
    os.replace(mp, backup / ("manifest.partial.json" if kept else "manifest.reverted.json"))
    return n

def _game_running():
    import subprocess
    try: return "SB-Win64-Shipping.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    except OSError: return False                              # no tasklist: the file-lock checks still protect

def interrupted(backup):
    """move journals that were started but never finished (crash, power loss, closed window)"""
    import glob, json
    out = []
    for d in glob.glob(glob.escape(backup) + "/move-*") + glob.glob(glob.escape(backup) + "/ids-*"):
        for name in ("manifest.json", "manifest.partial.json"):       # .partial = a failed move whose own rollback could not undo everything (a file changed meanwhile)
            try:
                if json.loads(open(d + "/" + name, encoding="utf-8").read()).get("done") is False: out.append(d); break       # journals from before this flag existed are not flagged
            except (OSError, ValueError): pass
    return out

def partial_pending(dirs):
    """the unfinished journals that are NOT revertible any more (manifest.partial.json): reverting would only touch older runs"""
    return [d for d in dirs if os.path.exists(os.path.join(d, "manifest.partial.json")) and not os.path.exists(os.path.join(d, "manifest.json"))]

def sweep_temp(paks):
    """remove temp containers a killed run may have left in Paks (they would be mounted by the game); returns the removed names"""
    out = []
    for pat in ("*.utoc.new", "*.ucas.new"):                 # the only names this tool writes; a mod called X.new.utoc is a user file
        for f in pathlib.Path(paks).rglob(pat):
            try: f.unlink(); out.append(f.name)
            except OSError: pass
    return out

def _ask(q):
    try: return input("%s [y/N] " % q).strip().lower() in ("y", "yes")
    except (EOFError, RuntimeError, OSError): return False

def main(argv):
    import argparse, time
    ap = argparse.ArgumentParser(prog="slots", description="Stellar Blade anim slot organizer (scan, fixids, moveslots, auto, revert)")
    ap.add_argument("cmd", choices=["scan", "plan", "fixids", "moveslots", "auto", "revert", "log"]); ap.add_argument("--game"); ap.add_argument("--ceiling", type=int, default=None, help="default: auto (1000, or the AToolSlotLimit limit)"); ap.add_argument("--reserved", default=os.path.join(HERE, "reserved.txt")); ap.add_argument("--run", help=argparse.SUPPRESS)
    ap.add_argument("--apply", action="store_true", help="fixids/moveslots: really write (default: dry run)"); ap.add_argument("--pak", help="moveslots: move this pak (path relative to Paks, e.g. ~mods/BBS_P.utoc)"); ap.add_argument("--slot", type=int, help="moveslots --pak: the slot to move"); ap.add_argument("--to", type=int, help="moveslots --pak: the target slot"); ap.add_argument("--backup", default=os.path.join(DATA, "slot_backups")); ap.add_argument("--cache", default=os.path.join(DATA, "slot_cache.json")); ap.add_argument("--no-cache", action="store_true"); ap.add_argument("--version", action="version", version="SlotOrganizer " + VERSION); ap.add_argument("--yes", action="store_true", help="apply without asking")
    a = ap.parse_args(argv)
    if a.cmd == "log":                                     # where the support log is, and its last lines
        out = sys.__stdout__ or sys.stdout                      # not the tee: showing the log must not append to it
        print(LOG_PATH or _log_default(), file=out)
        try:
            for l in open(LOG_PATH or _log_default(), encoding="utf-8", errors="replace").read().splitlines()[-40:]: print(l, file=out)
        except OSError: print("(no log yet)", file=out)
        return 0
    if a.cmd == "revert":                                  # journals hold absolute paths: no game folder needed
        import glob
        if _game_running(): print("Stellar Blade is running: close it first"); return 2
        pp0 = partial_pending(interrupted(a.backup))
        if pp0: print("A failed move could not be undone completely (%s): revert cannot fix it and would only undo OLDER runs, so it does nothing. The originals are in that journal folder under %s and as *.orig files next to the paks; send the log. Once the files are checked, delete that journal folder to clear this warning." % (", ".join(os.path.basename(d) for d in pp0), a.backup)); return 2
        ds = [d for d in glob.glob(glob.escape(a.backup) + "/ids-*") + glob.glob(glob.escape(a.backup) + "/move-*") if os.path.exists(d + "/manifest.json")]
        if not ds: print("nothing to revert in", a.backup); return 0
        ts = lambda d: re.search(r"(\d{8}-\d{6})", os.path.basename(d)).group(1)
        last = max(ts(d) for d in ds); grp = [d for d in ds if ts(d) == last]       # the newest run: its moves newest first, then its id patches
        grp.sort(key=lambda d: (0, -int(d.rsplit("-", 1)[1])) if os.path.basename(d).startswith("move-") else (1, 0))
        kept = 0
        for d in grp:
            try:
                if os.path.basename(d).startswith("move-"): print("undid %d step(s) of %s" % (revert_move(d), d)); kept += getattr(revert_move, "kept", 0)
                else: print("restored %d container id(s) from %s" % (revert_fix(d), d))
            except OSError as e: print("could not revert %s: %s (is the game or Vortex using the files?)" % (d, e)); return 2
        if kept: print("\n%d file(s) were NOT restored because they changed after the tool wrote them; the originals are still there: paks as *.orig beside them, other files in the journal folder (files\\<n>) - check them by hand." % kept); return 3
        return 0
    g = find_game(a.game)
    if not g and not a.game and sys.stdin is not None and sys.stdin.isatty():
        try: r = input("Stellar Blade not found automatically. Paste the folder that contains SB (e.g. D:\\Games\\StellarBlade): ").strip().strip('"')
        except (EOFError, RuntimeError, OSError): r = ""
        g = _sb(r) if r else None
        if g:
            try: os.makedirs(DATA, exist_ok=True); open(os.path.join(DATA, "game.txt"), "w", encoding="utf-8").write(str(g))
            except OSError: pass
    if not g: print("Stellar Blade not found; pass --game <path to StellarBlade or its SB folder> or set SB_GAME"); return 2
    if a.cmd == "auto":                                    # what a double-click does: fix container ids, then slot clashes, asking first; one run stamp so `revert` undoes both
        import time as _t
        run = _t.strftime("%Y%m%d-%H%M%S")
        iv0 = interrupted(a.backup)
        if iv0:
            print("An interrupted run was found: %s" % ", ".join(os.path.basename(d) for d in iv0))
            if not _game_running() and _ask("Undo it now?"): return main(["revert", "--backup", a.backup])
            print("Nothing was changed. Run Undo-last-run.bat (or SlotOrganizer.exe revert) first."); return 2
        base = ["--game", str(g), "--backup", a.backup, "--cache", a.cache, "--reserved", a.reserved, "--apply", "--run", run] + (["--yes"] if a.yes else []) + (["--ceiling", str(a.ceiling)] if a.ceiling else []) + (["--no-cache"] if a.no_cache else [])
        r1 = main(["fixids"] + base)
        if r1 >= 2: return r1
        r2 = main(["moveslots"] + base)
        if r2 >= 2: return r2
        if os.path.isdir(a.backup) and any(os.path.basename(d).endswith(run) or run in d for d in os.listdir(a.backup)): print("\nUndo this run with: SlotOrganizer.exe revert")
        return 0
    explicit = a.ceiling is not None
    if a.ceiling is None: a.ceiling = detect_ceiling(g)
    if not _IDENT: _IDENT.append(1); print(identity_line(g, a.ceiling, explicit))
    w = ceiling_warning(g, a.ceiling)
    if w and not _NOTED:
        _NOTED.append(1); print(w)                         # once per run, even when auto calls main twice
    t = time.time(); inv = scan(g / "Content" / "Paks", None if a.no_cache else a.cache)
    lp = os.path.join(os.path.dirname(os.path.abspath(a.cache)), "slot_owners.json"); first_run = not os.path.exists(lp)
    vsrc = sources(g / "Content" / "Paks"); units = group_units(g / "Content" / "Paks", inv, vsrc); uinv = unit_inv(inv, units)       # a mod's containers = ONE unit (Lilly-Hug is 3)
    lab = {ks[0]: unit_label(u, ks) for u, ks in units.items()}; rep = {k: ks[0] for ks in units.values() for k in ks}
    for n_ in group_units.notes: _once("note: " + n_)
    for u_, ks_ in sorted(units.items()):
        if len(ks_) > 1: _once("mod %s = %s" % (unit_label(u_, ks_), ", ".join(os.path.basename(k) for k in ks_)))        # what was grouped (support log), every run
    ledger = ledger_update(g, uinv, lp, rep)
    ss = {s for v in inv.values() for s in v}; cl = {s: [lab[k] for k in ks] for s, ks in clashes(uinv).items()}
    print("%d paks, %d slots, %d clashes, %d above %d, %d free <= %d  (%d cached, %.2fs)" % (len(inv), len(ss), len(cl), sum(s > a.ceiling for s in ss), a.ceiling, a.ceiling - len([s for s in ss if s <= a.ceiling]), a.ceiling, scan.hits, time.time() - t))
    members = {unit_label(u, ks): ks for u, ks in units.items() if len(ks) > 1}
    for s, p in sorted(cl.items()):
        print("  clash slot %d: %s" % (s, " | ".join(p)))
        for lb_ in p:
            if lb_ in members: print("      %s = %s" % (lb_, ", ".join(os.path.basename(k) for k in members[lb_])))      # what was grouped (support log)
    idc = id_clashes(g / "Content" / "Paks"); anim = {k.replace("\\", "/") for k in inv}
    hit = {v: ks for v, ks in idc.items() if any(k in anim for k in ks)}
    if hit: print("%d container-id clash(es) involve anim paks (only one pak per id mounts, the other one's clips are unavailable)" % len(hit))
    iv = interrupted(a.backup)
    pp = partial_pending(iv)
    if iv and len(pp) < len(iv): print("WARNING: an interrupted run was found (%s). Run Undo-last-run.bat (or SlotOrganizer.exe revert) before changing anything." % ", ".join(os.path.basename(d) for d in iv if d not in pp))
    if pp: print("WARNING: a failed move could not be undone completely (%s). Do NOT run revert (it cannot fix this and would only undo older runs). The originals are in that journal folder under %s and as *.orig files next to the paks; send the log. Once the files are checked, delete that journal folder to clear this warning." % (", ".join(os.path.basename(d) for d in pp), a.backup))
    for v, ks in hit.items(): print("  id %#x: %s" % (v, " | ".join(ks)))
    cl = {**cl, **{("id", v): ks for v, ks in hit.items()}}
    if a.cmd == "fixids":
        import subprocess, time as _t
        fx = plan_fix(g / "Content" / "Paks", inv)
        for k, o, n in fx: print("  %s: id %#x -> %#x" % (k, o, n))
        if not fx: print("nothing to fix"); return 0
        if not a.apply: print("dry run: %d container id(s) would change (add --apply, close the game first)" % len(fx)); return 1
        if _game_running(): print("Stellar Blade is running: close it first"); return 2
        if iv: print("not applying while an interrupted run is pending"); return 2
        if not a.yes and not _ask("Patch %d container id(s) now?" % len(fx)): print("cancelled, nothing changed"); return 1
        if _game_running(): print("Stellar Blade was started meanwhile: close it first"); return 2
        sweep_temp(g / "Content" / "Paks")
        bk = "%s/ids-%s" % (a.backup, a.run or _t.strftime("%Y%m%d-%H%M%S")); print("game folder:", g)
        done, skipped = apply_fix(g / "Content" / "Paks", fx, bk)
        for k, why in skipped: print("  skipped %s: %s" % (k, why))
        print("changed %d container id(s); undo with: SlotOrganizer.exe revert (journal %s)" % (len(done), bk)); return 0
    if a.cmd == "moveslots":
        import subprocess, time as _t
        paks = g / "Content" / "Paks"; rs = load_reserved(a.reserved)
        if a.pak:
            if a.slot is None or a.to is None: print("--pak needs --slot and --to"); return 2
            kk = a.pak.replace(chr(92), "/")
            if kk not in inv: print("--pak %s is not an anim pak under %s (use the path shown by scan)" % (a.pak, paks)); return 2
            used = {x for v in inv.values() for x in v}
            if not (1 <= a.to <= a.ceiling) or a.to in rs or a.to in used: print("--to %d is not a free slot within 1..%d" % (a.to, a.ceiling)); return 2
            if a.slot not in inv[kk]: print("%s does not hold slot %d (it holds %s)" % (kk, a.slot, ", ".join(map(str, inv[kk])))); return 2
            uk = next((u for u, ks in units.items() if kk in ks), None); ks = [k for k in units.get(uk, []) if a.slot in inv[k]]      # the whole mod moves, not one container
            if not ks: print("%s is not part of any mod group (internal error, see log)" % kk); return 2
            why_ = slot_refusal(paks, inv, units, a.slot, [u for u, ks2 in units.items() if any(a.slot in inv[k] for k in ks2)])        # same guard as the automatic plan
            if why_: print("cannot move %s: %s" % (kk, why_)); return 2
            for k in ks:
                c0, why0 = try_rename(paks, k, a.slot, a.to)
                if c0 is None: print("cannot move %s: %s" % (k, why0)); return 2
            moves, unresolved = [{"unit": uk, "keys": ks, "old": a.slot, "new": a.to}], []
        else: moves, unresolved = plan_unit_moves(paks, inv, a.ceiling, rs, units=units)
        for slot, ps, why in unresolved:
            print("  slot %d cannot be fixed automatically (%s):" % (slot, " | ".join(ps)))
            for w in why: print("      " + w)
        srcs = {**ledger, **vsrc}                               # Vortex's word beats the ledger
        def shared(mv): return any(mv["old"] in v for r, v in uinv.items() if r != units[mv["unit"]][0])      # held by ANOTHER mod
        def mover(k): return srcs.get(os.path.normcase(str(paks / k))) or "pak:" + rep[k]                     # the ledger names a mod by its first container
        if moves and first_run and not vsrc: print("  note: first run without a mod manager manifest - who owns each slot's audio/PELA files is unknown, so those are copied, not moved. Run the tool once on a clean install, then after each install, to keep ownership exact.")
        for mv in moves:
            ks = mv["keys"]; lb = unit_label(mv["unit"], units[mv["unit"]])
            print("  %s: slot %d -> %d%s" % (lb, mv["old"], mv["new"], " (%d containers moved together: %s)" % (len(ks), ", ".join(os.path.basename(k) for k in ks)) if len(ks) > 1 else ""))
            for what, _p in external_files(g, mv["old"], mv["new"], shared=shared(mv), mover=mover(ks[0]), srcs=srcs): print("      " + what)
        if not moves: print("nothing to move"); return 1 if unresolved else 0
        nc_ = sum(len(m["keys"]) for m in moves)
        if not a.apply: print("dry run: %d move(s), %d container(s) (add --apply, close the game first)" % (len(moves), nc_)); return 1
        if _game_running(): print("Stellar Blade is running: close it first"); return 2
        if iv: print("not applying while an interrupted run is pending"); return 2
        if not a.yes and not _ask("Move %d slot(s) now? (originals are kept as .orig, `revert` undoes it)" % len(moves)): print("cancelled, nothing changed"); return 1
        if _game_running(): print("Stellar Blade was started meanwhile: close it first"); return 2
        sweep_temp(paks)
        bk = "%s/move-%s" % (a.backup, a.run or _t.strftime("%Y%m%d-%H%M%S")); print("game folder:", g); i = 0
        for n_done, mv in enumerate(moves):
            bks = ["%s-%d" % (bk, i + x) for x in range(len(mv["keys"]))]; i += len(bks)
            try: js = apply_unit_move(paks, g, mv["keys"], mv["old"], mv["new"], bks, shared=shared(mv), srcs=srcs, unit=unit_label(mv["unit"], units[mv["unit"]]), mover=mover(mv["keys"][0]))
            except BaseException:
                lb_ = unit_label(mv["unit"], units[mv["unit"]])
                if apply_unit_move.clean: print("move of %s failed and was rolled back completely (all %d container(s) of it); see the log" % (lb_, len(mv["keys"])))
                else: print("move of %s failed and was NOT fully rolled back: it may be half moved. Do NOT run revert; the originals are in the journal folders under %s and as *.orig files next to the paks. Send the log. The next run refuses to change anything until this is sorted out." % (lb_, a.backup))
                if n_done: print("%d earlier move(s) of this run were applied; `revert` undoes them" % n_done)
                raise
            for j in js:
                for w in j.get("notes", []): print("      " + w)
            print("  verified: %s now on slot %d (%d container(s))" % (unit_label(mv["unit"], units[mv["unit"]]), mv["new"], len(mv["keys"])))
        print("moved %d slot(s) (%d container(s)); undo with: SlotOrganizer.exe revert (journal %s-*)" % (len(moves), nc_, bk)); return 0
    if a.cmd == "plan":
        mv, unres = plan_unit_moves(g / "Content" / "Paks", inv, a.ceiling, load_reserved(a.reserved), units=units)       # the very planner moveslots uses (per mod, with its refusals)
        for m in mv: print("  %s: %d -> %d" % (unit_label(m["unit"], units[m["unit"]]), m["old"], m["new"]))
        for slot, ps, why in unres: print("  slot %d cannot be fixed automatically (%s): %s" % (slot, " | ".join(ps), "; ".join(why)))
        print("%d moves proposed (nothing is changed on disk yet)" % len(mv))
    return 1 if cl else 0

LOG_PATH = None

def _log_default(): return os.path.join(DATA, "logs", "slotorganizer.log")

class _Tee:
    """everything printed also goes to the log file (a missing console, e.g. pythonw, is fine)"""
    def __init__(self, stream, f): self.s, self.f = stream, f
    def write(self, x):
        try: self.f.write(x)
        except (OSError, ValueError): pass
        return self.s.write(x) if self.s is not None else len(x)
    def flush(self):
        try: self.f.flush()
        except (OSError, ValueError): pass
        if self.s is not None: self.s.flush()
    def __getattr__(self, n): return getattr(self.s, n)

def _open_log(path, argv=None, keep=512 * 1024):
    """append-mode support log with a small header (version, OS, args); rotates to .1 above `keep` bytes. None if it cannot be written."""
    import platform, time
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > keep: os.replace(path, path + ".1")
        f = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
        f.write("\n===== %s  SlotOrganizer %s  %s  %s  frozen=%s  args=%s =====\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), VERSION, platform.platform(), platform.python_version(), bool(getattr(sys, "frozen", False)), " ".join(argv or [])))
        return f
    except OSError: return None

def _failure_footer(rc, failed, log_path):
    """the line that points a user at the log: after any exception or error message, and after exit codes other than 0 (done) and 1 (dry run / nothing to do / cancelled)"""
    if log_path and (failed or rc not in (0, 1)): return "\nSomething did not go as planned. If you ask for help, attach this log file:\n  %s" % log_path
    return ""

def _cli():
    global LOG_PATH
    for st in (sys.stdout, sys.stderr):
        try: st.reconfigure(errors="replace")                 # odd characters in paths must never crash printing
        except (AttributeError, ValueError, OSError): pass
    argv = sys.argv[1:] or ["auto"]
    lf = None if argv[:1] == ["log"] else _open_log(_log_default(), argv if sys.argv[1:] else ["auto", "(double-click)"])   # showing the log must not write into it
    if lf: LOG_PATH = _log_default(); sys.stdout = _Tee(sys.stdout, lf); sys.stderr = _Tee(sys.stderr, lf)
    dbl = len(sys.argv) == 1                         # double-clicked exe: find clashes, show them, ask, fix, wait
    failed = False
    try: rc = main(argv)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
        if isinstance(e.code, str): print(e.code); failed = True
    except KeyboardInterrupt: print("interrupted"); rc = 130
    except BaseException:
        import traceback; traceback.print_exc(); print("\nUnexpected error. Nothing is left half-done unless the line above says so; `SlotOrganizer.exe revert` undoes the last run."); rc = 1; failed = True
    foot = _failure_footer(rc, failed, LOG_PATH)
    if foot: print(foot)
    if dbl and getattr(sys, "frozen", False):
        try: input("\nPress Enter to close")
        except (EOFError, RuntimeError, OSError): pass
    sys.exit(rc)

if __name__ == "__main__":
    _cli()
