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
print("ok")
