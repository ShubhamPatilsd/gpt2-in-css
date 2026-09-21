"""R4W (2026-09-21): make the per-position allocation of the capacity-32 V path
small and state-independent WITHOUT changing numerics (R4V §5.1 fix).

Background (R4V §2): every style pass re-substitutes the 65-axis V list into each
of the 768·p filled V leaves (`font-variation-settings:var(--fr-v-S-H),"P000" 1`)
because Blink re-does var() substitution for every element it restyles — the
substituted text is copied, re-tokenised and re-parsed per leaf per pass, then
converted to a FontVariationSettings and hashed for the font lookup. That is
≈1 KB of text + a 65-entry CSSValueList + a FontVariationSettings per filled
leaf per pass, ∝ p, while the live heap is constant → GC/purge work ∝ p.

  R4W_V_PRECAT=1 | wrapper (default)
      Fallback-family structure with the WIDTHS weight kept: one @font-face per
      KV slot (the v2 value operator with its 64 V axes retagged to that slot's
      private tags V{S·64+i} and its cmap shifted by S·64, `unicode-range`
      gated), one head wrapper `.fvs-value-head-H{font:1024px FvsValueSlot0,…;
      font-variation-settings:var(--fr-v-0-H),…,var(--fr-v-31-H),"P000" 1}`
      around the head's 64 rows, and leaves that carry NO font property at all:
      `.fvs-v-H-S{width:calc-size(max-content,calc(base+(size-base)*var(--fw-H-S)));
      min-width:0;flex:none}` with the character U+F5800+S·64+i selecting the
      slot font through unicode-range. The leaf inherits the wrapper's Font by
      pointer (no substitution, no parse, no FontDescription hash); the 65·p-axis
      list is substituted and parsed 12× per pass (once per head) instead of
      768·p×. The latched lists carry per-slot tags (the live list picks the
      write slot's tags with if(style(--fvs-write-slot:S))), so the same numbers
      reach the same operator axes: identical shaped advances, identical
      LayoutUnit snapping, identical row sums → exact w.r.t. combined4-c32c.
  R4W_V_PRECAT=alias
      R4V §5.1(a) literally: the latched field is written as
      `--fc-v-S-H:var(--fvs-live-v-H),"P000" 1` (complete value, latched once) and
      the leaf is `font-variation-settings:var(--fr-v-S-H)` (single var()).
      Exact, but saves only the 10-byte literal per leaf per pass (Blink still
      copies + re-parses the substituted list per leaf), kept for measurement.
  R4W_V_PRECAT=0
      combined4-c32c behaviour.
"""

import hashlib
import os
import re
import tempfile
from pathlib import Path

from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont

DIM = 64
ASSETS = Path(__file__).resolve().parents[1] / "assets-r4w" / "font-vector-operators-r4w"
# cmap is shifted on purpose; everything that determines advances is protected.
PROTECTED = ("HVAR", "hmtx", "glyf", "loca", "maxp", "hhea")


def mode():
    value = os.environ.get("R4W_V_PRECAT", "1").strip().lower()
    if value in ("0", "false", "no", "off"):
        return "off"
    if value in ("1", "true", "yes", "on", "wrapper"):
        return "wrapper"
    if value == "alias":
        return "alias"
    raise ValueError(f"R4W_V_PRECAT={value!r}: expected 0|1|wrapper|alias")


# How the write slot's tags get into the latched list: "if" = one --fvs-live-v-H per head
# with if(style(--fvs-write-slot:S):…) branches (default); "lists" = 32 per-slot lists
# --fvs-live-v-H-S referenced by the per-slot write rules (fallback if if() misbehaves).
LIVE_V = os.environ.get("R4W_LIVE_V", "if").strip().lower()
if LIVE_V not in ("if", "lists"):
    raise ValueError("R4W_LIVE_V must be if|lists")


def slot_tag(slot, coordinate):
    """Private per-slot V tags V000..VFFF (slot*64 + i), as fallback_value_fonts."""
    return f"V{slot * DIM + coordinate:03X}"


def slot_fonts(source, capacity, codepoint_base):
    """[(path, unicode_start)] per slot: the v2 value operator (P000 + 64 axes) with
    the 64 V axes retagged to the slot's tags and the cmap shifted by slot*64.
    HVAR/hmtx/glyf/loca/maxp/hhea are asserted byte-identical to the source."""
    if not 1 <= capacity <= 64:
        raise ValueError("R4W slot fonts support 1–64 slots")
    ASSETS.mkdir(parents=True, exist_ok=True)
    source = Path(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    result = []
    for slot in range(capacity):
        target = ASSETS / f"value-s{slot}-{digest}-r4w.woff2"
        if not target.exists():
            font = TTFont(source, recalcTimestamp=False)
            protected = {tag: font.getTableData(tag) for tag in PROTECTED if tag in font}
            axes = font["fvar"].axes
            if axes[0].axisTag != "P000" or len(axes) != DIM + 1:
                raise ValueError(f"Expected P000 + {DIM} axes in {source}, found {[a.axisTag for a in axes[:3]]}…")
            for i, axis in enumerate(axes[1:]):
                axis.axisTag = slot_tag(slot, i)
            original_cmap = None
            for table in font["cmap"].tables:
                if table.isUnicode():
                    original_cmap = dict(table.cmap)
                    table.cmap = {code + slot * DIM: glyph for code, glyph in table.cmap.items()}
            if not original_cmap or min(original_cmap) != codepoint_base or len(original_cmap) != DIM:
                raise ValueError("Unexpected value-operator cmap")
            for name_id in (1, 3, 4, 6):
                font["name"].setName(f"FvsValueSlot{slot}R4W", name_id, 3, 1, 0x409)
            buildStatTable(
                font,
                [
                    {"tag": a.axisTag, "name": a.axisNameID, "ordering": i}
                    for i, a in enumerate(font["fvar"].axes)
                ],
            )
            with tempfile.NamedTemporaryFile(dir=ASSETS, suffix=".woff2", delete=False) as staging:
                temporary = Path(staging.name)
            try:
                font.flavor = "woff2"
                font.save(temporary)
                checked = TTFont(temporary, recalcTimestamp=False)
                for tag, original in protected.items():
                    if checked.getTableData(tag) != original:
                        raise ValueError(f"{tag} changed while retagging slot {slot}")
                shifted = checked.getBestCmap()
                if {c - slot * DIM: g for c, g in shifted.items()} != original_cmap:
                    raise ValueError(f"cmap shift wrong for slot {slot}")
                if [a.axisTag for a in checked["fvar"].axes] != ["P000"] + [slot_tag(slot, i) for i in range(DIM)]:
                    raise ValueError(f"fvar tags wrong for slot {slot}")
                temporary.replace(target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        result.append((target, codepoint_base + slot * DIM))
    return result
