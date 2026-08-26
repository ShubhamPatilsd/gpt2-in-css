#!/usr/bin/env python3
"""Build a real GPT-2 768->3072 FC+GELU using Grid/Subgrid transport."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    MLP_WIDTH,
    OUT as FONT_OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    font_faces,
    gelu_new,
    model_data,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "grid-subgrid-gpt2-fc"
FONT_SIZE = 512
GEOMETRY_SCALE = 256
GEOMETRY_OFFSET = 4096


def settings(values: np.ndarray, activation_range: float) -> str:
    normalized = values / activation_range
    parts: list[str] = []
    for shard in range(3):
        prefix = chr(ord("A") + shard)
        start = shard * 256
        for local, value in enumerate(normalized[start : start + 256]):
            parts.append(f'"{prefix}{local:03d}" {css_number(float(value))}')
    return ",".join(parts)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)

    # Match the established FC fixture exactly so the existing timeline page is
    # a valid A/B control.
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    from build_gpt2_block_css import layer_norm

    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    attention = composed_weight @ n1 + composed_bias
    residual = data["x"] + attention
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    activation_range = float(np.max(np.abs(n2)) * 1.01)

    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fonts.bases)

    cases: list[dict[str, object]] = []
    for case_index in range(8):
        if case_index == 0:
            vector = n2.copy()
        else:
            # Dense, deterministic changes keep every axis live while remaining
            # inside the calibration range used by both pages.
            rolled = np.roll(n2, case_index * 37)
            vector = np.clip(
                n2 * (0.72 + case_index * 0.025) + rolled * 0.18,
                -activation_range,
                activation_range,
            )
        raw = q_fc.codes.astype(np.float64) @ (vector / activation_range)
        pre = raw * activation_range * q_fc.scales + data["fc_bias"]
        cases.append(
            {
                "input": vector.tolist(),
                "pre": pre.tolist(),
                "hidden": gelu_new(pre).tolist(),
            }
        )

    metrics: list[str] = []
    cells: list[str] = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        factor = activation_range * q_fc.scales[output]
        multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
        offset = (
            GEOMETRY_OFFSET
            + GEOMETRY_SCALE * data["fc_bias"][output]
            - GEOMETRY_SCALE * factor * base_total
        )
        metrics.append(
            f'<i class="metric" style="grid-column:{output + 1};'
            f'width:calc-size(max-content,size * {css_number(multiplier)} '
            f'+ ({css_number(offset)}px))">{characters}</i>'
        )
        cells.append(
            f'<i class="cell" data-index="{output}" style="grid-column:{output + 1}">'
            '<b class="consumer"></b></i>'
        )

    font_css = font_faces("fc", fonts).replace(
        'url("fc-', 'url("../gpt2-block-css/fc-'
    )
    initial_settings = settings(np.asarray(cases[0]["input"]), activation_range)
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>Grid/subgrid real GPT-2 FC + GELU</title>
<style>
{font_css}
@property --pre{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --hidden{{syntax:"<number>";inherits:true;initial-value:-99999}}
.bank{{display:grid;grid-template-columns:repeat({MLP_WIDTH},max-content);grid-template-rows:1px 1px;
 width:max-content;font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;
 font-variation-settings:{initial_settings};font-kerning:none;line-height:1;
 position:fixed;left:0;top:0}}
.metric{{grid-row:1;display:block;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.transport{{display:grid;grid-template-columns:subgrid;grid-column:1/-1;grid-row:2}}
.cell{{container-type:inline-size;position:relative;height:1px;min-width:0;font-style:normal}}
.consumer{{--pre:calc((100cqi / 1px - {GEOMETRY_OFFSET}) / {GEOMETRY_SCALE});
 --t:clamp(-20,calc(.7978845608028654 * (var(--pre) + .044715 * pow(var(--pre),3))),20);
 --hidden:calc(.5 * var(--pre) * (1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)));
 position:absolute;width:calc((var(--hidden) + 10000) * 1px);height:1px}}
</style>
<div id="bank" class="bank">{''.join(metrics)}<div class="transport">{''.join(cells)}</div></div>
'''
    (OUT / "index.html").write_text(html)
    reference = {
        "backend": "grid-subgrid-real-gpt2-fc-gelu",
        "width": WIDTH,
        "outputs": MLP_WIDTH,
        "fontSize": FONT_SIZE,
        "activationRange": activation_range,
        "geometryScale": GEOMETRY_SCALE,
        "geometryOffset": GEOMETRY_OFFSET,
        "baseTotal": base_total,
        "cases": cases,
        "htmlBytes": len(html.encode()),
        "fontBytes": sum((FONT_OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "htmlSha256": hashlib.sha256(html.encode()).hexdigest(),
    }
    (OUT / "reference.json").write_text(json.dumps(reference) + "\n")
    print(
        {
            "html_bytes": reference["htmlBytes"],
            "font_bytes": reference["fontBytes"],
            "tracks": MLP_WIDTH,
        }
    )


if __name__ == "__main__":
    main()
