#!/usr/bin/env python3
"""Build hierarchical anchor-width matmuls below Chromium's calc term limit."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from build_anchor_geometry_matmul import BASE, OUT, SCALE, length, number


SIZES = (128, 256, 768)
CHUNK = 96


def partial_expression(
    source_prefix: str,
    weights: np.ndarray,
    start: int,
) -> str:
    pieces = [length(BASE)]
    for offset, weight in enumerate(weights):
        index = start + offset
        operator = "+" if weight >= 0 else "-"
        pieces.append(
            f" {operator} {number(abs(float(weight)))} * "
            f"(anchor-size(--{source_prefix}{index} width) - {length(BASE)})"
        )
    return "calc(" + "".join(pieces) + ")"


def final_expression(partial_prefix: str, chunks: int, bias: float) -> str:
    pieces = [length(BASE + SCALE * bias)]
    for chunk in range(chunks):
        pieces.append(
            f" + anchor-size(--{partial_prefix}{chunk} width) - {length(BASE)}"
        )
    return "calc(" + "".join(pieces) + ")"


def add_stage(
    rules: list[str],
    nodes: list[str],
    source_prefix: str,
    output_prefix: str,
    weights: np.ndarray,
    biases: np.ndarray,
) -> tuple[int, int]:
    size = len(weights)
    chunks = math.ceil(size / CHUNK)
    partial_count = 0
    for output in range(size):
        for chunk in range(chunks):
            start = chunk * CHUNK
            stop = min(start + CHUNK, size)
            partial_name = f"{output_prefix}p{output}c{chunk}"
            rules.append(
                f".{partial_name}{{width:"
                f"{partial_expression(source_prefix, weights[output, start:stop], start)};"
                f"anchor-name:--{partial_name}}}"
            )
            nodes.append(f'<i class="v {partial_name}"></i>')
            partial_count += 1
    for output in range(size):
        name = f"{output_prefix}{output}"
        partial_prefix = f"{output_prefix}p{output}c"
        rules.append(
            f".{name}{{width:{final_expression(partial_prefix, chunks, float(biases[output]))};"
            f"anchor-name:--{name}}}"
        )
        nodes.append(
            f'<i class="v {name}" data-stage="{output_prefix}" data-index="{output}"></i>'
        )
    return partial_count, chunks


def build_page(size: int) -> dict[str, object]:
    rng = np.random.default_rng(20260912 + size)
    x = rng.uniform(-1.0, 1.0, size)
    w1 = rng.normal(0, 0.28 / np.sqrt(size), (size, size))
    b1 = rng.normal(0, 0.025, size)
    w2 = rng.normal(0, 0.28 / np.sqrt(size), (size, size))
    b2 = rng.normal(0, 0.025, size)
    y = w1 @ x + b1
    z = w2 @ y + b2

    rules = [
        "html,body{margin:0;width:1px;height:1px;overflow:hidden}"
        ".v{position:absolute;left:0;top:0;height:1px;min-width:0;max-width:none}"
    ]
    nodes: list[str] = []
    for index, value in enumerate(x):
        rules.append(
            f".x{index}{{width:{length(BASE + SCALE * float(value))};"
            f"anchor-name:--x{index}}}"
        )
        nodes.append(f'<i class="v x{index}" data-stage="x" data-index="{index}"></i>')
    y_partials, chunks = add_stage(rules, nodes, "x", "y", w1, b1)
    z_partials, _ = add_stage(rules, nodes, "y", "z", w2, b2)

    html = (
        "<!doctype html><meta charset=utf-8>"
        f"<title>Chunked anchor geometry matmul {size}</title><style>"
        + "".join(rules)
        + "</style><main>"
        + "".join(nodes)
        + "</main>"
    )
    basename = f"{size}-chunked"
    (OUT / f"{basename}.html").write_text(html)
    reference = {
        "size": size,
        "base": BASE,
        "scale": SCALE,
        "x": x.tolist(),
        "y": y.tolist(),
        "z": z.tolist(),
        "htmlBytes": len(html.encode()),
        "terms": 2 * size * size,
        "chunk": CHUNK,
        "chunksPerOutput": chunks,
        "partialBoxes": y_partials + z_partials,
        "totalBoxes": size * 3 + y_partials + z_partials,
    }
    (OUT / f"{basename}.json").write_text(json.dumps(reference) + "\n")
    return {
        key: reference[key]
        for key in (
            "size",
            "htmlBytes",
            "terms",
            "chunk",
            "chunksPerOutput",
            "partialBoxes",
            "totalBoxes",
        )
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = [build_page(size) for size in SIZES]
    (OUT / "chunked-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
