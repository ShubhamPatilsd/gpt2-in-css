#!/usr/bin/env python3
"""Build the 96-block Cauchy upper-head and bounded scaling probes."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-blockwise-cauchy-head"
CONTROL_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10"
CONTROL = ROOT / "experiments" / CONTROL_NAME
ONE_STEP_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
BLOCK_COUNT = 96
BLOCK_WIDTH = 8
# 128 keeps the outward coefficient lattice fine while also keeping the
# font's average/base advances inside OS/2's signed xAvgCharWidth field.
BOUND_QUANTIZATION = 128
BOUND_CODEPOINT_START = 0xA0000
BOUND_AXIS_PAD = 1.0 / 16_384.0
SCALING_GROUP_COUNTS = (1, 4, 16, 64)


def bound_tag(index: int) -> str:
    return f"b{index:03d}"


def css_number(value: float) -> str:
    return head.css_number(float(value))


def upper_block_norms(values: np.ndarray, block_width: int) -> np.ndarray:
    epsilon = np.finfo(np.float64).eps
    operation_count = 2 * block_width
    gamma = operation_count * epsilon / (1.0 - operation_count * epsilon)
    blocks = []
    for start in range(0, head.WIDTH, block_width):
        block = values[:, start:start + block_width]
        squared_sum = np.sum(block * block, axis=1, dtype=np.float64)
        upper_squared_sum = np.nextafter(squared_sum / (1.0 - gamma), np.inf)
        blocks.append(np.nextafter(np.sqrt(upper_squared_sum), np.inf))
    return np.stack(blocks, axis=1)


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
    declarations.append(f"--score-offset:{-int(score_floor) * head.SCORE_SCALE * 4}px")
    return ";".join(declarations)


def write_scaling_probes(
    control_html: str,
    candidate_html: str,
    input_range: float,
    block_axis_range: float,
    initial_hidden: np.ndarray,
    initial_floor: int,
) -> None:
    """Emit nested 1/4/16/64-group pages without the full-page router."""
    scaling = OUTPUT / "scaling"
    scaling.mkdir(parents=True, exist_ok=True)
    control_groups = extract_groups(control_html)
    candidate_groups = extract_groups(candidate_html)
    if len(control_groups) != len(candidate_groups) or len(control_groups) < max(SCALING_GROUP_COUNTS):
        raise RuntimeError("could not extract enough matching vocabulary groups")

    score_faces = "".join(
        f'@font-face{{font-family:Score{part};src:url("../../gpt2-hvar-grid-output-head/'
        f'score-d{part}.woff2") format("woff2")}}'
        for part in range(5)
    )
    score_settings = ",".join(
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
    control_css = (
        score_faces
        + "@property --query-norm{syntax:\"<number>\";inherits:true;initial-value:0}"
        + shared
        + f".compute-values{{--query-norm:sqrt(calc({query_norm}))}}"
        + ".score-stage{font-family:Score0,Score1,Score2,Score3,Score4;"
        + f"font-variation-settings:{score_settings}}}"
        + ".candidate{width:calc-size(max-content,calc(round(down,"
        + "(size - var(--base)*1px)*var(--factor) + var(--score-offset)"
        + "+ var(--query-norm)*var(--bound-factor)*1px + 4px,4px)"
        + "+ var(--local-tie)/64*1px))}"
    )

    block_norm_rules = []
    bound_settings = []
    for block in range(BLOCK_COUNT):
        start = block * BLOCK_WIDTH
        terms = " + ".join(
            f"var(--h{dimension}) * var(--h{dimension})"
            for dimension in range(start, start + BLOCK_WIDTH)
        )
        block_norm_rules.append(f"--bn{block}:sqrt(calc({terms}))")
        bound_settings.append(
            f'"{bound_tag(block)}" calc(min(1,var(--bn{block})/'
            f"{css_number(block_axis_range)} + {css_number(BOUND_AXIS_PAD)}))"
        )
    block_norm_properties = "".join(
        f'@property --bn{block}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for block in range(BLOCK_COUNT)
    )
    blockwise_css = (
        score_faces
        + block_norm_properties
        + f'@font-face{{font-family:Bound96;src:url("../bound-96.woff2") format("woff2");'
        + f"size-adjust:{css_number(100 / BOUND_QUANTIZATION)}%}}"
        + shared
        + ".compute-values{" + ";".join(block_norm_rules) + "}"
        + ".score-stage{font-family:Score0,Score1,Score2,Score3,Score4;"
        + f"font-variation-settings:{score_settings}}}"
        + ".bound-glyph{font-family:Bound96;font-style:normal;"
        + f"font-variation-settings:{','.join(bound_settings)}}}"
        + ".candidate{width:calc-size(max-content,calc(round(down,"
        + f"(size - (var(--base) + var(--bound-base)/{BOUND_QUANTIZATION})*1px)"
        + "*var(--factor) + var(--score-offset) + 4px,4px)"
        + "+ var(--local-tie)/64*1px))}"
    )
    (scaling / "control.css").write_text(control_css)
    (scaling / "blockwise.css").write_text(blockwise_css)

    inline_style = fixture_style(initial_hidden, initial_floor)
    for group_count in SCALING_GROUP_COUNTS:
        for kind, groups in (("control", control_groups), ("blockwise", candidate_groups)):
            body = "".join(groups[:group_count])
            document = (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                f"<title>{kind} Cauchy {group_count}-group scaling probe</title>"
                f'<link rel="stylesheet" href="{kind}.css"></head><body>'
                f'<main id="model" class="model" style="{inline_style}">'
                '<div class="compute-values"><div class="score-stage"><div class="groups">'
                f"{body}</div></div></div></main></body></html>"
            )
            (scaling / f"{kind}-{group_count}.html").write_text(document)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    control_reference = json.loads((CONTROL / "reference.json").read_text())
    control_html = (CONTROL / "index.html").read_text()
    control_css = (CONTROL / "index.css").read_text()
    input_range = float(control_reference["inputRange"])

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:head.VOCABULARY],
        dtype=np.float64,
    )
    row_scales = np.max(np.abs(weights), axis=1) / 511.0
    row_scales[row_scales == 0] = 1.0
    codes = np.rint(weights / row_scales[:, None]).clip(-511, 511).astype(np.int16)
    represented = codes.astype(np.float64) * row_scales[:, None]
    residual = weights - represented
    residual_block_norms = upper_block_norms(residual, BLOCK_WIDTH)

    # Every runtime coordinate is bounded by input_range, hence each 8-value
    # block norm is at most sqrt(8)*input_range. Coefficients are rounded up;
    # normalized-axis requests receive a full F2DOT14 step of positive padding.
    # Together those choices ensure the bound-font contribution cannot round
    # below sum_b ||h_b|| ||w_b-wq_b|| in the font's fixed-point representation.
    block_axis_range = math.sqrt(BLOCK_WIDTH) * input_range
    coefficients = np.ceil(
        residual_block_norms / row_scales[:, None]
        * math.sqrt(BLOCK_WIDTH)
        * BOUND_QUANTIZATION
    ).astype(np.int16)
    if np.any(coefficients < 0) or int(coefficients.max()) > 32_767:
        raise RuntimeError("outward residual coefficients do not fit int16")
    bound_bases = np.sum(coefficients.astype(np.int64), axis=1)
    if int(bound_bases.max()) > 65_535:
        raise RuntimeError("bound-font base advance does not fit uint16")

    font_path = OUTPUT / "bound-96.ttf"
    build_direct_font_backend(
        coefficients,
        font_path,
        signed_axes=False,
        base_advance=bound_bases,
        codepoint_start=BOUND_CODEPOINT_START,
        axis_tags=[bound_tag(index) for index in range(BLOCK_COUNT)],
        allow_out_of_range_result=True,
    )

    token = 0
    candidate_pattern = re.compile(
        r'<i class="candidate" style="([^"]+)">(.*?)</i>'
    )

    def rewrite_candidate(match: re.Match[str]) -> str:
        nonlocal token
        style = re.sub(r"--bound-factor:[^;]+;", "", match.group(1))
        style += f"--bound-base:{int(bound_bases[token])};"
        character = (
            '<span class="bound-glyph">'
            f"&#x{BOUND_CODEPOINT_START + token:X};</span>"
        )
        token += 1
        return f'<i class="candidate" style="{style}">{match.group(2)}{character}</i>'

    candidate_html = candidate_pattern.sub(rewrite_candidate, control_html)
    if token != head.VOCABULARY:
        raise RuntimeError(f"rewrote {token} candidates, expected {head.VOCABULARY}")
    candidate_html = candidate_html.replace(
        "Certified-upper row-wise int10 GPT-2 head",
        "GPT-2 96-block Cauchy upper-head probe",
        1,
    )

    # Compute block norms one dependency level above the element that expands
    # all score and bound axes. This avoids Chromium's per-element expansion
    # limit already observed by the global-Cauchy probe.
    opening = '<main id="model" class="model"><div class="group-scroller">'
    if candidate_html.count(opening) != 1:
        raise RuntimeError("coarse group-scroller opening marker missing")
    candidate_html = candidate_html.replace(
        opening,
        '<main id="model" class="model"><div class="bound-values">'
        '<div class="group-scroller">',
        1,
    )
    closing = "</div></div>"
    closing_index = candidate_html.find(closing, candidate_html.find(opening.split("><", 1)[0]))
    if closing_index < 0:
        raise RuntimeError("coarse group-scroller closing marker missing")
    candidate_html = (
        candidate_html[:closing_index]
        + "</div></div></div>"
        + candidate_html[closing_index + len(closing):]
    )

    scalar_term = "+ var(--query-norm)*var(--bound-factor)*1px + 4px,4px)"
    if control_css.count(scalar_term) != 1:
        raise RuntimeError("global-Cauchy scalar term missing")
    candidate_css = control_css.replace(scalar_term, "+ 4px,4px)", 1)
    base_term = "size - var(--base)*1px"
    if candidate_css.count(base_term) != 1:
        raise RuntimeError("candidate base subtraction missing")
    candidate_css = candidate_css.replace(
        base_term,
        f"size - (var(--base) + var(--bound-base)/{BOUND_QUANTIZATION})*1px",
        1,
    )
    candidate_css = candidate_css.replace(
        'url("score-d',
        f'url("../{CONTROL_NAME.replace("-certified-upper-int10", "")}/score-d',
    )

    block_norm_rules = []
    bound_settings = []
    for block in range(BLOCK_COUNT):
        start = block * BLOCK_WIDTH
        terms = " + ".join(
            f"var(--h{dimension}) * var(--h{dimension})"
            for dimension in range(start, start + BLOCK_WIDTH)
        )
        block_norm_rules.append(f"--bn{block}:sqrt(calc({terms}))")
        bound_settings.append(
            f'"{bound_tag(block)}" calc(min(1,var(--bn{block})/'
            f"{css_number(block_axis_range)} + {css_number(BOUND_AXIS_PAD)}))"
        )
    block_norm_properties = "".join(
        f'@property --bn{block}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for block in range(BLOCK_COUNT)
    )
    extra_css = (
        block_norm_properties
        + f'@font-face{{font-family:Bound96;src:url("bound-96.woff2") format("woff2");'
        f"size-adjust:{css_number(100 / BOUND_QUANTIZATION)}%}}"
        ".bound-values{display:contents;" + ";".join(block_norm_rules) + "}"
        ".bound-glyph{font-family:Bound96;font-style:normal;font-variation-settings:"
        + ",".join(bound_settings) + "}"
    )
    readback_marker = ".outer-reader{"
    if candidate_css.count(readback_marker) != 1:
        raise RuntimeError("outer readback marker missing")
    candidate_css = candidate_css.replace(
        readback_marker, extra_css + readback_marker, 1
    )

    fixtures = control_reference["allFixtures"]
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.int64)
    query_block_norms = np.stack([
        np.linalg.norm(hidden[:, start:start + BLOCK_WIDTH], axis=1)
        for start in range(0, head.WIDTH, BLOCK_WIDTH)
    ], axis=1)
    axis_coordinates = np.minimum(
        1.0,
        query_block_norms / block_axis_range + BOUND_AXIS_PAD,
    )
    font_radius = (
        axis_coordinates @ coefficients.astype(np.float64).T
        / BOUND_QUANTIZATION
        * input_range
        * row_scales[None, :]
    )
    approximate = hidden @ represented.T
    font_upper = approximate + font_radius
    font_upper_buckets = np.floor(
        (font_upper - floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int64) + 1
    winners = np.argmax(font_upper_buckets, axis=1).astype(np.int64)
    dense_winners = np.asarray(fixtures["denseWinners"], dtype=np.int64)

    query_norms = np.linalg.norm(hidden, axis=1)
    norm_order = np.argsort(query_norms)
    initial_fixture = int(norm_order[len(norm_order) // 2])
    mutation_fixture = int(norm_order[math.floor(0.9 * (len(norm_order) - 1))])
    write_scaling_probes(
        control_html,
        candidate_html,
        input_range,
        block_axis_range,
        hidden[initial_fixture],
        int(floors[initial_fixture]),
    )

    (OUTPUT / "candidate.html").write_text(candidate_html)
    (OUTPUT / "candidate.css").write_text(candidate_css)
    # The source HTML expects index.css.
    candidate_html = candidate_html.replace('href="index.css"', 'href="candidate.css"', 1)
    (OUTPUT / "candidate.html").write_text(candidate_html)
    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "target": "original float GPT-2 tied output rows",
        "controlDirectory": CONTROL_NAME,
        "oneStepDirectory": ONE_STEP_NAME,
        "blockCount": BLOCK_COUNT,
        "blockWidth": BLOCK_WIDTH,
        "boundQuantization": BOUND_QUANTIZATION,
        "boundAxisPad": BOUND_AXIS_PAD,
        "blockAxisRange": block_axis_range,
        "coarseGlyphsPerToken": control_reference.get("glyphsPerToken", 5) + 1,
        "candidateBoundFontBytes": (OUTPUT / "bound-96.woff2").stat().st_size,
        "candidateHtmlBytes": (OUTPUT / "candidate.html").stat().st_size,
        "candidateCssBytes": (OUTPUT / "candidate.css").stat().st_size,
        "scaling": {
            "groupCounts": list(SCALING_GROUP_COUNTS),
            "rowsPerFullGroup": head.GROUP_SIZE,
            "initialFixture": initial_fixture,
            "mutationFixture": mutation_fixture,
            "fixtureSelection": "hidden-state L2 norm median and nearest empirical p90",
            "scope": "coarse score rows plus within-group CSS grid max; full router excluded",
        },
        "fixtures": {
            "hiddenVectors": fixtures["hiddenVectors"],
            "scoreFloors": fixtures["scoreFloors"],
            "denseWinners": dense_winners.tolist(),
            "denseGroups": (dense_winners // head.GROUP_SIZE).tolist(),
            "globalUpperWinners": fixtures["upperWinners"],
            "globalUpperGroups": fixtures["upperGroups"],
            "blockwiseUpperWinners": winners.tolist(),
            "blockwiseUpperGroups": (winners // head.GROUP_SIZE).tolist(),
            "blockwiseUpperWinnerBuckets": font_upper_buckets[
                np.arange(len(winners)), winners
            ].astype(int).tolist(),
            "queryBlockNorms": query_block_norms.tolist(),
        },
        "outwardSafety": {
            "residualNorms": (
                "float64 gamma envelope for products/sums, then nextafter "
                "toward +infinity after sqrt"
            ),
            "fontCoefficients": "ceil",
            "normalizedAxes": "one full F2DOT14 step of positive padding",
            "upperBuckets": "floor plus one full bucket",
            "centerCoordinateCaveat": (
                "A/B retains the control head's browser-realized score-center "
                "contract; checkpoint-level deployment must retain its existing "
                "coarse/fine realization allowances."
            ),
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
