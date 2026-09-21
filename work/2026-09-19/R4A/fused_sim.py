#!/usr/bin/env python3
"""R4A: fused fc -> GELU -> proj inside one variable-font evaluation per layer (offline NumPy).

Reuses R3P/gate_sim.py (TODAY transport model: F2Dot14 axes, 1/64 px advances, 6-digit numbers,
float32 widths + 6-digit progress) and replaces the fc hop + CSS GELU + proj hop by the only
formulation that removes the geometry->number boundary: a font that sees all 768 LN2 outputs
as axes (needs >= 769 axes -> Fontations backend), computes the pre-activations in avar2
(2 linear regions per input axis, F2Dot14 coefficients, output coordinate rounded to F2Dot14
and clamped to [-1, 1]), applies GELU as K hat regions per hidden axis in HVAR with int16
deltas (B_oi * GELU(knot_k) * s_o) and returns the proj partial sums as glyph advances
(4 fonts x 768 hidden each; 4 glyphs per carrier; integer-unit advances as the Fontations
probe measured).

Error terms modelled (all switchable):
  F1 fixed per-input-dim scale R_j (no dynamic --range-fc possible before a nonlinearity)
  F2 avar2 coefficients A_ij R_j / S_i on the F2Dot14 grid
  F3 pre-activation coordinate z_i / S_i on the F2Dot14 grid, clamped (S_i fixed per unit)
  F4 K-hat piecewise-linear GELU (knots snapped to the F2Dot14 grid of S_i)
  F5 int16 HVAR deltas s_o * B_oi * GELU(knot) with s_o from the 32,767-unit advance budget
  F6 integer glyph advances (Fontations) + TODAY's carrier transport (adv64, w32(p6))
"""
import argparse
import json
import sys
import time

import numpy as np

sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3P")
import gate_sim as g  # noqa: E402

b = g.b
TOKENS, EXPECTED = g.TOKENS, g.EXPECTED
F14 = 16384.0
ADV_BUDGET = 32700.0  # safe_base_advance: base + max <= 65535 -> row range <= ~32.7k units


def gelu(z):
    z = np.asarray(z, dtype=np.float64)
    t = np.clip(0.7978845608028654 * (z + 0.044715 * z**3), -20, 20)
    return 0.5 * z * (1 + np.tanh(t))


def gelu_dd(z):
    h = 1e-3
    return (gelu(z + h) - 2 * gelu(z) + gelu(z - h)) / h**2


def knot_template(K, zc=6.0, mode="curv"):
    """K hat regions per axis = K knots excluding 0 (0 is always a knot; its hat is the 'always 1' HarfBuzz
    region with delta GELU(0)=0). Returns interior knots in z (without the +-S end knots)."""
    n_int = K - 2  # two of the K are the end knots at -S and +S
    if n_int < 1:
        return np.array([])
    if mode == "uniform":
        ks = np.linspace(-zc, zc, n_int + 2)[1:-1]
    else:
        zz = np.linspace(-zc, zc, 20001)
        dens = np.sqrt(np.abs(gelu_dd(zz))) + 1e-4
        cdf = np.cumsum(dens)
        cdf = (cdf - cdf[0]) / (cdf[-1] - cdf[0])
        ks = np.interp((np.arange(n_int) + 0.5) / n_int, cdf, zz)
    ks = ks[np.abs(ks) > 1e-9]
    return np.unique(np.r_[ks, 0.0])


def snap14(v):
    return np.rint(v * F14) / F14


class Fused:
    def __init__(self, K=32, zc=6.0, in_margin=2.0, z_margin=2.0, per_dim=True, units=True,
                 coef14=True, coord14=True, delta16=True, knots="curv", nfonts=4, exact_gelu=False,
                 dyn_scale=False, fine=False):
        self.K, self.zc = K, zc
        self.in_margin, self.z_margin, self.per_dim = in_margin, z_margin, per_dim
        self.units, self.coef14, self.coord14, self.delta16 = units, coef14, coord14, delta16
        self.knots, self.nfonts, self.exact_gelu = knots, nfonts, exact_gelu
        self.fine = fine  # two-level glyph: coarse int deltas + fine glyph (1/64 unit) at 1/64 font-size
        self.dyn_scale = dyn_scale  # hypothetical: dynamic ranges as today (not realisable; bound only)
        self.template = knot_template(K, zc, knots)
        self.stats = []

    def name(self):
        return (f"fused K={self.K} zc={self.zc} in={self.in_margin}x{'pd' if self.per_dim else 'gl'} "
                f"z={self.z_margin}x units={int(self.units)} c14={int(self.coef14)} k14={int(self.coord14)} "
                f"d16={int(self.delta16)} {self.knots}{' EXACTGELU' if self.exact_gelu else ''}"
                f"{' DYN' if self.dyn_scale else ''}")


def calibrate(tensors, cfg):
    """Ideal-model per-layer maxima of |n2| per input dim and |z| per hidden unit over the pinned run."""
    trace = {"n2": [], "z": []}
    g.forward(tensors, g.Cfg(), trace=None)  # populate _LAYERS
    # rerun manually to capture n2/z (gate_sim.forward does not expose them): duplicate its loop
    rows = np.asarray(tensors.tensor("wte.weight")[TOKENS], dtype=np.float64) + np.asarray(
        tensors.tensor("wpe.weight")[: len(TOKENS)], dtype=np.float64)
    for layer in range(12):
        data, mats, biases = g._LAYERS[layer]
        A, Bm = data["fc_weight"], data["mlp_proj_weight"]
        x = rows
        n1 = np.stack([b.layer_norm(r, data["ln1_gamma"], data["ln1_beta"]) for r in x])
        Wqkv = mats[0].reconstructed
        qkv = n1 @ Wqkv.T + biases[0]
        q, kk, vv = np.split(qkv, 3, axis=1)
        T = len(TOKENS)
        ctx = np.zeros((T, g.W))
        for t in range(T):
            ret = g.attention_positions(t, 8, 0)
            for h in range(12):
                sl = slice(h * 64, (h + 1) * 64)
                sc = kk[ret][:, sl] @ q[t, sl] / 8.0
                e = np.exp(sc - sc.max())
                ctx[t, sl] = (e / e.sum()) @ vv[ret][:, sl]
        residual = x + ctx @ mats[1].reconstructed.T + biases[1]
        n2 = np.stack([b.layer_norm(r, data["ln2_gamma"], data["ln2_beta"]) for r in residual])
        z = n2 @ A.T + biases[2]
        hidden = gelu(z)
        rows = residual + hidden @ Bm.T + biases[3]
        trace["n2"].append(np.abs(n2).max(0))
        trace["z"].append(np.abs(z).max(0))
    return trace


def fused_mlp(n2, data, biases, fu, calib, layer, cfg, S):
    """Return proj output (before residual add), plus per-layer stats appended to fu.stats."""
    A = data["fc_weight"]  # [3072, 768] float
    Bm = data["mlp_proj_weight"]  # [768, 3072]
    bfc, bproj = biases[2], biases[3]
    T = n2.shape[0]
    # ---- F1: input scale (fixed) ----
    if fu.dyn_scale:
        R = g.rng_of(n2)  # [T,1] per pass (hypothetical)
        Rj = np.broadcast_to(R, n2.shape)
    else:
        m = calib["n2"][layer]
        Rj = (m * fu.in_margin) if fu.per_dim else np.full_like(m, m.max() * fu.in_margin)
        Rj = np.maximum(Rj, 0.25)[None, :]
    xin = np.clip(n2 / Rj, -1, 1)
    if cfg.axis14:
        xin = g.axis14(xin)
    # ---- pre-activation scale S_i (fixed per unit) ----
    zmax = calib["z"][layer]
    if fu.dyn_scale:
        Si = np.maximum(zmax * 1.001, 6.0)  # still fixed: no dynamic scale exists inside a font
    else:
        Si = np.maximum(zmax * fu.z_margin, 6.0)
    # ---- F2: avar2 coefficients a_ij = A_ij R_j / S_i on F2Dot14; bias via constant axis ----
    if fu.dyn_scale:
        a = A[None, :, :] * Rj[:, None, :] / Si[None, :, None]  # [T,3072,768]
        if fu.coef14:
            a = snap14(a)
        zc = np.einsum("tij,tj->ti", a, xin) + (snap14(bfc / Si) if fu.coef14 else bfc / Si)[None, :]
        coef_max = float(np.abs(a).max())
    else:
        a = A * Rj / Si[:, None]
        if fu.coef14:
            a = snap14(a)
        bq = snap14(bfc / Si) if fu.coef14 else bfc / Si
        zc = xin @ a.T + bq[None, :]
        coef_max = float(np.abs(a).max())
    # ---- F3: output coordinate F2Dot14 + clamp ----
    clipped = float(np.mean(np.abs(zc) > 1.0))
    zc = np.clip(zc, -1, 1)
    if fu.coord14:
        zc = snap14(zc)
    z = zc * Si[None, :]
    # ---- F4: K-hat piecewise-linear GELU on knots snapped to the F2Dot14 grid of S_i ----
    # ---- F5: int16 HVAR deltas D[o,i,k] = rint(s_o B_oi GELU(knot_k)); the advance is the hat-interpolation
    #          of the rounded knot deltas (continuous between knots, exact at knots) ----
    # ---- F6: integer glyph advances per font (Fontations), then TODAY's carrier transport ----
    nf = fu.nfonts
    per = A.shape[0] // nf
    hk_max = np.maximum(np.abs(gelu(Si)), 0.17)  # worst |h_i| the axis can produce
    rowmax = np.zeros(Bm.shape[0])
    for f in range(nf):
        sl = slice(f * per, (f + 1) * per)
        rowmax = np.maximum(rowmax, np.abs(Bm[:, sl]) @ hk_max[sl])
    s_o = ADV_BUDGET / np.maximum(rowmax, 1e-9)  # units per value, shared by the nf glyphs of carrier o
    units_total = np.zeros((T, Bm.shape[0]))
    if fu.exact_gelu:
        h = gelu(z)
        for f in range(nf):
            sl = slice(f * per, (f + 1) * per)
            units_f = (h[:, sl] @ Bm[:, sl].T) * s_o[None, :]
            if fu.units:
                units_f = np.rint(units_f)
            if cfg.adv64:
                units_f = np.rint(units_f * 0.512 * 64.0) / 64.0 / 0.512
            units_total += units_f
    else:
        tmpl = fu.template
        for f in range(nf):
            units_f = np.zeros((T, Bm.shape[0]))
            fine_f = np.zeros((T, Bm.shape[0]))
            for i in range(f * per, (f + 1) * per):
                kz = np.r_[-Si[i], tmpl[np.abs(tmpl) < Si[i]], Si[i]]
                kz = np.unique(snap14(kz / Si[i])) * Si[i]  # knot positions representable on the axis grid
                gk = gelu(kz)  # [K+1]
                zi = np.clip(z[:, i], kz[0], kz[-1])
                idx = np.clip(np.searchsorted(kz, zi, side="right") - 1, 0, len(kz) - 2)
                w = (kz[idx + 1] - zi) / (kz[idx + 1] - kz[idx])  # weight of the left knot
                exact_D = s_o[:, None] * Bm[:, i][:, None] * gk[None, :]  # [768, K+1]
                if fu.delta16 and fu.fine:
                    C = np.rint(exact_D)
                    Fd = np.rint((exact_D - C) * 64.0)  # |F| <= 32 units of the fine glyph
                    units_f += w[:, None] * C[:, idx].T + (1 - w)[:, None] * C[:, idx + 1].T
                    fine_f += w[:, None] * Fd[:, idx].T + (1 - w)[:, None] * Fd[:, idx + 1].T
                elif fu.delta16:
                    D = np.rint(exact_D)  # int16 deltas
                    units_f += w[:, None] * D[:, idx].T + (1 - w)[:, None] * D[:, idx + 1].T
                else:
                    units_f += w[:, None] * exact_D[:, idx].T + (1 - w)[:, None] * exact_D[:, idx + 1].T
            if fu.units:
                units_f = np.rint(units_f)
                fine_f = np.rint(fine_f)
            if cfg.adv64:
                units_f = np.rint(units_f * 0.512 * 64.0) / 64.0 / 0.512
                fine_f = np.rint(fine_f * 0.008 * 64.0) / 64.0 / 0.008
            units_total += units_f + fine_f / 64.0
    # ---- carrier transport as font_dot (width32/p6): nf glyphs in one inline box ----
    if cfg.width32:
        base_px = nf * (ADV_BUDGET + 32.0) * 0.512
        wpx = g.f32(base_px + units_total * 0.512)
        p = 65536.0 / (65536.0 + wpx)
        if cfg.progress_sig6:
            p = g.sig6(p)
        units_total = (65536.0 / p - 65536.0) / 0.512 - base_px / 0.512
    y = units_total / s_o[None, :]
    s_min = float(s_o.min())
    fu.stats.append(dict(layer=layer, clipped_frac=clipped, coef_max=coef_max, s_o_min=s_min,
                         Si_max=float(Si.max()), Rj_max=float(Rj.max())))
    return S(y + bproj[None, :])


def forward_fused(tensors, cfg, fu, calib, kv_window=8, kv_sinks=0):
    """gate_sim.forward with the fc/GELU/proj section replaced by fused_mlp."""
    T = len(TOKENS)
    inputs = np.asarray(tensors.tensor("wte.weight")[TOKENS], dtype=np.float64) + np.asarray(
        tensors.tensor("wpe.weight")[:T], dtype=np.float64)
    S = g.sig6 if cfg.sig6 else (lambda a: a)
    rows = inputs.copy()
    caches = []
    for layer in range(12):
        data, mats, biases = g._LAYERS[layer]
        Wqkv, Wattn, Wfc, Wproj = mats
        x = S(rows)
        n1 = S(np.stack([b.layer_norm(r, data["ln1_gamma"], data["ln1_beta"]) for r in x]))
        r1 = g.rng_of(n1)
        units = g.font_dot(n1 / r1, Wqkv, cfg, "qkv")
        qkv = S(units * Wqkv.scales[None, :] * r1 + biases[0][None, :])
        q, kk, vv = np.split(qkv, 3, axis=1)
        caches.append(qkv[:, 768:].copy())
        ctx = np.zeros((T, g.W))
        for t in range(T):
            retained = g.attention_positions(t, kv_window, kv_sinks)
            for h in range(12):
                sl = slice(h * 64, (h + 1) * 64)
                qh = q[t, sl]
                fqs = max(1e-6, np.abs(qh).max())
                Q = qh / fqs
                if cfg.axis14:
                    Q = g.axis14(Q)
                kh = kk[retained][:, sl]
                vh = vv[retained][:, sl]
                ks = np.maximum(1e-6, np.abs(kh).max(1))
                vs = np.maximum(1e-6, np.abs(vh).max(1))
                K = kh / ks[:, None]
                V = vh / vs[:, None]
                if cfg.axis14:
                    K, V = g.axis14(K), g.axis14(V)
                su = g.SCORE_COEF * (K @ Q)
                if cfg.adv64:
                    su = np.rint(su * 0.512 * 64.0) / 64.0 / 0.512
                fs = S(su / g.SCORE_COEF * fqs * ks / 8.0)
                fm = fs.max()
                fe = S(np.exp(fs - fm))
                fd = S(fe.sum())
                fb = vs.max()
                fw = S(fe * vs / fb)
                if cfg.axis14:
                    fw = g.axis14(fw)
                gl = g.VALUE_COEF * (V * fw[:, None])
                if cfg.adv64:
                    gl = np.rint(gl * 1.024 * 64.0) / 64.0 / 1.024
                cu = gl.sum(0)
                if cfg.width32:
                    wpx = g.f32(262144.0 + cu * 1.024 * fb / fd * (128.0 / (g.VALUE_COEF * 1.024)))
                    p = 524288.0 / (524288.0 + wpx)
                    a = -2.0 + 3.0 * p
                    if cfg.progress_sig6:
                        a = g.sig6(a)
                    ctx_h = (1572864.0 / (a + 2.0) - 786432.0) / 128.0
                else:
                    ctx_h = cu / g.VALUE_COEF * fb / fd
                ctx[t, sl] = ctx_h
        ctx = S(ctx)
        r2 = g.rng_of(ctx)
        units = g.font_dot(ctx / r2, Wattn, cfg, "attn")
        residual = S(x + S(units * Wattn.scales[None, :] * r2 + biases[1][None, :]))
        n2 = S(np.stack([b.layer_norm(r, data["ln2_gamma"], data["ln2_beta"]) for r in residual]))
        if fu is None:
            r3 = g.rng_of(n2)
            units = g.font_dot(n2 / r3, Wfc, cfg, "fc")
            fz = S(units * Wfc.scales[None, :] * r3 + biases[2][None, :])
            hidden = S(gelu(fz))
            r4 = g.rng_of(hidden)
            units = g.font_dot(hidden / r4, Wproj, cfg, "proj")
            out = S(residual + S(units * Wproj.scales[None, :] * r4 + biases[3][None, :]))
        else:
            out = S(residual + fused_mlp(n2, data, biases, fu, calib, layer, cfg, S))
        out = g.number_carrier(out, cfg)
        rows = S(out)
    return rows, caches


def cost_model(K, nfonts=4, hidden_per=768, axes=769, glyphs=768, ns_per_eval=(0.5, 1.5)):
    avar_regions = 2 * 768 + 1
    hvar_regions = hidden_per * K
    region_list = (avar_regions + hvar_regions) * axes * 6
    avar_deltas = hidden_per * avar_regions * 2
    hvar_deltas = glyphs * hvar_regions * 2
    raw = region_list + avar_deltas + hvar_deltas
    evals = glyphs * (avar_regions + hvar_regions) * axes  # region-scalar axis evaluations per state change
    return dict(K=K, nfonts=nfonts, hidden_per=hidden_per, regions_per_font=avar_regions + hvar_regions, raw_MB_per_font=raw / 1e6,
                raw_GB_12_layers=raw * nfonts * 12 / 1e9, region_list_MB=region_list / 1e6,
                hvar_delta_MB=hvar_deltas / 1e6,
                axis_evals_per_layer_G=evals * nfonts / 1e9,
                secs_per_layer=(evals * nfonts * ns_per_eval[0] / 1e9, evals * nfonts * ns_per_eval[1] / 1e9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4A/fused_results.json")
    ap.add_argument("--ks", default="8,12,16,24,32,48,64,96")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    tensors = g.SafeTensors(g.MODEL_PATH)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    weights = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    qweights = np.rint(weights / g.WEIGHT_SCALE) * g.WEIGHT_SCALE
    chrome = json.load(open("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2H/run-combined3/verification-vectors.json"))
    chrome_final = np.asarray(chrome["finalResidual"], dtype=np.float64)
    from browser_gpt2_core import reference_sequence
    qref = reference_sequence(TOKENS, 12, kv_window=8, kv_sinks=0)
    fref = reference_sequence(TOKENS, 12, quantized=False, kv_window=8, kv_sinks=0)
    qref_out = np.asarray(qref["outputs"])
    fref_out = np.asarray(fref["outputs"])
    float_ids = g.head_ids(fref["outputs"], tensors, gamma, beta, qweights, weights, rounded=False)
    print(f"float ids {float_ids} expected {EXPECTED} ({time.time()-t0:.0f}s)", flush=True)
    calib = calibrate(tensors, g.Cfg())
    print("calibration: per-layer max|n2| = " + " ".join(f"{m.max():.2f}" for m in calib["n2"]))
    print("calibration: per-layer max|z|  = " + " ".join(f"{m.max():.2f}" for m in calib["z"]))
    results = {"expected": EXPECTED, "float_ids": float_ids, "runs": [], "cost": []}
    TODAY = dict(axis14=True, adv64=True, sig6=True, width32=True)

    def run(name, cfg, fu):
        t = time.time()
        rows, caches = forward_fused(tensors, cfg, fu, calib)
        ids, margins = g.head_ids(rows, tensors, gamma, beta, qweights, weights, margins=True)
        rq, mq = g.err(rows[-1], qref_out[-1])
        rf, mf = g.err(rows[-1], fref_out[-1])
        rc, _ = g.err(rows[-1], chrome_final)
        rec = dict(name=name, ids=ids, ids_ok=ids == EXPECTED, float_agree=ids == float_ids,
                   rmse_vs_qref=rq, max_vs_qref=mq, rmse_vs_fref=rf, max_vs_fref=mf, rmse_vs_chrome=rc,
                   margins=margins, min_margin=min(margins), secs=time.time() - t,
                   stats=(fu.stats if fu else None))
        results["runs"].append(rec)
        extra = ""
        if fu:
            cf = max(s["clipped_frac"] for s in fu.stats)
            extra = f" clip={cf:.4f} coefmax={max(s['coef_max'] for s in fu.stats):.2f} s_o_min={min(s['s_o_min'] for s in fu.stats):.1f}"
        print(f"{name:78s} ids={rec['ids_ok']!s:5s} float={rec['float_agree']!s:5s} rmse_q={rq:.4f} "
              f"rmse_f={rf:.4f} max_f={mf:.3f} minmargin={min(margins):.0f}{extra} ids={ids}", flush=True)
        return rec

    run("ideal (gate_sim weights-only qref path)", g.Cfg(), None)
    run("TODAY (R3P model, own fc/proj path)", g.Cfg(**TODAY), None)
    ks = [int(k) for k in args.ks.split(",")]
    # --- isolate the fused error terms (exact GELU) ---
    run("fused: float, exact GELU, dyn scales, no font terms (bound)", g.Cfg(**TODAY), Fused(exact_gelu=True, units=False, coef14=False, coord14=False, delta16=False, dyn_scale=True))
    for nf in (4, 12):
        tag = f"{nf}x{3072//nf}"
        run(f"fused {tag}: exact GELU, fixed 2x pd scales, no font quantisation", g.Cfg(**TODAY), Fused(exact_gelu=True, units=False, coef14=False, coord14=False, delta16=False, nfonts=nf))
        run(f"fused {tag}: exact GELU + coef14 only", g.Cfg(**TODAY), Fused(exact_gelu=True, units=False, coord14=False, delta16=False, nfonts=nf))
        run(f"fused {tag}: exact GELU + coord14 only", g.Cfg(**TODAY), Fused(exact_gelu=True, units=False, coef14=False, delta16=False, nfonts=nf))
        run(f"fused {tag}: exact GELU + units(int) only", g.Cfg(**TODAY), Fused(exact_gelu=True, coef14=False, coord14=False, delta16=False, nfonts=nf))
        run(f"fused {tag}: exact GELU + all font terms (F1-F3,F6)", g.Cfg(**TODAY), Fused(exact_gelu=True, nfonts=nf))
    if args.quick:
        ks = [16, 32]
    for nf in (4, 12):
        tag = f"{nf}x{3072//nf}"
        for K in ks:
            run(f"fused {tag} K={K} curv all terms (single glyph/font)", g.Cfg(**TODAY), Fused(K=K, nfonts=nf))
    for K in ks:
        run(f"fused 12x256 K={K} curv, GELU-only (no font quantisation, 2x pd scales)", g.Cfg(**TODAY), Fused(K=K, units=False, coef14=False, coord14=False, delta16=False, nfonts=12))
        run(f"fused 12x256 K={K} curv all terms, TWO-LEVEL glyph (coarse+fine/64)", g.Cfg(**TODAY), Fused(K=K, nfonts=12, fine=True))
    run("fused 12x256 exact GELU, all terms, TWO-LEVEL", g.Cfg(**TODAY), Fused(exact_gelu=True, nfonts=12, fine=True))
    if not args.quick:
        for K in (32, 64):
            run(f"fused 12x256 K={K} uniform[-6,6] TWO-LEVEL", g.Cfg(**TODAY), Fused(K=K, knots="uniform", nfonts=12, fine=True))
        for K in (32, 64):
            run(f"fused 12x256 K={K} curv TWO-LEVEL, margins 4x", g.Cfg(**TODAY), Fused(K=K, in_margin=4.0, z_margin=4.0, nfonts=12, fine=True))
            run(f"fused 12x256 K={K} curv TWO-LEVEL, margins 1.05x (no headroom)", g.Cfg(**TODAY), Fused(K=K, in_margin=1.05, z_margin=1.05, nfonts=12, fine=True))
            run(f"fused 12x256 K={K} curv TWO-LEVEL, global-per-layer in-scale 2x", g.Cfg(**TODAY), Fused(K=K, per_dim=False, nfonts=12, fine=True))
            run(f"fused 12x256 K={K} curv TWO-LEVEL, zc=8", g.Cfg(**TODAY), Fused(K=K, zc=8.0, nfonts=12, fine=True))
    for nf in (4, 12):
        for K in ks:
            results["cost"].append(cost_model(K, nfonts=nf, hidden_per=3072 // nf))
    print("\nasset / compute model per fused font (769 axes, 768 glyphs; nfonts/layer x hidden/font):")
    for c in results["cost"]:
        print(f"  {c['nfonts']:2d}x{c['hidden_per']:3d} K={c['K']:3d}: regions/font {c['regions_per_font']:6d}  raw {c['raw_MB_per_font']:7.1f} MB/font "
              f"(region list {c['region_list_MB']:.1f} + HVAR deltas {c['hvar_delta_MB']:.1f}), 12 layers {c['raw_GB_12_layers']:.2f} GB; "
              f"axis-evals {c['axis_evals_per_layer_G']:.1f} G/layer -> {c['secs_per_layer'][0]:.0f}-{c['secs_per_layer'][1]:.0f} s/layer at 0.5-1.5 ns")
    json.dump(results, open(args.out, "w"), indent=1, default=float)
    print(f"done {time.time()-t0:.0f}s -> {args.out}")


if __name__ == "__main__":
    main()
