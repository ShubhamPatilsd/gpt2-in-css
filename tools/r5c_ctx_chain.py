"""R5C (2026-09-24): the 768-value ctx hop (attention output -> proj input) leaves view-timelines.

Flag (default ON): R5C_CTX_CHAIN=0 restores combined7's ctx transport (`.cache-bridge-source`
scroller with 768 + 1 view-timeline carriers, 12 `.cache-bridge-cN` readers, receipt + gate,
`.shared-attn` with the 768-axis list and 768 three-glyph rows). Requires R4S_SMALL_HOPS (the V
rows already live inside the score chain's bottom) and the font-vector codec.

Mechanism (work/2026-09-19/R5C.md). The 768 V rows (`.fvs-value-row`, width = 262144 + 128*ctx_i)
become in-flow anchor rows (`anchor-name:--r5ca-i`) of a plain block stage inside `.fvs-softmax`.
The attn matvec's three 256-axis shard fonts each need their 256 axis values on ONE element, so
three PARALLEL chains of 128 `position:fixed; container-type:size` containers hang off the score
chain's bottom (`.fvs-score-reader`): chain s, container k takes `width/height:anchor-size(--r5ca-{256s+2k},{+1} width)`,
container k+1 publishes container k's two values as the registered inherited numbers
`--ctx-i:calc((100cqw / 1px - 262144) / 128)` (cqh for the second), the bottom `.r5c-xb{s}`
publishes the last two, declares the R2C quotients `--fq-attn-i:calc(var(--ctx-i) / var(--range-attn))`
for its 256 inputs and the shard's 256-axis `font-variation-settings` (inherited by its 768 in-flow
single-glyph rows `<i class="r5c-g" style="anchor-name:--r5cg-{s}-{i}">`, font b{L}attnS{s}).
The fan-in (output i = the sum of its three shard glyph advances, an inline run today) becomes, per
output, ONE `position:fixed` scroller (`.scroller.r5c-sum`) whose own width is
`calc(anchor-size(--r5cg-0-i width) + anchor-size(--r5cg-1-i width) + anchor-size(--r5cg-2-i width))`
with a constant-width (V) view-timeline subject inside (track 300 %): progress p = S/(S+V), the reader
decodes S = V*p/(1-p) (today: w = V/p - V; same 6-significant-digit sensitivity 4V*dp at S ~ V).
The whole `.shared-attn` stage (sums, marker scroller, readers, receipt, gate and everything below)
sits inside shard chain 2's bottom, so its fixed scrollers are laid out AFTER the three glyph stages
(nested out-of-flow roots are laid out in nesting order; F3.md §3b / F3b lint rule) and the readers
inherit `--range-attn`.

`--range-attn` (today max|ctx|*1.001 on `.shared-attn`, which needs all 768 values on one element)
becomes a bound computed on the softmax element from numbers it already has: ctx_h = sum_s p_s v_s
with p_s >= 0, sum p_s = 1, so |ctx_{h,i}| <= max_s |v_{s,i}| <= max_s vs_s = --fb-h (the per-head
maximum of the stored V scales); `--range-attn:calc((max(.000001,var(--fb-0),..,var(--fb-11)) + .0002) * 1.001)`
(+2e-4 covers the chain's 1/(64*128) rounding). Looser than max|ctx| by the averaging factor, so the
F2Dot14 axis quantisation of ctx/range is coarser by that factor (~3e-5*range absolute) — still far below
today's 6-digit timeline transport error of ~5e-3 per ctx value, which the chain removes (LayoutUnit exact).

Passes per layer: [proj+S1 | qkv+scores+V+ctx chains+attn glyphs+sums] [attn | fc] = 4 = 2.0 frames
(combined7: 5 = 2.5), -769 carrier animations and -12 readers -1 receipt/gate per layer.
"""

import os
import re

import r2c_hoist as r2c

W, SHARD, HEADS = 768, 256, 12
OFFSET, SCALE = 262144, 128  # the ctx carrier encoding (build_hybrid_twelve_block.bridge)


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


CTX_CHAIN = flag("R5C_CTX_CHAIN")

STAGE_CLASS = "r5c-ctx-stage"  # block stage holding the 768 V anchor rows
ROW_CLASS = "r5c-ctx-a"  # added to each .fvs-value-row
CHAIN_CLASS = "r5c-x"  # chain container
BOTTOM_CLASS = "r5c-xb"  # chain bottom (in-flow)
GLYPH_STAGE_CLASS = "r5c-gs"  # in-flow block with the shard's 768 glyph rows
GLYPH_CLASS = "r5c-g"
SUMS_CLASS = "r5c-sums"  # wrapper of the 768 sum scrollers + the marker scroller
SUM_CLASS = "r5c-sum"  # fixed scroller whose width is the shard-glyph sum
MARK_CLASS = "r5c-mark"  # ordinary fixed scroller for the attn generation marker

# set by build_hybrid_twelve_block.matvec (attn) before browser_gpt2_font_vector_cache.attention()
ATTN_GROUP = {}


def ctx_anchor(i):
    return f"--r5ca-{i:03d}"


def glyph_anchor(shard, i):
    return f"--r5cg-{shard}-{i:03d}"


def decode(unit):
    return f"calc((100{unit} / 1px - {OFFSET}) / {SCALE})"


def record_attn_group(layer, group):
    """The glyph rows are layer independent: same shard count and codepoints for every layer."""
    info = (len(group.names), tuple(group.codepoint_starts), group.output_count)
    if ATTN_GROUP and ATTN_GROUP["info"] != info:
        raise ValueError(f"R5C: attn font group of layer {layer} differs from layer 0: {info} vs {ATTN_GROUP['info']}")
    ATTN_GROUP["info"] = info


def shards():
    if not ATTN_GROUP:
        raise ValueError("R5C: attention() called before the attn matvec recorded its font group")
    return ATTN_GROUP["info"][0]


def context_carriers():
    """Replacement for bridge()'s source: the same carrier text attention() rewrites into V rows,
    with the anchor name in the timeline slot (finish_value_stage turns it into anchor-name)."""
    rows = "".join(
        f'<i class="metric" style="width:calc({OFFSET}px + var(--ctx-{i:03d}) * {SCALE}px);view-timeline:{ctx_anchor(i)} inline"></i>'
        for i in range(W)
    )
    return f'<div class="{STAGE_CLASS}">{rows}</div>'


def finish_value_stage(html):
    """After attention()'s row rewrite: in-flow anchor rows (no .metric = no position:absolute)."""
    new, count = re.subn(
        r'<span class="metric fvs-value-row" style="width:([^"]*);view-timeline:(--r5ca-\d{3}) inline">',
        r'<span class="fvs-value-row ' + ROW_CLASS + r'" style="anchor-name:\2;width:\1">',
        html,
    )
    if count != W:
        raise ValueError(f"R5C: expected {W} V rows to convert, found {count}")
    if "view-timeline" in new or 'class="metric' in new:
        raise ValueError("R5C: leftover timeline carriers in the V stage")
    return new


def range_rule():
    """--range-attn as the softmax element's bound (see module docstring)."""
    fbs = ",".join(f"var(--fb-{h})" for h in range(HEADS))
    return f".fvs-score-reader{{--range-attn:calc((max(.000001,{fbs}) + .0002) * 1.001)}}"


def settings(shard):
    """The shard's 256-axis list with R2C's hoisted quotients (same text matvec would emit)."""
    from build_gpt2_block_css import packed_axis_tag

    return ",".join(
        f'"{packed_axis_tag(shard, local)}" var(--fq-attn-{SHARD * shard + local:03d})'
        for local in range(SHARD)
    )


def quotients(shard):
    return ";".join(
        f"--fq-attn-{i:03d}:calc(var(--ctx-{i:03d}) / var(--range-attn))"
        for i in range(SHARD * shard, SHARD * (shard + 1))
    )


def chains(child="{child}"):
    """Three parallel 128-deep chains hanging off the score reader; returns (html, css).

    Chain s, container k: width/height = anchors 256s+2k, 256s+2k+1; container k+1 publishes
    container k's two values; the bottom publishes the last two, hosts the quotients + shard
    settings, the glyph stage, and (shard 2) the {child} placeholder = the attn stage and below."""
    count, codepoints, outputs = ATTN_GROUP["info"]
    if count * SHARD != W or outputs != W:
        raise ValueError(f"R5C: expected {W // SHARD} shards of {SHARD} axes and {W} outputs, got {count} / {outputs}")
    levels = SHARD // 2
    css = [
        f".{STAGE_CLASS}{{display:block;width:1px;height:1px;overflow:clip;visibility:hidden}}",
        f".{ROW_CLASS}{{display:flex;position:static;height:1px;overflow:clip;min-width:0}}",
        f".{CHAIN_CLASS}{{position:fixed;left:0;top:-300000px;container-type:size}}",
        f".{BOTTOM_CLASS}{{display:block;width:1px;height:1px;font-size:512px;font-style:normal;font-weight:normal;line-height:1;font-kerning:none;white-space:pre}}",
        f".{GLYPH_STAGE_CLASS}{{display:block;width:1px;height:1px;overflow:clip;visibility:hidden}}",
        f".{GLYPH_CLASS}{{display:block;width:max-content;height:1px;overflow:clip;min-width:0;white-space:pre;font-style:normal}}",
        f".{SUMS_CLASS}{{display:block;width:1px;height:1px}}",
        f".{SUM_CLASS}>.track{{width:300%}}",
        r2c.private_regs(f"--fq-attn-{i:03d}" for i in range(W)),
    ]
    html = []
    for s in range(count):
        for k in range(levels):
            i0, i1 = SHARD * s + 2 * k, SHARD * s + 2 * k + 1
            css.append(
                f"#{CHAIN_CLASS}{s}-{k}{{width:anchor-size({ctx_anchor(i0)} width);height:anchor-size({ctx_anchor(i1)} width)}}"
            )
            if k:
                css.append(
                    f"#{CHAIN_CLASS}{s}-{k}{{--ctx-{i0 - 2:03d}:{decode('cqw')};--ctx-{i1 - 2:03d}:{decode('cqh')}}}"
                )
            html.append(f'<div class="{CHAIN_CLASS}" id="{CHAIN_CLASS}{s}-{k}">')
        last0, last1 = SHARD * (s + 1) - 2, SHARD * (s + 1) - 1
        css.append(
            f".{BOTTOM_CLASS}{s}{{--ctx-{last0:03d}:{decode('cqw')};--ctx-{last1:03d}:{decode('cqh')};"
            f"{quotients(s)};font-variation-settings:{settings(s)}}}"
        )
        glyphs = "".join(
            f'<i class="{GLYPH_CLASS}" style="anchor-name:{glyph_anchor(s, i)}">&#x{codepoints[s] + i:X};</i>'
            for i in range(W)
        )
        html.append(
            f'<div class="{BOTTOM_CLASS} {BOTTOM_CLASS}{s}"><div class="{GLYPH_STAGE_CLASS}">{glyphs}</div>'
            + (child if s == count - 1 else "")
            + "</div>"
            + "</div>" * levels
        )
    return "".join(html), "".join(css)


def sum_carrier(i, timeline, shard_count):
    """One output's carrier: a fixed scroller as wide as the sum of its shard glyph advances,
    with a constant-width subject (per-layer width rule from matvec) inside."""
    total = " + ".join(f"anchor-size({glyph_anchor(s, i)} width)" for s in range(shard_count))
    return (
        f'<div class="scroller {SUM_CLASS}" style="width:calc({total})"><div class="track">'
        f'<i class="metric" style="view-timeline:{timeline} inline"></i></div></div>'
    )


def marker_carrier(width_expression, timeline):
    return (
        f'<div class="scroller {MARK_CLASS}"><div class="track">'
        f'<i class="metric" style="width:{width_expression};view-timeline:{timeline} inline"></i></div></div>'
    )


def stage_css(stem, viewport):
    """Per-layer (specialize()d) rules: subject width V and the marker scroller's V / 3V."""
    return (
        f".{stem} .{SUM_CLASS} .metric{{width:{viewport}px}}"
        f".{stem} .{MARK_CLASS}{{width:{viewport}px}}.{stem} .{MARK_CLASS}>.track{{width:{3 * viewport}px}}"
    )


def raw_width(viewport, progress):
    """Scroller width S from the subject's progress p = S / (S + V)."""
    return f"({viewport} * var({progress}) / (1 - var({progress})))"


def manifest():
    return {
        "r5cCtxChain": CTX_CHAIN,
        "r5cCtxChains": W // SHARD if CTX_CHAIN else 0,
        "r5cCtxChainContainers": W // 2 if CTX_CHAIN else 0,
        "r5cCtxAnchors": W if CTX_CHAIN else 0,
        "r5cGlyphAnchors": W * (W // SHARD) if CTX_CHAIN else 0,
        "r5cSumScrollers": W if CTX_CHAIN else 0,
    }
