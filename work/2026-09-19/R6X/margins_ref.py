"""R6X: per-position top1-top2 margin of the q16 head (integer score units, R4P/margins.py's arithmetic) along a reference_prompt.py JSON
(teacher-forced inputs = the 32 model inputs; winners = the head argmax at every position). usage: PYTHONPATH=<tools> margins_ref.py <ref.json> [<out.json>]"""
import json, sys
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
import browser_gpt2_core as core
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
T = SafeTensors(MODEL_PATH); core.SafeTensors = lambda p: T
_o = core.layer_matrices; _c = {}
core.layer_matrices = lambda t, l: _c.setdefault(l, _o(t, l))
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
q = np.rint(np.asarray(T.tensor("wte.weight"), dtype=np.float64) / WEIGHT_SCALE) * WEIGHT_SCALE
d = json.load(open(sys.argv[1])); seq = d["inputs"]; want = d["winners"]
ref = core.reference_sequence(seq, 12, kv_window=None, kv_sinks=0)
hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in ref["outputs"]])
hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
scores = np.rint(hidden @ q.T * SCORE_GAIN * 256)
order = np.argsort(scores, axis=1)
top1, top2 = order[:, -1], order[:, -2]
margins = (scores[np.arange(len(seq)), top1] - scores[np.arange(len(seq)), top2]).astype(int).tolist()
assert top1.tolist() == want, "argmax != reference winners"
rows = [{"position": i + 1, "input": seq[i], "winner": int(top1[i]), "runnerUp": int(top2[i]), "margin": margins[i]} for i in range(len(seq))]
print(f"{d['promptText']!r}: min margin {min(margins)} at position {margins.index(min(margins)) + 1}; margins by position: {margins}")
for r in rows: print(r)
if len(sys.argv) > 2: json.dump({"promptText": d["promptText"], "margins": margins, "rows": rows}, open(sys.argv[2], "w"), indent=1)
