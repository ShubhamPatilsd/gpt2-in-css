#!/usr/bin/env python3
"""Build a signed SVG-filter probe for one-token GPT-2 composed attention."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from build_gpt2_block_css import QUANT_BITS, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-filter-gpt2-attention"
WIDTH = 768
SHARD = 256
CENTER = 128 / 255


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
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    weights = q_attention.reconstructed
    vector = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    expected = data["x"] + weights @ vector + composed_bias

    weight_scales = np.maximum(np.max(np.abs(weights), axis=1), 1e-12)
    input_scale = float(np.max(np.abs(vector)))
    units = weight_scales * input_scale
    normalized_weights = weights / weight_scales[:, None]
    normalized_input = vector / input_scale
    partials = np.stack(
        [
            normalized_weights[:, start : start + SHARD]
            @ normalized_input[start : start + SHARD]
            for start in range(0, WIDTH, SHARD)
        ],
        axis=1,
    )
    normalized_bias_residual = (composed_bias + data["x"]) / units
    cumulative = np.cumsum(partials, axis=1)
    bound = max(
        float(np.max(np.abs(partials))),
        float(np.max(np.abs(cumulative))),
        float(np.max(np.abs(cumulative[:, -1] + normalized_bias_residual))),
    )
    divisor = bound * 1.02
    magnitude_bound = 0.0
    for start in range(0, WIDTH, SHARD):
        products = (
            normalized_weights[:, start : start + SHARD]
            * normalized_input[start : start + SHARD][None, :]
        )
        magnitude_bound = max(
            magnitude_bound,
            float(np.max(np.maximum(products, 0).sum(axis=1))),
            float(np.max(np.maximum(-products, 0).sum(axis=1))),
        )
    magnitude_divisor = magnitude_bound * 1.02

    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        w = normalized_weights[:, start : start + SHARD]
        x = normalized_input[start : start + SHARD][None, :]
        save_rg(OUT / f"weights-{shard}.png", np.maximum(w, 0), np.maximum(-w, 0))
        save_rg(OUT / f"vector-{shard}.png", np.maximum(x, 0), np.maximum(-x, 0))
        save_rg(OUT / f"vector-swapped-{shard}.png", np.maximum(-x, 0), np.maximum(x, 0))
        save_rg(OUT / f"vector-alt-{shard}.png", np.maximum(-x, 0), np.maximum(x, 0))
        save_rg(OUT / f"vector-alt-swapped-{shard}.png", np.maximum(x, 0), np.maximum(-x, 0))
    save_gray(
        OUT / "bias-residual.png",
        (CENTER + 0.5 * normalized_bias_residual / divisor)[:, None],
    )

    kernel = " ".join("1" for _ in range(SHARD))
    positive_matrix = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_matrix = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    coefficient = magnitude_divisor / (2 * divisor)
    center_css = f"{CENTER:.12g}"
    signed_matrix = (
        f"{coefficient} -{coefficient} 0 0 {center_css}  "
        f"{coefficient} -{coefficient} 0 0 {center_css}  "
        f"{coefficient} -{coefficient} 0 0 {center_css}  0 0 0 0 1"
    )
    primitives: list[str] = []
    for shard in range(WIDTH // SHARD):
        primitives.extend(
            (
                f'<feImage href="weights-{shard}.png" x="0" y="0" width="{SHARD}" '
                f'height="{WIDTH}" preserveAspectRatio="none" result="w{shard}"/>',
                f'<feImage href="vector-{shard}.png" x="0" y="0" width="{SHARD}" '
                f'height="1" preserveAspectRatio="none" result="vrow{shard}"/>',
                f'<feTile in="vrow{shard}" x="0" y="0" width="{SHARD}" '
                f'height="{WIDTH}" result="v{shard}"/>',
                f'<feImage href="vector-swapped-{shard}.png" x="0" y="0" '
                f'width="{SHARD}" height="1" preserveAspectRatio="none" '
                f'result="vsrow{shard}"/>',
                f'<feTile in="vsrow{shard}" x="0" y="0" width="{SHARD}" '
                f'height="{WIDTH}" result="vs{shard}"/>',
                f'<feComposite in="w{shard}" in2="v{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="same{shard}"/>',
                f'<feComposite in="w{shard}" in2="vs{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="cross{shard}"/>',
                f'<feColorMatrix in="same{shard}" values="{positive_matrix}" '
                f'result="positive{shard}"/>',
                f'<feColorMatrix in="cross{shard}" values="{negative_matrix}" '
                f'result="negative{shard}"/>',
                f'<feComposite in="positive{shard}" in2="negative{shard}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="split{shard}"/>',
                f'<feConvolveMatrix in="split{shard}" order="{SHARD} 1" '
                f'kernelMatrix="{kernel}" divisor="{magnitude_divisor}" bias="0" '
                f'targetX="{SHARD - 1}" targetY="0" edgeMode="none" '
                f'kernelUnitLength="1 1" preserveAlpha="true" x="{SHARD - 1}" '
                f'y="0" width="1" height="{WIDTH}" result="sum{shard}"/>',
                f'<feColorMatrix in="sum{shard}" values="{signed_matrix}" '
                f'result="encoded{shard}"/>',
            )
        )
    total = "encoded0"
    for shard in range(1, WIDTH // SHARD):
        result = f"total{shard}"
        primitives.append(
            f'<feComposite in="{total}" in2="encoded{shard}" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center_css}" result="{result}"/>'
        )
        total = result
    primitives.extend(
        (
            f'<feImage href="bias-residual.png" x="{SHARD - 1}" y="0" width="1" '
            f'height="{WIDTH}" preserveAspectRatio="none" result="bias"/>',
            f'<feComposite in="{total}" in2="bias" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center_css}" result="final"/>',
        )
    )
    html = f'''<!doctype html><meta charset="utf-8">
<title>SVG filter GPT-2 composed attention probe</title>
<style>html,body{{margin:0;background:black}}svg{{display:block;width:{SHARD}px;height:{WIDTH}px;image-rendering:pixelated}}</style>
<svg viewBox="0 0 {SHARD} {WIDTH}" xmlns="http://www.w3.org/2000/svg">
<filter id="attention" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
x="0" y="0" width="{SHARD}" height="{WIDTH}" color-interpolation-filters="sRGB">
{''.join(primitives)}</filter>
<rect width="{SHARD}" height="{WIDTH}" fill="white" filter="url(#attention)"/></svg>
'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "divisor": divisor,
                "units": units.tolist(),
                "surface_center": CENTER,
                "expected": expected.tolist(),
                "read_column": SHARD - 1,
            }
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "asset_bytes": sum(p.stat().st_size for p in OUT.glob("*.png"))})


if __name__ == "__main__":
    main()
