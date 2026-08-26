#!/usr/bin/env python3
"""Build a no-JS probe for reusable RGB-dithered SVG arithmetic."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-dither-transport"
CENTER = 128 / 255
RANGE = 1.0
SAMPLES = 256


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(
        np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8), mode="L"
    ).save(path, optimize=True)


def save_rgb(path: Path, values: np.ndarray) -> None:
    rgba = np.zeros((*values.shape[:2], 4), dtype=np.uint8)
    rgba[..., :3] = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def color_matrix(a: float, b: float, offsets: np.ndarray) -> str:
    coefficient = a / 3
    base = CENTER * (1 - a) + b / (2 * RANGE)
    rows = []
    for offset in offsets:
        rows.extend((coefficient, coefficient, coefficient, 0, base + offset / (2 * RANGE)))
    rows.extend((0, 0, 0, 1, 0))
    return " ".join(f"{value:.12g}" for value in rows)


def ordinary_matrix(a: float, b: float) -> str:
    base = CENTER * (1 - a) + b / (2 * RANGE)
    return " ".join(
        f"{value:.12g}"
        for value in (
            a, 0, 0, 0, base,
            0, a, 0, 0, base,
            0, 0, a, 0, base,
            0, 0, 0, 1, 0,
        )
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(872341)
    initial = rng.uniform(-0.72, 0.72, SAMPLES)
    # Kept comfortably inside the encoded range so this probe measures
    # quantization rather than clipping.
    coefficients = [
        (0.91, 0.037),
        (-0.83, 0.021),
        (0.88, -0.044),
        (0.94, 0.018),
        (-0.79, -0.031),
        (0.86, 0.052),
        (0.92, -0.027),
        (-0.81, 0.016),
        (0.89, 0.033),
        (0.95, -0.041),
        (-0.84, 0.025),
        (0.90, -0.019),
    ]
    quantization_step = 2 * RANGE / 255
    offsets = quantization_step * np.asarray([-1 / 3, 0, 1 / 3])

    ordinary_input = CENTER + initial / (2 * RANGE)
    dither_input = CENTER + (
        initial[:, None] + offsets[None, :]
    ) / (2 * RANGE)
    save_gray(OUT / "ordinary.png", ordinary_input.reshape(SAMPLES, 1))
    save_rgb(OUT / "dithered.png", dither_input.reshape(SAMPLES, 1, 3))

    ordinary_steps = []
    dither_steps = []
    ordinary_source = "ordinary-input"
    dither_source = "dither-input"
    expected = initial.copy()
    checkpoints = [initial.tolist()]
    for index, (a, b) in enumerate(coefficients, 1):
        ordinary_result = f"ordinary-{index}"
        dither_result = f"dither-{index}"
        ordinary_steps.append(
            f'<feColorMatrix in="{ordinary_source}" '
            f'values="{ordinary_matrix(a, b)}" result="{ordinary_result}"/>'
        )
        dither_steps.append(
            f'<feColorMatrix in="{dither_source}" '
            f'values="{color_matrix(a, b, offsets)}" result="{dither_result}"/>'
        )
        ordinary_source = ordinary_result
        dither_source = dither_result
        expected = a * expected + b
        checkpoints.append(expected.tolist())

    html = f'''<!doctype html><meta charset="utf-8">
<title>Reusable RGB dither transport</title>
<style>html,body{{margin:0;background:#000}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="2" height="{SAMPLES}" viewBox="0 0 2 {SAMPLES}" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="probe" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
 x="0" y="0" width="2" height="{SAMPLES}" color-interpolation-filters="sRGB">
<feImage href="ordinary.png" x="0" y="0" width="1" height="{SAMPLES}" result="ordinary-input"/>
<feImage href="dithered.png" x="1" y="0" width="1" height="{SAMPLES}" result="dither-input"/>
{''.join(ordinary_steps)}
{''.join(dither_steps)}
<feOffset in="{ordinary_source}" x="0" y="0" width="1" height="{SAMPLES}" result="ordinary-output"/>
<feOffset in="{dither_source}" x="1" y="0" width="1" height="{SAMPLES}" result="dither-output"/>
<feMerge><feMergeNode in="ordinary-output"/><feMergeNode in="dither-output"/></feMerge>
</filter></defs><rect width="2" height="{SAMPLES}" fill="white" filter="url(#probe)"/></svg>'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "center": CENTER,
                "range": RANGE,
                "samples": SAMPLES,
                "offsets": offsets.tolist(),
                "coefficients": coefficients,
                "checkpoints": checkpoints,
            },
            indent=2,
        )
        + "\n"
    )
    print({"output": str(OUT), "html_bytes": len(html.encode())})


if __name__ == "__main__":
    main()
