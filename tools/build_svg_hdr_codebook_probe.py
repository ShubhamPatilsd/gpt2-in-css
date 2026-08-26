#!/usr/bin/env python3
"""Build raw and locally amplified pages for calibrating all 4096 PQ codes."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-hdr-codebook"
SIDE = 64
DEPTH = 12
CODE_COUNT = 1 << DEPTH


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.04045,
        values / 12.92,
        np.power((values + 0.055) / 1.055, 2.4),
    )


def write_ramp(path: Path) -> None:
    header = f"YUV4MPEG2 W{SIDE} H{SIDE} F1:1 Ip A1:1 Cmono12 XCOLORRANGE=FULL\nFRAME\n"
    samples = b"".join(struct.pack("<H", code) for code in range(CODE_COUNT))
    path.write_bytes(header.encode() + samples)


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


def raw_page() -> str:
    identity = "1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 1 0"
    return f'''<!doctype html><meta charset="utf-8"><title>PQ codebook raw</title>
<style>html,body{{margin:0;background:#000}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="{SIDE}" height="{SIDE}" viewBox="0 0 {SIDE} {SIDE}" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="raw" x="0" y="0" width="{SIDE}" height="{SIDE}"
 filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" color-interpolation-filters="linearRGB">
<feImage href="pq-ramp-12bit.avif" x="0" y="0" width="{SIDE}" height="{SIDE}"
 preserveAspectRatio="none" result="source"/><feColorMatrix in="source" values="{identity}"/>
</filter></defs><rect width="{SIDE}" height="{SIDE}" fill="black" filter="url(#raw)"/></svg>'''


def calibrated_page(raw_values: np.ndarray) -> tuple[str, list[dict[str, float]]]:
    linear = srgb_to_linear(raw_values.astype(np.float64) / 255)
    filters: list[str] = []
    rects: list[str] = []
    calibration: list[dict[str, float]] = []
    for row in range(SIDE):
        row_values = linear[row]
        low = float(np.min(row_values))
        high = float(np.max(row_values))
        if high - low < 1e-5:
            gain = 1.0
            offset = 0.0
        else:
            gain = 0.6 / (high - low)
            offset = 0.2 - gain * low
        calibration.append({"row": row, "gain": gain, "offset": offset})
        matrix_row = f"{gain:.12g} 0 0 0 {offset:.12g}"
        matrix = f"{matrix_row} {matrix_row} {matrix_row} 0 0 0 1 0"
        filters.append(
            f'<filter id="row-{row}" x="0" y="{row}" width="{SIDE}" height="1" '
            'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
            'color-interpolation-filters="linearRGB">'
            f'<feImage href="pq-ramp-12bit.avif" x="0" y="0" width="{SIDE}" height="{SIDE}" '
            'preserveAspectRatio="none" result="source"/>'
            f'<feColorMatrix in="source" values="{matrix}"/>'
            '</filter>'
        )
        rects.append(
            f'<rect x="0" y="{row}" width="{SIDE}" height="1" fill="black" '
            f'filter="url(#row-{row})"/>'
        )
    html = (
        '<!doctype html><meta charset="utf-8"><title>PQ codebook calibrated</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{SIDE}" height="{SIDE}" viewBox="0 0 {SIDE} {SIDE}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>{"".join(rects)}</svg>'
    )
    return html, calibration


def finalize_codebook(profile: str) -> None:
    measured = json.loads((OUT / f"calibrated-{profile}.json").read_text())
    calibration = json.loads((OUT / f"calibration-{profile}.json").read_text())
    output = srgb_to_linear(np.asarray(measured["values"], dtype=np.float64) / 255)
    recovered = np.empty((SIDE, SIDE), dtype=np.float64)
    for row in range(SIDE):
        gain = calibration[row]["gain"]
        offset = calibration[row]["offset"]
        recovered[row] = (output[row] - offset) / gain
    flattened = recovered.reshape(-1)
    # Screenshot rounding can create tiny reversals. PQ decode itself is monotonic.
    flattened = np.maximum.accumulate(flattened)
    (OUT / f"codebook-{profile}.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "codes": list(range(CODE_COUNT)),
                "linear": flattened.tolist(),
                "uniqueRecoveredLevels": int(np.unique(np.round(flattened, 8)).size),
                "range": [float(flattened[0]), float(flattened[-1])],
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("raw", "calibrated", "finalize"), default="raw")
    parser.add_argument("--profile", default="srgb")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == "raw":
        source = OUT / "pq-ramp-12bit.y4m"
        write_ramp(source)
        encode_avif(source, OUT / "pq-ramp-12bit.avif")
        (OUT / "raw.html").write_text(raw_page())
    elif args.stage == "calibrated":
        raw = json.loads((OUT / f"raw-{args.profile}.json").read_text())
        html, calibration = calibrated_page(np.asarray(raw["values"], dtype=np.uint8))
        (OUT / "calibrated.html").write_text(html)
        (OUT / f"calibration-{args.profile}.json").write_text(
            json.dumps(calibration, indent=2) + "\n"
        )
    else:
        finalize_codebook(args.profile)


if __name__ == "__main__":
    main()
