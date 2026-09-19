"""F3b (2026-09-19): frameless fc -> proj -> out transport for the reused core.

Fix 3 (work/2026-09-19/F3.md): every view-timeline readback costs one frame, one
extra style pass and one layout per boundary, and re-restyles the downstream
chain.  A geometry -> number hop through `anchor-size()` on a `position:fixed`
size container and container-query units on its child resolves inside ONE
style/layout lifecycle.  This module emits the MLP (fc 768->3072, GELU,
proj 3072->768, +r) of one layer in that form; the HTML is layer-independent
(one reused graph), the per-layer constants live in `@container runtime
style(--layer:L)` rules exactly like the timeline emitter.

Layout of one layer (data-flow order = tree order, F3.md §3b ordering rule):

  .f3-mlp                         common ancestor; --range-fc = max|n2|*1.001
    .f3-stage.f3-fc (fixed)       3,072 in-flow rows, anchor-name --f3f{i};
                                  row width = sum of the 3 fc shard glyphs
                                  (fallback fonts), font-variation-settings = n2
    12 x fc chains (fixed size containers, one element per level, F3_CHAIN_LEVEL=1)
      #f3c{j}-{k}                 width/height = anchor-size(--f3f{2k},{2k+1})
                                  and publishes the PARENT container's two
                                  values as --hidden-* (GELU decode)
      #f3r{j} (in-flow bottom)    --range-proj = max|hidden shard j|*1.001,
                                  anchor #f3m{j} width = range*1024px,
                                  .f3-stage #f3s{j}: 768 proj glyph rows of
                                  shard j, anchor-name --f3p{j}_{i}
    out chain (fixed size containers, 6 range levels + 384 value levels)
      #f3g{t}                     reads --f3m{2t},{2t+1} -> --f3pr{j}
      #f3o{k}                     width = sum_j anchor-size(--f3p{j}_{2k}) * --f3pr{j}
      #f3b (in-flow bottom)       publishes --out-766/767 and hosts {child}

Chromium rules obeyed (F3.md §2/§3b): only `position:fixed` containers (any
absolute/relative/contained ancestor would become the containing block and hide
the anchors -> silent zeros); anchors precede their readers in tree order;
chain depth <= 391 elements (HTML parser nesting cap 512); widths < 2^24 px.

Env flags (default ON):
  F3_CHAIN_MLP=0     keep the view-timeline matvec() for fc and proj
  F3_CHAIN_LEVEL=2   fc chains with two elements per level (container + plain
                     child), the exact Prototype A/B shape; default 1 = the
                     next container itself publishes its parent's values.
                     The out chain (768 values = 390 levels) always uses 1.
"""

import os

import build_gpt2_block_css as b
import build_hybrid_twelve_block as h
import numpy as np
from build_pretrained_gpt2 import css_number as num

W, M = 768, 3072


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


CHAIN_MLP = flag("F3_CHAIN_MLP")
CHAIN_LEVEL = int(os.environ.get("F3_CHAIN_LEVEL", "1"))
if CHAIN_LEVEL not in (1, 2):
    raise ValueError("F3_CHAIN_LEVEL must be 1 or 2")

RANGE_PX = 1024  # --range-proj travels as an anchor of width range*1024px
SHARDS_PROJ = M // b.SHARD  # 12
SHARDS_FC = W // b.SHARD  # 3
FC_CHAIN = b.SHARD // 2  # 128 containers per fc chain (2 values each)
OUT_CHAIN = W // 2  # 384 containers in the out chain
RANGE_CHAIN = SHARDS_PROJ // 2  # 6 containers carry the 12 shard ranges

PX_TO_UNITS = f"{b.UNITS_PER_EM} / {b.FONT_SIZE}"


def _chain(ids, size, bottom, level):
    """Nested fixed size containers.

    ids[k]   element id of level k
    size[k]  (width, height) CSS values for level k (None -> a plain in-flow
             block: the chain bottom)
    bottom   html placed inside the last level
    level    1: level k's element itself publishes level k-1's two values;
             2: a plain child of k-1 (`#<id>p`) wraps level k and publishes.
    Returns (html, once_css) with the layer-independent width/height rules;
    the caller emits the publish declarations (see _publisher).
    """
    parts, css, depth = [], [], 0
    for k, ident in enumerate(ids):
        if size[k] is not None:
            css.append(f"#{ident}{{width:{size[k][0]};height:{size[k][1]}}}")
        if level == 2 and k >= 1:
            parts.append(f'<div class="f3-p" id="{ident}p">')
            depth += 1
        cls = "f3-c" if size[k] is not None else "f3-b"
        parts.append(f'<div class="{cls}" id="{ident}">')
        depth += 1
    parts.append(bottom)
    parts.append("</div>" * depth)
    return "".join(parts), "".join(css)


def _publisher(ident, level):
    """Selector of the element publishing the values of the container above `ident`."""
    return f"#{ident}p" if level == 2 else f"#{ident}"


def mlp_chain(layer, qfc, bfc, qproj, bproj):
    """Return (html, per_layer_css, once_css) for one layer's fc+proj hops.

    html is identical for every layer (checked by compile_reused's layouts
    identity); per_layer_css is wrapped by specialize() into
    `@container runtime style(--layer:L)`; once_css must be emitted once.
    """
    dfc, gfc = h.font_group(layer, "fc", qfc)
    dproj, gproj = h.font_group(layer, "proj", qproj)
    if len(gfc.names) != SHARDS_FC or len(gproj.names) != SHARDS_PROJ:
        raise ValueError("F3 chain MLP expects 3 fc shards and 12 proj shards")
    fc_bases = np.sum(np.stack(gfc.row_bases), axis=0)  # (3072,)
    proj_bases = np.stack(gproj.row_bases)  # (12, 768)
    n2, hid, outn, r = h.names("n2", W), h.names("hidden", M), h.names("out", W), h.names("r", W)
    ranges = [f"--f3pr{j}" for j in range(SHARDS_PROJ)]
    fam_fc, fam_proj = f"b{layer}fc", f"b{layer}proj"

    layer_css = []
    once = []
    # --- per-layer font faces (specialize() hoists @font-face out of the layer rule)
    layer_css.append(b.font_faces(f"b{layer}-fc", gfc).replace('url("', f'url("{dfc.as_uri()}/'))
    layer_css.append(b.font_faces(f"b{layer}-proj", gproj).replace('url("', f'url("{dproj.as_uri()}/'))
    layer_css.append(
        f".f3-fc{{font-family:{','.join(f'{fam_fc}S{s}' for s in range(SHARDS_FC))}}}"
    )
    for j in range(SHARDS_PROJ):
        layer_css.append(f"#f3s{j}{{font-family:{fam_proj}S{j}}}")

    # --- once: registrations, structure, layer-independent settings
    once.append(h.regs(["--range-fc", "--range-proj"] + ranges))
    once.append(
        ".f3-stage{position:fixed;left:0;top:-60000px;visibility:hidden;font-kerning:none;"
        f"white-space:pre;line-height:1;font-size:{b.FONT_SIZE}px;font-style:normal;font-weight:normal}}"
        ".f3-row{display:block;height:1px;width:max-content;font-style:normal}"
        ".f3-c{position:fixed;left:0;top:0;container-type:size}"
        ".f3-p,.f3-b{display:block;height:1px;width:1px}"
        ".f3-m{display:block;height:1px}"
    )
    once.append(
        f".f3-mlp{{--range-fc:calc(max(.000001,{','.join(f'abs(var({p}))' for p in n2)}) * 1.001)}}"
    )
    fc_settings = b.pack_font_settings(n2, 1, 0).replace(" / 1)", " / var(--range-fc))")
    once.append(f".f3-fc{{font-variation-settings:{fc_settings}}}")

    # --- fc anchors: one row per hidden unit, 3 shard glyphs (fallback fonts sum their advances)
    fc_rows = "".join(
        f'<i class="f3-row" style="anchor-name:--f3f{i}">'
        + "".join(f"&#x{gfc.codepoint_starts[s] + i:X};" for s in range(SHARDS_FC))
        + "</i>"
        for i in range(M)
    )
    html = [f'<div class="f3-mlp"><div class="f3-stage f3-fc" id="f3fs">{fc_rows}</div>']

    # --- 12 fc chains, each hosting its proj shard column
    for j in range(SHARDS_PROJ):
        ids = [f"f3c{j}-{k}" for k in range(FC_CHAIN)] + [f"f3r{j}"]
        size = [
            (f"anchor-size(--f3f{b.SHARD * j + 2 * k} width)", f"anchor-size(--f3f{b.SHARD * j + 2 * k + 1} width)")
            for k in range(FC_CHAIN)
        ] + [None]
        local = hid[b.SHARD * j : b.SHARD * (j + 1)]
        proj_settings = ",".join(
            f'"{b.packed_axis_tag(j % b.PACK_SHARDS, l)}" calc(var({local[l]}) / var(--range-proj))'
            for l in range(b.SHARD)
        )
        once.append(
            f"#f3r{j}{{--range-proj:calc(max(.000001,{','.join(f'abs(var({p}))' for p in local)}) * 1.001)}}"
            f"#f3m{j}{{width:calc(var(--range-proj) * {RANGE_PX}px)}}"
            f"#f3s{j}{{font-variation-settings:{proj_settings}}}"
        )
        prow = "".join(
            f'<i class="f3-row" style="anchor-name:--f3p{j}_{i}">&#x{gproj.codepoint_starts[j] + i:X};</i>'
            for i in range(W)
        )
        bottom = (
            f'<i class="f3-m" id="f3m{j}" style="anchor-name:--f3m{j}"></i>'
            f'<div class="f3-stage" id="f3s{j}">{prow}</div>'
        )
        chain_html, chain_css = _chain(ids, size, bottom, CHAIN_LEVEL)
        once.append(chain_css)
        html.append(chain_html)
        # per-layer GELU decode: level k+1 publishes container k's two values
        for k in range(FC_CHAIN):
            decls = []
            for i, unit in ((b.SHARD * j + 2 * k, "cqw"), (b.SHARD * j + 2 * k + 1, "cqh")):
                raw = f"(100{unit} / 1px * {PX_TO_UNITS} - {int(fc_bases[i])})"
                decls.append(
                    f"{hid[i]}:--gelu(calc({raw} * {num(qfc.scales[i])} * var(--range-fc) + ({num(bfc[i])})))"
                )
            layer_css.append(f"{_publisher(ids[k + 1], CHAIN_LEVEL)}{{{';'.join(decls)}}}")

    # --- out chain: 6 range containers, then 384 value containers, bottom hosts {child}
    ids = [f"f3g{t}" for t in range(RANGE_CHAIN)] + [f"f3o{k}" for k in range(OUT_CHAIN)] + ["f3b"]
    size = [
        (f"anchor-size(--f3m{2 * t} width)", f"anchor-size(--f3m{2 * t + 1} width)")
        for t in range(RANGE_CHAIN)
    ]
    for k in range(OUT_CHAIN):
        wsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
        hsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k + 1} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
        size.append((f"calc({wsum})", f"calc({hsum})"))
    size.append(None)
    # the out chain must hold 768 values: only one element per level fits the parser cap
    chain_html, chain_css = _chain(ids, size, "{child}", 1)
    once.append(chain_css)
    html.append(chain_html)
    html.append("</div>")
    # range publishers are layer-independent
    for t in range(RANGE_CHAIN):
        once.append(
            f"{_publisher(ids[t + 1], 1)}{{{ranges[2 * t]}:calc(100cqw / 1px / {RANGE_PX});"
            f"{ranges[2 * t + 1]}:calc(100cqh / 1px / {RANGE_PX})}}"
        )
    # per-layer output decode (+ residual r)
    for k in range(OUT_CHAIN):
        decls = []
        for i, unit in ((2 * k, "cqw"), (2 * k + 1, "cqh")):
            bases = " + ".join(f"{int(proj_bases[j][i])} * var({ranges[j]})" for j in range(SHARDS_PROJ))
            raw = f"(100{unit} / 1px * {PX_TO_UNITS} - ({bases}))"
            decls.append(f"{outn[i]}:calc(var({r[i]}) + {raw} * {num(qproj.scales[i])} + ({num(bproj[i])}))")
        layer_css.append(f"{_publisher(ids[RANGE_CHAIN + k + 1], 1)}{{{';'.join(decls)}}}")
    return "".join(html), "".join(layer_css), "".join(once)


def chain_depth():
    """Elements added below .f3-mlp on the deepest path (for the 512 parser cap check)."""
    out = 1 + (RANGE_CHAIN + OUT_CHAIN) + 1  # .f3-mlp + containers + #f3b
    fc = 1 + FC_CHAIN * CHAIN_LEVEL + CHAIN_LEVEL + 2  # .f3-mlp + containers(+publishers) + #f3r + .f3-stage + row
    return max(out, fc)


def metadata():
    return {
        "f3ChainMlp": CHAIN_MLP,
        "f3ChainLevel": CHAIN_LEVEL,
        "f3ChainContainers": SHARDS_PROJ * FC_CHAIN + RANGE_CHAIN + OUT_CHAIN,
        "f3ChainAnchors": M + SHARDS_PROJ * W + SHARDS_PROJ,
    }
