"""R5C numeric check (NumPy, no browser): per layer, over the 8-token demo run,
(a) today's dynamic range max|ctx|*1.001 vs the new bound (max_h max_slot ||v_{slot,h}||_inf + 2e-4)*1.001 on the softmax element,
(b) the attention-output error implied by the F2Dot14 axis quantisation (ctx/range in 1/16384 steps) under both ranges,
(c) today's 6-significant-digit timeline transport error of ctx (4.6e-3 per value) propagated through W_o, for comparison,
(d) the sum-scroller widths S_i = sum of the 3 shard glyph advances vs the stage viewport V (progress window)."""
import math, sys, time
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import layer_matrices, attention_positions, W
t0 = time.time()
expected = [11, 314, 1101, 7926, 11, 475, 314, 1101]
tokens = [15496] + expected[:-1]
T = SafeTensors(MODEL_PATH)
rows = np.asarray(T.tensor("wte.weight")[tokens], dtype=np.float64) + np.asarray(T.tensor("wpe.weight")[: len(tokens)], dtype=np.float64)
print("layer | max|ctx| (today range/1.001) | bound (new range/1.001) | ratio | rms out err F2Dot14 today | new | rms out err today's 6-digit ctx transport | S/V min..max")
worst = 0
for layer in range(12):
    data, matrices, biases = layer_matrices(T, layer)
    weights = [m.reconstructed for m in matrices]
    n = np.stack([b.layer_norm(x, data["ln1_gamma"], data["ln1_beta"]) for x in rows])
    qkv = n @ weights[0].T + biases[0]
    q, k, v = np.split(qkv, 3, axis=1)
    ctx, todays, bounds = [], [], []
    for t in range(len(tokens)):
        ret = attention_positions(t, None, 0)
        s = np.einsum("hd,thd->ht", q[t].reshape(12, 64), k[ret].reshape(-1, 12, 64)) / 8
        e = np.exp(s - s.max(1, keepdims=True))
        c = np.einsum("ht,thd->hd", e / e.sum(1, keepdims=True), v[ret].reshape(-1, 12, 64)).reshape(W)
        ctx.append(c)
        todays.append(np.abs(c).max())
        vs = np.abs(v[ret].reshape(-1, 12, 64)).max(2)  # (slots, heads) stored V scales
        bounds.append(vs.max() + 2e-4)
        assert np.abs(c).max() <= vs.max() + 1e-12
    ctx = np.asarray(ctx)
    Wo = weights[1]
    rown = np.sqrt((Wo ** 2).sum(1))  # ||W_o[i,:]||_2
    q_today = np.mean(todays) / 16384 / math.sqrt(12) * rown  # per-output rms from uniform axis rounding
    q_new = np.mean(bounds) / 16384 / math.sqrt(12) * rown
    tl = 4.6e-3 / math.sqrt(3) * rown  # today's ctx transport (uniform-ish +-4.6e-3) through W_o
    # (d) sum widths: shard glyph advances = base + sum codes*axis*coef; emulate with the quantised codes
    m = matrices[1]
    codes = m.codes.astype(np.float64)  # (768 out, 768 in)
    bases_rows = [np.sum(np.abs(codes[:, s * 256:(s + 1) * 256]), axis=1) + 32 for s in range(3)]
    V = 2 ** math.ceil(math.log2(max(1024, max(np.sum(np.stack(bases_rows), axis=0)) * b.FONT_SIZE / b.UNITS_PER_EM * 1.5)))
    rng = np.asarray(bounds) * 1.001
    S = []
    for t in range(len(tokens)):
        axis = ctx[t] / rng[t]
        adv = sum(bases_rows[s] + codes[:, s * 256:(s + 1) * 256] @ axis[s * 256:(s + 1) * 256] for s in range(3))
        S.append(adv * b.FONT_SIZE / b.UNITS_PER_EM)
    S = np.asarray(S)
    worst = max(worst, np.mean(bounds) / np.mean(todays))
    print(f"{layer:5d} | {np.mean(todays):8.3f} (max {max(todays):7.3f}) | {np.mean(bounds):8.3f} (max {max(bounds):7.3f}) | {np.mean(bounds)/np.mean(todays):5.2f} | {math.sqrt(np.mean(q_today**2)):.2e} | {math.sqrt(np.mean(q_new**2)):.2e} | {math.sqrt(np.mean(tl**2)):.2e} | V={V} S/V {S.min()/V:.3f}..{S.max()/V:.3f} (S min {S.min():.0f} px)")
    residual = rows + ctx @ Wo.T + biases[1]
    n2 = np.stack([b.layer_norm(x, data["ln2_gamma"], data["ln2_beta"]) for x in residual])
    h = n2 @ weights[2].T + biases[2]
    rows = residual + b.gelu_new(h) @ weights[3].T + biases[3]
print(f"worst mean bound/today ratio {worst:.2f}; {time.time()-t0:.0f}s")
