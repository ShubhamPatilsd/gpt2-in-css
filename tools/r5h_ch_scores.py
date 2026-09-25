"""R5H (2026-09-24): the attention-score hop read back with `ch` font-metric units (R4X §6.1).

Flag (default ON): R5H_CH_SCORES=0 restores the R4S / view-timeline score transport. When ON
the flag forces R4S_SMALL_HOPS off (both replace the same hop).

Mechanism (work/2026-09-19/R5H.md). Today every (head, slot) score is the advance of the
`dot` glyph of a bilinear `FvsDot{head}` font instance (font-variation-settings = the slot's
latched K list + the live Q list): the glyph is shaped, its `max-content` width is encoded
into a carrier width, and the width is transported back into a `<number>` either through a
view-timeline (combined4) or through an anchor -> size-container chain (R4S). Blink exposes
the advance of glyph U+0030 of an element's *primary font instance* (HVAR applied) directly
to style as the `ch` unit, and a custom property on the element resolves `ch` against the
element's OWN font (E1 #70/#73, R4X §1/§5 arm M). So:

  * fonts: the 12 F4 dot fonts get one extra cmap entry, U+0030 -> `dot` (every other table
    byte-identical; asserted at build), written to R5H/assets-r5h/;
  * per (head, slot) an EMPTY `display:block` element carries today's `font` +
    `font-variation-settings` declarations and
    `--fs-H-S: calc((1ch / 1px - base_px) * var(--fqs-H) * var(--fr-ks-S-H) * 1/(8*coef*unit))`
    (the width decode minus the 262144 / 128 carrier encoding), registered `<number>`
    `inherits:true`;
  * per head the `capacity` slot elements nest (chain) and the chain bottom
    `.fvs-score-reader.fvs-sr-H` hosts head H's softmax declarations and its 64 V rows.
    The 12 chains sit inside the ctx scroller's `.track` (the rows are position:absolute with
    the track as containing block, so their geometry is unchanged); depth grows by
    capacity + 1 instead of R4S's 12*capacity/2 containers.

No shaping, no layout, no containers, no timelines, no gate: the scores, the softmax and the
V-row widths are plain style dependencies of the qkv readback pass in which `.fvs-query` is
restyled, and the V rows are laid out in that pass's layout (ctx readback = next pass), i.e.
5 passes / 2.5 frames per layer like R4S, with RecalcStyleCount flat in the filled positions
(no interleaved container recalcs; R4M §4.1's 70.8*k penalty disappears).
"""

import os
from pathlib import Path

import r4s_small_hops as r4s
from fontTools.ttLib import TTFont


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


CH_SCORES = flag("R5H_CH_SCORES")
if CH_SCORES:
    # R5H replaces R4S's chain for the same hop; the two are mutually exclusive.
    r4s.SMALL_HOPS = False

ASSETS = Path(__file__).resolve().parents[1] / "assets-r5h" / "font-vector-operators-r5h"
ZERO = 0x30
BOTTOM_CLASS = "fvs-score-reader"


def no_score_hop():
    """True when the score hop has neither scroller, timelines, receipt nor gate (R4S or R5H)."""
    return CH_SCORES or r4s.SMALL_HOPS


def head_class(head):
    return f"fvs-sr-{head}"


def _table_bytes(font):
    return {tag: font.getTableData(tag) for tag in font.keys() if tag != "GlyphOrder"}


def ch_dot_font(source):
    """`source` dot font + cmap U+0030 -> the score glyph; every other table byte-identical.

    Built once into ASSETS (name = <source stem>-r5h.woff2) and re-verified on every call.
    """
    source = Path(source)
    ASSETS.mkdir(parents=True, exist_ok=True)
    target = ASSETS / f"{source.stem}-r5h.woff2"
    original = TTFont(source, recalcTimestamp=False)
    unicode_tables = [t for t in original["cmap"].tables if t.isUnicode()]
    if not unicode_tables:
        raise ValueError(f"R5H: {source} has no unicode cmap subtable")
    glyphs = {g for t in unicode_tables for g in t.cmap.values()}
    if len(glyphs) != 1:
        raise ValueError(f"R5H: expected exactly one mapped glyph in {source}, found {sorted(glyphs)}")
    (score_glyph,) = glyphs
    if any(ZERO in t.cmap for t in unicode_tables):
        raise ValueError(f"R5H: {source} already maps U+0030")
    if not target.exists():
        font = TTFont(source, recalcTimestamp=False)
        for table in font["cmap"].tables:
            if table.isUnicode():
                table.cmap[ZERO] = score_glyph
        font.flavor = "woff2"
        staging = target.with_suffix(".tmp.woff2")
        font.save(staging)
        staging.replace(target)
    # verify (always): only cmap differs (+ head.checkSumAdjustment); cmap = original + {U+0030: glyph}
    built = TTFont(target, recalcTimestamp=False)
    before, after = _table_bytes(original), _table_bytes(built)
    if set(before) != set(after):
        raise ValueError(f"R5H: table set changed for {source}: {sorted(set(before) ^ set(after))}")
    for tag in before:
        if tag == "cmap":
            continue
        a, b = before[tag], after[tag]
        if tag == "head":
            # bytes 8..12 = checkSumAdjustment (recomputed on save); everything else must match
            a, b = a[:8] + a[12:], b[:8] + b[12:]
        if a != b:
            raise ValueError(f"R5H: table {tag} changed for {source}")
    for t_old, t_new in zip(original["cmap"].tables, built["cmap"].tables):
        if (t_old.format, t_old.platformID, t_old.platEncID) != (t_new.format, t_new.platformID, t_new.platEncID):
            raise ValueError(f"R5H: cmap subtable layout changed for {source}")
        expected = dict(t_old.cmap)
        if t_old.isUnicode():
            expected[ZERO] = score_glyph
        if dict(t_new.cmap) != expected:
            raise ValueError(f"R5H: cmap subtable {t_new.format}/{t_new.platformID}/{t_new.platEncID} wrong for {source}")
    if built.getGlyphOrder() != original.getGlyphOrder():
        raise ValueError(f"R5H: glyph order changed for {source}")
    return target


def slot_rule(head, slot, size, family, fr_k, base_px, kconst):
    """The (head, slot) score element: today's font declarations + the ch decode."""
    return (
        f".fvs-score-{head}-{slot}{{display:block;font:{size}px {family};line-height:1;font-kerning:none;"
        f"font-variation-settings:var({fr_k}),var(--fvs-query-{head});"
        f"{r4s.field(head, slot)}:calc((1ch / 1px - {base_px:.12g}) * var(--fqs-{head}) * var(--fr-ks-{slot}-{head}) * {kconst:.12g})}}"
    )


def chain_open(head, capacity):
    """Nested slot elements of one head, then the head's softmax bottom (caller emits the rows)."""
    return "".join(f'<div class="fvs-score-{head}-{slot}">' for slot in range(capacity)) + (
        f'<div class="{BOTTOM_CLASS} {head_class(head)}">'
    )


def chain_close(capacity):
    return "</div>" * (capacity + 1)


def manifest(capacity):
    return {
        "r5hChScores": CH_SCORES,
        "r5hScoreElements": 12 * capacity if CH_SCORES else 0,
        "r5hScoreChains": 12 if CH_SCORES else 0,
        "r5hScoreChainDepth": capacity + 1 if CH_SCORES else 0,
    }
