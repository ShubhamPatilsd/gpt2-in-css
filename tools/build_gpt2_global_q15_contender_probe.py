#!/usr/bin/env python3
"""Build a production-range contender probe for global q15 versus q16."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-global-q15-contender"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
PRODUCTION = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
CALIBRATION = ROOT / "experiments" / "gpt2-q15-decision-calibration" / "results.json"
VOCABULARY = 50_257
WIDTH = 768
AXIS_STEPS = 16_384
Q15_MAXIMUM = 16_383
Q16_MAXIMUM = 32_767
SHARD = 256
SHARDS = WIDTH // SHARD
RADIX = 128
DISPLAY_SCALES = {
    "q15-s10": 0.1,
    "q15-s16": 1 / 16,
    "q15-s32": 1 / 32,
}
SAFETY = 32
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
TOP_FLOAT_CONTENDERS = 16
LOW_MARGIN_STATES = 8
STATE_519 = 519
CODEPOINT_STARTS = tuple(0x50000 + face * 0x10000 for face in range(2 * SHARDS))


def run_artifact_names() -> list[str]:
    names = ["reference.json", "results.json", "RESULTS.md", "index.html", "index.css"]
    names.extend(
        f"q15-{plane}{shard}.{suffix}"
        for shard in range(SHARDS)
        for plane in ("h", "l")
        for suffix in ("ttf", "woff2")
    )
    return names


def preserve_artifacts(prefix: str) -> list[str]:
    preserved = []
    for name in run_artifact_names():
        source = OUTPUT / name
        destination = OUTPUT / f"{prefix}-{name}"
        if source.exists() and not destination.exists():
            shutil.copy2(source, destination)
        if destination.exists():
            preserved.append(destination.name)
    return preserved


def preserve_nearest_artifacts() -> list[str]:
    """Keep the completed nearest-q15 run before replacing its live q15 fonts."""
    return preserve_artifacts("nearest")


def preserve_single_move_artifacts() -> list[str]:
    """Keep the completed first-calibration run before adding the production move."""
    existing = [
        f"single-move-{name}"
        for name in run_artifact_names()
        if (OUTPUT / f"single-move-{name}").exists()
    ]
    if existing:
        return existing
    reference_path = OUTPUT / "reference.json"
    if not reference_path.exists():
        return []
    reference = json.loads(reference_path.read_text())
    q15 = reference.get("q15", {})
    calibration = q15.get("calibration", {})
    if calibration.get("token") != 15 or "calibrations" in q15:
        return []
    return preserve_artifacts("single-move")


def preserve_two_move_scale_01_artifacts() -> list[str]:
    """Keep the two-move 0.1-only Chrome run before adding scale variants."""
    existing = [
        f"two-move-s10-{name}"
        for name in run_artifact_names()
        if (OUTPUT / f"two-move-s10-{name}").exists()
    ]
    if existing:
        return existing
    reference_path = OUTPUT / "reference.json"
    if not reference_path.exists():
        return []
    reference = json.loads(reference_path.read_text())
    q15 = reference.get("q15", {})
    if len(q15.get("calibrations", [])) != 2 or "displayScales" in q15:
        return []
    return preserve_artifacts("two-move-s10")


def css_number(value: float) -> str:
    return head.css_number(float(value))


def font_settings(production_range: float) -> str:
    return ",".join(
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{css_number(production_range)})"
        for dimension in range(WIDTH)
    )


def quantized(weights: np.ndarray, maximum: int) -> tuple[float, np.ndarray, np.ndarray]:
    scale = float(np.max(np.abs(weights)) / maximum)
    codes = np.rint(weights / scale).clip(-maximum, maximum).astype(np.int16)
    return scale, codes, codes.astype(np.float64) * scale


def build_q15_fonts(codes: np.ndarray) -> tuple[np.ndarray, list[dict[str, object]]]:
    equivalent_bases: list[np.ndarray] = []
    reports: list[dict[str, object]] = []
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        stop = start + SHARD
        values = codes[:, start:stop].astype(np.int32)
        high = np.trunc(values / RADIX).astype(np.int16)
        residual = (values - high.astype(np.int32) * RADIX).astype(np.int16)
        if not np.array_equal(
            high.astype(np.int32) * RADIX + residual.astype(np.int32), values
        ):
            raise RuntimeError(f"q15 shard {shard} radix split is not exact")
        plane_bases = []
        for plane, (letter, plane_values) in enumerate((("h", high), ("l", residual))):
            l1 = np.sum(np.abs(plane_values.astype(np.int64)), axis=1)
            bases = (l1 + SAFETY).astype(np.int32)
            if int(np.max(bases + l1)) > 65_535:
                raise RuntimeError(f"q15 shard {shard} plane {plane} exceeds uint16")
            destination = OUTPUT / f"q15-{letter}{shard}.ttf"
            build_direct_font_backend(
                plane_values,
                destination,
                signed_axes=True,
                base_advance=bases,
                codepoint_start=CODEPOINT_STARTS[2 * shard + plane],
                axis_tags=[global_axis_tag(dimension) for dimension in range(start, stop)],
            )
            font = destination.with_suffix(".woff2")
            reports.append(
                {
                    "shard": shard,
                    "plane": "high" if plane == 0 else "residual",
                    "dimensions": [start, stop],
                    "rows": len(codes),
                    "codeAbsoluteMaximum": int(np.max(np.abs(plane_values))),
                    "maximumL1": int(l1.max()),
                    "maximumBaseAdvance": int(bases.max()),
                    "maximumShapedAdvance": int(np.max(bases + l1)),
                    "woff2Bytes": font.stat().st_size,
                }
            )
            plane_bases.append(bases.astype(np.int64))
        equivalent_bases.append(plane_bases[0] * RADIX + plane_bases[1])
    return np.sum(np.stack(equivalent_bases), axis=0), reports


def render_html(
    contenders: list[int],
    q15_bases: np.ndarray,
    q15_factor_numerator: float,
    q16_records: list[tuple[str, str, str, str]],
) -> str:
    count = len(contenders)
    q15_sections = []
    for mode, display_scale in DISPLAY_SCALES.items():
        rows = []
        for index, token in enumerate(contenders):
            tie = count - 1 - index
            glyphs = "".join(chr(codepoint + index) for codepoint in CODEPOINT_STARTS)
            rows.append(
                f'<i id="{mode}-row-{index}" class="candidate q15-candidate {mode}-candidate" '
                f'data-token="{token}" style="--base:'
                f'{css_number(q15_bases[index] * display_scale)};'
                f'--factor:{css_number(q15_factor_numerator / display_scale)};'
                f'--tie:{tie}">{glyphs}</i>'
            )
        q15_sections.append(
            f'<section id="{mode}-stage" class="stage {mode}-stage" '
            f'style="--font-size:{css_number(display_scale * 1000)}px;'
            f'anchor-name:--{mode}-winner">{"".join(rows)}</section>'
            f'<span class="reader {mode}-reader"><output id="{mode}-result"></output></span>'
        )
    q16_rows = []
    for index, token in enumerate(contenders):
        tie = count - 1 - index
        base, factor, _source_tie, glyphs = q16_records[token]
        q16_rows.append(
            f'<i id="q16-row-{index}" class="candidate q16-candidate" data-token="{token}" '
            f'style="--base:{base};--factor:{factor};--tie:{tie}">{glyphs}</i>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2 global q15 contender probe</title>
<link rel="stylesheet" href="index.css">
<body class="mode-both" data-contenders="{count}">
<main id="probe" class="probe">
  {"".join(q15_sections)}
  <section id="q16-stage" class="stage q16-stage" style="--font-size:100px;anchor-name:--q16-winner">{"".join(q16_rows)}</section>
  <span class="reader q16-reader"><output id="q16-result"></output></span>
</main>
"""


def render_css(production_range: float, contender_count: int) -> str:
    q15_faces = "".join(
        f'@font-face{{font-family:Q15{plane.upper()}{shard};src:url("q15-{plane}{shard}.woff2") '
        f'format("woff2"){f";size-adjust:{RADIX * 100}%" if plane == "h" else ""}}}'
        for shard in range(SHARDS)
        for plane in ("h", "l")
    )
    q16_faces = "".join(
        f'@font-face{{font-family:Q16{plane.upper()}{shard};src:url("../gpt2-hvar-grid-output-head-global16-twoplane/'
        f'score-{plane}{shard}.woff2") format("woff2")'
        f'{";size-adjust:25600%" if plane == "h" else ""}}}'
        for shard in range(6)
        for plane in ("h", "l")
    )
    q15_families = ",".join(
        f"Q15{plane.upper()}{shard}" for shard in range(SHARDS) for plane in ("h", "l")
    )
    q16_families = ",".join(
        f"Q16{plane.upper()}{shard}" for shard in range(6) for plane in ("h", "l")
    )
    settings = font_settings(production_range)
    modes = [*DISPLAY_SCALES, "q16"]
    registrations = "".join(
        f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for mode in modes
        for name in (f"{mode}-bucket", f"{mode}-index")
    )
    stage_positions = "".join(
        f".{mode}-stage{{top:{-90000 + index * 1000}px}}"
        for index, mode in enumerate(modes)
    )
    readers = "".join(
        f".{mode}-reader{{position-anchor:--{mode}-winner;"
        f"top:{-89500 + index * 1000}px;width:anchor-size(--{mode}-winner width);"
        f"container:{mode}-result/inline-size}}"
        for index, mode in enumerate(modes)
    )
    containers = "".join(
        f"@container {mode}-result (width >= 0px){{#{mode}-result{{"
        f"--{mode}-bucket:round(down,100cqi/4px,1);"
        f"--{mode}-index:calc({contender_count - 1} - "
        "round(nearest,mod(100cqi,4px)/1px*64,1));"
        "display:block;width:1px;height:1px}}"
        for mode in modes
    )
    mode_visibility = "".join(
        f"body.mode-{mode} .stage:not(.{mode}-stage),"
        f"body.mode-{mode} .reader:not(.{mode}-reader){{display:none}}"
        for mode in modes
    )
    return "\n".join(
        (
            q15_faces + q16_faces,
            registrations,
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".probe{--score-offset:0px}",
            ".stage{position:fixed;left:0;display:grid;grid-template-columns:max-content;"
            "grid-template-rows:1px;width:max-content;height:1px}",
            stage_positions,
            ".candidate{display:block;grid-area:1/1;justify-self:start;height:1px;overflow:hidden;"
            "white-space:pre;font-style:normal;font-size:var(--font-size);line-height:1;font-kerning:none;"
            f"font-variation-settings:{settings};"
            "width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px) * var(--factor) + "
            "var(--score-offset),4px) + var(--tie)/64*1px))}",
            f".q15-candidate{{font-family:{q15_families}}}",
            f".q16-candidate{{font-family:{q16_families}}}",
            ".reader{position:fixed;left:0;height:1px}",
            readers,
            containers,
            mode_visibility,
        )
    ) + "\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    preserved_nearest_artifacts = preserve_nearest_artifacts()
    preserved_single_move_artifacts = preserve_single_move_artifacts()
    preserved_two_move_scale_01_artifacts = preserve_two_move_scale_01_artifacts()
    states = np.load(STATES)
    hidden = np.asarray(states["hidden"], dtype=np.float64)
    production_reference = json.loads((PRODUCTION / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    production_range = float(production_reference["productionInputRange"])
    source_range = float(production_reference["sourceInputRange"])
    score_gain = float(production_reference["scoreGain"])
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY], dtype=np.float64
    )
    calibration_reference = json.loads(CALIBRATION.read_text())
    calibrations = [
        calibration_reference["selectedCalibration"],
        calibration_reference["productionBucketCalibration"]["selectedCalibration"],
    ]
    q15_scale, q15_nearest_codes, q15_nearest_weights = quantized(weights, Q15_MAXIMUM)
    q15_calibrated_codes = q15_nearest_codes.copy()
    for calibration in calibrations:
        token = int(calibration["token"])
        dimension = int(calibration["dimension"])
        old_code = int(calibration["oldCode"])
        new_code = int(calibration["newCode"])
        if int(q15_calibrated_codes[token, dimension]) != old_code:
            raise RuntimeError(
                f"q15 calibration old code does not match token {token} dimension {dimension}"
            )
        q15_calibrated_codes[token, dimension] = new_code
    q15_calibrated_weights = q15_calibrated_codes.astype(np.float64) * q15_scale
    q16_scale, _q16_codes, q16_weights = quantized(weights, Q16_MAXIMUM)
    if abs(q16_scale - float(fine_reference["weightScale"])) > 1e-15:
        raise RuntimeError("recomputed q16 scale differs from retained font bank")

    float_winners = np.empty(len(hidden), dtype=np.int64)
    float_bucket_winners = np.empty(len(hidden), dtype=np.int64)
    q15_nearest_winners = np.empty(len(hidden), dtype=np.int64)
    q15_calibrated_winners = np.empty(len(hidden), dtype=np.int64)
    q16_winners = np.empty(len(hidden), dtype=np.int64)
    q15_nearest_bucket_winners = np.empty(len(hidden), dtype=np.int64)
    q15_calibrated_bucket_winners = np.empty(len(hidden), dtype=np.int64)
    q16_bucket_winners = np.empty(len(hidden), dtype=np.int64)
    float_margins = np.empty(len(hidden), dtype=np.float64)
    top_float = np.empty((len(hidden), TOP_FLOAT_CONTENDERS), dtype=np.int64)
    for start in range(0, len(hidden), 16):
        stop = min(start + 16, len(hidden))
        query = realized[start:stop]
        float_scores = query @ weights.T
        q15_nearest_scores = query @ q15_nearest_weights.T
        q15_calibrated_scores = query @ q15_calibrated_weights.T
        q16_scores = query @ q16_weights.T
        selected = np.argpartition(
            float_scores, -TOP_FLOAT_CONTENDERS, axis=1
        )[:, -TOP_FLOAT_CONTENDERS:]
        selected_scores = np.take_along_axis(float_scores, selected, axis=1)
        order = np.argsort(-selected_scores, axis=1, kind="stable")
        ordered = np.take_along_axis(selected, order, axis=1)
        ordered_scores = np.take_along_axis(float_scores, ordered, axis=1)
        top_float[start:stop] = ordered
        float_winners[start:stop] = ordered[:, 0]
        float_margins[start:stop] = ordered_scores[:, 0] - ordered_scores[:, 1]
        float_bucket_winners[start:stop] = np.argmax(
            np.rint(float_scores * score_gain * SCORE_SCALE).astype(np.int64), axis=1
        )
        q15_nearest_winners[start:stop] = np.argmax(q15_nearest_scores, axis=1)
        q15_calibrated_winners[start:stop] = np.argmax(q15_calibrated_scores, axis=1)
        q16_winners[start:stop] = np.argmax(q16_scores, axis=1)
        q15_nearest_bucket_winners[start:stop] = np.argmax(
            np.rint(q15_nearest_scores * score_gain * SCORE_SCALE).astype(np.int64), axis=1
        )
        q15_calibrated_bucket_winners[start:stop] = np.argmax(
            np.rint(q15_calibrated_scores * score_gain * SCORE_SCALE).astype(np.int64), axis=1
        )
        q16_bucket_winners[start:stop] = np.argmax(
            np.rint(q16_scores * score_gain * SCORE_SCALE).astype(np.int64), axis=1
        )

    q15_nearest_mismatch_states = np.flatnonzero(float_winners != q15_nearest_winners)
    q15_calibrated_mismatch_states = np.flatnonzero(float_winners != q15_calibrated_winners)
    q16_mismatch_states = np.flatnonzero(float_winners != q16_winners)
    if q15_nearest_mismatch_states.tolist() != [547]:
        raise RuntimeError(
            f"expected sole nearest q15 mismatch at 547, got {q15_nearest_mismatch_states.tolist()}"
        )
    if len(q15_calibrated_mismatch_states):
        raise RuntimeError(
            f"calibrated q15 mismatches: {q15_calibrated_mismatch_states.tolist()}"
        )
    if len(q16_mismatch_states):
        raise RuntimeError(f"mathematical q16 mismatches: {q16_mismatch_states.tolist()}")
    production_bucket_mismatch_states = np.flatnonzero(
        q15_calibrated_bucket_winners != q16_bucket_winners
    )
    if len(production_bucket_mismatch_states):
        raise RuntimeError(
            "production-calibrated q15 differs from q16 buckets: "
            f"{production_bucket_mismatch_states.tolist()}"
        )

    low_margin = np.argsort(float_margins, kind="stable")[:LOW_MARGIN_STATES]
    production_states = np.asarray(
        production_reference["certifiedFixtures"]["sourceStateIndices"], dtype=np.int64
    )
    selected_states: list[int] = []
    roles: dict[int, list[str]] = {}
    selections = (
        (STATE_519, "known-q16-browser-flip"),
        (int(q15_nearest_mismatch_states[0]), "sole-nearest-q15-mismatch"),
        *((int(state), "lowest-float-margin") for state in low_margin),
        *((int(state), "production-fixture") for state in production_states),
    )
    for state, role in selections:
        roles.setdefault(state, []).append(role)
        if state not in selected_states:
            selected_states.append(state)

    contender_set = set()
    for state in selected_states:
        contender_set.update(int(token) for token in top_float[state])
        contender_set.add(int(float_winners[state]))
        contender_set.add(int(q15_nearest_winners[state]))
        contender_set.add(int(q15_calibrated_winners[state]))
        contender_set.add(int(q16_winners[state]))
        contender_set.add(int(q15_nearest_bucket_winners[state]))
        contender_set.add(int(q15_calibrated_bucket_winners[state]))
        contender_set.add(int(q16_bucket_winners[state]))
    # Preserve the known browser alternate explicitly even if selection changes later.
    contender_set.add(2032)
    contenders = sorted(contender_set)
    if len(contenders) > 256:
        raise RuntimeError(f"{len(contenders)} contenders exceed four-pixel tie capacity")
    contender_index = {token: index for index, token in enumerate(contenders)}

    q15_bases, face_reports = build_q15_fonts(q15_calibrated_codes[contenders])
    q16_records = token_gate.records(FINE / "index.html")
    q15_factor_numerator = source_range * q15_scale * SCORE_SCALE * SCORE_STRIDE_PX
    (OUTPUT / "index.html").write_text(
        render_html(contenders, q15_bases, q15_factor_numerator, q16_records)
    )
    (OUTPUT / "index.css").write_text(render_css(production_range, len(contenders)))

    fixture_rows = []
    for state in selected_states:
        query = realized[state]
        float_scores = query @ weights[contenders].T * score_gain
        q15_nearest_scores = query @ q15_nearest_weights[contenders].T * score_gain
        q15_calibrated_scores = query @ q15_calibrated_weights[contenders].T * score_gain
        q16_scores = query @ q16_weights[contenders].T * score_gain
        score_floor = int(np.floor(min(
            float_scores.min(),
            q15_nearest_scores.min(),
            q15_calibrated_scores.min(),
            q16_scores.min(),
        )) - 2)
        q15_nearest_buckets = np.rint(
            (q15_nearest_scores - score_floor) * SCORE_SCALE
        ).astype(np.int64)
        q15_calibrated_buckets = np.rint(
            (q15_calibrated_scores - score_floor) * SCORE_SCALE
        ).astype(np.int64)
        q16_buckets = np.rint((q16_scores - score_floor) * SCORE_SCALE).astype(np.int64)
        q15_nearest_index = int(np.argmax(q15_nearest_buckets))
        q15_calibrated_index = int(np.argmax(q15_calibrated_buckets))
        q16_index = int(np.argmax(q16_buckets))
        top_tokens = top_float[state].astype(int).tolist()
        fixture_rows.append(
            {
                "state": state,
                "roles": roles[state],
                "hidden": hidden[state].tolist(),
                "realizedHidden": query.tolist(),
                "scoreFloor": score_floor,
                "floatWinner": int(float_winners[state]),
                "floatBucketWinner": int(float_bucket_winners[state]),
                "floatMargin": float(float_margins[state]),
                "q15NearestMathematicalWinner": int(q15_nearest_winners[state]),
                "q15CalibratedMathematicalWinner": int(q15_calibrated_winners[state]),
                "q16MathematicalWinner": int(q16_winners[state]),
                "q15NearestBucketWinner": contenders[q15_nearest_index],
                "q15CalibratedBucketWinner": contenders[q15_calibrated_index],
                "q16BucketWinner": contenders[q16_index],
                "q15NearestWinnerBucket": int(q15_nearest_buckets[q15_nearest_index]),
                "q15CalibratedWinnerBucket": int(
                    q15_calibrated_buckets[q15_calibrated_index]
                ),
                "q16WinnerBucket": int(q16_buckets[q16_index]),
                "topFloatContenders": top_tokens,
                "topFloatCoverage": sum(token in contender_index for token in top_tokens),
                "q15NearestBuckets": q15_nearest_buckets.tolist(),
                "q15CalibratedBuckets": q15_calibrated_buckets.tolist(),
                "q16Buckets": q16_buckets.tolist(),
            }
        )
    if any(row["topFloatCoverage"] != TOP_FLOAT_CONTENDERS for row in fixture_rows):
        raise RuntimeError("contender union lost a selected state's top-16 float token")
    if any(
        row["q15NearestBucketWinner"] != int(q15_nearest_bucket_winners[row["state"]])
        for row in fixture_rows
    ):
        raise RuntimeError("contender set lost a global nearest q15 bucket winner")
    if any(
        row["q15CalibratedBucketWinner"]
        != int(q15_calibrated_bucket_winners[row["state"]])
        for row in fixture_rows
    ):
        raise RuntimeError("contender set lost a global calibrated q15 bucket winner")
    if any(
        row["q16BucketWinner"] != int(q16_bucket_winners[row["state"]])
        for row in fixture_rows
    ):
        raise RuntimeError("contender set lost a global q16 bucket winner")

    reference = {
        "model": "openai-community/gpt2",
        "modelArchitectureChanged": False,
        "checkpointChanged": False,
        "sourceCheckpointWeightsChanged": False,
        "quantizedRepresentationCalibrated": True,
        "runtimeContainsJavaScript": False,
        "scope": "contender-only browser probe; no full q15 font bank",
        "productionCoordinates": {
            "inputRange": production_range,
            "axisSteps": AXIS_STEPS,
            "sourceInputRange": source_range,
            "homogeneousScoreGain": score_gain,
        },
        "corpusScreen": {
            "states": len(hidden),
            "floatBucketMismatchStates": np.flatnonzero(
                float_bucket_winners != float_winners
            ).astype(int).tolist(),
            "q15NearestMathematicalMismatchStates": (
                q15_nearest_mismatch_states.astype(int).tolist()
            ),
            "q15CalibratedMathematicalMismatchStates": (
                q15_calibrated_mismatch_states.astype(int).tolist()
            ),
            "q15NearestFloatBucketMismatchStates": np.flatnonzero(
                q15_nearest_bucket_winners != float_bucket_winners
            ).astype(int).tolist(),
            "q15CalibratedFloatBucketMismatchStates": np.flatnonzero(
                q15_calibrated_bucket_winners != float_bucket_winners
            ).astype(int).tolist(),
            "q15CalibratedQ16BucketMismatchStates": (
                production_bucket_mismatch_states.astype(int).tolist()
            ),
            "q16MathematicalMismatchStates": q16_mismatch_states.astype(int).tolist(),
            "lowestMarginStates": low_margin.astype(int).tolist(),
        },
        "selection": {
            "selectedStates": selected_states,
            "selectedStateCount": len(selected_states),
            "topFloatContendersPerState": TOP_FLOAT_CONTENDERS,
            "productionFixtureStates": production_states.astype(int).tolist(),
        },
        "contenders": contenders,
        "contenderCount": len(contenders),
        "coverage": {
            "topFloatSlotsRequested": len(selected_states) * TOP_FLOAT_CONTENDERS,
            "topFloatSlotsCovered": sum(row["topFloatCoverage"] for row in fixture_rows),
            "allFloatWinnersCovered": all(row["floatWinner"] in contender_index for row in fixture_rows),
            "allNearestQ15WinnersCovered": all(
                row["q15NearestMathematicalWinner"] in contender_index
                for row in fixture_rows
            ),
            "allCalibratedQ15WinnersCovered": all(
                row["q15CalibratedMathematicalWinner"] in contender_index
                for row in fixture_rows
            ),
            "allQ16WinnersCovered": all(row["q16MathematicalWinner"] in contender_index for row in fixture_rows),
        },
        "q15": {
            "bits": 15,
            "weightScale": q15_scale,
            "transport": "radix-128 high/residual, three 256-axis shards per plane",
            "radix": RADIX,
            "planes": 2,
            "shardsPerPlane": SHARDS,
            "glyphsPerRow": 2 * SHARDS,
            "displayScales": DISPLAY_SCALES,
            "fontRows": len(contenders),
            "liveRepresentation": "production-calibrated",
            "calibrationSource": str(CALIBRATION.relative_to(ROOT)),
            "calibrations": [
                {
                    "token": int(calibration["token"]),
                    "dimension": int(calibration["dimension"]),
                    "oldCode": int(calibration["oldCode"]),
                    "newCode": int(calibration["newCode"]),
                    "codeDelta": int(calibration["codeDelta"]),
                    "radix128Digits": calibration["radix128Digits"],
                }
                for calibration in calibrations
            ],
            "faces": face_reports,
            "woff2Bytes": sum(int(face["woff2Bytes"]) for face in face_reports),
        },
        "q16": {
            "bits": 16,
            "weightScale": q16_scale,
            "transport": "retained radix-256 high/residual, six 128-axis shards per plane",
            "glyphsPerRow": int(fine_reference["glyphsPerToken"]),
            "fontSource": "gpt2-hvar-grid-output-head-global16-twoplane",
        },
        "fixtures": fixture_rows,
        "preservedNearestArtifacts": preserved_nearest_artifacts,
        "preservedSingleMoveArtifacts": preserved_single_move_artifacts,
        "preservedTwoMoveScale01Artifacts": preserved_two_move_scale_01_artifacts,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key != "fixtures"}, indent=2))


if __name__ == "__main__":
    main()
