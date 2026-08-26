#!/usr/bin/env python3
"""Build one GPT-2 block using six-output direct container packets."""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np

from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
    OUT,
    PACK_SHARDS,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    FontGroup,
    build_font_group,
    font_faces,
    gelu_new,
    global_css,
    host,
    layer_norm,
    model_data,
    pack_font_settings,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import QuantizedRows, quantize_float_rows


RADIX = 256
LEVELS = 255
OUTPUTS_PER_PACKET = 6
HTML_PATH = OUT / "container-packed-block.html"
CSS_PATH = OUT / "container-packed-block.css"
REFERENCE_PATH = OUT / "container-packed-block-reference.json"


def pack_metric(font_group: FontGroup, glyph_index: int) -> str:
    packs = []
    for pack, first_shard in enumerate(range(0, len(font_group.names), PACK_SHARDS)):
        characters = "".join(
            f"&#x{font_group.codepoint_starts[shard] + glyph_index:X};"
            for shard in range(
                first_shard,
                min(first_shard + PACK_SHARDS, len(font_group.names)),
            )
        )
        packs.append((pack, characters))
    if len(packs) == 1:
        return packs[0][1]
    return "".join(
        f'<i class="pack pack-{pack}">{characters}</i>'
        for pack, characters in packs
    )


def packet_shadow(
    stage_name: str,
    font_group: FontGroup,
    input_properties: list[str],
    activation_range: float,
    quantized: QuantizedRows,
    bias: np.ndarray,
    output_ranges: np.ndarray,
    output_indices: list[int],
    *,
    family_prefix: str,
) -> str:
    if len(output_indices) % OUTPUTS_PER_PACKET:
        raise ValueError("six-output transport requires a multiple of six outputs")
    families = [
        f"{family_prefix.replace('-', '')}S{shard}"
        for shard in range(len(font_group.names))
    ]
    pack_rules = []
    for pack, first_shard in enumerate(range(0, len(families), PACK_SHARDS)):
        selector = ":host" if len(families) <= PACK_SHARDS else f".pack-{pack}"
        pack_rules.append(
            f'{selector}{{font-family:{",".join(families[first_shard:first_shard + PACK_SHARDS])};'
            f"font-variation-settings:{pack_font_settings(input_properties, activation_range, first_shard)}}}"
        )

    base_total = sum(font_group.bases)
    packet_metrics: list[list[str]] = []
    packet_dimensions: list[tuple[str, str]] = []
    packet_declarations: list[list[str]] = []
    for packet_start in range(0, len(output_indices), OUTPUTS_PER_PACKET):
        metrics = []
        dimensions = []
        declarations = []
        for axis in range(2):
            codes = []
            packed = f"round(nearest,100cq{'w' if axis == 0 else 'h'} / 1px,1)"
            for digit in range(3):
                local = packet_start + axis * 3 + digit
                output = output_indices[local]
                anchor = f"--cpm-{local:04d}"
                metrics.append(
                    f'<span class="metric" style="anchor-name:{anchor}">'
                    f"{pack_metric(font_group, output)}</span>"
                )
                factor = activation_range * quantized.scales[output]
                value_range = float(output_ranges[output])
                raw = (
                    f"round(nearest,anchor-size({anchor} width) / 1px * "
                    f"{UNITS_PER_EM} / {FONT_SIZE} - {base_total},1)"
                )
                value = (
                    f"({raw} * {css_number(factor)} + ({css_number(bias[output])}))"
                )
                codes.append(
                    "round(nearest,clamp(0px,calc(("
                    + value
                    + f" + {css_number(value_range)}) * {LEVELS} / "
                    + f"{css_number(2 * value_range)} * 1px),{LEVELS}px),1px)"
                )
                if digit == 0:
                    code = f"mod({packed},{RADIX})"
                elif digit == 1:
                    code = f"mod(round(down,{packed}/{RADIX},1),{RADIX})"
                else:
                    code = f"round(down,{packed}/{RADIX ** 2},1)"
                decoded = (
                    f"(-{css_number(value_range)} + {code} * "
                    f"{css_number(2 * value_range / LEVELS)})"
                )
                declarations.append(
                    f"--raw-{local:03d}:calc(({decoded} - "
                    f"({css_number(bias[output])})) / {css_number(factor)})"
                )
            dimensions.append(
                "calc("
                + " + ".join(
                    f"{code} * {RADIX ** digit}"
                    for digit, code in enumerate(codes)
                )
                + ")"
            )
        packet_metrics.append(metrics)
        packet_dimensions.append((dimensions[0], dimensions[1]))
        packet_declarations.append(declarations)

    rules = [
        ":host{display:block;position:relative}",
        f".metric{{position:fixed;inset:0 auto auto 0;display:inline-flex;width:max-content;"
        f"height:1px;overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;"
        "font-kerning:none;font-style:normal}",
        ".pack{display:inline-block;width:max-content;height:1px;overflow:hidden;white-space:pre}",
        ".probe{position:fixed;inset:0 auto auto 0;display:block;container-type:size}",
        *pack_rules,
    ]
    for packet, (width, height) in enumerate(packet_dimensions):
        inherited = [] if packet == 0 else packet_declarations[packet - 1]
        rules.append(
            f".probe-{packet:04d}{{width:{width};height:{height};"
            + ";".join(inherited)
            + "}"
        )
    rules.append("slot{" + ";".join(packet_declarations[-1]) + "}")
    stage_css = "".join(rules)
    path = OUT / f"stage-{stage_name}.css"
    path.write_text(stage_css)
    tag = hashlib.sha256(path.read_bytes()).hexdigest()[:12]

    child = '<slot name="next"></slot>'
    for packet in reversed(range(len(packet_dimensions))):
        child = (
            "".join(packet_metrics[packet])
            + f'<div class="probe probe-{packet:04d}">{child}</div>'
        )
    return (
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{path.name}?v={tag}">'
        + child
        + "</template>"
    )


def quantize_values(values: np.ndarray, ranges: np.ndarray) -> np.ndarray:
    codes = np.rint(np.clip((values + ranges) * LEVELS / (2 * ranges), 0, LEVELS))
    return -ranges + codes * (2 * ranges / LEVELS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_mlp = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)

    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    attention = q_attention.reconstructed @ n1 + composed_bias
    residual = data["x"] + attention
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    pre = q_fc.reconstructed @ n2 + data["fc_bias"]
    hidden = gelu_new(pre)
    projected = q_mlp.reconstructed @ hidden + data["mlp_proj_bias"]
    baseline = residual + projected

    attention_ranges = np.maximum(np.abs(attention) * 1.1, 0.05)
    pre_ranges = np.maximum(np.abs(pre) * 1.1, 0.05)
    projection_ranges = np.maximum(np.abs(projected) * 1.1, 0.05)
    packed_attention = quantize_values(attention, attention_ranges)
    packed_residual = data["x"] + packed_attention
    packed_n2 = layer_norm(
        packed_residual, data["ln2_gamma"], data["ln2_beta"]
    )
    packed_pre = quantize_values(
        q_fc.reconstructed @ packed_n2 + data["fc_bias"], pre_ranges
    )
    packed_hidden = gelu_new(packed_pre)
    packed_projection = quantize_values(
        q_mlp.reconstructed @ packed_hidden + data["mlp_proj_bias"],
        projection_ranges,
    )
    packed_output = packed_residual + packed_projection

    attention_fonts = build_font_group("attn-composed", q_attention.codes, rebuild=False)
    fc_fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    mlp_fonts = build_font_group("mlp-proj", q_mlp.codes, rebuild=False)
    n1_range = float(np.max(np.abs(n1)) * 1.01)
    n2_range = float(np.max(np.abs(packed_n2)) * 1.01)
    hidden_range = float(np.max(np.abs(packed_hidden)) * 1.01)

    attention_shadow = packet_shadow(
        "container6-attn",
        attention_fonts,
        [f"--n1-{index:03d}" for index in range(WIDTH)],
        n1_range,
        q_attention,
        composed_bias,
        attention_ranges,
        list(range(WIDTH)),
        family_prefix="composed-attn",
    )
    fc_shadows = [
        packet_shadow(
            f"container6-fc{stage}",
            fc_fonts,
            [f"--n2-{index:03d}" for index in range(WIDTH)],
            n2_range,
            q_fc,
            data["fc_bias"],
            pre_ranges,
            list(range(stage * 1536, (stage + 1) * 1536)),
            family_prefix="fc",
        )
        for stage in range(2)
    ]
    projection_shadow = packet_shadow(
        "container6-mlp",
        mlp_fonts,
        [f"--hidden-{index:03d}" for index in range(MLP_WIDTH)],
        hidden_range,
        q_mlp,
        data["mlp_proj_bias"],
        projection_ranges,
        list(range(WIDTH)),
        family_prefix="mlp",
    )

    refs: dict[str, object] = {
        "q_composed": q_attention,
        "composed_bias": composed_bias,
        "q_fc": q_fc,
        "q_mlp": q_mlp,
        "n1_range": n1_range,
        "n2_range": n2_range,
        "hidden_range": hidden_range,
    }
    CSS_PATH.write_text(
        font_faces("composedattn", attention_fonts)
        + font_faces("fc", fc_fonts)
        + font_faces("mlp", mlp_fonts)
        + global_css(
            data,
            refs,
            composed_attention=True,
            fc_stage_outputs_override=1536,
        )
    )
    css_tag = hashlib.sha256(CSS_PATH.read_bytes()).hexdigest()[:12]
    stages = [
        ("norm1", attention_shadow),
        ("after-attn", fc_shadows[0]),
        ("hidden-stage-00", fc_shadows[1]),
        ("hidden-stage-01", projection_shadow),
    ]
    child = '<output id="final" class="final" slot="next"></output>'
    for index, (css_class, shadow) in reversed(list(enumerate(stages))):
        child = host(css_class, shadow, child, outer=index == 0)
    page_prefix = (
        '<!doctype html><meta charset="utf-8"><title>Container-packed GPT-2 block</title>'
        f'<link rel="stylesheet" href="{CSS_PATH.name}?v={css_tag}">'
    )
    HTML_PATH.write_text(page_prefix + child)
    next_classes = ("after-attn", "hidden-stage-00", "hidden-stage-01", "final")
    for count in range(1, len(stages) + 1):
        prefix_child = (
            f'<output id="final" class="{next_classes[count - 1]}" slot="next"></output>'
        )
        for index in reversed(range(count)):
            css_class, shadow = stages[index]
            prefix_child = host(css_class, shadow, prefix_child, outer=index == 0)
        (OUT / f"container-packed-block-prefix-{count}.html").write_text(
            page_prefix + prefix_child
        )
    error = packed_output - baseline
    REFERENCE_PATH.write_text(
        json.dumps(
            {
                "input": data["x"].tolist(),
                "baseline": baseline.tolist(),
                "packed": packed_output.tolist(),
                "packedAttention": packed_attention.tolist(),
                "packedResidual": packed_residual.tolist(),
                "packedN2": packed_n2.tolist(),
                "packedPre": packed_pre.tolist(),
                "packedHidden": packed_hidden.tolist(),
                "packedProjection": packed_projection.tolist(),
                "simulatedRmse": float(np.sqrt(np.mean(error * error))),
                "simulatedMaximumError": float(np.max(np.abs(error))),
                "packets": {
                    "attention": WIDTH // OUTPUTS_PER_PACKET,
                    "fcPerStage": 1536 // OUTPUTS_PER_PACKET,
                    "fcStages": 2,
                    "projection": WIDTH // OUTPUTS_PER_PACKET,
                },
                "htmlBytes": HTML_PATH.stat().st_size,
                "cssBytes": CSS_PATH.stat().st_size
                + sum(
                    (OUT / f"stage-container6-{name}.css").stat().st_size
                    for name in ("attn", "fc0", "fc1", "mlp")
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "simulatedRmse": float(np.sqrt(np.mean(error * error))),
                "simulatedMaximumError": float(np.max(np.abs(error))),
                "packets": {
                    "attention": WIDTH // OUTPUTS_PER_PACKET,
                    "fcPerStage": 1536 // OUTPUTS_PER_PACKET,
                    "fcStages": 2,
                    "projection": WIDTH // OUTPUTS_PER_PACKET,
                },
                "htmlBytes": HTML_PATH.stat().st_size,
                "cssBytes": CSS_PATH.stat().st_size
                + sum(
                    (OUT / f"stage-container6-{name}.css").stat().st_size
                    for name in ("attn", "fc0", "fc1", "mlp")
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
