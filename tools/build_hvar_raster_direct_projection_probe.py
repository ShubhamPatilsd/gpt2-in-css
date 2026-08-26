#!/usr/bin/env python3
"""Test full-height SVG convolution kernels after a real HVAR GPT-2 FC."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    MLP_WIDTH,
    OUT as FONT_OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    gelu_new,
    layer_norm,
    model_data,
    packed_axis_tag,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "hvar-raster-direct-projection"
FONT_SIZE = 512
BAR_WIDTH = 256
OUTPUT_COUNT = int(os.environ.get("HVAR_DIRECT_OUTPUTS", "16"))
INPUT_COUNT = int(os.environ.get("HVAR_DIRECT_INPUTS", str(MLP_WIDTH)))
if not 1 <= OUTPUT_COUNT <= WIDTH:
    raise ValueError("HVAR_DIRECT_OUTPUTS must be between 1 and 768")
if not 1 <= INPUT_COUNT <= MLP_WIDTH:
    raise ValueError("HVAR_DIRECT_INPUTS must be between 1 and 3072")


def font_settings(vector: np.ndarray, activation_range: float) -> str:
    settings = []
    for index, value in enumerate(vector / activation_range):
        shard, local = divmod(index, 256)
        settings.append(f'"{packed_axis_tag(shard, local)}" {css_number(float(value))}')
    return ",".join(settings)


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
    alternate_n2 = n2 * 0.755 + np.sin(coordinates * 0.148 + 1) * 0.041
    input_cases = [n2, alternate_n2]
    activation_range = float(max(np.max(np.abs(v)) for v in input_cases) * 1.01)

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fonts.bases)

    def fc_case(vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raw = q_fc.codes.astype(np.float64) @ (vector / activation_range)
        pre = raw * activation_range * q_fc.scales + data["fc_bias"]
        return pre, gelu_new(pre)

    fc_cases = [fc_case(vector) for vector in input_cases]
    pre_cases = [case[0] for case in fc_cases]
    hidden_cases = [case[1] for case in fc_cases]
    pre_min = float(min(np.min(value) for value in pre_cases) - 0.25)
    pre_max = float(max(np.max(value) for value in pre_cases) + 0.25)
    pre_span = pre_max - pre_min
    hidden_range = float(max(np.max(np.abs(value)) for value in hidden_cases) * 1.02)

    q_projection = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    projection = q_projection.reconstructed
    bias_residual = residual + data["mlp_proj_bias"]
    expected_cases = [
        bias_residual + projection[:, :INPUT_COUNT] @ hidden[:INPUT_COUNT]
        for hidden in hidden_cases
    ]

    # Keep ordinary rows plus known high-range rows in every partial fixture so
    # small probes do not accidentally measure only easy coordinates.
    selected = list(range(OUTPUT_COUNT))
    forced = [138, 378, 447]
    for offset, output in enumerate(forced):
        if output not in selected and offset < OUTPUT_COUNT:
            selected[-1 - offset] = output
    selected = sorted(set(selected))
    while len(selected) < OUTPUT_COUNT:
        candidate = len(selected)
        if candidate not in selected:
            selected.append(candidate)
    selected = selected[:OUTPUT_COUNT]

    faces = "".join(
        f'@font-face{{font-family:fcS{shard};src:url("../gpt2-block-css/{name}.woff2?v={tag}") '
        f'format("woff2");unicode-range:U+{start:X}-{start + MLP_WIDTH - 1:X}}}'
        for shard, (name, tag, start) in enumerate(
            zip(fonts.names, fonts.tags, fonts.codepoint_starts, strict=True)
        )
    )
    bars = []
    for output in range(MLP_WIDTH):
        characters = "".join(f"&#x{start + output:X};" for start in fonts.codepoint_starts)
        factor = activation_range * q_fc.scales[output]
        bias = data["fc_bias"][output]
        bars.append(
            '<i class="bar" style="--factor:'
            f'{css_number(float(factor))};--bias:{css_number(float(bias))}">'
            f"{characters}</i>"
        )

    center = 128 / 255
    lut_pre = np.linspace(pre_min, pre_max, 256)
    centered_table = " ".join(
        css_number(float(center + 0.5 * value / hidden_range))
        for value in gelu_new(lut_pre)
    )
    bar_kernel = " ".join(["1"] * BAR_WIDTH)
    primitives: list[str] = [
        f'<feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" '
        f'targetX="{BAR_WIDTH - 1}" kernelMatrix="{bar_kernel}" divisor="{BAR_WIDTH}" '
        f'bias="0" edgeMode="none" preserveAlpha="false" '
        f'x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="pre"/>',
        '<feColorMatrix in="pre" type="matrix" '
        'values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1" '
        f'x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="pre-rgb"/>',
        '<feComponentTransfer in="pre-rgb" '
        f'x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="hidden">'
        f'<feFuncR type="table" tableValues="{centered_table}"/>'
        f'<feFuncG type="table" tableValues="{centered_table}"/>'
        f'<feFuncB type="table" tableValues="{centered_table}"/>'
        '<feFuncA type="identity"/></feComponentTransfer>',
    ]
    output_ranges = []
    output_results = []
    for slot, output in enumerate(selected):
        weights = projection[output, :INPUT_COUNT]
        weight_scale = max(float(np.max(np.abs(weights))), 1e-12)
        normalized_weights = weights / weight_scale
        unit = weight_scale * hidden_range
        normalized_bias = bias_residual[output] / unit
        normalized_expected = [
            float(
                normalized_weights @ (hidden[:INPUT_COUNT] / hidden_range)
                + normalized_bias
            )
            for hidden in hidden_cases
        ]
        bound = max(max(abs(value) for value in normalized_expected) * 1.08, 0.02)
        divisor = bound
        convolution_bias = (
            center
            + 0.5 * normalized_bias / bound
            - center * float(np.sum(normalized_weights)) / bound
        )
        # SVG convolution reverses the declared kernel before applying it.
        kernel = " ".join(css_number(float(value)) for value in normalized_weights[::-1])
        result = f"direct-{slot}"
        moved = f"output-{slot}"
        primitives.extend(
            (
                f'<feConvolveMatrix in="hidden" order="1 {INPUT_COUNT}" '
                f'kernelMatrix="{kernel}" divisor="{css_number(divisor)}" '
                f'bias="{css_number(convolution_bias)}" targetX="0" '
                f'targetY="{INPUT_COUNT - 1}" edgeMode="none" preserveAlpha="false" '
                f'x="{BAR_WIDTH - 1}" y="{INPUT_COUNT - 1}" width="1" height="1" '
                f'result="{result}"/>',
                f'<feOffset in="{result}" dx="{slot - (BAR_WIDTH - 1)}" '
                f'dy="-{INPUT_COUNT - 1}" x="{slot}" y="0" width="1" height="1" '
                f'result="{moved}"/>',
            )
        )
        output_results.append(moved)
        output_ranges.append(bound * unit)
    primitives.append(
        "<feMerge>"
        + "".join(f'<feMergeNode in="{name}"/>' for name in output_results)
        + "</feMerge>"
    )

    page_width = max(BAR_WIDTH, OUTPUT_COUNT)
    html = f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HVAR raster direct SVG projection</title>
<style>
{faces}
html{{background:transparent}}
body{{margin:0}}
svg{{position:fixed;left:0;top:0}}
.bank{{display:grid;grid-template-rows:repeat({MLP_WIDTH},1px);width:{page_width}px;height:{MLP_WIDTH}px;
  font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;
  font-variation-settings:{font_settings(n2, activation_range)};
  background:transparent;filter:url(#direct);contain:strict}}
.bar{{display:block;justify-self:start;height:1px;min-width:0;max-width:{BAR_WIDTH}px;overflow:hidden;
  white-space:pre;font-style:normal;color:transparent;background:#f00;width:0;
  width:calc-size(max-content,clamp(0px,
    (((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - {base_total}) * var(--factor)
      + var(--bias) - {css_number(pre_min)}) / {css_number(pre_span)} * {BAR_WIDTH}px,
    {BAR_WIDTH}px))}}
</style>
<svg width="0" height="0" aria-hidden="true">
  <filter id="direct" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{page_width}" height="{MLP_WIDTH}" color-interpolation-filters="sRGB">
    {''.join(primitives)}
  </filter>
</svg>
<div id="bank" class="bank">{''.join(bars)}</div>
'''
    stem = f"n{OUTPUT_COUNT}" if INPUT_COUNT == MLP_WIDTH else f"n{OUTPUT_COUNT}-i{INPUT_COUNT}"
    (OUT / f"{stem}.html").write_text(html)
    reference = {
        "outputCount": OUTPUT_COUNT,
        "inputCount": INPUT_COUNT,
        "selectedOutputs": selected,
        "outputRanges": output_ranges,
        "initialFontSettings": font_settings(n2, activation_range),
        "alternateFontSettings": font_settings(alternate_n2, activation_range),
        "initialExpected": [float(expected_cases[0][index]) for index in selected],
        "alternateExpected": [float(expected_cases[1][index]) for index in selected],
        "surfaceCenter": center,
        "htmlBytes": len(html.encode()),
        "fontBytes": sum((FONT_OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "runtimeJavascript": False,
    }
    (OUT / f"{stem}-reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        {
            "inputs": INPUT_COUNT,
            "outputs": OUTPUT_COUNT,
            "html_bytes": reference["htmlBytes"],
        }
    )


if __name__ == "__main__":
    main()
