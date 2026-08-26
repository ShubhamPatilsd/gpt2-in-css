#!/usr/bin/env python3
"""Compare ordinary and RGB magnitude-plane SVG dot products."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-magnitude-plane-dot"
CENTER = 128 / 255
WIDTH = 64


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(
        np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8), mode="L"
    ).save(path, optimize=True)


def save_rg(path: Path, values: np.ndarray) -> None:
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(np.maximum(values, 0) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(np.maximum(-values, 0) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_planes(path: Path, planes: np.ndarray) -> None:
    rgba = np.zeros((*planes.shape[1:], 4), dtype=np.uint8)
    for channel in range(3):
        rgba[..., channel] = np.rint(
            np.clip(CENTER + planes[channel] / 2, 0, 1) * 255
        ).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_rgb(path: Path, values: np.ndarray) -> None:
    rgba = np.zeros((*values.shape[1:], 4), dtype=np.uint8)
    for channel in range(3):
        rgba[..., channel] = np.rint(
            np.clip(values[channel], 0, 1) * 255
        ).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads(
        (ROOT / "experiments/gpt2-block-css/view-timeline-attention-2token-reference.json").read_text()
    )
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64)
    context = np.asarray(reference["context"], dtype=np.float64)[1]
    input_values = context[:WIDTH]
    input_scale = max(float(np.max(np.abs(input_values))) * 1.02, 1e-12)
    normalized_input = input_values / input_scale
    matrix = weights[:WIDTH, :WIDTH].T * input_scale
    row_units = np.maximum(np.max(np.abs(matrix), axis=1), 1e-12)
    normalized_weights = matrix / row_units[:, None]
    expected = normalized_weights @ normalized_input
    output_bound = max(float(np.max(np.abs(expected))) * 1.05, 1e-12)

    save_gray(OUT / "input.png", (CENTER + normalized_input / 2).reshape(1, WIDTH))
    common_input = CENTER + normalized_input / 2
    sample_count = 4
    sample_codes = np.empty((WIDTH, sample_count), dtype=np.uint8)
    for index, value in enumerate(common_input):
        total = int(np.rint(np.clip(value, 0, 1) * 255 * sample_count))
        base, remainder = divmod(total, sample_count)
        sample_codes[index] = [
            min(base + (sample < remainder), 255)
            for sample in range(sample_count)
        ]
    Image.fromarray(sample_codes.reshape(1, WIDTH * sample_count), mode="L").save(
        OUT / "input-4x.png", optimize=True
    )
    save_rg(OUT / "weights-rg.png", normalized_weights)

    plane_scales = np.asarray([1.0, 1 / 16, 1 / 256])
    absolute = np.abs(normalized_weights)
    planes = np.zeros((3, WIDTH, WIDTH), dtype=np.float64)
    high = absolute >= plane_scales[1]
    middle = (absolute < plane_scales[1]) & (absolute >= plane_scales[2])
    low = absolute < plane_scales[2]
    planes[0, high] = normalized_weights[high]
    planes[1, middle] = normalized_weights[middle] / plane_scales[1]
    planes[2, low] = normalized_weights[low] / plane_scales[2]
    save_planes(OUT / "weights-planes.png", planes)
    save_rgb(OUT / "weights-planes-positive.png", np.maximum(planes, 0))
    save_rgb(OUT / "weights-planes-negative.png", np.maximum(-planes, 0))
    plane_dots = np.stack([plane @ normalized_input for plane in planes])
    plane_bound = max(float(np.max(np.abs(plane_dots))) * 1.05, 1e-12)
    positive_input = np.maximum(normalized_input, 0)
    negative_input = np.maximum(-normalized_input, 0)
    same_plane_sums = np.stack([
        np.maximum(plane, 0) @ positive_input
        + np.maximum(-plane, 0) @ negative_input
        for plane in planes
    ])
    cross_plane_sums = np.stack([
        np.maximum(plane, 0) @ negative_input
        + np.maximum(-plane, 0) @ positive_input
        for plane in planes
    ])
    split_plane_magnitude = max(
        float(np.max(same_plane_sums)), float(np.max(cross_plane_sums))
    ) * 1.02
    independent_magnitudes = np.maximum(
        np.maximum(np.max(same_plane_sums, axis=1), np.max(cross_plane_sums, axis=1))
        * 1.02,
        1e-12,
    )

    center = f"{CENTER:.12g}"
    grid = np.linspace(0, 1, 256)
    positive_table = " ".join(
        f"{v:.8g}" for v in np.clip(2 * (grid - CENTER), 0, 1)
    )
    negative_table = " ".join(
        f"{v:.8g}" for v in np.clip(2 * (CENTER - grid), 0, 1)
    )
    swap_rg = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    positive_matrix = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_matrix = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    kernel = " ".join("1" for _ in range(WIDTH))
    magnitude = max(
        float(np.max(np.maximum(normalized_weights * normalized_input, 0).sum(1))),
        float(np.max(np.maximum(-normalized_weights * normalized_input, 0).sum(1))),
    ) * 1.02
    baseline_gain = magnitude / (2 * output_bound)
    baseline_matrix = (
        f"{baseline_gain} -{baseline_gain} 0 0 {center}  " * 3
        + "0 0 0 0 1"
    )
    product_k4 = CENTER + 2 * CENTER * CENTER
    packed_product = (
        f'<feComposite in="weights-planes" in2="input-tile" '
        f'operator="arithmetic" k1="2" k2="{-2 * CENTER}" '
        f'k3="{-2 * CENTER}" k4="{product_k4}" result="plane-products"/>'
    )
    plane_bias = CENTER - WIDTH * CENTER / plane_bound
    combine_offset = CENTER * (
        1 - plane_bound / output_bound * float(np.sum(plane_scales))
    )
    combine = plane_bound / output_bound * plane_scales
    combine_matrix = (
        f"{combine[0]} {combine[1]} {combine[2]} 0 {combine_offset}  " * 3
        + "0 0 0 0 1"
    )
    replicate_positive = "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
    replicate_negative = "0 1 0 0 0  0 1 0 0 0  0 1 0 0 0  0 0 0 0 1"
    split_gain = split_plane_magnitude / (2 * output_bound) * plane_scales
    split_combine = (
        f"{split_gain[0]} {split_gain[1]} {split_gain[2]} 0 0  " * 3
        + "0 0 0 0 1"
    )
    pack_same = "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    pack_cross = "0 0 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    subtract_split = (
        f"1 -1 0 0 {center}  " * 3 + "0 0 0 0 1"
    )
    independent_parts = []
    channel_names = ("r", "g", "b")
    for index, channel in enumerate(channel_names):
        gain = independent_magnitudes[index] * plane_scales[index] / (2 * output_bound)
        rows = [[0.0] * 5 for _ in range(4)]
        rows[index][index] = float(gain)
        rows[3][3] = 1.0
        pack_matrix = " ".join(str(value) for row in rows for value in row)
        for sign in ("same", "cross"):
            independent_parts.append(
                f'<feConvolveMatrix in="split-{sign}" order="64 1" '
                f'kernelMatrix="{kernel}" divisor="{independent_magnitudes[index]}" '
                f'targetX="63" targetY="0" edgeMode="none" preserveAlpha="true" '
                f'x="63" y="0" width="1" height="64" result="ind-{sign}-{channel}-sum"/>'
            )
            independent_parts.append(
                f'<feColorMatrix in="ind-{sign}-{channel}-sum" values="{pack_matrix}" '
                f'result="ind-{sign}-{channel}"/>'
            )
    for sign in ("same", "cross"):
        independent_parts.extend([
            f'<feBlend in="ind-{sign}-r" in2="ind-{sign}-g" mode="screen" result="ind-{sign}-rg"/>',
            f'<feBlend in="ind-{sign}-rg" in2="ind-{sign}-b" mode="screen" result="ind-{sign}-packed"/>',
        ])
    sum_rgb = "1 1 1 0 0  1 1 1 0 0  1 1 1 0 0  0 0 0 0 1"
    independent_parts.extend([
        f'<feColorMatrix in="ind-same-packed" values="{sum_rgb}" result="ind-same-combined"/>',
        f'<feColorMatrix in="ind-cross-packed" values="{sum_rgb}" result="ind-cross-combined"/>',
        f'<feColorMatrix in="ind-same-combined" values="{pack_same}" result="ind-same-r"/>',
        f'<feColorMatrix in="ind-cross-combined" values="{pack_cross}" result="ind-cross-g"/>',
        '<feBlend in="ind-same-r" in2="ind-cross-g" mode="screen" result="ind-packed"/>',
        f'<feColorMatrix in="ind-packed" values="{subtract_split}" result="ind-common"/>',
        '<feOffset in="ind-common" dx="-60" x="3" y="0" width="1" height="64" result="ind-col"/>',
    ])
    independent_xml = "\n".join(independent_parts)
    direct_kernel_parts = []
    for output_index, kernel_values in enumerate(normalized_weights):
        kernel_values = kernel_values[::-1]
        direct_kernel = " ".join(f"{value:.10g}" for value in kernel_values)
        direct_bias = CENTER - CENTER * float(np.sum(kernel_values)) / output_bound
        direct_kernel_parts.extend(
            (
                f'<feConvolveMatrix in="input-tile" order="64 1" '
                f'kernelMatrix="{direct_kernel}" divisor="{output_bound}" '
                f'bias="{direct_bias}" targetX="63" targetY="0" edgeMode="none" '
                f'preserveAlpha="true" x="63" y="{output_index}" width="1" height="1" '
                f'result="direct-{output_index}-sum"/>',
                f'<feOffset in="direct-{output_index}-sum" dx="-59" x="4" '
                f'y="{output_index}" width="1" height="1" '
                f'result="direct-{output_index}"/>',
            )
        )
    direct_kernel_xml = "\n".join(direct_kernel_parts)
    direct_4x_parts = [
        '<feImage href="input-4x.png" x="0" y="0" width="256" height="1" result="input-4x"/>',
        '<feTile in="input-4x" x="0" y="0" width="256" height="64" result="input-4x-tile"/>',
    ]
    for output_index, kernel_values in enumerate(normalized_weights):
        expanded_kernel = np.repeat(kernel_values / sample_count, sample_count)[::-1]
        direct_kernel = " ".join(f"{value:.10g}" for value in expanded_kernel)
        direct_bias = CENTER - CENTER * float(np.sum(kernel_values)) / output_bound
        direct_4x_parts.extend(
            (
                f'<feConvolveMatrix in="input-4x-tile" order="256 1" '
                f'kernelMatrix="{direct_kernel}" divisor="{output_bound}" '
                f'bias="{direct_bias}" targetX="255" targetY="0" edgeMode="none" '
                f'preserveAlpha="true" x="255" y="{output_index}" width="1" height="1" '
                f'result="direct-4x-{output_index}-sum"/>',
                f'<feOffset in="direct-4x-{output_index}-sum" dx="-250" x="5" '
                f'y="{output_index}" width="1" height="1" '
                f'result="direct-4x-{output_index}"/>',
            )
        )
    direct_4x_xml = "\n".join(direct_4x_parts)
    html = f'''<!doctype html><meta charset="utf-8">
<title>Magnitude-plane dot-product probe</title>
<style>html,body{{margin:0;background:black}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="6" height="64" viewBox="0 0 6 64" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="dot" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
 x="0" y="0" width="256" height="64" color-interpolation-filters="sRGB">
<feImage href="input.png" x="0" y="0" width="64" height="1" result="input"/>
<feTile in="input" x="0" y="0" width="64" height="64" result="input-tile"/>
<feComponentTransfer in="input-tile" result="input-signed">
 <feFuncR type="table" tableValues="{positive_table}"/>
 <feFuncG type="table" tableValues="{negative_table}"/>
 <feFuncB type="table" tableValues="0 0"/><feFuncA type="identity"/>
</feComponentTransfer>
<feColorMatrix in="input-signed" values="{swap_rg}" result="input-swapped"/>
<feImage href="weights-rg.png" x="0" y="0" width="64" height="64" result="weights-rg"/>
<feComposite in="weights-rg" in2="input-signed" operator="arithmetic" k1="1" result="same"/>
<feComposite in="weights-rg" in2="input-swapped" operator="arithmetic" k1="1" result="cross"/>
<feColorMatrix in="same" values="{positive_matrix}" result="positive"/>
<feColorMatrix in="cross" values="{negative_matrix}" result="negative"/>
<feComposite in="positive" in2="negative" operator="arithmetic" k2="1" k3="1" result="split"/>
<feConvolveMatrix in="split" order="64 1" kernelMatrix="{kernel}" divisor="{magnitude}"
 targetX="63" targetY="0" edgeMode="none" preserveAlpha="true"
 x="63" y="0" width="1" height="64" result="baseline-sum"/>
<feColorMatrix in="baseline-sum" values="{baseline_matrix}" result="baseline-common"/>
<feOffset in="baseline-common" dx="-63" x="0" y="0" width="1" height="64" result="baseline-col"/>
<feImage href="weights-planes.png" x="0" y="0" width="64" height="64" result="weights-planes"/>
{packed_product}
<feConvolveMatrix in="plane-products" order="64 1" kernelMatrix="{kernel}" divisor="{plane_bound}"
 bias="{plane_bias}" targetX="63" targetY="0" edgeMode="none" preserveAlpha="true"
 x="63" y="0" width="1" height="64" result="planes-sum"/>
<feColorMatrix in="planes-sum" values="{combine_matrix}" result="planes-common"/>
<feOffset in="planes-common" dx="-62" x="1" y="0" width="1" height="64" result="planes-col"/>
<feColorMatrix in="input-signed" values="{replicate_positive}" result="input-positive"/>
<feColorMatrix in="input-signed" values="{replicate_negative}" result="input-negative"/>
<feImage href="weights-planes-positive.png" x="0" y="0" width="64" height="64" result="weights-positive"/>
<feImage href="weights-planes-negative.png" x="0" y="0" width="64" height="64" result="weights-negative"/>
<feComposite in="weights-positive" in2="input-positive" operator="arithmetic" k1="1" result="same-positive"/>
<feComposite in="weights-negative" in2="input-negative" operator="arithmetic" k1="1" result="same-negative"/>
<feComposite in="same-positive" in2="same-negative" operator="arithmetic" k2="1" k3="1" result="split-same"/>
<feComposite in="weights-positive" in2="input-negative" operator="arithmetic" k1="1" result="cross-positive"/>
<feComposite in="weights-negative" in2="input-positive" operator="arithmetic" k1="1" result="cross-negative"/>
<feComposite in="cross-positive" in2="cross-negative" operator="arithmetic" k2="1" k3="1" result="split-cross"/>
<feConvolveMatrix in="split-same" order="64 1" kernelMatrix="{kernel}" divisor="{split_plane_magnitude}"
 targetX="63" targetY="0" edgeMode="none" preserveAlpha="true"
 x="63" y="0" width="1" height="64" result="split-same-sum"/>
<feConvolveMatrix in="split-cross" order="64 1" kernelMatrix="{kernel}" divisor="{split_plane_magnitude}"
 targetX="63" targetY="0" edgeMode="none" preserveAlpha="true"
 x="63" y="0" width="1" height="64" result="split-cross-sum"/>
<feColorMatrix in="split-same-sum" values="{split_combine}" result="split-same-combined"/>
<feColorMatrix in="split-cross-sum" values="{split_combine}" result="split-cross-combined"/>
<feColorMatrix in="split-same-combined" values="{pack_same}" result="split-same-r"/>
<feColorMatrix in="split-cross-combined" values="{pack_cross}" result="split-cross-g"/>
<feBlend in="split-same-r" in2="split-cross-g" mode="screen" result="split-packed"/>
<feColorMatrix in="split-packed" values="{subtract_split}" result="split-common"/>
<feOffset in="split-common" dx="-61" x="2" y="0" width="1" height="64" result="split-col"/>
{independent_xml}
{direct_kernel_xml}
{direct_4x_xml}
<feMerge><feMergeNode in="baseline-col"/><feMergeNode in="planes-col"/><feMergeNode in="split-col"/><feMergeNode in="ind-col"/>{''.join(f'<feMergeNode in="direct-{index}"/>' for index in range(WIDTH))}{''.join(f'<feMergeNode in="direct-4x-{index}"/>' for index in range(WIDTH))}</feMerge>
</filter></defs><rect width="64" height="64" fill="white" filter="url(#dot)"/></svg>'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps({"expected": expected.tolist(), "output_bound": output_bound})
    )


if __name__ == "__main__":
    main()
