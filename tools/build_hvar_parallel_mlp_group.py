#!/usr/bin/env python3
"""Build one exact-sharded GPT-2 MLP group with a 256-value boundary.

Three ordinary HVAR fonts compute a real 768 -> 256 FC slice. A 128-deep
width/height container chain captures those 256 preactivations. One nonlinear
HVAR font then applies piecewise GELU and the real 256 -> 768 projection slice.
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

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_avar2_hvar_real_gpt2_tile import TOKEN_IDS, block_zero_mlp_input
from build_gpt2_block_css import (
    FONT_SIZE,
    OUT as FC_FONT_DIR,
    QUANT_BITS,
    UNITS_PER_EM,
    build_font_group,
    font_faces,
    global_axis_tag,
    model_data,
)
from build_matrix_backend_prototypes import build_direct_font_backend
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
BACKEND = os.environ.get("HVAR_MLP_GROUP_BACKEND", "hvar-knots")
OUTPUT = ROOT / "experiments" / (
    "avar2-gelu-linear-hvar-group"
    if BACKEND == "avar2-gelu"
    else "hvar-parallel-mlp-group"
)
HIDDEN = 256
OUTPUTS = 768
PREACTIVATION_SCALE = 12.5
# GELU is essentially flat below -4 and linear above +4. Concentrating knots
# in its curved interval preserves accuracy without uniformly sampling the
# much wider real GPT-2 preactivation range.
KNOTS = np.unique(np.r_[
    -1.0,
    -6.0 / PREACTIVATION_SCALE,
    -4.0 / PREACTIVATION_SCALE,
    np.linspace(-4.0 / PREACTIVATION_SCALE, 4.0 / PREACTIVATION_SCALE, 25),
    6.0 / PREACTIVATION_SCALE,
    1.0,
])
OUTPUT_SCALE = 192.0
GEOMETRY_SCALE = 1024.0
GEOMETRY_OFFSET = 12_800.0
BASE_ADVANCE = 16_000
CODEPOINT_START = 0xE000
F2DOT14 = 1 << 14


def gelu(value: np.ndarray | float) -> np.ndarray | float:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def piecewise_gelu(values: np.ndarray) -> np.ndarray:
    scaled_knots = KNOTS * PREACTIVATION_SCALE
    return np.interp(values, scaled_knots, gelu(scaled_knots))


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


def gelu_knots(preactivation_scale: float) -> np.ndarray:
    """Normalized axis knots that keep dense samples in GELU's curved range."""
    return np.unique(np.r_[
        -1.0,
        -6.0 / preactivation_scale,
        -4.0 / preactivation_scale,
        np.linspace(-4.0 / preactivation_scale, 4.0 / preactivation_scale, 25),
        6.0 / preactivation_scale,
        1.0,
    ])


def add_sparse_gelu_avar2(
    font: TTFont,
    tags: list[str],
    preactivation_scale: float = PREACTIVATION_SCALE,
) -> int:
    """Map every axis from z/scale to GELU(z)/scale without a dense VarData."""
    supports: list[dict[str, tuple[float, float, float]]] = []
    per_axis_regions: list[list[int]] = []
    per_axis_deltas: list[list[int]] = []
    knots = gelu_knots(preactivation_scale)
    zero = int(np.where(np.isclose(knots, 0))[0][0])
    for tag in tags:
        indices = []
        deltas = []
        for index, knot in enumerate(knots):
            if index == zero:
                continue
            start = knots[index - 1] if index else -1.0
            end = knots[index + 1] if index + 1 < len(knots) else 1.0
            indices.append(len(supports))
            supports.append({tag: (float(start), float(knot), float(end))})
            mapped = float(gelu(knot * preactivation_scale) / preactivation_scale)
            deltas.append(int(round((mapped - float(knot)) * F2DOT14)))
        per_axis_regions.append(indices)
        per_axis_deltas.append(deltas)
    regions = buildVarRegionList(supports, tags)
    data = [
        buildVarData(indices, [deltas], optimize=True)
        for indices, deltas in zip(per_axis_regions, per_axis_deltas, strict=True)
    ]
    avar = newTable("avar")
    avar.majorVersion = 2
    avar.minorVersion = 0
    avar.segments = {tag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for tag in tags}
    avar.table = otTables.avar()
    avar.table.Reserved = 0
    avar.table.VarIdxMap = buildDeltaSetIndexMap([
        outer << 16 for outer in range(len(tags))
    ])
    avar.table.VarStore = buildVarStore(regions, data)
    font["avar"] = avar
    return len(supports)


def replace_linear_hvar(
    font: TTFont,
    tags: list[str],
    projection: np.ndarray,
    preactivation_scale: float = PREACTIVATION_SCALE,
    output_scale: float = OUTPUT_SCALE,
) -> int:
    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    rows = [[0] * len(supports)]
    factor = preactivation_scale * output_scale
    for output in range(OUTPUTS):
        row = []
        for value in projection[output]:
            endpoint = int(round(float(value) * factor))
            if not -32768 <= endpoint <= 32767:
                raise ValueError(f"linear HVAR delta does not fit int16: {endpoint}")
            row.extend((-endpoint, endpoint))
        rows.append(row)
    regions = buildVarRegionList(supports, tags)
    data = buildVarData(range(len(supports)), rows, optimize=True)
    font["HVAR"].table.VarStore = buildVarStore(regions, [data])
    return len(supports)


def nested_transport(metrics: list[str]) -> str:
    child = '<div class="projection">' + "".join(
        f'<i class="output" id="output-{index}">&#x{CODEPOINT_START + index:X};</i>'
        for index in range(OUTPUTS)
    ) + "</div>"
    for pair in reversed(range(HIDDEN // 2)):
        first = 2 * pair
        child = (
            metrics[first]
            + metrics[first + 1]
            + f'<div class="probe probe-{pair}">{child}</div>'
        )
    return child


def main() -> None:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    data = model_data()
    inputs = np.stack([block_zero_mlp_input(token_id, tensors) for token_id in TOKEN_IDS])
    activation_range = float(np.max(np.abs(inputs)) * 1.01)
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fc_fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fc_fonts.bases)
    projection = data["mlp_proj_weight"][:, :HIDDEN]
    preactivations = inputs @ q_fc.reconstructed[:HIDDEN].T + data["fc_bias"][:HIDDEN]
    if np.max(np.abs(preactivations / PREACTIVATION_SCALE)) > 1:
        raise ValueError("preactivation exceeds the nonlinear font's axis range")

    tags = [global_axis_tag(index) for index in range(HIDDEN)]
    ttf = OUTPUT / "gelu-projection.ttf"
    build_direct_font_backend(
        np.zeros((OUTPUTS, HIDDEN), dtype=np.int16),
        ttf,
        signed_axes=True,
        base_advance=BASE_ADVANCE,
        codepoint_start=CODEPOINT_START,
        axis_tags=tags,
    )
    font = TTFont(ttf, recalcTimestamp=False)
    if BACKEND == "avar2-gelu":
        avar_regions = add_sparse_gelu_avar2(font, tags)
        hvar_regions = replace_linear_hvar(font, tags, projection)
    else:
        avar_regions = 0
        hvar_regions = replace_hvar(font, tags, projection)
    font.recalcTimestamp = False
    font.save(ttf)
    font = TTFont(ttf, recalcTimestamp=False)
    font.flavor = "woff2"
    projection_font = OUTPUT / "gelu-projection.woff2"
    font.save(projection_font)

    represented = piecewise_gelu(preactivations) @ projection.T
    exact = np.asarray(gelu(preactivations)) @ projection.T
    controls = "".join(
        f'<input type="radio" name="case" id="case-{case}"'
        f'{" checked" if case == 0 else ""}>'
        for case in range(len(TOKEN_IDS))
    )
    input_rules = []
    for case, vector in enumerate(inputs):
        settings = []
        for shard in range(3):
            start = shard * 256
            for local, value in enumerate(vector[start : start + 256] / activation_range):
                prefix = chr(ord("A") + shard)
                settings.append(f'"{prefix}{local:03d}" {css_number(float(value))}')
        input_rules.append(
            f'body:has(#case-{case}:checked) .root{{font-variation-settings:'
            + ",".join(settings)
            + "}"
        )

    metrics = []
    metric_rules = []
    probe_rules = []
    capture_rules = []
    for hidden in range(HIDDEN):
        characters = "".join(
            f"&#x{start + hidden:X};" for start in fc_fonts.codepoint_starts
        )
        factor = activation_range * q_fc.scales[hidden]
        multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
        offset = (
            GEOMETRY_OFFSET
            + GEOMETRY_SCALE * data["fc_bias"][hidden]
            - GEOMETRY_SCALE * factor * base_total
        )
        metrics.append(
            f'<i class="metric metric-{hidden}" style="width:calc-size(max-content,'
            f'size * {css_number(float(multiplier))} + ({css_number(float(offset))}px))">'
            f"{characters}</i>"
        )
        metric_rules.append(f'.metric-{hidden}{{anchor-name:--m{hidden}}}')
    for pair in range(HIDDEN // 2):
        first = 2 * pair
        probe_rules.append(
            f'.probe-{pair}{{width:anchor-size(--m{first} width);'
            f'height:anchor-size(--m{first + 1} width);container-type:size}}'
        )
        target = f'.probe-{pair + 1}' if pair + 1 < HIDDEN // 2 else ".projection"
        capture_rules.append(
            f'{target}{{--z{first}:calc((100cqi / 1px - {GEOMETRY_OFFSET}) / '
            f'{GEOMETRY_SCALE * PREACTIVATION_SCALE});'
            f'--z{first + 1}:calc((100cqb / 1px - {GEOMETRY_OFFSET}) / '
            f'{GEOMETRY_SCALE * PREACTIVATION_SCALE})}}'
        )
    projection_settings = ",".join(
        f'"{tag}" var(--z{index})' for index, tag in enumerate(tags)
    )
    fc_face_css = font_faces("fc", fc_fonts).replace(
        'url("fc-', 'url("../gpt2-block-css/fc-'
    )
    projection_tag = hashlib.sha256(projection_font.read_bytes()).hexdigest()[:12]
    html = f'''<!doctype html><meta charset="utf-8"><title>Parallel HVAR MLP group</title>
<style>{fc_face_css}
@font-face{{font-family:GeluProjection;src:url("gelu-projection.woff2?v={projection_tag}") format("woff2")}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(HIDDEN))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.root{{font-family:fcS0,fcS1,fcS2;
font-size:{FONT_SIZE}px;font-kerning:none;line-height:1}}.metric{{position:fixed;inset:0 auto auto 0;
display:inline-flex;height:1px;overflow:hidden;white-space:pre;font-style:normal}}.probe{{position:fixed;
inset:0 auto auto 0;overflow:visible}}.projection{{font-family:GeluProjection;font-size:1000px;
font-variation-settings:{projection_settings};font-kerning:none;line-height:1}}.output{{display:inline-block;
width:max-content;height:1px;overflow:hidden;font-style:normal}}{''.join(input_rules)}{''.join(metric_rules)}
{''.join(probe_rules)}{''.join(capture_rules)}</style>{controls}<div class="root">{nested_transport(metrics)}</div>'''
    (OUTPUT / "index.html").write_text(html)
    reference = {
        "tokenIds": TOKEN_IDS,
        "shape": [768, HIDDEN, OUTPUTS],
        "backend": BACKEND,
        "quantizedFcBits": QUANT_BITS,
        "preactivationScale": PREACTIVATION_SCALE,
        "outputScale": OUTPUT_SCALE,
        "baseAdvance": BASE_ADVANCE,
        "activationRange": activation_range,
        "preactivationMinimum": float(np.min(preactivations)),
        "preactivationMaximum": float(np.max(preactivations)),
        "hvarRegions": hvar_regions,
        "hvarDeltaValues": int((OUTPUTS + 1) * hvar_regions),
        "avarRegions": avar_regions,
        "avarDeltaValues": int(HIDDEN * (len(KNOTS) - 1)) if avar_regions else 0,
        "representedOutputs": represented.tolist(),
        "exactOutputs": exact.tolist(),
        "approximationRmse": float(np.sqrt(np.mean((represented - exact) ** 2))),
        "approximationMaximum": float(np.max(np.abs(represented - exact))),
        "projectionFontBytes": projection_font.stat().st_size,
        "fcFontBytes": sum((FC_FONT_DIR / f"{name}.woff2").stat().st_size for name in fc_fonts.names),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "elements": 2 * HIDDEN + OUTPUTS + len(TOKEN_IDS) + 1,
        "buildMilliseconds": (time.perf_counter() - started) * 1000,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in ("representedOutputs", "exactOutputs")
    }, indent=2))


if __name__ == "__main__":
    main()
