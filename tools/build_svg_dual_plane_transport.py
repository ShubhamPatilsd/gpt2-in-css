#!/usr/bin/env python3
"""Build no-JS probes for persistent dual-plane and exact radix transport."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-dual-plane-transport"
WIDTH = 256
CENTER = 128 / 255
COARSE_RANGE = 2.0
FINE_RANGE = COARSE_RANGE / 255
CHECKPOINTS = (0, 1, 2, 4, 8, 12)


def radix_dot_cost(dot_length: int, digit_bits: int) -> dict[str, int]:
    """Lower-bound plane count for exact unsigned 16b-by-8b dot products."""
    radix = 1 << digit_bits
    product_max = (radix - 1) ** 2
    terms_per_byte = 255 // product_max
    activation_planes = math.ceil(16 / digit_bits)
    weight_planes = math.ceil(8 / digit_bits)
    plane_pairs = activation_planes * weight_planes
    chunks_per_pair = math.ceil(dot_length / terms_per_byte)
    return {
        "radix": radix,
        "activation_planes": activation_planes,
        "weight_planes": weight_planes,
        "plane_pairs": plane_pairs,
        "terms_per_exact_byte_accumulator": terms_per_byte,
        "chunks_per_plane_pair": chunks_per_pair,
        "partial_reductions": plane_pairs * chunks_per_pair,
    }


def save_rgba(path: Path, red: np.ndarray, green: np.ndarray) -> None:
    pixels = np.zeros((1, WIDTH, 4), dtype=np.uint8)
    pixels[0, :, 0] = red
    pixels[0, :, 1] = green
    pixels[0, :, 3] = 255
    Image.fromarray(pixels, mode="RGBA").save(path, optimize=True)


def matrix(a: float, red_offset: float, green_offset: float = 0.0) -> str:
    return (
        f"{a:.12g} 0 0 0 {red_offset:.12g}  "
        f"0 {a:.12g} 0 0 {green_offset:.12g}  "
        "0 0 0 0 0  0 0 0 0 1"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260911)
    initial = rng.uniform(-1, 1, WIDTH)
    coarse_codes = np.rint(
        np.clip(CENTER + initial / (2 * COARSE_RANGE), 0, 1) * 255
    ).astype(np.uint8)
    coarse = (coarse_codes / 255 - CENTER) * 2 * COARSE_RANGE
    residual = initial - coarse
    fine_codes = np.rint(
        np.clip(CENTER + residual / (2 * FINE_RANGE), 0, 1) * 255
    ).astype(np.uint8)
    single_codes = coarse_codes.copy()
    save_rgba(OUT / "single.png", single_codes, np.zeros(WIDTH, dtype=np.uint8))
    save_rgba(OUT / "dual.png", coarse_codes, fine_codes)

    # Stable but nontrivial affine recurrence. All exact values remain inside
    # COARSE_RANGE, so any loss is quantization rather than clamping.
    coefficients = [
        (0.91, 0.071),
        (0.87, -0.043),
        (0.94, 0.029),
        (0.89, 0.052),
        (0.92, -0.061),
        (0.86, 0.038),
        (0.95, -0.017),
        (0.88, 0.046),
        (0.93, -0.035),
        (0.90, 0.022),
        (0.85, 0.057),
        (0.96, -0.026),
    ]
    exact = initial.copy()
    exact_checkpoints = {0: exact.copy()}
    for index, (a, bias) in enumerate(coefficients, 1):
        exact = a * exact + bias
        if index in CHECKPOINTS:
            exact_checkpoints[index] = exact.copy()

    filters: list[str] = []
    rows: list[str] = []
    row = 0
    for checkpoint in CHECKPOINTS:
        single_steps: list[str] = []
        dual_steps: list[str] = []
        previous_single = "SourceGraphic"
        previous_dual = "SourceGraphic"
        for index, (a, bias) in enumerate(coefficients[:checkpoint], 1):
            single_result = f"s{checkpoint}-{index}"
            dual_result = f"d{checkpoint}-{index}"
            coarse_offset = CENTER * (1 - a) + bias / (2 * COARSE_RANGE)
            fine_offset = CENTER * (1 - a)
            single_steps.append(
                f'<feColorMatrix in="{previous_single}" '
                f'values="{matrix(a, coarse_offset)}" result="{single_result}"/>'
            )
            dual_steps.append(
                f'<feColorMatrix in="{previous_dual}" '
                f'values="{matrix(a, coarse_offset, fine_offset)}" '
                f'result="{dual_result}"/>'
            )
            previous_single = single_result
            previous_dual = dual_result
        if not single_steps:
            single_steps.append('<feOffset in="SourceGraphic" dx="0" dy="0"/>')
            dual_steps.append('<feOffset in="SourceGraphic" dx="0" dy="0"/>')
        filters.extend(
            (
                f'<filter id="single-{checkpoint}" x="0" y="0" width="1" '
                f'height="1" filterUnits="objectBoundingBox" '
                f'color-interpolation-filters="sRGB">'
                + "".join(single_steps)
                + "</filter>",
                f'<filter id="dual-{checkpoint}" x="0" y="0" width="1" '
                f'height="1" filterUnits="objectBoundingBox" '
                f'color-interpolation-filters="sRGB">'
                + "".join(dual_steps)
                + "</filter>",
            )
        )
        rows.extend(
            (
                f'<image href="single.png" x="0" y="{row}" width="{WIDTH}" height="1" '
                f'preserveAspectRatio="none" filter="url(#single-{checkpoint})"/>',
                f'<image href="dual.png" x="0" y="{row + 1}" width="{WIDTH}" height="1" '
                f'preserveAspectRatio="none" filter="url(#dual-{checkpoint})"/>',
            )
        )
        row += 2

    # Exact base-16 carry. A radix digit occupies byte codes 0, 8, ... 120,
    # leaving enough headroom to add two digits without clamping. The lookup
    # emits the low digit and carry in the same encoding so the result can be
    # fed into another integer-style stage.
    radix_step = 8
    left = rng.integers(0, 16, WIDTH, dtype=np.uint8)
    right = rng.integers(0, 16, WIDTH, dtype=np.uint8)
    save_rgba(OUT / "radix-addends.png", left * radix_step, right * radix_step)
    decoded_sums = [round(value / radix_step) for value in range(256)]
    # Bias each lookup result into the middle of the intended output byte's
    # quantization bin. Exact n/255 table entries can land infinitesimally
    # below the boundary in Chromium and materialize as n-1.
    def stable_byte(code: int) -> float:
        return (code + 0.25) / 255

    low_table = " ".join(
        f"{stable_byte((value % 16) * radix_step):.12g}" for value in decoded_sums
    )
    carry_table = " ".join(
        f"{stable_byte((value // 16) * radix_step):.12g}" for value in decoded_sums
    )
    carry_filter = (
        '<filter id="radix-carry" x="0" y="0" width="1" height="1" '
        'filterUnits="objectBoundingBox" '
        'color-interpolation-filters="sRGB">'
        '<feColorMatrix values="1 1 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1" '
        'result="digit-sum"/>'
        '<feComponentTransfer in="digit-sum">'
        f'<feFuncR type="discrete" tableValues="{low_table}"/>'
        f'<feFuncG type="discrete" tableValues="{carry_table}"/>'
        '<feFuncB type="discrete" tableValues="0"/>'
        '<feFuncA type="identity"/>'
        '</feComponentTransfer></filter>'
    )
    filters.append(carry_filter)
    rows.append(
        f'<image href="radix-addends.png" x="0" y="{row}" width="{WIDTH}" height="1" '
        'preserveAspectRatio="none" filter="url(#radix-carry)"/>'
    )

    height = row + 1
    html = (
        '<!doctype html><meta charset="utf-8"><title>Dual-plane transport</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(filters)
        + "</defs>"
        + "".join(rows)
        + "</svg>"
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "center": CENTER,
                "coarse_range": COARSE_RANGE,
                "fine_range": FINE_RANGE,
                "checkpoints": list(CHECKPOINTS),
                "exact": {
                    str(key): value.tolist() for key, value in exact_checkpoints.items()
                },
                "radix_left": left.astype(int).tolist(),
                "radix_right": right.astype(int).tolist(),
                "radix_step": radix_step,
                "exact_radix_dot_lower_bounds": {
                    str(dot_length): {
                        str(1 << digit_bits): radix_dot_cost(dot_length, digit_bits)
                        for digit_bits in (1, 2, 4)
                    }
                    for dot_length in (768, 3072)
                },
            },
            indent=2,
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "rows": height})


if __name__ == "__main__":
    main()
