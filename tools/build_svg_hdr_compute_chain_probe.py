#!/usr/bin/env python3
"""Build repeated two-input HDR arithmetic/convolution chains without JavaScript."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-hdr-compute-chain"
WIDTH = 64
DEPTH = 12
MAX_CODE = (1 << DEPTH) - 1
LOW_CODE = 2080
HIGH_CODE = 2143
# Recovered from the amplified direct PQ source in svg-avif-precision.
LOW_LINEAR = 0.49130784
HIGH_LINEAR = 0.57080429


def write_y4m(path: Path, width: int, samples: list[int]) -> None:
    header = f"YUV4MPEG2 W{width} H1 F1:1 Ip A1:1 Cmono12 XCOLORRANGE=FULL\nFRAME\n"
    path.write_bytes(header.encode() + b"".join(struct.pack("<H", value) for value in samples))


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


def linear_to_srgb(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.0031308,
        12.92 * values,
        1.055 * np.power(values, 1 / 2.4) - 0.055,
    )


def chain_filter(name: str, row: int, source: str, multiplier: str, depth: int) -> str:
    delta = HIGH_LINEAR - LOW_LINEAR
    k1 = 1 / delta
    k2 = -LOW_LINEAR / delta
    k3 = -LOW_LINEAR / delta
    k4 = LOW_LINEAR + LOW_LINEAR * LOW_LINEAR / delta
    stages: list[str] = []
    previous = "values"
    for index in range(depth):
        arithmetic = f"arithmetic-{index}"
        reduced = f"reduced-{index}"
        stages.append(
            f'<feComposite in="{previous}" in2="multiplier" operator="arithmetic" '
            f'k1="{k1:.12g}" k2="{k2:.12g}" k3="{k3:.12g}" k4="{k4:.12g}" '
            f'result="{arithmetic}"/>'
            f'<feConvolveMatrix in="{arithmetic}" order="1" kernelMatrix="1" '
            f'divisor="1" result="{reduced}"/>'
        )
        previous = reduced
    gain = 0.5 / delta
    offset = 0.25 - gain * LOW_LINEAR
    matrix_row = f"{gain:.12g} 0 0 0 {offset:.12g}"
    output_matrix = f"{matrix_row} {matrix_row} {matrix_row} 0 0 0 1 0"
    return (
        f'<filter id="{name}" x="0" y="{row}" width="{WIDTH}" height="1" '
        'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
        'color-interpolation-filters="linearRGB">'
        f'<feImage href="{source}" x="0" y="{row}" width="{WIDTH}" height="1" '
        'preserveAspectRatio="none" result="values"/>'
        f'<feImage href="{multiplier}" x="0" y="{row}" width="{WIDTH}" height="1" '
        'preserveAspectRatio="none" result="multiplier"/>'
        f'{"".join(stages)}'
        f'<feColorMatrix in="{previous}" values="{output_matrix}"/>'
        '</filter>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    codes = list(range(LOW_CODE, HIGH_CODE + 1))
    values_y4m = OUT / "values-pq-12bit.y4m"
    multiplier_y4m = OUT / "multiplier-pq-12bit.y4m"
    write_y4m(values_y4m, WIDTH, codes)
    write_y4m(multiplier_y4m, 1, [HIGH_CODE])
    encode_avif(values_y4m, OUT / "values-pq-12bit.avif")
    encode_avif(multiplier_y4m, OUT / "multiplier-pq-12bit.avif")

    linear_values = np.linspace(LOW_LINEAR, HIGH_LINEAR, WIDTH)
    sdr_codes = np.rint(np.clip(linear_to_srgb(linear_values), 0, 1) * 255).astype(np.uint8)
    multiplier_code = int(round(float(linear_to_srgb(np.asarray(HIGH_LINEAR))) * 255))
    Image.fromarray(sdr_codes.reshape(1, WIDTH), mode="L").save(OUT / "values-sdr.png")
    Image.fromarray(np.asarray([[multiplier_code]], dtype=np.uint8), mode="L").save(
        OUT / "multiplier-sdr.png"
    )

    cases: list[tuple[str, str, str, int]] = []
    for mode, source, multiplier in (
        ("hdr", "values-pq-12bit.avif", "multiplier-pq-12bit.avif"),
        ("sdr", "values-sdr.png", "multiplier-sdr.png"),
    ):
        for depth in (0, 1, 2, 4, 8, 12):
            cases.append((f"{mode}-depth-{depth}", source, multiplier, depth))
    filters: list[str] = []
    rects: list[str] = []
    rows: list[dict[str, object]] = []
    for row, (name, source, multiplier, depth) in enumerate(cases):
        filters.append(chain_filter(name, row, source, multiplier, depth))
        rects.append(
            f'<rect x="0" y="{row}" width="{WIDTH}" height="1" fill="black" '
            f'filter="url(#{name})"/>'
        )
        rows.append({
            "row": row,
            "name": name,
            "mode": name.split("-", 1)[0],
            "depth": depth,
        })
    html = (
        '<!doctype html><meta charset="utf-8"><title>HDR compute chain</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{WIDTH}" height="{len(cases)}" viewBox="0 0 {WIDTH} {len(cases)}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>{"".join(rects)}</svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "lowCode": LOW_CODE,
                "highCode": HIGH_CODE,
                "lowLinear": LOW_LINEAR,
                "highLinear": HIGH_LINEAR,
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
