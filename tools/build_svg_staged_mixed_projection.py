#!/usr/bin/env python3
"""Build QKV → attention → direct mixed-context projection as three SVG stages."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "SVG_MIXED_PROJECTION_SOURCE",
        ROOT / "experiments" / "svg-multitoken-attention-rgb-tile",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_MIXED_PROJECTION_OUT",
        ROOT / "experiments" / "svg-staged-mixed-projection",
    )
).resolve()
WIDTH = 768
HEADS = 12
HEAD_WIDTH = 64
CENTER = 128 / 255
TARGET_X = HEAD_WIDTH - 1
HEADROOM = float(os.environ.get("SVG_MIXED_CPROJ_HEADROOM", "1.02"))
PACK_MODE = os.environ.get("SVG_MIXED_CPROJ_PACK", "separate")
BLOCK_INDEX = int(os.environ.get("SVG_MIXED_PROJECTION_BLOCK", "0"))
if PACK_MODE not in {"separate", "rgb"}:
    raise ValueError("SVG_MIXED_CPROJ_PACK must be 'separate' or 'rgb'")


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


def split_markup(source: str, result: str) -> str:
    grid = np.linspace(0, 1, 256)
    positive = " ".join(
        f"{value:.8g}" for value in np.clip(2 * (grid - CENTER), 0, 1)
    )
    negative = " ".join(
        f"{value:.8g}" for value in np.clip(2 * (CENTER - grid), 0, 1)
    )
    return (
        f'<feComponentTransfer in="{source}" result="{result}">'
        f'<feFuncR type="table" tableValues="{positive}"/>'
        f'<feFuncG type="table" tableValues="{negative}"/>'
        '<feFuncB type="table" tableValues="0 0"/>'
        '<feFuncA type="identity"/></feComponentTransfer>'
    )


def filter_body(page: str, filter_id: str) -> str:
    marker = f'<filter id="{filter_id}"'
    marker_start = page.index(marker)
    start = page.index(">", marker_start) + 1
    end = page.index("</filter>", start)
    return page[start:end]


def route_channel(source_channel: int, target_channel: int) -> str:
    matrix = np.zeros((4, 5), dtype=np.float64)
    matrix[target_channel, source_channel] = 1
    matrix[3, 3] = 1
    return " ".join(f"{value:.8g}" for value in matrix.reshape(-1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("mixed-*.png"):
        stale.unlink()

    source_page = (SOURCE / "connected-qkv-staged.html").read_text()
    source_relative = os.path.relpath(SOURCE, OUT)
    qkv_body = filter_body(source_page, "qkv-stage").replace(
        'href="', f'href="{source_relative}/'
    )
    attention_body = filter_body(source_page, "attention-stage").replace(
        'href="', f'href="{source_relative}/'
    )
    reference = json.loads((SOURCE / "reference.json").read_text())
    expected_context = np.asarray(reference["expected_context"], dtype=np.float64)
    context_scales = np.asarray(reference["qkv_scales"], dtype=np.float64)[
        2 * WIDTH :
    ]
    projected_scales = np.asarray(reference["projected_scales"], dtype=np.float64)
    residual_scales = np.asarray(reference["residual_scales"], dtype=np.float64)
    expected_residual = np.asarray(reference["expected_residual"], dtype=np.float64)

    tensors = SafeTensors(MODEL_PATH)
    block_prefix = f"h.{BLOCK_INDEX}"
    weight = np.asarray(
        tensors.tensor(f"{block_prefix}.attn.c_proj.weight"), dtype=np.float64
    )
    bias = np.asarray(
        tensors.tensor(f"{block_prefix}.attn.c_proj.bias"), dtype=np.float64
    )
    projected = expected_context @ weight + bias
    residual_input = expected_residual - projected
    residual_input_scales = np.maximum(
        np.max(np.abs(residual_input), axis=0) * 1.08, 1e-6
    )
    effective_weight = weight.T * context_scales[None, :]
    normalized_context = expected_context[1] / context_scales

    center_css = f"{CENTER:.12g}"
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
    signed_to_common = (
        f".5 -.5 0 0 {center_css}  .5 -.5 0 0 {center_css}  "
        f".5 -.5 0 0 {center_css}  0 0 0 0 1"
    )
    kernel = " ".join("1" for _ in range(HEAD_WIDTH))
    primitives: list[str] = [
        '<feOffset in="SourceGraphic" y="1" width="768" height="1" '
        'result="mixed-context-row"/>',
        '<feOffset in="mixed-context-row" dy="-1" x="0" y="0" '
        'width="768" height="1" result="mixed-context-common"/>',
        split_markup("mixed-context-common", "mixed-context-signed"),
    ]
    bucket_debug: list[dict[str, object]] = []

    chunk_signed: list[str] = []
    chunk_common: list[str] = []
    for chunk_index, output_start in enumerate(range(0, WIDTH, HEAD_WIDTH)):
        output_stop = output_start + HEAD_WIDTH
        prefix = f"mixed-cproj-{chunk_index}"
        chunk_weight = effective_weight[output_start:output_stop]
        units = np.maximum(np.max(np.abs(chunk_weight), axis=1), 1e-12)
        normalized_weight = chunk_weight / units[:, None]
        scale_values = units / projected_scales[output_start:output_stop]
        log_scale = np.log2(np.maximum(scale_values, 1e-12))
        bucket_width = (
            2.0
            if chunk_index == 1
            else 5.0
            if chunk_index == 9
            else 4.0
            if chunk_index == 11
            else 3.0
        )
        bucket_ids = np.floor(
            (log_scale - np.min(log_scale)) / bucket_width
        ).astype(int)
        bucket_paths: list[tuple[str, str]] = []
        for bucket_id in np.unique(bucket_ids):
            mask = bucket_ids == bucket_id
            bucket_prefix = f"{prefix}-b{bucket_id}"
            bucket_weight = np.where(mask[:, None], normalized_weight, 0)
            partials = np.stack(
                [
                    bucket_weight[:, head * HEAD_WIDTH : (head + 1) * HEAD_WIDTH]
                    @ normalized_context[
                        head * HEAD_WIDTH : (head + 1) * HEAD_WIDTH
                    ]
                    for head in range(HEADS)
                ],
                axis=1,
            )
            bias_units = np.where(
                mask, bias[output_start:output_stop] / units, 0
            )
            cumulative = np.cumsum(partials, axis=1)
            rgb_group_partials = partials.reshape(HEAD_WIDTH, HEADS // 3, 3).sum(
                axis=2
            )
            divisor = max(
                float(np.max(np.abs(cumulative))),
                float(np.max(np.abs(cumulative[:, -1] + bias_units))),
                float(np.max(np.abs(rgb_group_partials)))
                if PACK_MODE == "rgb"
                else 0.0,
                1e-12,
            ) * HEADROOM
            accumulation_factor = 1
            if PACK_MODE == "rgb":
                bucket_debug.append(
                    {
                        "chunk": chunk_index,
                        "bucket": int(bucket_id),
                        "divisor": divisor,
                        "mask": mask.tolist(),
                        "groupEncodedExpected": (
                            CENTER + rgb_group_partials / (2 * divisor)
                        ).tolist(),
                        "totalEncodedExpected": (
                            CENTER
                            + partials.sum(axis=1) / (2 * divisor)
                        ).tolist(),
                        "biasedEncodedExpected": (
                            CENTER
                            + (partials.sum(axis=1) + bias_units)
                            / (2 * divisor)
                        ).tolist(),
                        "accumulationFactor": HEADS // 3,
                    }
                )
            magnitude = 0.0
            for head in range(HEADS):
                start = head * HEAD_WIDTH
                stop = start + HEAD_WIDTH
                products = (
                    bucket_weight[:, start:stop]
                    * normalized_context[None, start:stop]
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
            positive_channels_matrix = (
                f"{coefficient} {coefficient} {coefficient} 0 0  "
                "0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
            )
            negative_channels_matrix = (
                "0 0 0 0 0  "
                f"{coefficient} {coefficient} {coefficient} 0 0  "
                "0 0 0 0 0  0 0 0 0 1"
            )
            encoded_parts: list[str] = []
            if PACK_MODE == "rgb":
                for group_index, first_head in enumerate(range(0, HEADS, 3)):
                    name = f"{bucket_prefix}-g{group_index}"
                    positive_inputs: list[str] = []
                    negative_inputs: list[str] = []
                    weight_channels: list[np.ndarray] = []
                    for channel, head in enumerate(range(first_head, first_head + 3)):
                        start = head * HEAD_WIDTH
                        stop = start + HEAD_WIDTH
                        head_name = f"{name}-h{head}"
                        weight_channels.append(bucket_weight[:, start:stop])
                        primitives.extend(
                            (
                                f'<feOffset in="mixed-context-signed" '
                                f'x="{start}" y="0" width="{HEAD_WIDTH}" '
                                f'height="1" result="{head_name}-crop"/>',
                                f'<feOffset in="{head_name}-crop" dx="-{start}" '
                                f'dy="{output_start}" x="0" y="{output_start}" '
                                f'width="{HEAD_WIDTH}" height="1" '
                                f'result="{head_name}-row"/>',
                                f'<feTile in="{head_name}-row" x="0" '
                                f'y="{output_start}" width="{HEAD_WIDTH}" '
                                f'height="{HEAD_WIDTH}" '
                                f'result="{head_name}-values"/>',
                                f'<feColorMatrix in="{head_name}-values" '
                                f'values="{route_channel(0, channel)}" '
                                f'result="{head_name}-positive"/>',
                                f'<feColorMatrix in="{head_name}-values" '
                                f'values="{route_channel(1, channel)}" '
                                f'result="{head_name}-negative"/>',
                            )
                        )
                        positive_inputs.append(f"{head_name}-positive")
                        negative_inputs.append(f"{head_name}-negative")

                    positive_input = positive_inputs[0]
                    negative_input = negative_inputs[0]
                    for channel in range(1, 3):
                        next_positive = f"{name}-input-positive-{channel}"
                        next_negative = f"{name}-input-negative-{channel}"
                        primitives.extend(
                            (
                                f'<feComposite in="{positive_input}" '
                                f'in2="{positive_inputs[channel]}" '
                                f'operator="arithmetic" k1="0" k2="1" '
                                f'k3="1" k4="0" result="{next_positive}"/>',
                                f'<feComposite in="{negative_input}" '
                                f'in2="{negative_inputs[channel]}" '
                                f'operator="arithmetic" k1="0" k2="1" '
                                f'k3="1" k4="0" result="{next_negative}"/>',
                            )
                        )
                        positive_input = next_positive
                        negative_input = next_negative

                    packed_weights = np.stack(weight_channels, axis=-1)
                    save_rgb(
                        OUT / f"{name}-weights-positive.png",
                        np.maximum(packed_weights, 0),
                    )
                    save_rgb(
                        OUT / f"{name}-weights-negative.png",
                        np.maximum(-packed_weights, 0),
                    )
                    primitives.extend(
                        (
                            f'<feImage href="{name}-weights-positive.png" '
                            f'x="0" y="{output_start}" width="{HEAD_WIDTH}" '
                            f'height="{HEAD_WIDTH}" preserveAspectRatio="none" '
                            f'result="{name}-weights-positive"/>',
                            f'<feImage href="{name}-weights-negative.png" '
                            f'x="0" y="{output_start}" width="{HEAD_WIDTH}" '
                            f'height="{HEAD_WIDTH}" preserveAspectRatio="none" '
                            f'result="{name}-weights-negative"/>',
                            f'<feComposite in="{name}-weights-positive" '
                            f'in2="{positive_input}" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{name}-pp"/>',
                            f'<feComposite in="{name}-weights-negative" '
                            f'in2="{negative_input}" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{name}-nn"/>',
                            f'<feComposite in="{name}-weights-positive" '
                            f'in2="{negative_input}" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{name}-pn"/>',
                            f'<feComposite in="{name}-weights-negative" '
                            f'in2="{positive_input}" operator="arithmetic" '
                            f'k1="1" k2="0" k3="0" k4="0" '
                            f'result="{name}-np"/>',
                            f'<feComposite in="{name}-pp" in2="{name}-nn" '
                            f'operator="arithmetic" k1="0" k2="1" k3="1" '
                            f'k4="0" result="{name}-positive"/>',
                            f'<feComposite in="{name}-pn" in2="{name}-np" '
                            f'operator="arithmetic" k1="0" k2="1" k3="1" '
                            f'k4="0" result="{name}-negative"/>',
                            f'<feConvolveMatrix in="{name}-positive" '
                            f'order="64 1" kernelMatrix="{kernel}" '
                            f'divisor="{magnitude}" targetX="63" targetY="0" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="{TARGET_X}" '
                            f'y="{output_start}" width="1" height="64" '
                            f'result="{name}-positive-sum"/>',
                            f'<feConvolveMatrix in="{name}-negative" '
                            f'order="64 1" kernelMatrix="{kernel}" '
                            f'divisor="{magnitude}" targetX="63" targetY="0" '
                            f'edgeMode="none" kernelUnitLength="1 1" '
                            f'preserveAlpha="true" x="{TARGET_X}" '
                            f'y="{output_start}" width="1" height="64" '
                            f'result="{name}-negative-sum"/>',
                            f'<feColorMatrix in="{name}-positive-sum" '
                            f'values="{positive_channels_matrix}" '
                            f'result="{name}-positive-routed"/>',
                            f'<feColorMatrix in="{name}-negative-sum" '
                            f'values="{negative_channels_matrix}" '
                            f'result="{name}-negative-routed"/>',
                            f'<feComposite in="{name}-positive-routed" '
                            f'in2="{name}-negative-routed" '
                            f'operator="arithmetic" k1="0" k2="1" k3="1" '
                            f'k4="0" result="{name}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{name}-encoded")
            else:
                for head in range(HEADS):
                    start = head * HEAD_WIDTH
                    stop = start + HEAD_WIDTH
                    name = f"{bucket_prefix}-h{head}"
                    weight_image = bucket_weight[:, start:stop]
                    save_rg(
                        OUT / f"{name}-weights.png",
                        np.maximum(weight_image, 0),
                        np.maximum(-weight_image, 0),
                    )
                    primitives.extend(
                        (
                            f'<feOffset in="mixed-context-signed" x="{start}" y="0" '
                            f'width="{HEAD_WIDTH}" height="1" result="{name}-crop"/>',
                            f'<feOffset in="{name}-crop" dx="-{start}" '
                            f'dy="{output_start}" x="0" y="{output_start}" '
                            f'width="{HEAD_WIDTH}" height="1" '
                            f'result="{name}-row"/>',
                            f'<feTile in="{name}-row" x="0" y="{output_start}" '
                            f'width="{HEAD_WIDTH}" height="{HEAD_WIDTH}" '
                            f'result="{name}-values"/>',
                            f'<feColorMatrix in="{name}-values" values="{swap_rg}" '
                            f'result="{name}-swapped"/>',
                            f'<feImage href="{name}-weights.png" x="0" '
                            f'y="{output_start}" width="{HEAD_WIDTH}" '
                            f'height="{HEAD_WIDTH}" preserveAspectRatio="none" '
                            f'result="{name}-weights"/>',
                            f'<feComposite in="{name}-weights" in2="{name}-values" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{name}-same"/>',
                            f'<feComposite in="{name}-weights" in2="{name}-swapped" '
                            f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                            f'result="{name}-cross"/>',
                            f'<feColorMatrix in="{name}-same" '
                            f'values="{positive_matrix}" result="{name}-positive"/>',
                            f'<feColorMatrix in="{name}-cross" '
                            f'values="{negative_matrix}" result="{name}-negative"/>',
                            f'<feComposite in="{name}-positive" '
                            f'in2="{name}-negative" operator="arithmetic" '
                            f'k1="0" k2="1" k3="1" k4="0" '
                            f'result="{name}-product"/>',
                            f'<feConvolveMatrix in="{name}-product" order="64 1" '
                            f'kernelMatrix="{kernel}" divisor="{magnitude}" '
                            f'targetX="63" targetY="0" edgeMode="none" '
                            f'kernelUnitLength="1 1" preserveAlpha="true" '
                            f'x="{TARGET_X}" y="{output_start}" width="1" '
                            f'height="{HEAD_WIDTH}" result="{name}-sum"/>',
                            f'<feColorMatrix in="{name}-sum" '
                            f'values="{encoded_matrix}" result="{name}-encoded"/>',
                        )
                    )
                    encoded_parts.append(f"{name}-encoded")
            if PACK_MODE == "rgb":
                first_pair = f"{bucket_prefix}-average01"
                second_pair = f"{bucket_prefix}-average23"
                averaged = f"{bucket_prefix}-average-all"
                total = f"{bucket_prefix}-total"
                primitives.extend(
                    (
                        f'<feComposite in="{encoded_parts[0]}" '
                        f'in2="{encoded_parts[1]}" operator="arithmetic" '
                        f'k1="0" k2=".5" k3=".5" k4="0" '
                        f'result="{first_pair}"/>',
                        f'<feComposite in="{encoded_parts[2]}" '
                        f'in2="{encoded_parts[3]}" operator="arithmetic" '
                        f'k1="0" k2=".5" k3=".5" k4="0" '
                        f'result="{second_pair}"/>',
                        f'<feComposite in="{first_pair}" in2="{second_pair}" '
                        f'operator="arithmetic" k1="0" k2=".5" k3=".5" '
                        f'k4="0" result="{averaged}"/>',
                        f'<feColorMatrix in="{averaged}" values="'
                        f'{HEADS // 3} -{HEADS // 3} 0 0 {center_css}  '
                        f'{HEADS // 3} -{HEADS // 3} 0 0 {center_css}  '
                        f'{HEADS // 3} -{HEADS // 3} 0 0 {center_css}  '
                        f'0 0 0 0 1" result="{total}"/>',
                    )
                )
            else:
                total = encoded_parts[0]
                for head, encoded in enumerate(encoded_parts[1:], 1):
                    result = f"{bucket_prefix}-total{head}"
                    primitives.append(
                        f'<feComposite in="{total}" in2="{encoded}" '
                        f'operator="arithmetic" k1="0" k2="1" k3="1" '
                        f'k4="-{center_css}" result="{result}"/>'
                    )
                    total = result
            save_gray(
                OUT / f"{bucket_prefix}-bias.png",
                (
                    CENTER
                    + 0.5 * bias_units / (divisor * accumulation_factor)
                ).reshape(HEAD_WIDTH, 1),
            )
            bucket_scale = np.where(mask, scale_values, 0)
            max_scale = float(np.max(bucket_scale))
            save_gray(
                OUT / f"{bucket_prefix}-scale.png",
                (bucket_scale / max_scale).reshape(HEAD_WIDTH, 1),
            )
            primitives.extend(
                (
                    f'<feImage href="{bucket_prefix}-bias.png" x="{TARGET_X}" '
                    f'y="{output_start}" width="1" height="{HEAD_WIDTH}" '
                    f'preserveAspectRatio="none" result="{bucket_prefix}-bias"/>',
                    f'<feComposite in="{total}" in2="{bucket_prefix}-bias" '
                    f'operator="arithmetic" k1="0" k2="1" k3="1" '
                    f'k4="-{center_css}" result="{bucket_prefix}-biased"/>',
                    split_markup(f"{bucket_prefix}-biased", f"{bucket_prefix}-signed"),
                    f'<feImage href="{bucket_prefix}-scale.png" x="{TARGET_X}" '
                    f'y="{output_start}" width="1" height="{HEAD_WIDTH}" '
                    f'preserveAspectRatio="none" result="{bucket_prefix}-scale"/>',
                    f'<feComposite in="{bucket_prefix}-signed" '
                    f'in2="{bucket_prefix}-scale" operator="arithmetic" '
                    f'k1="{divisor * accumulation_factor * max_scale}" '
                    f'k2="0" k3="0" k4="0" '
                    f'result="{bucket_prefix}-scaled"/>',
                    f'<feColorMatrix in="{bucket_prefix}-scaled" '
                    f'values="{signed_to_common}" result="{bucket_prefix}-common"/>',
                )
            )
            bucket_paths.append(
                (f"{bucket_prefix}-common", f"{bucket_prefix}-scaled")
            )

        common, signed = bucket_paths[0]
        for bucket_index, (next_common, next_signed) in enumerate(
            bucket_paths[1:], 1
        ):
            common_result = f"{prefix}-common-total{bucket_index}"
            signed_result = f"{prefix}-signed-total{bucket_index}"
            primitives.extend(
                (
                    f'<feComposite in="{common}" in2="{next_common}" '
                    f'operator="arithmetic" k1="0" k2="1" k3="1" '
                    f'k4="-{center_css}" result="{common_result}"/>',
                    f'<feComposite in="{signed}" in2="{next_signed}" '
                    f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                    f'result="{signed_result}"/>',
                )
            )
            common, signed = common_result, signed_result
        primitives.extend(
            (
                f'<feOffset in="{common}" result="{prefix}-common"/>',
                f'<feOffset in="{signed}" result="{prefix}-scaled"/>',
            )
        )
        chunk_common.append(f"{prefix}-common")
        chunk_signed.append(f"{prefix}-scaled")

    save_gray(
        OUT / "mixed-residual-input.png",
        (CENTER + residual_input[1] / (2 * residual_input_scales)).reshape(WIDTH, 1),
    )
    primitives.extend(
        (
            '<feImage href="mixed-residual-input.png" x="63" y="0" '
            'width="1" height="768" preserveAspectRatio="none" '
            'result="mixed-residual-input"/>',
            split_markup("mixed-residual-input", "mixed-residual-input-signed"),
        )
    )
    residual_outputs: list[str] = []
    projected_ratio = projected_scales / residual_scales
    input_ratio = residual_input_scales / residual_scales
    for chunk_index, output_start in enumerate(range(0, WIDTH, HEAD_WIDTH)):
        prefix = f"mixed-residual-{chunk_index}"
        projected_chunk = chunk_signed[chunk_index]
        projected_values = projected_ratio[output_start : output_start + HEAD_WIDTH]
        input_values = input_ratio[output_start : output_start + HEAD_WIDTH]
        projected_max = float(np.max(projected_values))
        input_max = float(np.max(input_values))
        save_gray(
            OUT / f"{prefix}-projected-ratio.png",
            (projected_values / projected_max).reshape(HEAD_WIDTH, 1),
        )
        save_gray(
            OUT / f"{prefix}-input-ratio.png",
            (input_values / input_max).reshape(HEAD_WIDTH, 1),
        )
        primitives.extend(
            (
                f'<feImage href="{prefix}-projected-ratio.png" x="63" '
                f'y="{output_start}" width="1" height="64" '
                f'preserveAspectRatio="none" result="{prefix}-projected-ratio"/>',
                f'<feComposite in="{projected_chunk}" '
                f'in2="{prefix}-projected-ratio" operator="arithmetic" '
                f'k1="{projected_max}" k2="0" k3="0" k4="0" '
                f'x="63" y="{output_start}" width="1" height="64" '
                f'result="{prefix}-projected"/>',
                f'<feOffset in="mixed-residual-input-signed" x="63" '
                f'y="{output_start}" width="1" height="64" '
                f'result="{prefix}-input-raw"/>',
                f'<feImage href="{prefix}-input-ratio.png" x="63" '
                f'y="{output_start}" width="1" height="64" '
                f'preserveAspectRatio="none" result="{prefix}-input-ratio"/>',
                f'<feComposite in="{prefix}-input-raw" '
                f'in2="{prefix}-input-ratio" operator="arithmetic" '
                f'k1="{input_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-input"/>',
                f'<feComposite in="{prefix}-projected" in2="{prefix}-input" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'x="63" y="{output_start}" width="1" height="64" '
                f'result="{prefix}-signed"/>',
                f'<feColorMatrix in="{prefix}-signed" '
                f'values="{signed_to_common}" result="{prefix}-common"/>',
            )
        )
        residual_outputs.append(f"{prefix}-common")
    primitives.append(
        '<feMerge>'
        + "".join(f'<feMergeNode in="{name}"/>' for name in residual_outputs)
        + '</feMerge>'
    )

    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Three-stage mixed-context attention projection</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="63 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="qkv-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">{qkv_body}</filter>'
        '<filter id="attention-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">{attention_body}</filter>'
        '<filter id="projection-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="2304" '
        f'height="768" color-interpolation-filters="sRGB">'
        f'{"".join(primitives)}</filter></defs>'
        '<g filter="url(#projection-stage)">'
        '<g filter="url(#attention-stage)">'
        '<rect width="2304" height="768" fill="white" '
        'filter="url(#qkv-stage)"/></g></g></svg>'
    )
    (OUT / "index.html").write_text(html)
    payload = {
        "blockIndex": BLOCK_INDEX,
        "width": WIDTH,
        "surfaceCenter": CENTER,
        "residualScales": residual_scales.tolist(),
        "expectedResidual": expected_residual[1].tolist(),
        "projectedScales": projected_scales.tolist(),
        "expectedProjected": projected[1].tolist(),
        "htmlBytes": len(html.encode()),
        "projectionMarkupFragmentCount": len(primitives),
        "projectionPrimitiveCount": sum(
            primitive.count("<fe") for primitive in primitives
        ),
        "packMode": PACK_MODE,
        "headroom": HEADROOM,
        "bucketDebug": bucket_debug,
        "source": str(SOURCE),
    }
    (OUT / "reference.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({
        "htmlBytes": payload["htmlBytes"],
        "projectionPrimitiveCount": payload["projectionPrimitiveCount"],
        "projectionMarkupFragmentCount": payload["projectionMarkupFragmentCount"],
        "packMode": payload["packMode"],
        "headroom": payload["headroom"],
    }, indent=2))


if __name__ == "__main__":
    main()
