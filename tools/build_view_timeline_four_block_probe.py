#!/usr/bin/env python3
"""Build a real one-token GPT-2 h.0 -> h.1 -> h.2 -> h.3 CSS probe.

This is deliberately a truncated, four-block diagnostic.  It starts with the
existing faithful h.0 page and appends checkpoint layers h.1, h.2, and h.3.
It does not attach ln_f or the vocabulary head and is not full GPT-2 inference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import build_gpt2_block_css as block_css
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
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


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "experiments" / "gpt2-block-css"
OUT = ROOT / "experiments" / "gpt2-four-block-event-scheduler"
SOURCE_STEM = "view-timeline-block-hybrid-global-projection-easing"
SOURCE_HTML = SOURCE_DIR / f"{SOURCE_STEM}.html"
SOURCE_REFERENCE = SOURCE_DIR / "view-timeline-block-reference.json"
CONNECTED_HTML = OUT / "view-timeline-four-block-connected.html"
STYLESHEET = OUT / "view-timeline-four-block.css"
REFERENCE = OUT / "view-timeline-four-block-reference.json"
MANIFEST = OUT / "view-timeline-four-block-manifest.json"
SOURCE_LEAF = '<output id="final" class="proj-result-5"></output>'
OUTPUTS_PER_CONSUMER = 128
FC_EASING_STOPS = 513
PROJECTION_EASING_STOPS = 257
PROJECTION_MIN = -128.0
PROJECTION_MAX = 768.0


@dataclass(frozen=True)
class Stage:
    layer: int
    prefix: str
    source_prefix: str
    html: str
    css: str
    expected: np.ndarray
    attention_residual: np.ndarray
    normalized2: np.ndarray
    hidden: np.ndarray
    font_names: tuple[str, ...]
    font_bytes: int
    ttf_bytes: int
    viewports: dict[str, int]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def hrefs_from_source(source: str) -> str:
    """Make source-page stylesheet links valid from the new experiment dir."""
    return re.sub(
        r'href="(?![a-z]+:|/|\.\./)([^"]+)"',
        r'href="../gpt2-block-css/\1"',
        source,
        flags=re.IGNORECASE,
    )


def expected_font_files(stem: str, columns: int) -> list[Path]:
    return [
        OUT / f"{stem}-s{index}.woff2"
        for index in range(math.ceil(columns / 256))
    ]


def build_fonts(stem: str, codes: np.ndarray, *, global_axes: bool):
    expected = expected_font_files(stem, codes.shape[1])
    rebuild = not all(path.exists() for path in expected)
    return block_css.build_font_group(
        stem,
        codes,
        rebuild=rebuild,
        row_specific_bases=True,
        global_axis_offset=0 if global_axes else None,
    )


def registrations(prefix: str) -> str:
    return (
        f'@property --{prefix}-mean1{{syntax:"<number>";inherits:true;initial-value:0}}'
        f'@property --{prefix}-var1{{syntax:"<number>";inherits:true;initial-value:0}}'
        f'@property --{prefix}-mean2{{syntax:"<number>";inherits:true;initial-value:0}}'
        f'@property --{prefix}-var2{{syntax:"<number>";inherits:true;initial-value:0}}'
        + "".join(
            f'@property --{prefix}-n1-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --{prefix}-attn-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --{prefix}-n2-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --{prefix}-final-{index:03d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --{prefix}ap{index}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            f'@property --{prefix}pp{index}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for index in range(WIDTH)
        )
        + "".join(
            f'@property --{prefix}-hidden-{index:04d}'
            '{syntax:"<number>";inherits:true;initial-value:0}'
            f'@property --{prefix}fp{index}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for index in range(MLP_WIDTH)
        )
    )


def result_tree(prefix: str, family: str, count: int, child: str) -> str:
    tree = f'<div class="{prefix}{family}-result-{count - 1}">{child}</div>'
    for consumer in reversed(range(count - 1)):
        tree = f'<div class="{prefix}{family}-result-{consumer}">{tree}</div>'
    return tree


def animation_rules(
    prefix: str,
    family: str,
    keyframes: list[str],
    timelines: list[str],
    count: int,
    timing: str,
) -> str:
    rules = []
    for consumer in range(count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, len(keyframes))
        rules.append(
            f".{prefix}{family}-result-{consumer}{{animation-name:"
            f"{','.join(keyframes[start:stop])};animation-duration:1s;"
            f"animation-timing-function:{timing};animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[start:stop])};"
            "animation-range:cover}"
        )
    return "".join(rules)


def build_stage(layer: int, input_vector: np.ndarray) -> Stage:
    prefix = f"b{layer}"
    source_prefix = "out" if layer == 1 else f"b{layer - 1}-final"
    data = model_data(layer, input_vector=input_vector)

    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    normalized1 = layer_norm(
        input_vector, data["ln1_gamma"], data["ln1_beta"]
    )
    attention_range = float(np.max(np.abs(normalized1)) * 1.01)
    attention_residual = (
        input_vector + q_attention.reconstructed @ normalized1 + composed_bias
    )

    normalized2 = layer_norm(
        attention_residual, data["ln2_gamma"], data["ln2_beta"]
    )
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    fc_range = float(np.max(np.abs(normalized2)) * 1.01)
    preactivation = q_fc.reconstructed @ normalized2 + data["fc_bias"]
    hidden = gelu_new(preactivation)
    hidden_range = float(np.max(np.abs(hidden)) * 1.01)

    q_projection = quantize_float_rows(
        data["mlp_proj_weight"], bits=QUANT_BITS
    )
    expected = (
        attention_residual
        + q_projection.reconstructed @ hidden
        + data["mlp_proj_bias"]
    )
    arrays = [normalized1, attention_residual, normalized2, hidden, expected]
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ValueError(f"non-finite numerical oracle in checkpoint layer h.{layer}")

    attention_fonts = build_fonts(
        f"four-block-{prefix}-attn-rowbase", q_attention.codes, global_axes=False
    )
    fc_fonts = build_fonts(
        f"four-block-{prefix}-fc-rowbase", q_fc.codes, global_axes=False
    )
    projection_fonts = build_fonts(
        f"four-block-{prefix}-projection-global-rowbase",
        q_projection.codes,
        global_axes=True,
    )
    if any(
        group.row_bases is None
        for group in (attention_fonts, fc_fonts, projection_fonts)
    ):
        raise ValueError(f"row-specific metric bases missing for {prefix}")

    attention_bases = np.sum(np.stack(attention_fonts.row_bases), axis=0)
    fc_bases = np.sum(np.stack(fc_fonts.row_bases), axis=0)
    projection_bases = np.sum(np.stack(projection_fonts.row_bases), axis=0)

    def viewport_for(bases: np.ndarray) -> int:
        pixels = float(np.max(bases)) * FONT_SIZE / UNITS_PER_EM
        return 2 ** math.ceil(math.log2(max(1024, pixels * 1.25)))

    attention_viewport = viewport_for(attention_bases)
    fc_viewport = viewport_for(fc_bases)
    projection_viewport = viewport_for(projection_bases)

    attention_timelines = [f"--{prefix}at{index}" for index in range(WIDTH)]
    attention_progress = [f"--{prefix}ap{index}" for index in range(WIDTH)]
    attention_keyframes = [f"{prefix}ak{index}" for index in range(WIDTH)]
    fc_timelines = [f"--{prefix}ft{index}" for index in range(MLP_WIDTH)]
    fc_keyframes = [f"{prefix}fk{index}" for index in range(MLP_WIDTH)]
    projection_timelines = [f"--{prefix}pt{index}" for index in range(WIDTH)]
    projection_keyframes = [f"{prefix}pk{index}" for index in range(WIDTH)]

    attention_keyframe_css = "".join(
        f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for keyframe, progress in zip(
            attention_keyframes, attention_progress, strict=True
        )
    )
    fc_keyframe_css = "".join(
        f"@keyframes {keyframe}{{"
        f"from{{--{prefix}-hidden-{index:04d}:var(--{prefix}-gelu-min)}}"
        f"to{{--{prefix}-hidden-{index:04d}:var(--{prefix}-gelu-max)}}}}"
        for index, keyframe in enumerate(fc_keyframes)
    )
    projection_keyframe_css = "".join(
        f"@keyframes {keyframe}{{"
        f"from{{--{prefix}-final-{index:03d}:{PROJECTION_MIN:g}}}"
        f"to{{--{prefix}-final-{index:03d}:{PROJECTION_MAX:g}}}}}"
        for index, keyframe in enumerate(projection_keyframes)
    )

    normalization1 = norm_declarations(
        source_prefix,
        f"{prefix}-n1",
        data["ln1_gamma"],
        data["ln1_beta"],
        f"{prefix}-mean1",
        f"{prefix}-var1",
    )
    normalization2 = norm_declarations(
        f"{prefix}-attn",
        f"{prefix}-n2",
        data["ln2_gamma"],
        data["ln2_beta"],
        f"{prefix}-mean2",
        f"{prefix}-var2",
    )

    attention_settings = pack_font_settings(
        [f"--{prefix}-n1-{index:03d}" for index in range(WIDTH)],
        attention_range,
        0,
    )
    attention_families = ",".join(
        f"{prefix}attnS{index}" for index in range(len(attention_fonts.names))
    )
    attention_declarations = []
    for output, progress in enumerate(attention_progress):
        raw = (
            f"(({attention_viewport} / var({progress}) - {attention_viewport}) * "
            f"{UNITS_PER_EM} / {FONT_SIZE} - {int(attention_bases[output])})"
        )
        factor = attention_range * q_attention.scales[output]
        attention_declarations.append(
            f"--{prefix}-attn-{output:03d}:calc("
            f"var(--{source_prefix}-{output:03d}) + {raw} * "
            f"{css_number(factor)} + ({css_number(composed_bias[output])}))"
        )
    attention_math = []
    attention_consumers = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(attention_consumers):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
        attention_math.append(
            f".{prefix}attn-result-{consumer}{{"
            f"{';'.join(attention_declarations[start:stop])}}}"
        )
    attention_metrics = "".join(
        f'<span class="{prefix}attn-metric" style="view-timeline:{timeline} inline">'
        + "".join(
            f"&#x{start + output:X};" for start in attention_fonts.codepoint_starts
        )
        + "</span>"
        for output, timeline in enumerate(attention_timelines)
    )

    easing_z = np.linspace(24.0, -16.0, FC_EASING_STOPS)
    easing_hidden = gelu_new(easing_z)
    dense_hidden = gelu_new(np.linspace(-16.0, 24.0, 8193))
    gelu_min = float(np.min(dense_hidden))
    gelu_max = float(np.max(dense_hidden))
    fc_geometry_offset = fc_viewport // 2
    fc_geometry_scale = fc_viewport // 32
    easing_output = (easing_hidden - gelu_min) / (gelu_max - gelu_min)
    easing_progress = fc_viewport / (
        fc_viewport + fc_geometry_offset + fc_geometry_scale * easing_z
    )
    gelu_stops = [
        f"{css_number(easing_output[0])} 0%",
        *(
            f"{css_number(value)} {css_number(progress * 100)}%"
            for progress, value in zip(
                easing_progress, easing_output, strict=True
            )
        ),
    ]
    fc_settings = pack_font_settings(
        [f"--{prefix}-n2-{index:03d}" for index in range(WIDTH)], fc_range, 0
    )
    fc_families = ",".join(
        f"{prefix}fcS{index}" for index in range(len(fc_fonts.names))
    )
    fc_metrics = []
    for output, timeline in enumerate(fc_timelines):
        factor = fc_range * q_fc.scales[output]
        multiplier = fc_geometry_scale * factor * UNITS_PER_EM / FONT_SIZE
        offset = (
            fc_geometry_offset
            + fc_geometry_scale * data["fc_bias"][output]
            - fc_geometry_scale * factor * fc_bases[output]
        )
        characters = "".join(
            f"&#x{start + output:X};" for start in fc_fonts.codepoint_starts
        )
        fc_metrics.append(
            f'<span class="{prefix}fc-metric" style="view-timeline:{timeline} inline;'
            "width:calc-size(max-content,"
            f'size * {css_number(multiplier)} + {css_number(offset)}px)">'
            f"{characters}</span>"
        )
    fc_consumers = math.ceil(MLP_WIDTH / OUTPUTS_PER_CONSUMER)

    projection_geometry_scale = (
        projection_viewport * 0.5 / (PROJECTION_MAX - PROJECTION_MIN)
    )
    projection_geometry_offset = (
        projection_viewport * 0.25
        - projection_geometry_scale * PROJECTION_MIN
    )
    projection_z = np.linspace(
        PROJECTION_MAX, PROJECTION_MIN, PROJECTION_EASING_STOPS
    )
    projection_output = (
        (projection_z - PROJECTION_MIN) / (PROJECTION_MAX - PROJECTION_MIN)
    )
    projection_progress = projection_viewport / (
        projection_viewport
        + projection_geometry_offset
        + projection_geometry_scale * projection_z
    )
    projection_stops = [
        f"{css_number(projection_output[0])} 0%",
        *(
            f"{css_number(value)} {css_number(progress * 100)}%"
            for progress, value in zip(
                projection_progress, projection_output, strict=True
            )
        ),
    ]
    projection_families = ",".join(
        f"{prefix}projS{index}" for index in range(len(projection_fonts.names))
    )
    projection_settings = ",".join(
        f'"{global_axis_tag(index)}" '
        f"calc(var(--{prefix}-hidden-{index:04d}) / {css_number(hidden_range)})"
        for index in range(MLP_WIDTH)
    )
    projection_metrics = []
    for output, timeline in enumerate(projection_timelines):
        factor = hidden_range * q_projection.scales[output]
        multiplier = (
            projection_geometry_scale * factor * UNITS_PER_EM / FONT_SIZE
        )
        constant = (
            projection_geometry_offset
            + projection_geometry_scale
            * (data["mlp_proj_bias"][output] - factor * projection_bases[output])
        )
        characters = "".join(
            f"&#x{start + output:X};"
            for start in projection_fonts.codepoint_starts
        )
        projection_metrics.append(
            f'<span class="{prefix}proj-metric" '
            f'style="view-timeline:{timeline} inline;'
            "width:calc-size(max-content,calc("
            f"size * {css_number(multiplier)} + ({css_number(constant)} + "
            f"{css_number(projection_geometry_scale)} * "
            f'var(--{prefix}-attn-{output:03d})) * 1px))">'
            f"{characters}</span>"
        )
    projection_consumers = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)

    child_marker = f"__FOUR_BLOCK_CHILD_{layer}__"
    boundary = (
        f'<div id="four-block-boundary-h{layer}" '
        f'class="{prefix}proj-result-{projection_consumers - 1}">'
        f'<i id="four-block-ready-h{layer}" class="four-block-ready-probe" '
        f'aria-hidden="true"></i>{child_marker}</div>'
    )
    projection_tree = boundary
    for consumer in reversed(range(projection_consumers - 1)):
        projection_tree = (
            f'<div class="{prefix}proj-result-{consumer}">{projection_tree}</div>'
        )
    projection_html = (
        f'<div class="{prefix}proj-stage">'
        f'<div class="{prefix}proj-scroller"><div class="{prefix}proj-track">'
        + "".join(projection_metrics)
        + "</div></div>"
        + projection_tree
        + "</div>"
    )
    fc_tree = result_tree(prefix, "fc", fc_consumers, projection_html)
    fc_html = (
        f'<div class="{prefix}-ln2"><div class="{prefix}fc-stage">'
        f'<div class="{prefix}fc-scroller"><div class="{prefix}fc-track">'
        + "".join(fc_metrics)
        + "</div></div>"
        + fc_tree
        + "</div></div>"
    )
    attention_tree = result_tree(prefix, "attn", attention_consumers, fc_html)
    html = (
        f'<div class="{prefix}-norm" data-four-block-stage="{prefix}">'
        f'<div class="{prefix}attn-stage">'
        f'<div class="{prefix}attn-scroller"><div class="{prefix}attn-track">'
        + attention_metrics
        + "</div></div>"
        + attention_tree
        + "</div></div>"
    )

    css = (
        font_faces(f"{prefix}attn", attention_fonts)
        + font_faces(f"{prefix}fc", fc_fonts)
        + font_faces(f"{prefix}proj", projection_fonts)
        + registrations(prefix)
        + attention_keyframe_css
        + fc_keyframe_css
        + projection_keyframe_css
        + f".{prefix}-norm{{{';'.join(normalization1)}}}"
        + f".{prefix}-ln2{{{';'.join(normalization2)}}}"
        + f".{prefix}attn-stage{{timeline-scope:{','.join(attention_timelines)};"
        f"font-size:{FONT_SIZE}px;font-family:{attention_families};"
        f"font-kerning:none;font-style:normal;font-variation-settings:{attention_settings}}}"
        + f".{prefix}attn-scroller{{position:fixed;left:0;top:-{50 + layer}000px;"
        f"width:{attention_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".{prefix}attn-track{{position:relative;width:{attention_viewport * 3}px;height:1px}}"
        + f".{prefix}attn-metric{{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + animation_rules(
            prefix,
            "attn",
            attention_keyframes,
            attention_timelines,
            attention_consumers,
            "linear",
        )
        + "".join(attention_math)
        + f".{prefix}fc-stage{{timeline-scope:{','.join(fc_timelines)};"
        f"font-size:{FONT_SIZE}px;font-family:{fc_families};font-kerning:none;"
        f"font-style:normal;font-variation-settings:{fc_settings};"
        f"--{prefix}-gelu-min:{css_number(gelu_min)};"
        f"--{prefix}-gelu-max:{css_number(gelu_max)};"
        f"--{prefix}-gelu-ease:linear({','.join(gelu_stops)})}}"
        + f".{prefix}fc-scroller{{position:fixed;left:0;top:-{60 + layer}000px;"
        f"width:{fc_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".{prefix}fc-track{{position:relative;width:{fc_viewport * 3}px;height:1px}}"
        + f".{prefix}fc-metric{{position:absolute;left:0;top:0;display:inline-flex;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + animation_rules(
            prefix,
            "fc",
            fc_keyframes,
            fc_timelines,
            fc_consumers,
            f"var(--{prefix}-gelu-ease)",
        )
        + f".{prefix}proj-stage{{timeline-scope:{','.join(projection_timelines)};"
        f"font-size:{FONT_SIZE}px;font-family:{projection_families};"
        f"font-kerning:none;font-style:normal;font-variation-settings:{projection_settings};"
        f"--{prefix}-projection-ease:linear({','.join(projection_stops)})}}"
        + f".{prefix}proj-scroller{{position:fixed;left:0;top:-{70 + layer}000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".{prefix}proj-track{{position:relative;width:{projection_viewport * 3}px;height:1px}}"
        + f".{prefix}proj-metric{{position:absolute;left:0;top:0;display:inline-flex;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        + animation_rules(
            prefix,
            "proj",
            projection_keyframes,
            projection_timelines,
            projection_consumers,
            f"var(--{prefix}-projection-ease)",
        )
        + f"#four-block-ready-h{layer}{{animation:{prefix}-ready 1s linear both;"
        f"animation-timeline:--{prefix}pt767;animation-range:cover}}"
        + f"@keyframes {prefix}-ready{{from{{opacity:.99}}to{{opacity:1}}}}"
    )

    font_names = tuple(
        [
            *attention_fonts.names,
            *fc_fonts.names,
            *projection_fonts.names,
        ]
    )
    font_bytes = sum((OUT / f"{name}.woff2").stat().st_size for name in font_names)
    ttf_bytes = sum((OUT / f"{name}.ttf").stat().st_size for name in font_names)
    return Stage(
        layer=layer,
        prefix=prefix,
        source_prefix=source_prefix,
        html=html,
        css=css,
        expected=expected,
        attention_residual=attention_residual,
        normalized2=normalized2,
        hidden=hidden,
        font_names=font_names,
        font_bytes=font_bytes,
        ttf_bytes=ttf_bytes,
        viewports={
            "attention": attention_viewport,
            "fc": fc_viewport,
            "projection": projection_viewport,
        },
    )


def scheduler_svg() -> str:
    sets = "".join(
        f'<g id="four-block-signal-b{layer}">'
        f'<set attributeName="class" to="ready" '
        f'begin="four-block-ready-h{layer - 1}.animationend+0.05s" '
        'fill="freeze" /></g>'
        for layer in (1, 2, 3)
    )
    return (
        '<svg id="four-block-smil-scheduler" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f"{sets}</svg>"
    )


def isolated_page(stage: Stage, input_vector: np.ndarray, css_tag: str) -> str:
    marker = f"__FOUR_BLOCK_CHILD_{stage.layer}__"
    html = stage.html.replace(
        marker,
        f'<output id="four-block-isolated-h{stage.layer}">isolated h.{stage.layer}</output>',
        1,
    )
    input_style = ";".join(
        f"--{stage.source_prefix}-{index:03d}:{css_number(value)}"
        for index, value in enumerate(input_vector)
    )
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        f"<title>One-token truncated isolated h.{stage.layer} diagnostic</title>"
        f'<link rel="stylesheet" href="{STYLESHEET.name}?v={css_tag}">'
        f'<div style="{input_style}">{html}</div>'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
        help="refuse font generation if current free space is below this floor",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not SOURCE_HTML.exists() or not SOURCE_REFERENCE.exists():
        raise FileNotFoundError(f"missing existing h.0 source fixture: {SOURCE_HTML}")
    free_before = shutil.disk_usage(ROOT).free
    if free_before < args.minimum_free_gib * 1024**3:
        raise RuntimeError(
            f"only {free_before / 1024**3:.2f} GiB free; refusing generation"
        )
    OUT.mkdir(parents=True, exist_ok=True)

    # build_font_group intentionally uses its module-level output path.  Point
    # it only at this experiment so no pre-existing artifact can be touched.
    block_css.OUT = OUT

    source_reference = json.loads(SOURCE_REFERENCE.read_text())
    block0 = np.asarray(source_reference["output"], dtype=np.float64)
    if block0.shape != (WIDTH,) or not np.all(np.isfinite(block0)):
        raise ValueError("existing h.0 boundary is not a finite width-768 vector")

    stages = []
    prior = block0
    for layer in (1, 2, 3):
        stage = build_stage(layer, prior)
        stages.append(stage)
        prior = stage.expected

    css = (
        "/* One-token/truncated h.0->h.1->h.2->h.3 diagnostic; no vocab head. */"
        "#four-block-smil-scheduler,.four-block-ready-probe{position:fixed;"
        "left:-10000px;top:0;width:1px;height:1px}"
        "#four-block-boundary-h3{display:block;font:14px ui-monospace,monospace}"
        + "".join(stage.css for stage in stages)
    )
    STYLESHEET.write_text(css)
    css_tag = hashlib.sha256(STYLESHEET.read_bytes()).hexdigest()[:12]

    child = (
        '<output id="four-block-final">one-token truncated four-block diagnostic; '
        "not full GPT-2 inference</output>"
    )
    for stage in reversed(stages):
        marker = f"__FOUR_BLOCK_CHILD_{stage.layer}__"
        child = stage.html.replace(marker, child, 1)
    block0_wrapper = (
        '<div id="four-block-boundary-h0" class="proj-result-5">'
        '<i id="four-block-ready-h0" class="four-block-ready-probe" '
        'aria-hidden="true"></i>'
        + child
        + "</div>"
    )

    source = hrefs_from_source(SOURCE_HTML.read_text())
    if source.count(SOURCE_LEAF) != 1:
        raise ValueError("existing h.0 output leaf was not found exactly once")
    page = source.replace(SOURCE_LEAF, block0_wrapper, 1)
    page = page.replace(
        "</title>",
        " — one-token truncated four-block diagnostic</title>"
        f'<link rel="stylesheet" href="{STYLESHEET.name}?v={css_tag}">',
        1,
    )
    page = page.replace("<css-stage ", scheduler_svg() + "<css-stage ", 1)
    if "lm_head" in page or "vocabulary" in page.lower() or "__FOUR_BLOCK_CHILD" in page:
        raise ValueError("unexpected vocabulary head or unresolved child marker")
    CONNECTED_HTML.write_text(page)

    prior = block0
    isolated_files = []
    for stage in stages:
        path = OUT / f"view-timeline-four-block-isolated-h{stage.layer}.html"
        path.write_text(isolated_page(stage, prior, css_tag))
        isolated_files.append(path.name)
        prior = stage.expected

    tensors = SafeTensors(MODEL_PATH)
    architecture = {
        "name": "GPT-2 small",
        "layers": 12,
        "hidden_size": WIDTH,
        "mlp_width": MLP_WIDTH,
        "vocabulary_size": int(tensors.tensor("wte.weight").shape[0]),
        "context_size": int(tensors.tensor("wpe.weight").shape[0]),
    }
    if architecture != {
        "name": "GPT-2 small",
        "layers": 12,
        "hidden_size": 768,
        "mlp_width": 3072,
        "vocabulary_size": 50257,
        "context_size": 1024,
    }:
        raise ValueError(f"immutable GPT-2-small architecture mismatch: {architecture}")

    boundaries = {"h.0": block0.tolist()}
    boundaries.update({f"h.{stage.layer}": stage.expected.tolist() for stage in stages})
    reference = {
        "diagnostic": "one-token/truncated four-block diagnostic, not full GPT-2 inference",
        "vocabulary_head_attached": False,
        "architecture": architecture,
        "checkpoint": {
            "path": str(MODEL_PATH.relative_to(ROOT)),
            "bytes": MODEL_PATH.stat().st_size,
            "sha256": sha256(MODEL_PATH),
        },
        "token_id": int(source_reference["token_id"]),
        "layers": [0, 1, 2, 3],
        "real_checkpoint_layers": [1, 2, 3],
        "quantization_bits": QUANT_BITS,
        "fc_easing_stops": FC_EASING_STOPS,
        "projection_easing_stops": PROJECTION_EASING_STOPS,
        "boundaries": boundaries,
        "stage_oracles": {
            f"h.{stage.layer}": {
                "input_boundary": f"h.{stage.layer - 1}",
                "source_property_prefix": stage.source_prefix,
                "attention_residual": stage.attention_residual.tolist(),
                "normalized2": stage.normalized2.tolist(),
                "hidden": stage.hidden.tolist(),
                "output": stage.expected.tolist(),
                "viewports": stage.viewports,
                "font_names": list(stage.font_names),
                "woff2_bytes": stage.font_bytes,
                "ttf_bytes": stage.ttf_bytes,
            }
            for stage in stages
        },
        "handoff": {
            "relationship": "nested direct inheritance only",
            "materialized_sibling_values": 0,
            "property_prefixes": ["out", "b1-final", "b2-final", "b3-final"],
        },
    }
    REFERENCE.write_text(json.dumps(reference, indent=2) + "\n")

    manifest = {
        "diagnostic": reference["diagnostic"],
        "connected": CONNECTED_HTML.name,
        "stylesheet": STYLESHEET.name,
        "reference": REFERENCE.name,
        "isolated": isolated_files,
        "runtime_javascript": False,
        "smil_signal_dependencies": ["h.0->h.1", "h.1->h.2", "h.2->h.3"],
        "files": {
            path.name: path.stat().st_size
            for path in [CONNECTED_HTML, STYLESHEET, REFERENCE]
        },
        "font_bytes": sum(stage.font_bytes for stage in stages),
        "ttf_bytes": sum(stage.ttf_bytes for stage in stages),
        "free_bytes_before": free_before,
        "free_bytes_after": shutil.disk_usage(ROOT).free,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
