# R5F: numerics-preserving font compaction + verifier.
#   strip    <src> <out.woff2>            : HVAR bytes copied verbatim; glyf outlines emptied (except .notdef), post 3.0, name minimal (shared axis nameID), STAT dropped
#   reencode <src> <out.woff2>            : same as strip but the VarStore is re-serialised with the narrowest legal column widths, SAME region order (embedding LONG_WORDS fix)
#   merge    <out.woff2> <src1> <src2> .. : one file, one VarRegionList; one VarData per source (bytes/order preserved) + AdvWidthMap; codepoints re-packed sequentially from U+F0000
# Every mode verifies the variant against its source(s): identical regions, identical per-glyph delta rows in identical order, identical hmtx,
# identical advances on N random F2Dot14-grid locations + corners (NumPy, all glyphs) and fontTools VarStoreInstancer spot checks.
import sys, io, os, random, time, json
import numpy as np
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.varLib.varStore import VarStoreInstancer
from fontTools.varLib.models import supportScalar
from fontTools.varLib.builder import buildVarIdxMap
from fontTools.misc.roundTools import otRound

N_LOC = int(os.environ.get("R5F_NLOC", "2000"))
SEED = 20260924

def load(path):
    return TTFont(path, recalcBBoxes=False, recalcTimestamp=False)

def sfnt_bytes(font):
    b = io.BytesIO(); fl = font.flavor; font.flavor = None; font.save(b); font.flavor = fl; return len(b.getvalue())

def table_sizes(font):
    b = io.BytesIO(); fl = font.flavor; font.flavor = None; font.save(b); font.flavor = fl
    f2 = TTFont(io.BytesIO(b.getvalue()), lazy=True)
    return {t: f2.reader.tables[t].length for t in f2.reader.keys()}

# ---------- VarStore extraction (regions as tuples, rows as (regionIndices tuple, deltas tuple)) ----------
def regions_of(vs):
    rl = vs.VarRegionList
    return [tuple((a.StartCoord, a.PeakCoord, a.EndCoord) for a in r.VarRegionAxis) for r in rl.Region]

def varidx_of(hvar, font, gname):
    if hvar.AdvWidthMap is None:
        gid = font.getGlyphID(gname); return (0, gid)
    v = hvar.AdvWidthMap.mapping[gname]; return (v >> 16, v & 0xFFFF)

def row_of(vs, outer, inner):
    vd = vs.VarData[outer]
    return tuple(vd.VarRegionIndex), tuple(vd.Item[inner]), (vd.NumShorts & 0x7FFF, bool(vd.NumShorts & 0x8000))

def dense_row(vs, outer, inner):
    """deltas indexed by region index (dense), for numeric evaluation"""
    idx, item, _ = row_of(vs, outer, inner)
    out = np.zeros(vs.VarRegionList.RegionCount, dtype=np.int64)
    out[list(idx)] = item
    return out

# ---------- scalars, vectorised (same formula as fontTools supportScalar) ----------
def scalars_matrix(regions, locs):
    """regions: list of tuples of (start,peak,end) per axis; locs: (L, A) normalized coords -> (L, R) scalars"""
    R = len(regions); A = len(regions[0]); L = locs.shape[0]
    S = np.ones((L, R), dtype=np.float64)
    reg = np.array(regions, dtype=np.float64)  # R x A x 3
    for a in range(A):
        lo, pk, up = reg[:, a, 0], reg[:, a, 1], reg[:, a, 2]
        v = locs[:, a][:, None]  # L x 1
        active = (pk != 0) & ~((lo < 0) & (up > 0))   # peak 0 or straddling zero -> scalar 1 (fontTools/HarfBuzz rule)
        with np.errstate(divide="ignore", invalid="ignore"):
            below = np.where(pk != lo, (v - lo) / (pk - lo), 0.0)
            above = np.where(up != pk, (up - v) / (up - pk), 0.0)
        s = np.where(v == pk, 1.0, np.where((v <= lo) | (v >= up), 0.0, np.where(v < pk, below, above)))
        S *= np.where(active[None, :], s, 1.0)
    return S

def sample_locations(A, n, rng, grid=16384, fvar_axes=None):
    locs = rng.integers(-grid, grid + 1, size=(n, A)).astype(np.float64) / grid
    corners = [np.full(A, -1.0), np.full(A, 1.0), np.zeros(A), np.array([1.0 if i % 2 else -1.0 for i in range(A)])]
    for _ in range(8): corners.append(rng.choice([-1.0, 1.0], size=A))
    extra = []
    if fvar_axes is not None and [a.axisTag for a in fvar_axes] == ["GRUP", "LOCL"]:
        # the embedding pipeline's own locations: token t -> user (t//256, t%256), normalised (v-def)/(max-def), F2Dot14-rounded
        g, l = fvar_axes
        toks = np.unique(np.concatenate([rng.integers(0, 50257, size=n), np.array([0, 1, 255, 256, 50255, 50256])]))
        u = np.stack([toks // 256, toks % 256], 1).astype(np.float64)
        nrm = np.stack([(u[:, 0] - g.defaultValue) / (g.maxValue - g.defaultValue), (u[:, 1] - l.defaultValue) / (l.maxValue - l.defaultValue)], 1)
        extra.append(np.floor(nrm * grid + 0.5) / grid)
        locs = np.abs(locs)  # this face only has a positive normalised range
    return np.vstack([np.array(corners), locs] + extra)

def advances(font, glyphs, locs):
    """(len(glyphs), L) instanced advances = hmtx + otRound(sum scalar*delta) — fontTools semantics; chunked over locations"""
    vs = font["HVAR"].table.VarStore; hv = font["HVAR"].table
    regs = regions_of(vs); R = len(regs)
    D = np.stack([dense_row(vs, *varidx_of(hv, font, g)) for g in glyphs]).astype(np.float64)  # G x R
    base = np.array([font["hmtx"].metrics[g][0] for g in glyphs], dtype=np.int64)
    out = np.empty((len(glyphs), len(locs)), dtype=np.int64)
    step = max(1, int(4e6 // R))  # ~32 MB of scalars per chunk
    for i in range(0, len(locs), step):
        S = scalars_matrix(regs, locs[i:i + step])      # l x R
        out[:, i:i + step] = base[:, None] + np.floor(D @ S.T + 0.5).astype(np.int64)  # exact in float64 for these magnitudes
    return out

def verify_pair(src, var, gmap, label, rng, n_loc=N_LOC, spot=24):
    """gmap: {src glyph name: var glyph name}. Returns dict of check results; raises on mismatch."""
    t0 = time.time()
    svs = src["HVAR"].table.VarStore; vvs = var["HVAR"].table.VarStore
    sregs, vregs = regions_of(svs), regions_of(vvs)
    assert sregs == vregs, f"{label}: region lists differ"
    A = len(sregs[0])
    # structural: per glyph identical (regionIndices order, deltas, hmtx)
    rows_same = order_same = 0
    for sg, vg in gmap.items():
        sidx, sitem, senc = row_of(svs, *varidx_of(src["HVAR"].table, src, sg))
        vidx, vitem, venc = row_of(vvs, *varidx_of(var["HVAR"].table, var, vg))
        assert src["hmtx"].metrics[sg][0] == var["hmtx"].metrics[vg][0], f"{label}: hmtx differs for {sg}"
        if sidx == vidx: order_same += 1
        # dense compare (always required)
        ds = dict(zip(sidx, sitem)); dv = dict(zip(vidx, vitem))
        assert {k: v for k, v in ds.items() if v} == {k: v for k, v in dv.items() if v}, f"{label}: deltas differ for {sg}"
        rows_same += 1
    # numeric: all glyphs x (corners + n_loc random grid locations)
    locs = sample_locations(A, n_loc, rng, fvar_axes=src["fvar"].axes)
    sg_list = list(gmap); vg_list = [gmap[g] for g in sg_list]
    adv_s = advances(src, sg_list, locs); adv_v = advances(var, vg_list, locs)
    neq = int((adv_s != adv_v).sum())
    assert neq == 0, f"{label}: {neq} advance mismatches"
    # fontTools VarStoreInstancer spot checks (independent implementation of the scalar/rounding path)
    fv = src["fvar"].axes
    si = VarStoreInstancer(svs, fv); vi = VarStoreInstancer(vvs, var["fvar"].axes)
    spot_glyphs = rng.choice(len(sg_list), size=min(spot, len(sg_list)), replace=False)
    spot_locs = rng.choice(len(locs), size=min(64, len(locs)), replace=False)
    checked = 0
    for li in spot_locs:
        loc = {ax.axisTag: float(locs[li, i]) for i, ax in enumerate(fv)}
        si.setLocation(loc); vi.setLocation(loc)
        for gi in spot_glyphs:
            so, sin = varidx_of(src["HVAR"].table, src, sg_list[gi]); vo, vin = varidx_of(var["HVAR"].table, var, vg_list[gi])
            a = src["hmtx"].metrics[sg_list[gi]][0] + otRound(si[(so << 16) | sin])
            b = var["hmtx"].metrics[vg_list[gi]][0] + otRound(vi[(vo << 16) | vin])
            assert a == b == adv_s[gi, li], f"{label}: instancer mismatch {sg_list[gi]} {a} {b} {adv_s[gi, li]}"
            checked += 1
    # cross-check vectorised scalars against fontTools supportScalar on a sample
    for _ in range(200):
        li = rng.integers(len(locs)); ri = rng.integers(len(sregs))
        sup = {fv[i].axisTag: sregs[ri][i] for i in range(A) if sregs[ri][i][1] != 0}
        loc = {fv[i].axisTag: float(locs[li, i]) for i in range(A)}
        ref = supportScalar(loc, sup); mine = scalars_matrix([sregs[ri]], locs[li:li + 1])[0, 0]
        assert abs(ref - mine) < 1e-12, f"scalar mismatch {ref} {mine}"
    res = dict(glyphs=len(gmap), rows_identical=rows_same, region_order_identical=order_same, locations=int(len(locs)), corners=12,
               advance_cells=int(adv_s.size), mismatches=neq, instancer_spot_checks=checked,
               adv_min=int(adv_s.min()), adv_max=int(adv_s.max()), secs=round(time.time() - t0, 1))
    print(f"  VERIFY {label}: {res}")
    return res

# ---------- transforms ----------
def strip_tables(font, keep_notdef_outline=True):
    go = font.getGlyphOrder()
    if "glyf" in font:
        glyf = font["glyf"]
        for i, g in enumerate(go):
            if keep_notdef_outline and i == 0: continue
            glyf[g] = Glyph()  # empty outline, advance unaffected (hmtx/HVAR)
    post = font["post"]; post.formatType = 3.0; post.extraNames = []; post.mapping = {}
    if hasattr(post, "glyphOrder"): post.glyphOrder = None
    # name: keep IDs 0-6 on (3,1,0x409) only + one shared axis name
    name = font["name"]; keep = []
    for rec in name.names:
        if rec.nameID <= 6 and rec.platformID == 3: keep.append(rec)
    name.names = keep
    axis_id = name.addName("axis", platforms=((3, 1, 0x409),), minNameID=255)
    for ax in font["fvar"].axes: ax.axisNameID = axis_id
    font["fvar"].instances = []
    if "STAT" in font: del font["STAT"]
    if "DSIG" in font: del font["DSIG"]

def raw_copy_table(src, dst, tag):
    t = DefaultTable(tag); t.data = src.getTableData(tag); dst[tag] = t

def do_strip(src_path, out_path, reencode=False):
    src = load(src_path); var = load(src_path)
    hvar_raw = src.getTableData("HVAR")
    strip_tables(var)
    if reencode:
        vs = var["HVAR"].table.VarStore
        for vd in vs.VarData:
            # narrowest legal widths WITHOUT reordering columns. fontTools' calculateNumShorts overflows when > 32,767 columns
            # need 16 bits (NumShorts is uint16 with bit 15 = LONG_WORDS): 50,257 → 0xC451 = LONG_WORDS | 17,489 — the bug that
            # produced the original embedding face. Compute byte widths ourselves.
            M = np.abs(np.array(vd.Item, dtype=np.int32)).max(axis=0)
            assert M.max() <= 32767, "a delta needs 32 bits — keep fontTools' encoding"
            need16 = np.nonzero(M >= 128)[0]
            last16 = int(need16.max()) + 1 if len(need16) else 0   # columns [0, last16) become 16-bit (no reorder)
            vd.NumShorts = last16 if last16 <= 0x7FFF else 0x8000   # > 32,767 wide columns: LONG_WORDS mode with 0 int32 columns = all int16
            print(f"  reencode: {vd.ItemCount} items × {vd.VarRegionCount} regions, max|δ| {int(M.max())}, 16-bit columns needed {len(need16)} → NumShorts=0x{vd.NumShorts:04X}")
    else:
        raw_copy_table(src, var, "HVAR")
    b_src = len(open(src_path, "rb").read()); s_src = sfnt_bytes(src); ts_src = table_sizes(src)
    var.flavor = "woff2"; var.save(out_path)
    var2 = load(out_path)
    if not reencode: assert var2.getTableData("HVAR") == hvar_raw, "HVAR bytes changed"
    sgo, vgo = src.getGlyphOrder(), var2.getGlyphOrder(); assert len(sgo) == len(vgo)
    gmap = dict(zip(sgo, vgo))  # post 3.0 drops names: map by GID
    rng = np.random.default_rng(SEED)
    res = verify_pair(src, var2, gmap, os.path.basename(src_path), rng)
    # cmap identical modulo names
    scm, vcm = src.getBestCmap(), var2.getBestCmap()
    assert sorted(scm) == sorted(vcm) and all(gmap[scm[c]] == vcm[c] for c in scm), "cmap changed"
    s_var = sfnt_bytes(var2); b_var = os.path.getsize(out_path); ts_var = table_sizes(var2)
    out = dict(src=src_path, out=out_path, mode="reencode" if reencode else "strip", woff2_before=b_src, woff2_after=b_var,
               sfnt_before=s_src, sfnt_after=s_var, sfnt_saving_pct=round(100 * (1 - s_var / s_src), 2), tables_before=ts_src, tables_after=ts_var, verify=res)
    print(json.dumps({k: v for k, v in out.items() if k not in ("tables_before", "tables_after", "verify")}))
    return out

def do_merge(out_path, src_paths, base_cp=0xF0000):
    srcs = [load(p) for p in src_paths]
    first = srcs[0]
    tags = [a.axisTag for a in first["fvar"].axes]
    for s in srcs:
        assert [a.axisTag for a in s["fvar"].axes] == tags, "axis tags differ — cannot merge"
        assert [(a.minValue, a.defaultValue, a.maxValue) for a in s["fvar"].axes] == [(a.minValue, a.defaultValue, a.maxValue) for a in first["fvar"].axes]
        assert regions_of(s["HVAR"].table.VarStore) == regions_of(first["HVAR"].table.VarStore), "region lists differ — cannot merge"
        assert s["HVAR"].table.AdvWidthMap is None and s["HVAR"].table.VarStore.VarDataCount == 1
        assert s["head"].unitsPerEm == first["head"].unitsPerEm
    var = load(src_paths[0])
    # glyph order: .notdef + rows of each source (source .notdef rows are skipped; their VarData items keep source gids as inner index)
    order = [".notdef"]; hmtx = {".notdef": first["hmtx"].metrics[first.getGlyphOrder()[0]]}
    cmap = {}; mapping = {".notdef": 0}; gmaps = []; cp = base_cp; blocks = []
    for k, s in enumerate(srcs):
        go = s.getGlyphOrder(); scm = s.getBestCmap(); inv = {g: c for c, g in scm.items()}
        gm = {}; start = cp
        for gid, g in enumerate(go):
            if gid == 0: continue
            ng = f"s{k}g{gid}"; order.append(ng); hmtx[ng] = s["hmtx"].metrics[g]
            mapping[ng] = (k << 16) | gid; gm[g] = ng
            if g in inv:
                # sequential re-pack preserving each source's row order
                cmap[cp] = ng; cp += 1
        blocks.append((os.path.basename(src_paths[k]), hex(start), hex(cp - 1), cp - start))
        gmaps.append(gm)
    assert len(order) <= 65535, "glyph cap"
    var.setGlyphOrder(order)
    # glyf/loca: empty outlines
    glyf = newTable("glyf"); glyf.glyphs = {g: Glyph() for g in order}; glyf.glyphOrder = order
    nd = first["glyf"][first.getGlyphOrder()[0]]; glyf.glyphs[".notdef"] = nd
    var["glyf"] = glyf; var["loca"] = newTable("loca")
    var["hmtx"].metrics = hmtx
    var["maxp"].numGlyphs = len(order)
    # cmap format 12 only
    from fontTools.ttLib.tables._c_m_a_p import cmap_format_12
    cm = newTable("cmap"); cm.tableVersion = 0
    st = cmap_format_12(12); st.platformID = 3; st.platEncID = 10; st.language = 0; st.cmap = dict(cmap); st.format = 12; st.reserved = 0; st.length = 0; st.nGroups = 0
    cm.tables = [st]; var["cmap"] = cm
    # HVAR: region list of the first source; VarData k = source k's VarData object (unchanged: same NumShorts, VarRegionIndex, Items)
    hv = ot.HVAR(); hv.Version = 0x00010000
    vs = ot.VarStore(); vs.Format = 1
    vs.VarRegionList = first["HVAR"].table.VarStore.VarRegionList
    vs.VarData = [s["HVAR"].table.VarStore.VarData[0] for s in srcs]; vs.VarDataCount = len(vs.VarData)
    hv.VarStore = vs
    hv.AdvWidthMap = buildVarIdxMap([mapping[g] for g in order], order)
    hv.LsbMap = None; hv.RsbMap = None
    hvar = newTable("HVAR"); hvar.table = hv; var["HVAR"] = hvar
    gvar = newTable("gvar"); gvar.version = 1; gvar.reserved = 0; gvar.variations = {g: [] for g in order}; var["gvar"] = gvar
    strip_tables(var, keep_notdef_outline=True)
    var.flavor = "woff2"; var.save(out_path)
    var2 = load(out_path)
    vgo = var2.getGlyphOrder(); pos = {g: i for i, g in enumerate(order)}
    rename = {ng: vgo[pos[ng]] for ng in order}  # post 3.0 drops names: map by GID
    rng = np.random.default_rng(SEED)
    results = []
    for k, s in enumerate(srcs):
        gm = {sg: rename[ng] for sg, ng in gmaps[k].items()}
        r = verify_pair(s, var2, gm, f"merge[{k}]={os.path.basename(src_paths[k])}", rng)
        # cmap consistency: source cp order -> variant cp order within the block
        scm = s.getBestCmap(); vcm = var2.getBestCmap()
        lo, hi = int(blocks[k][1], 16), int(blocks[k][2], 16)
        src_cps = sorted(scm); var_cps = sorted(c for c in vcm if lo <= c <= hi)
        assert len(src_cps) == len(var_cps) and all(gm[scm[a]] == vcm[b] for a, b in zip(src_cps, var_cps)), "cmap row order broken"
        results.append(r)
    s_before = [sfnt_bytes(s) for s in srcs]; b_before = [os.path.getsize(p) for p in src_paths]
    out = dict(out=out_path, sources=src_paths, blocks=blocks, glyphs=len(order), woff2_before=sum(b_before), woff2_after=os.path.getsize(out_path),
               sfnt_before=sum(s_before), sfnt_after=sfnt_bytes(var2), tables_after=table_sizes(var2), verify=results)
    out["sfnt_saving_pct"] = round(100 * (1 - out["sfnt_after"] / out["sfnt_before"]), 2)
    print(json.dumps({k: v for k, v in out.items() if k not in ("tables_after", "verify")}))
    return out

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "strip": r = do_strip(sys.argv[2], sys.argv[3])
    elif mode == "reencode": r = do_strip(sys.argv[2], sys.argv[3], reencode=True)
    elif mode == "merge": r = do_merge(sys.argv[2], sys.argv[3:])
    else: raise SystemExit("mode?")
    json.dump(r, open(sys.argv[3 if mode != "merge" else 2] + ".json", "w"), indent=1)
