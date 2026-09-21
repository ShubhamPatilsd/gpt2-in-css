"""R4W: NumPy free-running reference ids for prompt 40 with the R4W tools copy (= R4C/reference_ids_32.py part 2),
compared with R4P/reference_ids_32_40.json. The tools copy differs from R4D/tools only in the CSS emitter, so this is a
by-construction check that the model/reference path is untouched."""
import json, sys, time
import numpy as np
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4W/tools")
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import reference_sequence
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
t = time.time()
T = SafeTensors(MODEL_PATH)
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
q = np.rint(np.asarray(T.tensor("wte.weight"), dtype=np.float64) / WEIGHT_SCALE) * WEIGHT_SCALE
def head_ids(outputs):
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs])
    hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    return np.rint(hidden @ q.T * SCORE_GAIN * 256).argmax(1).tolist()
ref = json.load(open("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4P/reference_ids_32_40.json"))
prompt = ref["promptToken"]; seq = [prompt]; out = []
for p in range(32):
    r = reference_sequence(seq, 12, kv_window=None, kv_sinks=0)
    nid = head_ids([r["outputs"][-1]])[0]; out.append(nid); seq.append(nid)
print(f"prompt {prompt}: free-running ids (R4W tools) = {out}; == R4P freeRunningReference: {out == ref['freeRunningReference']}; == teacherForced: {out == ref['teacherForcedReference']}; first mismatch: {next((i for i,(a,c) in enumerate(zip(out, ref['freeRunningReference'])) if a!=c), None)}; {time.time()-t:.0f}s")
