#!/usr/bin/env python3
"""Build a real GPT-2 FC -> GELU -> two-lane SWAR projection slice."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
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


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "hvar-swar-mlp-slice"
FONT_ROOT = ROOT / "experiments" / "gpt2-block-css"
RADIX = 32_768
HALF_RADIX = RADIX // 2
LEVELS = 63
OUTPUTS = 128
GEOMETRY_BASE = 4_096
GEOMETRY_SCALE = 128


def balanced_sum(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced_sum(terms[:middle])} + {balanced_sum(terms[middle:])})"


def input_settings(values: np.ndarray, value_range: float) -> str:
    return ",".join(
        f'"{packed_axis_tag(index // 256, index % 256)}" '
        f"{css_number(value / value_range)}"
        for index, value in enumerate(values)
    )


def pair_dot_expression(packet: int, w0: int, w1: int, scale: float) -> str:
    packed_weight = w1 + RADIX * w0
    source = f"(anchor-size(--p-{packet} width) / 1px)"
    dot = (
        "(mod("
        f"round(nearest,({source} * {packed_weight}) / {RADIX},1)"
        f" + {HALF_RADIX},{RADIX}) - {HALF_RADIX})"
    )
    return f"{css_number(GEOMETRY_SCALE * scale)}px * {dot}"


def main() -> None:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()

    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    case_inputs = np.stack((n2, np.roll(n2, 1) * 0.8))
    activation_range = float(np.max(np.abs(case_inputs)) * 1.01)

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fonts.bases)
    raw = (case_inputs / activation_range) @ q_fc.codes.T
    factors = activation_range * q_fc.scales
    pre = raw * factors + data["fc_bias"]

    observed_span = np.ptp(pre, axis=0)
    margins = np.maximum(0.05, observed_span * 0.1)
    pre_lo = np.min(pre, axis=0) - margins
    pre_hi = np.max(pre, axis=0) + margins
    pre_steps = (pre_hi - pre_lo) / LEVELS
    pre_codes = np.rint(np.clip((pre - pre_lo) / pre_steps, 0, LEVELS)).astype(np.int64)
    browser_pre = pre_lo + pre_codes * pre_steps
    browser_hidden = gelu_new(browser_pre)

    hidden_grid = gelu_new(
        pre_lo[None, :] + np.arange(LEVELS + 1)[:, None] * pre_steps[None, :]
    )
    hidden_lo = np.min(hidden_grid, axis=0)
    hidden_hi = np.max(hidden_grid, axis=0)
    hidden_steps = np.maximum((hidden_hi - hidden_lo) / LEVELS, 1e-9)
    hidden_codes = np.rint(
        np.clip((browser_hidden - hidden_lo) / hidden_steps, 0, LEVELS)
    ).astype(np.int64)
    hidden_reconstructed = hidden_lo + hidden_codes * hidden_steps

    projection_weight = data["mlp_proj_weight"][:OUTPUTS]
    projection_bias = data["mlp_proj_bias"][:OUTPUTS]
    effective_weight = projection_weight * hidden_steps[None, :]
    q_effective = quantize_float_rows(effective_weight, bits=8)
    projection_base = projection_bias + projection_weight @ hidden_lo
    expected_transport = (
        hidden_codes @ q_effective.reconstructed.T + projection_base
    )
    expected_float = gelu_new(pre) @ projection_weight.T + projection_bias
    fast_hidden = browser_pre / (
        1 + np.exp(-1.702 * np.clip(browser_pre, -10, 10))
    )
    fast_hidden_codes = np.rint(
        np.clip((fast_hidden - hidden_lo) / hidden_steps, 0, LEVELS)
    ).astype(np.int64)
    expected_fast_transport = (
        fast_hidden_codes @ q_effective.reconstructed.T + projection_base
    )

    faces = font_faces("fc", fonts).replace('url("', 'url("../gpt2-block-css/')
    sources = []
    fused_sources = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:x};" for start in fonts.codepoint_starts
        )
        sources.append(
            f'<i class="source" style="anchor-name:--a-{output}">{characters}</i>'
        )
        fused_sources.append(
            f'<i class="source" style="anchor-name:--a-{output};'
            f'--factor:{css_number(factors[output])};'
            f'--bias:{css_number(data["fc_bias"][output])};'
            f'--hidden-lo:{css_number(hidden_lo[output])};'
            f'--hidden-step:{css_number(hidden_steps[output])}">{characters}</i>'
        )

    pack_rules = []
    fused_pack_rules = []
    packs = []
    for packet, output in enumerate(range(0, MLP_WIDTH, 2)):
        declarations = []
        for lane, index in enumerate((output, output + 1)):
            raw_value = (
                f"((anchor-size(--a-{index} width) * {UNITS_PER_EM} / "
                f"{FONT_SIZE} - {base_total}px) / 1px)"
            )
            declarations.extend((
                f"--z{lane}:calc({raw_value} * {css_number(factors[index])} "
                f"+ ({css_number(data['fc_bias'][index])}))",
                f"--t{lane}:clamp(-20,calc({css_number(math.sqrt(2 / math.pi))} * "
                f"(var(--z{lane}) + .044715 * pow(var(--z{lane}),3))),20)",
                f"--h{lane}:calc(.5 * var(--z{lane}) * "
                f"(1 + (exp(2 * var(--t{lane})) - 1) / "
                f"(exp(2 * var(--t{lane})) + 1)))",
                f"--c{lane}:round(nearest,clamp(0,"
                f"(var(--h{lane}) - ({css_number(hidden_lo[index])})) / "
                f"{css_number(hidden_steps[index])},{LEVELS}),1)",
            ))
        declarations.extend((
            f"width:calc((var(--c0) + {RADIX} * var(--c1)) * 1px)",
            f"anchor-name:--p-{packet}",
        ))
        pack_rules.append(f".p-{packet}{{{';'.join(declarations)}}}")
        fused_pack_rules.append(
            f".p-{packet}{{width:calc(anchor-size(--a-{output} width) + "
            f"{RADIX} * anchor-size(--a-{output + 1} width));"
            f"anchor-name:--p-{packet}}}"
        )
        packs.append(f'<i class="packet p-{packet}"></i>')

    output_rules = []
    outputs = []
    for output, row in enumerate(q_effective.codes):
        terms = [
            pair_dot_expression(
                packet,
                int(row[index]),
                int(row[index + 1]),
                float(q_effective.scales[output]),
            )
            for packet, index in enumerate(range(0, MLP_WIDTH, 2))
        ]
        constant = GEOMETRY_BASE + GEOMETRY_SCALE * projection_base[output]
        output_rules.append(
            f".o-{output}{{width:calc({css_number(constant)}px + "
            f"{balanced_sum(terms)})}}"
        )
        outputs.append(f'<i class="result o-{output}"></i>')

    css = (
        faces
        + "#scope{position:fixed;inset:0;contain:layout style;anchor-scope:all;"
        f"--fc-settings:{input_settings(case_inputs[0], activation_range)}}}"
        + ".source{position:absolute;display:inline-flex;width:max-content;height:1px;"
        f"overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;font-kerning:none;"
        f"font-family:{','.join(f'fcS{i}' for i in range(len(fonts.names)))};"
        "font-variation-settings:var(--fc-settings);visibility:hidden}"
        + ".packet,.result{position:fixed;left:0;top:0;height:1px;display:block;"
        "visibility:hidden}"
        + "".join(pack_rules)
        + "".join(output_rules)
    )
    html = (
        "<!doctype html><meta charset=\"utf-8\"><title>Real GPT-2 HVAR + SWAR MLP slice</title>"
        '<link rel="stylesheet" href="style.css"><main id="scope">'
        + "".join(sources)
        + "".join(packs)
        + "".join(outputs)
        + "</main>"
    )
    (OUT / "style.css").write_text(css)
    (OUT / "index.html").write_text(html)

    fused_pre = (
        f"((((size * {UNITS_PER_EM} / {FONT_SIZE}) / 1px - {base_total}) "
        "* var(--factor) + var(--bias)))"
    )
    fused_t = (
        f"clamp(-20,calc({css_number(math.sqrt(2 / math.pi))} * "
        f"({fused_pre} + .044715 * pow({fused_pre},3))),20)"
    )
    fused_hidden = (
        f"(.5 * {fused_pre} * (1 + (exp(2 * {fused_t}) - 1) / "
        f"(exp(2 * {fused_t}) + 1)))"
    )
    def fused_stylesheet(hidden_expression: str) -> str:
        return (
            faces
            + "#scope{position:fixed;inset:0;contain:layout style;anchor-scope:all;"
            f"--fc-settings:{input_settings(case_inputs[0], activation_range)}}}"
            + ".source{position:absolute;display:inline-flex;height:1px;overflow:hidden;"
            f"white-space:pre;font-size:{FONT_SIZE}px;font-kerning:none;"
            f"font-family:{','.join(f'fcS{i}' for i in range(len(fonts.names)))};"
            "font-variation-settings:var(--fc-settings);visibility:hidden;width:0;"
            "width:calc-size(max-content,"
            f"round(nearest,clamp(0,({hidden_expression} - var(--hidden-lo)) / "
            "var(--hidden-step),63),1) * 1px)}"
            + ".packet,.result{position:fixed;left:0;top:0;height:1px;display:block;"
            "visibility:hidden}"
            + "".join(fused_pack_rules)
            + "".join(output_rules)
        )

    def fused_document(label: str, stylesheet: str) -> str:
        return (
            f"<!doctype html><meta charset=\"utf-8\"><title>{label}</title>"
            f'<link rel="stylesheet" href="{stylesheet}"><main id="scope">'
            + "".join(fused_sources)
            + "".join(packs)
            + "".join(outputs)
            + "</main>"
        )

    fused_css = fused_stylesheet(fused_hidden)
    fused_html = fused_document(
        "Fused real GPT-2 HVAR + SWAR MLP slice", "style-fused.css"
    )
    (OUT / "style-fused.css").write_text(fused_css)
    (OUT / "fused.html").write_text(fused_html)
    fused_fast_hidden = (
        f"({fused_pre} / (1 + exp(-1.702 * clamp(-10,{fused_pre},10))))"
    )
    fused_fast_css = fused_stylesheet(fused_fast_hidden)
    fused_fast_html = fused_document(
        "Fast fused real GPT-2 HVAR + SWAR MLP slice",
        "style-fused-fast.css",
    )
    (OUT / "style-fused-fast.css").write_text(fused_fast_css)
    (OUT / "fused-fast.html").write_text(fused_fast_html)
    reference = {
        "settings": [input_settings(row, activation_range) for row in case_inputs],
        "expectedTransport": expected_transport.tolist(),
        "expectedFastTransport": expected_fast_transport.tolist(),
        "expectedFloat": expected_float.tolist(),
        "hiddenCodes": hidden_codes.tolist(),
        "fastHiddenCodes": fast_hidden_codes.tolist(),
        "expectedPacketWidths": (
            hidden_codes[:, 0::2] + RADIX * hidden_codes[:, 1::2]
        ).tolist(),
        "pre": pre.tolist(),
        "browserPre": browser_pre.tolist(),
        "geometryBase": GEOMETRY_BASE,
        "geometryScale": GEOMETRY_SCALE,
        "radix": RADIX,
        "fontSize": FONT_SIZE,
        "unitsPerEm": UNITS_PER_EM,
        "baseTotal": base_total,
        "outputs": OUTPUTS,
        "sources": MLP_WIDTH,
        "packets": MLP_WIDTH // 2,
        "projectionTerms": OUTPUTS * MLP_WIDTH // 2,
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
        "fusedHtmlBytes": len(fused_html.encode()),
        "fusedCssBytes": len(fused_css.encode()),
        "fusedFastHtmlBytes": len(fused_fast_html.encode()),
        "fusedFastCssBytes": len(fused_fast_css.encode()),
        "fontBytes": sum((FONT_ROOT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "transportRmseVsFloat": float(np.sqrt(np.mean((expected_transport - expected_float) ** 2))),
        "transportMaxErrorVsFloat": float(np.max(np.abs(expected_transport - expected_float))),
        "buildSeconds": time.perf_counter() - started,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: reference[key] for key in (
        "htmlBytes", "cssBytes", "fontBytes", "transportRmseVsFloat",
        "transportMaxErrorVsFloat", "buildSeconds",
    )}, indent=2))


if __name__ == "__main__":
    main()
