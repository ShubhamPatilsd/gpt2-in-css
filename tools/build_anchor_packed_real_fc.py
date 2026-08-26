#!/usr/bin/env python3
"""Build a real GPT-2 FC HVAR -> packed carrier -> GELU vector probe."""

from __future__ import annotations

import json
import math

import numpy as np

from build_gpt2_block_css import (
    FONT_SIZE,
    OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    build_font_group,
    font_faces,
    gelu_new,
    layer_norm,
    model_data,
    packed_axis_tag,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


HTML = OUT / "anchor-packed-real-fc.html"
CSS = OUT / "anchor-packed-real-fc.css"
REFERENCE = OUT / "anchor-packed-real-fc-reference.json"
LEVELS = 63
OUTPUTS = 4


def input_settings(values: np.ndarray, value_range: float) -> str:
    settings = []
    for index, value in enumerate(values / value_range):
        shard, local = divmod(index, 256)
        settings.append(
            f'"{packed_axis_tag(shard, local)}" {css_number(value)}'
        )
    return ",".join(settings)


def basis_settings(active: int | None) -> str:
    return ",".join(
        f'"A{index:03d}" {1 if index == active else 0}'
        for index in range(OUTPUTS)
    )


def main() -> None:
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    attention = q_attention.reconstructed @ n1 + composed_bias
    residual = data["x"] + attention
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    case_inputs = np.stack((n2, np.roll(n2, 1) * 0.8))
    activation_range = float(np.max(np.abs(case_inputs)) * 1.01)

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    raw = (case_inputs / activation_range) @ q_fc.codes[:OUTPUTS].T
    factors = activation_range * q_fc.scales[:OUTPUTS]
    pre = raw * factors + data["fc_bias"][:OUTPUTS]

    # This test focuses on transport, so the range is derived from both test
    # cases with headroom. Production will use calibrated per-group ranges.
    pre_lo = float(np.min(pre) - max(0.05, np.ptp(pre) * 0.05))
    pre_hi = float(np.max(pre) + max(0.05, np.ptp(pre) * 0.05))
    codes = np.rint(
        np.clip((pre - pre_lo) * LEVELS / (pre_hi - pre_lo), 0, LEVELS)
    ).astype(np.int16)
    reconstructed_pre = pre_lo + codes * (pre_hi - pre_lo) / LEVELS
    hidden = gelu_new(reconstructed_pre)
    hidden_lo = float(min(-0.18, np.min(hidden) - 0.01))
    hidden_hi = float(max(0.18, np.max(hidden) + 0.01))
    progress = (hidden - hidden_lo) / (hidden_hi - hidden_lo)

    zero = basis_settings(None)
    keyframes = "".join(
        f"@keyframes c{index}{{from{{font-variation-settings:{zero}}}"
        f"to{{font-variation-settings:{basis_settings(index)}}}}}"
        for index in range(OUTPUTS)
    )
    sources = []
    for output in range(OUTPUTS):
        characters = "".join(
            f"&#x{start + output:x};" for start in fonts.codepoint_starts
        )
        sources.append(
            f'<i class="source s{output}" style="anchor-name:--a{output}">'
            f"{characters}</i>"
        )
    HTML.write_text(
        "<!doctype html><meta charset=\"utf-8\">"
        "<title>Real GPT-2 packed FC transport</title>"
        "<link rel=\"stylesheet\" href=\"anchor-packed-real-fc.css\">"
        f'<div id="scope">{"".join(sources)}'
        '<div id="packed" style="position:absolute;position-anchor:--a0;'
        'container-type:inline-size;height:1px">'
        '<output id="result">result</output></div></div>'
    )

    digit_lengths = []
    delays = []
    result_math = []
    packed_integer = "(100cqi / 1px)"
    step = (pre_hi - pre_lo) / LEVELS
    for output in range(OUTPUTS):
        raw_length = (
            f"(anchor-size(--a{output} width) * {UNITS_PER_EM} / {FONT_SIZE} "
            f"- {sum(fonts.bases)}px)"
        )
        pre_length = (
            f"({raw_length} * {css_number(factors[output])} + "
            f"({css_number(data['fc_bias'][output])}px))"
        )
        code_length = (
            f"round(nearest,clamp(0px,({pre_length} - "
            f"({css_number(pre_lo)}px)) * {LEVELS} / "
            f"{css_number(pre_hi - pre_lo)},63px),1px)"
        )
        digit_lengths.append(code_length)
        if output == 0:
            digit = f"mod(round(nearest,{packed_integer},1),64)"
        elif output == OUTPUTS - 1:
            digit = f"round(down,{packed_integer}/{64 ** output},1)"
        else:
            digit = (
                f"mod(round(down,{packed_integer}/{64 ** output},1),64)"
            )
        z = f"({css_number(pre_lo)} + {digit} * {css_number(step)})"
        result_math.extend((
            f"--z{output}:calc({z})",
            f"--h{output}:--gelu(var(--z{output}))",
            f"--p{output}:calc((var(--h{output}) - "
            f"({css_number(hidden_lo)})) / "
            f"{css_number(hidden_hi - hidden_lo)})",
        ))
        delays.append(f"calc(-1s * clamp(0,var(--p{output}),1))")

    gelu = (
        f"@function --gelu(--z <number>) returns <number>{{"
        f"--t:clamp(-20,calc({css_number(math.sqrt(2 / math.pi))} * "
        "(var(--z) + .044715 * pow(var(--z),3))),20);"
        "result:calc(.5 * var(--z) * "
        "(1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
    )
    CSS.write_text(
        font_faces("fc", fonts)
        + gelu
        + keyframes
        + f"#scope{{position:relative;font-variation-settings:"
        f"{input_settings(case_inputs[0], activation_range)};"
        f"font-family:{','.join(f'fcS{i}' for i in range(len(fonts.names)))}}}"
        + f".source{{position:absolute;display:inline-flex;width:max-content;"
        f"height:1px;overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;"
        "font-kerning:none}}"
        + "#packed { position: absolute; position-anchor: --a0; "
        "container-type: inline-size; height: 1px; }"
        + "".join(
            f"#packed {{ --d{index}: {value}; }}"
            for index, value in enumerate(digit_lengths)
        )
        + "#packed { width: calc(var(--d0) + 64 * var(--d1) + "
        "4096 * var(--d2) + 262144 * var(--d3)); }"
        + f"#result{{position:absolute;font-variation-settings:{zero};"
        + ";".join(result_math)
        + ";"
        f"animation-name:{','.join(f'c{i}' for i in range(OUTPUTS))};"
        "animation-duration:1s;animation-play-state:paused;"
        "animation-timing-function:linear;animation-fill-mode:both;"
        f"animation-composition:add;animation-delay:{','.join(delays)}}}"
    )
    REFERENCE.write_text(json.dumps({
        "settings": [input_settings(row, activation_range) for row in case_inputs],
        "raw": raw.tolist(),
        "pre": pre.tolist(),
        "codes": codes.tolist(),
        "reconstructedPre": reconstructed_pre.tolist(),
        "hidden": hidden.tolist(),
        "progress": progress.tolist(),
        "ranges": {
            "activation": activation_range,
            "pre": [pre_lo, pre_hi],
            "hidden": [hidden_lo, hidden_hi],
        },
        "baseTotal": sum(fonts.bases),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
