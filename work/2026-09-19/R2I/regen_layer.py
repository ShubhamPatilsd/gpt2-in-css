#!/usr/bin/env python3
"""Regenerate the 36 rowbase fonts (18 .ttf + 18 .woff2) for one flat-chain layer into OUTDIR.

Mirrors tools/build_view_timeline_two_block_probe.py: build_font_group(name, codes,
row_specific_bases=True) for attn-composed / fc / mlp-proj of GPT-2 block LAYER.
The fonts depend only on the block's weights (quantised q9 per row), never on the input vector.
Usage: PYTHONPATH=tools python regen_layer.py LAYER OUTDIR
"""
import os, sys, time
from pathlib import Path
layer = int(sys.argv[1]); outdir = Path(sys.argv[2]).resolve()
outdir.mkdir(parents=True, exist_ok=True)
os.environ["GPT2_BLOCK_CSS_OUT"] = str(outdir)   # OUT is read at import time
import fontTools, brotli, numpy as np
from build_gpt2_block_css import QUANT_BITS, build_font_group, model_data
from build_signed_hvar_chain import quantize_float_rows
print(f"layer={layer} out={outdir} fontTools={fontTools.version} brotli={getattr(brotli,'__version__','?')} numpy={np.__version__} python={sys.version.split()[0]} QUANT_BITS={QUANT_BITS}", flush=True)
t0 = time.time()
data = model_data(layer)
composed_weight = data["attn_proj_weight"] @ data["v_weight"]
groups = [
    (f"b{layer}-attn-composed-rowbase", quantize_float_rows(composed_weight, bits=QUANT_BITS).codes),
    (f"b{layer}-fc-rowbase", quantize_float_rows(data["fc_weight"], bits=QUANT_BITS).codes),
    (f"b{layer}-mlp-proj-rowbase", quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS).codes),
]
for name, codes in groups:
    g = build_font_group(name, codes, rebuild=True, row_specific_bases=True)
    print(f"  built {name}: shards={len(g.names)} tags={g.tags} ({time.time()-t0:.0f}s)", flush=True)
print(f"done layer {layer} in {time.time()-t0:.0f}s", flush=True)
