"""R4V: what does bundles/combined4-c32c actually instantiate per generation step, for two prompt
trajectories (15496 "Hello" loop vs 40 "I")?  Offline NumPy, using browser_gpt2_core.reference_sequence
(R4D/tools) exactly as R4C/reference_ids_32.py does, and the emitter's own formulas
(R4D/tools/browser_gpt2_font_vector_cache.py):

  K list  (per slot S, packed 768 axes) : "K{H}{i}" var(--fvn-k-H-i),  --fvn-k-H-i = qkv_k[H,i] / --fvs-live-ks-H,
                                          --fvs-live-ks-H = max(.000001, max_i |qkv_k[H,i]|)             (:250-272)
  V list  (per slot S, head H, 64 axes)  : same with v / --fvs-live-vs-H                                  (R4D_UNPACK_V)
  query   (per head H)                    : "Q{i}" qkv_q[H,i] / --fqs-H,  --fqs-H = max(.000001, max_i |q|) (:233-248)
  score glyph instance (L,t,H,S)          : font-variation-settings: var(--fr-k-S), var(--fvs-query-H)      (:380)
  V leaf instance, widths layout (L,S,H)  : font-variation-settings: var(--fr-v-S-H), "P000" 1              (:498, :514)
  V leaf instance, runs layout   (L,S,H)  : var(--fr-v-S-H), "P000" var(--fw-H-S)                           (:487)
  --fw-H-S = --fe-H-S * --fr-vs-S-H / --fb-H,  --fe = exp(fs - max fs), --fb = max(.000001, vs_S over filled)  (:420-431, :470)
  V leaf width (widths)                   : calc-size(max-content, base + (size - base) * --fw-H-S)          (:500)
                                            size - base = coefficient * V_i * P * (VALUE_SIZE/UPEM) px = 12000*1.024*V_i px
  score width                             : 262144px + (size - base) * fqs * ks * 128/(8*coef*unit)            (:381)
                                            size - base = 468 * (sum_i Qn_i Kn_i) * 0.512 px

Number serialization: Blink serializes computed <number>s substituted into a '*' list with 6 significant
digits (project observation: R4D/tools/browser_gpt2_core.py:145-149) -> '%.6g'.  LayoutUnit = 1/64 px.
The reference uses the emitter's q9 weights but float64 activations; the page's --qkv values are LayoutUnit
readbacks (grid 1/8192).  For DISTINCT-STRING counting this only matters for exact collisions, which are
reported separately at coarser grids (4, 3 significant digits) to bound the effect.
"""
import json, os, sys, time
from collections import Counter
from pathlib import Path

import numpy as np

W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
sys.path.insert(0, str(W / "R4D/tools"))
from browser_gpt2_core import reference_sequence  # noqa: E402

BUSY = W / "CPU-BUSY-R4V"
HEADS, DIM, L = 12, 64, 12
UPEM = 1000
VALUE_SIZE, QK_SIZE = 1024, 512
ops = json.load(open(W / "../../experiments/browser-gpt2/font-vector-operators-v2/operators.json"))
V_BASE_PX = ops["value"]["base"] * VALUE_SIZE / UPEM       # 12320.768
V_COEF_PX = ops["value"]["coefficient"] * VALUE_SIZE / UPEM  # 12288
D_BASE_PX = ops["dot"]["base"] * QK_SIZE / UPEM             # 15351.808
D_COEF_PX = ops["dot"]["coefficient"] * QK_SIZE / UPEM       # 239.616
SCORE_K = 128 / (8 * ops["dot"]["coefficient"] * QK_SIZE / UPEM)
LU = 64.0  # LayoutUnit per px


def snap(px):
    return np.floor(np.asarray(px) * LU) / LU  # LayoutUnit(float) truncates toward zero; widths are positive


def fmt(x, sig=6):
    return f"{x:.{sig}g}"


def lists(arr, sig):
    """arr[..., 64] -> array of joined strings along last axis."""
    flat = arr.reshape(-1, arr.shape[-1])
    out = [",".join(fmt(v, sig) for v in row) for row in flat]
    return np.array(out, dtype=object).reshape(arr.shape[:-1])


def analyse(name, prompt, ids, sigs=(6, 4, 3)):
    tokens = [prompt] + ids[:31]  # 32 positions; step k (1..32) attends over slots 0..k-1, writes slot k-1
    T = len(tokens)
    t0 = time.time()
    ref = reference_sequence(tokens, L, kv_window=None, kv_sinks=0)
    print(f"[{name}] reference {time.time()-t0:.1f}s", flush=True)
    qkv = np.array([layer["qkv"] for layer in ref["layers"]])  # (L, T, 2304)
    q, k, v = np.split(qkv, 3, axis=2)
    q = q.reshape(L, T, HEADS, DIM); k = k.reshape(L, T, HEADS, DIM); v = v.reshape(L, T, HEADS, DIM)
    ks = np.maximum(1e-6, np.abs(k).max(-1))  # (L,T,H)
    vs = np.maximum(1e-6, np.abs(v).max(-1))
    qs = np.maximum(1e-6, np.abs(q).max(-1))
    Kn, Vn, Qn = k / ks[..., None], v / vs[..., None], q / qs[..., None]

    # exact model quantities per (L, t=query pos, H, S<=t)
    scores = np.einsum("lthd,lshd->lths", q, k) / 8  # (L,T,H,T)
    mask = np.tril(np.ones((T, T), bool))  # [t, s]
    scores_m = np.where(mask[None, :, None, :], scores, -np.inf)
    e = np.exp(scores_m - scores_m.max(-1, keepdims=True))  # --fe (0 for masked)
    fd = e.sum(-1)  # --fd
    p = e / fd[..., None]  # softmax prob
    # --fb-H = max over filled S of vs[L,S,H]; filled = S<=t
    vs_ts = np.where(mask[None, :, None, :], vs.transpose(0, 2, 1)[:, None, :, :], 0)  # (L,T,H,S)
    fb = vs_ts.max(-1)  # (L,T,H)
    fw = e * vs_ts / fb[..., None]  # --fw-H-S  (L,T,H,S)
    # leaf widths (widths layout): base + coef * Vn[L,S,H,i] * fw[L,t,H,S]   -> (L,T,H,S,i)
    Vn_s = Vn.transpose(0, 2, 1, 3)  # (L,H,S,i)
    leaf_delta = V_COEF_PX * Vn_s[:, None, :, :, :] * fw[..., None]  # (L,T,H,S,i)
    leaf_w = snap(V_BASE_PX + leaf_delta)
    # score widths
    dot = np.einsum("lthd,lshd->lths", Qn, Kn)  # sum Qn_i Kn_i
    score_w = snap(262144 + D_COEF_PX * dot * qs[..., None] * ks.transpose(0, 2, 1)[:, None, :, :] * SCORE_K)

    res = {"name": name, "prompt": prompt, "ids": ids, "steps": []}
    seen = {sig: {"K": set(), "V": set(), "Q": set(), "score": set(), "vleaf_runs": set()} for sig in sigs}
    Kstr = {sig: lists(Kn.reshape(L, T, HEADS * DIM), sig) for sig in sigs}  # packed 768-axis K list per (L,S)
    Vstr = {sig: lists(Vn, sig) for sig in sigs}  # (L,S,H)
    Qstr = {sig: lists(Qn, sig) for sig in sigs}  # (L,t,H)
    prev_leaf = None  # snapped leaf widths of the previous pass (layer 11 of previous token)
    prev_score = None
    for kstep in range(1, T + 1):
        t = kstep - 1
        S = np.arange(kstep)
        row = {"k": kstep, "id": tokens[t], "filled": kstep, "repeat_token_in_ctx": tokens[t] in tokens[:t]}
        row["distinct_ids_in_ctx"] = len(set(tokens[: t + 1]))
        for sig in sigs:
            # (c) KV cache lists written this step: K packed (12 layers), V per head (12*12)
            newK = [Kstr[sig][l, t] for l in range(L)]
            newV = [Vstr[sig][l, t, h] for l in range(L) for h in range(HEADS)]
            newQ = [Qstr[sig][l, t, h] for l in range(L) for h in range(HEADS)]
            # (a) score instances this step: K_S list + query, for S<=t, all layers/heads
            sc = [Kstr[sig][l, s] + "|" + Qstr[sig][l, t, h] for l in range(L) for h in range(HEADS) for s in S]
            # (b) V leaf instances: widths layout -> V list + "P000 1": the set live this step
            vw = [Vstr[sig][l, s, h] for l in range(L) for h in range(HEADS) for s in S]
            # runs layout -> V list + P000 fw (fw serialized 6 sig)
            vr = [Vstr[sig][l, s, h] + "|" + fmt(fw[l, t, h, s], sig) for l in range(L) for h in range(HEADS) for s in S]
            d = {}
            d["K_new"], d["K_repeat"] = len(set(newK) - seen[sig]["K"]), sum(1 for x in newK if x in seen[sig]["K"])
            d["V_new"], d["V_repeat"] = len(set(newV) - seen[sig]["V"]), sum(1 for x in newV if x in seen[sig]["V"])
            d["Q_new"], d["Q_repeat"] = len(set(newQ) - seen[sig]["Q"]), sum(1 for x in newQ if x in seen[sig]["Q"])
            d["score_instances"] = len(sc); d["score_distinct"] = len(set(sc))
            d["score_repeat_from_earlier_steps"] = sum(1 for x in sc if x in seen[sig]["score"])
            d["vleaf_widths_instances"] = len(vw); d["vleaf_widths_distinct"] = len(set(vw))
            d["vleaf_widths_new_this_step"] = len(set(vw) - set(Vstr[sig][l, s, h] for l in range(L) for h in range(HEADS) for s in S[:-1]))
            d["vleaf_runs_instances"] = len(vr); d["vleaf_runs_distinct"] = len(set(vr))
            d["vleaf_runs_repeat_from_earlier_steps"] = sum(1 for x in vr if x in seen[sig]["vleaf_runs"])
            seen[sig]["K"].update(newK); seen[sig]["V"].update(newV); seen[sig]["Q"].update(newQ)
            seen[sig]["score"].update(sc); seen[sig]["vleaf_runs"].update(vr)
            row[f"sig{sig}"] = d
        # attention weight statistics over (L,H) for this query position
        P = p[:, t, :, :kstep]  # (L,H,S)
        FW = fw[:, t, :, :kstep]
        ent = -(P * np.log(np.where(P > 0, P, 1))).sum(-1)  # nats
        row["attn_entropy_mean_nats"] = float(ent.mean())
        row["attn_effective_slots_mean"] = float(np.exp(ent).mean())
        row["attn_pmax_mean"] = float(P.max(-1).mean())
        for thr in (1e-2, 1e-3, 1e-4, 1e-6):
            row[f"fw_ge_{thr:g}"] = int((FW >= thr).sum())  # count over (L,H,S) of 144*k
        # leaves (L,H,S,i) whose snapped width != base (the weight moves the glyph by >= 1 LayoutUnit)
        LW = leaf_w[:, t, :, :kstep, :]  # (L,H,S,i)
        row["leaves_filled"] = int(LW.size)
        row["leaves_width_ne_base"] = int((LW != snap(V_BASE_PX)).sum())
        # leaves whose snapped width changed vs the previous pass of the same leaf (layer l-1 same token; layer 0 vs
        # layer 11 of the previous token (previous token had one fewer filled slot: the new slot's leaf was display:none))
        changed = 0
        for l in range(L):
            cur = LW[l]
            if l == 0:
                if prev_leaf is None:
                    changed += cur.size
                else:
                    changed += int((cur[:, :-1, :] != prev_leaf[:, :, :]).sum()) + cur[:, -1, :].size
            else:
                changed += int((cur != LW[l - 1]).sum())
        row["leaves_width_changed_per_token"] = changed
        prev_leaf = LW[L - 1]
        SW = score_w[:, t, :, :kstep]  # (L,H,S)
        row["score_glyphs_filled"] = int(SW.size)
        ch = 0
        for l in range(L):
            if l == 0:
                ch += SW[l].size if prev_score is None else int((SW[l][:, :-1] != prev_score).sum()) + SW[l][:, -1].size
            else:
                ch += int((SW[l] != SW[l - 1]).sum())
        row["score_width_changed_per_token"] = ch
        prev_score = SW[L - 1]
        # exact repeats of the fw VALUE for the same (L,H,S) between consecutive layers (would make the leaf style equal)
        same_fw = 0
        for l in range(1, L):
            same_fw += int((FW[l] == FW[l - 1]).sum())
        row["fw_identical_consecutive_layers"] = same_fw
        row["fw_exactly_one"] = int((FW == 1.0).sum())
        res["steps"].append(row)
        print(f"[{name}] k={kstep:2d} id={tokens[t]:6d} rep={row['repeat_token_in_ctx']!s:5} "
              f"score new={row['sig6']['score_instances']-row['sig6']['score_repeat_from_earlier_steps']}/{row['sig6']['score_instances']} "
              f"Vwidths distinct={row['sig6']['vleaf_widths_distinct']}/{row['sig6']['vleaf_widths_instances']} "
              f"Vruns rep={row['sig6']['vleaf_runs_repeat_from_earlier_steps']} K rep={row['sig6']['K_repeat']} V rep={row['sig6']['V_repeat']} "
              f"H={row['attn_entropy_mean_nats']:.2f} eff={row['attn_effective_slots_mean']:.2f} fw>=1e-4: {row['fw_ge_0.0001']}/{144*kstep} "
              f"leaf!=base {row['leaves_width_ne_base']}/{row['leaves_filled']} leafchg {row['leaves_width_changed_per_token']} "
              f"scorechg {row['score_width_changed_per_token']}/{12*row['score_glyphs_filled']}", flush=True)
    # KV list cross-position collisions at any layer (the prompt's 'identical K lists impossible' check)
    for sig in sigs:
        cK = Counter(Kstr[sig].reshape(-1)); cV = Counter(Vstr[sig].reshape(-1))
        res[f"sig{sig}_K_lists_total_distinct"] = [int(Kstr[sig].size), len(cK)]
        res[f"sig{sig}_V_lists_total_distinct"] = [int(Vstr[sig].size), len(cV)]
    # nearest-neighbour distance between K lists of repeated tokens (how far from colliding)
    reps = [(a, b) for b in range(T) for a in range(b) if tokens[a] == tokens[b]]
    if reps:
        dmin = min(float(np.abs(Kn[:, a] - Kn[:, b]).max()) for a, b in reps)
        dmed = float(np.median([np.abs(Kn[:, a] - Kn[:, b]).max() for a, b in reps]))
        res["repeated_token_pairs"] = len(reps)
        res["repeated_token_Kn_maxabs_diff_min_median"] = [dmin, dmed]
    return res


def main():
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    hello = json.load(open(W / "R4C/reference_ids_32.json"))["savedCodex32"]
    p40 = json.load(open(W / "R4P/reference_ids_32_40.json"))["freeRunningReference"]
    BUSY.touch()
    try:
        out = {"hello": analyse("hello", 15496, hello), "p40": analyse("p40", 40, p40)}
    finally:
        BUSY.unlink(missing_ok=True)
    json.dump(out, open(W / "R4V/trajectory_counts.json", "w"), indent=1)
    print("wrote R4V/trajectory_counts.json")


if __name__ == "__main__":
    main()
