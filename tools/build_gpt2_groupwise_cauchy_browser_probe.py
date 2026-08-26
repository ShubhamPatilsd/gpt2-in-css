#!/usr/bin/env python3
"""Build script-free group-level 96-block Cauchy browser scaling probes."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
CONTROL_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10"
CONTROL = ROOT / "experiments" / CONTROL_NAME
BLOCK_COUNT = 96
BLOCK_WIDTH = 8
BOUND_CODEPOINT_START = 0xA8000
BOUND_AXIS_PAD = 1.0 / 16_384.0
BOUND_QUANTIZATION = 128
SCALING_GROUP_COUNTS = (1, 4, 16, 64, 197)


def bound_tag(index: int) -> str:
    return f"b{index:03d}"


def css_number(value: float) -> str:
    return head.css_number(float(value))


def extract_groups(document: str) -> list[str]:
    return re.findall(
        r'<section class="group-wrapper"[^>]*>.*?</section>',
        document,
        flags=re.DOTALL,
    )


def fixture_style(hidden: np.ndarray, score_floor: int) -> str:
    declarations = [
        f"--h{dimension}:{css_number(value)}"
        for dimension, value in enumerate(hidden)
    ]
    declarations.append(
        f"--score-offset:{-int(score_floor) * head.SCORE_SCALE * head.SCORE_STRIDE_PX}px"
    )
    return ";".join(declarations)


def score_faces() -> str:
    return "".join(
        f'@font-face{{font-family:Score{part};src:url("../../gpt2-hvar-grid-output-head/'
        f'score-d{part}.woff2") format("woff2")}}'
        for part in range(5)
    )


def shared_css(input_range: float) -> tuple[str, str, str]:
    settings = ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f'calc(var(--h{dimension})/{css_number(input_range)})'
        for dimension in range(head.WIDTH)
    )
    query_norm = " + ".join(
        f"var(--h{dimension}) * var(--h{dimension})"
        for dimension in range(head.WIDTH)
    )
    shared = (
        "*{box-sizing:border-box}html,body{margin:0;width:1px;height:1px;overflow:hidden}"
        ".model{position:fixed;left:0;top:-90000px;font-size:1000px;line-height:1}"
        ".compute-values,.score-stage{display:contents}"
        ".groups{display:block;width:max-content;height:1px}"
        ".group-wrapper{display:block;width:calc-size(max-content,round(down,size,4px));height:1px}"
        ".group-grid{display:grid;grid-template-columns:max-content;grid-template-rows:1px;"
        "width:max-content;height:1px}"
        ".candidate{grid-area:1/1;display:block;justify-self:start;height:1px;overflow:hidden;"
        "white-space:pre;font-style:normal}"
    )
    score_stage = (
        ".score-stage{font-family:Score0,Score1,Score2,Score3,Score4;"
        f"font-variation-settings:{settings}}}"
    )
    return shared, score_stage, query_norm


def build_css(
    input_range: float,
    block_axis_range: float,
    bound_pixel_scale: float,
) -> tuple[str, str]:
    shared, score_stage, query_norm = shared_css(input_range)
    control = (
        score_faces()
        + '@property --query-norm{syntax:"<number>";inherits:true;initial-value:0}'
        + shared
        + f".compute-values{{--query-norm:sqrt(calc({query_norm}))}}"
        + score_stage
        + ".candidate{width:calc-size(max-content,calc(round(down,"
        + "(size - var(--base)*1px)*var(--factor) + var(--score-offset)"
        + "+ var(--query-norm)*var(--bound-factor)*1px + 4px,4px)"
        + "+ var(--local-tie)/64*1px))}"
    )

    block_rules = []
    bound_settings = []
    for block in range(BLOCK_COUNT):
        start = block * BLOCK_WIDTH
        terms = " + ".join(
            f"var(--h{dimension}) * var(--h{dimension})"
            for dimension in range(start, start + BLOCK_WIDTH)
        )
        block_rules.append(f"--bn{block}:sqrt(calc({terms}))")
        bound_settings.append(
            f'"{bound_tag(block)}" calc(min(1,var(--bn{block})/'
            f"{css_number(block_axis_range)} + {css_number(BOUND_AXIS_PAD)}))"
        )
    registrations = "".join(
        f'@property --bn{block}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for block in range(BLOCK_COUNT)
    )
    groupwise = (
        score_faces()
        + registrations
        + '@font-face{font-family:GroupBound96;src:url("../group-bound-96.woff2") format("woff2");'
        + f"size-adjust:{css_number(bound_pixel_scale * 100)}%}}"
        + shared
        + ".group-wrapper{display:grid;grid-template-columns:max-content max-content}"
        + ".compute-values{" + ";".join(block_rules) + "}"
        + score_stage
        + ".candidate{width:calc-size(max-content,calc(round(down,"
        + "(size - var(--base)*1px)*var(--factor) + var(--score-offset) + 4px,4px)"
        + "+ var(--local-tie)/64*1px))}"
        + ".group-bound{display:block;grid-column:2;height:1px;overflow:hidden;white-space:pre;"
        + "font-family:GroupBound96;font-style:normal;"
        + "font-variation-settings:" + ",".join(bound_settings) + ";"
        + "width:calc-size(max-content,round(down,size + 4px,4px))}"
    )
    return control, groupwise


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    offline = json.loads((OUTPUT / "offline-results.json").read_text())
    if not offline["browserGate"]["plausible"]:
        raise RuntimeError("offline pruning gate rejected browser generation")
    control_reference = json.loads((CONTROL / "reference.json").read_text())
    control_html = (CONTROL / "index.html").read_text()
    groups = extract_groups(control_html)
    if len(groups) != offline["groups"]:
        raise RuntimeError("control vocabulary group count changed")

    group_norms = np.load(OUTPUT / "group-residual-norms-96.npy")
    if group_norms.shape != (offline["groups"], BLOCK_COUNT):
        raise RuntimeError(f"unexpected group norm matrix {group_norms.shape}")
    input_range = float(control_reference["inputRange"])
    block_axis_range = math.sqrt(BLOCK_WIDTH) * input_range
    output_scale = head.SCORE_SCALE * head.SCORE_STRIDE_PX
    bound_pixel_scale = output_scale / BOUND_QUANTIZATION
    # At a 1000px font size and 1000 UPEM, one HVAR unit is one CSS px.
    # Axis coordinates are bn/block_axis_range plus a positive F2DOT14 pad;
    # ceil therefore makes every font delta an outward radius in score pixels.
    coefficients = np.ceil(
        group_norms * block_axis_range * BOUND_QUANTIZATION
    ).astype(np.int16)
    if np.any(coefficients < 0) or int(coefficients.max()) > 32_767:
        raise RuntimeError("group bound coefficients do not fit int16")
    bound_bases = np.sum(coefficients.astype(np.int64), axis=1)
    if int(bound_bases.max()) > 65_535:
        raise RuntimeError("group bound base advance does not fit uint16")
    build_direct_font_backend(
        coefficients,
        OUTPUT / "group-bound-96.ttf",
        signed_axes=False,
        base_advance=bound_bases,
        codepoint_start=BOUND_CODEPOINT_START,
        axis_tags=[bound_tag(index) for index in range(BLOCK_COUNT)],
        allow_out_of_range_result=True,
    )
    # The helper's conservative base-advance contract covers signed matrices,
    # but this font has only non-negative axes and deltas. Keeping that base and
    # applying 800% size-adjust exceeds Chrome's 32,768px shaped-advance clamp.
    # Zero hmtx advances make the glyph width equal to the positive HVAR radius
    # directly; every possible varied advance remains non-negative.
    font_path = OUTPUT / "group-bound-96.ttf"
    bound_font = TTFont(font_path, recalcTimestamp=False)
    for glyph, (_advance, lsb) in bound_font["hmtx"].metrics.items():
        bound_font["hmtx"].metrics[glyph] = (0, lsb)
    bound_font["hhea"].advanceWidthMax = 0
    bound_font.recalcTimestamp = False
    bound_font.save(font_path)
    compressed_font = TTFont(font_path, recalcTimestamp=False)
    compressed_font.flavor = "woff2"
    compressed_font.save(font_path.with_suffix(".woff2"))

    candidate_groups: list[str] = []
    for group, markup in enumerate(groups):
        markup = re.sub(r"--bound-factor:[^;]+;", "", markup)
        bound = (
            '<i class="group-bound">'
            f"&#x{BOUND_CODEPOINT_START + group:X};</i>"
        )
        if markup.count("</section>") != 1:
            raise RuntimeError(f"group {group} does not have one section close")
        candidate_groups.append(markup.replace("</section>", bound + "</section>"))

    scaling = OUTPUT / "scaling"
    scaling.mkdir(parents=True, exist_ok=True)
    control_css, groupwise_css = build_css(
        input_range, block_axis_range, bound_pixel_scale
    )
    (scaling / "control.css").write_text(control_css)
    (scaling / "groupwise.css").write_text(groupwise_css)

    fixtures = control_reference["allFixtures"]
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.int64)
    query_norms = np.linalg.norm(hidden, axis=1)
    norm_order = np.argsort(query_norms)
    initial_fixture = int(norm_order[len(norm_order) // 2])
    mutation_fixture = int(norm_order[math.floor(0.9 * (len(norm_order) - 1))])
    initial_style = fixture_style(hidden[initial_fixture], int(floors[initial_fixture]))

    for group_count in SCALING_GROUP_COUNTS:
        for kind, source_groups in (("control", groups), ("groupwise", candidate_groups)):
            body = "".join(source_groups[:group_count])
            document = (
                '<!doctype html><html><head><meta charset="utf-8">'
                f"<title>{kind} {group_count}-group Cauchy scaling probe</title>"
                f'<link rel="stylesheet" href="{kind}.css"></head><body>'
                f'<main id="model" class="model" style="{initial_style}">'
                '<div class="compute-values"><div class="score-stage"><div class="groups">'
                f"{body}</div></div></div></main></body></html>"
            )
            (scaling / f"{kind}-{group_count}.html").write_text(document)

    query_block_norms = np.stack([
        np.linalg.norm(hidden[:, start:start + BLOCK_WIDTH], axis=1)
        for start in range(0, head.WIDTH, BLOCK_WIDTH)
    ], axis=1)
    axis_coordinates = np.minimum(
        1.0,
        query_block_norms / block_axis_range + BOUND_AXIS_PAD,
    )
    browser_group_radius_pixels = (
        axis_coordinates @ coefficients.astype(np.float64).T * bound_pixel_scale
    )
    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "target": "original float GPT-2 tied output rows",
        "controlDirectory": CONTROL_NAME,
        "blockCount": BLOCK_COUNT,
        "blockWidth": BLOCK_WIDTH,
        "boundAxisPad": BOUND_AXIS_PAD,
        "blockAxisRange": block_axis_range,
        "outputScalePixelsPerLogit": output_scale,
        "boundQuantization": BOUND_QUANTIZATION,
        "boundPixelScale": bound_pixel_scale,
        "groupBoundGlyphs": offline["groups"],
        "groupBoundFontBytes": (OUTPUT / "group-bound-96.woff2").stat().st_size,
        "coefficientMinimum": int(coefficients.min()),
        "coefficientMaximum": int(coefficients.max()),
        "boundBaseMaximum": int(bound_bases.max()),
        "scaling": {
            "groupCounts": list(SCALING_GROUP_COUNTS),
            "rowsPerFullGroup": head.GROUP_SIZE,
            "initialFixture": initial_fixture,
            "mutationFixture": mutation_fixture,
            "fixtureSelection": "hidden-state L2 norm median and nearest empirical p90",
            "mutationIterations": 5,
            "scope": (
                "coarse reconstructed score rows plus within-group grid maximum; "
                "global control uses one scalar residual term per row; candidate uses "
                "one 96-axis residual glyph per group; full router excluded"
            ),
        },
        "fixtures": {
            "hiddenVectors": fixtures["hiddenVectors"],
            "scoreFloors": fixtures["scoreFloors"],
            "queryBlockNorms": query_block_norms.tolist(),
            "browserGroupRadiusPixels": browser_group_radius_pixels.tolist(),
        },
        "outwardSafety": {
            "groupResidualNorms": (
                "loaded from offline outward-rounded float64 max-over-row block norms"
            ),
            "fontCoefficients": "ceil(group norm * block axis range * 128)",
            "fontSizeAdjust": "800%, yielding 1024 score px/logit after coefficient scaling",
            "defaultAdvance": (
                "zero; all axes and HVAR deltas are nonnegative, avoiding Chrome's "
                "32768px shaped-advance clamp"
            ),
            "normalizedAxes": "one full F2DOT14 step of positive padding",
            "scoreRows": "floor plus one full 4px bucket before group max",
            "groupRadius": "zero-base HVAR width, then floor plus one full 4px bucket",
        },
        "earlyStopGates": {
            "invalidCarrier": "stop if any of 96 query block norms or axes is dead",
            "decisiveSlowdown": (
                "after 64 groups, stop before 197 when candidate mutation is at least "
                "2x control and over 100ms slower"
            ),
            "payoff": (
                "stop before 197 when 64-group extra coarse mutation exceeds global-to-"
                "groupwise exact groups saved times the measured one-group control cost"
            ),
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
