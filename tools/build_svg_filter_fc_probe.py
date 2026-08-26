#!/usr/bin/env python3
"""Build an SVG-filter 768→3,072 unsigned matvec scaling probe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-filter-fc"
INPUTS = 768
OUTPUTS = 3072
SHARD = 256


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(np.rint(values * 255).astype(np.uint8), mode="L").save(
        path, optimize=True
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260908)
    weights = rng.uniform(0, 0.8, size=(OUTPUTS, INPUTS))
    vector = rng.uniform(0, 1, size=INPUTS)
    expected = weights @ vector / INPUTS
    for shard, start in enumerate(range(0, INPUTS, SHARD)):
        save_gray(OUT / f"weights-{shard}.png", weights[:, start : start + SHARD])
        save_gray(OUT / f"vector-{shard}.png", vector[start : start + SHARD][None, :])

    kernel = " ".join("1" for _ in range(SHARD))
    primitives: list[str] = []
    partials: list[str] = []
    for shard in range(INPUTS // SHARD):
        primitives.extend(
            (
                f'<feImage href="weights-{shard}.png" x="0" y="0" '
                f'width="{SHARD}" height="{OUTPUTS}" preserveAspectRatio="none" '
                f'result="w{shard}"/>',
                f'<feImage href="vector-{shard}.png" x="0" y="0" '
                f'width="{SHARD}" height="1" preserveAspectRatio="none" '
                f'result="vrow{shard}"/>',
                f'<feTile in="vrow{shard}" x="0" y="0" width="{SHARD}" '
                f'height="{OUTPUTS}" result="v{shard}"/>',
                f'<feComposite in="w{shard}" in2="v{shard}" operator="arithmetic" '
                f'k1="1" k2="0" k3="0" k4="0" result="p{shard}"/>',
                f'<feConvolveMatrix in="p{shard}" order="{SHARD} 1" '
                f'kernelMatrix="{kernel}" divisor="{INPUTS}" targetX="{SHARD - 1}" '
                f'targetY="0" edgeMode="none" kernelUnitLength="1 1" '
                f'preserveAlpha="true" x="{SHARD - 1}" y="0" width="1" '
                f'height="{OUTPUTS}" result="s{shard}"/>',
            )
        )
        partials.append(f"s{shard}")
    primitives.extend(
        (
            f'<feComposite in="{partials[0]}" in2="{partials[1]}" '
            'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="sum01"/>',
            f'<feComposite in="sum01" in2="{partials[2]}" '
            'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="sum"/>',
        )
    )
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>SVG filter 768→3,072 FC probe</title>
<style>
  html, body {{ margin: 0; background: black; }}
  svg {{ display: block; width: {SHARD}px; height: {OUTPUTS}px; image-rendering: pixelated; }}
</style>
<svg viewBox="0 0 {SHARD} {OUTPUTS}" xmlns="http://www.w3.org/2000/svg">
  <filter id="fc" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
          x="0" y="0" width="{SHARD}" height="{OUTPUTS}"
          color-interpolation-filters="sRGB">
    {''.join(primitives)}
  </filter>
  <rect width="{SHARD}" height="{OUTPUTS}" fill="white" filter="url(#fc)"/>
</svg>
'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "inputs": INPUTS,
                "outputs": OUTPUTS,
                "shards": INPUTS // SHARD,
                "expected": expected.tolist(),
                "read_column": SHARD - 1,
                "encoding": "8-bit unsigned sRGB; result divided by 768",
            }
        )
        + "\n"
    )
    print(
        {
            "outputs": OUTPUTS,
            "expected_min": float(expected.min()),
            "expected_max": float(expected.max()),
            "asset_bytes": sum(path.stat().st_size for path in OUT.glob("*.png")),
            "html_bytes": len(html.encode()),
        }
    )


if __name__ == "__main__":
    main()
