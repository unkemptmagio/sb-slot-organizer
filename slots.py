"""Scan installed Stellar Blade anim paks for ATOOL slot use. Stdlib only."""
import struct, re, pathlib, collections, sys

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
    for c in [arg, os.environ.get("SB_GAME")]:
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
        if e not in (".utoc", ".pak") or not p.is_file() or (e == ".pak" and p.with_suffix(".utoc").exists()): continue
        st = p.stat(); key = str(p.relative_to(root)).replace("\\", "/"); sig = [st.st_size, int(st.st_mtime)]
        c = cache.get(key)
        if c and c["sig"] == sig: slots = c["slots"]; hits += 1
        else: slots = sorted(pak_slots(p))
        new[key] = {"sig": sig, "slots": slots}
        if slots: inv[key] = slots
    if cache_file: pathlib.Path(cache_file).write_text(json.dumps(new))
    scan.hits = hits
    return inv

def clashes(inv):
    by = collections.defaultdict(list)
    for k, v in inv.items():
        for s in v: by[s].append(k)
    return {s: p for s, p in by.items() if len(p) > 1}

def plan(inv, ceiling=1000, pinned=lambda k: k.startswith("LogicMods/"), reserved=()):
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

def main(argv):
    import argparse, time
    ap = argparse.ArgumentParser(prog="slots", description="Stellar Blade anim slot organizer (scan/plan only so far)")
    ap.add_argument("cmd", choices=["scan", "plan"]); ap.add_argument("--game"); ap.add_argument("--ceiling", type=int, default=1000)
    ap.add_argument("--cache", default="slot_cache.json"); ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args(argv); g = find_game(a.game)
    if not g: print("Stellar Blade not found; pass --game <...>\SB or set SB_GAME"); return 2
    t = time.time(); inv = scan(g / "Content" / "Paks", None if a.no_cache else a.cache)
    ss = {s for v in inv.values() for s in v}; cl = clashes(inv)
    print("%d paks, %d slots, %d clashes, %d above %d, %d free <= %d  (%d cached, %.2fs)" % (len(inv), len(ss), len(cl), sum(s > a.ceiling for s in ss), a.ceiling, a.ceiling - len([s for s in ss if s <= a.ceiling]), a.ceiling, scan.hits, time.time() - t))
    for s, p in sorted(cl.items()): print("  clash slot %d: %s" % (s, " | ".join(p)))
    if a.cmd == "plan":
        mv = plan(inv, a.ceiling)
        for k, o, n in mv: print("  %s: %d -> %d" % (k, o, n))
        print("%d moves proposed (nothing is changed on disk yet)" % len(mv))
    return 1 if cl else 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
