#!/usr/bin/env python3
"""Build a no-JS A/B probe for 8-, 16-, and 24-bit SVG value transport."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-rgb-precision-transport"
WIDTH = 768
CENTER_CODE = 128
CENTER = CENTER_CODE / 255
VALUE_RANGE = 2.0
CHECKPOINTS = (0, 1, 2, 4, 8, 12)
PLANE_SCALES = (VALUE_RANGE, VALUE_RANGE / 255, VALUE_RANGE / 255**2)


def encode_plane(value: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    codes = np.rint(np.clip(CENTER + value / (2 * scale), 0, 1) * 255).astype(
        np.uint8
    )
    decoded = (codes.astype(np.float64) / 255 - CENTER) * 2 * scale
    return codes, decoded


def encode(value: np.ndarray, planes: int) -> np.ndarray:
    residual = value.copy()
    result = np.full((1, WIDTH, 4), 0, dtype=np.uint8)
    result[..., 3] = 255
    for channel, scale in enumerate(PLANE_SCALES[:planes]):
        codes, decoded = encode_plane(residual, scale)
        result[0, :, channel] = codes
        residual -= decoded
    return result


def save_source(name: str, value: np.ndarray, planes: int) -> None:
    Image.fromarray(encode(value, planes), mode="RGBA").save(
        OUT / name, optimize=True
    )


def affine_matrix(a: float, bias: float, planes: int) -> str:
    rows: list[list[float]] = []
    for channel in range(3):
        row = [0.0] * 5
        if channel < planes:
            row[channel] = a
            # The real recurrence bias belongs to the coarse plane. Every
            # centered channel also needs its center restored after scaling.
            row[4] = CENTER * (1 - a)
            if channel == 0:
                row[4] += bias / (2 * PLANE_SCALES[0])
        rows.append(row)
    rows.append([0.0, 0.0, 0.0, 1.0, 0.0])
    return " ".join(f"{item:.12g}" for row in rows for item in row)


def filter_for(planes: int, checkpoint: int, coefficients: list[tuple[float, float]]) -> str:
    primitives: list[str] = []
    source = "SourceGraphic"
    if checkpoint == 0:
        primitives.append('<feOffset in="SourceGraphic" dx="0" dy="0"/>')
    for stage, (a, bias) in enumerate(coefficients[:checkpoint], 1):
        calculated = f"p{planes}-c{checkpoint}-calc{stage}"
        bounded = f"p{planes}-c{checkpoint}-boundary{stage}"
        primitives.append(
            f'<feColorMatrix in="{source}" values="{affine_matrix(a, bias, planes)}" '
            f'result="{calculated}"/>'
        )
        # A 1x1 convolution is mathematically the identity, but it is a real
        # image-filter boundary. It prevents Chromium from merely folding a
        # run of color matrices into one high-precision expression.
        primitives.append(
            f'<feConvolveMatrix in="{calculated}" order="1" kernelMatrix="1" '
            f'edgeMode="none" preserveAlpha="true" result="{bounded}"/>'
        )
        source = bounded
    return (
        f'<filter id="p{planes}-c{checkpoint}" filterUnits="objectBoundingBox" '
        f'x="0" y="0" width="1" height="1" '
        'color-interpolation-filters="sRGB">'
        + "".join(primitives)
        + "</filter>"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260912)
    initial = rng.uniform(-1.0, 1.0, WIDTH)
    for planes in (1, 2, 3):
        save_source(f"source-{planes}.png", initial, planes)

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
    exact_by_checkpoint: dict[str, list[float]] = {"0": exact.tolist()}
    for stage, (a, bias) in enumerate(coefficients, 1):
        exact = a * exact + bias
        if stage in CHECKPOINTS:
            exact_by_checkpoint[str(stage)] = exact.tolist()

    filters: list[str] = []
    images: list[str] = []
    rows: list[dict[str, int]] = []
    row = 0
    for checkpoint in CHECKPOINTS:
        for planes in (1, 2, 3):
            filters.append(filter_for(planes, checkpoint, coefficients))
            images.append(
                f'<image href="source-{planes}.png" x="0" y="{row}" '
                f'width="{WIDTH}" height="1" preserveAspectRatio="none" '
                f'filter="url(#p{planes}-c{checkpoint})"/>'
            )
            rows.append({"checkpoint": checkpoint, "planes": planes, "row": row})
            row += 1

    html = (
        '<!doctype html><meta charset="utf-8"><title>RGB precision transport</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{WIDTH}" height="{row}" viewBox="0 0 {WIDTH} {row}" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        + "".join(filters)
        + "</defs>"
        + "".join(images)
        + "</svg>"
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "center": CENTER,
                "planeScales": PLANE_SCALES,
                "checkpoints": CHECKPOINTS,
                "rows": rows,
                "exact": exact_by_checkpoint,
                "htmlBytes": len(html.encode()),
            },
            indent=2,
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "rows": row})


if __name__ == "__main__":
    main()
