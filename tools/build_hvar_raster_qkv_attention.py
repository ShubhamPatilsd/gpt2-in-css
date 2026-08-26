#!/usr/bin/env python3
"""Connect HVAR QKV rows to the existing SVG attention raster in bulk."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import (
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    packed_axis_tag,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "hvar-raster-qkv-attention"
FONT_OUT = ROOT / "experiments" / "gpt2-block-css"
CSS_REFERENCE = FONT_OUT / "view-timeline-attention-2token-reference.json"
SVG_REFERENCE = ROOT / "experiments" / "svg-multitoken-attention-rgb-centered" / "reference.json"
SVG_STAGED_PAGE = (
    ROOT
    / "experiments"
    / "svg-multitoken-attention-rgb-centered"
    / "connected-qkv-staged.html"
)

FONT_SIZE = 512
BAR_WIDTH = 256
BAR_STRIDE = 256
HEADS = 12
HEAD_WIDTH = 64
QKV_WIDTH = 3 * WIDTH
ROWS_PER_TOKEN = 3 * HEADS
GRID_ROWS = 2 * ROWS_PER_TOKEN
CENTER = 128 / 255


def font_settings(vector: np.ndarray, activation_range: float) -> str:
    settings = []
    for index, value in enumerate(vector / activation_range):
        shard, local = divmod(index, 256)
        settings.append(
            f'"{packed_axis_tag(shard, local)}" {css_number(float(value))}'
        )
    return ",".join(settings)


def extract_filter(page: str, filter_id: str) -> str:
    start = page.index(f'<filter id="{filter_id}"')
    stop = page.index("</filter>", start) + len("</filter>")
    return page[start:stop]


def attention_reference(qkv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    query, key, value = np.split(qkv, 3, axis=1)
    query = query.reshape(2, HEADS, HEAD_WIDTH)
    key = key.reshape(2, HEADS, HEAD_WIDTH)
    value = value.reshape(2, HEADS, HEAD_WIDTH)
    context = np.empty((2, HEADS, HEAD_WIDTH), dtype=np.float64)
    probabilities = np.zeros((2, HEADS, 2), dtype=np.float64)
    context[0] = value[0]
    probabilities[0, :, 0] = 1
    for head in range(HEADS):
        scores = np.asarray(
            [
                np.dot(query[1, head], key[source, head])
                / math.sqrt(HEAD_WIDTH)
                for source in range(2)
            ]
        )
        shifted = scores - np.max(scores)
        probability = np.exp(shifted) / np.exp(shifted).sum()
        probabilities[1, head] = probability
        context[1, head] = sum(
            probability[source] * value[source, head] for source in range(2)
        )
    return context.reshape(2, WIDTH), probabilities


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    css_reference = json.loads(CSS_REFERENCE.read_text())
    svg_reference = json.loads(SVG_REFERENCE.read_text())
    normalized = np.asarray(css_reference["normalized"], dtype=np.float64)
    qkv_scales = np.asarray(svg_reference["qkv_scales"], dtype=np.float64)
    value_scales = np.asarray(svg_reference["value_scales"], dtype=np.float64)

    tensors = SafeTensors(MODEL_PATH)
    weight = np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    ).T
    bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    quantized = quantize_float_rows(weight, bits=QUANT_BITS)
    qkv = normalized @ quantized.reconstructed.T + bias
    expected_context, expected_probabilities = attention_reference(qkv)

    activation_range = float(np.max(np.abs(normalized)) * 1.01)
    fonts = build_font_group(
        "qkv-rowbase",
        quantized.codes,
        rebuild=False,
        row_specific_bases=True,
    )
    if fonts.row_bases is None:
        raise ValueError("row-specific QKV bases are required")
    bases = np.sum(np.stack(fonts.row_bases), axis=0)

    faces = "".join(
        f'@font-face{{font-family:qkvS{shard};'
        f'src:url("../gpt2-block-css/{name}.woff2?v={tag}") format("woff2");'
        f'unicode-range:U+{start:X}-{start + QKV_WIDTH - 1:X}}}'
        for shard, (name, tag, start) in enumerate(
            zip(fonts.names, fonts.tags, fonts.codepoint_starts, strict=True)
        )
    )
    families = ",".join(f"qkvS{index}" for index in range(len(fonts.names)))

    groups: list[str] = []
    wide_bars: list[str] = []
    for token in range(2):
        for part in range(3):
            for head in range(HEADS):
                output_start = part * WIDTH + head * HEAD_WIDTH
                row = token * ROWS_PER_TOKEN + part * HEADS + head
                bars: list[str] = []
                for output in range(output_start, output_start + HEAD_WIDTH):
                    characters = "".join(
                        f"&#x{start + output:X};" for start in fonts.codepoint_starts
                    )
                    factor = activation_range * quantized.scales[output]
                    bars.append(
                        '<i class="bar" style="'
                        f'--base:{int(bases[output])};'
                        f'--factor:{css_number(float(factor))};'
                        f'--bias:{css_number(float(bias[output]))};'
                        f'--range:{css_number(float(qkv_scales[output]))}'
                        f'">{characters}</i>'
                    )
                    wide_bars.append(
                        '<i class="bar token-'
                        f'{token}" style="--base:{int(bases[output])};'
                        f'--factor:{css_number(float(factor))};'
                        f'--bias:{css_number(float(bias[output]))};'
                        f'--range:{css_number(float(qkv_scales[output]))}'
                        f'">{characters}</i>'
                    )
                groups.append(
                    f'<div class="group token-{token}" style="--row:{row}">'
                    + "".join(bars)
                    + "</div>"
                )

    qkv_grid = '<div id="qkv-grid" class="qkv-grid">' + "".join(groups) + "</div>"
    bar_kernel = " ".join("1" for _ in range(BAR_WIDTH))
    reduce_filter = (
        '<filter id="reduce-qkv" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" '
        f'x="0" y="0" width="{BAR_WIDTH}" height="{HEAD_WIDTH}" '
        'color-interpolation-filters="sRGB">'
        '<feConvolveMatrix in="SourceGraphic" '
        f'order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}" '
        f'kernelMatrix="{bar_kernel}" divisor="{BAR_WIDTH}" bias="0" '
        'edgeMode="none" preserveAlpha="false" '
        f'x="{BAR_WIDTH - 1}" y="0" width="1" height="{HEAD_WIDTH}" result="column"/>'
        '<feColorMatrix in="column" type="matrix" '
        'values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1" '
        f'x="{BAR_WIDTH - 1}" y="0" width="1" height="{HEAD_WIDTH}" result="opaque"/>'
        f'<feOffset in="opaque" dx="-{BAR_WIDTH - 1}" x="0" y="0" '
        f'width="1" height="{HEAD_WIDTH}"/>'
        "</filter>"
    )
    grid_filter = (
        '<filter id="grid-raster" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="64" height="72" '
        'color-interpolation-filters="sRGB">'
        '<feOffset in="SourceGraphic" x="0" y="0" width="64" height="72"/>'
        '</filter>'
    )
    staged_source = SVG_STAGED_PAGE.read_text()
    attention_filter = extract_filter(staged_source, "attention-stage")

    source_columns = 8
    source_chunks = HEAD_WIDTH // source_columns
    source_rows = GRID_ROWS * source_chunks
    wide_width = source_columns * BAR_STRIDE
    sample_x = np.arange(source_columns, dtype=np.int64) * BAR_STRIDE + BAR_WIDTH - 1
    mask = np.zeros((source_rows, wide_width), dtype=np.uint8)
    mask[:, sample_x] = 255
    Image.fromarray(mask, mode="L").save(OUT / "sample-mask.png", optimize=True)
    horizontal_scale = (BAR_STRIDE - 1) * 255 / 32
    horizontal_x = round(
        (BAR_WIDTH - 1) - (16 / 255 - 0.5) * horizontal_scale
    )
    horizontal_y = round(horizontal_scale / (2 * 255))
    horizontal_map = np.zeros((source_rows, source_columns, 3), dtype=np.uint8)
    horizontal_map[:, :, 0] = 16 + 32 * np.arange(source_columns, dtype=np.uint8)
    horizontal_map[:, :, 1] = 127
    Image.fromarray(horizontal_map, mode="RGB").save(
        OUT / "horizontal-map.png", optimize=True
    )
    vertical_scale = 7 * 255 / 3
    vertical_map = np.zeros((GRID_ROWS, source_columns, 3), dtype=np.uint8)
    vertical_map[:, :, 0] = 127
    vertical_map[:, :, 1] = 20 + 3 * np.arange(GRID_ROWS, dtype=np.uint8)[:, None]
    Image.fromarray(vertical_map, mode="RGB").save(
        OUT / "vertical-map.png", optimize=True
    )
    filter_height = max(source_rows, 340)
    vertical_primitives: list[str] = []
    vertical_outputs: list[str] = []
    for chunk in range(source_chunks):
        vertical_y = round(
            chunk - (20 / 255 - 0.5) * vertical_scale
        )
        name = f"chunk-{chunk}"
        vertical_primitives.extend(
            (
                f'<feImage href="vertical-map.png" x="1" y="{vertical_y}" '
                f'width="{source_columns}" height="{GRID_ROWS}" '
                f'preserveAspectRatio="none" result="{name}-map"/>',
                f'<feDisplacementMap in="horizontal" in2="{name}-map" '
                f'scale="{css_number(vertical_scale)}" xChannelSelector="R" '
                f'yChannelSelector="G" x="1" y="{vertical_y}" '
                f'width="{source_columns}" height="{GRID_ROWS}" result="{name}-sampled"/>',
                f'<feOffset in="{name}-sampled" dx="{chunk * source_columns - 1}" '
                f'dy="-{vertical_y}" x="{chunk * source_columns}" y="0" '
                f'width="{source_columns}" height="{GRID_ROWS}" result="{name}-positioned"/>',
            )
        )
        vertical_outputs.append(f"{name}-positioned")
    wide_filter = (
        '<filter id="wide-qkv" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" '
        f'x="0" y="0" width="{wide_width}" height="{filter_height}" '
        'color-interpolation-filters="sRGB">'
        '<feConvolveMatrix in="SourceGraphic" '
        f'order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}" '
        f'kernelMatrix="{bar_kernel}" divisor="{BAR_WIDTH}" bias="0" '
        'edgeMode="none" preserveAlpha="false" '
        f'x="0" y="0" width="{wide_width}" height="{source_rows}" result="averaged"/>'
        '<feColorMatrix in="averaged" type="matrix" '
        'values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1" result="opaque"/>'
        f'<feImage href="sample-mask.png" x="0" y="0" width="{wide_width}" '
        f'height="{source_rows}" preserveAspectRatio="none" result="mask"/>'
        '<feComposite in="opaque" in2="mask" operator="in" result="samples"/>'
        f'<feImage href="horizontal-map.png" x="{horizontal_x}" y="{horizontal_y}" '
        f'width="{source_columns}" height="{source_rows}" preserveAspectRatio="none" result="horizontal-map"/>'
        f'<feDisplacementMap in="samples" in2="horizontal-map" scale="{css_number(horizontal_scale)}" '
        'xChannelSelector="R" yChannelSelector="G" '
        f'x="{horizontal_x}" y="{horizontal_y}" width="{source_columns}" '
        f'height="{source_rows}" result="horizontal-packed"/>'
        f'<feOffset in="horizontal-packed" dx="-{horizontal_x}" dy="-{horizontal_y}" '
        f'x="0" y="0" width="{source_columns}" height="{source_rows}" '
        f'result="horizontal"/>'
        + "".join(vertical_primitives)
        + '<feMerge result="qkv-grid">'
        + "".join(f'<feMergeNode in="{name}"/>' for name in vertical_outputs)
        + '</feMerge>'
        '</filter>'
    )
    wide_grid = (
        f'<div xmlns="http://www.w3.org/1999/xhtml" class="wide-grid">'
        + "".join(wide_bars)
        + '</div>'
    )
    wide_inner = wide_filter[wide_filter.index(">") + 1 : -len("</filter>")]
    attention_inner = attention_filter[
        attention_filter.index(">") + 1 : -len("</filter>")
    ].replace('in="SourceGraphic"', 'in="qkv-grid"')
    fused_filter = (
        '<filter id="fused-attention" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" height="768" '
        'color-interpolation-filters="sRGB">'
        + wide_inner
        + attention_inner
        + '</filter>'
    )

    css = f"""
{faces}
*{{box-sizing:border-box}}
html,body{{margin:0;background:#000}}
svg.defs{{position:fixed;width:0;height:0;overflow:hidden}}
.qkv-grid{{position:relative;width:{HEAD_WIDTH}px;height:{GRID_ROWS}px;filter:url(#grid-raster)}}
.qkv-grid.connected-grid{{filter:url(#grid-raster) url(#attention-stage)}}
.wide-grid{{display:grid;grid-template-columns:repeat({source_columns},{BAR_STRIDE}px);
  grid-template-rows:repeat({source_rows},1px);width:{wide_width}px;height:{source_rows}px;
  font-family:{families};font-size:{FONT_SIZE}px;font-kerning:none}}
.group{{position:absolute;left:0;top:calc((var(--row) + 1) * 1px);width:{BAR_WIDTH}px;
  height:{HEAD_WIDTH}px;display:grid;grid-template-rows:repeat({HEAD_WIDTH},1px);
  font-family:{families};font-size:{FONT_SIZE}px;font-kerning:none;
  filter:url(#reduce-qkv);transform:rotate(-90deg);transform-origin:0 0;
  contain:layout style paint}}
.token-0{{font-variation-settings:{font_settings(normalized[0], activation_range)}}}
.token-1{{font-variation-settings:{font_settings(normalized[1], activation_range)}}}
.bar{{display:block;justify-self:start;height:1px;min-width:0;max-width:{BAR_WIDTH}px;
  overflow:hidden;white-space:pre;font-style:normal;color:transparent;background:#fff;
  width:0;width:calc-size(max-content,clamp(0px,
    (((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - var(--base)) * var(--factor)
      + var(--bias) + var(--range)) / (2 * var(--range)) * {BAR_WIDTH}px,
    {BAR_WIDTH}px))}}
.attention-output{{position:relative;width:2304px;height:768px;filter:url(#attention-stage)}}
"""
    defs = f'<svg class="defs" aria-hidden="true"><defs>{reduce_filter}{grid_filter}{attention_filter}</defs></svg>'
    grouped_qkv_page = (
        '<!doctype html><meta charset="utf-8"><title>HVAR raster QKV</title>'
        f"<style>{css}</style>{defs}{qkv_grid}"
    )
    wide_defs = f'{wide_filter}{attention_filter}{fused_filter}'
    qkv_page = (
        '<!doctype html><meta charset="utf-8"><title>Monolithic HVAR raster QKV</title>'
        f'<style>{css}</style><svg id="qkv-grid" width="{wide_width}" height="{source_rows}" '
        f'viewBox="0 0 {wide_width} {source_rows}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{wide_defs}</defs><g filter="url(#wide-qkv)">'
        f'<foreignObject x="0" y="0" width="{wide_width}" height="{source_rows}">'
        f'{wide_grid}</foreignObject></g></svg>'
    )
    connected_page = (
        '<!doctype html><meta charset="utf-8"><title>HVAR raster QKV attention</title>'
        f'<style>{css}</style><svg id="attention-output" width="2304" height="768" '
        'viewBox="0 0 2304 768" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{wide_defs}</defs><g filter="url(#attention-stage)">'
        '<g filter="url(#wide-qkv)">'
        f'<foreignObject x="0" y="0" width="{wide_width}" height="{source_rows}">'
        f'{wide_grid}</foreignObject></g></g></svg>'
    )
    fused_page = (
        '<!doctype html><meta charset="utf-8"><title>Fused HVAR raster QKV attention</title>'
        f'<style>{css}</style><svg id="attention-output" width="2304" height="768" '
        'viewBox="0 0 2304 768" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{wide_defs}</defs><g filter="url(#fused-attention)">'
        f'<foreignObject x="0" y="0" width="{wide_width}" height="{source_rows}">'
        f'{wide_grid}</foreignObject></g></svg>'
    )
    (OUT / "qkv-groups.html").write_text(grouped_qkv_page)
    (OUT / "qkv-debug.html").write_text(qkv_page)
    (OUT / "connected.html").write_text(connected_page)
    (OUT / "connected-fused.html").write_text(fused_page)

    font_bytes = sum((FONT_OUT / f"{name}.woff2").stat().st_size for name in fonts.names)
    reference = {
        "width": WIDTH,
        "heads": HEADS,
        "headWidth": HEAD_WIDTH,
        "surfaceCenter": CENTER,
        "qkvScales": qkv_scales.tolist(),
        "valueScales": value_scales.tolist(),
        "expectedQkv": qkv.tolist(),
        "expectedContext": expected_context.tolist(),
        "expectedProbabilities": expected_probabilities[1, :, 0].tolist(),
        "activationRange": activation_range,
        "qkvClippedFraction": float(np.mean(np.abs(qkv) > qkv_scales)),
        "groups": GRID_ROWS,
        "bars": 2 * QKV_WIDTH,
        "qkvHtmlBytes": len(qkv_page.encode()),
        "groupedQkvHtmlBytes": len(grouped_qkv_page.encode()),
        "connectedHtmlBytes": len(connected_page.encode()),
        "fusedHtmlBytes": len(fused_page.encode()),
        "fontBytes": font_bytes,
        "runtimeJavascript": False,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    digest = hashlib.sha256(connected_page.encode()).hexdigest()[:12]
    print(
        {
            "digest": digest,
            "groups": reference["groups"],
            "bars": reference["bars"],
            "qkv_clipped_fraction": reference["qkvClippedFraction"],
            "connected_html_bytes": reference["connectedHtmlBytes"],
            "font_bytes": font_bytes,
        }
    )


if __name__ == "__main__":
    main()
