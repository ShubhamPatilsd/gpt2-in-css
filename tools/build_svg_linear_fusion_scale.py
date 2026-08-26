#!/usr/bin/env python3
"""Build no-script SVG probes comparing chained and algebraically fused math."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-linear-fusion-scale"
WIDTHS = (64, 256, 768, 3072)
STAGE_COUNTS = (1, 2, 4, 8, 16, 32, 64)
DELTA = 0.001


def color_matrix(offset: float, source: str | None = None, result: str | None = None) -> str:
    attributes = []
    if source:
        attributes.append(f'in="{source}"')
    if result:
        attributes.append(f'result="{result}"')
    attributes.append(
        'values="1 0 0 0 '
        f'{offset:.12g}  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"'
    )
    return f"<feColorMatrix {' '.join(attributes)}/>"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260911)
    references: dict[str, object] = {
        "delta": DELTA,
        "widths": list(WIDTHS),
        "stage_counts": list(STAGE_COUNTS),
        "cases": {},
    }

    links = []
    for width in WIDTHS:
        source = rng.uniform(-0.75, 0.75, width)
        source_codes = np.rint((source + 1) * 0.5 * 255).astype(np.uint8)
        source_decoded = source_codes.astype(np.float64) / 255 * 2 - 1
        pixels = np.zeros((1, width, 4), dtype=np.uint8)
        pixels[0, :, 0] = source_codes
        pixels[0, :, 3] = 255
        Image.fromarray(pixels, mode="RGBA").save(OUT / f"input-{width}.png", optimize=True)

        for stages in STAGE_COUNTS:
            case = f"w{width}-s{stages}"
            previous = None
            chain_steps = []
            bounded_steps = []
            previous_bounded = None
            for index in range(stages):
                result = f"step-{index}"
                chain_steps.append(color_matrix(DELTA / 2, previous, result))
                previous = result
                bounded_value = f"bounded-value-{index}"
                bounded_result = f"bounded-result-{index}"
                bounded_steps.append(
                    color_matrix(DELTA / 2, previous_bounded, bounded_value)
                )
                bounded_steps.append(
                    f'<feConvolveMatrix in="{bounded_value}" order="1 1" '
                    'kernelMatrix="1" divisor="1" bias="0" '
                    f'preserveAlpha="false" result="{bounded_result}"/>'
                )
                previous_bounded = bounded_result
            fused_step = color_matrix(stages * DELTA / 2)
            svg = (
                f'<svg width="{width}" height="3" viewBox="0 0 {width} 3" '
                'xmlns="http://www.w3.org/2000/svg">'
                '<defs>'
                '<filter id="chain" x="0" y="0" width="1" height="1" '
                'filterUnits="objectBoundingBox" color-interpolation-filters="sRGB">'
                + "".join(chain_steps)
                + '</filter>'
                '<filter id="bounded" x="0" y="0" width="1" height="1" '
                'filterUnits="objectBoundingBox" color-interpolation-filters="sRGB">'
                + "".join(bounded_steps)
                + '</filter>'
                '<filter id="fused" x="0" y="0" width="1" height="1" '
                'filterUnits="objectBoundingBox" color-interpolation-filters="sRGB">'
                + fused_step
                + '</filter></defs>'
                f'<image href="input-{width}.png" x="0" y="0" width="{width}" height="1" '
                'preserveAspectRatio="none" filter="url(#chain)"/>'
                f'<image href="input-{width}.png" x="0" y="1" width="{width}" height="1" '
                'preserveAspectRatio="none" filter="url(#bounded)"/>'
                f'<image href="input-{width}.png" x="0" y="2" width="{width}" height="1" '
                'preserveAspectRatio="none" filter="url(#fused)"/>'
                '</svg>'
            )
            html = (
                '<!doctype html><meta charset="utf-8">'
                f'<title>Linear fusion {case}</title>'
                '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
                + svg
            )
            (OUT / f"{case}.html").write_text(html)
            references["cases"][case] = {
                "width": width,
                "stages": stages,
                "expected": (source_decoded + stages * DELTA).tolist(),
                "html_bytes": len(html.encode()),
                "chain_primitives": stages,
                "bounded_primitives": stages * 2,
                "fused_primitives": 1,
            }
            links.append(f'<li><a href="{case}.html">{case}</a></li>')

    (OUT / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Linear fusion scale probes</title>'
        '<h1>Linear fusion scale probes</h1><ul>' + "".join(links) + '</ul>'
    )
    (OUT / "reference.json").write_text(json.dumps(references, indent=2) + "\n")
    print({"cases": len(references["cases"]), "output": str(OUT)})


if __name__ == "__main__":
    main()
