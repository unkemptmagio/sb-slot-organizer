"""IoStore (UE 4.26) helpers: CityHash64 and the ids/hashes derived from it. Stdlib only.
Everything here is proven against real paks in tests/iostore_test.py before any container is rewritten."""
import struct

M = 0xFFFFFFFFFFFFFFFF
K0, K1, K2 = 0xc3a5c85c97cb3127, 0xb492b66fbe98f273, 0x9ae16a3b2f90404f

def _f64(s, i): return struct.unpack_from("<Q", s, i)[0]
def _f32(s, i): return struct.unpack_from("<I", s, i)[0]
def _rot(v, n): return v if n == 0 else ((v >> n) | (v << (64 - n))) & M
def _smix(v): return v ^ (v >> 47)
def _bswap(v): return int.from_bytes(v.to_bytes(8, "little"), "big")

def _h16(u, v, mul=0x9ddfea08eb382d69):
    a = ((u ^ v) * mul) & M; a ^= a >> 47
    b = ((v ^ a) * mul) & M; b ^= b >> 47
    return (b * mul) & M

def _weak(s, i, a, b):
    w, x, y, z = _f64(s, i), _f64(s, i + 8), _f64(s, i + 16), _f64(s, i + 24)
    a = (a + w) & M; b = _rot((b + a + z) & M, 21); c = a
    a = (a + x) & M; a = (a + y) & M; b = (b + _rot(a, 44)) & M
    return (a + z) & M, (b + c) & M

def _h0_16(s):
    n = len(s)
    if n >= 8:
        mul = (K2 + n * 2) & M; a = (_f64(s, 0) + K2) & M; b = _f64(s, n - 8)
        c = (_rot(b, 37) * mul + a) & M; d = ((_rot(a, 25) + b) * mul) & M
        return _h16(c, d, mul)
    if n >= 4:
        mul = (K2 + n * 2) & M; a = _f32(s, 0)
        return _h16((n + (a << 3)) & M, _f32(s, n - 4), mul)
    if n > 0:
        y = (s[0] + (s[n >> 1] << 8)) & 0xFFFFFFFF; z = (n + (s[n - 1] << 2)) & 0xFFFFFFFF
        return (_smix((y * K2 ^ z * K0) & M) * K2) & M
    return K2

def _h17_32(s):
    n = len(s); mul = (K2 + n * 2) & M
    a = (_f64(s, 0) * K1) & M; b = _f64(s, 8); c = (_f64(s, n - 8) * mul) & M; d = (_f64(s, n - 16) * K2) & M
    return _h16((_rot((a + b) & M, 43) + _rot(c, 30) + d) & M, (a + _rot((b + K2) & M, 18) + c) & M, mul)

def _h33_64(s):
    n = len(s); mul = (K2 + n * 2) & M
    a = (_f64(s, 0) * K2) & M; b = _f64(s, 8); c = _f64(s, n - 24); d = _f64(s, n - 32)
    e = (_f64(s, 16) * K2) & M; f = (_f64(s, 24) * 9) & M; g = _f64(s, n - 8); h = (_f64(s, n - 16) * mul) & M
    u = (_rot((a + g) & M, 43) + (_rot(b, 30) + c) * 9) & M
    v = (((a + g) ^ d) + f + 1) & M
    w = (_bswap(((u + v) * mul) & M) + h) & M
    x = (_rot((e + f) & M, 42) + c) & M
    y = ((_bswap(((v + w) * mul) & M) + g) * mul) & M
    z = (e + f + c) & M
    a = (_bswap((((x + z) * mul) + y) & M) + b) & M
    b = (_smix((((z + a) * mul) + d + h) & M) * mul) & M
    return (b + x) & M

ALLOW_LONG = True        # long branch verified 2026-11-25: 3793/3793 stored hashes (65..232 B) from 205 installed containers

class Unsupported(Exception):
    pass

def cityhash64(s):
    """CityHash64 (v1.1) of bytes; verified against real paks, short and long inputs"""
    n = len(s)
    if n <= 32: return _h0_16(s) if n <= 16 else _h17_32(s)
    if n <= 64: return _h33_64(s)
    if not ALLOW_LONG: raise Unsupported("hash input of %d bytes (> 64) is not verified" % n)
    x = _f64(s, n - 40); y = (_f64(s, n - 16) + _f64(s, n - 56)) & M
    z = _h16((_f64(s, n - 48) + n) & M, _f64(s, n - 24))
    v = _weak(s, n - 64, n, z); w = _weak(s, n - 32, (y + K1) & M, x)
    x = (x * K1 + _f64(s, 0)) & M
    n = (n - 1) & ~63; i = 0
    while True:
        x = (_rot((x + y + v[0] + _f64(s, i + 8)) & M, 37) * K1) & M
        y = (_rot((y + v[1] + _f64(s, i + 48)) & M, 42) * K1) & M
        x ^= w[1]; y = (y + v[0] + _f64(s, i + 40)) & M
        z = (_rot((z + w[0]) & M, 33) * K1) & M
        v = _weak(s, i, (v[1] * K1) & M, (x + w[0]) & M)
        w = _weak(s, i + 32, (z + w[1]) & M, (y + _f64(s, i + 16)) & M)
        z, x = x, z; i += 64; n -= 64
        if n == 0: break
    return _h16((_h16(v[0], w[0]) + _smix(y) * K1 + z) & M, (_h16(v[1], w[1]) + x) & M)

def package_id(name):
    """FPackageId: CityHash64 over the lowercased UTF-16LE package name"""
    return cityhash64(name.lower().encode("utf-16-le"))


# ------------------------------------------------------------------ container (.utoc + .ucas), uncompressed TOC v2 only
import hashlib, pathlib

MAGIC = b"-==--==--==--==-"

def _fstr(b, o):
    n = struct.unpack_from("<i", b, o)[0]; o += 4
    if n == 0: return "", o, 0
    if n < 0:
        n = -n; return b[o:o + 2 * n].decode("utf-16-le").rstrip("\0"), o + 2 * n, 2
    return b[o:o + n].decode("latin-1").rstrip("\0"), o + n, 1

def _wfstr(s, kind):
    if not s and kind == 0: return struct.pack("<i", 0)
    if kind == 2: return struct.pack("<i", -(len(s) + 1)) + s.encode("utf-16-le") + b"\0\0"
    return struct.pack("<i", len(s) + 1) + s.encode("latin-1") + b"\0"

class Container:
    """header: the 144 TOC header bytes; chunks: [dict(id, index, pad, type, data, meta_flags)]; dirindex: dict(mount, mount_kind, dirs, files, strings, kinds)"""

def read_container(utoc, ucas=None):
    utoc = pathlib.Path(utoc); b = utoc.read_bytes(); u = pathlib.Path(ucas or str(utoc)[:-5] + ".ucas").read_bytes()
    if b[:16] != MAGIC: raise Unsupported("not an IoStore TOC")
    if b[16] != 2: raise Unsupported("TOC version %d (only 2)" % b[16])
    hs, ec, cbc, cbes, mnc, mnl, bs, dis, pc = struct.unpack_from("<9I", b, 20)
    if mnc: raise Unsupported("compressed container")
    if hs != 144 or cbes != 12 or pc > 1: raise Unsupported("unexpected TOC header (size %d, partitions %d)" % (hs, pc))
    flags = b[80]
    if flags & ~0x8: raise Unsupported("container flags %#x (compressed/encrypted/signed)" % flags)
    c = Container(); c.header = bytearray(b[:144]); c.block_size = bs; c.container_id = struct.unpack_from("<Q", b, 56)[0]
    o_ids = 144; o_off = o_ids + ec * 12; o_blk = o_off + ec * 10; o_dir = o_blk + cbc * 12; o_meta = o_dir + dis
    if len(b) != o_meta + ec * 33: raise Unsupported("unexpected TOC tail length")
    blocks = []
    for i in range(cbc):
        po = int.from_bytes(b[o_blk + 12 * i:o_blk + 12 * i + 5], "little"); cs = int.from_bytes(b[o_blk + 12 * i + 5:o_blk + 12 * i + 8], "little")
        us = int.from_bytes(b[o_blk + 12 * i + 8:o_blk + 12 * i + 11], "little"); m = b[o_blk + 12 * i + 11]
        if m or cs != us: raise Unsupported("compressed block")
        blocks.append((po, us))
    end = 0; gaps = False                                       # packers differ: some align blocks to 16 bytes, some pack them back to back
    for po, us in blocks:
        gaps = gaps or po != end; end = po + us
    c.block_align = 16 if (gaps or len(u) > end) else 1
    c.chunks = []; bi = 0
    for i in range(ec):
        cid, idx, pad, typ = struct.unpack_from("<QHBB", b, o_ids + 12 * i)
        off = int.from_bytes(b[o_off + 10 * i:o_off + 10 * i + 5], "big"); ln = int.from_bytes(b[o_off + 10 * i + 5:o_off + 10 * i + 10], "big")
        if off % bs: raise Unsupported("unaligned chunk offset")
        first = off // bs; n = -(-ln // bs)
        data = b"".join(u[blocks[first + k][0]:blocks[first + k][0] + blocks[first + k][1]] for k in range(n))
        if len(data) != ln: raise Unsupported("chunk length mismatch")
        meta = b[o_meta + 33 * i:o_meta + 33 * i + 33]
        c.chunks.append(dict(id=cid, index=idx, pad=pad, type=typ, data=data, meta_flags=meta[32], meta_pad=meta[20:32], meta_hash=meta[:20],
                             sha_ok=hashlib.sha1(data).digest() == meta[:20], dirty=False))
    # directory index
    d = b[o_dir:o_dir + dis]; o = 0
    mount, o, mk = _fstr(d, o)
    nd = struct.unpack_from("<I", d, o)[0]; o += 4
    dirs = [struct.unpack_from("<IIII", d, o + 16 * i) for i in range(nd)]; o += 16 * nd
    nf = struct.unpack_from("<I", d, o)[0]; o += 4
    files = [struct.unpack_from("<III", d, o + 12 * i) for i in range(nf)]; o += 12 * nf
    ns = struct.unpack_from("<I", d, o)[0]; o += 4
    strs, kinds = [], []
    for _ in range(ns):
        s, o, k = _fstr(d, o); strs.append(s); kinds.append(k)
    if o != len(d): raise Unsupported("directory index tail")
    c.dirindex = dict(mount=mount, mount_kind=mk, dirs=[list(x) for x in dirs], files=[list(x) for x in files], strings=strs, kinds=kinds)
    return c

def _dirindex_bytes(di):
    o = _wfstr(di["mount"], di["mount_kind"]) + struct.pack("<I", len(di["dirs"]))
    for e in di["dirs"]: o += struct.pack("<IIII", *e)
    o += struct.pack("<I", len(di["files"]))
    for e in di["files"]: o += struct.pack("<III", *e)
    o += struct.pack("<I", len(di["strings"]))
    for s, k in zip(di["strings"], di["kinds"]): o += _wfstr(s, k)
    return o

def container_bytes(c):
    """-> (utoc bytes, ucas bytes); a container read and written unchanged is byte-identical to the originals.
    Virtual chunk offsets start on block boundaries; the blocks themselves are packed in the .ucas on 16-byte boundaries."""
    bs = c.block_size; ec = len(c.chunks); ids = off_tab = blk = meta = b""; ucas = bytearray(); nblocks = 0; virt = 0
    for ch in c.chunks:
        data = ch["data"]; ln = len(data)
        if virt % bs: virt += bs - virt % bs
        ids += struct.pack("<QHBB", ch["id"], ch["index"], ch["pad"], ch["type"])
        off_tab += virt.to_bytes(5, "big") + ln.to_bytes(5, "big")
        for k in range(-(-ln // bs)):
            if len(ucas) % c.block_align: ucas += bytes(c.block_align - len(ucas) % c.block_align)
            n = min(bs, ln - k * bs)
            blk += len(ucas).to_bytes(5, "little") + n.to_bytes(3, "little") + n.to_bytes(3, "little") + b"\0"; nblocks += 1
            ucas += data[k * bs:k * bs + n]
        virt += ln
        meta += (hashlib.sha1(data).digest() if ch["dirty"] or ch["sha_ok"] else ch["meta_hash"]) + ch["meta_pad"] + bytes([ch["meta_flags"]])   # untouched chunks keep their stored hash (some packers do not use sha1)
    if len(ucas) % c.block_align: ucas += bytes(c.block_align - len(ucas) % c.block_align)
    di = _dirindex_bytes(c.dirindex)
    h = bytearray(c.header); struct.pack_into("<III", h, 24, ec, nblocks, 12); struct.pack_into("<I", h, 48, len(di)); struct.pack_into("<Q", h, 56, c.container_id)
    return bytes(h) + ids + off_tab + blk + di + meta, bytes(ucas)


# ------------------------------------------------------------------ zen package (the payload of a type 2 chunk)
import re

class Package:
    """summary(64 B) | names | pad8 | hashes | imports | exports(72 B each) | bundles | graph | export data. Parsed so it can be rebuilt byte-identical."""
    pass

def read_package(d):
    p = Package()
    (p.name_idx, p.name_no, p.src_idx, p.src_no, p.flags, p.cooked_hdr, nno, nns, nho, nhs, imo, emo, ebo, gdo, gds, p.pad) = struct.unpack_from("<IIIIIIIIIIIIIIII", d, 0)
    if nno != 64 or nho != (nno + nns + 7) & ~7 or imo != nho + nhs or emo < imo or ebo < emo or gdo < ebo: raise Unsupported("package layout")
    if (ebo - emo) % 72: raise Unsupported("export map size")
    p.names = []; o = nno
    while o < nno + nns:
        h = struct.unpack_from(">H", d, o)[0]; o += 2; n = h & 0x7fff
        if h & 0x8000: p.names.append((d[o:o + 2 * n].decode("utf-16-le"), True)); o += 2 * n
        else: p.names.append((d[o:o + n].decode("latin-1"), False)); o += n
    if o != nno + nns: raise Unsupported("name map size")
    if nhs != 8 + 8 * len(p.names): raise Unsupported("name hash block")
    p.algo = struct.unpack_from("<Q", d, nho)[0]
    p.hashes = [struct.unpack_from("<Q", d, nho + 8 + 8 * i)[0] for i in range(len(p.names))]
    p.imports = d[imo:emo]
    p.exports = [list(struct.unpack_from("<QQIIQQQQQIBBBB", d, emo + 72 * i)) for i in range((ebo - emo) // 72)]
    p.bundles = d[ebo:gdo]; p.graph = d[gdo:gdo + gds]; hdr_end = gdo + gds
    p.blobs = []; pos = hdr_end; expect = p.cooked_hdr
    for e in p.exports:
        if e[0] != expect: raise Unsupported("exports are not contiguous")
        p.blobs.append(d[pos:pos + e[1]]); pos += e[1]; expect += e[1]
    if pos != len(d): raise Unsupported("export data length")
    return p

def _name_bytes(names):
    o = b""
    for s, wide in names:
        raw = s.encode("utf-16-le") if wide else s.encode("latin-1")
        assert len(s) < 0x8000
        o += struct.pack(">H", len(s) | (0x8000 if wide else 0)) + raw
    return o

def name_hash(s, wide=False):
    return cityhash64(s.lower().encode("utf-16-le" if wide else "latin-1"))

def package_bytes(p):
    nb = _name_bytes(p.names); nho = (64 + len(nb) + 7) & ~7
    hb = struct.pack("<Q", p.algo) + b"".join(struct.pack("<Q", h) for h in p.hashes)
    imo = nho + len(hb); emo = imo + len(p.imports)
    eb = b"".join(struct.pack("<QQIIQQQQQIBBBB", *e) for e in p.exports)
    ebo = emo + len(eb); gdo = ebo + len(p.bundles)
    head = struct.pack("<IIIIIIIIIIIIIIII", p.name_idx, p.name_no, p.src_idx, p.src_no, p.flags, p.cooked_hdr, 64, len(nb), nho, len(hb), imo, emo, ebo, gdo, len(p.graph), p.pad)
    return head + nb + bytes(nho - 64 - len(nb)) + hb + p.imports + eb + p.bundles + p.graph + b"".join(p.blobs)

def package_name(p): return p.names[p.name_idx][0]

# ------------------------------------------------------------------ ContainerHeader (type 10 chunk)
def header_layout(h):
    """-> dict(ids_off, count, store_off, store_len). Layout: id u64, package count u32, names TArray<u8>, name hashes TArray<u8>, package ids, store entries (32 B each + import arrays)"""
    cid, pc, nn = struct.unpack_from("<QII", h, 0); o = 16 + nn
    nh = struct.unpack_from("<I", h, o)[0]; o += 4 + nh
    n = struct.unpack_from("<I", h, o)[0]; o += 4; ids_off = o; o += 8 * n
    se = struct.unpack_from("<I", h, o)[0]; o += 4
    if n != pc or se < 32 * n: raise Unsupported("container header layout")
    return dict(ids_off=ids_off, count=n, store_off=o, store_len=se)

# ------------------------------------------------------------------ re-slot: rename the slot namespace inside a container
ANIM = "/Game/Mods/HD-ATOOL_P/anim/"

def _pkg_re(old):
    return re.compile(r"^" + re.escape(ANIM) + r"(%s)(a?)(/.*)?$" % re.escape(str(old)))

def _fix_strings(blob, old, new):
    """rewrite ASCII FStrings (int32 length incl. NUL) that contain .../anim/<old>[a] followed by / . ' | or end; anything unclear raises Unsupported"""
    pat = re.compile(rb"(/Game/Mods/HD-ATOOL_P/anim/)" + str(old).encode() + rb"(a?)(?=[/.'|\"\x00]|$)")
    pos = 0; out = bytearray(); last = 0
    while True:
        m = pat.search(blob, pos)
        if not m: break
        s = m.start()
        while s > 4 and 0x20 <= blob[s - 1] <= 0x7e: s -= 1
        e = m.end()
        while e < len(blob) and 0x20 <= blob[e] <= 0x7e: e += 1
        if e >= len(blob) or blob[e] != 0 or s < 4 or struct.unpack_from("<i", blob, s - 4)[0] != e - s + 1:
            raise Unsupported("unrecognised string container for the slot path")
        text = blob[s:e].decode("ascii")
        text = re.sub(r"(%s)%s(a?)(?=[/.'|\"]|$)" % (re.escape(ANIM), re.escape(str(old))), lambda mm: mm.group(1) + str(new) + mm.group(2), text)
        text = re.sub(r"(%s)%s(a?)\.%s\2" % (re.escape(ANIM), str(new), re.escape(str(old))), lambda mm: mm.group(1) + str(new) + mm.group(2) + "." + str(new) + mm.group(2), text)
        out += blob[last:s - 4] + struct.pack("<i", len(text) + 1) + text.encode("ascii") + b"\x00"; last = e + 1; pos = e + 1
    out += blob[last:]
    return bytes(out)

def packages_of(c):
    """{chunk index: Package or None} for every type 2 chunk"""
    out = {}
    for i, ch in enumerate(c.chunks):
        if ch["type"] == 2:
            try: out[i] = read_package(ch["data"])
            except (Unsupported, struct.error, IndexError, UnicodeDecodeError): out[i] = None
    return out

BULK_EXTS = (".m.ubulk", ".uptnl", ".ubulk")      # chunk files that hang off a package and carry its id

def path_names(c, ext=".uasset"):
    """{chunk index: package name derived from the directory index path}. The chunk id is the hash of THIS name; the name stored inside
    the package can differ (ports keep 'Adam' inside while the file is 'Adam_982')."""
    di = c.dirindex; paths = _dir_paths(di); out = {}
    for idx in range(len(di["dirs"])):
        ff = di["dirs"][idx][3]
        while ff != 0xFFFFFFFF:
            f = di["files"][ff]; name = di["strings"][f[0]]
            full = di["mount"] + (paths[idx] + "/" if paths[idx] else "") + name
            hit = next((x for x in (ext if isinstance(ext, tuple) else (ext,)) if name.endswith(x)), None)
            if hit and f[2] < len(c.chunks) and "Content/" in full:
                out[f[2]] = "/Game/" + full[:-len(hit)].split("Content/", 1)[1]
            ff = f[1]
    return out

def slots_in(c):
    """{slot: [package names]} for packages under .../anim/<n>[a][/...] (by directory path)"""
    out = {}; r = re.compile(r"^" + re.escape(ANIM) + r"(\d+)a?(/.*)?$")
    for i, nm in path_names(c).items():
        m = r.match(nm)
        if m: out.setdefault(int(m.group(1)), []).append(nm)
    return out

def rename_slot(c, old, new):
    """in place: move every package of slot <old> to <new> (names, ids, strings, container header, directory index). Returns [(old name, new name)]."""
    rx = _pkg_re(old); pk = packages_of(c); pn = path_names(c); moved = [i for i, nm in pn.items() if rx.match(nm) and pk.get(i) is not None]
    if not moved: raise Unsupported("slot %s is not in this container" % old)
    if any(p is None for p in pk.values()): raise Unsupported("a package of the container cannot be parsed")
    movedids = {c.chunks[j]["id"] for j in moved}; idmap = {}; renames = []
    for i in moved:
        nm = pn[i]; m = rx.match(nm)
        nn = ANIM + str(new) + m.group(2) + (m.group(3) or ""); nid = package_id(nn)
        if any(ch["id"] == nid and ch["id"] not in movedids for ch in c.chunks): raise Unsupported("new package id collides inside the container")
        idmap[c.chunks[i]["id"]] = nid; renames.append((nm, nn))
    for ch in c.chunks:                                     # bulk data (.ubulk etc.): its chunk id is the package id
        if ch["type"] not in (2, 10) and ch["id"] in idmap: ch["id"] = idmap[ch["id"]]               # data unchanged: keep the packer's stored hash
    for i, p in pk.items():
        mine = i in moved
        leaf = None
        if mine:
            m0 = rx.match(pn[i]); leaf = m0.group(1) + m0.group(2) if not m0.group(3) else None
        names = []; hashes = []
        for (s, wide), h in zip(p.names, p.hashes):
            ns = s; m2 = rx.match(s)
            if m2: ns = ANIM + str(new) + m2.group(2) + (m2.group(3) or "")
            elif mine and leaf and s == leaf: ns = str(new) + leaf[len(str(old)):]
            names.append((ns, wide)); hashes.append(h if ns == s else name_hash(ns, wide))
        p.names, p.hashes = names, hashes
        nb = [_fix_strings(b, old, new) for b in p.blobs]
        if nb != p.blobs:
            off = p.cooked_hdr
            for e, b in zip(p.exports, nb): e[0] = off; e[1] = len(b); off += len(b)
            p.blobs = nb
        for a, b2 in idmap.items():
            p.imports = p.imports.replace(struct.pack("<Q", a), struct.pack("<Q", b2)); p.graph = p.graph.replace(struct.pack("<Q", a), struct.pack("<Q", b2))
        nd = package_bytes(p)
        if nd != c.chunks[i]["data"]: c.chunks[i]["data"] = nd; c.chunks[i]["dirty"] = True
        if mine: c.chunks[i]["id"] = idmap[c.chunks[i]["id"]]; c.chunks[i]["dirty"] = True
    hi = next(k for k, ch in enumerate(c.chunks) if ch["type"] == 10); h = bytes(c.chunks[hi]["data"])
    for a, b2 in idmap.items():
        if h.count(struct.pack("<Q", a)) < 1: raise Unsupported("package id not in the container header")
        h = h.replace(struct.pack("<Q", a), struct.pack("<Q", b2))
    h = bytearray(h); L = header_layout(bytes(h)); byid = {ch["id"]: ch for ch in c.chunks if ch["type"] == 2}
    for k in range(L["count"]):
        pid = struct.unpack_from("<Q", h, L["ids_off"] + 8 * k)[0]
        if pid in byid: struct.pack_into("<Q", h, L["store_off"] + 32 * k, len(byid[pid]["data"]))
    c.chunks[hi]["data"] = bytes(h); c.chunks[hi]["dirty"] = True
    _rename_dirindex(c, old, new)
    return renames

def _dir_paths(di):
    """{dir index: path relative to the mount point}"""
    par = {}
    for idx, (nm, ch, sib, ff) in enumerate(di["dirs"]):
        c2 = ch
        while c2 != 0xFFFFFFFF: par[c2] = idx; c2 = di["dirs"][c2][2]
    def path(d):
        parts = []
        while d is not None:
            nm = di["dirs"][d][0]
            if nm != 0xFFFFFFFF: parts.append(di["strings"][nm])
            d = par.get(d)
        return "/".join(reversed(parts))
    return {i: path(i) for i in range(len(di["dirs"]))}

def _rename_dirindex(c, old, new):
    di = c.dirindex; so, sn = str(old), str(new); paths = _dir_paths(di)
    def newstr(i, text):                    # string table entries may be shared: add a new one and repoint, never edit in place
        di["strings"].append(text); di["kinds"].append(di["kinds"][i]); return len(di["strings"]) - 1
    for idx, e in enumerate(di["dirs"]):
        if e[0] != 0xFFFFFFFF and di["strings"][e[0]] == so + "a" and (di["mount"] + paths[idx]).rstrip("/").lower().endswith("hd-atool_p/anim/" + so.lower() + "a"): e[0] = newstr(e[0], sn + "a")
    paths = _dir_paths(di)
    for idx, e in enumerate(di["dirs"]):
        ff = e[3]
        while ff != 0xFFFFFFFF:
            f = di["files"][ff]; s = di["strings"][f[0]]
            if (di["mount"] + paths[idx]).rstrip("/").lower().endswith("hd-atool_p/anim") and s in tuple(so + sfx + x for sfx in ("", "a") for x in (".uasset",) + BULK_EXTS): f[0] = newstr(f[0], sn + s[len(so):])
            ff = f[1]
    used = {e[0] for e in di["dirs"] if e[0] != 0xFFFFFFFF} | {f[0] for f in di["files"]}
    remap = {}; strings = []; kinds = []
    for i, (s, k) in enumerate(zip(di["strings"], di["kinds"])):
        if i in used: remap[i] = len(strings); strings.append(s); kinds.append(k)
    for e in di["dirs"]:
        if e[0] != 0xFFFFFFFF: e[0] = remap[e[0]]
    for f in di["files"]: f[0] = remap[f[0]]
    di["strings"], di["kinds"] = strings, kinds

def check_container(c):
    """internal consistency: every package parses, id == hash(name), name hashes valid, header lists it with the right size, directory index agrees. -> [problems]"""
    bad = []; hi = [k for k, ch in enumerate(c.chunks) if ch["type"] == 10]
    if len(hi) != 1: return ["container header chunks: %d" % len(hi)]
    h = c.chunks[hi[0]]["data"]; L = header_layout(h)
    ids = [struct.unpack_from("<Q", h, L["ids_off"] + 8 * k)[0] for k in range(L["count"])]
    pk = {ch["id"]: ch for ch in c.chunks if ch["type"] == 2}
    if sorted(ids) != sorted(pk): bad.append("header ids differ from package chunks")
    for k, pid in enumerate(ids):
        ch = pk.get(pid)
        if not ch: continue
        try: p = read_package(ch["data"])
        except Exception as e: bad.append("package %#x unparsable: %s" % (pid, e)); continue
        for (s, w), hh in zip(p.names, p.hashes):
            try:
                if hh != name_hash(s, w): bad.append("package %s: stale hash for name %r" % (package_name(p), s)); break
            except Unsupported: pass                       # long name: cannot be verified
        if struct.unpack_from("<Q", h, L["store_off"] + 32 * k)[0] != len(ch["data"]): bad.append("package %s: ExportBundlesSize is stale" % package_name(p))
    for i, nm in path_names(c).items():
        try:
            if c.chunks[i]["id"] != package_id(nm): bad.append("chunk %d: id is not the hash of its path %s" % (i, nm))
        except Unsupported: pass
    for i, nm in path_names(c, BULK_EXTS).items():            # bulk data: id must be the hash of its package path too
        try:
            if c.chunks[i]["id"] != package_id(nm): bad.append("chunk %d: bulk id is not the hash of its path %s" % (i, nm))
        except Unsupported: pass
    return bad
