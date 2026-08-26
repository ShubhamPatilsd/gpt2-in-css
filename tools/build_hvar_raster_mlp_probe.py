#!/usr/bin/env python3
"""Connect real HVAR GPT-2 FC geometry to an SVG 3,072→768 projection."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

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
PROJECTION_SHARD = int(os.environ.get("HVAR_RASTER_PROJECTION_SHARD", "256"))
if MLP_WIDTH % PROJECTION_SHARD:
    raise ValueError("HVAR_RASTER_PROJECTION_SHARD must divide 3072")
PROJECTION_BUCKETS = int(os.environ.get("HVAR_RASTER_PROJECTION_BUCKETS", "1"))
if not 1 <= PROJECTION_BUCKETS <= WIDTH:
    raise ValueError("HVAR_RASTER_PROJECTION_BUCKETS must be between 1 and 768")
PAGE_STEM = "mlp" if PROJECTION_SHARD == 256 else f"mlp-shard{PROJECTION_SHARD}"
if PROJECTION_BUCKETS > 1:
    PAGE_STEM += f"-buckets{PROJECTION_BUCKETS}"
SURFACE_CENTER = 128 / 255
CENTERED_GAIN = 1.9


def save_rg(path: Path, positive: np.ndarray, negative: np.ndarray) -> None:
    rgba = np.zeros((*positive.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(np.clip(positive, 0, 1) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(np.clip(negative, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_gray(path: Path, values: np.ndarray) -> None:
    image = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(image, mode="L").save(path, optimize=True)


def font_settings(vector: np.ndarray, activation_range: float) -> str:
    settings = []
    for index, value in enumerate(vector / activation_range):
        shard, local = divmod(index, 256)
        settings.append(f'"{packed_axis_tag(shard, local)}" {css_number(float(value))}')
    return ",".join(settings)


def projection_calibration(
    projection: np.ndarray,
    hidden_cases: list[np.ndarray],
    bias_residual: np.ndarray,
    hidden_range: float,
    shard_width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    weight_scales = np.maximum(np.max(np.abs(projection), axis=1), 1e-12)
    normalized_projection = projection / weight_scales[:, None]
    units = weight_scales * hidden_range
    normalized_bias = bias_residual / units

    divisor_bound = np.zeros(WIDTH, dtype=np.float64)
    magnitude_bound = np.zeros(WIDTH, dtype=np.float64)
    for hidden in hidden_cases:
        normalized_hidden = hidden / hidden_range
        partials = np.stack(
            [
                normalized_projection[:, start : start + shard_width]
                @ normalized_hidden[start : start + shard_width]
                for start in range(0, MLP_WIDTH, shard_width)
            ],
            axis=1,
        )
        cumulative = np.cumsum(partials, axis=1)
        divisor_bound = np.maximum(
            divisor_bound,
            np.maximum.reduce(
                (
                    np.max(np.abs(partials), axis=1),
                    np.max(np.abs(cumulative), axis=1),
                    np.abs(cumulative[:, -1] + normalized_bias),
                )
            ),
        )
        for start in range(0, MLP_WIDTH, shard_width):
            products = (
                normalized_projection[:, start : start + shard_width]
                * normalized_hidden[start : start + shard_width][None, :]
            )
            magnitude_bound = np.maximum(
                magnitude_bound,
                np.maximum(
                    np.maximum(products, 0).sum(axis=1),
                    np.maximum(-products, 0).sum(axis=1),
                ),
            )
    return (
        normalized_projection,
        units,
        np.maximum(divisor_bound * 1.02, 1e-6),
        np.maximum(magnitude_bound * 1.02, 1e-6),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()

    # Match the one-token block fixture used by the existing exact HVAR probes.
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])

    coordinates = np.arange(WIDTH, dtype=np.float64)
    alternate_n2 = n2 * 0.755 + np.sin(coordinates * 0.148 + 1) * 0.041
    input_cases = [n2, alternate_n2]
    activation_range = float(
        max(np.max(np.abs(vector)) for vector in input_cases) * 1.01
    )

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fonts.bases)

    def hidden_for(vector: np.ndarray) -> np.ndarray:
        raw = q_fc.codes.astype(np.float64) @ (vector / activation_range)
        pre = raw * activation_range * q_fc.scales + data["fc_bias"]
        return gelu_new(pre)

    hidden_cases = [hidden_for(vector) for vector in input_cases]
    # The bar encodes FC preactivation. The LUT turns that byte into signed GELU.
    pre_cases = [
        q_fc.reconstructed @ vector + data["fc_bias"] for vector in input_cases
    ]
    pre_min = float(min(np.min(value) for value in pre_cases) - 0.25)
    pre_max = float(max(np.max(value) for value in pre_cases) + 0.25)
    pre_span = pre_max - pre_min
    hidden_range = float(max(np.max(np.abs(value)) for value in hidden_cases) * 1.02)

    q_projection = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    projection = q_projection.reconstructed
    bias_residual = residual + data["mlp_proj_bias"]
    expected_cases = [bias_residual + projection @ hidden for hidden in hidden_cases]
    normalized_projection, projection_units, row_divisors, row_magnitudes = (
        projection_calibration(
            projection, hidden_cases, bias_residual, hidden_range, PROJECTION_SHARD
        )
    )
    projection_divisor = float(np.max(row_divisors))
    magnitude_divisor = float(np.max(row_magnitudes))
    metric = np.maximum(row_divisors, row_magnitudes)
    bucket_ids = np.zeros(WIDTH, dtype=np.int64)
    if PROJECTION_BUCKETS > 1:
        for bucket, indices in enumerate(
            np.array_split(np.argsort(metric), PROJECTION_BUCKETS)
        ):
            bucket_ids[indices] = bucket
    bucket_divisors = np.zeros(PROJECTION_BUCKETS, dtype=np.float64)
    bucket_magnitudes = np.zeros(PROJECTION_BUCKETS, dtype=np.float64)
    output_divisors = np.zeros(WIDTH, dtype=np.float64)
    for bucket in range(PROJECTION_BUCKETS):
        mask = bucket_ids == bucket
        bucket_divisors[bucket] = max(float(np.max(row_divisors[mask])), 1e-6)
        bucket_magnitudes[bucket] = max(float(np.max(row_magnitudes[mask])), 1e-6)
        output_divisors[mask] = bucket_divisors[bucket]

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

    asset_prefix = f"{PAGE_STEM}-projection"
    for stale in OUT.glob(f"{asset_prefix}-*.png"):
        stale.unlink()
    normalized_bias = bias_residual / projection_units
    for bucket in range(PROJECTION_BUCKETS):
        mask = bucket_ids == bucket
        for shard, start in enumerate(range(0, MLP_WIDTH, PROJECTION_SHARD)):
            weights = normalized_projection[:, start : start + PROJECTION_SHARD]
            weights = np.where(mask[:, None], weights, 0).T
            save_rg(
                OUT / f"{asset_prefix}-b{bucket}-weights-{shard}.png",
                np.maximum(weights, 0),
                np.maximum(-weights, 0),
            )
        encoded_bias = np.full(WIDTH, SURFACE_CENTER, dtype=np.float64)
        encoded_bias[mask] += (
            0.5 * normalized_bias[mask] / bucket_divisors[bucket]
        )
        save_gray(
            OUT / f"{asset_prefix}-b{bucket}-bias.png", encoded_bias[None, :]
        )
    for shard, start in enumerate(range(0, MLP_WIDTH, PROJECTION_SHARD)):
        weights = normalized_projection[:, start : start + PROJECTION_SHARD].T
        save_gray(
            OUT / f"{asset_prefix}-centered-weights-{shard}.png",
            SURFACE_CENTER + 0.5 * weights,
        )
    centered_bias = SURFACE_CENTER + 0.5 * normalized_bias / projection_divisor
    save_gray(
        OUT / f"{asset_prefix}-centered-bias.png", centered_bias[None, :]
    )

    lut_pre = np.linspace(pre_min, pre_max, 256)
    lut_hidden = gelu_new(lut_pre)
    positive_table = " ".join(
        css_number(float(value)) for value in np.clip(lut_hidden, 0, None) / hidden_range
    )
    negative_table = " ".join(
        css_number(float(value)) for value in np.clip(-lut_hidden, 0, None) / hidden_range
    )
    zero_table = "0 0"
    center = css_number(SURFACE_CENTER)
    sum_channels = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_channels = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    swap_red_green = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    bar_kernel = " ".join(["1"] * BAR_WIDTH)
    projection_kernel = " ".join(["1"] * PROJECTION_SHARD)

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
        f'<feFuncR type="table" tableValues="{positive_table}"/>'
        f'<feFuncG type="table" tableValues="{negative_table}"/>'
        f'<feFuncB type="table" tableValues="{zero_table}"/>'
        '<feFuncA type="identity"/></feComponentTransfer>',
    ]

    bucket_outputs: list[str] = []
    for bucket in range(PROJECTION_BUCKETS):
        bucket_magnitude = float(bucket_magnitudes[bucket])
        bucket_divisor = float(bucket_divisors[bucket])
        signed_coefficient = bucket_magnitude / (2 * bucket_divisor)
        signed = css_number(signed_coefficient)
        signed_gray = (
            f"{signed} -{signed} 0 0 {center}  "
            f"{signed} -{signed} 0 0 {center}  "
            f"{signed} -{signed} 0 0 {center}  0 0 0 0 1"
        )
        projected: list[str] = []
        for shard, start in enumerate(range(0, MLP_WIDTH, PROJECTION_SHARD)):
            prefix = f"b{bucket}s{shard}"
            primitives.extend(
                (
                    f'<feOffset in="hidden" dx="-{BAR_WIDTH - 1}" dy="-{start}" '
                    f'x="0" y="0" width="1" height="{PROJECTION_SHARD}" result="hcol{prefix}"/>',
                    f'<feTile in="hcol{prefix}" x="0" y="0" width="{WIDTH}" '
                    f'height="{PROJECTION_SHARD}" result="h{prefix}"/>',
                    f'<feColorMatrix in="h{prefix}" type="matrix" '
                    f'values="{swap_red_green}" result="hs{prefix}"/>',
                    f'<feImage href="{asset_prefix}-b{bucket}-weights-{shard}.png" x="0" y="0" '
                    f'width="{WIDTH}" height="{PROJECTION_SHARD}" preserveAspectRatio="none" result="pw{prefix}"/>',
                    f'<feComposite in="pw{prefix}" in2="h{prefix}" operator="arithmetic" '
                    f'k1="1" k2="0" k3="0" k4="0" result="psame{prefix}"/>',
                    f'<feComposite in="pw{prefix}" in2="hs{prefix}" operator="arithmetic" '
                    f'k1="1" k2="0" k3="0" k4="0" result="pcross{prefix}"/>',
                    f'<feColorMatrix in="psame{prefix}" type="matrix" '
                    f'values="{sum_channels}" result="ppositive{prefix}"/>',
                    f'<feColorMatrix in="pcross{prefix}" type="matrix" '
                    f'values="{negative_channels}" result="pnegative{prefix}"/>',
                    f'<feComposite in="ppositive{prefix}" in2="pnegative{prefix}" '
                    f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="psplit{prefix}"/>',
                    f'<feConvolveMatrix in="psplit{prefix}" order="1 {PROJECTION_SHARD}" '
                    f'kernelMatrix="{projection_kernel}" divisor="{css_number(bucket_magnitude)}" '
                    f'bias="0" targetX="0" targetY="{PROJECTION_SHARD - 1}" edgeMode="none" '
                    f'preserveAlpha="true" x="0" y="{PROJECTION_SHARD - 1}" width="{WIDTH}" height="1" '
                    f'result="psum{prefix}"/>',
                    f'<feColorMatrix in="psum{prefix}" type="matrix" '
                    f'values="{signed_gray}" result="projected{prefix}"/>',
                )
            )
            projected.append(f"projected{prefix}")

        accumulated = projected[0]
        for index, value in enumerate(projected[1:], 1):
            result = f"b{bucket}-projected-total-{index}"
            primitives.append(
                f'<feComposite in="{accumulated}" in2="{value}" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="-{center}" result="{result}"/>'
            )
            accumulated = result
        biased = f"b{bucket}-final"
        primitives.extend(
            (
                f'<feImage href="{asset_prefix}-b{bucket}-bias.png" x="0" '
                f'y="{PROJECTION_SHARD - 1}" width="{WIDTH}" height="1" '
                f'preserveAspectRatio="none" result="b{bucket}-bias"/>',
                f'<feComposite in="{accumulated}" in2="b{bucket}-bias" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="-{center}" result="{biased}"/>',
            )
        )
        bucket_outputs.append(biased)
    final = bucket_outputs[0]
    for bucket, value in enumerate(bucket_outputs[1:], 1):
        result = f"bucket-total-{bucket}"
        primitives.append(
            f'<feComposite in="{final}" in2="{value}" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center}" result="{result}"/>'
        )
        final = result
    primitives.append(f'<feOffset in="{final}" result="final"/>')

    html = f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HVAR raster GPT-2 MLP</title>
<style>
{faces}
html{{background:transparent}}
body{{margin:0}}
svg{{position:fixed;left:0;top:0}}
.bank{{display:grid;grid-template-rows:repeat({MLP_WIDTH},1px);width:{WIDTH}px;height:{MLP_WIDTH}px;
  font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;
  font-variation-settings:{font_settings(n2, activation_range)};
  background:transparent;filter:url(#mlp);contain:strict}}
.bar{{display:block;justify-self:start;height:1px;min-width:0;max-width:{BAR_WIDTH}px;overflow:hidden;
  white-space:pre;font-style:normal;color:transparent;background:#f00;width:0;
  width:calc-size(max-content,clamp(0px,
    (((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - {base_total}) * var(--factor)
      + var(--bias) - {css_number(pre_min)}) / {css_number(pre_span)} * {BAR_WIDTH}px,
    {BAR_WIDTH}px))}}
</style>
<svg width="0" height="0" aria-hidden="true">
  <filter id="mlp" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{WIDTH}" height="{MLP_WIDTH}" color-interpolation-filters="sRGB">
    {''.join(primitives)}
  </filter>
</svg>
<div id="bank" class="bank">{''.join(bars)}</div>
'''
    (OUT / f"{PAGE_STEM}.html").write_text(html)

    centered_table = " ".join(
        css_number(float(SURFACE_CENTER + 0.5 * value / hidden_range))
        for value in lut_hidden
    )
    centered_primitives: list[str] = [
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
    centered_projected: list[str] = []
    centered_k2 = -CENTERED_GAIN * SURFACE_CENTER
    centered_k4 = SURFACE_CENTER + CENTERED_GAIN * SURFACE_CENTER * SURFACE_CENTER
    centered_convolution_divisor = CENTERED_GAIN * projection_divisor / 2
    centered_convolution_bias = (
        SURFACE_CENTER
        - PROJECTION_SHARD * SURFACE_CENTER / centered_convolution_divisor
    )
    for shard, start in enumerate(range(0, MLP_WIDTH, PROJECTION_SHARD)):
        centered_primitives.extend(
            (
                f'<feOffset in="hidden" dx="-{BAR_WIDTH - 1}" dy="-{start}" '
                f'x="0" y="0" width="1" height="{PROJECTION_SHARD}" result="hcol{shard}"/>',
                f'<feTile in="hcol{shard}" x="0" y="0" width="{WIDTH}" '
                f'height="{PROJECTION_SHARD}" result="h{shard}"/>',
                f'<feImage href="{asset_prefix}-centered-weights-{shard}.png" x="0" y="0" '
                f'width="{WIDTH}" height="{PROJECTION_SHARD}" preserveAspectRatio="none" result="pw{shard}"/>',
                f'<feComposite in="pw{shard}" in2="h{shard}" operator="arithmetic" '
                f'k1="{CENTERED_GAIN}" k2="{css_number(centered_k2)}" '
                f'k3="{css_number(centered_k2)}" k4="{css_number(centered_k4)}" '
                f'result="pcentered{shard}"/>',
                f'<feConvolveMatrix in="pcentered{shard}" order="1 {PROJECTION_SHARD}" '
                f'kernelMatrix="{projection_kernel}" divisor="{css_number(centered_convolution_divisor)}" '
                f'bias="{css_number(centered_convolution_bias)}" targetX="0" '
                f'targetY="{PROJECTION_SHARD - 1}" edgeMode="none" preserveAlpha="false" '
                f'x="0" y="{PROJECTION_SHARD - 1}" width="{WIDTH}" height="1" '
                f'result="projected{shard}"/>',
            )
        )
        centered_projected.append(f"projected{shard}")
    centered_accumulated = centered_projected[0]
    for index, value in enumerate(centered_projected[1:], 1):
        result = f"projected-total-{index}"
        centered_primitives.append(
            f'<feComposite in="{centered_accumulated}" in2="{value}" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center}" result="{result}"/>'
        )
        centered_accumulated = result
    centered_primitives.extend(
        (
            f'<feImage href="{asset_prefix}-centered-bias.png" x="0" y="{PROJECTION_SHARD - 1}" '
            f'width="{WIDTH}" height="1" preserveAspectRatio="none" result="projection-bias"/>',
            f'<feComposite in="{centered_accumulated}" in2="projection-bias" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center}" result="final"/>',
        )
    )
    centered_html = f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Centered HVAR raster GPT-2 MLP</title>
<style>
{faces}
html{{background:transparent}}
body{{margin:0}}
svg{{position:fixed;left:0;top:0}}
.bank{{display:grid;grid-template-rows:repeat({MLP_WIDTH},1px);width:{WIDTH}px;height:{MLP_WIDTH}px;
  font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;
  font-variation-settings:{font_settings(n2, activation_range)};
  background:transparent;filter:url(#mlp);contain:strict}}
.bar{{display:block;justify-self:start;height:1px;min-width:0;max-width:{BAR_WIDTH}px;overflow:hidden;
  white-space:pre;font-style:normal;color:transparent;background:#f00;width:0;
  width:calc-size(max-content,clamp(0px,
    (((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - {base_total}) * var(--factor)
      + var(--bias) - {css_number(pre_min)}) / {css_number(pre_span)} * {BAR_WIDTH}px,
    {BAR_WIDTH}px))}}
</style>
<svg width="0" height="0" aria-hidden="true">
  <filter id="mlp" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{WIDTH}" height="{MLP_WIDTH}" color-interpolation-filters="sRGB">
    {''.join(centered_primitives)}
  </filter>
</svg>
<div id="bank" class="bank">{''.join(bars)}</div>
'''
    centered_stem = f"{PAGE_STEM}-centered"
    (OUT / f"{centered_stem}.html").write_text(centered_html)

    reference = {
        "width": WIDTH,
        "hiddenWidth": MLP_WIDTH,
        "readRow": PROJECTION_SHARD - 1,
        "projectionShard": PROJECTION_SHARD,
        "surfaceCenter": SURFACE_CENTER,
        "projectionDivisor": projection_divisor,
        "projectionDivisors": output_divisors.tolist(),
        "projectionBuckets": PROJECTION_BUCKETS,
        "bucketDivisors": bucket_divisors.tolist(),
        "bucketMagnitudes": bucket_magnitudes.tolist(),
        "projectionUnits": projection_units.tolist(),
        "initialFontSettings": font_settings(n2, activation_range),
        "alternateFontSettings": font_settings(alternate_n2, activation_range),
        "initialExpected": expected_cases[0].tolist(),
        "alternateExpected": expected_cases[1].tolist(),
        "hiddenRange": hidden_range,
        "preRange": [pre_min, pre_max],
        "magnitudeDivisor": magnitude_divisor,
        "htmlBytes": len(html.encode()),
        "assetBytes": sum(path.stat().st_size for path in OUT.glob(f"{asset_prefix}-*.png")),
        "fontBytes": sum((FONT_OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "runtimeJavascript": False,
        "centeredGain": CENTERED_GAIN,
        "centeredHtmlBytes": len(centered_html.encode()),
    }
    (OUT / f"{PAGE_STEM}-reference.json").write_text(
        json.dumps(reference, indent=2) + "\n"
    )
    (OUT / f"{centered_stem}-reference.json").write_text(
        json.dumps(reference, indent=2) + "\n"
    )
    print(
        {
            "html_bytes": reference["htmlBytes"],
            "asset_bytes": reference["assetBytes"],
            "projection_divisor": projection_divisor,
            "magnitude_divisor": magnitude_divisor,
        }
    )


if __name__ == "__main__":
    main()
