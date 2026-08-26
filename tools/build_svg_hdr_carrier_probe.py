#!/usr/bin/env python3
"""Build a no-JS probe for carrying computed corrections on an HDR surface."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-hdr-carrier-transport"
SAMPLES = 64
DEPTH = 12
CARRIER_CODE = 2080
SPAN = 1 / 256
GAIN = 128
# Measured from the PQ carrier by the existing amplified direct-source probe.
CARRIER_LINEAR = 0.49131


def write_carrier(path: Path) -> None:
    header = "YUV4MPEG2 W1 H1 F1:1 Ip A1:1 Cmono12 XCOLORRANGE=FULL\nFRAME\n"
    path.write_bytes(header.encode() + struct.pack("<H", CARRIER_CODE))


def encode_avif(source: Path, target: Path) -> None:
    encoder = shutil.which("avifenc")
    if not encoder:
        raise SystemExit("avifenc is required")
    subprocess.run(
        [
            encoder,
            "--lossless",
            "--cicp",
            "9/16/0",
            "--jobs",
            "all",
            str(source),
            str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def constant_matrix(value: float) -> str:
    row = f"0 0 0 0 {value:.12g}"
    return f"{row} {row} {row} 0 0 0 1 0"


def output_matrix() -> str:
    offset = 0.25 - GAIN * CARRIER_LINEAR
    row = f"{GAIN} 0 0 0 {offset:.12g}"
    return f"{row} {row} {row} 0 0 0 1 0"


def filter_markup(name: str, x: int, y: int, mode: str, depth: int) -> str:
    delta = SPAN * x / (SAMPLES - 1)
    if mode == "hdr":
        carrier = (
            f'<feImage href="carrier-pq-12bit.avif" x="{x}" y="{y}" '
            'width="1" height="1" preserveAspectRatio="none" result="carrier"/>'
        )
    else:
        carrier = (
            f'<feColorMatrix in="SourceGraphic" values="{constant_matrix(CARRIER_LINEAR)}" '
            'result="carrier"/>'
        )
    chain = []
    previous = "carried"
    for index in range(depth):
        result = f"stage-{index}"
        chain.append(
            f'<feConvolveMatrix in="{previous}" order="1" kernelMatrix="1" '
            f'divisor="1" result="{result}"/>'
        )
        previous = result
    return (
        f'<filter id="{name}" x="{x}" y="{y}" width="1" height="1" '
        'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
        'color-interpolation-filters="linearRGB">'
        f'<feColorMatrix in="SourceGraphic" values="{constant_matrix(delta)}" result="delta"/>'
        f'{carrier}'
        '<feComposite in="carrier" in2="delta" operator="arithmetic" '
        'k1="0" k2="1" k3="1" k4="0" result="carried"/>'
        f'{"".join(chain)}'
        f'<feColorMatrix in="{previous}" values="{output_matrix()}"/>'
        '</filter>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT / "carrier-12bit.y4m"
    write_carrier(source)
    encode_avif(source, OUT / "carrier-pq-12bit.avif")

    cases = [
        ("hdr-add", "hdr", 0),
        ("hdr-add-convolve1", "hdr", 1),
        ("hdr-add-convolve4", "hdr", 4),
        ("hdr-add-convolve12", "hdr", 12),
        ("sdr-add", "sdr", 0),
        ("sdr-add-convolve1", "sdr", 1),
        ("sdr-add-convolve4", "sdr", 4),
        ("sdr-add-convolve12", "sdr", 12),
    ]
    filters: list[str] = []
    rects: list[str] = []
    rows: list[dict[str, object]] = []
    for y, (name, mode, depth) in enumerate(cases):
        rows.append({"row": y, "name": name, "mode": mode, "depth": depth})
        for x in range(SAMPLES):
            filter_name = f"f-{y}-{x}"
            filters.append(filter_markup(filter_name, x, y, mode, depth))
            rects.append(
                f'<rect x="{x}" y="{y}" width="1" height="1" fill="black" '
                f'filter="url(#{filter_name})"/>'
            )
    html = (
        '<!doctype html><meta charset="utf-8"><title>HDR carrier transport</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{SAMPLES}" height="{len(cases)}" viewBox="0 0 {SAMPLES} {len(cases)}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>{"".join(rects)}</svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "samples": SAMPLES,
                "span": SPAN,
                "gain": GAIN,
                "carrierCode": CARRIER_CODE,
                "carrierLinear": CARRIER_LINEAR,
                "idealOutput": [0.25 + GAIN * SPAN * i / (SAMPLES - 1) for i in range(SAMPLES)],
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
