#!/usr/bin/env python3
"""Build a full-vocabulary integer-axis global-q16 final-LN output head."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

import build_gpt2_hvar_grid_output_head as baseline
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_master


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-global-q16-layernorm-integer-full"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
PRODUCTION = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
TARGETED = ROOT / "experiments" / "gpt2-global-q16-layernorm-bound"
RETAINED = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
VOCABULARY = 50_257
WIDTH = 768
SHARD = 256
SHARDS = 3
RADIX = 256
Q16_MAXIMUM = 32_767
AXIS_STEPS = 16_384
DISPLAY_SCALE = 1 / 16
FONT_SIZE_PX = 1_000 * DISPLAY_SCALE
SAFETY_MARGIN_UNITS = 24
CODEPOINT_STARTS = (0x20000, 0x30000, 0x40000, 0x50000, 0x60000, 0x70000)
CHROME_ADVANCE_CEILING_PX = 32_768


def css_number(value: float) -> str:
    return baseline.css_number(float(value))


def analytic_bases(
    coefficients: np.ndarray,
    start: int,
    gamma: np.ndarray,
    beta: np.ndarray,
    coordinate_range: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    stop = start + coefficients.shape[1]
    local_gamma = gamma[start:stop]
    local_beta = beta[start:stop]
    bases = np.empty(len(coefficients), dtype=np.int32)
    minimum = math.inf
    maximum = -math.inf
    minimum_bias = math.inf
    maximum_bias = -math.inf
    minimum_radius = math.inf
    maximum_radius = -math.inf
    for row_start in range(0, len(coefficients), 2048):
        row_stop = min(row_start + 2048, len(coefficients))
        rows = coefficients[row_start:row_stop].astype(np.float64)
        weighted = rows * local_gamma
        weighted_sum = weighted.sum(axis=1)
        projected_norm_squared = np.maximum(
            np.square(weighted).sum(axis=1) - np.square(weighted_sum) / WIDTH,
            0,
        )
        bias = rows @ local_beta / coordinate_range
        radius = math.sqrt(WIDTH) * np.sqrt(projected_norm_squared) / coordinate_range
        row_bases = np.ceil(radius - bias + SAFETY_MARGIN_UNITS).astype(np.int32)
        lower = row_bases + bias - radius
        upper = row_bases + bias + radius
        if not np.all(lower >= SAFETY_MARGIN_UNITS - 1e-9) or not np.all(lower > 0):
            raise RuntimeError("analytic lower bound is not strictly positive")
        if not np.all(upper < 65_535):
            raise RuntimeError("analytic upper bound exceeds uint16")
        bases[row_start:row_stop] = row_bases
        minimum = min(minimum, float(lower.min()))
        maximum = max(maximum, float(upper.max()))
        minimum_bias = min(minimum_bias, float(bias.min()))
        maximum_bias = max(maximum_bias, float(bias.max()))
        minimum_radius = min(minimum_radius, float(radius.min()))
        maximum_radius = max(maximum_radius, float(radius.max()))
    return bases, {
        "biasMinimum": minimum_bias,
        "biasMaximum": maximum_bias,
        "radiusMinimum": minimum_radius,
        "radiusMaximum": maximum_radius,
        "baseMinimum": int(bases.min()),
        "baseMaximum": int(bases.max()),
        "analyticMinimumAdvance": minimum,
        "analyticMaximumAdvance": maximum,
    }


def hvar_items(coefficients: np.ndarray):
    yield [0] * (2 * coefficients.shape[1])
    for row in coefficients:
        yield [delta for value in row for delta in (-int(value), int(value))]


def build_integer_font(
    coefficients: np.ndarray,
    bases: np.ndarray,
    destination: Path,
    codepoint_start: int,
    axis_tags: list[str],
) -> None:
    """Build one final WOFF2 with integer user axes and normalized signed HVAR."""
    partial = destination.with_name(destination.name + ".partial")
    if partial.exists():
        partial.unlink()
    with tempfile.TemporaryDirectory(prefix="gpt2-q16-full-font-") as temporary:
        source = Path(temporary) / "source.ttf"
        build_master(source, bases, "Regular", codepoint_start=codepoint_start)
        font = TTFont(source, recalcTimestamp=False)

        fvar = newTable("fvar")
        fvar.axes = []
        fvar.instances = []
        stat_axes = []
        for index, tag in enumerate(axis_tags):
            axis = Axis()
            axis.axisTag = tag
            axis.minValue = -AXIS_STEPS
            axis.defaultValue = 0
            axis.maxValue = AXIS_STEPS
            axis.flags = 0
            axis.axisNameID = font["name"].addName(tag)
            fvar.axes.append(axis)
            stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
        font["fvar"] = fvar
        buildStatTable(font, stat_axes)

        supports = []
        for tag in axis_tags:
            supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
        region_list = buildVarRegionList(supports, axis_tags)
        var_data = buildVarData(
            range(len(supports)),
            hvar_items(coefficients),
            optimize=False,
        )
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
        font.save(partial)
        font.close()
    partial.replace(destination)


def render_html(row_bases: np.ndarray, factor: float, fixture_count: int) -> str:
    groups = math.ceil(VOCABULARY / baseline.GROUP_SIZE)
    group_markup = []
    for group in range(groups):
        start = group * baseline.GROUP_SIZE
        stop = min(VOCABULARY, start + baseline.GROUP_SIZE)
        items = []
        for token in range(start, stop):
            characters = "".join(chr(codepoint + token) for codepoint in CODEPOINT_STARTS)
            items.append(
                f'<i class="candidate" data-token="{token}" '
                f'style="--base:{css_number(row_bases[token] * DISPLAY_SCALE)};'
                f'--factor:{css_number(factor)};'
                f'--local-tie:{baseline.GROUP_SIZE - 1 - token % baseline.GROUP_SIZE}">'
                f"{characters}</i>"
            )
        group_markup.append(
            f'<section class="group-wrapper" style="anchor-name:--score-group-{group};'
            f'view-timeline:--ogt{group} inline"><div class="group-grid group-{group}">'
            f'{"".join(items)}</div></section>'
        )
    controls = "".join(
        f'<input type="radio" name="query" id="q{query}"'
        f'{" checked" if query == 0 else ""}>'
        for query in range(fixture_count)
    )
    match_carriers = "".join(
        f'<i class="match-carrier match-carrier-{group}"></i>' for group in range(groups)
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none'; base-uri 'none'">
<title>Full GPT-2 global-q16 integer-axis final-LN output head</title>
<link rel="stylesheet" href="index.css">
{controls}
<main id="model" class="model">{"".join(group_markup)}</main>
<i class="outer-max"></i>
<div class="outer-reader"><div class="selection">
{match_carriers}<i class="group-choice"></i>
<div class="group-choice-reader"><output id="result" class="result"></output></div>
</div></div>
"""


def render_css(
    hidden: np.ndarray,
    floors: np.ndarray,
    coordinate_range: float,
) -> str:
    groups = math.ceil(VOCABULARY / baseline.GROUP_SIZE)
    placeholder_scales = np.ones(VOCABULARY, dtype=np.float64)
    css = baseline.render_css(hidden, placeholder_scales, coordinate_range, floors, groups)
    _faces, body = css.split("\n", 1)
    face_rules = []
    families = []
    for shard in range(SHARDS):
        for plane, name in enumerate(("high", "residual")):
            family = f"FullQ16{'H' if plane == 0 else 'R'}{shard}"
            adjustment = ";size-adjust:25600%" if plane == 0 else ""
            face_rules.append(
                f'@font-face{{font-family:{family};src:url("score-{name}-{shard}.woff2") '
                f'format("woff2"){adjustment}}}'
            )
            families.append(family)
    settings = ",".join(
        f'"{global_axis_tag(dimension)}" round(nearest,'
        f'calc(var(--h{dimension})/{css_number(coordinate_range)}*{AXIS_STEPS}),1)'
        for dimension in range(WIDTH)
    )
    body = body.replace(
        "font-family:Score0,Score1,Score2,Score3,Score4;",
        f"font-family:{','.join(families)};",
    )
    body = body.replace(
        f"font-size:{baseline.FONT_SIZE}px;",
        f"font-size:{css_number(FONT_SIZE_PX)}px;",
    )
    body, replacements = re.subn(
        r"font-variation-settings:[^;]+;",
        f"font-variation-settings:{settings};",
        body,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("could not replace normalized font variation settings")
    body = body.replace("font-kerning:none}", "font-kerning:none;font-synthesis:none}")
    # Put all bucket-rounded group wrappers in one overlapping grid. This makes
    # the model's max-content width the winning bucket directly. The retained
    # unrounded group-grid anchors still carry the 1/64 px local tie identity.
    # The baseline scroll-timeline proxy can lag an axis mutation by one input,
    # which aliases group/local decoding and can emit the sentinel group 197.
    outer_sizes = ",".join(
        f"anchor-size(--score-group-{group} width)" for group in range(groups)
    )
    direct_match_rules = "".join(
        f".match-carrier-{group}{{width:calc(clamp(0px,"
        f"anchor-size(--score-group-{group} width) - "
        "anchor-size(--outer-winner width) + 1px,1px) * "
        f"{(groups - group) * 4} + "
        f"mod(anchor-size(--group-{group} width),4px))}}"
        for group in range(groups)
    )
    body += (
        "\n.model{anchor-name:none}.model>.group-wrapper{position:relative;left:auto;top:auto;"
        "grid-area:1/1}"
        ".outer-max{position:fixed;left:0;top:-85000px;height:1px;"
        "position-anchor:--score-group-0;anchor-name:--outer-winner;"
        f"width:max({outer_sizes})}}"
        + direct_match_rules
        + "@container group-choice-result (width >= 0px){.result{"
        f"--group:calc({groups} - round(down,100cqi/4px,1));"
        "--local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
        "--winner:calc(var(--group)*256 + var(--local));"
        "display:block;width:calc(var(--winner)*1px);height:1px}}"
    )
    return "".join(face_rules) + "\n" + body


def main() -> None:
    started = time.monotonic()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    free_before = shutil.disk_usage(OUTPUT).free
    production = json.loads((PRODUCTION / "reference.json").read_text())
    targeted = json.loads((TARGETED / "reference.json").read_text())
    retained = json.loads((RETAINED / "reference.json").read_text())
    coordinate_range = float(production["productionInputRange"])
    score_gain = float(production["scoreGain"])
    state_data = np.load(STATES)
    hidden_all = np.asarray(state_data["hidden"], dtype=np.float64)
    tensors = SafeTensors(MODEL_PATH)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    weights = np.asarray(tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float64)
    q16_scale = float(np.max(np.abs(weights)) / Q16_MAXIMUM)
    if abs(q16_scale - float(retained["weightScale"])) > 1e-15:
        raise RuntimeError("immutable global-q16 scale changed")
    q16_codes = np.rint(weights / q16_scale).clip(-Q16_MAXIMUM, Q16_MAXIMUM).astype(np.int16)
    q16_weights = q16_codes.astype(np.float64) * q16_scale
    high = np.trunc(q16_codes.astype(np.int32) / RADIX).astype(np.int16)
    residual = (q16_codes.astype(np.int32) - high.astype(np.int32) * RADIX).astype(np.int16)
    if not np.array_equal(high.astype(np.int32) * RADIX + residual.astype(np.int32), q16_codes):
        raise RuntimeError("radix-256 decomposition changed q16 codes")

    realized_all = (
        np.rint(hidden_all / coordinate_range * AXIS_STEPS)
        / AXIS_STEPS * coordinate_range
    )
    corpus_q16_margin_buckets = np.empty(len(hidden_all), dtype=np.float64)
    corpus_q16_winners = np.empty(len(hidden_all), dtype=np.int64)
    for batch_start in range(0, len(hidden_all), 16):
        batch_stop = min(batch_start + 16, len(hidden_all))
        scores = hidden_all[batch_start:batch_stop] @ q16_weights.T * score_gain
        top2 = np.argpartition(scores, -2, axis=1)[:, -2:]
        top2_scores = np.take_along_axis(scores, top2, axis=1)
        order = np.argsort(-top2_scores, axis=1, kind="stable")
        ordered = np.take_along_axis(top2, order, axis=1)
        ordered_scores = np.take_along_axis(scores, ordered, axis=1)
        corpus_q16_winners[batch_start:batch_stop] = ordered[:, 0]
        corpus_q16_margin_buckets[batch_start:batch_stop] = (
            ordered_scores[:, 0] - ordered_scores[:, 1]
        ) * baseline.SCORE_SCALE
    lowest_margin_states = np.argsort(corpus_q16_margin_buckets, kind="stable")[:32]
    production_states = np.asarray(
        production["certifiedFixtures"]["sourceStateIndices"], dtype=np.int64
    )
    selected_states = [int(state) for state in lowest_margin_states]
    selected_states.extend(
        int(state) for state in production_states if int(state) not in selected_states
    )
    at_most_two = np.flatnonzero(corpus_q16_margin_buckets <= 2 + 1e-12)
    at_most_one = np.flatnonzero(corpus_q16_margin_buckets <= 1 + 1e-12)
    if len(at_most_two) != 20 or len(at_most_one) != 10:
        raise RuntimeError(
            "decision-risk screen changed: expected 20 states <=2 buckets and 10 <=1"
        )
    if not set(at_most_two.astype(int)).issubset(selected_states):
        raise RuntimeError("lowest-32 suite lost a <=2-bucket decision-risk state")
    hidden = hidden_all[selected_states]
    realized = realized_all[selected_states]
    float_scores = realized @ weights.T * score_gain
    q16_scores = realized @ q16_weights.T * score_gain
    floors = np.floor(np.minimum(float_scores.min(axis=1), q16_scores.min(axis=1))).astype(int) - 2
    float_buckets = np.rint((float_scores - floors[:, None]) * baseline.SCORE_SCALE).astype(np.int32)
    q16_buckets = np.rint((q16_scores - floors[:, None]) * baseline.SCORE_SCALE).astype(np.int32)
    float_winners = float_scores.argmax(axis=1)
    q16_winners = q16_scores.argmax(axis=1)
    q16_bucket_winners = q16_buckets.argmax(axis=1)
    if not np.array_equal(q16_winners, q16_bucket_winners):
        raise RuntimeError("q16 bucket quantization changed a fixture winner")

    row_bases = np.zeros(VOCABULARY, dtype=np.int64)
    face_records = []
    font_paths = []
    reuse_fonts = os.environ.get("GPT2_Q16_INTEGER_FULL_REUSE_FONTS", "0") == "1"
    for shard in range(SHARDS):
        start = shard * SHARD
        stop = start + SHARD
        for plane, (name, values) in enumerate((("high", high), ("residual", residual))):
            coefficients = values[:, start:stop]
            bases, bounds = analytic_bases(
                coefficients, start, gamma, beta, coordinate_range
            )
            multiplier = RADIX if name == "high" else 1
            row_bases += bases.astype(np.int64) * multiplier
            destination = OUTPUT / f"score-{name}-{shard}.woff2"
            face_started = time.monotonic()
            if reuse_fonts and destination.exists():
                print(f"reusing {destination.name}", flush=True)
            else:
                print(f"building {destination.name} ({len(coefficients):,} rows)", flush=True)
                build_integer_font(
                    coefficients,
                    bases,
                    destination,
                    CODEPOINT_STARTS[2 * shard + plane],
                    [global_axis_tag(dimension) for dimension in range(start, stop)],
                )
            font = TTFont(destination, recalcTimestamp=False)
            ranges = {
                (float(axis.minValue), float(axis.defaultValue), float(axis.maxValue))
                for axis in font["fvar"].axes
            }
            if ranges != {(-AXIS_STEPS, 0.0, AXIS_STEPS)}:
                raise RuntimeError(f"{destination.name} has the wrong fvar range")
            if len(font.getGlyphOrder()) != VOCABULARY + 1 or len(font["fvar"].axes) != SHARD:
                raise RuntimeError(f"{destination.name} has the wrong glyph or axis count")
            hvar_hash = hashlib.sha256(font.getTableData("HVAR")).hexdigest()
            font.close()
            adjusted_scale = DISPLAY_SCALE * multiplier
            face_records.append(
                {
                    "shard": shard,
                    "plane": name,
                    "dimensions": [start, stop],
                    "rows": VOCABULARY,
                    "axes": SHARD,
                    "fvarUserRange": [-AXIS_STEPS, 0, AXIS_STEPS],
                    "coefficientMinimum": int(coefficients.min()),
                    "coefficientMaximum": int(coefficients.max()),
                    **bounds,
                    "analyticMaximumAdjustedAdvancePx": bounds["analyticMaximumAdvance"]
                    * adjusted_scale,
                    "font": destination.name,
                    "bytes": destination.stat().st_size,
                    "hvarSha256": hvar_hash,
                    "buildSeconds": time.monotonic() - face_started,
                }
            )
            font_paths.append(destination)
            print(
                f"finished {destination.name}: {destination.stat().st_size / 2**20:.1f} MiB",
                flush=True,
            )

    factor = (
        coordinate_range * score_gain * q16_scale * baseline.SCORE_SCALE
        * baseline.SCORE_STRIDE_PX / DISPLAY_SCALE
    )
    (OUTPUT / "index.css").write_text(render_css(hidden, floors, coordinate_range))
    (OUTPUT / "index.html").write_text(render_html(row_bases, factor, len(hidden)))

    targeted_roles = {int(row["state"]): row["roles"] for row in targeted["fixtures"]}
    fixtures = []
    for index, state in enumerate(selected_states):
        ordered_q16 = np.argsort(-q16_scores[index], kind="stable")[:2]
        ordered_float = np.argsort(-float_scores[index], kind="stable")[:2]
        fixtures.append(
            {
                "query": index,
                "state": state,
                "roles": [
                    *(targeted_roles.get(state, [])),
                    *( ["lowest-32-q16-margin"] if state in set(lowest_margin_states.astype(int)) else [] ),
                    *( ["q16-margin-at-most-2-buckets"] if state in set(at_most_two.astype(int)) else [] ),
                    *( ["q16-margin-at-most-1-bucket"] if state in set(at_most_one.astype(int)) else [] ),
                    *( ["production-route-fixture"] if state in set(production_states.astype(int)) else [] ),
                ],
                "hidden": hidden[index].tolist(),
                "realizedHidden": realized[index].tolist(),
                "scoreFloor": int(floors[index]),
                "q16Winner": int(q16_winners[index]),
                "q16RunnerUp": int(ordered_q16[1]),
                "q16Margin": float(q16_scores[index, ordered_q16[0]] - q16_scores[index, ordered_q16[1]]),
                "rawProductionQ16MarginBuckets": float(corpus_q16_margin_buckets[state]),
                "q16BucketWinner": int(q16_bucket_winners[index]),
                "floatWinner": int(float_winners[index]),
                "floatRunnerUp": int(ordered_float[1]),
                "floatMargin": float(float_scores[index, ordered_float[0]] - float_scores[index, ordered_float[1]]),
                "q16Buckets": q16_buckets[index].tolist(),
                "floatBuckets": float_buckets[index].tolist(),
            }
        )

    z = (hidden_all - beta) / gamma
    coordinate_radius = np.abs(gamma) * math.sqrt(WIDTH - 1)
    coordinate_maximum = np.maximum(
        np.abs(beta - coordinate_radius), np.abs(beta + coordinate_radius)
    )
    reference = {
        "model": "openai-community/gpt2",
        "modelArchitectureChanged": False,
        "sourceCheckpointWeightsChanged": False,
        "quantizedRepresentation": "immutable global-q16 approximation derived from the source checkpoint",
        "runtimeContainsJavaScript": False,
        "backend": "full-vocabulary-global-q16-radix256-integer-axis-final-ln-bounds-direct-grid-reducer",
        "vocabulary": VOCABULARY,
        "width": WIDTH,
        "groups": math.ceil(VOCABULARY / baseline.GROUP_SIZE),
        "reducer": {
            "topology": "direct-overlapping-group-grid-single-stage-group-local-decoder",
            "groupIdentityTieBreak": "lowest group id",
            "localIdentityTieBreak": "lowest local id via (255-local)/64px",
            "encodedMatchWidth": "(197-group)*4px + local-tie/64px",
            "lastPartialGroupRows": VOCABULARY % baseline.GROUP_SIZE,
            "maximumDecodedToken": VOCABULARY - 1,
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
        },
        "coordinates": {
            "declaredRangeR": coordinate_range,
            "axisSteps": AXIS_STEPS,
            "fvarUserRange": [-AXIS_STEPS, 0, AXIS_STEPS],
            "cssFormula": "round(nearest, hidden/R*16384, 1)",
            "displayScale": DISPLAY_SCALE,
            "fontSizePx": FONT_SIZE_PX,
            "scoreGain": score_gain,
            "storedCorpusMaximumAbsolute": float(np.max(np.abs(hidden_all))),
            "analyticCoordinateMaximumAbsolute": float(coordinate_maximum.max()),
            "exactTransportScope": "final-LN reachability ball intersected with |y_i|<=R",
        },
        "layerNormBound": {
            "formula": "bias=c.beta/R; radius=sqrt(768)*||P(c*gamma padded to 768)||2/R",
            "baseFormula": "ceil(radius-bias+24)",
            "safetyMarginUnits": SAFETY_MARGIN_UNITS,
            "minimumAnalyticAdvance": min(face["analyticMinimumAdvance"] for face in face_records),
            "maximumAnalyticAdvance": max(face["analyticMaximumAdvance"] for face in face_records),
            "maximumAdjustedAdvancePx": max(
                face["analyticMaximumAdjustedAdvancePx"] for face in face_records
            ),
            "belowChromeAdvanceCeiling": max(
                face["analyticMaximumAdjustedAdvancePx"] for face in face_records
            ) < CHROME_ADVANCE_CEILING_PX,
        },
        "storedLayerNormReconstruction": {
            "maximumAbsoluteZMean": float(np.max(np.abs(z.mean(axis=1)))),
            "expectedZNorm": math.sqrt(WIDTH),
            "maximumAbsoluteZNormError": float(
                np.max(np.abs(np.linalg.norm(z, axis=1) - math.sqrt(WIDTH)))
            ),
        },
        "faceRecords": face_records,
        "fontBytes": sum(path.stat().st_size for path in font_paths),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
        "fixtureSelection": {
            "states": selected_states,
            "count": len(selected_states),
            "source": "lowest 32 raw production-coordinate q16 margins union six production route fixtures",
            "lowest32MarginStates": lowest_margin_states.astype(int).tolist(),
            "productionRouteStates": production_states.astype(int).tolist(),
            "q16MarginAtMost2BucketStates": at_most_two.astype(int).tolist(),
            "q16MarginAtMost1BucketStates": at_most_one.astype(int).tolist(),
            "q16MarginAtMost2BucketCount": len(at_most_two),
            "q16MarginAtMost1BucketCount": len(at_most_one),
            "lowest32MaximumMarginBuckets": float(
                corpus_q16_margin_buckets[lowest_margin_states[-1]]
            ),
        },
        "fixtures": fixtures,
        "build": {
            "seconds": time.monotonic() - started,
            "freeDiskBytesBefore": free_before,
            "freeDiskBytesAfter": shutil.disk_usage(OUTPUT).free,
            "retainedFullTtfFiles": 0,
        },
        "generatedFiles": {
            "html": "index.html",
            "css": "index.css",
            "fonts": [path.name for path in font_paths],
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key != "fixtures"}, indent=2))


if __name__ == "__main__":
    main()
