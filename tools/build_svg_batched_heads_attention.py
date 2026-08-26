#!/usr/bin/env python3
"""Build a no-JS SVG attention core that batches all GPT-2 heads spatially."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REFERENCE = (
    ROOT / "experiments" / "gpt2-block-css" / "view-timeline-attention-2token-reference.json"
)
OUT = Path(
    os.environ.get(
        "SVG_BATCHED_ATTENTION_OUT",
        ROOT / "experiments" / "svg-multitoken-attention-batched",
    )
).resolve()
HEADS = 12
HEAD_WIDTH = 64
WIDTH = HEADS * HEAD_WIDTH
REDUCE_WIDTH = HEAD_WIDTH
SCORE_X = REDUCE_WIDTH - 1
SURFACE_WIDTH = WIDTH
REDUCTION_SURFACE_WIDTH = WIDTH
CENTER = 128 / 255
BASE_Y = int(os.environ.get("SVG_BATCHED_ATTENTION_BASE_Y", "0"))
if BASE_Y < 0:
    raise ValueError("SVG_BATCHED_ATTENTION_BASE_Y must be non-negative")
BROADCAST_MODE = os.environ.get("SVG_BATCHED_ATTENTION_BROADCAST", "tile")
if BROADCAST_MODE not in {"tile", "convolve"}:
    raise ValueError("SVG_BATCHED_ATTENTION_BROADCAST must be 'tile' or 'convolve'")


def save_gray(path: Path, values: np.ndarray) -> None:
    pixels = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_reference = json.loads(SOURCE_REFERENCE.read_text())
    normalized = np.asarray(source_reference["normalized"], dtype=np.float64)
    tensors = SafeTensors(MODEL_PATH)
    qkv_weight = np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    )
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    qkv = normalized @ qkv_weight + qkv_bias
    query, key, value = (
        part.reshape(2, HEADS, HEAD_WIDTH) for part in np.split(qkv, 3, axis=1)
    )
    qkv_scales = np.maximum(np.max(np.abs(qkv), axis=0) * 1.08, 1e-6)
    part_scales = [
        qkv_scales[start : start + WIDTH].reshape(HEADS, HEAD_WIDTH)
        for start in (0, WIDTH, 2 * WIDTH)
    ]
    for token in range(2):
        for part_name, part_values, scales in zip(
            ("q", "k", "v"), (query, key, value), part_scales
        ):
            packed = CENTER + part_values[token].reshape(1, WIDTH) / (
                2 * scales.reshape(1, WIDTH)
            )
            save_gray(
                OUT / f"t{token}-{part_name}.png",
                packed,
            )

    scores = np.empty((HEADS, 2), dtype=np.float64)
    probabilities = np.empty_like(scores)
    context = np.empty((2, HEADS, HEAD_WIDTH), dtype=np.float64)
    context[0] = value[0]
    for head in range(HEADS):
        scores[head] = [
            np.dot(query[1, head], key[source, head]) / math.sqrt(HEAD_WIDTH)
            for source in range(2)
        ]
        shifted = scores[head] - np.max(scores[head])
        probabilities[head] = np.exp(shifted) / np.exp(shifted).sum()
        context[1, head] = (
            probabilities[head, 0] * value[0, head]
            + probabilities[head, 1] * value[1, head]
        )

    # Both score products remain sign/magnitude separated until reduction. The
    # shared range must therefore cover the positive and negative accumulation
    # pools, not only the much smaller final score difference.
    term_sets: list[np.ndarray] = []
    head_ranges: list[float] = []
    for head in range(HEADS):
        term0 = query[1, head] * key[0, head] / math.sqrt(HEAD_WIDTH)
        term1 = query[1, head] * key[1, head] / math.sqrt(HEAD_WIDTH)
        positive_pool = np.maximum(term0, 0).sum() + np.maximum(-term1, 0).sum()
        negative_pool = np.maximum(-term0, 0).sum() + np.maximum(term1, 0).sum()
        head_ranges.append(float(max(positive_pool, negative_pool, 1e-9) * 1.08))
        term_sets.append(term0 - term1)
    difference_range = max(head_ranges)

    grid = np.linspace(0, 1, 256)
    positive_table = " ".join(
        f"{item:.8g}" for item in np.clip(2 * (grid - CENTER), 0, 1)
    )
    negative_table = " ".join(
        f"{item:.8g}" for item in np.clip(2 * (CENTER - grid), 0, 1)
    )
    sigmoid_table = " ".join(
        f"{1 / (1 + math.exp(-((item - CENTER) * 2 * difference_range))):.8g}"
        for item in grid
    )
    center_css = f"{CENTER:.12g}"
    swap_rg = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    positive_matrix = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_matrix = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    signed_to_common = (
        f".5 -.5 0 0 {center_css}  .5 -.5 0 0 {center_css}  "
        f".5 -.5 0 0 {center_css}  0 0 0 0 1"
    )
    kernel = " ".join("1" for _ in range(REDUCE_WIDTH))
    primitives: list[str] = []

    def split(source: str, result: str) -> None:
        primitives.append(
            f'<feComponentTransfer in="{source}" result="{result}">'
            f'<feFuncR type="table" tableValues="{positive_table}"/>'
            f'<feFuncG type="table" tableValues="{negative_table}"/>'
            '<feFuncB type="table" tableValues="0 0"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )

    for token in range(2):
        for part in ("q", "k", "v"):
            name = f"t{token}-{part}"
            primitives.append(
                f'<feImage href="{name}.png" x="0" y="{BASE_Y}" '
                f'width="{SURFACE_WIDTH}" height="1" '
                f'preserveAspectRatio="none" result="{name}"/>'
            )
            split(name, f"{name}-signed")
    fixed_input_primitive_count = len(primitives)

    query_scales = part_scales[0]
    key_scales = part_scales[1]
    scaled_products: list[str] = []
    all_factors = [
        query_scales * key_scales / math.sqrt(HEAD_WIDTH) / difference_range
        for _ in range(2)
    ]
    head_factor_max = np.maximum(
        np.max(np.stack(all_factors), axis=(0, 2)), 1e-12
    )
    head_divisors = np.asarray(
        [
            head_ranges[head]
            / (1.08 * difference_range * head_factor_max[head])
            * 1.02
            for head in range(HEADS)
        ],
        dtype=np.float64,
    )
    for source in range(2):
        prefix = f"score{source}"
        primitives.extend(
            (
                f'<feColorMatrix in="t{source}-k-signed" values="{swap_rg}" '
                f'result="{prefix}-k-swapped"/>',
                f'<feComposite in="t1-q-signed" in2="t{source}-k-signed" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-same"/>',
                f'<feComposite in="t1-q-signed" in2="{prefix}-k-swapped" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-cross"/>',
                f'<feColorMatrix in="{prefix}-same" values="{positive_matrix}" '
                f'result="{prefix}-positive"/>',
                f'<feColorMatrix in="{prefix}-cross" values="{negative_matrix}" '
                f'result="{prefix}-negative"/>',
                f'<feComposite in="{prefix}-positive" in2="{prefix}-negative" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-signed"/>',
            )
        )
        packed_factors = (
            all_factors[source] / head_factor_max[:, None]
        ).reshape(1, SURFACE_WIDTH)
        save_gray(OUT / f"{prefix}-scale.png", packed_factors)
        primitives.extend(
            (
                f'<feImage href="{prefix}-scale.png" x="0" y="{BASE_Y}" '
                f'width="{SURFACE_WIDTH}" height="1" '
                f'preserveAspectRatio="none" result="{prefix}-scale"/>',
                f'<feComposite in="{prefix}-signed" in2="{prefix}-scale" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" '
                f'k4="0" result="{prefix}-scaled"/>',
            )
        )
        scaled_products.append(f"{prefix}-scaled")

    primitives.extend(
        (
            f'<feColorMatrix in="{scaled_products[1]}" values="{swap_rg}" '
            f'result="score1-negated"/>',
            f'<feComposite in="{scaled_products[0]}" in2="score1-negated" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
            f'result="difference-terms"/>',
        )
    )
    reduced_heads: list[str] = []
    broadcast_kernel = " ".join("1" for _ in range(2 * HEAD_WIDTH - 1))
    for head in range(HEADS):
        start = head * HEAD_WIDTH
        score_x = start + SCORE_X
        raw_result = f"difference-h{head}-raw"
        result = f"difference-h{head}-signed"
        if BROADCAST_MODE == "convolve":
            crop = f"difference-h{head}-terms"
            primitives.append(
                f'<feOffset in="difference-terms" x="{start}" y="{BASE_Y}" '
                f'width="{HEAD_WIDTH}" height="1" result="{crop}"/>'
            )
            primitives.append(
                f'<feConvolveMatrix in="{crop}" order="{2 * HEAD_WIDTH - 1} 1" '
                f'kernelMatrix="{broadcast_kernel}" '
                f'divisor="{head_divisors[head]}" targetX="{HEAD_WIDTH - 1}" '
                f'targetY="0" edgeMode="none" kernelUnitLength="1 1" '
                f'preserveAlpha="false" x="{start}" y="{BASE_Y}" '
                f'width="{HEAD_WIDTH}" height="1" result="{raw_result}"/>'
            )
        else:
            primitives.append(
                f'<feConvolveMatrix in="difference-terms" '
                f'order="{REDUCE_WIDTH} 1" kernelMatrix="{kernel}" '
                f'divisor="{head_divisors[head]}" targetX="{SCORE_X}" '
                f'targetY="0" edgeMode="none" kernelUnitLength="1 1" '
                f'preserveAlpha="false" x="{score_x}" y="{BASE_Y}" width="1" '
                f'height="1" result="{raw_result}"/>'
            )
        factor = head_factor_max[head] * head_divisors[head]
        primitives.append(
            f'<feColorMatrix in="{raw_result}" '
            f'values="{factor} 0 0 0 0  0 {factor} 0 0 0  '
            f'0 0 0 0 0  0 0 0 0 1" result="{result}"/>'
        )
        reduced_heads.append(result)
    primitives.extend(
        (
            '<feMerge result="difference-signed">'
            + "".join(f'<feMergeNode in="{name}"/>' for name in reduced_heads)
            + '</feMerge>',
            f'<feColorMatrix in="difference-signed" values="{signed_to_common}" '
            f'result="difference-common"/>',
        )
    )
    if BROADCAST_MODE == "convolve":
        primitives.extend(
            (
                '<feComponentTransfer in="difference-common" result="prob0-tile">'
                f'<feFuncR type="table" tableValues="{sigmoid_table}"/>'
                f'<feFuncG type="table" tableValues="{sigmoid_table}"/>'
                f'<feFuncB type="table" tableValues="{sigmoid_table}"/>'
                '<feFuncA type="identity"/></feComponentTransfer>',
                '<feComponentTransfer in="prob0-tile" result="prob1-tile">'
                '<feFuncR type="linear" slope="-1" intercept="1"/>'
                '<feFuncG type="linear" slope="-1" intercept="1"/>'
                '<feFuncB type="linear" slope="-1" intercept="1"/>'
                '<feFuncA type="identity"/></feComponentTransfer>',
            )
        )
        probability_surface = "prob0-tile"
    else:
        primitives.extend(
            (
                '<feComponentTransfer in="difference-common" result="prob0">'
                f'<feFuncR type="table" tableValues="{sigmoid_table}"/>'
                f'<feFuncG type="table" tableValues="{sigmoid_table}"/>'
                f'<feFuncB type="table" tableValues="{sigmoid_table}"/>'
                '<feFuncA type="identity"/></feComponentTransfer>',
                '<feComponentTransfer in="prob0" result="prob1">'
                '<feFuncR type="linear" slope="-1" intercept="1"/>'
                '<feFuncG type="linear" slope="-1" intercept="1"/>'
                '<feFuncB type="linear" slope="-1" intercept="1"/>'
                '<feFuncA type="identity"/></feComponentTransfer>',
            )
        )
        probability_outputs: list[str] = []
        for probability in (0, 1):
            tiles: list[str] = []
            for head in range(HEADS):
                start = head * HEAD_WIDTH
                score_x = start + SCORE_X
                origin = f"prob{probability}-h{head}-origin"
                tile = f"prob{probability}-h{head}-tile"
                primitives.extend(
                    (
                        f'<feOffset in="prob{probability}" '
                        f'dx="{start - score_x}" x="{start}" y="{BASE_Y}" '
                        f'width="1" height="1" result="{origin}"/>',
                        f'<feTile in="{origin}" x="{start}" y="{BASE_Y}" '
                        f'width="{HEAD_WIDTH}" height="1" result="{tile}"/>',
                    )
                )
                tiles.append(tile)
                if probability == 0:
                    probability_outputs.append(origin)
            primitives.append(
                f'<feMerge result="prob{probability}-tile">'
                + "".join(f'<feMergeNode in="{tile}"/>' for tile in tiles)
                + '</feMerge>'
            )
        primitives.append(
            '<feMerge result="probability-scalars">'
            + "".join(
                f'<feMergeNode in="{name}"/>' for name in probability_outputs
            )
            + '</feMerge>'
        )
        probability_surface = "probability-scalars"
    primitives.extend(
        (
            '<feComposite in="t0-v-signed" in2="prob0-tile" '
            'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
            'result="weighted0"/>',
            '<feComposite in="t1-v-signed" in2="prob1-tile" '
            'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
            'result="weighted1"/>',
            '<feComposite in="weighted0" in2="weighted1" '
            'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
            'result="context1-signed"/>',
            f'<feColorMatrix in="context1-signed" values="{signed_to_common}" '
            'result="context1-common"/>',
            f'<feOffset in="t0-v" dy="{-BASE_Y}" x="0" y="0" '
            f'width="{SURFACE_WIDTH}" height="1" result="context0-output"/>',
            f'<feOffset in="context1-common" dy="{1 - BASE_Y}" x="0" y="1" '
            f'width="{SURFACE_WIDTH}" height="1" result="context1-output"/>',
            f'<feOffset in="{probability_surface}" dy="{2 - BASE_Y}" x="0" y="2" '
            f'width="{SURFACE_WIDTH}" height="1" '
            'result="probability-output"/>',
            '<feMerge>'
            '<feMergeNode in="context0-output"/>'
            '<feMergeNode in="context1-output"/>'
            '<feMergeNode in="probability-output"/>'
            '</feMerge>',
        )
    )

    html = (
        '<!doctype html><meta charset="utf-8"><title>Batched-head SVG attention</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{SURFACE_WIDTH}" height="3" '
        f'viewBox="0 0 {SURFACE_WIDTH} 3" xmlns="http://www.w3.org/2000/svg">'
        '<defs><filter id="attention" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{REDUCTION_SURFACE_WIDTH}" '
        f'height="{max(3, BASE_Y + 1)}" color-interpolation-filters="sRGB">'
        + "".join(primitives)
        + '</filter></defs>'
        f'<rect width="{SURFACE_WIDTH}" height="3" fill="white" '
        'filter="url(#attention)"/></svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "core-fragment.svg").write_text(
        "".join(primitives[fixed_input_primitive_count:]) + "\n"
    )
    debug_outputs = []
    for head in range(HEADS):
        score_x = head * REDUCE_WIDTH + SCORE_X
        name = f"debug-h{head}"
        debug_outputs.append(
            f'<feOffset in="difference-common" dx="{head - score_x}" '
            f'dy="{-BASE_Y}" x="{head}" y="0" width="1" height="1" '
            f'result="{name}"/>'
        )
    debug_outputs.append(
        '<feMerge>'
        + "".join(f'<feMergeNode in="debug-h{head}"/>' for head in range(HEADS))
        + '</feMerge>'
    )
    debug_html = (
        '<!doctype html><meta charset="utf-8"><title>Batched score debug</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{HEADS}" height="1" viewBox="0 0 {HEADS} 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="debug" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{REDUCTION_SURFACE_WIDTH}" '
        f'height="{max(3, BASE_Y + 1)}" color-interpolation-filters="sRGB">'
        + "".join(primitives)
        + "".join(debug_outputs)
        + '</filter></defs>'
        f'<rect width="{HEADS}" height="1" fill="white" filter="url(#debug)"/>'
        '</svg>'
    )
    (OUT / "score-debug.html").write_text(debug_html)
    reference_payload = {
        "heads": HEADS,
        "headWidth": HEAD_WIDTH,
        "contextStride": HEAD_WIDTH,
        "reductionLaneWidth": REDUCE_WIDTH,
        "surfaceCenter": CENTER,
        "differenceRange": difference_range,
        "headDifferenceRanges": head_ranges,
        "headFactorMax": head_factor_max.tolist(),
        "headDivisors": head_divisors.tolist(),
        "valueScales": part_scales[2].tolist(),
        "expectedContext": context.tolist(),
        "expectedProbabilities": probabilities[:, 0].tolist(),
        "expectedDifferences": (scores[:, 0] - scores[:, 1]).tolist(),
        "primitiveCount": len(primitives),
        "fixedInputPrimitiveCount": fixed_input_primitive_count,
        "htmlBytes": len(html.encode()),
        "baseY": BASE_Y,
        "broadcastMode": BROADCAST_MODE,
    }
    (OUT / "reference.json").write_text(json.dumps(reference_payload, indent=2) + "\n")
    print(json.dumps({key: reference_payload[key] for key in ("primitiveCount", "htmlBytes", "differenceRange")}, indent=2))


if __name__ == "__main__":
    main()
