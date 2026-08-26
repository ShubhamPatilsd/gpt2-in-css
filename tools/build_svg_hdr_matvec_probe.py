#!/usr/bin/env python3
"""Build a real GPT-2 64x64 SVG matvec with SDR and 12-bit HDR operands."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-hdr-matvec"
WIDTH = 64
DEPTH = 12
LOW_CODE = 2080
HIGH_CODE = 2143
GAMMA = 0.45
CENTER = 0.5


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.04045,
        values / 12.92,
        np.power((values + 0.055) / 1.055, 2.4),
    )


def linear_to_srgb(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.0031308,
        12.92 * values,
        1.055 * np.power(values, 1 / 2.4) - 0.055,
    )


def hdr_codebook() -> tuple[np.ndarray, np.ndarray]:
    full_codebook = ROOT / "experiments/svg-hdr-codebook/codebook-srgb.json"
    if full_codebook.exists():
        data = json.loads(full_codebook.read_text())
        codes = np.asarray(data["codes"], dtype=np.int64)
        internal = np.asarray(data["linear"], dtype=np.float64)
        usable = (internal >= 0.05) & (internal <= 0.95)
        return codes[usable], internal[usable]
    result = json.loads((ROOT / "experiments/svg-avif-precision/results.json").read_text())
    profile = next(item for item in result["profiles"] if item["profile"] == "srgb")
    row = next(item for item in profile["rows"] if item["name"] == "hdr-linear-direct")
    output = srgb_to_linear(np.asarray(row["values"], dtype=np.float64) / 255)
    base = LOW_CODE / ((1 << DEPTH) - 1)
    internal = base + (output - 0.25) / 8
    return np.arange(LOW_CODE, HIGH_CODE + 1), internal


def encode_hdr(values: np.ndarray, low: float, high: float, code_values: np.ndarray,
               linear_values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    targets = low + (np.clip(values, -1, 1) + 1) * (high - low) / 2
    indices = np.abs(targets[..., None] - linear_values).argmin(axis=-1)
    codes = code_values[indices].astype(np.uint16)
    effective = 2 * (linear_values[indices] - low) / (high - low) - 1
    return codes, effective


def encode_sdr(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    target = CENTER + np.clip(values, -1, 1) / 2
    codes = np.rint(np.clip(target, 0, 1) * 255).astype(np.uint8)
    decoded = codes.astype(np.float64) / 255
    return codes, 2 * (decoded - CENTER)


def write_y4m(path: Path, values: np.ndarray) -> None:
    height, width = values.shape
    header = f"YUV4MPEG2 W{width} H{height} F1:1 Ip A1:1 Cmono12 XCOLORRANGE=FULL\nFRAME\n"
    samples = b"".join(struct.pack("<H", int(value)) for value in values.flat)
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


def save_sdr(path: Path, values: np.ndarray) -> None:
    Image.fromarray(values, mode="L").save(path, optimize=True)


def filter_markup(
    name: str,
    column: int,
    input_href: str,
    weight_href: str,
    midpoint: float,
    half_range: float,
    output_bound: float,
    interpolation: str,
) -> str:
    k1 = GAMMA / (half_range * half_range)
    k2 = -GAMMA * midpoint / (half_range * half_range)
    k3 = k2
    k4 = midpoint + GAMMA * midpoint * midpoint / (half_range * half_range)
    kernel = " ".join("1" for _ in range(WIDTH))
    divisor = 2 * GAMMA * output_bound
    bias = midpoint - WIDTH * midpoint / divisor
    row = f"1 0 0 0 {0.5 - midpoint:.12g}"
    decode = f"{row} {row} {row} 0 0 0 1 0"
    return (
        f'<filter id="{name}" x="0" y="0" width="{WIDTH}" height="{WIDTH}" '
        'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
        f'color-interpolation-filters="{interpolation}">'
        f'<feImage href="{input_href}" x="0" y="0" width="{WIDTH}" height="1" '
        'preserveAspectRatio="none" result="input"/>'
        f'<feTile in="input" x="0" y="0" width="{WIDTH}" height="{WIDTH}" result="input-tile"/>'
        f'<feImage href="{weight_href}" x="0" y="0" width="{WIDTH}" height="{WIDTH}" '
        'preserveAspectRatio="none" result="weights"/>'
        '<feComposite in="weights" in2="input-tile" operator="arithmetic" '
        f'k1="{k1:.12g}" k2="{k2:.12g}" k3="{k3:.12g}" k4="{k4:.12g}" '
        'result="products"/>'
        f'<feConvolveMatrix in="products" order="{WIDTH} 1" kernelMatrix="{kernel}" '
        f'divisor="{divisor:.12g}" bias="{bias:.12g}" targetX="{WIDTH - 1}" '
        'targetY="0" edgeMode="none" '
        f'preserveAlpha="false" x="{WIDTH - 1}" y="0" width="1" height="{WIDTH}" '
        'result="averages"/>'
        f'<feColorMatrix in="averages" values="{decode}" result="decoded"/>'
        f'<feOffset in="decoded" dx="{-WIDTH + 1 + column}" x="{column}" y="0" '
        f'width="1" height="{WIDTH}"/>'
        '</filter>'
    )


def direct_filter_markup(
    matrix: np.ndarray,
    midpoint: float,
    half_range: float,
    output_bound: float,
) -> str:
    tiled = (
        f'<feImage href="input-hdr.avif" x="0" y="0" width="{WIDTH}" height="1" '
        'preserveAspectRatio="none" result="input"/>'
        f'<feTile in="input" x="0" y="0" width="{WIDTH}" height="{WIDTH}" '
        'result="input-tile"/>'
    )
    divisor = 2 * half_range * output_bound
    rows: list[str] = []
    for output, weights in enumerate(matrix):
        reversed_weights = weights[::-1]
        kernel = " ".join(f"{value:.10g}" for value in reversed_weights)
        bias = 0.5 - midpoint * float(np.sum(weights)) / divisor
        rows.append(
            f'<feConvolveMatrix in="input-tile" order="{WIDTH} 1" kernelMatrix="{kernel}" '
            f'divisor="{divisor:.12g}" bias="{bias:.12g}" targetX="{WIDTH - 1}" '
            f'targetY="0" edgeMode="none" preserveAlpha="true" x="{WIDTH - 1}" '
            f'y="{output}" width="1" height="1" result="direct-{output}-sum"/>'
            f'<feOffset in="direct-{output}-sum" dx="{-WIDTH + 3}" x="2" y="{output}" '
            f'width="1" height="1" result="direct-{output}"/>'
        )
    merge = "".join(f'<feMergeNode in="direct-{output}"/>' for output in range(WIDTH))
    return (
        f'<filter id="hdr-direct" x="0" y="0" width="{WIDTH}" height="{WIDTH}" '
        'filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
        'color-interpolation-filters="linearRGB">'
        f'{tiled}{"".join(rows)}<feMerge>{merge}</feMerge></filter>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads(
        (ROOT / "experiments/gpt2-block-css/view-timeline-attention-2token-reference.json").read_text()
    )
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64)
    context = np.asarray(reference["context"], dtype=np.float64)[1]
    input_values = context[:WIDTH]
    input_scale = max(float(np.max(np.abs(input_values))) * 1.02, 1e-12)
    normalized_input = input_values / input_scale
    matrix = weights[:WIDTH, :WIDTH].T * input_scale
    row_units = np.maximum(np.max(np.abs(matrix), axis=1), 1e-12)
    normalized_weights = matrix / row_units[:, None]
    expected_float = normalized_weights @ normalized_input

    sdr_input_codes, sdr_input_effective = encode_sdr(normalized_input)
    sdr_weight_codes, sdr_weight_effective = encode_sdr(normalized_weights)
    expected_sdr = sdr_weight_effective @ sdr_input_effective
    save_sdr(OUT / "input-sdr.png", sdr_input_codes.reshape(1, WIDTH))
    save_sdr(OUT / "weights-sdr.png", sdr_weight_codes)

    code_values, linear_values = hdr_codebook()
    low = float(np.min(linear_values))
    high = float(np.max(linear_values))
    hdr_input_codes, hdr_input_effective = encode_hdr(
        normalized_input, low, high, code_values, linear_values
    )
    hdr_weight_codes, hdr_weight_effective = encode_hdr(
        normalized_weights, low, high, code_values, linear_values
    )
    expected_hdr = hdr_weight_effective @ hdr_input_effective
    expected_hdr_direct = normalized_weights @ hdr_input_effective
    input_y4m = OUT / "input-hdr.y4m"
    weights_y4m = OUT / "weights-hdr.y4m"
    write_y4m(input_y4m, hdr_input_codes.reshape(1, WIDTH))
    write_y4m(weights_y4m, hdr_weight_codes)
    encode_avif(input_y4m, OUT / "input-hdr.avif")
    encode_avif(weights_y4m, OUT / "weights-hdr.avif")

    output_bound = max(
        float(np.max(np.abs(expected_float))),
        float(np.max(np.abs(expected_sdr))),
        float(np.max(np.abs(expected_hdr))),
        1e-12,
    ) * 1.08
    filters = [
        filter_markup(
            "sdr",
            0,
            "input-sdr.png",
            "weights-sdr.png",
            CENTER,
            0.5,
            output_bound,
            "sRGB",
        ),
        filter_markup(
            "hdr",
            1,
            "input-hdr.avif",
            "weights-hdr.avif",
            (low + high) / 2,
            (high - low) / 2,
            output_bound,
            "linearRGB",
        ),
        direct_filter_markup(
            normalized_weights,
            (low + high) / 2,
            (high - low) / 2,
            output_bound,
        ),
    ]
    html = (
        '<!doctype html><meta charset="utf-8"><title>HDR SVG GPT-2 matvec</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="3" height="{WIDTH}" viewBox="0 0 3 {WIDTH}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(filters)}</defs>'
        f'<rect width="{WIDTH}" height="{WIDTH}" fill="black" filter="url(#sdr)"/>'
        f'<rect width="{WIDTH}" height="{WIDTH}" fill="black" filter="url(#hdr)"/>'
        f'<rect width="{WIDTH}" height="{WIDTH}" fill="black" filter="url(#hdr-direct)"/>'
        '</svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "outputBound": output_bound,
                "hdrLinearRange": [low, high],
                "hdrUniqueCodesInput": int(np.unique(hdr_input_codes).size),
                "hdrUniqueCodesWeights": int(np.unique(hdr_weight_codes).size),
                "sdrUniqueCodesInput": int(np.unique(sdr_input_codes).size),
                "sdrUniqueCodesWeights": int(np.unique(sdr_weight_codes).size),
                "expectedFloat": expected_float.tolist(),
                "expectedSdrEncoded": expected_sdr.tolist(),
                "expectedHdrEncoded": expected_hdr.tolist(),
                "expectedHdrDirect": expected_hdr_direct.tolist(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
