#!/usr/bin/env python3
"""Probe supersampled HVAR coordinates on GPT-2's closest logit pair."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as baseline
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hvar-coordinate-dither"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
SUBFONTS = ROOT / "experiments" / "gpt2-hvar-grid-output-head-cascade-subfonts"
TOKENS = (11, 13)
PHASE_COUNTS = (1, 2, 4, 5, 6, 7, 8, 16, 32, 64)
F2DOT14_STEP = 1 / 16_384
DISPLAY_SCALE = 0.1


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((FINE / "reference.json").read_text())
    fixture = reference["validation"]["tokenIds"].index(11776)
    hidden = np.asarray(reference["validation"]["hiddenVectors"][fixture])
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight")[:50_257], dtype=np.float64)
    codes = np.rint(embeddings / reference["weightScale"]).astype(np.int16)
    fine_html = (FINE / "index.html").read_text()
    candidates = re.findall(
        r'<i class="candidate" style="--base:([^;]+);'
        r'--factor:([^;]+);--local-tie:([^\"]+)">(.*?)</i>',
        fine_html,
    )
    subfont_css = (SUBFONTS / "index.css").read_text()
    font_faces = subfont_css.split("\n", 1)[0].replace(
        'url("score-',
        'url("../gpt2-hvar-grid-output-head-cascade-subfonts/score-',
    )
    families = ",".join(
        f"Score{plane}{shard}G0"
        for shard in range(6)
        for plane in ("H", "L")
    )

    phase_rules: list[str] = []
    markup: list[str] = []
    for count in PHASE_COUNTS:
        for phase in range(count):
            offset = phase * F2DOT14_STEP / count
            settings = ",".join(
                f'"{baseline.global_axis_tag(dimension)}" '
                f"calc({hidden[dimension]}/{reference['inputRange']} + {offset})"
                for dimension in range(baseline.WIDTH)
            )
            phase_rules.append(
                f".phase-{count}-{phase}{{font-variation-settings:{settings}}}"
            )
        items = []
        offset_sum = F2DOT14_STEP * (count - 1) / 2
        for token in TOKENS:
            base, factor, _, glyphs = candidates[token]
            # Chrome floors each normalized variation coordinate to F2DOT14.
            # Averaging the positive phases removes the input-dependent error;
            # the remaining -step/2 bias is deterministic and folded into the
            # candidate base here.
            correction = DISPLAY_SCALE * int(codes[token].sum()) * (
                offset_sum - count * F2DOT14_STEP / 2
            )
            total_base = count * float(base) + correction
            spans = "".join(
                f'<span class="phase phase-{count}-{phase}">{html.escape(glyphs)}</span>'
                for phase in range(count)
            )
            items.append(
                f'<i class="candidate" data-token="{token}" '
                f'data-base="{total_base}" data-factor="{float(factor) / count}">'
                f"{spans}</i>"
            )
        markup.append(
            f'<section class="sample" data-phases="{count}">{"".join(items)}</section>'
        )

    css = f"""{font_faces}
*{{box-sizing:border-box}}
body{{margin:0}}
.sample{{font-family:{families};font-size:100px;line-height:1;white-space:pre}}
.candidate{{display:block;width:max-content;height:1px;overflow:hidden;font-style:normal}}
.phase{{display:inline}}
{"".join(phase_rules)}
"""
    (OUTPUT / "index.css").write_text(css)
    (OUTPUT / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="index.css">'
        + "".join(markup)
    )
    dense = hidden @ embeddings.T
    quantized = hidden @ (codes.astype(np.float64) * reference["weightScale"]).T
    (OUTPUT / "reference.json").write_text(json.dumps({
        "inputToken": 11776,
        "tokens": list(TOKENS),
        "phaseCounts": list(PHASE_COUNTS),
        "ditherMode": "positive-one-cell-with-floor-bias-correction",
        "denseDifference11Minus13": float(dense[11] - dense[13]),
        "quantizedDifference11Minus13": float(quantized[11] - quantized[13]),
        "expectedDecodedDifference": float(
            (quantized[11] - quantized[13])
            * baseline.SCORE_SCALE * baseline.SCORE_STRIDE_PX
        ),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
