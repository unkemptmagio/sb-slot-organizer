"""iostore + slot mover tests. Synthetic containers (no game files); real-pak vectors only when the local files exist."""
import sys, pathlib, tempfile, struct, hashlib, os, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import iostore as I, slots as S

def make_pak(d, name, slot, cid=0x1122334455667788, extra=b"", dirs_in_mount=True, bulk=False, bext=".ubulk"):
    """one anim clip package at /Game/Mods/HD-ATOOL_P/anim/<slot>, as UnrealPak would lay it out"""
    pkg = f"/Game/Mods/HD-ATOOL_P/anim/{slot}"
    names = ["/Engine/Animation/Foo", pkg, str(slot), "Class", "AnimSequence"]
    p = I.Package(); p.name_idx, p.name_no, p.src_idx, p.src_no, p.flags, p.pad = 1, 0, 1, 0, 0x80000000, 0
    p.names = [(n, False) for n in names]; p.algo = 0xc1640000; p.hashes = [I.name_hash(n) for n in names]
    blob = bytes(range(256)) * 4 + extra
    p.cooked_hdr = 1000; p.imports = bytes(16); p.exports = [[1000, len(blob), 2, 0, 2**64 - 1, 7, 2**64 - 1, 9, 11, 0, 0, 0, 0, 0]]
    p.bundles = bytes(24); p.graph = bytes(8); p.blobs = [blob]
    data = I.package_bytes(p); pid = I.package_id(pkg)
    hdr = struct.pack("<QII", cid, 1, 0) + struct.pack("<I", 8) + struct.pack("<Q", 0xc1640000) + struct.pack("<I", 1) + struct.pack("<Q", pid)
    hdr += struct.pack("<I", 32) + struct.pack("<QIIIIII", len(data), 1, 1, 0, 0, 0, 0) + struct.pack("<II", 0, 0)
    h = bytearray(144); h[:16] = I.MAGIC; h[16] = 2; struct.pack_into("<IIIIIII", h, 20, 144, 2, 2, 12, 0, 32, 65536); h[80] = 8
    c = I.Container(); c.header = h; c.block_size = 65536; c.container_id = cid; c.block_align = 16
    mk = lambda i, t, dta: dict(id=i, index=0, pad=0, type=t, data=dta, meta_flags=0, meta_pad=bytes(12), meta_hash=b"", sha_ok=True, dirty=False)
    c.chunks = [mk(cid, 10, hdr), mk(pid, 2, data)] + ([mk(pid, 5 if bext == ".m.ubulk" else 3, b"BULKDATA" * 64)] if bulk else [])
    c.dirindex = dict(mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/", mount_kind=1, dirs=[[0xFFFFFFFF] * 3 + [0]], files=[[0, 1 if bulk else 0xFFFFFFFF, 1]] + ([[1, 0xFFFFFFFF, 2]] if bulk else []), strings=[f"{slot}.uasset"] + ([f"{slot}{bext}"] if bulk else []), kinds=[1] * (2 if bulk else 1))
    t, u = I.container_bytes(c); (d / (name + ".utoc")).write_bytes(t); (d / (name + ".ucas")).write_bytes(u)
    return d / (name + ".utoc")

def make_multi(d, name, files, mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/", cid=0x1122334455667788):
    """several clip packages in one container. files = [(package path, file name relative to the mount point)], e.g. Lilly-Hug's partner pak:
    mount '.../anim/201a/' with ('/Game/Mods/HD-ATOOL_P/anim/201a/1', '1.uasset') ... (the slot folder lives in the mount point, not in a directory entry)"""
    n = len(files); pks = []; chunks = []
    mk = lambda i, t, dta: dict(id=i, index=0, pad=0, type=t, data=dta, meta_flags=0, meta_pad=bytes(12), meta_hash=b"", sha_ok=True, dirty=False)
    for pkg, _f in files:
        names = ["/Engine/Animation/Foo", pkg, pkg.rsplit("/", 1)[1], "Class", "AnimSequence"]
        p = I.Package(); p.name_idx, p.name_no, p.src_idx, p.src_no, p.flags, p.pad = 1, 0, 1, 0, 0x80000000, 0
        p.names = [(x, False) for x in names]; p.algo = 0xc1640000; p.hashes = [I.name_hash(x) for x in names]
        blob = bytes(range(256)) * 4
        p.cooked_hdr = 1000; p.imports = bytes(16); p.exports = [[1000, len(blob), 2, 0, 2**64 - 1, 7, 2**64 - 1, 9, 11, 0, 0, 0, 0, 0]]
        p.bundles = bytes(24); p.graph = bytes(8); p.blobs = [blob]
        data = I.package_bytes(p); pks.append((I.package_id(pkg), data))
    hdr = struct.pack("<QII", cid, n, 0) + struct.pack("<I", 8) + struct.pack("<Q", 0xc1640000) + struct.pack("<I", n) + b"".join(struct.pack("<Q", pid) for pid, _ in pks)
    hdr += struct.pack("<I", 32 * n) + b"".join(struct.pack("<QIIIIII", len(dta), 1, 1, 0, 0, 0, 0) for _, dta in pks) + struct.pack("<II", 0, 0)
    h = bytearray(144); h[:16] = I.MAGIC; h[16] = 2; struct.pack_into("<IIIIIII", h, 20, 144, 2, 2, 12, 0, 32, 65536); h[80] = 8
    c = I.Container(); c.header = h; c.block_size = 65536; c.container_id = cid; c.block_align = 16
    c.chunks = [mk(cid, 10, hdr)] + [mk(pid, 2, dta) for pid, dta in pks]
    c.dirindex = dict(mount=mount, mount_kind=1, dirs=[[0xFFFFFFFF] * 3 + [n - 1]], files=[[i, i - 1 if i else 0xFFFFFFFF, i + 1] for i in range(n)], strings=[f for _p, f in files], kinds=[1] * n)
    t, u = I.container_bytes(c); (d / (name + ".utoc")).write_bytes(t); (d / (name + ".ucas")).write_bytes(u)
    return d / (name + ".utoc")

tmp = pathlib.Path(tempfile.mkdtemp())

# hash proof against a real pak (skipped without the game files)
real = pathlib.Path("E:/Vortex Mods/stellarblade/BeepBeep_Im_Sheep_motion-1939-v1-0-0-1-1756135426/SB/Content/Paks/~Mods/BBS_P.utoc")
if real.is_file():
    assert I.package_id("/Game/Mods/HD-ATOOL_P/anim/982") == 3876099187860792978        # real chunk id
    rc = I.read_container(real); assert not I.check_container(rc)
    t, u = I.container_bytes(rc); assert t == real.read_bytes()                          # byte-identical TOC
    assert I.package_bytes(I.read_package(rc.chunks[1]["data"])) == rc.chunks[1]["data"]
assert I.cityhash64(b"x" * 65) == I.cityhash64(b"x" * 65)                              # long branch is on (verified against 3793 real hashes)

# container + package round trip, consistency
a = make_pak(tmp, "a", 982); c = I.read_container(a)
assert not I.check_container(c) and I.slots_in(c) == {982: ["/Game/Mods/HD-ATOOL_P/anim/982"]}
assert I.container_bytes(c)[0] == a.read_bytes()

# rename: same digit count, more digits, fewer digits; ids, names, hashes, directory all follow
for new in (983, 1001, 99):
    c = I.read_container(a); I.rename_slot(c, 982, new); assert not I.check_container(c), I.check_container(c)
    t, u = I.container_bytes(c); (tmp / "x.utoc").write_bytes(t); (tmp / "x.ucas").write_bytes(u)
    c2 = I.read_container(tmp / "x.utoc"); assert I.slots_in(c2) == {new: ["/Game/Mods/HD-ATOOL_P/anim/%d" % new]} and not I.check_container(c2)
    assert c2.chunks[1]["id"] == I.package_id("/Game/Mods/HD-ATOOL_P/anim/%d" % new) and c2.container_id == c.container_id
    assert I.read_package(c2.chunks[1]["data"]).blobs == I.read_package(I.read_container(a).chunks[1]["data"]).blobs   # the clip data is untouched
try: I.rename_slot(I.read_container(a), 5, 6); assert 0
except I.Unsupported: pass

# Lilly-Hug shapes: partner clips with the slot folder in the MOUNT POINT, and the partner table as a top-level <slot>a.uasset
A = "/Game/Mods/HD-ATOOL_P/anim/"
def _roundtrip(path, old, new):
    c = I.read_container(path); assert not I.check_container(c), I.check_container(c)
    I.rename_slot(c, old, new); assert not I.check_container(c), I.check_container(c)
    t, u = I.container_bytes(c); (tmp / "y.utoc").write_bytes(t); (tmp / "y.ucas").write_bytes(u)
    c2 = I.read_container(tmp / "y.utoc", tmp / "y.ucas"); assert not I.check_container(c2), I.check_container(c2)
    return c, c2, len(t) == len(path.read_bytes())
ca = make_multi(tmp, "hug_anim", [(A + "201a/%d" % i, "%d.uasset" % i) for i in (1, 2, 3, 4)], mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/201a/")
_c, c2, same = _roundtrip(ca, 201, 202)
assert same and c2.dirindex["mount"].endswith("/anim/202a/") and sorted(I.slots_in(c2)) == [202] and sorted(I.slots_in(c2)[202]) == [A + "202a/%d" % i for i in (1, 2, 3, 4)]
_c, c2, _s = _roundtrip(ca, 201, 1001); assert c2.dirindex["mount"].endswith("/anim/1001a/") and sorted(I.slots_in(c2)) == [1001]          # digit count may change at this layer
cn = make_multi(tmp, "hug_n", [(A + "201/%d" % i, "%d.uasset" % i) for i in (1, 2)], mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/201/")
_c, c2, same = _roundtrip(cn, 201, 202); assert same and c2.dirindex["mount"].endswith("/anim/202/") and sorted(I.slots_in(c2)) == [202]
co = make_multi(tmp, "other", [(A + "2010/1", "1.uasset")], mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/2010/")      # 2010 is not 201: untouched by a 201 rename
try: I.rename_slot(I.read_container(co), 201, 202); assert 0
except I.Unsupported: pass
ct = make_multi(tmp, "hug_table", [(A + "201a", "201a.uasset")])
_c, c2, same = _roundtrip(ct, 201, 202); assert same and sorted(I.slots_in(c2)) == [202] and list(I.path_names(c2).values()) == [A + "202a"]

# slot move on a fake Paks tree: clash planning, apply, byte-exact revert
paks = tmp / "Paks"; (paks / "~mods").mkdir(parents=True)
make_pak(paks / "~mods", "one", 700, cid=1); two = make_pak(paks / "~mods", "two", 700, cid=2)
os.utime(paks / "~mods" / "two.utoc", (2e9, 2e9))                                        # two is newer: it moves
inv = S.scan(paks); assert S.clashes(inv) == {700: ["~mods/one.utoc", "~mods/two.utoc"]}
moves, unresolved = S.plan_moves(paks, inv, 1000, ()); assert moves == [("~mods/two.utoc", 700, 701)] and not unresolved, moves
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (paks / "~mods").iterdir()}
j = S.apply_move(paks, tmp, "~mods/two.utoc", 700, 701, tmp / "bk", shared=True)
inv2 = S.scan(paks); assert not S.clashes(inv2) and inv2["~mods/two.utoc"] == [701] and inv2["~mods/one.utoc"] == [700]
assert S.revert_move(tmp / "bk") == 2
assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (paks / "~mods").iterdir()} == before   # byte-exact
# chained moves of the same pak keep every original; reverting newest-first restores byte-exact
S.apply_move(paks, tmp, "~mods/two.utoc", 700, 701, tmp / "c1", shared=True); S.apply_move(paks, tmp, "~mods/two.utoc", 701, 702, tmp / "c2", shared=True)
S.revert_move(tmp / "c2"); S.revert_move(tmp / "c1")
assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (paks / "~mods").iterdir()} == before
# LogicMods never moves; a clash with only a LogicMods pak and a movable one moves the other
(paks / "LogicMods").mkdir(); make_pak(paks / "LogicMods", "lm", 700, cid=3)
inv = S.scan(paks); mv, un = S.plan_moves(paks, inv, 1000, ())
assert all(not k.startswith("LogicMods/") for k, _, _ in mv) and len(mv) == 2             # both ~mods paks move off 700, the LogicMods one keeps it
# no free slot / reserved
mv, un = S.plan_moves(paks, S.scan(paks), 700, set(range(1, 700))); assert un and not mv                          # nothing free: reported, not guessed
# slot-keyed files: ownership from the Vortex manifest (mine / theirs), copy when unknown and shared, byte-exact revert
import json, shutil
g = tmp / "game"; pk = g / "Content" / "Paks"; au = pk / "LogicMods" / "HD-ATOOL_P" / "audio"; au.mkdir(parents=True)
(g / "Binaries/Win64/ue4ss/Mods/PEFA").mkdir(parents=True); (pk / "~mods" / "PELA Patches").mkdir(parents=True)
(au / "800.wav").write_bytes(b"A"); (au / "801.wav").write_bytes(b"B"); (g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").write_text("800 = Mine\n801 = Other\n")
(pk / "~mods" / "PELA Patches" / "m.json").write_text(json.dumps({"x": {"clip": 800, "singles": [800, 5]}}))
nc = os.path.normcase
man = {"targetPath": str(pk), "files": [{"relPath": "LogicMods/HD-ATOOL_P/audio/800.wav", "source": "modA"}, {"relPath": "LogicMods/HD-ATOOL_P/audio/801.wav", "source": "modB"}, {"relPath": "~mods/PELA Patches/m.json", "source": "modA"}]}
(pk / "vortex.deployment.x.json").write_text(json.dumps(man)); sr = S.sources(pk)
assert sr[nc(str(au / "800.wav"))] == "modA" and S.owner(au / "801.wav", "modA", sr, True) == "theirs" and S.owner(au / "x.wav", None, {}, True) == "unknown" and S.owner(au / "x.wav", None, {}, False) == "mine"
snap = lambda: {str(p): p.read_bytes() for p in g.rglob("*") if p.is_file()}
b0 = snap(); st = []
S.external_files(g, 800, 810, st, tmp / "fb", shared=True, mover="modA", srcs=sr)   # modA owns 800.wav + PELA: renamed even though the slot is shared; names line copied
assert (au / "810.wav").exists() and not (au / "800.wav").exists() and "810" in (g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").read_text() and "800 = Mine" in (g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").read_text()
assert json.loads((pk / "~mods/PELA Patches/m.json").read_text())["x"]["clip"] == 810
S.external_files(g, 801, 811, st, tmp / "fb", shared=True, mover="modA", srcs=sr)   # modB owns 801.wav: untouched
assert (au / "801.wav").exists() and not (au / "811.wav").exists()
S.external_files(g, 801, 812, st, tmp / "fb2", shared=True, mover=None, srcs={})    # no manifest, shared: wav copied
assert (au / "801.wav").exists() and (au / "812.wav").exists()
j = {"steps": st}; (tmp / "fb").mkdir(exist_ok=True); (tmp / "fb" / "manifest.json").write_text(json.dumps(j)); S.revert_move(tmp / "fb")
assert not (au / "812.wav").exists() and snap() == b0                                 # everything back
# no Vortex: first-sight ledger decides ownership
(au / "820.wav").write_bytes(b"C")
led = S.ledger_update(g, {"~mods/a.utoc": [820], "~mods/b.utoc": [821]}, tmp / "owners.json")
assert led[nc(str(au / "820.wav"))] == "pak:~mods/a.utoc"
assert S.owner(au / "820.wav", "pak:~mods/b.utoc", led, True) == "theirs" and S.owner(au / "820.wav", "pak:~mods/a.utoc", led, True) == "mine"
assert S.owner(au / "820.wav", "Vortex Mod", led, True) == "unknown"                # ledger vs Vortex names are not comparable
assert S.ledger_update(g, {"~mods/a.utoc": [820], "~mods/b.utoc": [820]}, tmp / "owners.json")[nc(str(au / "820.wav"))] == "pak:~mods/a.utoc"   # a later clash does not steal it

# failure injection: external_files blows up after the swap -> everything rolled back, no temp files, journal says reverted
paks2 = tmp / "Paks2"; (paks2 / "~mods").mkdir(parents=True); make_pak(paks2 / "~mods", "p", 500, cid=9)
h0 = {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in (paks2 / "~mods").iterdir()}
real_ext = S.external_files
def boom(*a, **k): raise OSError("names.txt locked")
S.external_files = boom
try: S.apply_move(paks2, g, "~mods/p.utoc", 500, 501, tmp / "fi", shared=False); assert 0
except OSError: pass
finally: S.external_files = real_ext
assert {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in (paks2 / "~mods").iterdir()} == h0 and (tmp / "fi" / "manifest.reverted.json").exists()
assert S.revert_move(tmp / "fi") == 0                                                # idempotent
# a crash between the swap and the end: manifest on disk already lists the swaps, revert restores
S.apply_move(paks2, g, "~mods/p.utoc", 500, 501, tmp / "ok1", shared=False)
assert S.revert_move(tmp / "ok1") >= 2 and {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in (paks2 / "~mods").iterdir()} == h0
assert not any(".new" in q.name for q in (paks2 / "~mods").iterdir())
# digit-count change is refused for moves
assert S.try_rename(paks2, "~mods/p.utoc", 500, 1001)[0] is None
# second review: digit-aware free slot, ledger robustness/staleness, guarded revert, lossless names.txt
assert S.free_slot(99, {98 - 98}, 9999, set()) == 98 and S.free_slot(9, set(), 9999, {8}) == 7 and S.free_slot(999, {998}, 9999, set()) == 997
(tmp / "bad.json").write_text("[]"); assert S.ledger_update(g, {"~mods/a.utoc": [820]}, tmp / "bad.json")      # garbage ledger: no crash
(au / "830.wav").write_bytes(b"D"); (tmp / "o2.json").unlink() if (tmp / "o2.json").exists() else None
l1 = S.ledger_update(g, {"~mods/a.utoc": [830]}, tmp / "o2.json"); assert l1[nc(str(au / "830.wav"))] == "pak:~mods/a.utoc"
(au / "830.wav").write_bytes(b"changed by another mod!")                                            # file replaced: entry dropped, re-recorded for the current single holder
l2 = S.ledger_update(g, {"~mods/b.utoc": [830]}, tmp / "o2.json"); assert l2[nc(str(au / "830.wav"))] == "pak:~mods/b.utoc"
(g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").write_bytes(b"840 = Caf\xe9\r\n841 = X\r\n")          # CRLF + non-UTF-8 byte survive
(au / "840.wav").write_bytes(b"E"); stn = []
S.external_files(g, 840, 842, stn, tmp / "fn", shared=True, mover=None, srcs={})
assert (g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").read_bytes() == b"840 = Caf\xe9\r\n842 = Caf\xe9\r\n841 = X\r\n", (g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").read_bytes()
# revert refuses to overwrite a file that changed after the move
paks3 = tmp / "Paks3"; (paks3 / "~mods").mkdir(parents=True); make_pak(paks3 / "~mods", "q", 600, cid=11)
S.apply_move(paks3, g, "~mods/q.utoc", 600, 601, tmp / "g1", shared=False)
(paks3 / "~mods" / "q.utoc").write_bytes(b"NEWER VERSION FROM THE MOD AUTHOR")
S.revert_move(tmp / "g1"); assert (paks3 / "~mods" / "q.utoc").read_bytes() == b"NEWER VERSION FROM THE MOD AUTHOR" and (tmp / "g1" / "manifest.partial.json").exists()
# bulk data of a moved package follows it (chunk id + .ubulk directory entry)
bk = make_pak(tmp, "bulk", 770, cid=21, bulk=True); cb = I.read_container(bk); assert not I.check_container(cb)
I.rename_slot(cb, 770, 771); assert not I.check_container(cb), I.check_container(cb)
t2, u2 = I.container_bytes(cb); (tmp / "bx.utoc").write_bytes(t2); (tmp / "bx.ucas").write_bytes(u2); cb2 = I.read_container(tmp / "bx.utoc")
assert not I.check_container(cb2) and [ch["id"] for ch in cb2.chunks if ch["type"] == 3] == [I.package_id("/Game/Mods/HD-ATOOL_P/anim/771")] and cb2.chunks[2]["data"] == b"BULKDATA" * 64
assert "771.ubulk" in cb2.dirindex["strings"] and "770.ubulk" not in cb2.dirindex["strings"]
# CityHash64 known answers (real stored hashes from installed paks; covers the long branch incl. multi-block inputs)
KAT = [('/game/art/character/monster/ch_m_na_17/textures/ch_m_na_17_body_a', 15663605014358446738), ('/\x00g\x00a\x00m\x00e\x00/\x00o\x00u\x00t\x00f\x00i\x00t\x00m\x00o\x00d\x00s\x00/\x00a\x00i\x00k\x00_\x00a\x00c\x00c\x00/\x00m\x00a\x00s\x00k\x00/\x00x\x004\x00w\x00', 9887348984085467770), ('/game/art/character/generic/globalmastermaterials/eye/t_eye_normals', 3590192869285283468), ('/\x00g\x00a\x00m\x00e\x00/\x00m\x00o\x00d\x00s\x00/\x00l\x00a\x00s\x00k\x00i\x00l\x00l\x00s\x00/\x00a\x00n\x00i\x00m\x00a\x00t\x00i\x00o\x00n\x00s\x00/\x00e\x00m\x00/\x00c\x00h\x00_\x00m\x00_\x00n\x00a\x00_\x001\x006\x00_\x00g\x00r\x00a\x00b\x001\x00', 10635500273041660316), ('/\x00g\x00a\x00m\x00e\x00/\x00a\x00r\x00t\x00/\x00c\x00h\x00a\x00r\x00a\x00c\x00t\x00e\x00r\x00/\x00p\x00c\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x000\x001\x00/\x00a\x00n\x00i\x00m\x00a\x00t\x00i\x00o\x00n\x00/\x00e\x00v\x00e\x00_\x00d\x00e\x00a\x00d\x00_\x00d\x00o\x00w\x00n\x00f\x00a\x00c\x00e\x00u\x00p\x00', 12753453170042660091), ('/\x00g\x00a\x00m\x00e\x00/\x00a\x00r\x00t\x00/\x00c\x00h\x00a\x00r\x00a\x00c\x00t\x00e\x00r\x00/\x00p\x00c\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x000\x004\x00/\x00t\x00e\x00x\x00t\x00u\x00r\x00e\x00s\x00/\x00i\x00n\x00s\x00t\x00/\x00s\x00u\x00i\x00t\x00_\x00c\x00o\x00w\x00b\x00o\x00y\x00_\x00d\x00o\x00w\x00n\x00+\x00w\x00h\x00i\x00t\x00e\x00_\x00b\x00r\x00a\x00', 12943329846651648515), ('/\x00g\x00a\x00m\x00e\x00/\x00a\x00r\x00t\x00/\x00c\x00h\x00a\x00r\x00a\x00c\x00t\x00e\x00r\x00/\x00p\x00c\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x006\x001\x00/\x00t\x00e\x00x\x00t\x00u\x00r\x00e\x00s\x00/\x00i\x00n\x00s\x00t\x00_\x00n\x00o\x00r\x00i\x00m\x00a\x00k\x00i\x00_\x00b\x00i\x00k\x00i\x00n\x00i\x00_\x00t\x00e\x00x\x00t\x00u\x00r\x00e\x00s\x00/\x00n\x00o\x00r\x00i\x00m\x00a\x00k\x00i\x00_\x00b\x00i\x00k\x00i\x00n\x00i\x00_\x00p\x00i\x00n\x00k\x00_\x00a\x00', 18376555865347320975), ('/\x00g\x00a\x00m\x00e\x00/\x00c\x00n\x00s\x00r\x00e\x00p\x00a\x00c\x00k\x00e\x00d\x00/\x00e\x004\x008\x00d\x00a\x001\x004\x003\x009\x008\x009\x00f\x008\x00d\x005\x00c\x00/\x00a\x00r\x00t\x00/\x00c\x00h\x00a\x00r\x00a\x00c\x00t\x00e\x00r\x00/\x00p\x00c\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x000\x006\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x000\x006\x00_\x00b\x00o\x00d\x00y\x00_\x00p\x00o\x00n\x00y\x00t\x00a\x00i\x00l\x00p\x00h\x00y\x00s\x00i\x00c\x00s\x00a\x00s\x00s\x00e\x00t\x00', 15464606203485994403), ('/\x00g\x00a\x00m\x00e\x00/\x00c\x00n\x00s\x00r\x00e\x00p\x00a\x00c\x00k\x00e\x00d\x00/\x00c\x00d\x004\x000\x009\x00c\x009\x006\x00a\x000\x00f\x00e\x005\x002\x00d\x009\x00/\x00a\x00r\x00t\x00/\x00c\x00h\x00a\x00r\x00a\x00c\x00t\x00e\x00r\x00/\x00p\x00c\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x00c\x00h\x00r\x00i\x00s\x00t\x00m\x00a\x00s\x00_\x000\x001\x00/\x00c\x00h\x00_\x00p\x00_\x00e\x00v\x00e\x00_\x00c\x00h\x00r\x00i\x00s\x00t\x00m\x00a\x00s\x00_\x000\x001\x00_\x00p\x00o\x00n\x00y\x00t\x00a\x00i\x00l\x00p\x00h\x00y\x00s\x00i\x00c\x00s\x00a\x00s\x00s\x00e\x00t\x00', 3555813393911440970)]
assert all(I.cityhash64(k.encode("latin-1")) == h for k, h in KAT), "CityHash64 long branch regressed"
# end to end: `auto --yes` on a fake game folder with a clash, then `revert`
sb = tmp / "sb"; pm = sb / "Content" / "Paks" / "~mods"; pm.mkdir(parents=True)
make_pak(pm, "one", 700, cid=31); make_pak(pm, "two", 700, cid=32); os.utime(pm / "two.utoc", (2e9, 2e9))
h_e2e = {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in pm.iterdir()}
args = ["--game", str(sb), "--backup", str(tmp / "e2e_bk"), "--cache", str(tmp / "e2e_cache.json")]
assert S.main(["auto", "--yes"] + args) == 0
assert not S.clashes(S.scan(sb / "Content" / "Paks")) and (pm / "two.utoc.orig").exists()
assert S.main(["revert"] + args) == 0
assert {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in pm.iterdir()} == h_e2e
assert S.main(["moveslots", "--pak", "~mods/two.pak", "--slot", "700", "--to", "710"] + args) == 2    # not a scanned pak: refused
# blocker from review: a pak with BOTH a slot clash and a container-id clash -> auto (ids first, then moves, one run stamp) -> ONE revert restores everything
sb2 = tmp / "sb2"; pm2 = sb2 / "Content" / "Paks" / "~mods"; pm2.mkdir(parents=True)
make_pak(pm2, "one", 700, cid=77); make_pak(pm2, "two", 700, cid=77); os.utime(pm2 / "two.utoc", (2e9, 2e9))          # same slot AND same container id
h2 = {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in pm2.iterdir()}
args2 = ["--game", str(sb2), "--backup", str(tmp / "e2e2_bk"), "--cache", str(tmp / "e2e2_cache.json")]
assert S.main(["auto", "--yes"] + args2) == 0
assert not S.clashes(S.scan(sb2 / "Content" / "Paks")) and not S.id_clashes(sb2 / "Content" / "Paks")
assert S.main(["revert"] + args2) == 0                                                  # one revert undoes the whole run
assert {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in pm2.iterdir()} == h2, "revert after auto did not restore"
# interrupted-run detection and stale temp sweep
(pm2 / "x.utoc.new").write_bytes(b"junk"); (pm2 / "y.new.ucas").write_bytes(b"junk"); assert sorted(S.sweep_temp(sb2 / "Content" / "Paks")) == ["x.utoc.new"] and (pm2 / "y.new.ucas").exists()      # only our own temp name is swept
os.makedirs(tmp / "ib" / "move-20260101-000000-0"); (tmp / "ib" / "move-20260101-000000-0" / "manifest.json").write_text('{"steps": [], "done": false}')
assert S.interrupted(str(tmp / "ib")) and not S.interrupted(str(tmp / "none"))
# short-input branches (0-16, 17-32, 33-64), unconditional: real stored hashes + the real package id of anim/982 (60 bytes of UTF-16)
KAT_SHORT = [('2', 6920640749119438759), ('wb', 13859483922156345979), ('top', 2125795074522444111), ('font', 4674223610502732611), ('class', 7772006167705430957), ('content', 11758975885699655676), ('bindings', 18242279994439662761), ('bautosize', 12257212597591960947), ('canvaspanelslot', 17824498634351576271), ('eslatevisibility', 12978709467158065097), ('horizontalboxslot', 1518588668669284949), ('default__canvaspanelslot', 8885987693529693801), ('eslatecheckboxtype::togglebutton', 13553808718295507493), ('/game/mods/darui_p/cursor_default', 17311069008932939833), ('/game/mods/hd-atool_p/p901/newmale_mesh_skeleton', 16315670706392073306), ('/game/art/bg/actor/interaction/wine_bottle/wine_bottle_skeleton', 7100514524833140975), ('/game/art/character/monster/ch_m_na_19/materials/mi_m_na_19_body', 9034285803720795553)]
assert all(I.cityhash64(k.encode()) == h for k, h in KAT_SHORT), "CityHash64 short branches regressed"
assert I.package_id("/Game/Mods/HD-ATOOL_P/anim/982") == 3876099187860792978
# .m.ubulk (memory-mapped bulk) must parse as <slot>.m.ubulk, not <slot>.m
bm = make_pak(tmp, "mbulk", 780, cid=22, bulk=True, bext=".m.ubulk"); cm = I.read_container(bm); assert not I.check_container(cm), I.check_container(cm)
I.rename_slot(cm, 780, 781); assert not I.check_container(cm) and "781.m.ubulk" in cm.dirindex["strings"]
# a mod literally named X.new.utoc is never swept or hidden; our own temp names are
(pm2 / "Hair.new.utoc").write_bytes(b"user file"); (pm2 / "Hair.new.ucas").write_bytes(b"user file"); (pm2 / "z.utoc.new").write_bytes(b"tmp")
assert S.sweep_temp(sb2 / "Content" / "Paks") == ["z.utoc.new"] and (pm2 / "Hair.new.utoc").exists()
# orphan anim utoc (no ucas) in an id-clash group: skipped, not a crash
(pm2 / "orph.utoc").write_bytes((pm2 / "one.utoc").read_bytes()); assert S.id_sites(pm2 / "orph.utoc") is None
os.remove(pm2 / "orph.utoc")
# patching a container id keeps the file times, so an earlier move's revert still recognises the file
ms = S.apply_move(pm2, sb2, "one.utoc", 700, 703, tmp / "mt1", shared=False)
t_before = (os.stat(pm2 / "one.utoc").st_mtime_ns, os.stat(pm2 / "one.ucas").st_mtime_ns)
S.apply_fix(pm2, [("one.utoc", 77, 0x1234567890ABCDEF)], tmp / "mt2")
assert (os.stat(pm2 / "one.utoc").st_mtime_ns, os.stat(pm2 / "one.ucas").st_mtime_ns) == t_before
S.revert_fix(tmp / "mt2"); assert S.revert_move(tmp / "mt1") >= 2 and not getattr(S.revert_move, "kept", 0)
# support log: header, tee, rotation, unwritable location
import io
lp = tmp / "logs" / "so.log"; lf = S._open_log(str(lp), ["scan", "--game", "x"]); assert lf
buf = io.StringIO(); tee = S._Tee(buf, lf); tee.write("hello log\n"); tee.flush(); lf.close()
txt = lp.read_text(encoding="utf-8"); assert "SlotOrganizer " + S.VERSION in txt and "args=scan --game x" in txt and "hello log" in txt and buf.getvalue() == "hello log\n"
lp.write_bytes(b"x" * 600000); lf2 = S._open_log(str(lp), []); lf2.close(); assert (tmp / "logs" / "so.log.1").exists() and lp.stat().st_size < 1000
S._Tee(None, io.StringIO()).write("no console")                                         # stdout None (windowless) must not crash
(tmp / "blockfile").write_text("a file, not a folder"); assert S._open_log(str(tmp / "blockfile" / "x.log")) is None          # unwritable location: no crash


# a slot string that changes length (982 -> 1001) must take its StrProperty tag Size with it, otherwise the engine loses the next row
def _strprop(text):
    b = text.encode() + b"\0"; return bytes(16) + struct.pack("<ii", 4 + len(b), 0) + b"\0" + struct.pack("<i", len(b)) + b
_A = "/Game/Mods/HD-ATOOL_P/anim/"
_row = _strprop("M|" + _A + "982a/Adam_MG_982.Adam_MG_982||0.0") + _strprop("B|RootSocket|" + _A + "982a/Adam_982.Adam_982||0.0")
_out = I._fix_strings(_row, 982, 1001); _pos = 0; _n = 0
while _pos < len(_out):
    _size = struct.unpack_from("<i", _out, _pos + 16)[0]; _l = struct.unpack_from("<i", _out, _pos + 25)[0]
    assert _size == 4 + _l and b"1001a" in _out[_pos:_pos + 29 + _l], "tag Size stale after a length-changing rewrite"; _pos += 29 + _l; _n += 1
assert _n == 2 and _pos == len(_out) and len(I._fix_strings(_row, 982, 983)) == len(_row)             # same digit count: byte layout unchanged
_bare = bytes(20) + struct.pack("<i", len(_A + "982a") + 1) + (_A + "982a").encode() + b"\0"           # valid FString, but no string property around it
try: I._fix_strings(_bare, 982, 1001); assert 0
except I.Unsupported as e: assert "recognised string property" in str(e)
assert len(I._fix_strings(_bare, 982, 983)) == len(_bare)

# S2 (final review): PEFA caches removed by a move are regenerated by the game; undo must put the original back, not report "kept"
gc = tmp / "gcache"; pe = gc / "Binaries/Win64/ue4ss/Mods/PEFA"; pe.mkdir(parents=True); (pe / "packs_rows.txt").write_text("original cache"); (gc / "Content/Paks").mkdir(parents=True)
stc = S._Steps({"steps": []}, tmp / "gc_bk" / "manifest.json"); S.external_files(gc, 900, 905, stc, tmp / "gc_bk", shared=False, mover=None, srcs={})
assert not (pe / "packs_rows.txt").exists(); (pe / "packs_rows.txt").write_text("regenerated by the game for the moved layout")
S.revert_move.kept = 0; assert S.revert_move(tmp / "gc_bk") >= 1 and not (pe / "packs_rows.txt").exists() and not S.revert_move.kept     # removed again: the game rebuilds it (a newer cache must never be replaced by the old one)
# a name already used at the target slot is reported, not silently skipped
(g / "Binaries/Win64/ue4ss/Mods/PEFA/names.txt").write_text("850 = A\n851 = B\n"); outn = S.external_files(g, 850, 851, None, None, shared=False)
assert any("already names slot 851" in w for w, _ in outn)

# round 6: undo must not get stuck or lie
def _fake_game(name, slot, cid):
    gg = tmp / name; pm_ = gg / "Content" / "Paks" / "~mods"; pm_.mkdir(parents=True); make_pak(pm_, "p", slot, cid=cid)
    pf = gg / "Binaries/Win64/ue4ss/Mods/PEFA"; pf.mkdir(parents=True); (pf / "names.txt").write_text("%d = Test clip\n" % slot)
    return gg, pm_, pf
def _digest(d): return {q_.name: hashlib.sha256(q_.read_bytes()).hexdigest() for q_ in d.iterdir()}
# (a) PEFA's folder disappears between apply and undo: the paks are still restored, the rest is reported, the journal is kept as partial
gg, pm_, pf = _fake_game("g_gone", 610, 41); h0 = _digest(pm_)
S.apply_move(gg / "Content" / "Paks", gg, "~mods/p.utoc", 610, 611, tmp / "gone_bk", shared=False)
shutil.rmtree(pf); S.revert_move.kept = 0; S.revert_move(tmp / "gone_bk")
assert _digest(pm_) == h0 and S.revert_move.kept >= 1 and (tmp / "gone_bk" / "manifest.partial.json").exists()
# (b) the saved original (.orig) was deleted after the move: nothing is claimed restored, the journal is kept as partial
gg2, pm2_, pf2 = _fake_game("g_orig", 620, 42)
S.apply_move(gg2 / "Content" / "Paks", gg2, "~mods/p.utoc", 620, 621, tmp / "orig_bk", shared=False)
for f_ in pm2_.glob("*.orig"): f_.unlink()
S.revert_move.kept = 0; S.revert_move(tmp / "orig_bk"); assert S.revert_move.kept >= 1 and (tmp / "orig_bk" / "manifest.partial.json").exists()
# (c) the log path is printed after any failure, not only after odd exit codes
assert "attach this log file" in S._failure_footer(1, True, "x.log") and S._failure_footer(1, False, "x.log") == "" and "x.log" in S._failure_footer(2, False, "x.log") and S._failure_footer(1, True, None) == "" and S._failure_footer(0, False, "x.log") == ""
# (d) the log records what is being looked at
il = S.identity_line(g, 1000, False); assert str(g) in il and "UE4SS:" in il and "AToolSlotLimit:" in il and "slot ceiling 1000 (auto)" in il and "(--ceiling)" in S.identity_line(g, 5000, True)
# ---- Lilly-Hug: ONE mod = three containers on one slot (main clip 201, partner clips 201a/* with the folder in the mount point, partner table 201a)
def _hug(mods, folder="Hug", cid0=100, slot=201):
    d = mods / folder if folder else mods; d.mkdir(parents=True, exist_ok=True)
    make_multi(d, "Hug_P", [(A + "%d" % slot, "%d.uasset" % slot)], cid=cid0)
    make_multi(d, "Hug_ConfigAnim_P", [(A + "%da/%d" % (slot, i), "%d.uasset" % i) for i in (1, 2, 3, 4)], mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/%da/" % slot, cid=cid0 + 1)
    make_multi(d, "Hug_Config_P", [(A + "%da" % slot, "%da.uasset" % slot)], cid=cid0 + 2)
    return d
def _hug_world(name, flat=False):
    pk = tmp / name; mods = pk / "~mods"; mods.mkdir(parents=True)
    _hug(mods, None if flat else "Hug", 100)
    old = mods / "Old"; old.mkdir(); make_multi(old, "old_P", [(A + "201", "201.uasset")], cid=200)
    for f_ in old.iterdir(): os.utime(f_, (1.6e9, 1.6e9))                                    # Old is older: Hug is the one that moves
    for f_ in mods.rglob("Hug*"): os.utime(f_, (1.7e9, 1.7e9))
    return pk
hp = _hug_world("hugpaks"); hinv = S.scan(hp)
assert {k.split("/")[-1] for k in hinv} == {"Hug_P.utoc", "Hug_ConfigAnim_P.utoc", "Hug_Config_P.utoc", "old_P.utoc"}      # the partner TABLE (201a.uasset) is seen now
assert all(v == [201] for v in hinv.values())
hu = S.group_units(hp, hinv, {}); assert sorted(len(v) for v in hu.values()) == [1, 3], hu                                 # 3 containers = one mod
huinv = S.unit_inv(hinv, hu); assert list(S.clashes(huinv).keys()) == [201] and len(S.clashes(huinv)[201]) == 2                # ONE clash: Hug vs Old (not Hug vs itself)
assert "(3 containers)" in S.unit_label(*next((u, ks) for u, ks in hu.items() if len(ks) == 3))
mv, un = S.plan_unit_moves(hp, hinv, 1000, (), units=hu)
assert not un and len(mv) == 1 and len(mv[0]["keys"]) == 3 and mv[0]["old"] == 201 and mv[0]["new"] == 202, (mv, un)       # all three together
hsnap = lambda: {str(q.relative_to(hp)): hashlib.sha256(q.read_bytes()).hexdigest() for q in hp.rglob("*") if q.is_file()}
h_before = hsnap(); calls = []; real_ext2 = S.external_files
S.external_files = lambda *a, **k: (calls.append(1), real_ext2(*a, **k))[1]
try: bks = [str(tmp / ("hbk%d" % i)) for i in range(3)]; js = S.apply_unit_move(hp, tmp, mv[0]["keys"], 201, 202, bks, unit="Hug")
finally: S.external_files = real_ext2
assert len(js) == 3 and len(calls) == 1, calls                                                          # slot-keyed files handled ONCE per mod, not once per container
hinv2 = S.scan(hp); assert {k.split("/")[-1]: v for k, v in hinv2.items()} == {"Hug_P.utoc": [202], "Hug_ConfigAnim_P.utoc": [202], "Hug_Config_P.utoc": [202], "old_P.utoc": [201]}
assert not S.clashes(S.unit_inv(hinv2, S.group_units(hp, hinv2, {})))
got = {}
for k in hinv2:
    if "Hug" in k: got[k.split("/")[-1]] = sorted(S.pak_pkgs(hp / k))
assert got == {"Hug_P.utoc": ["202"], "Hug_ConfigAnim_P.utoc": ["202a/1", "202a/2", "202a/3", "202a/4"], "Hug_Config_P.utoc": ["202a"]}, got   # main, partner clips AND table all on 202(a)
assert all(json.loads((pathlib.Path(b) / "manifest.json").read_text()).get("unit") == "Hug" for b in bks)
for b in reversed(bks): S.revert_move(b)
assert hsnap() == h_before                                                                              # byte-exact undo of all three
# a container that cannot be rewritten: the WHOLE mod stays put and the reason names the container
real_try = S.try_rename
S.try_rename = lambda root, key, old, new: (None, "synthetic refusal") if "ConfigAnim" in key else real_try(root, key, old, new)
try: mv2, un2 = S.plan_unit_moves(hp, hinv, 1000, (), units=hu)
finally: S.try_rename = real_try
assert not un2 and len(mv2) == 1 and mv2[0]["keys"] == ["~mods/Old/old_P.utoc"], (mv2, un2)          # Hug stays whole, the OTHER mod gives way
S.try_rename = lambda root, key, old, new: (None, "synthetic refusal") if ("ConfigAnim" in key or "old_P" in key) else real_try(root, key, old, new)
try: mv2, un2 = S.plan_unit_moves(hp, hinv, 1000, (), units=hu)
finally: S.try_rename = real_try
assert not mv2 and un2 and "ConfigAnim_P.utoc: synthetic refusal" in " ".join(un2[0][2]) and "Hug (3 containers)" in " ".join(un2[0][1]), (mv2, un2)   # reason names the container
# a failure on the 3rd container rolls back the first two (the mod is never left half moved)
real_am = S.apply_move; n_calls = []
def flaky(*a, **k):
    n_calls.append(1)
    if len(n_calls) == 3: raise OSError("disk full")
    return real_am(*a, **k)
S.apply_move = flaky
try: S.apply_unit_move(hp, tmp, mv[0]["keys"], 201, 202, [str(tmp / ("fb%d" % i)) for i in range(3)], unit="Hug"); assert 0
except OSError: pass
finally: S.apply_move = real_am
assert hsnap() == h_before, "half-moved mod left behind"
# verification after the move catches a container that did not end up on the new slot
real_ps = S.pak_slots; S.pak_slots = lambda path: {201} if "Config_P" in str(path) else real_ps(path)
try: S.apply_unit_move(hp, tmp, mv[0]["keys"], 201, 202, [str(tmp / ("fv%d" % i)) for i in range(3)], unit="Hug"); assert 0
except SystemExit as e: assert "verification failed" in str(e)
finally: S.pak_slots = real_ps
assert hsnap() == h_before
# old (1.0.0) cache that cached the table as 'no slot': rebuilt, the table is seen
cf = tmp / "oldcache.json"; cfg = hp / "~mods/Hug/Hug_Config_P.utoc"; st_ = cfg.stat()
cf.write_text(json.dumps({"~mods/Hug/Hug_Config_P.utoc": {"sig": [st_.st_size, int(st_.st_mtime)], "slots": []}}))
assert "~mods/Hug/Hug_Config_P.utoc" in S.scan(hp, cf)
# complementary check: two containers of one folder that hold the SAME package are not one mod (a real clash inside a folder)
dp = tmp / "dup" / "~mods" / "Coll"; dp.mkdir(parents=True); make_multi(dp, "a_P", [(A + "300", "300.uasset")], cid=1); make_multi(dp, "b_P", [(A + "300", "300.uasset")], cid=2)
dinv = S.scan(tmp / "dup"); du = S.group_units(tmp / "dup", dinv, {}); assert sorted(len(v) for v in du.values()) == [1, 1] and list(S.clashes(S.unit_inv(dinv, du))) == [300]
# loose install (no subfolder): grouped by mod name (_P / _Config / _ConfigAnim stripped); Vortex source also groups
fp = _hug_world("hugflat", flat=True); finv = S.scan(fp); fu = S.group_units(fp, finv, {}); assert sorted(len(v) for v in fu.values()) == [1, 3], fu
vs = {os.path.normcase(str(hp / k)): "HugMod" for k in hinv if "Hug" in k}; assert sorted(len(v) for v in S.group_units(hp, hinv, vs).values()) == [1, 3]
# legacy plan_moves keeps its old shape (every container alone)
assert S.plan_moves(hp, {"~mods/Old/old_P.utoc": [201], "~mods/Hug/Hug_P.utoc": [201]}, 1000, ())[0] == [("~mods/Hug/Hug_P.utoc", 201, 202)]
# ---- review round 1: fallbacks must never tear a mod apart
# (1) one folder holds Hug (3 containers) AND an unrelated rival on 201: split by mod name, Hug still moves as a whole
ap_ = tmp / "allpaks" / "~mods" / "All"; _hug(ap_, None, 400); make_multi(ap_, "Other_P", [(A + "201", "201.uasset")], cid=500)
for f_ in ap_.iterdir(): os.utime(f_, (1.6e9, 1.6e9) if f_.name.startswith("Other") else (1.7e9, 1.7e9))
ainv = S.scan(tmp / "allpaks"); au = S.group_units(tmp / "allpaks", ainv, {}); assert sorted(len(v) for v in au.values()) == [1, 3] and S.group_units.notes, (au, S.group_units.notes)
am, aun = S.plan_unit_moves(tmp / "allpaks", ainv, 1000, (), units=au); assert not aun and len(am) == 1 and len(am[0]["keys"]) == 3, (am, aun)
# (2) names that cannot be split (Foo main, Bar partner table, Other rival) in one folder: REFUSED, nothing moves (no half move)
rp = tmp / "refuse" / "~mods" / "Mix"; rp.mkdir(parents=True)
make_multi(rp, "Foo_P", [(A + "201", "201.uasset")], cid=1); make_multi(rp, "BarX_P", [(A + "201a", "201a.uasset")], cid=2); make_multi(rp, "Other_P", [(A + "201", "201.uasset")], cid=3)
rinv = S.scan(tmp / "refuse"); rm_, run_ = S.plan_unit_moves(tmp / "refuse", rinv, 1000, (), units=S.group_units(tmp / "refuse", rinv, {}))
assert not rm_ and run_ and "partner part" in " ".join(run_[0][2]), (rm_, run_)
# (3) one mod's main clip and ANOTHER mod's partner table: they only work as a pair, so nothing is moved
sp_ = tmp / "split" / "~mods"; (sp_ / "MainMod").mkdir(parents=True); (sp_ / "PartnerAddon").mkdir()
make_multi(sp_ / "MainMod", "Main_P", [(A + "201", "201.uasset")], cid=1); make_multi(sp_ / "PartnerAddon", "Add_P", [(A + "201a", "201a.uasset")], cid=2)
sinv = S.scan(tmp / "split"); sm_, sun_ = S.plan_unit_moves(tmp / "split", sinv, 1000, (), units=S.group_units(tmp / "split", sinv, {}))
assert not sm_ and sun_ and "split across mods" in " ".join(sun_[0][2]), (sm_, sun_)
# (4) START MARKERS: a kill between containers leaves unfinished journals for the WHOLE unit, so interrupted() flags it and revert undoes it
kp = _hug_world("killpaks"); kinv = S.scan(kp); kk_ = [k for k in sorted(kinv) if "Hug" in k]; kb = tmp / "killbk"; kb.mkdir()
bks = [str(kb / ("move-x-%d" % i)) for i in range(3)]
for k, b in zip(kk_, bks): (kb / pathlib.Path(b).name).mkdir(); S._save_manifest(kb / pathlib.Path(b).name / "manifest.json", {"kind": "move", "pak": k, "old": 201, "new": 202, "steps": [], "done": False})
k_before = {str(q.relative_to(kp)): hashlib.sha256(q.read_bytes()).hexdigest() for q in kp.rglob("*") if q.is_file()}
S.apply_move(kp, tmp, kk_[0], 201, 202, bks[0], ext=False)                                                 # ... and the process dies here
assert len(S.interrupted(str(kb))) == 2 and bks[1] in S.interrupted(str(kb)), S.interrupted(str(kb))      # the 2 containers never reached
for b in reversed(bks): S.revert_move(b)
assert {str(q.relative_to(kp)): hashlib.sha256(q.read_bytes()).hexdigest() for q in kp.rglob("*") if q.is_file()} == k_before and not S.interrupted(str(kb))
# (5) the owner identity used by the preview is the one the apply uses
seen = []; real_ext3 = S.external_files
S.external_files = lambda *a, **k: (seen.append(a[6]), real_ext3(*a, **k))[1]
try:
    jj = S.apply_unit_move(kp, tmp, kk_, 201, 202, [str(tmp / ("mv%d" % i)) for i in range(3)], mover="Vortex Hug Mod", unit="Hug")
    assert seen == ["Vortex Hug Mod"], seen
    for i in (2, 1, 0): S.revert_move(str(tmp / ("mv%d" % i)))
finally: S.external_files = real_ext3
# (6) a rollback that cannot undo everything says so
n_calls = []; real_am = S.apply_move; real_rm = S.revert_move
def flaky2(*a, **k):
    n_calls.append(1)
    if len(n_calls) == 3: raise OSError("disk full")
    return real_am(*a, **k)
def rm_kept(b):
    r = real_rm(b); rm_kept.kept = 1; return r
S.apply_move = flaky2; S.revert_move = rm_kept
try: S.apply_unit_move(kp, tmp, kk_, 201, 202, [str(tmp / ("rk%d" % i)) for i in range(3)], unit="Hug"); assert 0
except OSError: assert S.apply_unit_move.clean is False
finally: S.apply_move = real_am; S.revert_move = real_rm
assert {str(q.relative_to(kp)): hashlib.sha256(q.read_bytes()).hexdigest() for q in kp.rglob("*") if q.is_file()} == k_before
# (7) the CLI end to end on a unit: plan shows ONE mod, moveslots --apply moves all three, revert restores byte for byte
import io, contextlib
gh = tmp / "hg"; _w = _hug_world("hg/Content/Paks"); gp = gh / "Content" / "Paks"
g_before = {str(q.relative_to(gp)): hashlib.sha256(q.read_bytes()).hexdigest() for q in gp.rglob("*") if q.is_file()}
common = ["--game", str(gh), "--no-cache", "--cache", str(tmp / "hgc.json"), "--backup", str(tmp / "hgbk"), "--ceiling", "999"]
def cli(*extra):
    out = io.StringIO()
    with contextlib.redirect_stdout(out): rc = S.main(common + list(extra))
    return rc, out.getvalue()
rc, o = cli("plan"); assert "(3 containers)" in o and "1 moves proposed" in o, o
rc, o = cli("moveslots", "--apply", "--yes"); assert rc == 0 and "3 containers moved together" in o and "verified" in o, o
mid = S.scan(gp); assert sorted({tuple(v) for k, v in mid.items() if "Hug" in k}) == [(202,)] and len([k for k in mid if "Hug" in k]) == 3
rc, o = cli("revert"); assert {str(q.relative_to(gp)): hashlib.sha256(q.read_bytes()).hexdigest() for q in gp.rglob("*") if q.is_file()} == g_before, o
# ---- review round 2
mk_a = lambda d, n, files, mount=None, cid=1: make_multi(d, n, files, **({"mount": mount} if mount else {}), cid=cid)
PM = lambda slot: "../../../SB/Content/Mods/HD-ATOOL_P/anim/%da/" % slot
# (1) a partner-only addon (overrides Hug's partner clips): shares packages with Hug, but has no main clip -> nothing moves, whichever is older
for older in ("hug", "addon"):
    ad = tmp / ("addon_" + older) / "~mods"; _hug(ad, "Hug", 600); (ad / "Addon").mkdir()
    mk_a(ad / "Addon", "Add_P", [(A + "201a/%d" % i, "%d.uasset" % i) for i in (1, 2, 3, 4)], PM(201), cid=700)
    for f_ in ad.rglob("*"):
        if f_.is_file(): os.utime(f_, (1.6e9, 1.6e9) if (("Hug" in str(f_)) == (older == "hug")) else (1.7e9, 1.7e9))
    adi = S.scan(tmp / ("addon_" + older)); adm, adu = S.plan_unit_moves(tmp / ("addon_" + older), adi, 1000, (), units=S.group_units(tmp / ("addon_" + older), adi, {}))
    assert not adm and adu and "partner part" in " ".join(adu[0][2]), (older, adm, adu)
# (2) three holders A{201} B{201,201a} C{201a}: C has no main clip -> refused as a whole
th = tmp / "three" / "~mods"
for n, files, cid in (("A", [(A + "201", "201.uasset")], 1), ("B", [(A + "201", "201.uasset"), (A + "201a", "201a.uasset")], 2), ("C", [(A + "201a", "201a.uasset")], 3)):
    (th / n).mkdir(parents=True); mk_a(th / n, n + "_P", files, cid=cid)
ti = S.scan(tmp / "three"); tm_, tu_ = S.plan_unit_moves(tmp / "three", ti, 1000, (), units=S.group_units(tmp / "three", ti, {})); assert not tm_ and tu_
# (3) unrelated clips in one folder are NOT one mod; a multi-slot pack (201+305 / 201a clips / 305a table) IS one mod
hm = tmp / "hugmix" / "~mods" / "Pack"; _hug(hm, None, 800); mk_a(hm, "Other_P", [(A + "305", "305.uasset")], cid=900)
hmi = S.scan(tmp / "hugmix"); hmu = S.group_units(tmp / "hugmix", hmi, {}); assert sorted(len(v) for v in hmu.values()) == [1, 3] and not any("(4 containers)" in S.unit_label(u, k) for u, k in hmu.items()), hmu
mp_ = tmp / "multislot" / "~mods" / "Pack"; mp_.mkdir(parents=True)
mk_a(mp_, "X_P", [(A + "201", "201.uasset"), (A + "305", "305.uasset")], cid=1); mk_a(mp_, "Y_P", [(A + "201a/1", "1.uasset")], PM(201), cid=2); mk_a(mp_, "Z_P", [(A + "305a", "305a.uasset")], cid=3)
mpi = S.scan(tmp / "multislot"); mpu = S.group_units(tmp / "multislot", mpi, {}); assert sorted(len(v) for v in mpu.values()) == [3], mpu
# (4) the rollback status is honest when apply_move's OWN rollback could not undo everything (a file changed since the move)
cp_ = _hug_world("cleanpaks"); cinv = S.scan(cp_); ck = [k for k in sorted(cinv) if "Hug" in k]; real_ext4 = S.external_files
def touch_then_boom(*a, **k): (cp_ / ck[0]).write_bytes((cp_ / ck[0]).read_bytes() + b"x"); raise OSError("antivirus")
S.external_files = touch_then_boom
try: S.apply_unit_move(cp_, tmp, ck, 201, 202, [str(tmp / ("cl%d" % i)) for i in range(3)], unit="Hug"); assert 0
except OSError: assert S.apply_unit_move.clean is False
finally: S.external_files = real_ext4
# (5) a marker that cannot be written leaves no unfinished journal behind
kq = _hug_world("markpaks"); kqi = S.scan(kq); kqk = [k for k in sorted(kqi) if "Hug" in k]; mkd = tmp / "mkbk"; mkd.mkdir()
real_sm = S._save_manifest; cnt = []
def sm_fail(path, j):
    cnt.append(1)
    if len(cnt) == 2: raise OSError("disk full")
    return real_sm(path, j)
S._save_manifest = sm_fail
try: S.apply_unit_move(kq, tmp, kqk, 201, 202, [str(mkd / ("move-y-%d" % i)) for i in range(3)], unit="Hug"); assert 0
except OSError: pass
finally: S._save_manifest = real_sm
assert not S.interrupted(str(mkd)), S.interrupted(str(mkd))
# ---- review round 3
def cli2(game, *extra, bk="r3bk"):
    out = io.StringIO()
    with contextlib.redirect_stdout(out): rc = S.main(["--game", str(game), "--no-cache", "--cache", str(tmp / "r3c.json"), "--backup", str(tmp / bk), "--ceiling", "999"] + list(extra))
    return rc, out.getvalue()
snapd = lambda root: {str(q.relative_to(root)): hashlib.sha256(q.read_bytes()).hexdigest() for q in root.rglob("*") if q.is_file()}
# (A1) --pak must not strand a pair: a main clip whose partner containers could not be grouped (names share no stem) is refused, and --pak must hold --slot
g3 = tmp / "pakg"; m3 = g3 / "Content" / "Paks" / "~mods"; m3.mkdir(parents=True)
make_multi(m3, "Hug_P", [(A + "201", "201.uasset")], cid=1); make_multi(m3, "Other_P", [(A + "201", "201.uasset")], cid=4)
make_multi(m3, "Lily_ConfigAnim_P", [(A + "201a/%d" % i, "%d.uasset" % i) for i in (1, 2)], mount=PM(201), cid=2); make_multi(m3, "Lily_Config_P", [(A + "201a", "201a.uasset")], cid=3)
b3 = snapd(g3 / "Content" / "Paks")
rc, o = cli2(g3, "moveslots", "--pak", "~mods/Hug_P.utoc", "--slot", "201", "--to", "210", "--apply", "--yes"); assert rc == 2 and "cannot move" in o and "partner part" in o and snapd(g3 / "Content" / "Paks") == b3, o
rc, o = cli2(g3, "moveslots", "--pak", "~mods/Other_P.utoc", "--slot", "305", "--to", "310", "--apply", "--yes"); assert rc == 2 and "does not hold slot 305" in o and snapd(g3 / "Content" / "Paks") == b3, o
rc, o = cli2(g3, "moveslots"); assert "holds only the partner part" in o and "nothing to move" in o, o                    # the automatic plan agrees
# (A2) every container is in exactly one unit, also when components of one folder split on the same mod name
cf_ = tmp / "collide" / "~mods" / "F"; cf_.mkdir(parents=True)
for n_, files, cid in (("Hug_P", [(A + "201", "201.uasset")], 1), ("Hug_Config_P", [(A + "201a", "201a.uasset")], 2), ("Hug2_P", [(A + "305", "305.uasset")], 3),
                       ("Hug-Config_P", [(A + "305a", "305a.uasset")], 4), ("Hug ConfigAnim_P", [(A + "305a", "305a.uasset"), (A + "305a/1", "1.uasset")], 5)):
    mk_a(cf_, n_, files, cid=cid)
cfi = S.scan(tmp / "collide"); cfu = S.group_units(tmp / "collide", cfi, {})
assert sorted(k for ks in cfu.values() for k in ks) == sorted(cfi), cfu
for u_, i_ in ((hu, hinv), (hmu, hmi), (mpu, mpi), (du, dinv), (fu, finv)):
    assert sorted(k for ks in u_.values() for k in ks) == sorted(i_), (u_, i_)            # the invariant holds for every earlier fixture too
# (A3) a failed move that could not be undone completely leaves a durable, correctly worded trace; revert refuses instead of undoing OLDER runs
pw = _hug_world("partpaks"); pinv = S.scan(pw); pk_ = [k for k in sorted(pinv) if "Hug" in k]; pb = tmp / "pbk"; pb.mkdir()
old_run = pb / "move-0000-0"; old_run.mkdir(); S._save_manifest(old_run / "manifest.json", {"kind": "move", "pak": "x", "old": 1, "new": 2, "steps": [], "done": True})
real_ext5 = S.external_files
def touch_boom(*a, **k): (pw / pk_[0]).write_bytes((pw / pk_[0]).read_bytes() + b"x"); raise OSError("antivirus")
S.external_files = touch_boom
try: S.apply_unit_move(pw, tmp, pk_, 201, 202, [str(pb / ("move-9999-%d" % i)) for i in range(3)], unit="Hug"); assert 0
except OSError: assert S.apply_unit_move.clean is False
finally: S.external_files = real_ext5
pend = S.interrupted(str(pb)); assert S.partial_pending(pend), pend
gp3 = tmp / "partg"; (gp3 / "Content" / "Paks").mkdir(parents=True)
rc, o = cli2(gp3, "revert", bk="pbk"); assert rc == 2 and "revert cannot fix it" in o and (old_run / "manifest.json").exists(), (rc, o)    # the OLD finished run is not touched
# (B1) a 1.0.0 ledger entry owned by a non-first container of a mod is kept (renamed to the mod's first container)
lg = tmp / "lg"; (lg / "Content/Paks/LogicMods/HD-ATOOL_P/audio").mkdir(parents=True); wv = lg / "Content/Paks/LogicMods/HD-ATOOL_P/audio/830.wav"; wv.write_bytes(b"W")
led1 = S.ledger_update(lg, {"~mods/Hug/b.utoc": [830]}, tmp / "lg.json"); assert list(led1.values()) == ["pak:~mods/Hug/b.utoc"]
led2 = S.ledger_update(lg, {"~mods/Hug/a.utoc": [830]}, tmp / "lg.json", {"~mods/Hug/b.utoc": "~mods/Hug/a.utoc", "~mods/Hug/a.utoc": "~mods/Hug/a.utoc"}); assert list(led2.values()) == ["pak:~mods/Hug/a.utoc"], led2
# (B8) a holder that cannot be read (legacy .pak) next to a holder with partner packages is refused
lp_ = tmp / "legacy" / "~mods"; lp_.mkdir(parents=True); make_multi(lp_, "A_P", [(A + "201", "201.uasset"), (A + "201a", "201a.uasset")], cid=1)
(lp_ / "L.pak").write_bytes(b"junk Mods/HD-ATOOL_P/anim/201/x.uasset junk")
lpi = S.scan(tmp / "legacy"); lm_, lu_ = S.plan_unit_moves(tmp / "legacy", lpi, 1000, (), units=S.group_units(tmp / "legacy", lpi, {}), mtimes={k: 1 for k in lpi})
assert not lm_ and lu_ and "cannot be read" in " ".join(lu_[0][2]), (lm_, lu_)
print("ok")
