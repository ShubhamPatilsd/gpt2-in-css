#!/usr/bin/env python3
"""Feed a 3,072-value geometry vector directly into HVAR axes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    font_faces,
    gelu_new,
    global_axis_tag,
    layer_norm,
    model_data,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "anchor-axis-vector-gather"
FONT_OUT = ROOT / "experiments" / "gpt2-block-css"
GEOMETRY_BASE = 2048
GEOMETRY_SCALE = 1024


def real_hidden_state() -> tuple[dict[str, np.ndarray], np.ndarray]:
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    hidden = gelu_new(q_fc.reconstructed @ n2 + data["fc_bias"])
    return data, hidden


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data, hidden = real_hidden_state()
    coordinates = np.arange(MLP_WIDTH, dtype=np.float64)
    alternate = hidden * 0.86 + np.sin(coordinates * 0.071 + 0.4) * 0.025
    hidden_range = float(max(np.max(np.abs(hidden)), np.max(np.abs(alternate))) * 1.01)
    states = [hidden / hidden_range, alternate / hidden_range]

    q_projection = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    expected = [q_projection.codes.astype(np.float64) @ state for state in states]
    projection_fonts = build_font_group(
        "mlp-proj-run",
        q_projection.codes,
        rebuild=False,
        row_specific_bases=True,
        global_axis_offset=0,
    )
    if projection_fonts.row_bases is None:
        raise ValueError("projection fonts require row-specific bases")
    missing = [
        name
        for name in projection_fonts.names
        if not (FONT_OUT / f"{name}.woff2").exists()
    ]
    if missing:
        raise FileNotFoundError(
            "build tools/build_additive_mlp_vector.py first; missing " + ", ".join(missing)
        )

    faces = font_faces("mlp-run", projection_fonts).replace(
        'url("', 'url("../gpt2-block-css/'
    )
    sources = "".join(
        f'<i class="source" id="s{index}" style="anchor-name:--h{index:04d};'
        f'width:{css_number(GEOMETRY_BASE + GEOMETRY_SCALE * states[0][index])}px"></i>'
        for index in range(MLP_WIDTH)
    )
    axis_settings = ",".join(
        f'"{global_axis_tag(index)}" calc('
        f'(anchor-size(--h{index:04d} width) / 1px - {GEOMETRY_BASE}) / {GEOMETRY_SCALE})'
        for index in range(MLP_WIDTH)
    )
    outputs = []
    expected_widths = []
    for output in range(WIDTH):
        characters = "".join(
            f"&#x{start + output:X};"
            for start in projection_fonts.codepoint_starts
        )
        base = sum(int(rows[output]) for rows in projection_fonts.row_bases)
        expected_width = (base + expected[0][output]) * FONT_SIZE / UNITS_PER_EM
        expected_widths.append(expected_width)
        outputs.append(
            f'<i class="output" id="o{output}" data-base="{base}">{characters}</i>'
        )

    css = (
        faces
        + "html,body{margin:0}"
        + f"#sources{{position:fixed;left:-10000px;top:0;width:{GEOMETRY_BASE * 2}px;"
        + "height:1px;contain:layout style}}"
        + ".source{position:absolute;left:0;top:0;display:block;height:1px}"
        + f"#projection{{position:fixed;left:0;top:0;position-anchor:--h0000;"
        + f"font-family:{','.join('mlprunS' + str(i) for i in range(len(projection_fonts.names)))};"
        + f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal;"
        + f"font-variant-ligatures:none;font-variation-settings:{axis_settings}}}"
        + ".output{position:absolute;left:0;top:0;display:inline-block;"
        + "width:max-content;height:1px;overflow:hidden;white-space:pre}"
    )
    (OUT / "style.css").write_text(css)
    tag = hashlib.sha256(css.encode()).hexdigest()[:12]
    html = (
        '<!doctype html><meta charset="utf-8"><title>3,072 geometry values to HVAR axes</title>'
        '<link rel="icon" href="data:,">'
        f'<link rel="stylesheet" href="style.css?v={tag}">'
        f'<div id="sources">{sources}</div>'
        f'<div id="projection">{"".join(outputs)}</div>'
    )
    (OUT / "index.html").write_text(html)
    reference = {
        "inputWidth": MLP_WIDTH,
        "outputWidth": WIDTH,
        "geometryBase": GEOMETRY_BASE,
        "geometryScale": GEOMETRY_SCALE,
        "initialState": states[0].tolist(),
        "alternateState": states[1].tolist(),
        "initialExpected": expected[0].tolist(),
        "alternateExpected": expected[1].tolist(),
        "initialExpectedWidths": expected_widths,
        "fontBytes": sum((FONT_OUT / f"{name}.woff2").stat().st_size for name in projection_fonts.names),
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
        "runtimeJavascript": False,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        {
            "inputs": MLP_WIDTH,
            "outputs": WIDTH,
            "font_bytes": reference["fontBytes"],
            "html_bytes": reference["htmlBytes"],
            "css_bytes": reference["cssBytes"],
        }
    )


if __name__ == "__main__":
    main()
