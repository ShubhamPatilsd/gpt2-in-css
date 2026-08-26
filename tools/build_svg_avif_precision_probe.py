#!/usr/bin/env python3
"""Build a no-JS SVG probe using a lossless 12-bit AVIF source."""

import json
import shutil
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-avif-precision"
WIDTH = 64
DEPTH = 12
MAX_CODE = (1 << DEPTH) - 1
BASE_CODE = 2080
GAIN = 8


def write_y4m(path: Path) -> None:
    header = f"YUV4MPEG2 W{WIDTH} H1 F1:1 Ip A1:1 Cmono12 XCOLORRANGE=FULL\nFRAME\n"
    samples = b"".join(struct.pack("<H", BASE_CODE + index) for index in range(WIDTH))
    path.write_bytes(header.encode() + samples)


def encode_avif(source: Path, target: Path, cicp: str) -> None:
    encoder = shutil.which("avifenc")
    if not encoder:
        raise SystemExit("avifenc is required")
    subprocess.run([
        encoder,
        "--lossless",
        "--cicp", cicp,
        "--jobs", "all",
        str(source),
        str(target),
    ], check=True, capture_output=True, text=True)


def filter_markup(
    name: str,
    href: str,
    row: int,
    interpolation: str,
    boundary: str,
) -> str:
    base = BASE_CODE / MAX_CODE
    offset = 0.25 - GAIN * base
    matrix = (
        f"{GAIN} 0 0 0 {offset:.12g} "
        f"0 {GAIN} 0 0 {offset:.12g} "
        f"0 0 {GAIN} 0 {offset:.12g} "
        "0 0 0 1 0"
    )
    boundaries = {
        "direct": "",
        "offset": '<feOffset in="source" dx="0" dy="0" result="boundary"/>',
        "convolve": (
            '<feConvolveMatrix in="source" order="1" kernelMatrix="1" '
            'divisor="1" result="boundary"/>'
        ),
        "transfer": (
            '<feComponentTransfer in="source" result="boundary">'
            '<feFuncR type="identity"/><feFuncG type="identity"/>'
            '<feFuncB type="identity"/><feFuncA type="identity"/>'
            '</feComponentTransfer>'
        ),
        "composite-copy": (
            '<feFlood flood-color="black" flood-opacity="0" result="aux"/>'
            '<feComposite in="source" in2="aux" operator="arithmetic" '
            'k1="0" k2="1" k3="0" k4="0" result="boundary"/>'
        ),
        "composite-multiply": (
            '<feFlood flood-color="white" result="aux"/>'
            '<feComposite in="source" in2="aux" operator="arithmetic" '
            'k1="1" k2="0" k3="0" k4="0" result="boundary"/>'
        ),
    }
    boundary_markup = boundaries[boundary]
    matrix_input = "boundary" if boundary_markup else "source"
    return (
        f'<filter id="{name}" x="0" y="{row}" width="{WIDTH}" height="1" '
        f'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
        f'color-interpolation-filters="{interpolation}">'
        f'<feImage href="{href}" x="0" y="{row}" width="{WIDTH}" height="1" '
        f'preserveAspectRatio="none" result="source"/>'
        f'{boundary_markup}<feColorMatrix in="{matrix_input}" values="{matrix}"/>'
        '</filter>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT / "values-12bit.y4m"
    write_y4m(source)
    encode_avif(source, OUT / "values-sdr-12bit.avif", "1/13/0")
    encode_avif(source, OUT / "values-hdr-12bit.avif", "9/16/0")
    encode_avif(source, OUT / "values-linear709-12bit.avif", "1/8/0")
    encode_avif(source, OUT / "values-linear2020-12bit.avif", "9/8/0")
    encode_avif(source, OUT / "values-hlg-12bit.avif", "9/18/0")
    sources = [
        ("sdr-srgb", "values-sdr-12bit.avif", "sRGB"),
        ("sdr-linear", "values-sdr-12bit.avif", "linearRGB"),
        ("hdr-srgb", "values-hdr-12bit.avif", "sRGB"),
        ("hdr-linear", "values-hdr-12bit.avif", "linearRGB"),
        ("linear709-srgb", "values-linear709-12bit.avif", "sRGB"),
        ("linear709-linear", "values-linear709-12bit.avif", "linearRGB"),
        ("linear2020-srgb", "values-linear2020-12bit.avif", "sRGB"),
        ("linear2020-linear", "values-linear2020-12bit.avif", "linearRGB"),
        ("hlg-srgb", "values-hlg-12bit.avif", "sRGB"),
        ("hlg-linear", "values-hlg-12bit.avif", "linearRGB"),
    ]
    boundaries = (
        "direct",
        "offset",
        "convolve",
        "transfer",
        "composite-copy",
        "composite-multiply",
    )
    rows = [
        (f"{name}-{boundary}", href, interpolation, boundary)
        for name, href, interpolation in sources
        for boundary in boundaries
    ]
    filters = []
    images = []
    metadata = []
    for row, (name, href, interpolation, boundary) in enumerate(rows):
        filters.append(filter_markup(name, href, row, interpolation, boundary))
        images.append(
            f'<rect x="0" y="{row}" width="{WIDTH}" height="1" fill="black" '
            f'filter="url(#{name})"/>'
        )
        metadata.append({
            "row": row,
            "name": name,
            "href": href,
            "interpolation": interpolation,
            "boundary": boundary,
        })
    html = (
        '<!doctype html><meta charset="utf-8"><title>12-bit AVIF SVG precision</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{WIDTH}" height="{len(rows)}" viewBox="0 0 {WIDTH} {len(rows)}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>{"".join(images)}</svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(json.dumps({
        "width": WIDTH,
        "depth": DEPTH,
        "baseCode": BASE_CODE,
        "gain": GAIN,
        "idealOutput": [0.25 + GAIN * index / MAX_CODE for index in range(WIDTH)],
        "rows": metadata,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
