#!/usr/bin/env python3
"""R7B: NumPy q9/q16 reference for the demo-c36 runtime (prefill head skip + stop rule + Gumbel sampling).

A run is (prompt text, seed s in 1..64 or 0 = greedy, temperature T). N = BPE ids of the prompt (teacher-forced into positions
1..N exactly as the typed-prompt bundle prefills them); epochs 1..N-1 are prefill epochs whose head is skipped (expected slot
value -1); epoch e >= N produces NEW token t = e-N+1 with noise column col = mod(s + e - N, 64) + 1 and scores
rint(raw_q + n[col]*T_r) (R7S verifier; T_r = round(T/2*16384)/16384*2 is the F2DOT14-realised temperature; T = 0 -> rint(raw_q)
= today's greedy head). Sampled ids are fed back (teacher-forced path). The run stops at epoch N-1+new_tokens.
Output JSON keys: freeRunningReference (= expectedSlots: per-epoch expected --saved-token-e, -1 on skipped prefill epochs),
winners (same, but the greedy discarded prediction on prefill epochs, for information), generatedIds, columns, fullText...
usage: PYTHONPATH=<tools> reference_r7b.py "<prompt>" <out.json> [new_tokens=32] [seed=0] [T=0] [blocks=12] [--no-float]"""
import json, sys, time
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors, ROOT
import browser_gpt2_core as core
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
from build_pretrained_gpt2 import Gpt2Tokenizer
from pathlib import Path

t0 = time.time()
def log(m): print(f"[{time.strftime('%H:%M:%S')} +{time.time()-t0:5.0f}s] {m}", flush=True)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
text, out_path = args[0], args[1]
NEW = int(args[2]) if len(args) > 2 else 32
SEED = int(args[3]) if len(args) > 3 else 0
TEMP = float(args[4]) if len(args) > 4 else 0.0
BLOCKS = int(args[5]) if len(args) > 5 else 12
DO_FLOAT = "--no-float" not in sys.argv and TEMP == 0
T_REAL = round(TEMP / 2 * 16384) / 16384 * 2
NOISE = Path(__file__).resolve().parent / "assets-r7b" / "noise-table.npz"
n_table = np.load(NOISE)["n_q"].astype(np.float64) if TEMP > 0 else None  # [64, 50257]
if TEMP > 0 and not 1 <= SEED <= 64:
    raise SystemExit("seed must be 1..64 when T > 0")

T = SafeTensors(MODEL_PATH); core.SafeTensors = lambda path: T
_lm, _cache = core.layer_matrices, {}
def _layer_matrices(tensors, layer):
    if layer not in _cache: _cache[layer] = _lm(tensors, layer)
    return _cache[layer]
core.layer_matrices = _layer_matrices
tok = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
wte = np.asarray(T.tensor("wte.weight"), dtype=np.float64); q = np.rint(wte / WEIGHT_SCALE) * WEIGHT_SCALE
Q = SCORE_GAIN * 256

def raw_q(outputs):
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs]); hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    return hidden @ q.T * Q  # unrounded q units
def greedy(outputs): return np.rint(raw_q(outputs)).argmax(1).tolist()
def head_float(outputs): return (np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs]) @ wte.T).argmax(1).tolist()
def column(e, n): return (SEED + e - n) % 64 + 1
def sampled(output, e, n):
    raw = raw_q([output])[0]
    if TEMP == 0:
        sc = np.rint(raw)
    else:
        sc = np.rint(raw + n_table[column(e, n) - 1] * T_REAL)
    w = int(sc.argmax()); s2 = np.sort(sc)[::-1]
    return w, float(s2[0] - s2[1]), int(np.rint(raw).argmax())

prompt = tok.encode(text); N = len(prompt); CAP = N - 1 + NEW
log(f"prompt {text!r} -> {prompt} ({N} tokens); seed {SEED} T {TEMP} (realised {T_REAL}); {NEW} new tokens -> {CAP} epochs; prefill epochs 1..{N-1} skipped")
seq = list(prompt)
r = core.reference_sequence(seq, BLOCKS, quantized=True, kv_window=None, kv_sinks=0)
discarded = greedy(r["outputs"][: N - 1]) if N > 1 else []     # what the head WOULD have predicted on prefill epochs (skipped in the demo)
expected = [-1] * (N - 1)
winners = list(discarded)
gen, cols, margins, greedy_at = [], [], [], []
w, m, g = sampled(r["outputs"][-1], N, N); expected.append(w); winners.append(w); gen.append(w); cols.append(column(N, N)); margins.append(m); greedy_at.append(g)
seq.append(w)
log(f"epoch {N}: new token 1 col {cols[-1]} -> {w} {tok.decode_token(w)!r} (margin {m:.0f} q, greedy would be {g})")
for e in range(N + 1, CAP + 1):
    r = core.reference_sequence(seq, BLOCKS, quantized=True, kv_window=None, kv_sinks=0)
    w, m, g = sampled(r["outputs"][-1], e, N); expected.append(w); winners.append(w); gen.append(w); cols.append(column(e, N)); margins.append(m); greedy_at.append(g)
    seq.append(w)
    log(f"epoch {e}: new token {e-N+1} col {cols[-1]} -> {w} {tok.decode_token(w)!r} (margin {m:.0f} q, greedy would be {g})")
inputs = seq[:CAP]
# teacher-forced check: one pass over the full input sequence reproduces every winner (prefill epochs: the greedy discarded ones)
r = core.reference_sequence(inputs, BLOCKS, quantized=True, kv_window=None, kv_sinks=0)
check = []
for e in range(1, CAP + 1):
    if e < N: check.append(greedy([r["outputs"][e - 1]])[0])
    else: check.append(sampled(r["outputs"][e - 1], e, N)[0])
fwin = None
if DO_FLOAT:
    seqf = list(prompt); fwin = []
    rf = core.reference_sequence(seqf, BLOCKS, quantized=False, kv_window=None, kv_sinks=0)
    fw = head_float(rf["outputs"]); fwin = fw[: N - 1] + [fw[-1]]; seqf.append(fw[-1])
    for e in range(N + 1, CAP + 1):
        rf = core.reference_sequence(seqf, BLOCKS, quantized=False, kv_window=None, kv_sinks=0); w = head_float([rf["outputs"][-1]])[0]; fwin.append(w); seqf.append(w)
res = dict(freeRunningReference=expected, expectedSlots=expected, winners=winners, promptText=text, promptTokens=prompt, promptTokenCount=N,
           newTokens=NEW, stopEpoch=CAP, capacity=CAP, seed=SEED, temperature=TEMP, temperatureRealized=T_REAL, columns=cols, marginsQ=margins,
           greedyWinnerAtStep=greedy_at, sampledDiffersFromGreedy=sum(1 for a, c in zip(gen, greedy_at) if a != c),
           inputs=inputs, generatedIds=gen, generatedText="".join(tok.decode_token(t) for t in gen), fullText=text + "".join(tok.decode_token(t) for t in gen),
           discardedPrefillWinners=discarded, teacherForcedCheck=check, teacherForcedEqualsWinners=check == winners,
           floatWinners=fwin, quantizedEqualsFloat=(fwin == winners) if fwin is not None else None,
           firstQuantizedFloatMismatch=next((i for i, (a, c) in enumerate(zip(winners, fwin)) if a != c), None) if fwin is not None else None,
           noiseTable=str(NOISE), rule="col = mod(seed + epoch - N, 64) + 1 (N = max(promptCount,1)); scores = rint(raw_q + n[col]*T_realized); first-index argmax; prefill epochs 1..N-1 skipped (slot -1)",
           note="freeRunningReference[e-1] = expected --saved-token-e: -1 for e < N (head skipped), else the (sampled) winner; the run stops at stopEpoch",
           blocks=BLOCKS, tools=sys.path[0], seconds=round(time.time() - t0))
json.dump(res, open(out_path, "w"), indent=1)
log(f"expected {expected}\nteacher-forced check == winners: {check == winners}; quantized == float: {res['quantizedEqualsFloat']}; sampled != greedy at {res['sampledDiffersFromGreedy']}/{NEW} steps\ntext: {res['fullText']!r}\nwrote {out_path}")
