#!/usr/bin/env python3
"""Build a TTC whose faces select HVAR output pairs through distinct cmaps."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "feature-metric-readback"
OUT = ROOT / "experiments" / "ttc-metric-bank"


def set_names(font: TTFont, pair: int) -> str:
    family = f"CSS Metric Pair {pair:03d}"
    postscript = f"CSSMetricPair{pair:03d}-Regular"
    names = font["name"]
    for record in list(names.names):
        if record.nameID in (1, 2, 3, 4, 6, 16, 17):
            names.removeNames(
                record.nameID, record.platformID, record.platEncID, record.langID
            )
    for platform, encoding, language in ((3, 1, 0x409), (1, 0, 0)):
        names.setName(family, 1, platform, encoding, language)
        names.setName("Regular", 2, platform, encoding, language)
        names.setName(f"{family} Regular", 3, platform, encoding, language)
        names.setName(f"{family} Regular", 4, platform, encoding, language)
        names.setName(postscript, 6, platform, encoding, language)
    return postscript


def remap_face(font: TTFont, pair: int) -> str:
    zero = f"zero.alt{pair:03d}"
    water = f"water.alt{pair:03d}"
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[0x30] = zero
            table.cmap[0x6C34] = water
    return set_names(font, pair)


def build_html(reference: dict, postscript_names: list[str]) -> str:
    pairs = reference["pairs"]
    font_size = reference["font_size"]
    units = reference["units_per_em"]
    base = reference["base"]
    settings = ",".join(
        f'"X{index:03d}" {value:g}'
        for index, value in enumerate(reference["inputs"])
    )
    faces = "".join(
        f'@font-face{{font-family:F{pair};src:url("metric-bank.ttc?face={pair}#{name}") '
        'format("collection")}'
        for pair, name in enumerate(postscript_names)
    )
    properties = "".join(
        f'@property --o{output:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for output in range(pairs * 2)
    )
    rules = "".join(
        f'.pair-{pair:03d}{{font-family:F{pair};'
        f'--o{2 * pair:03d}:calc(1ch / 1px * {units} / {font_size} - {base});'
        f'--o{2 * pair + 1:03d}:calc(1ic / 1px * {units} / {font_size} - {base})}}'
        for pair in range(pairs)
    )
    child = '<output id="result">ready</output>'
    for pair in reversed(range(pairs)):
        child = f'<i class="pair pair-{pair:03d}">{child}</i>'
    return f'''<!doctype html><meta charset="utf-8"><title>TTC metric bank</title>
<style>{faces}{properties}
.root{{font-size:{font_size}px;font-variation-settings:{settings}}}
.pair{{display:contents}}{rules}
#result{{font:14px monospace}}
</style><div class="root">{child}</div>
'''


def build_static_collection(base: TTFont, pairs: int) -> tuple[TTCollection, list[str], list[float]]:
    """Build a control TTC with no variation tables and distinct static advances."""
    static_base = copy.deepcopy(base)
    for tag in ("fvar", "HVAR", "STAT", "GSUB"):
        if tag in static_base:
            del static_base[tag]
    expected = []
    for pair in range(pairs):
        zero_advance = 700 + pair * 3
        water_advance = 1_100 + pair * 5
        static_base["hmtx"].metrics[f"zero.alt{pair:03d}"] = (zero_advance, 0)
        static_base["hmtx"].metrics[f"water.alt{pair:03d}"] = (water_advance, 0)
        expected.extend((float(zero_advance), float(water_advance)))

    fonts = []
    postscript_names = []
    for pair in range(pairs):
        font = copy.deepcopy(static_base)
        postscript_names.append(remap_face(font, pair))
        font.recalcTimestamp = False
        fonts.append(font)
    collection = TTCollection()
    collection.fonts = fonts
    return collection, postscript_names, expected


def build_static_html(postscript_names: list[str]) -> str:
    pairs = len(postscript_names)
    font_size = 1_000
    faces = "".join(
        f'@font-face{{font-family:S{pair};src:url("static-bank.ttc#{name}") '
        'format("collection")}'
        for pair, name in enumerate(postscript_names)
    )
    properties = "".join(
        f'@property --s{output:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for output in range(pairs * 2)
    )
    rules = "".join(
        f'.pair-{pair:03d}{{font-family:S{pair};'
        f'--s{2 * pair:03d}:calc(1ch / 1px * 1000 / {font_size});'
        f'--s{2 * pair + 1:03d}:calc(1ic / 1px * 1000 / {font_size})}}'
        for pair in range(pairs)
    )
    child = '<output id="result">ready</output>'
    for pair in reversed(range(pairs)):
        child = f'<i class="pair pair-{pair:03d}">{child}</i>'
    return f'''<!doctype html><meta charset="utf-8"><title>Static TTC face-selection control</title>
<style>{faces}{properties}
.root{{font-size:{font_size}px}}.pair{{display:contents}}{rules}
#result{{font:14px monospace}}
</style><div class="root">{child}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    base = TTFont(SOURCE / "feature-rows.ttf", recalcTimestamp=False)
    fonts = []
    postscript_names = []
    for pair in range(reference["pairs"]):
        font = copy.deepcopy(base)
        postscript_names.append(remap_face(font, pair))
        font.recalcTimestamp = False
        fonts.append(font)
    collection = TTCollection()
    collection.fonts = fonts
    collection.save(OUT / "metric-bank.ttc", shareTables=True)
    static_collection, static_names, static_expected = build_static_collection(
        base, reference["pairs"])
    static_collection.save(OUT / "static-bank.ttc", shareTables=True)
    (OUT / "index.html").write_text(build_html(reference, postscript_names))
    (OUT / "static.html").write_text(build_static_html(static_names))
    (OUT / "static-reference.json").write_text(
        json.dumps({"expected": static_expected}, indent=2) + "\n")
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "faces": len(fonts),
        "ttc_bytes": (OUT / "metric-bank.ttc").stat().st_size,
        "static_ttc_bytes": (OUT / "static-bank.ttc").stat().st_size,
        "source_ttf_bytes": (SOURCE / "feature-rows.ttf").stat().st_size,
        "html_bytes": (OUT / "index.html").stat().st_size,
    })


if __name__ == "__main__":
    main()
