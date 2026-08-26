#!/usr/bin/env python3
"""Attach a live block-1 attention residual to the packed block-0 CSS page."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
    OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    font_faces,
    gelu_new,
    global_axis_tag,
    layer_norm,
    model_data,
    norm_declarations,
    pack_font_settings,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


SOURCE_MODE = os.environ.get("TWO_BLOCK_SOURCE_MODE", "packed")
if SOURCE_MODE not in {
    "packed", "exact", "exact-easing", "exact-all-easing", "exact-global"
}:
    raise ValueError(
        "TWO_BLOCK_SOURCE_MODE must be packed, exact, exact-easing, "
        "exact-all-easing, or exact-global"
    )
BOUNDARY_MODE = os.environ.get("TWO_BLOCK_BOUNDARY_MODE", "direct")
if BOUNDARY_MODE not in {"direct", "timeline"}:
    raise ValueError("TWO_BLOCK_BOUNDARY_MODE must be direct or timeline")
if BOUNDARY_MODE == "timeline" and SOURCE_MODE not in {
    "exact", "exact-easing", "exact-all-easing", "exact-global"
}:
    raise ValueError("timeline boundary currently requires exact source mode")
GATE_MODE = os.environ.get("TWO_BLOCK_GATE_MODE", "none")
if GATE_MODE not in {"none", "content", "rearm"}:
    raise ValueError("TWO_BLOCK_GATE_MODE must be none, content, or rearm")
if GATE_MODE in {"content", "rearm"} and (
    SOURCE_MODE not in {
        "exact", "exact-easing", "exact-all-easing", "exact-global"
    }
    or BOUNDARY_MODE != "direct"
):
    raise ValueError("gating currently requires exact direct mode")
GATE_MILLISECONDS = int(os.environ.get("TWO_BLOCK_GATE_MILLISECONDS", "1"))
if GATE_MILLISECONDS < 1:
    raise ValueError("TWO_BLOCK_GATE_MILLISECONDS must be positive")
FC_EASING_GELU = os.environ.get("TWO_BLOCK_FC_EASING_GELU", "0") == "1"
FC_EASING_STOPS = int(os.environ.get("TWO_BLOCK_FC_EASING_STOPS", "257"))
if FC_EASING_STOPS < 3:
    raise ValueError("TWO_BLOCK_FC_EASING_STOPS must be at least 3")
PROJECTION_EASING = (
    os.environ.get("TWO_BLOCK_PROJECTION_EASING", "0") == "1"
)
PROJECTION_EASING_STOPS = int(
    os.environ.get("TWO_BLOCK_PROJECTION_EASING_STOPS", "129")
)
if PROJECTION_EASING_STOPS < 3:
    raise ValueError("TWO_BLOCK_PROJECTION_EASING_STOPS must be at least 3")
PROJECTION_EASING_MIN = float(
    os.environ.get("TWO_BLOCK_PROJECTION_EASING_MIN", "-128")
)
PROJECTION_EASING_MAX = float(
    os.environ.get("TWO_BLOCK_PROJECTION_EASING_MAX", "768")
)
if PROJECTION_EASING_MAX <= PROJECTION_EASING_MIN:
    raise ValueError("projection easing maximum must exceed minimum")
GLOBAL_PROJECTION = (
    os.environ.get("TWO_BLOCK_GLOBAL_PROJECTION", "0") == "1"
)
if SOURCE_MODE == "exact-global":
    SOURCE_STEM = "view-timeline-block-hybrid-global-projection-easing"
    SOURCE_LEAF_CLASS = "proj-result-5"
    OUTPUT_SUFFIX = "-exact-b0-global-projection"
elif SOURCE_MODE == "exact-all-easing":
    SOURCE_STEM = "view-timeline-block-hybrid-fc-projection-easing"
    SOURCE_LEAF_CLASS = "proj-result-5"
    OUTPUT_SUFFIX = "-exact-b0-all-easing"
elif SOURCE_MODE == "exact-easing":
    SOURCE_STEM = "view-timeline-block-hybrid-fc-easing-gelu"
    SOURCE_LEAF_CLASS = "proj-result-5"
    OUTPUT_SUFFIX = "-exact-b0-fc-easing"
elif SOURCE_MODE == "exact":
    SOURCE_STEM = "view-timeline-block-hybrid"
    SOURCE_LEAF_CLASS = "proj-result-5"
    OUTPUT_SUFFIX = "-exact"
else:
    SOURCE_STEM = "view-timeline-block-hybrid-packed4-chain-channel89asym-h15"
    SOURCE_LEAF_CLASS = "qo-result-5"
    OUTPUT_SUFFIX = ""
if BOUNDARY_MODE == "timeline":
    OUTPUT_SUFFIX += "-boundary"
if GATE_MODE != "none":
    OUTPUT_SUFFIX += "-gated"
if GATE_MODE == "rearm":
    OUTPUT_SUFFIX += "-rearm"
if GATE_MODE != "none" and GATE_MILLISECONDS != 1:
    OUTPUT_SUFFIX += f"-d{GATE_MILLISECONDS}"
if FC_EASING_GELU:
    OUTPUT_SUFFIX += "-fc-easing-gelu"
    if FC_EASING_STOPS != 257:
        OUTPUT_SUFFIX += f"-s{FC_EASING_STOPS}"
if PROJECTION_EASING:
    OUTPUT_SUFFIX += "-projection-easing"
    if PROJECTION_EASING_STOPS != 129:
        OUTPUT_SUFFIX += f"-s{PROJECTION_EASING_STOPS}"
if GLOBAL_PROJECTION:
    OUTPUT_SUFFIX += "-global-projection"
OUTPUTS_PER_CONSUMER = int(
    os.environ.get("TWO_BLOCK_OUTPUTS_PER_CONSUMER", "128")
)
if OUTPUTS_PER_CONSUMER <= 0 or OUTPUTS_PER_CONSUMER % 4:
    raise ValueError("TWO_BLOCK_OUTPUTS_PER_CONSUMER must be a positive multiple of 4")
if OUTPUTS_PER_CONSUMER != 128:
    OUTPUT_SUFFIX += f"-chunk{OUTPUTS_PER_CONSUMER}"
OUTPUT_STEM = f"view-timeline-two-block-attention-probe{OUTPUT_SUFFIX}"
SOURCE_DIR = Path(os.environ.get("TWO_BLOCK_SOURCE_DIR", OUT))
TARGET_BLOCK_INDEX = int(os.environ.get("TWO_BLOCK_TARGET_LAYER", "1"))
if not 1 <= TARGET_BLOCK_INDEX < 12:
    raise ValueError("TWO_BLOCK_TARGET_LAYER must be in [1, 11]")
TARGET_INPUT_JSON = os.environ.get("TWO_BLOCK_INPUT_JSON")


def calibrated_block0_packet(values: np.ndarray) -> np.ndarray:
    ranges = json.loads(
        (OUT.parent / "packed-activation-precision" / "hidden-ranges-headroom2.json")
        .read_text()
    )["blocks"][0]
    low = np.asarray(ranges["state_minimum"], dtype=np.float64) * 0.75
    high = np.asarray(ranges["state_maximum"], dtype=np.float64) * 0.75
    span = np.maximum(high - low, 1e-9)
    ranked = np.argsort(span)
    levels = np.full(WIDTH, 511, dtype=np.int64)
    levels[ranked[: WIDTH // 2]] = 255
    encoded = np.rint(np.clip((values - low) / span, 0, 1) * levels)
    return low + encoded / levels * span


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rebuild_fonts = os.environ.get("TWO_BLOCK_REBUILD_FONTS", "1") != "0"
    source_html_path = SOURCE_DIR / f"{SOURCE_STEM}.html"
    source_css_path = SOURCE_DIR / f"{SOURCE_STEM}.css"
    if not source_html_path.exists() or not source_css_path.exists():
        raise FileNotFoundError(
            "build the channel89asym-h15 block-0 page before this probe"
        )

    if TARGET_INPUT_JSON:
        block0_output = np.asarray(
            json.loads(Path(TARGET_INPUT_JSON).read_text()), dtype=np.float64
        )
        if block0_output.shape != (WIDTH,):
            raise ValueError("TWO_BLOCK_INPUT_JSON must contain 768 numbers")
        packed_input = block0_output
    else:
        block0_reference = json.loads(
            (SOURCE_DIR / "view-timeline-block-reference.json").read_text()
        )
        block0_output = np.asarray(block0_reference["output"], dtype=np.float64)
        packed_input = (
            block0_output
            if SOURCE_MODE in {
                "exact", "exact-easing", "exact-all-easing", "exact-global"
            }
            else calibrated_block0_packet(block0_output)
        )

    data = model_data(TARGET_BLOCK_INDEX, input_vector=packed_input)
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    quantized = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    normalized = layer_norm(packed_input, data["ln1_gamma"], data["ln1_beta"])
    activation_range = float(np.max(np.abs(normalized)) * 1.01)
    expected_attention = quantized.reconstructed @ normalized + composed_bias
    expected_output = packed_input + expected_attention
    normalized2 = layer_norm(expected_output, data["ln2_gamma"], data["ln2_beta"])
    quantized_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fc_activation_range = float(np.max(np.abs(normalized2)) * 1.01)
    expected_pre = quantized_fc.reconstructed @ normalized2 + data["fc_bias"]
    expected_hidden = gelu_new(expected_pre)
    hidden_range = float(np.max(np.abs(expected_hidden)) * 1.01)
    quantized_projection = quantize_float_rows(
        data["mlp_proj_weight"], bits=QUANT_BITS
    )
    expected_final = (
        expected_output
        + quantized_projection.reconstructed @ expected_hidden
        + data["mlp_proj_bias"]
    )

    fonts = build_font_group(
        "b1-attn-composed-rowbase",
        quantized.codes,
        rebuild=rebuild_fonts,
        row_specific_bases=True,
    )
    if fonts.row_bases is None:
        raise ValueError("block-1 row bases are required")
    fc_fonts = build_font_group(
        "b1-fc-rowbase",
        quantized_fc.codes,
        rebuild=rebuild_fonts,
        row_specific_bases=True,
    )
    projection_fonts = build_font_group(
        "b1-mlp-proj-rowbase",
        quantized_projection.codes,
        rebuild=rebuild_fonts,
        row_specific_bases=True,
    )
    global_projection_fonts = None
    if GLOBAL_PROJECTION:
        global_projection_shards = math.ceil(
            quantized_projection.codes.shape[1] / 256
        )
        global_projection_fonts_exist = all(
            (OUT / f"b1-mlp-proj-run-s{shard}.woff2").exists()
            for shard in range(global_projection_shards)
        )
        global_projection_fonts = build_font_group(
            "b1-mlp-proj-run",
            quantized_projection.codes,
            rebuild=rebuild_fonts or not global_projection_fonts_exist,
            row_specific_bases=True,
            global_axis_offset=0,
        )
    if fc_fonts.row_bases is None or projection_fonts.row_bases is None:
        raise ValueError("block-1 MLP row bases are required")
    if (
        GLOBAL_PROJECTION
        and global_projection_fonts is not None
        and global_projection_fonts.row_bases is None
    ):
        raise ValueError("block-1 global projection row bases are required")
    metric_bases = np.sum(np.stack(fonts.row_bases, axis=0), axis=0)
    base_pixels = float(np.max(metric_bases)) * FONT_SIZE / UNITS_PER_EM
    viewport = 2 ** math.ceil(math.log2(max(1024, base_pixels * 1.25)))
    track_width = viewport * 3

    timeline_names = [f"--b1t{index}" for index in range(WIDTH)]
    progress_names = [f"--b1p{index}" for index in range(WIDTH)]
    keyframe_names = [f"b1k{index}" for index in range(WIDTH)]
    registrations = (
        '@property --b1-mean{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --b1-var{syntax:"<number>";inherits:true;initial-value:0}'
        + "".join(
            f'@property --b1-n1-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --b1-out-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property {progress_names[index]}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for index in range(WIDTH)
        )
    )
    timeline_rules = "".join(
        f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for keyframe, progress in zip(keyframe_names, progress_names, strict=True)
    )
    normalization = norm_declarations(
        "out", "b1-n1", data["ln1_gamma"], data["ln1_beta"], "b1-mean", "b1-var"
    )
    input_names = [f"--b1-n1-{index:03d}" for index in range(WIDTH)]
    attention_settings = pack_font_settings(input_names, activation_range, 0)
    families = ",".join(f"b1attnS{index}" for index in range(len(fonts.names)))

    declarations: list[str] = []
    for output, progress in enumerate(progress_names):
        raw = (
            f"(({viewport} / var({progress}) - {viewport}) * "
            f"{UNITS_PER_EM} / {FONT_SIZE} - {int(metric_bases[output])})"
        )
        factor = activation_range * quantized.scales[output]
        declarations.append(
            f"--b1-out-{output:03d}:calc(var(--out-{output:03d}) + "
            f"{raw} * {css_number(factor)} + "
            f"({css_number(composed_bias[output])}))"
        )

    consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
    animation_rules: list[str] = []
    math_rules: list[str] = []
    for consumer in range(consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
        animation_rules.append(
            f".b1-result-{consumer}{{animation-name:"
            f"{','.join(keyframe_names[start:stop])};animation-duration:1s;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(timeline_names[start:stop])};"
            "animation-range:cover}"
        )
        math_rules.append(
            f".b1-result-{consumer}{{{';'.join(declarations[start:stop])}}}"
        )

    metrics: list[str] = []
    for output, timeline in enumerate(timeline_names):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        metrics.append(
            f'<span class="b1-metric" style="view-timeline:{timeline} inline">'
            f"{characters}</span>"
        )
    attention_leaf = (
        f'<output id="two-block-probe" class="b1-result-{consumer_count - 1}">'
        "block 1 attention residual</output>"
    )
    result_tree = attention_leaf
    for consumer in reversed(range(consumer_count - 1)):
        result_tree = f'<div class="b1-result-{consumer}">{result_tree}</div>'
    stage = (
        '<div class="b1-norm"><div class="b1-stage">'
        '<div class="b1-scroller"><div class="b1-track">'
        + "".join(metrics)
        + "</div></div>"
        + result_tree
        + "</div></div>"
    )

    # Complete block 1 with its second LayerNorm, FC + GELU, and projection.
    fc_metric_bases = np.sum(np.stack(fc_fonts.row_bases, axis=0), axis=0)
    fc_base_pixels = float(np.max(fc_metric_bases)) * FONT_SIZE / UNITS_PER_EM
    fc_viewport = 2 ** math.ceil(math.log2(max(1024, fc_base_pixels * 1.25)))
    fc_track_width = fc_viewport * 3
    fc_timeline_names = [f"--b1ft{index}" for index in range(MLP_WIDTH)]
    fc_progress_names = [f"--b1fp{index}" for index in range(MLP_WIDTH)]
    fc_keyframes = [f"b1fk{index}" for index in range(MLP_WIDTH)]
    active_projection_fonts = (
        global_projection_fonts
        if GLOBAL_PROJECTION and global_projection_fonts is not None
        else projection_fonts
    )
    if active_projection_fonts.row_bases is None:
        raise ValueError("active projection row bases are required")
    projection_metric_bases = np.sum(
        np.stack(active_projection_fonts.row_bases, axis=0), axis=0
    )
    projection_base_pixels = (
        float(np.max(projection_metric_bases)) * FONT_SIZE / UNITS_PER_EM
    )
    projection_viewport = 2 ** math.ceil(
        math.log2(max(1024, projection_base_pixels * 1.25))
    )
    projection_track_width = projection_viewport * 3
    projection_timeline_names = [f"--b1pt{index}" for index in range(WIDTH)]
    projection_progress_names = [f"--b1pp{index}" for index in range(WIDTH)]
    projection_keyframes = [f"b1pk{index}" for index in range(WIDTH)]

    full_registrations = (
        '@property --b1-mean2{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --b1-var2{syntax:"<number>";inherits:true;initial-value:0}'
        + "".join(
            f'@property --b1-n2-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --b1-final-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property {projection_progress_names[index]}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for index in range(WIDTH)
        )
        + "".join(
            f'@property --b1-hidden-{index:04d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property {fc_progress_names[index]}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for index in range(MLP_WIDTH)
        )
    )
    if FC_EASING_GELU:
        fc_keyframe_rules = "".join(
            f"@keyframes {keyframe}{{"
            f"from{{--b1-hidden-{index:04d}:var(--b1-ease-min)}}"
            f"to{{--b1-hidden-{index:04d}:var(--b1-ease-max)}}}}"
            for index, keyframe in enumerate(fc_keyframes)
        )
    else:
        fc_keyframe_rules = "".join(
            f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
            for keyframe, progress in zip(
                fc_keyframes, fc_progress_names, strict=True
            )
        )
    projection_easing_min = PROJECTION_EASING_MIN
    projection_easing_max = PROJECTION_EASING_MAX
    projection_easing_geometry_scale = (
        projection_viewport
        * 0.5
        / (projection_easing_max - projection_easing_min)
    )
    projection_easing_geometry_offset = (
        projection_viewport * 0.25
        - projection_easing_geometry_scale * projection_easing_min
    )
    projection_easing_css = ""
    if PROJECTION_EASING:
        projection_easing_z = np.linspace(
            projection_easing_max,
            projection_easing_min,
            PROJECTION_EASING_STOPS,
        )
        projection_easing_output = (
            (projection_easing_z - projection_easing_min)
            / (projection_easing_max - projection_easing_min)
        )
        projection_easing_progress = projection_viewport / (
            projection_viewport
            + projection_easing_geometry_offset
            + projection_easing_geometry_scale * projection_easing_z
        )
        projection_easing_stops = [
            f"{css_number(projection_easing_output[0])} 0%",
            *(
                f"{css_number(value)} {css_number(progress * 100)}%"
                for progress, value in zip(
                    projection_easing_progress,
                    projection_easing_output,
                    strict=True,
                )
            ),
        ]
        projection_easing_css = (
            f"--b1-projection-ease:linear({','.join(projection_easing_stops)})"
        )
        projection_keyframe_rules = "".join(
            f"@keyframes {keyframe}{{"
            f"from{{--b1-final-{index:03d}:{css_number(projection_easing_min)}}}"
            f"to{{--b1-final-{index:03d}:{css_number(projection_easing_max)}}}}}"
            for index, keyframe in enumerate(projection_keyframes)
        )
    else:
        projection_keyframe_rules = "".join(
            f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
            for keyframe, progress in zip(
                projection_keyframes, projection_progress_names, strict=True
            )
        )
    full_timeline_rules = fc_keyframe_rules + projection_keyframe_rules
    normalization2 = norm_declarations(
        "b1-out",
        "b1-n2",
        data["ln2_gamma"],
        data["ln2_beta"],
        "b1-mean2",
        "b1-var2",
    )
    n2_names = [f"--b1-n2-{index:03d}" for index in range(WIDTH)]
    fc_settings = pack_font_settings(n2_names, fc_activation_range, 0)
    fc_families = ",".join(f"b1fcS{index}" for index in range(len(fc_fonts.names)))
    hidden_names = [f"--b1-hidden-{index:04d}" for index in range(MLP_WIDTH)]

    # A view timeline normally exposes progress, after which 3,072 CSS
    # declarations invert the geometry, apply row scale/bias, and evaluate
    # GELU. In this variant each metric width is affinely normalized so every
    # row shares the same progress->preactivation mapping. One piecewise-linear
    # easing curve can then emit GELU directly into the registered hidden value.
    fc_easing_css = ""
    fc_easing_min = 0.0
    fc_easing_max = 1.0
    fc_easing_geometry_offset = fc_viewport // 2
    fc_easing_geometry_scale = fc_viewport // 32
    if FC_EASING_GELU:
        easing_z_min = -16.0
        easing_z_max = 24.0
        easing_z = np.linspace(easing_z_max, easing_z_min, FC_EASING_STOPS)
        easing_hidden = gelu_new(easing_z)
        dense_hidden = gelu_new(np.linspace(easing_z_min, easing_z_max, 8193))
        fc_easing_min = float(np.min(dense_hidden))
        fc_easing_max = float(np.max(dense_hidden))
        easing_output = (
            (easing_hidden - fc_easing_min)
            / (fc_easing_max - fc_easing_min)
        )
        easing_progress = fc_viewport / (
            fc_viewport
            + fc_easing_geometry_offset
            + fc_easing_geometry_scale * easing_z
        )
        easing_stops = [
            f"{css_number(easing_output[0])} 0%",
            *(
                f"{css_number(value)} {css_number(progress * 100)}%"
                for progress, value in zip(
                    easing_progress, easing_output, strict=True
                )
            ),
        ]
        fc_easing_css = (
            f"--b1-ease-min:{css_number(fc_easing_min)};"
            f"--b1-ease-max:{css_number(fc_easing_max)};"
            f"--b1-gelu-ease:linear({','.join(easing_stops)})"
        )

    fc_declarations: list[str] = []
    for output, progress in enumerate(fc_progress_names):
        raw = (
            f"(({fc_viewport} / var({progress}) - {fc_viewport}) * "
            f"{UNITS_PER_EM} / {FONT_SIZE} - {int(fc_metric_bases[output])})"
        )
        factor = fc_activation_range * quantized_fc.scales[output]
        pre = (
            f"({raw} * {css_number(factor)} + "
            f"({css_number(data['fc_bias'][output])}))"
        )
        fc_declarations.append(
            f"--b1-hidden-{output:04d}:--b1-gelu(calc{pre})"
        )
    fc_animation_rules: list[str] = []
    fc_math_rules: list[str] = []
    fc_consumer_count = math.ceil(MLP_WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(fc_consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, MLP_WIDTH)
        timing_function = "var(--b1-gelu-ease)" if FC_EASING_GELU else "linear"
        fc_animation_rules.append(
            f".b1fc-result-{consumer}{{animation-name:"
            f"{','.join(fc_keyframes[start:stop])};animation-duration:1s;"
            f"animation-timing-function:{timing_function};animation-fill-mode:both;"
            f"animation-timeline:{','.join(fc_timeline_names[start:stop])};"
            "animation-range:cover}"
        )
        if not FC_EASING_GELU:
            fc_math_rules.append(
                f".b1fc-result-{consumer}{{{';'.join(fc_declarations[start:stop])}}}"
            )
    fc_metrics = []
    for output, timeline in enumerate(fc_timeline_names):
        characters = "".join(
            f"&#x{start + output:X};" for start in fc_fonts.codepoint_starts
        )
        metric_style = f"view-timeline:{timeline} inline"
        if FC_EASING_GELU:
            factor = fc_activation_range * quantized_fc.scales[output]
            multiplier = (
                fc_easing_geometry_scale * factor * UNITS_PER_EM / FONT_SIZE
            )
            offset = (
                fc_easing_geometry_offset
                + fc_easing_geometry_scale * data["fc_bias"][output]
                - fc_easing_geometry_scale * factor * fc_metric_bases[output]
            )
            metric_style += (
                ";width:calc-size(max-content,"
                f"size * {css_number(multiplier)} + {css_number(offset)}px)"
            )
        fc_metrics.append(
            f'<span class="b1fc-metric" style="{metric_style}">'
            f"{characters}</span>"
        )

    projection_pack_rules: list[str] = []
    for pack, first_shard in enumerate(range(0, len(projection_fonts.names), 3)):
        families_for_pack = ",".join(
            f"b1projS{shard}"
            for shard in range(first_shard, min(first_shard + 3, len(projection_fonts.names)))
        )
        projection_pack_rules.append(
            f".b1proj-pack-{pack}{{font-family:{families_for_pack};"
            f"font-variation-settings:"
            f"{pack_font_settings(hidden_names, hidden_range, first_shard)}}}"
        )
    projection_global_css = ""
    if GLOBAL_PROJECTION and global_projection_fonts is not None:
        projection_global_families = ",".join(
            f"b1projrunS{shard}"
            for shard in range(len(global_projection_fonts.names))
        )
        projection_global_settings = ",".join(
            f'"{global_axis_tag(index)}" '
            f"calc(var(--b1-hidden-{index:04d}) / {css_number(hidden_range)})"
            for index in range(MLP_WIDTH)
        )
        projection_global_css = (
            f"font-family:{projection_global_families};"
            f"font-variation-settings:{projection_global_settings};"
        )
    projection_declarations: list[str] = []
    for output, progress in enumerate(projection_progress_names):
        raw = (
            f"(({projection_viewport} / var({progress}) - {projection_viewport}) * "
            f"{UNITS_PER_EM} / {FONT_SIZE} - {int(projection_metric_bases[output])})"
        )
        factor = hidden_range * quantized_projection.scales[output]
        projection_declarations.append(
            f"--b1-final-{output:03d}:calc(var(--b1-out-{output:03d}) + "
            f"{raw} * {css_number(factor)} + "
            f"({css_number(data['mlp_proj_bias'][output])}))"
        )
    projection_animation_rules: list[str] = []
    projection_math_rules: list[str] = []
    projection_consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(projection_consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
        projection_animation_rules.append(
            f".b1proj-result-{consumer}{{animation-name:"
            f"{','.join(projection_keyframes[start:stop])};animation-duration:1s;"
            "animation-timing-function:"
            f"{'var(--b1-projection-ease)' if PROJECTION_EASING else 'linear'};"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(projection_timeline_names[start:stop])};"
            "animation-range:cover}"
        )
        if not PROJECTION_EASING:
            projection_math_rules.append(
                f".b1proj-result-{consumer}{{"
                f"{';'.join(projection_declarations[start:stop])}}}"
            )
    projection_metrics: list[str] = []
    for output, timeline in enumerate(projection_timeline_names):
        if GLOBAL_PROJECTION and global_projection_fonts is not None:
            projection_content = "".join(
                f"&#x{start + output:X};"
                for start in global_projection_fonts.codepoint_starts
            )
        else:
            packs = []
            for pack, first_shard in enumerate(
                range(0, len(projection_fonts.names), 3)
            ):
                characters = "".join(
                    f"&#x{projection_fonts.codepoint_starts[shard] + output:X};"
                    for shard in range(
                        first_shard,
                        min(first_shard + 3, len(projection_fonts.names)),
                    )
                )
                packs.append(f'<i class="b1proj-pack-{pack}">{characters}</i>')
            projection_content = "".join(packs)
        metric_style = f"view-timeline:{timeline} inline"
        if PROJECTION_EASING:
            factor = hidden_range * quantized_projection.scales[output]
            multiplier = (
                projection_easing_geometry_scale
                * factor
                * UNITS_PER_EM
                / FONT_SIZE
            )
            constant_offset = (
                projection_easing_geometry_offset
                + projection_easing_geometry_scale
                * (data["mlp_proj_bias"][output] - factor * projection_metric_bases[output])
            )
            metric_style += (
                ";width:calc-size(max-content,calc("
                f"size * {css_number(multiplier)} + "
                f"({css_number(constant_offset)} + "
                f"{projection_easing_geometry_scale} * "
                f"var(--b1-out-{output:03d})) * 1px))"
            )
        projection_metrics.append(
            f'<span class="b1proj-metric" style="{metric_style}">'
            + projection_content
            + "</span>"
        )
    projection_leaf = (
        f'<output id="two-block-full" '
        f'class="b1proj-result-{projection_consumer_count - 1}">'
        "two complete blocks</output>"
    )
    projection_result_tree = projection_leaf
    for consumer in reversed(range(projection_consumer_count - 1)):
        projection_result_tree = (
            f'<div class="b1proj-result-{consumer}">{projection_result_tree}</div>'
        )
    projection_stage = (
        '<div class="b1proj-stage"><div class="b1proj-scroller">'
        '<div class="b1proj-track">'
        + "".join(projection_metrics)
        + "</div></div>"
        + projection_result_tree
        + "</div>"
    )
    fc_result_tree = (
        f'<div class="b1fc-result-{fc_consumer_count - 1}">'
        f"{projection_stage}</div>"
    )
    for consumer in reversed(range(fc_consumer_count - 1)):
        fc_result_tree = f'<div class="b1fc-result-{consumer}">{fc_result_tree}</div>'
    full_mlp_stage = (
        '<div class="b1-ln2"><div class="b1fc-stage">'
        '<div class="b1fc-scroller"><div class="b1fc-track">'
        + "".join(fc_metrics)
        + "</div></div>"
        + fc_result_tree
        + "</div></div>"
    )
    full_stage = stage.replace(
        attention_leaf,
        f'<div class="b1-result-{consumer_count - 1}">{full_mlp_stage}</div>',
        1,
    )

    # Optional materializing boundary between block 0 and block 1. The direct
    # page lets block 1 depend on block 0's 768 live custom properties. This
    # variant first turns every value into geometry, captures that geometry in
    # a fresh timeline-backed number, and only then exposes a new --out-* set
    # to block 1. It intentionally adds a lifecycle boundary to test whether
    # partitioning the cross-block style graph is cheaper than one giant graph.
    boundary_css = ""
    boundary_source_stage = ""
    boundary_consumer_stage = full_stage
    if BOUNDARY_MODE == "timeline":
        boundary_viewport = 16_384
        # Block residuals contain real outliers (about -72..104 in this
        # fixture), so leave enough signed headroom while retaining roughly
        # 2.4e-4 units of geometry precision.
        boundary_offset = 128
        boundary_scale = 64
        boundary_track_width = 32_768
        boundary_timelines = [f"--b0bt{index}" for index in range(WIDTH)]
        boundary_progress = [f"--b0bp{index}" for index in range(WIDTH)]
        boundary_keyframes = [f"b0bk{index}" for index in range(WIDTH)]
        boundary_registrations = "".join(
            f'@property {progress}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for progress in boundary_progress
        )
        boundary_keyframe_rules = "".join(
            f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
            for keyframe, progress in zip(
                boundary_keyframes, boundary_progress, strict=True
            )
        )
        boundary_metrics = "".join(
            f'<i class="b0b-metric" style="view-timeline:{timeline} inline;'
            f'width:calc((var(--out-{index:03d}) + {boundary_offset}) * '
            f'{boundary_scale}px)"></i>'
            for index, timeline in enumerate(boundary_timelines)
        )
        boundary_animation_rules: list[str] = []
        boundary_decode_rules: list[str] = []
        boundary_consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
        for consumer in range(boundary_consumer_count):
            start = consumer * OUTPUTS_PER_CONSUMER
            stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
            boundary_animation_rules.append(
                f".b0b-result-{consumer}{{animation-name:"
                f"{','.join(boundary_keyframes[start:stop])};"
                "animation-duration:1s;animation-timing-function:linear;"
                "animation-fill-mode:both;"
                f"animation-timeline:{','.join(boundary_timelines[start:stop])};"
                "animation-range:cover}"
            )
            decoded = []
            for index in range(start, stop):
                raw_width = (
                    f"({boundary_viewport} / "
                    f"var({boundary_progress[index]}) - {boundary_viewport})"
                )
                decoded.append(
                    f"--out-{index:03d}:calc({raw_width} / "
                    f"{boundary_scale} - {boundary_offset})"
                )
            boundary_decode_rules.append(
                f".b0b-result-{consumer}{{{';'.join(decoded)}}}"
            )
        boundary_result_tree = (
            f'<div class="b0b-result-{boundary_consumer_count - 1}">'
            f"{full_stage}</div>"
        )
        for consumer in reversed(range(boundary_consumer_count - 1)):
            boundary_result_tree = (
                f'<div class="b0b-result-{consumer}">{boundary_result_tree}</div>'
            )
        # Keep the geometry producers inside block 0 so they can inherit its
        # final --out-* values. The consumers are appended as document-level
        # siblings below, and therefore inherit none of block 0's temporary
        # state. A document timeline scope connects the otherwise independent
        # subtrees.
        boundary_source_stage = (
            '<div class="b0b-scroller"><div class="b0b-track">'
            + boundary_metrics
            + "</div></div>"
        )
        boundary_consumer_stage = boundary_result_tree
        boundary_css = (
            boundary_registrations
            + boundary_keyframe_rules
            + f'html{{timeline-scope:{",".join(boundary_timelines)}}}'
            + f".b0b-scroller{{position:fixed;left:0;top:-80000px;"
            f"width:{boundary_viewport}px;height:1px;overflow-x:scroll;"
            "overflow-y:hidden}"
            + f".b0b-track{{position:relative;width:{boundary_track_width}px;"
            "height:1px}"
            + ".b0b-metric{position:absolute;left:0;top:0;display:block;"
            "height:1px}"
            + "".join(boundary_animation_rules)
            + "".join(boundary_decode_rules)
        )
    gelu_function = (
        f"@function --b1-gelu(--z <number>) returns <number>{{"
        f"--t:clamp(-20,calc({css_number(math.sqrt(2 / math.pi))} * "
        "(var(--z) + .044715 * pow(var(--z),3))),20);"
        "result:calc(.5 * var(--z) * "
        "(1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
    )
    gate_css = ""
    if GATE_MODE in {"content", "rearm"}:
        gate_css = (
            '@property --b1-gate-open{syntax:"<integer>";inherits:false;'
            "initial-value:0}"
            "@keyframes b1-open-gate{to{--b1-gate-open:1}}"
            ".b1-norm{--b1-gate-open:0;content-visibility:"
            "if(style(--b1-gate-open:1):visible;else:hidden);"
            "contain-intrinsic-size:1px}"
            "@container style(--op0 > 0){.b1-norm{"
            f"animation:b1-open-gate {GATE_MILLISECONDS}ms "
            "steps(1,end) both}}"
        )
        if GATE_MODE == "rearm":
            gate_css += (
                "#b1-run:not(:checked)~css-stage{content-visibility:hidden;"
                "contain-intrinsic-size:1px}"
                "#b1-run:not(:checked)~css-stage .proj-result-0{"
                "animation:none!important}"
                "#b1-run{position:fixed;inset:auto auto 1rem 1rem}"
            )
    full_css = (
        font_faces("b1fc", fc_fonts)
        + (
            font_faces("b1projrun", global_projection_fonts)
            if GLOBAL_PROJECTION and global_projection_fonts is not None
            else font_faces("b1proj", projection_fonts)
        )
        + full_registrations
        + full_timeline_rules
        + boundary_css
        + gate_css
        + gelu_function
        + f".b1-ln2{{{';'.join(normalization2)}}}"
        + f'.b1fc-stage{{timeline-scope:{",".join(fc_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-family:{fc_families};font-kerning:none;"
        f"font-style:normal;font-variation-settings:{fc_settings};"
        f"{fc_easing_css}}}"
        + f".b1fc-scroller{{position:fixed;left:0;top:-60000px;width:{fc_viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}"
        + f".b1fc-track{{position:relative;width:{fc_track_width}px;height:1px}}"
        + ".b1fc-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + f'.b1proj-stage{{timeline-scope:{",".join(projection_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal;"
        f"{projection_global_css}{projection_easing_css}}}"
        + f".b1proj-scroller{{position:fixed;left:0;top:-70000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".b1proj-track{{position:relative;width:{projection_track_width}px;height:1px}}"
        + ".b1proj-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + ("" if GLOBAL_PROJECTION else "".join(projection_pack_rules))
        + "".join(fc_animation_rules)
        + "".join(fc_math_rules)
        + "".join(projection_animation_rules)
        + "".join(projection_math_rules)
        + "#two-block-full{display:block;font:14px ui-monospace,monospace}"
    )

    # Alternative complete block: quantize and pack four post-GELU values
    # into each timeline carrier, then decode them directly in the projection
    # font settings. This avoids materializing 3,072 independent CSS numbers.
    packed_group_count = MLP_WIDTH // 4
    packed_radix = 512
    packed_center = 128
    packed_hidden_min = -0.25
    packed_hidden_max = max(
        15.75,
        math.ceil(float(np.max(expected_hidden)) * 4) / 4 + 0.25,
    )
    packed_hidden_span = packed_hidden_max - packed_hidden_min
    packed_z_offset = 32
    packed_viewport = 1_048_576
    packed_extent = 300_000
    packed_left_base = packed_viewport - packed_extent
    packed_track_width = 1_600_000
    packed_importance = np.linalg.norm(
        quantized_projection.reconstructed, axis=0
    )
    packed_ranked = np.argsort(packed_importance)
    packed_low = packed_ranked[: MLP_WIDTH // 2]
    packed_high = packed_ranked[MLP_WIDTH // 2 :]
    packed_groups = [
        (
            int(packed_low[group * 2]),
            int(packed_high[group * 2]),
            int(packed_low[group * 2 + 1]),
            int(packed_high[group * 2 + 1]),
        )
        for group in range(packed_group_count)
    ]
    packed_locations = {
        output: (group, slot)
        for group, outputs in enumerate(packed_groups)
        for slot, output in enumerate(outputs)
    }
    packed_timeline_names = [f"--b1q4t{index}" for index in range(packed_group_count)]
    packed_cover_names = [f"--b1q4c{index}" for index in range(packed_group_count)]
    packed_entry_names = [f"--b1q4e{index}" for index in range(packed_group_count)]
    packed_keyframes = [f"b1q4k{index}" for index in range(packed_group_count)]
    packed_timeline_rules = "".join(
        f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{cover 0%{{{cover}:0;{entry}:0}}"
        f"entry 100%{{{entry}:1}}cover 100%{{{cover}:1;{entry}:1}}}}"
        for cover, entry, keyframe in zip(
            packed_cover_names, packed_entry_names, packed_keyframes, strict=True
        )
    )

    def packed_hidden_expression(output: int) -> str:
        group, slot = packed_locations[output]
        packed = (
            f"--b1q4l-{group:03d}" if slot < 2 else f"--b1q4p-{group:03d}"
        )
        if slot % 2 == 0:
            digit = f"(mod(var({packed}),{packed_radix}) - {packed_center})"
            levels = 255
        else:
            digit = f"round(down,var({packed}) / {packed_radix},1)"
            levels = 511
        return (
            f"calc(pow({digit} / {levels},2) * "
            f"{css_number(packed_hidden_span)} + "
            f"({css_number(packed_hidden_min)}))"
        )

    packed_digit_rules: list[str] = []
    packed_hidden_reference = np.empty(MLP_WIDTH, dtype=np.float64)
    for output in range(MLP_WIDTH):
        _, slot = packed_locations[output]
        multiplier = 1 if slot % 2 == 0 else packed_radix
        levels = 255 if multiplier == 1 else 511
        digit_offset = packed_center if multiplier == 1 else 0
        factor = fc_activation_range * quantized_fc.scales[output]
        z = (
            f"((size / 1px * {UNITS_PER_EM} / {FONT_SIZE} - "
            f"{int(fc_metric_bases[output])}) * {css_number(factor)} + "
            f"({css_number(data['fc_bias'][output])}))"
        )
        z_basis = f"calc-size(max-content,calc(({z} + {packed_z_offset}) * 1px))"
        u = f"(size / 1px - {packed_z_offset})"
        t = (
            f"clamp(-20,({css_number(math.sqrt(2 / math.pi))} * "
            f"({u} + .044715 * pow({u},3))),20)"
        )
        inline_gelu = (
            f"(.5 * {u} * (1 + (exp(2 * {t}) - 1) / "
            f"(exp(2 * {t}) + 1)))"
        )
        packed_digit_rules.append(
            f".b1q4d-{output:04d}{{width:calc-size({z_basis},calc((round(nearest,"
            f"sqrt((clamp({css_number(packed_hidden_min)},{inline_gelu},"
            f"{css_number(packed_hidden_max)}) - "
            f"({css_number(packed_hidden_min)})) / "
            f"{css_number(packed_hidden_span)}) * {levels},1) + "
            f"{digit_offset}) * 1px * {multiplier}))}}"
        )
        clipped = np.clip(
            expected_hidden[output], packed_hidden_min, packed_hidden_max
        )
        encoded = round(
            math.sqrt((clipped - packed_hidden_min) / packed_hidden_span)
            * levels
        )
        packed_hidden_reference[output] = (
            (encoded / levels) ** 2 * packed_hidden_span + packed_hidden_min
        )

    packed_declarations: list[str] = []
    for group in range(packed_group_count):
        cover = packed_cover_names[group]
        entry = packed_entry_names[group]
        width_name = f"--b1q4w-{group:03d}"
        left_name = f"--b1q4l-{group:03d}"
        payload_name = f"--b1q4p-{group:03d}"
        packed_declarations.extend((
            f"{width_name}:calc(var({cover}) * {packed_viewport} / "
            f"(var({entry}) - var({cover})))",
            f"{left_name}:round(nearest,{packed_viewport} - var({entry}) * "
            f"var({width_name}) - {packed_left_base},1)",
            f"{payload_name}:round(nearest,var({width_name}) - {packed_extent},1)",
        ))
    packed_groups_per_consumer = OUTPUTS_PER_CONSUMER // 4
    packed_consumer_count = math.ceil(
        packed_group_count / packed_groups_per_consumer
    )
    packed_animation_rules: list[str] = []
    packed_math_rules: list[str] = []
    packed_cached_math_rules: list[str] = []
    for consumer in range(packed_consumer_count):
        group_start = consumer * packed_groups_per_consumer
        group_stop = min(
            group_start + packed_groups_per_consumer, packed_group_count
        )
        packed_animation_rules.append(
            f".b1q4-result-{consumer}{{animation-name:"
            f"{','.join(packed_keyframes[group_start:group_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(packed_timeline_names[group_start:group_stop])}}}"
        )
        packed_math_rules.append(
            f".b1q4-result-{consumer}{{"
            + ";".join(
                packed_declarations[group_start * 3 : group_stop * 3]
            )
            + "}"
        )
        cached_outputs = [
            output
            for outputs in packed_groups[group_start:group_stop]
            for output in outputs
        ]
        packed_cached_math_rules.append(
            f".b1q4-result-{consumer}{{"
            + ";".join(
                [
                    *packed_declarations[group_start * 3 : group_stop * 3],
                    *(
                        f"--b1-hidden-{output:04d}:"
                        f"{packed_hidden_expression(output)}"
                        for output in cached_outputs
                    ),
                ]
            )
            + "}"
        )
    packed_group_html: list[str] = []
    for group, timeline in enumerate(packed_timeline_names):
        digits: list[str] = []
        for output in packed_groups[group]:
            characters = "".join(
                f"&#x{start + output:X};" for start in fc_fonts.codepoint_starts
            )
            digits.append(
                f'<i class="b1q4-digit b1q4d-{output:04d}">{characters}</i>'
            )
        packed_group_html.append(
            '<span class="b1q4-pair"><span class="b1q4-lead">'
            + "".join(digits[:2])
            + f'</span><span class="b1q4-subject" style="view-timeline:{timeline} inline">'
            + "".join(digits[2:])
            + "</span></span>"
        )

    packed_projection_pack_rules: list[str] = []
    shard_width = quantized_projection.codes.shape[1] // len(projection_fonts.names)
    for pack, first_shard in enumerate(range(0, len(projection_fonts.names), 3)):
        settings = pack_font_settings(hidden_names, hidden_range, first_shard)
        start = first_shard * shard_width
        stop = min((first_shard + 3) * shard_width, MLP_WIDTH)
        for output in range(start, stop):
            settings = settings.replace(
                f"var(--b1-hidden-{output:04d})",
                packed_hidden_expression(output),
            )
        packed_projection_pack_rules.append(
            f".b1proj-pack-{pack}{{font-family:"
            + ",".join(
                f"b1projS{shard}"
                for shard in range(
                    first_shard,
                    min(first_shard + 3, len(projection_fonts.names)),
                )
            )
            + f";font-variation-settings:{settings}}}"
        )

    packed_projection_global_css = ""
    if GLOBAL_PROJECTION and global_projection_fonts is not None:
        packed_projection_global_css = (
            "font-family:"
            + ",".join(
                f"b1projrunS{shard}"
                for shard in range(len(global_projection_fonts.names))
            )
            + ";font-variation-settings:"
            + ",".join(
                f'"{global_axis_tag(index)}" '
                f"calc({packed_hidden_expression(index)} / "
                f"{css_number(hidden_range)})"
                for index in range(MLP_WIDTH)
            )
            + ";"
        )

    packed_projection_tree = projection_stage
    packed_result_tree = (
        f'<div class="b1q4-result-{packed_consumer_count - 1}">'
        f"{packed_projection_tree}</div>"
    )
    for consumer in reversed(range(packed_consumer_count - 1)):
        packed_result_tree = (
            f'<div class="b1q4-result-{consumer}">{packed_result_tree}</div>'
        )
    packed_mlp_stage = (
        '<div class="b1-ln2"><div class="b1q4-stage">'
        '<div class="b1q4-scroller"><div class="b1q4-track">'
        + "".join(packed_group_html)
        + "</div></div>"
        + packed_result_tree
        + "</div></div>"
    )
    packed_full_stage = stage.replace(
        attention_leaf,
        f'<div class="b1-result-{consumer_count - 1}">{packed_mlp_stage}</div>',
        1,
    )
    packed_full_registrations = (
        '@property --b1-mean2{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --b1-var2{syntax:"<number>";inherits:true;initial-value:0}'
        + "".join(
            f'@property --b1-n2-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --b1-final-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property {projection_progress_names[index]}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for index in range(WIDTH)
        )
    )
    packed_full_css = (
        font_faces("b1fc", fc_fonts)
        + (
            font_faces("b1projrun", global_projection_fonts)
            if GLOBAL_PROJECTION and global_projection_fonts is not None
            else font_faces("b1proj", projection_fonts)
        )
        + packed_full_registrations
        + packed_timeline_rules
        + projection_keyframe_rules
        + f".b1-ln2{{{';'.join(normalization2)}}}"
        + f'.b1q4-stage{{timeline-scope:{",".join(packed_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-family:{fc_families};font-kerning:none;"
        f"font-style:normal;font-variation-settings:{fc_settings}}}"
        + f".b1q4-scroller{{position:fixed;left:0;top:-60000px;"
        f"width:{packed_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".b1q4-track{{position:relative;width:{packed_track_width}px;height:1px}}"
        + f".b1q4-pair{{position:absolute;left:{packed_left_base}px;top:0;"
        "display:inline-flex;height:1px}"
        + ".b1q4-lead,.b1q4-subject{display:inline-flex;flex:none;height:1px;"
        "white-space:pre;font-style:normal}"
        + f".b1q4-subject{{width:calc-size(max-content,size + {packed_extent}px)}}"
        + ".b1q4-digit{display:inline-block;flex:none;height:1px;overflow:hidden;"
        "white-space:pre;font-style:normal}"
        + "".join(packed_digit_rules)
        + f'.b1proj-stage{{timeline-scope:{",".join(projection_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal;"
        f"{packed_projection_global_css}{projection_easing_css}}}"
        + f".b1proj-scroller{{position:fixed;left:0;top:-70000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".b1proj-track{{position:relative;width:{projection_track_width}px;height:1px}}"
        + ".b1proj-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + (
            ""
            if GLOBAL_PROJECTION
            else "".join(packed_projection_pack_rules)
        )
        + "".join(packed_animation_rules)
        + "".join(packed_math_rules)
        + "".join(projection_animation_rules)
        + "".join(projection_math_rules)
        + "#two-block-full{display:block;font:14px ui-monospace,monospace}"
    )
    packed_cached_registrations = packed_full_registrations + "".join(
        f'@property --b1-hidden-{index:04d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(MLP_WIDTH)
    )
    packed_cached_css = packed_full_css.replace(
        packed_full_registrations,
        packed_cached_registrations,
        1,
    ).replace(
        "".join(packed_projection_pack_rules),
        "".join(projection_pack_rules),
        1,
    ).replace(
        "".join(packed_math_rules),
        "".join(packed_cached_math_rules),
        1,
    )
    expected_packed_final = (
        expected_output
        + quantized_projection.reconstructed @ packed_hidden_reference
        + data["mlp_proj_bias"]
    )

    css = (
        font_faces("b1attn", fonts)
        + registrations
        + timeline_rules
        + f".b1-norm{{{';'.join(normalization)}}}"
        + f'.b1-stage{{timeline-scope:{",".join(timeline_names)};font-size:{FONT_SIZE}px;'
        f"font-family:{families};font-kerning:none;font-style:normal;"
        f"font-variation-settings:{attention_settings}}}"
        + f".b1-scroller{{position:fixed;left:0;top:-50000px;width:{viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}"
        + f".b1-track{{position:relative;width:{track_width}px;height:1px}}"
        + ".b1-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + "".join(animation_rules)
        + "".join(math_rules)
        + "#two-block-probe{display:block;font:14px ui-monospace,monospace}"
    )
    css_path = OUT / f"{OUTPUT_STEM}.css"
    html_path = OUT / f"{OUTPUT_STEM}.html"
    isolated_html_path = OUT / f"view-timeline-block1-attention-isolated{OUTPUT_SUFFIX}.html"
    reference_path = OUT / f"{OUTPUT_STEM}-reference.json"
    full_css_path = OUT / f"view-timeline-two-block-full{OUTPUT_SUFFIX}.css"
    full_html_path = OUT / f"view-timeline-two-block-full{OUTPUT_SUFFIX}.html"
    full_isolated_html_path = OUT / f"view-timeline-block1-full-isolated{OUTPUT_SUFFIX}.html"
    full_reference_path = OUT / f"view-timeline-two-block-full{OUTPUT_SUFFIX}-reference.json"
    packed_full_css_path = OUT / f"view-timeline-two-block-full-packed4{OUTPUT_SUFFIX}.css"
    packed_full_html_path = OUT / f"view-timeline-two-block-full-packed4{OUTPUT_SUFFIX}.html"
    packed_full_isolated_html_path = (
        OUT / f"view-timeline-block1-full-packed4-isolated{OUTPUT_SUFFIX}.html"
    )
    packed_cached_css_path = OUT / f"view-timeline-two-block-full-packed4-cached{OUTPUT_SUFFIX}.css"
    packed_cached_html_path = OUT / f"view-timeline-two-block-full-packed4-cached{OUTPUT_SUFFIX}.html"
    packed_cached_isolated_html_path = (
        OUT / f"view-timeline-block1-full-packed4-cached-isolated{OUTPUT_SUFFIX}.html"
    )
    css_path.write_text(css)
    full_css_path.write_text(full_css)
    packed_full_css_path.write_text(packed_full_css)
    packed_cached_css_path.write_text(packed_cached_css)
    css_tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    full_css_tag = hashlib.sha256(full_css_path.read_bytes()).hexdigest()[:12]
    packed_full_css_tag = hashlib.sha256(
        packed_full_css_path.read_bytes()
    ).hexdigest()[:12]
    packed_cached_css_tag = hashlib.sha256(
        packed_cached_css_path.read_bytes()
    ).hexdigest()[:12]

    source_html = source_html_path.read_text()
    leaf = f'<output id="final" class="{SOURCE_LEAF_CLASS}"></output>'
    if source_html.count(leaf) != 1:
        raise ValueError("packed block-0 output leaf was not found exactly once")
    replacement = f'<div class="{SOURCE_LEAF_CLASS}">{stage}</div>'
    page = source_html.replace(leaf, replacement).replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{css_path.name}?v={css_tag}">',
        1,
    )
    html_path.write_text(page)
    if BOUNDARY_MODE == "timeline":
        full_replacement = (
            f'<div class="{SOURCE_LEAF_CLASS}">{boundary_source_stage}</div>'
        )
        full_page_source = (
            source_html.replace(leaf, full_replacement)
            + boundary_consumer_stage
        )
    else:
        full_replacement = f'<div class="{SOURCE_LEAF_CLASS}">{full_stage}</div>'
        full_page_source = source_html.replace(leaf, full_replacement)
    if GATE_MODE == "rearm":
        full_page_source = full_page_source.replace(
            "<css-stage ",
            '<input id="b1-run" type="checkbox" aria-label="Run inference">'
            "<css-stage ",
            1,
        )
    full_page = full_page_source.replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<link rel="stylesheet" href="{full_css_path.name}?v={full_css_tag}">',
        1,
    )
    full_html_path.write_text(full_page)
    packed_full_replacement = f'<div class="{SOURCE_LEAF_CLASS}">{packed_full_stage}</div>'
    packed_full_page = source_html.replace(
        leaf, packed_full_replacement
    ).replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<link rel="stylesheet" href="{packed_full_css_path.name}'
        f'?v={packed_full_css_tag}">',
        1,
    )
    packed_full_html_path.write_text(packed_full_page)
    packed_cached_page = source_html.replace(
        leaf, packed_full_replacement
    ).replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<link rel="stylesheet" href="{packed_cached_css_path.name}'
        f'?v={packed_cached_css_tag}">',
        1,
    )
    packed_cached_html_path.write_text(packed_cached_page)
    input_style = ";".join(
        f"--out-{index:03d}:{css_number(value)}"
        for index, value in enumerate(packed_input)
    )
    isolated_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Isolated block-1 attention probe</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<div style="{input_style}">{stage}</div>'
    )
    full_isolated_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Isolated complete block-1 probe</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<link rel="stylesheet" href="{full_css_path.name}?v={full_css_tag}">'
        f'<div style="{input_style}">{full_stage}</div>'
    )
    packed_full_isolated_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Isolated packed complete block-1 probe</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<link rel="stylesheet" href="{packed_full_css_path.name}'
        f'?v={packed_full_css_tag}">'
        f'<div style="{input_style}">{packed_full_stage}</div>'
    )
    packed_cached_isolated_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Isolated cached packed complete block-1 probe</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        f'<link rel="stylesheet" href="{packed_cached_css_path.name}'
        f'?v={packed_cached_css_tag}">'
        f'<div style="{input_style}">{packed_full_stage}</div>'
    )
    attention_font_bytes = sum(
        (OUT / f"{name}.woff2").stat().st_size for name in fonts.names
    )
    active_projection_font_names = (
        global_projection_fonts.names
        if GLOBAL_PROJECTION and global_projection_fonts is not None
        else projection_fonts.names
    )
    mlp_font_bytes = sum(
        (OUT / f"{name}.woff2").stat().st_size
        for name in [*fc_fonts.names, *active_projection_font_names]
    )
    reference_path.write_text(json.dumps({
        "source_mode": SOURCE_MODE,
        "boundary_mode": BOUNDARY_MODE,
        "gate_mode": GATE_MODE,
        "fc_easing_gelu": FC_EASING_GELU,
        "fc_easing_stops": FC_EASING_STOPS if FC_EASING_GELU else None,
        "projection_easing": PROJECTION_EASING,
        "projection_easing_stops": (
            PROJECTION_EASING_STOPS if PROJECTION_EASING else None
        ),
        "global_projection": GLOBAL_PROJECTION,
        "width": WIDTH,
        "block0_unpacked": block0_output.tolist(),
        "block0_packed": packed_input.tolist(),
        "block1_n1": normalized.tolist(),
        "expected": expected_output.tolist(),
        "activation_range": activation_range,
        "viewport": viewport,
        "timelines": WIDTH + 960,
        "html_bytes": html_path.stat().st_size,
        "isolated_html_bytes": isolated_html_path.stat().st_size,
        "css_bytes": css_path.stat().st_size + source_css_path.stat().st_size,
        "font_bytes": attention_font_bytes,
    }, indent=2) + "\n")
    full_reference_path.write_text(json.dumps({
        "source_mode": SOURCE_MODE,
        "boundary_mode": BOUNDARY_MODE,
        "gate_mode": GATE_MODE,
        "fc_easing_gelu": FC_EASING_GELU,
        "fc_easing_stops": FC_EASING_STOPS if FC_EASING_GELU else None,
        "projection_easing": PROJECTION_EASING,
        "projection_easing_stops": (
            PROJECTION_EASING_STOPS if PROJECTION_EASING else None
        ),
        "global_projection": GLOBAL_PROJECTION,
        "projection_easing_min": (
            projection_easing_min if PROJECTION_EASING else None
        ),
        "projection_easing_max": (
            projection_easing_max if PROJECTION_EASING else None
        ),
        "fc_easing_min": fc_easing_min,
        "fc_easing_max": fc_easing_max,
        "width": WIDTH,
        "mlp_width": MLP_WIDTH,
        "block0_unpacked": block0_output.tolist(),
        "block0_packed": packed_input.tolist(),
        "block1_attention_residual": expected_output.tolist(),
        "block1_n2": normalized2.tolist(),
        "block1_hidden": expected_hidden.tolist(),
        "expected": expected_final.tolist(),
        "block1_hidden_packed": packed_hidden_reference.tolist(),
        "expected_packed": expected_packed_final.tolist(),
        "packed_approximation_rmse": float(np.sqrt(np.mean(
            (expected_packed_final - expected_final) ** 2
        ))),
        "packed_approximation_max_error": float(np.max(np.abs(
            expected_packed_final - expected_final
        ))),
        "packed_hidden_min": packed_hidden_min,
        "packed_hidden_max": packed_hidden_max,
        "attention_activation_range": activation_range,
        "fc_activation_range": fc_activation_range,
        "hidden_range": hidden_range,
        "attention_viewport": viewport,
        "fc_viewport": fc_viewport,
        "projection_viewport": projection_viewport,
        "timelines": (
            960 + WIDTH + MLP_WIDTH + WIDTH
            + (WIDTH if BOUNDARY_MODE == "timeline" else 0)
        ),
        "html_bytes": full_html_path.stat().st_size,
        "isolated_html_bytes": full_isolated_html_path.stat().st_size,
        "css_bytes": (
            source_css_path.stat().st_size
            + css_path.stat().st_size
            + full_css_path.stat().st_size
        ),
        "font_bytes": attention_font_bytes + mlp_font_bytes,
        "packed": {
            "timelines": 960 + WIDTH + packed_group_count + WIDTH,
            "html_bytes": packed_full_html_path.stat().st_size,
            "isolated_html_bytes": packed_full_isolated_html_path.stat().st_size,
            "css_bytes": (
                source_css_path.stat().st_size
                + css_path.stat().st_size
                + packed_full_css_path.stat().st_size
            ),
            "font_bytes": attention_font_bytes + mlp_font_bytes,
            "cached": {
                "timelines": 960 + WIDTH + packed_group_count + WIDTH,
                "html_bytes": packed_cached_html_path.stat().st_size,
                "isolated_html_bytes": packed_cached_isolated_html_path.stat().st_size,
                "css_bytes": (
                    source_css_path.stat().st_size
                    + css_path.stat().st_size
                    + packed_cached_css_path.stat().st_size
                ),
                "font_bytes": attention_font_bytes + mlp_font_bytes,
            },
        },
    }, indent=2) + "\n")
    print({
        "html_bytes": html_path.stat().st_size,
        "css_bytes": css_path.stat().st_size + source_css_path.stat().st_size,
        "font_bytes": attention_font_bytes,
        "timelines": WIDTH + 960,
        "full_html_bytes": full_html_path.stat().st_size,
        "full_css_bytes": (
            source_css_path.stat().st_size
            + css_path.stat().st_size
            + full_css_path.stat().st_size
        ),
        "full_font_bytes": attention_font_bytes + mlp_font_bytes,
        "full_timelines": (
            960 + WIDTH + MLP_WIDTH + WIDTH
            + (WIDTH if BOUNDARY_MODE == "timeline" else 0)
        ),
        "packed_full_html_bytes": packed_full_html_path.stat().st_size,
        "packed_full_css_bytes": (
            source_css_path.stat().st_size
            + css_path.stat().st_size
            + packed_full_css_path.stat().st_size
        ),
        "packed_full_timelines": 960 + WIDTH + packed_group_count + WIDTH,
        "packed_cached_html_bytes": packed_cached_html_path.stat().st_size,
        "packed_cached_css_bytes": (
            source_css_path.stat().st_size
            + css_path.stat().st_size
            + packed_cached_css_path.stat().st_size
        ),
    })


if __name__ == "__main__":
    main()
