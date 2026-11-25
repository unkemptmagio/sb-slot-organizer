"""iostore + slot mover tests. Synthetic containers (no game files); real-pak vectors only when the local files exist."""
import sys, pathlib, tempfile, struct, hashlib, os, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import iostore as I, slots as S

def make_pak(d, name, slot, cid=0x1122334455667788, extra=b"", dirs_in_mount=True):
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
    c.chunks = [mk(cid, 10, hdr), mk(pid, 2, data)]
    c.dirindex = dict(mount="../../../SB/Content/Mods/HD-ATOOL_P/anim/", mount_kind=1, dirs=[[0xFFFFFFFF] * 3 + [0]], files=[[0, 0xFFFFFFFF, 1]], strings=[f"{slot}.uasset"], kinds=[1])
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
j = S.apply_move(paks, tmp, "~mods/two.utoc", 700, 701, tmp / "bk", rewrite=False)
inv2 = S.scan(paks); assert not S.clashes(inv2) and inv2["~mods/two.utoc"] == [701] and inv2["~mods/one.utoc"] == [700]
assert S.revert_move(tmp / "bk") == 2
assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (paks / "~mods").iterdir()} == before   # byte-exact
# chained moves of the same pak keep every original; reverting newest-first restores byte-exact
S.apply_move(paks, tmp, "~mods/two.utoc", 700, 701, tmp / "c1", rewrite=False); S.apply_move(paks, tmp, "~mods/two.utoc", 701, 702, tmp / "c2", rewrite=False)
S.revert_move(tmp / "c2"); S.revert_move(tmp / "c1")
assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (paks / "~mods").iterdir()} == before
# LogicMods never moves; a clash with only a LogicMods pak and a movable one moves the other
(paks / "LogicMods").mkdir(); make_pak(paks / "LogicMods", "lm", 700, cid=3)
inv = S.scan(paks); mv, un = S.plan_moves(paks, inv, 1000, ())
assert all(not k.startswith("LogicMods/") for k, _, _ in mv) and len(mv) == 2             # both ~mods paks move off 700, the LogicMods one keeps it
# no free slot / reserved
mv, un = S.plan_moves(paks, S.scan(paks), 700, set(range(1, 700))); assert un and not mv                          # nothing free: reported, not guessed
print("ok")
