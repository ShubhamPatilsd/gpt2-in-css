"""R3L offline numerics: the loop-bank latch quantisation. Replays browser_gpt2_core.reference_sequence (quantized
weights, kv_window 8) for the demo prompt with a hook on the residual that leaves each layer through the loop bank
(layers 0..10 -> next layer; layer 11 -> head, also latched), comparing
  exact          : no carrier quantisation (what verify/reference_ids compute)
  carrier-today  : v -> float32(262144 + 128 v) -> LayoutUnit trunc 1/64 px -> (w - 262144) / 128
  packed-p2      : q = clamp(round((v + 2048) * 8192)) -> w = q / 64 px -> float32 -> LayoutUnit -> (w - 262144) / 128
  packed-p3      : q = clamp(round((v + 2048) * 16))   -> w = q * 8 px  (fixture cost-model variant only)
Reports the value range at the write point, per-layer max |delta| vs exact / vs carrier-today, and the q9/q16 ids.
"""
import sys, time
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import W, attention_positions, layer_matrices
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R

EXPECTED = [11, 314, 1101, 7926, 11, 475, 314, 1101]
TOKENS = [15496] + EXPECTED[:-1]


def f32(x):
    return np.asarray(x, dtype=np.float32).astype(np.float64)


def lu(px):
    return np.trunc(px * 64) / 64


def sig6(v):
    # var() substitutes a registered <number> as text with 6 significant digits (R3L fixture)
    v = np.asarray(v, dtype=np.float64)
    with np.errstate(divide="ignore"):
        e = np.where(v == 0, 0, np.floor(np.log10(np.abs(np.where(v == 0, 1, v)))))
    scale = 10.0 ** (5 - e)
    return np.rint(v * scale) / scale


def carrier_today(v):
    return (lu(f32(262144 + 128 * sig6(v))) - 262144) / 128


def font_carrier(v):
    s = (sig6(v) + 2048) * 2
    khi = np.clip(np.floor(s), 0, 16383)
    klo = np.clip(np.floor((s - khi) * 4096), 0, 4095)
    return (64 * khi + klo / 64 - 262144) / 128


def packed(v, scale, maxq, unit):
    q = np.clip(np.rint((v + 2048) * scale), 0, maxq)
    return (lu(f32(q * unit)) - 262144) / 128


HOOKS = {
    "exact": lambda v: v,
    "carrier-today": carrier_today,
    "packed-p2": lambda v: packed(v, 8192, 67108863, 1 / 64),
    "packed-p3": lambda v: packed(v, 16, 131071, 8),
    "font-2glyph": font_carrier,
}


def forward(hook, tensors, blocks=12, kv_window=8):
    tokens = TOKENS
    inputs = np.asarray(tensors.tensor("wte.weight")[tokens], dtype=np.float64) + np.asarray(tensors.tensor("wpe.weight")[: len(tokens)], dtype=np.float64)
    rows = inputs.copy()
    outs = []
    for layer in range(blocks):
        data, matrices, biases = layer_matrices(tensors, layer)
        weights = [m.reconstructed for m in matrices]
        n = np.stack([b.layer_norm(x, data["ln1_gamma"], data["ln1_beta"]) for x in rows])
        qkv = n @ weights[0].T + biases[0]
        q, k, v = np.split(qkv, 3, axis=1)
        ctx = []
        for t in range(len(tokens)):
            retained = attention_positions(t, kv_window, 0)
            scores = np.einsum("hd,thd->ht", q[t].reshape(12, 64), k[retained].reshape(-1, 12, 64)) / 8
            e = np.exp(scores - scores.max(1, keepdims=True))
            ctx.append(np.einsum("ht,thd->hd", e / e.sum(1, keepdims=True), v[retained].reshape(-1, 12, 64)).reshape(W))
        residual = rows + np.asarray(ctx) @ weights[1].T + biases[1]
        n2 = np.stack([b.layer_norm(x, data["ln2_gamma"], data["ln2_beta"]) for x in residual])
        hidden = b.gelu_new(n2 @ weights[2].T + biases[2])
        rows = residual + hidden @ weights[3].T + biases[3]
        outs.append(rows.copy())          # value at the write point (before the carrier)
        rows = hook(rows)                 # what the next layer / head reads back
    return outs, rows


def ids(final, tensors):
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    qw = np.rint(np.asarray(tensors.tensor("wte.weight"), dtype=np.float64) / WEIGHT_SCALE) * WEIGHT_SCALE
    hidden = np.stack([b.layer_norm(x, gamma, beta) for x in final])
    hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    return np.rint(hidden @ qw.T * SCORE_GAIN * 256).argmax(1).tolist()


if __name__ == "__main__":
    t0 = time.time()
    T = SafeTensors(MODEL_PATH)
    results = {}
    for name, hook in HOOKS.items():
        outs, final = forward(hook, T)
        results[name] = (outs, final, ids(final, T))
        print(f"{name:14s} ids {results[name][2]} {'OK' if results[name][2] == EXPECTED else 'MISMATCH'} ({time.time() - t0:.0f}s)", flush=True)
    ex = results["exact"][0]
    allv = np.concatenate([o.ravel() for o in ex])
    print(f"write-point value range over 12 layers x 8 tokens x 768: min {allv.min():.3f} max {allv.max():.3f}; "
          f"|v|>2000: {(np.abs(allv) > 2000).sum()}, |v|>1000: {(np.abs(allv) > 1000).sum()}, |v|>100: {(np.abs(allv) > 100).sum()} of {allv.size}")
    print("per-layer min/max of the exact write-point values:", [(f"{o.min():.0f}", f"{o.max():.0f}") for o in ex])
    for name in ("carrier-today", "packed-p2", "packed-p3", "font-2glyph"):
        outs = results[name][0]
        d_exact = [np.abs(a - c).max() for a, c in zip(outs, ex)]
        print(f"{name:14s} per-layer max|Δ write-point value| vs exact (divergence accumulated through the loop): " + " ".join(f"{d:.2e}" for d in d_exact))
        # one-hop quantisation error of the transport itself on the exact values of that layer
        hop = [np.abs(HOOKS[name](o) - o).max() for o in ex]
        print(f"{name:14s} one-hop transport error max|hook(v) - v| per layer: " + " ".join(f"{d:.2e}" for d in hop))
    # packed-p2 vs carrier-today on identical inputs (the exact values): difference of the two transports
    for name in ("packed-p2", "font-2glyph"):
        diff = [np.abs(HOOKS[name](o) - HOOKS["carrier-today"](o)).max() for o in ex]
        frac = [np.mean(HOOKS[name](o) != HOOKS["carrier-today"](o)) for o in ex]
        print(f"{name} vs carrier-today one-hop max|Δ| per layer (identical inputs): " + " ".join(f"{d:.2e}" for d in diff) + f"; fraction differing {np.mean(frac):.3f}")
    ff = results["font-2glyph"][1]
    fin = results["packed-p2"][1]; fe = results["exact"][1]; fc = results["carrier-today"][1]
    print(f"final residual (token 8): rms|packed-p2 - exact| {np.sqrt(((fin - fe) ** 2).mean()):.3e}, rms|carrier-today - exact| {np.sqrt(((fc - fe) ** 2).mean()):.3e}, rms|font-2glyph - exact| {np.sqrt(((ff - fe) ** 2).mean()):.3e}, rms|font-2glyph - carrier-today| {np.sqrt(((ff - fc) ** 2).mean()):.3e}")
