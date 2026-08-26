#!/usr/bin/env python3
"""Build an SVG probe for sub-8-bit filter-intermediate precision."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "svg-internal-precision"
SAMPLES = 64
BASE = 0.5
SPAN = 1 / 1024
GAIN = 512


def matrix_constant(value: float, channel: str) -> str:
    if channel == "alpha":
        return f"0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 {value:.12g}"
    row = f"0 0 0 0 {value:.12g}"
    return f"{row} {row} {row} 0 0 0 1 0"


def matrix_amplify(channel: str) -> str:
    offset = 0.25 - GAIN * BASE
    if channel == "alpha":
        row = f"0 0 0 {GAIN} {offset:.12g}"
        return f"{row} {row} {row} 0 0 0 0 1"
    row = f"{GAIN} 0 0 0 {offset:.12g}"
    return f"{row} {row} {row} 0 0 0 1 0"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    modes = [
        ("srgb-white", "sRGB", "white", "rgb"),
        ("linear-white", "linearRGB", "white", "rgb"),
        ("srgb-p3", "sRGB", "color(display-p3 1 0 0)", "rgb"),
        ("linear-p3", "linearRGB", "color(display-p3 1 0 0)", "rgb"),
        ("srgb-rec2020", "sRGB", "color(rec2020 1 0 0)", "rgb"),
        ("linear-rec2020", "linearRGB", "color(rec2020 1 0 0)", "rgb"),
        ("srgb-alpha", "sRGB", "white", "alpha"),
        ("linear-alpha", "linearRGB", "white", "alpha"),
    ]
    boundaries = {
        "matrix": "",
        "named-matrix": (
            '<feColorMatrix in="encoded" values="1 0 0 0 0 '
            '0 1 0 0 0 0 0 1 0 0 0 0 0 1 0" result="boundary"/>'
        ),
        "offset": '<feOffset in="encoded" dx="0" dy="0" result="boundary"/>',
        "merge": (
            '<feMerge result="boundary"><feMergeNode in="encoded"/></feMerge>'
        ),
        "composite-copy": (
            '<feFlood flood-color="black" flood-opacity="0" result="aux"/>'
            '<feComposite in="encoded" in2="aux" operator="arithmetic" '
            'k1="0" k2="1" k3="0" k4="0" result="boundary"/>'
        ),
        "composite-add": (
            '<feColorMatrix in="SourceGraphic" values="0 0 0 0 .5 '
            '0 0 0 0 .5 0 0 0 0 .5 0 0 0 1 0" result="aux"/>'
            '<feComposite in="encoded" in2="aux" operator="arithmetic" '
            'k1="0" k2="1" k3="1" k4="-.5" result="boundary"/>'
        ),
        "composite-multiply": (
            '<feFlood flood-color="white" result="aux"/>'
            '<feComposite in="encoded" in2="aux" operator="arithmetic" '
            'k1="1" k2="0" k3="0" k4="0" result="boundary"/>'
        ),
        "blend": (
            '<feFlood flood-color="black" flood-opacity="0" result="aux"/>'
            '<feBlend in="encoded" in2="aux" mode="normal" result="boundary"/>'
        ),
        "blur-zero": (
            '<feGaussianBlur in="encoded" stdDeviation="0" result="boundary"/>'
        ),
        "blur-small": (
            '<feGaussianBlur in="encoded" stdDeviation="0.001" result="boundary"/>'
        ),
        "convolve": (
            '<feConvolveMatrix in="encoded" order="1" kernelMatrix="1" '
            'divisor="1" result="boundary"/>'
        ),
        "convolve-preserve-alpha": (
            '<feConvolveMatrix in="encoded" order="1" kernelMatrix="1" '
            'divisor="1" preserveAlpha="true" result="boundary"/>'
        ),
        "hdr-seed-add-convolve": (
            '<feImage href="../svg-avif-precision/values-hdr-12bit.avif" '
            'x="{sample}" y="{row}" width="1" height="1" preserveAspectRatio="none" result="hdr"/>'
            '<feColorMatrix in="hdr" values="0 0 0 0 0 0 0 0 0 0 '
            '0 0 0 0 0 0 0 0 0 0" result="hdr-zero"/>'
            '<feComposite in="encoded" in2="hdr-zero" operator="arithmetic" '
            'k1="0" k2="1" k3="1" k4="0" result="seeded"/>'
            '<feConvolveMatrix in="seeded" order="1" kernelMatrix="1" '
            'divisor="1" result="boundary"/>'
        ),
        "hdr-seed-multiply-convolve": (
            '<feImage href="../svg-avif-precision/values-hdr-12bit.avif" '
            'x="{sample}" y="{row}" width="1" height="1" preserveAspectRatio="none" result="hdr"/>'
            '<feColorMatrix in="hdr" values="0 0 0 0 1 0 0 0 0 1 '
            '0 0 0 0 1 0 0 0 0 1" result="hdr-one"/>'
            '<feComposite in="encoded" in2="hdr-one" operator="arithmetic" '
            'k1="1" k2="0" k3="0" k4="0" result="seeded"/>'
            '<feConvolveMatrix in="seeded" order="1" kernelMatrix="1" '
            'divisor="1" result="boundary"/>'
        ),
        "transfer": (
            '<feComponentTransfer in="encoded" result="boundary">'
            '<feFuncR type="identity"/><feFuncG type="identity"/>'
            '<feFuncB type="identity"/><feFuncA type="identity"/>'
            '</feComponentTransfer>'
        ),
    }
    rows = []
    filters = []
    rects = []
    row = 0
    for mode, interpolation, source, channel in modes:
        for boundary_name, boundary_template in boundaries.items():
            rows.append({
                "row": row,
                "mode": mode,
                "interpolation": interpolation,
                "source": source,
                "channel": channel,
                "boundary": boundary_name,
            })
            for sample in range(SAMPLES):
                boundary_markup = boundary_template.format(sample=sample, row=row)
                value = BASE + SPAN * sample / (SAMPLES - 1)
                name = f"f-{row}-{sample}"
                boundary_input = "boundary" if boundary_markup else "encoded"
                filters.append(
                    f'<filter id="{name}" x="{sample}" y="{row}" width="1" height="1" '
                    f'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
                    f'color-interpolation-filters="{interpolation}">'
                    f'<feColorMatrix in="SourceGraphic" values="{matrix_constant(value, channel)}" '
                    f'result="encoded"/>{boundary_markup}'
                    f'<feColorMatrix in="{boundary_input}" values="{matrix_amplify(channel)}"/>'
                    '</filter>'
                )
                rects.append(
                    f'<rect x="{sample}" y="{row}" width="1" height="1" '
                    f'fill="{source}" filter="url(#{name})"/>'
                )
            row += 1

    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>SVG internal precision probe</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{SAMPLES}" height="{row}" viewBox="0 0 {SAMPLES} {row}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>{"".join(rects)}</svg>'
    )
    (OUTPUT / "index.html").write_text(html)
    import json
    (OUTPUT / "reference.json").write_text(json.dumps({
        "samples": SAMPLES,
        "base": BASE,
        "span": SPAN,
        "gain": GAIN,
        "idealOutput": [0.25 + GAIN * SPAN * i / (SAMPLES - 1) for i in range(SAMPLES)],
        "rows": rows,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
