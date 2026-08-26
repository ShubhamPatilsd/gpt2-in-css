#!/usr/bin/env python3
"""Build a 256-node coarse-to-fine GPT-2 output head.

The coarse global-int11 head selects a 256-token group. Each of the 256 fine
candidate nodes then uses CSS if(style()) to select the corresponding token's
global-int16 glyph string and base correction. This keeps the accurate two-
plane math while avoiding one dormant fine DOM node per vocabulary token.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as baseline
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
PHASES = int(os.environ.get("GPT2_CASCADE_DITHER_PHASES", "1"))
ACTIVE_LOCALS = tuple(
    int(value) for value in os.environ.get("GPT2_CASCADE_ACTIVE_LOCALS", "").split(",")
    if value
)
NEAR_SELECTOR = os.environ.get("GPT2_CASCADE_NEAR_SELECTOR", "0") == "1"
NEAR_DITHER_PHASES = int(os.environ.get("GPT2_CASCADE_NEAR_DITHER_PHASES", "0"))
DEFAULT_OUTPUT_NAME = (
    f"gpt2-hvar-grid-output-head-cascade-near-dither{NEAR_DITHER_PHASES}"
    if NEAR_SELECTOR and NEAR_DITHER_PHASES
    else "gpt2-hvar-grid-output-head-cascade-near-selector" if NEAR_SELECTOR
    else "gpt2-hvar-grid-output-head-cascade-compact" if PHASES == 1
    else (
        f"gpt2-hvar-grid-output-head-cascade-dither{PHASES}-sparse{len(ACTIVE_LOCALS)}"
        if ACTIVE_LOCALS
        else f"gpt2-hvar-grid-output-head-cascade-dither{PHASES}"
    )
)
OUTPUT_NAME = os.environ.get("GPT2_CASCADE_OUTPUT_DIR", DEFAULT_OUTPUT_NAME)
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
COARSE_NAME = os.environ.get(
    "GPT2_CASCADE_COARSE_DIR",
    "gpt2-hvar-grid-output-head-global11-inline-tie",
)
COARSE = ROOT / "experiments" / COARSE_NAME
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
SOURCE_REFERENCE = ROOT / "experiments" / "svg-filter-full-block" / "reference.json"


def css_if(branches: list[tuple[int, str]], fallback: str) -> str:
    clauses = ";".join(
        f"style(--group:{group}):{value}" for group, value in branches
    )
    return f"if({clauses};else:{fallback})"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    source = json.loads(SOURCE_REFERENCE.read_text())
    hidden_vectors = np.stack((
        source["bucket_final_ln_expected"],
        source["bucket_final_ln_expected_alt"],
    )).astype(np.float64)

    fine_html = (FINE / "index.html").read_text()
    records = re.findall(
        r'<i class="candidate" style="--base:([^;]+);'
        r'--factor:([^;]+);--local-tie:([^\"]+)">(.*?)</i>',
        fine_html,
    )
    if len(records) != baseline.VOCABULARY:
        raise RuntimeError(f"expected {baseline.VOCABULARY} fine candidates")
    factors = {factor for _, factor, _, _ in records}
    if len(factors) != 1:
        raise RuntimeError("compact cascade requires one global fine factor")
    factor = next(iter(factors))

    code_sums = None
    if PHASES > 1 or NEAR_DITHER_PHASES > 1:
        tensors = SafeTensors(MODEL_PATH)
        embeddings = np.asarray(
            tensors.tensor("wte.weight")[:baseline.VOCABULARY], dtype=np.float64
        )
        codes = np.rint(
            embeddings / fine_reference["weightScale"]
        ).astype(np.int16)
        code_sums = codes.astype(np.int64).sum(axis=1)

    def adjusted_base(token: int, base: str, phases: int) -> str:
        if phases == 1:
            return base
        offset_sum = (phases - 1) / 2 / 16_384
        correction = (
            fine_reference["displayScale"] * int(code_sums[token])
            * (offset_sum - phases / 2 / 16_384)
        )
        return baseline.css_number(phases * float(base) + correction)

    phase_markup = "".join(
        f'<span class="fine-phase fine-phase-{phase}"></span>'
        for phase in range(PHASES)
    )
    rendered_locals = ACTIVE_LOCALS or tuple(range(baseline.GROUP_SIZE))
    candidate_markup = "".join(
        f'<i class="fine-candidate" style="--local-tie:{255 - local}">'
        f"{phase_markup}</i>"
        for local in rendered_locals
    )
    near_markup = ""
    if NEAR_SELECTOR:
        dither_markup = ""
        if NEAR_DITHER_PHASES:
            dither_phases = "".join(
                f'<span class="dither-phase dither-phase-{phase}"></span>'
                for phase in range(NEAR_DITHER_PHASES)
            )
            dither_markup = (
                '<span id="dither-stage" class="dither-stage">'
                f'<i class="dither-slot dither-low">{dither_phases}</i>'
                f'<i class="dither-slot dither-high">{dither_phases}</i>'
                '</span><span class="dither-reader"><i id="refined-result" '
                'class="refined-result"></i></span>'
            )
        near_markup = (
            '<span class="near-carriers">'
            + "".join(
                f'<i class="near-carrier near-carrier-{local}"></i>'
                for local in range(baseline.GROUP_SIZE)
            )
            + '</span><span class="near-reader"><i id="near-result" '
            f'class="near-result">{dither_markup}</i></span>'
        )
    fine_markup = (
        '<span id="fine-stage" class="fine-stage">'
        + candidate_markup
        + '</span><span class="fine-reader">'
        '<i id="fine-result" class="fine-result"></i></span>'
        + near_markup
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
<title>Compact coarse-to-fine GPT-2 CSS output head</title>
<link rel="stylesheet" href="../{COARSE_NAME}/index.css">
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
    phase_settings: list[str] = []
    for phase in range(PHASES):
        offset = phase / PHASES / 16_384 if PHASES > 1 else 0
        phase_setting = ",".join(
            f'"{baseline.global_axis_tag(dimension)}" '
            f"calc(var(--h{dimension})/{baseline.css_number(fine_reference['inputRange'])}"
            f" + {baseline.css_number(offset)})"
            for dimension in range(baseline.WIDTH)
        )
        phase_settings.append(
            f".fine-phase-{phase}{{font-variation-settings:{phase_setting}}}"
        )
    families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(fine_reference["shards"])
        for plane in ("H", "L")
    )
    query_rules = baseline.output_head.query_rules(hidden_vectors).replace(
        ".model", ".cascade"
    )
    score_offsets = "\n".join(
        f"body:has(#q{query}:checked) .cascade{{--score-offset:"
        f"{-floor * fine_reference['scoreScale'] * fine_reference['scoreStridePx']}px}}"
        for query, floor in enumerate(fine_reference["scoreFloors"])
    )

    candidate_rules: list[str] = []
    shared_source_values: list[str] = []
    last_group_validity_rules: list[str] = []
    for position, local in enumerate(rendered_locals, start=1):
        base_branches: list[tuple[int, str]] = []
        glyph_branches: list[tuple[int, str]] = []
        sum_branches: list[tuple[int, str]] = []
        for group in range(coarse_reference["groups"]):
            token = group * baseline.GROUP_SIZE + local
            if token >= baseline.VOCABULARY:
                break
            base, _, _, glyphs = records[token]
            base_branches.append((group, adjusted_base(token, base, PHASES)))
            glyph_branches.append((group, f'"{glyphs}"'))
            if NEAR_DITHER_PHASES:
                sum_branches.append((group, str(int(code_sums[token]))))
        if NEAR_DITHER_PHASES:
            shared_source_values.append(
                f"--source-base-{local}:{css_if(base_branches, base_branches[0][1])};"
                f"--source-glyphs-{local}:{css_if(glyph_branches, glyph_branches[0][1])};"
                f"--source-sum-{local}:{css_if(sum_branches, sum_branches[0][1])};"
            )
            candidate_value_rules = (
                f"--fine-base:var(--source-base-{local});"
                f"--fine-glyphs:var(--source-glyphs-{local})"
            )
        else:
            candidate_value_rules = (
                f"--fine-base:{css_if(base_branches, base_branches[0][1])};"
                f"--fine-glyphs:{css_if(glyph_branches, glyph_branches[0][1])}"
            )
        candidate_rules.append(
            f".fine-candidate:nth-child({position}){{"
            + candidate_value_rules
            + (f";anchor-name:--fine-candidate-{local}" if NEAR_SELECTOR else "")
            + "}"
        )
        if local >= 81:
            last_group_validity_rules.append(
                f".fine-candidate:nth-child({position})"
                "{display:if(style(--group:196):none;else:block)}"
            )

    near_css = ""
    if NEAR_SELECTOR:
        near_anchors = ",".join(
            f"anchor-size(--near-carrier-{local} width)"
            for local in range(baseline.GROUP_SIZE)
        )
        near_heights = ",".join(
            f"anchor-size(--near-carrier-{local} height)"
            for local in range(baseline.GROUP_SIZE)
        )
        near_rules = "".join(
            f".near-carrier-{local}{{position-anchor:--fine-candidate-{local};"
            f"anchor-name:--near-carrier-{local};"
            f"width:calc(clamp(0px,anchor-size(--fine-candidate-{local} width) - "
            f"anchor-size(--fine-winner width) + 24px,1px)*{local + 1});"
            f"height:calc(clamp(0px,anchor-size(--fine-candidate-{local} width) - "
            f"anchor-size(--fine-winner width) + 24px,1px)*{256 - local})}}"
            for local in range(baseline.GROUP_SIZE)
        )
        near_css = (
            '@property --near-high{syntax:"<number>";inherits:true;initial-value:-1}'
            '@property --near-low{syntax:"<number>";inherits:true;initial-value:-1}'
            '.near-carrier,.near-reader{position:fixed;left:0;top:-50000px}'
            + near_rules
            + f'.near-reader{{width:max({near_anchors});height:max({near_heights});'
            'container:near-result/size}'
            '@container near-result (width >= 0px){.near-result{'
            '--near-high:calc(100cqi/1px - 1);'
            '--near-low:calc(256 - 100cqb/1px);display:block;width:1px;height:1px}}'
        )

    dither_css = ""
    if NEAR_DITHER_PHASES:
        def local_if(property_name: str, value_prefix: str) -> str:
            return "if(" + ";".join(
                f"style({property_name}:{local}):var({value_prefix}{local})"
                for local in range(baseline.GROUP_SIZE)
            ) + f";else:var({value_prefix}0))"

        dither_phase_rules: list[str] = []
        for phase in range(NEAR_DITHER_PHASES):
            offset = phase / NEAR_DITHER_PHASES / 16_384
            dither_settings = ",".join(
                f'"{baseline.global_axis_tag(dimension)}" '
                f"calc(var(--h{dimension})/"
                f"{baseline.css_number(fine_reference['inputRange'])} + "
                f"{baseline.css_number(offset)})"
                for dimension in range(baseline.WIDTH)
            )
            dither_phase_rules.append(
                f".dither-phase-{phase}{{font-variation-settings:{dither_settings}}}"
            )
        dither_factor = baseline.css_number(
            float(factor) / NEAR_DITHER_PHASES
        )
        dither_base_correction = baseline.css_number(
            -fine_reference["displayScale"] / (2 * 16_384)
        )
        dither_css = (
            '#result{' + "".join(shared_source_values) + '}'
            '.dither-stage{position:fixed;left:0;top:-40000px;display:grid;'
            'grid-template-columns:max-content;grid-template-rows:1px;'
            'width:max-content;height:1px;anchor-name:--dither-winner;'
            f'font-family:{families};font-size:100px;line-height:1;'
            'font-kerning:none}'
            '.dither-slot{grid-area:1/1;display:block;justify-self:start;'
            'height:1px;overflow:hidden;white-space:pre;font-style:normal;'
            f'width:calc-size(max-content,calc(round(nearest,(size - var(--dither-base)*1px)'
            f'* {dither_factor} + var(--score-offset),4px) + var(--local-tie)/64*1px))}}'
            f'.dither-low{{--dither-source-base:{local_if("--near-low", "--source-base-")};'
            f'--dither-sum:{local_if("--near-low", "--source-sum-")};'
            f'--dither-base:calc(var(--dither-source-base)*{NEAR_DITHER_PHASES} + '
            f'var(--dither-sum)*{dither_base_correction});'
            f'--dither-glyphs:{local_if("--near-low", "--source-glyphs-")};'
            '--local-tie:calc(255 - var(--near-low))}'
            f'.dither-high{{--dither-source-base:{local_if("--near-high", "--source-base-")};'
            f'--dither-sum:{local_if("--near-high", "--source-sum-")};'
            f'--dither-base:calc(var(--dither-source-base)*{NEAR_DITHER_PHASES} + '
            f'var(--dither-sum)*{dither_base_correction});'
            f'--dither-glyphs:{local_if("--near-high", "--source-glyphs-")};'
            '--local-tie:calc(255 - var(--near-high))}'
            '.dither-phase{display:inline}.dither-phase::before{content:var(--dither-glyphs)}'
            + "".join(dither_phase_rules)
            + '.dither-reader{position:fixed;position-anchor:--dither-winner;'
            'left:0;top:-30000px;width:anchor-size(--dither-winner width);height:1px;'
            'container:dither-result/inline-size}'
            '@container dither-result (width >= 0px){.refined-result{'
            '--fine-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));'
            '--refined-winner:calc(var(--group)*256 + var(--fine-local));'
            'display:block;width:calc(var(--refined-winner)*1px);height:1px}}'
        )

    css = (
        font_faces + "\n"
        + '@property --fine-local{syntax:"<number>";inherits:true;initial-value:0}'
        + '@property --fine-bucket{syntax:"<number>";inherits:true;initial-value:0}'
        + '@property --refined-winner{syntax:"<number>";inherits:true;initial-value:0}'
        + query_rules + "\n" + score_offsets + "\n"
        + f".fine-stage{{position:fixed;left:0;top:-80000px;display:grid;"
        f"grid-template-columns:max-content;grid-template-rows:1px;"
        f"width:max-content;height:1px;anchor-name:--fine-winner;"
        f"font-family:{families};font-size:100px;line-height:1;"
        f"font-variation-settings:{settings};font-kerning:none}}"
        + ".fine-candidate{grid-area:1/1;display:block;justify-self:start;"
        + "height:1px;overflow:hidden;white-space:pre;font-style:normal;"
        + f"width:calc-size(max-content,calc(round(nearest,(size - var(--fine-base)*1px)"
        + f"* {baseline.css_number(float(factor) / PHASES)} + var(--score-offset),4px)"
        + " + var(--local-tie)/64*1px))}"
        + ".fine-phase{display:inline}.fine-phase::before{content:var(--fine-glyphs)}"
        + "".join(phase_settings)
        + "".join(last_group_validity_rules)
        + "".join(candidate_rules)
        + near_css
        + dither_css
        + ".fine-reader{position:fixed;position-anchor:--fine-winner;"
        + "left:0;top:-70000px;width:anchor-size(--fine-winner width);height:1px;"
        + "container:fine-result/inline-size}"
        + "@container fine-result (width >= 0px){.fine-result{"
        + "--fine-bucket:round(down,100cqi/4px,1);"
        + "--fine-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
        + "--refined-winner:calc(var(--group)*256 + var(--fine-local));"
        + "display:block;width:calc(var(--refined-winner)*1px);height:1px}}\n"
    )
    (OUTPUT / "index.css").write_text(css)

    certified_fixtures = None
    if "allFixtures" in coarse_reference:
        fixture_hidden = np.asarray(
            coarse_reference["allFixtures"]["hiddenVectors"], dtype=np.float64
        )
        fixture_groups = np.asarray(
            coarse_reference["allFixtures"]["upperGroups"], dtype=int
        )
        tensors = SafeTensors(MODEL_PATH)
        embeddings = np.asarray(
            tensors.tensor("wte.weight")[:baseline.VOCABULARY], dtype=np.float64
        )
        fine_codes = np.rint(
            embeddings / fine_reference["weightScale"]
        ).astype(np.int16)
        fine_weights = fine_codes.astype(np.float64) * fine_reference["weightScale"]
        fine_scores = fixture_hidden @ fine_weights.T
        fixture_floors = np.asarray(
            coarse_reference["allFixtures"]["scoreFloors"], dtype=int
        )
        fine_buckets = np.rint(
            (fine_scores - fixture_floors[:, None]) * fine_reference["scoreScale"]
        ).astype(int)
        selected_winners: list[int] = []
        selected_buckets: list[int] = []
        for fixture, group in enumerate(fixture_groups):
            start = int(group) * baseline.GROUP_SIZE
            stop = min(start + baseline.GROUP_SIZE, baseline.VOCABULARY)
            winner = start + int(np.argmax(fine_buckets[fixture, start:stop]))
            selected_winners.append(winner)
            selected_buckets.append(int(fine_buckets[fixture, winner]))
        certified_fixtures = {
            "hiddenVectors": fixture_hidden.tolist(),
            "scoreFloors": fixture_floors.tolist(),
            "upperWinners": coarse_reference["allFixtures"]["upperWinners"],
            "upperGroups": fixture_groups.tolist(),
            "upperWinnerBuckets": coarse_reference["allFixtures"][
                "upperWinnerBuckets"
            ],
            "selectedGroupFineWinners": selected_winners,
            "selectedGroupFineBuckets": selected_buckets,
            "selectedGroupFineLowerBuckets": [value - 1 for value in selected_buckets],
            "denseWinners": coarse_reference["allFixtures"]["denseWinners"],
            "denseGroups": coarse_reference["allFixtures"]["denseGroups"],
        }

    reference = {
        "model": "openai-community/gpt2",
        "backend": (
            f"{COARSE_NAME}-plus-css-if-selected-global-int16"
            if PHASES == 1
            else f"global-int11-coarse-plus-global-int16-dither{PHASES}"
        ),
        "vocabulary": baseline.VOCABULARY,
        "groupSize": baseline.GROUP_SIZE,
        "groups": coarse_reference["groups"],
        "coarseHead": COARSE_NAME,
        "coarseGlyphsPerToken": coarse_reference.get("glyphsPerToken"),
        "denseWinners": fine_reference["denseWinners"],
        "coarseWinners": coarse_reference["quantizedWinners"],
        "refinedWinners": fine_reference["quantizedWinners"],
        "validation": {
            "tokenIds": fine_reference["validation"]["tokenIds"],
            "hiddenVectors": fine_reference["validation"]["hiddenVectors"],
            "scoreFloors": fine_reference["validation"]["scoreFloors"],
            "denseWinners": fine_reference["validation"]["denseWinners"],
            "coarseWinners": coarse_reference["validation"]["quantizedWinners"],
            "refinedWinners": fine_reference["validation"]["quantizedWinners"],
        },
        "precisionScreen": {
            "samples": 256,
            "coarseGroupMatches": 256,
            "coarseWinnerMatches": 255,
            "fineWinnerMatches": 256,
        },
        "fineCandidateElements": len(rendered_locals),
        "coordinateDitherPhases": PHASES,
        "activeFineCandidates": (
            list(ACTIVE_LOCALS) if ACTIVE_LOCALS else list(range(baseline.GROUP_SIZE))
        ),
        "fineShapedGlyphs": (
            len(ACTIVE_LOCALS) if ACTIVE_LOCALS else baseline.GROUP_SIZE
        ) * 12 * PHASES,
        "nearScoreSelector": NEAR_SELECTOR,
        "nearThresholdPixels": 24 if NEAR_SELECTOR else None,
        "nearDitherPhases": NEAR_DITHER_PHASES,
        "nearDitherSlots": 2 if NEAR_DITHER_PHASES else 0,
        "certifiedFixtures": certified_fixtures,
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
        key: value for key, value in reference.items()
        if key not in {"validation", "certifiedFixtures"}
    }, indent=2))


if __name__ == "__main__":
    main()
