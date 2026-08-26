#!/usr/bin/env python3
"""Build the smallest integrated groupwise-Cauchy best-first CSS head gate.

The generated runtime is HTML/CSS/fonts only.  It combines the retained
197-glyph, 96-block group certificate with three gated global-int16 exact
group evaluations.  Three stages are intentionally the early feasibility
gate: an unresolved state exposes a mandatory-fallback flag, but the much
larger exact fallback is not generated unless this prefix can beat the
retained dense head.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_certified_int10_unrolled_cascade as cascade
import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-groupwise-cauchy-cascade"
ONE_STEP = ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
GROUPWISE = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
RETAINED = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max-shard256"
STAGES = 3
BLOCK_COUNT = 96
BLOCK_WIDTH = 8
BOUND_CODEPOINT_START = 0xA8000
BOUND_AXIS_PAD = 1.0 / 16_384.0
SLACK_BUCKETS_PER_SIDE = 24
GROUPS = (head.VOCABULARY + head.GROUP_SIZE - 1) // head.GROUP_SIZE


def css_number(value: float) -> str:
    return head.css_number(float(value))


def bound_tag(index: int) -> str:
    return f"b{index:03d}"


def add_group_bounds(document: str) -> str:
    seen = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        group = seen
        seen += 1
        section = match.group(0)
        if section.count("</section>") != 1:
            raise RuntimeError(f"group {group} does not have one closing tag")
        glyph = f'<i class="group-bound">&#x{BOUND_CODEPOINT_START + group:X};</i>'
        return section.replace("</section>", glyph + "</section>")

    result = re.sub(
        r'<section class="group-wrapper"[^>]*>.*?</section>',
        replace,
        document,
        flags=re.DOTALL,
    )
    if seen != GROUPS:
        raise RuntimeError(f"expected {GROUPS} groups, found {seen}")
    return result


def groupwise_css(reference: dict[str, object]) -> str:
    input_range = float(reference["inputRange"])
    block_axis_range = math.sqrt(BLOCK_WIDTH) * input_range
    registrations = "".join(
        f'@property --bn{block}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for block in range(BLOCK_COUNT)
    )
    norms = []
    settings = []
    for block in range(BLOCK_COUNT):
        start = block * BLOCK_WIDTH
        terms = " + ".join(
            f"var(--h{dimension}) * var(--h{dimension})"
            for dimension in range(start, start + BLOCK_WIDTH)
        )
        norms.append(f"--bn{block}:sqrt(calc({terms}))")
        settings.append(
            f'"{bound_tag(block)}" calc(min(1,var(--bn{block})/'
            f"{css_number(block_axis_range)} + {css_number(BOUND_AXIS_PAD)}))"
        )
    return "".join((
        registrations,
        '@font-face{font-family:GroupBound96;src:url("../gpt2-groupwise-cauchy-head/'
        'group-bound-96.woff2") format("woff2");size-adjust:800%}',
        ".cascade{" + ";".join(norms) + "}",
        ".group-wrapper{display:grid;grid-template-columns:max-content max-content}",
        ".candidate{width:calc-size(max-content,calc(round(down,"
        "(size - var(--base)*1px)*var(--factor) + var(--score-offset) + 4px,4px)"
        "+ var(--local-tie)/64*1px))}",
        ".group-bound{display:block;grid-column:2;height:1px;overflow:hidden;"
        "white-space:pre;font-family:GroupBound96;font-style:normal;"
        "font-size:1000px;line-height:1;font-variation-settings:",
        ",".join(settings),
        ";width:calc-size(max-content,round(down,size + 4px,4px))}",
    ))


def build_prefix(document: str, source_css: str) -> tuple[str, str]:
    cascade.STAGES = STAGES
    cascade.SLACK_BUCKETS = SLACK_BUCKETS_PER_SIDE
    cascade.GATE_LATER_STAGES = True
    cascade.INCREMENTAL_MASK = False
    cascade.PACKED_MASK = False

    marker = '<span id="fine-stage" class="fine-stage">'
    start = document.index(marker) + len(marker)
    stop = document.index('</span><span class="fine-reader">', start)
    candidates = document[start:stop]

    child = cascade.router_markup(STAGES, GROUPS, "")
    for stage in range(STAGES - 1, 0, -1):
        child = cascade.router_markup(
            stage,
            GROUPS,
            cascade.fine_markup(stage, candidates, child),
        )
    result_marker = '<i id="fine-result" class="fine-result"></i>'
    if document.count(result_marker) != 1:
        raise RuntimeError("fine result insertion point changed")
    document = document.replace(
        result_marker,
        f'<i id="fine-result" class="fine-result">{child}</i>',
        1,
    ).replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Three-stage groupwise-Cauchy CSS cascade feasibility gate",
        1,
    )

    registrations = [
        cascade.property_registration("best-bucket-0"),
        cascade.property_registration("best-winner-0"),
    ]
    for stage in range(1, STAGES + 1):
        for name in (
            f"upper-mask-{stage}", f"upper-bucket-{stage}",
            f"remaining-group-{stage}", f"certificate-gap-{stage - 1}",
            f"done-{stage - 1}",
        ):
            registrations.append(cascade.property_registration(name))
        if stage < STAGES:
            for name in (
                f"fine-bucket-{stage}", f"fine-local-{stage}",
                f"fine-winner-{stage}", f"score-delta-{stage}",
                f"use-stage-{stage}", f"best-bucket-{stage}",
                f"best-winner-{stage}",
            ):
                registrations.append(cascade.property_registration(name))

    parts = [
        source_css,
        "".join(registrations),
        ".fine-result{--best-bucket-0:var(--fine-bucket);"
        "--best-winner-0:var(--refined-winner)}",
    ]
    selected = ["group"]
    for stage in range(1, STAGES + 1):
        parts.append(cascade.router_css(stage, GROUPS, selected))
        selected.append(f"remaining-group-{stage}")
        if stage < STAGES:
            parts.append(cascade.fine_css(stage))
            parts.append(cascade.fine_gate_css(stage))
    # The last router's --done flag is the finite-prefix contract. A zero means
    # that any complete implementation must run its exact fallback.
    parts.append(
        ".remaining-result-3{--fallback-required:calc(1 - var(--done-2))}"
    )
    return document, "".join(parts) + "\n"


def oracle() -> dict[str, object]:
    source = json.loads((ONE_STEP / "reference.json").read_text())
    groupwise = json.loads((GROUPWISE / "reference.json").read_text())
    fine = json.loads((FINE / "reference.json").read_text())
    fixtures = source["certifiedFixtures"]
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.int64)
    group_hidden = np.asarray(groupwise["fixtures"]["hiddenVectors"], dtype=np.float64)
    if not np.array_equal(hidden, group_hidden):
        raise RuntimeError("one-step and groupwise browser fixtures differ")

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:head.VOCABULARY],
        dtype=np.float64,
    )
    row_scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    row_scales[row_scales == 0] = 1.0
    int10 = np.rint(weights / row_scales[:, None]).clip(
        -head.WEIGHT_MAX, head.WEIGHT_MAX
    ).astype(np.int16)
    represented = int10.astype(np.float64) * row_scales[:, None]
    represented_scores = hidden @ represented.T
    represented_buckets = np.floor(
        (represented_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int64) + 1
    padding = GROUPS * head.GROUP_SIZE - head.VOCABULARY
    represented_group = np.max(
        np.pad(represented_buckets, ((0, 0), (0, padding)), constant_values=-10**9)
        .reshape(len(hidden), GROUPS, head.GROUP_SIZE),
        axis=2,
    )
    radius_pixels = np.asarray(
        groupwise["fixtures"]["browserGroupRadiusPixels"], dtype=np.float64
    )
    radius_buckets = np.floor(radius_pixels / head.SCORE_STRIDE_PX).astype(np.int64) + 1
    group_upper = represented_group + radius_buckets

    fine_scale = float(fine["weightScale"])
    fine_codes = np.rint(weights / fine_scale).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_scale
    fine_scores = hidden @ fine_weights.T
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int64)
    target_winners = np.argmax(fine_scores, axis=1)
    float_winners = np.argmax(hidden @ weights.T, axis=1)
    order = np.argsort(-group_upper, axis=1, kind="stable")

    stage_groups = order[:, :STAGES]
    stage_winners = np.empty((len(hidden), STAGES), dtype=np.int64)
    stage_buckets = np.empty_like(stage_winners)
    best_winners = np.empty_like(stage_winners)
    best_buckets = np.empty_like(stage_winners)
    gaps = np.empty_like(stage_winners)
    first_done: list[int | None] = []
    threshold = 2 * SLACK_BUCKETS_PER_SIDE
    for fixture in range(len(hidden)):
        best_winner = -1
        best_bucket = -10**9
        done_at = None
        for stage in range(STAGES):
            group = int(stage_groups[fixture, stage])
            begin = group * head.GROUP_SIZE
            end = min(begin + head.GROUP_SIZE, head.VOCABULARY)
            winner = begin + int(np.argmax(fine_buckets[fixture, begin:end]))
            bucket = int(fine_buckets[fixture, winner])
            stage_winners[fixture, stage] = winner
            stage_buckets[fixture, stage] = bucket
            if bucket > best_bucket or (
                bucket == best_bucket and (best_winner < 0 or winner < best_winner)
            ):
                best_winner, best_bucket = winner, bucket
            best_winners[fixture, stage] = best_winner
            best_buckets[fixture, stage] = best_bucket
            next_upper = int(group_upper[fixture, order[fixture, stage + 1]])
            gaps[fixture, stage] = best_bucket - next_upper
            if done_at is None and gaps[fixture, stage] > threshold:
                done_at = stage
        first_done.append(done_at)

    return {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointWeightsChanged": False,
        "target": (
            "argmax of global-int16 tied output weights at Chromium F2DOT14-realized "
            "hidden coordinates, 1/256-logit score buckets, lower token id on ties"
        ),
        "targetIsOriginalFloatExact": False,
        "targetMatchesFloatOnFixtures": int(np.sum(target_winners == float_winners)),
        "prefixStages": STAGES,
        "scoreSlackBucketsPerSide": SLACK_BUCKETS_PER_SIDE,
        "strictStopGapBuckets": threshold,
        "schedule": "best-first by live groupwise upper; exact one 256-row group per stage",
        "finitePrefixContract": (
            "done iff incumbent fine lower exceeds next unvisited group upper by 48 "
            "buckets; otherwise --fallback-required is 1"
        ),
        "fallback": {
            "requiredForCompleteness": True,
            "generated": False,
            "reason": "deferred until the three-stage loaded-latency feasibility gate passes",
            "soundOptions": [
                "one conditional 50257-row global-int16 dense scorer",
                "197 conditional exact-group tail branches",
                "continue the same unrolled schedule to all 197 groups",
            ],
        },
        "groups": GROUPS,
        "groupSize": head.GROUP_SIZE,
        "vocabulary": head.VOCABULARY,
        "blockCount": BLOCK_COUNT,
        "blockWidth": BLOCK_WIDTH,
        "fixtures": {
            "hiddenVectors": fixtures["hiddenVectors"],
            "scoreFloors": fixtures["scoreFloors"],
            "stageGroups": stage_groups.tolist(),
            "stageFineWinners": stage_winners.tolist(),
            "stageFineBuckets": stage_buckets.tolist(),
            "bestWinners": best_winners.tolist(),
            "bestBuckets": best_buckets.tolist(),
            "certificateGaps": gaps.tolist(),
            "firstDoneZeroBased": first_done,
            "targetWinners": target_winners.tolist(),
            "floatWinners": float_winners.tolist(),
            "browserGroupRadiusPixels": radius_pixels.tolist(),
        },
        "comparisons": {
            "retained": RETAINED.name,
            "globalCauchy": "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated",
        },
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    group_reference = json.loads(
        (ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-upper-int10" / "reference.json").read_text()
    )
    document = add_group_bounds((ONE_STEP / "index.html").read_text())
    document, css = build_prefix(document, (ONE_STEP / "index.css").read_text())
    css += groupwise_css(group_reference)
    (OUTPUT / "index.html").write_text(document)
    (OUTPUT / "index.css").write_text(css)
    reference = oracle()
    reference["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    reference["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    reference["groupBoundFontBytes"] = (GROUPWISE / "group-bound-96.woff2").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "prefixStages": STAGES,
        "fixtures": len(reference["fixtures"]["hiddenVectors"]),
        "certifiedWithinPrefix": sum(
            value is not None for value in reference["fixtures"]["firstDoneZeroBased"]
        ),
        "targetMatchesFloatOnFixtures": reference["targetMatchesFloatOnFixtures"],
        "htmlBytes": reference["htmlBytes"],
        "cssBytes": reference["cssBytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
