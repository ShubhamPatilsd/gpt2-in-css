#!/usr/bin/env python3
"""Build a contender-only display-lattice sweep for the retained global q16 bank."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-global-q16-lattice-scale"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
PRODUCTION = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
VOCABULARY = 50_257
WIDTH = 768
AXIS_STEPS = 16_384
Q16_MAXIMUM = 32_767
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
TOP_CONTENDERS = 16
LOW_MARGIN_STATES = 8
STATE_519 = 519
STATE_547 = 547
CHROME_ADVANCE_CEILING_PX = 32_768
SCALES = (
    ("0p1", 0.1, "0.1"),
    ("1over16", 1 / 16, "1/16"),
    ("1over32", 1 / 32, "1/32"),
    ("1over64", 1 / 64, "1/64"),
)


def css_number(value: float) -> str:
    return head.css_number(float(value))


def font_settings(production_range: float) -> str:
    return ",".join(
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{css_number(production_range)})"
        for dimension in range(WIDTH)
    )


def top_k(scores: np.ndarray, count: int) -> np.ndarray:
    selected = np.argpartition(scores, -count, axis=1)[:, -count:]
    selected_scores = np.take_along_axis(scores, selected, axis=1)
    order = np.argsort(-selected_scores, axis=1, kind="stable")
    return np.take_along_axis(selected, order, axis=1)


def render_html(
    slug: str,
    label: str,
    display_scale: float,
    contenders: list[int],
    base_units: list[int],
    glyphs: list[str],
    factor: float,
) -> str:
    rows = []
    count = len(contenders)
    for index, (token, base, characters) in enumerate(
        zip(contenders, base_units, glyphs, strict=True)
    ):
        tie = count - 1 - index
        rows.append(
            f'<i id="row-{index}" class="candidate" data-token="{token}" '
            f'style="--base:{css_number(base * display_scale)};'
            f'--factor:{css_number(factor)};--tie:{tie}">{characters}</i>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none'">
<title>GPT-2 global q16 lattice scale {label}</title>
<link rel="stylesheet" href="index.css">
<body data-scale="{slug}" data-contenders="{count}">
<main id="probe" class="probe">
  <section id="stage" class="stage" style="--font-size:{css_number(display_scale * 1000)}px;anchor-name:--winner">{"".join(rows)}</section>
  <span id="reader" class="reader"><output id="result"></output></span>
</main>
"""


def render_css(production_range: float, contender_count: int) -> str:
    faces = "".join(
        f'@font-face{{font-family:Q16{plane.upper()}{shard};'
        f'src:url("../gpt2-hvar-grid-output-head-global16-twoplane/'
        f'score-{plane}{shard}.woff2") format("woff2")'
        f'{";size-adjust:25600%" if plane == "h" else ""}}}'
        for shard in range(6)
        for plane in ("h", "l")
    )
    families = ",".join(
        f"Q16{plane.upper()}{shard}"
        for shard in range(6)
        for plane in ("h", "l")
    )
    settings = font_settings(production_range)
    return "\n".join(
        (
            faces,
            '@property --bucket{syntax:"<number>";inherits:true;initial-value:0}'
            '@property --index{syntax:"<number>";inherits:true;initial-value:0}',
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}"
            "body{anchor-scope:all}",
            ".probe{--score-offset:0px}",
            ".stage{position:fixed;left:0;top:-90000px;display:grid;"
            "grid-template-columns:max-content;grid-template-rows:1px;"
            "width:max-content;height:1px;"
            f"font-family:{families};font-size:var(--font-size);line-height:1;"
            f"font-variation-settings:{settings};font-kerning:none;font-synthesis:none}}",
            ".candidate{display:block;grid-area:1/1;justify-self:start;height:1px;"
            "overflow:hidden;white-space:pre;font-style:normal;"
            "width:calc-size(max-content,calc(round(nearest,"
            "(size - var(--base)*1px)*var(--factor) + var(--score-offset),4px) "
            "+ var(--tie)/64*1px))}",
            ".reader{position:fixed;position-anchor:--winner;left:0;top:-89000px;"
            "width:anchor-size(--winner width);height:1px;container:result/inline-size}",
            "@container result (width >= 0px){#result{"
            "--bucket:round(down,100cqi/4px,1);"
            f"--index:calc({contender_count - 1} - "
            "round(nearest,mod(100cqi,4px)/1px*64,1));"
            "display:block;width:1px;height:1px}}",
        )
    ) + "\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state_data = np.load(STATES)
    hidden = np.asarray(state_data["hidden"], dtype=np.float64)
    production_reference = json.loads((PRODUCTION / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    production_range = float(production_reference["productionInputRange"])
    source_range = float(production_reference["sourceInputRange"])
    score_gain = float(production_reference["scoreGain"])
    source_display_scale = float(fine_reference["displayScale"])
    if source_display_scale != 0.1:
        raise RuntimeError("retained q16 source display scale changed")
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY], dtype=np.float64
    )
    q16_scale = float(np.max(np.abs(weights)) / Q16_MAXIMUM)
    if abs(q16_scale - float(fine_reference["weightScale"])) > 1e-15:
        raise RuntimeError("recomputed q16 scale differs from retained font bank")
    q16_codes = np.rint(weights / q16_scale).clip(
        -Q16_MAXIMUM, Q16_MAXIMUM
    ).astype(np.int16)
    q16_weights = q16_codes.astype(np.float64) * q16_scale

    float_winners = np.empty(len(hidden), dtype=np.int64)
    q16_winners = np.empty(len(hidden), dtype=np.int64)
    float_margins = np.empty(len(hidden), dtype=np.float64)
    top_float = np.empty((len(hidden), TOP_CONTENDERS), dtype=np.int64)
    top_q16 = np.empty((len(hidden), TOP_CONTENDERS), dtype=np.int64)
    for start in range(0, len(hidden), 16):
        stop = min(start + 16, len(hidden))
        query = realized[start:stop]
        float_scores = query @ weights.T
        q16_scores = query @ q16_weights.T
        ordered_float = top_k(float_scores, TOP_CONTENDERS)
        ordered_q16 = top_k(q16_scores, TOP_CONTENDERS)
        ordered_float_scores = np.take_along_axis(
            float_scores, ordered_float, axis=1
        )
        top_float[start:stop] = ordered_float
        top_q16[start:stop] = ordered_q16
        float_winners[start:stop] = ordered_float[:, 0]
        q16_winners[start:stop] = ordered_q16[:, 0]
        float_margins[start:stop] = (
            ordered_float_scores[:, 0] - ordered_float_scores[:, 1]
        )

    q16_mismatch_states = np.flatnonzero(float_winners != q16_winners)
    low_margin = np.argsort(float_margins, kind="stable")[:LOW_MARGIN_STATES]
    production_states = np.asarray(
        production_reference["certifiedFixtures"]["sourceStateIndices"],
        dtype=np.int64,
    )
    selected_states: list[int] = []
    roles: dict[int, list[str]] = {}
    selections = (
        (STATE_519, "known-q16-browser-flip"),
        (STATE_547, "known-q15-mathematical-flip"),
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
    if len(contenders) > 256:
        raise RuntimeError(
            f"{len(contenders)} contenders exceed the four-pixel tie channel"
        )
    contender_index = {token: index for index, token in enumerate(contenders)}

    source_records = token_gate.records(FINE / "index.html")
    base_units: list[int] = []
    glyphs: list[str] = []
    source_factors = set()
    for token in contenders:
        base, factor, _tie, characters = source_records[token]
        units = round(float(base) / source_display_scale)
        if abs(units * source_display_scale - float(base)) > 1e-7:
            raise RuntimeError(f"token {token} source base does not recover integral units")
        base_units.append(units)
        glyphs.append(characters)
        source_factors.add(factor)
    if len(source_factors) != 1:
        raise RuntimeError("retained q16 rows do not share one score factor")

    scale_rows = []
    for slug, display_scale, label in SCALES:
        factor = (
            source_range
            * q16_scale
            * SCORE_SCALE
            * SCORE_STRIDE_PX
            / display_scale
        )
        filename = f"scale-{slug}.html"
        (OUTPUT / filename).write_text(
            render_html(
                slug,
                label,
                display_scale,
                contenders,
                base_units,
                glyphs,
                factor,
            )
        )
        high_maximum = max(
            int(face["maximumAdvance"])
            for face in fine_reference["faceRanges"]
            if int(face["plane"]) == 0
        )
        low_maximum = max(
            int(face["maximumAdvance"])
            for face in fine_reference["faceRanges"]
            if int(face["plane"]) == 1
        )
        theoretical_high = high_maximum * display_scale * 256
        theoretical_low = low_maximum * display_scale
        scale_rows.append(
            {
                "slug": slug,
                "label": label,
                "html": filename,
                "displayScale": display_scale,
                "fontSizePx": display_scale * 1000,
                "lowPlaneUnitPx": display_scale,
                "lowPlaneUnitLayout64": display_scale * 64,
                "highPlaneUnitPx": display_scale * 256,
                "highPlaneUnitLayout64": display_scale * 256 * 64,
                "serializedBaseMinimumPx": min(base_units) * display_scale,
                "serializedBaseMaximumPx": max(base_units) * display_scale,
                "scoreFactor": factor,
                "theoreticalMaximumHighAdvancePx": theoretical_high,
                "theoreticalMaximumResidualAdvancePx": theoretical_low,
                "theoreticalMaximumAdjustedAdvancePx": max(
                    theoretical_high, theoretical_low
                ),
                "theoreticallyClearsChromeAdvanceCeiling": max(
                    theoretical_high, theoretical_low
                )
                < CHROME_ADVANCE_CEILING_PX,
            }
        )

    (OUTPUT / "index.css").write_text(
        render_css(production_range, len(contenders))
    )

    fixture_rows = []
    for state in selected_states:
        query = realized[state]
        float_scores = query @ weights[contenders].T * score_gain
        q16_scores = query @ q16_weights[contenders].T * score_gain
        score_floor = int(np.floor(min(float_scores.min(), q16_scores.min())) - 2)
        float_buckets = np.rint(
            (float_scores - score_floor) * SCORE_SCALE
        ).astype(np.int64)
        q16_buckets = np.rint(
            (q16_scores - score_floor) * SCORE_SCALE
        ).astype(np.int64)
        float_bucket_index = int(np.argmax(float_buckets))
        q16_bucket_index = int(np.argmax(q16_buckets))
        fixture_rows.append(
            {
                "state": state,
                "roles": roles[state],
                "hidden": hidden[state].tolist(),
                "realizedHidden": query.tolist(),
                "scoreFloor": score_floor,
                "floatWinner": int(float_winners[state]),
                "q16MathematicalWinner": int(q16_winners[state]),
                "floatMargin": float(float_margins[state]),
                "floatBucketWinner": contenders[float_bucket_index],
                "q16BucketWinner": contenders[q16_bucket_index],
                "floatWinnerBucket": int(float_buckets[float_bucket_index]),
                "q16WinnerBucket": int(q16_buckets[q16_bucket_index]),
                "topFloatContenders": top_float[state].astype(int).tolist(),
                "topQ16Contenders": top_q16[state].astype(int).tolist(),
                "floatBuckets": float_buckets.tolist(),
                "q16Buckets": q16_buckets.tolist(),
            }
        )

    for fixture in fixture_rows:
        if not all(
            token in contender_index
            for token in fixture["topFloatContenders"] + fixture["topQ16Contenders"]
        ):
            raise RuntimeError("contender union lost a requested top-16 token")

    font_files = [
        FINE / f"score-{plane}{shard}.woff2"
        for shard in range(6)
        for plane in ("h", "l")
    ]
    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "runtimeContainsJavaScript": False,
        "scope": "contender-only scale probe reusing the retained global q16 font bank",
        "productionCoordinates": {
            "inputRange": production_range,
            "axisSteps": AXIS_STEPS,
            "sourceInputRange": source_range,
            "homogeneousScoreGain": score_gain,
        },
        "q16": {
            "bits": 16,
            "weightScale": q16_scale,
            "radix": 256,
            "planes": 2,
            "shardsPerPlane": 6,
            "glyphsPerRow": int(fine_reference["glyphsPerToken"]),
            "sourceDisplayScale": source_display_scale,
            "fontSource": "gpt2-hvar-grid-output-head-global16-twoplane",
            "reusedWoff2Bytes": sum(path.stat().st_size for path in font_files),
            "newFontBankBuilt": False,
        },
        "chromeAdvanceCeilingPx": CHROME_ADVANCE_CEILING_PX,
        "corpusScreen": {
            "states": len(hidden),
            "q16MathematicalMismatchStates": q16_mismatch_states.astype(int).tolist(),
            "lowestMarginStates": low_margin.astype(int).tolist(),
        },
        "selection": {
            "selectedStates": selected_states,
            "selectedStateCount": len(selected_states),
            "productionFixtureStates": production_states.astype(int).tolist(),
            "topFloatContendersPerState": TOP_CONTENDERS,
            "topQ16ContendersPerState": TOP_CONTENDERS,
            "explicitAlternateToken": 2032,
        },
        "contenders": contenders,
        "contenderCount": len(contenders),
        "coverage": {
            "topFloatSlotsRequested": len(selected_states) * TOP_CONTENDERS,
            "topQ16SlotsRequested": len(selected_states) * TOP_CONTENDERS,
            "topFloatSlotsCovered": sum(
                len(fixture["topFloatContenders"]) for fixture in fixture_rows
            ),
            "topQ16SlotsCovered": sum(
                len(fixture["topQ16Contenders"]) for fixture in fixture_rows
            ),
            "token2032Covered": 2032 in contender_index,
        },
        "scales": scale_rows,
        "fixtures": fixture_rows,
        "generatedFiles": {
            "css": "index.css",
            "html": [row["html"] for row in scale_rows],
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in reference.items() if key != "fixtures"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
