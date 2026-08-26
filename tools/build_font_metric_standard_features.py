#!/usr/bin/env python3
"""Test whether CSS font units honor standard OpenType substitutions."""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "feature-metric-readback"
OUT = ROOT / "experiments" / "font-metric-standard-features"
FONT_SIZE = 512

CASES = [
    ("default", "", None),
    ("salt", 'font-feature-settings:"salt" 1', 0),
    ("pnum", "font-variant-numeric:proportional-nums", 1),
    ("tnum", "font-variant-numeric:tabular-nums", 2),
    ("zero", "font-variant-numeric:slashed-zero", 3),
    ("sups", "font-variant-position:super", 4),
    ("subs", "font-variant-position:sub", 5),
    ("ss01", 'font-feature-settings:"ss01" 1', 6),
    ("cv01", 'font-feature-settings:"cv01" 1', 7),
    ("fwid", "font-variant-east-asian:full-width", 8),
    ("pwid", 'font-feature-settings:"pwid" 1', 9),
    ("trad", "font-variant-east-asian:traditional", 10),
    ("smpl", "font-variant-east-asian:simplified", 11),
]


def feature(tag: str, pair: int) -> str:
    return (
        f"feature {tag} {{ sub zero by zero.alt{pair:03d}; "
        f"sub water by water.alt{pair:03d}; }} {tag};"
    )


def build_font(destination: Path) -> None:
    font = TTFont(SOURCE / "feature-rows.ttf", recalcTimestamp=False)
    if "GSUB" in font:
        del font["GSUB"]
    features = [
        "feature salt { sub zero from [" +
        " ".join(f"zero.alt{index:03d}" for index in range(64)) +
        "]; sub water from [" +
        " ".join(f"water.alt{index:03d}" for index in range(64)) +
        "]; } salt;"
    ]
    for tag, pair in (
        ("pnum", 1), ("tnum", 2), ("zero", 3), ("sups", 4),
        ("subs", 5), ("ss01", 6), ("cv01", 7), ("fwid", 8),
        ("pwid", 9), ("trad", 10), ("smpl", 11),
    ):
        features.append(feature(tag, pair))
    addOpenTypeFeaturesFromString(font, "\n".join(features))
    font.recalcTimestamp = False
    font.save(destination)


def build_html(reference: dict) -> str:
    settings = ",".join(
        f'"X{index:03d}" {value:g}' for index, value in enumerate(reference["inputs"]))
    rules = "".join(
        f'.{name}{{{declaration}}}' for name, declaration, _ in CASES if declaration)
    rows = "".join(
        f'<div class="case {name}" id="{name}"><i class="ch"></i><i class="ic"></i>'
        '<span class="glyph-zero">0</span><span class="glyph-water">水</span></div>'
        for name, _, _ in CASES
    )
    return f'''<!doctype html><meta charset="utf-8"><title>Font-unit standard-feature probe</title>
<style>
@font-face{{font-family:FeatureUnits;src:url("standard-features.ttf") format("truetype")}}
.root{{font-family:FeatureUnits;font-size:{FONT_SIZE}px;font-variation-settings:{settings}}}
.case{{height:1px}}.ch{{display:inline-block;width:1ch}}.ic{{display:inline-block;width:1ic}}
.glyph-zero,.glyph-water{{display:inline-block}}{rules}
</style><div class="root">{rows}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    build_font(OUT / "standard-features.ttf")
    (OUT / "index.html").write_text(build_html(reference))
    (OUT / "reference.json").write_text(json.dumps({
        "font_size": FONT_SIZE,
        "units_per_em": reference["units_per_em"],
        "base": reference["base"],
        "expected": reference["expected"],
        "cases": [
            {"name": name, "pair": pair} for name, _, pair in CASES
        ],
    }, indent=2) + "\n")
    print({"font_bytes": (OUT / "standard-features.ttf").stat().st_size,
           "html_bytes": (OUT / "index.html").stat().st_size})


if __name__ == "__main__":
    main()
