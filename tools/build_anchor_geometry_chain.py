#!/usr/bin/env python3
"""Build no-JS dense affine chains that keep every vector as anchor geometry."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "anchor-geometry-chain"
BASE = 2_000.0
SCALE = 64.0
CHUNK = 96


def css_number(value: float) -> str:
    if abs(value) < 5e-13:
        return "0"
    return f"{value:.9g}"


def affine(width: int, seed: int) -> tuple[list[list[float]], list[float]]:
    rng = random.Random(seed)
    weight_scale = 0.72 / math.sqrt(width)
    weights = [
        [rng.uniform(-weight_scale, weight_scale) for _ in range(width)]
        for _ in range(width)
    ]
    bias = [rng.uniform(-0.08, 0.08) for _ in range(width)]
    return weights, bias


def matvec(weights: list[list[float]], values: list[float], bias: list[float]) -> list[float]:
    return [
        sum(weight * value for weight, value in zip(row, values, strict=True)) + offset
        for row, offset in zip(weights, bias, strict=True)
    ]


def balanced_sum(terms: list[str]) -> str:
    """Keep Blink's CSS math tree shallow instead of emitting a left-deep sum."""
    if not terms:
        return "0px"
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced_sum(terms[:middle])} + {balanced_sum(terms[middle:])})"


def source_markup(values: list[float]) -> str:
    return "".join(
        f'<i class="source" style="width:{css_number(BASE + SCALE * value)}px;'
        f'anchor-name:--x-{index}"></i>'
        for index, value in enumerate(values)
    )


def layer_rules(
    name: str,
    source: str,
    weights: list[list[float]],
    bias: list[float],
    *,
    mode: str,
) -> tuple[str, str]:
    rules: list[str] = []
    partials: list[str] = []
    for output, (row, offset) in enumerate(zip(weights, bias, strict=True)):
        if mode == "balanced":
            constant = BASE * (1 - sum(row)) + SCALE * offset
            weighted = [
                f"({css_number(weight)} * anchor-size(--{source}-{index} width))"
                for index, weight in enumerate(row)
                if weight
            ]
            expression = balanced_sum(weighted)
            rules.append(
                f".{name}-{output}{{width:calc({css_number(constant)}px + {expression});"
                f"anchor-name:--{name}-{output}}}"
            )
            continue
        if mode == "vars" and len(row) > CHUNK:
            groups = [row[start : start + CHUNK] for start in range(0, len(row), CHUNK)]
            declarations: list[str] = []
            for group_index, group in enumerate(groups):
                start = group_index * CHUNK
                terms: list[str] = []
                for local, weight in enumerate(group):
                    if not weight:
                        continue
                    operator = "+" if weight > 0 and terms else "-" if weight < 0 else ""
                    terms.append(
                        f"{operator} {css_number(abs(weight))} * "
                        f"anchor-size(--{source}-{start + local} width)"
                    )
                declarations.append(f"--part-{group_index}:calc({' '.join(terms)})")
            constant = BASE * (1 - sum(row)) + SCALE * offset
            final_terms = [f"{css_number(constant)}px"]
            final_terms.extend(f"+ var(--part-{index})" for index in range(len(groups)))
            declarations.extend(
                (
                    f"width:calc({' '.join(final_terms)})",
                    f"anchor-name:--{name}-{output}",
                )
            )
            rules.append(f".{name}-{output}{{{';'.join(declarations)}}}")
            continue
        if mode == "tree" and len(row) > CHUNK:
            groups = [row[start : start + CHUNK] for start in range(0, len(row), CHUNK)]
            for group_index, group in enumerate(groups):
                start = group_index * CHUNK
                constant = BASE * (1 - sum(group))
                terms = [f"{css_number(constant)}px"]
                for local, weight in enumerate(group):
                    if not weight:
                        continue
                    operator = "+" if weight > 0 else "-"
                    terms.append(
                        f"{operator} {css_number(abs(weight))} * "
                        f"anchor-size(--{source}-{start + local} width)"
                    )
                partial_name = f"{name}-p-{output}-{group_index}"
                rules.append(
                    f".{partial_name}{{width:calc({' '.join(terms)});"
                    f"anchor-name:--{partial_name}}}"
                )
                partials.append(f'<i class="node {partial_name}"></i>')
            final_terms = [f"{css_number(BASE * (1 - len(groups)) + SCALE * offset)}px"]
            final_terms.extend(
                f"+ anchor-size(--{name}-p-{output}-{group_index} width)"
                for group_index in range(len(groups))
            )
            rules.append(
                f".{name}-{output}{{width:calc({' '.join(final_terms)});"
                f"anchor-name:--{name}-{output}}}"
            )
            continue
        # If input geometry is BASE + SCALE*x, this evaluates to
        # BASE + SCALE*(W*x+b) without exposing x as a CSS number.
        constant = BASE * (1 - sum(row)) + SCALE * offset
        terms = [f"{css_number(constant)}px"]
        for index, weight in enumerate(row):
            if not weight:
                continue
            operator = "+" if weight > 0 else "-"
            terms.append(
                f"{operator} {css_number(abs(weight))} * "
                f"anchor-size(--{source}-{index} width)"
            )
        rules.append(
            f".{name}-{output}{{width:calc({' '.join(terms)});"
            f"anchor-name:--{name}-{output}}}"
        )
    return "".join(rules), "".join(partials)


def layer_markup(name: str, width: int, *, result: bool = False) -> str:
    classes = "node result" if result else "node"
    return "".join(
        f'<i id="{name}-{index}" class="{classes} {name}-{index}"></i>'
        for index in range(width)
    )


def build(width: int, layers: int, mode: str) -> dict[str, object]:
    rng = random.Random(0xA11CE + width)
    inputs = [rng.uniform(-1, 1) for _ in range(width)]
    alternate_inputs = [rng.uniform(-1, 1) for _ in range(width)]
    expected = inputs
    alternate_expected = alternate_inputs
    rules: list[str] = []
    markup: list[str] = [source_markup(inputs)]
    source = "x"
    for layer in range(layers):
        name = f"l{layer + 1}"
        weights, bias = affine(width, seed=0xC55000 + width * 17 + layer)
        expected = matvec(weights, expected, bias)
        alternate_expected = matvec(weights, alternate_expected, bias)
        layer_css, partial_markup = layer_rules(
            name, source, weights, bias, mode=mode
        )
        rules.append(layer_css)
        markup.append(partial_markup)
        markup.append(layer_markup(name, width, result=layer == layers - 1))
        source = name

    html = f'''<!doctype html>
<meta charset="utf-8">
<title>Anchor geometry chain {width}x{width} x {layers} ({mode})</title>
<style>
html,body{{margin:0}}
.stage{{position:fixed;inset:0;contain:layout style}}
.source,.node{{position:fixed;left:0;top:0;height:1px;display:block;visibility:hidden}}
{''.join(rules)}
</style>
<div class="stage">{''.join(markup)}</div>
'''
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"n{width}-l{layers}-{mode}"
    page = OUT / f"{stem}.html"
    reference = OUT / f"{stem}.json"
    page.write_text(html)
    metadata: dict[str, object] = {
        "width": width,
        "layers": layers,
        "mode": mode,
        "page": page.name,
        "base": BASE,
        "scale": SCALE,
        "expected": expected,
        "alternate_expected": alternate_expected,
        "input_widths": [BASE + SCALE * value for value in inputs],
        "alternate_input_widths": [BASE + SCALE * value for value in alternate_inputs],
        "html_bytes": len(html.encode()),
        "matrix_terms": layers * width * width,
        "anchors": html.count("anchor-name:"),
        "no_javascript": "<script" not in html.lower(),
    }
    reference.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="384,512,768")
    parser.add_argument("--layers", default="1")
    parser.add_argument("--modes", default="balanced")
    args = parser.parse_args()
    sizes = [int(value) for value in args.sizes.split(",") if value]
    layers = [int(value) for value in args.layers.split(",") if value]
    modes = [value for value in args.modes.split(",") if value]
    summaries = [
        build(width, count, mode)
        for width in sizes
        for count in layers
        for mode in modes
    ]
    (OUT / "manifest.json").write_text(json.dumps(summaries, indent=2) + "\n")
    for item in summaries:
        print(
            f"n={item['width']} layers={item['layers']} mode={item['mode']} "
            f"terms={item['matrix_terms']} bytes={item['html_bytes']}"
        )


if __name__ == "__main__":
    main()
