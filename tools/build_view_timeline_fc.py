#!/usr/bin/env python3
"""Build a flat HTML/CSS-only GPT-2 768→3072 FC + GELU stage."""

from __future__ import annotations

import hashlib
import json
import math
import os

import numpy as np

from build_gpt2_block_css import (
    EPSILON,
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


FONT_SIZE = 512
VIEWPORT = 32768
TRACK_WIDTH = 100000
OUTPUTS_PER_CONSUMER = int(os.environ.get("VIEW_TIMELINE_FC_CHUNK", "128"))
# One timeline carries the sum of all four projection font packs. Splitting it
# into four timelines was both slower and unreliable in Chromium at this scale.
PROJECTION_METRICS_PER_OUTPUT = 1
HTML_PATH = OUT / "view-timeline-fc.html"
CSS_PATH = OUT / "view-timeline-fc.css"
REFERENCE_PATH = OUT / "view-timeline-fc-reference.json"
MLP_HTML_PATH = OUT / "view-timeline-mlp.html"
MLP_CSS_PATH = OUT / "view-timeline-mlp.css"
MLP_REFERENCE_PATH = OUT / "view-timeline-mlp-reference.json"
BLOCK_HTML_PATH = OUT / "view-timeline-block.html"
BLOCK_CSS_PATH = OUT / "view-timeline-block.css"
BLOCK_REFERENCE_PATH = OUT / "view-timeline-block-reference.json"
HYBRID_BLOCK_HTML_PATH = OUT / "view-timeline-block-hybrid.html"
HYBRID_BLOCK_CSS_PATH = OUT / "view-timeline-block-hybrid.css"
FC_EASING_STOPS = int(os.environ.get("VIEW_TIMELINE_FC_EASING_STOPS", "513"))
if FC_EASING_STOPS < 3:
    raise ValueError("VIEW_TIMELINE_FC_EASING_STOPS must be at least 3")
FC_EASING_SUFFIX = "" if FC_EASING_STOPS == 513 else f"-s{FC_EASING_STOPS}"
HYBRID_FC_EASING_BLOCK_HTML_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-easing-gelu{FC_EASING_SUFFIX}.html"
)
HYBRID_FC_EASING_BLOCK_CSS_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-easing-gelu{FC_EASING_SUFFIX}.css"
)
HYBRID_FC_EASING_BLOCK_REFERENCE_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-easing-gelu{FC_EASING_SUFFIX}-reference.json"
)
PROJECTION_EASING_STOPS = int(
    os.environ.get("VIEW_TIMELINE_PROJECTION_EASING_STOPS", "257")
)
if PROJECTION_EASING_STOPS < 3:
    raise ValueError("VIEW_TIMELINE_PROJECTION_EASING_STOPS must be at least 3")
PROJECTION_EASING_SUFFIX = (
    "" if PROJECTION_EASING_STOPS == 257 else f"-s{PROJECTION_EASING_STOPS}"
)
HYBRID_ALL_EASING_BLOCK_HTML_PATH = (
    OUT
    / (
        "view-timeline-block-hybrid-fc-projection-easing"
        f"{PROJECTION_EASING_SUFFIX}.html"
    )
)
HYBRID_ALL_EASING_BLOCK_CSS_PATH = (
    OUT
    / (
        "view-timeline-block-hybrid-fc-projection-easing"
        f"{PROJECTION_EASING_SUFFIX}.css"
    )
)
HYBRID_ALL_EASING_BLOCK_REFERENCE_PATH = (
    OUT
    / (
        "view-timeline-block-hybrid-fc-projection-easing"
        f"{PROJECTION_EASING_SUFFIX}-reference.json"
    )
)
HYBRID_GLOBAL_PROJECTION_BLOCK_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-global-projection-easing.html"
)
HYBRID_GLOBAL_PROJECTION_BLOCK_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-global-projection-easing.css"
)
HYBRID_GLOBAL_PROJECTION_BLOCK_REFERENCE_PATH = (
    OUT / "view-timeline-block-hybrid-global-projection-easing-reference.json"
)
HYBRID_FC_PAIRED_BLOCK_HTML_PATH = OUT / "view-timeline-block-hybrid-fc-paired.html"
HYBRID_FC_PAIRED_BLOCK_CSS_PATH = OUT / "view-timeline-block-hybrid-fc-paired.css"
HYBRID_FC_PACKED4_BLOCK_HTML_PATH = OUT / "view-timeline-block-hybrid-fc-packed4.html"
HYBRID_FC_PACKED4_BLOCK_CSS_PATH = OUT / "view-timeline-block-hybrid-fc-packed4.css"
HYBRID_FC_PACKED4_HVAR_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar.html"
)
HYBRID_FC_PACKED4_HVAR_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar.css"
)
HYBRID_FC_PACKED4_HVAR_REFERENCE_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-reference.json"
)
HYBRID_FC_PACKED4_HVAR_GATHER_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather.html"
)
HYBRID_FC_PACKED4_HVAR_GATHER_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather.css"
)
HYBRID_FC_PACKED4_HVAR_GATHER_REFERENCE_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather-reference.json"
)
HYBRID_FC_PACKED4_HVAR_GATHER8_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather8.html"
)
HYBRID_FC_PACKED4_HVAR_GATHER8_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather8.css"
)
HYBRID_FC_PACKED4_HVAR_GATHER8_REFERENCE_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather8-reference.json"
)
HYBRID_FC_PACKED4_HVAR_GATHER_FLAT_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather-flat.html"
)
HYBRID_FC_PACKED4_HVAR_GATHER_FLAT_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather-flat.css"
)
HYBRID_FC_PACKED4_HVAR_GATHER_FIXED_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather-fixed.html"
)
HYBRID_FC_PACKED4_HVAR_GATHER_FIXED_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather-fixed.css"
)
HYBRID_FC_PACKED4_HVAR_DIRECT_LN_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-direct-ln.html"
)
HYBRID_FC_PACKED4_HVAR_DIRECT_LN_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-direct-ln.css"
)
HYBRID_FC_PACKED4_HVAR_DIRECT_LN_REFERENCE_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-hvar-direct-ln-reference.json"
)
HYBRID_FC_PACKED4_TRANSPORT_HTML_PATH = OUT / "view-timeline-block-hybrid-fc-packed4-transport.html"
HYBRID_FC_PACKED4_TRANSPORT_CSS_PATH = OUT / "view-timeline-block-hybrid-fc-packed4-transport.css"
OUTPUT_PACK_SCHEME = os.environ.get("VIEW_TIMELINE_OUTPUT_PACK_SCHEME", "global")
if OUTPUT_PACK_SCHEME not in {"global", "channel89", "channel89asym", "channel910"}:
    raise ValueError(
        "VIEW_TIMELINE_OUTPUT_PACK_SCHEME must be global, channel89, "
        "channel89asym, or channel910"
    )
OUTPUT_PACK_HEADROOM = float(
    os.environ.get("VIEW_TIMELINE_OUTPUT_PACK_HEADROOM", "1.1")
)
if OUTPUT_PACK_HEADROOM <= 0:
    raise ValueError("VIEW_TIMELINE_OUTPUT_PACK_HEADROOM must be positive")
if OUTPUT_PACK_SCHEME == "global":
    OUTPUT_PACK_SUFFIX = ""
else:
    scheme_suffix = OUTPUT_PACK_SCHEME.removeprefix("channel")
    OUTPUT_PACK_SUFFIX = f"-channel{scheme_suffix}"
    if not math.isclose(OUTPUT_PACK_HEADROOM, 1.1):
        headroom_suffix = format(OUTPUT_PACK_HEADROOM, "g").replace(".", "")
        OUTPUT_PACK_SUFFIX += f"-h{headroom_suffix}"
HYBRID_PACKED4_CHAIN_HTML_PATH = (
    OUT / f"view-timeline-block-hybrid-packed4-chain{OUTPUT_PACK_SUFFIX}.html"
)
HYBRID_PACKED4_CHAIN_CSS_PATH = (
    OUT / f"view-timeline-block-hybrid-packed4-chain{OUTPUT_PACK_SUFFIX}.css"
)
HYBRID_FC_PACKED4_PAIRED_OUTPUT_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-paired-output.html"
)
HYBRID_FC_PACKED4_PAIRED_OUTPUT_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-packed4-paired-output.css"
)
PACKED6_SCHEME = os.environ.get("VIEW_TIMELINE_PACKED6_SCHEME", "mixed")
if PACKED6_SCHEME not in {
    "mixed", "uniform6", "uniform6asym", "logasym4", "importance566",
    "packed7-56", "uniform7"
}:
    raise ValueError(
        "VIEW_TIMELINE_PACKED6_SCHEME must be mixed, uniform6, "
        "uniform6asym, logasym4, importance566, packed7-56, or uniform7"
    )
PACKED6_SUFFIX = "" if PACKED6_SCHEME == "mixed" else f"-{PACKED6_SCHEME}"
HYBRID_FC_PACKED6_BLOCK_HTML_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-packed6{PACKED6_SUFFIX}.html"
)
HYBRID_FC_PACKED6_BLOCK_CSS_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-packed6{PACKED6_SUFFIX}.css"
)
HYBRID_FC_PACKED6_TRANSPORT_HTML_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-packed6-transport{PACKED6_SUFFIX}.html"
)
HYBRID_FC_PACKED6_TRANSPORT_CSS_PATH = (
    OUT / f"view-timeline-block-hybrid-fc-packed6-transport{PACKED6_SUFFIX}.css"
)
HYBRID_FC_HETERO58_BLOCK_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-hetero58.html"
)
HYBRID_FC_HETERO58_BLOCK_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-hetero58.css"
)
HYBRID_FC_SENSITIVITY3456_BLOCK_HTML_PATH = (
    OUT / "view-timeline-block-hybrid-fc-sensitivity3456.html"
)
HYBRID_FC_SENSITIVITY3456_BLOCK_CSS_PATH = (
    OUT / "view-timeline-block-hybrid-fc-sensitivity3456.css"
)
ADDITIVE_PROJECTION_BLOCK_HTML_PATH = (
    OUT / "view-timeline-block-additive-projection.html"
)
ADDITIVE_PROJECTION_BLOCK_CSS_PATH = (
    OUT / "view-timeline-block-additive-projection.css"
)
BUILD_ADDITIVE_PROJECTION = os.environ.get("BUILD_ADDITIVE_PROJECTION", "0") == "1"
HYBRID_PAIRED_BLOCK_HTML_PATH = OUT / "view-timeline-block-hybrid-paired.html"
HYBRID_PAIRED_BLOCK_CSS_PATH = OUT / "view-timeline-block-hybrid-paired.css"
ATTENTION_PREFIX_CSS_PATH = OUT / "view-timeline-attention-prefix.css"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()
    next_block_data = model_data(
        block_index=1, input_vector=np.zeros(WIDTH, dtype=np.float64)
    )
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    attention = q_attention.reconstructed @ n1 + composed_bias
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_mlp = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    residual = data["x"] + attention
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    activation_range = float(np.max(np.abs(n2)) * 1.01)
    normalized = n2 / activation_range
    raw = q_fc.codes.astype(np.float64) @ normalized
    pre = raw * activation_range * q_fc.scales + data["fc_bias"]
    hidden = gelu_new(pre)
    hidden_range = float(np.max(np.abs(hidden)) * 1.01)
    projection_raw = q_mlp.codes.astype(np.float64) @ (hidden / hidden_range)
    projected = (
        projection_raw * hidden_range * q_mlp.scales + data["mlp_proj_bias"]
    )
    final_output = residual + projected

    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    attention_shards = math.ceil(q_attention.codes.shape[1] / 256)
    attention_fonts_exist = all(
        (OUT / f"attn-composed-rowbase-s{shard}.woff2").exists()
        for shard in range(attention_shards)
    )
    attention_fonts = build_font_group(
        "attn-composed-rowbase",
        q_attention.codes,
        rebuild=not attention_fonts_exist,
        row_specific_bases=True,
    )
    packed_attention_fonts = build_font_group(
        "attn-composed", q_attention.codes, rebuild=False
    )
    projection_shards = math.ceil(q_mlp.codes.shape[1] / 256)
    row_base_fonts_exist = all(
        (OUT / f"mlp-proj-rowbase-s{shard}.woff2").exists()
        for shard in range(projection_shards)
    )
    mlp_fonts = build_font_group(
        "mlp-proj-rowbase",
        q_mlp.codes,
        rebuild=not row_base_fonts_exist,
        row_specific_bases=True,
    )
    global_projection_fonts_exist = all(
        (OUT / f"mlp-proj-run-s{shard}.woff2").exists()
        for shard in range(projection_shards)
    )
    global_projection_fonts = build_font_group(
        "mlp-proj-run",
        q_mlp.codes,
        rebuild=not global_projection_fonts_exist,
        row_specific_bases=True,
        global_axis_offset=0,
    )
    base_total = sum(fonts.bases)
    input_names = [f"--n2-{index:03d}" for index in range(WIDTH)]
    timeline_names = [f"--t{index}" for index in range(MLP_WIDTH)]
    progress_names = [f"--p{index}" for index in range(MLP_WIDTH)]
    keyframe_names = [f"k{index}" for index in range(MLP_WIDTH)]

    timeline_rules = "".join(
        f'@property {progress}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for progress, keyframe in zip(progress_names, keyframe_names, strict=True)
    )
    hidden_registrations = "".join(
        f'@property --hidden-{index:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(MLP_WIDTH)
    )
    inputs = ";".join(
        [
            *(f"{name}:{css_number(value)}" for name, value in zip(input_names, n2, strict=True)),
            *(f"--r1-{index:03d}:{css_number(value)}" for index, value in enumerate(residual)),
        ]
    )
    font_settings = pack_font_settings(input_names, activation_range, 0)

    result_declarations: list[str] = []
    for index, progress in enumerate(progress_names):
        raw_name = f"--raw-{index:03d}"
        pre_name = f"--pre-{index:03d}"
        factor = activation_range * q_fc.scales[index]
        result_declarations.append(
            f"{raw_name}:calc(({VIEWPORT} / var({progress}) - {VIEWPORT}) "
            f"* {UNITS_PER_EM} / {FONT_SIZE} - {base_total})"
        )
        result_declarations.append(
            f"{pre_name}:calc(var({raw_name}) * {css_number(factor)} "
            f"+ ({css_number(data['fc_bias'][index])}))"
        )
        result_declarations.append(
            f"--hidden-{index:03d}:--gelu(var({pre_name}))"
        )

    gelu_function = (
        f"@function --gelu(--z <number>) returns <number>{{"
        f"--t:clamp(-20,calc({css_number(math.sqrt(2 / math.pi))} * "
        "(var(--z) + .044715 * pow(var(--z), 3))),20);"
        "result:calc(.5 * var(--z) * "
        "(1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
    )

    faces = font_faces("fc", fonts)
    inherited_font_state = (
        f"font-size:{FONT_SIZE}px;font-kerning:none;"
        f"font-family:{','.join(f'fcS{index}' for index in range(len(fonts.names)))};"
        f"font-variation-settings:{font_settings}"
    )
    scope_with_timelines = (
        f'.scope{{{inputs};timeline-scope:{",".join(timeline_names)};'
        f"{inherited_font_state}}}"
    )
    scope_without_timelines = f'.scope{{{inputs};{inherited_font_state}}}'
    layout_css = (
        ".scroller{position:fixed;left:0;top:-10000px;"
        + f"width:{VIEWPORT}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".track{{position:relative;width:{TRACK_WIDTH}px;height:1px}}"
        + ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;"
        + "height:1px;overflow:hidden;white-space:pre}"
    )
    animation_rules: list[str] = []
    result_math_rules: list[str] = []
    consumer_count = math.ceil(MLP_WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, MLP_WIDTH)
        animation_rules.append(
            f".result-{consumer}{{"
            f"animation-name:{','.join(keyframe_names[start:stop])};"
            "animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(timeline_names[start:stop])};"
            "animation-range:cover}"
        )
        result_math_rules.append(
            f".result-{consumer}{{"
            + ";".join(result_declarations[start * 3 : stop * 3])
            + "}"
        )
    animation_css = "".join(animation_rules)
    result_math_css = "".join(result_math_rules)
    visible_css = (
        "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}"
        + "body{margin:2rem}h1{font:600 1.25rem system-ui,sans-serif}"
    )
    css = (
        faces
        + timeline_rules
        + hidden_registrations
        + gelu_function
        + scope_with_timelines
        + layout_css
        + animation_css
        + result_math_css
        + visible_css
    )
    CSS_PATH.write_text(css)
    css_tag = hashlib.sha256(CSS_PATH.read_bytes()).hexdigest()[:12]

    glyphs_with_timelines: list[str] = []
    glyphs_without_timelines: list[str] = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        glyphs_with_timelines.append(
            f'<i class="metric" style="view-timeline:{timeline_names[output]} inline">'
            f"{characters}</i>"
        )
        glyphs_without_timelines.append(f'<i class="metric">{characters}</i>')

    timeline_scrollers = "".join(
        f'<div class="scroller"><div class="track">{glyph}</div></div>'
        for glyph in glyphs_with_timelines
    )
    shared_timeline_scroller = (
        '<div class="scroller"><div class="track">'
        + "".join(glyphs_with_timelines)
        + "</div></div>"
    )

    # Normalize every FC metric's geometry to the same preactivation range,
    # then use a shared piecewise-linear animation easing to emit GELU. This
    # replaces 3,072 progress inversions, row scales/biases, and CSS exp/pow
    # evaluations while keeping the exact HVAR dot products and projection.
    easing_z_min = -16.0
    easing_z_max = 24.0
    easing_geometry_offset = VIEWPORT // 2
    easing_geometry_scale = VIEWPORT // 32
    easing_z = np.linspace(easing_z_max, easing_z_min, FC_EASING_STOPS)
    easing_hidden = gelu_new(easing_z)
    dense_easing_hidden = gelu_new(
        np.linspace(easing_z_min, easing_z_max, 8193)
    )
    easing_hidden_min = float(np.min(dense_easing_hidden))
    easing_hidden_max = float(np.max(dense_easing_hidden))
    easing_outputs = (
        (easing_hidden - easing_hidden_min)
        / (easing_hidden_max - easing_hidden_min)
    )
    easing_progress = VIEWPORT / (
        VIEWPORT + easing_geometry_offset + easing_geometry_scale * easing_z
    )
    easing_stops = [
        f"{css_number(easing_outputs[0])} 0%",
        *(
            f"{css_number(value)} {css_number(progress * 100)}%"
            for progress, value in zip(
                easing_progress, easing_outputs, strict=True
            )
        ),
    ]
    easing_timeline_rules = "".join(
        f"@keyframes {keyframe}{{"
        f"from{{--hidden-{index:03d}:var(--fc-ease-min)}}"
        f"to{{--hidden-{index:03d}:var(--fc-ease-max)}}}}"
        for index, keyframe in enumerate(keyframe_names)
    )
    easing_animation_rules: list[str] = []
    for consumer in range(consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, MLP_WIDTH)
        easing_animation_rules.append(
            f".result-{consumer}{{"
            f"animation-name:{','.join(keyframe_names[start:stop])};"
            "animation-duration:1s;"
            "animation-timing-function:var(--fc-gelu-ease);"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(timeline_names[start:stop])};"
            "animation-range:cover}"
        )
    easing_metrics: list[str] = []
    for output, timeline in enumerate(timeline_names):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        factor = activation_range * q_fc.scales[output]
        multiplier = (
            easing_geometry_scale * factor * UNITS_PER_EM / FONT_SIZE
        )
        offset = (
            easing_geometry_offset
            + easing_geometry_scale * data["fc_bias"][output]
            - easing_geometry_scale * factor * base_total
        )
        easing_metrics.append(
            f'<i class="metric" style="view-timeline:{timeline} inline;'
            "width:calc-size(max-content,"
            f'size * {css_number(multiplier)} + {css_number(offset)}px)">'
            f"{characters}</i>"
        )
    easing_shared_timeline_scroller = (
        '<div class="scroller"><div class="track">'
        + "".join(easing_metrics)
        + "</div></div>"
    )
    # Best-case shaping control: the exact same 9,216 FC glyphs grouped into
    # one continuous text run per 256-input font shard. This performs every
    # HVAR row calculation but exposes no individual result to CSS.
    three_run_html = "".join(
        f'<i class="font-run font-run-{shard}">'
        + "".join(
            f"&#x{fonts.codepoint_starts[shard] + output:X};"
            for output in range(MLP_WIDTH)
        )
        + "</i>"
        for shard in range(len(fonts.names))
    )

    # Carry two FC results on each view timeline. The first glyph determines
    # the subject's position and the second determines its width. Absolute
    # cover/entry keyframes let one animation recover both progress values.
    if OUTPUTS_PER_CONSUMER % 2:
        raise ValueError("paired transport requires an even consumer width")
    pair_origin = -20_000
    pair_count = MLP_WIDTH // 2
    paired_timeline_names = [f"--pt{index}" for index in range(pair_count)]
    paired_cover_names = [f"--pc{index}" for index in range(pair_count)]
    paired_entry_names = [f"--pe{index}" for index in range(pair_count)]
    paired_keyframe_names = [f"pk{index}" for index in range(pair_count)]
    paired_timeline_rules = "".join(
        f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{"
        f"cover 0%{{{cover}:0;{entry}:0}}"
        f"entry 100%{{{entry}:1}}"
        f"cover 100%{{{cover}:1;{entry}:1}}}}"
        for cover, entry, keyframe in zip(
            paired_cover_names,
            paired_entry_names,
            paired_keyframe_names,
            strict=True,
        )
    )
    paired_declarations: list[str] = []
    for pair in range(pair_count):
        width_name = f"--pair-width-{pair:04d}"
        cover = paired_cover_names[pair]
        entry = paired_entry_names[pair]
        paired_declarations.append(
            f"{width_name}:calc(var({cover}) * {VIEWPORT} / "
            f"(var({entry}) - var({cover})))"
        )
        for within_pair in range(2):
            output = pair * 2 + within_pair
            raw_name = f"--raw-{output:03d}"
            pre_name = f"--pre-{output:03d}"
            factor = activation_range * q_fc.scales[output]
            if within_pair == 0:
                encoded = (
                    f"({VIEWPORT} - var({entry}) * var({width_name}) "
                    f"- ({pair_origin}))"
                )
            else:
                encoded = f"var({width_name})"
            paired_declarations.extend(
                (
                    f"{raw_name}:calc({encoded} * {UNITS_PER_EM} / "
                    f"{FONT_SIZE} - {base_total})",
                    f"{pre_name}:calc(var({raw_name}) * {css_number(factor)} "
                    f"+ ({css_number(data['fc_bias'][output])}))",
                    f"--hidden-{output:03d}:--gelu(var({pre_name}))",
                )
            )
    paired_animation_rules: list[str] = []
    paired_math_rules: list[str] = []
    declarations_per_pair = 7
    for consumer in range(consumer_count):
        output_start = consumer * OUTPUTS_PER_CONSUMER
        output_stop = min(output_start + OUTPUTS_PER_CONSUMER, MLP_WIDTH)
        pair_start = output_start // 2
        pair_stop = output_stop // 2
        paired_animation_rules.append(
            f".paired-result-{consumer}{{"
            f"animation-name:{','.join(paired_keyframe_names[pair_start:pair_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(paired_timeline_names[pair_start:pair_stop])}}}"
        )
        paired_math_rules.append(
            f".paired-result-{consumer}{{"
            + ";".join(
                paired_declarations[
                    pair_start * declarations_per_pair : pair_stop * declarations_per_pair
                ]
            )
            + "}"
        )
    range_pair_layout_css = (
        f".pair{{position:absolute;left:{pair_origin}px;top:0;display:inline-flex;height:1px}}"
        ".pair-subject{display:inline-block;width:max-content;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal}"
    )
    paired_glyphs: list[str] = []
    for pair, timeline in enumerate(paired_timeline_names):
        encoded: list[str] = []
        for output in (pair * 2, pair * 2 + 1):
            encoded.append(
                "".join(
                    f"&#x{start + output:X};" for start in fonts.codepoint_starts
                )
            )
        paired_glyphs.append(
            f'<span class="pair">{encoded[0]}'
            f'<i class="pair-subject" style="view-timeline:{timeline} inline">'
            f"{encoded[1]}</i></span>"
        )
    paired_shared_timeline_scroller = (
        '<div class="scroller"><div class="track">'
        + "".join(paired_glyphs)
        + "</div></div>"
    )

    # Quantize post-GELU values to eight bits and pack four FC outputs into
    # the two independent geometric degrees of one inline view timeline.
    # Each intrinsic glyph width is transformed and rounded before two base-512
    # digits are combined, so small transport error cannot carry into the high
    # digit. This is an inference approximation, not a precomputed activation.
    packed4_group_count = MLP_WIDTH // 4
    packed4_radix = 512
    packed4_center = 128
    packed4_hidden_min = -0.25
    packed4_hidden_max = 15.75
    packed4_hidden_span = packed4_hidden_max - packed4_hidden_min
    packed4_z_offset = 32
    packed4_viewport = 1_048_576
    packed4_extent_offset = 300_000
    packed4_left_base = packed4_viewport - packed4_extent_offset
    packed4_track_width = 1_600_000
    packed4_timeline_names = [
        f"--q4t{index}" for index in range(packed4_group_count)
    ]
    packed4_cover_names = [
        f"--q4c{index}" for index in range(packed4_group_count)
    ]
    packed4_entry_names = [
        f"--q4e{index}" for index in range(packed4_group_count)
    ]
    packed4_keyframes = [f"q4k{index}" for index in range(packed4_group_count)]
    packed4_importance = np.linalg.norm(q_mlp.reconstructed, axis=0)
    packed4_ranked_outputs = np.argsort(packed4_importance)
    packed4_low_outputs = packed4_ranked_outputs[: MLP_WIDTH // 2]
    packed4_high_outputs = packed4_ranked_outputs[MLP_WIDTH // 2 :]
    packed4_group_outputs: list[tuple[int, int, int, int]] = []
    for group in range(packed4_group_count):
        packed4_group_outputs.append(
            (
                int(packed4_low_outputs[group * 2]),
                int(packed4_high_outputs[group * 2]),
                int(packed4_low_outputs[group * 2 + 1]),
                int(packed4_high_outputs[group * 2 + 1]),
            )
        )
    packed4_multiplier_by_output = {
        output: (1 if slot % 2 == 0 else packed4_radix)
        for outputs in packed4_group_outputs
        for slot, output in enumerate(outputs)
    }
    packed4_location_by_output = {
        output: (group, slot)
        for group, outputs in enumerate(packed4_group_outputs)
        for slot, output in enumerate(outputs)
    }

    def packed4_hidden_expression(output: int) -> str:
        group, slot = packed4_location_by_output[output]
        packed = f"--q4l-{group:03d}" if slot < 2 else f"--q4p-{group:03d}"
        if slot % 2 == 0:
            digit = f"(mod(var({packed}),{packed4_radix}) - {packed4_center})"
            levels = 255
        else:
            digit = f"round(down,var({packed}) / {packed4_radix},1)"
            levels = 511
        return (
            f"calc(pow({digit} / {levels},2) * "
            f"{css_number(packed4_hidden_span)} + "
            f"({css_number(packed4_hidden_min)}))"
        )

    # Browser-equivalent reference for the packed timeline boundary. The two
    # high-importance digits receive nine bits; the other two receive eight.
    def quantize_packed4_hidden(values: np.ndarray) -> np.ndarray:
        result = np.empty_like(values)
        for output in range(MLP_WIDTH):
            levels = 255 if packed4_multiplier_by_output[output] == 1 else 511
            normalized_hidden = np.clip(
                (values[output] - packed4_hidden_min) / packed4_hidden_span,
                0,
                1,
            )
            code = math.floor(math.sqrt(normalized_hidden) * levels + 0.5)
            result[output] = (
                (code / levels) ** 2 * packed4_hidden_span
                + packed4_hidden_min
            )
        return result

    packed4_hidden = quantize_packed4_hidden(hidden)
    packed4_projected = (
        q_mlp.reconstructed @ packed4_hidden + data["mlp_proj_bias"]
    )
    packed4_final_output = residual + packed4_projected

    case_inputs = np.stack((data["x"], data["x"].copy()))
    case_inputs[1, :16] += np.linspace(-0.2, 0.2, 16)
    packed4_case_outputs = []
    dense_case_outputs = []
    packed4_case_residuals = []
    for case_input in case_inputs:
        case_n1 = layer_norm(
            case_input, data["ln1_gamma"], data["ln1_beta"]
        )
        case_attention = q_attention.reconstructed @ case_n1 + composed_bias
        case_residual = case_input + case_attention
        case_n2 = layer_norm(
            case_residual, data["ln2_gamma"], data["ln2_beta"]
        )
        case_pre = q_fc.reconstructed @ case_n2 + data["fc_bias"]
        dense_case_hidden = gelu_new(case_pre)
        case_hidden = quantize_packed4_hidden(dense_case_hidden)
        case_output = (
            case_residual
            + q_mlp.reconstructed @ case_hidden
            + data["mlp_proj_bias"]
        )
        packed4_case_residuals.append(case_residual)
        packed4_case_outputs.append(case_output)
        dense_case_outputs.append(
            case_residual
            + q_mlp.reconstructed @ dense_case_hidden
            + data["mlp_proj_bias"]
        )
    packed4_timeline_rules = "".join(
        f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{cover 0%{{{cover}:0;{entry}:0}}"
        f"entry 100%{{{entry}:1}}cover 100%{{{cover}:1;{entry}:1}}}}"
        for cover, entry, keyframe in zip(
            packed4_cover_names,
            packed4_entry_names,
            packed4_keyframes,
            strict=True,
        )
    )
    packed4_digit_rules: list[str] = []
    for output in range(MLP_WIDTH):
        factor = activation_range * q_fc.scales[output]
        multiplier = packed4_multiplier_by_output[output]
        levels = 255 if multiplier == 1 else 511
        digit_offset = packed4_center if multiplier == 1 else 0
        z = (
            f"((size / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total}) "
            f"* {css_number(factor)} + ({css_number(data['fc_bias'][output])}))"
        )
        z_basis = (
            f"calc-size(max-content,calc(({z} + {packed4_z_offset}) * 1px))"
        )
        u = f"(size / 1px - {packed4_z_offset})"
        t = (
            f"clamp(-20,({css_number(math.sqrt(2 / math.pi))} * "
            f"({u} + .044715 * pow({u},3))),20)"
        )
        inline_gelu = (
            f"(.5 * {u} * (1 + (exp(2 * {t}) - 1) / "
            f"(exp(2 * {t}) + 1)))"
        )
        packed4_digit_rules.append(
            f".q4d-{output:04d}{{width:calc-size({z_basis},calc((round(nearest,"
            f"sqrt((clamp({css_number(packed4_hidden_min)},{inline_gelu},"
            f"{css_number(packed4_hidden_max)}) - ({css_number(packed4_hidden_min)})) / "
            f"{css_number(packed4_hidden_span)}) * {levels},1) + {digit_offset}) * 1px * "
            f"{multiplier}))}}"
        )
    packed4_declarations: list[str] = []
    for group in range(packed4_group_count):
        cover = packed4_cover_names[group]
        entry = packed4_entry_names[group]
        width_name = f"--q4w-{group:03d}"
        left_pack = f"--q4l-{group:03d}"
        width_pack = f"--q4p-{group:03d}"
        packed4_declarations.extend(
            (
                f"{width_name}:calc(var({cover}) * {packed4_viewport} / "
                f"(var({entry}) - var({cover})))",
                f"{left_pack}:round(nearest,{packed4_viewport} - var({entry}) * "
                f"var({width_name}) - {packed4_left_base},1)",
                f"{width_pack}:round(nearest,var({width_name}) - "
                f"{packed4_extent_offset},1)",
            )
        )
    packed4_animation_rules: list[str] = []
    packed4_math_rules: list[str] = []
    packed4_groups_per_consumer = OUTPUTS_PER_CONSUMER // 4
    for consumer in range(consumer_count):
        group_start = consumer * packed4_groups_per_consumer
        group_stop = min(
            group_start + packed4_groups_per_consumer, packed4_group_count
        )
        packed4_animation_rules.append(
            f".q4-result-{consumer}{{animation-name:"
            f"{','.join(packed4_keyframes[group_start:group_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(packed4_timeline_names[group_start:group_stop])}}}"
        )
        declaration_start = group_start * 3
        declaration_stop = group_stop * 3
        packed4_math_rules.append(
            f".q4-result-{consumer}{{"
            + ";".join(packed4_declarations[declaration_start:declaration_stop])
            + "}"
        )
    packed4_groups: list[str] = []
    for group, timeline in enumerate(packed4_timeline_names):
        encoded: list[str] = []
        for output in packed4_group_outputs[group]:
            characters = "".join(
                f"&#x{start + output:X};" for start in fonts.codepoint_starts
            )
            encoded.append(
                f'<i class="q4-digit q4d-{output:04d}">{characters}</i>'
            )
        packed4_groups.append(
            '<span class="q4-pair"><span class="q4-lead">'
            + encoded[0]
            + encoded[1]
            + f'</span><span class="q4-subject" style="view-timeline:{timeline} inline">'
            + encoded[2]
            + encoded[3]
            + "</span></span>"
        )
    packed4_scroller = (
        '<div class="q4-scroller"><div class="q4-track">'
        + "".join(packed4_groups)
        + "</div></div>"
    )
    packed4_layout_css = (
        f".q4-scroller{{position:fixed;left:0;top:-25000px;width:{packed4_viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}"
        f".q4-track{{position:relative;width:{packed4_track_width}px;height:1px}}"
        f".q4-pair{{position:absolute;left:{packed4_left_base}px;top:0;"
        "display:inline-flex;height:1px}"
        ".q4-lead,.q4-subject{display:inline-flex;flex:none;height:1px;"
        "white-space:pre;font-style:normal}"
        f".q4-subject{{width:calc-size(max-content,size + {packed4_extent_offset}px)}}"
        ".q4-digit{display:inline-block;flex:none;height:1px;overflow:hidden;"
        "white-space:pre;font-style:normal}"
        + "".join(packed4_digit_rules)
    )

    # Six activations per timeline: three radix digits in the subject's
    # position and three in its width.  The default mixed scheme assigns
    # 4/5/7 bits by projection importance.  Uniform 6- and 7-bit schemes are
    # emitted on demand so browser geometry precision and model fidelity can
    # be measured independently from timeline count.
    packed6_group_size = 7 if PACKED6_SCHEME == "packed7-56" else 6
    packed6_left_size = 3
    packed6_group_count = math.ceil(MLP_WIDTH / packed6_group_size)
    if PACKED6_SCHEME == "mixed":
        packed6_multipliers = (16, 512, 16_384)
        packed6_levels = (15, 31, 127)
        packed6_digit_offsets = (8, 0, 0)
        packed6_middle_radix = 32
        packed6_viewport = 4_194_304
        packed6_extent_offset = 2_200_000
        packed6_track_width = 9_000_000
    elif PACKED6_SCHEME in {"uniform6", "uniform6asym", "logasym4"}:
        # Four-pixel guard protects the low digit while keeping the complete
        # 18-bit payload near one megapixel.
        packed6_multipliers = (4, 256, 16_384)
        packed6_levels = (63, 63, 63)
        packed6_digit_offsets = (0, 0, 0)
        packed6_middle_radix = 64
        packed6_viewport = 2_097_152
        packed6_extent_offset = 1_100_000
        packed6_track_width = 4_500_000
    elif PACKED6_SCHEME == "importance566":
        # Five guarded bits in the low place and six bits in each safer place.
        # Projection-column norms assign the least important third to the
        # guarded digit.
        packed6_multipliers = (8, 512, 32_768)
        packed6_levels = (31, 63, 63)
        packed6_digit_offsets = (0, 0, 0)
        packed6_middle_radix = 64
        packed6_viewport = 4_194_304
        packed6_extent_offset = 2_200_000
        packed6_track_width = 9_000_000
    elif PACKED6_SCHEME == "packed7-56":
        # Seven values share one timeline. Each side begins with a five-bit
        # digit; the remaining five values use six bits. Keeping the 23-bit
        # width payload unscaled avoids the severe reconstruction failure seen
        # when a two-pixel guard pushed it to ~16.7M CSS pixels.
        packed6_multipliers = (1, 32, 2_048, 131_072)
        packed6_levels = (31, 63, 63, 63)
        packed6_digit_offsets = (0, 0, 0, 0)
        packed6_middle_radix = 64
        # The viewport must be wider than the largest subject (extent plus
        # payload), otherwise entry/cover ranges overlap and cannot be inverted.
        packed6_viewport = 16_777_216
        packed6_extent_offset = 4_000_000
        packed6_track_width = 13_000_000
    else:
        # A full 21-bit packet cannot afford a guard without making layout
        # enormous.  This deliberately tests whether Chromium preserves its
        # unguarded low seven-bit digit.
        packed6_multipliers = (1, 128, 16_384)
        packed6_levels = (127, 127, 127)
        packed6_digit_offsets = (0, 0, 0)
        packed6_middle_radix = 128
        packed6_viewport = 4_194_304
        packed6_extent_offset = 2_200_000
        packed6_track_width = 9_000_000
    packed6_hidden_min = packed4_hidden_min
    packed6_hidden_max = packed4_hidden_max
    packed6_hidden_span = packed4_hidden_span
    packed6_transport_guard = (
        16_384 if PACKED6_SCHEME in {"uniform6asym", "logasym4"} else 0
    )
    if PACKED6_SCHEME in {"uniform6asym", "logasym4", "importance566"}:
        calibration_path = (
            OUT.parent / "packed-activation-precision" /
            "hidden-ranges-headroom2.json"
        )
        calibration = json.loads(calibration_path.read_text())["blocks"][0]
        calibration_factor = 0.55 if PACKED6_SCHEME == "importance566" else 1.0
        packed6_channel_min = np.maximum(
            np.asarray(calibration["minimum"], dtype=np.float64)
            * calibration_factor,
            -hidden_range,
        )
        packed6_channel_max = np.minimum(
            np.asarray(calibration["maximum"], dtype=np.float64)
            * calibration_factor,
            hidden_range,
        )
        packed6_channel_span = np.maximum(
            packed6_channel_max - packed6_channel_min, 1e-9
        )
        packed6_projection_activation_range = hidden_range
    else:
        packed6_channel_min = np.full(MLP_WIDTH, packed6_hidden_min)
        packed6_channel_max = np.full(MLP_WIDTH, packed6_hidden_max)
        packed6_channel_span = np.full(MLP_WIDTH, packed6_hidden_span)
        packed6_projection_activation_range = hidden_range
    packed6_z_offset = packed4_z_offset
    packed6_left_base = packed6_viewport - packed6_extent_offset
    packed6_timeline_names = [
        f"--q6t{index}" for index in range(packed6_group_count)
    ]
    packed6_cover_names = [
        f"--q6c{index}" for index in range(packed6_group_count)
    ]
    packed6_entry_names = [
        f"--q6e{index}" for index in range(packed6_group_count)
    ]
    packed6_keyframes = [f"q6k{index}" for index in range(packed6_group_count)]
    packed6_group_outputs: list[tuple[int, ...]] = []
    if PACKED6_SCHEME == "packed7-56":
        low_count = packed6_group_count * 2
        packed6_low_outputs = packed4_ranked_outputs[:low_count]
        packed6_high_outputs = packed4_ranked_outputs[low_count:]
        for group in range(packed6_group_count):
            low = packed6_low_outputs[group * 2 : group * 2 + 2]
            high = packed6_high_outputs[group * 5 : group * 5 + 5]
            outputs = (
                [int(low[0])]
                + [int(value) for value in high[:2]]
                + [int(low[1])]
                + [int(value) for value in high[2:]]
            )
            packed6_group_outputs.append(tuple(outputs))
    else:
        packed6_low_outputs = packed4_ranked_outputs[: MLP_WIDTH // 3]
        packed6_mid_outputs = packed4_ranked_outputs[
            MLP_WIDTH // 3 : 2 * MLP_WIDTH // 3
        ]
        packed6_high_outputs = packed4_ranked_outputs[2 * MLP_WIDTH // 3 :]
        for group in range(packed6_group_count):
            packed6_group_outputs.append(
                (
                    int(packed6_low_outputs[group * 2]),
                    int(packed6_mid_outputs[group * 2]),
                    int(packed6_high_outputs[group * 2]),
                    int(packed6_low_outputs[group * 2 + 1]),
                    int(packed6_mid_outputs[group * 2 + 1]),
                    int(packed6_high_outputs[group * 2 + 1]),
                )
            )
    packed6_multiplier_by_output = {
        output: packed6_multipliers[
            slot if slot < packed6_left_size else slot - packed6_left_size
        ]
        for outputs in packed6_group_outputs
        for slot, output in enumerate(outputs)
    }
    packed6_place_by_output = {
        output: slot if slot < packed6_left_size else slot - packed6_left_size
        for outputs in packed6_group_outputs
        for slot, output in enumerate(outputs)
    }
    packed6_location_by_output = {
        output: (group, slot)
        for group, outputs in enumerate(packed6_group_outputs)
        for slot, output in enumerate(outputs)
    }

    def packed6_hidden_expression(output: int) -> str:
        group, slot = packed6_location_by_output[output]
        is_left = slot < packed6_left_size
        packed = f"--q6l-{group:03d}" if is_left else f"--q6p-{group:03d}"
        place = slot if is_left else slot - packed6_left_size
        side_length = (
            min(packed6_left_size, len(packed6_group_outputs[group]))
            if is_left
            else len(packed6_group_outputs[group]) - packed6_left_size
        )
        if place == 0:
            digit = (
                f"(round(nearest,mod(var({packed}),{packed6_multipliers[1]}) / "
                f"{packed6_multipliers[0]},1) - {packed6_digit_offsets[0]})"
            )
        elif place == side_length - 1:
            digit = f"round(down,var({packed}) / {packed6_multipliers[place]},1)"
        else:
            digit = (
                f"mod(round(down,var({packed}) / {packed6_multipliers[place]},1),"
                f"{packed6_middle_radix})"
            )
        levels = packed6_levels[place]
        if PACKED6_SCHEME in {"uniform6asym", "logasym4", "importance566"}:
            normalized = (
                f"({digit} / {levels})"
                if PACKED6_SCHEME != "logasym4"
                else (
                    f"((exp({digit} / {levels} * {css_number(math.log(5))}) "
                    f"- 1) / 4)"
                )
            )
            return (
                f"calc({normalized} * "
                f"{css_number(packed6_channel_span[output])} + "
                f"({css_number(packed6_channel_min[output])}))"
            )
        return (
            f"calc(pow({digit} / {levels},2) * "
            f"{css_number(packed6_hidden_span)} + "
            f"({css_number(packed6_hidden_min)}))"
        )

    packed6_timeline_rules = "".join(
        f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{cover 0%{{{cover}:0;{entry}:0}}"
        f"entry 100%{{{entry}:1}}cover 100%{{{cover}:1;{entry}:1}}}}"
        for cover, entry, keyframe in zip(
            packed6_cover_names,
            packed6_entry_names,
            packed6_keyframes,
            strict=True,
        )
    )
    packed6_digit_rules: list[str] = []
    for output in range(MLP_WIDTH):
        factor = activation_range * q_fc.scales[output]
        multiplier = packed6_multiplier_by_output[output]
        place = packed6_place_by_output[output]
        levels = packed6_levels[place]
        digit_offset = packed6_digit_offsets[place]
        z = (
            f"((size / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total}) "
            f"* {css_number(factor)} + ({css_number(data['fc_bias'][output])}))"
        )
        z_basis = f"calc-size(max-content,calc(({z} + {packed6_z_offset}) * 1px))"
        u = f"(size / 1px - {packed6_z_offset})"
        t = (
            f"clamp(-20,({css_number(math.sqrt(2 / math.pi))} * "
            f"({u} + .044715 * pow({u},3))),20)"
        )
        inline_gelu = (
            f"(.5 * {u} * (1 + (exp(2 * {t}) - 1) / "
            f"(exp(2 * {t}) + 1)))"
        )
        if PACKED6_SCHEME in {"uniform6asym", "logasym4", "importance566"}:
            linear_encoded = (
                f"(clamp({css_number(packed6_channel_min[output])},{inline_gelu},"
                f"{css_number(packed6_channel_max[output])}) - "
                f"({css_number(packed6_channel_min[output])})) / "
                f"{css_number(packed6_channel_span[output])}"
            )
            encoded = (
                linear_encoded
                if PACKED6_SCHEME != "logasym4"
                else (
                    f"log(1 + 4 * ({linear_encoded})) / "
                    f"{css_number(math.log(5))}"
                )
            )
        else:
            encoded = (
                f"sqrt((clamp({css_number(packed6_hidden_min)},{inline_gelu},"
                f"{css_number(packed6_hidden_max)}) - "
                f"({css_number(packed6_hidden_min)})) / "
                f"{css_number(packed6_hidden_span)})"
            )
        packed6_digit_rules.append(
            f".q6d-{output:04d}{{width:calc-size({z_basis},calc((round(nearest,"
            f"{encoded} * {levels},1) + {digit_offset}) * "
            f"1px * {multiplier}))}}"
        )
    packed6_declarations: list[str] = []
    for group in range(packed6_group_count):
        cover = packed6_cover_names[group]
        entry = packed6_entry_names[group]
        width_name = f"--q6w-{group:03d}"
        left_pack = f"--q6l-{group:03d}"
        width_pack = f"--q6p-{group:03d}"
        packed6_declarations.extend(
            (
                f"{width_name}:calc(var({cover}) * {packed6_viewport} / "
                f"(var({entry}) - var({cover})))",
                f"{left_pack}:round(nearest,{packed6_viewport} - var({entry}) * "
                f"var({width_name}) - {packed6_left_base} - "
                f"{packed6_transport_guard},1)",
                f"{width_pack}:round(nearest,var({width_name}) - "
                f"{packed6_extent_offset} - {packed6_transport_guard},1)",
            )
        )
    packed6_groups_per_consumer = OUTPUTS_PER_CONSUMER // packed6_group_size
    packed6_consumer_count = math.ceil(
        packed6_group_count / packed6_groups_per_consumer
    )
    packed6_animation_rules: list[str] = []
    packed6_math_rules: list[str] = []
    for consumer in range(packed6_consumer_count):
        group_start = consumer * packed6_groups_per_consumer
        group_stop = min(
            group_start + packed6_groups_per_consumer, packed6_group_count
        )
        packed6_animation_rules.append(
            f".q6-result-{consumer}{{animation-name:"
            f"{','.join(packed6_keyframes[group_start:group_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(packed6_timeline_names[group_start:group_stop])}}}"
        )
        packed6_math_rules.append(
            f".q6-result-{consumer}{{"
            + ";".join(packed6_declarations[group_start * 3 : group_stop * 3])
            + "}"
        )
    packed6_groups: list[str] = []
    for group, timeline in enumerate(packed6_timeline_names):
        encoded: list[str] = []
        for output in packed6_group_outputs[group]:
            characters = "".join(
                f"&#x{start + output:X};" for start in fonts.codepoint_starts
            )
            encoded.append(
                f'<i class="q6-digit q6d-{output:04d}">{characters}</i>'
            )
        packed6_groups.append(
            '<span class="q6-pair"><span class="q6-lead">'
            + "".join(encoded[:packed6_left_size])
            + f'</span><span class="q6-subject" style="view-timeline:{timeline} inline">'
            + "".join(encoded[packed6_left_size:])
            + "</span></span>"
        )
    packed6_scroller = (
        '<div class="q6-scroller"><div class="q6-track">'
        + "".join(packed6_groups)
        + "</div></div>"
    )
    packed6_layout_css = (
        f".q6-scroller{{position:fixed;left:0;top:-26000px;width:{packed6_viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}"
        f".q6-track{{position:relative;width:{packed6_track_width}px;height:1px}}"
        f".q6-pair{{position:absolute;left:{packed6_left_base}px;top:0;"
        "display:inline-flex;height:1px}"
        ".q6-lead,.q6-subject{display:inline-flex;flex:none;height:1px;"
        "white-space:pre;font-style:normal}"
        f".q6-lead{{padding-left:{packed6_transport_guard}px}}"
        f".q6-subject{{width:calc-size(max-content,size + "
        f"{packed6_extent_offset + packed6_transport_guard}px)}}"
        ".q6-digit{display:inline-block;flex:none;height:1px;overflow:hidden;"
        "white-space:pre;font-style:normal}"
        + "".join(packed6_digit_rules)
    )

    # Heterogeneous 5/8-bit transport. The lower half of projection-column
    # importance uses six five-bit values per timeline; the upper half uses
    # four eight-bit values per timeline. Both packets stay below 18 bits per
    # geometric coordinate and guard their low digit with four-pixel spacing.
    hetero_calibration = json.loads(
        (
            OUT.parent / "packed-activation-precision" /
            "hidden-ranges-headroom2.json"
        ).read_text()
    )["blocks"][0]
    hetero_min = np.maximum(
        np.asarray(hetero_calibration["minimum"], dtype=np.float64) * 0.75,
        -hidden_range,
    )
    hetero_max = np.minimum(
        np.asarray(hetero_calibration["maximum"], dtype=np.float64) * 0.75,
        hidden_range,
    )
    hetero_span = np.maximum(hetero_max - hetero_min, 1e-9)

    def build_hetero_bank(
        prefix: str,
        selected_outputs: np.ndarray,
        channel_min: np.ndarray,
        channel_max: np.ndarray,
        group_size: int,
        bits: int,
        guard: int,
        viewport: int,
        extent: int,
        track_width: int,
        top: int,
    ) -> dict[str, object]:
        if group_size % 2 or len(selected_outputs) % group_size:
            raise ValueError("heterogeneous packet groups must divide evenly")
        side_size = group_size // 2
        radix = 1 << bits
        levels = radix - 1
        channel_span = np.maximum(channel_max - channel_min, 1e-9)
        multipliers = tuple(guard * radix**place for place in range(side_size))
        groups = [
            tuple(
                int(value)
                for value in selected_outputs[
                    group * group_size : (group + 1) * group_size
                ]
            )
            for group in range(len(selected_outputs) // group_size)
        ]
        locations = {
            output: (group, slot)
            for group, outputs in enumerate(groups)
            for slot, output in enumerate(outputs)
        }
        timeline_names = [f"--{prefix}t{index}" for index in range(len(groups))]
        cover_names = [f"--{prefix}c{index}" for index in range(len(groups))]
        entry_names = [f"--{prefix}e{index}" for index in range(len(groups))]
        keyframes = [f"{prefix}k{index}" for index in range(len(groups))]
        timeline_rules = "".join(
            f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f"@keyframes {keyframe}{{cover 0%{{{cover}:0;{entry}:0}}"
            f"entry 100%{{{entry}:1}}cover 100%{{{cover}:1;{entry}:1}}}}"
            for cover, entry, keyframe in zip(
                cover_names, entry_names, keyframes, strict=True
            )
        )

        def hidden_expression(output: int) -> str:
            group, slot = locations[output]
            packed = (
                f"--{prefix}l-{group:03d}"
                if slot < side_size
                else f"--{prefix}p-{group:03d}"
            )
            place = slot % side_size
            if place == 0:
                digit = (
                    f"round(nearest,mod(var({packed}),{multipliers[1]}) / "
                    f"{multipliers[0]},1)"
                )
            elif place == side_size - 1:
                digit = f"round(down,var({packed}) / {multipliers[place]},1)"
            else:
                digit = (
                    f"mod(round(down,var({packed}) / {multipliers[place]},1),"
                    f"{radix})"
                )
            return (
                f"calc({digit} / {levels} * {css_number(channel_span[output])} + "
                f"({css_number(channel_min[output])}))"
            )

        digit_rules: list[str] = []
        for output in selected_outputs:
            output = int(output)
            _, slot = locations[output]
            multiplier = multipliers[slot % side_size]
            factor = activation_range * q_fc.scales[output]
            z = (
                f"((size / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total}) "
                f"* {css_number(factor)} + ({css_number(data['fc_bias'][output])}))"
            )
            z_basis = f"calc-size(max-content,calc(({z} + 32) * 1px))"
            u = "(size / 1px - 32)"
            t = (
                f"clamp(-20,({css_number(math.sqrt(2 / math.pi))} * "
                f"({u} + .044715 * pow({u},3))),20)"
            )
            inline_gelu = (
                f"(.5 * {u} * (1 + (exp(2 * {t}) - 1) / "
                f"(exp(2 * {t}) + 1)))"
            )
            encoded = (
                f"(clamp({css_number(channel_min[output])},{inline_gelu},"
                f"{css_number(channel_max[output])}) - "
                f"({css_number(channel_min[output])})) / "
                f"{css_number(channel_span[output])}"
            )
            digit_rules.append(
                f".{prefix}d-{output:04d}{{width:calc-size({z_basis},calc("
                f"round(nearest,{encoded} * {levels},1) * 1px * {multiplier}))}}"
            )

        left_base = viewport - extent
        declarations: list[str] = []
        for group in range(len(groups)):
            cover = cover_names[group]
            entry = entry_names[group]
            width_name = f"--{prefix}w-{group:03d}"
            left_pack = f"--{prefix}l-{group:03d}"
            width_pack = f"--{prefix}p-{group:03d}"
            declarations.extend((
                f"{width_name}:calc(var({cover}) * {viewport} / "
                f"(var({entry}) - var({cover})))",
                f"{left_pack}:round(nearest,{viewport} - var({entry}) * "
                f"var({width_name}) - {left_base},1)",
                f"{width_pack}:round(nearest,var({width_name}) - {extent},1)",
            ))
        groups_per_consumer = max(1, OUTPUTS_PER_CONSUMER // group_size)
        consumer_count = math.ceil(len(groups) / groups_per_consumer)
        animation_rules: list[str] = []
        math_rules: list[str] = []
        for consumer in range(consumer_count):
            start = consumer * groups_per_consumer
            stop = min(start + groups_per_consumer, len(groups))
            animation_rules.append(
                f".{prefix}-result-{consumer}{{animation-name:"
                f"{','.join(keyframes[start:stop])};animation-duration:1s;"
                "animation-timing-function:linear;animation-fill-mode:both;"
                f"animation-timeline:{','.join(timeline_names[start:stop])}}}"
            )
            math_rules.append(
                f".{prefix}-result-{consumer}{{"
                + ";".join(declarations[start * 3 : stop * 3])
                + "}"
            )
        group_html: list[str] = []
        for group, timeline in enumerate(timeline_names):
            digits = []
            for output in groups[group]:
                characters = "".join(
                    f"&#x{start + output:X};" for start in fonts.codepoint_starts
                )
                digits.append(
                    f'<i class="{prefix}-digit {prefix}d-{output:04d}">'
                    f"{characters}</i>"
                )
            group_html.append(
                f'<span class="{prefix}-pair"><span class="{prefix}-lead">'
                + "".join(digits[:side_size])
                + f'</span><span class="{prefix}-subject" '
                f'style="view-timeline:{timeline} inline">'
                + "".join(digits[side_size:])
                + "</span></span>"
            )
        scroller = (
            f'<div class="{prefix}-scroller"><div class="{prefix}-track">'
            + "".join(group_html)
            + "</div></div>"
        )
        layout_css = (
            f".{prefix}-scroller{{position:fixed;left:0;top:{top}px;width:{viewport}px;"
            "height:1px;overflow-x:scroll;overflow-y:hidden}"
            f".{prefix}-track{{position:relative;width:{track_width}px;height:1px}}"
            f".{prefix}-pair{{position:absolute;left:{left_base}px;top:0;"
            "display:inline-flex;height:1px}"
            f".{prefix}-lead,.{prefix}-subject{{display:inline-flex;flex:none;"
            "height:1px;white-space:pre;font-style:normal}"
            f".{prefix}-subject{{width:calc-size(max-content,size + {extent}px)}}"
            f".{prefix}-digit{{display:inline-block;flex:none;height:1px;"
            "overflow:hidden;white-space:pre;font-style:normal}"
            + "".join(digit_rules)
        )
        return {
            "timelines": timeline_names,
            "timeline_rules": timeline_rules,
            "animation_rules": animation_rules,
            "math_rules": math_rules,
            "consumer_count": consumer_count,
            "scroller": scroller,
            "layout_css": layout_css,
            "hidden_expression": hidden_expression,
            "groups": groups,
        }

    hetero_low_outputs = packed4_ranked_outputs[: MLP_WIDTH // 2]
    hetero_high_outputs = packed4_ranked_outputs[MLP_WIDTH // 2 :]
    hetero_low = build_hetero_bank(
        "h5", hetero_low_outputs, hetero_min, hetero_max,
        6, 5, 4, 524_288, 150_000, 800_000, -27_000
    )
    hetero_high = build_hetero_bank(
        "h8", hetero_high_outputs, hetero_min, hetero_max,
        4, 8, 4, 1_048_576, 300_000,
        1_700_000, -28_000,
    )
    hetero_hidden_expression_by_output = {
        int(output): hetero_low["hidden_expression"](int(output))
        for output in hetero_low_outputs
    }
    hetero_hidden_expression_by_output.update({
        int(output): hetero_high["hidden_expression"](int(output))
        for output in hetero_high_outputs
    })

    sensitivity_min = np.maximum(
        np.asarray(hetero_calibration["minimum"], dtype=np.float64) * 0.55,
        -hidden_range,
    )
    sensitivity_max = np.minimum(
        np.asarray(hetero_calibration["maximum"], dtype=np.float64) * 0.55,
        hidden_range,
    )
    sensitivity_span = np.maximum(sensitivity_max - sensitivity_min, 1e-9)
    sensitivity_importance = packed4_importance * sensitivity_span
    sensitivity_ranked = np.argsort(sensitivity_importance)
    sensitivity_quarters = np.array_split(sensitivity_ranked, 4)
    sensitivity_banks = (
        ("s3", build_hetero_bank(
            "s3", sensitivity_quarters[0], sensitivity_min, sensitivity_max,
            12, 3, 4, 2_097_152, 1_100_000, 4_500_000, -29_000,
        )),
        ("s4", build_hetero_bank(
            "s4", sensitivity_quarters[1], sensitivity_min, sensitivity_max,
            8, 4, 4, 1_048_576, 550_000, 2_300_000, -30_000,
        )),
        ("s5", build_hetero_bank(
            "s5", sensitivity_quarters[2], sensitivity_min, sensitivity_max,
            6, 5, 4, 524_288, 270_000, 1_200_000, -31_000,
        )),
        ("s6", build_hetero_bank(
            "s6", sensitivity_quarters[3], sensitivity_min, sensitivity_max,
            6, 6, 4, 2_097_152, 1_100_000, 4_500_000, -32_000,
        )),
    )
    sensitivity_hidden_expression_by_output = {
        int(output): bank["hidden_expression"](int(output))
        for _, bank in sensitivity_banks
        for outputs in bank["groups"]
        for output in outputs
    }
    plain_scrollers = "".join(
        f'<div class="scroller"><div class="track">{glyph}</div></div>'
        for glyph in glyphs_without_timelines
    )
    result_tree = (
        f'<output id="fc-result" class="result-{consumer_count - 1}"></output>'
    )
    for consumer in reversed(range(consumer_count - 1)):
        result_tree = f'<div class="result-{consumer}">{result_tree}</div>'

    HTML_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Flat view-timeline GPT-2 FC layer</title>'
        f'<link rel="stylesheet" href="view-timeline-fc.css?v={css_tag}">'
        '<h1>Flat 768→3,072 GPT-2 FC + GELU in HTML/CSS</h1>'
        '<p>No JavaScript. Flat HVAR readback with 128 outputs per consumer.</p>'
        '<div class="scope">'
        + timeline_scrollers
        + result_tree
        + "</div>"
    )

    shared_html_path = OUT / "view-timeline-fc-shared-scroller.html"
    shared_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Shared-scroller view-timeline GPT-2 FC</title>'
        f'<link rel="stylesheet" href="view-timeline-fc.css?v={css_tag}">'
        '<h1>Shared-scroller 768→3,072 GPT-2 FC + GELU</h1>'
        '<p>No JavaScript. All named timeline subjects share one scroll container.</p>'
        '<div class="scope">'
        + shared_timeline_scroller
        + result_tree
        + "</div>"
    )

    variant_specs = (
        (
            "view-timeline-fc-font-only",
            faces + scope_without_timelines + layout_css + visible_css,
            plain_scrollers,
            False,
        ),
        (
            "view-timeline-fc-timeline-only",
            faces
            + timeline_rules
            + scope_with_timelines
            + layout_css
            + animation_css
            + visible_css,
            timeline_scrollers,
            True,
        ),
    )
    for stem, variant_css, variant_scrollers, include_result in variant_specs:
        css_path = OUT / f"{stem}.css"
        html_path = OUT / f"{stem}.html"
        css_path.write_text(variant_css)
        tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
        html_path.write_text(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f'<title>{stem}</title><link rel="stylesheet" href="{stem}.css?v={tag}">'
            f'<div class="scope">'
            + variant_scrollers
            + (result_tree if include_result else "")
            + "</div>"
        )

    three_run_css_path = OUT / "view-timeline-fc-font-three-runs.css"
    three_run_html_path = OUT / "view-timeline-fc-font-three-runs.html"
    three_run_css_path.write_text(
        faces
        + scope_without_timelines
        + ".scope{position:fixed;left:0;top:-10000px;width:1000000px}"
        + ".font-run{display:block;width:1000000px;white-space:normal;"
        "word-break:break-all;font-style:normal;line-height:1}"
        + "".join(
            f".font-run-{shard}{{font-family:fcS{shard}}}"
            for shard in range(len(fonts.names))
        )
        + visible_css
    )
    three_run_tag = hashlib.sha256(
        three_run_css_path.read_bytes()
    ).hexdigest()[:12]
    three_run_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>GPT-2 FC HVAR shaping in three text runs</title>'
        f'<link rel="stylesheet" href="{three_run_css_path.name}?v={three_run_tag}">'
        f'<div class="scope">{three_run_html}</div>'
    )

    shared_font_css_path = OUT / "view-timeline-fc-font-shared-spans.css"
    shared_font_html_path = OUT / "view-timeline-fc-font-shared-spans.html"
    shared_font_css_path.write_text(
        faces + scope_without_timelines + layout_css + visible_css
    )
    shared_font_tag = hashlib.sha256(
        shared_font_css_path.read_bytes()
    ).hexdigest()[:12]
    shared_font_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>GPT-2 FC HVAR shaping in shared output spans</title>'
        f'<link rel="stylesheet" href="{shared_font_css_path.name}?v={shared_font_tag}">'
        '<div class="scope"><div class="scroller"><div class="track">'
        + "".join(glyphs_without_timelines)
        + "</div></div></div>"
    )

    anchor_css_path = OUT / "view-timeline-fc-anchor.css"
    anchor_html_path = OUT / "view-timeline-fc-anchor.html"
    anchor_layout_css = (
        ".scroller{position:fixed;left:0;top:-10000px;"
        f"width:{VIEWPORT}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".track{{position:relative;width:{TRACK_WIDTH}px;height:1px}}"
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre}"
        + ".subject{position:absolute;left:0;top:0;height:1px}"
    )
    anchor_css_path.write_text(
        faces
        + timeline_rules
        + hidden_registrations
        + gelu_function
        + scope_with_timelines
        + anchor_layout_css
        + animation_css
        + result_math_css
        + visible_css
    )
    anchor_tag = hashlib.sha256(anchor_css_path.read_bytes()).hexdigest()[:12]
    anchor_scrollers: list[str] = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        anchor = f"--m{output}"
        anchor_scrollers.append(
            '<div class="scroller"><div class="track">'
            f'<i class="metric" style="anchor-name:{anchor}">{characters}</i>'
            f'<i class="subject" style="position-anchor:{anchor};'
            f'width:anchor-size({anchor} width);view-timeline:{timeline_names[output]} inline"></i>'
            "</div></div>"
        )
    anchor_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Anchor-decoupled view-timeline GPT-2 FC</title>'
        f'<link rel="stylesheet" href="view-timeline-fc-anchor.css?v={anchor_tag}">'
        '<div class="scope">'
        + "".join(anchor_scrollers)
        + result_tree
        + "</div>"
    )

    paired_css_path = OUT / "view-timeline-fc-2d.css"
    paired_html_path = OUT / "view-timeline-fc-2d.html"
    paired_layout_css = (
        ".pair-scroller{position:fixed;left:0;top:-30000px;"
        f"width:{VIEWPORT}px;height:{VIEWPORT}px;overflow:scroll}}"
        f".pair-track{{position:relative;width:{TRACK_WIDTH}px;height:{TRACK_WIDTH}px}}"
        ".pair-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        ".pair-subject{position:absolute;left:0;top:0;display:block}"
    )
    paired_css_path.write_text(
        faces
        + timeline_rules
        + hidden_registrations
        + gelu_function
        + scope_with_timelines
        + paired_layout_css
        + animation_css
        + result_math_css
        + visible_css
    )
    paired_tag = hashlib.sha256(paired_css_path.read_bytes()).hexdigest()[:12]
    paired_scrollers: list[str] = []
    for first_output in range(0, MLP_WIDTH, 2):
        second_output = first_output + 1
        first_characters = "".join(
            f"&#x{start + first_output:X};" for start in fonts.codepoint_starts
        )
        second_characters = "".join(
            f"&#x{start + second_output:X};" for start in fonts.codepoint_starts
        )
        first_anchor = f"--pm{first_output}"
        second_anchor = f"--pm{second_output}"
        paired_scrollers.append(
            '<div class="pair-scroller"><div class="pair-track">'
            f'<i class="pair-metric" style="anchor-name:{first_anchor}">'
            f"{first_characters}</i>"
            f'<i class="pair-metric" style="anchor-name:{second_anchor}">'
            f"{second_characters}</i>"
            f'<i class="pair-subject" style="width:anchor-size({first_anchor} width);'
            f"height:anchor-size({second_anchor} width);"
            f"view-timeline-name:{timeline_names[first_output]},"
            f"{timeline_names[second_output]};"
            'view-timeline-axis:inline,block"></i>'
            "</div></div>"
        )
    paired_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Two-axis view-timeline GPT-2 FC</title>'
        f'<link rel="stylesheet" href="view-timeline-fc-2d.css?v={paired_tag}">'
        '<h1>Two outputs per scroller: GPT-2 FC + GELU</h1>'
        '<p>No JavaScript. Width and height carry independent outputs.</p>'
        '<div class="scope">'
        + "".join(paired_scrollers)
        + result_tree
        + "</div>"
    )
    paired_shared_html_path = OUT / "view-timeline-fc-2d-shared.html"
    pair_prefix = '<div class="pair-scroller"><div class="pair-track">'
    pair_suffix = "</div></div>"
    paired_shared_contents = "".join(
        scroller.removeprefix(pair_prefix).removesuffix(pair_suffix)
        for scroller in paired_scrollers
    )
    paired_shared_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Shared two-axis view-timeline GPT-2 FC</title>'
        f'<link rel="stylesheet" href="view-timeline-fc-2d.css?v={paired_tag}">'
        '<h1>Shared two-axis GPT-2 FC + GELU</h1>'
        '<p>No JavaScript. One scroller, two outputs per subject.</p>'
        '<div class="scope"><div class="pair-scroller"><div class="pair-track">'
        + paired_shared_contents
        + "</div></div>"
        + result_tree
        + "</div>"
    )

    REFERENCE_PATH.write_text(
        json.dumps(
            {
                "width": WIDTH,
                "output_width": MLP_WIDTH,
                "font_size": FONT_SIZE,
                "viewport": VIEWPORT,
                "base_total": base_total,
                "activation_range": activation_range,
                "outputs_per_consumer": OUTPUTS_PER_CONSUMER,
                "layout_strategy": "flat-named-view-timelines",
                "raw": raw.tolist(),
                "pre": pre.tolist(),
                "hidden": hidden.tolist(),
                "html_bytes": HTML_PATH.stat().st_size,
                "css_bytes": CSS_PATH.stat().st_size,
                "font_bytes": sum((OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
            },
            indent=2,
        )
        + "\n"
    )

    # Chain the browser-computed FC activations directly into the real GPT-2
    # 3,072→768 projection. Each projection glyph reads --hidden-* from the
    # FC result ancestors; no precomputed hidden value is placed in this page.
    if mlp_fonts.row_bases is None:
        raise ValueError("projection fonts require per-output base advances")
    projection_base_total = sum(mlp_fonts.bases)
    projection_pack_count = math.ceil(len(mlp_fonts.names) / 3)
    if projection_pack_count % PROJECTION_METRICS_PER_OUTPUT:
        raise ValueError("projection metric count must divide the four font packs")
    packs_per_metric = projection_pack_count // PROJECTION_METRICS_PER_OUTPUT
    projection_metric_bases = [
        np.sum(
            np.stack(
                mlp_fonts.row_bases[
                    pack * 3 : min(
                        (pack + packs_per_metric) * 3, len(mlp_fonts.names)
                    )
                ]
            ),
            axis=0,
        )
        for pack in range(0, projection_pack_count, packs_per_metric)
    ]
    projection_base_pixels = max(
        int(np.max(bases)) for bases in projection_metric_bases
    ) * FONT_SIZE / UNITS_PER_EM
    projection_viewport = 2 ** math.ceil(
        math.log2(max(1024, projection_base_pixels * 1.25))
    )
    projection_track_width = projection_viewport * 3
    projection_timeline_count = WIDTH * PROJECTION_METRICS_PER_OUTPUT
    projection_timeline_names = [
        f"--ot{index}" for index in range(projection_timeline_count)
    ]
    projection_progress_names = [
        f"--op{index}" for index in range(projection_timeline_count)
    ]
    projection_keyframe_names = [
        f"ok{index}" for index in range(projection_timeline_count)
    ]
    projection_timeline_rules = "".join(
        f'@property {progress}'
        '{syntax:"<number>";inherits:true;initial-value:-1}'
        f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for progress, keyframe in zip(
            projection_progress_names, projection_keyframe_names, strict=True
        )
    )
    output_registrations = "".join(
        f'@property --out-{index:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(WIDTH)
    )
    projection_pack_rules: list[str] = []
    hidden_names = [f"--hidden-{index:03d}" for index in range(MLP_WIDTH)]
    for pack, first_shard in enumerate(
        range(0, len(mlp_fonts.names), 3)
    ):
        families = ",".join(
            f"mlpflatS{shard}"
            for shard in range(first_shard, min(first_shard + 3, len(mlp_fonts.names)))
        )
        projection_pack_rules.append(
            f".proj-pack-{pack}{{font-family:{families};"
            f"font-variation-settings:"
            f"{pack_font_settings(hidden_names, hidden_range, first_shard)}}}"
        )
    packed4_projection_pack_rules: list[str] = []
    shard_width = q_mlp.codes.shape[1] // len(mlp_fonts.names)
    for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
        settings = pack_font_settings(hidden_names, hidden_range, first_shard)
        start = first_shard * shard_width
        stop = min((first_shard + 3) * shard_width, MLP_WIDTH)
        for output in range(start, stop):
            settings = settings.replace(
                f"var(--hidden-{output:03d})",
                packed4_hidden_expression(output),
            )
        packed4_projection_pack_rules.append(
            f".proj-pack-{pack}{{font-variation-settings:{settings}}}"
        )
    packed6_projection_pack_rules: list[str] = []
    for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
        settings = pack_font_settings(
            hidden_names, packed6_projection_activation_range, first_shard
        )
        start = first_shard * shard_width
        stop = min((first_shard + 3) * shard_width, MLP_WIDTH)
        for output in range(start, stop):
            settings = settings.replace(
                f"var(--hidden-{output:03d})",
                packed6_hidden_expression(output),
            )
        packed6_projection_pack_rules.append(
            f".proj-pack-{pack}{{font-variation-settings:{settings}}}"
        )
    hetero_projection_pack_rules: list[str] = []
    for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
        settings = pack_font_settings(hidden_names, hidden_range, first_shard)
        start = first_shard * shard_width
        stop = min((first_shard + 3) * shard_width, MLP_WIDTH)
        for output in range(start, stop):
            settings = settings.replace(
                f"var(--hidden-{output:03d})",
                hetero_hidden_expression_by_output[output],
            )
        hetero_projection_pack_rules.append(
            f".proj-pack-{pack}{{font-variation-settings:{settings}}}"
        )
    sensitivity_projection_pack_rules: list[str] = []
    for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
        settings = pack_font_settings(hidden_names, hidden_range, first_shard)
        start = first_shard * shard_width
        stop = min((first_shard + 3) * shard_width, MLP_WIDTH)
        for output in range(start, stop):
            settings = settings.replace(
                f"var(--hidden-{output:03d})",
                sensitivity_hidden_expression_by_output[output],
            )
        sensitivity_projection_pack_rules.append(
            f".proj-pack-{pack}{{font-variation-settings:{settings}}}"
        )
    projection_layout_css = (
        f'.projection-stage{{timeline-scope:{",".join(projection_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal}}"
        ".proj-scroller{position:fixed;left:0;top:-20000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".proj-track{{position:relative;width:{projection_track_width}px;height:1px}}"
        ".proj-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + "".join(projection_pack_rules)
    )
    def make_projection_declarations(activation_scale: float) -> list[str]:
        declarations: list[str] = []
        for index in range(WIDTH):
            raw_name = f"--proj-raw-{index:03d}"
            factor = activation_scale * q_mlp.scales[index]
            raw_parts = []
            for metric in range(PROJECTION_METRICS_PER_OUTPUT):
                progress = projection_progress_names[
                    index * PROJECTION_METRICS_PER_OUTPUT + metric
                ]
                raw_parts.append(
                    f"(({projection_viewport} / var({progress}) - "
                    f"{projection_viewport}) * {UNITS_PER_EM} / {FONT_SIZE} - "
                    f"{int(projection_metric_bases[metric][index])})"
                )
            declarations.append(f"{raw_name}:calc({'+'.join(raw_parts)})")
            declarations.append(
                f"--out-{index:03d}:calc(var(--r1-{index:03d}) + "
                f"var({raw_name}) * {css_number(factor)} + "
                f"({css_number(data['mlp_proj_bias'][index])}))"
            )
        return declarations

    projection_declarations = make_projection_declarations(hidden_range)
    packed6_projection_declarations = make_projection_declarations(
        packed6_projection_activation_range
    )
    projection_animation_rules: list[str] = []
    projection_math_rules: list[str] = []
    packed6_projection_math_rules: list[str] = []
    projection_outputs_per_consumer = max(
        1, OUTPUTS_PER_CONSUMER // PROJECTION_METRICS_PER_OUTPUT
    )
    projection_consumer_count = math.ceil(
        WIDTH / projection_outputs_per_consumer
    )
    for consumer in range(projection_consumer_count):
        start = consumer * projection_outputs_per_consumer
        stop = min(start + projection_outputs_per_consumer, WIDTH)
        timeline_start = start * PROJECTION_METRICS_PER_OUTPUT
        timeline_stop = stop * PROJECTION_METRICS_PER_OUTPUT
        projection_animation_rules.append(
            f".proj-result-{consumer}{{"
            f"animation-name:{','.join(projection_keyframe_names[timeline_start:timeline_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(projection_timeline_names[timeline_start:timeline_stop])};"
            "animation-range:cover}"
        )
        projection_math_rules.append(
            f".proj-result-{consumer}{{"
            + ";".join(projection_declarations[start * 2 : stop * 2])
            + "}"
        )
        packed6_projection_math_rules.append(
            f".proj-result-{consumer}{{"
            + ";".join(
                packed6_projection_declarations[start * 2 : stop * 2]
            )
            + "}"
        )

    projection_scrollers: list[str] = []
    for output_index in range(WIDTH):
        packs: list[str] = []
        for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
            characters = "".join(
                f"&#x{mlp_fonts.codepoint_starts[shard] + output_index:X};"
                for shard in range(
                    first_shard, min(first_shard + 3, len(mlp_fonts.names))
                )
            )
            packs.append(f'<i class="proj-pack-{pack}">{characters}</i>')
        for metric_index in range(PROJECTION_METRICS_PER_OUTPUT):
            timeline_index = (
                output_index * PROJECTION_METRICS_PER_OUTPUT + metric_index
            )
            pack_start = metric_index * packs_per_metric
            pack_stop = pack_start + packs_per_metric
            metric = (
                f'<span class="proj-metric" style="view-timeline:'
                f'{projection_timeline_names[timeline_index]} inline">'
                + "".join(packs[pack_start:pack_stop])
                + "</span>"
            )
            projection_scrollers.append(
                f'<div class="proj-scroller"><div class="proj-track">{metric}</div></div>'
            )
    projection_result_tree = (
        f'<output id="final" class="proj-result-{projection_consumer_count - 1}"></output>'
    )
    for consumer in reversed(range(projection_consumer_count - 1)):
        projection_result_tree = (
            f'<div class="proj-result-{consumer}">{projection_result_tree}</div>'
        )
    projection_stage = (
        '<div class="projection-stage">'
        + '<div class="proj-scroller"><div class="proj-track">'
        + "".join(
            scroller.removeprefix(
                '<div class="proj-scroller"><div class="proj-track">'
            ).removesuffix("</div></div>")
            for scroller in projection_scrollers
        )
        + "</div></div>"
        + projection_result_tree
        + "</div>"
    )

    # The projection has the same avoidable decode pattern as the FC stage.
    # Normalize each metric width to the final residual-added output and use a
    # shared easing curve to invert view-timeline geometry directly into
    # --out-*. The wide fixed range covers GPT-2's known residual outliers.
    projection_easing_min = -128.0
    projection_easing_max = 768.0
    projection_easing_geometry_scale = (
        projection_viewport
        * 0.5
        / (projection_easing_max - projection_easing_min)
    )
    projection_easing_geometry_offset = (
        projection_viewport * 0.25
        - projection_easing_geometry_scale * projection_easing_min
    )
    projection_easing_z = np.linspace(
        projection_easing_max,
        projection_easing_min,
        PROJECTION_EASING_STOPS,
    )
    projection_easing_outputs = (
        (projection_easing_z - projection_easing_min)
        / (projection_easing_max - projection_easing_min)
    )
    projection_easing_progress = projection_viewport / (
        projection_viewport
        + projection_easing_geometry_offset
        + projection_easing_geometry_scale * projection_easing_z
    )
    projection_easing_stops = [
        f"{css_number(projection_easing_outputs[0])} 0%",
        *(
            f"{css_number(value)} {css_number(progress * 100)}%"
            for progress, value in zip(
                projection_easing_progress,
                projection_easing_outputs,
                strict=True,
            )
        ),
    ]
    projection_easing_keyframes = "".join(
        f"@keyframes {keyframe}{{"
        f"from{{--out-{index:03d}:{css_number(projection_easing_min)}}}"
        f"to{{--out-{index:03d}:{css_number(projection_easing_max)}}}}}"
        for index, keyframe in enumerate(projection_keyframe_names)
    )
    projection_easing_animation_rules: list[str] = []
    for consumer in range(projection_consumer_count):
        start = consumer * projection_outputs_per_consumer
        stop = min(start + projection_outputs_per_consumer, WIDTH)
        projection_easing_animation_rules.append(
            f".proj-result-{consumer}{{"
            f"animation-name:{','.join(projection_keyframe_names[start:stop])};"
            "animation-duration:1s;"
            "animation-timing-function:var(--projection-ease);"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(projection_timeline_names[start:stop])};"
            "animation-range:cover}"
        )
    projection_easing_metrics: list[str] = []
    for output_index in range(WIDTH):
        packs: list[str] = []
        for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
            characters = "".join(
                f"&#x{mlp_fonts.codepoint_starts[shard] + output_index:X};"
                for shard in range(
                    first_shard,
                    min(first_shard + 3, len(mlp_fonts.names)),
                )
            )
            packs.append(f'<i class="proj-pack-{pack}">{characters}</i>')
        factor = hidden_range * q_mlp.scales[output_index]
        multiplier = (
            projection_easing_geometry_scale
            * factor
            * UNITS_PER_EM
            / FONT_SIZE
        )
        constant_offset = (
            projection_easing_geometry_offset
            + projection_easing_geometry_scale
            * (
                data["mlp_proj_bias"][output_index]
                - factor * projection_metric_bases[0][output_index]
            )
        )
        metric_style = (
            f"view-timeline:{projection_timeline_names[output_index]} inline;"
            "width:calc-size(max-content,calc("
            f"size * {css_number(multiplier)} + "
            f"({css_number(constant_offset)} + "
            f"{css_number(projection_easing_geometry_scale)} * "
            f"var(--r1-{output_index:03d})) * 1px))"
        )
        projection_easing_metrics.append(
            f'<span class="proj-metric" style="{metric_style}">'
            + "".join(packs)
            + "</span>"
        )
    projection_easing_layout_css = (
        f'.projection-stage{{timeline-scope:{",".join(projection_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal;"
        f"--projection-ease:linear({','.join(projection_easing_stops)})}}"
        ".proj-scroller{position:fixed;left:0;top:-20000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".proj-track{{position:relative;width:{projection_track_width}px;height:1px}}"
        ".proj-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + "".join(projection_pack_rules)
    )
    projection_easing_stage = (
        '<div class="projection-stage">'
        '<div class="proj-scroller"><div class="proj-track">'
        + "".join(projection_easing_metrics)
        + "</div></div>"
        + projection_result_tree
        + "</div>"
    )

    if global_projection_fonts.row_bases is None:
        raise ValueError("global projection fonts require per-row bases")
    global_projection_bases = np.sum(
        np.stack(global_projection_fonts.row_bases), axis=0
    )
    global_projection_families = ",".join(
        f"mlprunS{shard}" for shard in range(len(global_projection_fonts.names))
    )
    global_projection_settings = ",".join(
        f'"{global_axis_tag(index)}" '
        f"calc(var(--hidden-{index:03d}) / {css_number(hidden_range)})"
        for index in range(MLP_WIDTH)
    )
    global_projection_metrics: list[str] = []
    for output_index in range(WIDTH):
        characters = "".join(
            f"&#x{start + output_index:X};"
            for start in global_projection_fonts.codepoint_starts
        )
        factor = hidden_range * q_mlp.scales[output_index]
        multiplier = (
            projection_easing_geometry_scale
            * factor
            * UNITS_PER_EM
            / FONT_SIZE
        )
        constant_offset = (
            projection_easing_geometry_offset
            + projection_easing_geometry_scale
            * (
                data["mlp_proj_bias"][output_index]
                - factor * global_projection_bases[output_index]
            )
        )
        metric_style = (
            f"view-timeline:{projection_timeline_names[output_index]} inline;"
            "width:calc-size(max-content,calc("
            f"size * {css_number(multiplier)} + "
            f"({css_number(constant_offset)} + "
            f"{css_number(projection_easing_geometry_scale)} * "
            f"var(--r1-{output_index:03d})) * 1px))"
        )
        global_projection_metrics.append(
            f'<span class="proj-metric" style="{metric_style}">'
            f"{characters}</span>"
        )
    global_projection_layout_css = (
        f'.projection-stage{{timeline-scope:{",".join(projection_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal;"
        f"font-family:{global_projection_families};"
        f"font-variation-settings:{global_projection_settings};"
        f"--projection-ease:linear({','.join(projection_easing_stops)})}}"
        ".proj-scroller{position:fixed;left:0;top:-20000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".proj-track{{position:relative;width:{projection_track_width}px;height:1px}}"
        ".proj-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
    )
    global_projection_stage = (
        '<div class="projection-stage">'
        '<div class="proj-scroller"><div class="proj-track">'
        + "".join(global_projection_metrics)
        + "</div></div>"
        + projection_result_tree
        + "</div>"
    )

    # Direct packed-timeline -> HVAR projection. The packed FC transport has
    # already recovered all 3,072 post-GELU values as CSS expressions. Feed
    # those expressions to one global variation-vector declaration and expose
    # the 768 projection results as glyph widths. This deliberately omits the
    # old 768-timeline output readback so its cost can be measured separately.
    packed4_hvar_settings = ",".join(
        f'"{global_axis_tag(index)}" '
        f"calc({packed4_hidden_expression(index)} / "
        f"{css_number(hidden_range)})"
        for index in range(MLP_WIDTH)
    )
    packed4_hvar_metrics = "".join(
        f'<i class="packed4-hvar-metric" data-output="{output}" '
        f'style="anchor-name:--hp{output:03d}">'
        + "".join(
            f"&#x{start + output:X};"
            for start in global_projection_fonts.codepoint_starts
        )
        + "</i>"
        for output in range(WIDTH)
    )
    packed4_hvar_stage = (
        '<output id="final" class="packed4-hvar-projection">'
        + packed4_hvar_metrics
        + "</output>"
    )
    packed4_hvar_layout_css = (
        ".packed4-hvar-projection{position:absolute;width:1px;height:1px;"
        f"font-size:{FONT_SIZE}px;font-kerning:none;white-space:pre;"
        f"font-family:{global_projection_families};"
        f"font-variation-settings:{packed4_hvar_settings}}}"
        ".packed4-hvar-metric{position:absolute;left:0;top:0;"
        "display:inline-block;width:max-content;height:1px;overflow:hidden;"
        "font-style:normal}"
    )

    direct_ln_value_names = [f"--hv-{index:03d}" for index in range(WIDTH)]
    direct_ln_registrations = (
        '@property --hv-mean{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --hv-variance{syntax:"<number>";inherits:true;initial-value:0}'
        + "".join(
            f'@property --next-norm-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            for index in range(WIDTH)
        )
    )
    direct_ln_values = []
    for output in range(WIDTH):
        raw_units = (
            f"(anchor-size(--hp{output:03d} width) / 1px * "
            f"{UNITS_PER_EM} / {FONT_SIZE} - "
            f"{css_number(global_projection_bases[output])})"
        )
        direct_ln_values.append(
            f"{direct_ln_value_names[output]}:calc("
            f"var(--r1-{output:03d}) + {raw_units} * "
            f"{css_number(hidden_range * q_mlp.scales[output])} + "
            f"({css_number(data['mlp_proj_bias'][output])}))"
        )
    direct_ln_mean = (
        f"--hv-mean:calc(({' + '.join(f'var({name})' for name in direct_ln_value_names)}) "
        f"/ {WIDTH})"
    )
    direct_ln_variance = (
        "--hv-variance:calc(("
        + " + ".join(
            f"(var({name}) - var(--hv-mean)) * "
            f"(var({name}) - var(--hv-mean))"
            for name in direct_ln_value_names
        )
        + f") / {WIDTH})"
    )
    direct_ln_outputs = [
        f"--next-norm-{output:03d}:calc((var(--hv-{output:03d}) - "
        f"var(--hv-mean)) / sqrt(var(--hv-variance) + {EPSILON}) * "
        f"{css_number(next_block_data['ln1_gamma'][output])} + "
        f"({css_number(next_block_data['ln1_beta'][output])}))"
        for output in range(WIDTH)
    ]
    packed4_hvar_direct_ln_stage = (
        '<div class="packed4-hvar-direct-ln-stage">'
        + packed4_hvar_metrics
        + '<output id="final" class="direct-ln"></output></div>'
    )
    packed4_hvar_direct_ln_layout_css = (
        ".packed4-hvar-direct-ln-stage{position:absolute;anchor-scope:all;"
        f"font-size:{FONT_SIZE}px;font-kerning:none;white-space:pre;"
        f"font-family:{global_projection_families};"
        f"font-variation-settings:{packed4_hvar_settings}}}"
        ".packed4-hvar-direct-ln-stage .packed4-hvar-metric{"
        "position:absolute;left:0;top:0;display:inline-block;width:max-content;"
        "height:1px;overflow:hidden;font-style:normal}"
        ".direct-ln{position:absolute;position-anchor:--hp000;"
        + ";".join(
            (
                *direct_ln_values,
                direct_ln_mean,
                direct_ln_variance,
                *direct_ln_outputs,
            )
        )
        + "}"
    )

    # Re-import the 768 live HVAR widths as registered CSS numbers for the
    # next transformer block. Four 12-bit values share each two-dimensional
    # carrier: low base-64 digits in width, high digits in height.
    hvar_gather_group_size = 4
    hvar_gather_radix = 64
    hvar_gather_levels = 4095
    hvar_gather_group_count = WIDTH // hvar_gather_group_size
    state_calibration = json.loads(
        (
            OUT.parent
            / "packed-activation-precision"
            / "hidden-ranges-headroom2.json"
        ).read_text()
    )["blocks"][0]
    hvar_gather_bound = np.asarray(
        state_calibration["state_bound"], dtype=np.float64
    )
    observed_case_bound = np.max(
        np.abs(np.stack(packed4_case_outputs)), axis=0
    ) * 1.05
    hvar_gather_bound = np.maximum(hvar_gather_bound, observed_case_bound)
    hvar_gather_low = -hvar_gather_bound
    hvar_gather_span = 2 * hvar_gather_bound
    hvar_gather_registrations = "".join(
        f'@property --next-{index:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(WIDTH)
    )

    def hvar_gather_digit(dimension: str, place: int) -> str:
        size = "100cqi" if dimension == "i" else "100cqb"
        power = hvar_gather_radix**place
        if place == 0:
            return f"mod(round(nearest,{size}/1px,1),{hvar_gather_radix})"
        if place == hvar_gather_group_size - 1:
            return f"round(down,{size}/1px/{power},1)"
        return (
            f"mod(round(down,{size}/1px/{power},1),"
            f"{hvar_gather_radix})"
        )

    hvar_gather_pack_rules = []
    hvar_gather_decode_rules = []
    hvar_gather_sources = []
    for group in range(hvar_gather_group_count):
        start = group * hvar_gather_group_size
        code_declarations = []
        low_terms = []
        high_terms = []
        decoded = []
        sources = []
        for place in range(hvar_gather_group_size):
            output = start + place
            raw_width = (
                f"(anchor-size(--hp{output:03d} width) * "
                f"{UNITS_PER_EM} / {FONT_SIZE} - "
                f"{css_number(global_projection_bases[output])}px)"
            )
            final_value = (
                f"({raw_width} * {css_number(hidden_range * q_mlp.scales[output])} "
                f"+ ({css_number(data['mlp_proj_bias'][output])}px) + "
                f"var(--r1-{output:03d}) * 1px)"
            )
            code_declarations.append(
                f"--hvc{place}:round(nearest,clamp(0px,"
                f"({final_value} - ({css_number(hvar_gather_low[output])}px)) "
                f"* {hvar_gather_levels} / "
                f"{css_number(hvar_gather_span[output])},"
                f"{hvar_gather_levels}px),1px)"
            )
            low_terms.append(
                f"{hvar_gather_radix**place} * "
                f"mod(var(--hvc{place})/1px,{hvar_gather_radix}) * 1px"
            )
            high_terms.append(
                f"{hvar_gather_radix**place} * "
                f"round(down,var(--hvc{place})/1px/"
                f"{hvar_gather_radix},1) * 1px"
            )
            code = (
                f"({hvar_gather_digit('i', place)} + "
                f"{hvar_gather_radix} * {hvar_gather_digit('b', place)})"
            )
            decoded.append(
                f"--next-{output:03d}:calc("
                f"{css_number(hvar_gather_low[output])} + {code} * "
                f"{css_number(hvar_gather_span[output])} / "
                f"{hvar_gather_levels})"
            )
            characters = "".join(
                f"&#x{codepoint_start + output:X};"
                for codepoint_start in global_projection_fonts.codepoint_starts
            )
            sources.append(
                f'<i class="hvar-gather-source" '
                f'style="anchor-name:--hp{output:03d}">{characters}</i>'
            )
        hvar_gather_pack_rules.append(
            f".hvg-pack-{group}{{{';'.join(code_declarations)};"
            f"width:calc({' + '.join(low_terms)});"
            f"height:calc({' + '.join(high_terms)})}}"
        )
        hvar_gather_decode_rules.append(
            f".hvg-decode-{group}{{{';'.join(decoded)}}}"
        )
        hvar_gather_sources.append("".join(sources))

    hvar_gather_chain = (
        f'<output id="final" class="hvg-decode-'
        f'{hvar_gather_group_count - 1}"></output>'
    )
    for group in reversed(range(hvar_gather_group_count)):
        classes = f"hvar-gather-carrier hvg-pack-{group}"
        if group:
            classes += f" hvg-decode-{group - 1}"
        hvar_gather_chain = (
            hvar_gather_sources[group]
            + f'<div class="{classes}" '
            + f'style="position-anchor:--hp{group * hvar_gather_group_size:03d}">'
            + hvar_gather_chain
            + "</div>"
        )
    packed4_hvar_gather_stage = (
        '<div class="packed4-hvar-gather-stage">'
        + hvar_gather_chain
        + "</div>"
    )
    hvar_gather_flat_chain = (
        f'<output id="final" class="hvg-decode-'
        f'{hvar_gather_group_count - 1}"></output>'
    )
    for group in reversed(range(hvar_gather_group_count)):
        classes = f"hvar-gather-carrier hvg-pack-{group}"
        if group:
            classes += f" hvg-decode-{group - 1}"
        hvar_gather_flat_chain = (
            f'<div class="{classes}" '
            + f'style="position-anchor:--hp{group * hvar_gather_group_size:03d}">'
            + hvar_gather_flat_chain
            + "</div>"
        )
    packed4_hvar_gather_flat_stage = (
        '<div class="packed4-hvar-gather-stage hvar-gather-flat">'
        + "".join(hvar_gather_sources)
        + hvar_gather_flat_chain
        + "</div>"
    )
    packed4_hvar_gather_fixed_stage = (
        '<div class="packed4-hvar-gather-stage hvar-gather-flat-fixed">'
        + "".join(hvar_gather_sources)
        + hvar_gather_flat_chain
        + "</div>"
    )
    packed4_hvar_gather_layout_css = (
        ".packed4-hvar-gather-stage{position:absolute;"
        f"font-size:{FONT_SIZE}px;font-kerning:none;white-space:pre;"
        f"font-family:{global_projection_families};"
        f"font-variation-settings:{packed4_hvar_settings}}}"
        ".hvar-gather-source{position:absolute;display:inline-block;"
        "width:max-content;height:1px;overflow:hidden;font-style:normal}"
        ".hvar-gather-carrier{position:absolute;container-type:size}"
        + "".join(hvar_gather_pack_rules)
        + "".join(hvar_gather_decode_rules)
    )

    # Eight-bit alternative: six values per carrier instead of four. This
    # tests whether calibrated per-channel ranges retain enough accuracy to
    # justify a one-third shallower dependency chain.
    hvar_gather8_group_size = 6
    hvar_gather8_radix = 16
    hvar_gather8_levels = 255
    hvar_gather8_group_count = WIDTH // hvar_gather8_group_size

    def hvar_gather8_digit(dimension: str, place: int) -> str:
        size = "100cqi" if dimension == "i" else "100cqb"
        power = hvar_gather8_radix**place
        if place == 0:
            return f"mod(round(nearest,{size}/1px,1),{hvar_gather8_radix})"
        if place == hvar_gather8_group_size - 1:
            return f"round(down,{size}/1px/{power},1)"
        return (
            f"mod(round(down,{size}/1px/{power},1),"
            f"{hvar_gather8_radix})"
        )

    hvar_gather8_pack_rules = []
    hvar_gather8_decode_rules = []
    hvar_gather8_sources = []
    for group in range(hvar_gather8_group_count):
        start = group * hvar_gather8_group_size
        code_declarations = []
        low_terms = []
        high_terms = []
        decoded = []
        sources = []
        for place in range(hvar_gather8_group_size):
            output = start + place
            raw_width = (
                f"(anchor-size(--h8p{output:03d} width) * "
                f"{UNITS_PER_EM} / {FONT_SIZE} - "
                f"{css_number(global_projection_bases[output])}px)"
            )
            final_value = (
                f"({raw_width} * {css_number(hidden_range * q_mlp.scales[output])} "
                f"+ ({css_number(data['mlp_proj_bias'][output])}px) + "
                f"var(--r1-{output:03d}) * 1px)"
            )
            code_declarations.append(
                f"--h8c{place}:round(nearest,clamp(0px,"
                f"({final_value} - ({css_number(hvar_gather_low[output])}px)) "
                f"* {hvar_gather8_levels} / "
                f"{css_number(hvar_gather_span[output])},"
                f"{hvar_gather8_levels}px),1px)"
            )
            low_terms.append(
                f"{hvar_gather8_radix**place} * "
                f"mod(var(--h8c{place})/1px,{hvar_gather8_radix}) * 1px"
            )
            high_terms.append(
                f"{hvar_gather8_radix**place} * "
                f"round(down,var(--h8c{place})/1px/"
                f"{hvar_gather8_radix},1) * 1px"
            )
            code = (
                f"({hvar_gather8_digit('i', place)} + "
                f"{hvar_gather8_radix} * "
                f"{hvar_gather8_digit('b', place)})"
            )
            decoded.append(
                f"--next-{output:03d}:calc("
                f"{css_number(hvar_gather_low[output])} + {code} * "
                f"{css_number(hvar_gather_span[output])} / "
                f"{hvar_gather8_levels})"
            )
            characters = "".join(
                f"&#x{codepoint_start + output:X};"
                for codepoint_start in global_projection_fonts.codepoint_starts
            )
            sources.append(
                f'<i class="hvar-gather8-source" '
                f'style="anchor-name:--h8p{output:03d}">{characters}</i>'
            )
        hvar_gather8_pack_rules.append(
            f".h8-pack-{group}{{{';'.join(code_declarations)};"
            f"width:calc({' + '.join(low_terms)});"
            f"height:calc({' + '.join(high_terms)})}}"
        )
        hvar_gather8_decode_rules.append(
            f".h8-decode-{group}{{{';'.join(decoded)}}}"
        )
        hvar_gather8_sources.append("".join(sources))
    hvar_gather8_chain = (
        f'<output id="final" class="h8-decode-'
        f'{hvar_gather8_group_count - 1}"></output>'
    )
    for group in reversed(range(hvar_gather8_group_count)):
        classes = f"hvar-gather8-carrier h8-pack-{group}"
        if group:
            classes += f" h8-decode-{group - 1}"
        hvar_gather8_chain = (
            hvar_gather8_sources[group]
            + f'<div class="{classes}" '
            + f'style="position-anchor:--h8p{group * hvar_gather8_group_size:03d}">'
            + hvar_gather8_chain
            + "</div>"
        )
    packed4_hvar_gather8_stage = (
        '<div class="packed4-hvar-gather8-stage">'
        + hvar_gather8_chain
        + "</div>"
    )
    packed4_hvar_gather8_layout_css = (
        ".packed4-hvar-gather8-stage{position:absolute;"
        f"font-size:{FONT_SIZE}px;font-kerning:none;white-space:pre;"
        f"font-family:{global_projection_families};"
        f"font-variation-settings:{packed4_hvar_settings}}}"
        ".hvar-gather8-source{position:absolute;display:inline-block;"
        "width:max-content;height:1px;overflow:hidden;font-style:normal}"
        ".hvar-gather8-carrier{position:absolute;container-type:size}"
        + "".join(hvar_gather8_pack_rules)
        + "".join(hvar_gather8_decode_rules)
    )
    packed4_hvar_gather_flat_layout_css = (
        packed4_hvar_gather_layout_css
        + ".hvar-gather-flat{anchor-scope:all}"
    )
    packed4_hvar_gather_fixed_layout_css = (
        packed4_hvar_gather_layout_css
        + ".hvar-gather-flat-fixed{anchor-scope:all}"
        + ".hvar-gather-flat-fixed .hvar-gather-source,"
        + ".hvar-gather-flat-fixed .hvar-gather-carrier{position:fixed}"
    )

    if PROJECTION_METRICS_PER_OUTPUT != 1:
        raise ValueError("paired projection transport requires one metric per output")
    projection_pair_count = WIDTH // 2
    paired_projection_timeline_names = [
        f"--pot{index}" for index in range(projection_pair_count)
    ]
    paired_projection_cover_names = [
        f"--poc{index}" for index in range(projection_pair_count)
    ]
    paired_projection_entry_names = [
        f"--poe{index}" for index in range(projection_pair_count)
    ]
    paired_projection_keyframes = [
        f"pok{index}" for index in range(projection_pair_count)
    ]
    paired_projection_timeline_rules = "".join(
        f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{"
        f"cover 0%{{{cover}:0;{entry}:0}}"
        f"entry 100%{{{entry}:1}}"
        f"cover 100%{{{cover}:1;{entry}:1}}}}"
        for cover, entry, keyframe in zip(
            paired_projection_cover_names,
            paired_projection_entry_names,
            paired_projection_keyframes,
            strict=True,
        )
    )
    projection_pair_origins: list[float] = []
    paired_projection_declarations: list[str] = []
    for pair in range(projection_pair_count):
        first = pair * 2
        second = first + 1
        first_base_px = (
            float(projection_metric_bases[0][first]) * FONT_SIZE / UNITS_PER_EM
        )
        second_base_px = (
            float(projection_metric_bases[0][second]) * FONT_SIZE / UNITS_PER_EM
        )
        origin = projection_viewport - first_base_px - second_base_px / 2
        projection_pair_origins.append(origin)
        cover = paired_projection_cover_names[pair]
        entry = paired_projection_entry_names[pair]
        pair_width = f"--proj-pair-width-{pair:03d}"
        paired_projection_declarations.append(
            f"{pair_width}:calc(var({cover}) * {projection_viewport} / "
            f"(var({entry}) - var({cover})))"
        )
        for within_pair, output in enumerate((first, second)):
            raw_name = f"--proj-raw-{output:03d}"
            factor = hidden_range * q_mlp.scales[output]
            if within_pair == 0:
                encoded = (
                    f"({projection_viewport} - var({entry}) * var({pair_width}) "
                    f"- ({css_number(origin)}))"
                )
            else:
                encoded = f"var({pair_width})"
            paired_projection_declarations.extend(
                (
                    f"{raw_name}:calc({encoded} * {UNITS_PER_EM} / {FONT_SIZE} "
                    f"- {int(projection_metric_bases[0][output])})",
                    f"--out-{output:03d}:calc(var(--r1-{output:03d}) + "
                    f"var({raw_name}) * {css_number(factor)} + "
                    f"({css_number(data['mlp_proj_bias'][output])}))",
                )
            )
    paired_projection_animation_rules: list[str] = []
    paired_projection_math_rules: list[str] = []
    projection_declarations_per_pair = 5
    for consumer in range(projection_consumer_count):
        output_start = consumer * projection_outputs_per_consumer
        output_stop = min(output_start + projection_outputs_per_consumer, WIDTH)
        pair_start = output_start // 2
        pair_stop = output_stop // 2
        paired_projection_animation_rules.append(
            f".paired-proj-result-{consumer}{{"
            f"animation-name:{','.join(paired_projection_keyframes[pair_start:pair_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(paired_projection_timeline_names[pair_start:pair_stop])}}}"
        )
        paired_projection_math_rules.append(
            f".paired-proj-result-{consumer}{{"
            + ";".join(
                paired_projection_declarations[
                    pair_start * projection_declarations_per_pair :
                    pair_stop * projection_declarations_per_pair
                ]
            )
            + "}"
        )

    def projection_packs_for_output(output: int) -> list[str]:
        packs: list[str] = []
        for pack, first_shard in enumerate(range(0, len(mlp_fonts.names), 3)):
            characters = "".join(
                f"&#x{mlp_fonts.codepoint_starts[shard] + output:X};"
                for shard in range(
                    first_shard, min(first_shard + 3, len(mlp_fonts.names))
                )
            )
            packs.append(f'<i class="proj-pack-{pack}">{characters}</i>')
        return packs

    # Quantize and pack the final projection state four values per timeline.
    # This is the form a following block can consume directly, avoiding a
    # 768-value numeric transport boundary between transformer blocks.
    output_pack_group_count = WIDTH // 4
    if OUTPUT_PACK_SCHEME == "channel910":
        output_pack_viewport = 4_194_304
        output_pack_extent_offset = 1_100_000
        output_pack_track_width = 6_500_000
        output_pack_radix = 1024
        output_pack_center = 256
    else:
        output_pack_viewport = 1_048_576
        output_pack_extent_offset = 300_000
        output_pack_track_width = 1_600_000
        output_pack_radix = 512
        output_pack_center = 128
    output_pack_left_base = output_pack_viewport - output_pack_extent_offset
    output_pack_range = 128
    if OUTPUT_PACK_SCHEME != "global":
        state_range_path = (
            OUT.parent
            / "packed-activation-precision"
            / "hidden-ranges-headroom2.json"
        )
        state_range_data = json.loads(state_range_path.read_text())
        # The stored bounds include 2x calibration headroom. Scale them to the
        # requested operating point without regenerating calibration data.
        block_state_ranges = state_range_data["blocks"][0]
        output_pack_bounds = np.asarray(
            block_state_ranges["state_bound"], dtype=np.float64
        ) * (OUTPUT_PACK_HEADROOM / 2)
        if OUTPUT_PACK_SCHEME == "channel89asym":
            output_pack_lows = np.asarray(
                block_state_ranges["state_minimum"], dtype=np.float64
            ) * (OUTPUT_PACK_HEADROOM / 2)
            output_pack_highs = np.asarray(
                block_state_ranges["state_maximum"], dtype=np.float64
            ) * (OUTPUT_PACK_HEADROOM / 2)
            output_pack_spans = np.maximum(
                output_pack_highs - output_pack_lows, 1e-9
            )
            ranking_range = output_pack_spans
        else:
            output_pack_lows = -output_pack_bounds
            output_pack_highs = output_pack_bounds
            output_pack_spans = output_pack_highs - output_pack_lows
            ranking_range = output_pack_bounds
        ranked_output_channels = np.argsort(ranking_range)
        low_precision_channels = ranked_output_channels[: WIDTH // 2]
        high_precision_channels = ranked_output_channels[WIDTH // 2 :]
        output_pack_group_outputs = [
            (
                int(low_precision_channels[group * 2]),
                int(high_precision_channels[group * 2]),
                int(low_precision_channels[group * 2 + 1]),
                int(high_precision_channels[group * 2 + 1]),
            )
            for group in range(output_pack_group_count)
        ]
    else:
        output_pack_bounds = np.full(WIDTH, output_pack_range, dtype=np.float64)
        output_pack_lows = -output_pack_bounds
        output_pack_highs = output_pack_bounds
        output_pack_spans = output_pack_highs - output_pack_lows
        output_pack_group_outputs = [
            tuple(range(group * 4, group * 4 + 4))
            for group in range(output_pack_group_count)
        ]
    output_pack_location_by_output = {
        output: (group, slot)
        for group, outputs in enumerate(output_pack_group_outputs)
        for slot, output in enumerate(outputs)
    }
    output_pack_timeline_names = [
        f"--qot{index}" for index in range(output_pack_group_count)
    ]
    output_pack_cover_names = [
        f"--qoc{index}" for index in range(output_pack_group_count)
    ]
    output_pack_entry_names = [
        f"--qoe{index}" for index in range(output_pack_group_count)
    ]
    output_pack_keyframes = [
        f"qok{index}" for index in range(output_pack_group_count)
    ]
    output_pack_timeline_rules = "".join(
        f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{cover 0%{{{cover}:0;{entry}:0}}"
        f"entry 100%{{{entry}:1}}cover 100%{{{cover}:1;{entry}:1}}}}"
        for cover, entry, keyframe in zip(
            output_pack_cover_names,
            output_pack_entry_names,
            output_pack_keyframes,
            strict=True,
        )
    )
    output_pack_digit_rules: list[str] = []
    for output in range(WIDTH):
        factor = hidden_range * q_mlp.scales[output]
        _, slot = output_pack_location_by_output[output]
        multiplier = 1 if slot % 2 == 0 else output_pack_radix
        levels = output_pack_center * 2 - 1 if multiplier == 1 else output_pack_radix - 1
        digit_offset = output_pack_center if multiplier == 1 else 0
        value = (
            f"((size / 1px * {UNITS_PER_EM} / {FONT_SIZE} - "
            f"{int(projection_metric_bases[0][output])}) * "
            f"{css_number(factor)} + ({css_number(data['mlp_proj_bias'][output])}) "
            f"+ var(--r1-{output:03d}))"
        )
        value_basis = f"calc-size(max-content,calc(({value} + 256) * 1px))"
        u = "(size / 1px - 256)"
        if OUTPUT_PACK_SCHEME == "channel89asym":
            encoded = (
                f"clamp(0,({u} - {css_number(output_pack_lows[output])}) / "
                f"{css_number(output_pack_spans[output])},1) * {levels}"
            )
        elif OUTPUT_PACK_SCHEME != "global":
            encoded = (
                f"(clamp(-1,{u} / {css_number(output_pack_bounds[output])},1) "
                f"+ 1) * {levels} / 2"
            )
        else:
            encoded = (
                f"(clamp(-1,sign({u}) * sqrt(abs({u}) / {output_pack_range}),1) "
                f"+ 1) * {levels} / 2"
            )
        output_pack_digit_rules.append(
            f".qod-{output:03d}{{width:calc-size({value_basis},calc((round(nearest,"
            f"{encoded},1) + {digit_offset}) * 1px * {multiplier}))}}"
        )
    output_pack_declarations: list[str] = []
    for group in range(output_pack_group_count):
        cover = output_pack_cover_names[group]
        entry = output_pack_entry_names[group]
        width_name = f"--qow-{group:03d}"
        left_pack = f"--qol-{group:03d}"
        width_pack = f"--qop-{group:03d}"
        output_pack_declarations.extend(
            (
                f"{width_name}:calc(var({cover}) * {output_pack_viewport} / "
                f"(var({entry}) - var({cover})))",
                f"{left_pack}:round(nearest,{output_pack_viewport} - var({entry}) * "
                f"var({width_name}) - {output_pack_left_base},1)",
                f"{width_pack}:round(nearest,var({width_name}) - "
                f"{output_pack_extent_offset},1)",
            )
        )
        for within_group in range(4):
            output = output_pack_group_outputs[group][within_group]
            packed = left_pack if within_group < 2 else width_pack
            if within_group % 2 == 0:
                digit = f"(mod(var({packed}),{output_pack_radix}) - {output_pack_center})"
                levels = output_pack_center * 2 - 1
            else:
                digit = f"round(down,var({packed}) / {output_pack_radix},1)"
                levels = output_pack_radix - 1
            normalized = f"({digit} * 2 / {levels} - 1)"
            if OUTPUT_PACK_SCHEME == "channel89asym":
                decoded = (
                    f"{css_number(output_pack_lows[output])} + {digit} / "
                    f"{levels} * {css_number(output_pack_spans[output])}"
                )
            elif OUTPUT_PACK_SCHEME != "global":
                decoded = (
                    f"{normalized} * {css_number(output_pack_bounds[output])}"
                )
            else:
                decoded = (
                    f"sign({normalized}) * pow(abs({normalized}),2) "
                    f"* {output_pack_range}"
                )
            output_pack_declarations.append(
                f"--out-{output:03d}:calc({decoded})"
            )
    output_pack_animation_rules: list[str] = []
    output_pack_math_rules: list[str] = []
    output_groups_per_consumer = OUTPUTS_PER_CONSUMER // 4
    output_consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(output_consumer_count):
        group_start = consumer * output_groups_per_consumer
        group_stop = min(
            group_start + output_groups_per_consumer, output_pack_group_count
        )
        output_pack_animation_rules.append(
            f".qo-result-{consumer}{{animation-name:"
            f"{','.join(output_pack_keyframes[group_start:group_stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(output_pack_timeline_names[group_start:group_stop])}}}"
        )
        output_pack_math_rules.append(
            f".qo-result-{consumer}{{"
            + ";".join(
                output_pack_declarations[group_start * 7 : group_stop * 7]
            )
            + "}"
        )
    output_pack_groups: list[str] = []
    for group, timeline in enumerate(output_pack_timeline_names):
        digits: list[str] = []
        for output in output_pack_group_outputs[group]:
            digits.append(
                f'<span class="qo-digit qod-{output:03d}">'
                + "".join(projection_packs_for_output(output))
                + "</span>"
            )
        output_pack_groups.append(
            '<span class="qo-pair"><span class="qo-lead">'
            + digits[0]
            + digits[1]
            + f'</span><span class="qo-subject" style="view-timeline:{timeline} inline">'
            + digits[2]
            + digits[3]
            + "</span></span>"
        )
    output_pack_result_tree = (
        f'<output id="final" class="qo-result-{output_consumer_count - 1}"></output>'
    )
    for consumer in reversed(range(output_consumer_count - 1)):
        output_pack_result_tree = (
            f'<div class="qo-result-{consumer}">{output_pack_result_tree}</div>'
        )
    output_pack_stage = (
        '<div class="output-packed-stage"><div class="qo-scroller"><div class="qo-track">'
        + "".join(output_pack_groups)
        + "</div></div>"
        + output_pack_result_tree
        + "</div>"
    )
    output_pack_layout_css = (
        f'.output-packed-stage{{timeline-scope:{",".join(output_pack_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal}}"
        f".qo-scroller{{position:fixed;left:0;top:-30000px;width:{output_pack_viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}"
        f".qo-track{{position:relative;width:{output_pack_track_width}px;height:1px}}"
        f".qo-pair{{position:absolute;left:{output_pack_left_base}px;top:0;"
        "display:inline-flex;height:1px}"
        ".qo-lead,.qo-subject{display:inline-flex;flex:none;height:1px;"
        "white-space:pre;font-style:normal}"
        f".qo-subject{{width:calc-size(max-content,size + {output_pack_extent_offset}px)}}"
        ".qo-digit{display:inline-flex;flex:none;height:1px;overflow:hidden;"
        "white-space:pre;font-style:normal}"
        + "".join(output_pack_digit_rules)
    )

    paired_projection_metrics: list[str] = []
    for pair, timeline in enumerate(paired_projection_timeline_names):
        first = pair * 2
        second = first + 1
        paired_projection_metrics.append(
            f'<span class="proj-pair" style="left:{css_number(projection_pair_origins[pair])}px">'
            + "".join(projection_packs_for_output(first))
            + f'<span class="proj-pair-subject" style="view-timeline:{timeline} inline">'
            + "".join(projection_packs_for_output(second))
            + "</span></span>"
        )
    paired_projection_result_tree = (
        f'<output id="final" class="paired-proj-result-{projection_consumer_count - 1}"></output>'
    )
    for consumer in reversed(range(projection_consumer_count - 1)):
        paired_projection_result_tree = (
            f'<div class="paired-proj-result-{consumer}">'
            f"{paired_projection_result_tree}</div>"
        )
    paired_projection_stage = (
        '<div class="paired-projection-stage">'
        '<div class="proj-scroller"><div class="proj-track">'
        + "".join(paired_projection_metrics)
        + "</div></div>"
        + paired_projection_result_tree
        + "</div>"
    )
    paired_projection_layout_css = (
        f'.paired-projection-stage{{timeline-scope:{",".join(paired_projection_timeline_names)};'
        f"font-size:{FONT_SIZE}px;font-kerning:none;font-style:normal}}"
        ".proj-pair{position:absolute;top:0;display:inline-flex;height:1px;"
        "white-space:pre;font-style:normal}"
        ".proj-pair-subject{display:inline-flex;width:max-content;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal}"
    )
    chained_fc_tree = projection_stage
    for consumer in reversed(range(consumer_count)):
        chained_fc_tree = f'<div class="result-{consumer}">{chained_fc_tree}</div>'
    all_easing_chained_fc_tree = projection_easing_stage
    for consumer in reversed(range(consumer_count)):
        all_easing_chained_fc_tree = (
            f'<div class="result-{consumer}">{all_easing_chained_fc_tree}</div>'
        )
    global_projection_chained_fc_tree = global_projection_stage
    for consumer in reversed(range(consumer_count)):
        global_projection_chained_fc_tree = (
            f'<div class="result-{consumer}">'
            f"{global_projection_chained_fc_tree}</div>"
        )
    paired_chained_fc_tree = paired_projection_stage
    for consumer in reversed(range(consumer_count)):
        paired_chained_fc_tree = (
            f'<div class="paired-result-{consumer}">{paired_chained_fc_tree}</div>'
        )
    paired_fc_only_chained_tree = projection_stage
    for consumer in reversed(range(consumer_count)):
        paired_fc_only_chained_tree = (
            f'<div class="paired-result-{consumer}">{paired_fc_only_chained_tree}</div>'
        )
    packed4_chained_tree = projection_stage
    for consumer in reversed(range(consumer_count)):
        packed4_chained_tree = (
            f'<div class="q4-result-{consumer}">{packed4_chained_tree}</div>'
        )
    packed4_hvar_tree = packed4_hvar_stage
    for consumer in reversed(range(consumer_count)):
        packed4_hvar_tree = (
            f'<div class="q4-result-{consumer}">{packed4_hvar_tree}</div>'
        )
    packed4_hvar_direct_ln_tree = packed4_hvar_direct_ln_stage
    for consumer in reversed(range(consumer_count)):
        packed4_hvar_direct_ln_tree = (
            f'<div class="q4-result-{consumer}">'
            f"{packed4_hvar_direct_ln_tree}</div>"
        )
    packed4_hvar_gather_tree = packed4_hvar_gather_stage
    for consumer in reversed(range(consumer_count)):
        packed4_hvar_gather_tree = (
            f'<div class="q4-result-{consumer}">'
            f"{packed4_hvar_gather_tree}</div>"
        )
    packed4_hvar_gather8_tree = packed4_hvar_gather8_stage
    for consumer in reversed(range(consumer_count)):
        packed4_hvar_gather8_tree = (
            f'<div class="q4-result-{consumer}">'
            f"{packed4_hvar_gather8_tree}</div>"
        )
    packed4_hvar_gather_flat_tree = packed4_hvar_gather_flat_stage
    for consumer in reversed(range(consumer_count)):
        packed4_hvar_gather_flat_tree = (
            f'<div class="q4-result-{consumer}">'
            f"{packed4_hvar_gather_flat_tree}</div>"
        )
    packed4_hvar_gather_fixed_tree = packed4_hvar_gather_fixed_stage
    for consumer in reversed(range(consumer_count)):
        packed4_hvar_gather_fixed_tree = (
            f'<div class="q4-result-{consumer}">'
            f"{packed4_hvar_gather_fixed_tree}</div>"
        )
    packed4_paired_output_tree = paired_projection_stage
    for consumer in reversed(range(consumer_count)):
        packed4_paired_output_tree = (
            f'<div class="q4-result-{consumer}">'
            f"{packed4_paired_output_tree}</div>"
        )
    packed4_output_packed_tree = output_pack_stage
    for consumer in reversed(range(consumer_count)):
        packed4_output_packed_tree = (
            f'<div class="q4-result-{consumer}">{packed4_output_packed_tree}</div>'
        )
    packed4_transport_tree = (
        f'<output id="final" class="q4-result-{consumer_count - 1}"></output>'
    )
    for consumer in reversed(range(consumer_count - 1)):
        packed4_transport_tree = (
            f'<div class="q4-result-{consumer}">{packed4_transport_tree}</div>'
        )
    packed6_chained_tree = projection_stage
    for consumer in reversed(range(packed6_consumer_count)):
        packed6_chained_tree = (
            f'<div class="q6-result-{consumer}">{packed6_chained_tree}</div>'
        )
    packed6_transport_tree = (
        f'<output id="final" class="q6-result-{packed6_consumer_count - 1}"></output>'
    )
    for consumer in reversed(range(packed6_consumer_count - 1)):
        packed6_transport_tree = (
            f'<div class="q6-result-{consumer}">{packed6_transport_tree}</div>'
        )
    hetero_chained_tree = projection_stage
    for bank_prefix, bank in (("h8", hetero_high), ("h5", hetero_low)):
        for consumer in reversed(range(int(bank["consumer_count"]))):
            hetero_chained_tree = (
                f'<div class="{bank_prefix}-result-{consumer}">'
                f"{hetero_chained_tree}</div>"
            )
    sensitivity_chained_tree = projection_stage
    for bank_prefix, bank in reversed(sensitivity_banks):
        for consumer in reversed(range(int(bank["consumer_count"]))):
            sensitivity_chained_tree = (
                f'<div class="{bank_prefix}-result-{consumer}">'
                f"{sensitivity_chained_tree}</div>"
            )

    mlp_css = (
        faces
        + font_faces("mlp-flat", mlp_fonts)
        + timeline_rules
        + projection_timeline_rules
        + hidden_registrations
        + output_registrations
        + gelu_function
        + scope_with_timelines
        + layout_css
        + projection_layout_css
        + animation_css
        + result_math_css
        + "".join(projection_animation_rules)
        + "".join(projection_math_rules)
        + visible_css
    )
    MLP_CSS_PATH.write_text(mlp_css)
    mlp_css_tag = hashlib.sha256(MLP_CSS_PATH.read_bytes()).hexdigest()[:12]
    MLP_HTML_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Flat view-timeline GPT-2 MLP</title>'
        f'<link rel="stylesheet" href="view-timeline-mlp.css?v={mlp_css_tag}">'
        '<h1>Flat GPT-2 MLP in HTML/CSS</h1>'
        '<p>No JavaScript. 768→3,072 + GELU →768 + residual.</p>'
        '<div class="scope">'
        + shared_timeline_scroller
        + chained_fc_tree
        + "</div>"
    )
    MLP_REFERENCE_PATH.write_text(
        json.dumps(
            {
                "input_width": WIDTH,
                "hidden_width": MLP_WIDTH,
                "output_width": WIDTH,
                "outputs_per_consumer": OUTPUTS_PER_CONSUMER,
                "layout_strategy": "flat-fc-direct-flat-projection",
                "fc_base_total": base_total,
                "projection_base_total": projection_base_total,
                "projection_metric_base_min": int(
                    min(np.min(bases) for bases in projection_metric_bases)
                ),
                "projection_metric_base_max": int(
                    max(np.max(bases) for bases in projection_metric_bases)
                ),
                "projection_metrics_per_output": PROJECTION_METRICS_PER_OUTPUT,
                "projection_viewport": projection_viewport,
                "activation_range": activation_range,
                "hidden_range": hidden_range,
                "residual": residual.tolist(),
                "projection_raw": projection_raw.tolist(),
                "projected": projected.tolist(),
                "output": final_output.tolist(),
                "html_bytes": MLP_HTML_PATH.stat().st_size,
                "css_bytes": MLP_CSS_PATH.stat().st_size,
                "font_bytes": sum(
                    (OUT / f"{name}.woff2").stat().st_size
                    for name in (*fonts.names, *mlp_fonts.names)
                ),
            },
            indent=2,
        )
        + "\n"
    )

    # Full one-token block: CSS computes LN1, the composed one-token attention
    # matmul, its residual, and LN2 before entering the flat MLP chain above.
    if attention_fonts.row_bases is None:
        raise ValueError("attention fonts require per-output base advances")
    attention_base_rows = np.sum(np.stack(attention_fonts.row_bases), axis=0)
    attention_base_pixels = int(np.max(attention_base_rows)) * FONT_SIZE / UNITS_PER_EM
    attention_viewport = 2 ** math.ceil(
        math.log2(max(1024, attention_base_pixels * 1.25))
    )
    attention_track_width = attention_viewport * 3
    attention_range = float(np.max(np.abs(n1)) * 1.01)
    attention_input_names = [f"--n1-{index:03d}" for index in range(WIDTH)]
    attention_timeline_names = [f"--at{index}" for index in range(WIDTH)]
    attention_progress_names = [f"--ap{index}" for index in range(WIDTH)]
    attention_keyframe_names = [f"ak{index}" for index in range(WIDTH)]
    attention_timeline_rules = "".join(
        f'@property {progress}'
        '{syntax:"<number>";inherits:true;initial-value:-1}'
        f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for progress, keyframe in zip(
            attention_progress_names, attention_keyframe_names, strict=True
        )
    )
    block_registrations = "".join(
        f'@property {name}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for name in (
            "--mean1",
            "--var1",
            "--mean2",
            "--var2",
            *(
                f"--{prefix}-{index:03d}"
                for prefix in ("n1", "attn", "r1", "n2")
                for index in range(WIDTH)
            ),
        )
    )
    x_inputs = ";".join(
        f"--x-{index:03d}:{css_number(value)}"
        for index, value in enumerate(data["x"])
    )
    n1_math = ";".join(
        norm_declarations(
            "x",
            "n1",
            data["ln1_gamma"],
            data["ln1_beta"],
            "mean1",
            "var1",
        )
    )
    attention_font_state = (
        f"font-size:{FONT_SIZE}px;font-kerning:none;"
        f"font-family:{','.join(f'attnflatS{index}' for index in range(len(attention_fonts.names)))};"
        f"font-variation-settings:"
        f"{pack_font_settings(attention_input_names, attention_range, 0)}"
    )
    block_scope_css = (
        f'.block-scope{{{x_inputs};{n1_math};'
        f'timeline-scope:{",".join(attention_timeline_names)};'
        f"{attention_font_state}}}"
    )
    attention_layout_css = (
        ".attn-scroller{position:fixed;left:0;top:-40000px;"
        f"width:{attention_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".attn-track{{position:relative;width:{attention_track_width}px;height:1px}}"
        ".attn-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
    )
    attention_declarations: list[str] = []
    for index, progress in enumerate(attention_progress_names):
        raw_name = f"--attn-raw-{index:03d}"
        factor = attention_range * q_attention.scales[index]
        attention_declarations.append(
            f"{raw_name}:calc(({attention_viewport} / var({progress}) - "
            f"{attention_viewport}) * {UNITS_PER_EM} / {FONT_SIZE} - "
            f"{int(attention_base_rows[index])})"
        )
        attention_declarations.append(
            f"--attn-{index:03d}:calc(var({raw_name}) * {css_number(factor)} "
            f"+ ({css_number(composed_bias[index])}))"
        )
        attention_declarations.append(
            f"--r1-{index:03d}:calc(var(--x-{index:03d}) + "
            f"var(--attn-{index:03d}))"
        )
    attention_animation_rules: list[str] = []
    attention_math_rules: list[str] = []
    attention_consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(attention_consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
        attention_animation_rules.append(
            f".attn-result-{consumer}{{"
            f"animation-name:{','.join(attention_keyframe_names[start:stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(attention_timeline_names[start:stop])};"
            "animation-range:cover}"
        )
        attention_math_rules.append(
            f".attn-result-{consumer}{{"
            + ";".join(attention_declarations[start * 3 : stop * 3])
            + "}"
        )
    n2_math = ";".join(
        norm_declarations(
            "r1",
            "n2",
            data["ln2_gamma"],
            data["ln2_beta"],
            "mean2",
            "var2",
        )
    )
    n2_stage_css = (
        f'.n2-stage{{{n2_math};timeline-scope:{",".join(timeline_names)};'
        f"{inherited_font_state}}}"
    )
    attention_metrics: list[str] = []
    for output_index in range(WIDTH):
        characters = "".join(
            f"&#x{start + output_index:X};"
            for start in attention_fonts.codepoint_starts
        )
        attention_metrics.append(
            f'<i class="attn-metric" style="view-timeline:'
            f'{attention_timeline_names[output_index]} inline">{characters}</i>'
        )
    attention_scroller = (
        '<div class="attn-scroller"><div class="attn-track">'
        + "".join(attention_metrics)
        + "</div></div>"
    )
    n2_stage = (
        '<div class="n2-stage">'
        + shared_timeline_scroller
        + chained_fc_tree
        + "</div>"
    )
    attention_tree = n2_stage
    for consumer in reversed(range(attention_consumer_count)):
        attention_tree = (
            f'<div class="attn-result-{consumer}">{attention_tree}</div>'
        )
    block_css = (
        font_faces("attn-flat", attention_fonts)
        + faces
        + font_faces("mlp-flat", mlp_fonts)
        + attention_timeline_rules
        + timeline_rules
        + projection_timeline_rules
        + block_registrations
        + hidden_registrations
        + output_registrations
        + gelu_function
        + block_scope_css
        + attention_layout_css
        + n2_stage_css
        + layout_css
        + projection_layout_css
        + "".join(attention_animation_rules)
        + "".join(attention_math_rules)
        + animation_css
        + result_math_css
        + "".join(projection_animation_rules)
        + "".join(projection_math_rules)
        + visible_css
    )
    BLOCK_CSS_PATH.write_text(block_css)
    block_css_tag = hashlib.sha256(BLOCK_CSS_PATH.read_bytes()).hexdigest()[:12]
    BLOCK_HTML_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Complete one-token GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="view-timeline-block.css?v={block_css_tag}">'
        '<h1>Complete one-token GPT-2-small block in HTML/CSS</h1>'
        '<p>No JavaScript. LN1 → attention → residual → LN2 → MLP → residual.</p>'
        '<div class="block-scope">'
        + attention_scroller
        + attention_tree
        + "</div>"
    )
    BLOCK_REFERENCE_PATH.write_text(
        json.dumps(
            {
                "width": WIDTH,
                "hidden_width": MLP_WIDTH,
                "token_id": 15496,
                "layout_strategy": "flat-shared-scroller-complete-block",
                "n1": n1.tolist(),
                "attention": attention.tolist(),
                "residual": residual.tolist(),
                "n2": n2.tolist(),
                "hidden": hidden.tolist(),
                "output": final_output.tolist(),
                "html_bytes": BLOCK_HTML_PATH.stat().st_size,
                "css_bytes": BLOCK_CSS_PATH.stat().st_size,
                "font_bytes": sum(
                    (OUT / f"{name}.woff2").stat().st_size
                    for name in (
                        *attention_fonts.names,
                        *fonts.names,
                        *mlp_fonts.names,
                    )
                ),
            },
            indent=2,
        )
        + "\n"
    )
    packed_prefix_path = OUT / "composed-packed-prefix-1.html"
    if packed_prefix_path.exists():
        packed_prefix = packed_prefix_path.read_text()
        prefix_registrations = "".join(
            f'@property {name}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            for name in (
                "--mean1",
                "--var1",
                "--mean2",
                "--var2",
                *(
                    f"--{prefix}-{index:03d}"
                    for prefix in ("raw", "x", "n1", "r1", "n2")
                    for index in range(WIDTH)
                ),
            )
        )
        packed_after_attention = []
        for index in range(WIDTH):
            factor = attention_range * q_attention.scales[index]
            packed_after_attention.append(
                f"--r1-{index:03d}:calc(var(--x-{index:03d}) + "
                f"var(--raw-{index:03d}) * {css_number(factor)} + "
                f"({css_number(composed_bias[index])}))"
            )
        packed_after_attention.extend(
            norm_declarations(
                "r1",
                "n2",
                data["ln2_gamma"],
                data["ln2_beta"],
                "mean2",
                "var2",
            )
        )
        attention_prefix_css = (
            font_faces("composedattn", packed_attention_fonts)
            + prefix_registrations
            + f'.norm1{{{x_inputs};{n1_math}}}'
            + f'.after-attn{{{";".join(packed_after_attention)}}}'
            + "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}"
            + "body{margin:2rem}css-stage{display:block;position:relative}"
        )
        ATTENTION_PREFIX_CSS_PATH.write_text(attention_prefix_css)
        attention_prefix_tag = hashlib.sha256(
            ATTENTION_PREFIX_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        old_model_link_start = packed_prefix.index(
            '<link rel="stylesheet" href="model-composed.css'
        )
        old_model_link_end = packed_prefix.index(">", old_model_link_start) + 1
        packed_prefix = (
            packed_prefix[:old_model_link_start]
            + f'<link rel="stylesheet" href="view-timeline-attention-prefix.css?v={attention_prefix_tag}">'
            + packed_prefix[old_model_link_end:]
        )
        hybrid_stage_css = (
            f'.hybrid-mlp-stage{{timeline-scope:{",".join(timeline_names)};'
            f"{inherited_font_state}}}"
        )
        hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + timeline_rules
            + projection_timeline_rules
            + hidden_registrations
            + output_registrations
            + gelu_function
            + hybrid_stage_css
            + layout_css
            + projection_layout_css
            + animation_css
            + result_math_css
            + "".join(projection_animation_rules)
            + "".join(projection_math_rules)
            + visible_css
        )
        HYBRID_BLOCK_CSS_PATH.write_text(hybrid_css)
        hybrid_css_tag = hashlib.sha256(
            HYBRID_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        hybrid_css_link = (
            f'<link rel="stylesheet" href="view-timeline-block-hybrid.css?v={hybrid_css_tag}">'
        )
        hybrid_mlp = (
            '<div class="after-attn hybrid-mlp-stage" slot="next">'
            + shared_timeline_scroller
            + chained_fc_tree
            + "</div>"
        )
        hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            hybrid_mlp,
            1,
        )
        if hybrid_page == packed_prefix or 'id="final"' not in hybrid_page:
            raise ValueError("failed to attach flat MLP to packed attention prefix")
        HYBRID_BLOCK_HTML_PATH.write_text(hybrid_page)

        easing_hybrid_stage_css = (
            f'.hybrid-easing-mlp-stage{{timeline-scope:{",".join(timeline_names)};'
            f"{inherited_font_state};"
            f"--fc-ease-min:{css_number(easing_hidden_min)};"
            f"--fc-ease-max:{css_number(easing_hidden_max)};"
            f"--fc-gelu-ease:linear({','.join(easing_stops)})}}"
        )
        easing_hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + easing_timeline_rules
            + projection_timeline_rules
            + hidden_registrations
            + output_registrations
            + easing_hybrid_stage_css
            + layout_css
            + projection_layout_css
            + "".join(easing_animation_rules)
            + "".join(projection_animation_rules)
            + "".join(projection_math_rules)
            + visible_css
        )
        HYBRID_FC_EASING_BLOCK_CSS_PATH.write_text(easing_hybrid_css)
        easing_hybrid_css_tag = hashlib.sha256(
            HYBRID_FC_EASING_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        easing_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_EASING_BLOCK_CSS_PATH.name}'
            f'?v={easing_hybrid_css_tag}">'
        )
        easing_hybrid_mlp = (
            '<div class="after-attn hybrid-easing-mlp-stage" slot="next">'
            + easing_shared_timeline_scroller
            + chained_fc_tree
            + "</div>"
        )
        easing_hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + easing_hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            easing_hybrid_mlp,
            1,
        )
        if (
            easing_hybrid_page == packed_prefix
            or 'id="final"' not in easing_hybrid_page
        ):
            raise ValueError("failed to attach easing MLP to packed attention prefix")
        HYBRID_FC_EASING_BLOCK_HTML_PATH.write_text(easing_hybrid_page)
        HYBRID_FC_EASING_BLOCK_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "source": HYBRID_BLOCK_HTML_PATH.name,
                    "fc_easing_stops": FC_EASING_STOPS,
                    "fc_easing_z_min": easing_z_min,
                    "fc_easing_z_max": easing_z_max,
                    "fc_easing_min": easing_hidden_min,
                    "fc_easing_max": easing_hidden_max,
                    "expected": final_output.tolist(),
                    "html_bytes": HYBRID_FC_EASING_BLOCK_HTML_PATH.stat().st_size,
                    "css_bytes": HYBRID_FC_EASING_BLOCK_CSS_PATH.stat().st_size,
                },
                indent=2,
            )
            + "\n"
        )

        all_easing_hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + easing_timeline_rules
            + projection_easing_keyframes
            + hidden_registrations
            + output_registrations
            + easing_hybrid_stage_css
            + layout_css
            + projection_easing_layout_css
            + "".join(easing_animation_rules)
            + "".join(projection_easing_animation_rules)
            + visible_css
        )
        HYBRID_ALL_EASING_BLOCK_CSS_PATH.write_text(all_easing_hybrid_css)
        all_easing_hybrid_css_tag = hashlib.sha256(
            HYBRID_ALL_EASING_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        all_easing_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_ALL_EASING_BLOCK_CSS_PATH.name}'
            f'?v={all_easing_hybrid_css_tag}">'
        )
        all_easing_hybrid_mlp = (
            '<div class="after-attn hybrid-easing-mlp-stage" slot="next">'
            + easing_shared_timeline_scroller
            + all_easing_chained_fc_tree
            + "</div>"
        )
        all_easing_hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + all_easing_hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            all_easing_hybrid_mlp,
            1,
        )
        if (
            all_easing_hybrid_page == packed_prefix
            or 'id="final"' not in all_easing_hybrid_page
        ):
            raise ValueError(
                "failed to attach FC/projection easing MLP to attention prefix"
            )
        HYBRID_ALL_EASING_BLOCK_HTML_PATH.write_text(all_easing_hybrid_page)
        HYBRID_ALL_EASING_BLOCK_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "fc_easing_stops": FC_EASING_STOPS,
                    "projection_easing_stops": PROJECTION_EASING_STOPS,
                    "projection_easing_min": projection_easing_min,
                    "projection_easing_max": projection_easing_max,
                    "expected": final_output.tolist(),
                    "html_bytes": HYBRID_ALL_EASING_BLOCK_HTML_PATH.stat().st_size,
                    "css_bytes": HYBRID_ALL_EASING_BLOCK_CSS_PATH.stat().st_size,
                },
                indent=2,
            )
            + "\n"
        )

        global_projection_hybrid_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + easing_timeline_rules
            + projection_easing_keyframes
            + hidden_registrations
            + output_registrations
            + easing_hybrid_stage_css
            + layout_css
            + global_projection_layout_css
            + "".join(easing_animation_rules)
            + "".join(projection_easing_animation_rules)
            + visible_css
        )
        HYBRID_GLOBAL_PROJECTION_BLOCK_CSS_PATH.write_text(
            global_projection_hybrid_css
        )
        global_projection_hybrid_css_tag = hashlib.sha256(
            HYBRID_GLOBAL_PROJECTION_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        global_projection_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_GLOBAL_PROJECTION_BLOCK_CSS_PATH.name}'
            f'?v={global_projection_hybrid_css_tag}">'
        )
        global_projection_hybrid_mlp = (
            '<div class="after-attn hybrid-easing-mlp-stage" slot="next">'
            + easing_shared_timeline_scroller
            + global_projection_chained_fc_tree
            + "</div>"
        )
        global_projection_hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + global_projection_hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            global_projection_hybrid_mlp,
            1,
        )
        if (
            global_projection_hybrid_page == packed_prefix
            or 'id="final"' not in global_projection_hybrid_page
        ):
            raise ValueError("failed to attach global-run projection")
        HYBRID_GLOBAL_PROJECTION_BLOCK_HTML_PATH.write_text(
            global_projection_hybrid_page
        )
        HYBRID_GLOBAL_PROJECTION_BLOCK_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "fc_easing_stops": FC_EASING_STOPS,
                    "projection_easing_stops": PROJECTION_EASING_STOPS,
                    "projection_elements": WIDTH,
                    "projection_glyphs": WIDTH * len(global_projection_fonts.names),
                    "projection_child_pack_elements": 0,
                    "expected": final_output.tolist(),
                    "html_bytes": (
                        HYBRID_GLOBAL_PROJECTION_BLOCK_HTML_PATH.stat().st_size
                    ),
                    "css_bytes": (
                        HYBRID_GLOBAL_PROJECTION_BLOCK_CSS_PATH.stat().st_size
                    ),
                },
                indent=2,
            )
            + "\n"
        )

        paired_hybrid_stage_css = (
            f'.hybrid-paired-mlp-stage{{timeline-scope:{",".join(paired_timeline_names)};'
            f"{inherited_font_state}}}"
        )
        paired_fc_hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + paired_timeline_rules
            + projection_timeline_rules
            + hidden_registrations
            + output_registrations
            + gelu_function
            + paired_hybrid_stage_css
            + layout_css
            + range_pair_layout_css
            + projection_layout_css
            + "".join(paired_animation_rules)
            + "".join(paired_math_rules)
            + "".join(projection_animation_rules)
            + "".join(projection_math_rules)
            + visible_css
        )
        HYBRID_FC_PAIRED_BLOCK_CSS_PATH.write_text(paired_fc_hybrid_css)
        paired_fc_hybrid_css_tag = hashlib.sha256(
            HYBRID_FC_PAIRED_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        paired_fc_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="view-timeline-block-hybrid-fc-paired.css?v={paired_fc_hybrid_css_tag}">'
        )
        paired_fc_hybrid_mlp = (
            '<div class="after-attn hybrid-paired-mlp-stage" slot="next">'
            + paired_shared_timeline_scroller
            + paired_fc_only_chained_tree
            + "</div>"
        )
        paired_fc_hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + paired_fc_hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            paired_fc_hybrid_mlp,
            1,
        )
        if paired_fc_hybrid_page == packed_prefix or 'id="final"' not in paired_fc_hybrid_page:
            raise ValueError("failed to attach paired FC to packed attention prefix")
        HYBRID_FC_PAIRED_BLOCK_HTML_PATH.write_text(paired_fc_hybrid_page)

        packed4_hybrid_stage_css = (
            f'.hybrid-packed4-mlp-stage{{timeline-scope:'
            f'{",".join(packed4_timeline_names)};{inherited_font_state}}}'
        )
        packed4_hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + packed4_timeline_rules
            + projection_timeline_rules
            + output_registrations
            + gelu_function
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + projection_layout_css
            + "".join(packed4_projection_pack_rules)
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + "".join(projection_animation_rules)
            + "".join(projection_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_BLOCK_CSS_PATH.write_text(packed4_hybrid_css)
        packed4_hybrid_css_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="view-timeline-block-hybrid-fc-packed4.css?v={packed4_hybrid_css_tag}">'
        )
        packed4_hybrid_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_chained_tree
            + "</div>"
        )
        packed4_hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + packed4_hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hybrid_mlp,
            1,
        )
        if packed4_hybrid_page == packed_prefix or 'id="final"' not in packed4_hybrid_page:
            raise ValueError("failed to attach packed-four FC to attention prefix")
        HYBRID_FC_PACKED4_BLOCK_HTML_PATH.write_text(packed4_hybrid_page)

        packed4_hvar_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + packed4_timeline_rules
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + packed4_hvar_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_HVAR_CSS_PATH.write_text(packed4_hvar_css)
        packed4_hvar_css_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_HVAR_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hvar_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_HVAR_CSS_PATH.name}'
            f'?v={packed4_hvar_css_tag}">'
        )
        packed4_hvar_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_hvar_tree
            + "</div>"
        )
        packed4_hvar_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_hvar_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hvar_mlp,
            1,
        )
        if (
            packed4_hvar_page == packed_prefix
            or packed4_hvar_page.count('class="packed4-hvar-metric"') != WIDTH
        ):
            raise ValueError("failed to attach packed-four HVAR projection")
        HYBRID_FC_PACKED4_HVAR_HTML_PATH.write_text(packed4_hvar_page)
        HYBRID_FC_PACKED4_HVAR_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "width": WIDTH,
                    "mlpWidth": MLP_WIDTH,
                    "expectedPacked": packed4_final_output.tolist(),
                    "inputCases": case_inputs.tolist(),
                    "expectedPackedCases": [
                        value.tolist() for value in packed4_case_outputs
                    ],
                    "expectedDenseQuantizedCases": [
                        value.tolist() for value in dense_case_outputs
                    ],
                    "residualCases": [
                        value.tolist() for value in packed4_case_residuals
                    ],
                    "expectedDenseQuantized": final_output.tolist(),
                    "residual": residual.tolist(),
                    "projectionBias": data["mlp_proj_bias"].tolist(),
                    "projectionScales": q_mlp.scales.tolist(),
                    "projectionBases": global_projection_bases.tolist(),
                    "hiddenRange": hidden_range,
                    "unitsPerEm": UNITS_PER_EM,
                    "fontSize": FONT_SIZE,
                    "fcTimelines": packed4_group_count,
                    "outputTimelines": 0,
                    "projectionGlyphs": (
                        WIDTH * len(global_projection_fonts.names)
                    ),
                    "htmlBytes": HYBRID_FC_PACKED4_HVAR_HTML_PATH.stat().st_size,
                    "cssBytes": HYBRID_FC_PACKED4_HVAR_CSS_PATH.stat().st_size,
                    "fontBytes": sum(
                        (OUT / f"{name}.woff2").stat().st_size
                        for name in (
                            *fonts.names,
                            *global_projection_fonts.names,
                        )
                    ),
                },
                indent=2,
            )
            + "\n"
        )

        packed4_hvar_direct_ln_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + packed4_timeline_rules
            + direct_ln_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + packed4_hvar_direct_ln_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_HVAR_DIRECT_LN_CSS_PATH.write_text(
            packed4_hvar_direct_ln_css
        )
        packed4_hvar_direct_ln_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_HVAR_DIRECT_LN_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hvar_direct_ln_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_HVAR_DIRECT_LN_CSS_PATH.name}'
            f'?v={packed4_hvar_direct_ln_tag}">'
        )
        packed4_hvar_direct_ln_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_hvar_direct_ln_tree
            + "</div>"
        )
        packed4_hvar_direct_ln_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_hvar_direct_ln_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hvar_direct_ln_mlp,
            1,
        )
        if (
            packed4_hvar_direct_ln_page == packed_prefix
            or packed4_hvar_direct_ln_page.count(
                'class="packed4-hvar-metric"'
            ) != WIDTH
        ):
            raise ValueError("failed to attach direct HVAR layer norm")
        HYBRID_FC_PACKED4_HVAR_DIRECT_LN_HTML_PATH.write_text(
            packed4_hvar_direct_ln_page
        )
        expected_direct_ln_cases = [
            layer_norm(
                value,
                next_block_data["ln1_gamma"],
                next_block_data["ln1_beta"],
            )
            for value in packed4_case_outputs
        ]
        expected_dense_ln_cases = [
            layer_norm(
                value,
                next_block_data["ln1_gamma"],
                next_block_data["ln1_beta"],
            )
            for value in dense_case_outputs
        ]
        HYBRID_FC_PACKED4_HVAR_DIRECT_LN_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "width": WIDTH,
                    "inputCases": case_inputs.tolist(),
                    "expectedPackedLayerNormCases": [
                        value.tolist() for value in expected_direct_ln_cases
                    ],
                    "expectedDenseLayerNormCases": [
                        value.tolist() for value in expected_dense_ln_cases
                    ],
                    "htmlBytes": (
                        HYBRID_FC_PACKED4_HVAR_DIRECT_LN_HTML_PATH.stat().st_size
                    ),
                    "cssBytes": (
                        HYBRID_FC_PACKED4_HVAR_DIRECT_LN_CSS_PATH.stat().st_size
                    ),
                    "fontBytes": sum(
                        (OUT / f"{name}.woff2").stat().st_size
                        for name in (
                            *fonts.names,
                            *global_projection_fonts.names,
                        )
                    ),
                },
                indent=2,
            )
            + "\n"
        )

        packed4_hvar_gather_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + packed4_timeline_rules
            + hvar_gather_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + packed4_hvar_gather_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_HVAR_GATHER_CSS_PATH.write_text(
            packed4_hvar_gather_css
        )
        packed4_hvar_gather_css_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_HVAR_GATHER_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hvar_gather_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_HVAR_GATHER_CSS_PATH.name}'
            f'?v={packed4_hvar_gather_css_tag}">'
        )
        packed4_hvar_gather_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_hvar_gather_tree
            + "</div>"
        )
        packed4_hvar_gather_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_hvar_gather_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hvar_gather_mlp,
            1,
        )
        if (
            packed4_hvar_gather_page == packed_prefix
            or packed4_hvar_gather_page.count(
                'class="hvar-gather-source"'
            ) != WIDTH
        ):
            raise ValueError("failed to attach registered HVAR gather")
        HYBRID_FC_PACKED4_HVAR_GATHER_HTML_PATH.write_text(
            packed4_hvar_gather_page
        )
        expected_gather_cases = []
        for value in packed4_case_outputs:
            codes = np.rint(
                np.clip(
                    (value - hvar_gather_low) / hvar_gather_span,
                    0,
                    1,
                ) * hvar_gather_levels
            )
            expected_gather_cases.append(
                hvar_gather_low
                + codes * hvar_gather_span / hvar_gather_levels
            )
        HYBRID_FC_PACKED4_HVAR_GATHER_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "width": WIDTH,
                    "bits": 12,
                    "groups": hvar_gather_group_count,
                    "inputCases": case_inputs.tolist(),
                    "expectedPackedCases": [
                        value.tolist() for value in packed4_case_outputs
                    ],
                    "expectedDenseQuantizedCases": [
                        value.tolist() for value in dense_case_outputs
                    ],
                    "expectedGatherCases": [
                        value.tolist() for value in expected_gather_cases
                    ],
                    "low": hvar_gather_low.tolist(),
                    "span": hvar_gather_span.tolist(),
                    "htmlBytes": (
                        HYBRID_FC_PACKED4_HVAR_GATHER_HTML_PATH.stat().st_size
                    ),
                    "cssBytes": (
                        HYBRID_FC_PACKED4_HVAR_GATHER_CSS_PATH.stat().st_size
                    ),
                    "fontBytes": sum(
                        (OUT / f"{name}.woff2").stat().st_size
                        for name in (
                            *fonts.names,
                            *global_projection_fonts.names,
                        )
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        packed4_hvar_gather8_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + packed4_timeline_rules
            + hvar_gather_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + packed4_hvar_gather8_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_HVAR_GATHER8_CSS_PATH.write_text(
            packed4_hvar_gather8_css
        )
        packed4_hvar_gather8_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_HVAR_GATHER8_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hvar_gather8_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_HVAR_GATHER8_CSS_PATH.name}'
            f'?v={packed4_hvar_gather8_tag}">'
        )
        packed4_hvar_gather8_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_hvar_gather8_tree
            + "</div>"
        )
        packed4_hvar_gather8_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_hvar_gather8_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hvar_gather8_mlp,
            1,
        )
        if (
            packed4_hvar_gather8_page == packed_prefix
            or packed4_hvar_gather8_page.count(
                'class="hvar-gather8-source"'
            ) != WIDTH
        ):
            raise ValueError("failed to attach eight-bit HVAR gather")
        HYBRID_FC_PACKED4_HVAR_GATHER8_HTML_PATH.write_text(
            packed4_hvar_gather8_page
        )
        expected_gather8_cases = []
        for value in packed4_case_outputs:
            codes = np.rint(
                np.clip(
                    (value - hvar_gather_low) / hvar_gather_span,
                    0,
                    1,
                ) * hvar_gather8_levels
            )
            expected_gather8_cases.append(
                hvar_gather_low
                + codes * hvar_gather_span / hvar_gather8_levels
            )
        HYBRID_FC_PACKED4_HVAR_GATHER8_REFERENCE_PATH.write_text(
            json.dumps(
                {
                    "width": WIDTH,
                    "bits": 8,
                    "groups": hvar_gather8_group_count,
                    "inputCases": case_inputs.tolist(),
                    "expectedPackedCases": [
                        value.tolist() for value in packed4_case_outputs
                    ],
                    "expectedDenseQuantizedCases": [
                        value.tolist() for value in dense_case_outputs
                    ],
                    "expectedGatherCases": [
                        value.tolist() for value in expected_gather8_cases
                    ],
                    "htmlBytes": (
                        HYBRID_FC_PACKED4_HVAR_GATHER8_HTML_PATH.stat().st_size
                    ),
                    "cssBytes": (
                        HYBRID_FC_PACKED4_HVAR_GATHER8_CSS_PATH.stat().st_size
                    ),
                    "fontBytes": sum(
                        (OUT / f"{name}.woff2").stat().st_size
                        for name in (
                            *fonts.names,
                            *global_projection_fonts.names,
                        )
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        packed4_hvar_gather_flat_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + packed4_timeline_rules
            + hvar_gather_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + packed4_hvar_gather_flat_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_HVAR_GATHER_FLAT_CSS_PATH.write_text(
            packed4_hvar_gather_flat_css
        )
        packed4_hvar_gather_flat_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_HVAR_GATHER_FLAT_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hvar_gather_flat_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_HVAR_GATHER_FLAT_CSS_PATH.name}'
            f'?v={packed4_hvar_gather_flat_tag}">'
        )
        packed4_hvar_gather_flat_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_hvar_gather_flat_tree
            + "</div>"
        )
        packed4_hvar_gather_flat_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_hvar_gather_flat_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hvar_gather_flat_mlp,
            1,
        )
        if (
            packed4_hvar_gather_flat_page == packed_prefix
            or packed4_hvar_gather_flat_page.count(
                'class="hvar-gather-source"'
            ) != WIDTH
        ):
            raise ValueError("failed to attach flat registered HVAR gather")
        HYBRID_FC_PACKED4_HVAR_GATHER_FLAT_HTML_PATH.write_text(
            packed4_hvar_gather_flat_page
        )
        packed4_hvar_gather_fixed_css = (
            faces
            + font_faces("mlp-run", global_projection_fonts)
            + packed4_timeline_rules
            + hvar_gather_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + packed4_hvar_gather_fixed_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_HVAR_GATHER_FIXED_CSS_PATH.write_text(
            packed4_hvar_gather_fixed_css
        )
        packed4_hvar_gather_fixed_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_HVAR_GATHER_FIXED_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_hvar_gather_fixed_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_HVAR_GATHER_FIXED_CSS_PATH.name}'
            f'?v={packed4_hvar_gather_fixed_tag}">'
        )
        packed4_hvar_gather_fixed_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_hvar_gather_fixed_tree
            + "</div>"
        )
        packed4_hvar_gather_fixed_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_hvar_gather_fixed_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_hvar_gather_fixed_mlp,
            1,
        )
        if (
            packed4_hvar_gather_fixed_page == packed_prefix
            or packed4_hvar_gather_fixed_page.count(
                'class="hvar-gather-source"'
            ) != WIDTH
        ):
            raise ValueError("failed to attach fixed registered HVAR gather")
        HYBRID_FC_PACKED4_HVAR_GATHER_FIXED_HTML_PATH.write_text(
            packed4_hvar_gather_fixed_page
        )

        packed4_paired_output_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + packed4_timeline_rules
            + paired_projection_timeline_rules
            + output_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + projection_layout_css
            + paired_projection_layout_css
            + "".join(packed4_projection_pack_rules)
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + "".join(paired_projection_animation_rules)
            + "".join(paired_projection_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_PAIRED_OUTPUT_CSS_PATH.write_text(
            packed4_paired_output_css
        )
        packed4_paired_output_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_PAIRED_OUTPUT_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_paired_output_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED4_PAIRED_OUTPUT_CSS_PATH.name}'
            f'?v={packed4_paired_output_tag}">'
        )
        packed4_paired_output_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_paired_output_tree
            + "</div>"
        )
        packed4_paired_output_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_paired_output_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_paired_output_mlp,
            1,
        )
        if (
            packed4_paired_output_page == packed_prefix
            or 'id="final"' not in packed4_paired_output_page
        ):
            raise ValueError("failed to attach paired block-output transport")
        HYBRID_FC_PACKED4_PAIRED_OUTPUT_HTML_PATH.write_text(
            packed4_paired_output_page
        )

        packed4_transport_css = (
            faces
            + packed4_timeline_rules
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED4_TRANSPORT_CSS_PATH.write_text(packed4_transport_css)
        packed4_transport_css_tag = hashlib.sha256(
            HYBRID_FC_PACKED4_TRANSPORT_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_transport_link = (
            '<link rel="stylesheet" '
            f'href="view-timeline-block-hybrid-fc-packed4-transport.css?v={packed4_transport_css_tag}">'
        )
        packed4_transport_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_transport_tree
            + "</div>"
        )
        packed4_transport_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_transport_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_transport_mlp,
            1,
        )
        if packed4_transport_page == packed_prefix or 'id="final"' not in packed4_transport_page:
            raise ValueError("failed to attach packed-four transport probe")
        HYBRID_FC_PACKED4_TRANSPORT_HTML_PATH.write_text(packed4_transport_page)

        packed6_hybrid_stage_css = (
            f'.hybrid-packed6-mlp-stage{{timeline-scope:'
            f'{",".join(packed6_timeline_names)};{inherited_font_state}}}'
        )
        packed6_hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + packed6_timeline_rules
            + projection_timeline_rules
            + output_registrations
            + packed6_hybrid_stage_css
            + packed6_layout_css
            + projection_layout_css
            + "".join(packed6_projection_pack_rules)
            + "".join(packed6_animation_rules)
            + "".join(packed6_math_rules)
            + "".join(projection_animation_rules)
            + "".join(packed6_projection_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED6_BLOCK_CSS_PATH.write_text(packed6_hybrid_css)
        packed6_hybrid_css_tag = hashlib.sha256(
            HYBRID_FC_PACKED6_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed6_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED6_BLOCK_CSS_PATH.name}?v={packed6_hybrid_css_tag}">'
        )
        packed6_hybrid_mlp = (
            '<div class="after-attn hybrid-packed6-mlp-stage" slot="next">'
            + packed6_scroller
            + packed6_chained_tree
            + "</div>"
        )
        packed6_hybrid_page = packed_prefix.replace(
            "</title>", "</title>" + packed6_hybrid_css_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed6_hybrid_mlp,
            1,
        )
        if packed6_hybrid_page == packed_prefix or 'id="final"' not in packed6_hybrid_page:
            raise ValueError("failed to attach packed-six FC to attention prefix")
        HYBRID_FC_PACKED6_BLOCK_HTML_PATH.write_text(packed6_hybrid_page)

        if BUILD_ADDITIVE_PROJECTION:
            if PACKED6_SCHEME != "uniform6":
                raise ValueError(
                    "BUILD_ADDITIVE_PROJECTION requires "
                    "VIEW_TIMELINE_PACKED6_SCHEME=uniform6"
                )
            axis_tags = [f"A{index:03d}" for index in range(WIDTH)]
            zero_axis_settings = ",".join(
                f'"{axis}" 0' for axis in axis_tags
            )
            projection_base = (
                data["mlp_proj_bias"]
                + packed6_hidden_min * np.sum(q_mlp.reconstructed, axis=1)
            )
            base_axis_settings = ",".join(
                f'"{axis}" calc(var(--r1-{index:03d}) + '
                f'{css_number(projection_base[index])})'
                for index, axis in enumerate(axis_tags)
            )
            additive_keyframes = []
            for hidden_index in range(MLP_WIDTH):
                column = q_mlp.reconstructed[:, hidden_index] * packed6_hidden_span
                column_settings = ",".join(
                    f'"{axis}" {css_number(column[output])}'
                    for output, axis in enumerate(axis_tags)
                )
                additive_keyframes.append(
                    f"@keyframes ap{hidden_index}{{from{{font-variation-settings:"
                    f"var(--ap-zero)}}to{{font-variation-settings:"
                    f"{column_settings}}}}}"
                )
            additive_names = ",".join(
                f"ap{index}" for index in range(MLP_WIDTH)
            )
            additive_delays = ",".join(
                f"calc(-1s * clamp(0,({packed6_hidden_expression(index)} - "
                f"({css_number(packed6_hidden_min)})) / "
                f"{css_number(packed6_hidden_span)},1))"
                for index in range(MLP_WIDTH)
            )
            additive_projection_css = (
                ".additive-projection{display:block;--ap-zero:"
                + zero_axis_settings
                + ";font-variation-settings:"
                + base_axis_settings
                + ";animation-name:"
                + additive_names
                + ";animation-duration:1s;animation-delay:"
                + additive_delays
                + ";animation-play-state:paused;animation-timing-function:linear;"
                "animation-fill-mode:both;animation-composition:add}"
                + "".join(additive_keyframes)
            )
            additive_css = (
                faces
                + packed6_timeline_rules
                + packed6_hybrid_stage_css
                + packed6_layout_css
                + "".join(packed6_animation_rules)
                + "".join(packed6_math_rules)
                + additive_projection_css
                + visible_css
            )
            ADDITIVE_PROJECTION_BLOCK_CSS_PATH.write_text(additive_css)
            additive_css_tag = hashlib.sha256(
                ADDITIVE_PROJECTION_BLOCK_CSS_PATH.read_bytes()
            ).hexdigest()[:12]
            additive_css_link = (
                '<link rel="stylesheet" '
                f'href="{ADDITIVE_PROJECTION_BLOCK_CSS_PATH.name}?v={additive_css_tag}">'
            )
            additive_tree = '<output id="final" class="additive-projection"></output>'
            for consumer in reversed(range(packed6_consumer_count)):
                additive_tree = (
                    f'<div class="q6-result-{consumer}">{additive_tree}</div>'
                )
            additive_mlp = (
                '<div class="after-attn hybrid-packed6-mlp-stage" slot="next">'
                + packed6_scroller
                + additive_tree
                + "</div>"
            )
            additive_page = packed_prefix.replace(
                "</title>", "</title>" + additive_css_link, 1
            ).replace(
                '<output id="final" class="final" slot="next"></output>',
                additive_mlp,
                1,
            )
            if additive_page == packed_prefix or 'id="final"' not in additive_page:
                raise ValueError("failed to attach additive projection")
            ADDITIVE_PROJECTION_BLOCK_HTML_PATH.write_text(additive_page)

        packed6_transport_css = (
            faces
            + packed6_timeline_rules
            + packed6_hybrid_stage_css
            + packed6_layout_css
            + "".join(packed6_animation_rules)
            + "".join(packed6_math_rules)
            + visible_css
        )
        HYBRID_FC_PACKED6_TRANSPORT_CSS_PATH.write_text(packed6_transport_css)
        packed6_transport_css_tag = hashlib.sha256(
            HYBRID_FC_PACKED6_TRANSPORT_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed6_transport_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_PACKED6_TRANSPORT_CSS_PATH.name}?v={packed6_transport_css_tag}">'
        )
        packed6_transport_mlp = (
            '<div class="after-attn hybrid-packed6-mlp-stage" slot="next">'
            + packed6_scroller
            + packed6_transport_tree
            + "</div>"
        )
        packed6_transport_page = packed_prefix.replace(
            "</title>", "</title>" + packed6_transport_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed6_transport_mlp,
            1,
        )
        if packed6_transport_page == packed_prefix or 'id="final"' not in packed6_transport_page:
            raise ValueError("failed to attach packed-six transport probe")
        HYBRID_FC_PACKED6_TRANSPORT_HTML_PATH.write_text(packed6_transport_page)

        hetero_timeline_names = (
            list(hetero_low["timelines"]) + list(hetero_high["timelines"])
        )
        hetero_stage_css = (
            f'.hybrid-hetero58-mlp-stage{{timeline-scope:'
            f'{",".join(hetero_timeline_names)};{inherited_font_state}}}'
        )
        hetero_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + str(hetero_low["timeline_rules"])
            + str(hetero_high["timeline_rules"])
            + projection_timeline_rules
            + output_registrations
            + hetero_stage_css
            + str(hetero_low["layout_css"])
            + str(hetero_high["layout_css"])
            + projection_layout_css
            + "".join(hetero_projection_pack_rules)
            + "".join(hetero_low["animation_rules"])
            + "".join(hetero_high["animation_rules"])
            + "".join(hetero_low["math_rules"])
            + "".join(hetero_high["math_rules"])
            + "".join(projection_animation_rules)
            + "".join(projection_math_rules)
            + visible_css
        )
        HYBRID_FC_HETERO58_BLOCK_CSS_PATH.write_text(hetero_css)
        hetero_css_tag = hashlib.sha256(
            HYBRID_FC_HETERO58_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        hetero_css_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_HETERO58_BLOCK_CSS_PATH.name}?v={hetero_css_tag}">'
        )
        hetero_mlp = (
            '<div class="after-attn hybrid-hetero58-mlp-stage" slot="next">'
            + str(hetero_low["scroller"])
            + str(hetero_high["scroller"])
            + hetero_chained_tree
            + "</div>"
        )
        hetero_page = packed_prefix.replace(
            "</title>", "</title>" + hetero_css_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            hetero_mlp,
            1,
        )
        if hetero_page == packed_prefix or 'id="final"' not in hetero_page:
            raise ValueError("failed to attach heterogeneous FC transport")
        HYBRID_FC_HETERO58_BLOCK_HTML_PATH.write_text(hetero_page)

        sensitivity_timeline_names = [
            timeline
            for _, bank in sensitivity_banks
            for timeline in bank["timelines"]
        ]
        sensitivity_stage_css = (
            f'.hybrid-sensitivity3456-mlp-stage{{timeline-scope:'
            f'{",".join(sensitivity_timeline_names)};{inherited_font_state}}}'
        )
        sensitivity_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + "".join(str(bank["timeline_rules"]) for _, bank in sensitivity_banks)
            + projection_timeline_rules
            + output_registrations
            + sensitivity_stage_css
            + "".join(str(bank["layout_css"]) for _, bank in sensitivity_banks)
            + projection_layout_css
            + "".join(sensitivity_projection_pack_rules)
            + "".join(
                rule
                for _, bank in sensitivity_banks
                for rule in bank["animation_rules"]
            )
            + "".join(
                rule
                for _, bank in sensitivity_banks
                for rule in bank["math_rules"]
            )
            + "".join(projection_animation_rules)
            + "".join(projection_math_rules)
            + visible_css
        )
        HYBRID_FC_SENSITIVITY3456_BLOCK_CSS_PATH.write_text(sensitivity_css)
        sensitivity_css_tag = hashlib.sha256(
            HYBRID_FC_SENSITIVITY3456_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        sensitivity_css_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_FC_SENSITIVITY3456_BLOCK_CSS_PATH.name}?v={sensitivity_css_tag}">'
        )
        sensitivity_mlp = (
            '<div class="after-attn hybrid-sensitivity3456-mlp-stage" slot="next">'
            + "".join(str(bank["scroller"]) for _, bank in sensitivity_banks)
            + sensitivity_chained_tree
            + "</div>"
        )
        sensitivity_page = packed_prefix.replace(
            "</title>", "</title>" + sensitivity_css_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            sensitivity_mlp,
            1,
        )
        if sensitivity_page == packed_prefix or 'id="final"' not in sensitivity_page:
            raise ValueError("failed to attach sensitivity-tiered FC transport")
        HYBRID_FC_SENSITIVITY3456_BLOCK_HTML_PATH.write_text(sensitivity_page)

        packed4_chain_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + packed4_timeline_rules
            + output_pack_timeline_rules
            + output_registrations
            + packed4_hybrid_stage_css
            + packed4_layout_css
            + projection_layout_css
            + "".join(packed4_projection_pack_rules)
            + output_pack_layout_css
            + "".join(packed4_animation_rules)
            + "".join(packed4_math_rules)
            + "".join(output_pack_animation_rules)
            + "".join(output_pack_math_rules)
            + visible_css
        )
        HYBRID_PACKED4_CHAIN_CSS_PATH.write_text(packed4_chain_css)
        packed4_chain_css_tag = hashlib.sha256(
            HYBRID_PACKED4_CHAIN_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        packed4_chain_link = (
            '<link rel="stylesheet" '
            f'href="{HYBRID_PACKED4_CHAIN_CSS_PATH.name}?v={packed4_chain_css_tag}">'
        )
        packed4_chain_mlp = (
            '<div class="after-attn hybrid-packed4-mlp-stage" slot="next">'
            + packed4_scroller
            + packed4_output_packed_tree
            + "</div>"
        )
        packed4_chain_page = packed_prefix.replace(
            "</title>", "</title>" + packed4_chain_link, 1
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            packed4_chain_mlp,
            1,
        )
        if packed4_chain_page == packed_prefix or 'id="final"' not in packed4_chain_page:
            raise ValueError("failed to attach packed-four block chain")
        HYBRID_PACKED4_CHAIN_HTML_PATH.write_text(packed4_chain_page)

        paired_hybrid_css = (
            faces
            + font_faces("mlp-flat", mlp_fonts)
            + paired_timeline_rules
            + projection_timeline_rules
            + hidden_registrations
            + output_registrations
            + gelu_function
            + paired_hybrid_stage_css
            + layout_css
            + range_pair_layout_css
            + projection_layout_css
            + paired_projection_layout_css
            + "".join(paired_animation_rules)
            + "".join(paired_math_rules)
            + paired_projection_timeline_rules
            + "".join(paired_projection_animation_rules)
            + "".join(paired_projection_math_rules)
            + visible_css
        )
        HYBRID_PAIRED_BLOCK_CSS_PATH.write_text(paired_hybrid_css)
        paired_hybrid_css_tag = hashlib.sha256(
            HYBRID_PAIRED_BLOCK_CSS_PATH.read_bytes()
        ).hexdigest()[:12]
        paired_hybrid_css_link = (
            '<link rel="stylesheet" '
            f'href="view-timeline-block-hybrid-paired.css?v={paired_hybrid_css_tag}">'
        )
        paired_hybrid_mlp = (
            '<div class="after-attn hybrid-paired-mlp-stage" slot="next">'
            + paired_shared_timeline_scroller
            + paired_chained_fc_tree
            + "</div>"
        )
        paired_hybrid_page = packed_prefix.replace(
            "</title>",
            "</title>" + paired_hybrid_css_link,
            1,
        ).replace(
            '<output id="final" class="final" slot="next"></output>',
            paired_hybrid_mlp,
            1,
        )
        if paired_hybrid_page == packed_prefix or 'id="final"' not in paired_hybrid_page:
            raise ValueError("failed to attach paired MLP to packed attention prefix")
        HYBRID_PAIRED_BLOCK_HTML_PATH.write_text(paired_hybrid_page)
    print(
        {
            "html_bytes": HTML_PATH.stat().st_size,
            "css_bytes": CSS_PATH.stat().st_size,
            "font_count": len(fonts.names),
            "expected_hidden_max": float(np.max(hidden)),
            "mlp_html_bytes": MLP_HTML_PATH.stat().st_size,
            "mlp_css_bytes": MLP_CSS_PATH.stat().st_size,
            "mlp_font_count": len(fonts.names) + len(mlp_fonts.names),
            "block_html_bytes": BLOCK_HTML_PATH.stat().st_size,
            "block_css_bytes": BLOCK_CSS_PATH.stat().st_size,
            "block_font_count": (
                len(attention_fonts.names) + len(fonts.names) + len(mlp_fonts.names)
            ),
        }
    )


if __name__ == "__main__":
    main()
