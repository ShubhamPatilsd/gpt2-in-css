"""R4C: NumPy q9/q16 reference ids for prompt 15496 + 32 generated tokens (= R3M/reference_ids.py at 32),
teacher inputs = Codex's saved 32-token ids (experiments/browser-gpt2/demo-font-vector-context32/numerical-results.json).
Compares the free-running reference (feed back our own argmax) with the saved ids as well."""
import json, sys, time
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import reference_sequence
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
t = time.time()
saved = json.load(open("/Users/shubhampatil/Documents/programming/gpt2-css/experiments/browser-gpt2/demo-font-vector-context32/numerical-results.json"))
codex = saved["tokens"]; assert len(codex) == 32
T = SafeTensors(MODEL_PATH)
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
q = np.rint(np.asarray(T.tensor("wte.weight"), dtype=np.float64) / WEIGHT_SCALE) * WEIGHT_SCALE
def head_ids(outputs):
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs])
    hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    return np.rint(hidden @ q.T * SCORE_GAIN * 256).argmax(1).tolist()
# (1) teacher inputs = saved ids, one pass, kv_window None (= capacity) and 32
tokens = [15496] + codex[:-1]
for kw in (None, 32):
    ref = reference_sequence(tokens, 12, kv_window=kw, kv_sinks=0)
    ids = head_ids(ref["outputs"])
    print(f"kv_window={kw}: teacher-forced reference ids == saved 32: {ids == codex}; ids={ids}; {time.time()-t:.0f}s", flush=True)
# (2) free-running: feed back our own argmax position by position (32 sequential passes)
seq = [15496]; out = []
for p in range(32):
    ref = reference_sequence(seq, 12, kv_window=None, kv_sinks=0)
    nid = head_ids([ref["outputs"][-1]])[0]
    out.append(nid); seq.append(nid)
print(f"free-running reference ids: {out}; == saved: {out == codex}; first mismatch: {next((i for i,(a,c) in enumerate(zip(out,codex)) if a!=c), None)}; {time.time()-t:.0f}s", flush=True)
json.dump({"savedCodex32": codex, "teacherForcedReference": ids, "freeRunningReference": out, "agree": out == codex and ids == codex}, open("reference_ids_32.json", "w"), indent=1)
