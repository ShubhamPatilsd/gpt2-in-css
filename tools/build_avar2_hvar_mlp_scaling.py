#!/usr/bin/env python3
"""Scale dense avar2 -> piecewise-GELU HVAR composition to 256 axes."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.varLib.builder import (
    buildDeltaSetIndexMap,
    buildVarData,
    buildVarRegionList,
    buildVarStore,
)

from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "avar2-hvar-mlp-scaling"
SIZES = (16, 32, 64, 128, 256)
KNOTS = np.linspace(-1, 1, 9)
F2DOT14 = 1 << 14
BASE_ADVANCE = 16_000
CODEPOINT_START = 0xE000


def gelu(value: np.ndarray | float) -> np.ndarray | float:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def supports_and_knots(tags: list[str]) -> tuple[list[dict[str, tuple[float, float, float]]], list[tuple[int, float]]]:
    supports: list[dict[str, tuple[float, float, float]]] = []
    indexed: list[tuple[int, float]] = []
    zero = len(KNOTS) // 2
    for axis, tag in enumerate(tags):
        for index, knot in enumerate(KNOTS):
            if index == zero:
                continue
            if index < zero:
                start = KNOTS[index - 1] if index else -1.0
                end = KNOTS[index + 1]
            else:
                start = KNOTS[index - 1]
                end = KNOTS[index + 1] if index + 1 < len(KNOTS) else 1.0
            supports.append({tag: (float(start), float(knot), float(end))})
            indexed.append((axis, float(knot)))
    return supports, indexed


def piecewise_gelu(values: np.ndarray) -> np.ndarray:
    return np.interp(values, KNOTS, gelu(KNOTS))


def add_avar2(font: TTFont, tags: list[str], matrix: np.ndarray) -> None:
    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    delta_map = matrix - np.eye(len(tags))
    rows = []
    for output in range(len(tags)):
        row = []
        for value in delta_map[output]:
            endpoint = int(round(float(value) * F2DOT14))
            row.extend((-endpoint, endpoint))
        rows.append(row)
    regions = buildVarRegionList(supports, tags)
    data = buildVarData(range(len(supports)), rows, optimize=True)
    avar = newTable("avar")
    avar.majorVersion = 2
    avar.minorVersion = 0
    avar.segments = {tag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for tag in tags}
    avar.table = otTables.avar()
    avar.table.Reserved = 0
    avar.table.VarIdxMap = buildDeltaSetIndexMap(range(len(tags)))
    avar.table.VarStore = buildVarStore(regions, [data])
    font["avar"] = avar


def replace_hvar(font: TTFont, tags: list[str], matrix: np.ndarray) -> int:
    supports, indexed = supports_and_knots(tags)
    rows = [[0] * len(supports)]
    for output in range(len(tags)):
        rows.append([
            int(round(float(matrix[output, axis]) * float(gelu(knot))))
            for axis, knot in indexed
        ])
    regions = buildVarRegionList(supports, tags)
    data = buildVarData(range(len(supports)), rows, optimize=True)
    font["HVAR"].table.VarStore = buildVarStore(regions, [data])
    return len(supports)


def build_size(size: int) -> dict[str, object]:
    started = time.perf_counter()
    directory = OUTPUT / f"n{size}"
    directory.mkdir(parents=True, exist_ok=True)
    tags = [global_axis_tag(index) for index in range(size)]
    rng = np.random.default_rng(0xA2A20000 + size)
    a = rng.normal(size=(size, size))
    a *= (0.72 / np.sum(np.abs(a), axis=1))[:, None]
    b = rng.integers(-48, 49, size=(size, size), dtype=np.int16)
    inputs = rng.uniform(-0.8, 0.8, size=(2, size))

    ttf = directory / "mlp.ttf"
    build_direct_font_backend(
        np.zeros_like(b),
        ttf,
        signed_axes=True,
        base_advance=BASE_ADVANCE,
        codepoint_start=CODEPOINT_START,
        axis_tags=tags,
    )
    font = TTFont(ttf, recalcTimestamp=False)
    regions = replace_hvar(font, tags, b)
    add_avar2(font, tags, a)
    font.recalcTimestamp = False
    font.save(ttf)
    font = TTFont(ttf, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(directory / "mlp.woff2")

    transformed = inputs @ a.T
    represented = piecewise_gelu(transformed) @ b.T
    exact = np.asarray(gelu(transformed)) @ b.T
    controls = "".join(
        f'<input type="radio" name="case" id="case-{case}"'
        f'{" checked" if case == 0 else ""}>' for case in range(2)
    )
    rules = "".join(
        f'body:has(#case-{case}:checked) .outputs{{font-variation-settings:'
        + ",".join(
            f'"{tag}" {value:.9g}' for tag, value in zip(tags, vector, strict=True)
        ) + "}" for case, vector in enumerate(inputs)
    )
    glyphs = "".join(
        f'<i class="output" id="output-{index}">&#x{CODEPOINT_START + index:X};</i>'
        for index in range(size)
    )
    html = f'''<!doctype html><meta charset="utf-8"><title>avar2 HVAR MLP n{size}</title>
<style>@font-face{{font-family:AvarMLP;src:url("mlp.woff2") format("woff2")}}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.outputs{{position:fixed;
left:0;top:0;font-family:AvarMLP;font-size:1000px;line-height:1;font-kerning:none}}
.output{{display:inline-block;width:max-content;height:1px;overflow:hidden}}{rules}</style>
{controls}<div class="outputs">{glyphs}</div>'''
    (directory / "index.html").write_text(html)
    result = {
        "size": size,
        "avarRegions": 2 * size,
        "hvarRegions": regions,
        "avarDeltaValues": 2 * size * size,
        "hvarDeltaValues": (size + 1) * regions,
        "inputs": inputs.tolist(),
        "representedOutputs": represented.tolist(),
        "exactOutputs": exact.tolist(),
        "representedWidths": (represented + BASE_ADVANCE).tolist(),
        "approximationRmse": float(np.sqrt(np.mean((represented - exact) ** 2))),
        "approximationMaximum": float(np.max(np.abs(represented - exact))),
        "baseAdvance": BASE_ADVANCE,
        "fontBytes": (directory / "mlp.woff2").stat().st_size,
        "htmlBytes": (directory / "index.html").stat().st_size,
        "buildMilliseconds": (time.perf_counter() - started) * 1000,
    }
    (directory / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = [build_size(size) for size in SIZES]
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps([{k: v for k, v in item.items() if k not in (
        "inputs", "representedOutputs", "exactOutputs", "representedWidths"
    )} for item in manifest], indent=2))


if __name__ == "__main__":
    main()
