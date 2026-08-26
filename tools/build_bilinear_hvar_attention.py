#!/usr/bin/env python3
"""Build live Q·K attention scores with bilinear HVAR variation regions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from build_matrix_backend_prototypes import build_master, output_glyph


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "bilinear-hvar-attention"
HEAD_WIDTH = 64
VALUE_MAX = 31
PRODUCT_SCALE = VALUE_MAX * VALUE_MAX
UNITS_PER_EM = 1_000
FONT_SIZE = 1_000
CASES = 2
VARIANTS = {
    "exact4": {"shardWidth": 16, "delta": PRODUCT_SCALE, "baseAdvance": 16_000},
    # Chromium clamps an individual glyph advance at roughly 32,767 font
    # units. These variants trade precision for fewer glyphs while keeping
    # both sides of the signed dot product inside that limit.
    "scaled2": {"shardWidth": 32, "delta": 511, "baseAdvance": 16_384},
    "scaled1": {"shardWidth": 64, "delta": 255, "baseAdvance": 16_384},
}
CSS_OUTPUT_BASE = 70_000


def q_tag(index: int) -> str:
    return f"Q{index:03d}"


def k_tag(index: int) -> str:
    return f"K{index:03d}"


def add_axis(font: TTFont, tag: str, ordering: int) -> tuple[Axis, dict[str, object]]:
    axis = Axis()
    axis.axisTag = tag
    axis.minValue = -1
    axis.defaultValue = 0
    axis.maxValue = 1
    axis.flags = 0
    axis.axisNameID = font["name"].addName(tag)
    return axis, {"tag": tag, "name": axis.axisNameID, "ordering": ordering}


def build_font(variant: str, spec: dict[str, int]) -> dict[str, object]:
    OUT.mkdir(parents=True, exist_ok=True)
    shard_width = spec["shardWidth"]
    shards = HEAD_WIDTH // shard_width
    delta = spec["delta"]
    base_advance = spec["baseAdvance"]
    if HEAD_WIDTH % shard_width:
        raise ValueError("shard width must divide the attention-head width")
    maximum_delta = shard_width * delta
    if base_advance < maximum_delta or base_advance + maximum_delta > 32_767:
        raise ValueError("variant advance range exceeds Chromium's signed advance limit")
    ttf_path = OUT / f"bilinear-attention-{variant}.ttf"
    build_master(
        ttf_path,
        np.full(shards, base_advance, dtype=np.int32),
        "Regular",
    )
    font = TTFont(ttf_path, recalcTimestamp=False)

    tags = [q_tag(index) for index in range(HEAD_WIDTH)] + [
        k_tag(index) for index in range(HEAD_WIDTH)
    ]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for ordering, tag in enumerate(tags):
        axis, stat_axis = add_axis(font, tag, ordering)
        fvar.axes.append(axis)
        stat_axes.append(stat_axis)
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    positive = (0, 1, 1)
    negative = (-1, -1, 0)
    supports: list[dict[str, tuple[int, int, int]]] = []
    for index in range(HEAD_WIDTH):
        q = q_tag(index)
        k = k_tag(index)
        supports.extend(
            [
                {q: positive, k: positive},
                {q: positive, k: negative},
                {q: negative, k: positive},
                {q: negative, k: negative},
            ]
        )

    rows = [[0] * len(supports)]
    for shard in range(shards):
        row = [0] * len(supports)
        for index in range(shard * shard_width, (shard + 1) * shard_width):
            offset = index * 4
            row[offset : offset + 4] = [
                delta,
                -delta,
                -delta,
                delta,
            ]
        rows.append(row)

    regions = buildVarRegionList(supports, tags)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions,
        [buildVarData(range(len(supports)), rows, optimize=True)],
    )
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in font.getGlyphOrder()}
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(ttf_path)

    woff2_path = ttf_path.with_suffix(".woff2")
    compressed = TTFont(ttf_path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(woff2_path)
    return {
        "ttfBytes": ttf_path.stat().st_size,
        "woff2Bytes": woff2_path.stat().st_size,
        "axes": len(tags),
        "regions": len(supports),
        "glyphsPerScore": shards,
        "shardWidth": shard_width,
        "delta": delta,
        "baseAdvance": base_advance,
        "decodeScale": PRODUCT_SCALE / delta,
        "file": woff2_path.name,
    }


def custom_properties(prefix: str, values: np.ndarray) -> str:
    return "".join(
        f"--{prefix}{index}:{int(value) / VALUE_MAX:.12g};"
        for index, value in enumerate(values)
    )


def balanced_sum(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced_sum(terms[:middle])} + {balanced_sum(terms[middle:])})"


def build_case(
    heads: int,
    tokens: int,
    seed: int,
    fonts: dict[str, dict[str, object]],
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    q = rng.integers(
        -VALUE_MAX, VALUE_MAX + 1, size=(CASES, heads, HEAD_WIDTH), dtype=np.int64
    )
    k = rng.integers(
        -VALUE_MAX,
        VALUE_MAX + 1,
        size=(CASES, heads, tokens, HEAD_WIDTH),
        dtype=np.int64,
    )
    initial = np.einsum("htd,hd->ht", k[0], q[0])
    query_only = np.einsum("htd,hd->ht", k[0], q[1])
    full = np.einsum("htd,hd->ht", k[1], q[1])

    settings = ",".join(
        [f'"{q_tag(index)}" var(--q{index})' for index in range(HEAD_WIDTH)]
        + [f'"{k_tag(index)}" var(--k{index})' for index in range(HEAD_WIDTH)]
    )
    pages = {}
    css_terms = [
        f"(var(--q{index}) * var(--k{index}))" for index in range(HEAD_WIDTH)
    ]
    css_scores = []
    for head in range(heads):
        scores = "".join(
            f'<i class="score" data-head="{head}" data-token="{token}" '
            f'style="{custom_properties("k", k[0, head, token])}"></i>'
            for token in range(tokens)
        )
        css_scores.append(
            f'<section class="head" data-head="{head}" '
            f'style="{custom_properties("q", q[0, head])}">{scores}</section>'
        )
    css_html = f'''<!doctype html>
<meta charset="utf-8">
<title>Native CSS-number attention: {heads} heads × {tokens} tokens</title>
<style>
html,body{{margin:0}}
.stage{{position:fixed;inset:0;contain:layout style;visibility:hidden}}
.head{{position:fixed;left:0;top:0}}
.score{{position:fixed;left:0;top:0;display:block;height:1px;
width:calc({CSS_OUTPUT_BASE}px + {PRODUCT_SCALE}px * {balanced_sum(css_terms)})}}
</style>
<main class="stage">{''.join(css_scores)}</main>
'''
    css_page = f"h{heads}-t{tokens}-css.html"
    (OUT / css_page).write_text(css_html)
    pages["css"] = {
        "page": css_page,
        "bytes": len(css_html.encode()),
        "outputBase": CSS_OUTPUT_BASE,
        "decodeScale": 1,
    }
    for variant, font in fonts.items():
        glyphs = "".join(
            f"&#x{0xE000 + shard:x};" for shard in range(font["glyphsPerScore"])
        )
        head_markup = []
        for head in range(heads):
            scores = "".join(
                f'<i class="score" data-head="{head}" data-token="{token}" '
                f'style="{custom_properties("k", k[0, head, token])}">{glyphs}</i>'
                for token in range(tokens)
            )
            head_markup.append(
                f'<section class="head" data-head="{head}" '
                f'style="{custom_properties("q", q[0, head])}">{scores}</section>'
            )

        html = f'''<!doctype html>
<meta charset="utf-8">
<title>Bilinear HVAR attention {variant}: {heads} heads × {tokens} tokens</title>
<style>
@font-face{{font-family:BilinearAttention;src:url("{font['file']}?v=1") format("woff2")}}
html,body{{margin:0}}
.stage{{position:fixed;inset:0;contain:layout style;visibility:hidden}}
.head{{position:fixed;left:0;top:0}}
.score{{position:fixed;left:0;top:0;display:inline-block;white-space:nowrap;
font-family:BilinearAttention;font-size:{FONT_SIZE}px;line-height:1;
font-variation-settings:{settings}}}
</style>
<main class="stage">{''.join(head_markup)}</main>
'''
        page = f"h{heads}-t{tokens}-{variant}.html"
        (OUT / page).write_text(html)
        pages[variant] = {
            "page": page,
            "bytes": len(html.encode()),
            "outputBase": font["glyphsPerScore"] * font["baseAdvance"],
            "decodeScale": font["decodeScale"],
        }
    reference = {
        "heads": heads,
        "tokens": tokens,
        "headWidth": HEAD_WIDTH,
        "valueMax": VALUE_MAX,
        "productScale": PRODUCT_SCALE,
        "fontSize": FONT_SIZE,
        "unitsPerEm": UNITS_PER_EM,
        "elements": 2 + heads + heads * tokens,
        "pages": pages,
        "q": q.tolist(),
        "k": k.tolist(),
        "expectedInitial": initial.reshape(-1).tolist(),
        "expectedQueryOnly": query_only.reshape(-1).tolist(),
        "expectedFull": full.reshape(-1).tolist(),
    }
    (OUT / f"h{heads}-t{tokens}.json").write_text(json.dumps(reference) + "\n")
    return reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shapes", default="1x4,1x16,1x64,12x4,12x16,12x64")
    args = parser.parse_args()
    shapes = [
        tuple(int(value) for value in item.split("x", maxsplit=1))
        for item in args.shapes.split(",")
        if item
    ]
    fonts = {variant: build_font(variant, spec) for variant, spec in VARIANTS.items()}
    cases = [
        build_case(heads, tokens, 0xB11E + heads * 1009 + tokens, fonts)
        for heads, tokens in shapes
    ]
    manifest = {"fonts": fonts, "variants": ["css", *fonts], "cases": cases}
    (OUT / "manifest.json").write_text(json.dumps(manifest) + "\n")
    print(
        json.dumps(
            {
                "fonts": fonts,
                "cases": [
                    {
                        "shape": f"{case['heads']}x{case['tokens']}",
                        "bytes": {
                            variant: page["bytes"]
                            for variant, page in case["pages"].items()
                        },
                        "elements": case["elements"],
                    }
                    for case in cases
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
