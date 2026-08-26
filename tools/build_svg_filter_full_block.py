#!/usr/bin/env python3
"""Build one connected no-JS SVG-filter GPT-2-small transformer block."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import (
    EPSILON,
    QUANT_BITS,
    final_layer_norm_data,
    gelu_new,
    layer_norm,
    model_data,
)
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(
    os.environ.get(
        "SVG_FILTER_OUT", ROOT / "experiments" / "svg-filter-full-block"
    )
).resolve()
WIDTH = 768
HIDDEN = 3072
SHARD = 256
CENTER = 128 / 255
CX = SHARD - 1
CY = SHARD - 1
OUTLIER_DIMS = (138, 378, 447, 481)
FILTER_COLOR = os.environ.get("SVG_FILTER_COLOR", "sRGB")


def encode_surface(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0, 1)
    if FILTER_COLOR != "linearRGB":
        return values
    return np.where(
        values <= 0.0031308,
        values * 12.92,
        1.055 * np.power(values, 1 / 2.4) - 0.055,
    )


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(np.rint(encode_surface(values) * 255).astype(np.uint8), mode="L").save(
        path, optimize=True
    )


def save_rg(path: Path, positive: np.ndarray, negative: np.ndarray) -> None:
    rgba = np.zeros((*positive.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(encode_surface(positive) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(encode_surface(negative) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_grouped_rg(path: Path, normal: np.ndarray, outlier: np.ndarray) -> None:
    rgba = np.zeros((*normal.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(encode_surface(normal) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(encode_surface(outlier) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def calibration_absmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return np.abs(values) if values.ndim == 1 else np.max(np.abs(values), axis=0)


def calibration_affine(
    values: np.ndarray, weights: np.ndarray, bias: np.ndarray
) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return (
        weights @ values + bias
        if values.ndim == 1
        else values @ weights.T + bias
    )


def calibration_layer_norm(
    values: np.ndarray, gamma: np.ndarray, beta: np.ndarray
) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim == 1:
        return layer_norm(values, gamma, beta)
    return np.stack([layer_norm(value, gamma, beta) for value in values])


def main(helper_sink: dict | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    center_css = f"{CENTER:.12g}"
    kernel = " ".join("1" for _ in range(SHARD))
    copy_red = "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
    to_red = "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    to_green = "0 0 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    positive_matrix = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_matrix = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    swap_rg = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    signed_to_common = (
        f".5 -.5 0 0 {center_css}  .5 -.5 0 0 {center_css}  "
        f".5 -.5 0 0 {center_css}  0 0 0 0 1"
    )
    primitives: list[str] = []

    def geometry(orientation: str, length: int) -> tuple[int, int, int, int]:
        return (0, CY, length, 1) if orientation == "h" else (CX, 0, 1, length)

    def split_markup(source: str, result: str) -> str:
        t = np.linspace(0, 1, 256)
        positive = " ".join(f"{v:.8g}" for v in np.clip(2 * (t - CENTER), 0, 1))
        negative = " ".join(f"{v:.8g}" for v in np.clip(2 * (CENTER - t), 0, 1))
        return (
            f'<feComponentTransfer in="{source}" result="{result}">'
            f'<feFuncR type="table" tableValues="{positive}"/>'
            f'<feFuncG type="table" tableValues="{negative}"/>'
            '<feFuncB type="table" tableValues="0 0"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )

    def split_signed(source: str, prefix: str) -> str:
        result = f"{prefix}-signed"
        primitives.append(split_markup(source, result))
        return result

    def reduce_vector(
        source: str,
        prefix: str,
        orientation: str,
        length: int,
        scale: float = 1.0,
        centered: bool = False,
    ) -> str:
        parts: list[str] = []
        bias = CENTER * (1 - scale) if centered else 0.0
        for shard, start in enumerate(range(0, length, SHARD)):
            chunk = f"{prefix}-chunk{shard}"
            part = f"{prefix}-part{shard}"
            if orientation == "h":
                primitives.extend(
                    (
                        f'<feOffset in="{source}" dx="-{start}" dy="-{CY}" '
                        f'x="0" y="0" width="{SHARD}" height="1" result="{chunk}"/>',
                        f'<feConvolveMatrix in="{chunk}" order="{SHARD} 1" '
                        f'kernelMatrix="{kernel}" divisor="{SHARD / scale}" targetX="{CX}" '
                        f'targetY="0" bias="{bias}" edgeMode="none" kernelUnitLength="1 1" '
                        f'preserveAlpha="true" x="{CX}" y="0" width="1" height="1" '
                        f'result="{part}"/>',
                    )
                )
            else:
                primitives.extend(
                    (
                        f'<feOffset in="{source}" dx="-{CX}" dy="-{start}" '
                        f'x="0" y="0" width="1" height="{SHARD}" result="{chunk}"/>',
                        f'<feConvolveMatrix in="{chunk}" order="1 {SHARD}" '
                        f'kernelMatrix="{kernel}" divisor="{SHARD / scale}" targetX="0" '
                        f'targetY="{CY}" bias="{bias}" edgeMode="none" kernelUnitLength="1 1" '
                        f'preserveAlpha="true" x="0" y="{CY}" width="1" height="1" '
                        f'result="{part}"/>',
                    )
                )
            parts.append(part)
        count = len(parts)
        acc = f"{prefix}-acc0"
        primitives.append(
            f'<feComposite in="{parts[0]}" in2="{parts[0]}" operator="arithmetic" '
            f'k1="0" k2="{1 / count}" k3="0" k4="0" result="{acc}"/>'
        )
        for index, part in enumerate(parts[1:], 1):
            result = f"{prefix}-acc{index}"
            primitives.append(
                f'<feComposite in="{acc}" in2="{part}" operator="arithmetic" '
                f'k1="0" k2="1" k3="{1 / count}" k4="0" result="{result}"/>'
            )
            acc = result
        return acc

    def tile_scalar(source: str, prefix: str, orientation: str, length: int) -> str:
        origin = f"{prefix}-origin"
        tiled = f"{prefix}-tiled"
        if orientation == "h":
            primitives.extend(
                (
                    f'<feOffset in="{source}" dx="-{CX}" dy="0" x="0" y="0" '
                    f'width="1" height="1" result="{origin}"/>',
                    f'<feTile in="{origin}" x="0" y="{CY}" width="{length}" height="1" '
                    f'result="{tiled}"/>',
                )
            )
        else:
            primitives.extend(
                (
                    f'<feOffset in="{source}" dx="0" dy="-{CY}" x="0" y="0" '
                    f'width="1" height="1" result="{origin}"/>',
                    f'<feTile in="{origin}" x="{CX}" y="0" width="1" height="{length}" '
                    f'result="{tiled}"/>',
                )
            )
        return tiled

    def layernorm_stage(
        source: str,
        vector: np.ndarray,
        input_range: float,
        gamma: np.ndarray,
        beta: np.ndarray,
        orientation: str,
        prefix: str,
        calibration_vector: np.ndarray | None = None,
    ) -> tuple[str, str, np.ndarray, float]:
        expected = layer_norm(vector, gamma, beta)
        calibration = vector if calibration_vector is None else calibration_vector
        calibration_expected = layer_norm(calibration, gamma, beta)
        mean = float(np.mean(vector))
        diff = vector - mean
        calibration_diff = calibration - float(np.mean(calibration))
        diff_range = float(
            max(np.max(np.abs(diff)), np.max(np.abs(calibration_diff))) * 1.02
        )
        normalized = diff / np.sqrt(np.mean(diff**2) + EPSILON)
        calibration_normalized = calibration_diff / np.sqrt(
            np.mean(calibration_diff**2) + EPSILON
        )
        normalized_range = float(
            max(
                np.max(np.abs(normalized)),
                np.max(np.abs(calibration_normalized)),
            )
            * 1.02
        )
        output_range = float(
            max(np.max(np.abs(expected)), np.max(np.abs(calibration_expected))) * 1.05
        )
        x, y, width, height = geometry(orientation, WIDTH)
        normalized_input = vector / input_range
        calibration_input = calibration / input_range
        shard_means = [
            max(
                abs(float(np.mean(normalized_input[start : start + SHARD]))),
                abs(float(np.mean(calibration_input[start : start + SHARD]))),
            )
            for start in range(0, WIDTH, SHARD)
        ]
        mean_scale = min(64.0, 0.9 / max(max(shard_means), 1e-12))
        mean_scalar = reduce_vector(
            source,
            f"{prefix}-mean",
            orientation,
            WIDTH,
            scale=mean_scale,
            centered=True,
        )
        mean_tiled = tile_scalar(mean_scalar, f"{prefix}-mean", orientation, WIDTH)
        primitives.extend(
            (
                f'<feColorMatrix in="{source}" values="{to_red}" result="{prefix}-input-red"/>',
                f'<feColorMatrix in="{mean_tiled}" values="{to_green}" '
                f'result="{prefix}-mean-green"/>',
                f'<feComposite in="{prefix}-input-red" in2="{prefix}-mean-green" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-split"/>',
            )
        )
        coef = input_range / diff_range
        mean_coef = coef / mean_scale
        diff_offset = CENTER - coef * CENTER + mean_coef * CENTER
        diff_matrix = (
            f"{coef} -{mean_coef} 0 0 {diff_offset}  " * 3
            + "0 0 0 0 1"
        )
        primitives.extend(
            (
                f'<feColorMatrix in="{prefix}-split" values="{diff_matrix}" '
                f'result="{prefix}-diff"/>',
                f'<feComposite in="{prefix}-diff" in2="{prefix}-diff" '
                f'operator="arithmetic" k1="4" k2="{-4 * CENTER}" '
                f'k3="{-4 * CENTER}" k4="{4 * CENTER * CENTER}" '
                f'result="{prefix}-square-alpha"/>',
                f'<feColorMatrix in="{prefix}-square-alpha" values="{copy_red}" '
                f'result="{prefix}-square"/>',
            )
        )
        normalized_square = (diff / diff_range) ** 2
        calibration_square = (calibration_diff / diff_range) ** 2
        square_shard_means = [
            max(
                float(np.mean(normalized_square[start : start + SHARD])),
                float(np.mean(calibration_square[start : start + SHARD])),
            )
            for start in range(0, WIDTH, SHARD)
        ]
        variance_scale = min(64.0, 0.9 / max(square_shard_means))
        variance = reduce_vector(
            f"{prefix}-square",
            f"{prefix}-variance",
            orientation,
            WIDTH,
            scale=variance_scale,
        )
        grid = np.linspace(0, 1, 256)
        gain = np.clip(
            1
            / (
                np.sqrt(grid / variance_scale + EPSILON / diff_range**2)
                * normalized_range
            ),
            0,
            1,
        )
        gain_values = " ".join(f"{v:.8g}" for v in gain)
        primitives.append(
            f'<feComponentTransfer in="{variance}" result="{prefix}-gain-scalar">'
            f'<feFuncR type="table" tableValues="{gain_values}"/>'
            f'<feFuncG type="table" tableValues="{gain_values}"/>'
            f'<feFuncB type="table" tableValues="{gain_values}"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )
        gain_tiled = tile_scalar(
            f"{prefix}-gain-scalar", f"{prefix}-gain", orientation, WIDTH
        )
        gamma_max = float(np.max(gamma))
        save_gray(OUT / f"{prefix}-gamma.png", (gamma / gamma_max).reshape(height, width))
        save_gray(
            OUT / f"{prefix}-beta.png",
            (CENTER + beta / (2 * output_range)).reshape(height, width),
        )
        gamma_coef = gamma_max * normalized_range / output_range
        primitives.extend(
            (
                f'<feComposite in="{prefix}-diff" in2="{gain_tiled}" '
                f'operator="arithmetic" k1="1" k2="0" k3="-{center_css}" '
                f'k4="{center_css}" result="{prefix}-normalized"/>',
                f'<feImage href="{prefix}-gamma.png" x="{x}" y="{y}" width="{width}" '
                f'height="{height}" preserveAspectRatio="none" result="{prefix}-gamma"/>',
                f'<feComposite in="{prefix}-normalized" in2="{prefix}-gamma" '
                f'operator="arithmetic" k1="{gamma_coef}" k2="0" '
                f'k3="{-gamma_coef * CENTER}" k4="{center_css}" '
                f'result="{prefix}-scaled"/>',
                f'<feImage href="{prefix}-beta.png" x="{x}" y="{y}" width="{width}" '
                f'height="{height}" preserveAspectRatio="none" result="{prefix}-beta"/>',
                f'<feComposite in="{prefix}-scaled" in2="{prefix}-beta" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="-{center_css}" result="{prefix}-out"/>',
            )
        )
        signed = split_signed(f"{prefix}-out", prefix)
        return f"{prefix}-out", signed, expected, output_range

    def grouped_layernorm_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        normal_range: float,
        outlier_range: float,
        gamma: np.ndarray,
        beta: np.ndarray,
        orientation: str,
        prefix: str,
    ) -> tuple[str, np.ndarray, float]:
        """Layer-normalize an RG residual with dense and outlier scales."""
        output = layer_norm(vector, gamma, beta)
        calibration_output = layer_norm(calibration_vector, gamma, beta)
        vector_diff = vector - float(np.mean(vector))
        calibration_vector_diff = calibration_vector - float(
            np.mean(calibration_vector)
        )
        normalized_vector = vector_diff / np.sqrt(
            np.mean(vector_diff**2) + EPSILON
        )
        calibration_normalized_vector = calibration_vector_diff / np.sqrt(
            np.mean(calibration_vector_diff**2) + EPSILON
        )
        normalized_range = float(
            max(
                np.max(np.abs(normalized_vector)),
                np.max(np.abs(calibration_normalized_vector)),
            )
            * 1.02
        )
        output_range = float(
            max(np.max(np.abs(output)), np.max(np.abs(calibration_output))) * 1.05
        )
        mask = np.zeros(WIDTH, dtype=bool)
        mask[list(OUTLIER_DIMS)] = True
        normal_mask = ~mask
        x, y, width, height = geometry(orientation, WIDTH)
        mask_shape = (height, width)
        save_gray(OUT / f"{prefix}-normal-mask.png", normal_mask.reshape(mask_shape))
        save_gray(OUT / f"{prefix}-outlier-mask.png", mask.reshape(mask_shape))
        copy_green = "0 1 0 0 0  " * 3 + "0 0 0 0 1"
        primitives.extend(
            (
                f'<feColorMatrix in="{source}" values="{copy_red}" '
                f'result="{prefix}-normal-source"/>',
                f'<feColorMatrix in="{source}" values="{copy_green}" '
                f'result="{prefix}-outlier-source"/>',
            )
        )

        normal_values = np.where(normal_mask, vector / normal_range, 0.0)
        outlier_values = np.where(mask, vector / outlier_range, 0.0)
        calibration_normal = np.where(
            normal_mask, calibration_vector / normal_range, 0.0
        )
        calibration_outlier = np.where(
            mask, calibration_vector / outlier_range, 0.0
        )

        def reduction_scale(values: np.ndarray, alternate: np.ndarray) -> float:
            shard_means = [
                max(
                    abs(float(np.mean(values[start : start + SHARD]))),
                    abs(float(np.mean(alternate[start : start + SHARD]))),
                )
                for start in range(0, WIDTH, SHARD)
            ]
            return min(128.0, 0.9 / max(max(shard_means), 1e-12))

        normal_mean_scale = reduction_scale(normal_values, calibration_normal)
        outlier_mean_scale = reduction_scale(outlier_values, calibration_outlier)
        normal_mean = reduce_vector(
            f"{prefix}-normal-source",
            f"{prefix}-normal-mean",
            orientation,
            WIDTH,
            scale=normal_mean_scale,
            centered=True,
        )
        outlier_mean = reduce_vector(
            f"{prefix}-outlier-source",
            f"{prefix}-outlier-mean",
            orientation,
            WIDTH,
            scale=outlier_mean_scale,
            centered=True,
        )
        mean = float(np.mean(vector))
        calibration_mean = float(np.mean(calibration_vector))
        mean_range = max(abs(mean), abs(calibration_mean), 1e-6) * 1.05
        normal_mean_coef = normal_range / (mean_range * normal_mean_scale)
        outlier_mean_coef = outlier_range / (
            mean_range * outlier_mean_scale
        )
        mean_matrix = (
            f"{normal_mean_coef} {outlier_mean_coef} 0 0 "
            f"{CENTER * (1 - normal_mean_coef - outlier_mean_coef)}  " * 3
            + "0 0 0 0 1"
        )
        primitives.extend(
            (
                f'<feColorMatrix in="{normal_mean}" values="{to_red}" '
                f'result="{prefix}-normal-mean-red"/>',
                f'<feColorMatrix in="{outlier_mean}" values="{to_green}" '
                f'result="{prefix}-outlier-mean-green"/>',
                f'<feComposite in="{prefix}-normal-mean-red" '
                f'in2="{prefix}-outlier-mean-green" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-mean-pair"/>',
                f'<feColorMatrix in="{prefix}-mean-pair" values="{mean_matrix}" '
                f'result="{prefix}-mean"/>',
            )
        )
        mean_tiled = tile_scalar(
            f"{prefix}-mean", f"{prefix}-mean", orientation, WIDTH
        )

        normal_diff = vector - mean
        calibration_normal_diff = calibration_vector - calibration_mean
        normal_diff_range = float(
            max(
                np.max(np.abs(normal_diff[normal_mask])),
                np.max(np.abs(calibration_normal_diff[normal_mask])),
            )
            * 1.03
        )
        outlier_diff_range = float(
            max(
                np.max(np.abs(normal_diff[mask])),
                np.max(np.abs(calibration_normal_diff[mask])),
            )
            * 1.03
        )

        def build_diff(
            group: str,
            source_name: str,
            source_range: float,
            diff_range: float,
        ) -> str:
            pair = f"{prefix}-{group}-diff-pair"
            raw = f"{prefix}-{group}-diff-raw"
            masked = f"{prefix}-{group}-diff"
            source_coef = source_range / diff_range
            mean_coef = mean_range / diff_range
            offset = CENTER * (1 - source_coef + mean_coef)
            matrix = (
                f"{source_coef} -{mean_coef} 0 0 {offset}  " * 3
                + "0 0 0 0 1"
            )
            primitives.extend(
                (
                    f'<feColorMatrix in="{source_name}" values="{to_red}" '
                    f'result="{prefix}-{group}-source-red"/>',
                    f'<feColorMatrix in="{mean_tiled}" values="{to_green}" '
                    f'result="{prefix}-{group}-mean-green"/>',
                    f'<feComposite in="{prefix}-{group}-source-red" '
                    f'in2="{prefix}-{group}-mean-green" operator="arithmetic" '
                    f'k1="0" k2="1" k3="1" k4="0" result="{pair}"/>',
                    f'<feColorMatrix in="{pair}" values="{matrix}" result="{raw}"/>',
                    f'<feImage href="{prefix}-{group}-mask.png" x="{x}" y="{y}" '
                    f'width="{width}" height="{height}" preserveAspectRatio="none" '
                    f'result="{prefix}-{group}-mask"/>',
                    f'<feComposite in="{raw}" in2="{prefix}-{group}-mask" '
                    f'operator="arithmetic" k1="1" k2="0" k3="-{CENTER}" '
                    f'k4="{CENTER}" result="{masked}"/>',
                )
            )
            return masked

        normal_diff_name = build_diff(
            "normal", f"{prefix}-normal-source", normal_range, normal_diff_range
        )
        outlier_diff_name = build_diff(
            "outlier",
            f"{prefix}-outlier-source",
            outlier_range,
            outlier_diff_range,
        )

        def square_and_reduce(
            group: str,
            diff_name: str,
            diff_values: np.ndarray,
            alternate_diff: np.ndarray,
            diff_range: float,
        ) -> tuple[str, float]:
            square = f"{prefix}-{group}-square"
            primitives.extend(
                (
                    f'<feComposite in="{diff_name}" in2="{diff_name}" '
                    f'operator="arithmetic" k1="4" k2="{-4 * CENTER}" '
                    f'k3="{-4 * CENTER}" k4="{4 * CENTER * CENTER}" '
                    f'result="{prefix}-{group}-square-alpha"/>',
                    f'<feColorMatrix in="{prefix}-{group}-square-alpha" '
                    f'values="{copy_red}" result="{square}"/>',
                )
            )
            normalized_square = (diff_values / diff_range) ** 2
            alternate_square = (alternate_diff / diff_range) ** 2
            scale = reduction_scale(normalized_square, alternate_square)
            reduced = reduce_vector(
                square,
                f"{prefix}-{group}-variance",
                orientation,
                WIDTH,
                scale=scale,
            )
            return reduced, scale

        normal_reduced, normal_variance_scale = square_and_reduce(
            "normal",
            normal_diff_name,
            np.where(normal_mask, normal_diff, 0.0),
            np.where(normal_mask, calibration_normal_diff, 0.0),
            normal_diff_range,
        )
        outlier_reduced, outlier_variance_scale = square_and_reduce(
            "outlier",
            outlier_diff_name,
            np.where(mask, normal_diff, 0.0),
            np.where(mask, calibration_normal_diff, 0.0),
            outlier_diff_range,
        )
        variance = float(np.mean(normal_diff**2))
        calibration_variance = float(np.mean(calibration_normal_diff**2))
        variance_range = max(variance, calibration_variance) * 1.05
        normal_variance_coef = normal_diff_range**2 / (
            variance_range * normal_variance_scale
        )
        outlier_variance_coef = outlier_diff_range**2 / (
            variance_range * outlier_variance_scale
        )
        variance_matrix = (
            f"{normal_variance_coef} {outlier_variance_coef} 0 0 0  " * 3
            + "0 0 0 0 1"
        )
        primitives.extend(
            (
                f'<feColorMatrix in="{normal_reduced}" values="{to_red}" '
                f'result="{prefix}-normal-variance-red"/>',
                f'<feColorMatrix in="{outlier_reduced}" values="{to_green}" '
                f'result="{prefix}-outlier-variance-green"/>',
                f'<feComposite in="{prefix}-normal-variance-red" '
                f'in2="{prefix}-outlier-variance-green" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-variance-pair"/>',
                f'<feColorMatrix in="{prefix}-variance-pair" '
                f'values="{variance_matrix}" result="{prefix}-variance"/>',
            )
        )

        grid = np.linspace(0, 1, 256)

        def normalize_group(group: str, diff_name: str, diff_range: float) -> str:
            raw_factor = diff_range / (
                np.sqrt(grid * variance_range + EPSILON) * normalized_range
            )
            gain_scale = max(
                1.0,
                diff_range
                / (
                    np.sqrt(min(variance, calibration_variance) + EPSILON)
                    * normalized_range
                )
                * 1.05,
            )
            factor = np.clip(
                raw_factor / gain_scale,
                0,
                1,
            )
            table = " ".join(f"{value:.8g}" for value in factor)
            scalar = f"{prefix}-{group}-gain-scalar"
            primitives.append(
                f'<feComponentTransfer in="{prefix}-variance" result="{scalar}">'
                f'<feFuncR type="table" tableValues="{table}"/>'
                f'<feFuncG type="table" tableValues="{table}"/>'
                f'<feFuncB type="table" tableValues="{table}"/>'
                '<feFuncA type="identity"/></feComponentTransfer>'
            )
            tiled = tile_scalar(
                scalar, f"{prefix}-{group}-gain", orientation, WIDTH
            )
            signed = split_signed(diff_name, f"{prefix}-{group}-diff")
            result = f"{prefix}-{group}-normalized-signed"
            primitives.append(
                f'<feComposite in="{signed}" in2="{tiled}" '
                f'operator="arithmetic" k1="{gain_scale}" k2="0" k3="0" k4="0" '
                f'result="{result}"/>'
            )
            return result

        normal_signed = normalize_group(
            "normal", normal_diff_name, normal_diff_range
        )
        outlier_signed = normalize_group(
            "outlier", outlier_diff_name, outlier_diff_range
        )
        primitives.append(
            f'<feComposite in="{normal_signed}" in2="{outlier_signed}" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
            f'result="{prefix}-normalized-signed"/>'
        )
        gamma_max = float(np.max(np.abs(gamma)))
        affine_range = float(
            max(
                np.max(np.abs(normalized_vector * gamma)),
                np.max(np.abs(calibration_normalized_vector * gamma)),
            )
            * 1.05
        )
        gamma_coef = gamma_max * normalized_range / affine_range
        affine_coef = affine_range / output_range
        save_gray(
            OUT / f"{prefix}-gamma.png",
            (np.abs(gamma) / gamma_max).reshape(mask_shape),
        )
        save_gray(
            OUT / f"{prefix}-beta.png",
            (CENTER + beta / (2 * output_range)).reshape(mask_shape),
        )
        primitives.extend(
            (
                f'<feImage href="{prefix}-gamma.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-gamma"/>',
                f'<feComposite in="{prefix}-normalized-signed" '
                f'in2="{prefix}-gamma" operator="arithmetic" '
                f'k1="{gamma_coef}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-scaled-signed"/>',
                f'<feColorMatrix in="{prefix}-scaled-signed" '
                f'values="{signed_to_common}" result="{prefix}-scaled"/>',
                f'<feImage href="{prefix}-beta.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-beta"/>',
                f'<feComposite in="{prefix}-scaled" in2="{prefix}-beta" '
                f'operator="arithmetic" k1="0" k2="{affine_coef}" k3="1" '
                f'k4="{-CENTER * affine_coef}" result="{prefix}-out"/>',
            )
        )
        return f"{prefix}-out", output, output_range

    def grouped_ranges(
        vector: np.ndarray, calibration_vector: np.ndarray
    ) -> tuple[float, float]:
        mask = np.zeros(WIDTH, dtype=bool)
        mask[list(OUTLIER_DIMS)] = True
        normal_range = float(
            max(
                np.max(np.abs(vector[~mask])),
                np.max(np.abs(calibration_vector[~mask])),
                1e-6,
            )
            * 1.05
        )
        outlier_range = float(
            max(
                np.max(np.abs(vector[mask])),
                np.max(np.abs(calibration_vector[mask])),
                1e-6,
            )
            * 1.05
        )
        return normal_range, outlier_range

    def pack_grouped_planes(
        normal_source: str,
        outlier_source: str,
        prefix: str,
    ) -> str:
        red_only = (
            "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
        )
        red_to_green = (
            "0 0 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
        )
        result = f"{prefix}-grouped"
        primitives.extend(
            (
                f'<feColorMatrix in="{normal_source}" values="{red_only}" '
                f'result="{prefix}-normal-red"/>',
                f'<feColorMatrix in="{outlier_source}" values="{red_to_green}" '
                f'result="{prefix}-outlier-green"/>',
                f'<feComposite in="{prefix}-normal-red" '
                f'in2="{prefix}-outlier-green" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" result="{result}"/>',
            )
        )
        return result

    def add_to_grouped_stage(
        learned_source: str,
        learned_range: float,
        residual_grouped_source: str,
        residual_normal_range: float,
        residual_outlier_range: float,
        output_vector: np.ndarray,
        calibration_output: np.ndarray,
        orientation: str,
        prefix: str,
    ) -> tuple[str, float, float]:
        output_normal_range, output_outlier_range = grouped_ranges(
            output_vector, calibration_output
        )
        x, y, width, height = geometry(orientation, WIDTH)
        mask = np.zeros(WIDTH, dtype=bool)
        mask[list(OUTLIER_DIMS)] = True
        mask_shape = (height, width)
        save_gray(OUT / f"{prefix}-normal-mask.png", (~mask).reshape(mask_shape))
        save_gray(OUT / f"{prefix}-outlier-mask.png", mask.reshape(mask_shape))
        copy_green = "0 1 0 0 0  " * 3 + "0 0 0 0 1"
        primitives.extend(
            (
                f'<feColorMatrix in="{learned_source}" values="{copy_red}" '
                f'result="{prefix}-learned"/>',
                f'<feColorMatrix in="{residual_grouped_source}" values="{copy_red}" '
                f'result="{prefix}-residual-normal"/>',
                f'<feColorMatrix in="{residual_grouped_source}" values="{copy_green}" '
                f'result="{prefix}-residual-outlier"/>',
            )
        )

        def add_group(group: str, residual_source: str, residual_range: float, output_range: float) -> str:
            learned_coef = learned_range / output_range
            residual_coef = residual_range / output_range
            raw = f"{prefix}-{group}-sum-raw"
            masked = f"{prefix}-{group}-sum"
            primitives.extend(
                (
                    f'<feComposite in="{prefix}-learned" in2="{residual_source}" '
                    f'operator="arithmetic" k1="0" k2="{learned_coef}" '
                    f'k3="{residual_coef}" '
                    f'k4="{CENTER * (1 - learned_coef - residual_coef)}" '
                    f'result="{raw}"/>',
                    f'<feImage href="{prefix}-{group}-mask.png" x="{x}" y="{y}" '
                    f'width="{width}" height="{height}" preserveAspectRatio="none" '
                    f'result="{prefix}-{group}-mask"/>',
                    f'<feComposite in="{raw}" in2="{prefix}-{group}-mask" '
                    f'operator="arithmetic" k1="1" k2="0" k3="-{CENTER}" '
                    f'k4="{CENTER}" result="{masked}"/>',
                )
            )
            return masked

        normal = add_group(
            "normal",
            f"{prefix}-residual-normal",
            residual_normal_range,
            output_normal_range,
        )
        outlier = add_group(
            "outlier",
            f"{prefix}-residual-outlier",
            residual_outlier_range,
            output_outlier_range,
        )
        return (
            pack_grouped_planes(normal, outlier, prefix),
            output_normal_range,
            output_outlier_range,
        )

    def matrix_stage(
        source_signed: str,
        vector: np.ndarray,
        input_range: float,
        weights: np.ndarray,
        bias: np.ndarray,
        orientation: str,
        prefix: str,
        shard_sources: list[tuple[str, int]] | None = None,
        calibration_vector: np.ndarray | None = None,
        output_scales: np.ndarray | None = None,
    ) -> tuple[str, str, np.ndarray, float]:
        outputs, inputs = weights.shape
        expected = weights @ vector + bias
        calibration = vector if calibration_vector is None else calibration_vector
        calibration_expected = calibration_affine(calibration, weights, bias)
        weight_scales = np.maximum(np.max(np.abs(weights), axis=1), 1e-12)
        units = weight_scales * input_range
        nw = weights / weight_scales[:, None]
        nv = vector / input_range
        calibration_nv = calibration / input_range
        partials = np.stack(
            [nw[:, start : start + SHARD] @ nv[start : start + SHARD]
             for start in range(0, inputs, SHARD)],
            axis=1,
        )
        if calibration_nv.ndim == 1:
            calibration_partials = np.stack(
                [
                    nw[:, start : start + SHARD]
                    @ calibration_nv[start : start + SHARD]
                    for start in range(0, inputs, SHARD)
                ],
                axis=1,
            )
            calibration_cumulative = np.cumsum(calibration_partials, axis=1)
        else:
            calibration_partials = np.stack(
                [
                    calibration_nv[:, start : start + SHARD]
                    @ nw[:, start : start + SHARD].T
                    for start in range(0, inputs, SHARD)
                ],
                axis=2,
            )
            calibration_cumulative = np.cumsum(calibration_partials, axis=2)
        nbias = bias / units
        cumulative = np.cumsum(partials, axis=1)
        calibration_final = (
            calibration_cumulative[:, -1]
            if calibration_cumulative.ndim == 2
            else calibration_cumulative[:, :, -1]
        )
        bound = max(
            float(np.max(np.abs(cumulative))),
            float(np.max(np.abs(cumulative[:, -1] + nbias))),
            float(np.max(np.abs(calibration_cumulative))),
            float(np.max(np.abs(calibration_final + nbias))),
        )
        divisor = bound * 1.02
        mag = 0.0
        for start in range(0, inputs, SHARD):
            products = nw[:, start : start + SHARD] * nv[start : start + SHARD][None, :]
            # sum(max(a*b, 0)) = (sum(abs(a*b)) + sum(a*b))/2.
            # Avoid a calibration_cases x outputs x SHARD temporary when the
            # causal quality fixture calibrates on a representative corpus.
            calibration_signed = (
                calibration_nv[..., start : start + SHARD]
                @ nw[:, start : start + SHARD].T
            )
            calibration_absolute = (
                np.abs(calibration_nv[..., start : start + SHARD])
                @ np.abs(nw[:, start : start + SHARD]).T
            )
            mag = max(
                mag,
                float(np.max(np.maximum(products, 0).sum(1))),
                float(np.max(np.maximum(-products, 0).sum(1))),
                float(np.max((calibration_absolute + calibration_signed) / 2)),
                float(np.max((calibration_absolute - calibration_signed) / 2)),
            )
        mag_divisor = mag * 1.02
        coefficient = mag_divisor / (2 * divisor)
        signed_matrix = (
            f"{coefficient} -{coefficient} 0 0 {center_css}  " * 3 + "0 0 0 0 1"
        )
        encoded_parts: list[str] = []
        for shard, start in enumerate(range(0, inputs, SHARD)):
            shard_source, source_start = (
                shard_sources[shard]
                if shard_sources is not None
                else (source_signed, start)
            )
            if orientation == "h":
                w = nw[:, start : start + SHARD]
                save_rg(OUT / f"{prefix}-w{shard}.png", np.maximum(w, 0), np.maximum(-w, 0))
                chunk = f'<feOffset in="{shard_source}" dx="-{source_start}" dy="-{CY}" x="0" y="0" width="{SHARD}" height="1" result="{prefix}-vrow{shard}"/>'
                tile = f'<feTile in="{prefix}-vrow{shard}" x="0" y="0" width="{SHARD}" height="{outputs}" result="{prefix}-v{shard}"/>'
                weight = f'<feImage href="{prefix}-w{shard}.png" x="0" y="0" width="{SHARD}" height="{outputs}" preserveAspectRatio="none" result="{prefix}-w{shard}"/>'
                conv = f'<feConvolveMatrix in="{prefix}-split{shard}" order="{SHARD} 1" kernelMatrix="{kernel}" divisor="{mag_divisor}" targetX="{CX}" targetY="0" edgeMode="none" kernelUnitLength="1 1" preserveAlpha="true" x="{CX}" y="0" width="1" height="{outputs}" result="{prefix}-sum{shard}"/>'
            else:
                w = nw[:, start : start + SHARD].T
                save_rg(OUT / f"{prefix}-w{shard}.png", np.maximum(w, 0), np.maximum(-w, 0))
                chunk = f'<feOffset in="{shard_source}" dx="-{CX}" dy="-{source_start}" x="0" y="0" width="1" height="{SHARD}" result="{prefix}-vcol{shard}"/>'
                tile = f'<feTile in="{prefix}-vcol{shard}" x="0" y="0" width="{outputs}" height="{SHARD}" result="{prefix}-v{shard}"/>'
                weight = f'<feImage href="{prefix}-w{shard}.png" x="0" y="0" width="{outputs}" height="{SHARD}" preserveAspectRatio="none" result="{prefix}-w{shard}"/>'
                conv = f'<feConvolveMatrix in="{prefix}-split{shard}" order="1 {SHARD}" kernelMatrix="{kernel}" divisor="{mag_divisor}" targetX="0" targetY="{CY}" edgeMode="none" kernelUnitLength="1 1" preserveAlpha="true" x="0" y="{CY}" width="{outputs}" height="1" result="{prefix}-sum{shard}"/>'
            primitives.extend((chunk, tile, f'<feColorMatrix in="{prefix}-v{shard}" values="{swap_rg}" result="{prefix}-vs{shard}"/>', weight,
                f'<feComposite in="{prefix}-w{shard}" in2="{prefix}-v{shard}" operator="arithmetic" k1="1" k2="0" k3="0" k4="0" result="{prefix}-same{shard}"/>',
                f'<feComposite in="{prefix}-w{shard}" in2="{prefix}-vs{shard}" operator="arithmetic" k1="1" k2="0" k3="0" k4="0" result="{prefix}-cross{shard}"/>',
                f'<feColorMatrix in="{prefix}-same{shard}" values="{positive_matrix}" result="{prefix}-pos{shard}"/>',
                f'<feColorMatrix in="{prefix}-cross{shard}" values="{negative_matrix}" result="{prefix}-neg{shard}"/>',
                f'<feComposite in="{prefix}-pos{shard}" in2="{prefix}-neg{shard}" operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="{prefix}-split{shard}"/>', conv,
                f'<feColorMatrix in="{prefix}-sum{shard}" values="{signed_matrix}" result="{prefix}-encoded{shard}"/>'))
            encoded_parts.append(f"{prefix}-encoded{shard}")
        total = encoded_parts[0]
        for index, part in enumerate(encoded_parts[1:], 1):
            result = f"{prefix}-total{index}"
            primitives.append(f'<feComposite in="{total}" in2="{part}" operator="arithmetic" k1="0" k2="1" k3="1" k4="-{center_css}" result="{result}"/>')
            total = result
        output_orientation = "v" if orientation == "h" else "h"
        x, y, width, height = geometry(output_orientation, outputs)
        save_gray(OUT / f"{prefix}-bias.png", (CENTER + .5 * nbias / divisor).reshape(height, width))
        primitives.extend((f'<feImage href="{prefix}-bias.png" x="{x}" y="{y}" width="{width}" height="{height}" preserveAspectRatio="none" result="{prefix}-bias"/>',
            f'<feComposite in="{total}" in2="{prefix}-bias" operator="arithmetic" k1="0" k2="1" k3="1" k4="-{center_css}" result="{prefix}-row-scaled"/>'))
        if output_scales is None:
            output_range = float(
                max(np.max(np.abs(expected)), np.max(np.abs(calibration_expected)))
                * 1.05
            )
            scale_values = units
        else:
            output_scales = np.asarray(output_scales, dtype=np.float64)
            if output_scales.shape != (outputs,):
                raise ValueError(
                    f"{prefix}: expected {outputs} output scales, got "
                    f"{output_scales.shape}"
                )
            output_range = 1.0
            scale_values = units / output_scales
        max_unit = float(np.max(scale_values))
        save_gray(
            OUT / f"{prefix}-scales.png",
            (scale_values / max_unit).reshape(height, width),
        )
        scale_coef = divisor * max_unit / output_range
        row_signed = split_signed(f"{prefix}-row-scaled", f"{prefix}-row")
        primitives.extend((f'<feImage href="{prefix}-scales.png" x="{x}" y="{y}" width="{width}" height="{height}" preserveAspectRatio="none" result="{prefix}-scales"/>',
            f'<feComposite in="{row_signed}" in2="{prefix}-scales" operator="arithmetic" k1="{scale_coef}" k2="0" k3="0" k4="0" result="{prefix}-common-signed"/>',
            f'<feColorMatrix in="{prefix}-common-signed" values="{signed_to_common}" result="{prefix}-common"/>'))
        return f"{prefix}-common", f"{prefix}-common-signed", expected, output_range

    BUCKETS = int(os.environ.get("SVG_FILTER_BUCKETS", "32"))
    if BUCKETS < 1:
        raise ValueError("SVG_FILTER_BUCKETS must be at least 1")
    BUCKET_HEADROOM = float(os.environ.get("SVG_FILTER_BUCKET_HEADROOM", "1.08"))
    if BUCKET_HEADROOM < 1:
        raise ValueError("SVG_FILTER_BUCKET_HEADROOM must be at least 1")
    correction_path = os.environ.get("SVG_FILTER_BIAS_CORRECTIONS")
    correction_payload = (
        json.loads(Path(correction_path).read_text()) if correction_path else None
    )
    if correction_payload is not None:
        if len(correction_payload.get("blocks", [])) != 12:
            raise ValueError("SVG_FILTER_BIAS_CORRECTIONS must contain 12 blocks")
        if int(correction_payload.get("groups", BUCKETS)) != BUCKETS:
            raise ValueError("correction group count does not match SVG_FILTER_BUCKETS")
        correction_headroom = float(
            correction_payload.get("headroom", BUCKET_HEADROOM)
        )
        if not np.isclose(correction_headroom, BUCKET_HEADROOM):
            raise ValueError(
                "correction headroom does not match SVG_FILTER_BUCKET_HEADROOM"
            )
    ROTATION_GAIN = 18 / 17
    PACKED_GELU = os.environ.get("SVG_FILTER_PACKED_GELU") == "1"
    GELU_BUCKETS = int(os.environ.get("SVG_FILTER_GELU_BUCKETS", str(BUCKETS)))
    if not 1 <= GELU_BUCKETS <= BUCKETS:
        raise ValueError("SVG_FILTER_GELU_BUCKETS must be between 1 and SVG_FILTER_BUCKETS")

    def perdim_spec_from_bound(bound: np.ndarray) -> dict[str, np.ndarray]:
        scales = np.maximum(
            np.asarray(bound, dtype=np.float64) * BUCKET_HEADROOM, 1e-6
        )
        return {
            "ids": np.zeros(len(scales), dtype=np.int16),
            "group_scales": np.asarray([float(np.max(scales))]),
            "scales": scales,
        }

    def bucket_spec_from_bound(bound: np.ndarray) -> dict[str, np.ndarray]:
        desired = np.maximum(
            np.asarray(bound, dtype=np.float64) * BUCKET_HEADROOM, 1e-6
        )
        logs = np.log2(desired)
        edges = np.linspace(float(np.min(logs)), float(np.max(logs)), BUCKETS + 1)
        ids = np.clip(np.searchsorted(edges, logs, side="right") - 1, 0, BUCKETS - 1)
        group_scales = np.exp2(edges[1:])
        per_dimension = group_scales[ids]
        return {
            "ids": ids.astype(np.int16),
            "group_scales": group_scales,
            "scales": per_dimension,
        }

    def bucket_spec(
        vector: np.ndarray, calibration_vector: np.ndarray
    ) -> dict[str, np.ndarray]:
        return bucket_spec_from_bound(
            np.maximum(np.abs(vector), calibration_absmax(calibration_vector))
        )

    def save_bucketed_state(
        path: Path,
        vector: np.ndarray,
        spec: dict[str, np.ndarray],
        orientation: str,
    ) -> None:
        shape = (1, WIDTH) if orientation == "h" else (WIDTH, 1)
        save_gray(
            path,
            (CENTER + vector / (2 * spec["scales"])).reshape(shape),
        )

    def bucketed_matrix_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        input_spec: dict[str, np.ndarray],
        weights: np.ndarray,
        bias: np.ndarray,
        orientation: str,
        prefix: str,
        output_bound: np.ndarray | None = None,
        bucket_output: bool = True,
        runtime_bias: np.ndarray | None = None,
    ) -> tuple[str, str, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        scales = input_spec["scales"]
        normalized = vector / scales
        calibration_normalized = calibration_vector / scales
        expected = weights @ vector + bias
        calibration_expected = calibration_affine(calibration_vector, weights, bias)
        if output_bound is None:
            output_bound = np.maximum(
                np.abs(expected), calibration_absmax(calibration_expected)
            )
        output_spec = (
            bucket_spec_from_bound(output_bound)
            if bucket_output
            else perdim_spec_from_bound(output_bound)
        )
        source_signed = split_signed(source, f"{prefix}-input")
        common, signed, browser_expected, _ = matrix_stage(
            source_signed,
            normalized,
            1.0,
            weights * scales[None, :],
            bias if runtime_bias is None else runtime_bias,
            orientation,
            prefix,
            calibration_vector=calibration_normalized,
            output_scales=output_spec["scales"],
        )
        return (
            common,
            signed,
            browser_expected,
            calibration_expected,
            output_spec,
        )

    def bucketed_rotate_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        spec: dict[str, np.ndarray],
        orientation: str,
        prefix: str,
    ) -> str:
        scales = spec["scales"]
        source_signed = split_signed(source, f"{prefix}-input")
        common, _, _, _ = matrix_stage(
            source_signed,
            vector / scales,
            1.0,
            np.eye(WIDTH) * scales[None, :],
            np.zeros(WIDTH),
            orientation,
            prefix,
            calibration_vector=calibration_vector / scales,
            output_scales=scales * ROTATION_GAIN,
        )
        return common

    def bucketed_add_stage(
        learned_source: str,
        learned: np.ndarray,
        calibration_learned: np.ndarray,
        learned_spec: dict[str, np.ndarray],
        residual_source: str,
        residual: np.ndarray,
        calibration_residual: np.ndarray,
        residual_spec: dict[str, np.ndarray],
        orientation: str,
        prefix: str,
    ) -> tuple[str, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        output = learned + residual
        calibration_output = calibration_learned + calibration_residual
        conservative_bound = (
            np.maximum(np.abs(learned), calibration_absmax(calibration_learned))
            + np.maximum(np.abs(residual), calibration_absmax(calibration_residual))
        )
        output_spec = bucket_spec_from_bound(conservative_bound)
        output_scales = output_spec["scales"]
        learned_ratio = learned_spec["scales"] / output_scales
        residual_ratio = residual_spec["scales"] / output_scales
        x, y, width, height = geometry(orientation, WIDTH)
        shape = (height, width)
        learned_max = float(np.max(learned_ratio))
        residual_max = float(np.max(residual_ratio))
        save_gray(
            OUT / f"{prefix}-learned-ratio.png",
            (learned_ratio / learned_max).reshape(shape),
        )
        save_gray(
            OUT / f"{prefix}-residual-ratio.png",
            (residual_ratio / residual_max).reshape(shape),
        )
        learned_signed = split_signed(learned_source, f"{prefix}-learned")
        residual_signed = split_signed(residual_source, f"{prefix}-residual")
        primitives.extend(
            (
                f'<feImage href="{prefix}-learned-ratio.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-learned-ratio"/>',
                f'<feComposite in="{learned_signed}" '
                f'in2="{prefix}-learned-ratio" operator="arithmetic" '
                f'k1="{learned_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-learned-scaled"/>',
                f'<feImage href="{prefix}-residual-ratio.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-residual-ratio"/>',
                f'<feComposite in="{residual_signed}" '
                f'in2="{prefix}-residual-ratio" operator="arithmetic" '
                f'k1="{residual_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-residual-scaled"/>',
                f'<feComposite in="{prefix}-learned-scaled" '
                f'in2="{prefix}-residual-scaled" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" result="{prefix}-sum-signed"/>',
                f'<feColorMatrix in="{prefix}-sum-signed" values="{signed_to_common}" '
                f'result="{prefix}-out"/>',
            )
        )
        return f"{prefix}-out", output, calibration_output, output_spec

    def bucketed_layernorm_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        input_spec: dict[str, np.ndarray],
        gamma: np.ndarray,
        beta: np.ndarray,
        orientation: str,
        prefix: str,
    ) -> tuple[str, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        output = layer_norm(vector, gamma, beta)
        calibration_output = layer_norm(calibration_vector, gamma, beta)
        mean = float(np.mean(vector))
        calibration_mean = float(np.mean(calibration_vector))
        diff = vector - mean
        calibration_diff = calibration_vector - calibration_mean
        variance = float(np.mean(diff**2))
        calibration_variance = float(np.mean(calibration_diff**2))
        normalized = diff / np.sqrt(variance + EPSILON)
        calibration_normalized = calibration_diff / np.sqrt(
            calibration_variance + EPSILON
        )
        normalized_range = float(
            max(np.max(np.abs(normalized)), np.max(np.abs(calibration_normalized)))
            * 1.04
        )
        ids = input_spec["ids"]
        group_scales = input_spec["group_scales"]
        x, y, width, height = geometry(orientation, WIDTH)
        shape = (height, width)

        def reduction_scale(values: np.ndarray, alternate: np.ndarray) -> float:
            shard_means = [
                max(
                    abs(float(np.mean(values[start : start + SHARD]))),
                    abs(float(np.mean(alternate[start : start + SHARD]))),
                )
                for start in range(0, WIDTH, SHARD)
            ]
            return min(128.0, 0.9 / max(max(shard_means), 1e-12))

        group_sources: list[str] = []
        group_masks: list[np.ndarray] = []
        group_mean_results: list[str] = []
        group_mean_scales: list[float] = []
        group_mean_contributions: list[tuple[float, float]] = []
        for group in range(BUCKETS):
            mask = ids == group
            group_masks.append(mask)
            save_gray(OUT / f"{prefix}-g{group}-mask.png", mask.reshape(shape))
            mask_name = f"{prefix}-g{group}-mask"
            source_name = f"{prefix}-g{group}-source"
            primitives.extend(
                (
                    f'<feImage href="{prefix}-g{group}-mask.png" x="{x}" y="{y}" '
                    f'width="{width}" height="{height}" preserveAspectRatio="none" '
                    f'result="{mask_name}"/>',
                    f'<feComposite in="{source}" in2="{mask_name}" '
                    f'operator="arithmetic" k1="1" k2="0" k3="-{CENTER}" '
                    f'k4="{CENTER}" result="{source_name}"/>',
                )
            )
            group_sources.append(source_name)
            scale = float(group_scales[group])
            values = np.where(mask, vector / scale, 0.0)
            alternate = np.where(mask, calibration_vector / scale, 0.0)
            mean_scale = reduction_scale(values, alternate)
            group_mean_scales.append(mean_scale)
            group_mean_results.append(
                reduce_vector(
                    source_name,
                    f"{prefix}-g{group}-mean",
                    orientation,
                    WIDTH,
                    scale=mean_scale,
                    centered=True,
                )
            )
            group_mean_contributions.append(
                (
                    float(np.sum(vector[mask]) / WIDTH),
                    float(np.sum(calibration_vector[mask]) / WIDTH),
                )
            )

        mean_range = max(
            sum(max(abs(a), abs(b)) for a, b in group_mean_contributions) * 1.05,
            1e-6,
        )
        encoded_means: list[str] = []
        for group, reduced in enumerate(group_mean_results):
            coefficient = float(group_scales[group]) / (
                mean_range * group_mean_scales[group]
            )
            matrix = (
                f"{coefficient} 0 0 0 {CENTER * (1 - coefficient)}  " * 3
                + "0 0 0 0 1"
            )
            encoded = f"{prefix}-g{group}-mean-encoded"
            primitives.append(
                f'<feColorMatrix in="{reduced}" values="{matrix}" result="{encoded}"/>'
            )
            encoded_means.append(encoded)
        mean_name = encoded_means[0]
        for group, encoded in enumerate(encoded_means[1:], 1):
            result = f"{prefix}-mean-sum{group}"
            primitives.append(
                f'<feComposite in="{mean_name}" in2="{encoded}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="-{CENTER}" result="{result}"/>'
            )
            mean_name = result
        mean_tiled = tile_scalar(mean_name, f"{prefix}-mean", orientation, WIDTH)

        diff_names: list[str] = []
        diff_ranges: list[float] = []
        variance_parts: list[tuple[str, float]] = []
        variance_contributions: list[tuple[float, float]] = []
        for group, mask in enumerate(group_masks):
            group_diff = np.where(mask, diff, 0.0)
            alternate_group_diff = np.where(mask, calibration_diff, 0.0)
            diff_range = max(
                float(np.max(np.abs(group_diff))),
                float(np.max(np.abs(alternate_group_diff))),
                1e-6,
            ) * 1.05
            diff_ranges.append(diff_range)
            source_coefficient = float(group_scales[group]) / diff_range
            mean_coefficient = mean_range / diff_range
            offset = CENTER * (1 - source_coefficient + mean_coefficient)
            pair = f"{prefix}-g{group}-diff-pair"
            raw = f"{prefix}-g{group}-diff-raw"
            diff_name = f"{prefix}-g{group}-diff"
            primitives.extend(
                (
                    f'<feColorMatrix in="{group_sources[group]}" values="{to_red}" '
                    f'result="{prefix}-g{group}-source-red"/>',
                    f'<feColorMatrix in="{mean_tiled}" values="{to_green}" '
                    f'result="{prefix}-g{group}-mean-green"/>',
                    f'<feComposite in="{prefix}-g{group}-source-red" '
                    f'in2="{prefix}-g{group}-mean-green" operator="arithmetic" '
                    f'k1="0" k2="1" k3="1" k4="0" result="{pair}"/>',
                    f'<feColorMatrix in="{pair}" '
                    f'values="{source_coefficient} -{mean_coefficient} 0 0 {offset}  '
                    f'{source_coefficient} -{mean_coefficient} 0 0 {offset}  '
                    f'{source_coefficient} -{mean_coefficient} 0 0 {offset}  '
                    f'0 0 0 0 1" result="{raw}"/>',
                    f'<feComposite in="{raw}" in2="{prefix}-g{group}-mask" '
                    f'operator="arithmetic" k1="1" k2="0" k3="-{CENTER}" '
                    f'k4="{CENTER}" result="{diff_name}"/>',
                    f'<feComposite in="{diff_name}" in2="{diff_name}" '
                    f'operator="arithmetic" k1="4" k2="{-4 * CENTER}" '
                    f'k3="{-4 * CENTER}" k4="{4 * CENTER * CENTER}" '
                    f'result="{prefix}-g{group}-square-alpha"/>',
                    f'<feColorMatrix in="{prefix}-g{group}-square-alpha" '
                    f'values="{copy_red}" result="{prefix}-g{group}-square"/>',
                )
            )
            diff_names.append(diff_name)
            normalized_square = (group_diff / diff_range) ** 2
            alternate_square = (alternate_group_diff / diff_range) ** 2
            variance_scale = reduction_scale(normalized_square, alternate_square)
            reduced = reduce_vector(
                f"{prefix}-g{group}-square",
                f"{prefix}-g{group}-variance",
                orientation,
                WIDTH,
                scale=variance_scale,
            )
            variance_parts.append((reduced, variance_scale))
            variance_contributions.append(
                (
                    float(np.sum(group_diff**2) / WIDTH),
                    float(np.sum(alternate_group_diff**2) / WIDTH),
                )
            )

        variance_range = max(
            sum(max(a, b) for a, b in variance_contributions) * 1.05,
            1e-9,
        )
        encoded_variances: list[str] = []
        for group, (reduced, variance_scale) in enumerate(variance_parts):
            coefficient = diff_ranges[group] ** 2 / (
                variance_range * variance_scale
            )
            encoded = f"{prefix}-g{group}-variance-encoded"
            primitives.append(
                f'<feComposite in="{reduced}" in2="{reduced}" '
                f'operator="arithmetic" k1="0" k2="{coefficient}" '
                f'k3="0" k4="0" result="{encoded}"/>'
            )
            encoded_variances.append(encoded)
        variance_name = encoded_variances[0]
        for group, encoded in enumerate(encoded_variances[1:], 1):
            result = f"{prefix}-variance-sum{group}"
            primitives.append(
                f'<feComposite in="{variance_name}" in2="{encoded}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="0" result="{result}"/>'
            )
            variance_name = result

        grid = np.linspace(0, 1, 256)
        normalized_parts: list[str] = []
        for group, diff_name in enumerate(diff_names):
            raw_factor = diff_ranges[group] / (
                np.sqrt(grid * variance_range + EPSILON) * normalized_range
            )
            gain_scale = max(
                1.0,
                diff_ranges[group]
                / (
                    np.sqrt(min(variance, calibration_variance) + EPSILON)
                    * normalized_range
                )
                * 1.08,
            )
            table = " ".join(
                f"{value:.8g}" for value in np.clip(raw_factor / gain_scale, 0, 1)
            )
            scalar = f"{prefix}-g{group}-gain-scalar"
            primitives.append(
                f'<feComponentTransfer in="{variance_name}" result="{scalar}">'
                f'<feFuncR type="table" tableValues="{table}"/>'
                f'<feFuncG type="table" tableValues="{table}"/>'
                f'<feFuncB type="table" tableValues="{table}"/>'
                '<feFuncA type="identity"/></feComponentTransfer>'
            )
            tiled = tile_scalar(scalar, f"{prefix}-g{group}-gain", orientation, WIDTH)
            signed = split_signed(diff_name, f"{prefix}-g{group}-diff")
            result = f"{prefix}-g{group}-normalized-signed"
            primitives.append(
                f'<feComposite in="{signed}" in2="{tiled}" '
                f'operator="arithmetic" k1="{gain_scale}" k2="0" '
                f'k3="0" k4="0" result="{result}"/>'
            )
            normalized_parts.append(result)
        normalized_signed = normalized_parts[0]
        for group, part in enumerate(normalized_parts[1:], 1):
            result = f"{prefix}-normalized-sum{group}"
            primitives.append(
                f'<feComposite in="{normalized_signed}" in2="{part}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="0" result="{result}"/>'
            )
            normalized_signed = result

        affine_bound = np.maximum(
            np.abs(normalized * gamma), np.abs(calibration_normalized * gamma)
        ) + np.abs(beta)
        output_spec = bucket_spec_from_bound(affine_bound)
        output_scales = output_spec["scales"]
        positive_ratio = normalized_range * np.maximum(gamma, 0) / output_scales
        negative_ratio = normalized_range * np.maximum(-gamma, 0) / output_scales
        positive_max = max(float(np.max(positive_ratio)), 1e-12)
        negative_max = max(float(np.max(negative_ratio)), 1e-12)
        save_gray(
            OUT / f"{prefix}-gamma-positive.png",
            (positive_ratio / positive_max).reshape(shape),
        )
        save_gray(
            OUT / f"{prefix}-gamma-negative.png",
            (negative_ratio / negative_max).reshape(shape),
        )
        save_gray(
            OUT / f"{prefix}-beta-bucketed.png",
            (CENTER + beta / (2 * output_scales)).reshape(shape),
        )
        primitives.extend(
            (
                f'<feImage href="{prefix}-gamma-positive.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-gamma-positive"/>',
                f'<feComposite in="{normalized_signed}" '
                f'in2="{prefix}-gamma-positive" operator="arithmetic" '
                f'k1="{positive_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-positive-scaled"/>',
                f'<feColorMatrix in="{normalized_signed}" values="{swap_rg}" '
                f'result="{prefix}-normalized-swapped"/>',
                f'<feImage href="{prefix}-gamma-negative.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-gamma-negative"/>',
                f'<feComposite in="{prefix}-normalized-swapped" '
                f'in2="{prefix}-gamma-negative" operator="arithmetic" '
                f'k1="{negative_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-negative-scaled"/>',
                f'<feComposite in="{prefix}-positive-scaled" '
                f'in2="{prefix}-negative-scaled" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-affine-signed"/>',
                f'<feColorMatrix in="{prefix}-affine-signed" '
                f'values="{signed_to_common}" result="{prefix}-affine"/>',
                f'<feImage href="{prefix}-beta-bucketed.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-beta-bucketed"/>',
                f'<feComposite in="{prefix}-affine" '
                f'in2="{prefix}-beta-bucketed" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="-{CENTER}" '
                f'result="{prefix}-out"/>',
            )
        )
        return f"{prefix}-out", output, calibration_output, output_spec

    def scaled_layernorm_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        input_spec: dict[str, np.ndarray],
        gamma: np.ndarray,
        beta: np.ndarray,
        orientation: str,
        prefix: str,
        runtime_beta: np.ndarray | None = None,
    ) -> tuple[str, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        scales = input_spec["scales"]
        normalized_input = vector / scales
        calibration_normalized_input = calibration_vector / scales
        mean = float(np.mean(vector))
        calibration_mean = np.mean(calibration_vector, axis=-1)
        diff = vector - mean
        calibration_diff = calibration_vector - np.expand_dims(
            calibration_mean, axis=-1
        ) if np.ndim(calibration_mean) else calibration_vector - calibration_mean
        variance = float(np.mean(diff**2))
        calibration_variance = np.mean(calibration_diff**2, axis=-1)
        gain = 1 / np.sqrt(variance + EPSILON)
        calibration_gain = 1 / np.sqrt(calibration_variance + EPSILON)
        output = diff * gain * gamma + beta
        calibration_output = (
            calibration_diff * calibration_gain * gamma + beta
            if np.ndim(calibration_gain) == 0
            else calibration_diff * calibration_gain[:, None] * gamma + beta
        )
        q_signed = split_signed(source, f"{prefix}-input")

        mean_common, mean_signed, _, mean_range = matrix_stage(
            q_signed,
            normalized_input,
            1.0,
            (scales / WIDTH)[None, :],
            np.zeros(1),
            orientation,
            f"{prefix}-mean",
            calibration_vector=calibration_normalized_input,
        )
        primitives.extend(
            (
                f'<feComposite in="{q_signed}" in2="{q_signed}" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-q-square-rg"/>',
                f'<feColorMatrix in="{prefix}-q-square-rg" '
                f'values="{positive_matrix}" result="{prefix}-q-square"/>',
            )
        )
        second_common, second_signed, _, second_range = matrix_stage(
            f"{prefix}-q-square",
            normalized_input**2,
            1.0,
            (scales**2 / WIDTH)[None, :],
            np.zeros(1),
            orientation,
            f"{prefix}-second",
            calibration_vector=calibration_normalized_input**2,
        )
        variance_range = max(
            variance, float(np.max(calibration_variance)), 1e-9
        ) * 1.08
        primitives.extend(
            (
                f'<feComposite in="{mean_signed}" in2="{mean_signed}" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-mean-square-rg"/>',
                f'<feColorMatrix in="{prefix}-mean-square-rg" '
                f'values="{positive_matrix}" result="{prefix}-mean-square"/>',
                f'<feComposite in="{second_signed}" in2="{prefix}-mean-square" '
                f'operator="arithmetic" k1="0" '
                f'k2="{second_range / variance_range}" '
                f'k3="{-mean_range**2 / variance_range}" k4="0" '
                f'result="{prefix}-variance-red"/>',
                f'<feColorMatrix in="{prefix}-variance-red" values="{copy_red}" '
                f'result="{prefix}-variance"/>',
            )
        )
        gain_max = max(gain, float(np.max(calibration_gain))) * 1.04
        grid = np.linspace(0, 1, 256)
        gain_table = " ".join(
            f"{value:.8g}"
            for value in np.clip(
                1 / np.sqrt(grid * variance_range + EPSILON) / gain_max,
                0,
                1,
            )
        )
        primitives.append(
            f'<feComponentTransfer in="{prefix}-variance" '
            f'result="{prefix}-gain-scalar">'
            f'<feFuncR type="table" tableValues="{gain_table}"/>'
            f'<feFuncG type="table" tableValues="{gain_table}"/>'
            f'<feFuncB type="table" tableValues="{gain_table}"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )
        gain_tiled = tile_scalar(
            f"{prefix}-gain-scalar", f"{prefix}-gain", orientation, WIDTH
        )
        mean_tiled = tile_scalar(
            mean_common, f"{prefix}-mean-value", orientation, WIDTH
        )
        mean_tiled_signed = split_signed(mean_tiled, f"{prefix}-mean-tiled")

        q_bound = np.maximum(
            np.abs(vector * gain * gamma),
            calibration_absmax(
                calibration_vector * calibration_gain * gamma
                if np.ndim(calibration_gain) == 0
                else calibration_vector * calibration_gain[:, None] * gamma
            ),
        )
        mean_bound = np.maximum(
            np.abs(mean * gain * gamma),
            calibration_absmax(
                calibration_mean * calibration_gain * gamma
                if np.ndim(calibration_gain) == 0
                else (calibration_mean * calibration_gain)[:, None] * gamma
            ),
        )
        output_spec = bucket_spec_from_bound(q_bound + mean_bound + np.abs(beta))
        output_scales = output_spec["scales"]
        x, y, width, height = geometry(orientation, WIDTH)
        shape = (height, width)
        q_ratio_positive = scales * np.maximum(gamma, 0) * gain_max / output_scales
        q_ratio_negative = scales * np.maximum(-gamma, 0) * gain_max / output_scales
        mean_ratio_positive = (
            mean_range * np.maximum(gamma, 0) * gain_max / output_scales
        )
        mean_ratio_negative = (
            mean_range * np.maximum(-gamma, 0) * gain_max / output_scales
        )

        def ratio_image(name: str, values: np.ndarray) -> tuple[str, float]:
            maximum = max(float(np.max(values)), 1e-12)
            save_gray(OUT / f"{prefix}-{name}.png", (values / maximum).reshape(shape))
            result = f"{prefix}-{name}"
            primitives.append(
                f'<feImage href="{prefix}-{name}.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{result}"/>'
            )
            return result, maximum

        q_positive_image, q_positive_max = ratio_image(
            "q-positive-ratio", q_ratio_positive
        )
        q_negative_image, q_negative_max = ratio_image(
            "q-negative-ratio", q_ratio_negative
        )
        mean_positive_image, mean_positive_max = ratio_image(
            "mean-positive-ratio", mean_ratio_positive
        )
        mean_negative_image, mean_negative_max = ratio_image(
            "mean-negative-ratio", mean_ratio_negative
        )
        rendered_beta = beta if runtime_beta is None else runtime_beta
        save_gray(
            OUT / f"{prefix}-beta-scaled.png",
            (CENTER + rendered_beta / (2 * output_scales)).reshape(shape),
        )
        primitives.extend(
            (
                f'<feComposite in="{q_signed}" in2="{gain_tiled}" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-q-gained"/>',
                f'<feComposite in="{prefix}-q-gained" in2="{q_positive_image}" '
                f'operator="arithmetic" k1="{q_positive_max}" k2="0" k3="0" '
                f'k4="0" result="{prefix}-q-positive"/>',
                f'<feColorMatrix in="{prefix}-q-gained" values="{swap_rg}" '
                f'result="{prefix}-q-gained-swapped"/>',
                f'<feComposite in="{prefix}-q-gained-swapped" '
                f'in2="{q_negative_image}" operator="arithmetic" '
                f'k1="{q_negative_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-q-negative"/>',
                f'<feComposite in="{mean_tiled_signed}" in2="{gain_tiled}" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-mean-gained"/>',
                f'<feColorMatrix in="{prefix}-mean-gained" values="{swap_rg}" '
                f'result="{prefix}-mean-gained-negated"/>',
                f'<feComposite in="{prefix}-mean-gained-negated" '
                f'in2="{mean_positive_image}" operator="arithmetic" '
                f'k1="{mean_positive_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-mean-positive"/>',
                f'<feComposite in="{prefix}-mean-gained" '
                f'in2="{mean_negative_image}" operator="arithmetic" '
                f'k1="{mean_negative_max}" k2="0" k3="0" k4="0" '
                f'result="{prefix}-mean-negative"/>',
                f'<feComposite in="{prefix}-q-positive" '
                f'in2="{prefix}-q-negative" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" result="{prefix}-q-term"/>',
                f'<feComposite in="{prefix}-mean-positive" '
                f'in2="{prefix}-mean-negative" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" result="{prefix}-mean-term"/>',
                f'<feComposite in="{prefix}-q-term" in2="{prefix}-mean-term" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-normalized-affine-signed"/>',
                f'<feColorMatrix in="{prefix}-normalized-affine-signed" '
                f'values="{signed_to_common}" result="{prefix}-affine"/>',
                f'<feImage href="{prefix}-beta-scaled.png" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{prefix}-beta-scaled"/>',
                f'<feComposite in="{prefix}-affine" in2="{prefix}-beta-scaled" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="-{CENTER}" result="{prefix}-out"/>',
            )
        )
        return f"{prefix}-out", output, calibration_output, output_spec

    if os.environ.get("SVG_FILTER_LN_FUSION_BUCKETED_ONLY") == "1":
        input_vector = data["x"]
        calibration_input = -input_vector
        input_spec = bucket_spec(input_vector, calibration_input)
        save_bucketed_state(OUT / "input.png", input_vector, input_spec, "h")
        save_bucketed_state(
            OUT / "input-alt.png", calibration_input, input_spec, "h"
        )
        input_start = len(primitives)
        primitives.append(
            f'<feImage href="input.png" x="0" y="{CY}" width="{WIDTH}" '
            'height="1" preserveAspectRatio="none" result="fusion-x"/>'
        )
        input_end = len(primitives)

        block_data = model_data(0, input_vector)
        composed_weight = (
            block_data["attn_proj_weight"] @ block_data["v_weight"]
        )
        composed_bias = (
            block_data["attn_proj_weight"] @ block_data["v_bias"]
            + block_data["attn_proj_bias"]
        )
        q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
        normalized = layer_norm(
            input_vector, block_data["ln1_gamma"], block_data["ln1_beta"]
        )
        calibration_normalized = layer_norm(
            calibration_input,
            block_data["ln1_gamma"],
            block_data["ln1_beta"],
        )
        expected = q_attention.reconstructed @ normalized + composed_bias
        calibration_expected = (
            q_attention.reconstructed @ calibration_normalized + composed_bias
        )
        shared_output_bound = np.maximum(
            np.abs(expected), np.abs(calibration_expected)
        )

        baseline_start = len(primitives)
        baseline_ln, _, baseline_calibration_ln, baseline_ln_spec = (
            scaled_layernorm_stage(
                "fusion-x",
                input_vector,
                calibration_input,
                input_spec,
                block_data["ln1_gamma"],
                block_data["ln1_beta"],
                "h",
                "fusion-baseline-ln",
            )
        )
        baseline_ln_end = len(primitives)
        baseline_output, _, _, _, baseline_output_spec = bucketed_matrix_stage(
            baseline_ln,
            normalized,
            calibration_normalized,
            baseline_ln_spec,
            q_attention.reconstructed,
            composed_bias,
            "h",
            "fusion-baseline-matrix",
            output_bound=shared_output_bound,
        )
        baseline_end = len(primitives)

        fused_stats_start = len(primitives)
        scaled_layernorm_stage(
            "fusion-x",
            input_vector,
            calibration_input,
            input_spec,
            block_data["ln1_gamma"],
            block_data["ln1_beta"],
            "h",
            "fusion-stats",
        )
        fused_stats_full_end = len(primitives)
        fused_stats_end = next(
            index + 1
            for index in range(fused_stats_start, fused_stats_full_end)
            if 'result="fusion-stats-gain-scalar"' in primitives[index]
        )

        gamma_weight = (
            q_attention.reconstructed * block_data["ln1_gamma"][None, :]
        )
        fused_constant = (
            q_attention.reconstructed @ block_data["ln1_beta"] + composed_bias
        )
        mean = float(np.mean(input_vector))
        calibration_mean = float(np.mean(calibration_input))
        mean_bound = max(abs(mean), abs(calibration_mean), 1e-9)
        mean_range = mean_bound * 1.05
        mean_spec = perdim_spec_from_bound(np.full(WIDTH, mean_bound))
        mean_scale = float(mean_spec["scales"][0])
        fused_diff_start = len(primitives)
        mean_tiled = tile_scalar(
            "fusion-stats-mean-common", "fusion-direct-mean", "h", WIDTH
        )
        mean_coefficient = -mean_range / mean_scale
        mean_matrix = (
            f"{mean_coefficient} 0 0 0 {CENTER * (1 - mean_coefficient)}  "
            * 3
            + "0 0 0 0 1"
        )
        primitives.append(
            f'<feColorMatrix in="{mean_tiled}" values="{mean_matrix}" '
            'result="fusion-negative-mean"/>'
        )
        negative_mean = np.full(WIDTH, -mean)
        calibration_negative_mean = np.full(WIDTH, -calibration_mean)
        fused_diff_source, fused_diff, calibration_fused_diff, fused_diff_spec = (
            bucketed_add_stage(
                "fusion-x",
                input_vector,
                calibration_input,
                input_spec,
                "fusion-negative-mean",
                negative_mean,
                calibration_negative_mean,
                mean_spec,
                "h",
                "fusion-direct-diff",
            )
        )
        fused_diff_end = len(primitives)
        reduced = gamma_weight @ fused_diff
        calibration_reduced = gamma_weight @ calibration_fused_diff
        reduced_bound = np.maximum(np.abs(reduced), np.abs(calibration_reduced))
        fused_matrix_start = len(primitives)
        fused_reduced_common, fused_reduced_signed, _, _, fused_reduced_spec = bucketed_matrix_stage(
            fused_diff_source,
            fused_diff,
            calibration_fused_diff,
            fused_diff_spec,
            gamma_weight,
            np.zeros(WIDTH),
            "h",
            "fusion-direct-matrix",
            output_bound=reduced_bound,
        )
        fused_matrix_end = len(primitives)

        variance = float(np.mean((input_vector - mean) ** 2))
        calibration_variance = float(
            np.mean((calibration_input - calibration_mean) ** 2)
        )
        gain = 1 / np.sqrt(variance + EPSILON)
        calibration_gain = 1 / np.sqrt(calibration_variance + EPSILON)
        gain_max = max(gain, calibration_gain) * 1.04
        fused_exact = reduced * gain + fused_constant
        fused_calibration_exact = (
            calibration_reduced * calibration_gain + fused_constant
        )
        fused_component_bound = np.maximum(
            np.abs(reduced * gain),
            np.abs(calibration_reduced * calibration_gain),
        ) + np.abs(fused_constant)
        fused_output_spec = bucket_spec_from_bound(fused_component_bound)
        target_scales = fused_output_spec["scales"]
        gain_ratios = (
            fused_reduced_spec["scales"] * gain_max / target_scales
        )
        gain_ratio_max = float(np.max(gain_ratios))
        save_gray(
            OUT / "fusion-gain-ratios.png",
            (gain_ratios / gain_ratio_max).reshape(WIDTH, 1),
        )
        save_rg(
            OUT / "fusion-constant-signed.png",
            (np.maximum(fused_constant, 0) / target_scales).reshape(WIDTH, 1),
            (np.maximum(-fused_constant, 0) / target_scales).reshape(WIDTH, 1),
        )
        fused_combine_start = len(primitives)
        primitives.extend(
            (
                '<feImage href="fusion-gain-ratios.png" x="255" y="0" '
                'width="1" height="768" preserveAspectRatio="none" '
                'result="fusion-gain-ratios"/>',
                f'<feComposite in="{fused_reduced_signed}" '
                'in2="fusion-gain-ratios" operator="arithmetic" '
                f'k1="{gain_ratio_max}" k2="0" k3="0" k4="0" '
                'result="fusion-ratio-scaled"/>',
                '<feOffset in="fusion-stats-gain-scalar" dx="-255" '
                'x="0" y="0" width="1" height="1" '
                'result="fusion-gain-origin"/>',
                '<feTile in="fusion-gain-origin" x="255" y="0" '
                'width="1" height="768" result="fusion-gain-tiled"/>',
                '<feComposite in="fusion-ratio-scaled" '
                'in2="fusion-gain-tiled" operator="arithmetic" '
                'k1="1" k2="0" k3="0" k4="0" '
                'result="fusion-gained-signed"/>',
                '<feImage href="fusion-constant-signed.png" x="255" y="0" '
                'width="1" height="768" preserveAspectRatio="none" '
                'result="fusion-constant-signed"/>',
                '<feComposite in="fusion-gained-signed" '
                'in2="fusion-constant-signed" '
                'operator="arithmetic" k1="0" k2="1" k3="1" '
                'k4="0" result="fusion-output-signed"/>',
                '<feColorMatrix in="fusion-output-signed" '
                f'values="{signed_to_common}" result="fusion-direct-output"/>',
            )
        )
        fused_combine_end = len(primitives)

        def bucketed_fusion_page(title: str, body: str, output: str) -> str:
            return (
                '<!doctype html><meta charset="utf-8">'
                f'<title>{title}</title>'
                '<style>html,body{margin:0;background:black}'
                'svg{display:block;image-rendering:pixelated}</style>'
                '<svg width="1" height="768" viewBox="0 0 1 768" '
                'xmlns="http://www.w3.org/2000/svg"><defs>'
                '<filter id="test" filterUnits="userSpaceOnUse" '
                'primitiveUnits="userSpaceOnUse" x="0" y="0" width="768" '
                f'height="768" color-interpolation-filters="{FILTER_COLOR}">'
                + body
                + f'<feOffset in="{output}" dx="-255" x="0" y="0" '
                'width="1" height="768"/></filter></defs>'
                '<rect width="768" height="768" fill="white" '
                'filter="url(#test)"/></svg>'
            )

        input_body = "".join(primitives[input_start:input_end])
        baseline_body = input_body + "".join(
            primitives[baseline_start:baseline_end]
        )
        fused_body = (
            input_body
            + "".join(primitives[fused_stats_start:fused_stats_end])
            + "".join(primitives[fused_diff_start:fused_diff_end])
            + "".join(primitives[fused_matrix_start:fused_matrix_end])
            + "".join(primitives[fused_combine_start:fused_combine_end])
        )
        baseline_html = bucketed_fusion_page(
            "Bucketed materialized LayerNorm consumer",
            baseline_body,
            baseline_output,
        )
        fused_html = bucketed_fusion_page(
            "Bucketed fused LayerNorm consumer",
            fused_body,
            "fusion-direct-output",
        )
        pages = {
            "materialized": baseline_html,
            "fused": fused_html,
            "materialized-alt": baseline_html.replace(
                'href="input.png"', 'href="input-alt.png"'
            ),
            "fused-alt": fused_html.replace(
                'href="input.png"', 'href="input-alt.png"'
            ),
            "reduced": bucketed_fusion_page(
                "Bucketed centered matrix debug",
                input_body
                + "".join(primitives[fused_stats_start:fused_stats_end])
                + "".join(primitives[fused_diff_start:fused_diff_end])
                + "".join(primitives[fused_matrix_start:fused_matrix_end]),
                fused_reduced_common,
            ),
        }
        for name, page in pages.items():
            (OUT / f"{name}.html").write_text(page)
        (OUT / "reference.json").write_text(
            json.dumps(
                {
                    "expected": expected.tolist(),
                    "expected_alt": calibration_expected.tolist(),
                    "fused_algebraic_expected": fused_exact.tolist(),
                    "fused_algebraic_expected_alt": fused_calibration_exact.tolist(),
                    "baseline_output_scales": baseline_output_spec["scales"].tolist(),
                    "fused_output_scales": target_scales.tolist(),
                    "reduced": reduced.tolist(),
                    "reduced_scales": fused_reduced_spec["scales"].tolist(),
                    "algebraic_max_error": float(
                        max(
                            np.max(np.abs(expected - fused_exact)),
                            np.max(
                                np.abs(
                                    calibration_expected
                                    - fused_calibration_exact
                                )
                            ),
                        )
                    ),
                    "baseline_primitives": (baseline_end - baseline_start) + 1,
                    "fused_primitives": (
                        (fused_stats_end - fused_stats_start)
                        + (fused_diff_end - fused_diff_start)
                        + (fused_matrix_end - fused_matrix_start)
                        + (fused_combine_end - fused_combine_start)
                        + 1
                    ),
                    "pages": {
                        name: len(page.encode()) for name, page in pages.items()
                    },
                },
                indent=2,
            )
            + "\n"
        )
        print(
            {
                "output": str(OUT),
                "baseline_primitives": (baseline_end - baseline_start) + 1,
                "fused_primitives": (
                    (fused_stats_end - fused_stats_start)
                    + (fused_diff_end - fused_diff_start)
                    + (fused_matrix_end - fused_matrix_start)
                    + (fused_combine_end - fused_combine_start)
                    + 1
                ),
            }
        )
        return

    def bucketed_gelu_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        input_spec: dict[str, np.ndarray],
        orientation: str,
        prefix: str,
    ) -> tuple[str, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        output = gelu_new(vector)
        calibration_output = gelu_new(calibration_vector)
        input_scales = np.asarray(input_spec["scales"], dtype=np.float64)
        if GELU_BUCKETS == BUCKETS:
            ids = input_spec["ids"]
            input_group_scales = input_spec["group_scales"]
            gelu_source = source
        else:
            logs = np.log2(input_scales)
            edges = np.linspace(
                float(np.min(logs)), float(np.max(logs)), GELU_BUCKETS + 1
            )
            ids = np.clip(
                np.searchsorted(edges, logs, side="right") - 1,
                0,
                GELU_BUCKETS - 1,
            ).astype(np.int16)
            input_group_scales = np.exp2(edges[1:])
            target_scales = input_group_scales[ids]
            ratios = input_scales / target_scales
            x, y, width, height = geometry(orientation, len(vector))
            shape = (height, width)
            save_gray(
                OUT / f"{prefix}-input-ratio.png",
                ratios.reshape(shape),
            )
            gelu_source = f"{prefix}-reencoded"
            primitives.extend(
                (
                    f'<feImage href="{prefix}-input-ratio.png" x="{x}" y="{y}" '
                    f'width="{width}" height="{height}" preserveAspectRatio="none" '
                    f'result="{prefix}-input-ratio"/>',
                    f'<feComposite in="{source}" in2="{prefix}-input-ratio" '
                    f'operator="arithmetic" k1="1" k2="0" k3="-{CENTER}" '
                    f'k4="{CENTER}" result="{gelu_source}"/>',
                )
            )
        output_group_scales = np.empty(GELU_BUCKETS, dtype=np.float64)
        for group in range(GELU_BUCKETS):
            mask = ids == group
            output_group_scales[group] = max(
                float(np.max(np.abs(output[mask]))) if np.any(mask) else 0.0,
                (
                    float(np.max(np.abs(calibration_output[..., mask])))
                    if np.any(mask)
                    else 0.0
                ),
                1e-6,
            ) * BUCKET_HEADROOM
        output_spec = {
            "ids": ids.copy(),
            "group_scales": output_group_scales,
            "scales": output_group_scales[ids],
        }
        length = len(vector)
        x, y, width, height = geometry(orientation, length)
        shape = (height, width)
        grid = np.linspace(0, 1, 256)
        if PACKED_GELU:
            packed_parts: list[str] = []
            for pack_index, first_group in enumerate(range(0, GELU_BUCKETS, 3)):
                groups = list(
                    range(first_group, min(first_group + 3, GELU_BUCKETS))
                )
                mask = np.zeros((*shape, 3), dtype=np.uint8)
                tables: list[str] = []
                for channel, group in enumerate(groups):
                    mask[..., channel] = np.where(ids.reshape(shape) == group, 255, 0)
                    values = gelu_new(
                        (grid - CENTER) * 2 * input_group_scales[group]
                    )
                    encoded = np.clip(
                        CENTER + values / (2 * output_group_scales[group]), 0, 1
                    )
                    tables.append(" ".join(f"{value:.8g}" for value in encoded))
                while len(tables) < 3:
                    tables.append("0 0")
                mask_path = OUT / f"{prefix}-pack{pack_index}-mask.png"
                Image.fromarray(mask, mode="RGB").save(mask_path, optimize=True)
                raw = f"{prefix}-pack{pack_index}-raw"
                selected = f"{prefix}-pack{pack_index}-selected"
                common = f"{prefix}-pack{pack_index}-common"
                primitives.extend(
                    (
                        f'<feComponentTransfer in="{gelu_source}" result="{raw}">'
                        f'<feFuncR type="table" tableValues="{tables[0]}"/>'
                        f'<feFuncG type="table" tableValues="{tables[1]}"/>'
                        f'<feFuncB type="table" tableValues="{tables[2]}"/>'
                        '<feFuncA type="identity"/></feComponentTransfer>',
                        f'<feImage href="{mask_path.name}" x="{x}" y="{y}" '
                        f'width="{width}" height="{height}" '
                        f'preserveAspectRatio="none" result="{prefix}-pack{pack_index}-mask"/>',
                        f'<feComposite in="{raw}" '
                        f'in2="{prefix}-pack{pack_index}-mask" '
                        f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                        f'result="{selected}"/>',
                        f'<feColorMatrix in="{selected}" '
                        f'values="1 1 1 0 0  1 1 1 0 0  1 1 1 0 0  0 0 0 0 1" '
                        f'result="{common}"/>',
                    )
                )
                packed_parts.append(common)
            packed_result = packed_parts[0]
            for pack_index, part in enumerate(packed_parts[1:], 1):
                combined = f"{prefix}-pack-sum{pack_index}"
                primitives.append(
                    f'<feComposite in="{packed_result}" in2="{part}" '
                    f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                    f'result="{combined}"/>'
                )
                packed_result = combined
            return (
                packed_result,
                output,
                calibration_output,
                output_spec,
            )

        parts: list[str] = []
        for group in range(GELU_BUCKETS):
            mask = ids == group
            save_gray(OUT / f"{prefix}-g{group}-mask.png", mask.reshape(shape))
            values = gelu_new((grid - CENTER) * 2 * input_group_scales[group])
            positive = " ".join(
                f"{value:.8g}"
                for value in np.clip(values, 0, None) / output_group_scales[group]
            )
            negative = " ".join(
                f"{value:.8g}"
                for value in np.clip(-values, 0, None) / output_group_scales[group]
            )
            raw = f"{prefix}-g{group}-raw"
            part = f"{prefix}-g{group}-signed"
            primitives.extend(
                (
                    f'<feComponentTransfer in="{gelu_source}" result="{raw}">'
                    f'<feFuncR type="table" tableValues="{positive}"/>'
                    f'<feFuncG type="table" tableValues="{negative}"/>'
                    '<feFuncB type="table" tableValues="0 0"/>'
                    '<feFuncA type="identity"/></feComponentTransfer>',
                    f'<feImage href="{prefix}-g{group}-mask.png" x="{x}" y="{y}" '
                    f'width="{width}" height="{height}" preserveAspectRatio="none" '
                    f'result="{prefix}-g{group}-mask"/>',
                    f'<feComposite in="{raw}" in2="{prefix}-g{group}-mask" '
                    f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                    f'result="{part}"/>',
                )
            )
            parts.append(part)
        result = parts[0]
        for group, part in enumerate(parts[1:], 1):
            combined = f"{prefix}-sum{group}"
            primitives.append(
                f'<feComposite in="{result}" in2="{part}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="0" result="{combined}"/>'
            )
            result = combined
        return result, output, calibration_output, output_spec

    def append_bucketed_block(
        block_index: int,
        input_vector: np.ndarray,
        calibration_input: np.ndarray,
        input_spec: dict[str, np.ndarray],
        input_orientation: str,
        prefix: str,
        initial_href: str | None = None,
    ) -> dict[str, object]:
        block_data = model_data(block_index, input_vector)
        correction = (
            correction_payload["blocks"][block_index]
            if correction_payload is not None
            else None
        )
        input_name = f"{prefix}-x"
        ln1_begin = len(primitives)
        if initial_href is not None:
            x, y, width, height = geometry(input_orientation, WIDTH)
            primitives.append(
                f'<feImage href="{initial_href}" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{input_name}"/>'
            )
        ln1_output, normalized1, calibration_normalized1, ln1_spec = (
            scaled_layernorm_stage(
                input_name,
                input_vector,
                calibration_input,
                input_spec,
                block_data["ln1_gamma"],
                block_data["ln1_beta"],
                input_orientation,
                f"{prefix}-ln1",
            )
        )
        ln1_finish = len(primitives)

        composed_weight = block_data["attn_proj_weight"] @ block_data["v_weight"]
        composed_bias = (
            block_data["attn_proj_weight"] @ block_data["v_bias"]
            + block_data["attn_proj_bias"]
        )
        q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
        attention_begin = len(primitives)
        learned_source, _, learned, calibration_learned, learned_spec = (
            bucketed_matrix_stage(
                ln1_output,
                normalized1,
                calibration_normalized1,
                ln1_spec,
                q_attention.reconstructed,
                composed_bias,
                input_orientation,
                f"{prefix}-attention",
                runtime_bias=(
                    composed_bias + np.asarray(correction["attention"])
                    if correction is not None
                    else None
                ),
            )
        )
        rotated_input = bucketed_rotate_stage(
            input_name,
            input_vector,
            calibration_input,
            input_spec,
            input_orientation,
            f"{prefix}-skip",
        )
        middle_orientation = "v" if input_orientation == "h" else "h"
        residual_source, residual, calibration_residual, residual_spec = (
            bucketed_add_stage(
                learned_source,
                learned,
                calibration_learned,
                learned_spec,
                rotated_input,
                input_vector,
                calibration_input,
                input_spec,
                middle_orientation,
                f"{prefix}-attention-residual",
            )
        )
        attention_finish = len(primitives)

        ln2_begin = len(primitives)
        ln2_output, normalized2, calibration_normalized2, ln2_spec = (
            scaled_layernorm_stage(
                residual_source,
                residual,
                calibration_residual,
                residual_spec,
                block_data["ln2_gamma"],
                block_data["ln2_beta"],
                middle_orientation,
                f"{prefix}-ln2",
            )
        )
        ln2_finish = len(primitives)

        q_fc = quantize_float_rows(block_data["fc_weight"], bits=QUANT_BITS)
        fc_begin = len(primitives)
        pre_source, _, pre, calibration_pre, pre_spec = bucketed_matrix_stage(
            ln2_output,
            normalized2,
            calibration_normalized2,
            ln2_spec,
            q_fc.reconstructed,
            block_data["fc_bias"],
            middle_orientation,
            f"{prefix}-fc",
            bucket_output=True,
            runtime_bias=(
                block_data["fc_bias"] + np.asarray(correction["fc"])
                if correction is not None
                else None
            ),
        )
        hidden_encoded, hidden, calibration_hidden, hidden_spec = (
            bucketed_gelu_stage(
                pre_source,
                pre,
                calibration_pre,
                pre_spec,
                input_orientation,
                f"{prefix}-gelu",
            )
        )
        if PACKED_GELU:
            hidden_common = hidden_encoded
        else:
            hidden_common = f"{prefix}-hidden-common"
            primitives.append(
                f'<feColorMatrix in="{hidden_encoded}" values="{signed_to_common}" '
                f'result="{hidden_common}"/>'
            )
        fc_finish = len(primitives)

        q_projection = quantize_float_rows(
            block_data["mlp_proj_weight"], bits=QUANT_BITS
        )
        projection_begin = len(primitives)
        projection_source, _, projection, calibration_projection, projection_spec = (
            bucketed_matrix_stage(
                hidden_common,
                hidden,
                calibration_hidden,
                hidden_spec,
                q_projection.reconstructed,
                block_data["mlp_proj_bias"],
                input_orientation,
                f"{prefix}-projection",
                runtime_bias=(
                    block_data["mlp_proj_bias"]
                    + np.asarray(correction["projection"])
                    if correction is not None
                    else None
                ),
            )
        )
        output_source, output, calibration_output, output_spec = bucketed_add_stage(
            projection_source,
            projection,
            calibration_projection,
            projection_spec,
            residual_source,
            residual,
            calibration_residual,
            residual_spec,
            middle_orientation,
            f"{prefix}-output",
        )
        projection_finish = len(primitives)
        return {
            "index": block_index,
            "prefix": prefix,
            "input_orientation": input_orientation,
            "output_orientation": middle_orientation,
            "input_spec": input_spec,
            "output_spec": output_spec,
            "ln1_spec": ln1_spec,
            "attention_learned_spec": learned_spec,
            "attention_residual_spec": residual_spec,
            "ln2_spec": ln2_spec,
            "fc_pre_spec": pre_spec,
            "fc_hidden_spec": hidden_spec,
            "projection_spec": projection_spec,
            "ln1_slice": (ln1_begin, ln1_finish),
            "attention_slice": (attention_begin, attention_finish),
            "ln2_slice": (ln2_begin, ln2_finish),
            "fc_slice": (fc_begin, fc_finish),
            "projection_slice": (projection_begin, projection_finish),
            "input_name": input_name,
            "ln1_output": ln1_output,
            "residual_source": residual_source,
            "ln2_output": ln2_output,
            "hidden_common": hidden_common,
            "output_source": output_source,
            "output": output,
            "calibration_output": calibration_output,
        }

    def rotate_grouped_stage(
        source: str,
        vector: np.ndarray,
        calibration_vector: np.ndarray,
        normal_range: float,
        outlier_range: float,
        orientation: str,
        prefix: str,
    ) -> str:
        mask = np.zeros(WIDTH, dtype=bool)
        mask[list(OUTLIER_DIMS)] = True
        normal_vector = np.where(~mask, vector, 0.0)
        outlier_vector = np.where(mask, vector, 0.0)
        calibration_normal = np.where(~mask, calibration_vector, 0.0)
        calibration_outlier = np.where(mask, calibration_vector, 0.0)
        copy_green = "0 1 0 0 0  " * 3 + "0 0 0 0 1"
        primitives.extend(
            (
                f'<feColorMatrix in="{source}" values="{copy_red}" '
                f'result="{prefix}-normal-common"/>',
                f'<feColorMatrix in="{source}" values="{copy_green}" '
                f'result="{prefix}-outlier-common"/>',
            )
        )
        normal_signed = split_signed(
            f"{prefix}-normal-common", f"{prefix}-normal-input"
        )
        outlier_signed = split_signed(
            f"{prefix}-outlier-common", f"{prefix}-outlier-input"
        )
        normal_rotated, _, _, _ = matrix_stage(
            normal_signed,
            normal_vector,
            normal_range,
            np.eye(WIDTH),
            np.zeros(WIDTH),
            orientation,
            f"{prefix}-normal-rotate",
            calibration_vector=calibration_normal,
        )
        outlier_rotated, _, _, _ = matrix_stage(
            outlier_signed,
            outlier_vector,
            outlier_range,
            np.eye(WIDTH),
            np.zeros(WIDTH),
            orientation,
            f"{prefix}-outlier-rotate",
            calibration_vector=calibration_outlier,
        )
        return pack_grouped_planes(normal_rotated, outlier_rotated, f"{prefix}-rotated")

    def append_grouped_block(
        block_index: int,
        input_vector: np.ndarray,
        calibration_input: np.ndarray,
        input_orientation: str,
        prefix: str,
        initial_href: str | None = None,
    ) -> dict[str, object]:
        block_data = model_data(block_index, input_vector)
        input_normal_range, input_outlier_range = grouped_ranges(
            input_vector, calibration_input
        )
        input_name = f"{prefix}-x"
        ln1_begin = len(primitives)
        if initial_href is not None:
            x, y, width, height = geometry(input_orientation, WIDTH)
            primitives.append(
                f'<feImage href="{initial_href}" x="{x}" y="{y}" '
                f'width="{width}" height="{height}" preserveAspectRatio="none" '
                f'result="{input_name}"/>'
            )
        ln1_output, normalized1, normalized1_range = grouped_layernorm_stage(
            input_name,
            input_vector,
            calibration_input,
            input_normal_range,
            input_outlier_range,
            block_data["ln1_gamma"],
            block_data["ln1_beta"],
            input_orientation,
            f"{prefix}-ln1",
        )
        normalized1_signed = split_signed(ln1_output, f"{prefix}-ln1")
        ln1_finish = len(primitives)
        calibration_normalized1 = layer_norm(
            calibration_input, block_data["ln1_gamma"], block_data["ln1_beta"]
        )

        composed_weight = block_data["attn_proj_weight"] @ block_data["v_weight"]
        composed_bias = (
            block_data["attn_proj_weight"] @ block_data["v_bias"]
            + block_data["attn_proj_bias"]
        )
        q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
        calibration_learned = (
            q_attention.reconstructed @ calibration_normalized1 + composed_bias
        )
        attention_begin = len(primitives)
        learned_gray, _, learned, learned_range = matrix_stage(
            normalized1_signed,
            normalized1,
            normalized1_range,
            q_attention.reconstructed,
            composed_bias,
            input_orientation,
            f"{prefix}-attention",
            calibration_vector=calibration_normalized1,
        )
        rotated_input = rotate_grouped_stage(
            input_name,
            input_vector,
            calibration_input,
            input_normal_range,
            input_outlier_range,
            input_orientation,
            f"{prefix}-skip",
        )
        residual = learned + input_vector
        calibration_residual = calibration_learned + calibration_input
        middle_orientation = "v" if input_orientation == "h" else "h"
        residual_grouped, residual_normal_range, residual_outlier_range = (
            add_to_grouped_stage(
                learned_gray,
                learned_range,
                rotated_input,
                input_normal_range,
                input_outlier_range,
                residual,
                calibration_residual,
                middle_orientation,
                f"{prefix}-attention-residual",
            )
        )
        attention_finish = len(primitives)

        ln2_begin = len(primitives)
        ln2_output, normalized2, normalized2_range = grouped_layernorm_stage(
            residual_grouped,
            residual,
            calibration_residual,
            residual_normal_range,
            residual_outlier_range,
            block_data["ln2_gamma"],
            block_data["ln2_beta"],
            middle_orientation,
            f"{prefix}-ln2",
        )
        normalized2_signed = split_signed(ln2_output, f"{prefix}-ln2")
        ln2_finish = len(primitives)
        calibration_normalized2 = layer_norm(
            calibration_residual,
            block_data["ln2_gamma"],
            block_data["ln2_beta"],
        )

        q_fc = quantize_float_rows(block_data["fc_weight"], bits=QUANT_BITS)
        calibration_pre = (
            q_fc.reconstructed @ calibration_normalized2 + block_data["fc_bias"]
        )
        fc_begin = len(primitives)
        pre_gray, _, pre, pre_range = matrix_stage(
            normalized2_signed,
            normalized2,
            normalized2_range,
            q_fc.reconstructed,
            block_data["fc_bias"],
            middle_orientation,
            f"{prefix}-fc",
            calibration_vector=calibration_normalized2,
        )
        hidden = gelu_new(pre)
        calibration_hidden = gelu_new(calibration_pre)
        hidden_range = float(
            max(np.max(np.abs(hidden)), np.max(np.abs(calibration_hidden))) * 1.05
        )
        grid = np.linspace(0, 1, 256)
        hidden_grid = gelu_new((grid - CENTER) * 2 * pre_range)
        positive_table = " ".join(
            f"{value:.8g}" for value in np.clip(hidden_grid, 0, None) / hidden_range
        )
        negative_table = " ".join(
            f"{value:.8g}" for value in np.clip(-hidden_grid, 0, None) / hidden_range
        )
        hidden_signed = f"{prefix}-hidden-signed"
        primitives.append(
            f'<feComponentTransfer in="{pre_gray}" result="{hidden_signed}">'
            f'<feFuncR type="table" tableValues="{positive_table}"/>'
            f'<feFuncG type="table" tableValues="{negative_table}"/>'
            '<feFuncB type="table" tableValues="0 0"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )
        fc_finish = len(primitives)

        q_projection = quantize_float_rows(
            block_data["mlp_proj_weight"], bits=QUANT_BITS
        )
        calibration_projection = (
            q_projection.reconstructed @ calibration_hidden
            + block_data["mlp_proj_bias"]
        )
        projection_begin = len(primitives)
        projection_gray, _, projection, projection_range = matrix_stage(
            hidden_signed,
            hidden,
            hidden_range,
            q_projection.reconstructed,
            block_data["mlp_proj_bias"],
            input_orientation,
            f"{prefix}-projection",
            calibration_vector=calibration_hidden,
        )
        output = projection + residual
        calibration_output = calibration_projection + calibration_residual
        output_grouped, output_normal_range, output_outlier_range = (
            add_to_grouped_stage(
                projection_gray,
                projection_range,
                residual_grouped,
                residual_normal_range,
                residual_outlier_range,
                output,
                calibration_output,
                middle_orientation,
                f"{prefix}-output",
            )
        )
        projection_finish = len(primitives)
        return {
            "index": block_index,
            "prefix": prefix,
            "input_orientation": input_orientation,
            "output_orientation": middle_orientation,
            "input_normal_range": input_normal_range,
            "input_outlier_range": input_outlier_range,
            "residual_normal_range": residual_normal_range,
            "residual_outlier_range": residual_outlier_range,
            "output_normal_range": output_normal_range,
            "output_outlier_range": output_outlier_range,
            "ln1_slice": (ln1_begin, ln1_finish),
            "attention_slice": (attention_begin, attention_finish),
            "ln2_slice": (ln2_begin, ln2_finish),
            "fc_slice": (fc_begin, fc_finish),
            "projection_slice": (projection_begin, projection_finish),
            "input_name": input_name,
            "ln1_output": ln1_output,
            "residual_grouped": residual_grouped,
            "ln2_output": ln2_output,
            "hidden_signed": hidden_signed,
            "output_grouped": output_grouped,
            "normalized1": normalized1,
            "normalized1_range": normalized1_range,
            "residual": residual,
            "normalized2": normalized2,
            "normalized2_range": normalized2_range,
            "hidden": hidden,
            "hidden_range": hidden_range,
            "output": output,
            "calibration_output": calibration_output,
        }

    if helper_sink is not None:
        # Export the existing SVG emitters without compiling any one-token
        # shortcut graph. Callers supply their own connected causal topology.
        helper_sink.update(locals())
        return

    x = data["x"]
    x_range = float(np.max(np.abs(x)) * 1.05)
    save_gray(OUT / "x.png", (CENTER + x / (2 * x_range))[None, :])
    save_gray(OUT / "x-alt.png", (CENTER - x / (2 * x_range))[None, :])
    ln1_start = len(primitives)
    primitives.append(f'<feImage href="x.png" x="0" y="{CY}" width="{WIDTH}" height="1" preserveAspectRatio="none" result="x"/>')
    x_signed = split_signed("x", "x-input")
    _, n1_signed, n1, n1_range = layernorm_stage("x", x, x_range, data["ln1_gamma"], data["ln1_beta"], "h", "ln1")
    ln1_end = len(primitives)
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    qa = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    attention_start = len(primitives)
    attention_gray, _, attention_output, attention_range = matrix_stage(
        n1_signed,
        n1,
        n1_range,
        qa.reconstructed,
        composed_bias,
        "h",
        "attention-affine",
    )
    skip_gray, _, skip_output, skip_range = matrix_stage(
        x_signed,
        x,
        x_range,
        np.eye(WIDTH),
        np.zeros(WIDTH),
        "h",
        "attention-skip",
    )
    residual = attention_output + skip_output
    residual_range = float(np.max(np.abs(residual)) * 1.05)
    attention_coef = attention_range / residual_range
    skip_coef = skip_range / residual_range
    primitives.append(
        f'<feComposite in="{attention_gray}" in2="{skip_gray}" '
        f'operator="arithmetic" k1="0" k2="{attention_coef}" '
        f'k3="{skip_coef}" k4="{CENTER * (1 - attention_coef - skip_coef)}" '
        'result="attention-common"/>'
    )
    residual_gray = "attention-common"
    attention_end = len(primitives)

    if os.environ.get("SVG_FILTER_LN_FUSION_ONLY") == "1":
        # Compare the ordinary materialized LayerNorm -> matrix path above with
        # an algebraically fused consumer. The fused path keeps only the live
        # mean/variance/gain calculation, applies W*gamma directly to x-mean,
        # then broadcasts the scalar gain after the reduction. It never emits
        # the 768-value normalized LayerNorm output.
        fusion_start = len(primitives)
        mean = float(np.mean(x))
        diff = x - mean
        variance = float(np.mean(diff**2))
        gain = 1 / np.sqrt(variance + EPSILON)
        diff_range = float(np.max(np.abs(diff)) * 1.02)
        normalized = diff * gain
        normalized_range = float(np.max(np.abs(normalized)) * 1.02)
        gamma_weight = qa.reconstructed * data["ln1_gamma"][None, :]
        # Center each row so B@x == (W*gamma)@(x-mean(x)). This removes the
        # live mean from the matrix consumer entirely; only inverse stddev is
        # broadcast after the reduction.
        fused_weight = gamma_weight - np.mean(gamma_weight, axis=1, keepdims=True)
        fused_constant = (
            qa.reconstructed @ data["ln1_beta"] + composed_bias
        )
        _, fused_reduced_signed, fused_reduced, fused_reduced_range = matrix_stage(
            x_signed,
            x,
            x_range,
            fused_weight,
            np.zeros(WIDTH),
            "h",
            "ln-fusion-matrix",
        )
        fused_linear = fused_reduced * gain
        fused_linear_range = float(np.max(np.abs(fused_linear)) * 1.05)
        fused_output = fused_linear + fused_constant
        fused_output_range = float(np.max(np.abs(fused_output)) * 1.05)
        gain_coefficient = (
            fused_reduced_range
            * normalized_range
            / (diff_range * fused_linear_range)
        )
        primitives.extend(
            (
                '<feOffset in="ln1-gain-scalar" dx="-255" x="0" y="0" '
                'width="1" height="1" result="ln-fusion-gain-origin"/>',
                '<feTile in="ln-fusion-gain-origin" x="255" y="0" width="1" '
                'height="768" result="ln-fusion-gain"/>',
                f'<feComposite in="{fused_reduced_signed}" '
                'in2="ln-fusion-gain" operator="arithmetic" '
                f'k1="{gain_coefficient}" k2="0" k3="0" k4="0" '
                'result="ln-fusion-linear-signed"/>',
            )
        )
        fused_to_common_coefficient = fused_linear_range / (
            2 * fused_output_range
        )
        fused_to_common = (
            f"{fused_to_common_coefficient} -{fused_to_common_coefficient} "
            f"0 0 {center_css}  " * 3 + "0 0 0 0 1"
        )
        save_gray(
            OUT / "ln-fusion-constant.png",
            (CENTER + fused_constant / (2 * fused_output_range)).reshape(WIDTH, 1),
        )
        primitives.extend(
            (
                '<feColorMatrix in="ln-fusion-linear-signed" '
                f'values="{fused_to_common}" result="ln-fusion-linear"/>',
                '<feImage href="ln-fusion-constant.png" x="255" y="0" '
                'width="1" height="768" preserveAspectRatio="none" '
                'result="ln-fusion-constant"/>',
                '<feComposite in="ln-fusion-linear" in2="ln-fusion-constant" '
                'operator="arithmetic" k1="0" k2="1" k3="1" '
                f'k4="-{center_css}" result="ln-fusion-output"/>',
            )
        )
        fusion_end = len(primitives)
        ln_stats_end = next(
            index + 1
            for index in range(ln1_start, ln1_end)
            if 'result="ln1-gain-scalar"' in primitives[index]
        )

        def fusion_page(title: str, body: str, output: str) -> str:
            return (
                '<!doctype html><meta charset="utf-8">'
                f'<title>{title}</title>'
                '<style>html,body{margin:0;background:black}'
                'svg{display:block;image-rendering:pixelated}</style>'
                '<svg width="1" height="768" viewBox="0 0 1 768" '
                'xmlns="http://www.w3.org/2000/svg"><defs>'
                '<filter id="test" filterUnits="userSpaceOnUse" '
                'primitiveUnits="userSpaceOnUse" x="0" y="0" width="768" '
                f'height="768" color-interpolation-filters="{FILTER_COLOR}">'
                + body
                + f'<feOffset in="{output}" dx="-255" x="0" y="0" '
                'width="1" height="768"/></filter></defs>'
                '<rect width="768" height="768" fill="white" '
                'filter="url(#test)"/></svg>'
            )

        baseline_html = fusion_page(
            "Materialized LayerNorm consumer",
            "".join(primitives[ln1_start:attention_end]),
            attention_gray,
        )
        fused_html = fusion_page(
            "Fused LayerNorm consumer",
            "".join(primitives[ln1_start:ln_stats_end])
            + "".join(primitives[fusion_start:fusion_end]),
            "ln-fusion-output",
        )
        (OUT / "materialized.html").write_text(baseline_html)
        (OUT / "fused.html").write_text(fused_html)
        (OUT / "reference.json").write_text(
            json.dumps(
                {
                    "expected": attention_output.tolist(),
                    "algebraic_expected": fused_output.tolist(),
                    "baseline_range": attention_range,
                    "fused_range": fused_output_range,
                    "baseline_primitives": attention_end - ln1_start,
                    "fused_primitives": (ln_stats_end - ln1_start)
                    + (fusion_end - fusion_start),
                    "baseline_html_bytes": len(baseline_html.encode()),
                    "fused_html_bytes": len(fused_html.encode()),
                    "algebraic_max_error": float(
                        np.max(np.abs(attention_output - fused_output))
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        print(
            {
                "output": str(OUT),
                "baseline_primitives": attention_end - ln1_start,
                "fused_primitives": (ln_stats_end - ln1_start)
                + (fusion_end - fusion_start),
            }
        )
        return

    ln2_start = len(primitives)
    _, n2_signed, n2, n2_range = layernorm_stage(residual_gray, residual, residual_range, data["ln2_gamma"], data["ln2_beta"], "v", "ln2")
    ln2_end = len(primitives)
    qfc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fc_start = len(primitives)
    pre_gray, _, pre, pre_range = matrix_stage(n2_signed, n2, n2_range, qfc.reconstructed, data["fc_bias"], "v", "fc")
    pre_grid = np.linspace(0, 1, 256)
    hidden_range = float(np.max(np.abs(gelu_new(pre))) * 1.05)
    hidden_values = gelu_new((pre_grid - CENTER) * 2 * pre_range)
    pos_table = " ".join(f"{v:.8g}" for v in np.clip(hidden_values, 0, None) / hidden_range)
    neg_table = " ".join(f"{v:.8g}" for v in np.clip(-hidden_values, 0, None) / hidden_range)
    primitives.append(f'<feComponentTransfer in="{pre_gray}" result="hidden-signed"><feFuncR type="table" tableValues="{pos_table}"/><feFuncG type="table" tableValues="{neg_table}"/><feFuncB type="table" tableValues="0 0"/><feFuncA type="identity"/></feComponentTransfer>')
    fc_end = len(primitives)
    hidden = gelu_new(pre)
    qproj = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    projection_start = len(primitives)
    projection_gray, _, projection, projection_range = matrix_stage(
        "hidden-signed",
        hidden,
        hidden_range,
        qproj.reconstructed,
        data["mlp_proj_bias"],
        "h",
        "projection",
    )
    final = projection + residual
    final_range = float(np.max(np.abs(final)) * 1.05)
    projection_coef = projection_range / final_range
    residual_coef = residual_range / final_range
    primitives.append(
        f'<feComposite in="{projection_gray}" in2="{residual_gray}" '
        f'operator="arithmetic" k1="0" k2="{projection_coef}" '
        f'k3="{residual_coef}" '
        f'k4="{CENTER * (1 - projection_coef - residual_coef)}" '
        'result="block-common"/>'
    )
    primitives.append(
        f'<feColorMatrix in="block-common" values="{copy_red}" result="block-output"/>'
    )
    projection_end = len(primitives)

    def block_reference(input_vector: np.ndarray) -> np.ndarray:
        normalized1 = layer_norm(input_vector, data["ln1_gamma"], data["ln1_beta"])
        reference_residual = qa.reconstructed @ normalized1 + composed_bias + input_vector
        normalized2 = layer_norm(
            reference_residual,
            data["ln2_gamma"],
            data["ln2_beta"],
        )
        reference_hidden = gelu_new(qfc.reconstructed @ normalized2 + data["fc_bias"])
        return (
            qproj.reconstructed @ reference_hidden
            + data["mlp_proj_bias"]
            + reference_residual
        )

    expected_alt = block_reference(-x)

    # A second, independently weighted GPT-2 block consumes block 0's live output.
    # Its layout is transposed (vertical in, horizontal out), so the two blocks can
    # be chained without a separate transpose/readback stage.
    data1 = model_data(1, final)
    group_mask = np.zeros(WIDTH, dtype=bool)
    group_mask[list(OUTLIER_DIMS)] = True
    group_normal_range = float(
        max(
            np.max(np.abs(final[~group_mask])),
            np.max(np.abs(expected_alt[~group_mask])),
        )
        * 1.05
    )
    group_outlier_range = float(
        max(
            np.max(np.abs(final[group_mask])),
            np.max(np.abs(expected_alt[group_mask])),
        )
        * 1.05
    )

    def save_grouped_input(path: Path, value: np.ndarray) -> None:
        normal = np.full(WIDTH, CENTER)
        outlier = np.full(WIDTH, CENTER)
        normal[~group_mask] = (
            CENTER + value[~group_mask] / (2 * group_normal_range)
        )
        outlier[group_mask] = (
            CENTER + value[group_mask] / (2 * group_outlier_range)
        )
        save_grouped_rg(path, normal[None, :], outlier[None, :])

    save_grouped_input(OUT / "grouped-ln-x.png", final)
    save_grouped_input(OUT / "grouped-ln-x-alt.png", expected_alt)
    grouped_ln_start = len(primitives)
    primitives.append(
        f'<feImage href="grouped-ln-x.png" x="0" y="{CY}" width="{WIDTH}" '
        'height="1" preserveAspectRatio="none" result="grouped-ln-x"/>'
    )
    grouped_ln_output, grouped_ln_expected, grouped_ln_range = grouped_layernorm_stage(
        "grouped-ln-x",
        final,
        expected_alt,
        group_normal_range,
        group_outlier_range,
        data1["ln1_gamma"],
        data1["ln1_beta"],
        "h",
        "grouped-ln",
    )
    grouped_ln_end = len(primitives)
    grouped_ln_expected_alt = layer_norm(
        expected_alt, data1["ln1_gamma"], data1["ln1_beta"]
    )
    grouped_ln_filter = (
        '<filter id="grouped-ln-filter" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="768" height="256" '
        f'color-interpolation-filters="{FILTER_COLOR}">'
        + "".join(primitives[grouped_ln_start:grouped_ln_end])
        + f'<feOffset in="{grouped_ln_output}" dy="-{CY}" x="0" y="0" '
        'width="768" height="1"/></filter>'
    )
    grouped_ln_html = (
        '<!doctype html><meta charset="utf-8"><title>Two-scale grouped layer norm</title>'
        '<style>html,body{margin:0;background:black}svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + grouped_ln_filter
        + '</defs><rect width="768" height="256" fill="white" '
        'filter="url(#grouped-ln-filter)"/></svg>'
    )
    (OUT / "grouped-layernorm.html").write_text(grouped_ln_html)
    block1_start = len(primitives)
    b1_ln1_start = len(primitives)
    b1_x_signed = split_signed("b1-x", "b1-x-input")
    _, b1_n1_signed, b1_n1, b1_n1_range = layernorm_stage(
        "b1-x",
        final,
        final_range,
        data1["ln1_gamma"],
        data1["ln1_beta"],
        "v",
        "b1-ln1",
    )
    b1_ln1_end = len(primitives)

    b1_composed_weight = data1["attn_proj_weight"] @ data1["v_weight"]
    b1_composed_bias = (
        data1["attn_proj_weight"] @ data1["v_bias"]
        + data1["attn_proj_bias"]
    )
    b1_qa = quantize_float_rows(b1_composed_weight, bits=QUANT_BITS)
    b1_attention_start = len(primitives)
    b1_attention_gray, _, b1_attention_output, b1_attention_range = matrix_stage(
        b1_n1_signed,
        b1_n1,
        b1_n1_range,
        b1_qa.reconstructed,
        b1_composed_bias,
        "v",
        "b1-attention-affine",
    )
    b1_skip_gray, _, b1_skip_output, b1_skip_range = matrix_stage(
        b1_x_signed,
        final,
        final_range,
        np.eye(WIDTH),
        np.zeros(WIDTH),
        "v",
        "b1-attention-skip",
    )
    b1_residual = b1_attention_output + b1_skip_output
    b1_residual_range = float(np.max(np.abs(b1_residual)) * 1.05)
    b1_attention_coef = b1_attention_range / b1_residual_range
    b1_skip_coef = b1_skip_range / b1_residual_range
    primitives.append(
        f'<feComposite in="{b1_attention_gray}" in2="{b1_skip_gray}" '
        f'operator="arithmetic" k1="0" k2="{b1_attention_coef}" '
        f'k3="{b1_skip_coef}" '
        f'k4="{CENTER * (1 - b1_attention_coef - b1_skip_coef)}" '
        'result="b1-attention-common"/>'
    )
    b1_residual_gray = "b1-attention-common"
    b1_attention_end = len(primitives)

    b1_ln2_start = len(primitives)
    _, b1_n2_signed, b1_n2, b1_n2_range = layernorm_stage(
        b1_residual_gray,
        b1_residual,
        b1_residual_range,
        data1["ln2_gamma"],
        data1["ln2_beta"],
        "h",
        "b1-ln2",
    )
    b1_ln2_end = len(primitives)

    b1_qfc = quantize_float_rows(data1["fc_weight"], bits=QUANT_BITS)
    b1_fc_start = len(primitives)
    b1_pre_gray, _, b1_pre, b1_pre_range = matrix_stage(
        b1_n2_signed,
        b1_n2,
        b1_n2_range,
        b1_qfc.reconstructed,
        data1["fc_bias"],
        "h",
        "b1-fc",
    )
    b1_pre_grid = np.linspace(0, 1, 256)
    b1_hidden = gelu_new(b1_pre)
    b1_hidden_range = float(np.max(np.abs(b1_hidden)) * 1.05)
    b1_hidden_values = gelu_new((b1_pre_grid - CENTER) * 2 * b1_pre_range)
    b1_pos_table = " ".join(
        f"{value:.8g}"
        for value in np.clip(b1_hidden_values, 0, None) / b1_hidden_range
    )
    b1_neg_table = " ".join(
        f"{value:.8g}"
        for value in np.clip(-b1_hidden_values, 0, None) / b1_hidden_range
    )
    primitives.append(
        '<feComponentTransfer in="b1-fc-common" result="b1-hidden-signed">'
        f'<feFuncR type="table" tableValues="{b1_pos_table}"/>'
        f'<feFuncG type="table" tableValues="{b1_neg_table}"/>'
        '<feFuncB type="table" tableValues="0 0"/>'
        '<feFuncA type="identity"/></feComponentTransfer>'
    )
    b1_fc_end = len(primitives)

    b1_qproj = quantize_float_rows(data1["mlp_proj_weight"], bits=QUANT_BITS)
    b1_projection_start = len(primitives)
    b1_projection_gray, _, b1_projection, b1_projection_range = matrix_stage(
        "b1-hidden-signed",
        b1_hidden,
        b1_hidden_range,
        b1_qproj.reconstructed,
        data1["mlp_proj_bias"],
        "v",
        "b1-projection",
    )
    b1_final = b1_projection + b1_residual
    b1_final_range = float(np.max(np.abs(b1_final)) * 1.05)
    b1_projection_coef = b1_projection_range / b1_final_range
    b1_residual_coef = b1_residual_range / b1_final_range
    primitives.append(
        f'<feComposite in="{b1_projection_gray}" in2="{b1_residual_gray}" '
        f'operator="arithmetic" k1="0" k2="{b1_projection_coef}" '
        f'k3="{b1_residual_coef}" '
        f'k4="{CENTER * (1 - b1_projection_coef - b1_residual_coef)}" '
        'result="b1-block-common"/>'
    )
    b1_projection_end = len(primitives)
    block1_end = len(primitives)

    def block1_reference(input_vector: np.ndarray) -> np.ndarray:
        normalized1 = layer_norm(
            input_vector, data1["ln1_gamma"], data1["ln1_beta"]
        )
        reference_residual = (
            b1_qa.reconstructed @ normalized1 + b1_composed_bias + input_vector
        )
        normalized2 = layer_norm(
            reference_residual, data1["ln2_gamma"], data1["ln2_beta"]
        )
        reference_hidden = gelu_new(
            b1_qfc.reconstructed @ normalized2 + data1["fc_bias"]
        )
        return (
            b1_qproj.reconstructed @ reference_hidden
            + data1["mlp_proj_bias"]
            + reference_residual
        )

    b1_expected_alt = block1_reference(expected_alt)

    def append_additional_block(
        block_index: int,
        input_vector: np.ndarray,
        alternate_input: np.ndarray,
        input_range: float,
        input_orientation: str,
    ) -> dict[str, object]:
        prefix = f"b{block_index}"
        block_data = model_data(block_index, input_vector)
        source_name = f"{prefix}-x"

        ln1_begin = len(primitives)
        x_signed_name = split_signed(source_name, f"{prefix}-x-input")
        alternate_normalized1 = layer_norm(
            alternate_input,
            block_data["ln1_gamma"],
            block_data["ln1_beta"],
        )
        _, normalized1_signed, normalized1, normalized1_range = layernorm_stage(
            source_name,
            input_vector,
            input_range,
            block_data["ln1_gamma"],
            block_data["ln1_beta"],
            input_orientation,
            f"{prefix}-ln1",
            calibration_vector=alternate_input,
        )
        ln1_finish = len(primitives)

        composed = block_data["attn_proj_weight"] @ block_data["v_weight"]
        composed_bias = (
            block_data["attn_proj_weight"] @ block_data["v_bias"]
            + block_data["attn_proj_bias"]
        )
        q_attention = quantize_float_rows(composed, bits=QUANT_BITS)
        alternate_learned = (
            q_attention.reconstructed @ alternate_normalized1 + composed_bias
        )
        attention_begin = len(primitives)
        learned_gray, _, learned, learned_range = matrix_stage(
            normalized1_signed,
            normalized1,
            normalized1_range,
            q_attention.reconstructed,
            composed_bias,
            input_orientation,
            f"{prefix}-attention-affine",
            calibration_vector=alternate_normalized1,
        )
        identity_gray, _, identity_value, identity_range = matrix_stage(
            x_signed_name,
            input_vector,
            input_range,
            np.eye(WIDTH),
            np.zeros(WIDTH),
            input_orientation,
            f"{prefix}-attention-skip",
            calibration_vector=alternate_input,
        )
        residual_value = learned + identity_value
        alternate_residual = alternate_learned + alternate_input
        residual_value_range = float(
            max(
                np.max(np.abs(residual_value)),
                np.max(np.abs(alternate_residual)),
            )
            * 1.05
        )
        learned_coef = learned_range / residual_value_range
        identity_coef = identity_range / residual_value_range
        residual_name = f"{prefix}-attention-common"
        primitives.append(
            f'<feComposite in="{learned_gray}" in2="{identity_gray}" '
            f'operator="arithmetic" k1="0" k2="{learned_coef}" '
            f'k3="{identity_coef}" '
            f'k4="{CENTER * (1 - learned_coef - identity_coef)}" '
            f'result="{residual_name}"/>'
        )
        attention_finish = len(primitives)

        middle_orientation = "v" if input_orientation == "h" else "h"
        ln2_begin = len(primitives)
        alternate_normalized2 = layer_norm(
            alternate_residual,
            block_data["ln2_gamma"],
            block_data["ln2_beta"],
        )
        _, normalized2_signed, normalized2, normalized2_range = layernorm_stage(
            residual_name,
            residual_value,
            residual_value_range,
            block_data["ln2_gamma"],
            block_data["ln2_beta"],
            middle_orientation,
            f"{prefix}-ln2",
            calibration_vector=alternate_residual,
        )
        ln2_finish = len(primitives)

        q_fc = quantize_float_rows(block_data["fc_weight"], bits=QUANT_BITS)
        alternate_pre = (
            q_fc.reconstructed @ alternate_normalized2 + block_data["fc_bias"]
        )
        fc_begin = len(primitives)
        pre_gray, _, pre_value, pre_value_range = matrix_stage(
            normalized2_signed,
            normalized2,
            normalized2_range,
            q_fc.reconstructed,
            block_data["fc_bias"],
            middle_orientation,
            f"{prefix}-fc",
            calibration_vector=alternate_normalized2,
        )
        hidden_value = gelu_new(pre_value)
        alternate_hidden = gelu_new(alternate_pre)
        hidden_value_range = float(
            max(
                np.max(np.abs(hidden_value)),
                np.max(np.abs(alternate_hidden)),
            )
            * 1.05
        )
        grid = np.linspace(0, 1, 256)
        gelu_grid = gelu_new((grid - CENTER) * 2 * pre_value_range)
        positive_table = " ".join(
            f"{value:.8g}"
            for value in np.clip(gelu_grid, 0, None) / hidden_value_range
        )
        negative_table = " ".join(
            f"{value:.8g}"
            for value in np.clip(-gelu_grid, 0, None) / hidden_value_range
        )
        hidden_name = f"{prefix}-hidden-signed"
        primitives.append(
            f'<feComponentTransfer in="{pre_gray}" result="{hidden_name}">'
            f'<feFuncR type="table" tableValues="{positive_table}"/>'
            f'<feFuncG type="table" tableValues="{negative_table}"/>'
            '<feFuncB type="table" tableValues="0 0"/>'
            '<feFuncA type="identity"/></feComponentTransfer>'
        )
        fc_finish = len(primitives)

        q_projection = quantize_float_rows(
            block_data["mlp_proj_weight"], bits=QUANT_BITS
        )
        alternate_projection = (
            q_projection.reconstructed @ alternate_hidden
            + block_data["mlp_proj_bias"]
        )
        projection_begin = len(primitives)
        projection_gray, _, projection_value, projection_value_range = matrix_stage(
            hidden_name,
            hidden_value,
            hidden_value_range,
            q_projection.reconstructed,
            block_data["mlp_proj_bias"],
            input_orientation,
            f"{prefix}-projection",
            calibration_vector=alternate_hidden,
        )
        output_value = projection_value + residual_value
        alternate_output = alternate_projection + alternate_residual
        output_value_range = float(
            max(
                np.max(np.abs(output_value)),
                np.max(np.abs(alternate_output)),
            )
            * 1.05
        )
        projection_coef = projection_value_range / output_value_range
        residual_coef = residual_value_range / output_value_range
        output_name = f"{prefix}-block-common"
        primitives.append(
            f'<feComposite in="{projection_gray}" in2="{residual_name}" '
            f'operator="arithmetic" k1="0" k2="{projection_coef}" '
            f'k3="{residual_coef}" '
            f'k4="{CENTER * (1 - projection_coef - residual_coef)}" '
            f'result="{output_name}"/>'
        )
        projection_finish = len(primitives)

        return {
            "index": block_index,
            "prefix": prefix,
            "input_orientation": input_orientation,
            "output_orientation": middle_orientation,
            "input_range": input_range,
            "ln1_slice": (ln1_begin, ln1_finish),
            "attention_slice": (attention_begin, attention_finish),
            "ln2_slice": (ln2_begin, ln2_finish),
            "fc_slice": (fc_begin, fc_finish),
            "projection_slice": (projection_begin, projection_finish),
            "output": output_value,
            "alternate_output": alternate_output,
            "output_range": output_value_range,
        }

    additional_blocks: list[dict[str, object]] = []
    current_vector = b1_final
    current_alternate = b1_expected_alt
    current_range = b1_final_range
    current_orientation = "h"
    for block_index in range(2, 12):
        block = append_additional_block(
            block_index,
            current_vector,
            current_alternate,
            current_range,
            current_orientation,
        )
        additional_blocks.append(block)
        current_vector = np.asarray(block["output"])
        current_alternate = np.asarray(block["alternate_output"])
        current_range = float(block["output_range"])
        current_orientation = str(block["output_orientation"])

    final_gamma, final_beta = final_layer_norm_data()
    final_ln_start = len(primitives)
    _, _, final_normalized, final_normalized_range = layernorm_stage(
        "final-x",
        current_vector,
        current_range,
        final_gamma,
        final_beta,
        current_orientation,
        "final-ln",
        calibration_vector=current_alternate,
    )
    final_ln_end = len(primitives)
    alternate_final_normalized = layer_norm(
        current_alternate, final_gamma, final_beta
    )

    grouped_x_normal_range, grouped_x_outlier_range = grouped_ranges(x, -x)
    grouped_x_mask = np.zeros(WIDTH, dtype=bool)
    grouped_x_mask[list(OUTLIER_DIMS)] = True

    def save_grouped_state(
        path: Path,
        value: np.ndarray,
        normal_range: float,
        outlier_range: float,
        orientation: str,
    ) -> None:
        normal = np.full(WIDTH, CENTER)
        outlier = np.full(WIDTH, CENTER)
        normal[~grouped_x_mask] = (
            CENTER + value[~grouped_x_mask] / (2 * normal_range)
        )
        outlier[grouped_x_mask] = (
            CENTER + value[grouped_x_mask] / (2 * outlier_range)
        )
        shape = (1, WIDTH) if orientation == "h" else (WIDTH, 1)
        save_grouped_rg(path, normal.reshape(shape), outlier.reshape(shape))

    save_grouped_state(
        OUT / "grouped-x.png",
        x,
        grouped_x_normal_range,
        grouped_x_outlier_range,
        "h",
    )
    save_grouped_state(
        OUT / "grouped-x-alt.png",
        -x,
        grouped_x_normal_range,
        grouped_x_outlier_range,
        "h",
    )
    grouped_block0 = append_grouped_block(
        0, x, -x, "h", "g0", initial_href="grouped-x.png"
    )
    grouped_block1 = append_grouped_block(
        1,
        np.asarray(grouped_block0["output"]),
        np.asarray(grouped_block0["calibration_output"]),
        str(grouped_block0["output_orientation"]),
        "g1",
    )
    grouped_blocks = [grouped_block0, grouped_block1]
    grouped_current = np.asarray(grouped_block1["output"])
    grouped_calibration_current = np.asarray(
        grouped_block1["calibration_output"]
    )
    grouped_orientation = str(grouped_block1["output_orientation"])
    for grouped_block_index in range(2, 12):
        next_grouped_block = append_grouped_block(
            grouped_block_index,
            grouped_current,
            grouped_calibration_current,
            grouped_orientation,
            f"g{grouped_block_index}",
        )
        grouped_blocks.append(next_grouped_block)
        grouped_current = np.asarray(next_grouped_block["output"])
        grouped_calibration_current = np.asarray(
            next_grouped_block["calibration_output"]
        )
        grouped_orientation = str(next_grouped_block["output_orientation"])

    grouped_final_ln_start = len(primitives)
    grouped_final_ln_output, grouped_final_expected, grouped_final_ln_range = (
        grouped_layernorm_stage(
            "grouped-final-x",
            grouped_current,
            grouped_calibration_current,
            float(grouped_blocks[-1]["output_normal_range"]),
            float(grouped_blocks[-1]["output_outlier_range"]),
            final_gamma,
            final_beta,
            grouped_orientation,
            "grouped-final-ln",
        )
    )
    grouped_final_ln_end = len(primitives)
    grouped_final_expected_alt = layer_norm(
        grouped_calibration_current, final_gamma, final_beta
    )

    calibration_token_ids = tuple(
        int(value)
        for value in os.environ.get("SVG_FILTER_CALIBRATION_TOKEN_IDS", "").split(",")
        if value.strip()
    )
    if calibration_token_ids:
        calibration_tensors = SafeTensors(MODEL_PATH)
        calibration_embedding = np.asarray(
            calibration_tensors.tensor("wte.weight"), dtype=np.float64
        )
        calibration_position = np.asarray(
            calibration_tensors.tensor("wpe.weight")[0], dtype=np.float64
        )
        calibration_inputs = np.stack(
            [
                calibration_embedding[token_id] + calibration_position
                for token_id in calibration_token_ids
            ]
        )
        calibration_inputs = np.concatenate(((-x)[None, :], calibration_inputs))
        bucket_x_spec = bucket_spec_from_bound(
            np.max(np.abs(calibration_inputs), axis=0)
        )
    else:
        bucket_x_spec = bucket_spec(x, -x)
    save_bucketed_state(OUT / "bucket-x.png", x, bucket_x_spec, "h")
    save_bucketed_state(OUT / "bucket-x-alt.png", -x, bucket_x_spec, "h")
    bucket_blocks: list[dict[str, object]] = []
    bucket_current = x
    bucket_calibration_current = (
        calibration_inputs if calibration_token_ids else -x
    )
    bucket_current_spec = bucket_x_spec
    bucket_orientation = "h"
    for bucket_block_index in range(12):
        bucket_block = append_bucketed_block(
            bucket_block_index,
            bucket_current,
            bucket_calibration_current,
            bucket_current_spec,
            bucket_orientation,
            f"k{bucket_block_index}",
            initial_href="bucket-x.png" if bucket_block_index == 0 else None,
        )
        bucket_blocks.append(bucket_block)
        bucket_current = np.asarray(bucket_block["output"])
        bucket_calibration_current = np.asarray(
            bucket_block["calibration_output"]
        )
        bucket_current_spec = bucket_block["output_spec"]
        bucket_orientation = str(bucket_block["output_orientation"])

    bucket_final_ln_start = len(primitives)
    bucket_final_ln_output, bucket_final_expected, bucket_final_expected_alt, bucket_final_spec = (
        scaled_layernorm_stage(
            "bucket-final-x",
            bucket_current,
            bucket_calibration_current,
            bucket_current_spec,
            final_gamma,
            final_beta,
            bucket_orientation,
            "bucket-final-ln",
            runtime_beta=(
                final_beta + np.asarray(correction_payload["final"])
                if correction_payload is not None
                else None
            ),
        )
    )
    bucket_final_ln_end = len(primitives)

    def grouped_chain_specs(
        block: dict[str, object], first: bool = False
    ) -> list[tuple[str, int, int, str, int, int]]:
        prefix = str(block["prefix"])
        orientation = str(block["input_orientation"])
        input_name = str(block["input_name"])
        ln1_output = str(block["ln1_output"])
        residual_grouped = str(block["residual_grouped"])
        ln2_output = str(block["ln2_output"])
        hidden_signed = str(block["hidden_signed"])
        output_grouped = str(block["output_grouped"])
        ln1_begin, ln1_finish = block["ln1_slice"]
        attention_begin, attention_finish = block["attention_slice"]
        ln2_begin, ln2_finish = block["ln2_slice"]
        fc_begin, fc_finish = block["fc_slice"]
        projection_begin, projection_finish = block["projection_slice"]

        if orientation == "h":
            ln1_input = "" if first else (
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{input_name}"/>'
            )
            return [
                (
                    f"chain-{prefix}-ln1", 768, 256,
                    ln1_input + "".join(primitives[ln1_begin:ln1_finish])
                    + f'<feOffset in="{ln1_output}" dy="-255" x="0" y="0" '
                    f'width="768" height="1" result="{prefix}-ln1-boundary"/>'
                    + f'<feOffset in="{input_name}" dy="-254" x="0" y="1" '
                    f'width="768" height="1" result="{prefix}-input-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-ln1-boundary"/>'
                    f'<feMergeNode in="{prefix}-input-boundary"/></feMerge>', 768, 1,
                ),
                (
                    f"chain-{prefix}-attention", 768, 768,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="768" height="1" result="{prefix}-ln1-common"/>'
                    + split_markup(f"{prefix}-ln1-common", f"{prefix}-ln1-signed")
                    + '<feOffset in="SourceGraphic" dy="254" x="0" y="255" '
                    f'width="768" height="1" result="{input_name}"/>'
                    + "".join(primitives[attention_begin:attention_finish])
                    + f'<feOffset in="{residual_grouped}" dx="-255" '
                    'x="0" y="0" width="1" height="768"/>', 1, 768,
                ),
                (
                    f"chain-{prefix}-ln2", 256, 768,
                    '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                    f'width="1" height="768" result="{residual_grouped}"/>'
                    + "".join(primitives[ln2_begin:ln2_finish])
                    + f'<feOffset in="{ln2_output}" dx="-255" x="0" y="0" '
                    f'width="1" height="768" result="{prefix}-ln2-boundary"/>'
                    + '<feOffset in="SourceGraphic" dx="1" x="1" y="0" '
                    f'width="1" height="768" result="{prefix}-residual-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-ln2-boundary"/>'
                    f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 1, 768,
                ),
                (
                    f"chain-{prefix}-fc", 3073, 768,
                    '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                    f'width="1" height="768" result="{prefix}-ln2-common"/>'
                    + split_markup(f"{prefix}-ln2-common", f"{prefix}-ln2-signed")
                    + "".join(primitives[fc_begin:fc_finish])
                    + f'<feColorMatrix in="{hidden_signed}" values="{signed_to_common}" '
                    f'result="{prefix}-hidden-common"/>'
                    + f'<feOffset in="{prefix}-hidden-common" dy="-255" x="0" y="0" '
                    f'width="3072" height="1" result="{prefix}-hidden-boundary"/>'
                    + '<feOffset in="SourceGraphic" dx="3071" x="3072" y="0" '
                    f'width="1" height="768" result="{prefix}-residual-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-hidden-boundary"/>'
                    f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 3072, 1,
                ),
                (
                    f"chain-{prefix}-projection", 3073, 768,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="3072" height="1" result="{prefix}-hidden-common"/>'
                    + split_markup(f"{prefix}-hidden-common", hidden_signed)
                    + '<feOffset in="SourceGraphic" dx="-2817" x="255" y="0" '
                    f'width="1" height="768" result="{residual_grouped}"/>'
                    + "".join(primitives[projection_begin:projection_finish])
                    + f'<feOffset in="{output_grouped}" dx="-255" '
                    'x="0" y="0" width="1" height="768"/>', 1, 768,
                ),
            ]

        ln1_input = "" if first else (
            '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
            f'width="1" height="768" result="{input_name}"/>'
        )
        return [
            (
                f"chain-{prefix}-ln1", 256, 768,
                ln1_input + "".join(primitives[ln1_begin:ln1_finish])
                + f'<feOffset in="{ln1_output}" dx="-255" x="0" y="0" '
                f'width="1" height="768" result="{prefix}-ln1-boundary"/>'
                + f'<feOffset in="{input_name}" dx="-254" x="1" y="0" '
                f'width="1" height="768" result="{prefix}-input-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-ln1-boundary"/>'
                f'<feMergeNode in="{prefix}-input-boundary"/></feMerge>', 1, 768,
            ),
            (
                f"chain-{prefix}-attention", 768, 768,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="768" result="{prefix}-ln1-common"/>'
                + split_markup(f"{prefix}-ln1-common", f"{prefix}-ln1-signed")
                + '<feOffset in="SourceGraphic" dx="254" x="255" y="0" '
                f'width="1" height="768" result="{input_name}"/>'
                + "".join(primitives[attention_begin:attention_finish])
                + f'<feOffset in="{residual_grouped}" dy="-255" '
                'x="0" y="0" width="768" height="1"/>', 768, 1,
            ),
            (
                f"chain-{prefix}-ln2", 768, 256,
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{residual_grouped}"/>'
                + "".join(primitives[ln2_begin:ln2_finish])
                + f'<feOffset in="{ln2_output}" dy="-255" x="0" y="0" '
                f'width="768" height="1" result="{prefix}-ln2-boundary"/>'
                + '<feOffset in="SourceGraphic" dy="1" x="0" y="1" '
                f'width="768" height="1" result="{prefix}-residual-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-ln2-boundary"/>'
                f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 768, 1,
            ),
            (
                f"chain-{prefix}-fc", 768, 3073,
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{prefix}-ln2-common"/>'
                + split_markup(f"{prefix}-ln2-common", f"{prefix}-ln2-signed")
                + "".join(primitives[fc_begin:fc_finish])
                + f'<feColorMatrix in="{hidden_signed}" values="{signed_to_common}" '
                f'result="{prefix}-hidden-common"/>'
                + f'<feOffset in="{prefix}-hidden-common" dx="-255" x="0" y="0" '
                f'width="1" height="3072" result="{prefix}-hidden-boundary"/>'
                + '<feOffset in="SourceGraphic" dy="3071" x="0" y="3072" '
                f'width="768" height="1" result="{prefix}-residual-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-hidden-boundary"/>'
                f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 1, 3072,
            ),
            (
                f"chain-{prefix}-projection", 768, 3073,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="3072" result="{prefix}-hidden-common"/>'
                + split_markup(f"{prefix}-hidden-common", hidden_signed)
                + '<feOffset in="SourceGraphic" dy="-2817" x="0" y="255" '
                f'width="768" height="1" result="{residual_grouped}"/>'
                + "".join(primitives[projection_begin:projection_finish])
                + f'<feOffset in="{output_grouped}" dy="-255" '
                'x="0" y="0" width="768" height="1"/>', 768, 1,
            ),
        ]

    grouped_specs = [
        spec
        for index, block in enumerate(grouped_blocks)
        for spec in grouped_chain_specs(block, first=index == 0)
    ]
    grouped_filters = []
    for filter_id, work_width, work_height, body, _, _ in grouped_specs:
        grouped_filters.append(
            f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
            f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
            f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">'
            f'{body}</filter>'
        )
    grouped_filter_value = " ".join(
        f'url(#{spec[0]})' for spec in grouped_specs[:10]
    )
    grouped_one_filter_value = " ".join(
        f'url(#{spec[0]})' for spec in grouped_specs[:5]
    )
    grouped_one_block_html = (
        '<!doctype html><meta charset="utf-8"><title>Two-scale one-block GPT-2</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="1" height="768" viewBox="0 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(grouped_filters)
        + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
        f'fill="white" style="filter:{grouped_one_filter_value}"/></svg>'
    )
    (OUT / "grouped-chain-1block.html").write_text(grouped_one_block_html)
    grouped_two_block_html = (
        '<!doctype html><meta charset="utf-8"><title>Two-scale two-block GPT-2</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(grouped_filters)
        + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
        f'fill="white" style="filter:{grouped_filter_value}"/></svg>'
    )
    (OUT / "grouped-chain-2blocks.html").write_text(grouped_two_block_html)
    grouped_twelve_filter_value = " ".join(
        f'url(#{spec[0]})' for spec in grouped_specs
    )
    grouped_twelve_html = (
        '<!doctype html><meta charset="utf-8"><title>Two-scale twelve-block GPT-2</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(grouped_filters)
        + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
        f'fill="white" style="filter:{grouped_twelve_filter_value}"/></svg>'
    )
    (OUT / "grouped-chain-12blocks.html").write_text(grouped_twelve_html)

    grouped_final_ln_body = (
        '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
        'width="768" height="1" result="grouped-final-x"/>'
        + "".join(primitives[grouped_final_ln_start:grouped_final_ln_end])
        + f'<feOffset in="{grouped_final_ln_output}" dy="-255" x="0" y="0" '
        'width="768" height="1"/>'
    )
    grouped_final_filter = (
        '<filter id="chain-grouped-final-ln" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="768" height="256" '
        f'color-interpolation-filters="{FILTER_COLOR}">{grouped_final_ln_body}</filter>'
    )
    grouped_final_filter_value = (
        grouped_twelve_filter_value + " url(#chain-grouped-final-ln)"
    )
    grouped_final_html = (
        '<!doctype html><meta charset="utf-8"><title>Two-scale full GPT-2 state</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(grouped_filters)
        + grouped_final_filter
        + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
        f'fill="white" style="filter:{grouped_final_filter_value}"/></svg>'
    )
    (OUT / "grouped-chain-12blocks-final-ln.html").write_text(grouped_final_html)

    def bucket_chain_specs(
        block: dict[str, object], first: bool = False
    ) -> list[tuple[str, int, int, str]]:
        prefix = str(block["prefix"])
        orientation = str(block["input_orientation"])
        input_name = str(block["input_name"])
        ln1_output = str(block["ln1_output"])
        residual_source = str(block["residual_source"])
        ln2_output = str(block["ln2_output"])
        hidden_common = str(block["hidden_common"])
        output_source = str(block["output_source"])
        ln1_begin, ln1_finish = block["ln1_slice"]
        attention_begin, attention_finish = block["attention_slice"]
        ln2_begin, ln2_finish = block["ln2_slice"]
        fc_begin, fc_finish = block["fc_slice"]
        projection_begin, projection_finish = block["projection_slice"]
        if orientation == "h":
            ln1_input = "" if first else (
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{input_name}"/>'
            )
            return [
                (
                    f"bucket-{prefix}-ln1", 768, 256,
                    ln1_input + "".join(primitives[ln1_begin:ln1_finish])
                    + f'<feOffset in="{ln1_output}" dy="-255" x="0" y="0" '
                    f'width="768" height="1" result="{prefix}-ln1-boundary"/>'
                    + f'<feOffset in="{input_name}" dy="-254" x="0" y="1" '
                    f'width="768" height="1" result="{prefix}-input-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-ln1-boundary"/>'
                    f'<feMergeNode in="{prefix}-input-boundary"/></feMerge>',
                ),
                (
                    f"bucket-{prefix}-attention", 768, 768,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="768" height="1" result="{ln1_output}"/>'
                    + '<feOffset in="SourceGraphic" dy="254" x="0" y="255" '
                    f'width="768" height="1" result="{input_name}"/>'
                    + "".join(primitives[attention_begin:attention_finish])
                    + f'<feOffset in="{residual_source}" dx="-255" '
                    'x="0" y="0" width="1" height="768"/>',
                ),
                (
                    f"bucket-{prefix}-ln2", 256, 768,
                    '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                    f'width="1" height="768" result="{residual_source}"/>'
                    + "".join(primitives[ln2_begin:ln2_finish])
                    + f'<feOffset in="{ln2_output}" dx="-255" x="0" y="0" '
                    f'width="1" height="768" result="{prefix}-ln2-boundary"/>'
                    + '<feOffset in="SourceGraphic" dx="1" x="1" y="0" '
                    f'width="1" height="768" result="{prefix}-residual-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-ln2-boundary"/>'
                    f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>',
                ),
                (
                    f"bucket-{prefix}-fc", 3073, 768,
                    '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                    f'width="1" height="768" result="{ln2_output}"/>'
                    + "".join(primitives[fc_begin:fc_finish])
                    + f'<feOffset in="{hidden_common}" dy="-255" x="0" y="0" '
                    f'width="3072" height="1" result="{prefix}-hidden-boundary"/>'
                    + '<feOffset in="SourceGraphic" dx="3071" x="3072" y="0" '
                    f'width="1" height="768" result="{prefix}-residual-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-hidden-boundary"/>'
                    f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>',
                ),
                (
                    f"bucket-{prefix}-projection", 3073, 768,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="3072" height="1" result="{hidden_common}"/>'
                    + '<feOffset in="SourceGraphic" dx="-2817" x="255" y="0" '
                    f'width="1" height="768" result="{residual_source}"/>'
                    + "".join(primitives[projection_begin:projection_finish])
                    + f'<feOffset in="{output_source}" dx="-255" '
                    'x="0" y="0" width="1" height="768"/>',
                ),
            ]
        ln1_input = "" if first else (
            '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
            f'width="1" height="768" result="{input_name}"/>'
        )
        return [
            (
                f"bucket-{prefix}-ln1", 256, 768,
                ln1_input + "".join(primitives[ln1_begin:ln1_finish])
                + f'<feOffset in="{ln1_output}" dx="-255" x="0" y="0" '
                f'width="1" height="768" result="{prefix}-ln1-boundary"/>'
                + f'<feOffset in="{input_name}" dx="-254" x="1" y="0" '
                f'width="1" height="768" result="{prefix}-input-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-ln1-boundary"/>'
                f'<feMergeNode in="{prefix}-input-boundary"/></feMerge>',
            ),
            (
                f"bucket-{prefix}-attention", 768, 768,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="768" result="{ln1_output}"/>'
                + '<feOffset in="SourceGraphic" dx="254" x="255" y="0" '
                f'width="1" height="768" result="{input_name}"/>'
                + "".join(primitives[attention_begin:attention_finish])
                + f'<feOffset in="{residual_source}" dy="-255" '
                'x="0" y="0" width="768" height="1"/>',
            ),
            (
                f"bucket-{prefix}-ln2", 768, 256,
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{residual_source}"/>'
                + "".join(primitives[ln2_begin:ln2_finish])
                + f'<feOffset in="{ln2_output}" dy="-255" x="0" y="0" '
                f'width="768" height="1" result="{prefix}-ln2-boundary"/>'
                + '<feOffset in="SourceGraphic" dy="1" x="0" y="1" '
                f'width="768" height="1" result="{prefix}-residual-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-ln2-boundary"/>'
                f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>',
            ),
            (
                f"bucket-{prefix}-fc", 768, 3073,
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{ln2_output}"/>'
                + "".join(primitives[fc_begin:fc_finish])
                + f'<feOffset in="{hidden_common}" dx="-255" x="0" y="0" '
                f'width="1" height="3072" result="{prefix}-hidden-boundary"/>'
                + '<feOffset in="SourceGraphic" dy="3071" x="0" y="3072" '
                f'width="768" height="1" result="{prefix}-residual-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-hidden-boundary"/>'
                f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>',
            ),
            (
                f"bucket-{prefix}-projection", 768, 3073,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="3072" result="{hidden_common}"/>'
                + '<feOffset in="SourceGraphic" dy="-2817" x="0" y="255" '
                f'width="768" height="1" result="{residual_source}"/>'
                + "".join(primitives[projection_begin:projection_finish])
                + f'<feOffset in="{output_source}" dy="-255" '
                'x="0" y="0" width="768" height="1"/>',
            ),
        ]

    bucket_specs = [
        spec
        for index, block in enumerate(bucket_blocks)
        for spec in bucket_chain_specs(block, first=index == 0)
    ]
    bucket_filters = [
        f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
        f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">'
        f'{body}</filter>'
        for filter_id, work_width, work_height, body in bucket_specs
    ]
    bucket_filter_value = " ".join(f'url(#{spec[0]})' for spec in bucket_specs)
    bucket_html = (
        '<!doctype html><meta charset="utf-8"><title>16-scale twelve-block GPT-2</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(bucket_filters)
        + f'</defs><rect width="{HIDDEN}" height="{HIDDEN}" fill="white" '
        f'style="filter:{bucket_filter_value}"/></svg>'
    )
    (OUT / "bucket-chain-12blocks.html").write_text(bucket_html)

    bucket_final_body = (
        '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
        'width="768" height="1" result="bucket-final-x"/>'
        + "".join(primitives[bucket_final_ln_start:bucket_final_ln_end])
        + f'<feOffset in="{bucket_final_ln_output}" dy="-255" '
        'x="0" y="0" width="768" height="1"/>'
    )
    bucket_final_filter = (
        '<filter id="bucket-final" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="768" height="256" '
        f'color-interpolation-filters="{FILTER_COLOR}">{bucket_final_body}</filter>'
    )
    bucket_final_html = (
        '<!doctype html><meta charset="utf-8"><title>16-scale full GPT-2 state</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(bucket_filters)
        + bucket_final_filter
        + f'</defs><rect width="{HIDDEN}" height="{HIDDEN}" fill="white" '
        f'style="filter:{bucket_filter_value} url(#bucket-final)"/></svg>'
    )
    (OUT / "bucket-chain-12blocks-final-ln.html").write_text(bucket_final_html)

    html = f'''<!doctype html><meta charset="utf-8"><title>Connected SVG-filter GPT-2 block</title>
<style>html,body{{margin:0;background:black}}svg{{display:block;width:{HIDDEN}px;height:{WIDTH}px;image-rendering:pixelated}}</style>
<svg viewBox="0 0 {HIDDEN} {WIDTH}" xmlns="http://www.w3.org/2000/svg"><filter id="block" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" x="0" y="0" width="{HIDDEN}" height="{WIDTH}" color-interpolation-filters="{FILTER_COLOR}">{''.join(primitives[:projection_end])}</filter><rect width="{HIDDEN}" height="{WIDTH}" fill="white" filter="url(#block)"/></svg>'''
    (OUT / "index.html").write_text(html)
    stage_specs = [
        (
            "ln1-stage",
            "ln1-filter",
            768,
            256,
            "0 0 768 1",
            "".join(primitives[ln1_start:ln1_end])
            + '<feOffset in="ln1-signed" dx="0" dy="-255" x="0" y="0" '
            'width="768" height="1"/>',
        ),
        (
            "attention-stage",
            "attention-filter",
            256,
            768,
            "0 0 1 768",
            '<feImage href="#ln1-stage" x="0" y="255" width="768" height="1" '
            'preserveAspectRatio="none" result="ln1-signed"/>'
            + "".join(primitives[attention_start:attention_end])
            + '<feOffset in="attention-common" dx="-255" dy="0" x="0" y="0" '
            'width="1" height="768"/>',
        ),
        (
            "ln2-stage",
            "ln2-filter",
            256,
            768,
            "0 0 1 768",
            '<feImage href="#attention-stage" x="255" y="0" width="1" height="768" '
            'preserveAspectRatio="none" result="attention-common"/>'
            + "".join(primitives[ln2_start:ln2_end])
            + '<feOffset in="ln2-signed" dx="-255" dy="0" x="0" y="0" '
            'width="1" height="768"/>',
        ),
        (
            "fc-stage",
            "fc-filter",
            3072,
            256,
            "0 0 3072 1",
            '<feImage href="#ln2-stage" x="255" y="0" width="1" height="768" '
            'preserveAspectRatio="none" result="ln2-signed"/>'
            + "".join(primitives[fc_start:fc_end])
            + '<feOffset in="hidden-signed" dx="0" dy="-255" x="0" y="0" '
            'width="3072" height="1"/>',
        ),
        (
            "projection-stage",
            "projection-filter",
            256,
            768,
            "0 0 1 768",
            '<feImage href="#fc-stage" x="0" y="255" width="3072" height="1" '
            'preserveAspectRatio="none" result="hidden-signed"/>'
            + "".join(primitives[projection_start:projection_end])
            + '<feOffset in="projection-common" dx="-255" dy="0" x="0" y="0" '
            'width="1" height="768"/>',
        ),
    ]

    chain_specs = [
        (
            "chain-ln1",
            768,
            256,
            "".join(primitives[ln1_start:ln1_end])
            + '<feOffset in="ln1-out" dx="0" dy="-255" x="0" y="0" '
            'width="768" height="1" result="ln1-boundary"/>'
            + '<feOffset in="x" dx="0" dy="-254" x="0" y="1" '
            'width="768" height="1" result="x-boundary"/>'
            + '<feMerge><feMergeNode in="ln1-boundary"/>'
            '<feMergeNode in="x-boundary"/></feMerge>',
            768,
            1,
        ),
        (
            "chain-attention",
            768,
            768,
            '<feOffset in="SourceGraphic" dx="0" dy="255" x="0" y="255" '
            'width="768" height="1" result="ln1-common"/>'
            + split_markup("ln1-common", "ln1-signed")
            + '<feOffset in="SourceGraphic" dx="0" dy="254" x="0" y="255" '
            'width="768" height="1" result="x-common"/>'
            + split_markup("x-common", "x-input-signed")
            + "".join(primitives[attention_start:attention_end])
            + '<feOffset in="attention-common" dx="-255" dy="0" x="0" y="0" '
            'width="1" height="768"/>',
            1,
            768,
        ),
        (
            "chain-ln2",
            256,
            768,
            '<feOffset in="SourceGraphic" dx="255" dy="0" x="255" y="0" '
            'width="1" height="768" result="attention-common"/>'
            + "".join(primitives[ln2_start:ln2_end])
            + '<feOffset in="ln2-out" dx="-255" dy="0" x="0" y="0" '
            'width="1" height="768" result="ln2-boundary"/>'
            + '<feOffset in="SourceGraphic" dx="1" dy="0" x="1" y="0" '
            'width="1" height="768" result="residual-boundary"/>'
            + '<feMerge><feMergeNode in="ln2-boundary"/>'
            '<feMergeNode in="residual-boundary"/></feMerge>',
            1,
            768,
        ),
        (
            "chain-fc",
            3073,
            768,
            '<feOffset in="SourceGraphic" dx="255" dy="0" x="255" y="0" '
            'width="1" height="768" result="ln2-common"/>'
            + split_markup("ln2-common", "ln2-signed")
            + "".join(primitives[fc_start:fc_end])
            + f'<feColorMatrix in="hidden-signed" values="{signed_to_common}" '
            'result="hidden-common"/>'
            + '<feOffset in="hidden-common" dx="0" dy="-255" x="0" y="0" '
            'width="3072" height="1" result="hidden-boundary"/>'
            + '<feOffset in="SourceGraphic" dx="3071" dy="0" x="3072" y="0" '
            'width="1" height="768" result="residual-boundary"/>'
            + '<feMerge><feMergeNode in="hidden-boundary"/>'
            '<feMergeNode in="residual-boundary"/></feMerge>',
            3072,
            1,
        ),
        (
            "chain-projection",
            3073,
            768,
            '<feOffset in="SourceGraphic" dx="0" dy="255" x="0" y="255" '
            'width="3072" height="1" result="hidden-common"/>'
            + split_markup("hidden-common", "hidden-signed")
            + '<feOffset in="SourceGraphic" dx="-2817" dy="0" x="255" y="0" '
            'width="1" height="768" result="attention-common"/>'
            + "".join(primitives[projection_start:projection_end])
            + '<feOffset in="block-common" dx="-255" dy="0" x="0" y="0" '
            'width="1" height="768"/>',
            1,
            768,
        ),
    ]
    chain_filters = []
    for filter_id, work_width, work_height, body, _, _ in chain_specs:
        chain_filters.append(
            f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
            f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
            f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">{body}</filter>'
        )
    for cutoff in range(1, len(chain_specs) + 1):
        _, _, _, _, visible_width, visible_height = chain_specs[cutoff - 1]
        filter_value = " ".join(f'url(#{spec[0]})' for spec in chain_specs[:cutoff])
        chain_html = (
            '<!doctype html><meta charset="utf-8"><title>SVG-filter GPT-2 chain</title>'
            '<style>html,body{margin:0;background:black}svg{display:block;image-rendering:pixelated}</style>'
            f'<svg width="{visible_width}" height="{visible_height}" viewBox="0 0 '
            f'{visible_width} {visible_height}" xmlns="http://www.w3.org/2000/svg"><defs>'
            + "".join(chain_filters)
            + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{WIDTH}" '
            f'fill="white" style="filter:{filter_value}"/></svg>'
        )
        name = "chain.html" if cutoff == len(chain_specs) else f"chain-{cutoff}.html"
        (OUT / name).write_text(chain_html)

    block1_chain_specs = [
        (
            "chain-b1-ln1",
            256,
            768,
            '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
            'width="1" height="768" result="b1-x"/>'
            + "".join(primitives[b1_ln1_start:b1_ln1_end])
            + '<feOffset in="b1-ln1-out" dx="-255" x="0" y="0" '
            'width="1" height="768" result="b1-ln1-boundary"/>'
            + '<feOffset in="SourceGraphic" dx="1" x="1" y="0" '
            'width="1" height="768" result="b1-x-boundary"/>'
            + '<feMerge><feMergeNode in="b1-ln1-boundary"/>'
            '<feMergeNode in="b1-x-boundary"/></feMerge>',
            1,
            768,
        ),
        (
            "chain-b1-attention",
            768,
            768,
            '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
            'width="1" height="768" result="b1-ln1-common"/>'
            + split_markup("b1-ln1-common", "b1-ln1-signed")
            + '<feOffset in="SourceGraphic" dx="254" x="255" y="0" '
            'width="1" height="768" result="b1-x-common"/>'
            + split_markup("b1-x-common", "b1-x-input-signed")
            + "".join(primitives[b1_attention_start:b1_attention_end])
            + '<feOffset in="b1-attention-common" dy="-255" x="0" y="0" '
            'width="768" height="1"/>',
            768,
            1,
        ),
        (
            "chain-b1-ln2",
            768,
            256,
            '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
            'width="768" height="1" result="b1-attention-common"/>'
            + "".join(primitives[b1_ln2_start:b1_ln2_end])
            + '<feOffset in="b1-ln2-out" dy="-255" x="0" y="0" '
            'width="768" height="1" result="b1-ln2-boundary"/>'
            + '<feOffset in="SourceGraphic" dy="1" x="0" y="1" '
            'width="768" height="1" result="b1-residual-boundary"/>'
            + '<feMerge><feMergeNode in="b1-ln2-boundary"/>'
            '<feMergeNode in="b1-residual-boundary"/></feMerge>',
            768,
            1,
        ),
        (
            "chain-b1-fc",
            768,
            3073,
            '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
            'width="768" height="1" result="b1-ln2-common"/>'
            + split_markup("b1-ln2-common", "b1-ln2-signed")
            + "".join(primitives[b1_fc_start:b1_fc_end])
            + f'<feColorMatrix in="b1-hidden-signed" values="{signed_to_common}" '
            'result="b1-hidden-common"/>'
            + '<feOffset in="b1-hidden-common" dx="-255" x="0" y="0" '
            'width="1" height="3072" result="b1-hidden-boundary"/>'
            + '<feOffset in="SourceGraphic" dy="3071" x="0" y="3072" '
            'width="768" height="1" result="b1-residual-boundary"/>'
            + '<feMerge><feMergeNode in="b1-hidden-boundary"/>'
            '<feMergeNode in="b1-residual-boundary"/></feMerge>',
            1,
            3072,
        ),
        (
            "chain-b1-projection",
            768,
            3073,
            '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
            'width="1" height="3072" result="b1-hidden-common"/>'
            + split_markup("b1-hidden-common", "b1-hidden-signed")
            + '<feOffset in="SourceGraphic" dy="-2817" x="0" y="255" '
            'width="768" height="1" result="b1-attention-common"/>'
            + "".join(primitives[b1_projection_start:b1_projection_end])
            + '<feOffset in="b1-block-common" dy="-255" x="0" y="0" '
            'width="768" height="1"/>',
            768,
            1,
        ),
    ]

    def chain_specs_for_additional_block(
        block: dict[str, object],
    ) -> list[tuple[str, int, int, str, int, int]]:
        prefix = str(block["prefix"])
        orientation = str(block["input_orientation"])
        ln1_begin, ln1_finish = block["ln1_slice"]
        attention_begin, attention_finish = block["attention_slice"]
        ln2_begin, ln2_finish = block["ln2_slice"]
        fc_begin, fc_finish = block["fc_slice"]
        projection_begin, projection_finish = block["projection_slice"]

        if orientation == "h":
            return [
                (
                    f"chain-{prefix}-ln1", 768, 256,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="768" height="1" result="{prefix}-x"/>'
                    + "".join(primitives[ln1_begin:ln1_finish])
                    + f'<feOffset in="{prefix}-ln1-out" dy="-255" x="0" y="0" '
                    f'width="768" height="1" result="{prefix}-ln1-boundary"/>'
                    + '<feOffset in="SourceGraphic" dy="1" x="0" y="1" '
                    f'width="768" height="1" result="{prefix}-x-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-ln1-boundary"/>'
                    f'<feMergeNode in="{prefix}-x-boundary"/></feMerge>', 768, 1,
                ),
                (
                    f"chain-{prefix}-attention", 768, 768,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="768" height="1" result="{prefix}-ln1-common"/>'
                    + split_markup(f"{prefix}-ln1-common", f"{prefix}-ln1-signed")
                    + '<feOffset in="SourceGraphic" dy="254" x="0" y="255" '
                    f'width="768" height="1" result="{prefix}-x-common"/>'
                    + split_markup(f"{prefix}-x-common", f"{prefix}-x-input-signed")
                    + "".join(primitives[attention_begin:attention_finish])
                    + f'<feOffset in="{prefix}-attention-common" dx="-255" '
                    'x="0" y="0" width="1" height="768"/>', 1, 768,
                ),
                (
                    f"chain-{prefix}-ln2", 256, 768,
                    '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                    f'width="1" height="768" result="{prefix}-attention-common"/>'
                    + "".join(primitives[ln2_begin:ln2_finish])
                    + f'<feOffset in="{prefix}-ln2-out" dx="-255" x="0" y="0" '
                    f'width="1" height="768" result="{prefix}-ln2-boundary"/>'
                    + '<feOffset in="SourceGraphic" dx="1" x="1" y="0" '
                    f'width="1" height="768" result="{prefix}-residual-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-ln2-boundary"/>'
                    f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 1, 768,
                ),
                (
                    f"chain-{prefix}-fc", 3073, 768,
                    '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                    f'width="1" height="768" result="{prefix}-ln2-common"/>'
                    + split_markup(f"{prefix}-ln2-common", f"{prefix}-ln2-signed")
                    + "".join(primitives[fc_begin:fc_finish])
                    + f'<feColorMatrix in="{prefix}-hidden-signed" '
                    f'values="{signed_to_common}" result="{prefix}-hidden-common"/>'
                    + f'<feOffset in="{prefix}-hidden-common" dy="-255" x="0" y="0" '
                    f'width="3072" height="1" result="{prefix}-hidden-boundary"/>'
                    + '<feOffset in="SourceGraphic" dx="3071" x="3072" y="0" '
                    f'width="1" height="768" result="{prefix}-residual-boundary"/>'
                    + f'<feMerge><feMergeNode in="{prefix}-hidden-boundary"/>'
                    f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 3072, 1,
                ),
                (
                    f"chain-{prefix}-projection", 3073, 768,
                    '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                    f'width="3072" height="1" result="{prefix}-hidden-common"/>'
                    + split_markup(f"{prefix}-hidden-common", f"{prefix}-hidden-signed")
                    + '<feOffset in="SourceGraphic" dx="-2817" x="255" y="0" '
                    f'width="1" height="768" result="{prefix}-attention-common"/>'
                    + "".join(primitives[projection_begin:projection_finish])
                    + f'<feOffset in="{prefix}-block-common" dx="-255" '
                    'x="0" y="0" width="1" height="768"/>', 1, 768,
                ),
            ]
        return [
            (
                f"chain-{prefix}-ln1", 256, 768,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="768" result="{prefix}-x"/>'
                + "".join(primitives[ln1_begin:ln1_finish])
                + f'<feOffset in="{prefix}-ln1-out" dx="-255" x="0" y="0" '
                f'width="1" height="768" result="{prefix}-ln1-boundary"/>'
                + '<feOffset in="SourceGraphic" dx="1" x="1" y="0" '
                f'width="1" height="768" result="{prefix}-x-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-ln1-boundary"/>'
                f'<feMergeNode in="{prefix}-x-boundary"/></feMerge>', 1, 768,
            ),
            (
                f"chain-{prefix}-attention", 768, 768,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="768" result="{prefix}-ln1-common"/>'
                + split_markup(f"{prefix}-ln1-common", f"{prefix}-ln1-signed")
                + '<feOffset in="SourceGraphic" dx="254" x="255" y="0" '
                f'width="1" height="768" result="{prefix}-x-common"/>'
                + split_markup(f"{prefix}-x-common", f"{prefix}-x-input-signed")
                + "".join(primitives[attention_begin:attention_finish])
                + f'<feOffset in="{prefix}-attention-common" dy="-255" '
                'x="0" y="0" width="768" height="1"/>', 768, 1,
            ),
            (
                f"chain-{prefix}-ln2", 768, 256,
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{prefix}-attention-common"/>'
                + "".join(primitives[ln2_begin:ln2_finish])
                + f'<feOffset in="{prefix}-ln2-out" dy="-255" x="0" y="0" '
                f'width="768" height="1" result="{prefix}-ln2-boundary"/>'
                + '<feOffset in="SourceGraphic" dy="1" x="0" y="1" '
                f'width="768" height="1" result="{prefix}-residual-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-ln2-boundary"/>'
                f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 768, 1,
            ),
            (
                f"chain-{prefix}-fc", 768, 3073,
                '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
                f'width="768" height="1" result="{prefix}-ln2-common"/>'
                + split_markup(f"{prefix}-ln2-common", f"{prefix}-ln2-signed")
                + "".join(primitives[fc_begin:fc_finish])
                + f'<feColorMatrix in="{prefix}-hidden-signed" '
                f'values="{signed_to_common}" result="{prefix}-hidden-common"/>'
                + f'<feOffset in="{prefix}-hidden-common" dx="-255" x="0" y="0" '
                f'width="1" height="3072" result="{prefix}-hidden-boundary"/>'
                + '<feOffset in="SourceGraphic" dy="3071" x="0" y="3072" '
                f'width="768" height="1" result="{prefix}-residual-boundary"/>'
                + f'<feMerge><feMergeNode in="{prefix}-hidden-boundary"/>'
                f'<feMergeNode in="{prefix}-residual-boundary"/></feMerge>', 1, 3072,
            ),
            (
                f"chain-{prefix}-projection", 768, 3073,
                '<feOffset in="SourceGraphic" dx="255" x="255" y="0" '
                f'width="1" height="3072" result="{prefix}-hidden-common"/>'
                + split_markup(f"{prefix}-hidden-common", f"{prefix}-hidden-signed")
                + '<feOffset in="SourceGraphic" dy="-2817" x="0" y="255" '
                f'width="768" height="1" result="{prefix}-attention-common"/>'
                + "".join(primitives[projection_begin:projection_finish])
                + f'<feOffset in="{prefix}-block-common" dy="-255" '
                'x="0" y="0" width="768" height="1"/>', 768, 1,
            ),
        ]

    additional_chain_specs = [
        spec
        for block in additional_blocks
        for spec in chain_specs_for_additional_block(block)
    ]
    block1_filters = []
    for filter_id, work_width, work_height, body, _, _ in block1_chain_specs:
        block1_filters.append(
            f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
            f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
            f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">'
            f'{body}</filter>'
        )
    all_chain_specs = chain_specs + block1_chain_specs
    for cutoff in range(len(chain_specs) + 1, len(all_chain_specs) + 1):
        _, _, _, _, visible_width, visible_height = all_chain_specs[cutoff - 1]
        filter_value = " ".join(
            f'url(#{spec[0]})' for spec in all_chain_specs[:cutoff]
        )
        two_block_html = (
            '<!doctype html><meta charset="utf-8">'
            '<title>Two connected SVG-filter GPT-2 blocks</title>'
            '<style>html,body{margin:0;background:black}'
            'svg{display:block;image-rendering:pixelated}</style>'
            f'<svg width="{visible_width}" height="{visible_height}" '
            f'viewBox="0 0 {visible_width} {visible_height}" '
            'xmlns="http://www.w3.org/2000/svg"><defs>'
            + "".join(chain_filters)
            + "".join(block1_filters)
            + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
            f'fill="white" style="filter:{filter_value}"/></svg>'
        )
        name = "chain-2blocks.html" if cutoff == len(all_chain_specs) else f"chain-{cutoff}.html"
        (OUT / name).write_text(two_block_html)

    additional_filters = []
    for filter_id, work_width, work_height, body, _, _ in additional_chain_specs:
        additional_filters.append(
            f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
            f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
            f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">'
            f'{body}</filter>'
        )
    twelve_specs = all_chain_specs + additional_chain_specs
    twelve_filter_value = " ".join(f'url(#{spec[0]})' for spec in twelve_specs)
    _, _, _, _, twelve_width, twelve_height = twelve_specs[-1]
    twelve_html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Twelve connected SVG-filter GPT-2 blocks</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{twelve_width}" height="{twelve_height}" '
        f'viewBox="0 0 {twelve_width} {twelve_height}" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(chain_filters)
        + "".join(block1_filters)
        + "".join(additional_filters)
        + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
        f'fill="white" style="filter:{twelve_filter_value}"/></svg>'
    )
    (OUT / "chain-12blocks.html").write_text(twelve_html)
    final_ln_body = (
        '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
        'width="768" height="1" result="final-x"/>'
        + "".join(primitives[final_ln_start:final_ln_end])
        + '<feOffset in="final-ln-out" dy="-255" x="0" y="0" '
        'width="768" height="1"/>'
    )
    final_ln_filter = (
        '<filter id="chain-final-ln" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="768" '
        f'height="256" color-interpolation-filters="{FILTER_COLOR}">'
        + final_ln_body
        + '</filter>'
    )
    final_ln_filter_value = twelve_filter_value + " url(#chain-final-ln)"
    final_ln_html = (
        '<!doctype html><meta charset="utf-8"><title>Full GPT-2 stack plus final LN</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="768" height="1" viewBox="0 0 768 1" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(chain_filters)
        + "".join(block1_filters)
        + "".join(additional_filters)
        + final_ln_filter
        + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
        f'fill="white" style="filter:{final_ln_filter_value}"/></svg>'
    )
    (OUT / "chain-12blocks-final-ln.html").write_text(final_ln_html)
    all_filter_markup = chain_filters + block1_filters + additional_filters
    for block_count in range(3, 12):
        cutoff = block_count * 5
        prefix_specs = twelve_specs[:cutoff]
        _, _, _, _, page_width, page_height = prefix_specs[-1]
        page_filter_value = " ".join(f'url(#{spec[0]})' for spec in prefix_specs)
        page_html = (
            '<!doctype html><meta charset="utf-8">'
            f'<title>{block_count} connected SVG-filter GPT-2 blocks</title>'
            '<style>html,body{margin:0;background:black}'
            'svg{display:block;image-rendering:pixelated}</style>'
            f'<svg width="{page_width}" height="{page_height}" '
            f'viewBox="0 0 {page_width} {page_height}" '
            'xmlns="http://www.w3.org/2000/svg"><defs>'
            + "".join(all_filter_markup)
            + f'</defs><rect id="chain-output" width="{HIDDEN}" height="{HIDDEN}" '
            f'fill="white" style="filter:{page_filter_value}"/></svg>'
        )
        (OUT / f"chain-{block_count}blocks.html").write_text(page_html)

    identity = "1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0"
    nested_specs = [
        (
            "nested-ln1",
            768,
            256,
            "".join(primitives[ln1_start:ln1_end]),
            "0 255 768 1",
            768,
            1,
        ),
        (
            "nested-attention",
            256,
            768,
            f'<feColorMatrix in="SourceGraphic" values="{identity}" result="ln1-signed"/>'
            + "".join(primitives[attention_start:attention_end]),
            "255 0 1 768",
            1,
            768,
        ),
        (
            "nested-ln2",
            256,
            768,
            f'<feColorMatrix in="SourceGraphic" values="{identity}" result="attention-common"/>'
            + "".join(primitives[ln2_start:ln2_end]),
            "255 0 1 768",
            1,
            768,
        ),
        (
            "nested-fc",
            3072,
            256,
            f'<feColorMatrix in="SourceGraphic" values="{identity}" result="ln2-signed"/>'
            + "".join(primitives[fc_start:fc_end]),
            "0 255 3072 1",
            3072,
            1,
        ),
        (
            "nested-projection",
            256,
            768,
            f'<feColorMatrix in="SourceGraphic" values="{identity}" result="hidden-signed"/>'
            + "".join(primitives[projection_start:projection_end]),
            "255 0 1 768",
            1,
            768,
        ),
    ]
    nested_filters = []
    for filter_id, work_width, work_height, body, _, _, _ in nested_specs:
        nested_filters.append(
            f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
            f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
            f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">{body}</filter>'
        )
    for cutoff in range(1, len(nested_specs) + 1):
        _, _, _, _, view_box, visible_width, visible_height = nested_specs[cutoff - 1]
        content = '<rect x="0" y="255" width="768" height="1" fill="white" filter="url(#nested-ln1)"/>'
        for spec in nested_specs[1:cutoff]:
            content = f'<g filter="url(#{spec[0]})">{content}</g>'
        nested_html = (
            '<!doctype html><meta charset="utf-8"><title>Nested SVG-filter GPT-2 block</title>'
            '<style>html,body{margin:0;background:black}svg{display:block;image-rendering:pixelated}</style>'
            f'<svg id="nested-output" width="{visible_width}" height="{visible_height}" '
            f'viewBox="{view_box}" xmlns="http://www.w3.org/2000/svg"><defs>'
            + "".join(nested_filters)
            + "</defs>"
            + content
            + "</svg>"
        )
        name = "nested.html" if cutoff == len(nested_specs) else f"nested-{cutoff}.html"
        (OUT / name).write_text(nested_html)

    staged_svgs: list[str] = []
    for index, (stage_id, filter_id, work_width, work_height, view_box, body) in enumerate(stage_specs):
        css_class = "final-stage" if index == len(stage_specs) - 1 else "hidden-stage"
        visible_width = 3072 if stage_id == "fc-stage" else (768 if stage_id == "ln1-stage" else 1)
        visible_height = 1 if stage_id in {"ln1-stage", "fc-stage"} else 768
        staged_svgs.append(
            f'<svg id="{stage_id}-surface" class="{css_class}" width="{visible_width}" '
            f'height="{visible_height}" viewBox="{view_box}" '
            f'xmlns="http://www.w3.org/2000/svg"><defs><filter id="{filter_id}" '
            f'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
            f'x="0" y="0" width="{work_width}" height="{work_height}" '
            f'color-interpolation-filters="{FILTER_COLOR}">{body}</filter></defs>'
            f'<rect id="{stage_id}" x="0" y="0" width="{visible_width}" '
            f'height="{visible_height}" fill="white" '
            f'filter="url(#{filter_id})"/></svg>'
        )
    separate_html = (
        '<!doctype html><meta charset="utf-8"><title>Staged SVG-filter GPT-2 block</title>'
        '<style>html,body{margin:0;background:black}.hidden-stage{position:absolute;left:0;top:0}'
        '.final-stage{display:block;image-rendering:pixelated}</style>'
        + "".join(staged_svgs)
    )
    (OUT / "staged.html").write_text(separate_html)

    filter_defs: list[str] = []
    stage_rects: list[str] = []
    for stage_id, filter_id, work_width, work_height, view_box, body in stage_specs:
        view_x, view_y, visible_width, visible_height = map(int, view_box.split())
        filter_defs.append(
            f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
            f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{work_width}" '
            f'height="{work_height}" color-interpolation-filters="{FILTER_COLOR}">{body}</filter>'
        )
        stage_rects.append(
            f'<rect id="{stage_id}" x="{view_x}" y="{view_y}" '
            f'width="{visible_width}" height="{visible_height}" fill="white" '
            f'filter="url(#{filter_id})"/>'
        )
    single_svg_html = (
        '<!doctype html><meta charset="utf-8"><title>Staged SVG-filter GPT-2 block</title>'
        '<style>html,body{margin:0;background:black}svg{display:block;width:1px;height:768px;'
        'image-rendering:pixelated}</style>'
        '<svg id="staged-root" width="1" height="768" viewBox="0 0 1 768" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(filter_defs)
        + "</defs>"
        + "".join(stage_rects)
        + "</svg>"
    )
    (OUT / "staged-single-svg.html").write_text(single_svg_html)
    block_outputs = [
        {
            "block": 1,
            "expected": final.tolist(),
            "alternate": expected_alt.tolist(),
            "range": final_range,
        },
        {
            "block": 2,
            "expected": b1_final.tolist(),
            "alternate": b1_expected_alt.tolist(),
            "range": b1_final_range,
        },
    ] + [
        {
            "block": int(block["index"]) + 1,
            "expected": np.asarray(block["output"]).tolist(),
            "alternate": np.asarray(block["alternate_output"]).tolist(),
            "range": float(block["output_range"]),
        }
        for block in additional_blocks
    ]
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "surface_center": CENTER,
                "filter_color": FILTER_COLOR,
                "grouped_ln_expected": grouped_ln_expected.tolist(),
                "grouped_ln_expected_alt": grouped_ln_expected_alt.tolist(),
                "grouped_ln_range": grouped_ln_range,
                "grouped_normal_range": group_normal_range,
                "grouped_outlier_range": group_outlier_range,
                "grouped_outlier_dims": list(OUTLIER_DIMS),
                "grouped_2blocks_expected": np.asarray(
                    grouped_block1["output"]
                ).tolist(),
                "grouped_2blocks_expected_alt": np.asarray(
                    grouped_block1["calibration_output"]
                ).tolist(),
                "grouped_2blocks_normal_range": float(
                    grouped_block1["output_normal_range"]
                ),
                "grouped_2blocks_outlier_range": float(
                    grouped_block1["output_outlier_range"]
                ),
                "grouped_1block_expected": np.asarray(
                    grouped_block0["output"]
                ).tolist(),
                "grouped_1block_expected_alt": np.asarray(
                    grouped_block0["calibration_output"]
                ).tolist(),
                "grouped_1block_normal_range": float(
                    grouped_block0["output_normal_range"]
                ),
                "grouped_1block_outlier_range": float(
                    grouped_block0["output_outlier_range"]
                ),
                "grouped_12blocks_expected": grouped_current.tolist(),
                "grouped_12blocks_expected_alt": grouped_calibration_current.tolist(),
                "grouped_12blocks_normal_range": float(
                    grouped_blocks[-1]["output_normal_range"]
                ),
                "grouped_12blocks_outlier_range": float(
                    grouped_blocks[-1]["output_outlier_range"]
                ),
                "grouped_final_ln_expected": grouped_final_expected.tolist(),
                "grouped_final_ln_expected_alt": grouped_final_expected_alt.tolist(),
                "grouped_final_ln_range": grouped_final_ln_range,
                "bucket_count": BUCKETS,
                "bucket_headroom": BUCKET_HEADROOM,
                "bucket_bias_corrections": correction_path,
                "bucket_packed_gelu": PACKED_GELU,
                "bucket_gelu_buckets": GELU_BUCKETS,
                "bucket_input_scales": bucket_x_spec["scales"].tolist(),
                "bucket_input_ids": bucket_x_spec["ids"].tolist(),
                "bucket_calibration_token_ids": list(calibration_token_ids),
                "bucket_block_specs": [
                    {
                        "ln1_scales": block["ln1_spec"]["scales"].tolist(),
                        "attention_residual_scales": block[
                            "attention_residual_spec"
                        ]["scales"].tolist(),
                        "ln2_scales": block["ln2_spec"]["scales"].tolist(),
                        "fc_hidden_scales": block["fc_hidden_spec"][
                            "scales"
                        ].tolist(),
                        "projection_output_scales": block["output_spec"][
                            "scales"
                        ].tolist(),
                    }
                    for block in bucket_blocks
                ],
                "bucket_12blocks_expected": bucket_current.tolist(),
                "bucket_12blocks_expected_alt": np.asarray(
                    bucket_calibration_current[0]
                    if np.asarray(bucket_calibration_current).ndim == 2
                    else bucket_calibration_current
                ).tolist(),
                "bucket_12blocks_scales": bucket_current_spec["scales"].tolist(),
                "bucket_12blocks_ids": bucket_current_spec["ids"].tolist(),
                "bucket_final_ln_expected": bucket_final_expected.tolist(),
                "bucket_final_ln_expected_alt": np.asarray(
                    bucket_final_expected_alt[0]
                    if np.asarray(bucket_final_expected_alt).ndim == 2
                    else bucket_final_expected_alt
                ).tolist(),
                "bucket_final_ln_scales": bucket_final_spec["scales"].tolist(),
                "bucket_final_ln_ids": bucket_final_spec["ids"].tolist(),
                "n1": n1.tolist(),
                "n1_range": n1_range,
                "residual": residual.tolist(),
                "residual_range": residual_range,
                "n2": n2.tolist(),
                "n2_range": n2_range,
                "pre": pre.tolist(),
                "pre_range": pre_range,
                "hidden": hidden.tolist(),
                "hidden_range": hidden_range,
                "expected": final.tolist(),
                "expected_alt": expected_alt.tolist(),
                "output_range": final_range,
                "expected_2blocks": b1_final.tolist(),
                "expected_alt_2blocks": b1_expected_alt.tolist(),
                "output_range_2blocks": b1_final_range,
                "b1_n1": b1_n1.tolist(),
                "b1_n1_range": b1_n1_range,
                "b1_residual": b1_residual.tolist(),
                "b1_residual_range": b1_residual_range,
                "b1_n2": b1_n2.tolist(),
                "b1_n2_range": b1_n2_range,
                "b1_hidden": b1_hidden.tolist(),
                "b1_hidden_range": b1_hidden_range,
                "expected_12blocks": current_vector.tolist(),
                "expected_alt_12blocks": current_alternate.tolist(),
                "output_range_12blocks": current_range,
                "expected_final_ln": final_normalized.tolist(),
                "expected_alt_final_ln": alternate_final_normalized.tolist(),
                "final_ln_range": final_normalized_range,
                "block_outputs": block_outputs,
                "read_column": CX,
            }
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "asset_bytes": sum(p.stat().st_size for p in OUT.glob("*.png")), "output_range": final_range})


if __name__ == "__main__":
    main()
