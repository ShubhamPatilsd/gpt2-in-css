"""R4P: per-step top1-top2 margin of the q16 head (integer score units, same rounding as R4C head) along the
free-running quantized sequence, for chosen prompts. Small margins = steps that could flip under browser arithmetic."""
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
rows = {r["id"]: r for r in json.load(open("screen_results.json"))}
out = {}
for arg in sys.argv[1:]:
    r = rows[int(arg)]; seq = [r["id"]] + r["quantized"][:-1]
    ref = core.reference_sequence(seq, 12, kv_window=None, kv_sinks=0)
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in ref["outputs"]])
    hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    scores = np.rint(hidden @ q.T * SCORE_GAIN * 256)
    top2 = np.sort(scores, axis=1)[:, -2:]
    margins = (top2[:, 1] - top2[:, 0]).astype(int).tolist()
    assert scores.argmax(1).tolist() == r["quantized"]
    out[r["id"]] = margins
    print(f"id={r['id']} {r['text']!r}: min margin {min(margins)} at step {margins.index(min(margins))}; margins={margins}", flush=True)
json.dump(out, open("margins.json", "w"), indent=1)
