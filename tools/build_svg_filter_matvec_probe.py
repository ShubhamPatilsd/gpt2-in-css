#!/usr/bin/env python3
"""Build a no-JavaScript SVG-filter matrix-vector multiplication probe."""

from __future__ import annotations

import base64
import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-filter-matvec"


def png_url(values: np.ndarray) -> str:
    image = Image.fromarray(np.rint(values * 255).astype(np.uint8), mode="L").convert(
        "RGBA"
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=4)
    args = parser.parse_args()
    size = args.size
    if size == 4:
        weights = np.array(
            [
                [0.10, 0.20, 0.30, 0.40],
                [0.25, 0.05, 0.15, 0.35],
                [0.30, 0.10, 0.20, 0.05],
                [0.05, 0.35, 0.10, 0.25],
            ],
            dtype=np.float64,
        )
        vector = np.array([0.20, 0.40, 0.60, 0.80], dtype=np.float64)
        divisor = 1
    else:
        rng = np.random.default_rng(20260908 + size)
        # Keep every reduced result below one so the filter's mandated channel
        # clamping does not alter the dot product.
        weights = rng.uniform(0, 0.8, size=(size, size))
        vector = rng.uniform(0, 1, size=size)
        divisor = size
    out = OUT if size == 4 else OUT / str(size)
    out.mkdir(parents=True, exist_ok=True)
    # Every image row receives the same vector. Pixelwise multiplication then
    # produces W[i,j] * x[j] before horizontal reduction.
    tiled_vector = np.broadcast_to(vector, weights.shape)
    expected = weights @ vector / divisor

    kernel = " ".join("1" for _ in range(size))
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>SVG filter 4×4 matrix-vector probe</title>
<style>
  html, body {{ margin: 0; background: black; }}
  svg {{ display: block; width: {size}px; height: {size}px; image-rendering: pixelated; }}
</style>
<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <filter id="matvec" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
          x="0" y="0" width="{size}" height="{size}" color-interpolation-filters="sRGB">
    <feImage href="{png_url(weights)}" x="0" y="0" width="{size}" height="{size}"
             preserveAspectRatio="none" result="weights"/>
    <feImage href="{png_url(tiled_vector)}" x="0" y="0" width="{size}" height="{size}"
             preserveAspectRatio="none" result="vector"/>
    <feComposite in="weights" in2="vector" operator="arithmetic"
                 k1="1" k2="0" k3="0" k4="0" result="products"/>
    <feConvolveMatrix in="products" order="{size} 1" kernelMatrix="{kernel}"
                      divisor="{divisor}" targetX="{size - 1}" targetY="0" edgeMode="none"
                      kernelUnitLength="1 1" preserveAlpha="true"
                      x="{size - 1}" y="0" width="1" height="{size}" result="sums"/>
  </filter>
  <rect width="{size}" height="{size}" fill="white" filter="url(#matvec)"/>
</svg>
'''
    (out / "index.html").write_text(html)
    (out / "reference.json").write_text(
        json.dumps(
            {
                "weights": weights.tolist(),
                "vector": vector.tolist(),
                "expected": expected.tolist(),
                "read_column": size - 1,
                "encoding": "8-bit sRGB grayscale",
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "size": size,
            "expected_min": float(expected.min()),
            "expected_max": float(expected.max()),
            "html_bytes": len(html.encode()),
        }
    )


if __name__ == "__main__":
    main()
