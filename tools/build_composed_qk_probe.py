#!/usr/bin/env python3
"""Compare direct K geometry with a fused K-projection/Q-dot bilinear font."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT, TOKENS
from build_gpt2_block_css import (
    QUANT_BITS,
    WIDTH,
    build_font_group,
    layer_norm,
    pack_font_settings,
)
from build_matrix_backend_prototypes import build_master
from build_multitoken_attention_css import FONT_SIZE, HEAD_WIDTH
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "composed-qk-probe"
CONTEXT = 16
HEAD = 0
SHARD_WIDTH = 192
SHARDS = WIDTH // SHARD_WIDTH
UNITS_PER_EM = 1_000
BASE_ADVANCE = 16_000
CODEPOINT = 0xE000


def add_axis(font: TTFont, tag: str, ordering: int) -> tuple[Axis, dict[str, object]]:
    axis = Axis()
    axis.axisTag = tag
    axis.minValue = -1
    axis.defaultValue = 0
    axis.maxValue = 1
    axis.flags = 0
    axis.axisNameID = font["name"].addName(tag)
    return axis, {"tag": tag, "name": axis.axisNameID, "ordering": ordering}


def add_shifted_axis(
    font: TTFont, tag: str, ordering: int
) -> tuple[Axis, dict[str, object]]:
    axis = Axis()
    axis.axisTag = tag
    axis.minValue = 0
    axis.defaultValue = 0
    axis.maxValue = 1
    axis.flags = 0
    axis.axisNameID = font["name"].addName(tag)
    return axis, {"tag": tag, "name": axis.axisNameID, "ordering": ordering}


def q_tag(index: int) -> str:
    return f"Q{index:03d}"


def x_tag(index: int) -> str:
    return f"X{index:03d}"


def build_composed_font(
    shard: int,
    key_weight: np.ndarray,
    key_bias: np.ndarray,
    q_ranges: np.ndarray,
    input_range: float,
) -> dict[str, object]:
    start = shard * SHARD_WIDTH
    stop = start + SHARD_WIDTH
    coefficients = key_weight[:, start:stop] * q_ranges[:, None] * input_range
    bias_coefficients = key_bias * q_ranges / SHARDS
    maximum = float(np.sum(np.abs(coefficients)) + np.sum(np.abs(bias_coefficients)))
    scale = min(256.0, 14_000 / max(maximum, 1))
    ttf_path = OUT / f"composed-head{HEAD}-shard{shard}.ttf"
    woff2_path = ttf_path.with_suffix(".woff2")
    if ttf_path.exists() and woff2_path.exists():
        return {
            "file": woff2_path.name,
            "ttfFile": ttf_path.name,
            "scale": scale,
            "maximum": maximum,
            "regions": HEAD_WIDTH * SHARD_WIDTH * 4 + HEAD_WIDTH * 2,
            "bytes": woff2_path.stat().st_size,
            "ttfBytes": ttf_path.stat().st_size,
        }
    build_master(ttf_path, np.asarray([BASE_ADVANCE]), f"Composed{shard}")
    font = TTFont(ttf_path, recalcTimestamp=False)
    tags = [q_tag(index) for index in range(HEAD_WIDTH)] + [
        x_tag(index) for index in range(SHARD_WIDTH)
    ]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for ordering, tag in enumerate(tags):
        axis, stat = add_axis(font, tag, ordering)
        fvar.axes.append(axis)
        stat_axes.append(stat)
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    positive = (0, 1, 1)
    negative = (-1, -1, 0)
    supports = []
    deltas = []
    for q_index in range(HEAD_WIDTH):
        for x_index in range(SHARD_WIDTH):
            q = q_tag(q_index)
            x = x_tag(x_index)
            delta = int(round(coefficients[q_index, x_index] * scale))
            supports.extend((
                {q: positive, x: positive},
                {q: positive, x: negative},
                {q: negative, x: positive},
                {q: negative, x: negative},
            ))
            deltas.extend((delta, -delta, -delta, delta))
    for q_index in range(HEAD_WIDTH):
        q = q_tag(q_index)
        delta = int(round(bias_coefficients[q_index] * scale))
        supports.extend(({q: positive}, {q: negative}))
        deltas.extend((delta, -delta))
    regions = buildVarRegionList(supports, tags)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions,
        [buildVarData(range(len(supports)), [[0] * len(supports), deltas], optimize=True)],
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
    compressed = TTFont(ttf_path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(woff2_path)
    return {
        "file": woff2_path.name,
        "ttfFile": ttf_path.name,
        "scale": scale,
        "maximum": maximum,
        "regions": len(supports),
        "bytes": woff2_path.stat().st_size,
        "ttfBytes": ttf_path.stat().st_size,
    }


def build_shifted_composed_font(
    shard: int,
    key_weight: np.ndarray,
    key_bias: np.ndarray,
    q_ranges: np.ndarray,
    input_range: float,
) -> dict[str, object]:
    """Use q=2u-1 and x=2v-1 to need one Q/X region per term."""
    start = shard * SHARD_WIDTH
    stop = start + SHARD_WIDTH
    coefficients = key_weight[:, start:stop] * q_ranges[:, None] * input_range
    bias_coefficients = key_bias * q_ranges / SHARDS
    maximum = float(np.sum(np.abs(coefficients)) + np.sum(np.abs(bias_coefficients)))
    scale = min(256.0, 30_000 / max(maximum, 1))
    constant = float(np.sum(coefficients) - np.sum(bias_coefficients))
    static_advance = int(round(32_000 + constant * scale))
    ttf_path = OUT / f"shifted-head{HEAD}-shard{shard}.ttf"
    woff2_path = ttf_path.with_suffix(".woff2")
    region_count = HEAD_WIDTH * SHARD_WIDTH + HEAD_WIDTH + SHARD_WIDTH
    if ttf_path.exists() and woff2_path.exists():
        return {
            "file": woff2_path.name,
            "ttfFile": ttf_path.name,
            "scale": scale,
            "maximum": maximum,
            "regions": region_count,
            "bytes": woff2_path.stat().st_size,
            "ttfBytes": ttf_path.stat().st_size,
            "baseAdvance": 32_000,
        }
    if not 0 <= static_advance <= 65_535:
        raise ValueError(f"shifted static advance out of range: {static_advance}")
    build_master(ttf_path, np.asarray([static_advance]), f"Shifted{shard}")
    font = TTFont(ttf_path, recalcTimestamp=False)
    tags = [q_tag(index) for index in range(HEAD_WIDTH)] + [
        x_tag(index) for index in range(SHARD_WIDTH)
    ]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for ordering, tag in enumerate(tags):
        axis, stat = add_shifted_axis(font, tag, ordering)
        fvar.axes.append(axis)
        stat_axes.append(stat)
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    positive = (0, 1, 1)
    supports = []
    deltas = []
    for q_index in range(HEAD_WIDTH):
        for x_index in range(SHARD_WIDTH):
            supports.append({q_tag(q_index): positive, x_tag(x_index): positive})
            deltas.append(int(round(4 * coefficients[q_index, x_index] * scale)))
    q_linear = -2 * np.sum(coefficients, axis=1) + 2 * bias_coefficients
    for q_index, coefficient in enumerate(q_linear):
        supports.append({q_tag(q_index): positive})
        deltas.append(int(round(coefficient * scale)))
    x_linear = -2 * np.sum(coefficients, axis=0)
    for x_index, coefficient in enumerate(x_linear):
        supports.append({x_tag(x_index): positive})
        deltas.append(int(round(coefficient * scale)))

    regions = buildVarRegionList(supports, tags)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions,
        [buildVarData(range(len(supports)), [[0] * len(supports), deltas], optimize=True)],
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
    compressed = TTFont(ttf_path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(woff2_path)
    return {
        "file": woff2_path.name,
        "ttfFile": ttf_path.name,
        "scale": scale,
        "maximum": maximum,
        "regions": region_count,
        "bytes": woff2_path.stat().st_size,
        "ttfBytes": ttf_path.stat().st_size,
        "baseAdvance": 32_000,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    token_embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position_embeddings = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    states = np.stack([
        layer_norm(token_embeddings[token] + position_embeddings[position], gamma, beta)
        for position, token in enumerate(TOKENS[:CONTEXT])
    ])
    weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    reconstructed = quantize_float_rows(weight, bits=QUANT_BITS).reconstructed
    q_qkv = quantize_float_rows(weight, bits=QUANT_BITS)
    qkv = states @ reconstructed.T + bias
    precision = json.loads(PRECISION_REPORT.read_text())
    q_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )[HEAD * HEAD_WIDTH:(HEAD + 1) * HEAD_WIDTH]
    input_range = float(precision["inputAbsMaxCalibration"] * 1.05)
    query_exact = qkv[-1, HEAD * HEAD_WIDTH:(HEAD + 1) * HEAD_WIDTH]
    query_codes = np.rint(
        np.clip((query_exact + q_ranges) * 255 / (2 * q_ranges), 0, 255)
    )
    query = -q_ranges + query_codes * (2 * q_ranges / 255)
    key_start = WIDTH + HEAD * HEAD_WIDTH
    key_weight = reconstructed[key_start:key_start + HEAD_WIDTH]
    key_bias = bias[key_start:key_start + HEAD_WIDTH]
    keys = qkv[:, key_start:key_start + HEAD_WIDTH]
    expected = keys @ query / math.sqrt(HEAD_WIDTH)

    fonts = [
        build_composed_font(shard, key_weight, key_bias, q_ranges, input_range)
        for shard in range(SHARDS)
    ]
    shifted_fonts = [
        build_shifted_composed_font(shard, key_weight, key_bias, q_ranges, input_range)
        for shard in range(SHARDS)
    ]
    q_properties = ";".join(
        f"--q-{index}:{css_number(value)}" for index, value in enumerate(query)
    )

    composed_rules = []
    composed_markup = []
    for source in range(CONTEXT):
        glyphs = []
        for shard, font in enumerate(fonts):
            x_settings = ",".join(
                f'"{x_tag(index)}" {css_number(states[source, shard * SHARD_WIDTH + index] / input_range)}'
                for index in range(SHARD_WIDTH)
            )
            q_settings = ",".join(
                f'"{q_tag(index)}" {css_number(query[index] / q_ranges[index])}'
                for index in range(HEAD_WIDTH)
            )
            composed_rules.append(
                f".composed-{source}-{shard}{{font-family:Composed{shard};"
                f"font-variation-settings:{q_settings},{x_settings}}}"
            )
            glyphs.append(
                f'<i class="glyph composed-{source}-{shard}" data-source="{source}" '
                f'data-shard="{shard}">&#x{CODEPOINT:X};</i>'
            )
        composed_markup.append(f'<div class="source">{"".join(glyphs)}</div>')
    composed_body_css = (
        "".join(composed_rules)
        + ".glyph{position:fixed;inset:0 auto auto 0;display:inline-block;white-space:nowrap;"
        f"font-size:{UNITS_PER_EM}px;font-kerning:none}}"
    )
    composed_html = ""
    for extension, output_name in (("woff2", "composed.html"), ("ttf", "composed-ttf.html")):
        source_key = "file" if extension == "woff2" else "ttfFile"
        format_hint = "woff2" if extension == "woff2" else "truetype"
        faces = "".join(
            f'@font-face{{font-family:Composed{shard};src:url("{font[source_key]}?v=1") '
            f'format("{format_hint}")}}'
            for shard, font in enumerate(fonts)
        )
        composed_html = (
            '<!doctype html><meta charset="utf-8"><title>Composed QK probe</title><style>'
            + faces + composed_body_css + "</style><main>" + "".join(composed_markup) + "</main>"
        )
        (OUT / output_name).write_text(composed_html)

    shifted_rules = []
    shifted_markup = []
    for source in range(CONTEXT):
        glyphs = []
        for shard, font in enumerate(shifted_fonts):
            x_settings = ",".join(
                f'"{x_tag(index)}" {css_number((states[source, shard * SHARD_WIDTH + index] / input_range + 1) / 2)}'
                for index in range(SHARD_WIDTH)
            )
            q_settings = ",".join(
                f'"{q_tag(index)}" {css_number((query[index] / q_ranges[index] + 1) / 2)}'
                for index in range(HEAD_WIDTH)
            )
            shifted_rules.append(
                f".shifted-{source}-{shard}{{font-family:Shifted{shard};"
                f"font-variation-settings:{q_settings},{x_settings}}}"
            )
            glyphs.append(
                f'<i class="glyph shifted-{source}-{shard}" data-source="{source}" '
                f'data-shard="{shard}">&#x{CODEPOINT:X};</i>'
            )
        shifted_markup.append(f'<div class="source">{"".join(glyphs)}</div>')
    shifted_body_css = (
        "".join(shifted_rules)
        + ".glyph{position:fixed;inset:0 auto auto 0;display:inline-block;white-space:nowrap;"
        f"font-size:{UNITS_PER_EM}px;font-kerning:none}}"
    )
    shifted_html = ""
    for extension, output_name in (("woff2", "shifted.html"), ("ttf", "shifted-ttf.html")):
        source_key = "file" if extension == "woff2" else "ttfFile"
        format_hint = "woff2" if extension == "woff2" else "truetype"
        faces = "".join(
            f'@font-face{{font-family:Shifted{shard};src:url("{font[source_key]}?v=1") '
            f'format("{format_hint}")}}'
            for shard, font in enumerate(shifted_fonts)
        )
        shifted_html = (
            '<!doctype html><meta charset="utf-8"><title>Shifted composed QK probe</title><style>'
            + faces + shifted_body_css + "</style><main>" + "".join(shifted_markup) + "</main>"
        )
        (OUT / output_name).write_text(shifted_html)

    qkv_group = build_font_group(
        "qkv-rowbase", q_qkv.codes, rebuild=False, row_specific_bases=True
    )
    if qkv_group.row_bases is None:
        raise ValueError("row-specific QKV bases are required")
    qkv_bases = np.sum(np.stack(qkv_group.row_bases), axis=0)
    qkv_font_names = [f"qkvS{shard}" for shard in range(len(qkv_group.names))]
    direct_faces = "".join(
        f'@font-face{{font-family:{family};src:url("../gpt2-block-css/{name}.woff2?v=1") format("woff2")}}'
        for family, name in zip(qkv_font_names, qkv_group.names, strict=True)
    )
    direct_rules = [direct_faces]
    direct_markup = []
    direct_base = 4096
    direct_scale = 64
    for source in range(CONTEXT):
        input_names = [f"--s{source}-x{index}" for index in range(WIDTH)]
        values = ";".join(
            f"{name}:{css_number(value)}"
            for name, value in zip(input_names, states[source], strict=True)
        )
        settings = pack_font_settings(input_names, input_range, 0)
        direct_rules.append(
            f".direct-source-{source}{{{values};font-family:{','.join(qkv_font_names)};"
            f"font-variation-settings:{settings}}}"
        )
        metrics = []
        terms = []
        for index in range(HEAD_WIDTH):
            output = key_start + index
            anchor = f"--direct-k-{source}-{index}"
            chars = "".join(
                f"&#x{start + output:X};" for start in qkv_group.codepoint_starts
            )
            metrics.append(f'<i class="metric" style="anchor-name:{anchor}">{chars}</i>')
            # The row-specific bases are recovered from the generated reference font metadata.
            factor = input_range * q_qkv.scales[output]
            terms.append(
                f"var(--q-{index}) * (((anchor-size({anchor} width) / 1px * 1000 / "
                f"{FONT_SIZE}) - {int(qkv_bases[output])}) * {css_number(factor)} + "
                f"({css_number(bias[output])}))"
            )
        direct_rules.append(
            f".direct-score-{source}{{width:calc({direct_base}px + {direct_scale}px * "
            f"(({' + '.join(terms)}) / {math.sqrt(HEAD_WIDTH)}))}}"
        )
        direct_markup.append(
            f'<div class="direct-source direct-source-{source}">{"".join(metrics)}'
            f'<i class="direct-score direct-score-{source}" data-source="{source}"></i></div>'
        )
    direct_css = (
        "".join(direct_rules)
        + f":root{{{q_properties}}}"
        + ".metric{position:fixed;inset:0 auto auto 0;display:inline-flex;width:max-content;"
        f"height:1px;white-space:pre;font-size:{FONT_SIZE}px;font-kerning:none}}"
        + ".direct-score{position:fixed;inset:0 auto auto 0;display:block;height:1px}"
    )
    direct_html = (
        '<!doctype html><meta charset="utf-8"><title>Direct K probe</title><style>'
        + direct_css + "</style><main>" + "".join(direct_markup) + "</main>"
    )
    (OUT / "direct.html").write_text(direct_html)

    report = {
        "context": CONTEXT,
        "head": HEAD,
        "expected": expected.tolist(),
        "composedFonts": fonts,
        "shiftedFonts": shifted_fonts,
        "composedHtmlBytes": len(composed_html.encode()),
        "shiftedHtmlBytes": len(shifted_html.encode()),
        "directHtmlBytes": len(direct_html.encode()),
        "directBase": direct_base,
        "directScale": direct_scale,
        "unitsPerEm": UNITS_PER_EM,
        "fontSize": FONT_SIZE,
        "baseAdvance": BASE_ADVANCE,
    }
    (OUT / "reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
