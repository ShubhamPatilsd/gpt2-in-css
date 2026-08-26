#!/usr/bin/env python3
"""Combine the fast global-int11 head with one selected int16 refinement group."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as baseline


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-cascade"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global11-inline-tie"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
SOURCE_REFERENCE = ROOT / "experiments" / "svg-filter-full-block" / "reference.json"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    source = json.loads(SOURCE_REFERENCE.read_text())
    hidden_vectors = np.stack((
        source["bucket_final_ln_expected"],
        source["bucket_final_ln_expected_alt"],
    )).astype(np.float64)
    if coarse_reference["scoreFloors"] != fine_reference["scoreFloors"]:
        raise RuntimeError("coarse and fine source floors differ")
    if (
        coarse_reference["validation"]["scoreFloors"]
        != fine_reference["validation"]["scoreFloors"]
    ):
        raise RuntimeError("coarse and fine validation floors differ")

    fine_html = (FINE / "index.html").read_text()
    candidates = re.findall(
        r'<i class="candidate"[^>]*>.*?</i>', fine_html
    )
    if len(candidates) != baseline.VOCABULARY:
        raise RuntimeError(f"expected {baseline.VOCABULARY} fine candidates")
    fine_groups = []
    for group in range(coarse_reference["groups"]):
        start = group * baseline.GROUP_SIZE
        stop = min(start + baseline.GROUP_SIZE, baseline.VOCABULARY)
        markup = "".join(
            candidate.replace('class="candidate"', 'class="fine-candidate"')
            for candidate in candidates[start:stop]
        )
        fine_groups.append(
            f'<span class="fine-group fine-group-{group}">{markup}</span>'
        )
    fine_markup = (
        '<span id="fine-stage" class="fine-stage">'
        + "".join(fine_groups)
        + '</span><span class="fine-reader">'
        '<i id="fine-result" class="fine-result"></i></span>'
    )

    coarse_html = (COARSE / "index.html").read_text()
    coarse_body = coarse_html[coarse_html.index('<main id="model"'):]
    result_tag = '<output id="result" class="result"></output>'
    if result_tag not in coarse_body:
        raise RuntimeError("coarse result insertion point missing")
    coarse_body = coarse_body.replace(
        result_tag,
        '<output id="result" class="result">' + fine_markup + "</output>",
        1,
    )
    html = f"""<!doctype html>
<meta charset="utf-8">
<title>Coarse-to-fine GPT-2 CSS output head</title>
<link rel="stylesheet" href="../gpt2-hvar-grid-output-head-global11-inline-tie/index.css">
<link rel="stylesheet" href="index.css">
<input type="radio" name="query" id="q0" checked><input type="radio" name="query" id="q1">
<div class="cascade">{coarse_body}</div>
"""
    (OUTPUT / "index.html").write_text(html)

    fine_css = (FINE / "index.css").read_text()
    font_faces = fine_css.split("\n", 1)[0].replace(
        'url("score-',
        'url("../gpt2-hvar-grid-output-head-global16-twoplane/score-',
    )
    settings = ",".join(
        f'"{baseline.global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{baseline.css_number(fine_reference['inputRange'])})"
        for dimension in range(baseline.WIDTH)
    )
    families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(fine_reference["shards"])
        for plane in ("H", "L")
    )
    group_rules = "".join(
        f".fine-group-{group}{{display:if(style(--group:{group}):grid;else:none)}}"
        for group in range(coarse_reference["groups"])
    )
    query_rules = baseline.output_head.query_rules(hidden_vectors).replace(
        ".model", ".cascade"
    )
    score_offsets = "\n".join(
        f"body:has(#q{query}:checked) .cascade{{--score-offset:"
        f"{-floor * fine_reference['scoreScale'] * fine_reference['scoreStridePx']}px}}"
        for query, floor in enumerate(fine_reference["scoreFloors"])
    )
    css = (
        font_faces + "\n"
        + '@property --fine-local{syntax:"<number>";inherits:true;initial-value:0}'
        + '@property --refined-winner{syntax:"<number>";inherits:true;initial-value:0}'
        + query_rules + "\n" + score_offsets + "\n"
        + f".fine-stage{{position:fixed;left:0;top:-80000px;"
        f"display:block;width:max-content;height:1px;anchor-name:--fine-winner;"
        f"font-family:{families};font-size:100px;line-height:1;"
        f"font-variation-settings:{settings};font-kerning:none}}"
        + ".fine-group{grid-template-columns:max-content;grid-template-rows:1px;"
        + "width:max-content;height:1px}"
        + group_rules
        + ".fine-candidate{grid-area:1/1;display:block;justify-self:start;"
        + "height:1px;overflow:hidden;white-space:pre;font-style:normal;"
        + "width:calc-size(max-content,calc(round(nearest,"
        + "(size - var(--base)*1px) * var(--factor) + var(--score-offset),"
        + "4px) + var(--local-tie)/64*1px))}"
        + ".fine-reader{position:fixed;position-anchor:--fine-winner;"
        + "left:0;top:-70000px;width:anchor-size(--fine-winner width);height:1px;"
        + "container:fine-result/inline-size}"
        + "@container fine-result (width >= 0px){.fine-result{"
        + "--fine-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
        + "--refined-winner:calc(var(--group)*256 + var(--fine-local));"
        + "display:block;width:calc(var(--refined-winner)*1px);height:1px}}\n"
    )
    (OUTPUT / "index.css").write_text(css)

    coarse_groups = (
        np.asarray(coarse_reference["quantizedWinners"], dtype=int) // 256
    )
    dense_groups = np.asarray(fine_reference["denseWinners"], dtype=int) // 256
    validation_coarse_groups = (
        np.asarray(coarse_reference["validation"]["quantizedWinners"], dtype=int)
        // 256
    )
    validation_dense_groups = (
        np.asarray(fine_reference["validation"]["denseWinners"], dtype=int) // 256
    )
    reference = {
        "model": "openai-community/gpt2",
        "backend": "global-int11-coarse-group-plus-global-int16-selected-group",
        "vocabulary": baseline.VOCABULARY,
        "groupSize": baseline.GROUP_SIZE,
        "groups": coarse_reference["groups"],
        "coarseGroupCorrect": bool(np.array_equal(coarse_groups, dense_groups)),
        "denseWinners": fine_reference["denseWinners"],
        "coarseWinners": coarse_reference["quantizedWinners"],
        "refinedWinners": fine_reference["quantizedWinners"],
        "winnerBuckets": fine_reference["winnerBuckets"],
        "validation": {
            "tokenIds": fine_reference["validation"]["tokenIds"],
            "hiddenVectors": fine_reference["validation"]["hiddenVectors"],
            "scoreFloors": fine_reference["validation"]["scoreFloors"],
            "denseWinners": fine_reference["validation"]["denseWinners"],
            "coarseWinners": coarse_reference["validation"]["quantizedWinners"],
            "refinedWinners": fine_reference["validation"]["quantizedWinners"],
            "winnerBuckets": fine_reference["validation"]["winnerBuckets"],
            "coarseGroupCorrect": bool(np.array_equal(
                validation_coarse_groups, validation_dense_groups
            )),
        },
        "precisionScreen": {
            "samples": 256,
            "coarseGroupMatches": 256,
            "coarseWinnerMatches": 255,
            "fineWinnerMatches": 256,
        },
        "coarseRuntimeBytes": (
            coarse_reference["htmlBytes"] + coarse_reference["cssBytes"]
            + coarse_reference["fontBytes"]
        ),
        "fineFontBytes": fine_reference["fontBytes"],
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    reference["totalRuntimeBytes"] = (
        reference["htmlBytes"] + reference["cssBytes"]
        + coarse_reference["cssBytes"] + coarse_reference["fontBytes"]
        + fine_reference["fontBytes"]
    )
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items() if key != "validation"
    }, indent=2))


if __name__ == "__main__":
    main()
