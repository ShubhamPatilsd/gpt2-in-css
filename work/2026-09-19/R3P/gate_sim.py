#!/usr/bin/env python3
"""R3P §1 exactness gate (offline, NumPy, no Chrome).

Re-implements the browser's per-layer numerics on the pinned 8-token run
(prompt 15496, teacher inputs = expected outputs 11,314,1101,7926,11,475,314) with
hooks at every carrier hop, and measures the effect of (a) today's transport
(font units rounding, F2Dot14 axes, 6-significant-digit typed numbers, float32
widths) and (b) a k-bit 2-per-carrier packing of one hop at a time.

Hops (what the carrier transports):
  qkv    font dot  n1 @ Wqkv          (2,305 carriers)   consumer: K/V/Q font axes + KV bank
  scores font dot  q.k  per head/slot (97)               consumer: softmax numbers
  ctx    font rows sum_s w_s v_is     (769)              consumer: attn font axes (--fq-attn)
  attn   font dot  ctx @ Wattn        (769)              consumer: --r = x + . (number)
  fc     font dot  n2 @ Wfc           (3,073)            consumer: GELU numbers -> proj axes
  proj   font dot  hidden @ Wproj     (769)              consumer: --out = r + . (number)
  loop   number    layer output rows  (2x769)            consumer: --x (LN numbers)
  bridge number    layer-11 output    (769)              consumer: head input (final LN)
"""
import argparse
import json
import math
import sys
import time

import numpy as np

TOOLS = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2H/tools"
sys.path.insert(0, TOOLS)
import build_gpt2_block_css as b  # noqa: E402
from analyze_full_gpt2 import MODEL_PATH, SafeTensors  # noqa: E402
from browser_gpt2_core import layer_matrices, attention_positions, W  # noqa: E402
from build_gpt2_groupwise_production_q16_sixfont import (  # noqa: E402
    AXIS_STEPS,
    SCORE_GAIN,
    WEIGHT_SCALE,
    R,
)

EXPECTED = [11, 314, 1101, 7926, 11, 475, 314, 1101]
TOKENS = [15496] + EXPECTED[:-1]
SHARD = 256
SCORE_COEF, SCORE_BASE = 468.0, 29984.0  # FvsDot: 15351.808px / 0.512, 128/(8*coef*.512)=.0667735
VALUE_COEF, VALUE_BASE = 12000.0, 12032.0  # FvsValue: 98566.144px = 8*base*1.024, 128/(coef*1.024)=.0104167
_LAYERS = {}
HOPS = ["qkv", "scores", "ctx", "attn", "fc", "proj", "loop", "bridge"]


def sig6(a):
    """Blink serialisation of a <number>: 6 significant digits."""
    a = np.asarray(a, dtype=np.float64)
    out = np.zeros_like(a)
    nz = a != 0
    e = np.floor(np.log10(np.abs(a[nz])))
    s = 10.0 ** (e - 5)
    out[nz] = np.round(a[nz] / s) * s
    return out


def f32(a):
    return np.asarray(a, dtype=np.float32).astype(np.float64)


def axis14(x):
    return np.rint(np.clip(x, -1, 1) * 16384) / 16384


def uniform_q(v, full_scale, k):
    """k-bit uniform quantiser over [-full_scale, full_scale] (full_scale broadcastable)."""
    step = 2.0 * np.asarray(full_scale, dtype=np.float64) / 2.0**k
    return np.rint(v / step) * step


class Cfg:
    def __init__(self, **kw):
        self.units = False  # integer glyph advances (per shard / per glyph)
        self.axis14 = False  # F2Dot14 quantisation of every font axis input
        self.sig6 = False  # 6-significant-digit typed numbers everywhere
        self.width32 = False  # float32 width + 1/64 px LayoutUnit + 6-digit progress on number hops
        self.progress_sig6 = True  # the animated progress number is itself serialised at 6 digits
        self.adv64 = False  # glyph advance px snapped to 1/64 px (LayoutUnit) per glyph run
        self.packs = {}  # hop -> (k, scale); scale: font (row base units) | dyn (per-row max|v|) | fixed
        self.fixed_scale = 2048.0
        self.__dict__.update(kw)
        if "pack" in kw and kw["pack"]:
            self.packs = {kw["pack"][0]: (kw["pack"][1], kw.get("pack_scale", "font"))}

    def packed(self, hop):
        return self.packs.get(hop)


def number_carrier(v, cfg, k=None, full_scale=None):
    """--saved / --out number -> width:calc(262144px + v*128px) -> view timeline -> --lp/--bridge-p -> decode."""
    v = np.asarray(v, dtype=np.float64)
    if k is not None:
        v = uniform_q(v, full_scale, k)
    if not cfg.width32:
        return v
    width = f32(262144.0 + f32(v) * 128.0)
    width = np.clip(width, 0, None)
    width = np.floor(width * 64.0) / 64.0  # LayoutUnit truncation (no-op above 2^18 where float spacing is 1/32)
    p = 524288.0 / (524288.0 + width)
    a = -2.0 + 3.0 * p
    if cfg.progress_sig6:
        a = sig6(a)
    return (1572864.0 / (a + 2.0) - 786432.0) / 128.0


def font_dot(xn, q, cfg, hop):
    """Glyph-advance dot product. xn: normalised inputs [T, in] in [-1,1]; q: QuantizedRows [out, in]."""
    if cfg.axis14:
        xn = axis14(xn)
    codes = q.codes.astype(np.float64)
    nin = codes.shape[1]
    units = np.zeros((xn.shape[0], codes.shape[0]))
    nshards = 0
    for s in range(0, nin, SHARD):
        part = xn[:, s : s + SHARD] @ codes[:, s : s + SHARD].T
        if cfg.units:
            part = np.rint(part)
        units += part
        nshards += 1
    if cfg.adv64:
        units = np.rint(units * 0.512 * 64.0) / 64.0 / 0.512
    pk = cfg.packed(hop)
    if pk:
        k, scale = pk
        if scale == "font":
            base = np.abs(codes).sum(1) + 32 * nshards  # row base = max |units| the font can emit
            units = uniform_q(units, base[None, :], k)
        else:
            units = uniform_q(units, np.abs(units).max(1, keepdims=True) * 1.001, k)
    # transport: (65536/p - 65536)*1000/512 - base = units, progress 0..1 serialised at 6 digits
    if cfg.width32:
        adv_px = units * 0.512  # advance px relative to base advance; base itself is exact integer units
        base_px = (np.abs(codes).sum(1) + 32 * nshards) * 0.512
        wpx = f32(base_px[None, :] + adv_px)
        p = 65536.0 / (65536.0 + wpx)
        if cfg.progress_sig6:
            p = sig6(p)
        units = (65536.0 / p - 65536.0) / 0.512 - base_px[None, :] / 0.512
    return units  # caller multiplies by scale * range


def rng_of(x):
    return np.maximum(1e-6, np.abs(x).max(1, keepdims=True)) * 1.001


def forward(tensors, cfg, blocks=12, kv_window=8, kv_sinks=0, trace=None):
    T = len(TOKENS)
    inputs = np.asarray(tensors.tensor("wte.weight")[TOKENS], dtype=np.float64) + np.asarray(
        tensors.tensor("wpe.weight")[:T], dtype=np.float64
    )
    S = sig6 if cfg.sig6 else (lambda a: a)
    rows = inputs.copy()
    caches = []
    for layer in range(blocks):
        if layer not in _LAYERS:
            _LAYERS[layer] = layer_matrices(tensors, layer)
        data, mats, biases = _LAYERS[layer]
        Wqkv, Wattn, Wfc, Wproj = mats
        # ---- LN1 (numbers) ----
        x = S(rows)
        n1 = S(np.stack([b.layer_norm(r, data["ln1_gamma"], data["ln1_beta"]) for r in x]))
        # ---- qkv font hop ----
        r1 = rng_of(n1)
        units = font_dot(n1 / r1, Wqkv, cfg, "qkv")
        qkv = S(units * Wqkv.scales[None, :] * r1 + biases[0][None, :])
        q, kk, vv = np.split(qkv, 3, axis=1)
        caches.append(qkv[:, 768:].copy())
        # ---- attention: scores font (bilinear), softmax numbers, V rows font ----
        ctx = np.zeros((T, W))
        for t in range(T):
            retained = attention_positions(t, kv_window, kv_sinks)
            for h in range(12):
                sl = slice(h * 64, (h + 1) * 64)
                qh = q[t, sl]
                fqs = max(1e-6, np.abs(qh).max())
                Q = qh / fqs
                if cfg.axis14:
                    Q = axis14(Q)
                kh = kk[retained][:, sl]
                vh = vv[retained][:, sl]
                ks = np.maximum(1e-6, np.abs(kh).max(1))
                vs = np.maximum(1e-6, np.abs(vh).max(1))
                K = kh / ks[:, None]
                V = vh / vs[:, None]
                if cfg.axis14:
                    K, V = axis14(K), axis14(V)
                su = SCORE_COEF * (K @ Q)  # units of Σ Q·K per slot
                if cfg.units:
                    su = np.rint(su)
                if cfg.adv64:
                    su = np.rint(su * 0.512 * 64.0) / 64.0 / 0.512
                pk = cfg.packed("scores")
                if pk:
                    su = uniform_q(su, SCORE_BASE if pk[1] == "font" else np.abs(su).max() * 1.001, pk[0])
                fs = S(su / SCORE_COEF * fqs * ks / 8.0)  # = q.k/8
                fm = fs.max()
                fe = S(np.exp(fs - fm))
                fd = S(fe.sum())
                fb = vs.max()
                fw = S(fe * vs / fb)  # P000 weight axis in [0,1]
                if cfg.axis14:
                    fw = axis14(fw)
                # value rows: Σ_s round(base + coef * V_is * fw_s) - 8*base
                gl = VALUE_COEF * (V * fw[:, None])  # [slots, 64]
                if cfg.units:
                    gl = np.rint(gl)
                cu = gl.sum(0)  # units above base per coordinate
                if cfg.adv64:
                    gl = np.rint(gl * 1.024 * 64.0) / 64.0 / 1.024
                    cu = gl.sum(0)
                pk = cfg.packed("ctx")
                if pk:
                    cu = uniform_q(cu, VALUE_COEF * len(retained) if pk[1] == "font" else np.abs(cu).max() * 1.001, pk[0])
                if cfg.width32:
                    # width = 262144 + (size - 8*base*1.024) * fb/fd * 128/(coef*1.024); progress via 524288 viewport
                    wpx = f32(262144.0 + cu * 1.024 * fb / fd * (128.0 / (VALUE_COEF * 1.024)))
                    p = 524288.0 / (524288.0 + wpx)
                    a = -2.0 + 3.0 * p
                    if cfg.progress_sig6:
                        a = sig6(a)
                    ctx_h = (1572864.0 / (a + 2.0) - 786432.0) / 128.0
                else:
                    ctx_h = cu / VALUE_COEF * fb / fd
                ctx[t, sl] = ctx_h
        ctx = S(ctx)
        # ---- attn projection font hop ----
        r2 = rng_of(ctx)
        units = font_dot(ctx / r2, Wattn, cfg, "attn")
        residual = S(x + S(units * Wattn.scales[None, :] * r2 + biases[1][None, :]))
        # ---- LN2 + fc font hop + GELU numbers ----
        n2 = S(np.stack([b.layer_norm(r, data["ln2_gamma"], data["ln2_beta"]) for r in residual]))
        r3 = rng_of(n2)
        units = font_dot(n2 / r3, Wfc, cfg, "fc")
        fz = S(units * Wfc.scales[None, :] * r3 + biases[2][None, :])
        ft = np.clip(0.7978845608028654 * (fz + 0.044715 * fz**3), -20, 20)
        hidden = S(0.5 * fz * (1 + np.tanh(ft)))
        # ---- proj font hop ----
        r4 = rng_of(hidden)
        units = font_dot(hidden / r4, Wproj, cfg, "proj")
        out = S(residual + S(units * Wproj.scales[None, :] * r4 + biases[3][None, :]))
        # ---- loop / bridge number hop ----
        hop = "bridge" if layer == blocks - 1 else "loop"
        pk = cfg.packed(hop)
        if pk:
            k, scale = pk
            fs_ = np.abs(out).max(1, keepdims=True) * 1.001 if scale == "dyn" else cfg.fixed_scale
            out = number_carrier(out, cfg, k, fs_)
        else:
            out = number_carrier(out, cfg)
        rows = S(out)
        if trace is not None:
            trace.append(
                dict(
                    layer=layer,
                    max_abs=dict(
                        n1=float(np.abs(n1).max()),
                        qkv=float(np.abs(qkv).max()),
                        ctx=float(np.abs(ctx).max()),
                        attn_dot=float(np.abs(residual - x).max()),
                        fz=float(np.abs(fz).max()),
                        hidden=float(np.abs(hidden).max()),
                        proj_dot=float(np.abs(out - residual).max()),
                        out=float(np.abs(out).max()),
                    ),
                )
            )
    return rows, caches


def head_ids(outputs, tensors, gamma, beta, qweights, weights, rounded=True, margins=False):
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs])
    if rounded:
        hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
        sc = np.rint(hidden @ qweights.T * SCORE_GAIN * 256)
    else:
        sc = hidden @ weights.T
    ids = sc.argmax(1).tolist()
    if not margins:
        return ids
    top2 = np.sort(sc, axis=1)[:, -2:]
    return ids, (top2[:, 1] - top2[:, 0]).tolist()


def err(a, bref):
    d = np.asarray(a) - np.asarray(bref)
    return float(np.sqrt(np.mean(d * d))), float(np.abs(d).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ks", default="10,12,14,16,18")
    ap.add_argument("--hops", default=",".join(HOPS))
    ap.add_argument("--scale", default="font")
    ap.add_argument("--out", default="/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3P/gate_results.json")
    ap.add_argument("--chrome", default="/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2H/run-combined3/verification-vectors.json")
    args = ap.parse_args()
    t0 = time.time()
    tensors = SafeTensors(MODEL_PATH)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    weights = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    qweights = np.rint(weights / WEIGHT_SCALE) * WEIGHT_SCALE
    chrome = json.load(open(args.chrome))
    chrome_final = np.asarray(chrome["finalResidual"], dtype=np.float64)

    from browser_gpt2_core import reference_sequence

    qref = reference_sequence(TOKENS, 12, kv_window=8, kv_sinks=0)
    fref = reference_sequence(TOKENS, 12, quantized=False)
    qref_out = np.asarray(qref["outputs"])
    float_ids = head_ids(fref["outputs"], tensors, gamma, beta, qweights, weights, rounded=False)
    qref_ids = head_ids(qref_out, tensors, gamma, beta, qweights, weights)
    results = {"expected": EXPECTED, "float_ids": float_ids, "qref_ids": qref_ids, "runs": []}
    print(f"float ids {float_ids}  qref ids {qref_ids}  expected {EXPECTED}  ({time.time()-t0:.0f}s)", flush=True)
    print(f"chrome finalResidual vs qref: rmse/max = {err(chrome_final, qref_out[-1])}", flush=True)

    def run(name, cfg, trace=None):
        t = time.time()
        rows, caches = forward(tensors, cfg, trace=trace)
        ids, margins = head_ids(rows, tensors, gamma, beta, qweights, weights, margins=True)
        rmse_q, max_q = err(rows[-1], qref_out[-1])
        rmse_c, max_c = err(rows[-1], chrome_final)
        kv_rmse = float(np.mean([err(caches[l][p], np.asarray(qref["layers"][l]["qkv"][p])[768:])[0] for l in range(12) for p in range(8)]))
        rec = dict(
            name=name,
            ids=ids,
            ids_ok=ids == EXPECTED,
            float_agree=[a == b_ for a, b_ in zip(ids, float_ids)],
            rmse_vs_qref=rmse_q,
            max_vs_qref=max_q,
            rmse_vs_chrome=rmse_c,
            max_vs_chrome=max_c,
            kv_rmse_vs_qref=kv_rmse,
            margins=margins,
            min_margin=min(margins),
            secs=time.time() - t,
        )
        results["runs"].append(rec)
        print(
            f"{name:34s} ids_ok={rec['ids_ok']!s:5s} float_agree={all(rec['float_agree'])!s:5s} "
            f"rmse_q={rmse_q:.5f} max_q={max_q:.4f} rmse_chrome={rmse_c:.5f} kv={kv_rmse:.5f} minmargin={min(margins):.0f} ids={ids}",
            flush=True,
        )
        return rec

    trace = []
    run("ideal (weights-only, = qref)", Cfg(), trace=trace)
    results["ranges"] = trace
    for tr in trace:
        print("  ranges L%2d: " % tr["layer"] + " ".join(f"{k}={v:.3g}" for k, v in tr["max_abs"].items()), flush=True)
    run("calib: units(int) only", Cfg(units=True))
    run("calib: axis14 only", Cfg(axis14=True))
    run("calib: adv64 only", Cfg(adv64=True))
    run("calib: sig6 only", Cfg(sig6=True))
    run("calib: w32(p6) only", Cfg(width32=True))
    run("calib: w32(pfull) only", Cfg(width32=True, progress_sig6=False))
    run("calib: axis14+adv64", Cfg(axis14=True, adv64=True))
    run("calib: axis14+adv64+sig6", Cfg(axis14=True, adv64=True, sig6=True))
    TODAY = dict(axis14=True, adv64=True, sig6=True, width32=True)
    run("TODAY = axis14+adv64+sig6+w32(p6)", Cfg(**TODAY))
    run("today variant: w32(pfull)", Cfg(axis14=True, adv64=True, sig6=True, width32=True, progress_sig6=False))
    run("today variant: +units(int)", Cfg(units=True, **TODAY))
    ks = [int(k) for k in args.ks.split(",")]
    for hop in args.hops.split(","):
        for k in ks:
            run(f"pack {hop} k={k} [{args.scale}]", Cfg(pack=(hop, k), pack_scale=args.scale))
    combos = {
        "TODAY + loop k14 dyn": {"loop": (14, "dyn")},
        "TODAY + loop k14 dyn + bridge k14 dyn": {"loop": (14, "dyn"), "bridge": (14, "dyn")},
        "TODAY + loop k14 fixed2048 + bridge k14 fixed2048": {"loop": (14, "fixed"), "bridge": (14, "fixed")},
        "TODAY + loop k12 dyn": {"loop": (12, "dyn")},
        "TODAY + attn/ctx/scores k14 font": {"attn": (14, "font"), "ctx": (14, "font"), "scores": (14, "font")},
        "TODAY + attn/ctx/scores k14 font + loop/bridge k14 dyn": {"attn": (14, "font"), "ctx": (14, "font"), "scores": (14, "font"), "loop": (14, "dyn"), "bridge": (14, "dyn")},
        "TODAY + all hops k14 font (loop/bridge dyn)": {h: (14, "font") for h in ["qkv", "scores", "ctx", "attn", "fc", "proj"]} | {"loop": (14, "dyn"), "bridge": (14, "dyn")},
        "TODAY + all hops k12 (font / dyn)": {h: (12, "font") for h in ["qkv", "scores", "ctx", "attn", "fc", "proj"]} | {"loop": (12, "dyn"), "bridge": (12, "dyn")},
    }
    for name, packs in combos.items():
        run(name, Cfg(packs=packs, **TODAY))
    json.dump(results, open(args.out, "w"), indent=1)
    print(f"done {time.time()-t0:.0f}s -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
