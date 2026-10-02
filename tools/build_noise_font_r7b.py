#!/usr/bin/env python3
"""R7B: build the Gumbel 'noise font' for the demo = R7S/build_noise_font.py (same table: rng seed 20261001, 64 columns x 50,257
rows, n = rint(clip(Gumbel(0,1), -3, 12) * SCORE_GAIN*256), deltas 2n, SEED tents / TEMP ramp, base advance 800, size-adjust
4*UPEM/(62.5*FACTOR)) written to R7B/assets-r7b/ (fonts only under R7B/assets-r7b). Also writes noise-table.npz (int16) and
noise-meta.json (sha256 of the table bytes and of the font). No fixture references (R7S/head-sample has them).
Run: cd R7B && uv run --with numpy --with fonttools python tools/build_noise_font_r7b.py
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.otlLib.builder import buildStatTable
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from build_matrix_backend_prototypes import build_master, UNITS_PER_EM
from build_gpt2_groupwise_production_q16_sixfont import SCORE_GAIN, FACTOR, FONT_SIZE_PX

OUT_DIR = Path(__file__).resolve().parents[1] / "assets-r7b"
VOCAB = 50_257
S = 64
BASE_ADVANCE = 800
CLIP = (-3.0, 12.0)
Q_PER_LOGIT = SCORE_GAIN * 256
SIZE_ADJUST = 4 * UNITS_PER_EM / (FONT_SIZE_PX * float(FACTOR))
TABLE_SEED = 20261001
FONT_NAME = "gumbel-noise.ttf"


def gumbel_table():
    rng = np.random.default_rng(TABLE_SEED)
    u = rng.random((S, VOCAB))
    g = -np.log(-np.log(u))
    g = np.clip(g, *CLIP)
    return g, np.rint(g * Q_PER_LOGIT).astype(np.int32)


def build_font(n: np.ndarray, out: Path):
    widths = np.full(VOCAB, BASE_ADVANCE, dtype=np.int64)
    tmp = out.with_suffix(".master.ttf")
    build_master(tmp, widths, "Noise", codepoint_start=0x80000)
    font = TTFont(tmp, recalcTimestamp=False)
    fvar = newTable("fvar"); fvar.axes = []; fvar.instances = []
    stat = []
    for i, (tag, lo, hi) in enumerate((("SEED", 0, S), ("TEMP", 0, 2))):
        ax = Axis(); ax.axisTag = tag; ax.minValue = lo; ax.defaultValue = 0; ax.maxValue = hi; ax.flags = 0
        ax.axisNameID = font["name"].addName(tag); fvar.axes.append(ax)
        stat.append({"tag": tag, "name": ax.axisNameID, "ordering": i})
    font["fvar"] = fvar
    buildStatTable(font, stat)
    supports = [{"SEED": ((s - 1) / S, s / S, min(1.0, (s + 1) / S)), "TEMP": (0.0, 1.0, 1.0)} for s in range(1, S + 1)]
    region_list = buildVarRegionList(supports, ["SEED", "TEMP"])
    items = [[0] * S]
    items.extend((2 * n).T.astype(int).tolist())
    var_data = buildVarData(list(range(S)), items, optimize=False)
    hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [var_data])
    hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
    font["HVAR"] = hvar
    gvar = newTable("gvar"); gvar.version = 1; gvar.reserved = 0
    gvar.variations = {g: [] for g in font.getGlyphOrder()}
    font["gvar"] = gvar
    font.save(out); font.close(); tmp.unlink()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    g, n = gumbel_table()
    out_font = OUT_DIR / FONT_NAME
    build_font(n, out_font)
    n16 = n.astype(np.int16)
    np.savez_compressed(OUT_DIR / "noise-table.npz", n_q=n16, gumbel=g.astype(np.float32), table_seed=TABLE_SEED,
                        q_per_logit=Q_PER_LOGIT, clip=np.array(CLIP))
    meta = {"S": S, "vocab": VOCAB, "baseAdvance": BASE_ADVANCE, "clipLogits": CLIP, "qPerLogit": Q_PER_LOGIT,
            "sizeAdjustPercent": SIZE_ADJUST * 100, "tableSeed": TABLE_SEED, "font": FONT_NAME,
            "fontBytes": out_font.stat().st_size, "fontSha256": hashlib.sha256(out_font.read_bytes()).hexdigest(),
            "tableSha256": hashlib.sha256(np.ascontiguousarray(n16).tobytes()).hexdigest(),
            "noiseMinQ": int(n.min()), "noiseMaxQ": int(n.max()), "upem": UNITS_PER_EM}
    (OUT_DIR / "noise-meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
