#!/usr/bin/env python3
"""Build real-font latency crossover pages for q10->q16 vs q10->q12->q16."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-progressive-precision-crossover"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
FIXTURES = ROOT / "experiments" / "gpt2-token-uncertainty-block-gate" / "reference.json"
WIDTH = 768
SHARD = 256
SHARDS = WIDTH // SHARD
RADIX = 64
DISPLAY_SCALE = 0.1
SAFETY = 32
Q12_MAXIMUM = 2047
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
SCALE_POINTS = (128, 256, 418, 640)
GLOBAL_Q12_ROWS = 418
GLOBAL_Q16_ROWS = 22
MAXIMUM_ROWS = max(SCALE_POINTS)
CODEPOINT_STARTS = tuple(0x50000 + face * 0x10000 for face in range(2 * SHARDS))


def css_number(value: float) -> str:
    return head.css_number(float(value))


def font_settings(input_range: float) -> str:
    return ",".join(
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{css_number(input_range)})"
        for dimension in range(WIDTH)
    )


def q16_rows_for(q12_rows: int) -> int:
    return max(1, round(q12_rows * GLOBAL_Q16_ROWS / GLOBAL_Q12_ROWS))


def build_q12_fonts(codes: np.ndarray) -> tuple[np.ndarray, list[dict[str, object]]]:
    equivalent_bases: list[np.ndarray] = []
    reports: list[dict[str, object]] = []
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        stop = start + SHARD
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / RADIX).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * RADIX).astype(np.int16)
        if not np.array_equal(
            high.astype(np.int32) * RADIX + residual.astype(np.int32), shard_codes
        ):
            raise RuntimeError(f"q12 shard {shard} radix split is not exact")
        plane_bases = []
        for plane, (letter, values) in enumerate((("h", high), ("l", residual))):
            l1 = np.sum(np.abs(values.astype(np.int64)), axis=1)
            bases = (l1 + SAFETY).astype(np.int32)
            if int(np.max(bases + l1)) > 65_535:
                raise RuntimeError(f"q12 shard {shard} plane {plane} exceeds uint16")
            destination = OUTPUT / f"q12-{letter}{shard}.ttf"
            build_direct_font_backend(
                values,
                destination,
                signed_axes=True,
                base_advance=bases,
                codepoint_start=CODEPOINT_STARTS[2 * shard + plane],
                axis_tags=[global_axis_tag(dimension) for dimension in range(start, stop)],
            )
            font = destination.with_suffix(".woff2")
            reports.append(
                {
                    "shard": shard,
                    "plane": "high" if plane == 0 else "residual",
                    "rows": len(codes),
                    "dimensions": [start, stop],
                    "codeAbsoluteMaximum": int(np.max(np.abs(values))),
                    "maximumL1": int(l1.max()),
                    "maximumBaseAdvance": int(bases.max()),
                    "maximumShapedAdvance": int(np.max(bases + l1)),
                    "woff2Bytes": font.stat().st_size,
                }
            )
            plane_bases.append(bases.astype(np.int64))
        equivalent_bases.append(plane_bases[0] * RADIX + plane_bases[1])
    return np.sum(np.stack(equivalent_bases), axis=0), reports


def q12_markup(
    count: int,
    row_bases: np.ndarray,
    row_scales: np.ndarray,
    input_range: float,
) -> str:
    rows = []
    for row in range(count):
        glyphs = "".join(chr(codepoint + row) for codepoint in CODEPOINT_STARTS)
        factor = (
            input_range
            * row_scales[row]
            * SCORE_SCALE
            * SCORE_STRIDE_PX
            / DISPLAY_SCALE
        )
        rows.append(
            f'<i class="score-row q12-row" style="--base:'
            f'{css_number(row_bases[row] * DISPLAY_SCALE)};'
            f'--factor:{css_number(factor)}">{glyphs}</i>'
        )
    return "".join(rows)


def q16_markup(count: int, fine_rows: list[tuple[str, str, str, str]]) -> str:
    return "".join(
        f'<i class="score-row q16-row" style="--base:{base};--factor:{factor};'
        f'--local-tie:{tie}">{glyphs}</i>'
        for base, factor, tie, glyphs in fine_rows[:count]
    )


def render_html(mode: str, q12_rows: str, q16_rows: str, rows: int, survivors: int) -> str:
    if mode == "direct":
        pipeline = (
            '<i id="first-gate" class="first-gate">'
            '<span id="final-stage" class="score-stage q16-stage first-wave-content" '
            f'style="anchor-name:--final-stage">{q16_rows}</span></i>'
        )
    elif mode == "progressive":
        pipeline = (
            '<i id="first-gate" class="first-gate">'
            '<span id="q12-stage" class="score-stage q12-stage first-wave-content" '
            f'style="anchor-name:--q12-stage">{q12_rows}</span></i>'
            '<i id="second-gate" class="second-gate">'
            '<span id="final-stage" class="score-stage q16-stage second-wave-content" '
            f'style="anchor-name:--final-stage">{q16_rows}</span></i>'
        )
    else:
        raise ValueError(mode)
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Progressive precision crossover {mode} rows={rows}</title>
<link rel="stylesheet" href="index.css">
<body data-mode="{mode}" data-q12-rows="{rows}" data-q16-rows="{survivors}">
<main id="probe" class="probe">{pipeline}
  <span id="result-reader" class="result-reader"><output id="result"></output></span>
</main>
"""


def render_css(coarse_reference: dict[str, object], fine_reference: dict[str, object]) -> str:
    q12_faces = "".join(
        f'@font-face{{font-family:Q12{plane.upper()}{shard};src:url("q12-{plane}{shard}.woff2") '
        f'format("woff2"){f";size-adjust:{RADIX * 100}%" if plane == "h" else ""}}}'
        for shard in range(SHARDS)
        for plane in ("h", "l")
    )
    q16_faces = "".join(
        f'@font-face{{font-family:Q16{plane.upper()}{shard};src:url("../gpt2-hvar-grid-output-head-global16-twoplane/'
        f'score-{plane}{shard}.woff2") format("woff2")'
        f'{";size-adjust:25600%" if plane == "h" else ""}}}'
        for shard in range(int(fine_reference["shards"]))
        for plane in ("h", "l")
    )
    q12_families = ",".join(
        f"Q12{plane.upper()}{shard}" for shard in range(SHARDS) for plane in ("h", "l")
    )
    q16_families = ",".join(
        f"Q16{plane.upper()}{shard}"
        for shard in range(int(fine_reference["shards"]))
        for plane in ("h", "l")
    )
    return "\n".join(
        (
            q12_faces + q16_faces,
            '@property --observed{syntax:"<number>";inherits:true;initial-value:0}',
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".probe{--score-offset:0px}",
            ".first-gate{position:fixed;left:0;top:-90000px;height:1px;"
            "width:clamp(1px,calc(abs(var(--h0))*1px + 1px),2px);container:first-wave/inline-size}",
            ".first-wave-content,.second-wave-content{display:none}",
            "@container first-wave (width >= 1px){.first-wave-content{display:grid}}",
            ".score-stage{position:fixed;left:0;width:max-content;height:1px;"
            "grid-template-columns:max-content;grid-template-rows:1px}",
            ".score-row{display:block;grid-area:1/1;justify-self:start;height:1px;overflow:hidden;"
            "white-space:pre;font-style:normal;font-kerning:none}",
            ".q12-stage{top:-89000px}",
            f".q12-row{{font-family:{q12_families};font-size:{css_number(head.FONT_SIZE * DISPLAY_SCALE)}px;"
            f"line-height:1;font-variation-settings:{font_settings(float(coarse_reference['inputRange']))};"
            "width:calc-size(max-content,calc((size - var(--base)*1px) * var(--factor) + "
            "var(--score-offset)))}",
            ".second-gate{position:fixed;position-anchor:--q12-stage;left:0;top:-88000px;height:1px;"
            "width:clamp(1px,anchor-size(--q12-stage width),2px);container:second-wave/inline-size}",
            "@container second-wave (width >= 1px){.second-wave-content{display:grid}}",
            ".q16-stage{top:-87000px}",
            f".q16-row{{font-family:{q16_families};font-size:100px;line-height:1;"
            f"font-variation-settings:{font_settings(float(fine_reference['inputRange']))};"
            "width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px) * var(--factor) + "
            "var(--score-offset),4px) + var(--local-tie)/64*1px))}",
            ".result-reader{position:fixed;position-anchor:--final-stage;left:0;top:-86000px;"
            "width:anchor-size(--final-stage width);height:1px;container:crossover-result/inline-size}",
            "@container crossover-result (width >= 0px){#result{--observed:round(nearest,100cqi/1px,1);"
            "display:block;width:1px;height:1px}}",
        )
    ) + "\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    fixture_reference = json.loads(FIXTURES.read_text())
    fixtures = next(
        variant["fixtures"]
        for variant in fixture_reference["variants"]
        if variant["blockSize"] == 4
    )
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:MAXIMUM_ROWS], dtype=np.float64
    )
    scales = np.max(np.abs(weights), axis=1) / Q12_MAXIMUM
    scales[scales == 0] = 1.0
    codes = np.rint(weights / scales[:, None]).clip(-Q12_MAXIMUM, Q12_MAXIMUM).astype(np.int16)
    row_bases, face_reports = build_q12_fonts(codes)
    fine_rows = token_gate.records(FINE / "index.html")[:MAXIMUM_ROWS]
    input_range = float(coarse_reference["inputRange"])

    (OUTPUT / "index.css").write_text(render_css(coarse_reference, fine_reference))
    points = []
    for rows in SCALE_POINTS:
        survivors = q16_rows_for(rows)
        q12 = q12_markup(rows, row_bases, scales, input_range)
        direct_q16 = q16_markup(rows, fine_rows)
        progressive_q16 = q16_markup(survivors, fine_rows)
        direct_name = f"direct-r{rows}.html"
        progressive_name = f"progressive-r{rows}.html"
        (OUTPUT / direct_name).write_text(
            render_html("direct", "", direct_q16, rows, rows)
        )
        (OUTPUT / progressive_name).write_text(
            render_html("progressive", q12, progressive_q16, rows, survivors)
        )
        points.append(
            {
                "q12Rows": rows,
                "directQ16Rows": rows,
                "progressiveQ16Rows": survivors,
                "directPage": direct_name,
                "progressivePage": progressive_name,
                "directHtmlBytes": (OUTPUT / direct_name).stat().st_size,
                "progressiveHtmlBytes": (OUTPUT / progressive_name).stat().st_size,
            }
        )

    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "purpose": "synthetic real-font mutation-latency crossover; not a correctness claim",
        "globalB4OfflineBudget": {
            "directQ16Rows": GLOBAL_Q12_ROWS,
            "progressiveQ12Rows": GLOBAL_Q12_ROWS,
            "progressiveQ16Rows": GLOBAL_Q16_ROWS,
        },
        "dependencyTopology": {
            "direct": "one container wave reveals q16 rows, then final max-content read",
            "progressive": "first container wave reveals q12 rows; q12 max anchors a second container wave revealing q16 rows",
        },
        "hiddenPropertiesMutated": WIDTH,
        "runtimeContainsJavaScript": False,
        "q12Transport": {
            "quantization": "real GPT-2 rowwise symmetric q12",
            "radix": RADIX,
            "planes": 2,
            "shardsPerPlane": SHARDS,
            "glyphsPerRow": 2 * SHARDS,
            "displayScale": DISPLAY_SCALE,
            "fontRows": MAXIMUM_ROWS,
            "faces": face_reports,
            "woff2Bytes": sum(int(face["woff2Bytes"]) for face in face_reports),
        },
        "q16Transport": {
            "source": "gpt2-hvar-grid-output-head-global16-twoplane",
            "glyphsPerRow": int(fine_reference["glyphsPerToken"]),
            "shardsPerPlane": int(fine_reference["shards"]),
        },
        "fixtures": [
            {
                "fixture": int(fixture["fixture"]),
                "hidden": fixture["hidden"],
                "scoreFloor": int(fixture["scoreFloor"]),
            }
            for fixture in fixtures
        ],
        "scalePoints": points,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key != "fixtures"}, indent=2))


if __name__ == "__main__":
    main()
