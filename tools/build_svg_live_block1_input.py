#!/usr/bin/env python3
"""Normalize block 0's live newest-token output for block 1 QKV."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from build_gpt2_block_css import EPSILON, layer_norm, model_data


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "SVG_BLOCK1_INPUT_SOURCE",
        ROOT / "experiments" / "svg-live-complete-block",
    )
).resolve()
ATTENTION = Path(
    os.environ.get(
        "SVG_BLOCK1_INPUT_ATTENTION",
        ROOT / "experiments" / "svg-block1-attention-rgb-centered",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_BLOCK1_INPUT_OUT",
        ROOT / "experiments" / "svg-live-block1-input",
    )
).resolve()
WIDTH = 768
SHARD = 256
CENTER = 128 / 255
SOURCE_X = 255
LIVE_X = 1
REDUCTION = os.environ.get("SVG_BLOCK1_INPUT_REDUCTION", "sharded")
if REDUCTION not in {"sharded", "gaussian-tiled", "hier4"}:
    raise ValueError(f"Unknown SVG_BLOCK1_INPUT_REDUCTION: {REDUCTION}")
GAUSSIAN_SIGMA = float(os.environ.get("SVG_BLOCK1_INPUT_GAUSSIAN_SIGMA", "384"))
GAUSSIAN_TILES = int(os.environ.get("SVG_BLOCK1_INPUT_GAUSSIAN_TILES", "3"))
if GAUSSIAN_TILES < 3 or GAUSSIAN_TILES % 2 == 0:
    raise ValueError("SVG_BLOCK1_INPUT_GAUSSIAN_TILES must be odd and >= 3")


def save_gray(path: Path, values: np.ndarray) -> None:
    pixels = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(path, optimize=True)


def svg_parts(page: str) -> tuple[str, str]:
    defs_marker = page.index("<defs")
    defs_start = page.index(">", defs_marker) + 1
    defs_end = page.index("</defs>", defs_start)
    content_start = defs_end + len("</defs>")
    content_end = page.rindex("</svg>")
    return page[defs_start:defs_end], page[content_start:content_end]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("block1-ln1-*.png"):
        stale.unlink()
    source_page = (SOURCE / "index.html").read_text()
    source_relative = os.path.relpath(SOURCE, OUT)
    source_defs, source_content = svg_parts(source_page)
    source_defs = source_defs.replace('href="', f'href="{source_relative}/')
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    attention_reference = json.loads((ATTENTION / "reference.json").read_text())
    vector = np.asarray(source_reference["expected"], dtype=np.float64)
    input_scales = np.asarray(source_reference["finalScales"], dtype=np.float64)
    qkv_input_scales = np.asarray(
        attention_reference["input_scales"], dtype=np.float64
    )
    block = model_data(block_index=1, input_vector=vector)
    gamma = block["ln1_gamma"]
    beta = block["ln1_beta"]
    expected = layer_norm(vector, gamma, beta)

    input_range = float(np.max(np.abs(vector)) * 1.02)
    difference = vector - np.mean(vector)
    difference_range = float(np.max(np.abs(difference)) * 1.02)
    normalized = difference / np.sqrt(np.mean(difference**2) + EPSILON)
    normalized_range = float(np.max(np.abs(normalized)) * 1.02)
    output_range = float(np.max(np.abs(expected)) * 1.05)
    gamma_max = float(np.max(np.abs(gamma)))

    input_ratios = input_scales / input_range
    input_ratio_max = float(np.max(input_ratios))
    save_gray(
        OUT / "block1-ln1-input-ratios.png",
        (input_ratios / input_ratio_max).reshape(WIDTH, 1),
    )
    save_gray(
        OUT / "block1-ln1-gamma.png", (gamma / gamma_max).reshape(WIDTH, 1)
    )
    save_gray(
        OUT / "block1-ln1-beta.png",
        (CENTER + beta / (2 * output_range)).reshape(WIDTH, 1),
    )
    qkv_ratios = output_range / qkv_input_scales
    qkv_ratio_max = float(np.max(qkv_ratios))
    save_gray(
        OUT / "block1-ln1-qkv-ratios.png",
        (qkv_ratios / qkv_ratio_max).reshape(WIDTH, 1),
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
        f'<feImage href="block1-ln1-input-ratios.png" x="{SOURCE_X}" y="0" '
        f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
        'result="block1-ln1-input-ratios"/>',
        '<feComposite in="SourceGraphic" in2="block1-ln1-input-ratios" '
        f'operator="arithmetic" k1="{input_ratio_max}" k2="0" '
        f'k3="{-CENTER * input_ratio_max}" k4="{center_css}" '
        f'x="{SOURCE_X}" y="0" width="1" height="{WIDTH}" '
        'result="block1-ln1-input"/>',
    ]

    def reduce_vector(source: str, prefix: str) -> tuple[str, int]:
        if REDUCTION == "hier4":
            reduced: list[str] = []
            for shard, start in enumerate(range(0, WIDTH, SHARD)):
                chunk = f"{prefix}-chunk-{shard}"
                primitives.append(
                    f'<feOffset in="{source}" dy="-{start}" x="{SOURCE_X}" '
                    f'y="0" width="1" height="{SHARD}" result="{chunk}"/>'
                )
                current = chunk
                dilation = 1
                for stage_index in range(4):
                    final_stage = stage_index == 3
                    result = (
                        f"{prefix}-part-{shard}"
                        if final_stage
                        else f"{prefix}-chunk-{shard}-h{stage_index}"
                    )
                    region = (
                        f'y="{SHARD - 1}" width="1" height="1"'
                        if final_stage
                        else f'y="0" width="1" height="{SHARD}"'
                    )
                    primitives.append(
                        f'<feConvolveMatrix in="{current}" order="1 4" '
                        'kernelMatrix="1 1 1 1" divisor="4" bias="0" '
                        f'targetX="0" targetY="3" edgeMode="none" '
                        f'kernelUnitLength="1 {dilation}" preserveAlpha="true" '
                        f'x="{SOURCE_X}" {region} result="{result}"/>'
                    )
                    current = result
                    dilation *= 4
                reduced.append(current)
            first = f"{prefix}-first"
            final = f"{prefix}-scalar"
            primitives.extend(
                (
                    f'<feComposite in="{reduced[0]}" in2="{reduced[1]}" '
                    'operator="arithmetic" k1="0" k2=".333333333333" '
                    f'k3=".333333333333" k4="0" result="{first}"/>',
                    f'<feComposite in="{first}" in2="{reduced[2]}" '
                    'operator="arithmetic" k1="0" k2="1" '
                    f'k3=".333333333333" k4="0" result="{final}"/>',
                )
            )
            return final, SHARD - 1

        if REDUCTION == "gaussian-tiled":
            cell = f"{prefix}-cell"
            tiled = f"{prefix}-tiled"
            blurred = f"{prefix}-blurred"
            final = f"{prefix}-scalar"
            surface_height = WIDTH * GAUSSIAN_TILES
            sample_y = surface_height // 2
            primitives.extend(
                (
                    f'<feComposite in="{source}" in2="{source}" operator="in" '
                    f'x="{SOURCE_X}" y="0" width="1" height="{WIDTH}" '
                    f'result="{cell}"/>',
                    f'<feTile in="{cell}" x="{SOURCE_X}" y="0" width="1" '
                    f'height="{surface_height}" result="{tiled}"/>',
                    f'<feGaussianBlur in="{tiled}" stdDeviation="0 {GAUSSIAN_SIGMA:.12g}" '
                    f'edgeMode="none" x="{SOURCE_X}" y="0" width="1" '
                    f'height="{surface_height}" result="{blurred}"/>',
                    f'<feColorMatrix in="{blurred}" values="1 0 0 0 0  '
                    f'0 1 0 0 0  0 0 1 0 0  0 0 0 1 0" '
                    f'x="{SOURCE_X}" y="{sample_y}" width="1" height="1" '
                    f'result="{final}"/>',
                )
            )
            return final, sample_y

        reduced = []
        for shard, start in enumerate(range(0, WIDTH, SHARD)):
            chunk = f"{prefix}-chunk-{shard}"
            part = f"{prefix}-part-{shard}"
            primitives.extend(
                (
                    f'<feOffset in="{source}" dy="-{start}" x="{SOURCE_X}" '
                    f'y="0" width="1" height="{SHARD}" result="{chunk}"/>',
                    f'<feConvolveMatrix in="{chunk}" order="1 {SHARD}" '
                    f'kernelMatrix="{kernel}" divisor="{SHARD}" bias="0" '
                    f'targetX="0" targetY="{SHARD - 1}" edgeMode="none" '
                    f'kernelUnitLength="1 1" preserveAlpha="true" '
                    f'x="{SOURCE_X}" y="{SHARD - 1}" width="1" height="1" '
                    f'result="{part}"/>',
                )
            )
            reduced.append(part)
        first = f"{prefix}-first"
        final = f"{prefix}-scalar"
        primitives.extend(
            (
                f'<feComposite in="{reduced[0]}" in2="{reduced[1]}" '
                'operator="arithmetic" k1="0" k2=".333333333333" '
                f'k3=".333333333333" k4="0" result="{first}"/>',
                f'<feComposite in="{first}" in2="{reduced[2]}" '
                'operator="arithmetic" k1="0" k2="1" '
                f'k3=".333333333333" k4="0" result="{final}"/>',
            )
        )
        return final, SHARD - 1

    mean_scalar, mean_y = reduce_vector("block1-ln1-input", "block1-ln1-mean")
    primitives.extend(
        (
            f'<feOffset in="{mean_scalar}" dy="-{mean_y}" '
            f'x="{SOURCE_X}" y="0" width="1" height="1" '
            'result="block1-ln1-mean-origin"/>',
            f'<feTile in="block1-ln1-mean-origin" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" result="block1-ln1-mean-tiled"/>',
            f'<feColorMatrix in="block1-ln1-input" values="{to_red}" '
            'result="block1-ln1-input-red"/>',
            f'<feColorMatrix in="block1-ln1-mean-tiled" values="{to_green}" '
            'result="block1-ln1-mean-green"/>',
            '<feComposite in="block1-ln1-input-red" '
            'in2="block1-ln1-mean-green" operator="arithmetic" '
            'k1="0" k2="1" k3="1" k4="0" '
            'result="block1-ln1-input-mean-split"/>',
            f'<feColorMatrix in="block1-ln1-input-mean-split" '
            f'values="{difference_matrix}" result="block1-ln1-difference"/>',
            '<feComposite in="block1-ln1-difference" '
            'in2="block1-ln1-difference" operator="arithmetic" '
            f'k1="4" k2="{-4 * CENTER}" k3="{-4 * CENTER}" '
            f'k4="{4 * CENTER * CENTER}" result="block1-ln1-squared-alpha"/>',
            f'<feColorMatrix in="block1-ln1-squared-alpha" values="{copy_red}" '
            'result="block1-ln1-squared"/>',
        )
    )
    variance_scalar, variance_y = reduce_vector(
        "block1-ln1-squared", "block1-ln1-variance"
    )
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
    attention_relative = os.path.relpath(ATTENTION, OUT)
    primitives.extend(
        (
            f'<feComponentTransfer in="{variance_scalar}" '
            'result="block1-ln1-gain-scalar">'
            f'<feFuncR type="table" tableValues="{gain_values}"/>'
            f'<feFuncG type="table" tableValues="{gain_values}"/>'
            f'<feFuncB type="table" tableValues="{gain_values}"/>'
            '<feFuncA type="identity"/></feComponentTransfer>',
            f'<feOffset in="block1-ln1-gain-scalar" dy="-{variance_y}" '
            f'x="{SOURCE_X}" y="0" width="1" height="1" '
            'result="block1-ln1-gain-origin"/>',
            f'<feTile in="block1-ln1-gain-origin" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" result="block1-ln1-gain"/>',
            '<feComposite in="block1-ln1-difference" in2="block1-ln1-gain" '
            f'operator="arithmetic" k1="1" k2="0" k3="-{center_css}" '
            f'k4="{center_css}" result="block1-ln1-normalized"/>',
            f'<feImage href="block1-ln1-gamma.png" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="block1-ln1-gamma"/>',
            '<feComposite in="block1-ln1-normalized" in2="block1-ln1-gamma" '
            f'operator="arithmetic" k1="{gamma_coefficient}" k2="0" '
            f'k3="{-gamma_coefficient * CENTER}" k4="{center_css}" '
            'result="block1-ln1-scaled"/>',
            f'<feImage href="block1-ln1-beta.png" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="block1-ln1-beta"/>',
            '<feComposite in="block1-ln1-scaled" in2="block1-ln1-beta" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="block1-ln1-common"/>',
            f'<feImage href="block1-ln1-qkv-ratios.png" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="block1-ln1-qkv-ratios"/>',
            '<feComposite in="block1-ln1-common" '
            'in2="block1-ln1-qkv-ratios" operator="arithmetic" '
            f'k1="{qkv_ratio_max}" k2="0" '
            f'k3="{-CENTER * qkv_ratio_max}" k4="{center_css}" '
            'result="block1-ln1-qkv-encoded"/>',
            f'<feOffset in="block1-ln1-qkv-encoded" '
            f'dx="{LIVE_X - SOURCE_X}" x="{LIVE_X}" y="0" '
            f'width="1" height="{WIDTH}" result="block1-live-input"/>',
            f'<feImage href="{attention_relative}/normalized-input.png" '
            f'x="0" y="0" width="2" height="{WIDTH}" '
            'preserveAspectRatio="none" result="block1-fixed-inputs"/>',
            '<feMerge result="block1-inputs">'
            '<feMergeNode in="block1-fixed-inputs"/>'
            '<feMergeNode in="block1-live-input"/></feMerge>',
        )
    )

    input_filter = (
        '<filter id="block1-input-stage" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{SOURCE_X + 1}" '
        f'height="{WIDTH * GAUSSIAN_TILES if REDUCTION == "gaussian-tiled" else WIDTH}" '
        'color-interpolation-filters="sRGB">'
        f'{"".join(primitives)}</filter>'
    )
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Live block 0 output normalized for block 1</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="2" height="{WIDTH}" viewBox="0 0 2 {WIDTH}" '
        f'xmlns="http://www.w3.org/2000/svg"><defs>{source_defs}{input_filter}</defs>'
        f'<g filter="url(#block1-input-stage)">{source_content}</g></svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "liveX": LIVE_X,
                "surfaceCenter": CENTER,
                "reduction": REDUCTION,
                "gaussianSigma": GAUSSIAN_SIGMA if REDUCTION == "gaussian-tiled" else None,
                "gaussianTiles": GAUSSIAN_TILES if REDUCTION == "gaussian-tiled" else None,
                "qkvInputScales": qkv_input_scales.tolist(),
                "expected": expected.tolist(),
                "source": os.path.relpath(SOURCE, OUT),
                "attention": attention_relative,
                "primitiveCount": len(primitives),
                "htmlBytes": len(html.encode()),
            }
        )
        + "\n"
    )
    print(
        {
            "html_bytes": len(html.encode()),
            "input_primitives": len(primitives),
            "output_range": output_range,
        }
    )


if __name__ == "__main__":
    main()
