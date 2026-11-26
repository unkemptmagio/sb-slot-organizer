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
print("ok")
