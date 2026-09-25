"""NumPy reference ids for the demo prompt (15496) with teacher inputs = the expected outputs, q9/q16 head as verify_browser_gpt2_runtime does."""
import time, numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import reference_sequence
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
t = time.time()
expected = [11, 314, 1101, 7926, 11, 475, 314, 1101]
tokens = [15496] + expected[:-1]
ref = reference_sequence(tokens, 12, kv_window=8, kv_sinks=0)
T = SafeTensors(MODEL_PATH)
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
q = np.rint(np.asarray(T.tensor("wte.weight"), dtype=np.float64) / WEIGHT_SCALE) * WEIGHT_SCALE
hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in ref["outputs"]])
hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
ids = np.rint(hidden @ q.T * SCORE_GAIN * 256).argmax(1).tolist()
print(f"reference q9/q16 ids for prompt 15496 + teacher inputs {tokens[1:]} -> {ids} expected {expected}: {ids == expected} {time.time()-t:.0f}s")
