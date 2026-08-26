#!/usr/bin/env python3
"""Build the live QK/softmax/V core of two-token GPT-2 attention in SVG."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-block-css"
OUT = Path(
    os.environ.get(
        "SVG_MULTITOKEN_OUT", ROOT / "experiments" / "svg-multitoken-attention"
    )
).resolve()
REFERENCE = Path(
    os.environ.get(
        "SVG_MULTITOKEN_REFERENCE",
        SOURCE / "view-timeline-attention-2token-reference.json",
    )
).resolve()
BLOCK_INDEX = int(os.environ.get("SVG_MULTITOKEN_BLOCK", "0"))
WIDTH = 768
HEADS = 12
HEAD_WIDTH = 64
REDUCE_WIDTH = 256
SCORE_X = REDUCE_WIDTH - 1
QKV_WIDTH = 2304
QKV_SHARD = int(os.environ.get("SVG_QKV_SHARD", "256"))
if WIDTH % QKV_SHARD:
    raise ValueError("SVG_QKV_SHARD must divide 768 exactly")
QKV_CY = QKV_SHARD - 1
QKV_CORRECTION_THRESHOLD = float(
    os.environ.get("SVG_QKV_CORRECTION_THRESHOLD", "0.04")
)
QKV_LAYOUT = os.environ.get("SVG_QKV_LAYOUT", "head")
if QKV_LAYOUT not in {"head", "rgb", "group", "part", "vector"}:
    raise ValueError(
        "SVG_QKV_LAYOUT must be 'head', 'rgb', 'group', 'part', or 'vector'"
    )
QKV_GROUP_HEADS = int(os.environ.get("SVG_QKV_GROUP_HEADS", "2"))
if QKV_GROUP_HEADS <= 0 or HEADS % QKV_GROUP_HEADS:
    raise ValueError("SVG_QKV_GROUP_HEADS must be a positive divisor of 12")
RGB_ATTENTION_BROADCAST = os.environ.get(
    "SVG_RGB_ATTENTION_BROADCAST", "convolve"
)
if RGB_ATTENTION_BROADCAST not in {"convolve", "tile"}:
    raise ValueError("SVG_RGB_ATTENTION_BROADCAST must be 'convolve' or 'tile'")
RGB_QKV_TOKEN_BATCH = os.environ.get("SVG_RGB_QKV_TOKEN_BATCH", "0") == "1"
if RGB_QKV_TOKEN_BATCH and QKV_LAYOUT != "rgb":
    raise ValueError("SVG_RGB_QKV_TOKEN_BATCH requires SVG_QKV_LAYOUT=rgb")
RGB_QKV_CENTERED_DOT = os.environ.get("SVG_RGB_QKV_CENTERED_DOT", "0") == "1"
if RGB_QKV_CENTERED_DOT and QKV_LAYOUT != "rgb":
    raise ValueError("SVG_RGB_QKV_CENTERED_DOT requires SVG_QKV_LAYOUT=rgb")
if RGB_QKV_CENTERED_DOT and RGB_QKV_TOKEN_BATCH:
    raise ValueError("centered-dot and token-batch QKV are separate experiments")
RGB_QKV_CENTERED_GAIN = float(os.environ.get("SVG_RGB_QKV_CENTERED_GAIN", "2"))
if RGB_QKV_CENTERED_GAIN <= 0:
    raise ValueError("SVG_RGB_QKV_CENTERED_GAIN must be positive")
RGB_QKV_CENTERED_REDUCTION = os.environ.get(
    "SVG_RGB_QKV_CENTERED_REDUCTION", "convolve"
)
if RGB_QKV_CENTERED_REDUCTION not in {
    "convolve", "gaussian-tiled", "hier4", "hier4-scaled"
}:
    raise ValueError(
        "SVG_RGB_QKV_CENTERED_REDUCTION must be 'convolve', "
        "'gaussian-tiled', 'hier4', or 'hier4-scaled'"
    )
if RGB_QKV_CENTERED_REDUCTION != "convolve" and not RGB_QKV_CENTERED_DOT:
    raise ValueError("alternate centered reduction requires centered-dot QKV")
RGB_QKV_GAUSSIAN_SIGMA = float(
    os.environ.get("SVG_RGB_QKV_GAUSSIAN_SIGMA", str(QKV_SHARD / 2))
)
RGB_QKV_GAUSSIAN_TILES = int(os.environ.get("SVG_RGB_QKV_GAUSSIAN_TILES", "3"))
if RGB_QKV_GAUSSIAN_TILES < 3 or RGB_QKV_GAUSSIAN_TILES % 2 == 0:
    raise ValueError("SVG_RGB_QKV_GAUSSIAN_TILES must be odd and >= 3")
CPROJ_HEADROOM = float(os.environ.get("SVG_CPROJ_HEADROOM", "1.02"))
CENTER = 128 / 255


def save_gray(path: Path, values: np.ndarray) -> None:
    pixels = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(path, optimize=True)


def save_rg(path: Path, positive: np.ndarray, negative: np.ndarray) -> None:
    rgba = np.zeros((*positive.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(np.clip(positive, 0, 1) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(np.clip(negative, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_rgb(path: Path, values: np.ndarray) -> None:
    pixels = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="RGB").save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in (
        "live-t*.png",
        "live-rgb-h*.png",
        "p*-cproj-*.png",
        "p*-projected-ratio.png",
        "p*-input-ratio.png",
        "p*-residual-c*-*ratio.png",
    ):
        for stale_asset in OUT.glob(pattern):
            stale_asset.unlink()
    reference = json.loads(REFERENCE.read_text())
    normalized = np.asarray(reference["normalized"], dtype=np.float64)
    tensors = SafeTensors(MODEL_PATH)
    block_prefix = f"h.{BLOCK_INDEX}"
    qkv_weight = np.asarray(
        tensors.tensor(f"{block_prefix}.attn.c_attn.weight"), dtype=np.float64
    )
    qkv_bias = np.asarray(
        tensors.tensor(f"{block_prefix}.attn.c_attn.bias"), dtype=np.float64
    )
    qkv = normalized @ qkv_weight + qkv_bias
    query, key, value = np.split(qkv, 3, axis=1)
    query = query.reshape(2, HEADS, HEAD_WIDTH)
    key = key.reshape(2, HEADS, HEAD_WIDTH)
    value = value.reshape(2, HEADS, HEAD_WIDTH)
    scores = np.full((2, HEADS, 2), -np.inf)
    probabilities = np.zeros_like(scores)
    context = np.zeros((2, HEADS, HEAD_WIDTH))
    context[0] = value[0]
    probabilities[0, :, 0] = 1
    for head in range(HEADS):
        head_scores = np.asarray(
            [
                np.dot(query[1, head], key[source, head])
                / math.sqrt(HEAD_WIDTH)
                for source in range(2)
            ]
        )
        scores[1, head] = head_scores
        shifted = head_scores - np.max(head_scores)
        probabilities[1, head] = np.exp(shifted) / np.exp(shifted).sum()
        context[1, head] = sum(
            probabilities[1, head, source] * value[source, head]
            for source in range(2)
        )
    expected_context = context.reshape(2, WIDTH)
    qkv_scales = np.maximum(np.max(np.abs(qkv), axis=0) * 1.08, 1e-6)
    input_scales = np.maximum(np.max(np.abs(normalized), axis=0) * 1.08, 1e-6)
    save_gray(
        OUT / "normalized-input.png",
        CENTER + normalized.T / (2 * input_scales[:, None]),
    )
    for token in range(2):
        save_gray(
            OUT / f"qkv-{token}.png",
            (CENTER + qkv[token] / (2 * qkv_scales)).reshape(1, QKV_WIDTH),
        )
        for head in range(HEADS):
            for part, base in (("q", 0), ("k", WIDTH), ("v", 2 * WIDTH)):
                start = base + head * HEAD_WIDTH
                save_gray(
                    OUT / f"t{token}-h{head}-{part}.png",
                    (
                        CENTER
                        + qkv[token, start : start + HEAD_WIDTH]
                        / (2 * qkv_scales[start : start + HEAD_WIDTH])
                    ).reshape(1, HEAD_WIDTH),
                )

    grid = np.linspace(0, 1, 256)
    positive_table = " ".join(
        f"{value:.8g}" for value in np.clip(2 * (grid - CENTER), 0, 1)
    )
    negative_table = " ".join(
        f"{value:.8g}" for value in np.clip(2 * (CENTER - grid), 0, 1)
    )
    swap_rg = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    positive_matrix = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_matrix = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    center_css = f"{CENTER:.12g}"
    signed_to_common = (
        f".5 -.5 0 0 {center_css}  .5 -.5 0 0 {center_css}  "
        f".5 -.5 0 0 {center_css}  0 0 0 0 1"
    )
    kernel = " ".join("1" for _ in range(REDUCE_WIDTH))
    primitives: list[str] = []

    def split(source: str, result: str) -> str:
        primitives.append(split_markup(source, result))
        return result

    def split_markup(source: str, result: str) -> str:
        return (
            f'<feComponentTransfer in="{source}" result="{result}">'
            f'<feFuncR type="table" tableValues="{positive_table}"/>'
            f'<feFuncG type="table" tableValues="{negative_table}"/>'
            '<feFuncB type="table" tableValues="0 0"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )

    for token in range(2):
        for head in range(HEADS):
            for part in ("q", "k", "v"):
                name = f"t{token}-h{head}-{part}"
                primitives.append(
                    f'<feImage href="{name}.png" x="0" y="0" '
                    f'width="{HEAD_WIDTH}" height="1" preserveAspectRatio="none" '
                    f'result="{name}"/>'
                )
                split(name, f"{name}-signed")

    fixed_input_primitive_count = len(primitives)

    def crop(source: str, start: int, result: str) -> str:
        primitives.extend(
            (
                f'<feOffset in="{source}" x="{start}" y="0" '
                f'width="{HEAD_WIDTH}" height="1" result="{result}-crop"/>',
                f'<feOffset in="{result}-crop" dx="-{start}" x="0" y="0" '
                f'width="{HEAD_WIDTH}" height="1" result="{result}"/>',
            )
        )
        return result

    def score(target: int, source: int, head: int) -> tuple[str, float]:
        q_start = head * HEAD_WIDTH
        k_start = WIDTH + head * HEAD_WIDTH
        query = f"t{target}-h{head}-q-signed"
        key = f"t{source}-h{head}-k-signed"
        swapped = f"h{head}-s{source}-k-swap"
        same = f"h{head}-t{target}-s{source}-same"
        cross = f"h{head}-t{target}-s{source}-cross"
        positive = f"h{head}-t{target}-s{source}-positive"
        negative = f"h{head}-t{target}-s{source}-negative"
        product = f"h{head}-t{target}-s{source}-product"
        q_values = qkv[target, q_start : q_start + HEAD_WIDTH]
        k_values = qkv[source, k_start : k_start + HEAD_WIDTH]
        terms = q_values * k_values / math.sqrt(HEAD_WIDTH)
        bound = max(
            float(np.maximum(terms, 0).sum()),
            float(np.maximum(-terms, 0).sum()),
            1e-9,
        ) * 1.08
        factors = (
            qkv_scales[q_start : q_start + HEAD_WIDTH]
            * qkv_scales[k_start : k_start + HEAD_WIDTH]
            / math.sqrt(HEAD_WIDTH)
            / bound
        )
        factor_max = float(np.max(factors))
        save_gray(
            OUT / f"h{head}-t{target}-s{source}-scale.png",
            (factors / factor_max).reshape(1, HEAD_WIDTH),
        )
        primitives.extend(
            (
                f'<feColorMatrix in="{key}" values="{swap_rg}" result="{swapped}"/>',
                f'<feComposite in="{query}" in2="{key}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="{same}"/>',
                f'<feComposite in="{query}" in2="{swapped}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="{cross}"/>',
                f'<feColorMatrix in="{same}" values="{positive_matrix}" '
                f'result="{positive}"/>',
                f'<feColorMatrix in="{cross}" values="{negative_matrix}" '
                f'result="{negative}"/>',
                f'<feComposite in="{positive}" in2="{negative}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="{product}"/>',
                f'<feImage href="h{head}-t{target}-s{source}-scale.png" '
                f'x="0" y="0" width="{HEAD_WIDTH}" height="1" '
                f'preserveAspectRatio="none" result="{product}-scale"/>',
                f'<feComposite in="{product}" in2="{product}-scale" '
                f'operator="arithmetic" k1="{factor_max}" k2="0" k3="0" '
                f'k4="0" result="{product}-scaled"/>',
                f'<feConvolveMatrix in="{product}-scaled" order="{REDUCE_WIDTH} 1" '
                f'kernelMatrix="{kernel}" divisor="1" targetX="{SCORE_X}" '
                f'targetY="0" edgeMode="none" kernelUnitLength="1 1" '
                f'preserveAlpha="false" x="{SCORE_X}" y="0" width="1" '
                f'height="1" result="{product}-sum"/>',
                f'<feColorMatrix in="{product}-sum" values="{signed_to_common}" '
                f'result="{product}-score"/>',
            )
        )
        return f"{product}-score", bound

    context_heads = []
    probability_outputs = []
    probability_ranges = []
    probability_broadcast_kernel = " ".join(
        "1" for _ in range(2 * HEAD_WIDTH - 1)
    )
    for head in range(HEADS):
        score_10, bound_10 = score(1, 0, head)
        score_11, bound_11 = score(1, 1, head)
        score_10_signed = split(score_10, f"h{head}-score10-signed")
        score_11_signed = split(score_11, f"h{head}-score11-signed")
        reference_difference = float(scores[1, head, 0] - scores[1, head, 1])
        difference_range = max(
            abs(reference_difference) * 1.25,
            bound_10 + bound_11,
            1.0,
        )
        factor_10 = bound_10 / difference_range
        factor_11 = bound_11 / difference_range
        scale_10 = (
            f"{factor_10} 0 0 0 0  0 {factor_10} 0 0 0  "
            f"0 0 0 0 0  0 0 0 0 1"
        )
        scale_11_negated = (
            f"0 {factor_11} 0 0 0  {factor_11} 0 0 0 0  "
            f"0 0 0 0 0  0 0 0 0 1"
        )
        primitives.extend(
            (
                f'<feColorMatrix in="{score_10_signed}" values="{scale_10}" '
                f'result="h{head}-score10-scaled"/>',
                f'<feColorMatrix in="{score_11_signed}" values="{scale_11_negated}" '
                f'result="h{head}-score11-negated"/>',
                f'<feComposite in="h{head}-score10-scaled" '
                f'in2="h{head}-score11-negated" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" '
                f'result="h{head}-difference-signed"/>',
                f'<feColorMatrix in="h{head}-difference-signed" '
                f'values="{signed_to_common}" result="h{head}-difference"/>',
            )
        )
        sigmoid = " ".join(
            f"{1 / (1 + math.exp(-((value - CENTER) * 2 * difference_range))):.8g}"
            for value in grid
        )
        primitives.append(
            f'<feComponentTransfer in="h{head}-difference" result="h{head}-prob0">'
            f'<feFuncR type="table" tableValues="{sigmoid}"/>'
            f'<feFuncG type="table" tableValues="{sigmoid}"/>'
            f'<feFuncB type="table" tableValues="{sigmoid}"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )
        primitives.append(
            f'<feOffset in="h{head}-prob0" dx="{head - SCORE_X}" dy="2" '
            f'x="{head}" y="2" width="1" height="1" '
            f'result="h{head}-probability-output"/>'
        )
        probability_outputs.append(f"h{head}-probability-output")
        primitives.append(
            f'<feComponentTransfer in="h{head}-prob0" result="h{head}-prob1">'
            '<feFuncR type="linear" slope="-1" intercept="1"/>'
            '<feFuncG type="linear" slope="-1" intercept="1"/>'
            '<feFuncB type="linear" slope="-1" intercept="1"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )
        for probability in (0, 1):
            if QKV_LAYOUT == "rgb" and RGB_ATTENTION_BROADCAST == "convolve":
                primitives.append(
                    f'<feConvolveMatrix in="h{head}-prob{probability}" '
                    f'order="{2 * HEAD_WIDTH - 1} 1" '
                    f'kernelMatrix="{probability_broadcast_kernel}" divisor="1" '
                    f'targetX="{HEAD_WIDTH - 1}" targetY="0" edgeMode="none" '
                    f'kernelUnitLength="1 1" preserveAlpha="false" '
                    f'x="0" y="0" width="{HEAD_WIDTH}" height="1" '
                    f'result="h{head}-prob{probability}-tile"/>'
                )
            else:
                primitives.extend(
                    (
                        f'<feOffset in="h{head}-prob{probability}" '
                        f'dx="-{SCORE_X}" x="0" y="0" width="1" height="1" '
                        f'result="h{head}-prob{probability}-origin"/>',
                        f'<feTile in="h{head}-prob{probability}-origin" x="0" y="0" '
                        f'width="{HEAD_WIDTH}" height="1" '
                        f'result="h{head}-prob{probability}-tile"/>',
                    )
                )
        value_0 = f"t0-h{head}-v-signed"
        value_1 = f"t1-h{head}-v-signed"
        primitives.extend(
            (
                f'<feComposite in="{value_0}" in2="h{head}-prob0-tile" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="h{head}-weighted0"/>',
                f'<feComposite in="{value_1}" in2="h{head}-prob1-tile" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="h{head}-weighted1"/>',
                f'<feComposite in="h{head}-weighted0" in2="h{head}-weighted1" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="h{head}-context-signed"/>',
                f'<feColorMatrix in="h{head}-context-signed" '
                f'values="{signed_to_common}" result="h{head}-context-common"/>',
                f'<feOffset in="h{head}-context-common" dx="{head * HEAD_WIDTH}" dy="1" '
                f'x="{head * HEAD_WIDTH}" y="1" width="{HEAD_WIDTH}" height="1" '
                f'result="h{head}-context-positioned"/>',
            )
        )
        context_heads.append(f"h{head}-context-positioned")
        probability_ranges.append(difference_range)

    context_zero_heads = []
    for head in range(HEADS):
        result = f"h{head}-context0-positioned"
        primitives.append(
            f'<feOffset in="t0-h{head}-v" dx="{head * HEAD_WIDTH}" '
            f'x="{head * HEAD_WIDTH}" y="0" width="{HEAD_WIDTH}" height="1" '
            f'result="{result}"/>'
        )
        context_zero_heads.append(result)
    primitives.extend(
        (
            '<feMerge result="context0-common">'
            + "".join(f'<feMergeNode in="{name}"/>' for name in context_zero_heads)
            + '</feMerge>',
            '<feMerge result="context1-common">'
            + "".join(f'<feMergeNode in="{name}"/>' for name in context_heads)
            + '</feMerge>',
            "<feMerge>"
            + '<feMergeNode in="context0-common"/>'
            + '<feMergeNode in="context1-common"/>'
            + "".join(f'<feMergeNode in="{name}"/>' for name in probability_outputs)
            + "</feMerge>",
        )
    )
    attention_core = primitives[fixed_input_primitive_count:]
    html = (
        '<!doctype html><meta charset="utf-8"><title>Two-token SVG attention</title>'
        '<style>html,body{margin:0;background:black}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{QKV_WIDTH}" height="3" viewBox="0 0 {QKV_WIDTH} 3" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        f'<filter id="attention" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{QKV_WIDTH}" '
        f'height="3" color-interpolation-filters="sRGB">'
        f'{"".join(primitives)}</filter></defs>'
        f'<rect width="{QKV_WIDTH}" height="2" fill="white" filter="url(#attention)"/>'
        '</svg>'
    )
    (OUT / "index.html").write_text(html)

    # Connected fixture: build all 2,304 QKV values from the two live normalized
    # token states, then feed the resulting surface directly into the attention
    # core above.  The 2,304 results are packed as 72 rows of 64 values:
    # token-major, then Q/K/V, then attention head.
    qkv_primitives: list[str] = [
        '<feImage href="normalized-input.png" x="0" y="0" width="2" '
        'height="768" preserveAspectRatio="none" result="live-input-common"/>',
        split_markup("live-input-common", "live-input-signed"),
    ]
    qkv_rows: list[str] = []
    normalized_inputs = normalized / input_scales[None, :]
    output_weights = qkv_weight.T * input_scales[None, :]
    qkv_kernel = " ".join("1" for _ in range(QKV_SHARD))
    contiguous_qkv_primitives: list[str] | None = None

    for token in range(2):
        for part_index, part in enumerate(("q", "k", "v")):
            for head in range(HEADS):
                output_start = part_index * WIDTH + head * HEAD_WIDTH
                output_stop = output_start + HEAD_WIDTH
                row = token * 36 + part_index * HEADS + head
                prefix = f"live-t{token}-{part}-h{head}"
                weights = output_weights[output_start:output_stop]
                units = np.maximum(np.max(np.abs(weights), axis=1), 1e-12)
                normalized_weights = weights / units[:, None]
                all_partials = np.stack(
                    [
                        np.stack(
                            [
                                normalized_weights[:, shard : shard + QKV_SHARD]
                                @ normalized_inputs[
                                    input_token, shard : shard + QKV_SHARD
                                ]
                                for shard in range(0, WIDTH, QKV_SHARD)
                            ],
                            axis=1,
                        )
                        for input_token in range(2)
                    ],
                    axis=0,
                )
                bias_units = qkv_bias[output_start:output_stop] / units
                cumulative = np.cumsum(all_partials, axis=2) + bias_units[None, :, None]
                divisor = max(float(np.max(np.abs(cumulative))), 1e-12) * 1.02
                qkv_primitives.extend(
                    (
                        f'<feOffset in="live-input-signed" x="{token}" y="0" '
                        f'width="1" height="768" result="{prefix}-column"/>',
                        f'<feOffset in="{prefix}-column" dx="-{token}" x="0" y="0" '
                        f'width="1" height="768" result="{prefix}-input"/>',
                    )
                )
                encoded_parts: list[str] = []
                for shard_index, shard in enumerate(range(0, WIDTH, QKV_SHARD)):
                    shard_weights = normalized_weights[:, shard : shard + QKV_SHARD]
                    magnitude = 0.0
                    for input_token in range(2):
                        products = (
                            shard_weights
                            * normalized_inputs[
                                input_token, None, shard : shard + QKV_SHARD
                            ]
                        )
                        magnitude = max(
                            magnitude,
                            float(np.max(np.maximum(products, 0).sum(axis=1))),
                            float(np.max(np.maximum(-products, 0).sum(axis=1))),
                        )
                    magnitude = max(magnitude * 1.02, 1e-12)
                    coefficient = magnitude / (2 * divisor)
                    encoded_matrix = (
                        f"{coefficient} -{coefficient} 0 0 {center_css}  " * 3
                        + "0 0 0 0 1"
                    )
                    image_name = f"{prefix}-s{shard_index}-coarse-weights"
                    save_rg(
                        OUT / f"{image_name}.png",
                        np.maximum(shard_weights.T, 0),
                        np.maximum(-shard_weights.T, 0),
                    )
                    path_prefix = f"{prefix}-s{shard_index}-coarse"
                    qkv_primitives.extend(
                        (
                            f'<feOffset in="{prefix}-input" y="{shard}" width="1" '
                            f'height="{QKV_SHARD}" result="{path_prefix}-crop"/>',
                            f'<feOffset in="{path_prefix}-crop" dy="-{shard}" '
                            f'x="0" y="0" width="1" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-origin"/>',
                            f'<feTile in="{path_prefix}-origin" x="0" y="0" '
                            f'width="64" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-values"/>',
                            f'<feColorMatrix in="{path_prefix}-values" '
                            f'values="{swap_rg}" result="{path_prefix}-swapped"/>',
                            f'<feImage href="{image_name}.png" x="0" y="0" '
                            f'width="64" height="{QKV_SHARD}" '
                            f'preserveAspectRatio="none" result="{path_prefix}-weights"/>',
                            f'<feComposite in="{path_prefix}-weights" '
                            f'in2="{path_prefix}-values" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-same"/>',
                            f'<feComposite in="{path_prefix}-weights" '
                            f'in2="{path_prefix}-swapped" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-cross"/>',
                            f'<feColorMatrix in="{path_prefix}-same" '
                            f'values="{positive_matrix}" result="{path_prefix}-pos"/>',
                            f'<feColorMatrix in="{path_prefix}-cross" '
                            f'values="{negative_matrix}" result="{path_prefix}-neg"/>',
                            f'<feComposite in="{path_prefix}-pos" '
                            f'in2="{path_prefix}-neg" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{path_prefix}-product"/>',
                            f'<feConvolveMatrix in="{path_prefix}-product" '
                            f'order="1 {QKV_SHARD}" kernelMatrix="{qkv_kernel}" '
                            f'divisor="{magnitude}" targetX="0" targetY="{QKV_CY}" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="0" y="{QKV_CY}" '
                            f'width="64" height="1" result="{path_prefix}-sum"/>',
                            f'<feColorMatrix in="{path_prefix}-sum" '
                            f'values="{encoded_matrix}" result="{path_prefix}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{path_prefix}-encoded")

                total = encoded_parts[0]
                for shard_index, encoded in enumerate(encoded_parts[1:], 1):
                    result = f"{prefix}-total{shard_index}"
                    qkv_primitives.append(
                        f'<feComposite in="{total}" in2="{encoded}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{result}"/>'
                    )
                    total = result
                bias_values = CENTER + 0.5 * bias_units / divisor
                save_gray(OUT / f"{prefix}-bias.png", bias_values.reshape(1, 64))
                qkv_primitives.extend(
                    (
                        f'<feImage href="{prefix}-bias.png" x="0" y="{QKV_CY}" '
                        f'width="64" height="1" preserveAspectRatio="none" '
                        f'result="{prefix}-bias"/>',
                        f'<feComposite in="{total}" in2="{prefix}-bias" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{prefix}-biased"/>',
                    )
                )
                scale_values = units / qkv_scales[output_start:output_stop]
                max_scale = float(np.max(scale_values))
                normalized_scale = scale_values / max_scale
                qkv_primitives.append(
                    split_markup(f"{prefix}-biased", f"{prefix}-raw-signed")
                )
                if (
                    part_index < 2
                    and float(np.min(normalized_scale)) < QKV_CORRECTION_THRESHOLD
                ):
                    coarse_scale = np.floor(normalized_scale * 255) / 255
                    correction_scale = (normalized_scale - coarse_scale) * 255
                    save_gray(
                        OUT / f"{prefix}-scale-coarse.png",
                        coarse_scale.reshape(1, 64),
                    )
                    save_gray(
                        OUT / f"{prefix}-scale-correction.png",
                        correction_scale.reshape(1, 64),
                    )
                    qkv_primitives.extend(
                        (
                            f'<feImage href="{prefix}-scale-coarse.png" x="0" y="{QKV_CY}" '
                            f'width="64" height="1" preserveAspectRatio="none" '
                            f'result="{prefix}-scale-coarse"/>',
                            f'<feImage href="{prefix}-scale-correction.png" x="0" y="{QKV_CY}" '
                            f'width="64" height="1" preserveAspectRatio="none" '
                            f'result="{prefix}-scale-correction"/>',
                            f'<feComposite in="{prefix}-raw-signed" '
                            f'in2="{prefix}-scale-coarse" operator="arithmetic" '
                            f'k1="{divisor * max_scale}" k2="0" k3="0" k4="0" '
                            f'result="{prefix}-scaled-coarse"/>',
                            f'<feComposite in="{prefix}-raw-signed" '
                            f'in2="{prefix}-scale-correction" operator="arithmetic" '
                            f'k1="{divisor * max_scale / 255}" k2="0" k3="0" k4="0" '
                            f'result="{prefix}-scaled-correction"/>',
                            f'<feComposite in="{prefix}-scaled-coarse" '
                            f'in2="{prefix}-scaled-correction" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{prefix}-scaled-signed"/>',
                        )
                    )
                else:
                    save_gray(
                        OUT / f"{prefix}-scale.png",
                        normalized_scale.reshape(1, 64),
                    )
                    qkv_primitives.extend(
                        (
                            f'<feImage href="{prefix}-scale.png" x="0" y="{QKV_CY}" '
                            f'width="64" height="1" preserveAspectRatio="none" '
                            f'result="{prefix}-scale"/>',
                            f'<feComposite in="{prefix}-raw-signed" '
                            f'in2="{prefix}-scale" operator="arithmetic" '
                            f'k1="{divisor * max_scale}" k2="0" k3="0" k4="0" '
                            f'result="{prefix}-scaled-signed"/>',
                        )
                    )
                qkv_primitives.extend(
                    (
                        f'<feColorMatrix in="{prefix}-scaled-signed" '
                        f'values="{signed_to_common}" result="{prefix}-common"/>',
                        split_markup(f"{prefix}-common", f"{prefix}-signed"),
                        f'<feOffset in="{prefix}-common" dy="{row - QKV_CY}" '
                        f'x="0" y="{row}" width="64" height="1" '
                        f'result="{prefix}-positioned"/>',
                    )
                )
                qkv_rows.append(f"{prefix}-positioned")

    if QKV_LAYOUT == "rgb":
        # Pack Q, K, and V for each head into the R, G, and B channels of one
        # 64-pixel surface. Positive and negative accumulations remain on two
        # separate surfaces, so two RGB convolutions replace three RG
        # convolutions without changing the 256x64 fast-path geometry.
        qkv_primitives = [
            '<feImage href="normalized-input.png" x="0" y="0" width="2" '
            'height="768" preserveAspectRatio="none" result="live-input-common"/>',
            split_markup("live-input-common", "live-input-signed"),
        ]
        qkv_rows = []
        replicate_positive = (
            "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
        )
        replicate_negative = (
            "0 1 0 0 0  0 1 0 0 0  0 1 0 0 0  0 0 0 0 1"
        )
        channel_extract = {
            "q": "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1",
            "k": "0 1 0 0 0  0 1 0 0 0  0 1 0 0 0  0 0 0 0 1",
            "v": "0 0 1 0 0  0 0 1 0 0  0 0 1 0 0  0 0 0 0 1",
        }
        for token in range(2):
            qkv_primitives.extend(
                (
                    f'<feOffset in="live-input-signed" x="{token}" y="0" '
                    f'width="1" height="768" result="live-t{token}-column"/>',
                    f'<feOffset in="live-t{token}-column" dx="-{token}" '
                    f'x="0" y="0" width="1" height="768" '
                    f'result="live-t{token}-input"/>',
                )
            )
            if RGB_QKV_CENTERED_DOT:
                qkv_primitives.extend(
                    (
                        f'<feOffset in="live-input-common" x="{token}" y="0" '
                        f'width="1" height="768" '
                        f'result="live-t{token}-common-column"/>',
                        f'<feOffset in="live-t{token}-common-column" '
                        f'dx="-{token}" x="0" y="0" width="1" height="768" '
                        f'result="live-t{token}-input-common"/>',
                    )
                )
        for head in range(HEADS):
            output_indices = np.stack(
                [
                    np.arange(
                        part_index * WIDTH + head * HEAD_WIDTH,
                        part_index * WIDTH + (head + 1) * HEAD_WIDTH,
                    )
                    for part_index in range(3)
                ]
            )
            weights = output_weights[output_indices]
            units = np.maximum(np.max(np.abs(weights), axis=2), 1e-12)
            normalized_weights = weights / units[:, :, None]
            bias_units = qkv_bias[output_indices] / units
            all_partials = np.stack(
                [
                    np.stack(
                        [
                            np.einsum(
                                "cos,s->co",
                                normalized_weights[:, :, shard : shard + QKV_SHARD],
                                normalized_inputs[
                                    input_token, shard : shard + QKV_SHARD
                                ],
                            )
                            for shard in range(0, WIDTH, QKV_SHARD)
                        ],
                        axis=2,
                    )
                    for input_token in range(2)
                ],
                axis=0,
            )
            cumulative = np.cumsum(all_partials, axis=3) + bias_units[None, :, :, None]
            divisor = max(float(np.max(np.abs(cumulative))), 1e-12) * 1.02
            shard_metadata: list[tuple[int, float, str, str, str]] = []
            for shard_index, shard in enumerate(range(0, WIDTH, QKV_SHARD)):
                shard_weights = normalized_weights[:, :, shard : shard + QKV_SHARD]
                magnitude = 0.0
                for input_token in range(2):
                    products = (
                        shard_weights
                        * normalized_inputs[
                            input_token, None, None, shard : shard + QKV_SHARD
                        ]
                    )
                    magnitude = max(
                        magnitude,
                        float(np.max(np.maximum(products, 0).sum(axis=2))),
                        float(np.max(np.maximum(-products, 0).sum(axis=2))),
                    )
                magnitude = max(magnitude * 1.02, 1e-12)
                positive_name = f"live-rgb-h{head}-s{shard_index}-positive"
                negative_name = f"live-rgb-h{head}-s{shard_index}-negative"
                centered_name = f"live-rgb-h{head}-s{shard_index}-centered"
                positive_pixels = np.moveaxis(
                    np.maximum(shard_weights, 0), 0, -1
                ).transpose(1, 0, 2)
                negative_pixels = np.moveaxis(
                    np.maximum(-shard_weights, 0), 0, -1
                ).transpose(1, 0, 2)
                if RGB_QKV_TOKEN_BATCH:
                    positive_pixels = np.concatenate(
                        (positive_pixels, positive_pixels), axis=1
                    )
                    negative_pixels = np.concatenate(
                        (negative_pixels, negative_pixels), axis=1
                    )
                if RGB_QKV_CENTERED_DOT:
                    centered_pixels = np.moveaxis(
                        CENTER + 0.5 * shard_weights, 0, -1
                    ).transpose(1, 0, 2)
                    save_rgb(OUT / f"{centered_name}.png", centered_pixels)
                else:
                    save_rgb(OUT / f"{positive_name}.png", positive_pixels)
                    save_rgb(OUT / f"{negative_name}.png", negative_pixels)
                shard_metadata.append(
                    (
                        shard,
                        magnitude,
                        positive_name,
                        negative_name,
                        centered_name,
                    )
                )

            bias_rgb = np.moveaxis(
                CENTER + 0.5 * bias_units / divisor, 0, -1
            ).reshape(1, HEAD_WIDTH, 3)
            if RGB_QKV_TOKEN_BATCH:
                bias_rgb = np.concatenate((bias_rgb, bias_rgb), axis=1)
            save_rgb(OUT / f"live-rgb-h{head}-bias.png", bias_rgb)
            scales = units / qkv_scales[output_indices]
            max_scale = float(np.max(scales))
            normalized_scale = scales / max_scale
            coarse_scale = np.floor(normalized_scale * 255) / 255
            correction_scale = (normalized_scale - coarse_scale) * 255
            coarse_scale_rgb = np.moveaxis(coarse_scale, 0, -1).reshape(
                1, HEAD_WIDTH, 3
            )
            correction_scale_rgb = np.moveaxis(
                correction_scale, 0, -1
            ).reshape(1, HEAD_WIDTH, 3)
            if RGB_QKV_TOKEN_BATCH:
                coarse_scale_rgb = np.concatenate(
                    (coarse_scale_rgb, coarse_scale_rgb), axis=1
                )
                correction_scale_rgb = np.concatenate(
                    (correction_scale_rgb, correction_scale_rgb), axis=1
                )
            save_rgb(
                OUT / f"live-rgb-h{head}-scale-coarse.png",
                coarse_scale_rgb,
            )
            save_rgb(
                OUT / f"live-rgb-h{head}-scale-correction.png",
                correction_scale_rgb,
            )

            if RGB_QKV_TOKEN_BATCH:
                batch_width = 2 * HEAD_WIDTH
                prefix = f"live-batch-rgb-h{head}"
                encoded_parts: list[str] = []
                for shard_index, (
                    shard,
                    magnitude,
                    positive_name,
                    negative_name,
                    _centered_name,
                ) in enumerate(shard_metadata):
                    path_prefix = f"{prefix}-s{shard_index}"
                    coefficient = magnitude / (2 * divisor)
                    encoded_matrix = (
                        f"{coefficient} 0 0 0 {center_css}  "
                        f"0 {coefficient} 0 0 {center_css}  "
                        f"0 0 {coefficient} 0 {center_css}  "
                        "0 0 0 0 1"
                    )
                    positive_inputs: list[str] = []
                    negative_inputs: list[str] = []
                    for token in range(2):
                        token_prefix = f"{path_prefix}-t{token}"
                        x = token * HEAD_WIDTH
                        qkv_primitives.extend(
                            (
                                f'<feOffset in="live-t{token}-input" y="{shard}" '
                                f'width="1" height="{QKV_SHARD}" '
                                f'result="{token_prefix}-crop"/>',
                                f'<feOffset in="{token_prefix}-crop" dy="-{shard}" '
                                f'x="0" y="0" width="1" height="{QKV_SHARD}" '
                                f'result="{token_prefix}-origin"/>',
                                f'<feTile in="{token_prefix}-origin" x="0" y="0" '
                                f'width="{HEAD_WIDTH}" height="{QKV_SHARD}" '
                                f'result="{token_prefix}-values"/>',
                                f'<feColorMatrix in="{token_prefix}-values" '
                                f'values="{replicate_positive}" '
                                f'result="{token_prefix}-input-positive-raw"/>',
                                f'<feColorMatrix in="{token_prefix}-values" '
                                f'values="{replicate_negative}" '
                                f'result="{token_prefix}-input-negative-raw"/>',
                                f'<feOffset in="{token_prefix}-input-positive-raw" '
                                f'dx="{x}" x="{x}" y="0" width="{HEAD_WIDTH}" '
                                f'height="{QKV_SHARD}" '
                                f'result="{token_prefix}-input-positive"/>',
                                f'<feOffset in="{token_prefix}-input-negative-raw" '
                                f'dx="{x}" x="{x}" y="0" width="{HEAD_WIDTH}" '
                                f'height="{QKV_SHARD}" '
                                f'result="{token_prefix}-input-negative"/>',
                            )
                        )
                        positive_inputs.append(f"{token_prefix}-input-positive")
                        negative_inputs.append(f"{token_prefix}-input-negative")
                    qkv_primitives.extend(
                        (
                            '<feMerge result="'
                            f'{path_prefix}-input-positive">'
                            + "".join(
                                f'<feMergeNode in="{name}"/>'
                                for name in positive_inputs
                            )
                            + "</feMerge>",
                            '<feMerge result="'
                            f'{path_prefix}-input-negative">'
                            + "".join(
                                f'<feMergeNode in="{name}"/>'
                                for name in negative_inputs
                            )
                            + "</feMerge>",
                            f'<feImage href="{positive_name}.png" x="0" y="0" '
                            f'width="{batch_width}" height="{QKV_SHARD}" '
                            f'preserveAspectRatio="none" '
                            f'result="{path_prefix}-weights-positive"/>',
                            f'<feImage href="{negative_name}.png" x="0" y="0" '
                            f'width="{batch_width}" height="{QKV_SHARD}" '
                            f'preserveAspectRatio="none" '
                            f'result="{path_prefix}-weights-negative"/>',
                            f'<feComposite in="{path_prefix}-weights-positive" '
                            f'in2="{path_prefix}-input-positive" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-pp"/>',
                            f'<feComposite in="{path_prefix}-weights-negative" '
                            f'in2="{path_prefix}-input-negative" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-nn"/>',
                            f'<feComposite in="{path_prefix}-weights-positive" '
                            f'in2="{path_prefix}-input-negative" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-pn"/>',
                            f'<feComposite in="{path_prefix}-weights-negative" '
                            f'in2="{path_prefix}-input-positive" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-np"/>',
                            f'<feComposite in="{path_prefix}-pp" '
                            f'in2="{path_prefix}-nn" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{path_prefix}-positive"/>',
                            f'<feComposite in="{path_prefix}-pn" '
                            f'in2="{path_prefix}-np" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{path_prefix}-negative"/>',
                            f'<feConvolveMatrix in="{path_prefix}-positive" '
                            f'order="1 {QKV_SHARD}" kernelMatrix="{qkv_kernel}" '
                            f'divisor="{magnitude}" targetX="0" targetY="{QKV_CY}" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="0" y="{QKV_CY}" '
                            f'width="{batch_width}" height="1" '
                            f'result="{path_prefix}-positive-sum"/>',
                            f'<feConvolveMatrix in="{path_prefix}-negative" '
                            f'order="1 {QKV_SHARD}" kernelMatrix="{qkv_kernel}" '
                            f'divisor="{magnitude}" targetX="0" targetY="{QKV_CY}" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="0" y="{QKV_CY}" '
                            f'width="{batch_width}" height="1" '
                            f'result="{path_prefix}-negative-sum"/>',
                            f'<feComposite in="{path_prefix}-positive-sum" '
                            f'in2="{path_prefix}-negative-sum" '
                            f'operator="arithmetic" k1="0" '
                            f'k2="{coefficient}" k3="-{coefficient}" '
                            f'k4="{center_css}" result="{path_prefix}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{path_prefix}-encoded")
                total = encoded_parts[0]
                for shard_index, encoded in enumerate(encoded_parts[1:], 1):
                    result = f"{prefix}-total{shard_index}"
                    qkv_primitives.append(
                        f'<feComposite in="{total}" in2="{encoded}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{result}"/>'
                    )
                    total = result
                scale_factor = divisor * max_scale
                qkv_primitives.extend(
                    (
                        f'<feImage href="live-rgb-h{head}-bias.png" '
                        f'x="0" y="{QKV_CY}" width="{batch_width}" height="1" '
                        f'preserveAspectRatio="none" result="{prefix}-bias"/>',
                        f'<feComposite in="{total}" in2="{prefix}-bias" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{prefix}-biased"/>',
                        f'<feImage href="live-rgb-h{head}-scale-coarse.png" '
                        f'x="0" y="{QKV_CY}" width="{batch_width}" height="1" '
                        f'preserveAspectRatio="none" '
                        f'result="{prefix}-scale-coarse"/>',
                        f'<feImage href="live-rgb-h{head}-scale-correction.png" '
                        f'x="0" y="{QKV_CY}" width="{batch_width}" height="1" '
                        f'preserveAspectRatio="none" '
                        f'result="{prefix}-scale-correction"/>',
                        f'<feComposite in="{prefix}-biased" '
                        f'in2="{prefix}-scale-coarse" operator="arithmetic" '
                        f'k1="{scale_factor}" k2="0" '
                        f'k3="{-scale_factor * CENTER}" k4="{center_css}" '
                        f'result="{prefix}-scaled-coarse"/>',
                        f'<feComposite in="{prefix}-biased" '
                        f'in2="{prefix}-scale-correction" operator="arithmetic" '
                        f'k1="{scale_factor / 255}" k2="0" '
                        f'k3="{-scale_factor * CENTER / 255}" '
                        f'k4="{center_css}" '
                        f'result="{prefix}-scaled-correction"/>',
                        f'<feComposite in="{prefix}-scaled-coarse" '
                        f'in2="{prefix}-scaled-correction" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{prefix}-common"/>',
                    )
                )
                for token in range(2):
                    x = token * HEAD_WIDTH
                    token_common = f"live-t{token}-rgb-h{head}-origin"
                    qkv_primitives.extend(
                        (
                            f'<feOffset in="{prefix}-common" x="{x}" y="{QKV_CY}" '
                            f'width="{HEAD_WIDTH}" height="1" '
                            f'result="{token_common}-crop"/>',
                            f'<feOffset in="{token_common}-crop" dx="-{x}" '
                            f'dy="-{QKV_CY}" x="0" y="0" '
                            f'width="{HEAD_WIDTH}" height="1" '
                            f'result="{token_common}"/>',
                        )
                    )
                    row_base = token * 36
                    for part_index, part in enumerate(("q", "k", "v")):
                        common = f"live-t{token}-{part}-h{head}-common"
                        row = row_base + part_index * HEADS + head
                        qkv_primitives.extend(
                            (
                                f'<feColorMatrix in="{token_common}" '
                                f'values="{channel_extract[part]}" '
                                f'result="{common}"/>',
                                split_markup(
                                    common,
                                    f"live-t{token}-{part}-h{head}-signed",
                                ),
                                f'<feOffset in="{common}" dy="{row}" '
                                f'x="0" y="{row}" width="{HEAD_WIDTH}" height="1" '
                                f'result="{common}-positioned"/>',
                            )
                        )
                        qkv_rows.append(f"{common}-positioned")
                continue

            for token in range(2):
                prefix = f"live-t{token}-rgb-h{head}"
                encoded_parts: list[str] = []
                for shard_index, (
                    shard,
                    magnitude,
                    positive_name,
                    negative_name,
                    centered_name,
                ) in enumerate(shard_metadata):
                    path_prefix = f"{prefix}-s{shard_index}"
                    coefficient = magnitude / (2 * divisor)
                    encoded_matrix = (
                        f"{coefficient} 0 0 0 {center_css}  "
                        f"0 {coefficient} 0 0 {center_css}  "
                        f"0 0 {coefficient} 0 {center_css}  "
                        "0 0 0 0 1"
                    )
                    if RGB_QKV_CENTERED_DOT:
                        product_k1 = RGB_QKV_CENTERED_GAIN
                        product_k2 = -product_k1 * CENTER
                        product_k4 = CENTER + product_k1 * CENTER * CENTER
                        convolution_divisor = product_k1 * divisor / 2
                        convolution_bias = (
                            CENTER
                            - QKV_SHARD * CENTER / convolution_divisor
                        )
                        product_region = ""
                        if RGB_QKV_CENTERED_REDUCTION in {
                            "gaussian-tiled", "hier4", "hier4-scaled"
                        }:
                            product_region = (
                                f' x="0" y="0" width="{HEAD_WIDTH}" '
                                f'height="{QKV_SHARD}"'
                            )
                        if RGB_QKV_CENTERED_REDUCTION == "gaussian-tiled":
                            gaussian_height = QKV_SHARD * RGB_QKV_GAUSSIAN_TILES
                            gaussian_y = gaussian_height // 2
                            gaussian_gain = QKV_SHARD / convolution_divisor
                            gaussian_bias = CENTER * (1 - gaussian_gain)
                            gaussian_matrix = (
                                f"{gaussian_gain} 0 0 0 {gaussian_bias}  "
                                f"0 {gaussian_gain} 0 0 {gaussian_bias}  "
                                f"0 0 {gaussian_gain} 0 {gaussian_bias}  "
                                "0 0 0 1 0"
                            )
                            reduction_markup = (
                                f'<feTile in="{path_prefix}-product-centered" '
                                f'x="0" y="0" width="{HEAD_WIDTH}" '
                                f'height="{gaussian_height}" '
                                f'result="{path_prefix}-product-tiled"/>'
                                f'<feGaussianBlur in="{path_prefix}-product-tiled" '
                                f'stdDeviation="0 {RGB_QKV_GAUSSIAN_SIGMA:.12g}" '
                                f'edgeMode="none" x="0" y="0" '
                                f'width="{HEAD_WIDTH}" height="{gaussian_height}" '
                                f'result="{path_prefix}-product-blurred"/>'
                                f'<feColorMatrix in="{path_prefix}-product-blurred" '
                                f'values="{gaussian_matrix}" x="0" y="{gaussian_y}" '
                                f'width="{HEAD_WIDTH}" height="1" '
                                f'result="{path_prefix}-encoded-sample"/>'
                                f'<feOffset in="{path_prefix}-encoded-sample" '
                                f'dy="{QKV_CY - gaussian_y}" x="0" y="{QKV_CY}" '
                                f'width="{HEAD_WIDTH}" height="1" '
                                f'result="{path_prefix}-encoded"/>'
                            )
                        elif RGB_QKV_CENTERED_REDUCTION in {"hier4", "hier4-scaled"}:
                            hierarchical_gain = QKV_SHARD / convolution_divisor
                            hierarchical_bias = CENTER * (1 - hierarchical_gain)
                            hierarchical_matrix = (
                                f"{hierarchical_gain} 0 0 0 {hierarchical_bias}  "
                                f"0 {hierarchical_gain} 0 0 {hierarchical_bias}  "
                                f"0 0 {hierarchical_gain} 0 {hierarchical_bias}  "
                                "0 0 0 1 0"
                            )
                            scaled_hierarchy = (
                                RGB_QKV_CENTERED_REDUCTION == "hier4-scaled"
                            )
                            stage_gain = hierarchical_gain ** 0.25
                            stage_divisor = 4 / stage_gain if scaled_hierarchy else 4
                            stage_bias = CENTER * (1 - stage_gain) if scaled_hierarchy else 0
                            current = f"{path_prefix}-product-centered"
                            hierarchical_stages = []
                            dilation = 1
                            for hierarchical_index in range(4):
                                final_hierarchical = hierarchical_index == 3
                                result = (
                                    f"{path_prefix}-encoded"
                                    if scaled_hierarchy and final_hierarchical
                                    else f"{path_prefix}-hier-{hierarchical_index}"
                                )
                                region = (
                                    f'x="0" y="{QKV_CY}" width="{HEAD_WIDTH}" height="1"'
                                    if final_hierarchical
                                    else f'x="0" y="0" width="{HEAD_WIDTH}" height="{QKV_SHARD}"'
                                )
                                hierarchical_stages.append(
                                    f'<feConvolveMatrix in="{current}" order="1 4" '
                                    f'kernelMatrix="1 1 1 1" divisor="{stage_divisor:.12g}" '
                                    f'bias="{stage_bias:.12g}" '
                                    f'targetX="0" targetY="3" edgeMode="none" '
                                    f'kernelUnitLength="1 {dilation}" preserveAlpha="false" '
                                    f'{region} result="{result}"/>'
                                )
                                current = result
                                dilation *= 4
                            reduction_markup = "".join(hierarchical_stages)
                            if not scaled_hierarchy:
                                reduction_markup += (
                                    f'<feColorMatrix in="{current}" '
                                    f'values="{hierarchical_matrix}" x="0" y="{QKV_CY}" '
                                    f'width="{HEAD_WIDTH}" height="1" '
                                    f'result="{path_prefix}-encoded"/>'
                                )
                        else:
                            reduction_markup = (
                                f'<feConvolveMatrix in="{path_prefix}-product-centered" '
                                f'order="1 {QKV_SHARD}" '
                                f'kernelMatrix="{qkv_kernel}" '
                                f'divisor="{convolution_divisor}" '
                                f'bias="{convolution_bias}" targetX="0" '
                                f'targetY="{QKV_CY}" edgeMode="none" '
                                f'kernelUnitLength="1 1" preserveAlpha="false" '
                                f'x="0" y="{QKV_CY}" width="{HEAD_WIDTH}" '
                                f'height="1" result="{path_prefix}-encoded"/>'
                            )
                        qkv_primitives.extend(
                            (
                                f'<feOffset in="live-t{token}-input-common" '
                                f'y="{shard}" width="1" height="{QKV_SHARD}" '
                                f'result="{path_prefix}-crop"/>',
                                f'<feOffset in="{path_prefix}-crop" '
                                f'dy="-{shard}" x="0" y="0" width="1" '
                                f'height="{QKV_SHARD}" '
                                f'result="{path_prefix}-origin"/>',
                                f'<feTile in="{path_prefix}-origin" x="0" y="0" '
                                f'width="{HEAD_WIDTH}" height="{QKV_SHARD}" '
                                f'result="{path_prefix}-values"/>',
                                f'<feColorMatrix in="{path_prefix}-values" '
                                f'values="{replicate_positive}" '
                                f'result="{path_prefix}-input-centered"/>',
                                f'<feImage href="{centered_name}.png" x="0" y="0" '
                                f'width="{HEAD_WIDTH}" height="{QKV_SHARD}" '
                                f'preserveAspectRatio="none" '
                                f'result="{path_prefix}-weights-centered"/>',
                                f'<feComposite in="{path_prefix}-input-centered" '
                                f'in2="{path_prefix}-weights-centered" '
                                f'operator="arithmetic" k1="{product_k1}" '
                                f'k2="{product_k2}" k3="{product_k2}" '
                                f'k4="{product_k4}"{product_region} '
                                f'result="{path_prefix}-product-centered"/>',
                                reduction_markup,
                            )
                        )
                        encoded_parts.append(f"{path_prefix}-encoded")
                        continue
                    qkv_primitives.extend(
                        (
                            f'<feOffset in="live-t{token}-input" y="{shard}" '
                            f'width="1" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-crop"/>',
                            f'<feOffset in="{path_prefix}-crop" dy="-{shard}" '
                            f'x="0" y="0" width="1" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-origin"/>',
                            f'<feTile in="{path_prefix}-origin" x="0" y="0" '
                            f'width="{HEAD_WIDTH}" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-values"/>',
                            f'<feColorMatrix in="{path_prefix}-values" '
                            f'values="{replicate_positive}" '
                            f'result="{path_prefix}-input-positive"/>',
                            f'<feColorMatrix in="{path_prefix}-values" '
                            f'values="{replicate_negative}" '
                            f'result="{path_prefix}-input-negative"/>',
                            f'<feImage href="{positive_name}.png" x="0" y="0" '
                            f'width="{HEAD_WIDTH}" height="{QKV_SHARD}" '
                            f'preserveAspectRatio="none" '
                            f'result="{path_prefix}-weights-positive"/>',
                            f'<feImage href="{negative_name}.png" x="0" y="0" '
                            f'width="{HEAD_WIDTH}" height="{QKV_SHARD}" '
                            f'preserveAspectRatio="none" '
                            f'result="{path_prefix}-weights-negative"/>',
                            f'<feComposite in="{path_prefix}-weights-positive" '
                            f'in2="{path_prefix}-input-positive" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-pp"/>',
                            f'<feComposite in="{path_prefix}-weights-negative" '
                            f'in2="{path_prefix}-input-negative" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-nn"/>',
                            f'<feComposite in="{path_prefix}-weights-positive" '
                            f'in2="{path_prefix}-input-negative" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-pn"/>',
                            f'<feComposite in="{path_prefix}-weights-negative" '
                            f'in2="{path_prefix}-input-positive" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-np"/>',
                            f'<feComposite in="{path_prefix}-pp" '
                            f'in2="{path_prefix}-nn" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{path_prefix}-positive"/>',
                            f'<feComposite in="{path_prefix}-pn" '
                            f'in2="{path_prefix}-np" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{path_prefix}-negative"/>',
                            f'<feConvolveMatrix in="{path_prefix}-positive" '
                            f'order="1 {QKV_SHARD}" kernelMatrix="{qkv_kernel}" '
                            f'divisor="{magnitude}" targetX="0" targetY="{QKV_CY}" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="0" y="{QKV_CY}" '
                            f'width="{HEAD_WIDTH}" height="1" '
                            f'result="{path_prefix}-positive-sum"/>',
                            f'<feConvolveMatrix in="{path_prefix}-negative" '
                            f'order="1 {QKV_SHARD}" kernelMatrix="{qkv_kernel}" '
                            f'divisor="{magnitude}" targetX="0" targetY="{QKV_CY}" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="0" y="{QKV_CY}" '
                            f'width="{HEAD_WIDTH}" height="1" '
                            f'result="{path_prefix}-negative-sum"/>',
                            f'<feComposite in="{path_prefix}-positive-sum" '
                            f'in2="{path_prefix}-negative-sum" '
                            f'operator="arithmetic" k1="0" '
                            f'k2="{coefficient}" k3="-{coefficient}" '
                            f'k4="{center_css}" result="{path_prefix}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{path_prefix}-encoded")
                total = encoded_parts[0]
                for shard_index, encoded in enumerate(encoded_parts[1:], 1):
                    result = f"{prefix}-total{shard_index}"
                    qkv_primitives.append(
                        f'<feComposite in="{total}" in2="{encoded}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{result}"/>'
                    )
                    total = result
                scale_factor = divisor * max_scale
                qkv_primitives.extend(
                    (
                        f'<feImage href="live-rgb-h{head}-bias.png" '
                        f'x="0" y="{QKV_CY}" width="{HEAD_WIDTH}" height="1" '
                        f'preserveAspectRatio="none" result="{prefix}-bias"/>',
                        f'<feComposite in="{total}" in2="{prefix}-bias" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{prefix}-biased"/>',
                        f'<feImage href="live-rgb-h{head}-scale-coarse.png" '
                        f'x="0" y="{QKV_CY}" width="{HEAD_WIDTH}" height="1" '
                        f'preserveAspectRatio="none" '
                        f'result="{prefix}-scale-coarse"/>',
                        f'<feImage href="live-rgb-h{head}-scale-correction.png" '
                        f'x="0" y="{QKV_CY}" width="{HEAD_WIDTH}" height="1" '
                        f'preserveAspectRatio="none" '
                        f'result="{prefix}-scale-correction"/>',
                        f'<feComposite in="{prefix}-biased" '
                        f'in2="{prefix}-scale-coarse" operator="arithmetic" '
                        f'k1="{scale_factor}" k2="0" '
                        f'k3="{-scale_factor * CENTER}" k4="{center_css}" '
                        f'result="{prefix}-scaled-coarse"/>',
                        f'<feComposite in="{prefix}-biased" '
                        f'in2="{prefix}-scale-correction" operator="arithmetic" '
                        f'k1="{scale_factor / 255}" k2="0" '
                        f'k3="{-scale_factor * CENTER / 255}" '
                        f'k4="{center_css}" '
                        f'result="{prefix}-scaled-correction"/>',
                        f'<feComposite in="{prefix}-scaled-coarse" '
                        f'in2="{prefix}-scaled-correction" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{prefix}-common"/>',
                        f'<feOffset in="{prefix}-common" dy="-{QKV_CY}" '
                        f'x="0" y="0" width="{HEAD_WIDTH}" height="1" '
                        f'result="{prefix}-origin"/>',
                    )
                )
                row_base = token * 36
                for part_index, part in enumerate(("q", "k", "v")):
                    common = f"live-t{token}-{part}-h{head}-common"
                    row = row_base + part_index * HEADS + head
                    qkv_primitives.extend(
                        (
                            f'<feColorMatrix in="{prefix}-origin" '
                            f'values="{channel_extract[part]}" result="{common}"/>',
                            split_markup(common, f"live-t{token}-{part}-h{head}-signed"),
                            f'<feOffset in="{common}" dy="{row}" '
                            f'x="0" y="{row}" width="{HEAD_WIDTH}" height="1" '
                            f'result="{common}-positioned"/>',
                        )
                    )
                    qkv_rows.append(f"{common}-positioned")

    if QKV_LAYOUT in {"group", "part", "vector"}:
        # Compute contiguous QKV surfaces before attention. ``vector`` uses
        # one 2,304-wide matrix per token. ``part`` uses separate 768-wide Q,
        # K, and V matrices per token, retaining contiguous heads without the
        # very wide intermediate surface.
        qkv_primitives = [
            '<feImage href="normalized-input.png" x="0" y="0" width="2" '
            'height="768" preserveAspectRatio="none" result="live-input-common"/>',
            split_markup("live-input-common", "live-input-signed"),
        ]
        qkv_rows = []
        for token in range(2):
            qkv_primitives.extend(
                (
                    f'<feOffset in="live-input-signed" x="{token}" y="0" '
                    f'width="1" height="768" result="live-t{token}-column"/>',
                    f'<feOffset in="live-t{token}-column" dx="-{token}" '
                    f'x="0" y="0" width="1" height="768" '
                    f'result="live-t{token}-input"/>',
                )
            )

        if QKV_LAYOUT == "vector":
            groups = [("vector", 0, QKV_WIDTH)]
        elif QKV_LAYOUT == "part":
            groups = [
                ("q", 0, WIDTH),
                ("k", WIDTH, 2 * WIDTH),
                ("v", 2 * WIDTH, QKV_WIDTH),
            ]
        else:
            groups = []
            group_width = QKV_GROUP_HEADS * HEAD_WIDTH
            for part_index, part in enumerate(("q", "k", "v")):
                part_start = part_index * WIDTH
                for group_index, start in enumerate(range(0, WIDTH, group_width)):
                    groups.append(
                        (
                            f"{part}g{group_index}",
                            part_start + start,
                            part_start + start + group_width,
                        )
                    )
        for group_name, group_start, group_stop in groups:
            group_width = group_stop - group_start
            group_weights = output_weights[group_start:group_stop]
            group_bias = qkv_bias[group_start:group_stop]
            group_scales = qkv_scales[group_start:group_stop]
            units = np.maximum(np.max(np.abs(group_weights), axis=1), 1e-12)
            normalized_weights = group_weights / units[:, None]
            bias_units = group_bias / units
            all_partials = np.stack(
                [
                    np.stack(
                        [
                            normalized_weights[:, shard : shard + QKV_SHARD]
                            @ normalized_inputs[token, shard : shard + QKV_SHARD]
                            for shard in range(0, WIDTH, QKV_SHARD)
                        ],
                        axis=1,
                    )
                    for token in range(2)
                ],
                axis=0,
            )
            cumulative = np.cumsum(all_partials, axis=2) + bias_units[None, :, None]
            divisor = max(float(np.max(np.abs(cumulative))), 1e-12) * 1.02
            shard_metadata: list[tuple[int, float, str]] = []
            for shard_index, shard in enumerate(range(0, WIDTH, QKV_SHARD)):
                shard_weights = normalized_weights[:, shard : shard + QKV_SHARD]
                magnitude = 0.0
                for token in range(2):
                    products = (
                        shard_weights
                        * normalized_inputs[token, None, shard : shard + QKV_SHARD]
                    )
                    magnitude = max(
                        magnitude,
                        float(np.max(np.maximum(products, 0).sum(axis=1))),
                        float(np.max(np.maximum(-products, 0).sum(axis=1))),
                    )
                magnitude = max(magnitude * 1.02, 1e-12)
                image_name = f"live-{group_name}-s{shard_index}-weights"
                save_rg(
                    OUT / f"{image_name}.png",
                    np.maximum(shard_weights.T, 0),
                    np.maximum(-shard_weights.T, 0),
                )
                shard_metadata.append((shard, magnitude, image_name))

            asset_prefix = f"live-{group_name}"
            save_gray(
                OUT / f"{asset_prefix}-bias.png",
                (CENTER + 0.5 * bias_units / divisor).reshape(1, group_width),
            )
            scale_values = units / group_scales
            max_scale = float(np.max(scale_values))
            normalized_scale = scale_values / max_scale
            coarse_scale = np.floor(normalized_scale * 255) / 255
            correction_scale = (normalized_scale - coarse_scale) * 255
            save_gray(
                OUT / f"{asset_prefix}-scale-coarse.png",
                coarse_scale.reshape(1, group_width),
            )
            save_gray(
                OUT / f"{asset_prefix}-scale-correction.png",
                correction_scale.reshape(1, group_width),
            )

            for token in range(2):
                prefix = f"live-t{token}-{group_name}"
                encoded_parts: list[str] = []
                for shard_index, (shard, magnitude, image_name) in enumerate(
                    shard_metadata
                ):
                    path_prefix = f"{prefix}-s{shard_index}"
                    coefficient = magnitude / (2 * divisor)
                    encoded_matrix = (
                        f"{coefficient} -{coefficient} 0 0 {center_css}  " * 3
                        + "0 0 0 0 1"
                    )
                    qkv_primitives.extend(
                        (
                            f'<feOffset in="live-t{token}-input" y="{shard}" '
                            f'width="1" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-crop"/>',
                            f'<feOffset in="{path_prefix}-crop" dy="-{shard}" '
                            f'x="0" y="0" width="1" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-origin"/>',
                            f'<feTile in="{path_prefix}-origin" x="0" y="0" '
                            f'width="{group_width}" height="{QKV_SHARD}" '
                            f'result="{path_prefix}-values"/>',
                            f'<feColorMatrix in="{path_prefix}-values" '
                            f'values="{swap_rg}" result="{path_prefix}-swapped"/>',
                            f'<feImage href="{image_name}.png" x="0" y="0" '
                            f'width="{group_width}" height="{QKV_SHARD}" '
                            f'preserveAspectRatio="none" '
                            f'result="{path_prefix}-weights"/>',
                            f'<feComposite in="{path_prefix}-weights" '
                            f'in2="{path_prefix}-values" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-same"/>',
                            f'<feComposite in="{path_prefix}-weights" '
                            f'in2="{path_prefix}-swapped" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{path_prefix}-cross"/>',
                            f'<feColorMatrix in="{path_prefix}-same" '
                            f'values="{positive_matrix}" '
                            f'result="{path_prefix}-pos"/>',
                            f'<feColorMatrix in="{path_prefix}-cross" '
                            f'values="{negative_matrix}" '
                            f'result="{path_prefix}-neg"/>',
                            f'<feComposite in="{path_prefix}-pos" '
                            f'in2="{path_prefix}-neg" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{path_prefix}-product"/>',
                            f'<feConvolveMatrix in="{path_prefix}-product" '
                            f'order="1 {QKV_SHARD}" kernelMatrix="{qkv_kernel}" '
                            f'divisor="{magnitude}" targetX="0" '
                            f'targetY="{QKV_CY}" edgeMode="none" '
                            f'kernelUnitLength="1 1" preserveAlpha="true" '
                            f'x="0" y="{QKV_CY}" width="{group_width}" '
                            f'height="1" result="{path_prefix}-sum"/>',
                            f'<feColorMatrix in="{path_prefix}-sum" '
                            f'values="{encoded_matrix}" '
                            f'result="{path_prefix}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{path_prefix}-encoded")
                total = encoded_parts[0]
                for shard_index, encoded in enumerate(encoded_parts[1:], 1):
                    result = f"{prefix}-total{shard_index}"
                    qkv_primitives.append(
                        f'<feComposite in="{total}" in2="{encoded}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{result}"/>'
                    )
                    total = result
                qkv_primitives.extend(
                    (
                        f'<feImage href="{asset_prefix}-bias.png" x="0" '
                        f'y="{QKV_CY}" width="{group_width}" height="1" '
                        f'preserveAspectRatio="none" result="{prefix}-bias"/>',
                        f'<feComposite in="{total}" in2="{prefix}-bias" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{prefix}-biased"/>',
                        split_markup(f"{prefix}-biased", f"{prefix}-raw-signed"),
                        f'<feImage href="{asset_prefix}-scale-coarse.png" '
                        f'x="0" y="{QKV_CY}" width="{group_width}" '
                        f'height="1" preserveAspectRatio="none" '
                        f'result="{prefix}-scale-coarse"/>',
                        f'<feImage href="{asset_prefix}-scale-correction.png" '
                        f'x="0" y="{QKV_CY}" width="{group_width}" '
                        f'height="1" preserveAspectRatio="none" '
                        f'result="{prefix}-scale-correction"/>',
                        f'<feComposite in="{prefix}-raw-signed" '
                        f'in2="{prefix}-scale-coarse" operator="arithmetic" '
                        f'k1="{divisor * max_scale}" k2="0" k3="0" k4="0" '
                        f'result="{prefix}-scaled-coarse"/>',
                        f'<feComposite in="{prefix}-raw-signed" '
                        f'in2="{prefix}-scale-correction" operator="arithmetic" '
                        f'k1="{divisor * max_scale / 255}" '
                        f'k2="0" k3="0" k4="0" '
                        f'result="{prefix}-scaled-correction"/>',
                        f'<feComposite in="{prefix}-scaled-coarse" '
                        f'in2="{prefix}-scaled-correction" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                        f'result="{prefix}-scaled-signed"/>',
                        f'<feColorMatrix in="{prefix}-scaled-signed" '
                        f'values="{signed_to_common}" '
                        f'result="{prefix}-common"/>',
                    )
                )

        # Retain the graph at the point where the live Q/K/V vectors exist as
        # contiguous surfaces. A batched attention consumer can use this
        # fragment directly instead of splitting it into 72 head-local rows.
        contiguous_qkv_primitives = list(qkv_primitives)

        for token in range(2):
            for part_index, part in enumerate(("q", "k", "v")):
                for head in range(HEADS):
                    output_start = part_index * WIDTH + head * HEAD_WIDTH
                    row = token * 36 + part_index * HEADS + head
                    live_name = f"live-t{token}-{part}-h{head}-common"
                    source_name = (
                        f"live-t{token}-vector-common"
                        if QKV_LAYOUT == "vector"
                        else (
                            f"live-t{token}-{part}-common"
                            if QKV_LAYOUT == "part"
                            else f"live-t{token}-{part}g{head // QKV_GROUP_HEADS}-common"
                        )
                    )
                    source_start = (
                        output_start
                        if QKV_LAYOUT == "vector"
                        else (
                            head * HEAD_WIDTH
                            if QKV_LAYOUT == "part"
                            else (head % QKV_GROUP_HEADS) * HEAD_WIDTH
                        )
                    )
                    crop_name = f"{live_name}-{QKV_LAYOUT}-crop"
                    qkv_primitives.extend(
                        (
                            f'<feOffset in="{source_name}" '
                            f'x="{source_start}" y="{QKV_CY}" width="64" '
                            f'height="1" result="{crop_name}"/>',
                            f'<feOffset in="{crop_name}" dx="-{source_start}" '
                            f'x="0" y="{QKV_CY}" width="64" height="1" '
                            f'result="{live_name}"/>',
                            f'<feOffset in="{live_name}" dy="{row - QKV_CY}" '
                            f'x="0" y="{row}" width="64" height="1" '
                            f'result="{live_name}-positioned"/>',
                        )
                    )
                    qkv_rows.append(f"{live_name}-positioned")

    qkv_primitives.append(
        '<feMerge result="live-qkv-grid">'
        + "".join(f'<feMergeNode in="{name}"/>' for name in qkv_rows)
        + '</feMerge>'
    )
    qkv_debug_html = (
        '<!doctype html><meta charset="utf-8"><title>Live QKV surface</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="64" height="72" viewBox="0 0 64 72" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="qkv" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(qkv_primitives)}</filter></defs>'
        '<rect width="2304" height="768" fill="white" filter="url(#qkv)"/>'
        '</svg>'
    )
    (OUT / "qkv-debug.html").write_text(qkv_debug_html)
    if contiguous_qkv_primitives is not None:
        (OUT / "qkv-contiguous-fragment.svg").write_text(
            "".join(contiguous_qkv_primitives) + "\n"
        )
        (OUT / "qkv-contiguous.json").write_text(
            json.dumps(
                {
                    "layout": QKV_LAYOUT,
                    "groupHeads": QKV_GROUP_HEADS if QKV_LAYOUT == "group" else None,
                    "surfaceY": QKV_CY,
                    "surfaceWidth": (
                        QKV_WIDTH
                        if QKV_LAYOUT == "vector"
                        else (
                            WIDTH
                            if QKV_LAYOUT == "part"
                            else QKV_GROUP_HEADS * HEAD_WIDTH
                        )
                    ),
                    "primitiveCount": len(contiguous_qkv_primitives),
                },
                indent=2,
            )
            + "\n"
        )
    connected_inputs: list[str] = []
    staged_inputs: list[str] = []
    handoff_rows: list[str] = []
    for token in range(2):
        for part_index, part in enumerate(("q", "k", "v")):
            for head in range(HEADS):
                row = token * 36 + part_index * HEADS + head
                name = f"t{token}-h{head}-{part}"
                live_name = f"live-t{token}-{part}-h{head}-common"
                if QKV_LAYOUT == "rgb":
                    connected_inputs.extend(
                        (
                            f'<feColorMatrix in="{live_name}" '
                            f'values="1 0 0 0 0  0 1 0 0 0  '
                            f'0 0 1 0 0  0 0 0 0 1" result="{name}"/>',
                            split_markup(name, f"{name}-signed"),
                        )
                    )
                else:
                    connected_inputs.extend(
                        (
                            f'<feOffset in="{live_name}" dy="-{QKV_CY}" '
                            f'x="0" y="0" width="64" height="1" '
                            f'result="{name}"/>',
                            split_markup(name, f"{name}-signed"),
                        )
                    )
                staged_inputs.extend(
                    (
                        f'<feOffset in="SourceGraphic" x="0" y="{row}" '
                        f'width="64" height="1" result="{name}-stage-row"/>',
                        f'<feOffset in="{name}-stage-row" dy="-{row}" x="0" y="0" '
                        f'width="64" height="1" result="{name}"/>',
                        split_markup(name, f"{name}-signed"),
                    )
                )
                connected_inputs.append(
                    f'<feOffset in="{name}" dy="{row}" x="0" y="{row}" '
                    f'width="64" height="1" result="{name}-handoff-row"/>'
                )
                handoff_rows.append(f"{name}-handoff-row")
    handoff_debug_primitives = qkv_primitives + connected_inputs + [
        '<feMerge>'
        + "".join(f'<feMergeNode in="{name}"/>' for name in handoff_rows)
        + '</feMerge>'
    ]
    handoff_debug_html = (
        '<!doctype html><meta charset="utf-8"><title>QKV handoff surface</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="64" height="72" viewBox="0 0 64 72" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="handoff" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(handoff_debug_primitives)}</filter></defs>'
        '<rect width="2304" height="768" fill="white" filter="url(#handoff)"/>'
        '</svg>'
    )
    (OUT / "qkv-handoff-debug.html").write_text(handoff_debug_html)
    connected_primitives = qkv_primitives + connected_inputs + attention_core
    connected_html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Live QKV and two-token SVG attention</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{QKV_WIDTH}" height="3" viewBox="0 0 {QKV_WIDTH} 3" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        f'<filter id="connected" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{QKV_WIDTH}" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(connected_primitives)}</filter></defs>'
        f'<rect width="{QKV_WIDTH}" height="768" fill="white" '
        'filter="url(#connected)"/></svg>'
    )
    (OUT / "connected-qkv.html").write_text(connected_html)
    staged_connected_html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Raster-staged live QKV and attention</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{QKV_WIDTH}" height="3" viewBox="0 0 {QKV_WIDTH} 3" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="qkv-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(qkv_primitives)}</filter>'
        '<filter id="attention-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(staged_inputs + attention_core)}</filter></defs>'
        '<g filter="url(#attention-stage)">'
        '<rect width="2304" height="768" fill="white" '
        'filter="url(#qkv-stage)"/></g></svg>'
    )
    (OUT / "connected-qkv-staged.html").write_text(staged_connected_html)

    # Continue the same live graph through c_proj and the attention residual.
    # This page deliberately stops before LN2 so the boundary can be tested in
    # isolation before adding the much larger MLP.
    cproj_weight = np.asarray(
        tensors.tensor(f"{block_prefix}.attn.c_proj.weight"), dtype=np.float64
    )
    cproj_bias = np.asarray(
        tensors.tensor(f"{block_prefix}.attn.c_proj.bias"), dtype=np.float64
    )
    projected = expected_context @ cproj_weight + cproj_bias
    reference_projected = np.asarray(reference["projected"], dtype=np.float64)
    reference_residual = np.asarray(reference["residual"], dtype=np.float64)
    residual_input = reference_residual - reference_projected
    residual = projected + residual_input
    context_scales = qkv_scales[2 * WIDTH :]
    projected_scales = np.maximum(np.max(np.abs(projected), axis=0) * 1.08, 1e-6)
    residual_input_scales = np.maximum(
        np.max(np.abs(residual_input), axis=0) * 1.08, 1e-6
    )
    residual_scales = np.maximum(np.max(np.abs(residual), axis=0) * 1.08, 1e-6)
    for token in range(2):
        save_gray(
            OUT / f"residual-input-{token}.png",
            (CENTER + residual_input[token] / (2 * residual_input_scales)).reshape(768, 1),
        )

    projection_primitives: list[str] = []
    projection_rows: list[str] = []
    projection_signed_rows: list[str] = []
    projection_chunks_by_token: dict[int, list[str]] = {}
    projection_signed_chunks_by_token: dict[int, list[str]] = {}
    effective_projection = cproj_weight.T * context_scales[None, :]
    normalized_context = expected_context / context_scales[None, :]
    horizontal_kernel = " ".join("1" for _ in range(64))
    for token in (1,):
        base_x = 0
        target_x = 63
        chunk_results: list[str] = []
        chunk_signed_results: list[str] = []
        for chunk_index, output_start in enumerate(range(0, WIDTH, 64)):
            output_stop = output_start + 64
            prefix = f"p{token}-cproj-{chunk_index}"
            weights = effective_projection[output_start:output_stop]
            weight_scales = np.maximum(np.max(np.abs(weights), axis=1), 1e-12)
            units = weight_scales
            normalized_weights = weights / weight_scales[:, None]
            scale_values = units / projected_scales[output_start:output_stop]
            log_scale = np.log2(np.maximum(scale_values, 1e-12))
            bucket_width = (
                2.0
                if chunk_index == 1
                else (
                    5.0
                    if chunk_index == 9
                    else (4.0 if chunk_index == 11 else 3.0)
                )
            )
            bucket_ids = np.floor(
                (log_scale - np.min(log_scale)) / bucket_width
            ).astype(int)
            bucket_paths: list[tuple[str, str]] = []

            for bucket_id in np.unique(bucket_ids):
                mask = bucket_ids == bucket_id
                bucket_prefix = f"{prefix}-b{bucket_id}"
                bucket_weights = np.where(mask[:, None], normalized_weights, 0)
                partials = np.stack(
                    [
                        bucket_weights[:, head * 64 : (head + 1) * 64]
                        @ (
                            value[source_token, head]
                            / context_scales[head * 64 : (head + 1) * 64]
                            * probabilities[token, head, source_token]
                        )
                        for head in range(HEADS)
                        for source_token in range(2)
                    ],
                    axis=1,
                )
                bias_units = np.where(
                    mask, cproj_bias[output_start:output_stop] / units, 0
                )
                cumulative = np.cumsum(partials, axis=1)
                divisor = max(
                    float(np.max(np.abs(cumulative))),
                    float(np.max(np.abs(cumulative[:, -1] + bias_units))),
                    1e-12,
                ) * CPROJ_HEADROOM
                magnitude = 0.0
                for head in range(HEADS):
                    start = head * 64
                    stop = start + 64
                    for source_token in range(2):
                        normalized_value = (
                            value[source_token, head] / context_scales[start:stop]
                        )
                        products = (
                            bucket_weights[:, start:stop]
                            * normalized_value[None, :]
                        )
                        magnitude = max(
                            magnitude,
                            float(np.max(np.maximum(products, 0).sum(axis=1))),
                            float(np.max(np.maximum(-products, 0).sum(axis=1))),
                        )
                magnitude = max(magnitude * 1.02, 1e-12)
                coefficient = magnitude / (2 * divisor)
                encoded_matrix = (
                    f"{coefficient} -{coefficient} 0 0 {center_css}  " * 3
                    + "0 0 0 0 1"
                )
                encoded_parts: list[str] = []
                for contribution_index, (head, source_token) in enumerate(
                    (head, source_token)
                    for head in range(HEADS)
                    for source_token in range(2)
                ):
                    start = head * 64
                    stop = start + 64
                    weight_image = bucket_weights[:, start:stop]
                    save_rg(
                        OUT / f"{bucket_prefix}-w{contribution_index}.png",
                        np.maximum(weight_image, 0),
                        np.maximum(-weight_image, 0),
                    )
                    source_prefix = f"{bucket_prefix}-s{contribution_index}"
                    projection_primitives.extend(
                        (
                            f'<feTile in="t{source_token}-h{head}-v-signed" '
                            f'x="{base_x}" y="{output_start}" width="64" height="64" '
                            f'result="{source_prefix}-values"/>',
                            f'<feColorMatrix in="{source_prefix}-values" '
                            f'values="{swap_rg}" result="{source_prefix}-swapped"/>',
                            f'<feImage href="{bucket_prefix}-w{contribution_index}.png" '
                            f'x="{base_x}" y="{output_start}" width="64" height="64" '
                            f'preserveAspectRatio="none" result="{source_prefix}-weights"/>',
                            f'<feComposite in="{source_prefix}-weights" '
                            f'in2="{source_prefix}-values" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{source_prefix}-same"/>',
                            f'<feComposite in="{source_prefix}-weights" '
                            f'in2="{source_prefix}-swapped" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{source_prefix}-cross"/>',
                            f'<feColorMatrix in="{source_prefix}-same" '
                            f'values="{positive_matrix}" result="{source_prefix}-pos"/>',
                            f'<feColorMatrix in="{source_prefix}-cross" '
                            f'values="{negative_matrix}" result="{source_prefix}-neg"/>',
                            f'<feComposite in="{source_prefix}-pos" '
                            f'in2="{source_prefix}-neg" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{source_prefix}-product"/>',
                            f'<feConvolveMatrix in="{source_prefix}-product" '
                            f'order="64 1" kernelMatrix="{horizontal_kernel}" '
                            f'divisor="{magnitude}" targetX="63" targetY="0" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="{target_x}" y="{output_start}" '
                            f'width="1" height="64" result="{source_prefix}-sum"/>',
                            f'<feTile in="h{head}-prob{source_token}-origin" '
                            f'x="{target_x}" y="{output_start}" width="1" height="64" '
                            f'result="{source_prefix}-probability"/>',
                            f'<feComposite in="{source_prefix}-sum" '
                            f'in2="{source_prefix}-probability" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{source_prefix}-weighted"/>',
                            f'<feColorMatrix in="{source_prefix}-weighted" '
                            f'values="{encoded_matrix}" result="{source_prefix}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{source_prefix}-encoded")
                total = encoded_parts[0]
                for contribution_index, encoded in enumerate(encoded_parts[1:], 1):
                    result = f"{bucket_prefix}-total{contribution_index}"
                    projection_primitives.append(
                        f'<feComposite in="{total}" in2="{encoded}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{result}"/>'
                    )
                    total = result
                save_gray(
                    OUT / f"{bucket_prefix}-bias.png",
                    (CENTER + 0.5 * bias_units / divisor).reshape(64, 1),
                )
                bucket_scale_values = np.where(mask, scale_values, 0)
                max_scale = float(np.max(bucket_scale_values))
                save_gray(
                    OUT / f"{bucket_prefix}-scale.png",
                    (bucket_scale_values / max_scale).reshape(64, 1),
                )
                projection_primitives.extend(
                    (
                        f'<feImage href="{bucket_prefix}-bias.png" x="{target_x}" '
                        f'y="{output_start}" width="1" height="64" '
                        f'preserveAspectRatio="none" result="{bucket_prefix}-bias"/>',
                        f'<feComposite in="{total}" in2="{bucket_prefix}-bias" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{bucket_prefix}-biased"/>',
                        split_markup(
                            f"{bucket_prefix}-biased", f"{bucket_prefix}-signed"
                        ),
                        f'<feImage href="{bucket_prefix}-scale.png" x="{target_x}" '
                        f'y="{output_start}" width="1" height="64" '
                        f'preserveAspectRatio="none" result="{bucket_prefix}-scale"/>',
                        f'<feComposite in="{bucket_prefix}-signed" '
                        f'in2="{bucket_prefix}-scale" operator="arithmetic" '
                        f'k1="{divisor * max_scale}" k2="0" k3="0" k4="0" '
                        f'result="{bucket_prefix}-scaled"/>',
                        f'<feColorMatrix in="{bucket_prefix}-scaled" '
                        f'values="{signed_to_common}" '
                        f'result="{bucket_prefix}-common"/>',
                    )
                )
                bucket_paths.append(
                    (f"{bucket_prefix}-common", f"{bucket_prefix}-scaled")
                )

            common = bucket_paths[0][0]
            signed = bucket_paths[0][1]
            for bucket_index, (bucket_common, bucket_signed) in enumerate(
                bucket_paths[1:], 1
            ):
                common_result = f"{prefix}-common-total{bucket_index}"
                signed_result = f"{prefix}-signed-total{bucket_index}"
                projection_primitives.extend(
                    (
                        f'<feComposite in="{common}" in2="{bucket_common}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{common_result}"/>',
                        f'<feComposite in="{signed}" in2="{bucket_signed}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                        f'result="{signed_result}"/>',
                    )
                )
                common = common_result
                signed = signed_result
            projection_primitives.extend(
                (
                    f'<feOffset in="{common}" result="{prefix}-common"/>',
                    f'<feOffset in="{signed}" result="{prefix}-scaled"/>',
                )
            )
            chunk_results.append(f"{prefix}-common")
            chunk_signed_results.append(f"{prefix}-scaled")
        projection_primitives.extend(
            (
                f'<feMerge result="p{token}-projected-common">'
                + "".join(f'<feMergeNode in="{name}"/>' for name in chunk_results)
                + '</feMerge>',
                f'<feMerge result="p{token}-projected-signed">'
                + "".join(
                    f'<feMergeNode in="{name}"/>' for name in chunk_signed_results
                )
                + '</feMerge>',
            )
        )
        projection_chunks_by_token[token] = chunk_results
        projection_signed_chunks_by_token[token] = chunk_signed_results

    projection_matrix_finish = len(projection_primitives)
    residual_outputs: list[str] = []
    for token in (1,):
        target_x = 63
        projected_ratio = projected_scales / residual_scales
        input_ratio = residual_input_scales / residual_scales
        projection_primitives.extend(
            (
                f'<feImage href="residual-input-{token}.png" x="{target_x}" y="0" '
                f'width="1" height="768" preserveAspectRatio="none" '
                f'result="p{token}-residual-input"/>',
                split_markup(
                    f"p{token}-residual-input", f"p{token}-residual-input-signed"
                ),
            )
        )
        for chunk_index, output_start in enumerate(range(0, WIDTH, 64)):
            projected_chunk = projection_signed_chunks_by_token[token][chunk_index]
            prefix = f"p{token}-residual-c{chunk_index}"
            projected_ratio_chunk = projected_ratio[output_start : output_start + 64]
            input_ratio_chunk = input_ratio[output_start : output_start + 64]
            projected_ratio_max = float(np.max(projected_ratio_chunk))
            input_ratio_max = float(np.max(input_ratio_chunk))
            save_gray(
                OUT / f"{prefix}-projected-ratio.png",
                (projected_ratio_chunk / projected_ratio_max).reshape(64, 1),
            )
            save_gray(
                OUT / f"{prefix}-input-ratio.png",
                (input_ratio_chunk / input_ratio_max).reshape(64, 1),
            )
            projection_primitives.extend(
                (
                    f'<feImage href="{prefix}-projected-ratio.png" '
                    f'x="{target_x}" y="{output_start}" width="1" height="64" '
                    f'preserveAspectRatio="none" '
                    f'result="{prefix}-projected-ratio"/>',
                    f'<feComposite in="{projected_chunk}" '
                    f'in2="{prefix}-projected-ratio" operator="arithmetic" '
                    f'k1="{projected_ratio_max}" k2="0" k3="0" k4="0" '
                    f'x="{target_x}" y="{output_start}" width="1" height="64" '
                    f'result="{prefix}-projected"/>',
                    f'<feOffset in="p{token}-residual-input-signed" '
                    f'x="{target_x}" y="{output_start}" width="1" height="64" '
                    f'result="{prefix}-input-raw"/>',
                    f'<feImage href="{prefix}-input-ratio.png" '
                    f'x="{target_x}" y="{output_start}" width="1" height="64" '
                    f'preserveAspectRatio="none" result="{prefix}-input-ratio"/>',
                    f'<feComposite in="{prefix}-input-raw" '
                    f'in2="{prefix}-input-ratio" operator="arithmetic" '
                    f'k1="{input_ratio_max}" k2="0" k3="0" k4="0" '
                    f'result="{prefix}-input"/>',
                    f'<feComposite in="{prefix}-projected" '
                    f'in2="{prefix}-input" operator="arithmetic" '
                    f'k1="0" k2="1" k3="1" k4="0" '
                    f'x="{target_x}" y="{output_start}" width="1" height="64" '
                    f'result="{prefix}-signed"/>',
                    f'<feColorMatrix in="{prefix}-signed" '
                    f'values="{signed_to_common}" result="{prefix}-common"/>',
                )
            )
            residual_outputs.append(f"{prefix}-common")
    projection_primitives.append(
        '<feMerge>'
        + "".join(f'<feMergeNode in="{name}"/>' for name in residual_outputs)
        + '</feMerge>'
    )
    projection_debug_outputs = projection_chunks_by_token[1]
    projection_debug_tail: list[str] = [
        '<feMerge>'
        + "".join(f'<feMergeNode in="{name}"/>' for name in projection_debug_outputs)
        + '</feMerge>'
    ]
    projection_debug_primitives = (
        qkv_primitives
        + connected_inputs
        + attention_core
        + projection_primitives[:projection_matrix_finish]
        + projection_debug_tail
    )
    projection_debug_html = (
        '<!doctype html><meta charset="utf-8"><title>Attention projection</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="63 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="projection" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(projection_debug_primitives)}</filter></defs>'
        '<rect width="2304" height="768" fill="white" '
        'filter="url(#projection)"/></svg>'
    )
    (OUT / "attention-projection-debug.html").write_text(projection_debug_html)
    staged_projection_primitives = (
        staged_inputs
        + attention_core
        + projection_primitives[:projection_matrix_finish]
        + projection_debug_tail
    )
    staged_projection_html = (
        '<!doctype html><meta charset="utf-8"><title>Staged attention projection</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="63 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="qkv-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(qkv_primitives)}</filter>'
        '<filter id="projection-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(staged_projection_primitives)}</filter></defs>'
        '<g filter="url(#projection-stage)">'
        '<rect width="2304" height="768" fill="white" filter="url(#qkv-stage)"/>'
        '</g></svg>'
    )
    (OUT / "attention-projection-staged.html").write_text(staged_projection_html)
    exact_projection_primitives = (
        primitives
        + projection_primitives[:projection_matrix_finish]
        + projection_debug_tail
    )
    exact_projection_html = (
        '<!doctype html><meta charset="utf-8"><title>Exact-input attention projection</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="63 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="projection" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(exact_projection_primitives)}</filter></defs>'
        '<rect width="2304" height="768" fill="white" '
        'filter="url(#projection)"/></svg>'
    )
    (OUT / "attention-projection-exact-input.html").write_text(
        exact_projection_html
    )
    projection_chunk_debug_primitives = (
        qkv_primitives
        + connected_inputs
        + attention_core
        + projection_primitives[:projection_matrix_finish]
        + ['<feMerge><feMergeNode in="p1-cproj-0-common"/>'
           '<feMergeNode in="p1-cproj-1-common"/></feMerge>']
    )
    projection_chunk_debug_html = (
        '<!doctype html><meta charset="utf-8"><title>Attention projection chunk</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="128" viewBox="63 0 1 128" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="chunk" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(projection_chunk_debug_primitives)}</filter></defs>'
        '<rect width="2304" height="768" fill="white" filter="url(#chunk)"/>'
        '</svg>'
    )
    (OUT / "attention-projection-chunk-debug.html").write_text(
        projection_chunk_debug_html
    )
    block_tail_primitives = qkv_primitives + connected_inputs + attention_core + projection_primitives
    block_tail_html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Live QKV, causal attention, projection and residual</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="63 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="tail" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(block_tail_primitives)}</filter></defs>'
        '<rect width="2304" height="768" fill="white" filter="url(#tail)"/>'
        '</svg>'
    )
    (OUT / "connected-attention-residual.html").write_text(block_tail_html)
    staged_tail_primitives = staged_inputs + attention_core + projection_primitives
    staged_tail_html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Staged QKV, attention, projection and residual</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="63 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="qkv-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(qkv_primitives)}</filter>'
        '<filter id="tail-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(staged_tail_primitives)}</filter></defs>'
        '<g filter="url(#tail-stage)">'
        '<rect width="2304" height="768" fill="white" filter="url(#qkv-stage)"/>'
        '</g></svg>'
    )
    (OUT / "connected-attention-residual-staged.html").write_text(staged_tail_html)
    output_reference = {
        "block_index": BLOCK_INDEX,
        "source_reference": str(REFERENCE),
        "width": WIDTH,
        "heads": HEADS,
        "head_width": HEAD_WIDTH,
        "surface_center": CENTER,
        "value_scales": qkv_scales[2 * WIDTH :].tolist(),
        "expected_context": expected_context.tolist(),
        "expected_probabilities": probabilities[1, :, 0].tolist(),
        "expected_qkv": qkv.tolist(),
        "qkv_scales": qkv_scales.tolist(),
        "input_scales": input_scales.tolist(),
        "expected_projected": projected.tolist(),
        "projected_scales": projected_scales.tolist(),
        "expected_residual": residual.tolist(),
        "residual_scales": residual_scales.tolist(),
        "difference_ranges": probability_ranges,
        "html_bytes": len(html.encode()),
        "connected_qkv_html_bytes": len(connected_html.encode()),
        "connected_qkv_staged_html_bytes": len(staged_connected_html.encode()),
        "connected_attention_residual_html_bytes": len(block_tail_html.encode()),
        "qkv_layout": QKV_LAYOUT,
        "qkv_group_heads": QKV_GROUP_HEADS if QKV_LAYOUT == "group" else None,
        "rgb_attention_broadcast": (
            RGB_ATTENTION_BROADCAST if QKV_LAYOUT == "rgb" else None
        ),
        "rgb_qkv_token_batch": (
            RGB_QKV_TOKEN_BATCH if QKV_LAYOUT == "rgb" else None
        ),
        "rgb_qkv_centered_dot": (
            RGB_QKV_CENTERED_DOT if QKV_LAYOUT == "rgb" else None
        ),
        "rgb_qkv_centered_gain": (
            RGB_QKV_CENTERED_GAIN if RGB_QKV_CENTERED_DOT else None
        ),
        "rgb_qkv_centered_reduction": (
            RGB_QKV_CENTERED_REDUCTION if RGB_QKV_CENTERED_DOT else None
        ),
        "rgb_qkv_gaussian_sigma": (
            RGB_QKV_GAUSSIAN_SIGMA
            if RGB_QKV_CENTERED_REDUCTION == "gaussian-tiled"
            else None
        ),
        "asset_bytes": sum(path.stat().st_size for path in OUT.glob("*.png")),
    }
    (OUT / "reference.json").write_text(json.dumps(output_reference, indent=2) + "\n")
    print(json.dumps(output_reference, indent=2)[:2000])


if __name__ == "__main__":
    main()
