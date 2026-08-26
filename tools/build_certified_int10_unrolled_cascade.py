#!/usr/bin/env python3
"""Build an N-stage best-first certified output-head cascade."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
SOURCE = ROOT / "experiments" / SOURCE_NAME
STAGES = int(os.environ.get("GPT2_CERTIFIED_STAGES", "6"))
if not 2 <= STAGES <= 197:
    raise ValueError("GPT2_CERTIFIED_STAGES must be between 2 and 197")
SLACK_BUCKETS = int(os.environ.get("GPT2_CERTIFIED_SLACK_BUCKETS", "24"))
GATE_LATER_STAGES = os.environ.get("GPT2_CERTIFIED_GATE", "0") == "1"
INCREMENTAL_MASK = os.environ.get("GPT2_CERTIFIED_INCREMENTAL_MASK", "0") == "1"
PACKED_MASK = os.environ.get("GPT2_CERTIFIED_PACKED_MASK", "0") == "1"
if INCREMENTAL_MASK and PACKED_MASK:
    raise ValueError("choose only one incremental mask representation")
MASK_CHUNK_BITS = 16
DEFAULT_OUTPUT_NAME = (
    f"gpt2-hvar-grid-output-head-certified-int10-unrolled{STAGES}"
    + ("-gated" if GATE_LATER_STAGES else "")
    + ("-linear-mask" if INCREMENTAL_MASK else "")
    + ("-packed-mask" if PACKED_MASK else "")
)
OUTPUT_NAME = os.environ.get(
    "GPT2_CERTIFIED_CASCADE_DIR",
    DEFAULT_OUTPUT_NAME,
)
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)


def property_registration(name: str) -> str:
    return f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'


def fine_markup(stage: int, candidates: str, child: str) -> str:
    return (
        f'<span id="fine-stage-{stage}" class="fine-stage fine-stage-{stage}">'
        + candidates
        + f'</span><span class="fine-reader fine-reader-{stage}">'
        f'<i id="fine-result-{stage}" class="fine-result-{stage}">{child}</i>'
        '</span>'
    )


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
        + '</output></span></span></span>'
    )


def router_css(stage: int, groups: int, selected_properties: list[str]) -> str:
    source_bank = "a" if stage % 2 == 1 else "b"
    target_bank = "b" if source_bank == "a" else "a"

    def mask_value(group: int) -> str:
        if PACKED_MASK:
            chunk = group // MASK_CHUNK_BITS
            divisor = 2 ** (group % MASK_CHUNK_BITS)
            return (
                "calc(1 - mod(round(down,"
                f"var(--visited-{source_bank}-{chunk})/{divisor},1),2))"
            )
        if INCREMENTAL_MASK:
            return f"var(--unvisited-{source_bank}-{group})"
        selected_terms = ",".join(
            f"abs(var(--{name}) - {group})" for name in selected_properties
        )
        return f"clamp(0,min({selected_terms}),1)"

    source_rules = "".join(
        f".upper-source-{stage}-{group}{{"
        f"--upper-mask-{stage}:{mask_value(group)};"
        f"position-anchor:--score-group-{group};"
        f"anchor-name:--upper-source-{stage}-{group};"
        f"width:calc(anchor-size(--score-group-{group} width) * "
        f"var(--upper-mask-{stage}))}}"
        for group in range(groups)
    )
    source_sizes = ",".join(
        f"anchor-size(--upper-source-{stage}-{group} width)"
        for group in range(groups)
    )
    match_rules = "".join(
        f".upper-match-{stage}-{group}{{"
        f"position-anchor:--upper-source-{stage}-{group};"
        f"anchor-name:--upper-match-{stage}-{group};"
        f"width:calc(clamp(0px,anchor-size(--upper-source-{stage}-{group} width) - "
        f"(var(--upper-bucket-{stage}) - .5)*4px,1px)*{groups - group})}}"
        for group in range(groups)
    )
    match_sizes = ",".join(
        f"anchor-size(--upper-match-{stage}-{group} width)"
        for group in range(groups)
    )
    threshold = 2 * SLACK_BUCKETS
    next_masks = ""
    if PACKED_MASK and stage < STAGES:
        chunks = math.ceil(groups / MASK_CHUNK_BITS)
        selected_chunk = (
            f"round(down,var(--remaining-group-{stage})/"
            f"{MASK_CHUNK_BITS},1)"
        )
        selected_bit = (
            f"pow(2,mod(var(--remaining-group-{stage}),{MASK_CHUNK_BITS}))"
        )
        next_masks = "".join(
            f"--visited-{target_bank}-{chunk}:calc("
            f"var(--visited-{source_bank}-{chunk}) + "
            f"clamp(0,1 - abs({selected_chunk} - {chunk}),1)*"
            f"{selected_bit});"
            for chunk in range(chunks)
        )
    elif INCREMENTAL_MASK and stage < STAGES:
        next_masks = "".join(
            f"--unvisited-{target_bank}-{group}:calc("
            f"var(--unvisited-{source_bank}-{group})*"
            f"clamp(0,abs(var(--remaining-group-{stage}) - {group}),1));"
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
        + source_rules
        + f".upper-max-{stage}{{position-anchor:--upper-source-{stage}-0;"
        f"anchor-name:--upper-max-anchor-{stage};width:max({source_sizes})}}"
        + f".upper-reader-{stage}{{position-anchor:--upper-max-anchor-{stage};"
        f"width:anchor-size(--upper-max-anchor-{stage} width);"
        f"container:upper-result-{stage}/inline-size}}"
        + f"@container upper-result-{stage} (width >= 0px){{"
        f".upper-selection-{stage}{{--upper-bucket-{stage}:"
        "round(down,100cqi/4px,1)}"
        + match_rules
        + f".upper-group-choice-{stage}{{position-anchor:--upper-match-{stage}-0;"
        f"anchor-name:--upper-group-choice-anchor-{stage};"
        f"width:max({match_sizes})}}"
        + f".upper-group-reader-{stage}{{"
        f"position-anchor:--upper-group-choice-anchor-{stage};"
        f"width:anchor-size(--upper-group-choice-anchor-{stage} width);"
        f"container:upper-group-result-{stage}/inline-size}}"
        + f"@container upper-group-result-{stage} (width >= 0px){{"
        f".remaining-result-{stage}{{{next_masks}"
        f"--remaining-group-{stage}:calc({groups} - "
        "round(nearest,100cqi/1px,1));"
        f"--certificate-gap-{stage - 1}:calc(var(--best-bucket-{stage - 1}) - "
        f"var(--upper-bucket-{stage}));"
        f"--done-{stage - 1}:clamp(0,sign(var(--certificate-gap-{stage - 1}) - "
        f"{threshold + 1}) + 1,1);display:block;"
        f"width:calc(var(--remaining-group-{stage})*1px);height:1px}}}}}}"
    )


def fine_css(stage: int) -> str:
    previous = stage - 1
    return (
        f".fine-stage-{stage}{{--group:var(--remaining-group-{stage});"
        f"top:{-50_000 + stage * 20}px;anchor-name:--fine-winner-{stage}}}"
        f".fine-reader-{stage}{{position-anchor:--fine-winner-{stage};"
        f"top:{-49_000 + stage * 20}px;"
        f"width:anchor-size(--fine-winner-{stage} width);"
        f"container:fine-result-{stage}/inline-size}}"
        f"@container fine-result-{stage} (width >= 0px){{.fine-result-{stage}{{"
        f"--fine-bucket-{stage}:round(down,100cqi/4px,1);"
        f"--fine-local-{stage}:calc(255 - "
        "round(nearest,mod(100cqi,4px)/1px*64,1));"
        f"--fine-winner-{stage}:calc(var(--remaining-group-{stage})*256 + "
        f"var(--fine-local-{stage}));"
        f"--score-delta-{stage}:calc(var(--fine-bucket-{stage}) - "
        f"var(--best-bucket-{previous}));"
        f"--use-stage-{stage}:max(clamp(0,sign(var(--score-delta-{stage})),1),"
        f"calc((1 - abs(sign(var(--score-delta-{stage})))) * "
        f"clamp(0,sign(var(--best-winner-{previous}) - "
        f"var(--fine-winner-{stage})),1)));"
        f"--best-winner-{stage}:calc(var(--best-winner-{previous}) * "
        f"(1 - var(--use-stage-{stage})) + var(--fine-winner-{stage}) * "
        f"var(--use-stage-{stage}));"
        f"--best-bucket-{stage}:max(var(--best-bucket-{previous}),"
        f"var(--fine-bucket-{stage}));display:block;"
        f"width:calc(var(--best-winner-{stage})*1px);height:1px}}}}"
    )


def fine_gate_css(stage: int) -> str:
    """Prune this stage and its nested descendants once the prior result is safe."""
    previous = stage - 1
    condition = f"style(--done-{previous}:1)"
    return (
        f".fine-stage-{stage}{{display:if({condition}:none;else:grid)}}"
        f".fine-reader-{stage}{{display:if({condition}:none;else:block)}}"
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    fixtures = reference["certifiedFixtures"]
    groups = int(reference["groups"])
    html = (SOURCE / "index.html").read_text()
    stage_marker = '<span id="fine-stage" class="fine-stage">'
    stage_start = html.index(stage_marker) + len(stage_marker)
    stage_end = html.index('</span><span class="fine-reader">', stage_start)
    candidate_markup = html[stage_start:stage_end]

    child = router_markup(STAGES, groups, "")
    for stage in range(STAGES - 1, 0, -1):
        child = router_markup(
            stage,
            groups,
            fine_markup(stage, candidate_markup, child),
        )
    result_marker = '<i id="fine-result" class="fine-result"></i>'
    if html.count(result_marker) != 1:
        raise RuntimeError("first fine result insertion point missing")
    html = html.replace(
        result_marker,
        f'<i id="fine-result" class="fine-result">{child}</i>',
        1,
    ).replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        f"Certified int10 {STAGES}-stage unrolled cascade",
        1,
    )

    registrations = [
        property_registration("best-bucket-0"),
        property_registration("best-winner-0"),
    ]
    for stage in range(1, STAGES + 1):
        for name in (
            f"upper-mask-{stage}", f"upper-bucket-{stage}",
            f"remaining-group-{stage}", f"certificate-gap-{stage - 1}",
            f"done-{stage - 1}",
        ):
            registrations.append(property_registration(name))
        if stage < STAGES:
            for name in (
                f"fine-bucket-{stage}", f"fine-local-{stage}",
                f"fine-winner-{stage}", f"score-delta-{stage}",
                f"use-stage-{stage}", f"best-bucket-{stage}",
                f"best-winner-{stage}",
            ):
                registrations.append(property_registration(name))

    css_parts = [
        (SOURCE / "index.css").read_text(),
        "".join(registrations),
        ".fine-result{--best-bucket-0:var(--fine-bucket);"
        "--best-winner-0:var(--refined-winner)}",
    ]
    if PACKED_MASK:
        chunks = math.ceil(groups / MASK_CHUNK_BITS)
        selected_chunk = f"round(down,var(--group)/{MASK_CHUNK_BITS},1)"
        selected_bit = f"pow(2,mod(var(--group),{MASK_CHUNK_BITS}))"
        initial_masks = "".join(
            f"--visited-a-{chunk}:calc("
            f"clamp(0,1 - abs({selected_chunk} - {chunk}),1)*"
            f"{selected_bit});"
            for chunk in range(chunks)
        )
        css_parts.append(f".fine-result{{{initial_masks}}}")
    elif INCREMENTAL_MASK:
        initial_masks = "".join(
            f"--unvisited-a-{group}:clamp(0,abs(var(--group) - {group}),1);"
            for group in range(groups)
        )
        css_parts.append(f".fine-result{{{initial_masks}}}")
    selected_properties = ["group"]
    for stage in range(1, STAGES + 1):
        css_parts.append(router_css(stage, groups, selected_properties))
        selected_properties.append(f"remaining-group-{stage}")
        if stage < STAGES:
            css_parts.append(fine_css(stage))
            if GATE_LATER_STAGES:
                css_parts.append(fine_gate_css(stage))
    css = "".join(css_parts) + "\n"

    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[:head.VOCABULARY], dtype=np.float64
    )
    coarse_scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    coarse_scales[coarse_scales == 0] = 1.0
    coarse_weights = np.rint(weights / coarse_scales[:, None]) * coarse_scales[:, None]
    error_norms = np.linalg.norm(weights - coarse_weights, axis=1)
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=int)
    upper_scores = (
        hidden @ coarse_weights.T
        + np.linalg.norm(hidden, axis=1)[:, None] * error_norms
    )
    upper_buckets = np.floor(
        (upper_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(int) + 1
    group_upper = np.full((len(hidden), groups), -1, dtype=int)
    for group in range(groups):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        group_upper[:, group] = np.max(upper_buckets[:, start:stop], axis=1)
    group_order = np.argsort(-group_upper, axis=1, kind="stable")

    fine_reference = json.loads(FINE_REFERENCE.read_text())
    fine_codes = np.rint(weights / fine_reference["weightScale"]).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_reference["weightScale"]
    fine_scores = hidden @ fine_weights.T
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * fine_reference["scoreScale"]
    ).astype(int)
    stage_groups = group_order[:, :STAGES]
    stage_winners = np.empty((len(hidden), STAGES), dtype=int)
    stage_buckets = np.empty((len(hidden), STAGES), dtype=int)
    best_winners = np.empty_like(stage_winners)
    best_buckets = np.empty_like(stage_buckets)
    certificate_gaps = np.empty((len(hidden), STAGES), dtype=int)
    for fixture in range(len(hidden)):
        best_winner = -1
        best_bucket = -1
        for stage in range(STAGES):
            group = int(stage_groups[fixture, stage])
            start = group * head.GROUP_SIZE
            stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
            winner = start + int(np.argmax(fine_buckets[fixture, start:stop]))
            bucket = int(fine_buckets[fixture, winner])
            stage_winners[fixture, stage] = winner
            stage_buckets[fixture, stage] = bucket
            if bucket > best_bucket or (
                bucket == best_bucket and (best_winner < 0 or winner < best_winner)
            ):
                best_winner = winner
                best_bucket = bucket
            best_winners[fixture, stage] = best_winner
            best_buckets[fixture, stage] = best_bucket
            next_group = int(group_order[fixture, stage + 1])
            certificate_gaps[fixture, stage] = (
                best_bucket - int(group_upper[fixture, next_group])
            )
    first_done = []
    threshold = 2 * SLACK_BUCKETS
    for gaps in certificate_gaps:
        indices = np.flatnonzero(gaps > threshold)
        first_done.append(int(indices[0]) if len(indices) else None)

    fixtures.update({
        "unrolledStageGroups": stage_groups.tolist(),
        "unrolledNextUpperGroups": group_order[:, 1:STAGES + 1].tolist(),
        "unrolledStageFineWinners": stage_winners.tolist(),
        "unrolledStageFineBuckets": stage_buckets.tolist(),
        "unrolledBestWinners": best_winners.tolist(),
        "unrolledBestBuckets": best_buckets.tolist(),
        "unrolledCertificateGaps": certificate_gaps.tolist(),
        "unrolledFirstDoneZeroBased": first_done,
    })
    updated = {
        **reference,
        "backend": f"certified-rowwise-int10-unrolled-{STAGES}-group-cascade",
        "source": SOURCE_NAME,
        "exactStages": STAGES,
        "stageGating": GATE_LATER_STAGES,
        "maskStrategy": (
            "packed-16-bit-two-bank" if PACKED_MASK else
            "incremental-two-bank" if INCREMENTAL_MASK else
            "expanded-history"
        ),
        "scoreSlackBucketsPerSide": SLACK_BUCKETS,
        "routerElementsPerStage": groups * 2 + 5,
        "fineCandidateElementsPerAdditionalStage": head.GROUP_SIZE,
        "certifiedFixtures": fixtures,
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    updated["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    updated["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(updated, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "exactStages": STAGES,
        "scoreSlackBucketsPerSide": SLACK_BUCKETS,
        "htmlBytes": updated["htmlBytes"],
        "cssBytes": updated["cssBytes"],
        "fixturesCertifiedWithinUnroll": sum(value is not None for value in first_done),
        "denseWinnersCovered": int(np.sum(
            best_winners[:, -1] == np.asarray(fixtures["denseWinners"])
        )),
        "firstDoneZeroBased": first_done,
    }, indent=2))


if __name__ == "__main__":
    main()
