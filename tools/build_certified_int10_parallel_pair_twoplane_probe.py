#!/usr/bin/env python3
"""Replace the failed packed pair merge with score/group then token planes."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-int10-parallel-pair"
OUTPUT_NAME = SOURCE_NAME + "-twoplane"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
GROUPS = 197
SCORE_STRIDE_PX = 1024
GROUP_TIE_STRIDE_PX = 4
CHROME_LAYOUT_LIMIT_PX = 33_554_428


def registration(name: str) -> str:
    return f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    if int(reference["groups"]) != GROUPS:
        raise RuntimeError("unexpected group count")

    html = (SOURCE / "index.html").read_text()
    old_result = '<output id="pair-result" class="pair-result"></output>'
    new_result = (
        '<output id="pair-score-result" class="pair-score-result">'
        '<i id="pair-token-choice" class="pair-token-choice"></i>'
        '<span id="pair-token-reader" class="pair-token-reader">'
        '<output id="pair-result" class="pair-token-result"></output>'
        '</span></output>'
    )
    if html.count(old_result) != 1:
        raise RuntimeError("one-plane merge result insertion point missing")
    html = html.replace(old_result, new_result, 1).replace(
        "Certified int10 parallel two-group exact probe",
        "Certified int10 parallel two-group exact two-plane merge probe",
        1,
    )

    # Later declarations replace the packed token subfield on the existing
    # score carriers. Four pixels per group leaves a 788px tie band, below the
    # 1024px score stride, while staying well above measured float-width loss.
    css = (SOURCE / "index.css").read_text() + "".join([
        registration("pair-winning-group"),
        registration("pair-use-second"),
        ".fine-result{anchor-name:--pair-token-anchor-1}",
        ".fine-result-2{anchor-name:--pair-token-anchor-2}",
        ".pair-carrier-1{width:calc(var(--fine-bucket)*1024px + "
        f"({GROUPS} - var(--group))*{GROUP_TIE_STRIDE_PX}px)}}",
        ".pair-carrier-2{width:calc(var(--fine-bucket-2)*1024px + "
        f"({GROUPS} - var(--pair-group))*{GROUP_TIE_STRIDE_PX}px)}}",
        ".pair-score-result,.pair-token-choice,.pair-token-reader,.pair-token-result{"
        "position:fixed;left:0;top:-58000px;height:1px}",
        "@container pair-max-readback (width >= 0px){.pair-score-result{"
        "--pair-bucket:round(down,100cqi/1024px,1);"
        f"--pair-winning-group:calc({GROUPS} - round(nearest,"
        f"mod(100cqi,{SCORE_STRIDE_PX}px)/{GROUP_TIE_STRIDE_PX}px,1));"
        "--pair-use-second:clamp(0,abs(var(--pair-winning-group) - var(--group)),1);"
        "display:block;width:calc(var(--pair-winning-group)*1px);height:1px}}",
        ".pair-token-choice{anchor-name:--pair-token-choice-anchor;"
        "width:calc(anchor-size(--pair-token-anchor-1 width) * "
        "(1 - var(--pair-use-second)) + anchor-size(--pair-token-anchor-2 width) * "
        "var(--pair-use-second))}",
        ".pair-token-reader{position-anchor:--pair-token-choice-anchor;"
        "width:anchor-size(--pair-token-choice-anchor width);"
        "container:pair-token-readback/inline-size}",
        "@container pair-token-readback (width >= 0px){.pair-token-result{"
        "--pair-winner:round(nearest,100cqi/1px,1);display:block;"
        "width:calc(var(--pair-winner)*1px);height:1px}}",
        "\n",
    ])

    fixtures = reference["certifiedFixtures"]
    geometry_widths = []
    winning_groups = []
    for bucket, winner in zip(
        fixtures["parallelPairBuckets"], fixtures["parallelPairWinners"], strict=True
    ):
        group = int(winner) // 256
        winning_groups.append(group)
        geometry_widths.append(
            int(bucket) * SCORE_STRIDE_PX
            + (GROUPS - group) * GROUP_TIE_STRIDE_PX
        )
    maximum = max(geometry_widths)
    if maximum >= CHROME_LAYOUT_LIMIT_PX:
        raise RuntimeError("fixture score/group geometry exceeds Chrome layout limit")
    fixtures["twoplaneWinningGroups"] = winning_groups
    fixtures["twoplaneScoreGroupGeometryWidthsPx"] = geometry_widths
    updated = {
        **reference,
        "backend": "certified-rowwise-int10-parallel-pair-two-plane-merge-probe",
        "source": SOURCE_NAME,
        "mergePlanes": ["score-bucket-plus-group-tie", "selected-token-anchor"],
        "scoreGeometryPixelsPerBucket": SCORE_STRIDE_PX,
        "groupTiePixelsPerGroup": GROUP_TIE_STRIDE_PX,
        "maxGroupTieBandPixels": GROUPS * GROUP_TIE_STRIDE_PX,
        "maxFixtureMergeGeometryPixels": maximum,
        "chromeLayoutLimitPixels": CHROME_LAYOUT_LIMIT_PX,
        "certifiedFixtures": fixtures,
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    updated["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    updated["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(updated, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "mergePlanes": updated["mergePlanes"],
        "maxGroupTieBandPixels": updated["maxGroupTieBandPixels"],
        "maxFixtureMergeGeometryPixels": maximum,
        "chromeLayoutHeadroomPixels": CHROME_LAYOUT_LIMIT_PX - maximum,
        "fixtures": len(geometry_widths),
    }, indent=2))


if __name__ == "__main__":
    main()
