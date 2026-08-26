#!/usr/bin/env python3
"""Build a 256x256 four-metrics-per-font transport benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import brotli
import numpy as np

from build_font_metric_vector_probe import FONT_SIZE, UNITS_PER_EM, axis_tag, build_font
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-metric-vector" / "256"
SIZE = 256
CHANNELS = 4
BASE_METRIC = 12_000
SEED = 0x47505432


def inputs_for_size(size: int) -> tuple[np.ndarray, np.ndarray]:
    """Match the existing matrix-scaling benchmark without importing Pillow."""
    rng = np.random.default_rng(SEED + size)
    weights = rng.integers(-32, 33, size=(size, size), dtype=np.int16)
    vector = rng.integers(0, 5, size=size).astype(np.float64) / 4
    return weights, vector


def compressed_size(path: Path) -> int:
    return len(brotli.compress(path.read_bytes(), quality=11))


def build_html(vector: np.ndarray, expected: np.ndarray, *, use_ttf: bool = False) -> str:
    settings = ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(vector)
    )
    font_faces = []
    registrations = []
    producer_rules = []
    for group in range(SIZE // CHANNELS):
        family = f"MetricVector{group:03d}"
        suffix = "ttf" if use_ttf else "woff2"
        font_format = "truetype" if use_ttf else "woff2"
        font_faces.append(
            f'@font-face{{font-family:{family};src:url("metric-{group:03d}.{suffix}?v=2") format("{font_format}")}}'
        )
        first = group * CHANNELS
        for output in range(first, first + CHANNELS):
            registrations.append(
                f'@property --mv-y-{output:03d}'
                '{syntax:"<number>";inherits:true;initial-value:-99999}'
            )
        producer_rules.append(
            f'.p{group:03d}{{font-family:{family};'
            f'--mv-y-{first:03d}:calc(1ex/1px*{UNITS_PER_EM}/{FONT_SIZE} - {BASE_METRIC});'
            f'--mv-y-{first + 1:03d}:calc(1cap/1px*{UNITS_PER_EM}/{FONT_SIZE} - {BASE_METRIC});'
            f'--mv-y-{first + 2:03d}:calc(1ch/1px*{UNITS_PER_EM}/{FONT_SIZE} - {BASE_METRIC});'
            f'--mv-y-{first + 3:03d}:calc(1ic/1px*{UNITS_PER_EM}/{FONT_SIZE} - {BASE_METRIC})}}'
        )

    chain = '<div id="metric-result" class="result"></div>'
    for group in reversed(range(SIZE // CHANNELS)):
        chain = f'<div class="producer p{group:03d}">{chain}</div>'

    expected_data = ",".join(f"{value:g}" for value in expected)
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>256x256 four-metric transport</title>
<style>
{''.join(font_faces)}
{''.join(registrations)}
html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
body{{margin:2rem;max-width:52rem}}
.metric-root{{font-size:{FONT_SIZE}px;font-variation-settings:{settings};height:0}}
.producer{{height:0;width:1ex}}
.producer::before{{content:"xH0水";position:absolute;color:transparent}}
{''.join(producer_rules)}
.result{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
</style>
<h1>256×256 four-metric matrix transport</h1>
<p id="reference" data-expected="{expected_data}">No JavaScript. One font instance exposes four matrix rows.</p>
<div class="metric-root">{chain}</div>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--ttf", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    weights, vector = inputs_for_size(SIZE)
    expected = weights.astype(np.float64) @ vector
    if not args.html_only:
        for group in range(SIZE // CHANNELS):
            first = group * CHANNELS
            build_font(
                weights[first : first + CHANNELS],
                OUT / f"metric-{group:03d}.ttf",
                family_name=f"Metric Vector {group:03d}",
                base_metric=BASE_METRIC,
                signed_axes=False,
            )
    html_path = OUT / "index.html"
    html_path.write_text(build_html(vector, expected, use_ttf=args.ttf))
    woff2_paths = sorted(OUT.glob("metric-*.woff2"))
    ttf_paths = sorted(OUT.glob("metric-*.ttf"))
    ttf_bytes = sum(path.stat().st_size for path in ttf_paths)
    woff2_bytes = sum(path.stat().st_size for path in woff2_paths)
    page_font_bytes = ttf_bytes if args.ttf else woff2_bytes
    metadata = {
        "size": SIZE,
        "channels_per_font": CHANNELS,
        "font_count": len(woff2_paths),
        "page_font_format": "ttf" if args.ttf else "woff2",
        "expected": expected.tolist(),
        "html_bytes": html_path.stat().st_size,
        "ttf_bytes": ttf_bytes,
        "woff2_bytes": woff2_bytes,
        "runtime_raw_bytes": html_path.stat().st_size + page_font_bytes,
        "woff2_candidate_brotli_bytes": compressed_size(html_path)
        + sum(compressed_size(path) for path in woff2_paths),
    }
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(metadata | {"expected": metadata["expected"][:4]})


if __name__ == "__main__":
    main()
