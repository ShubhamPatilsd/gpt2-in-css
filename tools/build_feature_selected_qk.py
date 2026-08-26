#!/usr/bin/env python3
"""Build one real GPT-2 head whose QK dot products are GSUB-selected HVAR sums."""

from __future__ import annotations

import hashlib
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
from build_signed_hvar_chain import quantize_float_rows
from build_pretrained_gpt2 import css_number


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "feature-selected-qk"
HEAD_WIDTH = 64
HEAD = 0
CONTEXT = 16
QUERY_BITS = 5
LEVELS = 1 << QUERY_BITS
SHARD = 256
TARGET_DELTA = 12_000
CODEPOINT_BASE = 0xF0000


def axis_tag(shard: int, local: int) -> str:
    return f"{chr(ord('A') + shard)}{local:03d}"


def feature_tag(coordinate: int) -> str:
    return f"Q{coordinate:03d}"


def rectangle():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def build_shard_font(
    *,
    head: int,
    shard: int,
    codes: np.ndarray,
    row_scales: np.ndarray,
    row_bias: np.ndarray,
    query_ranges: np.ndarray,
    input_range: float,
    dot_scale: int,
    base: int,
    destination: Path,
) -> None:
    input_width = codes.shape[1]
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
        CODEPOINT_BASE + shard * HEAD_WIDTH + coordinate: glyph
        for coordinate, glyph in enumerate(base_glyphs)
    })
    builder.setupGlyf({name: rectangle() for name in glyphs})
    metrics = {name: (0 if name == ".notdef" else base, 0) for name in glyphs}
    if shard == 0:
        for coordinate in range(HEAD_WIDTH):
            q_values = np.linspace(
                -query_ranges[coordinate], query_ranges[coordinate], LEVELS
            )
            for choice, query_value in enumerate(q_values):
                metrics[f"a{coordinate:03d}_{choice:02d}"] = (
                    base + round(query_value * row_bias[coordinate] * dot_scale),
                    0,
                )
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=1_000, descent=0)
    family = f"Feature QK H{head} S{shard}"
    builder.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"FeatureQKH{head}S{shard}-Regular",
        "fullName": f"{family} Regular",
        "psName": f"FeatureQKH{head}S{shard}-Regular",
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
    tags = [axis_tag(shard, local) for local in range(input_width)]
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
        q_values = np.linspace(
            -query_ranges[coordinate], query_ranges[coordinate], LEVELS
        )
        for choice, query_value in enumerate(q_values):
            coefficients = np.rint(
                query_value
                * row_scales[coordinate]
                * input_range
                * dot_scale
                * codes[coordinate]
            ).astype(np.int32)
            rows[glyph_index[f"a{coordinate:03d}_{choice:02d}"]] = [
                delta
                for coefficient in coefficients.tolist()
                for delta in (-coefficient, coefficient)
            ]
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


def quantize(values: np.ndarray, ranges: np.ndarray, bits: int) -> tuple[np.ndarray, np.ndarray]:
    levels = (1 << bits) - 1
    choices = np.rint(np.clip((values + ranges) * levels / (2 * ranges), 0, levels))
    return choices.astype(np.int64), -ranges + choices * (2 * ranges / levels)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
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
    qkv_weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    quantized = quantize_float_rows(qkv_weight, bits=QUANT_BITS)
    qkv = normalized @ quantized.reconstructed.T + qkv_bias
    precision = json.loads(PRECISION_REPORT.read_text())
    all_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    input_range = float(precision["inputAbsMaxCalibration"] * 1.05)
    query_ranges = all_ranges[:HEAD_WIDTH]
    _, query8 = quantize(qkv[-1, :HEAD_WIDTH], query_ranges, 8)
    choices, query5 = quantize(query8, query_ranges, QUERY_BITS)
    key_rows = np.arange(WIDTH, WIDTH + HEAD_WIDTH)
    key_codes = quantized.codes[key_rows]
    key_scales = quantized.scales[key_rows]
    key_bias = qkv_bias[key_rows]

    maximum_unscaled_delta = 0.0
    for coordinate in range(HEAD_WIDTH):
        for start in range(0, WIDTH, SHARD):
            stop = min(start + SHARD, WIDTH)
            bias_margin = (
                abs(query_ranges[coordinate] * key_bias[coordinate])
                if start == 0 else 0.0
            )
            maximum_unscaled_delta = max(
                maximum_unscaled_delta,
                float(
                    query_ranges[coordinate]
                    * key_scales[coordinate]
                    * input_range
                    * np.sum(np.abs(key_codes[coordinate, start:stop]))
                    + bias_margin
                ),
            )
    dot_scale = max(1, math.floor(TARGET_DELTA / maximum_unscaled_delta))
    base = math.ceil(maximum_unscaled_delta * dot_scale) + 32

    font_paths = []
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        stop = min(start + SHARD, WIDTH)
        path = OUT / f"feature-qk-s{shard}.ttf"
        build_shard_font(
            head=HEAD,
            shard=shard,
            codes=key_codes[:, start:stop],
            row_scales=key_scales,
            row_bias=key_bias,
            query_ranges=query_ranges,
            input_range=input_range,
            dot_scale=dot_scale,
            base=base,
            destination=path,
        )
        font_paths.append(path.with_suffix(".woff2"))

    q_settings = ";".join(
        f"--q-{coordinate:03d}:{css_number(query8[coordinate])}"
        for coordinate in range(HEAD_WIDTH)
    )
    feature_setting_items = [
        f'"{feature_tag(coordinate)}" calc(1 + round(nearest,'
        f'clamp(0,(var(--q-{coordinate:03d}) + {css_number(query_ranges[coordinate])})'
        f' * {LEVELS - 1} / {css_number(2 * query_ranges[coordinate])},{LEVELS - 1}),1))'
        for coordinate in range(HEAD_WIDTH)
    ]
    feature_settings = ",".join(feature_setting_items)
    faces = "".join(
        f'@font-face{{font-family:FeatureQKS{shard};src:url("{path.name}?v='
        f'{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}") format("woff2");'
        f'unicode-range:U+{CODEPOINT_BASE + shard * HEAD_WIDTH:X}-'
        f'{CODEPOINT_BASE + (shard + 1) * HEAD_WIDTH - 1:X}}}'
        for shard, path in enumerate(font_paths)
    )
    families = ",".join(f"FeatureQKS{shard}" for shard in range(len(font_paths)))
    text = "".join(
        f"&#x{CODEPOINT_BASE + shard * HEAD_WIDTH + coordinate:X};"
        for shard in range(len(font_paths))
        for coordinate in range(HEAD_WIDTH)
    )
    score_elements = "".join(
        f"<i class=\"score score-{source}\" style='font-variation-settings:"
        + ",".join(
            f'"{axis_tag(shard, local)}" {css_number(normalized[source, shard * SHARD + local] / input_range)}'
            for shard in range(len(font_paths))
            for local in range(SHARD)
        )
        + f"'>{text}</i>"
        for source in range(CONTEXT)
    )
    html_head = f'''<!doctype html>
<meta charset="utf-8">
<title>Feature-selected real GPT-2 QK head</title>
<style>
{faces}
.scores{{{q_settings}}}
.score{{position:fixed;display:inline-flex;width:max-content;height:1px;overflow:hidden;
white-space:pre;font:normal {FONT_SIZE}px FeatureQKS0;font-family:{families};
font-kerning:none;font-feature-settings:{feature_settings}}}
</style>
'''
    html = html_head + f'<div class="scores">{score_elements}</div>\n'
    html_path = OUT / "index.html"
    html_path.write_text(html)

    chunk_size = 5
    chunk_texts = [
        "".join(
            f"&#x{CODEPOINT_BASE + shard * HEAD_WIDTH + coordinate:X};"
            for shard in range(len(font_paths))
            for coordinate in range(start, min(start + chunk_size, HEAD_WIDTH))
        )
        for start in range(0, HEAD_WIDTH, chunk_size)
    ]
    chunk_features = [
        ",".join(feature_setting_items[start:min(start + chunk_size, HEAD_WIDTH)])
        for start in range(0, HEAD_WIDTH, chunk_size)
    ]
    chunk_score_elements = "".join(
        f"<i class=\"score score-{source}\" style='font-variation-settings:"
        + ",".join(
            f'"{axis_tag(shard, local)}" {css_number(normalized[source, shard * SHARD + local] / input_range)}'
            for shard in range(len(font_paths))
            for local in range(SHARD)
        )
        + "'>"
        + "".join(
            f"<b style='font-feature-settings:{settings}'>{chunk}</b>"
            for settings, chunk in zip(chunk_features, chunk_texts, strict=True)
        )
        + "</i>"
        for source in range(CONTEXT)
    )
    chunk_html = html_head.replace(
        f"font-kerning:none;font-feature-settings:{feature_settings}",
        "font-kerning:none;font-feature-settings:normal}.score b{font:inherit;font-feature-settings:inherit",
    ) + f'<div class="scores">{chunk_score_elements}</div>\n'
    (OUT / "chunked.html").write_text(chunk_html)

    keys = qkv[:, WIDTH:WIDTH + HEAD_WIDTH]
    expected_scores = keys @ query5 / math.sqrt(HEAD_WIDTH)
    baseline_scores = keys @ query8 / math.sqrt(HEAD_WIDTH)
    bias_correction = float(query5 @ key_bias)
    expected_shard_dots = []
    for source in range(CONTEXT):
        source_dots = []
        for start in range(0, WIDTH, SHARD):
            stop = min(start + SHARD, WIDTH)
            projected = (
                quantized.reconstructed[key_rows, start:stop]
                @ normalized[source, start:stop]
            )
            source_dots.append(float(query5 @ projected))
        expected_shard_dots.append(source_dots)
    expected_first_coordinate_dots = []
    expected_first_coordinate_full_dots = []
    for coordinate in range(HEAD_WIDTH):
        projected = float(
            quantized.reconstructed[key_rows[coordinate], :SHARD]
            @ normalized[0, :SHARD]
        )
        expected_first_coordinate_dots.append(float(query5[coordinate] * projected))
        projected_full = float(
            quantized.reconstructed[key_rows[coordinate]] @ normalized[0]
        )
        expected_first_coordinate_full_dots.append(
            float(query5[coordinate] * projected_full)
        )
    reference = {
        "context": CONTEXT,
        "head": HEAD,
        "queryBits": QUERY_BITS,
        "inputRange": input_range,
        "queryRanges": query_ranges.tolist(),
        "query8": query8.tolist(),
        "queryChoices": choices.tolist(),
        "query5": query5.tolist(),
        "keyBias": key_bias.tolist(),
        "biasCorrection": bias_correction,
        "biasFoldedIntoGlyphAdvance": True,
        "expectedShardDots": expected_shard_dots,
        "expectedFirstCoordinateDots": expected_first_coordinate_dots,
        "expectedFirstCoordinateFullDots": expected_first_coordinate_full_dots,
        "expectedScores": expected_scores.tolist(),
        "baselineScores": baseline_scores.tolist(),
        "queryBinningScoreRmse": float(np.sqrt(np.mean((expected_scores - baseline_scores) ** 2))),
        "dotScale": dot_scale,
        "base": base,
        "baseGlyphs": HEAD_WIDTH * len(font_paths),
        "fontBytes": [path.stat().st_size for path in font_paths],
        "htmlBytes": html_path.stat().st_size,
        "chunkedHtmlBytes": (OUT / "chunked.html").stat().st_size,
        "featureChunkSize": chunk_size,
        "runtimeJavaScript": False,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "dotScale": dot_scale,
        "base": base,
        "fontBytes": reference["fontBytes"],
        "htmlBytes": reference["htmlBytes"],
        "queryBinningScoreRmse": reference["queryBinningScoreRmse"],
    })


if __name__ == "__main__":
    main()
