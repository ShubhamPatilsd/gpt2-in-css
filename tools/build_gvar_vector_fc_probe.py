#!/usr/bin/env python3
"""Render GPT-2's full 768→3,072 FC as three complex variable glyphs."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    MLP_WIDTH,
    QUANT_BITS,
    WIDTH,
    gelu_new,
    layer_norm,
    model_data,
    packed_axis_tag,
)
from build_gvar_vector_glyph_probe import BAR_WIDTH, UPM, build_font
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gvar-vector-fc"
SHARD = 256


def settings(vector: np.ndarray, activation_range: float) -> str:
    values = vector / activation_range
    return ",".join(
        f'"{packed_axis_tag(shard, local)}" {css_number(float(values[index]))}'
        for index in range(WIDTH)
        for shard, local in [divmod(index, SHARD)]
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])

    coordinates = np.arange(WIDTH, dtype=np.float64)
    input_cases = [n2]
    for case_index in range(1, 8):
        scale = 0.72 + case_index * 0.035
        phase = np.sin(coordinates * (0.137 + case_index * 0.011) + case_index)
        input_cases.append(n2 * scale + phase * (0.035 + case_index * 0.006))
    activation_range = float(max(np.max(np.abs(value)) for value in input_cases) * 1.01)

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    weights = q_fc.reconstructed
    pre_cases = [weights @ value + data["fc_bias"] for value in input_cases]
    hidden_cases = [gelu_new(value) for value in pre_cases]

    # Size the outline for six calibration states, leaving two unseen states to
    # measure clipping/generalization. Each of the three glyphs carries one
    # third of the bias so their rasterized widths add to the complete affine.
    partial_cases = []
    for vector in input_cases[:6]:
        partial_cases.extend(
            weights[:, start : start + SHARD] @ vector[start : start + SHARD]
            + data["fc_bias"] / 3
            for start in range(0, WIDTH, SHARD)
        )
    calibrated_bound = max(float(np.max(np.abs(value))) for value in partial_cases) * 1.12
    # TrueType base coordinates are signed 16-bit. Keep base + the largest
    # calibrated delta below ~30k; Chromium otherwise wraps the varied outline.
    geometry_scale = max(1, math.floor(14_500 / calibrated_bound))
    base = math.ceil(calibrated_bound * geometry_scale)
    if base > 30_000:
        raise ValueError("calibrated vector-glyph base exceeds safe TrueType range")

    font_faces = []
    font_names = []
    font_bytes = 0
    quantized_geometry_weights = []
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        stop = start + SHARD
        delta_codes = np.rint(
            weights[:, start:stop] * activation_range * geometry_scale
        ).astype(np.int16)
        quantized_geometry_weights.append(
            delta_codes.astype(np.float64) / (activation_range * geometry_scale)
        )
        bias_offsets = np.rint(data["fc_bias"] / 3 * geometry_scale).astype(np.int32)
        path = OUT / f"fc-vector-s{shard}.ttf"
        build_font(
            delta_codes,
            path,
            base=base,
            base_offsets=bias_offsets,
            axis_shard=shard,
        )
        woff2 = path.with_suffix(".woff2")
        tag = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        family = f"FCVector{shard}"
        font_faces.append(
            f'@font-face{{font-family:{family};src:url("{woff2.name}?v={tag}") format("woff2")}}'
        )
        font_names.append(family)
        font_bytes += woff2.stat().st_size

    quantized_geometry_weight = np.concatenate(quantized_geometry_weights, axis=1)
    geometry_pre_cases = [
        quantized_geometry_weight @ vector
        + np.rint(data["fc_bias"] / 3 * geometry_scale) / geometry_scale * 3
        for vector in input_cases
    ]
    pre_min = float(min(np.min(value) for value in pre_cases[:6]) - 0.2)
    pre_max = float(max(np.max(value) for value in pre_cases[:6]) + 0.2)
    pre_span = pre_max - pre_min
    dense_pre = np.linspace(pre_min, pre_max, 16_385)
    dense_hidden = gelu_new(dense_pre)
    hidden_min = float(np.min(dense_hidden))
    hidden_max = float(np.max(dense_hidden))
    hidden_span = hidden_max - hidden_min
    lut_pre = np.linspace(pre_min, pre_max, 256)
    hidden_table = " ".join(
        css_number(float(value))
        for value in (gelu_new(lut_pre) - hidden_min) / hidden_span
    )

    scale_x = BAR_WIDTH / (2 * base)
    kernel = " ".join(["1"] * BAR_WIDTH)
    reducers = []
    texts = []
    for shard, family in enumerate(font_names):
        start = shard * BAR_WIDTH
        end = start + BAR_WIDTH - 1
        reducers.extend(
            (
                f'<feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" '
                f'targetX="{BAR_WIDTH - 1}" kernelMatrix="{kernel}" divisor="{BAR_WIDTH}" '
                f'edgeMode="none" preserveAlpha="false" x="{end}" y="0" width="1" '
                f'height="{MLP_WIDTH}" result="part{shard}"/>',
                f'<feColorMatrix in="part{shard}" '
                f'values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1" '
                f'result="part-rgb{shard}"/>',
                f'<feOffset in="part-rgb{shard}" dx="-{end}" x="0" y="0" '
                f'width="1" height="{MLP_WIDTH}" result="part-col{shard}"/>',
            )
        )
        texts.append(
            f'<text class="glyph s{shard}" x="0" y="{MLP_WIDTH}" '
            f'transform="matrix({css_number(scale_x)} 0 0 1 {start} 0)">&#xE000;</text>'
        )
    pre_coefficient = 6 * base / (geometry_scale * pre_span)
    pre_offset = -0.5 * pre_coefficient - pre_min / pre_span
    pre_matrix = (
        f"{css_number(pre_coefficient)} 0 0 0 {css_number(pre_offset)}  " * 3
        + "0 0 0 0 1"
    )
    html = f'''<!doctype html>
<meta charset="utf-8">
<style>
{''.join(font_faces)}
html,body{{margin:0;background:transparent}}
svg{{display:block;overflow:visible}}
#bank{{font-size:{UPM}px;font-variation-settings:{settings(n2, activation_range)};fill:red}}
.s0{{font-family:{font_names[0]}}}.s1{{font-family:{font_names[1]}}}.s2{{font-family:{font_names[2]}}}
</style>
<svg id="surface" width="{BAR_WIDTH * 3}" height="{MLP_WIDTH}"
 viewBox="0 0 {BAR_WIDTH * 3} {MLP_WIDTH}" xmlns="http://www.w3.org/2000/svg">
 <defs><filter id="fc" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
  x="0" y="0" width="{BAR_WIDTH * 3}" height="{MLP_WIDTH}"
  color-interpolation-filters="sRGB">
  {''.join(reducers)}
  <feComposite in="part-col0" in2="part-col1" operator="arithmetic"
   k1="0" k2=".5" k3=".5" k4="0" result="part01"/>
  <feComposite in="part01" in2="part-col2" operator="arithmetic"
   k1="0" k2=".6666666667" k3=".3333333333" k4="0" result="average"/>
  <feColorMatrix in="average" values="{pre_matrix}" result="pre"/>
  <feComponentTransfer in="pre" result="hidden">
   <feFuncR type="table" tableValues="{hidden_table}"/>
   <feFuncG type="table" tableValues="{hidden_table}"/>
   <feFuncB type="table" tableValues="{hidden_table}"/>
   <feFuncA type="identity"/>
  </feComponentTransfer>
  <feOffset in="hidden" result="final"/>
 </filter></defs>
 <g id="bank" filter="url(#fc)">{''.join(texts)}</g>
</svg>
'''
    (OUT / "index.html").write_text(html)
    cases = [
        {
            "fontSettings": settings(vector, activation_range),
            "expectedPre": pre.tolist(),
            "geometryExpectedPre": geometry_pre.tolist(),
            "expectedHidden": hidden.tolist(),
            "calibration": index < 6,
        }
        for index, (vector, pre, geometry_pre, hidden) in enumerate(
            zip(input_cases, pre_cases, geometry_pre_cases, hidden_cases, strict=True)
        )
    ]
    reference = {
        "outputs": MLP_WIDTH,
        "barWidth": BAR_WIDTH,
        "geometryScale": geometry_scale,
        "base": base,
        "calibratedPartialBound": calibrated_bound,
        "preMin": pre_min,
        "preMax": pre_max,
        "hiddenMin": hidden_min,
        "hiddenMax": hidden_max,
        "cases": cases,
        "fontBytes": font_bytes,
        "htmlBytes": len(html.encode()),
        "elements": 0,
        "runtimeJavascript": False,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        {
            "base": base,
            "geometry_scale": geometry_scale,
            "partial_bound": calibrated_bound,
            "font_bytes": font_bytes,
            "html_bytes": reference["htmlBytes"],
        }
    )


if __name__ == "__main__":
    main()
