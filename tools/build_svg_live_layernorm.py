#!/usr/bin/env python3
"""Connect the live two-token attention residual to GPT-2 block 0 LN2."""

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
        "SVG_LIVE_LN_SOURCE",
        ROOT / "experiments" / "svg-staged-mixed-projection-centered",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_LIVE_LN_OUT", ROOT / "experiments" / "svg-live-layernorm"
    )
).resolve()
WIDTH = 768
SHARD = 256
CENTER = 128 / 255
SOURCE_X = int(os.environ.get("SVG_LIVE_LN_SOURCE_X", "63"))
BLOCK_INDEX = int(os.environ.get("SVG_LIVE_LN_BLOCK", "0"))
REDUCTION = os.environ.get("SVG_LIVE_LN_REDUCTION", "sharded")
if REDUCTION not in {
    "sharded", "full", "gaussian", "gaussian-tiled", "hier16", "hier4"
}:
    raise ValueError(f"Unknown SVG_LIVE_LN_REDUCTION: {REDUCTION}")
REDUCTION_SHARD = (
    WIDTH
    if REDUCTION == "full"
    else int(os.environ.get("SVG_LIVE_LN_REDUCTION_SHARD", str(SHARD)))
)
if REDUCTION_SHARD <= 0 or WIDTH % REDUCTION_SHARD:
    raise ValueError(
        f"SVG_LIVE_LN_REDUCTION_SHARD must divide {WIDTH}: {REDUCTION_SHARD}"
    )
VARIANCE_METHOD = os.environ.get("SVG_LIVE_LN_VARIANCE", "centered")
if VARIANCE_METHOD not in {"centered", "moments"}:
    raise ValueError(f"Unknown SVG_LIVE_LN_VARIANCE: {VARIANCE_METHOD}")
GAUSSIAN_SIGMA = float(
    os.environ.get(
        "SVG_LIVE_LN_GAUSSIAN_SIGMA",
        "384" if REDUCTION == "gaussian-tiled" else str(WIDTH * 4),
    )
)
GAUSSIAN_GAIN = float(
    os.environ.get("SVG_LIVE_LN_GAUSSIAN_GAIN", str(255 / 97))
)
GAUSSIAN_TILES = int(os.environ.get("SVG_LIVE_LN_GAUSSIAN_TILES", "3"))
if GAUSSIAN_TILES < 3 or GAUSSIAN_TILES % 2 == 0:
    raise ValueError("SVG_LIVE_LN_GAUSSIAN_TILES must be an odd integer >= 3")


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
    for stale in OUT.glob("ln2-*.png"):
        stale.unlink()

    source_page = (SOURCE / "index.html").read_text()
    source_relative = os.path.relpath(SOURCE, OUT)
    source_defs, source_content = svg_parts(source_page)
    source_defs = source_defs.replace('href="', f'href="{source_relative}/')
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    residual_value = source_reference.get(
        "expectedResidual", source_reference.get("expected_residual")
    )
    if residual_value is None:
        raise ValueError("Source reference has no expected residual")
    residual = np.asarray(residual_value, dtype=np.float64)
    if residual.ndim == 2:
        residual = residual[-1]
    residual_scales = np.asarray(
        source_reference.get(
            "residualScales", source_reference.get("residual_scales")
        ),
        dtype=np.float64,
    )
    data = model_data(block_index=BLOCK_INDEX, input_vector=residual)
    gamma = np.asarray(data["ln2_gamma"], dtype=np.float64)
    beta = np.asarray(data["ln2_beta"], dtype=np.float64)
    expected = layer_norm(residual, gamma, beta)

    input_range = float(np.max(np.abs(residual)) * 1.02)
    difference = residual - np.mean(residual)
    difference_range = float(np.max(np.abs(difference)) * 1.02)
    normalized = difference / np.sqrt(np.mean(difference**2) + EPSILON)
    normalized_range = float(np.max(np.abs(normalized)) * 1.02)
    output_range = float(np.max(np.abs(expected)) * 1.05)
    gamma_max = float(np.max(np.abs(gamma)))

    input_ratios = residual_scales / input_range
    input_ratio_max = float(np.max(input_ratios))
    save_gray(
        OUT / "ln2-input-ratios.png",
        (input_ratios / input_ratio_max).reshape(WIDTH, 1),
    )
    save_gray(
        OUT / "ln2-gamma.png", (gamma / gamma_max).reshape(WIDTH, 1)
    )
    save_gray(
        OUT / "ln2-beta.png",
        (CENTER + beta / (2 * output_range)).reshape(WIDTH, 1),
    )

    center_css = f"{CENTER:.12g}"
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
        f'<feImage href="ln2-input-ratios.png" x="{SOURCE_X}" y="0" '
        f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
        'result="ln2-input-ratios"/>',
        '<feComposite in="SourceGraphic" in2="ln2-input-ratios" '
        f'operator="arithmetic" k1="{input_ratio_max}" k2="0" '
        f'k3="{-CENTER * input_ratio_max}" k4="{center_css}" '
        f'x="{SOURCE_X}" y="0" width="1" height="{WIDTH}" '
        'result="ln2-input"/>',
    ]

    def reduce_vector(source: str, prefix: str) -> tuple[str, int]:
        if REDUCTION in {"hier16", "hier4"}:
            factor = 16 if REDUCTION == "hier16" else 4
            stage_count = 2 if factor == 16 else 4
            small_kernel = " ".join("1" for _ in range(factor))
            reduced: list[str] = []
            for shard, start in enumerate(range(0, WIDTH, SHARD)):
                chunk = f"{prefix}-chunk-{shard}"
                primitives.append(
                    f'<feOffset in="{source}" dy="-{start}" x="{SOURCE_X}" '
                    f'y="0" width="1" height="{SHARD}" result="{chunk}"/>'
                )
                current = chunk
                dilation = 1
                for stage_index in range(stage_count):
                    final_stage = stage_index == stage_count - 1
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
                        f'<feConvolveMatrix in="{current}" order="1 {factor}" '
                        f'kernelMatrix="{small_kernel}" divisor="{factor}" bias="0" '
                        f'targetX="0" targetY="{factor - 1}" edgeMode="none" '
                        f'kernelUnitLength="1 {dilation}" preserveAlpha="true" '
                        f'x="{SOURCE_X}" {region} result="{result}"/>'
                    )
                    current = result
                    dilation *= factor
                reduced.append(current)
            first = f"{prefix}-sum-1"
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

        if REDUCTION == "gaussian":
            blurred = f"{prefix}-blurred"
            final = f"{prefix}-scalar"
            gain_matrix = (
                f"{GAUSSIAN_GAIN} 0 0 0 0  "
                f"0 {GAUSSIAN_GAIN} 0 0 0  "
                f"0 0 {GAUSSIAN_GAIN} 0 0  "
                "0 0 0 1 0"
            )
            sample_y = WIDTH // 2
            primitives.extend(
                (
                    f'<feGaussianBlur in="{source}" stdDeviation="0 {GAUSSIAN_SIGMA:.12g}" '
                    f'edgeMode="none" x="{SOURCE_X}" y="0" width="1" height="{WIDTH}" '
                    f'result="{blurred}"/>',
                    f'<feColorMatrix in="{blurred}" values="{gain_matrix}" '
                    f'x="{SOURCE_X}" y="{sample_y}" width="1" height="1" '
                    f'result="{final}"/>',
                )
            )
            return final, sample_y

        reduction_kernel = " ".join("1" for _ in range(REDUCTION_SHARD))
        part_count = WIDTH // REDUCTION_SHARD
        if part_count == 1:
            final = f"{prefix}-scalar"
            primitives.append(
                f'<feConvolveMatrix in="{source}" order="1 {WIDTH}" '
                f'kernelMatrix="{reduction_kernel}" divisor="{WIDTH}" bias="0" '
                f'targetX="0" targetY="{WIDTH - 1}" edgeMode="none" '
                f'kernelUnitLength="1 1" preserveAlpha="true" '
                f'x="{SOURCE_X}" y="{WIDTH - 1}" width="1" height="1" '
                f'result="{final}"/>'
            )
            return final, WIDTH - 1

        reduced: list[str] = []
        for shard, start in enumerate(range(0, WIDTH, REDUCTION_SHARD)):
            chunk = f"{prefix}-chunk-{shard}"
            part = f"{prefix}-part-{shard}"
            primitives.extend(
                (
                    f'<feOffset in="{source}" dy="-{start}" x="{SOURCE_X}" '
                    f'y="0" width="1" height="{REDUCTION_SHARD}" result="{chunk}"/>',
                    f'<feConvolveMatrix in="{chunk}" order="1 {REDUCTION_SHARD}" '
                    f'kernelMatrix="{reduction_kernel}" divisor="{REDUCTION_SHARD}" bias="0" '
                    f'targetX="0" targetY="{REDUCTION_SHARD - 1}" edgeMode="none" '
                    f'kernelUnitLength="1 1" preserveAlpha="true" '
                    f'x="{SOURCE_X}" y="{REDUCTION_SHARD - 1}" width="1" height="1" '
                    f'result="{part}"/>',
                )
            )
            reduced.append(part)
        weight = 1 / part_count
        final = f"{prefix}-scalar"
        accumulated = f"{prefix}-sum-1"
        primitives.append(
            f'<feComposite in="{reduced[0]}" in2="{reduced[1]}" '
            f'operator="arithmetic" k1="0" k2="{weight:.12g}" '
            f'k3="{weight:.12g}" k4="0" result="{accumulated}"/>'
        )
        for index, part in enumerate(reduced[2:], 2):
            result = final if index == part_count - 1 else f"{prefix}-sum-{index}"
            primitives.append(
                f'<feComposite in="{accumulated}" in2="{part}" '
                f'operator="arithmetic" k1="0" k2="1" '
                f'k3="{weight:.12g}" k4="0" result="{result}"/>'
            )
            accumulated = result
        if part_count == 2:
            final = accumulated
        return final, REDUCTION_SHARD - 1

    if VARIANCE_METHOD == "moments":
        primitives.extend(
            (
                '<feComposite in="ln2-input" in2="ln2-input" '
                f'operator="arithmetic" k1="4" k2="{-4 * CENTER}" '
                f'k3="{-4 * CENTER}" k4="{4 * CENTER * CENTER}" '
                'result="ln2-input-squared-alpha"/>',
                f'<feColorMatrix in="ln2-input-squared-alpha" values="{copy_red}" '
                'result="ln2-input-squared"/>',
            )
        )
    mean_scalar, mean_y = reduce_vector("ln2-input", "ln2-mean")
    if VARIANCE_METHOD == "moments":
        second_moment_scalar, second_moment_y = reduce_vector(
            "ln2-input-squared", "ln2-second-moment"
        )
        if second_moment_y != mean_y:
            raise AssertionError("moment reductions must use identical geometry")
    primitives.extend(
        (
            f'<feOffset in="{mean_scalar}" dy="-{mean_y}" '
            f'x="{SOURCE_X}" y="0" width="1" height="1" '
            'result="ln2-mean-origin"/>',
            f'<feTile in="ln2-mean-origin" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" result="ln2-mean-tiled"/>',
            f'<feColorMatrix in="ln2-input" values="{to_red}" '
            'result="ln2-input-red"/>',
            f'<feColorMatrix in="ln2-mean-tiled" values="{to_green}" '
            'result="ln2-mean-green"/>',
            '<feComposite in="ln2-input-red" in2="ln2-mean-green" '
            'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
            'result="ln2-input-mean-split"/>',
            f'<feColorMatrix in="ln2-input-mean-split" '
            f'values="{difference_matrix}" result="ln2-difference"/>',
        )
    )
    if VARIANCE_METHOD == "centered":
        primitives.extend(
            (
                '<feComposite in="ln2-difference" in2="ln2-difference" '
                f'operator="arithmetic" k1="4" k2="{-4 * CENTER}" '
                f'k3="{-4 * CENTER}" k4="{4 * CENTER * CENTER}" '
                'result="ln2-squared-alpha"/>',
                f'<feColorMatrix in="ln2-squared-alpha" values="{copy_red}" '
                'result="ln2-squared"/>',
            )
        )
        variance_scalar, variance_y = reduce_vector("ln2-squared", "ln2-variance")
    else:
        moment_scale = (input_range / difference_range) ** 2
        primitives.extend(
            (
                f'<feComposite in="{mean_scalar}" in2="{mean_scalar}" '
                f'operator="arithmetic" k1="4" k2="{-4 * CENTER}" '
                f'k3="{-4 * CENTER}" k4="{4 * CENTER * CENTER}" '
                'result="ln2-mean-squared"/>',
                f'<feComposite in="{second_moment_scalar}" '
                'in2="ln2-mean-squared" operator="arithmetic" k1="0" '
                f'k2="{moment_scale:.12g}" k3="{-moment_scale:.12g}" k4="0" '
                'result="ln2-variance-scalar"/>',
            )
        )
        variance_scalar, variance_y = "ln2-variance-scalar", mean_y
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
            f'<feComponentTransfer in="{variance_scalar}" result="ln2-gain-scalar">'
            f'<feFuncR type="table" tableValues="{gain_values}"/>'
            f'<feFuncG type="table" tableValues="{gain_values}"/>'
            f'<feFuncB type="table" tableValues="{gain_values}"/>'
            '<feFuncA type="identity"/></feComponentTransfer>',
            f'<feOffset in="ln2-gain-scalar" dy="-{variance_y}" '
            f'x="{SOURCE_X}" y="0" width="1" height="1" '
            'result="ln2-gain-origin"/>',
            f'<feTile in="ln2-gain-origin" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" result="ln2-gain"/>',
            '<feComposite in="ln2-difference" in2="ln2-gain" '
            f'operator="arithmetic" k1="1" k2="0" k3="-{center_css}" '
            f'k4="{center_css}" result="ln2-normalized"/>',
            f'<feImage href="ln2-gamma.png" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="ln2-gamma"/>',
            '<feComposite in="ln2-normalized" in2="ln2-gamma" '
            f'operator="arithmetic" k1="{gamma_coefficient}" k2="0" '
            f'k3="{-gamma_coefficient * CENTER}" k4="{center_css}" '
            'result="ln2-scaled"/>',
            f'<feImage href="ln2-beta.png" x="{SOURCE_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="ln2-beta"/>',
            '<feComposite in="ln2-scaled" in2="ln2-beta" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="ln2-final"/>',
            f'<feOffset in="SourceGraphic" dx="-1" x="{SOURCE_X - 1}" y="0" '
            f'width="1" height="{WIDTH}" result="ln2-residual-pass"/>',
            '<feMerge result="ln2-with-residual">'
            '<feMergeNode in="ln2-residual-pass"/>'
            '<feMergeNode in="ln2-final"/></feMerge>',
        )
    )

    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Live GPT-2 attention residual to LN2</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="1" height="{WIDTH}" viewBox="{SOURCE_X} 0 1 {WIDTH}" '
        f'xmlns="http://www.w3.org/2000/svg"><defs>{source_defs}'
        '<filter id="ln2-stage" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{SOURCE_X + 1}" '
        f'height="{WIDTH * GAUSSIAN_TILES if REDUCTION == "gaussian-tiled" else WIDTH}" '
        'color-interpolation-filters="sRGB">'
        f'{"".join(primitives)}</filter></defs>'
        f'<g filter="url(#ln2-stage)">{source_content}</g></svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "sourceX": SOURCE_X,
                "residualX": SOURCE_X - 1,
                "blockIndex": BLOCK_INDEX,
                "reduction": REDUCTION,
                "reductionShard": REDUCTION_SHARD,
                "varianceMethod": VARIANCE_METHOD,
                "gaussianSigma": GAUSSIAN_SIGMA if REDUCTION.startswith("gaussian") else None,
                "gaussianGain": GAUSSIAN_GAIN if REDUCTION == "gaussian" else None,
                "gaussianTiles": GAUSSIAN_TILES if REDUCTION == "gaussian-tiled" else None,
                "surfaceCenter": CENTER,
                "inputRange": input_range,
                "differenceRange": difference_range,
                "normalizedRange": normalized_range,
                "outputRange": output_range,
                "expected": expected.tolist(),
                "expectedResidual": residual.tolist(),
                "residualScales": residual_scales.tolist(),
                "source": os.path.relpath(SOURCE, OUT),
                "primitiveCount": len(primitives),
                "htmlBytes": len(html.encode()),
            }
        )
        + "\n"
    )
    print(
        {
            "html_bytes": len(html.encode()),
            "ln2_primitives": len(primitives),
            "output_range": output_range,
        }
    )


if __name__ == "__main__":
    main()
