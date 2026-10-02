#!/usr/bin/env python3
"""R7S: build the Gumbel 'noise font' (64 seed columns x 50,257 rows) + NumPy references.

Run with the fontTools-enabled interpreter:
  PYTHONPATH=work/2026-09-19/R6X/tools /opt/homebrew/opt/python@3.11/bin/python3.11 R7S/build_noise_font.py

Font: one glyph per vocabulary row at U+80000+token (a 7th code-point plane, disjoint from the six
ProdQ16 planes U+2xxxx..U+7xxxx), two axes:
  SEED in [0,64] (default 0): 64 HVAR regions, region s (1..64) is the tent ((s-1)/64, s/64, (s+1)/64)
        in normalized coordinates -> exactly representable in F2DOT14 (s*256), so at SEED=s only column s applies.
  TEMP in [0,2]  (default 0): every region also carries the ramp (0,1,1) on TEMP -> scalar = T/2.
Deltas are 2*n[s,row] so at T=1 (scalar exactly 0.5) the applied advance delta is n[s,row] font units.
n[s,row] = rint(clip(Gumbel(0,1), -3, 12) * Q_PER_LOGIT) is the noise table in q16 score units
(1 q = 1/(SCORE_GAIN*256) logit = 1/130.1 logit). With size-adjust 4*UPEM/(62.5*FACTOR) on the face,
1 font unit of advance == 4 px of row width == 1 q unit, i.e. the noise lands exactly on the head's lattice.
"""
from __future__ import annotations
import json, sys, math
from pathlib import Path
import numpy as np
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.otlLib.builder import buildStatTable
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from build_matrix_backend_prototypes import build_master, UNITS_PER_EM
from build_gpt2_groupwise_production_q16_sixfont import (AXIS_STEPS, R, WEIGHT_SCALE, SCORE_GAIN, FACTOR, FONT_SIZE_PX)
from analyze_full_gpt2 import MODEL_PATH, SafeTensors

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VOCAB = 50_257
S = 64
BASE_ADVANCE = 800          # units; keeps advance >= 0 for the most negative noise at T=2
CLIP = (-3.0, 12.0)         # logits
Q_PER_LOGIT = SCORE_GAIN * 256
SIZE_ADJUST = 4 * UNITS_PER_EM / (FONT_SIZE_PX * float(FACTOR))   # 1 unit -> 4 px of row width
TABLE_SEED = 20261001

def gumbel_table():
    rng = np.random.default_rng(TABLE_SEED)
    u = rng.random((S, VOCAB))
    g = -np.log(-np.log(u))
    g = np.clip(g, *CLIP)
    n = np.rint(g * Q_PER_LOGIT).astype(np.int32)
    return g, n

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
    supports = []
    for s in range(1, S + 1):
        supports.append({"SEED": ((s - 1) / S, s / S, min(1.0, (s + 1) / S)), "TEMP": (0.0, 1.0, 1.0)})
    region_list = buildVarRegionList(supports, ["SEED", "TEMP"])
    items = [[0] * S]  # .notdef
    d = (2 * n).T.astype(int)  # [VOCAB, S]
    items.extend(d.tolist())
    var_data = buildVarData(list(range(S)), items, optimize=False)
    hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [var_data])
    hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
    font["HVAR"] = hvar
    gvar = newTable("gvar"); gvar.version = 1; gvar.reserved = 0
    gvar.variations = {g: [] for g in font.getGlyphOrder()}
    font["gvar"] = gvar
    font.save(out); font.close(); tmp.unlink()

def head_scores(hidden: np.ndarray, qweights: np.ndarray):
    hq = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    raw = hq @ qweights.T * Q_PER_LOGIT      # unrounded q-units
    return raw, np.rint(raw)

def realized_T(T: float) -> float:
    return round(T / 2 * 16384) / 16384 * 2

def main():
    g, n = gumbel_table()
    out_font = HERE / "noise" / "gumbel-noise.ttf"
    build_font(n, out_font)
    np.savez_compressed(HERE / "noise" / "noise-table.npz", n_q=n.astype(np.int16), gumbel=g.astype(np.float32),
                        table_seed=TABLE_SEED, q_per_logit=Q_PER_LOGIT, clip=np.array(CLIP))
    # references for the fixture
    ref = json.loads((ROOT / "experiments/browser-gpt2/head-two-pass/reference.json").read_text())
    tensors = SafeTensors(MODEL_PATH)
    w = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    qweights = np.rint(w / WEIGHT_SCALE) * WEIGHT_SCALE
    states = [0, 1, 2]          # fixture indices into reference['hidden'] (states 391, 647, 382)
    cols = [1, 17, 42]
    temps = [0.0, 1.0, 0.7]
    cases = []
    for si in states:
        h = np.asarray(ref["hidden"][si], dtype=np.float64)
        raw, q = head_scores(h, qweights)
        greedy = int(q.argmax())
        srt = np.sort(q)[::-1]
        cases.append({"state": ref["sourceStates"][si], "fixtureIndex": si, "col": 0, "T": 0.0, "Treal": 0.0,
                      "expected": greedy, "marginQ": float(srt[0] - srt[1]), "kind": "greedy"})
        for col in cols:
            for T in temps[1:]:
                Tr = realized_T(T)
                if T == 1.0:
                    sc = q + n[col - 1]                 # lattice-exact integers
                else:
                    sc = np.rint(raw + n[col - 1] * Tr)
                win = int(sc.argmax()); s2 = np.sort(sc)[::-1]
                cases.append({"state": ref["sourceStates"][si], "fixtureIndex": si, "col": col, "T": T, "Treal": Tr,
                              "expected": win, "marginQ": float(s2[0] - s2[1]), "greedy": greedy,
                              "kind": "lattice-exact" if T == 1.0 else "rounded-model"})
    meta = {"S": S, "vocab": VOCAB, "baseAdvance": BASE_ADVANCE, "clipLogits": CLIP, "qPerLogit": Q_PER_LOGIT,
            "sizeAdjustPercent": SIZE_ADJUST * 100, "tableSeed": TABLE_SEED, "font": out_font.name,
            "fontBytes": out_font.stat().st_size, "noiseMinQ": int(n.min()), "noiseMaxQ": int(n.max()),
            "cases": cases}
    (HERE / "head-sample" / "expected.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k != "cases"}, indent=1))
    for c in cases: print(c)

if __name__ == "__main__":
    main()
