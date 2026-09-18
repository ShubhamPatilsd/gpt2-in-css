#!/usr/bin/env python3
"""Build a real GPT-2-small 255 -> 256 -> 256 MLP tile inside one font.

The last of the font's 256 axes is held at one so avar2 can include the real
GPT-2 FC bias.  avar2 computes the FC preactivations; HVAR applies a piecewise
GELU and the following projection without exporting the hidden vector to CSS.
"""

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

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag, layer_norm, model_data
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "avar2-hvar-real-gpt2-tile"
AXES = 256
INPUTS = AXES - 1
HIDDEN = AXES
OUTPUTS = AXES
TOKEN_IDS = (15496, 7454, 464, 1212)  # Hello, real GPT-2 vocabulary entries
KNOTS = np.linspace(-1.0, 1.0, 17)
F2DOT14 = 1 << 14
INPUT_SCALE = 2.0
PREACTIVATION_SCALE = 3.0
OUTPUT_SCALE = 4096.0
BASE_ADVANCE = 16_000
CODEPOINT_START = 0xE000


def gelu(value: np.ndarray | float) -> np.ndarray | float:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def piecewise_gelu(values: np.ndarray) -> np.ndarray:
    normalized_knots = KNOTS * PREACTIVATION_SCALE
    return np.interp(values, normalized_knots, gelu(normalized_knots))


def block_zero_mlp_input(token_id: int, tensors: SafeTensors) -> np.ndarray:
    x = np.asarray(
        tensors.tensor("wte.weight")[token_id] + tensors.tensor("wpe.weight")[0],
        dtype=np.float64,
    )
    data = model_data(input_vector=x)
    normalized = layer_norm(x, data["ln1_gamma"], data["ln1_beta"])
    value = data["v_weight"] @ normalized + data["v_bias"]
    after_attention = (
        x
        + data["attn_proj_weight"] @ value
        + data["attn_proj_bias"]
    )
    return layer_norm(after_attention, data["ln2_gamma"], data["ln2_beta"])


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
            if not -32768 <= endpoint <= 32767:
                raise ValueError(f"avar2 coefficient does not fit F2DOT14: {value}")
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


def replace_hvar(font: TTFont, tags: list[str], projection: np.ndarray) -> int:
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

    rows = [[0] * len(supports)]
    for output in range(OUTPUTS):
        row = []
        for hidden, knot in indexed:
            delta = (
                float(projection[output, hidden])
                * float(gelu(knot * PREACTIVATION_SCALE))
                * OUTPUT_SCALE
            )
            rounded = int(round(delta))
            if not -32768 <= rounded <= 32767:
                raise ValueError(f"HVAR delta does not fit int16: {delta}")
            row.append(rounded)
        rows.append(row)
    regions = buildVarRegionList(supports, tags)
    data = buildVarData(range(len(supports)), rows, optimize=True)
    font["HVAR"].table.VarStore = buildVarStore(regions, [data])
    return len(supports)


def main() -> None:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    data = model_data()
    fc = data["fc_weight"][:HIDDEN, :INPUTS]
    bias = data["fc_bias"][:HIDDEN]
    projection = data["mlp_proj_weight"][:OUTPUTS, :HIDDEN]
    inputs = np.stack([block_zero_mlp_input(token_id, tensors)[:INPUTS] for token_id in TOKEN_IDS])

    # CSS carries normalized inputs. avar2 overwrites the same 256 axes with
    # normalized FC preactivations; the final input axis is a constant-one bias.
    avar_matrix = np.empty((HIDDEN, AXES), dtype=np.float64)
    avar_matrix[:, :INPUTS] = fc * (INPUT_SCALE / PREACTIVATION_SCALE)
    avar_matrix[:, INPUTS] = bias / PREACTIVATION_SCALE
    encoded_inputs = np.concatenate(
        (inputs / INPUT_SCALE, np.ones((len(inputs), 1))), axis=1
    )
    preactivations = inputs @ fc.T + bias
    if np.max(np.abs(encoded_inputs)) > 1:
        raise ValueError("an encoded test input exceeds the font axis range")
    if np.max(np.abs(preactivations / PREACTIVATION_SCALE)) > 1:
        raise ValueError("a test preactivation exceeds the represented GELU range")

    tags = [global_axis_tag(index) for index in range(AXES)]
    ttf = OUTPUT / "real-gpt2-tile.ttf"
    build_direct_font_backend(
        np.zeros((OUTPUTS, AXES), dtype=np.int16),
        ttf,
        signed_axes=True,
        base_advance=BASE_ADVANCE,
        codepoint_start=CODEPOINT_START,
        axis_tags=tags,
    )
    font = TTFont(ttf, recalcTimestamp=False)
    hvar_regions = replace_hvar(font, tags, projection)
    add_avar2(font, tags, avar_matrix)
    font.recalcTimestamp = False
    font.save(ttf)
    font = TTFont(ttf, recalcTimestamp=False)
    font.flavor = "woff2"
    woff2 = OUTPUT / "real-gpt2-tile.woff2"
    font.save(woff2)

    represented = piecewise_gelu(preactivations) @ projection.T
    exact = np.asarray(gelu(preactivations)) @ projection.T
    controls = "".join(
        f'<input type="radio" name="case" id="case-{case}"'
        f'{" checked" if case == 0 else ""}>'
        for case in range(len(TOKEN_IDS))
    )
    rules = "".join(
        f'body:has(#case-{case}:checked) .outputs{{font-variation-settings:'
        + ",".join(
            f'"{tag}" {value:.9g}'
            for tag, value in zip(tags, vector, strict=True)
        )
        + "}"
        for case, vector in enumerate(encoded_inputs)
    )
    glyphs = "".join(
        f'<i class="output" id="output-{index}">&#x{CODEPOINT_START + index:X};</i>'
        for index in range(OUTPUTS)
    )
    html = f'''<!doctype html><meta charset="utf-8"><title>Real GPT-2 avar2 MLP tile</title>
<style>@font-face{{font-family:RealGPT2Tile;src:url("real-gpt2-tile.woff2") format("woff2")}}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.outputs{{position:fixed;
left:0;top:0;font-family:RealGPT2Tile;font-size:1000px;line-height:1;font-kerning:none}}
.output{{display:inline-block;width:max-content;height:1px;overflow:hidden}}{rules}</style>
{controls}<div class="outputs">{glyphs}</div>'''
    (OUTPUT / "index.html").write_text(html)

    reference = {
        "tokenIds": TOKEN_IDS,
        "shape": [INPUTS, HIDDEN, OUTPUTS],
        "inputScale": INPUT_SCALE,
        "preactivationScale": PREACTIVATION_SCALE,
        "outputScale": OUTPUT_SCALE,
        "baseAdvance": BASE_ADVANCE,
        "encodedInputMaximum": float(np.max(np.abs(encoded_inputs))),
        "preactivationMinimum": float(np.min(preactivations)),
        "preactivationMaximum": float(np.max(preactivations)),
        "avarCoefficientMaximum": float(np.max(np.abs(avar_matrix))),
        "avarDeltaValues": int(2 * AXES * AXES),
        "hvarRegions": hvar_regions,
        "hvarDeltaValues": int((OUTPUTS + 1) * hvar_regions),
        "representedOutputs": represented.tolist(),
        "exactOutputs": exact.tolist(),
        "representedWidths": (BASE_ADVANCE + represented * OUTPUT_SCALE).tolist(),
        "approximationRmse": float(np.sqrt(np.mean((represented - exact) ** 2))),
        "approximationMaximum": float(np.max(np.abs(represented - exact))),
        "fontBytes": woff2.stat().st_size,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "buildMilliseconds": (time.perf_counter() - started) * 1000,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in ("representedOutputs", "exactOutputs", "representedWidths")
    }, indent=2))


if __name__ == "__main__":
    main()
