#!/usr/bin/env python3
"""Build a minimal cross-font variation-composition probe.

Two one-axis HVAR faces contribute one glyph each to a fallback run.  Normal
text shaping adds their advances.  The page then contrasts that aggregate run
width with `1ch`, which comes from one face rather than the shaped fallback run.
Runtime output is HTML/CSS/fonts only; the test harness is external.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "cross-shard-font-composition"
FONT_SIZE = 40
UNITS_PER_EM = 1_000
BASE_ADVANCE = 500


def add_zero_mapping(path: Path) -> None:
    """Make `1ch` select shard A's sole HVAR-controlled glyph."""
    font = TTFont(path, recalcTimestamp=False)
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[0x30] = "y000"
    font.recalcTimestamp = False
    font.save(path)


def compress(path: Path) -> None:
    font = TTFont(path, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(path.with_suffix(".woff2"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    shard_a_ttf = OUT / "shard-a.ttf"
    build_direct_font_backend(
        np.asarray([[200]], dtype=np.int16),
        shard_a_ttf,
        base_advance=BASE_ADVANCE,
        codepoint_start=0xE000,
        axis_tags=["A000"],
    )
    add_zero_mapping(shard_a_ttf)
    compress(shard_a_ttf)

    shard_b_ttf = OUT / "shard-b.ttf"
    build_direct_font_backend(
        np.asarray([[300]], dtype=np.int16),
        shard_b_ttf,
        base_advance=BASE_ADVANCE,
        codepoint_start=0xE001,
        axis_tags=["B000"],
    )

    cases = [(0, 0), (1, 0), (0, 1), (1, 1)]
    controls = "".join(
        f'<input type="radio" name="case" id="case-{index}"'
        f'{" checked" if index == 0 else ""}>'
        for index in range(len(cases))
    )
    rules = "".join(
        f'body:has(#case-{index}:checked) .font-stack{{'
        f'font-variation-settings:"A000" {a},"B000" {b}}}'
        for index, (a, b) in enumerate(cases)
    )
    labels = "".join(
        f'<label for="case-{index}">A={a}, B={b}</label>'
        for index, (a, b) in enumerate(cases)
    )

    html = f'''<!doctype html>
<meta charset="utf-8">
<title>Cross-shard font composition probe</title>
<style>
@font-face{{font-family:ShardA;src:url("shard-a.woff2") format("woff2");unicode-range:U+0030,U+E000}}
@font-face{{font-family:ShardB;src:url("shard-b.woff2") format("woff2");unicode-range:U+E001}}
html,body{{margin:0}}
body{{font:16px system-ui}}
input{{position:fixed;left:-10000px}}
label{{display:inline-block;margin:.5rem;padding:.35rem .55rem;border:1px solid}}
.font-stack{{font-family:ShardA,ShardB;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1}}
#sum{{display:inline-block;width:max-content;white-space:pre;anchor-name:--sum}}
#single-face-metric{{display:block;width:1ch;height:4px;background:#e55}}
#bridge{{position:absolute;left:0;top:140px;position-anchor:--sum;
width:anchor-size(--sum width);container-type:inline-size}}
#bridge-value{{font-size:100cqi;line-height:1}}
{rules}
</style>
{controls}
<nav>{labels}</nav>
<main class="font-stack">
  <span id="sum">&#xE000;&#xE001;</span>
  <span id="single-face-metric"></span>
  <div id="bridge"><span id="bridge-value">.</span></div>
</main>
'''
    (OUT / "index.html").write_text(html)

    reference = {
        "fontSize": FONT_SIZE,
        "unitsPerEm": UNITS_PER_EM,
        "cases": [
            {
                "a": a,
                "b": b,
                "fallbackRunWidth": (2 * BASE_ADVANCE + 200 * a + 300 * b)
                * FONT_SIZE
                / UNITS_PER_EM,
                "chWidth": (BASE_ADVANCE + 200 * a) * FONT_SIZE / UNITS_PER_EM,
            }
            for a, b in cases
        ],
        "structuralPoint": (
            "fallback shaping sums both face advances; 1ch observes only shard A. "
            "The aggregate becomes reusable only after #bridge materializes it as "
            "a CSS sizing/container boundary."
        ),
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")


if __name__ == "__main__":
    main()
