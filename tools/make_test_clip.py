"""Make a test copy of an anim pak at another slot (a different digit count is fine) with a fresh container id, for in-game tests (a 982 -> 1001 copy of a clip with partner tables played with both partners in game, 2026-11-25).
The source is only read. Usage:
  python tools/make_test_clip.py <src.utoc> <from-slot> <to-slot> <out-dir> [--name NAME]
Writes <out-dir>/<NAME>.utoc/.ucas/.pak (NAME default <src stem>_S<to-slot>). Install it in ~mods; the original keeps working unless it holds the same slot."""
import argparse, pathlib, shutil, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import iostore as I, slots as S

def make(src, old, new, out_dir, name=None):
    src = pathlib.Path(src); out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    name = name or "%s_S%d" % (src.stem, new)
    c = I.read_container(src)
    I.rename_slot(c, old, new)
    nid = S.new_id(name, {c.container_id})                     # a copy must not share the container id: only one pak per id mounts
    c.container_id = nid
    for ch in c.chunks:
        if ch["type"] == 10: ch["id"] = nid; ch["data"] = struct.pack("<Q", nid) + bytes(ch["data"][8:]); ch["dirty"] = True
    bad = I.check_container(c)
    if bad: raise SystemExit("consistency check failed: %s" % bad[0])
    t, u = I.container_bytes(c)
    (out / (name + ".utoc")).write_bytes(t); (out / (name + ".ucas")).write_bytes(u)
    pak = src.with_suffix(".pak")
    if pak.is_file(): shutil.copy2(pak, out / (name + ".pak"))
    chk = I.read_container(out / (name + ".utoc"))             # verify what was written
    if I.check_container(chk) or new not in I.slots_in(chk) or old in I.slots_in(chk) or chk.container_id != nid: raise SystemExit("verification of the written copy failed")
    return out / (name + ".utoc"), nid

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("old", type=int); ap.add_argument("new", type=int); ap.add_argument("out"); ap.add_argument("--name")
    a = ap.parse_args(); p, nid = make(a.src, a.old, a.new, a.out, a.name)
    print("wrote %s (container id %#x), slot %d -> %d" % (p, nid, a.old, a.new))
