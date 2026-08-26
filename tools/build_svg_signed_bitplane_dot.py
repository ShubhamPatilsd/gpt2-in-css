#!/usr/bin/env python3
"""Compare ordinary SVG products with signed 6-bit activation planes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-signed-bitplane-dot"
WIDTH = 64
BITS = 6
CENTER = 128 / 255


def save_rg(path: Path, red: np.ndarray, green: np.ndarray) -> None:
    rgba = np.zeros((*red.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(np.clip(red, 0, 1) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(np.clip(green, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_rgb(path: Path, channels: np.ndarray) -> None:
    rgba = np.zeros((*channels.shape[1:], 4), dtype=np.uint8)
    for channel in range(3):
        rgba[..., channel] = np.rint(
            np.clip(channels[channel], 0, 1) * 255
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
    values = np.asarray(reference["context"], dtype=np.float64)[1, :WIDTH]
    input_max = max(float(np.max(np.abs(values))) * 1.001, 1e-12)
    input_step = input_max / ((1 << BITS) - 1)
    codes = np.rint(values / input_step).astype(np.int64)
    codes = np.clip(codes, -((1 << BITS) - 1), (1 << BITS) - 1)
    reconstructed_input = codes * input_step

    matrix = weights[:WIDTH, :WIDTH].T
    row_units = np.maximum(np.max(np.abs(matrix), axis=1), 1e-12)
    normalized_weights = matrix / row_units[:, None]
    # Use exactly the bytes stored in the runtime image as the numerical
    # reference. This isolates activation-product loss from weight quantization.
    weight_codes = np.rint(np.abs(normalized_weights) * 255).astype(np.uint8)
    stored_weights = np.sign(normalized_weights) * weight_codes / 255
    expected = stored_weights @ reconstructed_input
    output_bound = max(float(np.max(np.abs(expected))) * 1.08, 1e-9)

    save_rg(
        OUT / "weights.png",
        np.maximum(stored_weights, 0),
        np.maximum(-stored_weights, 0),
    )
    normalized_magnitude = np.abs(codes) / ((1 << BITS) - 1)
    save_rg(
        OUT / "input-continuous.png",
        np.where(codes >= 0, normalized_magnitude, 0)[None, :],
        np.where(codes < 0, normalized_magnitude, 0)[None, :],
    )
    for bit in range(BITS):
        enabled = ((np.abs(codes) >> bit) & 1).astype(np.float64)
        save_rg(
            OUT / f"input-bit-{bit}.png",
            np.where(codes >= 0, enabled, 0)[None, :],
            np.where(codes < 0, enabled, 0)[None, :],
        )

    # A denser alternative uses seven-bit two's-complement codes and carries
    # three independent planes in RGB. It needs three reductions instead of
    # the six signed-magnitude reductions above.
    twos_codes = np.where(codes < 0, codes + 128, codes)
    packed_groups = ((0, 1, 2), (3, 4, 5), (6,))
    for group, bits in enumerate(packed_groups):
        channels = np.zeros((3, 1, WIDTH), dtype=np.float64)
        for channel, bit in enumerate(bits):
            channels[channel, 0] = (twos_codes >> bit) & 1
        save_rgb(OUT / f"input-rgb-{group}.png", channels)

    centered_codes = np.rint(
        np.clip(CENTER + normalized_weights / 2, 0, 1) * 255
    ).astype(np.uint8)
    centered_weights = 2 * (centered_codes / 255 - CENTER)
    save_rgb(
        OUT / "weights-centered.png",
        np.stack([centered_codes / 255] * 3),
    )
    packed_sums = []
    for bits in packed_groups:
        for bit in bits:
            packed_sums.append(centered_weights @ (((twos_codes >> bit) & 1)))
    packed_bound = max(max(float(np.max(np.abs(v))) for v in packed_sums) * 1.02, 1e-9)

    signed_plane_sums = [
        stored_weights @ (
            (((np.abs(codes) >> bit) & 1) * np.sign(codes))
        )
        for bit in range(BITS)
    ]
    signed_rgb_groups = ((0, 1, 2), (3, 4, 5))
    signed_rgb_bounds = [
        max(max(float(np.max(np.abs(signed_plane_sums[bit]))) for bit in bits) * 1.02, 1e-9)
        for bits in signed_rgb_groups
    ]

    positive = np.maximum(stored_weights, 0)
    negative = np.maximum(-stored_weights, 0)
    same_sums = []
    cross_sums = []
    for bit in range(BITS):
        enabled = ((np.abs(codes) >> bit) & 1).astype(np.float64)
        pos = np.where(codes >= 0, enabled, 0)
        neg = np.where(codes < 0, enabled, 0)
        same_sums.append(positive @ pos + negative @ neg)
        cross_sums.append(positive @ neg + negative @ pos)
    magnitude_divisor = max(
        max(float(np.max(v)) for v in same_sums),
        max(float(np.max(v)) for v in cross_sums),
        1e-9,
    ) * 1.01
    cont_pos = np.maximum(reconstructed_input, 0) / input_max
    cont_neg = np.maximum(-reconstructed_input, 0) / input_max
    continuous_divisor = max(
        float(np.max(positive @ cont_pos + negative @ cont_neg)),
        float(np.max(positive @ cont_neg + negative @ cont_pos)),
        1e-9,
    ) * 1.01

    kernel = " ".join(["1"] * WIDTH)
    swap_rg = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    keep_positive = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    keep_negative = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    contribution_parts: list[str] = []

    def product_and_sum(prefix: str, input_name: str, divisor: float) -> str:
        return f'''
<feTile in="{input_name}" x="0" y="0" width="{WIDTH}" height="{WIDTH}" result="{prefix}-tile"/>
<feColorMatrix in="{prefix}-tile" values="{swap_rg}" result="{prefix}-swap"/>
<feComposite in="weights" in2="{prefix}-tile" operator="arithmetic" k1="1" result="{prefix}-same-products"/>
<feComposite in="weights" in2="{prefix}-swap" operator="arithmetic" k1="1" result="{prefix}-cross-products"/>
<feColorMatrix in="{prefix}-same-products" values="{keep_positive}" result="{prefix}-positive"/>
<feColorMatrix in="{prefix}-cross-products" values="{keep_negative}" result="{prefix}-negative"/>
<feComposite in="{prefix}-positive" in2="{prefix}-negative" operator="arithmetic" k2="1" k3="1" result="{prefix}-signed"/>
<feConvolveMatrix in="{prefix}-signed" order="{WIDTH} 1" kernelMatrix="{kernel}" divisor="{divisor}"
 targetX="{WIDTH - 1}" targetY="0" edgeMode="none" preserveAlpha="true"
 x="{WIDTH - 1}" y="0" width="1" height="{WIDTH}" result="{prefix}-sum"/>'''

    continuous_gain = continuous_divisor * input_max / (2 * output_bound)
    contribution_parts.append(
        '<feImage href="input-continuous.png" x="0" y="0" width="64" height="1" result="continuous-input"/>'
    )
    contribution_parts.append(product_and_sum("continuous", "continuous-input", continuous_divisor))
    continuous_matrix = (
        f"{continuous_gain} -{continuous_gain} 0 0 {CENTER}  " * 3
        + "0 0 0 0 1"
    )
    contribution_parts.append(
        f'<feColorMatrix in="continuous-sum" values="{continuous_matrix}" result="continuous-centered"/>'
    )
    contribution_parts.append(
        '<feOffset in="continuous-centered" dx="-63" x="0" y="0" width="1" height="64" result="continuous-column"/>'
    )

    bit_names: list[str] = []
    for bit in range(BITS):
        prefix = f"bit-{bit}"
        contribution_parts.append(
            f'<feImage href="input-bit-{bit}.png" x="0" y="0" width="64" height="1" result="{prefix}-input"/>'
        )
        contribution_parts.append(product_and_sum(prefix, f"{prefix}-input", magnitude_divisor))
        gain = magnitude_divisor * input_step * (1 << bit) / (2 * output_bound)
        matrix_text = f"{gain} -{gain} 0 0 {CENTER}  " * 3 + "0 0 0 0 1"
        name = f"{prefix}-centered"
        contribution_parts.append(
            f'<feColorMatrix in="{prefix}-sum" values="{matrix_text}" result="{name}"/>'
        )
        bit_names.append(name)
    combined = bit_names[0]
    for bit, name in enumerate(bit_names[1:], 1):
        next_name = f"bits-through-{bit}"
        contribution_parts.append(
            f'<feComposite in="{combined}" in2="{name}" operator="arithmetic" '
            f'k2="1" k3="1" k4="-{CENTER}" result="{next_name}"/>'
        )
        combined = next_name
    contribution_parts.append(
        f'<feOffset in="{combined}" dx="-62" x="1" y="0" width="1" height="64" result="bitplane-column"/>'
    )

    contribution_parts.append(
        '<feImage href="weights-centered.png" x="0" y="0" width="64" height="64" result="packed-weights"/>'
    )
    packed_contributions: list[str] = []
    packed_bias = CENTER - WIDTH * CENTER / packed_bound
    bit_coefficients = [1, 2, 4, 8, 16, 32, -64]
    for group, bits in enumerate(packed_groups):
        prefix = f"packed-{group}"
        contribution_parts.extend(
            [
                f'<feImage href="input-rgb-{group}.png" x="0" y="0" width="64" height="1" result="{prefix}-input"/>',
                f'<feTile in="{prefix}-input" x="0" y="0" width="64" height="64" result="{prefix}-tile"/>',
                f'<feComposite in="packed-weights" in2="{prefix}-tile" operator="arithmetic" '
                f'k1="1" k3="-{CENTER}" k4="{CENTER}" result="{prefix}-selected"/>',
                f'<feConvolveMatrix in="{prefix}-selected" order="64 1" kernelMatrix="{kernel}" '
                f'divisor="{packed_bound}" bias="{packed_bias}" targetX="63" targetY="0" '
                f'edgeMode="none" preserveAlpha="true" x="63" y="0" width="1" height="64" result="{prefix}-sum"/>',
            ]
        )
        gains = [0.0, 0.0, 0.0]
        for channel, bit in enumerate(bits):
            gains[channel] = packed_bound * input_step * bit_coefficients[bit] / output_bound
        offset = CENTER * (1 - sum(gains))
        matrix_text = (
            f"{gains[0]} {gains[1]} {gains[2]} 0 {offset}  " * 3
            + "0 0 0 0 1"
        )
        name = f"{prefix}-contribution"
        contribution_parts.append(
            f'<feColorMatrix in="{prefix}-sum" values="{matrix_text}" result="{name}"/>'
        )
        packed_contributions.append(name)
    packed_combined = packed_contributions[0]
    for group, name in enumerate(packed_contributions[1:], 1):
        next_name = f"packed-through-{group}"
        contribution_parts.append(
            f'<feComposite in="{packed_combined}" in2="{name}" operator="arithmetic" '
            f'k2="1" k3="1" k4="-{CENTER}" result="{next_name}"/>'
        )
        packed_combined = next_name
    contribution_parts.append(
        f'<feOffset in="{packed_combined}" dx="-61" x="2" y="0" width="1" height="64" result="packed-column"/>'
    )

    # Pack three signed-magnitude planes into RGB after selecting the positive
    # and negative weight bytes. Two shared reductions then replace six.
    signed_group_names: list[str] = []
    channel_rows = (
        ("1 0 0 0 0", "0 0 0 0 0", "0 0 0 0 0"),
        ("0 0 0 0 0", "1 0 0 0 0", "0 0 0 0 0"),
        ("0 0 0 0 0", "0 0 0 0 0", "1 0 0 0 0"),
    )
    for group, bits in enumerate(signed_rgb_groups):
        plane_channels: list[str] = []
        for channel, bit in enumerate(bits):
            prefix = f"signed-rgb-{group}-{channel}"
            contribution_parts.extend(
                [
                    f'<feImage href="input-bit-{bit}.png" x="0" y="0" width="64" height="1" result="{prefix}-input"/>',
                    f'<feTile in="{prefix}-input" x="0" y="0" width="64" height="64" result="{prefix}-tile"/>',
                    f'<feColorMatrix in="{prefix}-tile" values="{swap_rg}" result="{prefix}-swap"/>',
                    f'<feComposite in="weights" in2="{prefix}-tile" operator="arithmetic" k1="1" result="{prefix}-same"/>',
                    f'<feComposite in="weights" in2="{prefix}-swap" operator="arithmetic" k1="1" result="{prefix}-cross"/>',
                    f'<feColorMatrix in="{prefix}-same" values="{keep_positive}" result="{prefix}-positive"/>',
                    f'<feColorMatrix in="{prefix}-cross" values="{keep_negative}" result="{prefix}-negative"/>',
                    f'<feComposite in="{prefix}-positive" in2="{prefix}-negative" operator="arithmetic" k2="1" k3="1" result="{prefix}-split"/>',
                ]
            )
            rows = list(channel_rows[channel])
            rows[channel] = f".5 -.5 0 0 {CENTER}"
            matrix_text = "  ".join((*rows, "0 0 0 0 1"))
            channel_name = f"{prefix}-channel"
            contribution_parts.append(
                f'<feColorMatrix in="{prefix}-split" values="{matrix_text}" result="{channel_name}"/>'
            )
            plane_channels.append(channel_name)
        merged = plane_channels[0]
        for channel, channel_name in enumerate(plane_channels[1:], 1):
            next_name = f"signed-rgb-{group}-channels-{channel}"
            contribution_parts.append(
                f'<feComposite in="{merged}" in2="{channel_name}" operator="arithmetic" '
                f'k2="1" k3="1" result="{next_name}"/>'
            )
            merged = next_name
        bound = signed_rgb_bounds[group]
        bias = CENTER - WIDTH * CENTER / bound
        sum_name = f"signed-rgb-{group}-sum"
        contribution_parts.append(
            f'<feConvolveMatrix in="{merged}" order="64 1" kernelMatrix="{kernel}" '
            f'divisor="{bound}" bias="{bias}" targetX="63" targetY="0" edgeMode="none" '
            f'preserveAlpha="true" x="63" y="0" width="1" height="64" result="{sum_name}"/>'
        )
        gains = [bound * input_step * (1 << bit) / output_bound for bit in bits]
        offset = CENTER * (1 - sum(gains))
        combine_matrix = f"{gains[0]} {gains[1]} {gains[2]} 0 {offset}  " * 3 + "0 0 0 0 1"
        contribution_name = f"signed-rgb-{group}-contribution"
        contribution_parts.append(
            f'<feColorMatrix in="{sum_name}" values="{combine_matrix}" result="{contribution_name}"/>'
        )
        signed_group_names.append(contribution_name)
    contribution_parts.append(
        f'<feComposite in="{signed_group_names[0]}" in2="{signed_group_names[1]}" '
        f'operator="arithmetic" k2="1" k3="1" k4="-{CENTER}" result="signed-rgb-combined"/>'
    )
    contribution_parts.append(
        '<feOffset in="signed-rgb-combined" dx="-60" x="3" y="0" width="1" height="64" result="signed-rgb-column"/>'
    )

    html = f'''<!doctype html><meta charset="utf-8">
<title>Signed activation bit-plane SVG dot product</title>
<style>html,body{{margin:0;background:black}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="4" height="64" viewBox="0 0 4 64" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="dot" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
 x="0" y="0" width="64" height="64" color-interpolation-filters="sRGB">
<feImage href="weights.png" x="0" y="0" width="64" height="64" result="weights"/>
{''.join(contribution_parts)}
<feMerge><feMergeNode in="continuous-column"/><feMergeNode in="bitplane-column"/><feMergeNode in="packed-column"/><feMergeNode in="signed-rgb-column"/></feMerge>
</filter></defs><rect width="64" height="64" fill="white" filter="url(#dot)"/></svg>'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "expected": expected.tolist(),
                "originalExpected": (matrix @ values).tolist(),
                "outputBound": output_bound,
                "inputStep": input_step,
                "weightRmse": float(np.sqrt(np.mean((stored_weights - normalized_weights) ** 2))),
                "inputRmse": float(np.sqrt(np.mean((reconstructed_input - values) ** 2))),
                "packedWeightRmse": float(np.sqrt(np.mean((centered_weights - normalized_weights) ** 2))),
                "filterPrimitives": html.count("<fe"),
                "htmlBytes": len(html.encode()),
            }
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "filter_primitives": html.count("<fe")})


if __name__ == "__main__":
    main()
