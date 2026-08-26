#!/usr/bin/env python3
"""Build a CSS-native grouped-MLP browser scaling probe.

Each group is one variable font whose axes select a subset of one global input
vector.  avar2 performs a dense axes-by-axes remap, and HVAR evaluates a
nine-knot GELU representation while projecting every remapped coordinate to
every output glyph.  One fallback run containing one glyph from every face
sums the group contributions for an output.

The generated runtime is deliberately HTML/CSS/fonts only.  Playwright is an
external observer and mutates hidden radio controls to select fresh vectors.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
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
OUTPUT = ROOT / "experiments" / "css-native-grouped-mlp-browser"
DEFAULT_GROUPS = 12
DEFAULT_AXES = 256
DEFAULT_OUTPUTS = 768
DEFAULT_INPUTS = 768
VECTOR_COUNT = 4
KNOTS = np.linspace(-1.0, 1.0, 9)
F2DOT14 = 1 << 14
BASE_ADVANCE = 8_000
CODEPOINT_START = 0xF0000
PROJECTION_LIMIT = 24


def positive_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def gelu(value: np.ndarray | float) -> np.ndarray | float:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def piecewise(values: np.ndarray, ordinates: np.ndarray) -> np.ndarray:
    """Evaluate one knot ordinate vector independently on every coordinate."""
    flat = np.interp(values.ravel(), KNOTS, ordinates)
    return flat.reshape(values.shape)


def hvar_supports(
    tags: list[str],
) -> tuple[list[dict[str, tuple[float, float, float]]], list[tuple[int, float]]]:
    supports: list[dict[str, tuple[float, float, float]]] = []
    indexed: list[tuple[int, float]] = []
    zero = len(KNOTS) // 2
    for axis, tag in enumerate(tags):
        for index, knot in enumerate(KNOTS):
            if index == zero:
                continue
            start = KNOTS[index - 1] if index else -1.0
            end = KNOTS[index + 1] if index + 1 < len(KNOTS) else 1.0
            supports.append({tag: (float(start), float(knot), float(end))})
            indexed.append((axis, float(knot)))
    return supports, indexed


def add_dense_avar2(font: TTFont, tags: list[str], matrix: np.ndarray) -> np.ndarray:
    """Install a dense linear remap and return its F2DOT14-quantized matrix."""
    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    delta_endpoints = np.rint((matrix - np.eye(len(tags))) * F2DOT14).astype(np.int32)
    rows = [
        [signed for endpoint in row for signed in (-int(endpoint), int(endpoint))]
        for row in delta_endpoints
    ]
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
    return np.eye(len(tags)) + delta_endpoints.astype(np.float64) / F2DOT14


def replace_gelu_projection_hvar(
    font: TTFont, tags: list[str], projection: np.ndarray
) -> np.ndarray:
    """Fuse the nine-knot GELU basis and the output projection into HVAR."""
    supports, indexed = hvar_supports(tags)
    knot_deltas = np.zeros((projection.shape[0], projection.shape[1], len(KNOTS)))
    rows = [[0] * len(supports)]
    zero = len(KNOTS) // 2
    for output, projection_row in enumerate(projection):
        row = []
        for axis, knot in indexed:
            delta = int(round(float(projection_row[axis]) * float(gelu(knot))))
            if not -32768 <= delta <= 32767:
                raise ValueError(f"HVAR delta does not fit int16: {delta}")
            row.append(delta)
            knot_index = int(round((knot + 1.0) * (len(KNOTS) - 1) / 2.0))
            knot_deltas[output, axis, knot_index] = delta
        rows.append(row)
    knot_deltas[:, :, zero] = 0
    regions = buildVarRegionList(supports, tags)
    data = buildVarData(range(len(supports)), rows, optimize=True)
    font["HVAR"].table.VarStore = buildVarStore(regions, [data])
    return knot_deltas


def dense_matrix(rng: np.random.Generator, axes: int) -> np.ndarray:
    matrix = rng.normal(size=(axes, axes))
    # The induced infinity norm is 0.72, so all generated remaps stay well
    # within the normalized axis domain for inputs bounded by 0.8.
    matrix *= (0.72 / np.sum(np.abs(matrix), axis=1))[:, None]
    return matrix


def axis_subset(group: int, axes: int, inputs: int) -> list[int]:
    """Select deterministic global tags; 256/768 gives thirds repeated 4x."""
    blocks = math.ceil(inputs / axes)
    start = (group % blocks) * axes
    return [(start + local) % inputs for local in range(axes)]


def represented_group_outputs(
    vectors: np.ndarray,
    dense_quantized: np.ndarray,
    knot_deltas: np.ndarray,
) -> np.ndarray:
    remapped = vectors @ dense_quantized.T
    if np.max(np.abs(remapped)) > 1.0:
        raise ValueError("dense avar2 remap escaped the normalized axis domain")
    outputs = np.empty((len(vectors), knot_deltas.shape[0]), dtype=np.float64)
    for output in range(knot_deltas.shape[0]):
        represented = np.column_stack(
            [piecewise(remapped[:, axis], knot_deltas[output, axis])
             for axis in range(remapped.shape[1])]
        )
        outputs[:, output] = np.sum(represented, axis=1)
    return outputs


def build() -> dict[str, object]:
    groups = positive_env("CSS_MLP_GROUPS", DEFAULT_GROUPS)
    axes = positive_env("CSS_MLP_AXES", DEFAULT_AXES)
    outputs = positive_env("CSS_MLP_OUTPUTS", DEFAULT_OUTPUTS)
    inputs = positive_env("CSS_MLP_INPUTS", DEFAULT_INPUTS)
    if axes > 256:
        raise ValueError("CSS_MLP_AXES must be at most 256 per face")
    if axes > inputs:
        raise ValueError("CSS_MLP_AXES cannot exceed CSS_MLP_INPUTS")
    if CODEPOINT_START + groups * outputs > 0xFFFFD:
        raise ValueError("group/output combination exceeds the supplementary PUA")

    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0xC55A_12F0 + groups * 1009 + axes * 17 + outputs)
    vectors = rng.uniform(-0.8, 0.8, size=(VECTOR_COUNT, inputs))
    represented = np.zeros((VECTOR_COUNT, outputs), dtype=np.float64)
    font_faces: list[str] = []
    families: list[str] = []
    font_files: list[dict[str, object]] = []
    matrix_hashes: list[dict[str, str]] = []
    face_axis_subsets: list[list[int]] = []

    for group in range(groups):
        group_started = time.perf_counter()
        subset = axis_subset(group, axes, inputs)
        face_axis_subsets.append(subset)
        tags = [global_axis_tag(input_axis) for input_axis in subset]
        dense = dense_matrix(rng, axes)
        projection = rng.integers(
            -PROJECTION_LIMIT,
            PROJECTION_LIMIT + 1,
            size=(outputs, axes),
            dtype=np.int16,
        )
        codepoint = CODEPOINT_START + group * outputs
        ttf = OUTPUT / f"group-{group:02d}.ttf"
        woff2 = ttf.with_suffix(".woff2")
        build_direct_font_backend(
            np.zeros((outputs, axes), dtype=np.int16),
            ttf,
            signed_axes=True,
            base_advance=BASE_ADVANCE,
            codepoint_start=codepoint,
            axis_tags=tags,
        )
        font = TTFont(ttf, recalcTimestamp=False)
        dense_quantized = add_dense_avar2(font, tags, dense)
        knot_deltas = replace_gelu_projection_hvar(font, tags, projection)
        font.recalcTimestamp = False
        font.save(ttf)
        compressed = TTFont(ttf, recalcTimestamp=False)
        compressed.flavor = "woff2"
        compressed.save(woff2)

        group_vectors = vectors[:, subset]
        represented += represented_group_outputs(
            group_vectors, dense_quantized, knot_deltas
        )
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()
        family = f"GroupedMLP{group:02d}"
        families.append(family)
        font_faces.append(
            f'@font-face{{font-family:{family};src:url("{woff2.name}") format("woff2");'
            f'unicode-range:U+{codepoint:X}-U+{codepoint + outputs - 1:X}}}'
        )
        font_files.append(
            {
                "group": group,
                "file": woff2.name,
                "bytes": woff2.stat().st_size,
                "sha256": digest,
                "buildMilliseconds": (time.perf_counter() - group_started) * 1000,
            }
        )
        matrix_hashes.append(
            {
                "dense": hashlib.sha256(dense.tobytes()).hexdigest(),
                "projection": hashlib.sha256(projection.tobytes()).hexdigest(),
            }
        )
        print(
            f"built group {group + 1}/{groups}: {woff2.stat().st_size:,} bytes",
            flush=True,
        )

    controls = "".join(
        f'<input type="radio" name="vector" id="vector-{case}"'
        f'{" checked" if case == 0 else ""}>'
        for case in range(VECTOR_COUNT)
    )
    rules = []
    for case, vector in enumerate(vectors):
        settings = ",".join(
            f'"{global_axis_tag(axis)}" {value:.9g}'
            for axis, value in enumerate(vector)
        )
        rules.append(
            f'body:has(#vector-{case}:checked) .outputs{{font-variation-settings:{settings}}}'
        )
    output_elements = []
    for output in range(outputs):
        characters = "".join(
            f"&#x{CODEPOINT_START + group * outputs + output:X};"
            for group in range(groups)
        )
        output_elements.append(
            f'<i class="output" id="output-{output}">{characters}</i>'
        )
    html = f'''<!doctype html><meta charset="utf-8">
<title>CSS-native grouped MLP browser probe</title>
<style>{''.join(font_faces)}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}
.outputs{{font-family:{','.join(families)};font-size:1000px;font-kerning:none;line-height:1}}
.output{{position:fixed;inset:0 auto auto 0;display:inline-block;width:max-content;
height:1px;overflow:hidden;white-space:pre;font-style:normal}}
{''.join(rules)}</style>
{controls}<div class="outputs">{''.join(output_elements)}</div>
'''
    if "<script" in html.lower():
        raise AssertionError("runtime HTML must contain no JavaScript")
    (OUTPUT / "index.html").write_text(html)

    represented_widths = represented + groups * BASE_ADVANCE
    reference: dict[str, object] = {
        "architecture": {
            "groups": groups,
            "globalInputDimensions": inputs,
            "axesPerGroup": axes,
            "outputs": outputs,
            "vectors": VECTOR_COUNT,
            "glyphsPerOutput": groups,
            "geometryOutputs": outputs,
            "preactivationTransportBoxes": 0,
            "denseAvar2ShapePerFace": [axes, axes],
            "geluKnots": KNOTS.tolist(),
            "hvarProjectionShapePerFace": [outputs, axes],
            "inheritedAxisSettings": inputs,
            "globalAxisTags": inputs,
            "axisTagsReusedAcrossFaces": True,
            "faceAxisTagSubsets": face_axis_subsets,
        },
        "baseAdvancePerFace": BASE_ADVANCE,
        "codepointStart": CODEPOINT_START,
        "inputs": vectors.tolist(),
        "representedWidths": represented_widths.tolist(),
        # Every face can round its resulting advance by up to half a font unit;
        # the summed CSS width then has one final 1/64 px layout quantization.
        "numericToleranceFontUnits": groups * 0.5 + 1.0 / 64.0,
        "fontFiles": font_files,
        "fontBytes": sum(int(item["bytes"]) for item in font_files),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "matrixHashes": matrix_hashes,
        "runtimeContainsJavaScript": False,
        "buildMilliseconds": (time.perf_counter() - started) * 1000,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    return reference


def main() -> None:
    reference = build()
    print(
        json.dumps(
            {
                "architecture": reference["architecture"],
                "fontBytes": reference["fontBytes"],
                "htmlBytes": reference["htmlBytes"],
                "buildMilliseconds": reference["buildMilliseconds"],
                "output": str(OUTPUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
