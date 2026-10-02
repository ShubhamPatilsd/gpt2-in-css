# bundles/combined2 — F2 + F5 + F4 (`combined`) + F3b chain MLP (Fix 3 / Fix 6 for the fc→proj→out hops), 12 layers, capacity 8

Built by F3b on 2026-09-19 from `work/2026-09-19/combined2/tools` = `cp -R work/2026-09-19/F4/tools` (F2 + F5 + F4, all their
flags default ON, see `bundles/combined/BUILD.md` and `F4.md`) + `f3_chain_mlp.py` + the same two hooks as `bundles/F3a`
(`browser_gpt2_reused_core.py` compile_reused: fc → `f3.mlp_chain`, proj → passthrough; `browser_gpt2_reused_adapter.py`:
inline epoch-reader count 7→5, manifest). With `F3_CHAIN_MLP=1` the F2 `--global-projection` proj retag and the proj-pack
leaves are moot (the proj hop has no packs; the chain uses the original per-shard `mlp-proj-rowbase-s*` fonts), the F2 inline
GELU stays where F2 put it (timeline fc consumers, unused here); the chain decodes with the emitter's `--gelu()` function.

## Exact command (`work/2026-09-19/combined2/compile.sh combined2 12 8`)

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/combined2   # experiments/, data/ -> repo; assets -> ../F4/assets
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F3_CHAIN_MLP=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined2
```

Wall 9 s, peak RSS 2.5 GB, no fonts rebuilt.

## Offline verification

- `work/2026-09-19/F3b/lint_f3b.py bundles/combined2`: LINT OK (79,9k elements, max depth 434 < 512, 36 clean ancestors of
  `.f3-mlp`, 12,300 ordered `anchor-size()` references, 36,864 + 9,216 per-layer decode declarations, no fc/proj receipts/gates).
- `font-witnesses.json`: 283 faces (261 + F4's 24 retagged operator fonts − 2 originals), every face's codepoint/advance/upem equal to
  `bundles/combined`; the only key change is the 12 proj shards: the chain reads the original `experiments/gpt2-block-css/mlp-proj-rowbase-s*`
  / `gpt2-flat-12block-chain/layer*/b*-mlp-proj-rowbase-s*` fonts instead of F2's `global-projection-assets/*-global-v1` retags
  (same HVAR, only fvar tags differ).
- `tools/launch_browser_gpt2.py --check --directory bundles/combined2`: passes, 277,586,397 asset bytes, `runtimeJavaScript:false`.
- vs `bundles/combined`: inline `view-timeline` 10,858 → 7,016; `timeline-scope` 53 → 29; `animation-timeline` 242 → 122;
  `anchor-name` 486 → 12,786; `container-type` 3 → 4 (1,926 fixed size containers); runtime.css 40.8 MB → 30.4 MB; index.html 5.78 → 6.24 MB.
- Reference ids unchanged by construction (same quantised weights, fonts and decode arithmetic): 11,314,1101,7926,11,475,314,1101.

## Browser correctness run

PASS (`work/2026-09-19/F3b/runs/combined2/`, 2026-09-19 under CHROME.lock, headless Chrome 153, passive 5 s poll): ids 11,314,1101,7926,11,475,314,1101 = 8/8 (`verify_browser_gpt2_runtime.py` tokenAgreement all True), finalResidual rmse 1.60e-2; LayoutCount 680 for 8 tokens (85/token). Head-input vector derived offline from the browser residual because the F4 packed head hides `--h*` (see F3b.md §3b). READY created.

## Diff of the tools copy vs `work/2026-09-19/F4/tools` (the F3b delta; `diff -ruN -x __pycache__`)

```diff
diff -ruN -x __pycache__ work/2026-09-19/F4/tools/browser_gpt2_reused_adapter.py work/2026-09-19/combined2/tools/browser_gpt2_reused_adapter.py
--- work/2026-09-19/F4/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:38:03
+++ work/2026-09-19/combined2/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:50:14
@@ -8,6 +8,7 @@
 import re
 
 import build_hybrid_twelve_block as hybrid
+import f3_chain_mlp as f3
 import f4_packing as f4
 import f5_scoping as f5
 from browser_gpt2_reused_core import compile_reused
@@ -148,7 +149,9 @@
         body, tagged_position = f5.tag_inline_readers(
             body, "var(--position)", "pass-reader"
         )
-        if tagged != 7 or tagged_position != 2:
+        # F3: the fc and proj generation markers no longer exist (no timeline hop).
+        expected_epoch_readers = 5 if f3.CHAIN_MLP else 7
+        if tagged != expected_epoch_readers or tagged_position != 2:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -220,6 +223,7 @@
         "f4PackedBanks": f4.PACKED_BANKS and codec == "font-vector",
         "f4PackedHead": f4.PACKED_HEAD,
         "f4NumericLists": f4.NUMERIC_LISTS and codec == "font-vector",
+        **f3.metadata(),
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ruN -x __pycache__ work/2026-09-19/F4/tools/browser_gpt2_reused_core.py work/2026-09-19/combined2/tools/browser_gpt2_reused_core.py
--- work/2026-09-19/F4/tools/browser_gpt2_reused_core.py	2026-09-18 18:20:03
+++ work/2026-09-19/combined2/tools/browser_gpt2_reused_core.py	2026-09-18 19:52:34
@@ -13,6 +13,7 @@
 
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as h
+import f3_chain_mlp as f3
 import f5_scoping as f5
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
@@ -104,6 +105,11 @@
 ):
     if global_projection and isolate_metrics:
         raise ValueError("Do not combine global projection and metric isolation ablations")
+    if f3.CHAIN_MLP:
+        # F3: the proj hop no longer has packs or a global axis list; both
+        # ablations only shaped the timeline proj matvec and are moot here.
+        isolate_metrics = False
+        global_projection = False
     geometry_cache = codec == "geometry"
     font_vector_cache = codec == "font-vector"
     custom_cache = geometry_cache or font_vector_cache
@@ -132,6 +138,11 @@
         for kind in h.STAGES:
             if kind == "mix":
                 continue
+            if f3.CHAIN_MLP and kind == "proj":
+                # F3: the fc hop's anchor chains already host the proj shard
+                # columns and the out chain; nothing separate to nest here.
+                layouts[kind] = "{child}"
+                continue
             if kind in ("ln1", "ln2"):
                 n = 1 if kind == "ln1" else 2
                 html, rule = h.wrapper(
@@ -147,6 +158,15 @@
                         )
                     ),
                 )
+            elif f3.CHAIN_MLP and kind == "fc":
+                # F3 (Fix 3 + Fix 6 for the MLP hops): fc glyph rows are anchors,
+                # 12 fixed size-container chains gather them into --hidden-*,
+                # per-shard proj glyph columns hang under each chain bottom and
+                # one out chain sums the 12 shard advances into --out-*; no
+                # view-timeline, no generation receipt, no gate for fc/proj.
+                html, rule, once = f3.mlp_chain(layer, matrices[2], biases[2], matrices[3], biases[3])
+                if layer == 0:
+                    css += once
             else:
                 i = ("qkv", "attn", "fc", "proj").index(kind)
                 src, count = (("n1", W), ("ctx", W), ("n2", W), ("hidden", 4 * W))[i]
diff -ruN -x __pycache__ work/2026-09-19/F4/tools/f3_chain_mlp.py work/2026-09-19/combined2/tools/f3_chain_mlp.py
--- work/2026-09-19/F4/tools/f3_chain_mlp.py	1969-12-31 16:00:00
+++ work/2026-09-19/combined2/tools/f3_chain_mlp.py	2026-09-18 19:55:28
@@ -0,0 +1,242 @@
+"""F3b (2026-09-19): frameless fc -> proj -> out transport for the reused core.
+
+Fix 3 (work/2026-09-19/F3.md): every view-timeline readback costs one frame, one
+extra style pass and one layout per boundary, and re-restyles the downstream
+chain.  A geometry -> number hop through `anchor-size()` on a `position:fixed`
+size container and container-query units on its child resolves inside ONE
+style/layout lifecycle.  This module emits the MLP (fc 768->3072, GELU,
+proj 3072->768, +r) of one layer in that form; the HTML is layer-independent
+(one reused graph), the per-layer constants live in `@container runtime
+style(--layer:L)` rules exactly like the timeline emitter.
+
+Layout of one layer (data-flow order = tree order, F3.md §3b ordering rule):
+
+  .f3-mlp                         common ancestor; --range-fc = max|n2|*1.001
+    .f3-stage.f3-fc (fixed)       3,072 in-flow rows, anchor-name --f3f{i};
+                                  row width = sum of the 3 fc shard glyphs
+                                  (fallback fonts), font-variation-settings = n2
+    12 x fc chains (fixed size containers, one element per level, F3_CHAIN_LEVEL=1)
+      #f3c{j}-{k}                 width/height = anchor-size(--f3f{2k},{2k+1})
+                                  and publishes the PARENT container's two
+                                  values as --hidden-* (GELU decode)
+      #f3r{j} (in-flow bottom)    --range-proj = max|hidden shard j|*1.001,
+                                  anchor #f3m{j} width = range*1024px,
+                                  .f3-stage #f3s{j}: 768 proj glyph rows of
+                                  shard j, anchor-name --f3p{j}_{i}
+    out chain (fixed size containers, 6 range levels + 384 value levels)
+      #f3g{t}                     reads --f3m{2t},{2t+1} -> --f3pr{j}
+      #f3o{k}                     width = sum_j anchor-size(--f3p{j}_{2k}) * --f3pr{j}
+      #f3b (in-flow bottom)       publishes --out-766/767 and hosts {child}
+
+Chromium rules obeyed (F3.md §2/§3b): only `position:fixed` containers (any
+absolute/relative/contained ancestor would become the containing block and hide
+the anchors -> silent zeros); anchors precede their readers in tree order;
+chain depth <= 391 elements (HTML parser nesting cap 512); widths < 2^24 px.
+
+Env flags (default ON):
+  F3_CHAIN_MLP=0     keep the view-timeline matvec() for fc and proj
+  F3_CHAIN_LEVEL=2   fc chains with two elements per level (container + plain
+                     child), the exact Prototype A/B shape; default 1 = the
+                     next container itself publishes its parent's values.
+                     The out chain (768 values = 390 levels) always uses 1.
+"""
+
+import os
+
+import build_gpt2_block_css as b
+import build_hybrid_twelve_block as h
+import numpy as np
+from build_pretrained_gpt2 import css_number as num
+
+W, M = 768, 3072
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+CHAIN_MLP = flag("F3_CHAIN_MLP")
+CHAIN_LEVEL = int(os.environ.get("F3_CHAIN_LEVEL", "1"))
+if CHAIN_LEVEL not in (1, 2):
+    raise ValueError("F3_CHAIN_LEVEL must be 1 or 2")
+
+RANGE_PX = 1024  # --range-proj travels as an anchor of width range*1024px
+SHARDS_PROJ = M // b.SHARD  # 12
+SHARDS_FC = W // b.SHARD  # 3
+FC_CHAIN = b.SHARD // 2  # 128 containers per fc chain (2 values each)
+OUT_CHAIN = W // 2  # 384 containers in the out chain
+RANGE_CHAIN = SHARDS_PROJ // 2  # 6 containers carry the 12 shard ranges
+
+PX_TO_UNITS = f"{b.UNITS_PER_EM} / {b.FONT_SIZE}"
+
+
+def _chain(ids, size, bottom, level):
+    """Nested fixed size containers.
+
+    ids[k]   element id of level k
+    size[k]  (width, height) CSS values for level k (None -> a plain in-flow
+             block: the chain bottom)
+    bottom   html placed inside the last level
+    level    1: level k's element itself publishes level k-1's two values;
+             2: a plain child of k-1 (`#<id>p`) wraps level k and publishes.
+    Returns (html, once_css) with the layer-independent width/height rules;
+    the caller emits the publish declarations (see _publisher).
+    """
+    parts, css, depth = [], [], 0
+    for k, ident in enumerate(ids):
+        if size[k] is not None:
+            css.append(f"#{ident}{{width:{size[k][0]};height:{size[k][1]}}}")
+        if level == 2 and k >= 1:
+            parts.append(f'<div class="f3-p" id="{ident}p">')
+            depth += 1
+        cls = "f3-c" if size[k] is not None else "f3-b"
+        parts.append(f'<div class="{cls}" id="{ident}">')
+        depth += 1
+    parts.append(bottom)
+    parts.append("</div>" * depth)
+    return "".join(parts), "".join(css)
+
+
+def _publisher(ident, level):
+    """Selector of the element publishing the values of the container above `ident`."""
+    return f"#{ident}p" if level == 2 else f"#{ident}"
+
+
+def mlp_chain(layer, qfc, bfc, qproj, bproj):
+    """Return (html, per_layer_css, once_css) for one layer's fc+proj hops.
+
+    html is identical for every layer (checked by compile_reused's layouts
+    identity); per_layer_css is wrapped by specialize() into
+    `@container runtime style(--layer:L)`; once_css must be emitted once.
+    """
+    dfc, gfc = h.font_group(layer, "fc", qfc)
+    dproj, gproj = h.font_group(layer, "proj", qproj)
+    if len(gfc.names) != SHARDS_FC or len(gproj.names) != SHARDS_PROJ:
+        raise ValueError("F3 chain MLP expects 3 fc shards and 12 proj shards")
+    fc_bases = np.sum(np.stack(gfc.row_bases), axis=0)  # (3072,)
+    proj_bases = np.stack(gproj.row_bases)  # (12, 768)
+    n2, hid, outn, r = h.names("n2", W), h.names("hidden", M), h.names("out", W), h.names("r", W)
+    ranges = [f"--f3pr{j}" for j in range(SHARDS_PROJ)]
+    fam_fc, fam_proj = f"b{layer}fc", f"b{layer}proj"
+
+    layer_css = []
+    once = []
+    # --- per-layer font faces (specialize() hoists @font-face out of the layer rule)
+    layer_css.append(b.font_faces(f"b{layer}-fc", gfc).replace('url("', f'url("{dfc.as_uri()}/'))
+    layer_css.append(b.font_faces(f"b{layer}-proj", gproj).replace('url("', f'url("{dproj.as_uri()}/'))
+    layer_css.append(
+        f".f3-fc{{font-family:{','.join(f'{fam_fc}S{s}' for s in range(SHARDS_FC))}}}"
+    )
+    for j in range(SHARDS_PROJ):
+        layer_css.append(f"#f3s{j}{{font-family:{fam_proj}S{j}}}")
+
+    # --- once: registrations, structure, layer-independent settings
+    once.append(h.regs(["--range-fc", "--range-proj"] + ranges))
+    once.append(
+        ".f3-stage{position:fixed;left:0;top:-60000px;visibility:hidden;font-kerning:none;"
+        f"white-space:pre;line-height:1;font-size:{b.FONT_SIZE}px;font-style:normal;font-weight:normal}}"
+        ".f3-row{display:block;height:1px;width:max-content;font-style:normal}"
+        ".f3-c{position:fixed;left:0;top:0;container-type:size}"
+        ".f3-p,.f3-b{display:block;height:1px;width:1px}"
+        ".f3-m{display:block;height:1px}"
+    )
+    once.append(
+        f".f3-mlp{{--range-fc:calc(max(.000001,{','.join(f'abs(var({p}))' for p in n2)}) * 1.001)}}"
+    )
+    fc_settings = b.pack_font_settings(n2, 1, 0).replace(" / 1)", " / var(--range-fc))")
+    once.append(f".f3-fc{{font-variation-settings:{fc_settings}}}")
+
+    # --- fc anchors: one row per hidden unit, 3 shard glyphs (fallback fonts sum their advances)
+    fc_rows = "".join(
+        f'<i class="f3-row" style="anchor-name:--f3f{i}">'
+        + "".join(f"&#x{gfc.codepoint_starts[s] + i:X};" for s in range(SHARDS_FC))
+        + "</i>"
+        for i in range(M)
+    )
+    html = [f'<div class="f3-mlp"><div class="f3-stage f3-fc" id="f3fs">{fc_rows}</div>']
+
+    # --- 12 fc chains, each hosting its proj shard column
+    for j in range(SHARDS_PROJ):
+        ids = [f"f3c{j}-{k}" for k in range(FC_CHAIN)] + [f"f3r{j}"]
+        size = [
+            (f"anchor-size(--f3f{b.SHARD * j + 2 * k} width)", f"anchor-size(--f3f{b.SHARD * j + 2 * k + 1} width)")
+            for k in range(FC_CHAIN)
+        ] + [None]
+        local = hid[b.SHARD * j : b.SHARD * (j + 1)]
+        proj_settings = ",".join(
+            f'"{b.packed_axis_tag(j % b.PACK_SHARDS, l)}" calc(var({local[l]}) / var(--range-proj))'
+            for l in range(b.SHARD)
+        )
+        once.append(
+            f"#f3r{j}{{--range-proj:calc(max(.000001,{','.join(f'abs(var({p}))' for p in local)}) * 1.001)}}"
+            f"#f3m{j}{{width:calc(var(--range-proj) * {RANGE_PX}px)}}"
+            f"#f3s{j}{{font-variation-settings:{proj_settings}}}"
+        )
+        prow = "".join(
+            f'<i class="f3-row" style="anchor-name:--f3p{j}_{i}">&#x{gproj.codepoint_starts[j] + i:X};</i>'
+            for i in range(W)
+        )
+        bottom = (
+            f'<i class="f3-m" id="f3m{j}" style="anchor-name:--f3m{j}"></i>'
+            f'<div class="f3-stage" id="f3s{j}">{prow}</div>'
+        )
+        chain_html, chain_css = _chain(ids, size, bottom, CHAIN_LEVEL)
+        once.append(chain_css)
+        html.append(chain_html)
+        # per-layer GELU decode: level k+1 publishes container k's two values
+        for k in range(FC_CHAIN):
+            decls = []
+            for i, unit in ((b.SHARD * j + 2 * k, "cqw"), (b.SHARD * j + 2 * k + 1, "cqh")):
+                raw = f"(100{unit} / 1px * {PX_TO_UNITS} - {int(fc_bases[i])})"
+                decls.append(
+                    f"{hid[i]}:--gelu(calc({raw} * {num(qfc.scales[i])} * var(--range-fc) + ({num(bfc[i])})))"
+                )
+            layer_css.append(f"{_publisher(ids[k + 1], CHAIN_LEVEL)}{{{';'.join(decls)}}}")
+
+    # --- out chain: 6 range containers, then 384 value containers, bottom hosts {child}
+    ids = [f"f3g{t}" for t in range(RANGE_CHAIN)] + [f"f3o{k}" for k in range(OUT_CHAIN)] + ["f3b"]
+    size = [
+        (f"anchor-size(--f3m{2 * t} width)", f"anchor-size(--f3m{2 * t + 1} width)")
+        for t in range(RANGE_CHAIN)
+    ]
+    for k in range(OUT_CHAIN):
+        wsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
+        hsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k + 1} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
+        size.append((f"calc({wsum})", f"calc({hsum})"))
+    size.append(None)
+    # the out chain must hold 768 values: only one element per level fits the parser cap
+    chain_html, chain_css = _chain(ids, size, "{child}", 1)
+    once.append(chain_css)
+    html.append(chain_html)
+    html.append("</div>")
+    # range publishers are layer-independent
+    for t in range(RANGE_CHAIN):
+        once.append(
+            f"{_publisher(ids[t + 1], 1)}{{{ranges[2 * t]}:calc(100cqw / 1px / {RANGE_PX});"
+            f"{ranges[2 * t + 1]}:calc(100cqh / 1px / {RANGE_PX})}}"
+        )
+    # per-layer output decode (+ residual r)
+    for k in range(OUT_CHAIN):
+        decls = []
+        for i, unit in ((2 * k, "cqw"), (2 * k + 1, "cqh")):
+            bases = " + ".join(f"{int(proj_bases[j][i])} * var({ranges[j]})" for j in range(SHARDS_PROJ))
+            raw = f"(100{unit} / 1px * {PX_TO_UNITS} - ({bases}))"
+            decls.append(f"{outn[i]}:calc(var({r[i]}) + {raw} * {num(qproj.scales[i])} + ({num(bproj[i])}))")
+        layer_css.append(f"{_publisher(ids[RANGE_CHAIN + k + 1], 1)}{{{';'.join(decls)}}}")
+    return "".join(html), "".join(layer_css), "".join(once)
+
+
+def chain_depth():
+    """Elements added below .f3-mlp on the deepest path (for the 512 parser cap check)."""
+    out = 1 + (RANGE_CHAIN + OUT_CHAIN) + 1  # .f3-mlp + containers + #f3b
+    fc = 1 + FC_CHAIN * CHAIN_LEVEL + CHAIN_LEVEL + 2  # .f3-mlp + containers(+publishers) + #f3r + .f3-stage + row
+    return max(out, fc)
+
+
+def metadata():
+    return {
+        "f3ChainMlp": CHAIN_MLP,
+        "f3ChainLevel": CHAIN_LEVEL,
+        "f3ChainContainers": SHARDS_PROJ * FC_CHAIN + RANGE_CHAIN + OUT_CHAIN,
+        "f3ChainAnchors": M + SHARDS_PROJ * W + SHARDS_PROJ,
+    }
```

## Diff of the tools copy vs repo `tools/` (F2 + F5 + F4 + F3b; `diff -ruN -x __pycache__ tools work/2026-09-19/combined2/tools`)

```diff
diff -ruN -x __pycache__ tools/browser_gpt2_font_vector_cache.py work/2026-09-19/combined2/tools/browser_gpt2_font_vector_cache.py
--- tools/browser_gpt2_font_vector_cache.py	2026-09-17 00:53:12
+++ work/2026-09-19/combined2/tools/browser_gpt2_font_vector_cache.py	2026-09-18 19:48:57
@@ -11,6 +11,8 @@
 from pathlib import Path
 
 import build_hybrid_twelve_block as hybrid
+import f4_packing as f4
+import f5_scoping as f5
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -80,6 +82,18 @@
 
 
 def storage_names(capacity):
+    if f4.PACKED_BANKS:
+        # F4: one 768-axis list per vector kind (12 heads on disjoint tags) and
+        # the 24 per-head scales: 26 latched fields per slot instead of 48.
+        names = []
+        for slot in range(capacity):
+            names += [f"--fc-k-{slot}", f"--fc-v-{slot}"]
+            names += [
+                f"--fc-{kind}-{slot}-{head}"
+                for head in range(HEADS)
+                for kind in ("ks", "vs")
+            ]
+        return names
     return [
         f"--fc-{kind}-{slot}-{head}"
         for slot in range(capacity)
@@ -144,6 +158,7 @@
     kv_sinks=0,
     value_layout="runs",
     prewarm_values=False,
+    value_weight_once=True,
 ):
     positions = capacity
     capacity = capacity if kv_window is None else kv_window
@@ -154,24 +169,30 @@
     if prewarm_values and value_layout != "widths":
         raise ValueError("Early value preparation requires fixed font widths")
     operators = fonts()
+    packed = f4.PACKED_BANKS
+    if packed and value_layout != "runs":
+        raise ValueError("F4 packed banks are implemented for the runs value layout only")
     zero = ",".join(f'"K{i:03d}" 0' for i in range(DIM))
     all_fields = storage_names(capacity)
     css = ""
     for alias, inherits in (("fc", "false"), ("fr", "true")):
-        for slot in range(capacity):
-            for head in range(HEADS):
-                for kind in ("k", "v", "ks", "vs"):
-                    vector = kind in ("k", "v")
-                    css += f'@property --{alias}-{kind}-{slot}-{head}{{syntax:"{"*" if vector else "<number>"}";inherits:{inherits};initial-value:{zero if vector else "0"}}}'
+        for name in all_fields:
+            kind = f4.kind_of(name)
+            vector = kind in ("k", "v")
+            initial = (f4.zero_list(kind) if packed else zero) if vector else "0"
+            css += f'@property {name.replace("--fc-", f"--{alias}-")}{{syntax:"{"*" if vector else "<number>"}";inherits:{inherits};initial-value:{initial}}}'
     css += hybrid.regs([f"--fqs-{h}" for h in range(HEADS)] + ["--fvs-write-slot"])
     css += (
         ".fvs-query{container-name:fvscache;--fvs-write-slot:calc(min("
         f"var({write_epoch}) - 1,{kv_sinks} + mod(max(0,var({write_epoch}) - 1 - {kv_sinks}),{capacity - kv_sinks})))}}"
     )
+    literal = f5.BANK_LITERAL_LISTS
     css += (
         ".fvs-query{--fvs-all-fields:"
         + ",".join(all_fields)
-        + "}.fvs-bank{transition-property:var(--fvs-all-fields);transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
+        + "}.fvs-bank{transition-property:"
+        + (",".join(all_fields) if literal else "var(--fvs-all-fields)")
+        + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
     )
     for head in range(HEADS):
         maximum = ",".join(f"abs(var(--qkv-{head * DIM + i:03d}))" for i in range(DIM))
@@ -187,12 +208,35 @@
                 f"abs(var(--qkv-{offset + head * DIM + i:03d}))" for i in range(DIM)
             )
 
-            def settings_for(slot=None, offset=offset, head=head, scale=scale):
-                return ",".join(
-                    f'"{value_axis(slot, i) if slot is not None else f"K{i:03d}"}" calc(var(--qkv-{offset + head * DIM + i:03d}) / var({scale}))'
-                    for i in range(DIM)
+            def entry(i, offset=offset, head=head, scale=scale, kind=kind):
+                quotient = f"calc(var(--qkv-{offset + head * DIM + i:03d}) / var({scale}))"
+                if f4.NUMERIC_LISTS:
+                    # F4: evaluate once as a typed number on this element; the
+                    # list then latches ~15 B per axis instead of a ~45 B calc().
+                    return f"var(--fvn-{kind}-{head}-{i})"
+                return quotient
+
+            if f4.NUMERIC_LISTS:
+                numeric = [f"--fvn-{kind}-{head}-{i}" for i in range(DIM)]
+                css += "".join(
+                    f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}'
+                    for p in numeric
                 )
+                css += ".fvs-query{" + ";".join(
+                    f"{p}:calc(var(--qkv-{offset + head * DIM + i:03d}) / var({scale}))"
+                    for i, p in enumerate(numeric)
+                ) + "}"
 
+            def settings_for(slot=None, offset=offset, head=head, scale=scale, kind=kind):
+                def tag(i):
+                    if slot is not None:
+                        return value_axis(slot, i)
+                    if packed:
+                        return f4.head_axis(kind, head, i)
+                    return f"K{i:03d}"
+
+                return ",".join(f'"{tag(i)}" {entry(i)}' for i in range(DIM))
+
             if kind == "v" and value_layout == "fallback":
                 settings = (
                     "if("
@@ -207,28 +251,58 @@
             css += hybrid.regs([scale])
             css += f".fvs-query{{{scale}:max(.000001,{maximum});--fvs-live-{kind}-{head}:{settings}}}"
     for slot in range(capacity):
-        fields = {
-            f"--fc-{kind}-{slot}-{head}"
-            for head in range(HEADS)
-            for kind in ("k", "v", "ks", "vs")
-        }
+        fields = {name for name in all_fields if f4.slot_of(name) == slot}
         retained = ",".join(name for name in all_fields if name not in fields) or "none"
         css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
         writes = []
-        for head in range(HEADS):
-            for kind in ("k", "v", "ks", "vs"):
+        if packed:
+            # F4: the 12 live head lists concatenate into one latched list per kind.
+            for kind in ("k", "v"):
                 writes.append(
-                    f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
+                    f"--fc-{kind}-{slot}:"
+                    + ",".join(f"var(--fvs-live-{kind}-{head})" for head in range(HEADS))
                 )
+            for head in range(HEADS):
+                for kind in ("ks", "vs"):
+                    writes.append(
+                        f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
+                    )
+        else:
+            for head in range(HEADS):
+                for kind in ("k", "v", "ks", "vs"):
+                    writes.append(
+                        f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
+                    )
+        retained_value = retained if literal else f"var(--fvs-retained-{slot})"
         for layer in range(blocks):
-            css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:var(--fvs-retained-{slot});{';'.join(writes)}}}}}}}"
-    for layer in range(blocks):
-        aliases = ";".join(
-            f"{name.replace('--fc-', '--fr-')}:var({name})" for name in all_fields
-        )
-        css += f"@container runtime style(--layer:{layer}){{.fvs-bank-{layer}{{{aliases}}}}}"
-    for kind, family in (("dot", "FvsDot"), ("value", "FvsValue")):
-        css += f'@font-face{{font-family:{family};src:url("{(FONT_DIR / (kind + ".woff2")).as_uri()}")}}'
+            css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:{retained_value};{';'.join(writes)}}}}}}}"
+    sequential = kv_window is None or (kv_sinks == 0 and capacity == positions)
+    if f5.BANK_FILLED_ALIASES and sequential:
+        # F5: with a full causal window slots fill in order, so while slot S
+        # is being written only slots 0..S hold values; the others equal the
+        # zero initial value that --fr-* already has. Alias only those.
+        for layer in range(blocks):
+            for slot in range(capacity):
+                # names are --fc-{kind}-{slot}-{head}
+                filled = [name for name in all_fields if f4.slot_of(name) <= slot]
+                aliases = ";".join(
+                    f"{name.replace('--fc-', '--fr-')}:var({name})" for name in filled
+                )
+                css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{{aliases}}}}}}}"
+    else:
+        for layer in range(blocks):
+            aliases = ";".join(
+                f"{name.replace('--fc-', '--fr-')}:var({name})" for name in all_fields
+            )
+            css += f"@container runtime style(--layer:{layer}){{.fvs-bank-{layer}{{{aliases}}}}}"
+    if packed:
+        # F4: 12 dot + 12 value fonts, K axes retagged per head (F2's recipe).
+        for head, (dot_path, value_path) in enumerate(f4.packed_operator_fonts(FONT_DIR)):
+            css += f'@font-face{{font-family:FvsDot{head};src:url("{dot_path.as_uri()}")}}'
+            css += f'@font-face{{font-family:FvsValue{head};src:url("{value_path.as_uri()}")}}'
+    else:
+        for kind, family in (("dot", "FvsDot"), ("value", "FvsValue")):
+            css += f'@font-face{{font-family:{family};src:url("{(FONT_DIR / (kind + ".woff2")).as_uri()}")}}'
     if value_layout == "fallback":
         for slot, path in enumerate(fallback_value_fonts(capacity)):
             start = CODEPOINT_BASE + slot * DIM
@@ -248,8 +322,10 @@
             timelines.append(timeline)
             animations.append(name)
             css += f"@keyframes {name}{{from{{{progress}:-2}}to{{{progress}:1}}}}"
+            dot_family = f"FvsDot{head}" if packed else "FvsDot"
+            fr_k = f"--fr-k-{slot}" if packed else f"--fr-k-{slot}-{head}"
             css += (
-                f".{name}{{font:{QK_SIZE}px FvsDot;line-height:1;font-kerning:none;font-variation-settings:var(--fr-k-{slot}-{head}),var(--fvs-query-{head});"
+                f".{name}{{font:{QK_SIZE}px {dot_family};line-height:1;font-kerning:none;font-variation-settings:var({fr_k}),var(--fvs-query-{head});"
                 f"width:calc-size(max-content,calc(262144px + (size - {dot['base'] * unit:.12g}px) * var(--fqs-{head}) * var(--fr-ks-{slot}-{head}) * {128 / (8 * dot['coefficient'] * unit):.12g}))}}"
             )
             metrics.append(
@@ -319,6 +395,21 @@
     css += ".fvs-score-reader{" + ";".join(soft) + "}"
     value = operators["value"]
     value_unit = VALUE_SIZE / UNITS_PER_EM
+    slim_glyphs = value_weight_once and value_layout == "runs"
+    if slim_glyphs:
+        # F2: each (head, slot) softmax weight is one registered number on the
+        # score reader; every V glyph references it instead of re-evaluating
+        # calc(var()*var()/var()). The reader sits inside the banks, so the
+        # inherited --fr-vs alias is visible there. Numerically identical.
+        weight_fields = [
+            f"--fw-{head}-{slot}" for head in range(HEADS) for slot in range(capacity)
+        ]
+        css += hybrid.regs(weight_fields)
+        css += ".fvs-score-reader{" + ";".join(
+            f"--fw-{head}-{slot}:calc(var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
+            for head in range(HEADS)
+            for slot in range(capacity)
+        ) + "}"
     for head in range(HEADS):
         combined_settings = []
         for slot in range(capacity):
@@ -328,7 +419,9 @@
             # maximum scale after native inline width summation. Large neural
             # activations therefore cannot saturate individual glyph advances.
             weight = (
-                f"calc(var({exponent}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
+                f"var(--fw-{head}-{slot})"
+                if slim_glyphs
+                else f"calc(var({exponent}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
             )
             settings = f'"P000" {weight}'
             if value_layout == "fallback":
@@ -344,7 +437,17 @@
                     settings = '"P000" 1'
                     base_pixels = value["base"] * value_unit
                     width_rule = f"width:calc-size(max-content,calc({base_pixels:.12g}px + (size - {base_pixels:.12g}px) * {weight}));min-width:0;"
-                css += f".fvs-v-{head}-{slot}{{font-family:FvsValue;font-size:{VALUE_SIZE}px;font-variation-settings:var(--fr-v-{slot}-{head}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
+                fr_v = f"--fr-v-{slot}" if packed else f"--fr-v-{slot}-{head}"
+                value_family = f"FvsValue{head}" if packed else "FvsValue"
+                if slim_glyphs:
+                    # font-family/size/kerning/white-space inherit from the row
+                    # rule below; flex items are blockified; .metric i already
+                    # sets font-style. Only the per-(head, slot) list remains
+                    # (+ the per-head family when the banks are packed, F4).
+                    family_decl = f"font-family:{value_family};" if packed else ""
+                    css += f".fvs-v-{head}-{slot}{{{family_decl}font-variation-settings:var({fr_v}),{settings};flex:none}}"
+                else:
+                    css += f".fvs-v-{head}-{slot}{{font-family:{value_family};font-size:{VALUE_SIZE}px;font-variation-settings:var({fr_v}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
                 if width_rule:
                     css += f".fvs-v-{head}-{slot}{{{width_rule}}}"
         if value_layout == "fallback":
@@ -390,6 +493,8 @@
     css += (
         ".fvs-value-row{display:block;white-space:pre;font-style:normal;line-height:1}"
         if value_layout == "fallback"
+        else f".fvs-value-row{{display:inline-flex;gap:0;font:{VALUE_SIZE}px {'FvsValue0' if packed else 'FvsValue'};line-height:1;font-kerning:none;white-space:pre}}"
+        if slim_glyphs
         else ".fvs-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}"
     )
     body = (
@@ -415,6 +520,10 @@
             "kvSlots": capacity,
             "kvSinks": kv_sinks,
             "valueLayout": value_layout,
+            "valueWeightOnce": slim_glyphs,
+            "f4PackedBanks": packed,
+            "f4NumericLists": f4.NUMERIC_LISTS,
+            "latchedFieldsPerSlot": len(all_fields) // capacity,
             "prewarmValues": prewarm_values,
             "attentionMask": "full causal"
             if capacity == positions
diff -ruN -x __pycache__ tools/browser_gpt2_projection_layout.py work/2026-09-19/combined2/tools/browser_gpt2_projection_layout.py
--- tools/browser_gpt2_projection_layout.py	2026-09-17 00:18:08
+++ work/2026-09-19/combined2/tools/browser_gpt2_projection_layout.py	2026-09-18 19:48:57
@@ -13,7 +13,8 @@
 from fontTools.ttLib import TTFont
 
 ROOT = Path(__file__).resolve().parents[1]
-ASSETS = ROOT / "experiments/browser-gpt2/global-projection-assets"
+# F2 round: retagged shards are generated next to this tools copy.
+ASSETS = Path(__file__).resolve().parents[1] / "global-projection-assets"
 
 
 def global_projection_fonts(directory, group):
diff -ruN -x __pycache__ tools/browser_gpt2_reused_adapter.py work/2026-09-19/combined2/tools/browser_gpt2_reused_adapter.py
--- tools/browser_gpt2_reused_adapter.py	2026-09-17 00:17:23
+++ work/2026-09-19/combined2/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:50:14
@@ -8,6 +8,9 @@
 import re
 
 import build_hybrid_twelve_block as hybrid
+import f3_chain_mlp as f3
+import f4_packing as f4
+import f5_scoping as f5
 from browser_gpt2_reused_core import compile_reused
 
 
@@ -21,6 +24,7 @@
     isolate_metrics=False,
     value_layout="runs",
     global_projection=False,
+    value_weight_once=True,
 ):
     body, css = compile_reused(
         blocks,
@@ -33,6 +37,7 @@
         isolate_metrics=isolate_metrics,
         value_layout=value_layout,
         global_projection=global_projection,
+        value_weight_once=value_weight_once,
     )
     # The enclosing token controller owns root --epoch. Only matrix generation
     # receipts use the finer-grained pass counter, scoped to the shared core.
@@ -109,8 +114,50 @@
         css,
     )
     css += hybrid.regs(["--native-pass"])
-    for step in range(1, blocks * capacity + 1):
-        css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
+    if f5.SCOPED_HANDSHAKE:
+        # F5: the pass counter and the layer handshake flags are read by a
+        # handful of elements but, inherited, restyled the whole open core
+        # (P2 Table 3: ~12.27k-element passes). Register them non-inherited
+        # and stamp the current pass directly onto every reader.
+        receipts = [
+            f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
+        ] + [".cache-bridge-receipt", ".fvs-score-receipt"]
+        pass_readers = ",".join(
+            [
+                ".loop-input",
+                ".loop-bank-0",
+                ".loop-bank-1",
+                ".reused-input",
+                ".fvs-query",
+                ".fvs-score-reader",
+                ".pass-reader",
+            ]
+            + receipts
+        )
+        for step in range(1, blocks * capacity + 1):
+            css += f"@container loopcontrol style(--pass:{step}){{{pass_readers}{{--native-pass:{step}}}}}"
+        css += (
+            ",".join([".pass-reader"] + receipts) + "{--epoch:var(--native-pass)}"
+            ".reused-input,.core-valid,.fvs-query,.fvs-score-reader,.pass-reader{--position:calc(round(down,calc((var(--native-pass) - 1) / "
+            + str(blocks)
+            + "),1) + 1)}"
+        )
+        css = f5.make_private(
+            css, ["--loop-ready", "--loop-ack", "--native-pass", "--position"]
+        )
+        body, tagged = f5.tag_inline_readers(body, "var(--epoch)", "pass-reader")
+        body, tagged_position = f5.tag_inline_readers(
+            body, "var(--position)", "pass-reader"
+        )
+        # F3: the fc and proj generation markers no longer exist (no timeline hop).
+        expected_epoch_readers = 5 if f3.CHAIN_MLP else 7
+        if tagged != expected_epoch_readers or tagged_position != 2:
+            raise ValueError(
+                f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
+            )
+    else:
+        for step in range(1, blocks * capacity + 1):
+            css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
     # Style-container invalidation itself can cross private-property boundaries.
     # Move per-layer containers off body entirely, outside the head's ancestry.
     css = re.sub(r"\bbody(?=[{:\s])", ".core-controller", css)
@@ -153,6 +200,7 @@
         "isolatedMetricState": isolate_metrics,
         "valueLayout": value_layout,
         "globalProjection": global_projection,
+        "valueWeightOnce": value_weight_once and value_layout == "runs",
         "fontVectorOperatorVersion": 2 if codec == "font-vector" else None,
         "attentionMask": "full causal"
         if not kv_window or kv_window == capacity
@@ -166,6 +214,16 @@
         "nativeLayerTokenHandshake": True,
         "privateLayerControl": True,
         "localLayerContainer": True,
+        "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
+        "f5ScopedEpoch": f5.SCOPED_EPOCH,
+        "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
+        "f5InlineForward": f5.INLINE_FORWARD,
+        "f5BankFilledAliases": f5.BANK_FILLED_ALIASES,
+        "f5BankLiteralLists": f5.BANK_LITERAL_LISTS,
+        "f4PackedBanks": f4.PACKED_BANKS and codec == "font-vector",
+        "f4PackedHead": f4.PACKED_HEAD,
+        "f4NumericLists": f4.NUMERIC_LISTS and codec == "font-vector",
+        **f3.metadata(),
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ruN -x __pycache__ tools/browser_gpt2_reused_core.py work/2026-09-19/combined2/tools/browser_gpt2_reused_core.py
--- tools/browser_gpt2_reused_core.py	2026-09-17 00:17:23
+++ work/2026-09-19/combined2/tools/browser_gpt2_reused_core.py	2026-09-18 19:52:34
@@ -13,6 +13,8 @@
 
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as h
+import f3_chain_mlp as f3
+import f5_scoping as f5
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -99,9 +101,15 @@
     isolate_metrics=False,
     value_layout="runs",
     global_projection=False,
+    value_weight_once=True,
 ):
     if global_projection and isolate_metrics:
         raise ValueError("Do not combine global projection and metric isolation ablations")
+    if f3.CHAIN_MLP:
+        # F3: the proj hop no longer has packs or a global axis list; both
+        # ablations only shaped the timeline proj matvec and are moot here.
+        isolate_metrics = False
+        global_projection = False
     geometry_cache = codec == "geometry"
     font_vector_cache = codec == "font-vector"
     custom_cache = geometry_cache or font_vector_cache
@@ -130,6 +138,11 @@
         for kind in h.STAGES:
             if kind == "mix":
                 continue
+            if f3.CHAIN_MLP and kind == "proj":
+                # F3: the fc hop's anchor chains already host the proj shard
+                # columns and the out chain; nothing separate to nest here.
+                layouts[kind] = "{child}"
+                continue
             if kind in ("ln1", "ln2"):
                 n = 1 if kind == "ln1" else 2
                 html, rule = h.wrapper(
@@ -145,6 +158,15 @@
                         )
                     ),
                 )
+            elif f3.CHAIN_MLP and kind == "fc":
+                # F3 (Fix 3 + Fix 6 for the MLP hops): fc glyph rows are anchors,
+                # 12 fixed size-container chains gather them into --hidden-*,
+                # per-shard proj glyph columns hang under each chain bottom and
+                # one out chain sums the 12 shard advances into --out-*; no
+                # view-timeline, no generation receipt, no gate for fc/proj.
+                html, rule, once = f3.mlp_chain(layer, matrices[2], biases[2], matrices[3], biases[3])
+                if layer == 0:
+                    css += once
             else:
                 i = ("qkv", "attn", "fc", "proj").index(kind)
                 src, count = (("n1", W), ("ctx", W), ("n2", W), ("hidden", 4 * W))[i]
@@ -172,6 +194,13 @@
 
     if isolate_metrics:
         css = isolate_metric_state(css)
+    if h.INLINE_GELU:
+        # private scratch of the fc consumers; never inherited, never reset
+        css += "".join(
+            f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}'
+            for stem in ("fz", "ft")
+            for p in h.names(stem, 4 * W)
+        )
 
     # Cache storage stays outside the dense MLP subtree. Only the selected
     # layer exports a context vector through layout. Scalar banks are siblings;
@@ -204,6 +233,7 @@
             kv_window=kv_window,
             kv_sinks=kv_sinks,
             value_layout=value_layout,
+            value_weight_once=value_weight_once,
         )
         css += font_css
     if geometry_cache:
@@ -337,12 +367,25 @@
         css += forward(".loop-input", lp)
         css += forward(".loop-bank-0,.loop-bank-1", outputs)
         css += forward(".loop-scroll,.loop-track", saved)
-        for bank in range(2):
-            for i in range(W + 1):
-                css += forward(
-                    f".loop-bank-{bank}>.loop-scroll>.loop-track>.loop-metric:nth-child({i + 1})",
-                    [f"--saved-{bank}-{i}"],
-                )
+        if f5.INLINE_FORWARD:
+            # F5: 1,538 `.loop-metric:nth-child(N)` rules share one class
+            # bucket, so every loop-metric tested all 1,538 selectors on each
+            # restyle (P2: 153 us/element on the 1,553-element pass). The
+            # same forwarding as an inline declaration costs one rule.
+            body, count = re.subn(
+                r'<i class="loop-metric" style="width:calc\(262144px \+ var\((--saved-\d-\d+)\) \* 128px\);',
+                r'<i class="loop-metric" style="\1:inherit;width:calc(262144px + var(\1) * 128px);',
+                body,
+            )
+            if count != 2 * (W + 1):
+                raise ValueError(f"Expected {2 * (W + 1)} loop carriers, found {count}")
+        else:
+            for bank in range(2):
+                for i in range(W + 1):
+                    css += forward(
+                        f".loop-bank-{bank}>.loop-scroll>.loop-track>.loop-metric:nth-child({i + 1})",
+                        [f"--saved-{bank}-{i}"],
+                    )
         css += forward(".cache-active", bank_props)
         css += forward(
             ",".join(f".live-mix-{layer}" for layer in range(blocks)), bank_props
diff -ruN -x __pycache__ tools/browser_gpt2_runtime.py work/2026-09-19/combined2/tools/browser_gpt2_runtime.py
--- tools/browser_gpt2_runtime.py	2026-09-17 00:31:22
+++ work/2026-09-19/combined2/tools/browser_gpt2_runtime.py	2026-09-18 19:48:57
@@ -17,6 +17,8 @@
 
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as hybrid
+import f4_packing as f4
+import f5_scoping as f5
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -196,6 +198,7 @@
     font_backend="original",
     value_layout="runs",
     global_projection=False,
+    value_weight_once=True,
 ):
     if global_projection and not reuse_core:
         raise ValueError("Global projection currently requires the reused core")
@@ -235,6 +238,7 @@
             isolate_metrics,
             value_layout,
             global_projection,
+            value_weight_once,
         )
     else:
         core, core_css, metadata = compile_core(
@@ -253,6 +257,11 @@
     head_css = (head_dir / "head.css").read_text()
     if capacity > 8:
         head, head_css = split_head_receipt(head, head_css)
+    head_bank_regs = head_bank_decls = ""
+    if f4.PACKED_HEAD:
+        # F4: the head reads its 768 inputs only through two identical
+        # font-variation-settings lists; latch that list once instead of 768 numbers.
+        head_css, head_bank_regs, head_bank_decls = f4.pack_head_input(head_css)
     front, output, control_css, timeline_names = feedback(capacity)
     output_receiver = ""
     if detached_output:
@@ -286,7 +295,14 @@
         reset = [
             p
             for p in reset
-            if not re.fullmatch(r"--h\d+", p) and p != "--head-input-epoch"
+            if not re.fullmatch(r"--h\d+", p)
+            and p != "--head-input-epoch"
+            # F4: the packed head list must cross the wall; --hq-* never inherit
+            and p != "--head-fvs"
+            and not re.fullmatch(r"--hq-\d+", p)
+            and not re.fullmatch(r"--fvn-[kv]-\d+-\d+", p)
+            # F2: inherits:false fc scratch cannot reach the head; no wall needed
+            and not re.fullmatch(r"--f[zt]-\d+", p)
         ]
         css += (
             ".head-isolation{"
@@ -324,13 +340,22 @@
         "final-var",
     )
     css += ".final-normalization{" + ";".join(norm) + "}"
-    css += (
-        ".head-input-bank{"
-        + ";".join(f"--h{i}:var(--final-h-{i:03d})" for i in range(768))
-        + ";--head-input-epoch:calc(var(--epoch)*var(--bridge-ready));transition-property:"
-        + ",".join([f"--h{i}" for i in range(768)] + ["--head-input-epoch"])
-        + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}"
-    )
+    if f4.PACKED_HEAD:
+        css += head_bank_regs
+        css += (
+            ".head-input-bank{"
+            + head_bank_decls
+            + ";--head-input-epoch:calc(var(--epoch)*var(--bridge-ready));transition-property:--head-fvs,--head-input-epoch"
+            + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
+        )
+    else:
+        css += (
+            ".head-input-bank{"
+            + ";".join(f"--h{i}:var(--final-h-{i:03d})" for i in range(768))
+            + ";--head-input-epoch:calc(var(--epoch)*var(--bridge-ready));transition-property:"
+            + ",".join([f"--h{i}" for i in range(768)] + ["--head-input-epoch"])
+            + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}"
+        )
     css += f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.head-input-bank{{transition-property:none}}}}"
     # Probes load all head faces independently. Do not lay out the 50k-row
     # scorer on fallback fonts or provisional zero inputs during cold load.
@@ -382,6 +407,40 @@
             ".detached-head-state{--head-output-epoch:round(nearest,100cqi/1px,1);--winner:round(nearest,100cqb/1px,1)}"
             f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.full-head{{content-visibility:visible}}}}"
         )
+    if f5.SCOPED_FEEDBACK:
+        # F5: the token feedback state lives on .feedback-reader (depth 2,
+        # ~71.9k descendants) and is read by two of its children and by
+        # .embedding-source. Inherited, every readback restyled the document.
+        css = f5.make_private_prefix(
+            css, ["--feedback-", "--frozen-prompt", "--token"]
+        )
+        css += (
+            ".feedback-select,.visible-output{--frozen-prompt:inherit;"
+            + ";".join(f"--feedback-{i}:inherit" for i in range(1, capacity + 1))
+            + "}.embedding-source{--token:inherit}"
+        )
+    if f5.SCOPED_EPOCH and reuse_core and f5.SCOPED_HANDSHAKE:
+        # F5: body{--epoch} inherited into all 72k elements (P2: the whole-DOM
+        # pass at token-N-ack). Stamp the epoch onto its nine readers instead.
+        # Core-internal readers use the pass counter (pass-reader, adapter).
+        epoch_readers = ",".join(
+            [
+                ".epoch-reader",
+                ".embedding-receipt",
+                ".position-embedding",
+                ".feedback-select",
+                ".head-input-bank",
+                f".b{blocks - 1}-bridge-receipt",
+            ]
+        )
+        for e in range(1, capacity + 1):
+            css += f"@container runtime style(--epoch:{e}){{{epoch_readers}{{--epoch:{e}}}}}"
+        css = f5.make_private(css, ["--epoch"])
+        model, tagged = f5.tag_inline_readers(
+            model, "var(--epoch)", "epoch-reader", skip_class="pass-reader"
+        )
+        if tagged != 3:
+            raise ValueError(f"Unexpected inline epoch readers in model: {tagged}")
     font_html, font_css, font_count = font_barrier(css, directory)
     css += font_css
     scopes = re.findall(r"html\{timeline-scope:([^}]+)\}", css)
@@ -430,6 +489,12 @@
     )
 
     controls += '<svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="run-start"></g><g id="run-latched"><set attributeName="class" to="done" begin="run-start.animationend+0.001s" fill="freeze"/></g></svg>'
+    if f5.SCOPED_EPOCH and reuse_core and f5.SCOPED_HANDSHAKE:
+        controls, tagged_controls = f5.tag_inline_readers(
+            controls, "var(--epoch)", "epoch-reader"
+        )
+        if tagged_controls != 1:
+            raise ValueError(f"Unexpected inline epoch readers in controls: {tagged_controls}")
     speed = (
         "Measured warm speed: about 78 seconds/token on M2 Pro."
         if (blocks, capacity) == (12, 8)
@@ -466,7 +531,9 @@
     # There is no local-file URL dependency and no inference API endpoint.
     def relative_asset(match):
         parsed = urlparse(match[1])
-        relative = os.path.relpath(Path(unquote(parsed.path)), directory.resolve())
+        relative = os.path.relpath(
+            Path(unquote(parsed.path)).resolve(), directory.resolve()
+        )
         return (
             'url("'
             + quote(relative, safe="/.-_")
@@ -541,8 +608,17 @@
     parser.add_argument(
         "--value-layout", choices=("runs", "fallback", "widths"), default="runs"
     )
-    parser.add_argument("--global-projection", action="store_true")
+    # F2 round: both leaf-slimming changes default ON; --no-* restores the old emitter.
     parser.add_argument(
+        "--global-projection", action=argparse.BooleanOptionalAction, default=True
+    )
+    parser.add_argument(
+        "--value-weight-once", action=argparse.BooleanOptionalAction, default=True
+    )
+    parser.add_argument(
+        "--inline-gelu", action=argparse.BooleanOptionalAction, default=True
+    )
+    parser.add_argument(
         "--kv-window",
         type=int,
         help="Optional bounded attention context; changes the attention mask",
@@ -570,6 +646,7 @@
         default="scalar",
     )
     args = parser.parse_args()
+    hybrid.INLINE_GELU = args.inline_gelu
     if not 1 <= args.blocks <= 12 or not 2 <= args.capacity <= 32:
         parser.error("blocks must be 1–12; capacity must be 2–32")
     args.output.mkdir(parents=True, exist_ok=True)
@@ -595,6 +672,7 @@
         args.font_backend,
         args.value_layout,
         args.global_projection,
+        args.value_weight_once,
     )
 
 
diff -ruN -x __pycache__ tools/build_hybrid_twelve_block.py work/2026-09-19/combined2/tools/build_hybrid_twelve_block.py
--- tools/build_hybrid_twelve_block.py	2026-09-17 00:17:23
+++ work/2026-09-19/combined2/tools/build_hybrid_twelve_block.py	2026-09-18 19:48:57
@@ -27,6 +27,11 @@
 ASSET_OUT = OUT / "fonts"
 W = 768
 STAGES = ("ln1", "qkv", "mix", "attn", "ln2", "fc", "proj")
+# F2: replace the per-output --gelu() @function call (≈+10 µs each, M1 MB5) by the same
+# arithmetic split over three typed declarations on the consumer element. Same double ops
+# in the same order: --fz = pre-activation, --ft = clamped tanh argument, output = tanh form.
+INLINE_GELU = True
+GELU_K = ".7978845608028654"
 
 
 def names(stem, count):
@@ -164,6 +169,10 @@
         families = ",".join(
             f"{family}S{s}" for s in range(first, len(group.names) if global_axes else min(first + 3, len(group.names)))
         )
+        if compact and packs == 1:
+            # F2: the `font:` shorthand below resets this list and the stage
+            # rule re-declares it afterwards; the early copy never wins.
+            continue
         selector = f".{stem}" if compact and packs == 1 else f".{stem}-pack{pack}"
         css += f"{selector}{{font-family:{families};font-variation-settings:{settings(first)}}}"
     metrics = []
@@ -221,7 +230,15 @@
             gain = f"{num(quantized.scales[i])} * var(--range-{kind})" if dynamic_range else num(activation_range * quantized.scales[i])
             value = f"calc({raw} * {gain} + ({num(bias[i])}))"
             if kind == "fc":
-                value = f"--gelu({value})"
+                if INLINE_GELU:
+                    z, t = f"--fz-{i:03d}", f"--ft-{i:03d}"
+                    result.append(f"{z}:{value}")
+                    result.append(
+                        f"{t}:clamp(-20,calc({GELU_K} * (var({z}) + .044715 * pow(var({z}),3))),20)"
+                    )
+                    value = f"calc(.5 * var({z}) * (1 + (exp(2 * var({t})) - 1) / (exp(2 * var({t})) + 1)))"
+                else:
+                    value = f"--gelu({value})"
             elif kind == "attn":
                 value = f"calc(var(--x-{i:03d}) + {value})"
             elif kind == "proj":
diff -ruN -x __pycache__ tools/f3_chain_mlp.py work/2026-09-19/combined2/tools/f3_chain_mlp.py
--- tools/f3_chain_mlp.py	1969-12-31 16:00:00
+++ work/2026-09-19/combined2/tools/f3_chain_mlp.py	2026-09-18 19:55:28
@@ -0,0 +1,242 @@
+"""F3b (2026-09-19): frameless fc -> proj -> out transport for the reused core.
+
+Fix 3 (work/2026-09-19/F3.md): every view-timeline readback costs one frame, one
+extra style pass and one layout per boundary, and re-restyles the downstream
+chain.  A geometry -> number hop through `anchor-size()` on a `position:fixed`
+size container and container-query units on its child resolves inside ONE
+style/layout lifecycle.  This module emits the MLP (fc 768->3072, GELU,
+proj 3072->768, +r) of one layer in that form; the HTML is layer-independent
+(one reused graph), the per-layer constants live in `@container runtime
+style(--layer:L)` rules exactly like the timeline emitter.
+
+Layout of one layer (data-flow order = tree order, F3.md §3b ordering rule):
+
+  .f3-mlp                         common ancestor; --range-fc = max|n2|*1.001
+    .f3-stage.f3-fc (fixed)       3,072 in-flow rows, anchor-name --f3f{i};
+                                  row width = sum of the 3 fc shard glyphs
+                                  (fallback fonts), font-variation-settings = n2
+    12 x fc chains (fixed size containers, one element per level, F3_CHAIN_LEVEL=1)
+      #f3c{j}-{k}                 width/height = anchor-size(--f3f{2k},{2k+1})
+                                  and publishes the PARENT container's two
+                                  values as --hidden-* (GELU decode)
+      #f3r{j} (in-flow bottom)    --range-proj = max|hidden shard j|*1.001,
+                                  anchor #f3m{j} width = range*1024px,
+                                  .f3-stage #f3s{j}: 768 proj glyph rows of
+                                  shard j, anchor-name --f3p{j}_{i}
+    out chain (fixed size containers, 6 range levels + 384 value levels)
+      #f3g{t}                     reads --f3m{2t},{2t+1} -> --f3pr{j}
+      #f3o{k}                     width = sum_j anchor-size(--f3p{j}_{2k}) * --f3pr{j}
+      #f3b (in-flow bottom)       publishes --out-766/767 and hosts {child}
+
+Chromium rules obeyed (F3.md §2/§3b): only `position:fixed` containers (any
+absolute/relative/contained ancestor would become the containing block and hide
+the anchors -> silent zeros); anchors precede their readers in tree order;
+chain depth <= 391 elements (HTML parser nesting cap 512); widths < 2^24 px.
+
+Env flags (default ON):
+  F3_CHAIN_MLP=0     keep the view-timeline matvec() for fc and proj
+  F3_CHAIN_LEVEL=2   fc chains with two elements per level (container + plain
+                     child), the exact Prototype A/B shape; default 1 = the
+                     next container itself publishes its parent's values.
+                     The out chain (768 values = 390 levels) always uses 1.
+"""
+
+import os
+
+import build_gpt2_block_css as b
+import build_hybrid_twelve_block as h
+import numpy as np
+from build_pretrained_gpt2 import css_number as num
+
+W, M = 768, 3072
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+CHAIN_MLP = flag("F3_CHAIN_MLP")
+CHAIN_LEVEL = int(os.environ.get("F3_CHAIN_LEVEL", "1"))
+if CHAIN_LEVEL not in (1, 2):
+    raise ValueError("F3_CHAIN_LEVEL must be 1 or 2")
+
+RANGE_PX = 1024  # --range-proj travels as an anchor of width range*1024px
+SHARDS_PROJ = M // b.SHARD  # 12
+SHARDS_FC = W // b.SHARD  # 3
+FC_CHAIN = b.SHARD // 2  # 128 containers per fc chain (2 values each)
+OUT_CHAIN = W // 2  # 384 containers in the out chain
+RANGE_CHAIN = SHARDS_PROJ // 2  # 6 containers carry the 12 shard ranges
+
+PX_TO_UNITS = f"{b.UNITS_PER_EM} / {b.FONT_SIZE}"
+
+
+def _chain(ids, size, bottom, level):
+    """Nested fixed size containers.
+
+    ids[k]   element id of level k
+    size[k]  (width, height) CSS values for level k (None -> a plain in-flow
+             block: the chain bottom)
+    bottom   html placed inside the last level
+    level    1: level k's element itself publishes level k-1's two values;
+             2: a plain child of k-1 (`#<id>p`) wraps level k and publishes.
+    Returns (html, once_css) with the layer-independent width/height rules;
+    the caller emits the publish declarations (see _publisher).
+    """
+    parts, css, depth = [], [], 0
+    for k, ident in enumerate(ids):
+        if size[k] is not None:
+            css.append(f"#{ident}{{width:{size[k][0]};height:{size[k][1]}}}")
+        if level == 2 and k >= 1:
+            parts.append(f'<div class="f3-p" id="{ident}p">')
+            depth += 1
+        cls = "f3-c" if size[k] is not None else "f3-b"
+        parts.append(f'<div class="{cls}" id="{ident}">')
+        depth += 1
+    parts.append(bottom)
+    parts.append("</div>" * depth)
+    return "".join(parts), "".join(css)
+
+
+def _publisher(ident, level):
+    """Selector of the element publishing the values of the container above `ident`."""
+    return f"#{ident}p" if level == 2 else f"#{ident}"
+
+
+def mlp_chain(layer, qfc, bfc, qproj, bproj):
+    """Return (html, per_layer_css, once_css) for one layer's fc+proj hops.
+
+    html is identical for every layer (checked by compile_reused's layouts
+    identity); per_layer_css is wrapped by specialize() into
+    `@container runtime style(--layer:L)`; once_css must be emitted once.
+    """
+    dfc, gfc = h.font_group(layer, "fc", qfc)
+    dproj, gproj = h.font_group(layer, "proj", qproj)
+    if len(gfc.names) != SHARDS_FC or len(gproj.names) != SHARDS_PROJ:
+        raise ValueError("F3 chain MLP expects 3 fc shards and 12 proj shards")
+    fc_bases = np.sum(np.stack(gfc.row_bases), axis=0)  # (3072,)
+    proj_bases = np.stack(gproj.row_bases)  # (12, 768)
+    n2, hid, outn, r = h.names("n2", W), h.names("hidden", M), h.names("out", W), h.names("r", W)
+    ranges = [f"--f3pr{j}" for j in range(SHARDS_PROJ)]
+    fam_fc, fam_proj = f"b{layer}fc", f"b{layer}proj"
+
+    layer_css = []
+    once = []
+    # --- per-layer font faces (specialize() hoists @font-face out of the layer rule)
+    layer_css.append(b.font_faces(f"b{layer}-fc", gfc).replace('url("', f'url("{dfc.as_uri()}/'))
+    layer_css.append(b.font_faces(f"b{layer}-proj", gproj).replace('url("', f'url("{dproj.as_uri()}/'))
+    layer_css.append(
+        f".f3-fc{{font-family:{','.join(f'{fam_fc}S{s}' for s in range(SHARDS_FC))}}}"
+    )
+    for j in range(SHARDS_PROJ):
+        layer_css.append(f"#f3s{j}{{font-family:{fam_proj}S{j}}}")
+
+    # --- once: registrations, structure, layer-independent settings
+    once.append(h.regs(["--range-fc", "--range-proj"] + ranges))
+    once.append(
+        ".f3-stage{position:fixed;left:0;top:-60000px;visibility:hidden;font-kerning:none;"
+        f"white-space:pre;line-height:1;font-size:{b.FONT_SIZE}px;font-style:normal;font-weight:normal}}"
+        ".f3-row{display:block;height:1px;width:max-content;font-style:normal}"
+        ".f3-c{position:fixed;left:0;top:0;container-type:size}"
+        ".f3-p,.f3-b{display:block;height:1px;width:1px}"
+        ".f3-m{display:block;height:1px}"
+    )
+    once.append(
+        f".f3-mlp{{--range-fc:calc(max(.000001,{','.join(f'abs(var({p}))' for p in n2)}) * 1.001)}}"
+    )
+    fc_settings = b.pack_font_settings(n2, 1, 0).replace(" / 1)", " / var(--range-fc))")
+    once.append(f".f3-fc{{font-variation-settings:{fc_settings}}}")
+
+    # --- fc anchors: one row per hidden unit, 3 shard glyphs (fallback fonts sum their advances)
+    fc_rows = "".join(
+        f'<i class="f3-row" style="anchor-name:--f3f{i}">'
+        + "".join(f"&#x{gfc.codepoint_starts[s] + i:X};" for s in range(SHARDS_FC))
+        + "</i>"
+        for i in range(M)
+    )
+    html = [f'<div class="f3-mlp"><div class="f3-stage f3-fc" id="f3fs">{fc_rows}</div>']
+
+    # --- 12 fc chains, each hosting its proj shard column
+    for j in range(SHARDS_PROJ):
+        ids = [f"f3c{j}-{k}" for k in range(FC_CHAIN)] + [f"f3r{j}"]
+        size = [
+            (f"anchor-size(--f3f{b.SHARD * j + 2 * k} width)", f"anchor-size(--f3f{b.SHARD * j + 2 * k + 1} width)")
+            for k in range(FC_CHAIN)
+        ] + [None]
+        local = hid[b.SHARD * j : b.SHARD * (j + 1)]
+        proj_settings = ",".join(
+            f'"{b.packed_axis_tag(j % b.PACK_SHARDS, l)}" calc(var({local[l]}) / var(--range-proj))'
+            for l in range(b.SHARD)
+        )
+        once.append(
+            f"#f3r{j}{{--range-proj:calc(max(.000001,{','.join(f'abs(var({p}))' for p in local)}) * 1.001)}}"
+            f"#f3m{j}{{width:calc(var(--range-proj) * {RANGE_PX}px)}}"
+            f"#f3s{j}{{font-variation-settings:{proj_settings}}}"
+        )
+        prow = "".join(
+            f'<i class="f3-row" style="anchor-name:--f3p{j}_{i}">&#x{gproj.codepoint_starts[j] + i:X};</i>'
+            for i in range(W)
+        )
+        bottom = (
+            f'<i class="f3-m" id="f3m{j}" style="anchor-name:--f3m{j}"></i>'
+            f'<div class="f3-stage" id="f3s{j}">{prow}</div>'
+        )
+        chain_html, chain_css = _chain(ids, size, bottom, CHAIN_LEVEL)
+        once.append(chain_css)
+        html.append(chain_html)
+        # per-layer GELU decode: level k+1 publishes container k's two values
+        for k in range(FC_CHAIN):
+            decls = []
+            for i, unit in ((b.SHARD * j + 2 * k, "cqw"), (b.SHARD * j + 2 * k + 1, "cqh")):
+                raw = f"(100{unit} / 1px * {PX_TO_UNITS} - {int(fc_bases[i])})"
+                decls.append(
+                    f"{hid[i]}:--gelu(calc({raw} * {num(qfc.scales[i])} * var(--range-fc) + ({num(bfc[i])})))"
+                )
+            layer_css.append(f"{_publisher(ids[k + 1], CHAIN_LEVEL)}{{{';'.join(decls)}}}")
+
+    # --- out chain: 6 range containers, then 384 value containers, bottom hosts {child}
+    ids = [f"f3g{t}" for t in range(RANGE_CHAIN)] + [f"f3o{k}" for k in range(OUT_CHAIN)] + ["f3b"]
+    size = [
+        (f"anchor-size(--f3m{2 * t} width)", f"anchor-size(--f3m{2 * t + 1} width)")
+        for t in range(RANGE_CHAIN)
+    ]
+    for k in range(OUT_CHAIN):
+        wsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
+        hsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k + 1} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
+        size.append((f"calc({wsum})", f"calc({hsum})"))
+    size.append(None)
+    # the out chain must hold 768 values: only one element per level fits the parser cap
+    chain_html, chain_css = _chain(ids, size, "{child}", 1)
+    once.append(chain_css)
+    html.append(chain_html)
+    html.append("</div>")
+    # range publishers are layer-independent
+    for t in range(RANGE_CHAIN):
+        once.append(
+            f"{_publisher(ids[t + 1], 1)}{{{ranges[2 * t]}:calc(100cqw / 1px / {RANGE_PX});"
+            f"{ranges[2 * t + 1]}:calc(100cqh / 1px / {RANGE_PX})}}"
+        )
+    # per-layer output decode (+ residual r)
+    for k in range(OUT_CHAIN):
+        decls = []
+        for i, unit in ((2 * k, "cqw"), (2 * k + 1, "cqh")):
+            bases = " + ".join(f"{int(proj_bases[j][i])} * var({ranges[j]})" for j in range(SHARDS_PROJ))
+            raw = f"(100{unit} / 1px * {PX_TO_UNITS} - ({bases}))"
+            decls.append(f"{outn[i]}:calc(var({r[i]}) + {raw} * {num(qproj.scales[i])} + ({num(bproj[i])}))")
+        layer_css.append(f"{_publisher(ids[RANGE_CHAIN + k + 1], 1)}{{{';'.join(decls)}}}")
+    return "".join(html), "".join(layer_css), "".join(once)
+
+
+def chain_depth():
+    """Elements added below .f3-mlp on the deepest path (for the 512 parser cap check)."""
+    out = 1 + (RANGE_CHAIN + OUT_CHAIN) + 1  # .f3-mlp + containers + #f3b
+    fc = 1 + FC_CHAIN * CHAIN_LEVEL + CHAIN_LEVEL + 2  # .f3-mlp + containers(+publishers) + #f3r + .f3-stage + row
+    return max(out, fc)
+
+
+def metadata():
+    return {
+        "f3ChainMlp": CHAIN_MLP,
+        "f3ChainLevel": CHAIN_LEVEL,
+        "f3ChainContainers": SHARDS_PROJ * FC_CHAIN + RANGE_CHAIN + OUT_CHAIN,
+        "f3ChainAnchors": M + SHARDS_PROJ * W + SHARDS_PROJ,
+    }
diff -ruN -x __pycache__ tools/f4_packing.py work/2026-09-19/combined2/tools/f4_packing.py
--- tools/f4_packing.py	1969-12-31 16:00:00
+++ work/2026-09-19/combined2/tools/f4_packing.py	2026-09-18 19:48:57
@@ -0,0 +1,167 @@
+"""F4 (2026-09-19): cut the retained-transition count of the reused runtime.
+
+F5 §4 measured ≈5.7 µs per in-delay CSS transition on EVERY style pass of the
+document (the transition idiom is the only CSS-only value latch, so its COUNT is
+the lever). Both changes are behind environment flags (default ON):
+
+  F4_PACKED_BANKS=0  keep 48 latches per KV slot (12 heads × {k, v, ks, vs});
+                     ON: 26 per slot — one 768-axis `*` list per kind (k, v) with
+                     the 12 heads on disjoint axis tags + the 24 per-head scales
+  F4_PACKED_HEAD=0   keep the 769 `--h*` head-input latches;
+                     ON: 2 — the finished 768-entry head font-variation-settings
+                     list (exact integers) + the epoch
+
+Fonts ignore variation tags they do not define (the mechanism F2's global
+projection relies on), so one list can feed 12 differently-tagged fonts. The
+retagged operator fonts differ from font-vector-operators-v2 only in fvar tags,
+STAT and name (HVAR/hmtx/cmap/glyf/loca/maxp/hhea asserted byte-identical).
+"""
+
+import hashlib
+import os
+import re
+import tempfile
+from pathlib import Path
+
+from fontTools.otlLib.builder import buildStatTable
+from fontTools.ttLib import TTFont
+
+HEADS, DIM = 12, 64
+ASSETS = Path(__file__).resolve().parents[1] / "assets" / "font-vector-operators-f4"
+PROTECTED = ("HVAR", "hmtx", "cmap", "glyf", "loca", "maxp", "hhea")
+
+
+def flag(name):
+    return os.environ.get(name, "1") not in ("0", "false", "no", "off")
+
+
+PACKED_BANKS = flag("F4_PACKED_BANKS")
+PACKED_HEAD = flag("F4_PACKED_HEAD")
+# F4 micro-test 2: the per-pass cost of the retained `*` lists tracks their BYTES
+# (49.6 ms for `calc(a / b)` entries vs 35.7 ms for plain numbers, same entries),
+# so the live lists carry pre-evaluated typed numbers (6 significant digits when
+# substituted, like the calc operands were) instead of an unevaluated quotient.
+NUMERIC_LISTS = flag("F4_NUMERIC_LISTS")
+
+
+def head_axis(kind, head, coordinate):
+    """Disjoint per-head tags: K000..K2FF for keys, V000..V2FF for values."""
+    if kind not in ("k", "v") or not 0 <= head < HEADS or not 0 <= coordinate < DIM:
+        raise ValueError("Bad head axis")
+    return f"{kind.upper()}{head * DIM + coordinate:03X}"
+
+
+def zero_list(kind):
+    return ",".join(
+        f'"{head_axis(kind, head, i)}" 0' for head in range(HEADS) for i in range(DIM)
+    )
+
+
+def kind_of(name):
+    """--fc-{kind}-{slot}[-{head}] -> kind (works for packed and unpacked names)."""
+    return name.split("-")[3]
+
+
+def slot_of(name):
+    return int(name.split("-")[4])
+
+
+def packed_operator_fonts(source_dir):
+    """[(dot_path, value_path)] per head, retagged from the v2 operator fonts."""
+    ASSETS.mkdir(parents=True, exist_ok=True)
+    result = []
+    for head in range(HEADS):
+        pair = []
+        for kind, family in (("dot", "k"), ("value", "v")):
+            source = Path(source_dir) / f"{kind}.woff2"
+            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
+            target = ASSETS / f"{kind}-h{head}-{digest}-f4.woff2"
+            if not target.exists():
+                font = TTFont(source, recalcTimestamp=False)
+                protected = {
+                    tag: font.getTableData(tag) for tag in PROTECTED if tag in font
+                }
+                retagged = 0
+                for axis in font["fvar"].axes:
+                    if re.fullmatch(r"K\d{3}", axis.axisTag):
+                        axis.axisTag = head_axis(family, head, int(axis.axisTag[1:]))
+                        retagged += 1
+                if retagged != DIM:
+                    raise ValueError(f"Expected {DIM} K axes in {source}, found {retagged}")
+                buildStatTable(
+                    font,
+                    [
+                        {"tag": a.axisTag, "name": a.axisNameID, "ordering": i}
+                        for i, a in enumerate(font["fvar"].axes)
+                    ],
+                )
+                for name_id in (1, 3, 4, 6):
+                    font["name"].setName(
+                        f"Fvs{kind.title()}H{head}F4", name_id, 3, 1, 0x409
+                    )
+                with tempfile.NamedTemporaryFile(
+                    dir=ASSETS, suffix=".woff2", delete=False
+                ) as staging:
+                    temporary = Path(staging.name)
+                try:
+                    font.save(temporary)
+                    checked = TTFont(temporary, recalcTimestamp=False)
+                    for tag, original in protected.items():
+                        if checked.getTableData(tag) != original:
+                            raise ValueError(f"Retagging changed {tag}: {source}")
+                    tags = [a.axisTag for a in checked["fvar"].axes]
+                    expected = [
+                        head_axis(family, head, int(t[1:])) if re.fullmatch(r"K\d{3}", t) else t
+                        for t in (a.axisTag for a in TTFont(source, lazy=True)["fvar"].axes)
+                    ]
+                    if tags != expected:
+                        raise ValueError(f"Unexpected fvar tags after retagging: {source}")
+                    temporary.replace(target)
+                finally:
+                    temporary.unlink(missing_ok=True)
+            pair.append(target)
+        result.append(tuple(pair))
+    return result
+
+
+_HEAD_ENTRY = re.compile(
+    r'"(X[0-9A-Z]{3})" round\(nearest,calc\(var\(--h(\d+)\)/([0-9.]+)\*16384\),1\)'
+)
+_HEAD_LIST = re.compile(
+    r'font-variation-settings:((?:"X[0-9A-Z]{3}" round\(nearest,calc\(var\(--h\d+\)/[0-9.]+\*16384\),1\),?)+)'
+)
+
+
+def pack_head_input(head_css, width=768, final="final-h"):
+    """Replace head.css's two identical --h lists by var(--head-fvs).
+
+    Returns (head_css, registrations, bank_declarations). The bank computes the
+    768 rounded axis integers as typed numbers (same double ops, same order as
+    the head.css expression on --h_i == --final-h-i) and latches ONE list of
+    them; integers serialise exactly into the `*` property.
+    """
+    lists = _HEAD_LIST.findall(head_css)
+    if len(lists) != 2 or lists[0] != lists[1]:
+        raise ValueError(f"Expected two identical head input lists, found {len(lists)}")
+    entries = _HEAD_ENTRY.findall(lists[0])
+    if len(entries) != width or lists[0].count('"') != 2 * width:
+        raise ValueError(f"Expected {width} head axes, found {len(entries)}")
+    divisors = {d for _, _, d in entries}
+    if len(divisors) != 1 or [int(i) for _, i, _ in entries] != list(range(width)):
+        raise ValueError("Head input list is not the regular per-coordinate form")
+    divisor = divisors.pop()
+    head_css, replaced = _HEAD_LIST.subn("font-variation-settings:var(--head-fvs)", head_css)
+    if replaced != 2:
+        raise ValueError("Head list replacement mismatch")
+    quantized = [f"--hq-{i}" for i in range(width)]
+    regs = "".join(
+        f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for p in quantized
+    ) + '@property --head-fvs{syntax:"*";inherits:true;initial-value:"X000" 0}'
+    decls = ";".join(
+        f"{p}:round(nearest,calc(var(--{final}-{i:03d})/{divisor}*16384),1)"
+        for i, p in enumerate(quantized)
+    )
+    decls += ";--head-fvs:" + ",".join(
+        f'"{tag}" var(--hq-{i})' for tag, i, _ in entries
+    )
+    return head_css, regs, decls
diff -ruN -x __pycache__ tools/f5_scoping.py work/2026-09-19/combined2/tools/f5_scoping.py
--- tools/f5_scoping.py	1969-12-31 16:00:00
+++ work/2026-09-19/combined2/tools/f5_scoping.py	2026-09-18 19:48:58
@@ -0,0 +1,88 @@
+"""F5 (2026-09-19): narrow the inherited write points of the reused runtime.
+
+Every change is behind an environment flag (default ON) so it can be reverted
+independently when building:
+
+  F5_SCOPED_HANDSHAKE=0  keep --loop-ready/--loop-ack/--native-pass/--position inherited
+  F5_SCOPED_EPOCH=0      keep the token --epoch inherited from body
+  F5_SCOPED_FEEDBACK=0   keep --feedback-*/--feedback-p-*/--frozen-prompt/--token inherited
+  F5_INLINE_FORWARD=0    keep the 1,538 `.loop-metric:nth-child(N){--saved:inherit}` rules
+  F5_BANK_FILLED_ALIASES=0  alias all 48*capacity KV fields instead of only filled slots
+  F5_BANK_LITERAL_LISTS=0   keep `transition-property:var(--fvs-*)` instead of literal lists
+
+Mechanism (audit/2026-09-18/SYNTHESIS.md §8.1-8.2): a registered custom property
+written with inherits:true restyles every non-locked descendant of the element
+it is written on; inherits:false restyles one element. Readers get an explicit
+republish (`inherit`, or a container-query stamp of the same value).
+"""
+
+import os
+import re
+
+
+def flag(name):
+    return os.environ.get(name, "1") not in ("0", "false", "no", "off")
+
+
+SCOPED_HANDSHAKE = flag("F5_SCOPED_HANDSHAKE")
+SCOPED_EPOCH = flag("F5_SCOPED_EPOCH")
+SCOPED_FEEDBACK = flag("F5_SCOPED_FEEDBACK")
+INLINE_FORWARD = flag("F5_INLINE_FORWARD")
+BANK_FILLED_ALIASES = flag("F5_BANK_FILLED_ALIASES")
+BANK_LITERAL_LISTS = flag("F5_BANK_LITERAL_LISTS")
+
+_PROPERTY = re.compile(r"@property (--[\w-]+)\{[^{}]+\}")
+
+
+def make_private(css, names):
+    """Re-register the given custom properties with inherits:false."""
+    names = set(names)
+
+    def swap(match):
+        if match[1] in names:
+            return match[0].replace("inherits:true", "inherits:false")
+        return match[0]
+
+    return _PROPERTY.sub(swap, css)
+
+
+def make_private_prefix(css, prefixes):
+    prefixes = tuple(prefixes)
+
+    def swap(match):
+        if match[1].startswith(prefixes):
+            return match[0].replace("inherits:true", "inherits:false")
+        return match[0]
+
+    return _PROPERTY.sub(swap, css)
+
+
+_TAG = re.compile(r"<(i|span|div|output)\b([^>]*?)>")
+
+
+def tag_inline_readers(html, needle, cls, skip_class=None):
+    """Add `cls` to every element whose inline style contains `needle`.
+
+    Elements that already carry `skip_class` are left alone (they were tagged
+    by an inner compiler stage with a different republish source).
+    """
+    count = 0
+
+    def visit(match):
+        nonlocal count
+        attrs = match[2]
+        style = re.search(r'style="([^"]*)"', attrs)
+        if not style or needle not in style[1]:
+            return match[0]
+        existing = re.search(r'class="([^"]*)"', attrs)
+        if existing:
+            classes = existing[1].split()
+            if cls in classes or (skip_class and skip_class in classes):
+                return match[0]
+            attrs = attrs.replace(existing[0], f'class="{existing[1]} {cls}"', 1)
+        else:
+            attrs = f' class="{cls}"' + attrs
+        count += 1
+        return f"<{match[1]}{attrs}>"
+
+    return _TAG.sub(visit, html), count
```
