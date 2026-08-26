#!/usr/bin/env python3
"""Build a no-JavaScript SVG-filter probe for GPT-2 layer normalization."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from build_gpt2_block_css import EPSILON, QUANT_BITS, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-filter-layernorm"
WIDTH = 768
SHARD = 256
CENTER = 128 / 255


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8), mode="L").save(
        path, optimize=True
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    vector = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    gamma = data["ln2_gamma"]
    beta = data["ln2_beta"]
    expected = layer_norm(vector, gamma, beta)

    input_range = float(np.max(np.abs(vector)) * 1.02)
    mean = float(np.mean(vector))
    difference = vector - mean
    difference_range = float(np.max(np.abs(difference)) * 1.02)
    normalized = difference / np.sqrt(np.mean(difference**2) + EPSILON)
    normalized_range = float(np.max(np.abs(normalized)) * 1.02)
    output_range = float(np.max(np.abs(expected)) * 1.05)
    gamma_max = float(np.max(gamma))
    save_gray(OUT / "input.png", (CENTER + vector / (2 * input_range))[None, :])
    save_gray(
        OUT / "gamma-scale.png",
        (gamma / gamma_max)[None, :],
    )
    save_gray(
        OUT / "beta.png",
        (CENTER + beta / (2 * output_range))[None, :],
    )

    center_css = f"{CENTER:.12g}"
    kernel = " ".join("1" for _ in range(SHARD))
    copy_red = "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
    to_red = "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    to_green = "0 0 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    difference_coefficient = input_range / difference_range
    difference_matrix = (
        f"{difference_coefficient} -{difference_coefficient} 0 0 {center_css}  "
        f"{difference_coefficient} -{difference_coefficient} 0 0 {center_css}  "
        f"{difference_coefficient} -{difference_coefficient} 0 0 {center_css}  "
        "0 0 0 0 1"
    )

    primitives: list[str] = [
        f'<feImage href="input.png" x="0" y="0" width="{WIDTH}" height="1" '
        'preserveAspectRatio="none" result="input"/>'
    ]

    def reduce_three(source: str, prefix: str, centered: bool) -> str:
        reduced: list[str] = []
        for shard, start in enumerate(range(0, WIDTH, SHARD)):
            primitives.extend(
                (
                    f'<feOffset in="{source}" dx="-{start}" dy="0" x="0" y="0" '
                    f'width="{SHARD}" height="1" result="{prefix}-chunk{shard}"/>',
                    f'<feConvolveMatrix in="{prefix}-chunk{shard}" order="{SHARD} 1" '
                    f'kernelMatrix="{kernel}" divisor="{SHARD}" bias="0" '
                    f'targetX="{SHARD - 1}" targetY="0" edgeMode="none" '
                    f'kernelUnitLength="1 1" preserveAlpha="true" x="{SHARD - 1}" '
                    f'y="0" width="1" height="1" result="{prefix}-part{shard}"/>',
                )
            )
            reduced.append(f"{prefix}-part{shard}")
        first = f"{prefix}-first"
        final = f"{prefix}-scalar"
        primitives.extend(
            (
                f'<feComposite in="{reduced[0]}" in2="{reduced[1]}" '
                f'operator="arithmetic" k1="0" k2=".333333333333" '
                f'k3=".333333333333" k4="0" result="{first}"/>',
                f'<feComposite in="{first}" in2="{reduced[2]}" '
                f'operator="arithmetic" k1="0" k2="1" '
                f'k3=".333333333333" k4="0" result="{final}"/>',
            )
        )
        return final

    mean_scalar = reduce_three("input", "mean", centered=True)
    primitives.extend(
        (
            f'<feOffset in="{mean_scalar}" dx="-{SHARD - 1}" dy="0" '
            f'x="0" y="0" width="1" height="1" result="mean-origin"/>',
            f'<feTile in="mean-origin" x="0" y="0" width="{WIDTH}" height="1" '
            f'result="mean-tiled"/>',
            f'<feColorMatrix in="input" values="{to_red}" result="input-red"/>',
            f'<feColorMatrix in="mean-tiled" values="{to_green}" result="mean-green"/>',
            '<feComposite in="input-red" in2="mean-green" operator="arithmetic" '
            'k1="0" k2="1" k3="1" k4="0" result="input-mean-split"/>',
            f'<feColorMatrix in="input-mean-split" values="{difference_matrix}" '
            f'result="difference"/>',
            '<feComposite in="difference" in2="difference" operator="arithmetic" '
            f'k1="4" k2="{-4 * CENTER}" k3="{-4 * CENTER}" '
            f'k4="{4 * CENTER * CENTER}" result="squared-alpha"/>',
            f'<feColorMatrix in="squared-alpha" values="{copy_red}" result="squared"/>',
        )
    )
    variance_scalar = reduce_three("squared", "variance", centered=False)
    variance_grid = np.linspace(0, 1, 256)
    gain_table = np.clip(
        1
        / (
            np.sqrt(variance_grid + EPSILON / (difference_range**2))
            * normalized_range
        ),
        0,
        1,
    )
    gain_values = " ".join(f"{value:.8g}" for value in gain_table)
    gamma_coefficient = gamma_max * normalized_range / output_range
    primitives.extend(
        (
            f'<feComponentTransfer in="{variance_scalar}" result="gain-scalar">'
            f'<feFuncR type="table" tableValues="{gain_values}"/>'
            f'<feFuncG type="table" tableValues="{gain_values}"/>'
            f'<feFuncB type="table" tableValues="{gain_values}"/>'
            '<feFuncA type="identity"/></feComponentTransfer>',
            f'<feOffset in="gain-scalar" dx="-{SHARD - 1}" dy="0" '
            f'x="0" y="0" width="1" height="1" result="gain-origin"/>',
            f'<feTile in="gain-origin" x="0" y="0" width="{WIDTH}" height="1" '
            f'result="gain"/>',
            '<feComposite in="difference" in2="gain" operator="arithmetic" '
            f'k1="1" k2="0" k3="-{center_css}" k4="{center_css}" '
            'result="normalized"/>',
            f'<feImage href="gamma-scale.png" x="0" y="0" width="{WIDTH}" '
            f'height="1" preserveAspectRatio="none" result="gamma-scale"/>',
            '<feComposite in="normalized" in2="gamma-scale" operator="arithmetic" '
            f'k1="{gamma_coefficient}" k2="0" '
            f'k3="{-gamma_coefficient * CENTER}" k4="{center_css}" '
            'result="scaled"/>',
            f'<feImage href="beta.png" x="0" y="0" width="{WIDTH}" height="1" '
            f'preserveAspectRatio="none" result="beta"/>',
            '<feComposite in="scaled" in2="beta" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center_css}" result="final"/>',
        )
    )
    html = f'''<!doctype html><meta charset="utf-8">
<title>SVG filter GPT-2 layer normalization probe</title>
<style>html,body{{margin:0;background:black}}svg{{display:block;width:{WIDTH}px;height:1px;image-rendering:pixelated}}</style>
<svg viewBox="0 0 {WIDTH} 1" xmlns="http://www.w3.org/2000/svg">
<filter id="layernorm" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
x="0" y="0" width="{WIDTH}" height="1" color-interpolation-filters="sRGB">
{''.join(primitives)}</filter>
<rect width="{WIDTH}" height="1" fill="white" filter="url(#layernorm)"/></svg>
'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "input_range": input_range,
                "difference_range": difference_range,
                "normalized_range": normalized_range,
                "output_range": output_range,
                "surface_center": CENTER,
                "expected": expected.tolist(),
            }
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "output_range": output_range})


if __name__ == "__main__":
    main()
