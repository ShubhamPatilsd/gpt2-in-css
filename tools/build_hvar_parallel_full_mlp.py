#!/usr/bin/env python3
"""Build the full real GPT-2 768 -> 3072 -> 768 MLP in parallel font groups."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_avar2_hvar_real_gpt2_tile import TOKEN_IDS, block_zero_mlp_input
from build_gpt2_block_css import (
    FONT_SIZE,
    OUT as FC_FONT_DIR,
    QUANT_BITS,
    UNITS_PER_EM,
    build_font_group,
    font_faces,
    global_axis_tag,
    layer_norm,
    matrix_shadow,
    model_data,
)
from build_hvar_parallel_mlp_group import (
    BASE_ADVANCE,
    CODEPOINT_START,
    GEOMETRY_OFFSET,
    GEOMETRY_SCALE,
    HIDDEN,
    OUTPUTS,
    OUTPUT_SCALE,
    PREACTIVATION_SCALE,
    add_sparse_gelu_avar2,
    gelu,
    gelu_knots,
    piecewise_gelu,
    replace_linear_hvar,
    replace_hvar,
)
from build_matrix_backend_prototypes import build_direct_font_backend
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
BACKEND = os.environ.get("HVAR_FULL_MLP_BACKEND", "hvar-knots")
GROUPS = int(os.environ.get("HVAR_FULL_MLP_GROUPS", "12"))
OUTPUT_NAME = (
    "avar2-gelu-linear-hvar-full-mlp"
    if BACKEND == "avar2-gelu"
    else "hvar-parallel-full-mlp"
)
if GROUPS != 12:
    OUTPUT_NAME += f"-g{GROUPS}"
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
HIDDEN_PAIRS = 3072 // 2
PAIR_QUOTIENT, PAIR_REMAINDER = divmod(HIDDEN_PAIRS, GROUPS)
GROUP_WIDTHS = [
    2 * (PAIR_QUOTIENT + (1 if group < PAIR_REMAINDER else 0))
    for group in range(GROUPS)
]
if max(GROUP_WIDTHS) > HIDDEN:
    raise ValueError(f"{GROUPS} groups exceed the {HIDDEN}-axis font limit")
GROUP_STARTS = np.cumsum([0, *GROUP_WIDTHS[:-1]]).tolist()
MAX_GROUP_WIDTH = max(GROUP_WIDTHS)
REBUILD_FONTS = os.environ.get("HVAR_PARALLEL_REBUILD_FONTS", "0") == "1"
INPUT_GEOMETRY_SCALE = 2048.0
INPUT_GEOMETRY_OFFSET = 4096.0


def group_tree(group: int, metrics: list[str], width: int) -> str:
    child = f'<div class="projection projection-{group}">' + "".join(
        f'<i class="partial partial-{group}-{output}">&#x{CODEPOINT_START + output:X};</i>'
        for output in range(OUTPUTS)
    ) + "</div>"
    for pair in reversed(range(width // 2)):
        first = 2 * pair
        child = (
            metrics[first]
            + metrics[first + 1]
            + f'<div class="probe probe-{group}-{pair}">{child}</div>'
        )
    return f'<div class="group group-{group}">{child}</div>'


def projection_tree(group: int, width: int) -> str:
    """Projection half of a group, without nesting its FC glyph metrics."""
    child = f'<div class="projection projection-{group}">' + "".join(
        f'<i class="partial partial-{group}-{output}">&#x{CODEPOINT_START + output:X};</i>'
        for output in range(OUTPUTS)
    ) + "</div>"
    for pair in reversed(range(width // 2)):
        child = f'<div class="probe probe-{group}-{pair}">{child}</div>'
    return f'<div class="group group-{group}">{child}</div>'


def named_group_tree(
    prefix: str,
    group: int,
    metrics: list[str],
    width: int,
) -> str:
    """Build an independently named projection group for a later block."""
    child = f'<div class="{prefix}-projection {prefix}-projection-{group}">' + "".join(
        f'<i class="{prefix}-partial {prefix}-partial-{group}-{output}">'
        f'&#x{CODEPOINT_START + output:X};</i>'
        for output in range(OUTPUTS)
    ) + "</div>"
    for pair in reversed(range(width // 2)):
        first = 2 * pair
        child = (
            metrics[first]
            + metrics[first + 1]
            + f'<div class="{prefix}-probe {prefix}-probe-{group}-{pair}">{child}</div>'
        )
    return f'<div class="{prefix}-group {prefix}-group-{group}">{child}</div>'


def main() -> None:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    data = model_data()
    inputs = np.stack([block_zero_mlp_input(token_id, tensors) for token_id in TOKEN_IDS])
    activation_range = float(np.max(np.abs(inputs)) * 1.01)
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fc_fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fc_fonts.bases)

    font_faces_css = []
    group_html = []
    group_css = []
    represented_groups = []
    exact_groups = []
    projection_font_bytes = 0
    preactivation_minimum = float("inf")
    preactivation_maximum = float("-inf")

    for group, (start, width) in enumerate(zip(GROUP_STARTS, GROUP_WIDTHS)):
        stop = start + width
        tags = [global_axis_tag(index) for index in range(width)]
        projection = data["mlp_proj_weight"][:, start:stop]
        preactivations = (
            inputs @ q_fc.reconstructed[start:stop].T + data["fc_bias"][start:stop]
        )
        preactivation_minimum = min(preactivation_minimum, float(np.min(preactivations)))
        preactivation_maximum = max(preactivation_maximum, float(np.max(preactivations)))
        if np.max(np.abs(preactivations / PREACTIVATION_SCALE)) > 1:
            raise ValueError(
                f"group {group} preactivation exceeds {PREACTIVATION_SCALE}: "
                f"{np.max(np.abs(preactivations))}"
            )
        represented_groups.append(piecewise_gelu(preactivations) @ projection.T)
        # This is the exact GELU target for the quantized FC matrix.
        from build_gpt2_block_css import gelu_new
        exact_groups.append(gelu_new(preactivations) @ projection.T)

        woff2 = OUTPUT / f"gelu-projection-{group}.woff2"
        if REBUILD_FONTS or not woff2.exists():
            ttf = OUTPUT / f"gelu-projection-{group}.ttf"
            build_direct_font_backend(
                np.zeros((OUTPUTS, width), dtype=np.int16),
                ttf,
                signed_axes=True,
                base_advance=BASE_ADVANCE,
                codepoint_start=CODEPOINT_START,
                axis_tags=tags,
            )
            font = TTFont(ttf, recalcTimestamp=False)
            if BACKEND == "avar2-gelu":
                add_sparse_gelu_avar2(font, tags)
                replace_linear_hvar(font, tags, projection)
            else:
                replace_hvar(font, tags, projection)
            font.recalcTimestamp = False
            font.save(ttf)
            font = TTFont(ttf, recalcTimestamp=False)
            font.flavor = "woff2"
            font.save(woff2)
        projection_font_bytes += woff2.stat().st_size
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        font_faces_css.append(
            f'@font-face{{font-family:GeluProjection{group};'
            f'src:url("gelu-projection-{group}.woff2?v={digest}") format("woff2")}}'
        )

        metrics = []
        rules = []
        for local, hidden in enumerate(range(start, stop)):
            characters = "".join(
                f"&#x{codepoint + hidden:X};" for codepoint in fc_fonts.codepoint_starts
            )
            factor = activation_range * q_fc.scales[hidden]
            multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
            offset = (
                GEOMETRY_OFFSET
                + GEOMETRY_SCALE * data["fc_bias"][hidden]
                - GEOMETRY_SCALE * factor * base_total
            )
            metrics.append(
                f'<i class="metric metric-{group}-{local}" style="width:calc-size(max-content,'
                f'size * {css_number(float(multiplier))} + ({css_number(float(offset))}px))">'
                f"{characters}</i>"
            )
            rules.append(
                f'.metric-{group}-{local}{{anchor-name:--g{group}m{local}}}'
            )
        for pair in range(width // 2):
            first = 2 * pair
            rules.append(
                f'.probe-{group}-{pair}{{width:anchor-size(--g{group}m{first} width);'
                f'height:anchor-size(--g{group}m{first + 1} width);container-type:size}}'
            )
            target = (
                f'.probe-{group}-{pair + 1}'
                if pair + 1 < width // 2
                else f'.projection-{group}'
            )
            rules.append(
                f'{target}{{--z{first}:calc((100cqi / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * PREACTIVATION_SCALE});'
                f'--z{first + 1}:calc((100cqb / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * PREACTIVATION_SCALE})}}'
            )
        projection_settings = ",".join(
            f'"{tag}" var(--z{index})' for index, tag in enumerate(tags)
        )
        rules.append(
            f'.projection-{group}{{font-family:GeluProjection{group};'
            f'font-variation-settings:{projection_settings}}}'
        )
        rules.extend(
            f'.partial-{group}-{output}{{anchor-name:--g{group}o{output}}}'
            for output in range(OUTPUTS)
        )
        group_css.append("".join(rules))
        group_html.append(group_tree(group, metrics, width))
        print(f"built group {group + 1}/{GROUPS}", flush=True)

    represented = np.sum(represented_groups, axis=0)
    exact = np.sum(exact_groups, axis=0)
    controls = "".join(
        f'<input type="radio" name="case" id="case-{case}"'
        f'{" checked" if case == 0 else ""}>'
        for case in range(len(TOKEN_IDS))
    )
    input_rules = []
    for case, vector in enumerate(inputs):
        settings = []
        for shard in range(3):
            start = shard * 256
            for local, value in enumerate(vector[start : start + 256] / activation_range):
                prefix = chr(ord("A") + shard)
                settings.append(f'"{prefix}{local:03d}" {css_number(float(value))}')
        input_rules.append(
            f'body:has(#case-{case}:checked) .root{{font-variation-settings:'
            + ",".join(settings)
            + "}"
        )
    combined = []
    combined_rules = []
    base_subtraction = (GROUPS - 1) * BASE_ADVANCE
    for output in range(OUTPUTS):
        anchors = " + ".join(
            f"anchor-size(--g{group}o{output} width)" for group in range(GROUPS)
        )
        combined_rules.append(
            f'.output-{output}{{width:calc({anchors} - {base_subtraction}px)}}'
        )
        combined.append(f'<i class="output output-{output}" id="output-{output}"></i>')
    fc_face_css = font_faces("fc", fc_fonts).replace(
        'url("fc-', 'url("../gpt2-block-css/fc-'
    )
    html = f'''<!doctype html><meta charset="utf-8"><title>Parallel full GPT-2 MLP</title>
<style>{fc_face_css}{''.join(font_faces_css)}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.root{{anchor-scope:all;font-family:fcS0,fcS1,fcS2;
font-size:{FONT_SIZE}px;font-kerning:none;line-height:1}}.metric,.partial,.output{{position:fixed;
inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}.projection{{font-size:1000px;
font-kerning:none;line-height:1}}.partial{{width:max-content}}.output{{font-family:initial;font-size:1px}}
{''.join(input_rules)}{''.join(group_css)}{''.join(combined_rules)}</style>{controls}
<div class="root">{''.join(group_html)}<div class="combined">{''.join(combined)}</div></div>'''
    (OUTPUT / "index.html").write_text(html)

    # Composable form: obtain all 768 FC inputs from live geometry rather than
    # putting the case values directly in font-variation-settings.
    connected_axis_settings = []
    numeric_axis_settings = []
    for shard in range(3):
        for local in range(256):
            prefix = chr(ord("A") + shard)
            index = shard * 256 + local
            connected_axis_settings.append(f'"{prefix}{local:03d}" var(--x{index})')
            numeric_axis_settings.append(
                f'"{prefix}{local:03d}" var(--input-{index})'
            )
    connected_case_rules = []
    for case, vector in enumerate(inputs / activation_range):
        connected_case_rules.append(
            f'body:has(#case-{case}:checked) .input-stage{{'
            + ";".join(
                f"--input-{index}:{css_number(float(value))}"
                for index, value in enumerate(vector)
            )
            + "}"
        )
    input_metrics = [
        f'<i class="input-metric input-metric-{index}"></i>'
        for index in range(768)
    ]
    input_rules = []
    for index in range(768):
        input_rules.append(
            f'.input-metric-{index}{{anchor-name:--input-{index};'
            f'width:calc((var(--input-{index}) * {INPUT_GEOMETRY_SCALE} '
            f'+ {INPUT_GEOMETRY_OFFSET}) * 1px)}}'
        )
    connected_root = (
        f'<div class="root">{"".join(group_html)}'
        f'<div class="combined">{"".join(combined)}</div></div>'
    )
    for pair in reversed(range(384)):
        first = 2 * pair
        connected_root = (
            input_metrics[first]
            + input_metrics[first + 1]
            + f'<div class="input-probe input-probe-{pair}">{connected_root}</div>'
        )
        target = f'.input-probe-{pair + 1}' if pair + 1 < 384 else ".root"
        input_rules.append(
            f'.input-probe-{pair}{{width:anchor-size(--input-{first} width);'
            f'height:anchor-size(--input-{first + 1} width);container-type:size}}'
            f'{target}{{--x{first}:calc((100cqi / 1px - {INPUT_GEOMETRY_OFFSET}) / '
            f'{INPUT_GEOMETRY_SCALE});--x{first + 1}:calc((100cqb / 1px - '
            f'{INPUT_GEOMETRY_OFFSET}) / {INPUT_GEOMETRY_SCALE})}}'
        )
    connected_html = f'''<!doctype html><meta charset="utf-8"><title>Connected-input full GPT-2 MLP</title>
<style>{fc_face_css}{''.join(font_faces_css)}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --x{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(768))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.input-stage,.root{{anchor-scope:all}}
.root{{font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(connected_axis_settings)}}}.metric,.partial,.output,.input-metric{{
position:fixed;inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;
font-style:normal}}.probe,.input-probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}
.projection{{font-size:1000px;font-kerning:none;line-height:1}}.partial{{width:max-content}}
.output{{font-family:initial;font-size:1px}}{''.join(connected_case_rules)}{''.join(input_rules)}
{''.join(group_css)}{''.join(combined_rules)}</style>{controls}<div class="input-stage">{connected_root}</div>'''
    (OUTPUT / "connected-input.html").write_text(connected_html)

    # Real nonlinear boundary: compute block-0 LN2 with CSS math, expose its
    # 768 results as geometry, and feed those live values into the MLP.
    token_inputs = []
    normalized_inputs = []
    residual_inputs = []
    for token_id in TOKEN_IDS:
        token_input = np.asarray(
            tensors.tensor("wte.weight")[token_id]
            + tensors.tensor("wpe.weight")[0],
            dtype=np.float64,
        )
        normalized = layer_norm(token_input, data["ln1_gamma"], data["ln1_beta"])
        token_inputs.append(token_input)
        normalized_inputs.append(normalized)
        value = data["v_weight"] @ normalized + data["v_bias"]
        residual_inputs.append(
            token_input
            + data["attn_proj_weight"] @ value
            + data["attn_proj_bias"]
        )
    token_inputs = np.stack(token_inputs)
    normalized_inputs = np.stack(normalized_inputs)
    residual_inputs = np.stack(residual_inputs)
    layernorm_outputs = np.stack([
        layer_norm(vector, data["ln2_gamma"], data["ln2_beta"])
        for vector in residual_inputs
    ])
    if not np.allclose(layernorm_outputs, inputs, atol=1e-10, rtol=1e-10):
        raise ValueError("reconstructed LN2 inputs do not match the MLP fixtures")
    residual_names = [f"var(--r1-{index})" for index in range(768)]
    layernorm_mean = f"calc(({' + '.join(residual_names)}) / 768)"
    layernorm_variance = "calc((" + " + ".join(
        f"(var(--r1-{index}) - var(--ln-mean)) * "
        f"(var(--r1-{index}) - var(--ln-mean))"
        for index in range(768)
    ) + ") / 768)"
    layernorm_inputs = []
    for index in range(768):
        normalized = (
            f"((var(--r1-{index}) - var(--ln-mean)) / "
            f"sqrt(var(--ln-variance) + 0.00001) * "
            f"{css_number(float(data['ln2_gamma'][index]))} + "
            f"{css_number(float(data['ln2_beta'][index]))})"
        )
        layernorm_inputs.append(
            f"--input-{index}:calc({normalized} / {css_number(activation_range)})"
        )
    residual_case_rules = []
    for case, vector in enumerate(residual_inputs):
        residual_case_rules.append(
            f'body:has(#case-{case}:checked) .layernorm-stage{{'
            + ";".join(
                f"--r1-{index}:{css_number(float(value))}"
                for index, value in enumerate(vector)
            )
            + "}"
        )
    layernorm_html = f'''<!doctype html><meta charset="utf-8"><title>LayerNorm-connected full GPT-2 MLP</title>
<style>{fc_face_css}{''.join(font_faces_css)}
@property --ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --x{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(768))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.input-stage,.root{{anchor-scope:all}}
.layernorm-stage{{--ln-mean:{layernorm_mean};--ln-variance:{layernorm_variance};
{';'.join(layernorm_inputs)}}}
.root{{font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(connected_axis_settings)}}}.metric,.partial,.output,.input-metric{{
position:fixed;inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;
font-style:normal}}.probe,.input-probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}
.projection{{font-size:1000px;font-kerning:none;line-height:1}}.partial{{width:max-content}}
.output{{font-family:initial;font-size:1px}}{''.join(residual_case_rules)}{''.join(input_rules)}
{''.join(group_css)}{''.join(combined_rules)}</style>{controls}
<div class="layernorm-stage"><div class="input-stage">{connected_root}</div></div>'''
    (OUTPUT / "connected-layernorm-input.html").write_text(layernorm_html)

    # When the producer already yields CSS numbers, do not round-trip through
    # 768 geometry widths. LayerNorm's normalized numbers can drive FC directly.
    layernorm_numeric_html = f'''<!doctype html><meta charset="utf-8"><title>Numeric LayerNorm-connected full GPT-2 MLP</title>
<style>{fc_face_css}{''.join(font_faces_css)}
@property --ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}.root{{anchor-scope:all}}
.layernorm-stage{{--ln-mean:{layernorm_mean};--ln-variance:{layernorm_variance};
{';'.join(layernorm_inputs)}}}
.root{{font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(numeric_axis_settings)}}}.metric,.partial,.output{{position:fixed;
inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}.projection{{font-size:1000px;
font-kerning:none;line-height:1}}.partial{{width:max-content}}.output{{font-family:initial;font-size:1px}}
{''.join(residual_case_rules)}{''.join(group_css)}{''.join(combined_rules)}</style>{controls}
<div class="layernorm-stage"><div class="root">{''.join(group_html)}
<div class="combined">{''.join(combined)}</div></div></div>'''
    (OUTPUT / "connected-layernorm-numeric-input.html").write_text(
        layernorm_numeric_html
    )

    # Real dense predecessor. With one token, causal attention returns V, so
    # V and the attention output projection compose into one 768x768 map.
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_composed = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    composed_fonts_exist = all(
        (FC_FONT_DIR / f"attn-composed-s{shard}.woff2").exists()
        for shard in range(3)
    )
    composed_fonts = build_font_group(
        "attn-composed",
        q_composed.codes,
        rebuild=not composed_fonts_exist,
    )
    n1_range = float(np.max(np.abs(normalized_inputs)) * 1.01)
    attention_shadow = matrix_shadow(
        "connected-attn",
        composed_fonts,
        [f"--n1-{index}" for index in range(768)],
        n1_range,
        list(range(768)),
        family_prefix="composed-attn",
        direct_readback=True,
    ).replace(
        'href="stage-connected-attn.css',
        'href="../gpt2-block-css/stage-connected-attn.css',
    )
    composed_face_css = font_faces("composedattn", composed_fonts).replace(
        'url("attn-composed-', 'url("../gpt2-block-css/attn-composed-'
    )
    attention_case_rules = []
    for case, (token_input, normalized) in enumerate(
        zip(token_inputs, normalized_inputs)
    ):
        attention_case_rules.append(
            f'body:has(#case-{case}:checked) .attention-host{{'
            + ";".join(
                [
                    *(
                        f"--x-{index}:{css_number(float(value))}"
                        for index, value in enumerate(token_input)
                    ),
                    *(
                        f"--n1-{index}:{css_number(float(value))}"
                        for index, value in enumerate(normalized)
                    ),
                ]
            )
            + "}"
        )
    attention_residual = []
    for index in range(768):
        factor = n1_range * q_composed.scales[index]
        attention_residual.append(
            f"--r1-{index}:calc(var(--x-{index}) + var(--raw-{index:03d}) * "
            f"{css_number(float(factor))} + {css_number(float(composed_bias[index]))})"
        )
    quantized_residual_inputs = (
        token_inputs
        + normalized_inputs @ q_composed.reconstructed.T
        + composed_bias
    )
    quantized_layernorm_outputs = np.stack([
        layer_norm(vector, data["ln2_gamma"], data["ln2_beta"])
        for vector in quantized_residual_inputs
    ])
    attention_preactivations = (
        quantized_layernorm_outputs @ q_fc.reconstructed.T + data["fc_bias"]
    )
    attention_represented = (
        np.asarray(piecewise_gelu(attention_preactivations))
        @ data["mlp_proj_weight"].T
    )
    from build_gpt2_block_css import gelu_new
    attention_exact = (
        gelu_new(attention_preactivations) @ data["mlp_proj_weight"].T
    )
    attention_block_represented = (
        quantized_residual_inputs
        + attention_represented
        + data["mlp_proj_bias"]
    )
    attention_block_exact = (
        quantized_residual_inputs
        + attention_exact
        + data["mlp_proj_bias"]
    )
    if np.max(np.abs(quantized_layernorm_outputs / activation_range)) > 1:
        raise ValueError("attention-connected LN2 exceeds the calibrated MLP range")
    attention_html = f'''<!doctype html><meta charset="utf-8"><title>Attention-connected full GPT-2 MLP</title>
<style>{fc_face_css}{composed_face_css}{''.join(font_faces_css)}
@property --ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --x{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(768))}
{''.join(f'@property --raw-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(768))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}css-stage{{display:block}}
.input-stage,.root{{anchor-scope:all}}.layernorm-stage{{{';'.join(attention_residual)};
--ln-mean:{layernorm_mean};--ln-variance:{layernorm_variance};{';'.join(layernorm_inputs)}}}
.root{{font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(connected_axis_settings)}}}.metric,.partial,.output,.input-metric{{
position:fixed;inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;
font-style:normal}}.probe,.input-probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}
.projection{{font-size:1000px;font-kerning:none;line-height:1}}.partial{{width:max-content}}
.output{{font-family:initial;font-size:1px}}{''.join(attention_case_rules)}{''.join(input_rules)}
{''.join(group_css)}{''.join(combined_rules)}</style>{controls}
<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next"><div class="input-stage">{connected_root}</div></div>
</css-stage>'''
    (OUTPUT / "connected-attention-input.html").write_text(attention_html)

    attention_numeric_html = f'''<!doctype html><meta charset="utf-8"><title>Numeric attention-connected full GPT-2 MLP</title>
<style>{fc_face_css}{composed_face_css}{''.join(font_faces_css)}
@property --ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --raw-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(768))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}css-stage{{display:block}}.root{{anchor-scope:all}}
.layernorm-stage{{{';'.join(attention_residual)};--ln-mean:{layernorm_mean};
--ln-variance:{layernorm_variance};{';'.join(layernorm_inputs)}}}
.root{{font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(numeric_axis_settings)}}}.metric,.partial,.output{{position:fixed;
inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}.projection{{font-size:1000px;
font-kerning:none;line-height:1}}.partial{{width:max-content}}.output{{font-family:initial;font-size:1px}}
{''.join(attention_case_rules)}{''.join(group_css)}{''.join(combined_rules)}</style>{controls}
<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next"><div class="root">{''.join(group_html)}
<div class="combined">{''.join(combined)}</div></div></div></css-stage>'''
    (OUTPUT / "connected-attention-numeric-input.html").write_text(
        attention_numeric_html
    )

    # Complete block-0 output: add the live post-attention residual and the
    # learned MLP projection bias to the 13 partial projection widths.
    block_combined_rules = []
    for output in range(OUTPUTS):
        anchors = " + ".join(
            f"anchor-size(--g{group}o{output} width)" for group in range(GROUPS)
        )
        residual_and_bias = (
            f"(var(--r1-{output}) + "
            f"{css_number(float(data['mlp_proj_bias'][output]))}) * {OUTPUT_SCALE}px"
        )
        block_combined_rules.append(
            f'.output-{output}{{anchor-name:--block-output-{output};width:calc('
            f'{anchors} - {base_subtraction}px + {residual_and_bias})}}'
        )

    full_block_css = f'''{fc_face_css}{composed_face_css}{''.join(font_faces_css)}
@property --ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --raw-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(768))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}css-stage{{display:block}}.root{{anchor-scope:all}}
.layernorm-stage{{{';'.join(attention_residual)};--ln-mean:{layernorm_mean};
--ln-variance:{layernorm_variance};{';'.join(layernorm_inputs)}}}
.root{{font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(numeric_axis_settings)}}}.metric,.partial,.output{{position:fixed;
inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}.projection{{font-size:1000px;
font-kerning:none;line-height:1}}.partial{{width:max-content}}.output{{font-family:initial;font-size:1px}}
{''.join(attention_case_rules)}{''.join(group_css)}{''.join(block_combined_rules)}'''
    full_block_html = f'''<!doctype html><meta charset="utf-8"><title>Complete attention-connected GPT-2 block</title>
<style>{full_block_css}</style>{controls}<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next"><div class="root">{''.join(group_html)}
<div class="combined">{''.join(combined)}</div></div></div></css-stage>'''
    (OUTPUT / "connected-attention-full-block.html").write_text(full_block_html)

    # Convert all 768 complete block widths back into reusable typed CSS
    # numbers. This is the boundary that every additional transformer block
    # must cross, so keeping it explicit lets us measure the true chaining tax.
    # Keep the diagnostic width positive across GPT-2's real block-0 range.
    # This scale affects only the externally read verification elements; the
    # captured --state-* numbers retain their full CSS numeric precision.
    state_scale = 32.0
    state_offset = 4096.0
    state_child = '<div class="state-values">' + "".join(
        f'<i class="state-value state-value-{index}"></i>'
        for index in range(OUTPUTS)
    ) + "</div>"
    state_capture_rules = []
    for pair in reversed(range(OUTPUTS // 2)):
        first = pair * 2
        state_child = f'<div class="state-probe state-probe-{pair}">{state_child}</div>'
        state_capture_rules.append(
            f'.state-probe-{pair}{{width:anchor-size(--block-output-{first} width);'
            f'height:anchor-size(--block-output-{first + 1} width);container-type:size}}'
        )
        target = (
            f'.state-probe-{pair + 1}'
            if pair + 1 < OUTPUTS // 2
            else '.state-values'
        )
        state_capture_rules.append(
            f'{target}{{--state-{first:03d}:calc((100cqi / 1px - {BASE_ADVANCE}) / '
            f'{OUTPUT_SCALE});--state-{first + 1:03d}:calc((100cqb / 1px - '
            f'{BASE_ADVANCE}) / {OUTPUT_SCALE})}}'
        )
    state_capture_rules.extend(
        f'.state-value-{index}{{width:calc((var(--state-{index:03d}) * '
        f'{state_scale} + {state_offset}) * 1px)}}'
        for index in range(OUTPUTS)
    )
    captured_html = f'''<!doctype html><meta charset="utf-8"><title>Captured complete GPT-2 block state</title>
<style>{full_block_css}
{''.join(f'@property --state-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
.state-probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}.state-value{{position:fixed;
inset:0 auto auto 0;display:block;height:1px}}{''.join(state_capture_rules)}</style>{controls}
<css-stage class="attention-host">{attention_shadow}<div class="layernorm-stage" slot="next">
<div class="root">{''.join(group_html)}<div class="combined">{''.join(combined)}</div>
{state_child}</div></div></css-stage>'''
    (OUTPUT / "connected-attention-full-block-captured.html").write_text(captured_html)

    # Prove that the captured state is usable computation, not merely a value
    # that the test harness can inspect: feed it directly into block 1's real
    # LayerNorm 1 and expose all 768 normalized coordinates.
    block1 = model_data(1)
    next_layernorm_outputs = np.stack([
        layer_norm(vector, block1["ln1_gamma"], block1["ln1_beta"])
        for vector in attention_block_represented
    ])
    next_ln_mean = f"calc(({' + '.join(f'var(--state-{i:03d})' for i in range(OUTPUTS))}) / {OUTPUTS})"
    next_ln_variance = "calc((" + " + ".join(
        f"(var(--state-{index:03d}) - var(--next-ln-mean)) * "
        f"(var(--state-{index:03d}) - var(--next-ln-mean))"
        for index in range(OUTPUTS)
    ) + f") / {OUTPUTS})"
    next_ln_rules = []
    for index in range(OUTPUTS):
        next_ln_rules.append(
            f"--next-ln-{index:03d}:calc((var(--state-{index:03d}) - "
            f"var(--next-ln-mean)) / sqrt(var(--next-ln-variance) + 0.00001) * "
            f"{css_number(float(block1['ln1_gamma'][index]))} + "
            f"{css_number(float(block1['ln1_beta'][index]))})"
        )
    next_ln_scale = 256.0
    next_ln_offset = 4096.0
    next_ln_values = "".join(
        f'<i class="next-ln-value next-ln-value-{index}"></i>'
        for index in range(OUTPUTS)
    )
    next_ln_stage = f'<div class="next-layernorm">{next_ln_values}</div>'
    next_state_child = state_child.replace(
        '<div class="state-values">',
        f'<div class="state-values">{next_ln_stage}',
        1,
    )
    next_ln_html = f'''<!doctype html><meta charset="utf-8"><title>Block-0 state into block-1 LayerNorm</title>
<style>{full_block_css}
{''.join(f'@property --state-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
@property --next-ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --next-ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --next-ln-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
.state-probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}.state-value,.next-ln-value{{
position:fixed;inset:0 auto auto 0;display:block;height:1px}}
{''.join(state_capture_rules)}.next-layernorm{{--next-ln-mean:{next_ln_mean};
--next-ln-variance:{next_ln_variance};{';'.join(next_ln_rules)}}}
{''.join(f'.next-ln-value-{i}{{width:calc((var(--next-ln-{i:03d}) * {next_ln_scale} + {next_ln_offset}) * 1px)}}' for i in range(OUTPUTS))}
</style>{controls}<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next"><div class="root">{''.join(group_html)}
<div class="combined">{''.join(combined)}</div>{next_state_child}</div></div></css-stage>'''
    (OUTPUT / "connected-attention-full-block-next-layernorm.html").write_text(next_ln_html)

    # Full block 1, connected to the captured block-0 state. Both of block 1's
    # dense stages use fresh shadow roots, resetting the parser-depth budget.
    b1_composed_weight = block1["attn_proj_weight"] @ block1["v_weight"]
    b1_composed_bias = (
        block1["attn_proj_weight"] @ block1["v_bias"]
        + block1["attn_proj_bias"]
    )
    q_b1_composed = quantize_float_rows(b1_composed_weight, bits=QUANT_BITS)
    b1_attention_fonts_exist = all(
        (FC_FONT_DIR / f"attn1-composed-s{shard}.woff2").exists()
        for shard in range(3)
    )
    b1_attention_fonts = build_font_group(
        "attn1-composed",
        q_b1_composed.codes,
        rebuild=not b1_attention_fonts_exist,
    )
    b1_n1_range = float(np.max(np.abs(next_layernorm_outputs)) * 1.01)
    b1_attention_shadow = matrix_shadow(
        "connected-attn-b1",
        b1_attention_fonts,
        [f"--next-ln-{index:03d}" for index in range(OUTPUTS)],
        b1_n1_range,
        list(range(OUTPUTS)),
        family_prefix="composed-attn-b1",
        direct_readback=True,
    ).replace(
        'href="stage-connected-attn-b1.css',
        'href="../gpt2-block-css/stage-connected-attn-b1.css',
    )
    b1_attention_face_css = font_faces(
        "composedattnb1", b1_attention_fonts
    ).replace(
        'url("attn1-composed-', 'url("../gpt2-block-css/attn1-composed-'
    )
    b1_residual_inputs = (
        attention_block_represented
        + next_layernorm_outputs @ q_b1_composed.reconstructed.T
        + b1_composed_bias
    )
    b1_layernorm_outputs = np.stack([
        layer_norm(vector, block1["ln2_gamma"], block1["ln2_beta"])
        for vector in b1_residual_inputs
    ])
    b1_activation_range = float(np.max(np.abs(b1_layernorm_outputs)) * 1.01)
    q_b1_fc = quantize_float_rows(block1["fc_weight"], bits=QUANT_BITS)
    b1_all_preactivations = (
        b1_layernorm_outputs @ q_b1_fc.reconstructed.T + block1["fc_bias"]
    )
    b1_preactivation_maximum = float(np.max(np.abs(b1_all_preactivations)))
    b1_preactivation_scale = max(
        PREACTIVATION_SCALE,
        float(np.ceil(b1_preactivation_maximum * 1.05 * 2) / 2),
    )
    b1_knots = gelu_knots(b1_preactivation_scale)
    b1_scaled_knots = b1_knots * b1_preactivation_scale
    b1_piecewise_all = np.interp(
        b1_all_preactivations,
        b1_scaled_knots,
        gelu(b1_scaled_knots),
    )
    b1_preview_groups = [
        b1_piecewise_all[:, start:start + width]
        @ block1["mlp_proj_weight"][:, start:start + width].T
        for start, width in zip(GROUP_STARTS, GROUP_WIDTHS)
    ]
    b1_group_minimum = float(min(np.min(group) for group in b1_preview_groups))
    b1_group_maximum = float(max(np.max(group) for group in b1_preview_groups))
    b1_projection_maximum = float(np.max(np.abs(block1["mlp_proj_weight"])))
    b1_output_scale_limit = min(
        OUTPUT_SCALE,
        32700 / (b1_preactivation_scale * b1_projection_maximum),
        (32700 - BASE_ADVANCE) / max(b1_group_maximum, 1e-12),
        (BASE_ADVANCE - 32) / max(abs(b1_group_minimum), 1e-12),
    )
    b1_output_scale = float(np.floor(b1_output_scale_limit * 0.98))
    b1_scale_tag = (
        f"{css_number(b1_preactivation_scale)}-{css_number(b1_output_scale)}"
        .replace(".", "p")
    )
    b1_fc_fonts_exist = all(
        (FC_FONT_DIR / f"fc-b1-s{shard}.woff2").exists()
        for shard in range(3)
    )
    b1_fc_fonts = build_font_group(
        "fc-b1",
        q_b1_fc.codes,
        rebuild=not b1_fc_fonts_exist,
    )
    b1_fc_base_total = sum(b1_fc_fonts.bases)
    b1_fc_face_css = font_faces("fcb1", b1_fc_fonts).replace(
        'url("fc-b1-', 'url("../gpt2-block-css/fc-b1-'
    )
    b1_axis_settings = []
    for shard in range(3):
        prefix = chr(ord("A") + shard)
        for local in range(256):
            index = shard * 256 + local
            b1_axis_settings.append(
                f'"{prefix}{local:03d}" var(--b1-input-{index:03d})'
            )

    b1_group_html = []
    b1_group_css = []
    b1_projection_faces = []
    b1_represented_groups = []
    b1_exact_groups = []
    b1_projection_font_bytes = 0
    for group, (start, width) in enumerate(zip(GROUP_STARTS, GROUP_WIDTHS)):
        stop = start + width
        tags = [global_axis_tag(index) for index in range(width)]
        projection = block1["mlp_proj_weight"][:, start:stop]
        preactivations = b1_all_preactivations[:, start:stop]
        if np.max(np.abs(preactivations / b1_preactivation_scale)) > 1:
            raise ValueError(
                f"block 1 group {group} preactivation exceeds {b1_preactivation_scale}: "
                f"{np.max(np.abs(preactivations))}"
            )
        b1_represented_groups.append(b1_preview_groups[group])
        b1_exact_groups.append(gelu_new(preactivations) @ projection.T)

        woff2 = OUTPUT / f"gelu-projection-b1-{b1_scale_tag}-{group}.woff2"
        if REBUILD_FONTS or not woff2.exists():
            ttf = OUTPUT / f"gelu-projection-b1-{b1_scale_tag}-{group}.ttf"
            build_direct_font_backend(
                np.zeros((OUTPUTS, width), dtype=np.int16),
                ttf,
                signed_axes=True,
                base_advance=BASE_ADVANCE,
                codepoint_start=CODEPOINT_START,
                axis_tags=tags,
            )
            font = TTFont(ttf, recalcTimestamp=False)
            add_sparse_gelu_avar2(font, tags, b1_preactivation_scale)
            replace_linear_hvar(
                font,
                tags,
                projection,
                b1_preactivation_scale,
                b1_output_scale,
            )
            font.recalcTimestamp = False
            font.save(ttf)
            font = TTFont(ttf, recalcTimestamp=False)
            font.flavor = "woff2"
            font.save(woff2)
        b1_projection_font_bytes += woff2.stat().st_size
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        b1_projection_faces.append(
            f'@font-face{{font-family:B1GeluProjection{group};'
            f'src:url("gelu-projection-b1-{b1_scale_tag}-{group}.woff2?v={digest}") '
            f'format("woff2")}}'
        )

        metrics = []
        rules = []
        for local, hidden in enumerate(range(start, stop)):
            characters = "".join(
                f"&#x{codepoint + hidden:X};"
                for codepoint in b1_fc_fonts.codepoint_starts
            )
            factor = b1_activation_range * q_b1_fc.scales[hidden]
            multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
            offset = (
                GEOMETRY_OFFSET
                + GEOMETRY_SCALE * block1["fc_bias"][hidden]
                - GEOMETRY_SCALE * factor * b1_fc_base_total
            )
            metrics.append(
                f'<i class="b1-metric b1-metric-{group}-{local}" '
                f'style="width:calc-size(max-content,size * '
                f'{css_number(float(multiplier))} + ({css_number(float(offset))}px))">'
                f'{characters}</i>'
            )
            rules.append(
                f'.b1-metric-{group}-{local}{{anchor-name:--b1g{group}m{local}}}'
            )
        for pair in range(width // 2):
            first = pair * 2
            rules.append(
                f'.b1-probe-{group}-{pair}{{width:anchor-size(--b1g{group}m{first} width);'
                f'height:anchor-size(--b1g{group}m{first + 1} width);container-type:size}}'
            )
            target = (
                f'.b1-probe-{group}-{pair + 1}'
                if pair + 1 < width // 2
                else f'.b1-projection-{group}'
            )
            rules.append(
                f'{target}{{--b1-z{first}:calc((100cqi / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * b1_preactivation_scale});--b1-z{first + 1}:'
                f'calc((100cqb / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * b1_preactivation_scale})}}'
            )
        settings = ",".join(
            f'"{tag}" var(--b1-z{index})' for index, tag in enumerate(tags)
        )
        rules.append(
            f'.b1-projection-{group}{{font-family:B1GeluProjection{group};'
            f'font-variation-settings:{settings}}}'
        )
        rules.extend(
            f'.b1-partial-{group}-{output}{{anchor-name:--b1g{group}o{output}}}'
            for output in range(OUTPUTS)
        )
        b1_group_css.append("".join(rules))
        b1_group_html.append(named_group_tree("b1", group, metrics, width))

    b1_mlp_represented = np.sum(b1_represented_groups, axis=0)
    b1_mlp_exact = np.sum(b1_exact_groups, axis=0)
    b1_block_represented = (
        b1_residual_inputs + b1_mlp_represented + block1["mlp_proj_bias"]
    )
    b1_block_exact = b1_residual_inputs + b1_mlp_exact + block1["mlp_proj_bias"]
    b1_combined_html = "".join(
        f'<i class="b1-output b1-output-{output}"></i>'
        for output in range(OUTPUTS)
    )
    b1_combined_rules = []
    for output in range(OUTPUTS):
        anchors = " + ".join(
            f"anchor-size(--b1g{group}o{output} width)"
            for group in range(GROUPS)
        )
        b1_combined_rules.append(
            f'.b1-output-{output}{{width:calc({anchors} - {base_subtraction}px + '
            f'(var(--b1-r1-{output:03d}) + '
            f'{css_number(float(block1["mlp_proj_bias"][output]))}) * '
            f'{b1_output_scale}px)}}'
        )
    b1_mlp_css = f''':host{{display:block}}.b1-root{{anchor-scope:all;
font-family:fcb1S0,fcb1S1,fcb1S2;font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;
font-variation-settings:{','.join(b1_axis_settings)}}}
.b1-metric,.b1-partial,.b1-output{{position:fixed;inset:0 auto auto 0;display:inline-flex;
height:1px;overflow:hidden;white-space:pre;font-style:normal}}.b1-probe{{position:fixed;
inset:0 auto auto 0;overflow:visible}}.b1-projection{{font-size:1000px;font-kerning:none;
line-height:1}}.b1-partial{{width:max-content}}.b1-output{{font-family:initial;font-size:1px}}
{''.join(b1_group_css)}{''.join(b1_combined_rules)}'''
    b1_mlp_css_path = OUTPUT / "stage-connected-mlp-b1.css"
    b1_mlp_css_path.write_text(b1_mlp_css)
    b1_mlp_css_digest = hashlib.sha256(b1_mlp_css_path.read_bytes()).hexdigest()[:12]
    b1_mlp_shadow = (
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="stage-connected-mlp-b1.css?v={b1_mlp_css_digest}">'
        f'<div class="b1-root">{"".join(b1_group_html)}'
        f'<div class="b1-combined">{b1_combined_html}</div></div></template>'
    )

    b1_residual_rules = []
    for index in range(OUTPUTS):
        factor = b1_n1_range * q_b1_composed.scales[index]
        b1_residual_rules.append(
            f'--b1-r1-{index:03d}:calc(var(--state-{index:03d}) + '
            f'var(--raw-{index:03d}) * {css_number(float(factor))} + '
            f'{css_number(float(b1_composed_bias[index]))})'
        )
    b1_residual_names = [f"var(--b1-r1-{index:03d})" for index in range(OUTPUTS)]
    b1_ln_mean = f"calc(({' + '.join(b1_residual_names)}) / {OUTPUTS})"
    b1_ln_variance = "calc((" + " + ".join(
        f"(var(--b1-r1-{index:03d}) - var(--b1-ln-mean)) * "
        f"(var(--b1-r1-{index:03d}) - var(--b1-ln-mean))"
        for index in range(OUTPUTS)
    ) + f") / {OUTPUTS})"
    b1_input_rules = []
    for index in range(OUTPUTS):
        b1_input_rules.append(
            f'--b1-input-{index:03d}:calc(((var(--b1-r1-{index:03d}) - '
            f'var(--b1-ln-mean)) / sqrt(var(--b1-ln-variance) + 0.00001) * '
            f'{css_number(float(block1["ln2_gamma"][index]))} + '
            f'{css_number(float(block1["ln2_beta"][index]))}) / '
            f'{css_number(b1_activation_range)})'
        )
    b1_stage = (
        f'<css-stage class="b1-attention">{b1_attention_shadow}'
        f'<div class="b1-ln2-stage" slot="next"><css-stage class="b1-mlp">'
        f'{b1_mlp_shadow}</css-stage></div></css-stage>'
    )
    two_block_state = f'<div class="state-values"><div class="next-layernorm">{b1_stage}</div></div>'
    for pair in reversed(range(OUTPUTS // 2)):
        two_block_state = f'<div class="state-probe state-probe-{pair}">{two_block_state}</div>'
    two_block_html = f'''<!doctype html><meta charset="utf-8"><title>Two connected GPT-2 blocks</title>
<style>{full_block_css}{b1_attention_face_css}{b1_fc_face_css}{''.join(b1_projection_faces)}
{''.join(f'@property --state-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
@property --next-ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --next-ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
@property --b1-ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --b1-ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --next-ln-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
{''.join(f'@property --b1-z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
.state-probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}{''.join(state_capture_rules)}
.next-layernorm{{--next-ln-mean:{next_ln_mean};--next-ln-variance:{next_ln_variance};
{';'.join(next_ln_rules)}}}.b1-ln2-stage{{{';'.join(b1_residual_rules)};
--b1-ln-mean:{b1_ln_mean};--b1-ln-variance:{b1_ln_variance};{';'.join(b1_input_rules)}}}
</style>{controls}<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next"><div class="root">{''.join(group_html)}
<div class="combined">{''.join(combined)}</div>{two_block_state}</div></div></css-stage>'''
    (OUTPUT / "connected-two-block.html").write_text(two_block_html)

    # Scalable topology: every deep readback lives inside the producer's
    # shadow root. The next stage is a shallow light-DOM child assigned to the
    # terminal slot, so it inherits the produced CSS numbers without inheriting
    # hundreds of parser-depth levels.
    shadow_state_child = '<slot name="next"></slot>'
    shadow_state_rules = []
    for pair in reversed(range(OUTPUTS // 2)):
        first = pair * 2
        shadow_state_child = (
            f'<div class="state-probe state-probe-{pair}">'
            f'{shadow_state_child}</div>'
        )
        shadow_state_rules.append(
            f'.state-probe-{pair}{{width:anchor-size(--block-output-{first} width);'
            f'height:anchor-size(--block-output-{first + 1} width);container-type:size}}'
        )
        target = (
            f'.state-probe-{pair + 1}'
            if pair + 1 < OUTPUTS // 2
            else 'slot'
        )
        shadow_state_rules.append(
            f'{target}{{--state-{first:03d}:calc((100cqi / 1px - {BASE_ADVANCE}) / '
            f'{OUTPUT_SCALE});--state-{first + 1:03d}:calc((100cqb / 1px - '
            f'{BASE_ADVANCE}) / {OUTPUT_SCALE})}}'
        )
    b0_mlp_css = f''':host{{display:block}}.root{{anchor-scope:all;font-family:fcS0,fcS1,fcS2;
font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;font-variation-settings:{','.join(numeric_axis_settings)}}}
.metric,.partial,.output{{position:fixed;inset:0 auto auto 0;display:inline-flex;height:1px;
overflow:hidden;white-space:pre;font-style:normal}}.probe,.state-probe{{position:fixed;
inset:0 auto auto 0;overflow:visible}}.projection{{font-size:1000px;font-kerning:none;
line-height:1}}.partial{{width:max-content}}.output{{font-family:initial;font-size:1px}}
{''.join(group_css)}{''.join(block_combined_rules)}{''.join(shadow_state_rules)}'''
    b0_mlp_css_path = OUTPUT / "stage-connected-mlp-b0.css"
    b0_mlp_css_path.write_text(b0_mlp_css)
    b0_mlp_digest = hashlib.sha256(b0_mlp_css_path.read_bytes()).hexdigest()[:12]
    b0_mlp_shadow = (
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="stage-connected-mlp-b0.css?v={b0_mlp_digest}">'
        f'<div class="root">{"".join(group_html)}'
        f'<div class="combined">{"".join(combined)}</div>{shadow_state_child}</div>'
        '</template>'
    )
    b1_mlp_host = f'<css-stage class="b1-mlp">{b1_mlp_shadow}</css-stage>'
    b1_attention_host = (
        f'<css-stage class="b1-attention" slot="next">{b1_attention_shadow}'
        f'<div class="b1-ln2-stage" slot="next">{b1_mlp_host}</div></css-stage>'
    )
    b0_mlp_host = (
        f'<css-stage class="b0-mlp">{b0_mlp_shadow}{b1_attention_host}</css-stage>'
    )
    staged_global_css = f'''{fc_face_css}{composed_face_css}{''.join(font_faces_css)}
{b1_attention_face_css}{b1_fc_face_css}{''.join(b1_projection_faces)}
@property --ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
@property --next-ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --next-ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
@property --b1-ln-mean{{syntax:"<number>";inherits:true;initial-value:0}}
@property --b1-ln-variance{{syntax:"<number>";inherits:true;initial-value:0}}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --b1-z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --raw-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
{''.join(f'@property --state-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
{''.join(f'@property --next-ln-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(OUTPUTS))}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}css-stage{{display:block}}
.layernorm-stage{{{';'.join(attention_residual)};--ln-mean:{layernorm_mean};
--ln-variance:{layernorm_variance};{';'.join(layernorm_inputs)}}}
.b1-attention{{--next-ln-mean:{next_ln_mean};--next-ln-variance:{next_ln_variance};
{';'.join(next_ln_rules)}}}.b1-ln2-stage{{{';'.join(b1_residual_rules)};
--b1-ln-mean:{b1_ln_mean};--b1-ln-variance:{b1_ln_variance};{';'.join(b1_input_rules)}}}
{''.join(attention_case_rules)}'''
    staged_two_block_html = f'''<!doctype html><meta charset="utf-8"><title>Shadow-staged two-block GPT-2</title>
<style>{staged_global_css}</style>{controls}<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next">{b0_mlp_host}</div></css-stage>'''
    (OUTPUT / "connected-two-block-shadow-staged.html").write_text(
        staged_two_block_html
    )
    layoutless_transport_css = (
        'css-stage,.layernorm-stage,.b1-ln2-stage{display:contents!important}'
    )
    staged_two_block_layoutless_html = staged_two_block_html.replace(
        "<style>", f"<style>{layoutless_transport_css}", 1
    ).replace(
        "<title>Shadow-staged two-block GPT-2</title>",
        "<title>Layoutless shadow-staged two-block GPT-2</title>",
        1,
    )
    (OUTPUT / "connected-two-block-shadow-staged-layoutless.html").write_text(
        staged_two_block_layoutless_html
    )

    # Alternative projection topology. Each FC group lives in its own shadow
    # stage and passes its 236-238 GELU coordinates through a terminal slot.
    # The final stage uses unique axes/codepoints in 13 fallback fonts, exposing
    # each summed output with one element instead of 13 anchored elements.
    serial_codepoint_start = 0xF0000
    serial_projection_faces = []
    serial_projection_font_bytes = 0
    serial_group_hosts = []
    serial_axis_settings = []
    serial_output_characters = [[] for _ in range(OUTPUTS)]
    for group, (start, width) in enumerate(zip(GROUP_STARTS, GROUP_WIDTHS)):
        stop = start + width
        tags = [global_axis_tag(start + local) for local in range(width)]
        codepoint_start = serial_codepoint_start + group * OUTPUTS
        woff2 = OUTPUT / f"serial-projection-b1-{b1_scale_tag}-{group}.woff2"
        if REBUILD_FONTS or not woff2.exists():
            ttf = OUTPUT / f"serial-projection-b1-{b1_scale_tag}-{group}.ttf"
            build_direct_font_backend(
                np.zeros((OUTPUTS, width), dtype=np.int16),
                ttf,
                signed_axes=True,
                base_advance=BASE_ADVANCE,
                codepoint_start=codepoint_start,
                axis_tags=tags,
            )
            font = TTFont(ttf, recalcTimestamp=False)
            add_sparse_gelu_avar2(font, tags, b1_preactivation_scale)
            replace_linear_hvar(
                font,
                tags,
                block1["mlp_proj_weight"][:, start:stop],
                b1_preactivation_scale,
                b1_output_scale,
            )
            font.recalcTimestamp = False
            font.save(ttf)
            font = TTFont(ttf, recalcTimestamp=False)
            font.flavor = "woff2"
            font.save(woff2)
        serial_projection_font_bytes += woff2.stat().st_size
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        family = f"SerialB1Projection{group}"
        serial_projection_faces.append(
            f'@font-face{{font-family:{family};src:url("{woff2.name}?v={digest}") '
            f'format("woff2");unicode-range:U+{codepoint_start:X}-'
            f'{codepoint_start + OUTPUTS - 1:X}}}'
        )
        serial_axis_settings.extend(
            f'"{tag}" var(--serial-z-{start + local:04d})'
            for local, tag in enumerate(tags)
        )
        for output in range(OUTPUTS):
            serial_output_characters[output].append(
                f'&#x{codepoint_start + output:X};'
            )

        metrics = []
        metric_rules = []
        for local, hidden in enumerate(range(start, stop)):
            characters = "".join(
                f"&#x{codepoint + hidden:X};"
                for codepoint in b1_fc_fonts.codepoint_starts
            )
            factor = b1_activation_range * q_b1_fc.scales[hidden]
            multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
            offset = (
                GEOMETRY_OFFSET
                + GEOMETRY_SCALE * block1["fc_bias"][hidden]
                - GEOMETRY_SCALE * factor * b1_fc_base_total
            )
            metrics.append(
                f'<i class="metric metric-{local}" style="width:calc-size(max-content,'
                f'size * {css_number(float(multiplier))} + '
                f'({css_number(float(offset))}px))">{characters}</i>'
            )
            metric_rules.append(f'.metric-{local}{{anchor-name:--m{local}}}')
        chain = '<slot name="next"></slot>'
        probe_rules = []
        for pair in reversed(range(width // 2)):
            first = pair * 2
            chain = metrics[first] + metrics[first + 1] + f'<div class="probe probe-{pair}">{chain}</div>'
            probe_rules.append(
                f'.probe-{pair}{{width:anchor-size(--m{first} width);'
                f'height:anchor-size(--m{first + 1} width);container-type:size}}'
            )
            target = f'.probe-{pair + 1}' if pair + 1 < width // 2 else 'slot'
            probe_rules.append(
                f'{target}{{--serial-z-{start + first:04d}:'
                f'calc((100cqi / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * b1_preactivation_scale});'
                f'--serial-z-{start + first + 1:04d}:'
                f'calc((100cqb / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * b1_preactivation_scale})}}'
            )
        stage_css = f''':host{{display:block;font-family:fcb1S0,fcb1S1,fcb1S2;
font-size:{FONT_SIZE}px;font-kerning:none;line-height:1;font-variation-settings:{','.join(b1_axis_settings)}}}
.stage-root{{anchor-scope:all}}.metric{{position:fixed;inset:0 auto auto 0;display:inline-flex;
height:1px;overflow:hidden;white-space:pre;font-style:normal}}.probe{{position:fixed;
inset:0 auto auto 0;overflow:visible}}{''.join(metric_rules)}{''.join(probe_rules)}'''
        stage_css_path = OUTPUT / f"stage-serial-b1-group-{group}.css"
        stage_css_path.write_text(stage_css)
        stage_digest = hashlib.sha256(stage_css_path.read_bytes()).hexdigest()[:12]
        serial_group_hosts.append(
            '<template shadowrootmode="open">'
            f'<link rel="stylesheet" href="{stage_css_path.name}?v={stage_digest}">'
            f'<div class="stage-root">{chain}</div></template>'
        )

    serial_output_html = "".join(
        f'<i class="serial-output serial-output-{output}">'
        f'{"".join(serial_output_characters[output])}</i>'
        for output in range(OUTPUTS)
    )
    serial_projection_rules = []
    serial_base_total = GROUPS * BASE_ADVANCE
    for output in range(OUTPUTS):
        serial_projection_rules.append(
            f'.serial-output-{output}{{width:calc-size(max-content,size + '
            f'(var(--b1-r1-{output:03d}) + '
            f'{css_number(float(block1["mlp_proj_bias"][output]))}) * '
            f'{b1_output_scale}px)}}'
        )
    serial_projection_css = f''':host{{display:block}}.serial-root{{font-family:
{','.join(f'SerialB1Projection{group}' for group in range(GROUPS))};font-size:1000px;
font-kerning:none;line-height:1;font-variation-settings:{','.join(serial_axis_settings)}}}
.serial-output{{position:fixed;inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;
white-space:pre;font-style:normal}}{''.join(serial_projection_rules)}'''
    serial_projection_css_path = OUTPUT / "stage-serial-b1-projection.css"
    serial_projection_css_path.write_text(serial_projection_css)
    serial_projection_digest = hashlib.sha256(
        serial_projection_css_path.read_bytes()
    ).hexdigest()[:12]
    serial_projection_host = (
        '<css-stage class="serial-projection" slot="next">'
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{serial_projection_css_path.name}?v={serial_projection_digest}">'
        f'<div class="serial-root">{serial_output_html}</div></template></css-stage>'
    )
    serial_chain = serial_projection_host
    for group in reversed(range(GROUPS)):
        slot = ' slot="next"' if group else ''
        serial_chain = (
            f'<css-stage class="serial-group-{group}"{slot}>'
            f'{serial_group_hosts[group]}{serial_chain}</css-stage>'
        )
    serial_b1_attention_host = (
        f'<css-stage class="b1-attention" slot="next">{b1_attention_shadow}'
        f'<div class="b1-ln2-stage" slot="next">{serial_chain}</div></css-stage>'
    )
    serial_b0_host = (
        f'<css-stage class="b0-mlp">{b0_mlp_shadow}'
        f'{serial_b1_attention_host}</css-stage>'
    )
    serial_two_block_html = f'''<!doctype html><meta charset="utf-8"><title>Serial projection two-block GPT-2</title>
<style>{staged_global_css}{''.join(serial_projection_faces)}
{''.join(f'@property --serial-z-{i:04d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(3072))}
</style>{controls}<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next">{serial_b0_host}</div></css-stage>'''
    (OUTPUT / "connected-two-block-serial-projection.html").write_text(
        serial_two_block_html
    )
    serial_contents_css = (
        'css-stage[class^="serial-group-"]{display:contents!important}'
    )
    serial_two_block_contents_html = serial_two_block_html.replace(
        "<style>", f"<style>{serial_contents_css}", 1
    ).replace(
        "<title>Serial projection two-block GPT-2</title>",
        "<title>Display-contents serial projection two-block GPT-2</title>",
        1,
    )
    (OUTPUT / "connected-two-block-serial-projection-contents.html").write_text(
        serial_two_block_contents_html
    )
    serial_two_block_layoutless_html = serial_two_block_html.replace(
        "<style>", f"<style>{layoutless_transport_css}", 1
    ).replace(
        "<title>Serial projection two-block GPT-2</title>",
        "<title>Layoutless serial projection two-block GPT-2</title>",
        1,
    )
    (OUTPUT / "connected-two-block-serial-projection-layoutless.html").write_text(
        serial_two_block_layoutless_html
    )
    for reveal_delay in (0, 16, 50, 100, 200, 400, 800):
        reveal_rules = [
            f'@keyframes reveal-b1-{reveal_delay}-{case}'
            '{0%,99%{content-visibility:hidden}100%{content-visibility:visible}}'
            f'body:has(#case-{case}:checked) .b1-attention'
            f'{{animation:reveal-b1-{reveal_delay}-{case} 1ms step-end '
            f'{reveal_delay}ms both}}'
            for case in range(len(TOKEN_IDS))
        ]
        staged_css = layoutless_transport_css + "".join(reveal_rules)
        staged_html = serial_two_block_html.replace(
            "<style>", f"<style>{staged_css}", 1
        ).replace(
            "<title>Serial projection two-block GPT-2</title>",
            f"<title>Staged {reveal_delay}ms serial projection two-block GPT-2</title>",
            1,
        )
        (OUTPUT / f"connected-two-block-serial-staged-{reveal_delay}ms.html").write_text(
            staged_html
        )

    # Apply the serial topology to block 0 as well. Its final projection shadow
    # also captures the complete vector and passes it to block 1 through a slot,
    # yielding the architecture that can be repeated block by block.
    serial0_codepoint_start = 0xF4000
    serial0_projection_faces = []
    serial0_projection_font_bytes = 0
    serial0_group_hosts = []
    serial0_axis_settings = []
    serial0_output_characters = [[] for _ in range(OUTPUTS)]
    for group, (start, width) in enumerate(zip(GROUP_STARTS, GROUP_WIDTHS)):
        stop = start + width
        tags = [global_axis_tag(start + local) for local in range(width)]
        codepoint_start = serial0_codepoint_start + group * OUTPUTS
        woff2 = OUTPUT / f"serial-projection-b0-{group}.woff2"
        if REBUILD_FONTS or not woff2.exists():
            ttf = OUTPUT / f"serial-projection-b0-{group}.ttf"
            build_direct_font_backend(
                np.zeros((OUTPUTS, width), dtype=np.int16),
                ttf,
                signed_axes=True,
                base_advance=BASE_ADVANCE,
                codepoint_start=codepoint_start,
                axis_tags=tags,
            )
            font = TTFont(ttf, recalcTimestamp=False)
            add_sparse_gelu_avar2(font, tags)
            replace_linear_hvar(font, tags, data["mlp_proj_weight"][:, start:stop])
            font.recalcTimestamp = False
            font.save(ttf)
            font = TTFont(ttf, recalcTimestamp=False)
            font.flavor = "woff2"
            font.save(woff2)
        serial0_projection_font_bytes += woff2.stat().st_size
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        family = f"SerialB0Projection{group}"
        serial0_projection_faces.append(
            f'@font-face{{font-family:{family};src:url("{woff2.name}?v={digest}") '
            f'format("woff2");unicode-range:U+{codepoint_start:X}-'
            f'{codepoint_start + OUTPUTS - 1:X}}}'
        )
        serial0_axis_settings.extend(
            f'"{tag}" var(--serial0-z-{start + local:04d})'
            for local, tag in enumerate(tags)
        )
        for output in range(OUTPUTS):
            serial0_output_characters[output].append(
                f'&#x{codepoint_start + output:X};'
            )

        metrics = []
        metric_rules = []
        for local, hidden in enumerate(range(start, stop)):
            characters = "".join(
                f"&#x{codepoint + hidden:X};" for codepoint in fc_fonts.codepoint_starts
            )
            factor = activation_range * q_fc.scales[hidden]
            multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
            offset = (
                GEOMETRY_OFFSET
                + GEOMETRY_SCALE * data["fc_bias"][hidden]
                - GEOMETRY_SCALE * factor * base_total
            )
            metrics.append(
                f'<i class="metric metric-{local}" style="width:calc-size(max-content,'
                f'size * {css_number(float(multiplier))} + '
                f'({css_number(float(offset))}px))">{characters}</i>'
            )
            metric_rules.append(f'.metric-{local}{{anchor-name:--m{local}}}')
        chain = '<slot name="next"></slot>'
        probe_rules = []
        for pair in reversed(range(width // 2)):
            first = pair * 2
            chain = metrics[first] + metrics[first + 1] + f'<div class="probe probe-{pair}">{chain}</div>'
            probe_rules.append(
                f'.probe-{pair}{{width:anchor-size(--m{first} width);'
                f'height:anchor-size(--m{first + 1} width);container-type:size}}'
            )
            target = f'.probe-{pair + 1}' if pair + 1 < width // 2 else 'slot'
            probe_rules.append(
                f'{target}{{--serial0-z-{start + first:04d}:'
                f'calc((100cqi / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * PREACTIVATION_SCALE});'
                f'--serial0-z-{start + first + 1:04d}:'
                f'calc((100cqb / 1px - {GEOMETRY_OFFSET}) / '
                f'{GEOMETRY_SCALE * PREACTIVATION_SCALE})}}'
            )
        stage_css = f''':host{{display:block;font-family:fcS0,fcS1,fcS2;font-size:{FONT_SIZE}px;
font-kerning:none;line-height:1;font-variation-settings:{','.join(numeric_axis_settings)}}}
.stage-root{{anchor-scope:all}}.metric{{position:fixed;inset:0 auto auto 0;display:inline-flex;
height:1px;overflow:hidden;white-space:pre;font-style:normal}}.probe{{position:fixed;
inset:0 auto auto 0;overflow:visible}}{''.join(metric_rules)}{''.join(probe_rules)}'''
        stage_css_path = OUTPUT / f"stage-serial-b0-group-{group}.css"
        stage_css_path.write_text(stage_css)
        stage_digest = hashlib.sha256(stage_css_path.read_bytes()).hexdigest()[:12]
        serial0_group_hosts.append(
            '<template shadowrootmode="open">'
            f'<link rel="stylesheet" href="{stage_css_path.name}?v={stage_digest}">'
            f'<div class="stage-root">{chain}</div></template>'
        )

    serial0_base_total = GROUPS * BASE_ADVANCE
    serial0_output_html = "".join(
        f'<i class="serial0-output serial0-output-{output}">'
        f'{"".join(serial0_output_characters[output])}</i>'
        for output in range(OUTPUTS)
    )
    serial0_projection_rules = []
    for output in range(OUTPUTS):
        serial0_projection_rules.append(
            f'.serial0-output-{output}{{anchor-name:--serial0-output-{output};'
            f'width:calc-size(max-content,size + (var(--r1-{output}) + '
            f'{css_number(float(data["mlp_proj_bias"][output]))}) * {OUTPUT_SCALE}px)}}'
        )
    serial0_state_child = '<slot name="next"></slot>'
    serial0_state_rules = []
    for pair in reversed(range(OUTPUTS // 2)):
        first = pair * 2
        serial0_state_child = (
            f'<div class="state-probe state-probe-{pair}">'
            f'{serial0_state_child}</div>'
        )
        serial0_state_rules.append(
            f'.state-probe-{pair}{{width:anchor-size(--serial0-output-{first} width);'
            f'height:anchor-size(--serial0-output-{first + 1} width);container-type:size}}'
        )
        target = f'.state-probe-{pair + 1}' if pair + 1 < OUTPUTS // 2 else 'slot'
        serial0_state_rules.append(
            f'{target}{{--state-{first:03d}:calc((100cqi / 1px - {serial0_base_total}) / '
            f'{OUTPUT_SCALE});--state-{first + 1:03d}:calc((100cqb / 1px - '
            f'{serial0_base_total}) / {OUTPUT_SCALE})}}'
        )
    serial0_projection_css = f''':host{{display:block}}.serial0-root{{anchor-scope:all;
font-family:{','.join(f'SerialB0Projection{group}' for group in range(GROUPS))};
font-size:1000px;font-kerning:none;line-height:1;font-variation-settings:{','.join(serial0_axis_settings)}}}
.serial0-output{{position:fixed;inset:0 auto auto 0;display:inline-flex;height:1px;
overflow:hidden;white-space:pre;font-style:normal}}.state-probe{{position:fixed;
inset:0 auto auto 0;overflow:visible}}{''.join(serial0_projection_rules)}{''.join(serial0_state_rules)}'''
    serial0_projection_css_path = OUTPUT / "stage-serial-b0-projection.css"
    serial0_projection_css_path.write_text(serial0_projection_css)
    serial0_projection_digest = hashlib.sha256(
        serial0_projection_css_path.read_bytes()
    ).hexdigest()[:12]
    serial0_projection_host = (
        '<css-stage class="serial0-projection" slot="next">'
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{serial0_projection_css_path.name}?v={serial0_projection_digest}">'
        f'<div class="serial0-root">{serial0_output_html}{serial0_state_child}</div>'
        f'</template>{serial_b1_attention_host}</css-stage>'
    )
    serial0_chain = serial0_projection_host
    for group in reversed(range(GROUPS)):
        slot = ' slot="next"' if group else ''
        serial0_chain = (
            f'<css-stage class="serial0-group-{group}"{slot}>'
            f'{serial0_group_hosts[group]}{serial0_chain}</css-stage>'
        )
    fully_serial_html = f'''<!doctype html><meta charset="utf-8"><title>Fully serial two-block GPT-2</title>
<style>{staged_global_css}{''.join(serial_projection_faces)}{''.join(serial0_projection_faces)}
{''.join(f'@property --serial-z-{i:04d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(3072))}
{''.join(f'@property --serial0-z-{i:04d}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(3072))}
</style>{controls}<css-stage class="attention-host">{attention_shadow}
<div class="layernorm-stage" slot="next">{serial0_chain}</div></css-stage>'''
    (OUTPUT / "connected-two-block-fully-serial.html").write_text(fully_serial_html)
    fully_serial_contents_css = (
        'css-stage[class^="serial-group-"],'
        'css-stage[class^="serial0-group-"]{display:contents!important}'
    )
    fully_serial_contents_html = fully_serial_html.replace(
        "<style>", f"<style>{fully_serial_contents_css}", 1
    ).replace(
        "<title>Fully serial two-block GPT-2</title>",
        "<title>Display-contents fully serial two-block GPT-2</title>",
        1,
    )
    (OUTPUT / "connected-two-block-fully-serial-contents.html").write_text(
        fully_serial_contents_html
    )
    fully_serial_layoutless_html = fully_serial_html.replace(
        "<style>", f"<style>{layoutless_transport_css}", 1
    ).replace(
        "<title>Fully serial two-block GPT-2</title>",
        "<title>Layoutless fully serial two-block GPT-2</title>",
        1,
    )
    (OUTPUT / "connected-two-block-fully-serial-layoutless.html").write_text(
        fully_serial_layoutless_html
    )

    # Chainable form that stays below Chromium's ~512-level HTML nesting cap.
    # The 768 input coordinates are captured in three parallel 256-coordinate
    # branches. Each branch shapes one FC shard. Three geometry widths are then
    # merged into each of the 3,072 preactivations before the existing projection.
    source_html = "".join(input_metrics)
    sharded_input_css = []
    sharded_input_html = []
    for shard in range(3):
        prefix = chr(ord("A") + shard)
        shard_settings = ",".join(
            f'"{prefix}{local:03d}" var(--sx{local})' for local in range(256)
        )
        raw_metrics = "".join(
            f'<i class="shard-metric shard-metric-{shard}-{hidden}" '
            f'style="anchor-name:--s{shard}m{hidden}">'
            f'&#x{fc_fonts.codepoint_starts[shard] + hidden:X};</i>'
            for hidden in range(3072)
        )
        branch = (
            f'<div class="input-shard-leaf input-shard-leaf-{shard}">{raw_metrics}</div>'
        )
        sharded_input_css.append(
            f'.input-shard-leaf-{shard}{{font-family:fcS{shard};'
            f'font-variation-settings:{shard_settings}}}'
        )
        for pair in reversed(range(128)):
            first = 2 * pair
            branch = (
                f'<div class="input-shard-probe input-shard-probe-{shard}-{pair}">'
                f'{branch}</div>'
            )
            global_first = shard * 256 + first
            target = (
                f'.input-shard-probe-{shard}-{pair + 1}'
                if pair + 1 < 128
                else f'.input-shard-leaf-{shard}'
            )
            sharded_input_css.append(
                f'.input-shard-probe-{shard}-{pair}{{'
                f'width:anchor-size(--input-{global_first} width);'
                f'height:anchor-size(--input-{global_first + 1} width);'
                f'container-type:size}}'
                f'{target}{{--sx{first}:calc((100cqi / 1px - {INPUT_GEOMETRY_OFFSET}) / '
                f'{INPUT_GEOMETRY_SCALE});--sx{first + 1}:calc((100cqb / 1px - '
                f'{INPUT_GEOMETRY_OFFSET}) / {INPUT_GEOMETRY_SCALE})}}'
            )
        sharded_input_html.append(
            f'<div class="input-shard input-shard-{shard}">{branch}</div>'
        )

    merged_metrics = []
    for group, (start, width) in enumerate(zip(GROUP_STARTS, GROUP_WIDTHS)):
        for local, hidden in enumerate(range(start, start + width)):
            factor = activation_range * q_fc.scales[hidden]
            multiplier = GEOMETRY_SCALE * factor * UNITS_PER_EM / FONT_SIZE
            offset = (
                GEOMETRY_OFFSET
                + GEOMETRY_SCALE * data["fc_bias"][hidden]
                - GEOMETRY_SCALE * factor * base_total
            )
            shard_sum = " + ".join(
                f'anchor-size(--s{shard}m{hidden} width)' for shard in range(3)
            )
            merged_metrics.append(
                f'<i class="merged-metric metric-{group}-{local}" '
                f'style="anchor-name:--g{group}m{local};width:calc('
                f'({shard_sum}) * {css_number(float(multiplier))} '
                f'+ {css_number(float(offset))}px)"></i>'
            )

    sharded_connected_html = f'''<!doctype html><meta charset="utf-8"><title>Sharded connected-input full GPT-2 MLP</title>
<style>{fc_face_css}{''.join(font_faces_css)}
{''.join(f'@property --z{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(MAX_GROUP_WIDTH))}
{''.join(f'@property --sx{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for i in range(256))}
html,body{{margin:0}}body{{anchor-scope:all}}input{{position:fixed;left:-10000px}}
.metric,.merged-metric,.partial,.output,.input-metric,.shard-metric{{position:fixed;
inset:0 auto auto 0;display:inline-flex;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.input-shard-probe,.probe{{position:fixed;inset:0 auto auto 0;overflow:visible}}
.input-shard-leaf{{font-size:{FONT_SIZE}px;font-kerning:none;line-height:1}}
.shard-metric{{width:max-content}}.projection{{font-size:1000px;font-kerning:none;line-height:1}}
.partial{{width:max-content}}.output{{font-family:initial;font-size:1px}}
{''.join(connected_case_rules)}{''.join(input_rules)}{''.join(sharded_input_css)}
{''.join(group_css)}{''.join(combined_rules)}</style>{controls}
<div class="input-stage">{source_html}{''.join(sharded_input_html)}</div>
<div class="root">{''.join(merged_metrics)}{''.join(projection_tree(group, width) for group, width in enumerate(GROUP_WIDTHS))}
<div class="combined">{''.join(combined)}</div></div>'''
    (OUTPUT / "connected-sharded-input.html").write_text(sharded_connected_html)
    reference = {
        "tokenIds": TOKEN_IDS,
        "shape": [768, 3072, 768],
        "backend": BACKEND,
        "groups": GROUPS,
        "groupWidth": MAX_GROUP_WIDTH,
        "groupWidths": GROUP_WIDTHS,
        "quantizedFcBits": QUANT_BITS,
        "preactivationScale": PREACTIVATION_SCALE,
        "outputScale": OUTPUT_SCALE,
        "stateScale": state_scale,
        "stateOffset": state_offset,
        "nextLayernormScale": next_ln_scale,
        "nextLayernormOffset": next_ln_offset,
        "block1PreactivationScale": b1_preactivation_scale,
        "block1PreactivationMaximum": b1_preactivation_maximum,
        "block1OutputScale": b1_output_scale,
        "block1ProjectionMaximum": b1_projection_maximum,
        "block1GroupMinimum": b1_group_minimum,
        "block1GroupMaximum": b1_group_maximum,
        "baseAdvance": BASE_ADVANCE,
        "activationRange": activation_range,
        "preactivationMinimum": preactivation_minimum,
        "preactivationMaximum": preactivation_maximum,
        "preactivations": np.concatenate([
            inputs @ q_fc.reconstructed[start:start + width].T
            + data["fc_bias"][start:start + width]
            for start, width in zip(GROUP_STARTS, GROUP_WIDTHS)
        ], axis=1).tolist(),
        "representedGroupOutputs": np.stack(represented_groups, axis=1).tolist(),
        "representedOutputs": represented.tolist(),
        "exactOutputs": exact.tolist(),
        "attentionRepresentedOutputs": attention_represented.tolist(),
        "attentionExactOutputs": attention_exact.tolist(),
        "attentionBlockRepresentedOutputs": attention_block_represented.tolist(),
        "attentionBlockExactOutputs": attention_block_exact.tolist(),
        "nextLayernormOutputs": next_layernorm_outputs.tolist(),
        "block1RepresentedOutputs": b1_block_represented.tolist(),
        "block1ExactOutputs": b1_block_exact.tolist(),
        "approximationRmse": float(np.sqrt(np.mean((represented - exact) ** 2))),
        "approximationMaximum": float(np.max(np.abs(represented - exact))),
        "projectionFontBytes": projection_font_bytes,
        "block1ProjectionFontBytes": b1_projection_font_bytes,
        "block1SerialProjectionFontBytes": serial_projection_font_bytes,
        "block1SerialProjectionBase": serial_base_total,
        "block0SerialProjectionFontBytes": serial0_projection_font_bytes,
        "block0SerialProjectionBase": serial0_base_total,
        "block1FcFontBytes": sum(
            (FC_FONT_DIR / f"{name}.woff2").stat().st_size
            for name in b1_fc_fonts.names
        ),
        "block1AttentionFontBytes": sum(
            (FC_FONT_DIR / f"{name}.woff2").stat().st_size
            for name in b1_attention_fonts.names
        ),
        "fcFontBytes": sum((FC_FONT_DIR / f"{name}.woff2").stat().st_size for name in fc_fonts.names),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "connectedHtmlBytes": (OUTPUT / "connected-input.html").stat().st_size,
        "connectedLayernormHtmlBytes": (
            OUTPUT / "connected-layernorm-input.html"
        ).stat().st_size,
        "connectedLayernormNumericHtmlBytes": (
            OUTPUT / "connected-layernorm-numeric-input.html"
        ).stat().st_size,
        "connectedAttentionHtmlBytes": (
            OUTPUT / "connected-attention-input.html"
        ).stat().st_size,
        "connectedAttentionNumericHtmlBytes": (
            OUTPUT / "connected-attention-numeric-input.html"
        ).stat().st_size,
        "connectedAttentionFullBlockHtmlBytes": (
            OUTPUT / "connected-attention-full-block.html"
        ).stat().st_size,
        "connectedAttentionFullBlockCapturedHtmlBytes": (
            OUTPUT / "connected-attention-full-block-captured.html"
        ).stat().st_size,
        "connectedAttentionFullBlockNextLayernormHtmlBytes": (
            OUTPUT / "connected-attention-full-block-next-layernorm.html"
        ).stat().st_size,
        "connectedTwoBlockHtmlBytes": (
            OUTPUT / "connected-two-block.html"
        ).stat().st_size,
        "connectedTwoBlockShadowStagedHtmlBytes": (
            OUTPUT / "connected-two-block-shadow-staged.html"
        ).stat().st_size,
        "connectedTwoBlockShadowStagedLayoutlessHtmlBytes": (
            OUTPUT / "connected-two-block-shadow-staged-layoutless.html"
        ).stat().st_size,
        "connectedTwoBlockSerialProjectionHtmlBytes": (
            OUTPUT / "connected-two-block-serial-projection.html"
        ).stat().st_size,
        "connectedTwoBlockSerialProjectionLayoutlessHtmlBytes": (
            OUTPUT / "connected-two-block-serial-projection-layoutless.html"
        ).stat().st_size,
        "connectedTwoBlockFullySerialHtmlBytes": (
            OUTPUT / "connected-two-block-fully-serial.html"
        ).stat().st_size,
        "connectedTwoBlockFullySerialLayoutlessHtmlBytes": (
            OUTPUT / "connected-two-block-fully-serial-layoutless.html"
        ).stat().st_size,
        "connectedShardedHtmlBytes": (
            OUTPUT / "connected-sharded-input.html"
        ).stat().st_size,
        "buildMilliseconds": (time.perf_counter() - started) * 1000,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in (
            "preactivations", "representedGroupOutputs", "representedOutputs", "exactOutputs",
            "attentionRepresentedOutputs", "attentionExactOutputs"
        )
    }, indent=2))


if __name__ == "__main__":
    main()
