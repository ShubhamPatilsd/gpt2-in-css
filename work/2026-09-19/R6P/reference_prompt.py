"""R6P: NumPy q9/q16 reference for a TEXT prompt on the capacity-32 runtime: the prompt's N GPT-2 BPE ids are teacher-forced into
positions 1..N (exactly what the typed-prompt bundle does: epochs 1..N read the prompt ids instead of the fed-back argmax), then the
remaining positions N+1..32 are free-running greedy (feed back the q16 argmax). Same reference path as R4C/reference_ids_32.py and
R4P (browser_gpt2_core.reference_sequence quantized=True + q16 head), memoised like R4P/screen_prompts.py. Output JSON:
promptText, promptTokens, winners (32 = the head argmax at every epoch 1..32; winners[0..N-2] are the discarded predictions made
while the prompt was being prefilled, winners[N-1..31] are the 33-N generated ids), generatedIds, teacherForcedCheck (one pass over
the full 32-input sequence must reproduce winners), floatWinners (float weights + float head, for the fragility note).
usage: PYTHONPATH=<tools> reference_prompt.py "<prompt text>" <out.json> [capacity=32] [blocks=12]"""
import json, sys, time
import numpy as np
import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors, ROOT
import browser_gpt2_core as core
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, SCORE_GAIN, WEIGHT_SCALE, R
from build_pretrained_gpt2 import Gpt2Tokenizer
t0 = time.time()
def log(m): print(f"[{time.strftime('%H:%M:%S')} +{time.time()-t0:5.0f}s] {m}", flush=True)
text, out_path = sys.argv[1], sys.argv[2]; cap = int(sys.argv[3]) if len(sys.argv) > 3 else 32; BLOCKS = int(sys.argv[4]) if len(sys.argv) > 4 else 12
T = SafeTensors(MODEL_PATH); core.SafeTensors = lambda path: T
_lm, _cache = core.layer_matrices, {}
def _layer_matrices(tensors, layer):
    if layer not in _cache: _cache[layer] = _lm(tensors, layer)
    return _cache[layer]
core.layer_matrices = _layer_matrices
tok = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
gamma = np.asarray(T.tensor("ln_f.weight"), dtype=np.float64); beta = np.asarray(T.tensor("ln_f.bias"), dtype=np.float64)
wte = np.asarray(T.tensor("wte.weight"), dtype=np.float64); q = np.rint(wte / WEIGHT_SCALE) * WEIGHT_SCALE
def head_q16(outputs):
    hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs]); hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    return np.rint(hidden @ q.T * SCORE_GAIN * 256).argmax(1).tolist()
def head_float(outputs):
    return (np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in outputs]) @ wte.T).argmax(1).tolist()
prompt = tok.encode(text); N = len(prompt); assert 1 <= N <= cap
log(f"prompt {text!r} -> {prompt} ({N} tokens); capacity {cap}: positions 1..{N} teacher-forced, {N+1}..{cap} free-running ({cap-N+1} generated)")
def run(quantized, head):
    seq = list(prompt); winners = []
    r = core.reference_sequence(seq, BLOCKS, quantized=quantized, kv_window=None, kv_sinks=0)
    winners = head(r["outputs"])            # predictions at positions 1..N (the last one is the first generated token)
    seq.append(winners[-1])
    for p in range(N + 1, cap + 1):
        r = core.reference_sequence(seq, BLOCKS, quantized=quantized, kv_window=None, kv_sinks=0)
        w = head([r["outputs"][-1]])[0]; winners.append(w); seq.append(w)
        if quantized: log(f"epoch {p}: winner {w} {tok.decode_token(w)!r}")
    return winners, seq[:cap]
winners, inputs = run(True, head_q16)
check = head_q16(core.reference_sequence(inputs, BLOCKS, quantized=True, kv_window=None, kv_sinks=0)["outputs"])
fwin, _ = run(False, head_float)
gen = winners[N - 1:]
res = dict(freeRunningReference=winners, promptText=text, promptTokens=prompt, promptTokenCount=N, capacity=cap, inputs=inputs, winners=winners, generatedIds=gen,
           generatedText="".join(tok.decode_token(t) for t in gen), fullText=text + "".join(tok.decode_token(t) for t in gen),
           discardedPrefillWinners=winners[: N - 1], teacherForcedCheck=check, teacherForcedEqualsWinners=check == winners,
           floatWinners=fwin, quantizedEqualsFloat=fwin == winners,
           firstQuantizedFloatMismatch=next((i for i, (a, c) in enumerate(zip(winners, fwin)) if a != c), None),
           note="winners[e-1] = q9/q16 head argmax at epoch e (input = prompt id for e<=N, fed-back winners[e-2] for e>N); the browser's --saved-token-e / --feedback-e must equal winners[e-1] for all 32 epochs",
           blocks=BLOCKS, tools=sys.path[0], seconds=round(time.time() - t0))
json.dump(res, open(out_path, "w"), indent=1)
log(f"winners {winners}\nteacher-forced check == winners: {check == winners}; quantized == float: {fwin == winners} (first mismatch {res['firstQuantizedFloatMismatch']})\ntext: {res['fullText']!r}\nwrote {out_path}")
