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
    """patch the three sites; keep the old bytes in backup/manifest.json. Returns (done, skipped[(pak, why)])."""
    import json
    root = pathlib.Path(root); backup = pathlib.Path(backup); backup.mkdir(parents=True, exist_ok=True)
    man, skipped = [], []
    for k, old, new in fixes:
        sites = id_sites(root / k)
        if not sites or sites["id"] != old: skipped.append((k, "id sites differ or chunk is compressed")); continue
        man.append({"pak": k, "old": old, "new": new, **{x: sites[x] for x in ("utoc", "ucas", "toc_chunk_off", "ucas_off")}})
    (backup / "manifest.json").write_text(json.dumps(man, indent=1))
    for m in man:
        with open(m["utoc"], "r+b") as f:
            f.seek(56); f.write(struct.pack("<Q", m["new"])); f.seek(m["toc_chunk_off"]); f.write(struct.pack("<Q", m["new"]))
        with open(m["ucas"], "r+b") as f: f.seek(m["ucas_off"]); f.write(struct.pack("<Q", m["new"]))
        s2 = id_sites(m["utoc"])
        if not s2 or s2["id"] != m["new"]: raise SystemExit("verify failed for %s: run revert" % m["pak"])
    return man, skipped

def revert_fix(backup):
    import json
    man = json.loads((pathlib.Path(backup) / "manifest.json").read_text()); n = 0
    for m in man:
        s = id_sites(m["utoc"])
        if not s or s["id"] != m["new"]: continue            # not patched by us (or changed since): leave alone
        with open(m["utoc"], "r+b") as f:
            f.seek(56); f.write(struct.pack("<Q", m["old"])); f.seek(m["toc_chunk_off"]); f.write(struct.pack("<Q", m["old"]))
        with open(m["ucas"], "r+b") as f: f.seek(m["ucas_off"]); f.write(struct.pack("<Q", m["old"]))
        n += 1
    return n

def main(argv):
    import argparse, time
    ap = argparse.ArgumentParser(prog="slots", description="Stellar Blade anim slot organizer (scan/plan only so far)")
    ap.add_argument("cmd", choices=["scan", "plan", "fixids", "revert"]); ap.add_argument("--game"); ap.add_argument("--ceiling", type=int, default=1000)
    ap.add_argument("--apply", action="store_true", help="fixids: really write (default: dry run)"); ap.add_argument("--backup", default="slot_backups"); ap.add_argument("--cache", default="slot_cache.json"); ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args(argv); g = find_game(a.game)
    if not g: print("Stellar Blade not found; pass --game <...>\SB or set SB_GAME"); return 2
    if a.cmd == "revert":
        import glob
        dirs = sorted(glob.glob(a.backup + "/ids-*"))
        if not dirs: print("no backup in", a.backup); return 2
        print("restored %d container id(s) from %s" % (revert_fix(dirs[-1]), dirs[-1])); return 0
    t = time.time(); inv = scan(g / "Content" / "Paks", None if a.no_cache else a.cache)
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
        bk = "%s/ids-%s" % (a.backup, _t.strftime("%Y%m%d-%H%M%S"))
        done, skipped = apply_fix(g / "Content" / "Paks", fx, bk)
        for k, why in skipped: print("  skipped %s: %s" % (k, why))
        print("changed %d container id(s); undo with: python slots.py revert (backup %s)" % (len(done), bk)); return 0
    if a.cmd == "plan":
        mv = plan(inv, a.ceiling)
        for k, o, n in mv: print("  %s: %d -> %d" % (k, o, n))
        print("%d moves proposed (nothing is changed on disk yet)" % len(mv))
    return 1 if cl else 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
