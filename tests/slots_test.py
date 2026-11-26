import sys, pathlib, tempfile, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)); import slots as S

assert S.plan({"a": [1, 2], "b": [3]}) == []                                   # no clash, no moves
m = S.plan({"a": [5, 6], "b": [6, 7]})                                          # clash: b (later name) moves to a free slot
assert m == [("b", 6, 1)], m
assert S.plan({"~mods/x": [5], "LogicMods/y": [5]}) == [("~mods/x", 5, 1)]       # pinned LogicMods keeps its slot
assert S.plan({"a": [1001]}, 1000) == [("a", 1001, 1)]                           # out of range moves
assert S.plan({"a": [5], "b": [5]}, reserved=[1, 2]) == [("b", 5, 3)]            # reserved slots skipped
assert S.plan({"a": [2], "b": [2]}) == S.plan({"b": [2], "a": [2]})              # deterministic
try: S.plan({"a": [1, 2], "b": [1, 2]}, ceiling=2); assert 0
except SystemExit: pass                                                          # no free slot: clear failure
assert S.clashes({"a": [1], "b": [1, 2]}) == {1: ["a", "b"]}
d = pathlib.Path(tempfile.mkdtemp()); (d / "x.pak").write_bytes(b"junk"); c = d / "c.json"; c.write_text("{not json")
assert S.scan(d, c) == {} and S.scan.hits == 0                                   # corrupt cache rebuilt
S.scan(d, c); assert S.scan.hits == 1                                            # unchanged pak: cache hit
import struct
d2 = pathlib.Path(tempfile.mkdtemp())
for n, cid in (("a.utoc", 7), ("b.utoc", 7), ("c.utoc", 9)): (d2 / n).write_bytes(b"-==--==--==--==-" + bytes(40) + struct.pack("<Q", cid))
assert S.id_clashes(d2) == {7: ["a.utoc", "b.utoc"]}                              # same container id -> clash
# fix container-id clashes on synthetic containers (utoc header + chunk id + ucas head all carry the id)
def mk(d, name, cid):
    h = bytearray(144); h[:16] = b"-==--==--==--==-"; h[16] = 2
    struct.pack_into("<IIIIIII", h, 20, 144, 1, 1, 12, 0, 32, 65536); struct.pack_into("<Q", h, 56, cid)
    body = struct.pack("<QHBB", cid, 0, 0, 10) + (0).to_bytes(5, "big") + (16).to_bytes(5, "big") + (0).to_bytes(5, "little") + (16).to_bytes(3, "little") * 2 + bytes([0])
    (d / (name + ".utoc")).write_bytes(bytes(h) + body); (d / (name + ".ucas")).write_bytes(struct.pack("<Q", cid) + bytes(8))
d3 = pathlib.Path(tempfile.mkdtemp()); mk(d3, "a", 5); mk(d3, "b", 5); mk(d3, "other", 5)
inv = {"a.utoc": [10], "b.utoc": [11]}                        # a, b ship anim slots; "other" does not
fx = S.plan_fix(d3, inv); assert sorted(k for k, _, _ in fx) == ["a.utoc", "b.utoc"], fx   # other (non-anim) is never touched
assert len({n for _, _, n in fx}) == 2 and 5 not in {n for _, _, n in fx}
done, skipped = S.apply_fix(d3, fx, d3 / "bk"); assert len(done) == 2 and not skipped
ids = S.container_ids(d3); assert ids["other.utoc"] == 5 and len({ids["a.utoc"], ids["b.utoc"], 5}) == 3 and not S.id_clashes(d3)
assert S.revert_fix(d3 / "bk") == 2 and S.container_ids(d3) == {"a.utoc": 5, "b.utoc": 5, "other.utoc": 5}   # byte-exact round trip
assert S.revert_fix(d3 / "bk") == 0                                                  # reverting twice changes nothing
import hashlib
KN = {hashlib.sha256(b"fake ue4ss").hexdigest().upper(): "test build"}
g = pathlib.Path(tempfile.mkdtemp()); assert S.detect_ceiling(g, KN) == 1000                    # mod not installed
m = g / "Binaries" / "Win64" / "ue4ss" / "Mods" / "AToolSlotLimit"; (m / "dlls").mkdir(parents=True); (m / "dlls" / "main.dll").write_bytes(b"x")
U = g / "Binaries" / "Win64" / "ue4ss" / "UE4SS.dll"; U.write_bytes(b"fake ue4ss")
assert S.detect_ceiling(g, KN) == 9999                                                   # installed, no config -> default
NL = chr(10)
(m / "config.txt").write_text("limit=5000" + NL); assert S.detect_ceiling(g, KN) == 5000
(m / "config.txt").write_text("limit=1000" + NL); assert S.detect_ceiling(g, KN) == 1000
(m / "enabled.txt").write_text("0"); (m / "config.txt").write_text("limit=5000" + NL); assert S.detect_ceiling(g, KN) == 1000   # disabled
(m / "enabled.txt").write_text("1"); (m / "config.txt").write_text("limit=5000" + NL)
U.unlink(); assert S.detect_ceiling(g, KN) == 1000                                    # mod installed, UE4SS missing -> not trusted
U.write_bytes(b"other ue4ss"); assert S.detect_ceiling(g, KN) == 1000 and S.ue4ss_build(g, KN) is None     # unknown UE4SS build -> 1000
U.write_bytes(b"fake ue4ss"); assert S.detect_ceiling(g, KN) == 5000 and S.ue4ss_build(g, KN) == "test build"

rf = g / "r.txt"; rf.write_text(NL.join(["# c", "5", "10-12 # x", "bad"]) + NL); assert S.load_reserved(rf) == {5, 10, 11, 12}
assert S.load_reserved(g / "none.txt") == set(range(901, 908))
print("ok")
