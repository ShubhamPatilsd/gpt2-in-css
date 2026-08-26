#!/usr/bin/env python3
"""Build the narrow 16-group Cauchy + retained block-flow composition gate."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-gate"
BOUND = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
TOPOLOGY = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max-shard256"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-int10-shard256"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
GROUP_COUNT = 16
GROUP_SIZE = 256
WIDTH = 768
BLOCK_COUNT = 96
BLOCK_WIDTH = 8
VOCABULARY = 50_257
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
AXIS_STEPS = 16_384
BOUND_CODEPOINT_START = 0xA8000
FIXTURE_IDS = (0, 1, 2, 4, 6)


def css_number(value: float) -> str:
    text = f"{float(value):.12g}"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def style_for(hidden: np.ndarray, floor: int) -> str:
    values = [f"--h{i}:{css_number(v)}" for i, v in enumerate(hidden)]
    values.append(f"--score-offset:{-int(floor) * SCORE_SCALE * SCORE_STRIDE_PX}px")
    return ";".join(values)


def group_maximum(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    buckets = np.empty((len(values), GROUP_COUNT), dtype=np.int64)
    locals_ = np.empty_like(buckets)
    for group in range(GROUP_COUNT):
        rows = values[:, group * GROUP_SIZE : (group + 1) * GROUP_SIZE]
        buckets[:, group] = rows.max(axis=1)
        locals_[:, group] = np.argmax(rows == buckets[:, group, None], axis=1)
    return buckets, locals_


def oracle(
    hidden: np.ndarray,
    floors: np.ndarray,
    weights: np.ndarray,
    coarse_range: float,
    fine_scale: float,
    group_norms: np.ndarray,
    block_axis_range: float,
    axis_pad: float,
) -> dict[str, np.ndarray]:
    row_scales = np.max(np.abs(weights), axis=1) / 511.0
    row_scales[row_scales == 0] = 1.0
    codes = np.rint(weights / row_scales[:, None]).clip(-511, 511)
    represented = codes * row_scales[:, None]
    fine = np.rint(weights[: 2 * GROUP_SIZE] / fine_scale) * fine_scale

    # Chromium realizes HVAR coordinates on the F2DOT14 grid.
    realized = np.rint(hidden / coarse_range * AXIS_STEPS) / AXIS_STEPS * coarse_range
    scores = realized @ represented.T
    row_buckets = np.floor((scores - floors[:, None]) * SCORE_SCALE).astype(np.int64) + 1
    hot_scores = realized @ fine.T
    row_buckets[:, : 2 * GROUP_SIZE] = np.rint(
        (hot_scores - floors[:, None]) * SCORE_SCALE
    ).astype(np.int64)
    coarse_buckets, coarse_locals = group_maximum(row_buckets)
    coarse_widths = coarse_buckets * SCORE_STRIDE_PX + (255 - coarse_locals) / 64.0

    block_norms = np.linalg.norm(hidden.reshape(len(hidden), BLOCK_COUNT, BLOCK_WIDTH), axis=2)
    coefficients = np.ceil(group_norms * block_axis_range * 128.0)
    coordinates = np.minimum(1.0, block_norms / block_axis_range + axis_pad)
    # At exactly zero Chrome rounds the padded HVAR contribution below one
    # font unit back to the zero-base advance.  The CSS outward bucket still
    # contributes 4px, which safely covers the exact zero certified radius.
    coordinates = np.where(block_norms == 0.0, 0.0, coordinates)
    # Variable-font normalized coordinates are realized on the F2DOT14 grid.
    # The one-step positive pad makes nearest-grid realization outward-safe.
    coordinates = np.rint(coordinates * AXIS_STEPS) / AXIS_STEPS
    carrier_pixels = coordinates @ coefficients.T * 8.0
    bound_widths = np.floor((carrier_pixels + SCORE_STRIDE_PX) / SCORE_STRIDE_PX) * SCORE_STRIDE_PX
    certified_pixels = block_norms @ group_norms.T * (SCORE_SCALE * SCORE_STRIDE_PX)
    total_widths = coarse_widths + bound_widths[:, :GROUP_COUNT]
    integer_upper_buckets = coarse_buckets + bound_widths[:, :GROUP_COUNT].astype(np.int64) // 4
    selected = np.argmax(total_widths, axis=1)
    top = np.sort(integer_upper_buckets, axis=1)[:, -2:]
    return {
        "blockNorms": block_norms,
        "coarseWidths": coarse_widths,
        "carrierPixels": carrier_pixels[:, :GROUP_COUNT],
        "boundWidths": bound_widths[:, :GROUP_COUNT],
        "certifiedPixels": certified_pixels[:, :GROUP_COUNT],
        "totalWidths": total_widths,
        "selectedGroups": selected,
        "topBucketGaps": top[:, 1] - top[:, 0],
        "topTieCounts": np.sum(
            integer_upper_buckets == integer_upper_buckets.max(axis=1)[:, None], axis=1
        ),
    }


def bound_css(block_axis_range: float, axis_pad: float) -> str:
    registrations = "".join(
        f'@property --bn{i}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for i in range(BLOCK_COUNT)
    )
    norms = []
    settings = []
    for block in range(BLOCK_COUNT):
        terms = " + ".join(
            f"var(--h{dimension})*var(--h{dimension})"
            for dimension in range(block * BLOCK_WIDTH, (block + 1) * BLOCK_WIDTH)
        )
        norms.append(f"--bn{block}:sqrt(calc({terms}))")
        settings.append(
            f'"b{block:03d}" calc(min(1,var(--bn{block})/{css_number(block_axis_range)}'
            f" + {css_number(axis_pad)}))"
        )
    # Drop the quoting artifact around calc introduced above explicitly.
    settings_text = ",".join(settings).replace('))"', '))')
    return (
        registrations
        + '@font-face{font-family:GroupBound96;src:url("../gpt2-groupwise-cauchy-head/'
        'group-bound-96.woff2") format("woff2");size-adjust:800%}'
        + ".model{" + ";".join(norms) + "}"
        + ".group-bound{display:block;grid-column:2;grid-row:1;height:0;overflow:hidden;"
        "white-space:pre;font-family:GroupBound96;font-style:normal;font-size:1000px;"
        f"font-variation-settings:{settings_text};"
        "width:calc-size(max-content,round(down,size + 4px,4px))}"
    )


def hot_css() -> str:
    faces = []
    families = []
    for shard in range(6):
        for plane in ("H", "L"):
            family = f"Score{plane}{shard}"
            families.append(family)
            adjust = "size-adjust:25600%;" if plane == "H" else ""
            faces.append(
                f'@font-face{{font-family:{family};src:url("../gpt2-hvar-grid-output-head-'
                f'global16-twoplane/score-{plane.lower()}{shard}.woff2") format("woff2");{adjust}}}'
            )
    return "".join(faces) + (
        f".mixed-hot-candidate{{font-family:{','.join(families)};font-size:100px;"
        "width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px) * "
        "var(--factor) + var(--score-offset),4px) + var(--local-tie)/64*1px))}"
    )


def topology_css() -> str:
    group_terms = ",".join(
        f"anchor-size(--score-group-{group} width)" for group in range(GROUP_COUNT)
    )
    return (
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}"
        ".model{timeline-scope:none!important}.group-wrapper{view-timeline:none!important;"
        "width:max-content!important}.group-grid{display:block!important;"
        "grid-template-columns:none!important;height:0!important;overflow:visible!important;"
        "width:max-content}.group-grid>.candidate{grid-area:auto!important;justify-self:auto!important;"
        "height:0!important}.candidate:not(.mixed-hot-candidate){width:calc-size(max-content,"
        "calc(round(down,(size - var(--base)*1px)*var(--factor) + var(--score-offset) + "
        "4px,4px) + var(--local-tie)/64*1px))}"
        ".candidate-gate .group-wrapper{display:grid!important;grid-template-columns:max-content "
        "max-content!important;grid-template-rows:1px!important}.candidate-gate .group-grid{"
        "grid-column:1;grid-row:1}.outer-max-chunk,.direct-outer-max{position:fixed;left:0;"
        "top:-94000px;height:1px}.outer-max-chunk{anchor-name:--outer-max-chunk-0;"
        f"width:max({group_terms})}}.direct-outer-max{{top:-94300px;anchor-name:--direct-outer-max;"
        "width:anchor-size(--outer-max-chunk-0 width)}"
    )


def document(kind: str, groups: list[str], initial_style: str) -> str:
    rendered = []
    for group, markup in enumerate(groups):
        if kind == "candidate":
            bound = f'<i class="group-bound" data-group="{group}">&#x{BOUND_CODEPOINT_START + group:X};</i>'
            markup = markup.replace("</section>", bound + "</section>")
        rendered.append(markup)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>16-group Cauchy block-flow "
        f"{kind} gate</title><link rel=\"stylesheet\" href=\"../gpt2-hvar-grid-output-head-"
        "certified-upper-int10-shard256/index.css\"><link rel=\"stylesheet\" href=\"gate.css\">"
        f"</head><body class=\"{kind}-gate\"><main id=\"model\" class=\"model\" style=\"{initial_style}\">"
        '<div class="group-scroller"><div class="group-track">'
        + "".join(rendered)
        + '</div></div></main><i id="chunk-max" class="outer-max-chunk"></i>'
        '<i id="outer-max" class="direct-outer-max"></i></body></html>'
    )


def main() -> None:
    for path in (
        BOUND / "reference.json",
        BOUND / "group-residual-norms-96.npy",
        BOUND / "group-bound-96.woff2",
        TOPOLOGY / "index.html",
        COARSE / "reference.json",
        FINE / "reference.json",
    ):
        if not path.exists():
            raise FileNotFoundError(path)
    bound_reference = json.loads((BOUND / "reference.json").read_text())
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    source = (TOPOLOGY / "index.html").read_text()
    groups = re.findall(r'<section class="group-wrapper"[^>]*>.*?</section>', source, re.DOTALL)
    if len(groups) != 197:
        raise RuntimeError(f"expected 197 topology groups, found {len(groups)}")
    groups = groups[:GROUP_COUNT]

    source_hidden = np.asarray(bound_reference["fixtures"]["hiddenVectors"], dtype=np.float64)
    source_floors = np.asarray(bound_reference["fixtures"]["scoreFloors"], dtype=np.int64)
    hidden = np.concatenate(
        [source_hidden[list(FIXTURE_IDS)], np.zeros((1, WIDTH), dtype=np.float64)], axis=0
    )
    floors = np.concatenate([source_floors[list(FIXTURE_IDS)], np.zeros(1, dtype=np.int64)])
    names = [f"saved-{index}" for index in FIXTURE_IDS] + ["zero-tie"]
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY], dtype=np.float64
    )
    group_norms = np.load(BOUND / "group-residual-norms-96.npy")
    measured = oracle(
        hidden,
        floors,
        weights,
        float(coarse_reference["inputRange"]),
        float(fine_reference["weightScale"]),
        group_norms,
        float(bound_reference["blockAxisRange"]),
        float(bound_reference["boundAxisPad"]),
    )
    if len(set(measured["selectedGroups"].tolist())) < 3:
        raise RuntimeError("fixtures do not exercise three selected groups")
    if measured["topBucketGaps"][1] != 4 or measured["topTieCounts"][-1] < 2:
        raise RuntimeError("boundary/tie fixture contract changed")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    css = hot_css() + bound_css(
        float(bound_reference["blockAxisRange"]),
        float(bound_reference["boundAxisPad"]),
    ) + topology_css()
    (OUTPUT / "gate.css").write_text(css + "\n")
    initial = style_for(hidden[0], int(floors[0]))
    (OUTPUT / "control.html").write_text(document("control", groups, initial))
    (OUTPUT / "candidate.html").write_text(document("candidate", groups, initial))
    fixtures = []
    for row, name in enumerate(names):
        fixtures.append({
            "name": name,
            "sourceFixture": FIXTURE_IDS[row] if row < len(FIXTURE_IDS) else None,
            "hidden": hidden[row].tolist(),
            "scoreFloor": int(floors[row]),
            "blockNorms": measured["blockNorms"][row].tolist(),
            "coarseWidths": measured["coarseWidths"][row].tolist(),
            "carrierPixels": measured["carrierPixels"][row].tolist(),
            "boundWidths": measured["boundWidths"][row].tolist(),
            "certifiedRadiusPixels": measured["certifiedPixels"][row].tolist(),
            "totalWidths": measured["totalWidths"][row].tolist(),
            "selectedGroup": int(measured["selectedGroups"][row]),
            "topBucketGap": int(measured["topBucketGaps"][row]),
            "topTieCount": int(measured["topTieCounts"][row]),
        })
    reference = {
        "decisionScope": "16 groups, one retained fan-in-16 chunk, no exact cascade",
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "boundSource": BOUND.name,
        "topologySource": TOPOLOGY.name,
        "groupCount": GROUP_COUNT,
        "groupSize": GROUP_SIZE,
        "candidateRows": GROUP_COUNT * GROUP_SIZE,
        "boundGlyphs": GROUP_COUNT,
        "blockCount": BLOCK_COUNT,
        "blockWidth": BLOCK_WIDTH,
        "axisLivePair": [3, 2],
        "boundPredictionTolerancePx": SCORE_STRIDE_PX,
        "fixtures": fixtures,
        "timing": {
            "iterations": 5,
            "decisivePenalty": "reject only if candidate mean and median are both >=1.5x and >=50ms slower",
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT),
        "fixtures": names,
        "selectedGroups": measured["selectedGroups"].tolist(),
        "topBucketGaps": measured["topBucketGaps"].tolist(),
        "topTieCounts": measured["topTieCounts"].tolist(),
    }, indent=2))


if __name__ == "__main__":
    main()
