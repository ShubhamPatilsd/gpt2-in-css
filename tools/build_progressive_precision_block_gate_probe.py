#!/usr/bin/env python3
"""Build a fixed-group q10 -> q12 -> q16 progressive precision probe."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-progressive-precision-block-gate"
DIRECT = ROOT / "experiments" / "gpt2-token-uncertainty-block-gate"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
GROUP_SIZE = 256
WIDTH = 768
BLOCK_SIZE = 4
BLOCK_COUNT = GROUP_SIZE // BLOCK_SIZE
FAN_IN = 16
SHARD = 256
SHARDS = WIDTH // SHARD
RADIX = 64
DISPLAY_SCALE = 0.1
SAFETY = 32
Q10_MAXIMUM = 511
Q12_MAXIMUM = 2047
ALLOWANCE_BUCKETS = 27
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
CODEPOINT_STARTS = tuple(0x50000 + face * 0x10000 for face in range(2 * SHARDS))


def css_number(value: float) -> str:
    return head.css_number(float(value))


def outward_number(value: float) -> str:
    return token_gate.outward_number(float(value))


def represented_rows(
    weights: np.ndarray, maximum: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scales = np.max(np.abs(weights), axis=1) / maximum
    scales[scales == 0] = 1.0
    codes = np.rint(weights / scales[:, None]).clip(-maximum, maximum).astype(np.int16)
    return codes, scales, codes.astype(np.float64) * scales[:, None]


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


def font_settings(input_range: float) -> str:
    return ",".join(
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension})/{css_number(input_range)})"
        for dimension in range(WIDTH)
    )


def max_reduction_rules(prefix: str, terms: list[str], top: int) -> tuple[str, str]:
    chunks = []
    anchors = []
    for chunk, start in enumerate(range(0, len(terms), FAN_IN)):
        anchor = f"--{prefix}-chunk-{chunk}"
        chunks.append(
            f".{prefix}-chunk-{chunk}{{anchor-name:{anchor};"
            f"width:max({','.join(terms[start:start + FAN_IN])})}}"
        )
        anchors.append(f"anchor-size({anchor} width,0px)")
    common = (
        f".{prefix}-chunk{{position:fixed;left:0;top:{top}px;height:1px}}"
    )
    return common + "".join(chunks), f"max({','.join(anchors)})"


def render_html(
    coarse_rows: list[tuple[str, str, str, str]],
    q12_bases: np.ndarray,
    q12_scales: np.ndarray,
    q12_input_range: float,
    fine_rows: list[tuple[str, str, str, str]],
) -> str:
    coarse = "".join(
        f'<i id="q10-{token}" class="q10-row" '
        f'style="--base:{base};--factor:{factor};anchor-name:--q10-{token}">{glyphs}</i>'
        for token, (base, factor, _tie, glyphs) in enumerate(coarse_rows)
    )
    q12_blocks = []
    q16_blocks = []
    for block in range(BLOCK_COUNT):
        start = block * BLOCK_SIZE
        stop = start + BLOCK_SIZE
        q12_rows = []
        q16_rows = []
        for token in range(start, stop):
            glyphs12 = "".join(chr(codepoint + token) for codepoint in CODEPOINT_STARTS)
            factor12 = (
                q12_input_range
                * q12_scales[token]
                * SCORE_SCALE
                * SCORE_STRIDE_PX
                / DISPLAY_SCALE
            )
            q12_rows.append(
                f'<i id="q12-{token}" class="q12-row" '
                f'style="--base:{css_number(q12_bases[token] * DISPLAY_SCALE)};'
                f'--factor:{css_number(factor12)};anchor-name:--q12-{token}">{glyphs12}</i>'
            )
            base, factor, tie, glyphs16 = fine_rows[token]
            q16_rows.append(
                f'<i id="q16-{token}" class="q16-row" '
                f'style="--base:{base};--factor:{factor};--local-tie:{tie}">{glyphs16}</i>'
            )
        q12_blocks.append(
            f'<i id="q10-gate-{block}" class="q10-gate q10-gate-{block}">'
            f'<span id="q12-block-{block}" class="q12-block">{"".join(q12_rows)}</span>'
            "</i>"
        )
        q16_blocks.append(
            f'<i id="q16-gate-{block}" class="q16-gate q16-gate-{block}">'
            f'<span id="q16-block-{block}" class="q16-block" '
            f'style="anchor-name:--q16-block-{block}">{"".join(q16_rows)}</span>'
            "</i>"
        )
    q10_chunks = "".join(
        f'<i class="q10-lower-chunk q10-lower-chunk-{chunk}"></i>'
        for chunk in range(GROUP_SIZE // FAN_IN)
    )
    q12_chunks = "".join(
        f'<i class="q12-lower-chunk q12-lower-chunk-{chunk}"></i>'
        for chunk in range(GROUP_SIZE // FAN_IN)
    )
    exact_chunks = "".join(
        f'<i class="exact-chunk exact-chunk-{chunk}"></i>'
        for chunk in range(BLOCK_COUNT // FAN_IN)
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2 progressive q10-q12-q16 fixed-group block gate</title>
<link rel="stylesheet" href="index.css">
<body>
<main id="probe" class="probe">
  <span class="q10-stage">{coarse}</span>
  {q10_chunks}<i id="q10-lower-max" class="q10-lower-max"></i>
  <span class="q12-stage">{"".join(q12_blocks)}</span>
  {q12_chunks}<i id="q12-lower-max" class="q12-lower-max"></i>
  <span class="q16-stage">{"".join(q16_blocks)}</span>
  {exact_chunks}<i id="progressive-max" class="progressive-max"></i>
  <span class="progressive-reader"><output id="progressive-result"></output></span>
</main>
"""


def render_css(
    coarse_reference: dict[str, object],
    fine_reference: dict[str, object],
    error10: np.ndarray,
    error12: np.ndarray,
) -> str:
    q10_faces = "".join(
        f'@font-face{{font-family:Q10{shard};src:url("../gpt2-hvar-grid-output-head/'
        f'score-d{shard}.woff2") format("woff2")}}'
        for shard in range(len(coarse_reference["rowBaseMaximums"]))
    )
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
    q10_families = ",".join(
        f"Q10{shard}" for shard in range(len(coarse_reference["rowBaseMaximums"]))
    )
    q12_families = ",".join(
        f"Q12{plane.upper()}{shard}" for shard in range(SHARDS) for plane in ("h", "l")
    )
    q16_families = ",".join(
        f"Q16{plane.upper()}{shard}"
        for shard in range(int(fine_reference["shards"]))
        for plane in ("h", "l")
    )
    norm = "+".join(f"var(--h{dimension})*var(--h{dimension})" for dimension in range(WIDTH))
    allowance_px = ALLOWANCE_BUCKETS * SCORE_STRIDE_PX
    factor10 = [
        outward_number(value * SCORE_SCALE * SCORE_STRIDE_PX) for value in error10
    ]
    factor12 = [
        outward_number(value * SCORE_SCALE * SCORE_STRIDE_PX) for value in error12
    ]

    q10_lower_terms = [
        f"calc(anchor-size(--q10-{token} width) - var(--query-norm)*{factor10[token]}*1px - {allowance_px}px)"
        for token in range(GROUP_SIZE)
    ]
    q10_reduction, q10_maximum = max_reduction_rules(
        "q10-lower", q10_lower_terms, -89500
    )
    q10_gates = []
    for block in range(BLOCK_COUNT):
        terms = [
            f"calc(anchor-size(--q10-{token} width) + var(--query-norm)*{factor10[token]}*1px + {allowance_px}px)"
            for token in range(block * BLOCK_SIZE, (block + 1) * BLOCK_SIZE)
        ]
        q10_gates.append(
            f".q10-gate-{block}{{width:calc(clamp(0,sign(calc(max({','.join(terms)}) - "
            "anchor-size(--q10-lower-max width))) + 1,1)*1px)}"
        )

    q12_lower_terms = [
        f"calc(anchor-size(--q12-{token} width,0px) - var(--query-norm)*{factor12[token]}*1px - {allowance_px}px)"
        for token in range(GROUP_SIZE)
    ]
    q12_reduction, q12_maximum = max_reduction_rules(
        "q12-lower", q12_lower_terms, -86500
    )
    q16_gates = []
    for block in range(BLOCK_COUNT):
        terms = [
            f"calc(anchor-size(--q12-{token} width,0px) + var(--query-norm)*{factor12[token]}*1px + {allowance_px}px)"
            for token in range(block * BLOCK_SIZE, (block + 1) * BLOCK_SIZE)
        ]
        q16_gates.append(
            f".q16-gate-{block}{{width:calc(clamp(0,sign(calc(max({','.join(terms)}) - "
            "anchor-size(--q12-lower-max width))) + 1,1)*1px)}"
        )

    exact_terms = [
        f"anchor-size(--q16-block-{block} width,0px)" for block in range(BLOCK_COUNT)
    ]
    exact_reduction, exact_maximum = max_reduction_rules("exact", exact_terms, -83500)
    registrations = "".join(
        f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in ("query-norm", "winner-bucket", "winner-local", "winner")
    )
    return "\n".join(
        (
            q10_faces + q12_faces + q16_faces,
            registrations,
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".probe{--score-offset:0px}",
            f".probe{{--query-norm:sqrt(calc({norm}))}}",
            ".q10-stage{position:fixed;left:0;top:-90000px;width:1px;height:1px;"
            f"font-family:{q10_families};font-size:1000px;line-height:1;"
            f"font-variation-settings:{font_settings(float(coarse_reference['inputRange']))};font-kerning:none}}",
            ".q10-row{position:fixed;left:0;top:-90000px;display:block;height:1px;overflow:hidden;"
            "white-space:pre;font-style:normal;width:calc-size(max-content,calc((size - var(--base)*1px) * "
            "var(--factor) + var(--score-offset)))}",
            q10_reduction.replace(
                "position:fixed;", "position:fixed;position-anchor:--q10-0;", 1
            ),
            ".q10-lower-max{position:fixed;position-anchor:--q10-lower-chunk-0;left:0;top:-89000px;height:1px;anchor-name:--q10-lower-max;"
            f"width:{q10_maximum}}}",
            ".q10-gate{position:fixed;left:0;top:-88000px;height:1px;container:q10-gate/inline-size}",
            "".join(q10_gates),
            ".q12-block{display:none;position:fixed;left:0;top:-87500px;width:max-content;height:1px;"
            "grid-template-columns:max-content;grid-template-rows:1px}",
            "@container q10-gate (width >= 1px){.q12-block{display:grid}}",
            ".q12-row{display:block;grid-area:1/1;justify-self:start;height:1px;overflow:hidden;white-space:pre;"
            f"font-style:normal;font-family:{q12_families};font-size:{css_number(head.FONT_SIZE * DISPLAY_SCALE)}px;"
            f"line-height:1;font-variation-settings:{font_settings(float(coarse_reference['inputRange']))};"
            "font-kerning:none;width:calc-size(max-content,calc((size - var(--base)*1px) * var(--factor) + "
            "var(--score-offset)))}",
            q12_reduction.replace(
                "position:fixed;", "position:fixed;position-anchor:--q10-0;", 1
            ),
            ".q12-lower-max{position:fixed;position-anchor:--q12-lower-chunk-0;left:0;top:-86000px;height:1px;anchor-name:--q12-lower-max;"
            f"width:{q12_maximum}}}",
            ".q16-gate{position:fixed;left:0;top:-85000px;height:1px;container:q16-gate/inline-size}",
            "".join(q16_gates),
            ".q16-block{display:none;position:fixed;left:0;top:-84500px;width:max-content;height:1px;"
            "grid-template-columns:max-content;grid-template-rows:1px}",
            "@container q16-gate (width >= 1px){.q16-block{display:grid}}",
            ".q16-row{display:block;grid-area:1/1;justify-self:start;height:1px;overflow:hidden;white-space:pre;"
            f"font-style:normal;font-family:{q16_families};font-size:100px;line-height:1;"
            f"font-variation-settings:{font_settings(float(fine_reference['inputRange']))};font-kerning:none;"
            "width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px) * var(--factor) + "
            "var(--score-offset),4px) + var(--local-tie)/64*1px))}",
            exact_reduction.replace(
                "position:fixed;", "position:fixed;position-anchor:--q10-0;", 1
            ),
            ".progressive-max{position:fixed;position-anchor:--exact-chunk-0;left:0;top:-83000px;height:1px;anchor-name:--progressive-max;"
            f"width:{exact_maximum}}}",
            ".progressive-reader{position:fixed;position-anchor:--progressive-max;left:0;top:-82000px;"
            "width:anchor-size(--progressive-max width);height:1px;container:progressive-result/inline-size}",
            "@container progressive-result (width >= 0px){#progressive-result{"
            "--winner-bucket:round(down,100cqi/4px,1);"
            "--winner-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));"
            "--winner:var(--winner-local);display:block;width:1px;height:1px}}",
        )
    ) + "\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    direct_reference = json.loads((DIRECT / "reference.json").read_text())
    direct_variant = next(
        variant for variant in direct_reference["variants"] if variant["blockSize"] == BLOCK_SIZE
    )
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    coarse_rows = token_gate.records(COARSE / "index.html")[:GROUP_SIZE]
    fine_rows = token_gate.records(FINE / "index.html")[:GROUP_SIZE]
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:GROUP_SIZE], dtype=np.float64
    )
    _codes10, _scales10, represented10 = represented_rows(weights, Q10_MAXIMUM)
    codes12, scales12, represented12 = represented_rows(weights, Q12_MAXIMUM)
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale) * fine_scale
    error10 = np.linalg.norm(target - represented10, axis=1)
    error12 = np.linalg.norm(target - represented12, axis=1)
    q12_bases, face_reports = build_q12_fonts(codes12)

    fixtures = []
    for source in direct_variant["fixtures"]:
        hidden = np.asarray(source["hidden"], dtype=np.float64)
        floor = int(source["scoreFloor"])
        norm = float(np.linalg.norm(hidden))
        center10 = (hidden @ represented10.T - floor) * SCORE_SCALE
        radius10 = norm * error10 * SCORE_SCALE
        lower10 = center10 - radius10 - ALLOWANCE_BUCKETS
        upper10 = center10 + radius10 + ALLOWANCE_BUCKETS
        active10_tokens = upper10 >= np.max(lower10)
        active10_blocks = np.flatnonzero(
            np.any(active10_tokens.reshape(BLOCK_COUNT, BLOCK_SIZE), axis=1)
        )
        active10_rows = np.zeros(GROUP_SIZE, dtype=bool)
        for block in active10_blocks:
            active10_rows[block * BLOCK_SIZE : (block + 1) * BLOCK_SIZE] = True
        center12 = (hidden @ represented12.T - floor) * SCORE_SCALE
        radius12 = norm * error12 * SCORE_SCALE
        lower12 = np.where(
            active10_rows,
            center12 - radius12 - ALLOWANCE_BUCKETS,
            -np.inf,
        )
        upper12 = center12 + radius12 + ALLOWANCE_BUCKETS
        active12_tokens = active10_rows & (upper12 >= np.max(lower12))
        active16_blocks = np.flatnonzero(
            np.any(active12_tokens.reshape(BLOCK_COUNT, BLOCK_SIZE), axis=1)
        )
        exact_buckets = np.rint((hidden @ target.T - floor) * SCORE_SCALE).astype(np.int64)
        winner = int(np.argmax(exact_buckets))
        if not any(block * BLOCK_SIZE <= winner < (block + 1) * BLOCK_SIZE for block in active16_blocks):
            raise RuntimeError(f"fixture {source['fixture']} progressive gate lost winner {winner}")
        fixtures.append(
            {
                **source,
                "q10ActiveBlocks": active10_blocks.astype(int).tolist(),
                "q10ShapedQ12Rows": int(len(active10_blocks) * BLOCK_SIZE),
                "q12LowerMaxBucket": float(np.max(lower12)),
                "q12ActiveTokens": np.flatnonzero(active12_tokens).astype(int).tolist(),
                "q16ActiveBlocks": active16_blocks.astype(int).tolist(),
                "q16ShapedRows": int(len(active16_blocks) * BLOCK_SIZE),
                "exactWinner": winner,
                "exactWinnerBucket": int(exact_buckets[winner]),
            }
        )

    (OUTPUT / "index.html").write_text(
        render_html(
            coarse_rows,
            q12_bases,
            scales12,
            float(coarse_reference["inputRange"]),
            fine_rows,
        )
    )
    (OUTPUT / "index.css").write_text(
        render_css(coarse_reference, fine_reference, error10, error12)
    )
    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "backend": "fixed-group-progressive-rowwise-q10-q12-global-int16-q16",
        "scope": "group 0 only; 10 existing certified fixtures",
        "group": 0,
        "groupSize": GROUP_SIZE,
        "blockSize": BLOCK_SIZE,
        "blockCount": BLOCK_COUNT,
        "allowanceBucketsAtEachTransition": ALLOWANCE_BUCKETS,
        "target": "browser-realized global-int16 q16 buckets with lower-token ties",
        "q12Transport": {
            "quantization": "rowwise symmetric q12",
            "radix": RADIX,
            "planes": 2,
            "shardsPerPlane": SHARDS,
            "glyphsPerShapedRow": 2 * SHARDS,
            "displayScale": DISPLAY_SCALE,
            "faces": face_reports,
            "woff2Bytes": sum(int(face["woff2Bytes"]) for face in face_reports),
        },
        "directControl": "../gpt2-token-uncertainty-block-gate/index-b4.html",
        "fullQ16Control": "mode-full on directControl",
        "fixtures": fixtures,
        "offline": {
            "meanQ12Rows": float(np.mean([item["q10ShapedQ12Rows"] for item in fixtures])),
            "meanQ16Rows": float(np.mean([item["q16ShapedRows"] for item in fixtures])),
            "maximumQ12Rows": max(item["q10ShapedQ12Rows"] for item in fixtures),
            "maximumQ16Rows": max(item["q16ShapedRows"] for item in fixtures),
            "winnerRetained": len(fixtures),
        },
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key != "fixtures"}, indent=2))


if __name__ == "__main__":
    main()
