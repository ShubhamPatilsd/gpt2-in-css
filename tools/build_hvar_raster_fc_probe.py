#!/usr/bin/env python3
"""Bridge the real GPT-2 HVAR FC output into one SVG raster vector."""

from __future__ import annotations

import json
import math
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
OUT = ROOT / "experiments" / "hvar-raster-fc"
FONT_SIZE = 512
BAR_WIDTH = 256
LUT_SIZE = 256


def font_settings(vector: np.ndarray, activation_range: float) -> str:
    values = vector / activation_range
    settings = []
    for index, value in enumerate(values):
        shard, local = divmod(index, 256)
        settings.append(
            f'"{packed_axis_tag(shard, local)}" {css_number(float(value))}'
        )
    return ",".join(settings)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    # Six calibration states and two held-out states exercise changing HVAR
    # axes without requiring a second checkpoint fixture.
    coordinates = np.arange(WIDTH, dtype=np.float64)
    case_vectors = [n2]
    for case_index in range(1, 8):
        scale = 0.72 + case_index * 0.035
        phase = np.sin(coordinates * (0.137 + case_index * 0.011) + case_index)
        case_vectors.append(n2 * scale + phase * (0.035 + case_index * 0.006))
    alternate_n2 = case_vectors[1]
    activation_range = float(
        max(np.max(np.abs(vector)) for vector in case_vectors) * 1.01
    )

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fonts.bases)

    def evaluate(vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raw = q_fc.codes.astype(np.float64) @ (vector / activation_range)
        pre = raw * activation_range * q_fc.scales + data["fc_bias"]
        return pre, gelu_new(pre)

    evaluated_cases = [evaluate(vector) for vector in case_vectors]
    pre, hidden = evaluated_cases[0]
    alternate_pre, alternate_hidden = evaluated_cases[1]
    pre_min = float(min(np.min(pre), np.min(alternate_pre)) - 0.25)
    pre_max = float(max(np.max(pre), np.max(alternate_pre)) + 0.25)
    pre_span = pre_max - pre_min
    dense_pre = np.linspace(pre_min, pre_max, 16385)
    dense_hidden = gelu_new(dense_pre)
    hidden_min = float(np.min(dense_hidden))
    hidden_max = float(np.max(dense_hidden))
    hidden_span = hidden_max - hidden_min
    lut_pre = np.linspace(pre_min, pre_max, LUT_SIZE)
    lut = (gelu_new(lut_pre) - hidden_min) / hidden_span
    lut_text = " ".join(css_number(float(value)) for value in lut)

    faces = "".join(
        f'@font-face{{font-family:fcS{shard};src:url("../gpt2-block-css/{name}.woff2?v={tag}") '
        f'format("woff2");unicode-range:U+{start:X}-{start + MLP_WIDTH - 1:X}}}'
        for shard, (name, tag, start) in enumerate(
            zip(fonts.names, fonts.tags, fonts.codepoint_starts, strict=True)
        )
    )
    bars = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        factor = activation_range * q_fc.scales[output]
        bias = data["fc_bias"][output]
        bars.append(
            '<i class="bar" style="--factor:'
            f'{css_number(float(factor))};--bias:{css_number(float(bias))}">'
            f"{characters}</i>"
        )
    kernel = " ".join(["1"] * BAR_WIDTH)
    html = f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Real GPT-2 HVAR FC to raster vector</title>
<style>
{faces}
html{{background:transparent}}
body{{margin:0}}
svg{{position:fixed;left:0;top:0}}
.bank{{display:grid;grid-template-rows:repeat({MLP_WIDTH},1px);width:{BAR_WIDTH}px;height:{MLP_WIDTH}px;
  font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;
  font-variation-settings:{font_settings(n2, activation_range)};
  background:transparent;filter:url(#reduce-bars);contain:strict}}
.bar{{display:block;height:1px;min-width:0;max-width:{BAR_WIDTH}px;overflow:hidden;
  white-space:pre;font-style:normal;color:transparent;background:#f00;
  width:calc-size(max-content,clamp(0px,
    (((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - {base_total}) * var(--factor)
      + var(--bias) - {css_number(pre_min)}) / {css_number(pre_span)} * {BAR_WIDTH}px,
    {BAR_WIDTH}px))}}
</style>
<svg width="0" height="0" aria-hidden="true">
  <filter id="reduce-bars" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{BAR_WIDTH}" height="{MLP_WIDTH}" color-interpolation-filters="sRGB">
    <feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}"
      kernelMatrix="{kernel}" divisor="{BAR_WIDTH}" bias="0" edgeMode="none"
      preserveAlpha="false" x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="pre"/>
    <feColorMatrix in="pre" type="matrix"
      values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"
      x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="pre-rgb"/>
    <feComponentTransfer in="pre-rgb" x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="hidden">
      <feFuncR type="table" tableValues="{lut_text}"/>
      <feFuncG type="table" tableValues="{lut_text}"/>
      <feFuncB type="table" tableValues="{lut_text}"/>
      <feFuncA type="identity"/>
    </feComponentTransfer>
    <feOffset in="hidden" dx="-{BAR_WIDTH - 1}" dy="0" x="0" y="0" width="1" height="{MLP_WIDTH}"/>
  </filter>
</svg>
<div id="bank" class="bank">{''.join(bars)}</div>
'''
    (OUT / "index.html").write_text(html)

    calibration_hidden = np.stack(
        [case_hidden for _, case_hidden in evaluated_cases[:6]], axis=0
    )
    channel_low = np.min(calibration_hidden, axis=0)
    channel_high = np.max(calibration_hidden, axis=0)
    channel_span = np.maximum(channel_high - channel_low, 0.05)
    channel_center = (channel_low + channel_high) / 2
    channel_margin = channel_span * 0.1 + 0.005
    channel_low = channel_center - channel_span / 2 - channel_margin
    channel_high = channel_center + channel_span / 2 + channel_margin
    channel_span = channel_high - channel_low

    per_channel_bars = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        factor = activation_range * q_fc.scales[output]
        bias = data["fc_bias"][output]
        per_channel_bars.append(
            '<i class="bar" style="--factor:'
            f'{css_number(float(factor))};--bias:{css_number(float(bias))};'
            f'--hidden-min:{css_number(float(channel_low[output]))};'
            f'--hidden-span:{css_number(float(channel_span[output]))}">'
            f"{characters}</i>"
        )
    pre_css = (
        f"(((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - {base_total}) "
        "* var(--factor) + var(--bias))"
    )
    # The compact sigmoid form is a standard close GELU approximation. It is
    # evaluated while `size` still denotes the HVAR glyph's intrinsic width.
    gelu_css = (
        f"({pre_css} / (1 + exp(-1.702 * clamp(-10,{pre_css},10))))"
    )
    per_channel_html = f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Real GPT-2 HVAR FC to per-channel raster vector</title>
<style>
{faces}
html{{background:transparent}}
body{{margin:0}}
svg{{position:fixed;left:0;top:0}}
.bank{{display:grid;grid-template-rows:repeat({MLP_WIDTH},1px);width:{BAR_WIDTH}px;height:{MLP_WIDTH}px;
  font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;
  font-variation-settings:{font_settings(n2, activation_range)};
  background:transparent;filter:url(#reduce-bars);contain:strict}}
.bar{{display:block;justify-self:start;height:1px;min-width:0;max-width:{BAR_WIDTH}px;overflow:hidden;
  white-space:pre;font-style:normal;color:transparent;background:#f00;
  width:0;
  width:calc-size(max-content,clamp(0px,
    ({gelu_css} - var(--hidden-min)) / var(--hidden-span) * {BAR_WIDTH}px,
    {BAR_WIDTH}px))}}
</style>
<svg width="0" height="0" aria-hidden="true">
  <filter id="reduce-bars" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{BAR_WIDTH}" height="{MLP_WIDTH}" color-interpolation-filters="sRGB">
    <feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}"
      kernelMatrix="{kernel}" divisor="{BAR_WIDTH}" bias="0" edgeMode="none"
      preserveAlpha="false" x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="hidden"/>
    <feColorMatrix in="hidden" type="matrix"
      values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"
      x="{BAR_WIDTH - 1}" y="0" width="1" height="{MLP_WIDTH}" result="hidden-rgb"/>
    <feOffset in="hidden-rgb" dx="-{BAR_WIDTH - 1}" dy="0" x="0" y="0" width="1" height="{MLP_WIDTH}"/>
  </filter>
</svg>
<div id="bank" class="bank">{''.join(per_channel_bars)}</div>
'''
    (OUT / "per-channel.html").write_text(per_channel_html)

    cases = [
        {
            "fontSettings": font_settings(vector, activation_range),
            "expectedHidden": case_hidden.tolist(),
            "calibration": index < 6,
        }
        for index, (vector, (_, case_hidden)) in enumerate(
            zip(case_vectors, evaluated_cases, strict=True)
        )
    ]
    reference = {
        "width": WIDTH,
        "outputWidth": MLP_WIDTH,
        "fontSize": FONT_SIZE,
        "barWidth": BAR_WIDTH,
        "preMin": pre_min,
        "preMax": pre_max,
        "hiddenMin": hidden_min,
        "hiddenMax": hidden_max,
        "initialFontSettings": font_settings(n2, activation_range),
        "alternateFontSettings": font_settings(alternate_n2, activation_range),
        "initialHidden": hidden.tolist(),
        "alternateHidden": alternate_hidden.tolist(),
        "perChannelHiddenMin": channel_low.tolist(),
        "perChannelHiddenMax": channel_high.tolist(),
        "cases": cases,
        "htmlBytes": len(html.encode()),
        "perChannelHtmlBytes": len(per_channel_html.encode()),
        "fontBytes": sum((FONT_OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "runtimeJavascript": False,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "outputs": MLP_WIDTH,
        "html_bytes": reference["htmlBytes"],
        "font_bytes": reference["fontBytes"],
        "pre_range": [pre_min, pre_max],
        "hidden_range": [hidden_min, hidden_max],
    })


if __name__ == "__main__":
    main()
