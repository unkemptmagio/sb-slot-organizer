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
print("ok")
