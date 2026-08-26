#!/usr/bin/env python3
"""Build scalar and two-lane SWAR anchor matvec probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "anchor-swar-matvec"
RADIX = 32_768
HALF_RADIX = RADIX // 2
OUTPUT_BASE = 500_000


def balanced_sum(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced_sum(terms[:middle])} + {balanced_sum(terms[middle:])})"


def pair_code(a0: int, a1: int) -> int:
    return a0 + RADIX * a1


def pair_weight(w0: int, w1: int) -> int:
    return w1 + RADIX * w0


def pair_dot_expression(packet: int, w0: int, w1: int) -> str:
    packed_weight = pair_weight(w0, w1)
    source = f"(anchor-size(--p-{packet} width) / 1px)"
    # The product's radix-1 coefficient is a0*w0 + a1*w1. RADIX is
    # large enough that the lower coefficient is < 0.5 radix and the signed
    # pair dot remains inside (-RADIX/2, RADIX/2), so nearest-rounding plus a
    # centered modulo recovers it exactly while the full product stays below
    # JavaScript/CSS double's 53-bit integer boundary.
    return (
        "1px * (mod("
        f"round(nearest,({source} * {packed_weight}) / {RADIX},1)"
        f" + {HALF_RADIX},{RADIX}) - {HALF_RADIX})"
    )


def build(width: int, output_width: int, seed: int) -> dict[str, object]:
    if width % 2:
        raise ValueError("input width must be even")
    rng = np.random.default_rng(seed)
    inputs = rng.integers(0, 64, size=(2, width), dtype=np.int64)
    weights = rng.integers(-127, 128, size=(output_width, width), dtype=np.int64)
    expected = inputs @ weights.T
    packet_widths = np.stack([
        inputs[:, 0::2] + RADIX * inputs[:, 1::2]
    ], axis=0)[0]

    scalar_sources = "".join(
        f'<i class="source" data-index="{index}" '
        f'style="width:{int(value)}px;anchor-name:--s-{index}"></i>'
        for index, value in enumerate(inputs[0])
    )
    pair_sources = "".join(
        f'<i class="source" data-index="{index}" '
        f'style="width:{int(value)}px;anchor-name:--p-{index}"></i>'
        for index, value in enumerate(packet_widths[0])
    )

    scalar_rules = []
    pair_rules = []
    outputs = []
    for output, row in enumerate(weights):
        scalar_terms = [
            f"{int(weight)} * anchor-size(--s-{index} width)"
            for index, weight in enumerate(row)
        ]
        pair_terms = [
            pair_dot_expression(packet, int(row[index]), int(row[index + 1]))
            for packet, index in enumerate(range(0, width, 2))
        ]
        scalar_rules.append(
            f".o-{output}{{width:calc({OUTPUT_BASE}px + "
            f"{balanced_sum(scalar_terms)})}}"
        )
        pair_rules.append(
            f".o-{output}{{width:calc({OUTPUT_BASE}px + "
            f"{balanced_sum(pair_terms)})}}"
        )
        outputs.append(f'<i class="output o-{output}"></i>')

    common_css = (
        "html,body{margin:0}.stage{position:fixed;inset:0;contain:layout style}"
        ".source,.output{position:fixed;left:0;top:0;height:1px;display:block;"
        "visibility:hidden}"
    )
    pages = {}
    for variant, sources, rules in (
        ("scalar", scalar_sources, scalar_rules),
        ("pair", pair_sources, pair_rules),
    ):
        html = (
            "<!doctype html><meta charset=\"utf-8\"><title>"
            f"Anchor {variant} matvec {width}x{output_width}</title><style>"
            f"{common_css}{''.join(rules)}</style><main class=\"stage\">"
            f"{sources}{''.join(outputs)}</main>"
        )
        name = f"n{width}x{output_width}-{variant}.html"
        (OUT / name).write_text(html)
        pages[variant] = {"page": name, "bytes": len(html.encode())}

    reference = {
        "inputWidth": width,
        "outputWidth": output_width,
        "radix": RADIX,
        "outputBase": OUTPUT_BASE,
        "inputs": inputs.tolist(),
        "pairWidths": packet_widths.tolist(),
        "expected": expected.tolist(),
        "pages": pages,
        "scalarTerms": width * output_width,
        "pairTerms": width * output_width // 2,
        "scalarSources": width,
        "pairSources": width // 2,
    }
    reference_name = f"n{width}x{output_width}.json"
    (OUT / reference_name).write_text(json.dumps(reference, indent=2) + "\n")
    return {"reference": reference_name, **reference}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="128,256,384")
    parser.add_argument("--output-width", type=int)
    parser.add_argument(
        "--shapes",
        help="comma-separated inputxoutput shapes; overrides --sizes",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.shapes:
        shapes = [
            tuple(int(value) for value in item.split("x", maxsplit=1))
            for item in args.shapes.split(",")
            if item
        ]
    else:
        shapes = [
            (width, args.output_width or width)
            for width in (int(item) for item in args.sizes.split(",") if item)
        ]
    manifest = [
        build(width, output_width, 0x5A17 + width + output_width * 17)
        for width, output_width in shapes
    ]
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps([
        {
            "shape": f"{item['inputWidth']}x{item['outputWidth']}",
            "scalarBytes": item["pages"]["scalar"]["bytes"],
            "pairBytes": item["pages"]["pair"]["bytes"],
        }
        for item in manifest
    ], indent=2))


if __name__ == "__main__":
    main()
