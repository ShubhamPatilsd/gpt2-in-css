#!/usr/bin/env python3
"""Build a one-group aligned-int10 plus exact-residual browser probe."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-aligned-residual-group"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
CERTIFIED = ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-upper-int10"
GROUP = 0
START = GROUP * head.GROUP_SIZE
STOP = START + head.GROUP_SIZE
COARSE_SHARD = 160
RESIDUAL_SHARD = 256
DISPLAY_SCALE = 0.1
COARSE_OFFSET_PX = 200_000
COARSE_CODEPOINTS = tuple(0xD0000 + shard * 0x1000 for shard in range(5))
RESIDUAL_CODEPOINTS = tuple(0xD8000 + shard * 0x1000 for shard in range(3))
CONTROL_CODEPOINTS = tuple(
    [plane * 0x10000 for plane in range(2, 12)] + [0xF0000, 0x100000]
)


def glyphs(starts: tuple[int, ...], token: int) -> str:
    return "".join(chr(codepoint + token) for codepoint in starts)


def font_settings(input_range: float) -> str:
    return ",".join(
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension}) / {head.css_number(input_range)})"
        for dimension in range(head.WIDTH)
    )


def control_planes(codes: np.ndarray) -> tuple[list[np.ndarray], np.ndarray]:
    bases: list[np.ndarray] = []
    for start in range(0, head.WIDTH, 128):
        shard = codes[:, start : start + 128].astype(np.int32)
        high = np.trunc(shard / 256).astype(np.int16)
        low = (shard - high.astype(np.int32) * 256).astype(np.int16)
        high_base = np.sum(np.abs(high.astype(np.int64)), axis=1) + 32
        low_base = np.sum(np.abs(low.astype(np.int64)), axis=1) + 32
        bases.append(high_base * 256 + low_base)
    return bases, np.sum(np.stack(bases), axis=0)


def render_html(
    coarse_bases: np.ndarray,
    residual_bases: np.ndarray,
    control_bases: np.ndarray,
    multipliers: np.ndarray,
    input_range: float,
    global_scale: float,
) -> str:
    base_factor = (
        input_range * global_scale * head.SCORE_SCALE * head.SCORE_STRIDE_PX
        / DISPLAY_SCALE
    )
    coarse = []
    aligned = []
    control = []
    for local, token in enumerate(range(START, STOP)):
        tie = head.GROUP_SIZE - 1 - local
        coarse.append(
            f'<i data-token="{token}" style="--base:'
            f'{head.css_number(coarse_bases[local] * DISPLAY_SCALE)};'
            f'--factor:{head.css_number(base_factor * multipliers[local])}">'
            f"{glyphs(COARSE_CODEPOINTS, local)}</i>"
        )
        aligned.append(
            f'<i data-token="{token}" style="--base:'
            f'{head.css_number(residual_bases[local] * DISPLAY_SCALE)};'
            f'--factor:{head.css_number(base_factor)};--coarse-live:0px;'
            f'--local-tie:{tie}">{glyphs(RESIDUAL_CODEPOINTS, local)}</i>'
        )
        control.append(
            f'<i data-token="{token}" style="--base:'
            f'{head.css_number(control_bases[local] * DISPLAY_SCALE)};'
            f'--factor:{head.css_number(base_factor)};--local-tie:{tie}">'
            f"{glyphs(CONTROL_CODEPOINTS, token)}</i>"
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Aligned int10 plus three-glyph residual group probe</title>
<link rel="stylesheet" href="index.css">
<main id="probe" class="probe">
  <div id="coarse-cache" class="coarse-cache">{''.join(coarse)}</div>
  <div class="panels">
    <section class="panel aligned-panel"><h1>paid aligned int10 + 3 residual glyphs</h1>
      <div id="aligned-grid" class="score-grid aligned-grid">{''.join(aligned)}</div>
    </section>
    <section class="panel control-panel"><h1>existing 12-glyph global-int16 shadow</h1>
      <div id="control-grid" class="score-grid control-grid">{''.join(control)}</div>
    </section>
  </div>
</main>
"""


def render_css(input_range: float) -> str:
    faces = []
    for shard in range(5):
        faces.append(
            f'@font-face{{font-family:AlignedCoarse{shard};src:url("coarse-{shard}.woff2") format("woff2")}}'
        )
    for shard in range(3):
        faces.append(
            f'@font-face{{font-family:AlignedResidual{shard};src:url("residual-{shard}.woff2") format("woff2")}}'
        )
    for shard in range(6):
        faces.extend((
            f'@font-face{{font-family:ControlH{shard};src:url("../gpt2-hvar-grid-output-head-global16-twoplane/score-h{shard}.woff2") format("woff2");size-adjust:25600%}}',
            f'@font-face{{font-family:ControlL{shard};src:url("../gpt2-hvar-grid-output-head-global16-twoplane/score-l{shard}.woff2") format("woff2")}}',
        ))
    coarse_families = ",".join(f"AlignedCoarse{shard}" for shard in range(5))
    residual_families = ",".join(f"AlignedResidual{shard}" for shard in range(3))
    control_families = ",".join(
        family for shard in range(6) for family in (f"ControlH{shard}", f"ControlL{shard}")
    )
    return "".join(faces) + f"""
*{{box-sizing:border-box}}html,body{{margin:0}}body{{font:12px system-ui;background:#f5f7fb}}
.probe{{--score-offset:0px;position:relative;font-size:{head.css_number(head.FONT_SIZE * DISPLAY_SCALE)}px;line-height:1;font-variation-settings:{font_settings(input_range)};font-kerning:none}}
.panels{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}}
.panel{{min-width:0;padding:12px;background:white;border:1px solid #ccd3df;border-radius:8px;overflow:hidden}}
.panel h1{{font:600 13px/1.2 system-ui;margin:0 0 8px}}
.coarse-cache{{position:fixed;left:0;top:-1000px;width:1px;height:1px}}
.coarse-cache>i{{position:absolute;left:0;top:0;display:block;height:1px;overflow:hidden;white-space:pre;font-style:normal;font-family:{coarse_families};width:calc-size(max-content,calc((size - var(--base)*1px)*var(--factor) + {COARSE_OFFSET_PX}px))}}
.score-grid{{display:grid;grid-template-columns:max-content;grid-template-rows:1px;width:max-content;height:1px}}
.score-grid>i{{grid-area:1/1;display:block;justify-self:start;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.aligned-grid>i{{font-family:{residual_families};width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px)*var(--factor) + var(--coarse-live) - {COARSE_OFFSET_PX}px + var(--score-offset),{head.SCORE_STRIDE_PX}px) + var(--local-tie)/{head.LAYOUT_UNITS_PER_PX}*1px))}}
.control-grid>i{{font-family:{control_families};width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px)*var(--factor) + var(--score-offset),{head.SCORE_STRIDE_PX}px) + var(--local-tie)/{head.LAYOUT_UNITS_PER_PX}*1px))}}
body[data-mode="prime"] .panels,body[data-mode="hidden"] .panels{{display:none}}
body[data-mode="aligned"] .control-panel,body[data-mode="aligned"] .coarse-cache{{display:none}}
body[data-mode="control"] .aligned-panel,body[data-mode="control"] .coarse-cache{{display:none}}
"""


def main() -> None:
    fine_reference = json.loads((FINE / "reference.json").read_text())
    certified_reference = json.loads((CERTIFIED / "reference.json").read_text())
    fixtures = certified_reference["allFixtures"]
    if len(fixtures["hiddenVectors"]) != 10:
        raise RuntimeError("the certified screen must contain exactly ten fixtures")
    input_range = float(fine_reference["inputRange"])
    global_scale = float(fine_reference["weightScale"])
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight")[START:STOP], dtype=np.float64)
    global_codes = np.rint(embeddings / global_scale).astype(np.int32)
    multipliers = np.ceil(np.max(np.abs(global_codes), axis=1) / 511).astype(np.int32)
    multipliers[multipliers == 0] = 1
    int10_codes = np.rint(global_codes / multipliers[:, None]).astype(np.int16)
    residual_codes = (
        global_codes - multipliers[:, None] * int10_codes.astype(np.int32)
    ).astype(np.int16)
    reconstructed = multipliers[:, None] * int10_codes.astype(np.int32) + residual_codes
    if not np.array_equal(reconstructed, global_codes):
        raise RuntimeError("aligned decomposition is not exact")
    if int(np.max(np.abs(int10_codes))) > 511:
        raise RuntimeError("aligned coarse code escaped signed int10")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse_bases = []
    residual_bases = []
    font_paths = []
    for shard, start in enumerate(range(0, head.WIDTH, COARSE_SHARD)):
        values = int10_codes[:, start : start + COARSE_SHARD]
        bases = np.sum(np.abs(values.astype(np.int64)), axis=1) + 32
        destination = OUTPUT / f"coarse-{shard}.ttf"
        build_direct_font_backend(
            values,
            destination,
            signed_axes=True,
            base_advance=bases,
            codepoint_start=COARSE_CODEPOINTS[shard],
            axis_tags=[global_axis_tag(dimension) for dimension in range(start, min(start + COARSE_SHARD, head.WIDTH))],
        )
        coarse_bases.append(bases)
        font_paths.append(destination.with_suffix(".woff2"))
    for shard, start in enumerate(range(0, head.WIDTH, RESIDUAL_SHARD)):
        values = residual_codes[:, start : start + RESIDUAL_SHARD]
        bases = np.sum(np.abs(values.astype(np.int64)), axis=1) + 32
        destination = OUTPUT / f"residual-{shard}.ttf"
        build_direct_font_backend(
            values,
            destination,
            signed_axes=True,
            base_advance=bases,
            codepoint_start=RESIDUAL_CODEPOINTS[shard],
            axis_tags=[global_axis_tag(dimension) for dimension in range(start, start + RESIDUAL_SHARD)],
        )
        residual_bases.append(bases)
        font_paths.append(destination.with_suffix(".woff2"))
    coarse_row_bases = np.sum(np.stack(coarse_bases), axis=0)
    residual_row_bases = np.sum(np.stack(residual_bases), axis=0)
    control_ranges, control_row_bases = control_planes(global_codes)

    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.int32)
    exact_logits = hidden @ (global_codes.astype(np.float64) * global_scale).T
    offline_buckets = np.rint(
        (exact_logits - floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int32)
    offline_winners = offline_buckets.argmax(axis=1).astype(int)

    (OUTPUT / "index.html").write_text(render_html(
        coarse_row_bases,
        residual_row_bases,
        control_row_bases,
        multipliers,
        input_range,
        global_scale,
    ))
    (OUTPUT / "index.css").write_text(render_css(input_range))
    reference = {
        "experiment": "aligned-global-int16-residual-group",
        "group": GROUP,
        "tokenRange": [START, STOP - 1],
        "fixtures": {
            "hiddenVectors": fixtures["hiddenVectors"],
            "scoreFloors": fixtures["scoreFloors"],
            "count": len(hidden),
        },
        "decomposition": {
            "formula": "globalCode = m * int10Code + residual",
            "multiplierFormula": "ceil(max(abs(globalCode)) / 511)",
            "exactForEveryCoefficient": True,
            "multiplierRange": [int(multipliers.min()), int(multipliers.max())],
            "int10CodeMaximumMagnitude": int(np.max(np.abs(int10_codes))),
            "residualRange": [int(residual_codes.min()), int(residual_codes.max())],
        },
        "transport": {
            "paidCoarseRepresentationGlyphs": 5,
            "paidCoarseShardAxes": COARSE_SHARD,
            "incrementalResidualGlyphs": 3,
            "residualShardAxes": RESIDUAL_SHARD,
            "controlGlyphs": 12,
            "control": "existing global16-twoplane font bank",
            "coarseOffsetPixels": COARSE_OFFSET_PX,
            "displayScale": DISPLAY_SCALE,
        },
        "inputRange": input_range,
        "globalScale": global_scale,
        "scoreScale": head.SCORE_SCALE,
        "scoreStridePx": head.SCORE_STRIDE_PX,
        "offlineDiagnostic": {
            "buckets": offline_buckets.tolist(),
            "groupWinners": (offline_winners + START).tolist(),
        },
        "fontBytes": {
            "coarse": sum(path.stat().st_size for path in font_paths[:5]),
            "residual": sum(path.stat().st_size for path in font_paths[5:]),
        },
        "controlPlaneMaximumBases": [int(values.max()) for values in control_ranges],
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(
        "# Aligned int10 + exact residual group probe\n\nBrowser status: **pending**.\n"
    )
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "group": GROUP,
        "fixtures": len(hidden),
        "decomposition": reference["decomposition"],
        "transport": reference["transport"],
        "fontBytes": reference["fontBytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
