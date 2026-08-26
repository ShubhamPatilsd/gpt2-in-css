#!/usr/bin/env python3
"""Build a fixed-group token-level certified uncertainty gate probe."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-token-uncertainty-gate"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
FIXTURES = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
    / "reference.json"
)
GROUP = 0
GROUP_SIZE = 256
COARSE_ALLOWANCE_BUCKETS = 19
FINE_ALLOWANCE_BUCKETS = 8
TOTAL_ALLOWANCE_BUCKETS = COARSE_ALLOWANCE_BUCKETS + FINE_ALLOWANCE_BUCKETS
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4


def outward_number(value: float) -> str:
    """Serialize a nonnegative multiplicative error bound outward."""
    return head.css_number(math.ceil(float(value) * 1_000_000_000) / 1_000_000_000)


def records(path: Path) -> list[tuple[str, str, str, str]]:
    found = re.findall(
        r'<i class="candidate" style="--base:([^;]+);'
        r'--factor:([^;]+);--local-tie:([^\"]+)">(.*?)</i>',
        path.read_text(),
    )
    if len(found) != head.VOCABULARY:
        raise RuntimeError(f"expected {head.VOCABULARY} candidates in {path}")
    return found


def font_settings(input_range: float) -> str:
    return ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{head.css_number(input_range)})"
        for dimension in range(head.WIDTH)
    )


def render_html(
    coarse_rows: list[tuple[str, str, str, str]],
    fine_rows: list[tuple[str, str, str, str]],
) -> str:
    coarse = "".join(
        f'<i id="coarse-{token}" class="coarse-candidate" '
        f'style="--base:{base};--factor:{factor};anchor-name:--coarse-{token}">'
        f"{glyphs}</i>"
        for token, (base, factor, _, glyphs) in enumerate(coarse_rows)
    )
    lower_chunks = "".join(
        f'<i id="lower-chunk-{chunk}" class="lower-chunk lower-chunk-{chunk}"></i>'
        for chunk in range(16)
    )
    gated = "".join(
        f'<i id="gate-{token}" class="gate-carrier gate-{token}">'
        f'<i id="gated-exact-{token}" class="exact-candidate gated-exact" '
        f'style="--base:{base};--factor:{factor};--local-tie:{tie};'
        f'anchor-name:--gated-exact-{token}">{glyphs}</i></i>'
        for token, (base, factor, tie, glyphs) in enumerate(fine_rows)
    )
    gated_chunks = "".join(
        f'<i id="gated-chunk-{chunk}" class="gated-chunk gated-chunk-{chunk}"></i>'
        for chunk in range(16)
    )
    full = "".join(
        f'<i class="exact-candidate full-exact" '
        f'style="--base:{base};--factor:{factor};--local-tie:{tie}">{glyphs}</i>'
        for base, factor, tie, glyphs in fine_rows
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2 fixed-group token uncertainty gate</title>
<link rel="stylesheet" href="index.css">
<body class="mode-both">
<main id="probe" class="probe">
  <section id="gate-path" class="gate-path">
    <span id="coarse-stage" class="coarse-stage">{coarse}</span>
    {lower_chunks}
    <i id="lower-max" class="lower-max"></i>
    <span id="gate-stage" class="gate-stage">{gated}</span>
    {gated_chunks}
    <i id="gated-max" class="gated-max"></i>
    <span class="gated-reader"><output id="gated-result" class="gated-result"></output></span>
  </section>
  <section id="full-control" class="full-control">
    <span id="full-stage" class="full-stage">{full}</span>
    <span class="full-reader"><output id="full-result" class="full-result"></output></span>
  </section>
</main>
<aside id="equality-probe" class="equality-probe">
  <i id="equality-gate" class="synthetic-gate synthetic-equal"><b></b></i>
  <i id="below-gate" class="synthetic-gate synthetic-below"><b></b></i>
  <span id="tie-stage" class="tie-stage"><i style="--local-tie:252"></i><i style="--local-tie:248"></i></span>
  <span class="tie-reader"><output id="tie-result" class="tie-result"></output></span>
</aside>
"""


def render_css(
    coarse_reference: dict[str, object],
    fine_reference: dict[str, object],
    bound_factors: list[str],
) -> str:
    coarse_glyphs = len(coarse_reference["rowBaseMaximums"])
    coarse_faces = "".join(
        f'@font-face{{font-family:Coarse{shard};src:url("../gpt2-hvar-grid-output-head/'
        f'score-d{shard}.woff2") format("woff2")}}'
        for shard in range(coarse_glyphs)
    )
    fine_faces = "".join(
        f'@font-face{{font-family:Fine{plane}{shard};src:url("../gpt2-hvar-grid-output-head-global16-twoplane/'
        f'score-{plane.lower()}{shard}.woff2") format("woff2")'
        + (";size-adjust:25600%" if plane == "H" else "")
        + "}"
        for shard in range(fine_reference["shards"])
        for plane in ("H", "L")
    )
    coarse_families = ",".join(
        f"Coarse{shard}" for shard in range(coarse_glyphs)
    )
    fine_families = ",".join(
        f"Fine{plane}{shard}"
        for shard in range(fine_reference["shards"])
        for plane in ("H", "L")
    )
    norm = " + ".join(
        f"var(--h{dimension})*var(--h{dimension})"
        for dimension in range(head.WIDTH)
    )
    allowance_px = TOTAL_ALLOWANCE_BUCKETS * SCORE_STRIDE_PX

    lower_terms = []
    gate_rules = []
    gated_sizes = []
    for token, factor in enumerate(bound_factors):
        lower_terms.append(
            "calc("
            f"anchor-size(--coarse-{token} width) - var(--query-norm)*{factor}*1px"
            f" - {allowance_px}px)"
        )
        upper = (
            f"anchor-size(--coarse-{token} width) + var(--query-norm)*{factor}*1px"
            f" + {allowance_px}px"
        )
        gate_rules.append(
            f".gate-{token}{{width:calc(clamp(0,sign(calc({upper} -"
            " anchor-size(--lower-max width))) + 1,1)*1px)}"
        )
        gated_sizes.append(f"anchor-size(--gated-exact-{token} width,0px)")
    lower_chunk_rules = "".join(
        f".lower-chunk-{chunk}{{anchor-name:--lower-chunk-{chunk};"
        f"width:max({','.join(lower_terms[chunk * 16:(chunk + 1) * 16])})}}"
        for chunk in range(16)
    )
    lower_chunk_sizes = ",".join(
        f"anchor-size(--lower-chunk-{chunk} width)" for chunk in range(16)
    )
    gated_chunk_rules = "".join(
        f".gated-chunk-{chunk}{{anchor-name:--gated-chunk-{chunk};"
        f"width:max({','.join(gated_sizes[chunk * 16:(chunk + 1) * 16])})}}"
        for chunk in range(16)
    )
    gated_chunk_sizes = ",".join(
        f"anchor-size(--gated-chunk-{chunk} width)" for chunk in range(16)
    )

    registrations = "".join(
        f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in (
            "query-norm",
            "gated-bucket",
            "gated-local",
            "gated-winner",
            "full-bucket",
            "full-local",
            "full-winner",
            "tie-local",
        )
    )
    return "\n".join(
        (
            coarse_faces + fine_faces,
            registrations,
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".probe{--score-offset:0px}",
            f".gate-path{{--query-norm:sqrt(calc({norm}))}}",
            ".coarse-stage{position:fixed;left:0;top:-90000px;width:1px;height:1px;"
            f"font-family:{coarse_families};font-size:1000px;line-height:1;"
            f"font-variation-settings:{font_settings(float(coarse_reference['inputRange']))};"
            "font-kerning:none}",
            ".coarse-candidate{position:fixed;left:0;top:-90000px;display:block;height:1px;"
            "overflow:hidden;white-space:pre;font-style:normal;"
            "width:calc-size(max-content,calc((size - var(--base)*1px)*var(--factor) + "
            "var(--score-offset)))}",
            ".lower-chunk{position:fixed;position-anchor:--coarse-0;left:0;top:-89500px;height:1px}"
            + lower_chunk_rules,
            ".lower-max{position:fixed;position-anchor:--lower-chunk-0;left:0;top:-89000px;"
            "height:1px;anchor-name:--lower-max;"
            f"width:max({lower_chunk_sizes})}}",
            ".gate-carrier{position:fixed;left:0;top:-88000px;height:1px;"
            "container:token-gate/inline-size}",
            "".join(gate_rules),
            ".exact-candidate{height:1px;overflow:hidden;white-space:pre;font-style:normal;"
            f"font-family:{fine_families};font-size:100px;line-height:1;"
            f"font-variation-settings:{font_settings(float(fine_reference['inputRange']))};"
            "font-kerning:none;width:calc-size(max-content,calc(round(nearest,"
            "(size - var(--base)*1px)*var(--factor) + var(--score-offset),4px) + "
            "var(--local-tie)/64*1px))}",
            ".gated-exact{display:none;position:fixed;left:0;top:-87000px}",
            "@container token-gate (width >= 1px){.gated-exact{display:block}}",
            ".gated-chunk{position:fixed;position-anchor:--coarse-0;left:0;top:-86500px;height:1px}"
            + gated_chunk_rules,
            ".gated-max{position:fixed;position-anchor:--gated-chunk-0;left:0;top:-86000px;height:1px;"
            "anchor-name:--gated-winner;"
            f"width:max({gated_chunk_sizes})}}",
            ".gated-reader{position:fixed;position-anchor:--gated-winner;left:0;top:-85000px;"
            "width:anchor-size(--gated-winner width);height:1px;container:gated-result/inline-size}",
            "@container gated-result (width >= 0px){.gated-result{"
            "--gated-bucket:round(down,100cqi/4px,1);"
            "--gated-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
            "--gated-winner:var(--gated-local);display:block;width:1px;height:1px}}",
            ".full-stage{position:fixed;left:0;top:-84000px;display:grid;"
            "grid-template-columns:max-content;grid-template-rows:1px;width:max-content;"
            "height:1px;anchor-name:--full-winner}",
            ".full-exact{display:block;grid-area:1/1;justify-self:start}",
            ".full-reader{position:fixed;position-anchor:--full-winner;left:0;top:-83000px;"
            "width:anchor-size(--full-winner width);height:1px;container:full-result/inline-size}",
            "@container full-result (width >= 0px){.full-result{"
            "--full-bucket:round(down,100cqi/4px,1);"
            "--full-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
            "--full-winner:var(--full-local);display:block;width:1px;height:1px}}",
            "body.mode-gated .full-control{display:none}body.mode-full .gate-path{display:none}",
            ".equality-probe{position:fixed;left:0;top:-1000px}",
            ".synthetic-gate{position:fixed;height:1px;container:synthetic/inline-size}",
            ".synthetic-gate b{display:none}.synthetic-equal{width:calc(clamp(0,sign(calc(100px - 100px)) + 1,1)*1px)}",
            ".synthetic-below{width:calc(clamp(0,sign(calc(99px - 100px)) + 1,1)*1px)}",
            "@container synthetic (width >= 1px){.synthetic-gate b{display:block}}",
            ".tie-stage{position:fixed;display:grid;grid-template-columns:max-content;"
            "grid-template-rows:1px;width:max-content;height:1px;anchor-name:--tie-winner}",
            ".tie-stage i{grid-area:1/1;display:block;width:calc(400px + var(--local-tie)/64*1px);height:1px}",
            ".tie-reader{position:fixed;position-anchor:--tie-winner;width:anchor-size(--tie-winner width);"
            "height:1px;container:tie-result/inline-size}",
            "@container tie-result (width >= 0px){.tie-result{--tie-local:calc(255 - "
            "round(nearest,mod(100cqi,4px)/1px*64,1));display:block;width:1px;height:1px}}",
        )
    ) + "\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    fixture_reference = json.loads(FIXTURES.read_text())["certifiedFixtures"]
    coarse_rows = records(COARSE / "index.html")[:GROUP_SIZE]
    fine_rows = records(FINE / "index.html")[:GROUP_SIZE]

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:GROUP_SIZE], dtype=np.float64
    )
    row_scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    row_scales[row_scales == 0] = 1.0
    represented = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale) * fine_scale
    error_norms = np.linalg.norm(target - represented, axis=1)
    bound_factors_float = error_norms * SCORE_SCALE * SCORE_STRIDE_PX
    bound_factors = [outward_number(value) for value in bound_factors_float]

    hidden = np.asarray(fixture_reference["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixture_reference["scoreFloors"], dtype=np.int64)
    query_norms = np.linalg.norm(hidden, axis=1)
    coarse_bucket_centers = (hidden @ represented.T - floors[:, None]) * SCORE_SCALE
    radii = query_norms[:, None] * np.asarray(
        [float(value) for value in bound_factors], dtype=np.float64
    )[None, :] / SCORE_STRIDE_PX
    lower = coarse_bucket_centers - radii - TOTAL_ALLOWANCE_BUCKETS
    upper = coarse_bucket_centers + radii + TOTAL_ALLOWANCE_BUCKETS
    lower_max = np.max(lower, axis=1)
    active = upper >= lower_max[:, None]
    exact_buckets = np.rint(
        (hidden @ target.T - floors[:, None]) * SCORE_SCALE
    ).astype(np.int64)
    exact_winners = np.argmax(exact_buckets, axis=1)

    fixtures = []
    for index in range(len(hidden)):
        active_tokens = np.flatnonzero(active[index]).astype(int).tolist()
        winner = int(exact_winners[index])
        if winner not in active_tokens:
            raise RuntimeError(f"fixture {index} gate lost exact winner {winner}")
        fixtures.append(
            {
                "fixture": index,
                "hidden": hidden[index].tolist(),
                "scoreFloor": int(floors[index]),
                "queryNorm": float(query_norms[index]),
                "lowerMaxBucket": float(lower_max[index]),
                "lowerMaxTokens": np.flatnonzero(lower[index] == lower_max[index])
                .astype(int)
                .tolist(),
                "activeTokens": active_tokens,
                "activeCount": len(active_tokens),
                "equalityActiveTokens": np.flatnonzero(upper[index] == lower_max[index])
                .astype(int)
                .tolist(),
                "exactWinner": winner,
                "exactWinnerBucket": int(exact_buckets[index, winner]),
            }
        )

    reference = {
        "model": "openai-community/gpt2",
        "backend": "fixed-group-int10-token-bounds-plus-inclusive-css-exact-gate",
        "scope": "group 0 only; no 197-group router or six-stage cascade",
        "group": GROUP,
        "groupSize": GROUP_SIZE,
        "target": "global-int16 weights scored by the retained twelve-glyph browser rows",
        "coarseModel": "row-wise signed int10 with l2(h)*l2(w16-w10) Cauchy radius",
        "bucketContract": {
            "scoreScale": SCORE_SCALE,
            "scoreStridePx": SCORE_STRIDE_PX,
            "coarseAllowanceBuckets": COARSE_ALLOWANCE_BUCKETS,
            "fineAllowanceBuckets": FINE_ALLOWANCE_BUCKETS,
            "totalOutwardAllowanceBuckets": TOTAL_ALLOWANCE_BUCKETS,
            "lower": "center-radius-27",
            "upper": "center+radius+27",
            "active": "upper >= max(lower)",
        },
        "coarseGlyphsPerToken": len(coarse_reference["rowBaseMaximums"]),
        "exactGlyphsPerActiveToken": fine_reference["glyphsPerToken"],
        "gateCarriers": GROUP_SIZE,
        "fullControlExactRows": GROUP_SIZE,
        "fixtures": fixtures,
        "offlineChecks": {
            "fixtures": len(fixtures),
            "exactWinnerRetained": sum(
                fixture["exactWinner"] in fixture["activeTokens"] for fixture in fixtures
            ),
            "activeCountMinimum": min(fixture["activeCount"] for fixture in fixtures),
            "activeCountMaximum": max(fixture["activeCount"] for fixture in fixtures),
            "activeCountMean": float(np.mean([fixture["activeCount"] for fixture in fixtures])),
        },
    }
    (OUTPUT / "index.html").write_text(render_html(coarse_rows, fine_rows))
    (OUTPUT / "index.css").write_text(
        render_css(coarse_reference, fine_reference, bound_factors)
    )
    reference["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    reference["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key != "fixtures"}, indent=2))


if __name__ == "__main__":
    main()
