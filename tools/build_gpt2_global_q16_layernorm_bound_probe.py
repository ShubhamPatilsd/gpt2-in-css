#!/usr/bin/env python3
"""Build a contender-only global-q16 probe with analytic final-LN row bases."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_master


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-global-q16-layernorm-bound"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
PRODUCTION = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
RETAINED = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
RETAINED_PROBE = ROOT / "experiments" / "gpt2-global-q16-lattice-scale"
VOCABULARY = 50_257
WIDTH = 768
SHARD = 256
SHARDS = 3
Q16_MAXIMUM = 32_767
RADIX = 256
AXIS_STEPS = 16_384
DISPLAY_SCALES = (
    ("0p1", 0.1, "0.1", 0.0, False),
    ("1over16", 1 / 16, "1/16", 0.0, False),
    ("1over16-dither", 1 / 16, "1/16 + half-step", 0.5 / AXIS_STEPS, False),
    ("integer-axis", 1 / 16, "1/16 integer-axis", 0.0, True),
)
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
TOP_CONTENDERS = 16
LOW_MARGIN_STATES = 8
SAFETY_MARGIN_UNITS = 24
CHROME_ADVANCE_CEILING_PX = 32_768
CODEPOINT_STARTS = (0x20000, 0x30000, 0x40000, 0x50000, 0x60000, 0x70000)


def css_number(value: float) -> str:
    return head.css_number(float(value))


def top_k(scores: np.ndarray, count: int) -> np.ndarray:
    selected = np.argpartition(scores, -count, axis=1)[:, -count:]
    selected_scores = np.take_along_axis(scores, selected, axis=1)
    order = np.argsort(-selected_scores, axis=1, kind="stable")
    return np.take_along_axis(selected, order, axis=1)


def build_bounded_font(
    coefficients: np.ndarray,
    bases: np.ndarray,
    destination: Path,
    codepoint_start: int,
    axis_tags: list[str],
    axis_user_extent: int = 1,
) -> None:
    """Build HVAR rows whose bases are valid on the certified LN set, not a box."""
    if coefficients.shape[1] != len(axis_tags) or coefficients.shape[1] > 256:
        raise ValueError("one tag is required per coefficient and faces are capped at 256 axes")
    if np.any(coefficients < -32768) or np.any(coefficients > 32767):
        raise ValueError("HVAR deltas must fit signed int16")
    if np.any(bases <= 0) or np.any(bases > 65535):
        raise ValueError("default advances must be positive uint16 values")

    with tempfile.TemporaryDirectory(prefix="gpt2-ln-bound-font-") as temporary:
        source = Path(temporary) / "source.ttf"
        build_master(source, bases.astype(np.int32), "Regular", codepoint_start=codepoint_start)
        font = TTFont(source, recalcTimestamp=False)

        fvar = newTable("fvar")
        fvar.axes = []
        fvar.instances = []
        stat_axes = []
        for index, tag in enumerate(axis_tags):
            axis = Axis()
            axis.axisTag = tag
            axis.minValue = -axis_user_extent
            axis.defaultValue = 0
            axis.maxValue = axis_user_extent
            axis.flags = 0
            axis.axisNameID = font["name"].addName(tag)
            fvar.axes.append(axis)
            stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
        font["fvar"] = fvar
        buildStatTable(font, stat_axes)

        supports = []
        for tag in axis_tags:
            supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
        rows = [
            [delta for coefficient in row for delta in (-int(coefficient), int(coefficient))]
            for row in coefficients
        ]
        region_list = buildVarRegionList(supports, axis_tags)
        var_data = buildVarData(range(len(supports)), [[0] * len(supports), *rows], optimize=True)
        hvar = newTable("HVAR")
        hvar.table = otTables.HVAR()
        hvar.table.Version = 0x00010000
        hvar.table.VarStore = buildVarStore(region_list, [var_data])
        hvar.table.AdvWidthMap = None
        hvar.table.LsbMap = None
        hvar.table.RsbMap = None
        font["HVAR"] = hvar

        gvar = newTable("gvar")
        gvar.version = 1
        gvar.reserved = 0
        gvar.variations = {glyph: [] for glyph in font.getGlyphOrder()}
        font["gvar"] = gvar
        font.recalcTimestamp = False
        font.flavor = "woff2"
        font.save(destination)


def analytic_bounds(
    coefficients: np.ndarray,
    start: int,
    gamma: np.ndarray,
    beta: np.ndarray,
    coordinate_range: float,
) -> tuple[np.ndarray, list[dict[str, float | int]]]:
    stop = start + coefficients.shape[1]
    weighted = np.zeros((len(coefficients), WIDTH), dtype=np.float64)
    weighted[:, start:stop] = coefficients * gamma[None, start:stop]
    projected = weighted - weighted.mean(axis=1, keepdims=True)
    bias = coefficients @ beta[start:stop] / coordinate_range
    radius = math.sqrt(WIDTH) * np.linalg.norm(projected, axis=1) / coordinate_range
    bases = np.ceil(radius - bias + SAFETY_MARGIN_UNITS).astype(np.int32)
    lower = bases + bias - radius
    upper = bases + bias + radius
    if not np.all(lower >= SAFETY_MARGIN_UNITS - 1e-9) or not np.all(lower > 0):
        raise RuntimeError("analytic base failed its strict positive lower bound")
    if not np.all(upper < 65_535):
        raise RuntimeError("analytic reachable advance exceeded uint16")
    records = [
        {
            "bias": float(bias[row]),
            "radius": float(radius[row]),
            "base": int(bases[row]),
            "analyticMinimumAdvance": float(lower[row]),
            "analyticMaximumAdvance": float(upper[row]),
            "lowerBoundSafetyMargin": float(lower[row]),
        }
        for row in range(len(coefficients))
    ]
    return bases, records


def render_html(
    contenders: list[int],
    row_bases: np.ndarray,
    glyphs: list[str],
    factor: float,
    display_scale: float,
    slug: str,
    axis_dither: float,
    integer_axis: bool,
) -> str:
    rows = []
    count = len(contenders)
    for index, (token, base, characters) in enumerate(
        zip(contenders, row_bases, glyphs, strict=True)
    ):
        rows.append(
            f'<i id="row-{index}" class="candidate" data-token="{token}" '
            f'style="--base:{css_number(float(base) * display_scale)};'
            f'--factor:{css_number(factor)};--tie:{count - 1 - index}">{characters}</i>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none'; base-uri 'none'">
<title>GPT-2 global q16 analytic final-LayerNorm bound probe</title>
<link rel="stylesheet" href="index.css">
<body data-scale="{slug}" data-contenders="{count}" data-glyphs-per-row="6">
<main id="probe" class="probe">
  <section id="stage" class="stage{' integer-axis' if integer_axis else ''}" style="--font-size:{css_number(1_000 * display_scale)}px;--axis-dither:{css_number(axis_dither)};anchor-name:--winner">{"".join(rows)}</section>
  <span id="reader" class="reader"><output id="result"></output></span>
</main>
"""


def render_css(coordinate_range: float, contender_count: int) -> str:
    faces = []
    families = []
    integer_families = []
    for shard in range(SHARDS):
        for plane, name in enumerate(("high", "residual")):
            family = f"Bound{'H' if plane == 0 else 'R'}{shard}"
            integer_family = f"IntegerBound{'H' if plane == 0 else 'R'}{shard}"
            adjustment = ";size-adjust:25600%" if plane == 0 else ""
            faces.append(
                f'@font-face{{font-family:{family};src:url("score-{name}-{shard}.woff2") '
                f'format("woff2"){adjustment}}}'
            )
            faces.append(
                f'@font-face{{font-family:{integer_family};'
                f'src:url("score-integer-{name}-{shard}.woff2") '
                f'format("woff2"){adjustment}}}'
            )
            families.append(family)
            integer_families.append(integer_family)
    settings = ",".join(
        f'"{global_axis_tag(dimension)}" calc(var(--h{dimension})/{css_number(coordinate_range)} + var(--axis-dither))'
        for dimension in range(WIDTH)
    )
    integer_settings = ",".join(
        f'"{global_axis_tag(dimension)}" round(nearest,'
        f'calc(var(--h{dimension})/{css_number(coordinate_range)}*{AXIS_STEPS}),1)'
        for dimension in range(WIDTH)
    )
    return "\n".join(
        (
            "".join(faces),
            '@property --bucket{syntax:"<number>";inherits:true;initial-value:0}'
            '@property --index{syntax:"<number>";inherits:true;initial-value:0}',
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".probe{--score-offset:0px}",
            ".stage{position:fixed;left:0;top:-90000px;display:grid;"
            "grid-template-columns:max-content;grid-template-rows:1px;width:max-content;height:1px;"
            f"font-family:{','.join(families)};font-size:var(--font-size);line-height:1;"
            f"font-variation-settings:{settings};font-kerning:none;font-synthesis:none}}",
            f".stage.integer-axis{{font-family:{','.join(integer_families)};"
            f"font-variation-settings:{integer_settings}}}",
            ".candidate{display:block;grid-area:1/1;justify-self:start;height:1px;overflow:hidden;"
            "white-space:pre;font-style:normal;width:calc-size(max-content,calc(round(nearest,"
            "(size - var(--base)*1px)*var(--factor) + var(--score-offset),4px) "
            "+ var(--tie)/64*1px))}",
            ".reader{position:fixed;position-anchor:--winner;left:0;top:-89000px;"
            "width:anchor-size(--winner width);height:1px;container:result/inline-size}",
            "@container result (width >= 0px){#result{--bucket:round(down,100cqi/4px,1);"
            f"--index:calc({contender_count - 1} - round(nearest,mod(100cqi,4px)/1px*64,1));"
            "display:block;width:1px;height:1px}}",
        )
    ) + "\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    production_reference = json.loads((PRODUCTION / "reference.json").read_text())
    retained_reference = json.loads((RETAINED / "reference.json").read_text())
    retained_probe_reference = json.loads((RETAINED_PROBE / "reference.json").read_text())
    coordinate_range = float(production_reference["productionInputRange"])
    source_range = float(production_reference["sourceInputRange"])
    score_gain = float(production_reference["scoreGain"])

    state_data = np.load(STATES)
    hidden = np.asarray(state_data["hidden"], dtype=np.float64)
    tensors = SafeTensors(MODEL_PATH)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    z = (hidden - beta) / gamma
    z_means = z.mean(axis=1)
    z_norms = np.linalg.norm(z, axis=1)
    expected_norm = math.sqrt(WIDTH)

    coordinate_radius = np.abs(gamma) * math.sqrt(WIDTH - 1)
    coordinate_lower = beta - coordinate_radius
    coordinate_upper = beta + coordinate_radius
    coordinate_maximum = np.maximum(np.abs(coordinate_lower), np.abs(coordinate_upper))
    out_of_domain_dimensions = np.flatnonzero(coordinate_maximum > coordinate_range)
    if float(np.max(np.abs(hidden))) >= coordinate_range:
        raise RuntimeError("stored fixture corpus leaves the declared HVAR coordinate domain")

    weights = np.asarray(tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float64)
    q16_scale = float(np.max(np.abs(weights)) / Q16_MAXIMUM)
    if abs(q16_scale - float(retained_reference["weightScale"])) > 1e-15:
        raise RuntimeError("global q16 scale changed from the retained immutable bank")
    q16_codes = np.rint(weights / q16_scale).clip(-Q16_MAXIMUM, Q16_MAXIMUM).astype(np.int16)
    q16_weights = q16_codes.astype(np.float64) * q16_scale
    realized = np.rint(hidden / coordinate_range * AXIS_STEPS) / AXIS_STEPS * coordinate_range

    float_winners = np.empty(len(hidden), dtype=np.int64)
    q16_winners = np.empty(len(hidden), dtype=np.int64)
    float_margins = np.empty(len(hidden), dtype=np.float64)
    top_float = np.empty((len(hidden), TOP_CONTENDERS), dtype=np.int64)
    top_q16 = np.empty((len(hidden), TOP_CONTENDERS), dtype=np.int64)
    for start in range(0, len(hidden), 16):
        stop = min(start + 16, len(hidden))
        float_scores = realized[start:stop] @ weights.T
        q16_scores = realized[start:stop] @ q16_weights.T
        ordered_float = top_k(float_scores, TOP_CONTENDERS)
        ordered_q16 = top_k(q16_scores, TOP_CONTENDERS)
        ordered_float_scores = np.take_along_axis(float_scores, ordered_float, axis=1)
        top_float[start:stop] = ordered_float
        top_q16[start:stop] = ordered_q16
        float_winners[start:stop] = ordered_float[:, 0]
        q16_winners[start:stop] = ordered_q16[:, 0]
        float_margins[start:stop] = ordered_float_scores[:, 0] - ordered_float_scores[:, 1]

    low_margin = np.argsort(float_margins, kind="stable")[:LOW_MARGIN_STATES]
    production_states = np.asarray(
        production_reference["certifiedFixtures"]["sourceStateIndices"], dtype=np.int64
    )
    roles: dict[int, list[str]] = {}
    selected_states: list[int] = []
    selections = (
        (519, "named-state-519"),
        (547, "named-state-547"),
        (493, "named-state-493"),
        *((int(state), "lowest-float-margin") for state in low_margin),
        *((int(state), "production-fixture") for state in production_states),
    )
    for state, role in selections:
        roles.setdefault(state, []).append(role)
        if state not in selected_states:
            selected_states.append(state)

    contender_set = {2032}
    for state in selected_states:
        contender_set.update(int(token) for token in top_float[state])
        contender_set.update(int(token) for token in top_q16[state])
    contenders = sorted(contender_set)
    if contenders != retained_probe_reference["contenders"]:
        raise RuntimeError("targeted contender union changed from the retained 192-row control")
    contender_codes = q16_codes[contenders].astype(np.int32)
    high = np.trunc(contender_codes / RADIX).astype(np.int16)
    residual = (contender_codes - high.astype(np.int32) * RADIX).astype(np.int16)
    if not np.array_equal(high.astype(np.int32) * RADIX + residual.astype(np.int32), contender_codes):
        raise RuntimeError("radix-256 high/residual split is not exact")

    glyphs = [""] * len(contenders)
    row_bases = np.zeros(len(contenders), dtype=np.int64)
    row_bound_records = [{"token": token, "faces": []} for token in contenders]
    face_summaries = []
    font_files = []
    for shard in range(SHARDS):
        start = shard * SHARD
        stop = start + SHARD
        for plane, (name, coefficients) in enumerate((("high", high), ("residual", residual))):
            face = shard * 2 + plane
            values = coefficients[:, start:stop]
            bases, records = analytic_bounds(values, start, gamma, beta, coordinate_range)
            destination = OUTPUT / f"score-{name}-{shard}.woff2"
            build_bounded_font(
                values,
                bases,
                destination,
                CODEPOINT_STARTS[face],
                [global_axis_tag(dimension) for dimension in range(start, stop)],
            )
            integer_destination = OUTPUT / f"score-integer-{name}-{shard}.woff2"
            build_bounded_font(
                values,
                bases,
                integer_destination,
                CODEPOINT_STARTS[face],
                [global_axis_tag(dimension) for dimension in range(start, stop)],
                axis_user_extent=AXIS_STEPS,
            )
            normalized_font = TTFont(destination, recalcTimestamp=False)
            integer_font = TTFont(integer_destination, recalcTimestamp=False)
            integer_axis_ranges = {
                (float(axis.minValue), float(axis.defaultValue), float(axis.maxValue))
                for axis in integer_font["fvar"].axes
            }
            hvar_bytes_match = normalized_font.getTableData("HVAR") == integer_font.getTableData("HVAR")
            if integer_axis_ranges != {(-AXIS_STEPS, 0.0, AXIS_STEPS)}:
                raise RuntimeError("integer-axis font did not retain the requested fvar range")
            if not hvar_bytes_match:
                raise RuntimeError("integer-axis font changed normalized HVAR regions or deltas")
            hvar_sha256 = hashlib.sha256(integer_font.getTableData("HVAR")).hexdigest()
            normalized_font.close()
            integer_font.close()
            multiplier = RADIX if name == "high" else 1
            row_bases += bases.astype(np.int64) * multiplier
            for row, record in enumerate(records):
                row_bound_records[row]["faces"].append(
                    {"shard": shard, "plane": name, **record}
                )
                glyphs[row] += chr(CODEPOINT_STARTS[face] + row)
            minimum = min(record["analyticMinimumAdvance"] for record in records)
            maximum = max(record["analyticMaximumAdvance"] for record in records)
            face_summaries.append(
                {
                    "shard": shard,
                    "plane": name,
                    "dimensions": [start, stop],
                    "coefficientMinimum": int(values.min()),
                    "coefficientMaximum": int(values.max()),
                    "baseMinimum": int(bases.min()),
                    "baseMaximum": int(bases.max()),
                    "analyticMinimumAdvance": float(minimum),
                    "analyticMaximumAdvance": float(maximum),
                    "font": destination.name,
                    "bytes": destination.stat().st_size,
                    "integerAxisFont": integer_destination.name,
                    "integerAxisBytes": integer_destination.stat().st_size,
                    "integerAxisFvarRange": [-AXIS_STEPS, 0, AXIS_STEPS],
                    "integerAxisCount": SHARD,
                    "hvarBytesMatchNormalizedFont": hvar_bytes_match,
                    "sharedHvarSha256": hvar_sha256,
                }
            )
            font_files.append(destination)
            font_files.append(integer_destination)

    (OUTPUT / "index.css").write_text(render_css(coordinate_range, len(contenders)))
    scale_records = []
    for slug, display_scale, label, axis_dither, integer_axis in DISPLAY_SCALES:
        factor = (
            coordinate_range * score_gain * q16_scale * SCORE_SCALE
            * SCORE_STRIDE_PX / display_scale
        )
        html = f"scale-{slug}.html"
        (OUTPUT / html).write_text(
            render_html(
                contenders,
                row_bases,
                glyphs,
                factor,
                display_scale,
                slug,
                axis_dither,
                integer_axis,
            )
        )
        high_maximum = max(
            face["analyticMaximumAdvance"] for face in face_summaries if face["plane"] == "high"
        ) * display_scale * RADIX
        residual_maximum = max(
            face["analyticMaximumAdvance"] for face in face_summaries if face["plane"] == "residual"
        ) * display_scale
        scale_records.append(
            {
                "slug": slug,
                "label": label,
                "html": html,
                "displayScale": display_scale,
                "fontSizePx": 1_000 * display_scale,
                "axisDither": axis_dither,
                "axisMode": "integer-user-coordinate" if integer_axis else "normalized-user-coordinate",
                "fvarUserExtent": AXIS_STEPS if integer_axis else 1,
                "cssAxisFormula": (
                    "round(nearest, hidden/R*16384, 1)" if integer_axis
                    else "hidden/R + axisDither"
                ),
                "coordinateQuantizationOracle": "nearest 1/16384 normalized coordinate",
                "residualUnitLayout64": display_scale * 64,
                "highUnitLayout64": display_scale * RADIX * 64,
                "scoreFactor": factor,
                "analyticMaximumHighPlaneAdjustedAdvancePx": high_maximum,
                "analyticMaximumResidualPlaneAdjustedAdvancePx": residual_maximum,
                "analyticMaximumAdjustedAdvancePx": max(high_maximum, residual_maximum),
                "belowChromeAdvanceCeiling": max(high_maximum, residual_maximum)
                < CHROME_ADVANCE_CEILING_PX,
            }
        )

    fixtures = []
    contender_weights = weights[contenders]
    contender_q16_weights = q16_weights[contenders]
    for state in selected_states:
        query = realized[state]
        float_scores = query @ contender_weights.T * score_gain
        q16_scores = query @ contender_q16_weights.T * score_gain
        score_floor = int(np.floor(min(float_scores.min(), q16_scores.min())) - 2)
        float_buckets = np.rint((float_scores - score_floor) * SCORE_SCALE).astype(np.int64)
        q16_buckets = np.rint((q16_scores - score_floor) * SCORE_SCALE).astype(np.int64)
        fixtures.append(
            {
                "state": state,
                "roles": roles[state],
                "hidden": hidden[state].tolist(),
                "realizedHidden": query.tolist(),
                "reconstructedZMean": float(z_means[state]),
                "reconstructedZNorm": float(z_norms[state]),
                "scoreFloor": score_floor,
                "floatWinner": int(float_winners[state]),
                "q16MathematicalWinner": int(q16_winners[state]),
                "floatMargin": float(float_margins[state]),
                "floatBucketWinner": contenders[int(np.argmax(float_buckets))],
                "q16BucketWinner": contenders[int(np.argmax(q16_buckets))],
                "floatBuckets": float_buckets.tolist(),
                "q16Buckets": q16_buckets.tolist(),
                "topFloatContenders": top_float[state].astype(int).tolist(),
                "topQ16Contenders": top_q16[state].astype(int).tolist(),
            }
        )

    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "runtimeContainsJavaScript": False,
        "backend": "global-q16-radix256-three-shard-pairs-final-ln-cauchy-bases",
        "proofScope": {
            "advanceBound": "full set sum(z)=0 and ||z||2<=sqrt(768)",
            "exactTransport": "advance-bound set intersected with |y_i|<=R for every coordinate",
            "overclaimAvoided": True,
            "coordinateRangeR": coordinate_range,
            "analyticCoordinateMaximumAbsolute": float(coordinate_maximum.max()),
            "analyticCoordinateMaximumDimension": int(np.argmax(coordinate_maximum)),
            "dimensionsWhoseAnalyticCoordinateBoundExceedsR": out_of_domain_dimensions.astype(int).tolist(),
            "analyticCoordinateBounds": [
                {"dimension": int(index), "minimum": float(coordinate_lower[index]), "maximum": float(coordinate_upper[index])}
                for index in out_of_domain_dimensions
            ],
            "storedCorpusMaximumAbsoluteCoordinate": float(np.max(np.abs(hidden))),
            "storedCorpusInsideDeclaredDomain": bool(np.all(np.abs(hidden) <= coordinate_range)),
        },
        "layerNormReachability": {
            "formula": "bias=c.beta/R; radius=sqrt(768)*||P(c*gamma padded to 768)||2/R",
            "projection": "P(v)=v-mean(v)1, using sum(z)=0",
            "baseFormula": "ceil(radius-bias+safetyMargin)",
            "safetyMarginAdvanceUnits": SAFETY_MARGIN_UNITS,
            "allAnalyticLowerBoundsStrictlyPositive": all(
                face["analyticMinimumAdvance"] > 0 for face in face_summaries
            ),
            "minimumAnalyticAdvance": min(face["analyticMinimumAdvance"] for face in face_summaries),
            "maximumAnalyticAdvance": max(face["analyticMaximumAdvance"] for face in face_summaries),
        },
        "storedLayerNormReconstruction": {
            "states": len(hidden),
            "maximumAbsoluteZMean": float(np.max(np.abs(z_means))),
            "expectedZNorm": expected_norm,
            "minimumZNorm": float(z_norms.min()),
            "maximumZNorm": float(z_norms.max()),
            "maximumAbsoluteZNormError": float(np.max(np.abs(z_norms - expected_norm))),
        },
        "productionCoordinates": {
            "inputRange": coordinate_range,
            "axisSteps": AXIS_STEPS,
            "sourceInputRange": source_range,
            "homogeneousScoreGain": score_gain,
        },
        "q16": {
            "bits": 16,
            "weightScale": q16_scale,
            "codesSha256": hashlib.sha256(q16_codes.tobytes()).hexdigest(),
            "radix": RADIX,
            "planes": ["high", "residual"],
            "shardsPerPlane": SHARDS,
            "dimensionsPerShard": SHARD,
            "glyphsPerRow": 6,
            "displayScales": [scale[1] for scale in DISPLAY_SCALES],
            "boundedFontCount": 6,
            "integerAxisFontCount": 6,
            "newFontCount": len(font_files),
            "fontBytes": sum(path.stat().st_size for path in font_files),
        },
        "chromeAdvanceCeilingPx": CHROME_ADVANCE_CEILING_PX,
        "scales": scale_records,
        "faceBounds": face_summaries,
        "rowBounds": row_bound_records,
        "selection": {
            "selectedStates": selected_states,
            "selectedStateCount": len(selected_states),
            "lowestMarginStates": low_margin.astype(int).tolist(),
            "productionFixtureStates": production_states.astype(int).tolist(),
            "topFloatContendersPerState": TOP_CONTENDERS,
            "topQ16ContendersPerState": TOP_CONTENDERS,
            "explicitAlternateToken": 2032,
            "matchesRetainedContenderRowsExactly": True,
        },
        "corpusScreen": {
            "states": len(hidden),
            "q16MathematicalMismatchStates": np.flatnonzero(float_winners != q16_winners).astype(int).tolist(),
        },
        "contenders": contenders,
        "contenderCount": len(contenders),
        "fixtures": fixtures,
        "retainedLatencyControl": {
            "experiment": "gpt2-global-q16-lattice-scale",
            "html": "scale-0p1.html",
            "glyphsPerRow": 12,
            "correctnessOracle": False,
        },
        "generatedFiles": {
            "html": [scale["html"] for scale in scale_records],
            "css": "index.css",
            "fonts": [path.name for path in font_files],
        },
    }
    if reference["contenderCount"] != 192 or reference["q16"]["newFontCount"] != 12:
        raise RuntimeError(
            "targeted probe must contain exactly 192 rows and two six-font banks"
        )
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key not in {"fixtures", "rowBounds"}}, indent=2))


if __name__ == "__main__":
    main()
