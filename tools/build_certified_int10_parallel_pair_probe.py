#!/usr/bin/env python3
"""Build a two-group exact probe with parallel first-score and next-group branches."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
OUTPUT_NAME = "gpt2-hvar-grid-output-head-certified-int10-parallel-pair"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)
SCORE_GEOMETRY_PX = 1024
TOKEN_TIE_PX = 1 / 64
# Blink's LayoutUnit clamp is just under 2**25 CSS px. Keep the fixture probe well below it.
CHROME_LAYOUT_LIMIT_PX = 33_554_428


def property_registration(name: str) -> str:
    return f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    fixtures = reference["certifiedFixtures"]
    groups = int(reference["groups"])
    html = (SOURCE / "index.html").read_text()

    stage_marker = '<span id="fine-stage" class="fine-stage">'
    stage_start = html.index(stage_marker) + len(stage_marker)
    stage_end = html.index('</span><span class="fine-reader">', stage_start)
    candidates = html[stage_start:stage_end]

    sources = "".join(
        f'<i class="pair-source pair-source-{group}"></i>'
        for group in range(groups)
    )
    matches = "".join(
        f'<i class="pair-match pair-match-{group}"></i>'
        for group in range(groups)
    )
    # This whole branch is a sibling of the original exact stage/reader. It can
    # therefore route while the original exact font is shaping.
    second_branch = (
        f'<span class="pair-sources">{sources}</span>'
        '<i class="pair-upper"></i><span class="pair-upper-reader">'
        f'<span class="pair-selection">{matches}'
        '<i class="pair-group-choice"></i><span class="pair-group-reader">'
        '<output id="pair-group-result" class="pair-group-result">'
        '<span id="fine-stage-2" class="fine-stage fine-stage-2">'
        f'{candidates}</span><span class="fine-reader fine-reader-2">'
        '<i id="fine-result-2" class="fine-result-2">'
        '<i id="pair-carrier-2" class="pair-carrier-2"></i>'
        '</i></span></output></span></span></span>'
    )
    merge = (
        '<i id="pair-max" class="pair-max"></i>'
        '<span id="pair-max-reader" class="pair-max-reader">'
        '<output id="pair-result" class="pair-result"></output></span>'
    )

    first_result = '<i id="fine-result" class="fine-result"></i>'
    if html.count(first_result) != 1:
        raise RuntimeError("first fine result insertion point missing")
    html = html.replace(
        first_result,
        '<i id="fine-result" class="fine-result">'
        '<i id="pair-carrier-1" class="pair-carrier-1"></i></i>',
        1,
    )
    tail = '</span></output></div>\n'
    if html.count(tail) != 1:
        raise RuntimeError("result sibling insertion point missing")
    html = html.replace(
        tail,
        f'</span>{second_branch}{merge}</output></div>\n',
        1,
    ).replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Certified int10 parallel two-group exact probe",
        1,
    )

    source_rules = "".join(
        f".pair-source-{group}{{"
        f"--pair-mask:clamp(0,abs(var(--group) - {group}),1);"
        f"position-anchor:--score-group-{group};"
        f"anchor-name:--pair-source-{group};"
        f"width:calc(anchor-size(--score-group-{group} width) * var(--pair-mask))}}"
        for group in range(groups)
    )
    source_sizes = ",".join(
        f"anchor-size(--pair-source-{group} width)" for group in range(groups)
    )
    match_rules = "".join(
        f".pair-match-{group}{{position-anchor:--pair-source-{group};"
        f"anchor-name:--pair-match-{group};"
        f"width:calc(clamp(0px,anchor-size(--pair-source-{group} width) - "
        f"(var(--pair-upper-bucket) - .5)*4px,1px)*{groups - group})}}"
        for group in range(groups)
    )
    match_sizes = ",".join(
        f"anchor-size(--pair-match-{group} width)" for group in range(groups)
    )
    registrations = "".join(property_registration(name) for name in (
        "pair-mask", "pair-upper-bucket", "pair-group",
        "fine-bucket-2", "fine-local-2", "fine-winner-2",
        "pair-bucket", "pair-winner",
    ))
    fixed = (
        ".pair-source,.pair-upper,.pair-upper-reader,.pair-match,"
        ".pair-group-choice,.pair-group-reader,.pair-group-result,"
        ".pair-carrier-1,.pair-carrier-2,.pair-max,.pair-max-reader,.pair-result{"
        "position:fixed;left:0;top:-60000px;height:1px}"
    )
    router_css = (
        source_rules
        + f".pair-upper{{position-anchor:--pair-source-0;"
        f"anchor-name:--pair-upper-anchor;width:max({source_sizes})}}"
        ".pair-upper-reader{position-anchor:--pair-upper-anchor;"
        "width:anchor-size(--pair-upper-anchor width);"
        "container:pair-upper-result/inline-size}"
        "@container pair-upper-result (width >= 0px){"
        ".pair-selection{--pair-upper-bucket:round(down,100cqi/4px,1)}"
        + match_rules
        + ".pair-group-choice{position-anchor:--pair-match-0;"
        f"anchor-name:--pair-group-choice-anchor;width:max({match_sizes})}}"
        ".pair-group-reader{position-anchor:--pair-group-choice-anchor;"
        "width:anchor-size(--pair-group-choice-anchor width);"
        "container:pair-group-readback/inline-size}"
        "@container pair-group-readback (width >= 0px){.pair-group-result{"
        f"--pair-group:calc({groups} - round(nearest,100cqi/1px,1));"
        "display:block;width:calc(var(--pair-group)*1px);height:1px}}}"
    )
    second_css = (
        ".fine-stage-2{--group:var(--pair-group);top:-50000px;"
        "anchor-name:--fine-winner-2}"
        ".fine-reader-2{position-anchor:--fine-winner-2;top:-49000px;"
        "width:anchor-size(--fine-winner-2 width);"
        "container:fine-result-2/inline-size}"
        "@container fine-result-2 (width >= 0px){.fine-result-2{"
        "--fine-bucket-2:round(down,100cqi/4px,1);"
        "--fine-local-2:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
        "--fine-winner-2:calc(var(--pair-group)*256 + var(--fine-local-2));"
        "display:block;width:calc(var(--fine-winner-2)*1px);height:1px}}"
    )
    # A score bucket dominates all token tie values: the full tie range is
    # 785.25px, below the 1024px score stride. Smaller token ids are wider.
    merge_css = (
        ".pair-carrier-1{anchor-name:--pair-carrier-anchor-1;"
        f"width:calc(var(--fine-bucket)*{SCORE_GEOMETRY_PX}px + "
        f"({head.VOCABULARY} - var(--refined-winner))*{TOKEN_TIE_PX}px)}}"
        ".pair-carrier-2{anchor-name:--pair-carrier-anchor-2;"
        f"width:calc(var(--fine-bucket-2)*{SCORE_GEOMETRY_PX}px + "
        f"({head.VOCABULARY} - var(--fine-winner-2))*{TOKEN_TIE_PX}px)}}"
        ".pair-max{position-anchor:--pair-carrier-anchor-1;"
        "anchor-name:--pair-max-anchor;"
        "width:max(anchor-size(--pair-carrier-anchor-1 width),"
        "anchor-size(--pair-carrier-anchor-2 width))}"
        ".pair-max-reader{position-anchor:--pair-max-anchor;"
        "width:anchor-size(--pair-max-anchor width);"
        "container:pair-max-readback/inline-size}"
        "@container pair-max-readback (width >= 0px){.pair-result{"
        f"--pair-bucket:round(down,100cqi/{SCORE_GEOMETRY_PX}px,1);"
        f"--pair-winner:calc({head.VOCABULARY} - round(nearest,"
        f"mod(100cqi,{SCORE_GEOMETRY_PX}px)/1px*64,1));"
        "display:block;width:calc(var(--pair-winner)*1px);height:1px}}"
    )
    css = (
        (SOURCE / "index.css").read_text()
        + registrations + fixed + router_css + second_css + merge_css + "\n"
    )

    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[:head.VOCABULARY], dtype=np.float64
    )
    scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    scales[scales == 0] = 1.0
    coarse_weights = np.rint(weights / scales[:, None]) * scales[:, None]
    error_norms = np.linalg.norm(weights - coarse_weights, axis=1)
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=int)
    upper = hidden @ coarse_weights.T + np.linalg.norm(hidden, axis=1)[:, None] * error_norms
    upper_buckets = np.floor((upper - floors[:, None]) * head.SCORE_SCALE).astype(int) + 1
    group_upper = np.full((len(hidden), groups), -1, dtype=int)
    for group in range(groups):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        group_upper[:, group] = np.max(upper_buckets[:, start:stop], axis=1)
    group_order = np.argsort(-group_upper, axis=1, kind="stable")
    if not np.array_equal(group_order[:, 0], np.asarray(fixtures["upperGroups"])):
        raise RuntimeError("offline first group disagrees with source probe")

    fine_reference = json.loads(FINE_REFERENCE.read_text())
    fine_codes = np.rint(weights / fine_reference["weightScale"]).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_reference["weightScale"]
    fine_buckets = np.rint(
        (hidden @ fine_weights.T - floors[:, None]) * fine_reference["scoreScale"]
    ).astype(int)
    second_groups = group_order[:, 1].astype(int)
    second_winners: list[int] = []
    second_buckets: list[int] = []
    pair_winners: list[int] = []
    pair_buckets: list[int] = []
    geometry_widths: list[float] = []
    for fixture, group in enumerate(second_groups):
        start = int(group) * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        second_winner = start + int(np.argmax(fine_buckets[fixture, start:stop]))
        second_bucket = int(fine_buckets[fixture, second_winner])
        first_winner = int(fixtures["selectedGroupFineWinners"][fixture])
        first_bucket = int(fixtures["selectedGroupFineBuckets"][fixture])
        if second_bucket > first_bucket or (
            second_bucket == first_bucket and second_winner < first_winner
        ):
            pair_winner, pair_bucket = second_winner, second_bucket
        else:
            pair_winner, pair_bucket = first_winner, first_bucket
        second_winners.append(second_winner)
        second_buckets.append(second_bucket)
        pair_winners.append(pair_winner)
        pair_buckets.append(pair_bucket)
        geometry_widths.append(
            pair_bucket * SCORE_GEOMETRY_PX
            + (head.VOCABULARY - pair_winner) * TOKEN_TIE_PX
        )

    fixtures.update({
        "parallelSecondGroups": second_groups.tolist(),
        "parallelSecondFineWinners": second_winners,
        "parallelSecondFineBuckets": second_buckets,
        "parallelPairWinners": pair_winners,
        "parallelPairBuckets": pair_buckets,
        "parallelPairGeometryWidthsPx": geometry_widths,
    })
    max_geometry = max(geometry_widths)
    if max_geometry >= CHROME_LAYOUT_LIMIT_PX:
        raise RuntimeError("fixture merge geometry exceeds the Chrome layout limit")
    updated = {
        **reference,
        "backend": "certified-rowwise-int10-parallel-two-group-exact-probe",
        "source": SOURCE_NAME,
        "branchStructure": "sibling first-exact and next-group-router branches",
        "scoreGeometryPixelsPerBucket": SCORE_GEOMETRY_PX,
        "tokenTiePixelsPerId": TOKEN_TIE_PX,
        "chromeLayoutLimitPixels": CHROME_LAYOUT_LIMIT_PX,
        "maxFixtureMergeGeometryPixels": max_geometry,
        "certifiedFixtures": fixtures,
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    updated["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    updated["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(updated, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "branchStructure": updated["branchStructure"],
        "maxFixtureMergeGeometryPixels": max_geometry,
        "chromeLayoutHeadroomPixels": CHROME_LAYOUT_LIMIT_PX - max_geometry,
        "denseWinnersCoveredByPair": int(np.sum(
            np.asarray(pair_winners) == np.asarray(fixtures["denseWinners"])
        )),
        "fixtures": len(hidden),
    }, indent=2))


if __name__ == "__main__":
    main()
