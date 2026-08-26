#!/usr/bin/env python3
"""Build no-JS dense matmul probes using anchor widths as numeric state."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "anchor-geometry-matmul"
SIZES = (16, 32, 64, 128, 256, 768)
BASE = 100_000.0
SCALE = 10_000.0


def number(value: float) -> str:
    return f"{value:.9g}"


def length(value: float) -> str:
    return f"{value:.9g}px"


def dense_width_expression(
    prefix: str,
    weights: np.ndarray,
    bias: float,
) -> str:
    pieces = [length(BASE + SCALE * bias)]
    for index, weight in enumerate(weights):
        operator = "+" if weight >= 0 else "-"
        pieces.append(
            f" {operator} {number(abs(float(weight)))} * "
            f"(anchor-size(--{prefix}{index} width) - {length(BASE)})"
        )
    return "calc(" + "".join(pieces) + ")"


def build_page(size: int) -> dict[str, object]:
    rng = np.random.default_rng(20260912 + size)
    x = rng.uniform(-1.0, 1.0, size)
    # Keep each stage well inside the positive width encoding range.
    w1 = rng.normal(0, 0.28 / np.sqrt(size), (size, size))
    b1 = rng.normal(0, 0.025, size)
    w2 = rng.normal(0, 0.28 / np.sqrt(size), (size, size))
    b2 = rng.normal(0, 0.025, size)
    y = w1 @ x + b1
    z = w2 @ y + b2

    common = (
        "html,body{margin:0;width:1px;height:1px;overflow:hidden}"
        ".v{position:absolute;left:0;top:0;height:1px;min-width:0;max-width:none}"
    )
    rules = [common]
    nodes: list[str] = []
    for index, value in enumerate(x):
        rules.append(
            f".x{index}{{width:{length(BASE + SCALE * float(value))};"
            f"anchor-name:--x{index}}}"
        )
        nodes.append(f'<i class="v x{index}" data-stage="x" data-index="{index}"></i>')
    for index in range(size):
        rules.append(
            f".y{index}{{width:{dense_width_expression('x', w1[index], float(b1[index]))};"
            f"anchor-name:--y{index}}}"
        )
        nodes.append(f'<i class="v y{index}" data-stage="y" data-index="{index}"></i>')
    for index in range(size):
        rules.append(
            f".z{index}{{width:{dense_width_expression('y', w2[index], float(b2[index]))};"
            f"anchor-name:--z{index}}}"
        )
        nodes.append(f'<i class="v z{index}" data-stage="z" data-index="{index}"></i>')

    html = (
        "<!doctype html><meta charset=utf-8>"
        f"<title>Anchor geometry matmul {size}</title><style>"
        + "".join(rules)
        + "</style><main>"
        + "".join(nodes)
        + "</main>"
    )
    path = OUT / f"{size}.html"
    path.write_text(html)
    reference = {
        "size": size,
        "base": BASE,
        "scale": SCALE,
        "x": x.tolist(),
        "y": y.tolist(),
        "z": z.tolist(),
        "htmlBytes": len(html.encode()),
        "terms": 2 * size * size,
    }
    (OUT / f"{size}.json").write_text(json.dumps(reference) + "\n")
    return {
        "size": size,
        "htmlBytes": reference["htmlBytes"],
        "terms": reference["terms"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = [build_page(size) for size in SIZES]
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
