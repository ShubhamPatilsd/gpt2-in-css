#!/usr/bin/env python3
"""Build a signed SVG-filter probe for GPT-2's real 768→3,072 FC affine map."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image

from build_gpt2_block_css import QUANT_BITS, gelu_new, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(
    os.environ.get(
        "SVG_FC_OUT", ROOT / "experiments" / "svg-filter-gpt2-fc"
    )
).resolve()
INPUTS = 768
OUTPUTS = 3072
SHARD = 256
CENTERED_FC = os.environ.get("SVG_FC_CENTERED_DOT", "0") == "1"
CENTERED_PROJECTION = os.environ.get("SVG_PROJECTION_CENTERED_DOT", "0") == "1"
CENTERED_GAIN = float(os.environ.get("SVG_CENTERED_DOT_GAIN", "1.9"))
if CENTERED_GAIN <= 0:
    raise ValueError("SVG_CENTERED_DOT_GAIN must be positive")
PROJECTION_CENTERED_GAIN = float(
    os.environ.get("SVG_PROJECTION_CENTERED_GAIN", str(CENTERED_GAIN))
)
if PROJECTION_CENTERED_GAIN <= 0:
    raise ValueError("SVG_PROJECTION_CENTERED_GAIN must be positive")
RESIDUAL_REFERENCE = os.environ.get("SVG_FC_RESIDUAL_REFERENCE")
BLOCK_INDEX = int(os.environ.get("SVG_FC_BLOCK", "0"))


def save_rg(path: Path, positive: np.ndarray, negative: np.ndarray) -> None:
    rgba = np.zeros((*positive.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(np.clip(positive, 0, 1) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(np.clip(negative, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8), mode="L").save(
        path, optimize=True
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in (
        "weights*.png",
        "vector*.png",
        "projection-weights*.png",
    ):
        for stale in OUT.glob(pattern):
            stale.unlink()
    data = model_data(block_index=BLOCK_INDEX)
    if RESIDUAL_REFERENCE:
        residual_payload = json.loads(Path(RESIDUAL_REFERENCE).read_text())
        residual_value = residual_payload.get(
            "expectedResidual", residual_payload.get("expected_residual")
        )
        if residual_value is None:
            raise ValueError("Residual reference has no expected residual")
        residual = np.asarray(residual_value, dtype=np.float64)
        if residual.ndim == 2:
            residual = residual[-1]
    else:
        # Reproduce the input to the first block's MLP, including quantized
        # composed one-token attention, matching the original CSS block probe.
        composed_weight = data["attn_proj_weight"] @ data["v_weight"]
        composed_bias = (
            data["attn_proj_weight"] @ data["v_bias"]
            + data["attn_proj_bias"]
        )
        q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
        n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
        residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    weights = q_fc.reconstructed
    expected = weights @ n2 + data["fc_bias"]
    hidden_expected = gelu_new(expected)
    q_projection = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    projection_weights = q_projection.reconstructed
    final_expected = (
        residual + projection_weights @ hidden_expected + data["mlp_proj_bias"]
    )

    weight_scales = np.max(np.abs(weights), axis=1)
    weight_scales = np.maximum(weight_scales, 1e-12)
    input_scale = float(np.max(np.abs(n2)))
    units = weight_scales * input_scale
    normalized_weights = weights / weight_scales[:, None]
    normalized_input = n2 / input_scale
    partials = np.stack(
        [
            normalized_weights[:, start : start + SHARD]
            @ normalized_input[start : start + SHARD]
            for start in range(0, INPUTS, SHARD)
        ],
        axis=1,
    )
    normalized_bias = data["fc_bias"] / units
    surface_center = 128 / 255
    # The convolution maps each signed partial to .5 + .5*partial/D. Pick one
    # global D large enough that partial sums, combined sums, and learned bias
    # stay inside the filter channel's [0,1] range for this real model input.
    cumulative = np.cumsum(partials, axis=1)
    bound = max(
        float(np.max(np.abs(partials))),
        float(np.max(np.abs(cumulative))),
        float(np.max(np.abs(cumulative[:, -1] + normalized_bias))),
    )
    divisor = max(1e-6, bound * 1.02)
    magnitude_bound = 0.0
    for start in range(0, INPUTS, SHARD):
        products = (
            normalized_weights[:, start : start + SHARD]
            * normalized_input[start : start + SHARD][None, :]
        )
        magnitude_bound = max(
            magnitude_bound,
            float(np.max(np.maximum(products, 0).sum(axis=1))),
            float(np.max(np.maximum(-products, 0).sum(axis=1))),
        )
    magnitude_divisor = max(1e-6, magnitude_bound * 1.02)

    for shard, start in enumerate(range(0, INPUTS, SHARD)):
        w = normalized_weights[:, start : start + SHARD]
        x = normalized_input[start : start + SHARD][None, :]
        x_alt = -x
        if CENTERED_FC:
            save_gray(
                OUT / f"weights-centered-{shard}.png",
                surface_center + 0.5 * w,
            )
            save_gray(
                OUT / f"vector-centered-{shard}.png",
                surface_center + 0.5 * x,
            )
        else:
            save_rg(
                OUT / f"weights-{shard}.png",
                np.maximum(w, 0),
                np.maximum(-w, 0),
            )
            save_rg(
                OUT / f"vector-{shard}.png",
                np.maximum(x, 0),
                np.maximum(-x, 0),
            )
            save_rg(
                OUT / f"vector-swapped-{shard}.png",
                np.maximum(-x, 0),
                np.maximum(x, 0),
            )
            save_rg(
                OUT / f"vector-alt-{shard}.png",
                np.maximum(x_alt, 0),
                np.maximum(-x_alt, 0),
            )
            save_rg(
                OUT / f"vector-alt-swapped-{shard}.png",
                np.maximum(-x_alt, 0),
                np.maximum(x_alt, 0),
            )
    encoded_bias = surface_center + 0.5 * normalized_bias / divisor
    save_gray(OUT / "bias.png", encoded_bias[:, None])

    kernel = " ".join("1" for _ in range(SHARD))
    sum_channels = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_channels = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    center_css = f"{surface_center:.12g}"
    signed_coefficient = magnitude_divisor / (2 * divisor)
    signed_coefficient_css = f"{signed_coefficient:.12g}"
    signed_gray = (
        f"{signed_coefficient_css} -{signed_coefficient_css} 0 0 {center_css}  "
        f"{signed_coefficient_css} -{signed_coefficient_css} 0 0 {center_css}  "
        f"{signed_coefficient_css} -{signed_coefficient_css} 0 0 {center_css}  "
        "0 0 0 0 1"
    )
    centered_k1 = CENTERED_GAIN
    centered_k2 = -CENTERED_GAIN * surface_center
    centered_k4 = surface_center + CENTERED_GAIN * surface_center * surface_center
    primitives: list[str] = []
    for shard in range(INPUTS // SHARD):
        if CENTERED_FC:
            primitives.extend(
                (
                    f'<feImage href="weights-centered-{shard}.png" x="0" y="0" '
                    f'width="{SHARD}" height="{OUTPUTS}" '
                    f'preserveAspectRatio="none" result="w{shard}"/>',
                    f'<feImage href="vector-centered-{shard}.png" x="0" y="0" '
                    f'width="{SHARD}" height="1" '
                    f'preserveAspectRatio="none" result="vrow{shard}"/>',
                    f'<feTile in="vrow{shard}" x="0" y="0" width="{SHARD}" '
                    f'height="{OUTPUTS}" result="v{shard}"/>',
                    f'<feComposite in="w{shard}" in2="v{shard}" '
                    f'operator="arithmetic" k1="{centered_k1}" '
                    f'k2="{centered_k2}" k3="{centered_k2}" '
                    f'k4="{centered_k4}" result="centered{shard}"/>',
                )
            )
        else:
            primitives.extend(
                (
                f'<feImage href="weights-{shard}.png" x="0" y="0" width="{SHARD}" '
                f'height="{OUTPUTS}" preserveAspectRatio="none" result="w{shard}"/>',
                f'<feImage href="vector-{shard}.png" x="0" y="0" width="{SHARD}" '
                f'height="1" preserveAspectRatio="none" result="vrow{shard}"/>',
                f'<feTile in="vrow{shard}" x="0" y="0" width="{SHARD}" '
                f'height="{OUTPUTS}" result="v{shard}"/>',
                f'<feImage href="vector-swapped-{shard}.png" x="0" y="0" '
                f'width="{SHARD}" height="1" preserveAspectRatio="none" '
                f'result="vsrow{shard}"/>',
                f'<feTile in="vsrow{shard}" x="0" y="0" width="{SHARD}" '
                f'height="{OUTPUTS}" result="vs{shard}"/>',
                f'<feComposite in="w{shard}" in2="v{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="same{shard}"/>',
                f'<feComposite in="w{shard}" in2="vs{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="cross{shard}"/>',
                f'<feColorMatrix in="same{shard}" type="matrix" values="{sum_channels}" '
                f'result="positive{shard}"/>',
                f'<feColorMatrix in="cross{shard}" type="matrix" values="{negative_channels}" '
                f'result="negative{shard}"/>',
                f'<feComposite in="positive{shard}" in2="negative{shard}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="split{shard}"/>',
                )
            )
    fc_shards = INPUTS // SHARD
    fc_group_size = int(os.environ.get("SVG_FC_GROUP", "1"))
    if fc_shards % fc_group_size:
        raise ValueError("SVG_FC_GROUP must divide three FC shards")
    fc_groups: list[str] = []
    for group, group_start in enumerate(range(0, fc_shards, fc_group_size)):
        group_stop = group_start + fc_group_size
        input_prefix = "centered" if CENTERED_FC else "split"
        accumulated = f"fc-{input_prefix}-acc-{group}-0"
        primitives.append(
            f'<feComposite in="{input_prefix}{group_start}" '
            f'in2="{input_prefix}{group_start}" '
            f'operator="arithmetic" k1="0" k2="{1 / fc_group_size}" '
            f'k3="0" k4="0" result="{accumulated}"/>'
        )
        for within_group, shard in enumerate(range(group_start + 1, group_stop), 1):
            result = f"fc-{input_prefix}-acc-{group}-{within_group}"
            primitives.append(
                f'<feComposite in="{accumulated}" in2="{input_prefix}{shard}" '
                f'operator="arithmetic" k1="0" k2="1" '
                f'k3="{1 / fc_group_size}" k4="0" result="{result}"/>'
            )
            accumulated = result
        group_sum = f"fc-split-sum-{group}"
        encoded_group = f"fc-encoded-group-{group}"
        if CENTERED_FC:
            convolution_divisor = CENTERED_GAIN * divisor / (2 * fc_group_size)
            convolution_bias = (
                surface_center - SHARD * surface_center / convolution_divisor
            )
            primitives.append(
                f'<feConvolveMatrix in="{accumulated}" order="{SHARD} 1" '
                f'kernelMatrix="{kernel}" divisor="{convolution_divisor}" '
                f'bias="{convolution_bias}" targetX="{SHARD - 1}" targetY="0" '
                f'edgeMode="none" kernelUnitLength="1 1" '
                f'preserveAlpha="false" x="{SHARD - 1}" y="0" width="1" '
                f'height="{OUTPUTS}" result="{encoded_group}"/>'
            )
        else:
            primitives.extend(
                (
                f'<feConvolveMatrix in="{accumulated}" order="{SHARD} 1" '
                f'kernelMatrix="{kernel}" divisor="{magnitude_divisor / fc_group_size}" '
                f'bias="0" targetX="{SHARD - 1}" targetY="0" edgeMode="none" '
                f'kernelUnitLength="1 1" preserveAlpha="true" x="{SHARD - 1}" '
                f'y="0" width="1" height="{OUTPUTS}" result="{group_sum}"/>',
                f'<feColorMatrix in="{group_sum}" type="matrix" '
                f'values="{signed_gray}" result="{encoded_group}"/>',
                )
            )
        fc_groups.append(encoded_group)
    dot = fc_groups[0]
    for group, encoded_group in enumerate(fc_groups[1:], 1):
        result = f"fc-dot-{group}"
        primitives.append(
            f'<feComposite in="{dot}" in2="{encoded_group}" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center_css}" result="{result}"/>'
        )
        dot = result
    primitives.extend(
        (
            f'<feImage href="bias.png" x="{SHARD - 1}" y="0" width="1" '
            f'height="{OUTPUTS}" preserveAspectRatio="none" result="bias"/>',
            f'<feComposite in="{dot}" in2="bias" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center_css}" result="affine"/>',
        )
    )
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>SVG filter GPT-2 768→3,072 FC probe</title>
<style>
  html, body {{ margin: 0; background: black; }}
  svg {{ display: block; width: {SHARD}px; height: {OUTPUTS}px; image-rendering: pixelated; }}
</style>
<svg viewBox="0 0 {SHARD} {OUTPUTS}" xmlns="http://www.w3.org/2000/svg">
  <filter id="fc" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
          x="0" y="0" width="{SHARD}" height="{OUTPUTS}"
          color-interpolation-filters="sRGB">
    {''.join(primitives)}
  </filter>
  <rect width="{SHARD}" height="{OUTPUTS}" fill="white" filter="url(#fc)"/>
</svg>
'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "inputs": INPUTS,
                "outputs": OUTPUTS,
                "block_index": BLOCK_INDEX,
                "centered_dot": CENTERED_FC,
                "centered_gain": CENTERED_GAIN if CENTERED_FC else None,
                "divisor": divisor,
                "magnitude_divisor": magnitude_divisor,
                "magnitude_bound": magnitude_bound,
                "weight_scales": weight_scales.tolist(),
                "input_scale": input_scale,
                "units": units.tolist(),
                "surface_center": surface_center,
                "expected": expected.tolist(),
                "decode": "(red[row] - surface_center) * 2 * divisor * units[row]",
                "read_column": SHARD - 1,
            }
        )
        + "\n"
    )

    # Continue without a CSS readback: normalize each row-specific FC result to
    # one common preactivation range, apply GELU as a transfer table, tile that
    # vertical activation strip across twelve projection weight images, and
    # reduce each 256-row shard to one horizontal output strip.
    pre_range = float(np.max(np.abs(expected)) * 1.02)
    max_unit = float(np.max(units))
    save_gray(OUT / "pre-scales.png", (units / max_unit)[:, None])
    pre_scale_coefficient = divisor * max_unit / pre_range
    copy_red = "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
    full_primitives = list(primitives)
    full_primitives.extend(
        (
            f'<feImage href="pre-scales.png" x="{SHARD - 1}" y="0" width="1" '
            f'height="{OUTPUTS}" preserveAspectRatio="none" result="pre-scales"/>',
            '<feComposite in="affine" in2="pre-scales" operator="arithmetic" '
            f'k1="{pre_scale_coefficient}" k2="0" '
            f'k3="{-pre_scale_coefficient * surface_center}" k4="{center_css}" '
            'result="pre-normalized-alpha"/>',
            f'<feColorMatrix in="pre-normalized-alpha" type="matrix" values="{copy_red}" '
            'result="pre-normalized"/>',
        )
    )
    table_input = np.linspace(0, 1, 256)
    table_pre = (table_input - surface_center) * 2 * pre_range
    table_hidden = gelu_new(table_pre)
    hidden_range = float(np.max(np.abs(hidden_expected)) * 1.02)
    positive_table = " ".join(
        f"{value:.8g}" for value in np.clip(table_hidden, 0, None) / hidden_range
    )
    negative_table = " ".join(
        f"{value:.8g}" for value in np.clip(-table_hidden, 0, None) / hidden_range
    )
    zero_table = "0 0"
    full_primitives.append(
        '<feComponentTransfer in="pre-normalized" result="hidden">'
        f'<feFuncR type="table" tableValues="{positive_table}"/>'
        f'<feFuncG type="table" tableValues="{negative_table}"/>'
        f'<feFuncB type="table" tableValues="{zero_table}"/>'
        '<feFuncA type="identity"/>'
        '</feComponentTransfer>'
    )
    hidden_common = "hidden"
    if CENTERED_PROJECTION:
        hidden_common = "hidden-common"
        signed_to_common = (
            f".5 -.5 0 0 {center_css}  " * 3 + "0 0 0 0 1"
        )
        full_primitives.append(
            f'<feColorMatrix in="hidden" values="{signed_to_common}" '
            f'result="{hidden_common}"/>'
        )

    projection_weight_scales = np.max(np.abs(projection_weights), axis=1)
    projection_weight_scales = np.maximum(projection_weight_scales, 1e-12)
    projection_units = projection_weight_scales * hidden_range
    normalized_projection = projection_weights / projection_weight_scales[:, None]
    normalized_hidden = hidden_expected / hidden_range
    projection_partials = np.stack(
        [
            normalized_projection[:, start : start + SHARD]
            @ normalized_hidden[start : start + SHARD]
            for start in range(0, OUTPUTS, SHARD)
        ],
        axis=1,
    )
    normalized_projection_bias = (
        data["mlp_proj_bias"] + residual
    ) / projection_units
    projection_cumulative = np.cumsum(projection_partials, axis=1)
    projection_bound = max(
        float(np.max(np.abs(projection_partials))),
        float(np.max(np.abs(projection_cumulative))),
        float(
            np.max(
                np.abs(projection_cumulative[:, -1] + normalized_projection_bias)
            )
        ),
    )
    projection_divisor = max(1e-6, projection_bound * 1.02)
    projection_magnitude_bound = 0.0
    for start in range(0, OUTPUTS, SHARD):
        products = (
            normalized_projection[:, start : start + SHARD]
            * normalized_hidden[start : start + SHARD][None, :]
        )
        projection_magnitude_bound = max(
            projection_magnitude_bound,
            float(np.max(np.maximum(products, 0).sum(axis=1))),
            float(np.max(np.maximum(-products, 0).sum(axis=1))),
        )
    projection_magnitude_divisor = max(1e-6, projection_magnitude_bound * 1.02)
    projection_signed_coefficient = projection_magnitude_divisor / (
        2 * projection_divisor
    )
    projection_signed_css = f"{projection_signed_coefficient:.12g}"
    projection_signed_gray = (
        f"{projection_signed_css} -{projection_signed_css} 0 0 {center_css}  "
        f"{projection_signed_css} -{projection_signed_css} 0 0 {center_css}  "
        f"{projection_signed_css} -{projection_signed_css} 0 0 {center_css}  "
        "0 0 0 0 1"
    )
    swap_red_green = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    for shard, start in enumerate(range(0, OUTPUTS, SHARD)):
        w = normalized_projection[:, start : start + SHARD].T
        if CENTERED_PROJECTION:
            save_gray(
                OUT / f"projection-weights-centered-{shard}.png",
                surface_center + 0.5 * w,
            )
            full_primitives.extend(
                (
                    f'<feOffset in="{hidden_common}" dx="-{SHARD - 1}" '
                    f'dy="-{start}" x="0" y="0" width="1" height="{SHARD}" '
                    f'result="hcol{shard}"/>',
                    f'<feTile in="hcol{shard}" x="0" y="0" width="768" '
                    f'height="{SHARD}" result="h{shard}"/>',
                    f'<feImage href="projection-weights-centered-{shard}.png" '
                    f'x="0" y="0" width="768" height="{SHARD}" '
                    f'preserveAspectRatio="none" result="pw{shard}"/>',
                    f'<feComposite in="pw{shard}" in2="h{shard}" '
                    f'operator="arithmetic" k1="{PROJECTION_CENTERED_GAIN}" '
                    f'k2="{-PROJECTION_CENTERED_GAIN * surface_center}" '
                    f'k3="{-PROJECTION_CENTERED_GAIN * surface_center}" '
                    f'k4="{surface_center + PROJECTION_CENTERED_GAIN * surface_center * surface_center}" '
                    f'result="pcentered{shard}"/>',
                )
            )
        else:
            save_rg(
                OUT / f"projection-weights-{shard}.png",
                np.maximum(w, 0),
                np.maximum(-w, 0),
            )
            full_primitives.extend(
                (
                f'<feOffset in="hidden" dx="-{SHARD - 1}" dy="-{start}" '
                f'x="0" y="0" width="1" height="{SHARD}" result="hcol{shard}"/>',
                f'<feTile in="hcol{shard}" x="0" y="0" width="768" '
                f'height="{SHARD}" result="h{shard}"/>',
                f'<feColorMatrix in="h{shard}" type="matrix" '
                f'values="{swap_red_green}" result="hs{shard}"/>',
                f'<feImage href="projection-weights-{shard}.png" x="0" y="0" '
                f'width="768" height="{SHARD}" preserveAspectRatio="none" '
                f'result="pw{shard}"/>',
                f'<feComposite in="pw{shard}" in2="h{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="psame{shard}"/>',
                f'<feComposite in="pw{shard}" in2="hs{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="pcross{shard}"/>',
                f'<feColorMatrix in="psame{shard}" type="matrix" '
                f'values="{sum_channels}" result="ppositive{shard}"/>',
                f'<feColorMatrix in="pcross{shard}" type="matrix" '
                f'values="{negative_channels}" result="pnegative{shard}"/>',
                f'<feComposite in="ppositive{shard}" in2="pnegative{shard}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="psplit{shard}"/>',
                )
            )
    projection_shards = OUTPUTS // SHARD
    projection_group_size = int(os.environ.get("SVG_PROJECTION_GROUP", "1"))
    if projection_shards % projection_group_size:
        raise ValueError("SVG_PROJECTION_GROUP must divide twelve projection shards")
    projected_groups: list[str] = []
    for group, group_start in enumerate(
        range(0, projection_shards, projection_group_size)
    ):
        group_stop = min(group_start + projection_group_size, projection_shards)
        group_count = group_stop - group_start
        projection_input_prefix = "pcentered" if CENTERED_PROJECTION else "psplit"
        accumulated = f"{projection_input_prefix}-acc-{group}-0"
        full_primitives.append(
            f'<feComposite in="{projection_input_prefix}{group_start}" '
            f'in2="{projection_input_prefix}{group_start}" '
            f'operator="arithmetic" k1="0" k2="{1 / group_count}" '
            f'k3="0" k4="0" result="{accumulated}"/>'
        )
        for within_group, shard in enumerate(range(group_start + 1, group_stop), 1):
            result = f"{projection_input_prefix}-acc-{group}-{within_group}"
            full_primitives.append(
                f'<feComposite in="{accumulated}" '
                f'in2="{projection_input_prefix}{shard}" '
                f'operator="arithmetic" k1="0" k2="1" '
                f'k3="{1 / group_count}" k4="0" result="{result}"/>'
            )
            accumulated = result
        group_sum = f"projection-split-sum-{group}"
        projected = f"projected-group-{group}"
        if CENTERED_PROJECTION:
            convolution_divisor = (
                PROJECTION_CENTERED_GAIN
                * projection_divisor
                / (2 * group_count)
            )
            convolution_bias = (
                surface_center - SHARD * surface_center / convolution_divisor
            )
            full_primitives.append(
                f'<feConvolveMatrix in="{accumulated}" order="1 {SHARD}" '
                f'kernelMatrix="{kernel}" divisor="{convolution_divisor}" '
                f'bias="{convolution_bias}" targetX="0" targetY="{SHARD - 1}" '
                f'edgeMode="none" kernelUnitLength="1 1" '
                f'preserveAlpha="false" x="0" y="{SHARD - 1}" '
                f'width="768" height="1" result="{projected}"/>'
            )
        else:
            full_primitives.extend(
                (
            f'<feConvolveMatrix in="{accumulated}" order="1 {SHARD}" '
            f'kernelMatrix="{kernel}" '
            f'divisor="{projection_magnitude_divisor / group_count}" '
            f'bias="0" targetX="0" targetY="{SHARD - 1}" edgeMode="none" '
            f'kernelUnitLength="1 1" preserveAlpha="true" x="0" y="{SHARD - 1}" '
            f'width="768" height="1" result="{group_sum}"/>',
            f'<feColorMatrix in="{group_sum}" type="matrix" '
            f'values="{projection_signed_gray}" result="{projected}"/>',
                )
            )
        projected_groups.append(projected)
    accumulated = projected_groups[0]
    for group, projected in enumerate(projected_groups[1:], 1):
        result = f"projected-total-{group}"
        full_primitives.append(
            f'<feComposite in="{accumulated}" in2="{projected}" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="{result}"/>'
        )
        accumulated = result
    encoded_projection_bias = (
        surface_center
        + 0.5 * normalized_projection_bias / projection_divisor
    )
    save_gray(OUT / "projection-bias-residual.png", encoded_projection_bias[None, :])
    full_primitives.extend(
        (
            f'<feImage href="projection-bias-residual.png" x="0" y="{SHARD - 1}" '
            f'width="768" height="1" preserveAspectRatio="none" result="projection-bias"/>',
            f'<feComposite in="{accumulated}" in2="projection-bias" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="final"/>',
        )
    )
    full_html = f'''<!doctype html>
<meta charset="utf-8">
<title>SVG filter GPT-2 MLP probe</title>
<style>
  html, body {{ margin: 0; background: black; }}
  svg {{ display: block; width: 768px; height: {OUTPUTS}px; image-rendering: pixelated; }}
</style>
<svg viewBox="0 0 768 {OUTPUTS}" xmlns="http://www.w3.org/2000/svg">
  <filter id="mlp" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
          x="0" y="0" width="768" height="{OUTPUTS}"
          color-interpolation-filters="sRGB">
    {''.join(full_primitives)}
  </filter>
  <rect width="768" height="{OUTPUTS}" fill="white" filter="url(#mlp)"/>
</svg>
'''
    (OUT / "full.html").write_text(full_html)
    (OUT / "full-reference.json").write_text(
        json.dumps(
            {
                "inputs": INPUTS,
                "hidden": OUTPUTS,
                "outputs": 768,
                "block_index": BLOCK_INDEX,
                "centered_fc": CENTERED_FC,
                "centered_fc_gain": CENTERED_GAIN if CENTERED_FC else None,
                "centered_projection": CENTERED_PROJECTION,
                "centered_projection_gain": (
                    PROJECTION_CENTERED_GAIN if CENTERED_PROJECTION else None
                ),
                "pre_range": pre_range,
                "hidden_range": hidden_range,
                "projection_divisor": projection_divisor,
                "projection_magnitude_divisor": projection_magnitude_divisor,
                "projection_units": projection_units.tolist(),
                "surface_center": surface_center,
                "expected": final_expected.tolist(),
                "read_row": SHARD - 1,
                "decode": "(red[col] - surface_center) * 2 * projection_divisor * projection_units[col]",
            }
        )
        + "\n"
    )
    print(
        {
            "divisor": divisor,
            "bound": bound,
            "magnitude_divisor": magnitude_divisor,
            "magnitude_bound": magnitude_bound,
            "expected_min": float(expected.min()),
            "expected_max": float(expected.max()),
            "asset_bytes": sum(path.stat().st_size for path in OUT.glob("*.png")),
            "html_bytes": len(html.encode()),
        }
    )


if __name__ == "__main__":
    main()
