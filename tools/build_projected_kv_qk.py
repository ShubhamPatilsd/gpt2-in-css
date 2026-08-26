#!/usr/bin/env python3
"""Build Q-selected fonts that dot live 64-wide projected K cache vectors."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT
from build_gpt2_block_css import FONT_SIZE, QUANT_BITS, UNITS_PER_EM, WIDTH, layer_norm
from build_geometry_streaming_attention import TOKENS
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
BASE_OUT = ROOT / "experiments" / "projected-kv-qk"
HEADS = 12
HEAD_WIDTH = WIDTH // HEADS
QUERY_BITS = 5
LEVELS = 1 << QUERY_BITS
CONTEXT = 16
TARGET_DELTA = 12_000
CODEPOINT_BASE = 0xF4000


def range_tag(value: float) -> str:
    return f"{value:.4g}".replace(".", "p")


def axis_tag(index: int) -> str:
    return f"K{index:03d}"


def feature_tag(index: int) -> str:
    return f"Q{index:03d}"


def rectangle():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def quantize(values: np.ndarray, ranges: np.ndarray, bits: int) -> np.ndarray:
    levels = (1 << bits) - 1
    codes = np.rint(np.clip((values + ranges) * levels / (2 * ranges), 0, levels))
    return -ranges + codes * (2 * ranges / levels)


def build_head_font(
    *,
    head: int,
    query_ranges: np.ndarray,
    key_ranges: np.ndarray,
    destination: Path,
) -> tuple[int, int]:
    maximum = float(np.max(query_ranges * key_ranges))
    dot_scale = max(1, math.floor(TARGET_DELTA / maximum))
    base = math.ceil(maximum * dot_scale) + 32
    base_glyphs = [f"b{coordinate:03d}" for coordinate in range(HEAD_WIDTH)]
    alternate_glyphs = [
        f"a{coordinate:03d}_{choice:02d}"
        for coordinate in range(HEAD_WIDTH)
        for choice in range(LEVELS)
    ]
    glyphs = [".notdef", *base_glyphs, *alternate_glyphs]
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap({
        CODEPOINT_BASE + coordinate: glyph
        for coordinate, glyph in enumerate(base_glyphs)
    })
    builder.setupGlyf({name: rectangle() for name in glyphs})
    builder.setupHorizontalMetrics({
        name: (0 if name == ".notdef" else base, 0) for name in glyphs
    })
    builder.setupHorizontalHeader(ascent=1_000, descent=0)
    family = f"Projected KV QK H{head}"
    builder.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"ProjectedKVQKH{head}-Regular",
        "fullName": f"{family} Regular",
        "psName": f"ProjectedKVQKH{head}-Regular",
    })
    builder.setupOS2(
        version=4,
        sTypoAscender=1_000,
        sTypoDescender=0,
        usWinAscent=1_000,
        usWinDescent=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    tags = [axis_tag(index) for index in range(HEAD_WIDTH)]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = [
        support
        for tag in tags
        for support in ({tag: (-1, -1, 0)}, {tag: (0, 1, 1)})
    ]
    regions = buildVarRegionList(supports, tags)
    rows = [[0] * len(supports) for _ in glyphs]
    glyph_index = {name: index for index, name in enumerate(glyphs)}
    for coordinate in range(HEAD_WIDTH):
        q_values = np.linspace(-query_ranges[coordinate], query_ranges[coordinate], LEVELS)
        for choice, query_value in enumerate(q_values):
            coefficient = round(query_value * key_ranges[coordinate] * dot_scale)
            row = [0] * len(supports)
            row[coordinate * 2:coordinate * 2 + 2] = [-coefficient, coefficient]
            rows[glyph_index[f"a{coordinate:03d}_{choice:02d}"]] = row
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

    features = ["languagesystem DFLT dflt;"]
    for coordinate in range(HEAD_WIDTH):
        alternates = " ".join(
            f"a{coordinate:03d}_{choice:02d}" for choice in range(LEVELS)
        )
        tag = feature_tag(coordinate)
        features.append(
            f"feature {tag} {{ sub b{coordinate:03d} from [{alternates}]; }} {tag};"
        )
    addOpenTypeFeaturesFromString(font, "\n".join(features))
    font.recalcTimestamp = False
    font.flavor = "woff2"
    font.save(destination.with_suffix(".woff2"))
    return dot_scale, base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range-scale", type=float, default=1.0)
    args = parser.parse_args()
    if not 0 < args.range_scale <= 1.5:
        parser.error("range scale must be in (0, 1.5]")
    out = (
        BASE_OUT if args.range_scale == 1.0
        else BASE_OUT.with_name(f"{BASE_OUT.name}-range-{range_tag(args.range_scale)}")
    )
    out.mkdir(parents=True, exist_ok=True)

    precision = json.loads(PRECISION_REPORT.read_text())
    ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    query_ranges = ranges[:WIDTH] * args.range_scale
    key_ranges = ranges[WIDTH:2 * WIDTH]
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    positions = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    states = np.stack([
        embeddings[token] + positions[position]
        for position, token in enumerate(TOKENS[:CONTEXT])
    ])
    normalized = np.stack([layer_norm(row, gamma, beta) for row in states])
    weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    weight = quantize_float_rows(weight, bits=QUANT_BITS).reconstructed
    qkv = normalized @ weight.T + bias
    codes = np.rint(np.clip((qkv + ranges) * 255 / (2 * ranges), 0, 255))
    qkv = -ranges + codes * (2 * ranges / 255)

    heads = []
    total_font_bytes = 0
    for head in range(HEADS):
        start = head * HEAD_WIDTH
        stop = start + HEAD_WIDTH
        path = out / f"projected-kv-qk-h{head}.ttf"
        dot_scale, base = build_head_font(
            head=head,
            query_ranges=query_ranges[start:stop],
            key_ranges=key_ranges[start:stop],
            destination=path,
        )
        font_bytes = path.with_suffix(".woff2").stat().st_size
        total_font_bytes += font_bytes
        query = quantize(qkv[-1, start:stop], query_ranges[start:stop], QUERY_BITS)
        keys = qkv[:, WIDTH + start:WIDTH + stop]
        heads.append({
            "head": head,
            "queryRanges": query_ranges[start:stop].tolist(),
            "keyRanges": key_ranges[start:stop].tolist(),
            "dotScale": dot_scale,
            "base": base,
            "fontBytes": font_bytes,
            "expectedScores": (keys @ query / math.sqrt(HEAD_WIDTH)).tolist(),
        })

    reference = {
        "heads": HEADS,
        "headWidth": HEAD_WIDTH,
        "queryBits": QUERY_BITS,
        "queryRangeScale": args.range_scale,
        "codepointBase": CODEPOINT_BASE,
        "fontSize": FONT_SIZE,
        "totalFontBytes": total_font_bytes,
        "runtimeJavaScript": False,
        "headsReference": heads,
    }
    (out / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "heads": HEADS,
        "fonts": HEADS,
        "totalFontBytes": total_font_bytes,
        "queryRangeScale": args.range_scale,
    })


if __name__ == "__main__":
    main()
