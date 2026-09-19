"""NumPy reference ids for the pinned prompt (same recipe as tools/verify_browser_gpt2_runtime.py)."""
import json, sys, time
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import reference_sequence
from build_gpt2_groupwise_production_q16_sixfont import WEIGHT_SCALE, R, AXIS_STEPS, SCORE_GAIN
t0 = time.time()
expected = [11, 314, 1101, 7926, 11, 475, 314, 1101]
tokens = [15496] + expected[:-1]
ref = reference_sequence(tokens, 12, kv_window=8, kv_sinks=0)
tensors = SafeTensors(MODEL_PATH)
gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
weights = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
qweights = np.rint(weights / WEIGHT_SCALE) * WEIGHT_SCALE
hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in ref["outputs"]])
hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
ids = np.rint(hidden @ qweights.T * SCORE_GAIN * 256).argmax(1).tolist()
print(f"reference q9/q16 ids for prompt 15496 + teacher inputs {tokens[1:]} -> {ids} expected {expected}: {ids == expected} {time.time()-t0:.0f}s")
