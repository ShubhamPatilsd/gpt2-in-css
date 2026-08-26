#!/usr/bin/env python3
"""Build one scaled variable-font matrix backend experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import brotli
import numpy as np

from build_matrix_backend_prototypes import (
    FONT_BASE_ADVANCE,
    FONT_SIZE,
    ROOT,
    UNITS_PER_EM,
    build_direct_font_backend,
    build_font_backend,
    variable_font_html,
)


OUT = ROOT / "experiments" / "matrix-scaling"
SEED = 0x47505432


def inputs_for_size(size: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED + size)
    weights = rng.integers(-32, 33, size=(size, size), dtype=np.int16)
    vector = rng.integers(0, 5, size=size).astype(np.float64) / 4
    return weights, vector


def compressed_response_size(path: Path) -> int:
    return len(brotli.compress(path.read_bytes(), quality=11))


def write_index() -> None:
    links = []
    for directory in sorted(
        (path for path in OUT.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    ):
        links.append(
            f'<li><a href="{directory.name}/variable-font.html">'
            f'{directory.name}×{directory.name}</a></li>'
        )
    (OUT / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
        "<title>Variable-font matrix scaling</title>"
        "<style>body{font:16px system-ui;margin:2rem}li{margin:.6rem 0}</style>"
        "<h1>Variable-font matrix scaling</h1><ul>"
        + "".join(links)
        + '<li><a href="768-sharded/index.html">768×768 sharded</a></li>'
        + '</ul><p><a href="RESULTS.md">Measured results</a></p></html>'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args()
    size = args.size
    if not 1 <= size <= 0x10000 - 0xE000:
        raise SystemExit("size must fit in the private-use glyph range")

    destination = OUT / str(size)
    destination.mkdir(parents=True, exist_ok=True)
    weights, vector = inputs_for_size(size)
    expected = weights.astype(np.float64) @ vector

    ttf_path = destination / "variable-matvec.ttf"
    reference_path = destination / "reference.json"
    if args.html_only:
        if not ttf_path.exists() or not ttf_path.with_suffix(".woff2").exists():
            raise SystemExit("font artifacts must exist before --html-only")
        build_seconds = json.loads(reference_path.read_text())["build_seconds"]
    else:
        started = time.perf_counter()
        if size <= 256:
            build_direct_font_backend(weights, ttf_path)
            compiler = "direct-hvar"
        else:
            build_font_backend(weights, ttf_path)
            compiler = "designspace-masters"
        build_seconds = time.perf_counter() - started
    if args.html_only:
        compiler = json.loads(reference_path.read_text()).get(
            "compiler", "designspace-masters"
        )

    html_path = destination / "variable-font.html"
    html = variable_font_html(vector, expected)
    html_path.write_text(html)
    (destination / "variable-font-ttf.html").write_text(
        html.replace(
            'url("variable-matvec.woff2?v=4") format("woff2")',
            'url("variable-matvec.ttf?v=1") format("truetype")',
        )
    )
    woff2_path = destination / "variable-matvec.woff2"
    runtime_raw = html_path.stat().st_size + woff2_path.stat().st_size
    runtime_brotli = compressed_response_size(html_path) + compressed_response_size(
        woff2_path
    )
    metadata = {
        "size": size,
        "compiler": compiler,
        "weights": size * size,
        "weights_sha256": hashlib.sha256(weights.tobytes()).hexdigest(),
        "input": vector.tolist(),
        "expected": expected.tolist(),
        "base_advance": FONT_BASE_ADVANCE,
        "units_per_em": UNITS_PER_EM,
        "font_size_px": FONT_SIZE,
        "build_seconds": build_seconds,
        "ttf_bytes": ttf_path.stat().st_size,
        "woff2_bytes": woff2_path.stat().st_size,
        "html_bytes": html_path.stat().st_size,
        "runtime_raw_bytes": runtime_raw,
        "runtime_brotli_bytes": runtime_brotli,
    }
    reference_path.write_text(json.dumps(metadata, indent=2) + "\n")
    write_index()
    print(
        {
            key: metadata[key]
            for key in (
                "size",
                "weights",
                "build_seconds",
                "ttf_bytes",
                "woff2_bytes",
                "html_bytes",
                "runtime_raw_bytes",
                "runtime_brotli_bytes",
            )
        }
        | {"output": str(destination)}
    )


if __name__ == "__main__":
    main()
