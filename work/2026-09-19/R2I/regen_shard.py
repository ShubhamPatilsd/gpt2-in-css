#!/usr/bin/env python3
"""Build ONE rowbase shard: regen_shard.py LAYER GROUP SHARD OUTDIR  (GROUP in attn|fc|proj). Prints sha256[:12] of woff2 and ttf."""
import hashlib, os, sys
from pathlib import Path
layer, group, shard = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]); outdir = Path(sys.argv[4]).resolve(); outdir.mkdir(parents=True, exist_ok=True)
os.environ["GPT2_BLOCK_CSS_OUT"] = str(outdir)
import numpy as np
from build_gpt2_block_css import QUANT_BITS, SHARD, PACK_SHARDS, PACKED_CODEPOINT_BASE, model_data, packed_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend
from build_signed_hvar_chain import quantize_float_rows
data = model_data(layer)
if group == "attn": name, w = f"b{layer}-attn-composed-rowbase", data["attn_proj_weight"] @ data["v_weight"]
elif group == "fc": name, w = f"b{layer}-fc-rowbase", data["fc_weight"]
else: name, w = f"b{layer}-mlp-proj-rowbase", data["mlp_proj_weight"]
codes = quantize_float_rows(w, bits=QUANT_BITS).codes
start = shard * SHARD; stop = min(start + SHARD, codes.shape[1]); sc = codes[:, start:stop]
bases = np.sum(np.abs(sc.astype(np.int64)), axis=1).astype(np.int32) + 32
path = outdir / f"{name}-s{shard}.ttf"
build_direct_font_backend(sc, path, signed_axes=True, base_advance=bases, codepoint_start=PACKED_CODEPOINT_BASE + shard * codes.shape[0], axis_tags=[packed_axis_tag(shard % PACK_SHARDS, local) for local in range(stop - start)])
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()[:12]
print(f"seed={os.environ.get('PYTHONHASHSEED','?')} {path.with_suffix('.woff2').name} woff2={h(path.with_suffix('.woff2'))} ttf={h(path)} codes_sha={hashlib.sha256(sc.tobytes()).hexdigest()[:12]}", flush=True)
