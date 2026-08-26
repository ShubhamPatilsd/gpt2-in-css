#!/usr/bin/env python3
"""Build browser probes selected by the offline mixed group-size sweep.

The builder writes only the sweep experiment directory and never starts a
browser.  It reuses the existing int10 and global-int16 font banks.
"""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine_builder
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_mixed_precision_group_size_sweep import (
    ALLOWANCE_BUCKETS_PER_SIDE,
    OUTPUT,
    SCORE_SCALE,
    STAGES,
    STOP_GAP_BUCKETS,
    grouped_max,
    grouped_winners,
    stopping_route,
)


ROOT = Path(__file__).resolve().parents[1]
OFFLINE = OUTPUT / "offline-results.json"
BASELINE = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated"
)
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-upper-int10"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
COARSE_FONT_SOURCE = ROOT / "experiments" / "gpt2-hvar-grid-output-head"
LAYOUT_UNITS_PER_PX = 64


def css_number_up(value: float) -> str:
    return head.css_number(math.ceil(value * 1_000_000_000) / 1_000_000_000)


def css_if(branches: list[tuple[int, str]], fallback: str) -> str:
    return "if(" + ";".join(
        f"style(--group:{group}):{value}" for group, value in branches
    ) + f";else:{fallback})"


def property_registration(name: str) -> str:
    return f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'


def router_markup(stage: int, groups: int, child: str) -> str:
    sources = "".join(
        f'<i class="upper-source-{stage} upper-source-{stage}-{group}"></i>'
        for group in range(groups)
    )
    matches = "".join(
        f'<i class="upper-match-{stage} upper-match-{stage}-{group}"></i>'
        for group in range(groups)
    )
    return (
        f'<span class="upper-sources-{stage}">{sources}</span>'
        f'<i class="upper-max-{stage}"></i>'
        f'<span class="upper-reader-{stage}"><span class="upper-selection-{stage}">'
        + matches
        + f'<i class="upper-group-choice-{stage}"></i>'
        f'<span class="upper-group-reader-{stage}">'
        f'<output id="remaining-result-{stage}" class="remaining-result-{stage}">'
        + child
        + "</output></span></span></span>"
    )


def router_css(
    stage: int,
    groups: int,
    stride: int,
    selected_properties: list[str],
) -> str:
    def mask(group: int) -> str:
        terms = ",".join(
            f"abs(var(--{name}) - {group})" for name in selected_properties
        )
        return f"clamp(0,min({terms}),1)"

    sources = "".join(
        f".upper-source-{stage}-{group}{{--upper-mask-{stage}:{mask(group)};"
        f"position-anchor:--score-group-{group};"
        f"anchor-name:--upper-source-{stage}-{group};"
        f"width:calc(anchor-size(--score-group-{group} width)*"
        f"var(--upper-mask-{stage}))}}"
        for group in range(groups)
    )
    source_sizes = ",".join(
        f"anchor-size(--upper-source-{stage}-{group} width)"
        for group in range(groups)
    )
    matches = "".join(
        f".upper-match-{stage}-{group}{{"
        f"position-anchor:--upper-source-{stage}-{group};"
        f"anchor-name:--upper-match-{stage}-{group};"
        f"width:calc(clamp(0px,anchor-size(--upper-source-{stage}-{group} width) - "
        f"(var(--upper-bucket-{stage}) - .5)*{stride}px,1px)*"
        f"{groups - group})}}"
        for group in range(groups)
    )
    match_sizes = ",".join(
        f"anchor-size(--upper-match-{stage}-{group} width)"
        for group in range(groups)
    )
    fixed = (
        f".upper-source-{stage},.upper-max-{stage},.upper-reader-{stage},"
        f".upper-match-{stage},.upper-group-choice-{stage},"
        f".upper-group-reader-{stage},.remaining-result-{stage}{{"
        f"position:fixed;left:0;top:{-60_000 + stage * 20}px;height:1px}}"
    )
    return (
        fixed
        + sources
        + f".upper-max-{stage}{{position-anchor:--upper-source-{stage}-0;"
        f"anchor-name:--upper-max-anchor-{stage};width:max({source_sizes})}}"
        + f".upper-reader-{stage}{{position-anchor:--upper-max-anchor-{stage};"
        f"width:anchor-size(--upper-max-anchor-{stage} width);"
        f"container:upper-result-{stage}/inline-size}}"
        + f"@container upper-result-{stage} (width >= 0px){{"
        f".upper-selection-{stage}{{--upper-bucket-{stage}:"
        f"round(down,100cqi/{stride}px,1)}}"
        + matches
        + f".upper-group-choice-{stage}{{"
        f"position-anchor:--upper-match-{stage}-0;"
        f"anchor-name:--upper-group-choice-anchor-{stage};"
        f"width:max({match_sizes})}}"
        + f".upper-group-reader-{stage}{{"
        f"position-anchor:--upper-group-choice-anchor-{stage};"
        f"width:anchor-size(--upper-group-choice-anchor-{stage} width);"
        f"container:upper-group-result-{stage}/inline-size}}"
        + f"@container upper-group-result-{stage} (width >= 0px){{"
        f".remaining-result-{stage}{{--remaining-group-{stage}:calc("
        f"{groups} - round(nearest,100cqi/1px,1));"
        f"--certificate-gap-{stage - 1}:calc(var(--best-bucket-{stage - 1}) - "
        f"var(--upper-bucket-{stage}));"
        f"--done-{stage - 1}:clamp(0,sign(var(--certificate-gap-{stage - 1}) - "
        f"{STOP_GAP_BUCKETS + 1}) + 1,1);display:block;"
        f"width:calc(var(--remaining-group-{stage})*1px);height:1px}}}}}}"
    )


def stage_markup(stage: int, candidates: str, child: str) -> str:
    result_id = "fine-result" if stage == 0 else f"fine-result-{stage}"
    return (
        f'<span id="mixed-stage-{stage}" class="mixed-stage mixed-stage-{stage}">'
        f'<span id="dynamic-fine-stage-{stage}" '
        f'class="fine-stage dynamic-fine-stage dynamic-fine-stage-{stage}">'
        f"{candidates}</span>"
        f'<i id="mixed-choice-source-{stage}" '
        f'class="mixed-choice-source mixed-choice-source-{stage}"></i>'
        f'<span class="mixed-final-reader mixed-final-reader-{stage}">'
        f'<i id="{result_id}" class="mixed-fine-result '
        f'mixed-fine-result-{stage}">{child}</i></span></span>'
    )


def stage_css(
    stage: int, group_size: int, stride: int, hot_groups: tuple[int, ...]
) -> str:
    top = -92_000 + stage * 300
    gate = "display:contents;" if stage == 0 else (
        f"display:if(style(--done-{stage - 1}:1):none;else:contents);"
    )
    binding = "" if stage == 0 else f"--group:var(--remaining-group-{stage});"
    selected = "var(--group)" if stage == 0 else f"var(--remaining-group-{stage})"
    result_group = (
        "--search-root-group:var(--group);--selected-group-0:var(--group);"
        if stage == 0
        else (
            "--group:var(--search-root-group);"
            f"--selected-group-{stage}:var(--remaining-group-{stage});"
        )
    )
    if stage == 0:
        state = (
            "--best-bucket-0:var(--fine-bucket-0);"
            "--best-winner-0:var(--fine-winner-0);"
        )
    else:
        previous = stage - 1
        state = (
            f"--score-delta-{stage}:calc(var(--fine-bucket-{stage}) - "
            f"var(--best-bucket-{previous}));"
            f"--use-stage-{stage}:max(clamp(0,sign(var(--score-delta-{stage})),1),"
            f"calc((1 - abs(sign(var(--score-delta-{stage}))))*"
            f"clamp(0,sign(var(--best-winner-{previous}) - "
            f"var(--fine-winner-{stage})),1)));"
            f"--best-winner-{stage}:calc(var(--best-winner-{previous})*"
            f"(1 - var(--use-stage-{stage})) + var(--fine-winner-{stage})*"
            f"var(--use-stage-{stage}));"
            f"--best-bucket-{stage}:max(var(--best-bucket-{previous}),"
            f"var(--fine-bucket-{stage}));"
        )
    hot_choice = "".join(
        f"style(--group:{group}):anchor-size(--group-{group} width);"
        for group in hot_groups
    )
    hot_display = "".join(
        f"style(--group:{group}):none;" for group in hot_groups
    )
    return (
        f".mixed-stage-{stage}{{{gate}}}"
        f".dynamic-fine-stage-{stage}{{{binding}top:{top}px;"
        f"anchor-name:--dynamic-fine-winner-{stage};"
        f"display:if({hot_display}else:grid)}}"
        f".mixed-choice-source-{stage}{{{binding}position:fixed;left:0;"
        f"top:{top + 100}px;height:1px;anchor-name:--mixed-winner-{stage};"
        f"width:if({hot_choice}else:"
        f"anchor-size(--dynamic-fine-winner-{stage} width))}}"
        f".mixed-final-reader-{stage}{{position:fixed;left:0;top:{top + 200}px;"
        f"height:1px;position-anchor:--mixed-winner-{stage};"
        f"width:anchor-size(--mixed-winner-{stage} width);"
        f"container:mixed-fine-result-{stage}/inline-size}}"
        f"@container mixed-fine-result-{stage} (width >= 0px){{"
        f".mixed-fine-result-{stage}{{{result_group}"
        f"--fine-geometry-px-{stage}:calc((100cqi + .001px)/1px);"
        f"--fine-bucket-{stage}:round(down,var(--fine-geometry-px-{stage})/"
        f"{stride},1);"
        f"--fine-tie-code-{stage}:round(nearest,mod("
        f"var(--fine-geometry-px-{stage}),{stride})*"
        f"{head.css_number(group_size / stride)},1);"
        f"--fine-local-{stage}:calc({group_size - 1} - "
        f"var(--fine-tie-code-{stage}));"
        f"--fine-winner-{stage}:calc({selected}*{group_size} + "
        f"var(--fine-local-{stage}));{state}display:block;"
        f"width:calc(var(--best-winner-{stage})*1px);height:1px}}}}"
    )


def registrations() -> str:
    names: list[str] = ["search-root-group"]
    for stage in range(STAGES):
        names.extend(
            [
                f"selected-group-{stage}",
                f"fine-bucket-{stage}",
                f"fine-geometry-px-{stage}",
                f"fine-tie-code-{stage}",
                f"fine-local-{stage}",
                f"fine-winner-{stage}",
                f"best-bucket-{stage}",
                f"best-winner-{stage}",
            ]
        )
        if stage:
            names.extend([f"score-delta-{stage}", f"use-stage-{stage}"])
    for stage in range(1, STAGES + 1):
        names.extend(
            [
                f"upper-mask-{stage}",
                f"upper-bucket-{stage}",
                f"remaining-group-{stage}",
                f"certificate-gap-{stage - 1}",
                f"done-{stage - 1}",
            ]
        )
    return "".join(property_registration(name) for name in names)


def fine_assets(
    fine_codes: np.ndarray,
    input_range: float,
    fine_scale: float,
    display_scale: float,
    group_size: int,
    groups: int,
    stride: int,
) -> tuple[list[str], str, str, np.ndarray, float]:
    equivalent_bases: list[np.ndarray] = []
    for start in range(0, head.WIDTH, fine_builder.SHARD):
        stop = min(start + fine_builder.SHARD, head.WIDTH)
        shard_codes = fine_codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        high_base = np.sum(np.abs(high.astype(np.int64)), axis=1) + 32
        residual_base = np.sum(np.abs(residual.astype(np.int64)), axis=1) + 32
        equivalent_bases.append(high_base * 256 + residual_base)
    bases = np.sum(np.stack(equivalent_bases), axis=0)
    factor = input_range * fine_scale * SCORE_SCALE * stride / display_scale
    tie_step = stride / group_size

    glyphs = [
        "".join(chr(start + token) for start in fine_builder.CODEPOINT_STARTS)
        for token in range(head.VOCABULARY)
    ]
    exact_candidates = [
        f'<i class="candidate mixed-hot-candidate" style="--base:'
        f'{head.css_number(bases[token] * display_scale)};'
        f'--factor:{head.css_number(factor)};'
        f'--local-tie:{group_size - 1 - token % group_size}">'
        f"{glyphs[token]}</i>"
        for token in range(head.VOCABULARY)
    ]

    # A dynamic row represents the token at group * group_size + local.  Keep
    # the tie payload expressed from that token contract instead of inheriting
    # the retained G256 row ordering by accident.
    dynamic_tokens = range(group_size)
    candidate_markup = "".join(
        f'<i class="fine-candidate" data-local="{token % group_size}" '
        f'style="--local-tie:'
        f'{group_size - 1 - (token % group_size)}">'
        f'<span class="fine-phase"></span></i>'
        for token in dynamic_tokens
    )
    candidate_rules: list[str] = []
    last_group = groups - 1
    last_size = head.VOCABULARY - last_group * group_size
    for local in range(group_size):
        base_branches: list[tuple[int, str]] = []
        glyph_branches: list[tuple[int, str]] = []
        for group in range(groups):
            token = group * group_size + local
            if token >= head.VOCABULARY:
                break
            base_branches.append(
                (group, head.css_number(bases[token] * display_scale))
            )
            glyph_branches.append((group, json.dumps(glyphs[token], ensure_ascii=False)))
        fallback_base = base_branches[0][1]
        fallback_glyph = glyph_branches[0][1]
        validity = (
            f"display:if(style(--group:{last_group}):none;else:block);"
            if local >= last_size
            else ""
        )
        candidate_rules.append(
            f".fine-candidate:nth-child({local + 1}){{{validity}"
            f"--fine-base:{css_if(base_branches, fallback_base)};"
            f"--fine-glyphs:{css_if(glyph_branches, fallback_glyph)}}}"
        )

    families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(6)
        for plane in ("H", "L")
    )
    settings = ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{head.css_number(input_range)})"
        for dimension in range(head.WIDTH)
    )
    fine_css = (
        f".fine-stage{{position:fixed;left:0;display:grid;"
        f"grid-template-columns:max-content;grid-template-rows:1px;"
        f"width:max-content;height:1px;font-family:{families};font-size:100px;"
        f"line-height:1;font-variation-settings:{settings};font-kerning:none}}"
        + f".fine-phase{{display:inline;font-variation-settings:{settings}}}"
        + ".fine-phase::before{content:var(--fine-glyphs)}"
        + ".fine-candidate{grid-area:1/1;display:block;justify-self:start;"
        + "height:1px;overflow:hidden;white-space:pre;font-style:normal;"
        + f"width:calc-size(max-content,calc(round(nearest,(size - "
        + f"var(--fine-base)*1px)*{head.css_number(factor)} + "
        + f"var(--score-offset),{stride}px) + var(--local-tie)*"
        + f"{head.css_number(tie_step)}*1px))}}"
        + "".join(candidate_rules)
    )
    return exact_candidates, candidate_markup, fine_css, bases, factor


def fixture_contract(
    fixtures: dict[str, object],
    coarse_weights: np.ndarray,
    errors: np.ndarray,
    fine_weights: np.ndarray,
    group_size: int,
    hot_groups: tuple[int, ...],
) -> tuple[dict[str, object], dict[str, int]]:
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.int64)
    fine_scores = hidden @ fine_weights.T
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * SCORE_SCALE
    ).astype(np.int64)
    upper_buckets = (
        np.floor(
            (
                hidden @ coarse_weights.T
                + np.linalg.norm(hidden, axis=1)[:, None] * errors
                - floors[:, None]
            )
            * SCORE_SCALE
        ).astype(np.int64)
        + 1
    )
    group_fine = grouped_max(fine_buckets, group_size)
    group_winners = grouped_winners(fine_buckets, group_size)
    mixed_upper = grouped_max(upper_buckets, group_size)
    mixed_upper[:, hot_groups] = (
        group_fine[:, hot_groups] + ALLOWANCE_BUCKETS_PER_SIDE
    )
    order, stops = stopping_route(mixed_upper, group_fine)
    stage_groups = order[:, :STAGES]
    stage_winners = np.take_along_axis(group_winners, stage_groups, axis=1)
    stage_buckets = np.take_along_axis(group_fine, stage_groups, axis=1)
    best_winners = np.empty_like(stage_winners)
    best_buckets = np.empty_like(stage_buckets)
    gaps = np.empty_like(stage_buckets)
    for row in range(len(hidden)):
        best_winner = -1
        best_bucket = -10**9
        for stage in range(STAGES):
            winner = int(stage_winners[row, stage])
            bucket = int(stage_buckets[row, stage])
            if bucket > best_bucket or (
                bucket == best_bucket and (best_winner < 0 or winner < best_winner)
            ):
                best_winner = winner
                best_bucket = bucket
            best_winners[row, stage] = best_winner
            best_buckets[row, stage] = best_bucket
            next_group = int(order[row, stage + 1])
            gaps[row, stage] = best_bucket - int(mixed_upper[row, next_group])
    first_done: list[int | None] = []
    for row_gaps in gaps:
        indices = np.flatnonzero(row_gaps > STOP_GAP_BUCKETS)
        first_done.append(int(indices[0]) if len(indices) else None)
    active = np.asarray(
        [STAGES if value is None else value + 1 for value in first_done],
        dtype=np.int64,
    )
    final = best_winners[np.arange(len(hidden)), active - 1]
    targets = np.argmax(fine_buckets, axis=1)
    if not np.all(stops <= STAGES):
        raise RuntimeError(
            f"fixture route exceeds {STAGES} stages: {stops.tolist()}"
        )
    return (
        {
            **fixtures,
            "denseWinners": targets.tolist(),
            "unrolledStageGroups": stage_groups.tolist(),
            "unrolledNextUpperGroups": order[:, 1 : STAGES + 1].tolist(),
            "unrolledStageFineWinners": stage_winners.tolist(),
            "unrolledStageFineBuckets": stage_buckets.tolist(),
            "unrolledBestWinners": best_winners.tolist(),
            "unrolledBestBuckets": best_buckets.tolist(),
            "unrolledCertificateGaps": gaps.tolist(),
            "unrolledFirstDoneZeroBased": first_done,
        },
        {
            "fixtures": len(hidden),
            "finalExactWinners": int(np.sum(final == targets)),
            "maximumActiveStages": int(np.max(stops)),
        },
    )


def build_variant(
    row: dict[str, object],
    fixtures: dict[str, object],
    weights: np.ndarray,
    coarse_weights: np.ndarray,
    errors: np.ndarray,
    row_scales: np.ndarray,
    row_bases: np.ndarray,
    fine_weights: np.ndarray,
    fine_codes: np.ndarray,
    fine_reference: dict[str, object],
    input_range: float,
) -> dict[str, object]:
    name = str(row["name"])
    group_size = int(row["groupSize"])
    stride = int(row["scoreStridePx"])
    groups = int(row["groups"])
    hot_groups = tuple(int(value) for value in row["hotGroups"])
    directory = OUTPUT / name
    directory.mkdir(parents=True, exist_ok=True)

    old_group_size = head.GROUP_SIZE
    old_stride = head.SCORE_STRIDE_PX
    old_viewport = head.GROUP_VIEWPORT
    head.GROUP_SIZE = group_size
    head.SCORE_STRIDE_PX = stride
    head.GROUP_VIEWPORT = old_viewport * stride // 4
    try:
        html = head.render_html(row_scales, row_bases, input_range, groups)
        css = head.render_css(
            np.asarray(fixtures["hiddenVectors"], dtype=np.float64),
            row_scales,
            input_range,
            np.asarray(fixtures["scoreFloors"], dtype=np.int64),
            groups,
        )
    finally:
        head.GROUP_SIZE = old_group_size
        head.SCORE_STRIDE_PX = old_stride
        head.GROUP_VIEWPORT = old_viewport

    exact_candidates, fine_markup, fine_css, _fine_bases, _fine_factor = fine_assets(
        fine_codes,
        input_range,
        float(fine_reference["weightScale"]),
        float(fine_reference["displayScale"]),
        group_size,
        groups,
        stride,
    )
    token = 0
    candidate_pattern = re.compile(r'<i class="candidate" style="[^"]+">.*?</i>')

    def replace_candidate(match: re.Match[str]) -> str:
        nonlocal token
        current = token
        token += 1
        if current < row["exactUpperRows"]:
            return exact_candidates[current]
        bound = css_number_up(errors[current] * SCORE_SCALE * stride)
        text = re.sub(
            r"--local-tie:[^\"]+",
            f"--bound-factor:{bound};--local-tie:{group_size - 1 - current % group_size}",
            match.group(0),
            count=1,
        )
        return text

    html = candidate_pattern.sub(replace_candidate, html)
    if token != head.VOCABULARY:
        raise RuntimeError(f"{name}: replaced {token} upper candidates")

    old_transform = f"+ var(--score-offset),{stride}px)"
    new_transform = (
        "+ var(--score-offset) + var(--query-norm)*var(--bound-factor)*1px "
        f"+ {stride}px,{stride}px)"
    )
    if css.count(old_transform) != 1:
        raise RuntimeError(f"{name}: coarse score transform changed")
    css = css.replace(old_transform, new_transform, 1)
    old_tie_step = f"var(--local-tie)/{LAYOUT_UNITS_PER_PX}*1px"
    new_tie_step = (
        f"var(--local-tie)*{head.css_number(stride / group_size)}*1px"
    )
    if css.count(old_tie_step) != 1:
        raise RuntimeError(f"{name}: coarse tie encoding changed")
    css = css.replace(old_tie_step, new_tie_step, 1)
    old_round = "width:calc-size(max-content,calc(round(nearest,"
    if css.count(old_round) != 1:
        raise RuntimeError(f"{name}: coarse round rule changed")
    css = css.replace(
        old_round, "width:calc-size(max-content,calc(round(down,", 1
    )
    css = css.replace(
        'url("score-d',
        'url("../../gpt2-hvar-grid-output-head/score-d',
    )
    norm = " + ".join(
        f"var(--h{dimension})*var(--h{dimension})"
        for dimension in range(head.WIDTH)
    )
    norm_css = (
        '\n@property --query-norm{syntax:"<number>";inherits:true;initial-value:0}'
        f".group-scroller{{--query-norm:sqrt(calc({norm}))}}\n"
    )
    if css.count(".outer-reader{") != 1:
        raise RuntimeError(f"{name}: outer reader marker changed")
    css = css.replace(".outer-reader{", norm_css + ".outer-reader{", 1)

    # The result/fine circuit is emitted after </main>, so it is not a
    # descendant of .model.  Re-emit the fixture transport on every exact
    # stage, matching the retained one-step harness instead of leaving the
    # dynamic font axes and score floor at their zero defaults.
    fine_query_rules = head.output_head.query_rules(
        np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    ).replace(" .model{", " .fine-stage{")
    fine_score_offsets = "\n".join(
        f"body:has(#q{query}:checked) .fine-stage{{--score-offset:"
        f"{-int(floor) * SCORE_SCALE * stride}px}}"
        for query, floor in enumerate(fixtures["scoreFloors"])
    )
    fine_transport_css = fine_query_rules + "\n" + fine_score_offsets + "\n"

    child = router_markup(STAGES, groups, "")
    for stage in range(STAGES - 1, 0, -1):
        child = router_markup(
            stage, groups, stage_markup(stage, fine_markup, child)
        )
    mixed = stage_markup(0, fine_markup, child)
    result_tag = '<output id="result" class="result"></output>'
    if html.count(result_tag) != 1:
        raise RuntimeError(f"{name}: result insertion point changed")
    html = html.replace(
        result_tag,
        f'<output id="result" class="result">{mixed}</output>',
        1,
    ).replace('href="index.css"', 'href="topology.css"', 1)
    html = html.replace(
        "GPT-2-small HVAR + Grid output head",
        f"Mixed exact-upper group-size probe {name}",
    )

    exact_faces = (FINE / "index.css").read_text().split("\n", 1)[0].replace(
        'url("score-',
        'url("../../gpt2-hvar-grid-output-head-global16-twoplane/score-',
    )
    families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(6)
        for plane in ("H", "L")
    )
    hot_selectors = ",".join(
        f".group-wrapper:has(>.group-{group})" for group in hot_groups
    )
    mixed_css = (
        f".mixed-hot-candidate{{font-family:{families};font-size:100px;"
        f"width:calc-size(max-content,calc(round(nearest,(size - "
        f"var(--base)*1px)*var(--factor) + var(--score-offset),{stride}px) + "
        f"var(--local-tie)*{head.css_number(stride / group_size)}*1px))}}"
        + f"{hot_selectors}{{width:calc-size(max-content,calc("
        f"round(down,size,{stride}px) + "
        f"{ALLOWANCE_BUCKETS_PER_SIDE * stride}px))}}"
    )
    selected = ["selected-group-0"]
    routers: list[str] = []
    for stage in range(1, STAGES + 1):
        routers.append(router_css(stage, groups, stride, selected))
        selected.append(f"selected-group-{stage}")
    topology = (
        css
        # render_css intentionally relies on EOF to close the outer-result and
        # group-choice container scopes. This standalone file appends more
        # topology, so close those two inherited scopes explicitly first.
        + "}}"
        + exact_faces
        + fine_transport_css
        + fine_css
        + mixed_css
        + registrations()
        + "".join(routers)
        + "".join(
            stage_css(stage, group_size, stride, hot_groups)
            for stage in range(STAGES)
        )
        + "\n"
    )

    contract, fixture_summary = fixture_contract(
        fixtures,
        coarse_weights,
        errors,
        fine_weights,
        group_size,
        hot_groups,
    )
    if fixture_summary["finalExactWinners"] != fixture_summary["fixtures"]:
        raise RuntimeError(f"{name}: fixture contract lost a winner")
    checks = {
        "groupWrapperCount": len(
            re.findall(r'class="group-wrapper"', html)
        ),
        "upperCandidateCount": len(
            re.findall(r'class="candidate(?: mixed-hot-candidate)?"', html)
        ),
        "exactUpperCandidateCount": len(
            re.findall(r'class="candidate mixed-hot-candidate"', html)
        ),
        "dynamicFineCandidatesPerStage": len(
            re.findall(r'class="fine-candidate"', fine_markup)
        ),
        "scoreStridePerGroupSizeAtLeastOneLayoutUnit": (
            stride / group_size >= 1 / LAYOUT_UNITS_PER_PX
        ),
        "allowanceAppliedAfterGroupMaximum": (
            f"round(down,size,{stride}px) + "
            f"{ALLOWANCE_BUCKETS_PER_SIDE * stride}px" in topology
        ),
        "readbackUsesVariantStride": (
            f"var(--fine-geometry-px-{STAGES - 1})/{stride}" in topology
        ),
        "readbackUsesVariantGroupSize": (
            f"calc({group_size - 1} - var(--fine-tie-code-" in topology
        ),
        "tieEncodingUsesStridePerGroupSize": (
            topology.count(
                f"var(--local-tie)*{head.css_number(stride / group_size)}*1px"
            )
            == 3
        ),
        "fineWinnerUsesVariantGroupSize": (
            f"*{group_size} + var(--fine-local-" in topology
        ),
        "upperWinnerUsesVariantGroupSize": (
            f"--winner:calc(var(--group)*{group_size} + var(--local))"
            in topology
        ),
        "scaledGroupViewport": (
            f"width:{head.GROUP_VIEWPORT * stride // 4}px" in topology
        ),
        "rowsAdded": 0,
        "fineFixtureTransportTargetsEveryStage": (
            fine_transport_css.count(" .fine-stage{")
            == 2 * len(fixtures["hiddenVectors"])
        ),
    }
    if checks["groupWrapperCount"] != groups:
        raise RuntimeError(f"{name}: group wrapper count failed: {checks}")
    if checks["upperCandidateCount"] != head.VOCABULARY:
        raise RuntimeError(f"{name}: upper candidate count failed: {checks}")
    if checks["exactUpperCandidateCount"] != row["exactUpperRows"]:
        raise RuntimeError(f"{name}: exact upper replacement failed: {checks}")
    if checks["dynamicFineCandidatesPerStage"] != group_size:
        raise RuntimeError(f"{name}: dynamic fine count failed: {checks}")
    if not all(
        value
        for key, value in checks.items()
        if key
        not in {
            "upperCandidateCount",
            "groupWrapperCount",
            "exactUpperCandidateCount",
            "dynamicFineCandidatesPerStage",
            "rowsAdded",
        }
    ):
        raise RuntimeError(f"{name}: static transport check failed: {checks}")

    (directory / "index.html").write_text(html)
    (directory / "topology.css").write_text(topology)
    reference = {
        "backend": "mixed-int10-global-int16-variable-group-exact-upper",
        "variant": name,
        "groupSize": group_size,
        "groups": groups,
        "scoreScale": SCORE_SCALE,
        "scoreStridePx": stride,
        "hotGroups": list(hot_groups),
        "exactUpperRows": row["exactUpperRows"],
        "upperRowsAdded": 0,
        "allowanceBucketsPerSide": ALLOWANCE_BUCKETS_PER_SIDE,
        "stopGapBuckets": STOP_GAP_BUCKETS,
        "stages": STAGES,
        "offlineSweep": row,
        "fixtureFeasibility": fixture_summary,
        "certifiedFixtures": contract,
        "staticTransportChecks": checks,
        "assets": {
            "coarseFontDirectory": COARSE_FONT_SOURCE.name,
            "coarseFontFiles": len(list(COARSE_FONT_SOURCE.glob("score-d*.woff2"))),
            "exactFontDirectory": FINE.name,
            "exactFontFiles": len(list(FINE.glob("score-*.woff2"))),
            "fontsCopiedOrRebuilt": False,
        },
        "generatedBytes": {},
    }
    reference_path = directory / "reference.json"
    reference["generatedBytes"] = {
        "index.html": (directory / "index.html").stat().st_size,
        "topology.css": (directory / "topology.css").stat().st_size,
        "reference.json": 0,
    }
    while True:
        reference_path.write_text(json.dumps(reference, indent=2) + "\n")
        size = reference_path.stat().st_size
        if reference["generatedBytes"]["reference.json"] == size:
            break
        reference["generatedBytes"]["reference.json"] = size
    return {
        "variant": name,
        "directory": str(directory.relative_to(ROOT)),
        "fixtureFinalExactWinners": fixture_summary["finalExactWinners"],
        "fixtureCount": fixture_summary["fixtures"],
        "staticTransportChecks": checks,
        "generatedBytes": reference["generatedBytes"],
    }


def main() -> None:
    started = time.perf_counter()
    if not OFFLINE.exists():
        raise FileNotFoundError(
            "run analyze_mixed_precision_group_size_sweep.py first"
        )
    offline = json.loads(OFFLINE.read_text())
    selected = set(offline["pareto"]["browserArtifactNames"])
    rows = [row for row in offline["variants"] if row["name"] in selected]
    if {row["name"] for row in rows} != selected:
        raise RuntimeError("offline browser selection does not resolve")
    if "g256-s4" in selected:
        raise RuntimeError("retained g256-s4 control must not be rebuilt")
    transport_rows = offline.get("transportSweep", {}).get("variants", [])
    transport_names = [str(row["name"]) for row in transport_rows]
    if transport_names != ["g128-s8", "g128-s16", "g128-s32"]:
        raise RuntimeError(
            "append the ordered G128 transport sweep before building"
        )
    rows.extend(transport_rows)

    baseline = json.loads((BASELINE / "reference.json").read_text())
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    fixtures = baseline["certifiedFixtures"]
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    row_scales = np.max(np.abs(weights), axis=1) / (2**9 - 1)
    row_scales[row_scales == 0] = 1.0
    coarse_codes = np.rint(weights / row_scales[:, None]).astype(np.int16)
    coarse_weights = coarse_codes.astype(np.float64) * row_scales[:, None]
    errors = np.linalg.norm(weights - coarse_weights, axis=1)
    row_bases = np.zeros(head.VOCABULARY, dtype=np.int64)
    for start in range(0, head.WIDTH, head.SHARD):
        stop = min(start + head.SHARD, head.WIDTH)
        row_bases += (
            np.sum(np.abs(coarse_codes[:, start:stop].astype(np.int64)), axis=1)
            + 32
        )

    fine_scale = float(fine_reference["weightScale"])
    fine_codes = np.rint(weights / fine_scale).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_scale
    input_range = float(coarse_reference["inputRange"])
    if input_range != float(fine_reference["inputRange"]):
        raise RuntimeError("coarse and fine font coordinate ranges differ")

    built = [
        build_variant(
            row,
            fixtures,
            weights,
            coarse_weights,
            errors,
            row_scales,
            row_bases,
            fine_weights,
            fine_codes,
            fine_reference,
            input_range,
        )
        for row in rows
    ]
    manifest = {
        "status": "prepared-not-run",
        "browserLaunchedByBuilder": False,
        "offlinePareto": offline["pareto"]["variantNames"],
        "candidateVariants": [row["name"] for row in rows],
        "transportSweepVariants": transport_names,
        "transportSweepStopAtFirstSemanticallyExact": True,
        "retainedControl": (
            "experiments/gpt2-mixed-precision-hot2-upper"
        ),
        "pairedHarness": "tools/test_mixed_precision_group_size_probe.mjs",
        "candidates": built,
        "buildSeconds": time.perf_counter() - started,
    }
    (OUTPUT / "browser-artifacts.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
