#!/usr/bin/env python3
"""Build a browser-neutral SVG filter intermediate-precision gate."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "svg-cross-browser-precision"
SAMPLES = 64
BASE = 0.2
SPAN = 1 / 1024
GAIN = 512


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    boundaries = {
        "unfiltered-control": None,
        "single-matrix-control": "single",
        "adjacent-matrix": "",
        "named-matrix": (
            '<feColorMatrix in="encoded" values="1 0 0 0 0 0 1 0 0 0 '
            '0 0 1 0 0 0 0 0 1 0" result="boundary"/>'
        ),
        "composite-add": (
            '<feFlood flood-color="black" result="aux"/>'
            '<feComposite in="encoded" in2="aux" operator="arithmetic" '
            'k1="0" k2="1" k3="1" k4="0" result="boundary"/>'
        ),
        "composite-multiply": (
            '<feFlood flood-color="white" result="aux"/>'
            '<feComposite in="encoded" in2="aux" operator="arithmetic" '
            'k1="1" k2="0" k3="0" k4="0" result="boundary"/>'
        ),
        "convolve": (
            '<feConvolveMatrix in="encoded" order="1" kernelMatrix="1" '
            'divisor="1" result="boundary"/>'
        ),
        "transfer": (
            '<feComponentTransfer in="encoded" result="boundary">'
            '<feFuncR type="identity"/><feFuncG type="identity"/>'
            '<feFuncB type="identity"/><feFuncA type="identity"/>'
            '</feComponentTransfer>'
        ),
    }
    filters: list[str] = []
    cells: list[str] = []
    rows: list[dict[str, object]] = []
    amplify = (
        '<feColorMatrix in="{input}" values="4 0 0 0 -.6 0 4 0 0 -.6 '
        '0 0 4 0 -.6 0 0 0 1 0" result="amp1"/>'
        '<feColorMatrix in="amp1" values="4 0 0 0 -.6 0 4 0 0 -.6 '
        '0 0 4 0 -.6 0 0 0 1 0" result="amp2"/>'
        '<feColorMatrix in="amp2" values="4 0 0 0 -.6 0 4 0 0 -.6 '
        '0 0 4 0 -.6 0 0 0 1 0" result="amp3"/>'
        '<feColorMatrix in="amp3" values="8 0 0 0 -1.4 0 8 0 0 -1.4 '
        '0 0 8 0 -1.4 0 0 0 1 0"/>'
    )
    for row, (name, boundary) in enumerate(boundaries.items()):
        rows.append({"row": row, "boundary": name})
        for sample in range(SAMPLES):
            if boundary is None:
                cells.append(
                    f'<rect x="{sample}" y="{row}" width="1" height="1" fill="white"/>'
                )
                continue
            value = BASE + SPAN * sample / (SAMPLES - 1)
            filter_id = f"f-{row}-{sample}"
            if boundary == "single":
                filters.append(
                    f'<filter id="{filter_id}" x="-10%" y="-10%" width="120%" height="120%">'
                    f'<feColorMatrix in="SourceGraphic" values="0 0 0 0 {value:.12g} '
                    f'0 0 0 0 {value:.12g} 0 0 0 0 {value:.12g} 0 0 0 1 0"/>'
                    '</filter>'
                )
                cells.append(
                    f'<rect x="{sample}" y="{row}" width="1" height="1" fill="white" '
                    f'filter="url(#{filter_id})"/>'
                )
                continue
            boundary_input = "boundary" if boundary else "encoded"
            filters.append(
                f'<filter id="{filter_id}" x="-10%" y="-10%" width="120%" height="120%" '
                'color-interpolation-filters="linearRGB">'
                f'<feColorMatrix in="SourceGraphic" values="0 0 0 0 {value:.12g} '
                f'0 0 0 0 {value:.12g} 0 0 0 0 {value:.12g} 0 0 0 1 0" '
                f'result="encoded"/>{boundary}'
                f'{amplify.format(input=boundary_input)}'
                '</filter>'
            )
            cells.append(
                f'<rect x="{sample}" y="{row}" width="1" height="1" fill="white" '
                f'filter="url(#{filter_id})"/>'
            )
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{SAMPLES}" height="{len(rows)}" viewBox="0 0 {SAMPLES} {len(rows)}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>{"".join(cells)}</svg>'
    )
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "reference.json").write_text(json.dumps({
        "samples": SAMPLES,
        "rows": rows,
        "idealOutput": [BASE + GAIN * SPAN * i / (SAMPLES - 1) for i in range(SAMPLES)],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
