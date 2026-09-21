"""R4M: verify_browser_gpt2_runtime on a run whose KV V-half was not captured by the harness (R4D_UNPACK_V: the bank stores 12 per-head lists
--fc-v-S-H; F4's correctness_run.mjs read the packed --fc-v-S, which is empty -> null values -> verify crashed in error()).
1. verification-vectors.json: null -> NaN (kept as verification-vectors.raw.json), so error() reports finite=768/1536 (rmse None) instead of raising;
2. run the unchanged tools/verify_browser_gpt2_runtime.py (tokens, final residual, head, float agreement, text);
3. additionally compute the K-half cache errors (the captured 768 values per (layer, slot)) vs the same NumPy reference and append them to numerical-results.json.
usage: PYTHONPATH=tools python verify_wrapper.py <run-dir>"""
import json, math, subprocess, sys, pathlib
import numpy as np
run = pathlib.Path(sys.argv[1]).resolve()
vec = run / "verification-vectors.json"; raw = run / "verification-vectors.raw.json"
if not raw.exists(): raw.write_bytes(vec.read_bytes())
d = json.loads(raw.read_text())
missing = 0
for c in d["caches"]:
    vals = c["values"]; missing += sum(1 for v in vals if v is None)
    c["values"] = [float("nan") if v is None else v for v in vals]
vec.write_text(json.dumps(d).replace("NaN", "NaN"))  # json dumps NaN as NaN (allow_nan default), which json.loads accepts
print(f"caches: {len(d['caches'])} entries, {missing} null values replaced by NaN (expected 768 x entries = {768*len(d['caches'])} when only the V half is missing)")
rc = subprocess.call([sys.executable, str(pathlib.Path(__file__).parent / "tools/verify_browser_gpt2_runtime.py"), str(run)])
print(f"verify rc={rc}")
# K-half cache errors
from browser_gpt2_core import reference_sequence
man = json.loads((run / "manifest.json").read_text())
outputs = [int(t) for t in d["tokens"]]; prompt = d.get("prompt", 15496)
ref = reference_sequence([prompt] + outputs[:-1], man["blocks"], kv_window=man.get("kvWindow"), kv_sinks=man.get("kvSinks", 0))
rows = []
for c in d["caches"]:
    k = np.asarray(c["values"][:768], dtype=float); exp = np.asarray(ref["layers"][c["layer"]]["qkv"][c["position"]][768:1536], dtype=float)
    fin = int(np.isfinite(k).sum())
    if fin == 768:
        diff = k - exp; rows.append({"layer": c["layer"], "slot": c["slot"], "finite": fin, "rmse": float(np.sqrt((diff**2).mean())), "maximum": float(np.abs(diff).max())})
    else:
        rows.append({"layer": c["layer"], "slot": c["slot"], "finite": fin, "rmse": None, "maximum": None})
ok = [r for r in rows if r["rmse"] is not None]
summary = {"entries": len(rows), "kHalfComplete": len(ok), "kRmseMax": max(r["rmse"] for r in ok) if ok else None, "kAbsMax": max(r["maximum"] for r in ok) if ok else None,
           "vHalf": "not captured (R4D_UNPACK_V per-head lists --fc-v-S-H; harness read the packed --fc-v-S)"}
nr = run / "numerical-results.json"
if nr.exists():
    j = json.loads(nr.read_text()); j["cacheErrorsKHalf"] = rows; j["cacheErrorsKHalfSummary"] = summary; nr.write_text(json.dumps(j, indent=2))
print("K-half cache summary:", summary)
sys.exit(rc)
