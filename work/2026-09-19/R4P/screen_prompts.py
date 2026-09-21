"""R4P: screen single-token prompts through the SAME q9/q16 reference path as R4C/reference_ids_32.py
(browser_gpt2_core.reference_sequence with quantized weights + q16 head), free-running 32 tokens, plus the
float (unquantized weights, float head) greedy for comparison. NumPy only. Run with PYTHONPATH=../R3M/tools.
Only difference from R4C's script: SafeTensors/layer_matrices are memoized (pure functions of the checkpoint),
so the 33 sequential passes per prompt do not reload/re-quantize the checkpoint each time. Numerics unchanged
(checked by reproducing R4C's 15496 ids exactly; see the 15496 row)."""
import json, sys, time, functools
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors, ROOT
import browser_gpt2_core as core
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
from build_pretrained_gpt2 import Gpt2Tokenizer

t0 = time.time()
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')} +{time.time()-t0:5.0f}s] {msg}", flush=True)

T = SafeTensors(MODEL_PATH)
core.SafeTensors = lambda path: T                 # memoize checkpoint load (same object, same numbers)
_orig_layer_matrices = core.layer_matrices
_lm_cache = {}
def _layer_matrices(tensors, layer):
    if layer not in _lm_cache:
        _lm_cache[layer] = _orig_layer_matrices(tensors, layer)
    return _lm_cache[layer]
core.layer_matrices = _layer_matrices
reference_sequence = core.reference_sequence

tok = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
wte = np.asarray(T.tensor("wte.weight"), dtype=np.float64)
q = np.rint(wte / WEIGHT_SCALE) * WEIGHT_SCALE

def head_ids_q16(outputs):                        # identical to R4C/reference_ids_32.py
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs])
    hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    return np.rint(hidden @ q.T * SCORE_GAIN * 256).argmax(1).tolist()

def head_ids_float(outputs):
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs])
    return (hidden @ wte.T).argmax(1).tolist()

def free_run(prompt, n, quantized):
    seq = [prompt]; out = []
    head = head_ids_q16 if quantized else head_ids_float
    for _ in range(n):
        ref = reference_sequence(seq, 12, quantized=quantized, kv_window=None, kv_sinks=0)
        nid = head([ref["outputs"][-1]])[0]
        out.append(nid); seq.append(nid)
    return out

def teacher_forced(prompt, ids):
    ref = reference_sequence([prompt] + ids[:-1], 12, quantized=True, kv_window=None, kv_sinks=0)
    return head_ids_q16(ref["outputs"])

def longest_repeated_ngram(ids):
    best = 0
    for n in range(1, len(ids)):
        seen = set(); found = False
        for i in range(len(ids) - n + 1):
            g = tuple(ids[i:i + n])
            if g in seen: found = True; break
            seen.add(g)
        if found: best = n
        else: break
    return best

def decode(ids):
    return "".join(tok.decode_token(i) for i in ids)

words = ["Hello", "The", "Once", "In", "It", "When", "Scientists", "Today", "My", "I", "A", "There", "After",
         "Yesterday", "Breaking", "Dear", "Why", "This", "What", "She", "He", "We", "If", "Researchers", "London",
         "Chapter", "Water", "Every", "One", "Long"]
candidates = []                                   # (id, surface text)
for w in words:
    for variant in (w, " " + w):
        enc = tok.encode(variant)
        if len(enc) == 1 and enc[0] not in [c[0] for c in candidates]:
            candidates.append((enc[0], variant))
        elif len(enc) != 1:
            log(f"skip {variant!r}: encodes to {len(enc)} tokens {enc}")
log(f"{len(candidates)} single-token candidates: {candidates}")

N = 32
results = []
for pid, surface in candidates:
    t1 = time.time()
    qids = free_run(pid, N, True)
    tf = teacher_forced(pid, qids)
    fids = free_run(pid, N, False)
    mism = next((i for i, (a, c) in enumerate(zip(qids, fids)) if a != c), None)
    row = dict(id=pid, text=surface, quantized=qids, teacherForced=tf, teacherForcedEqualsFree=(tf == qids),
               float=fids, quantizedEqualsFloat=(qids == fids), firstQuantFloatMismatch=mism,
               distinct=len(set(qids)), longestRepeat=longest_repeated_ngram(qids),
               eosAt=(qids.index(50256) if 50256 in qids else None),
               decodedQuantized=decode(qids), decodedFloat=decode(fids))
    results.append(row)
    log(f"id={pid} {surface!r}: distinct={row['distinct']} longestRepeat={row['longestRepeat']} q==f={row['quantizedEqualsFloat']} (first mismatch {mism}) tf==free={tf==qids} {time.time()-t1:.0f}s\n    Q: {surface}{row['decodedQuantized']!r}\n    F: {surface}{row['decodedFloat']!r}")
    json.dump(results, open("screen_results.json", "w"), indent=1)
log("done")
