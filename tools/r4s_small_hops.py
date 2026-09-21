"""R4S (2026-09-20): the attention-score hop (96 values + stamp) leaves view-timelines.

Flag (default ON): R4S_SMALL_HOPS=0 restores combined4's score transport (97 view-timeline
carriers in a scroller, `.fvs-score-reader` with 96 animations, `.fvs-score-receipt` +
`.fvs-score-gate`).

Mechanism (work/2026-09-19/R4S.md): a view-timeline hop costs one style pass and half a
frame (two passes per frame, R3F §0). The score hop is the only per-layer hop with <= 500
values (R4S.md §1), so it fits ONE anchor -> size-container chain (F3.md §2, F3b: <= 250
containers, position:fixed only, anchors earlier in tree order). The 96 score glyphs become
in-flow block rows (`anchor-name:--fsa-H-S`) of a fixed stage; 12*capacity/2 nested
`position:fixed; container-type:size` containers take `width/height:anchor-size(...)`
from two carriers each, and each container publishes its PARENT's two sizes as the
registered numbers `--fs-H-S:calc((100cqw / 1px - 262144) / 128)` (cq units resolve
against the nearest ancestor container; the chain bottom `.fvs-score-reader` publishes the
last two and computes the softmax exactly as before). Everything resolves inside the qkv
readback pass's layout (interleaved container recalcs), the V rows are laid out in that
same layout, and the ctx readback becomes the frame's second pass:

    before  [proj+S1 | qkv] [scores | ctx] [attn | fc]              = 6 passes = 3.0 frames/layer
    after   [proj+S1 | qkv+scores] [ctx | attn] [fc | proj+S1'] ... = 5 passes = 2.5 frames/layer

The carrier width expression (262144px + 128 * score, calc-size on the glyph advance) is
byte-identical to combined4's, so the laid-out widths are the same LayoutUnits; only the
width -> number transport changes: exact LayoutUnit (1/64 px -> 1.2e-4 in score units)
instead of the timeline's float progress. No gate is needed: the scores are never stale
relative to the glyphs they are read from (same layout), and the qkv gate above still
closes the whole attention subtree in S1 (R3R §1.1 cascade).
"""

import os


def flag(name):
    return os.environ.get(name, "1") not in ("0", "false", "no", "off")


SMALL_HOPS = flag("R4S_SMALL_HOPS")

# the score carrier encoding (browser_gpt2_font_vector_cache.attention), unchanged
OFFSET = 262144
SCALE = 128

STAGE_CLASS = "fvs-score-stage"
ROW_CLASS = "fvs-score-a"
CHAIN_CLASS = "fvs-sc"
BOTTOM_CLASS = "fvs-score-reader"


def anchor(head, slot):
    return f"--fsa-{head}-{slot}"


def field(head, slot):
    return f"--fs-{head}-{slot}"


def decode(unit):
    return f"calc((100{unit} / 1px - {OFFSET}) / {SCALE})"


def carrier(head, slot, cls, glyph):
    """In-flow anchor row for one (head, slot) score glyph; `cls` keeps the font/width rule."""
    return f'<i class="{ROW_CLASS} {cls}" style="anchor-name:{anchor(head, slot)}">{glyph}</i>'


def stage(carriers):
    return f'<div class="{STAGE_CLASS}">{"".join(carriers)}</div>'


def chain(pairs):
    """Nested fixed size containers over the ordered (head, slot) pairs.

    Returns (open_html, close_html, css). Container k sizes itself from carriers 2k
    (width) and 2k+1 (height); container k+1 publishes container k's two values; the
    bottom element (class BOTTOM_CLASS, emitted by the caller inside open/close)
    publishes the last two.
    """
    if len(pairs) % 2:
        raise ValueError("R4S: the score chain needs an even number of carriers")
    levels = len(pairs) // 2
    if levels > 250:
        raise ValueError("R4S: more than 250 containers in one chain (F3.md §2 cap)")
    css = [
        f".{STAGE_CLASS}{{position:fixed;left:0;top:-60000px;width:1px;height:1px;overflow:clip;visibility:hidden}}",
        f".{ROW_CLASS}{{display:block;height:1px;overflow:clip;min-width:0;white-space:pre;font-style:normal}}",
        f".{CHAIN_CLASS}{{position:fixed;left:0;top:-300000px;container-type:size}}",
        f".{BOTTOM_CLASS}{{display:block;width:1px;height:1px}}",
    ]
    html = []
    for k in range(levels):
        (h0, s0), (h1, s1) = pairs[2 * k], pairs[2 * k + 1]
        css.append(
            f"#{CHAIN_CLASS}{k}{{width:anchor-size({anchor(h0, s0)} width);height:anchor-size({anchor(h1, s1)} width)}}"
        )
        if k:
            (p0, q0), (p1, q1) = pairs[2 * k - 2], pairs[2 * k - 1]
            css.append(f"#{CHAIN_CLASS}{k}{{{field(p0, q0)}:{decode('cqw')};{field(p1, q1)}:{decode('cqh')}}}")
        html.append(f'<div class="{CHAIN_CLASS}" id="{CHAIN_CLASS}{k}">')
    (p0, q0), (p1, q1) = pairs[-2], pairs[-1]
    css.append(f".{BOTTOM_CLASS}{{{field(p0, q0)}:{decode('cqw')};{field(p1, q1)}:{decode('cqh')}}}")
    return "".join(html), "</div>" * levels, "".join(css)


def manifest(capacity):
    return {
        "r4sSmallHops": SMALL_HOPS,
        "r4sScoreChainContainers": 12 * capacity // 2 if SMALL_HOPS else 0,
        "r4sScoreAnchors": 12 * capacity if SMALL_HOPS else 0,
    }
