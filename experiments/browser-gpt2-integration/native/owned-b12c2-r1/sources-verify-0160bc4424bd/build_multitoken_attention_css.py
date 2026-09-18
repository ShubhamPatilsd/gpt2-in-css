#!/usr/bin/env python3
"""Build a real two-token GPT-2 causal-attention pass in HTML/CSS only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import (
    OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    font_faces,
    layer_norm,
    pack_font_settings,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


TOKENS = (15496, 995)  # "Hello world"
TOKEN_COUNT = len(TOKENS)
HEADS = 12
HEAD_WIDTH = WIDTH // HEADS
QKV_WIDTH = WIDTH * 3
FONT_SIZE = 512
OUTPUTS_PER_CONSUMER = 128
BILINEAR_FONT = OUT.parent / "bilinear-hvar-attention" / "bilinear-attention-exact4.woff2"
BILINEAR_BASE = 64_000
BILINEAR_DELTA = 961
FLEX_NORMALIZER_WIDTH = 65_536


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    numerator = np.exp(shifted)
    return numerator / np.sum(numerator)


def timeline_rules(
    progress_names: list[str], keyframe_names: list[str]
) -> str:
    return "".join(
        f'@property {progress}'
        '{syntax:"<number>";inherits:true;initial-value:-1}'
        f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for progress, keyframe in zip(
            progress_names, keyframe_names, strict=True
        )
    )


def registrations(names: list[str]) -> str:
    return "".join(
        f'@property {name}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for name in names
    )


def shared_metrics(
    *,
    class_name: str,
    timeline_names: list[str],
    codepoint_starts: tuple[int, ...],
    output_count: int,
) -> str:
    metrics = []
    for output in range(output_count):
        characters = "".join(
            f"&#x{start + output:X};" for start in codepoint_starts
        )
        metrics.append(
            f'<i class="{class_name}" style="view-timeline:'
            f'{timeline_names[output]} inline">{characters}</i>'
        )
    return "".join(metrics)


def consumer_tree(
    prefix: str,
    count: int,
    child: str,
) -> str:
    for consumer in reversed(range(count)):
        child = f'<div class="{prefix}-{consumer}">{child}</div>'
    return child


def container_qkv_stage(
    *,
    token: int,
    normalized: np.ndarray,
    qkv_fonts,
    qkv_bases: np.ndarray,
    qkv_range: float,
    q_qkv,
    qkv_bias: np.ndarray,
    output_ranges: np.ndarray,
    css_stem: str | None = None,
    element_name: str | None = None,
) -> str:
    """Write one shadow-isolated six-output QKV container stage."""
    levels = 255
    radix = 256
    outputs_per_packet = 6
    input_names = [f"--n1-{token}-{index:03d}" for index in range(WIDTH)]
    inputs = ";".join(
        f"{name}:{css_number(value)}"
        for name, value in zip(input_names, normalized, strict=True)
    )
    families = ",".join(f"qkvS{index}" for index in range(len(qkv_fonts.names)))
    rules = [
        f":host{{display:block;position:relative;{inputs};font:normal {FONT_SIZE}px qkvS0;"
        f"font-family:{families};font-kerning:none;"
        f"font-variation-settings:{pack_font_settings(input_names, qkv_range, 0)}}}",
        ".metric{position:fixed;inset:0 auto auto 0;display:inline-flex;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}",
        ".packet{position:fixed;inset:0 auto auto 0;display:block;container-type:size}",
    ]
    metric_groups: list[list[str]] = []
    dimensions: list[tuple[str, str]] = []
    declarations: list[list[str]] = []
    for packet_start in range(0, QKV_WIDTH, outputs_per_packet):
        metrics = []
        packet_dimensions = []
        packet_declarations = []
        for axis in range(2):
            codes = []
            packed = f"round(nearest,100cq{'w' if axis == 0 else 'h'} / 1px,1)"
            for digit in range(3):
                output = packet_start + axis * 3 + digit
                anchor = f"--qcm-{token}-{output}"
                characters = "".join(
                    f"&#x{start + output:X};" for start in qkv_fonts.codepoint_starts
                )
                metrics.append(
                    f'<i class="metric" style="anchor-name:{anchor}">{characters}</i>'
                )
                factor = qkv_range * q_qkv.scales[output]
                value_range = float(output_ranges[output])
                value = (
                    f"((anchor-size({anchor} width) / 1px * {UNITS_PER_EM} / "
                    f"{FONT_SIZE} - {int(qkv_bases[output])}) * {css_number(factor)} "
                    f"+ ({css_number(qkv_bias[output])}))"
                )
                codes.append(
                    "round(nearest,clamp(0px,calc(("
                    + value
                    + f" + {css_number(value_range)}) * {levels} / "
                    + f"{css_number(2 * value_range)} * 1px),{levels}px),1px)"
                )
                if digit == 0:
                    code = f"mod({packed},{radix})"
                elif digit == 1:
                    code = f"mod(round(down,{packed}/{radix},1),{radix})"
                else:
                    code = f"round(down,{packed}/{radix ** 2},1)"
                packet_declarations.append(
                    f"--qkv-{token}-{output:04d}:calc(-{css_number(value_range)} + "
                    f"{code} * {css_number(2 * value_range / levels)})"
                )
            packet_dimensions.append(
                "calc("
                + " + ".join(
                    f"{code} * {radix ** digit}"
                    for digit, code in enumerate(codes)
                )
                + ")"
            )
        metric_groups.append(metrics)
        dimensions.append((packet_dimensions[0], packet_dimensions[1]))
        declarations.append(packet_declarations)
    for packet, (width, height) in enumerate(dimensions):
        inherited = [] if packet == 0 else declarations[packet - 1]
        rules.append(
            f".packet-{packet}{{width:{width};height:{height};"
            + ";".join(inherited)
            + "}"
        )
    rules.append("slot{" + ";".join(declarations[-1]) + "}")
    css_path = OUT / f"{css_stem or f'qkv-container-token-{token}'}.css"
    css_path.write_text("".join(rules))
    tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    child = "<slot></slot>"
    for packet in reversed(range(len(dimensions))):
        child = (
            "".join(metric_groups[packet])
            + f'<i class="packet packet-{packet}">{child}</i>'
        )
    tag_name = element_name or f"qkv-container-{token}"
    return (
        f'<{tag_name}><template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{css_path.name}?v={tag}">'
        + child
        + f"</template>{{child}}</{tag_name}>"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-backend", choices=("css", "bilinear"), default="css")
    parser.add_argument(
        "--qkv-transport", choices=("timeline", "container"), default="timeline"
    )
    parser.add_argument(
        "--mix-backend",
        choices=(
            "css",
            "css-fused",
            "css-typed-staged",
            "flex-prob",
            "flex-anchor",
        ),
        default="css",
        help=(
            "attention reducer: probability-materializing CSS, algebraically fused "
            "CSS, a typed max/exp/denominator/probability graph, flex-normalized "
            "probabilities followed by CSS mixing, or "
            "flex-normalized anchor-weighted value mixing"
        ),
    )
    args = parser.parse_args()
    suffix = "" if args.score_backend == "css" else "-bilinear"
    if args.mix_backend != "css":
        suffix += f"-{args.mix_backend}"
    if args.qkv_transport == "container":
        suffix += "-qkv-container"
    html_path = OUT / f"view-timeline-attention-2token{suffix}.html"
    css_path = OUT / f"view-timeline-attention-2token{suffix}.css"
    reference_path = OUT / f"view-timeline-attention-2token{suffix}-reference.json"
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    x = np.stack(
        [
            np.asarray(
                tensors.tensor("wte.weight")[token]
                + tensors.tensor("wpe.weight")[position],
                dtype=np.float64,
            )
            for position, token in enumerate(TOKENS)
        ]
    )
    ln1_gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    ln1_beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    normalized = np.stack(
        [layer_norm(row, ln1_gamma, ln1_beta) for row in x]
    )
    c_attn_weight = np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    )
    c_attn_bias = np.asarray(
        tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64
    )
    q_qkv = quantize_float_rows(c_attn_weight.T, bits=QUANT_BITS)
    qkv_unpacked = np.stack(
        [q_qkv.reconstructed @ row + c_attn_bias for row in normalized]
    )
    qkv_output_ranges = np.maximum(np.max(np.abs(qkv_unpacked), axis=0) * 1.1, 0.05)
    if args.qkv_transport == "container":
        qkv_codes = np.rint(
            np.clip(
                (qkv_unpacked + qkv_output_ranges) * 255 / (2 * qkv_output_ranges),
                0,
                255,
            )
        )
        qkv = -qkv_output_ranges + qkv_codes * (2 * qkv_output_ranges / 255)
    else:
        qkv = qkv_unpacked
    query, key, value = np.split(qkv, 3, axis=1)
    query = query.reshape(TOKEN_COUNT, HEADS, HEAD_WIDTH)
    key = key.reshape(TOKEN_COUNT, HEADS, HEAD_WIDTH)
    value = value.reshape(TOKEN_COUNT, HEADS, HEAD_WIDTH)
    scores = np.full((TOKEN_COUNT, HEADS, TOKEN_COUNT), -np.inf)
    probabilities = np.zeros_like(scores)
    context = np.zeros((TOKEN_COUNT, HEADS, HEAD_WIDTH))
    for target in range(TOKEN_COUNT):
        for head in range(HEADS):
            visible_scores = np.asarray(
                [
                    np.dot(query[target, head], key[source, head])
                    / math.sqrt(HEAD_WIDTH)
                    for source in range(target + 1)
                ]
            )
            scores[target, head, : target + 1] = visible_scores
            probabilities[target, head, : target + 1] = softmax(visible_scores)
            context[target, head] = sum(
                probabilities[target, head, source] * value[source, head]
                for source in range(target + 1)
            )
    context = context.reshape(TOKEN_COUNT, WIDTH)
    projection_weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    projection_bias = np.asarray(
        tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64
    )
    q_projection = quantize_float_rows(projection_weight, bits=QUANT_BITS)
    projected = np.stack(
        [q_projection.reconstructed @ row + projection_bias for row in context]
    )
    residual = x + projected

    qkv_shards = math.ceil(q_qkv.codes.shape[1] / 256)
    qkv_fonts_exist = all(
        (OUT / f"qkv-rowbase-s{shard}.woff2").exists()
        for shard in range(qkv_shards)
    )
    qkv_fonts = build_font_group(
        "qkv-rowbase",
        q_qkv.codes,
        rebuild=not qkv_fonts_exist,
        row_specific_bases=True,
    )
    projection_shards = math.ceil(WIDTH / 256)
    projection_fonts_exist = all(
        (OUT / f"attn-out-rowbase-s{shard}.woff2").exists()
        for shard in range(projection_shards)
    )
    projection_fonts = build_font_group(
        "attn-out-rowbase",
        q_projection.codes,
        rebuild=not projection_fonts_exist,
        row_specific_bases=True,
    )
    if qkv_fonts.row_bases is None or projection_fonts.row_bases is None:
        raise ValueError("two-token attention requires row-specific font bases")
    qkv_bases = np.sum(np.stack(qkv_fonts.row_bases), axis=0)
    projection_bases = np.sum(np.stack(projection_fonts.row_bases), axis=0)
    qkv_range = float(np.max(np.abs(normalized)) * 1.01)
    context_range = float(np.max(np.abs(context)) * 1.01)
    value_offsets = np.max(np.abs(value), axis=(0, 2)) * 1.01 + 1e-4
    qkv_viewport = 2 ** math.ceil(
        math.log2(
            max(1024, int(np.max(qkv_bases)) * FONT_SIZE / UNITS_PER_EM * 1.25)
        )
    )
    projection_viewport = 2 ** math.ceil(
        math.log2(
            max(
                1024,
                int(np.max(projection_bases))
                * FONT_SIZE
                / UNITS_PER_EM
                * 1.25,
            )
        )
    )

    css_parts = [font_faces("qkv", qkv_fonts), font_faces("attnout", projection_fonts)]
    property_names: list[str] = []
    for token in range(TOKEN_COUNT):
        property_names.extend(
            f"--qkv-{token}-{index:04d}" for index in range(QKV_WIDTH)
        )
        property_names.extend(
            f"--context-{token}-{index:03d}" for index in range(WIDTH)
        )
        property_names.extend(
            f"--attn-out-{token}-{index:03d}" for index in range(WIDTH)
        )
        property_names.extend(
            f"--r1-{token}-{index:03d}" for index in range(WIDTH)
        )
    property_names.extend(
        f"--score-{head}-{source}"
        for head in range(HEADS)
        for source in range(TOKEN_COUNT)
    )
    if args.mix_backend == "flex-prob":
        property_names.extend(
            f"--prob-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        )
    if args.mix_backend == "css-typed-staged":
        property_names.extend(f"--score-max-{head}" for head in range(HEADS))
        property_names.extend(f"--score-den-{head}" for head in range(HEADS))
        property_names.extend(
            f"--score-exp-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        )
        property_names.extend(
            f"--prob-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        )
    css_parts.append(registrations(property_names))

    qkv_stage_html: list[str] = []
    if args.qkv_transport == "timeline":
        for token in range(TOKEN_COUNT):
            timeline_names = [f"--qt-{token}-{index}" for index in range(QKV_WIDTH)]
            progress_names = [f"--qp-{token}-{index}" for index in range(QKV_WIDTH)]
            keyframe_names = [f"qk-{token}-{index}" for index in range(QKV_WIDTH)]
            css_parts.append(timeline_rules(progress_names, keyframe_names))
            input_names = [f"--n1-{token}-{index:03d}" for index in range(WIDTH)]
            inputs = ";".join(
                f"{name}:{css_number(value)}"
                for name, value in zip(input_names, normalized[token], strict=True)
            )
            families = ",".join(
                f"qkvS{index}" for index in range(len(qkv_fonts.names))
            )
            css_parts.append(
                f'.qkv-stage-{token}{{{inputs};timeline-scope:{",".join(timeline_names)};'
                f"font:normal {FONT_SIZE}px qkvS0;font-family:{families};font-kerning:none;"
                f"font-variation-settings:{pack_font_settings(input_names, qkv_range, 0)}}}"
            )
            declarations: list[str] = []
            for output_index, progress in enumerate(progress_names):
                raw_name = f"--qraw-{token}-{output_index:04d}"
                factor = qkv_range * q_qkv.scales[output_index]
                declarations.extend(
                    (
                        f"{raw_name}:calc(({qkv_viewport} / var({progress}) - "
                        f"{qkv_viewport}) * {UNITS_PER_EM} / {FONT_SIZE} - "
                        f"{int(qkv_bases[output_index])})",
                        f"--qkv-{token}-{output_index:04d}:calc(var({raw_name}) * "
                        f"{css_number(factor)} + ({css_number(c_attn_bias[output_index])}))",
                    )
                )
            consumer_count = math.ceil(QKV_WIDTH / OUTPUTS_PER_CONSUMER)
            for consumer in range(consumer_count):
                start = consumer * OUTPUTS_PER_CONSUMER
                stop = min(start + OUTPUTS_PER_CONSUMER, QKV_WIDTH)
                css_parts.append(
                    f".qkv-result-{token}-{consumer}{{"
                    f"animation-name:{','.join(keyframe_names[start:stop])};"
                    "animation-duration:1s;animation-timing-function:linear;"
                    "animation-fill-mode:both;"
                    f"animation-timeline:{','.join(timeline_names[start:stop])};"
                    "animation-range:cover;"
                    + ";".join(declarations[start * 2 : stop * 2])
                    + "}"
                )
            metrics = shared_metrics(
                class_name="qkv-metric",
                timeline_names=timeline_names,
                codepoint_starts=qkv_fonts.codepoint_starts,
                output_count=QKV_WIDTH,
            )
            qkv_stage_html.append(
                f'<div class="qkv-stage-{token}"><div class="qkv-scroller">'
                f'<div class="qkv-track">{metrics}</div></div>{{child}}</div>'
            )

    else:
        for token in range(TOKEN_COUNT):
            qkv_stage_html.append(
                container_qkv_stage(
                    token=token,
                    normalized=normalized[token],
                    qkv_fonts=qkv_fonts,
                    qkv_bases=qkv_bases,
                    qkv_range=qkv_range,
                    q_qkv=q_qkv,
                    qkv_bias=c_attn_bias,
                    output_ranges=qkv_output_ranges,
                )
            )

    if args.qkv_transport == "timeline":
        css_parts.append(
            ".qkv-scroller{position:fixed;left:0;top:-50000px;"
            f"width:{qkv_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
            f".qkv-track{{position:relative;width:{qkv_viewport * 3}px;height:1px}}"
            ".qkv-metric{position:absolute;left:0;top:0;display:inline-flex;"
            "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        )
        css_parts.append(
            "body.alternate .qkv-stage-1{--n1-1-000:"
            f"{css_number(normalized[1, 0] + 0.03125)}"
            "}"
        )

    mix_declarations: list[str] = []
    score_stage_html: str | None = None
    attention_range = float(max(np.max(np.abs(query)), np.max(np.abs(key))) * 1.01)
    if args.score_backend == "bilinear":
        if not BILINEAR_FONT.exists():
            raise FileNotFoundError(
                "build experiments/bilinear-hvar-attention before the bilinear score backend"
            )
        score_viewport = 131_072
        score_timelines = [
            f"--score-t-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        ]
        score_progress = [
            f"--score-p-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        ]
        score_keyframes = [
            f"score-k-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        ]
        css_parts.append(
            '@font-face{font-family:BilinearQK;src:url('
            '"../bilinear-hvar-attention/bilinear-attention-exact4.woff2?v=1"'
            ') format("woff2")}'
        )
        css_parts.append(timeline_rules(score_progress, score_keyframes))
        score_metrics = []
        score_declarations = []
        cursor = 0
        glyphs = "".join(f"&#x{0xE000 + shard:X};" for shard in range(4))
        for head in range(HEADS):
            q_start = head * HEAD_WIDTH
            for source in range(TOKEN_COUNT):
                k_start = WIDTH + head * HEAD_WIDTH
                settings = ",".join(
                    [
                        f'"Q{local:03d}" calc(var(--qkv-1-{q_start + local:04d}) / '
                        f"{css_number(attention_range)})"
                        for local in range(HEAD_WIDTH)
                    ]
                    + [
                        f'"K{local:03d}" calc(var(--qkv-{source}-{k_start + local:04d}) / '
                        f"{css_number(attention_range)})"
                        for local in range(HEAD_WIDTH)
                    ]
                )
                css_parts.append(
                    f".score-metric-{head}-{source}{{"
                    f"font-variation-settings:{settings}}}"
                )
                score_metrics.append(
                    f'<i class="score-metric score-metric-{head}-{source}" '
                    f'style="view-timeline:{score_timelines[cursor]} inline">'
                    f"{glyphs}</i>"
                )
                raw = (
                    f"(({score_viewport} / var({score_progress[cursor]}) - "
                    f"{score_viewport}) * {UNITS_PER_EM} / {FONT_SIZE} - "
                    f"{BILINEAR_BASE})"
                )
                score_declarations.append(
                    f"--score-{head}-{source}:calc({raw} * "
                    f"{css_number(attention_range * attention_range / BILINEAR_DELTA)} "
                    f"/ {math.sqrt(HEAD_WIDTH)})"
                )
                cursor += 1
        css_parts.append(
            ".score-stage{timeline-scope:"
            + ",".join(score_timelines)
            + ";font:normal "
            + f"{FONT_SIZE}px BilinearQK;font-kerning:none}}"
            + ".score-scroller{position:fixed;left:0;top:-55000px;"
            + f"width:{score_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
            + f".score-track{{position:relative;width:{score_viewport * 3}px;height:1px}}"
            + ".score-metric{position:absolute;left:0;top:0;display:inline-flex;"
            + "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
            + ".score-result{animation-name:"
            + ",".join(score_keyframes)
            + ";animation-duration:1s;animation-timing-function:linear;"
            + "animation-fill-mode:both;animation-timeline:"
            + ",".join(score_timelines)
            + ";animation-range:cover;"
            + ";".join(score_declarations)
            + "}"
        )
        score_stage_html = (
            '<div class="score-stage"><div class="score-scroller">'
            f'<div class="score-track">{"".join(score_metrics)}</div></div>'
            "{child}</div>"
        )

    for head in range(HEADS):
        q_start = head * HEAD_WIDTH
        k_start = WIDTH + head * HEAD_WIDTH
        if args.score_backend == "css":
            score_10 = " + ".join(
                f"var(--qkv-1-{q_start + local:04d}) * "
                f"var(--qkv-0-{k_start + local:04d})"
                for local in range(HEAD_WIDTH)
            )
            score_11 = " + ".join(
                f"var(--qkv-1-{q_start + local:04d}) * "
                f"var(--qkv-1-{k_start + local:04d})"
                for local in range(HEAD_WIDTH)
            )
            mix_declarations.extend(
                (
                    f"--score-{head}-0:calc(({score_10}) / {math.sqrt(HEAD_WIDTH)})",
                    f"--score-{head}-1:calc(({score_11}) / {math.sqrt(HEAD_WIDTH)})",
                )
            )
        mix_declarations.append(
            f"--score-max-{head}:max(var(--score-{head}-0),var(--score-{head}-1))"
        )
        if args.mix_backend == "css-typed-staged":
            mix_declarations.extend(
                (
                    f"--score-exp-{head}-0:exp(var(--score-{head}-0) - "
                    f"var(--score-max-{head}))",
                    f"--score-exp-{head}-1:exp(var(--score-{head}-1) - "
                    f"var(--score-max-{head}))",
                    f"--score-den-{head}:calc(var(--score-exp-{head}-0) + "
                    f"var(--score-exp-{head}-1))",
                    f"--prob-{head}-0:calc(var(--score-exp-{head}-0) / "
                    f"var(--score-den-{head}))",
                    f"--prob-{head}-1:calc(var(--score-exp-{head}-1) / "
                    f"var(--score-den-{head}))",
                )
            )
        elif args.mix_backend in ("css", "css-fused"):
            mix_declarations.append(
                f"--score-den-{head}:calc(exp(var(--score-{head}-0) - "
                f"var(--score-max-{head})) + exp(var(--score-{head}-1) - "
                f"var(--score-max-{head})))"
            )
            if args.mix_backend == "css":
                mix_declarations.extend(
                    (
                    f"--prob-{head}-0:calc(exp(var(--score-{head}-0) - "
                    f"var(--score-max-{head})) / var(--score-den-{head}))",
                    f"--prob-{head}-1:calc(exp(var(--score-{head}-1) - "
                    f"var(--score-max-{head})) / var(--score-den-{head}))",
                    )
                )
    for index in range(WIDTH):
        head = index // HEAD_WIDTH
        value_index = 2 * WIDTH + index
        mix_declarations.append(
            f"--context-0-{index:03d}:var(--qkv-0-{value_index:04d})"
        )
        if args.mix_backend in ("css", "css-typed-staged"):
            mix_declarations.append(
                f"--context-1-{index:03d}:calc(var(--prob-{head}-0) * "
                f"var(--qkv-0-{value_index:04d}) + var(--prob-{head}-1) * "
                f"var(--qkv-1-{value_index:04d}))"
            )
        elif args.mix_backend == "css-fused":
            mix_declarations.append(
                f"--context-1-{index:03d}:calc((exp(var(--score-{head}-0) - "
                f"var(--score-max-{head})) * var(--qkv-0-{value_index:04d}) + "
                f"exp(var(--score-{head}-1) - var(--score-max-{head})) * "
                f"var(--qkv-1-{value_index:04d})) / var(--score-den-{head}))"
            )
    css_parts.append(f'.attention-mix{{{";".join(mix_declarations)}}}')

    flex_stage_html: str | None = None
    flex_consumer_count = 0
    if args.mix_backend in ("flex-prob", "flex-anchor"):
        probability_anchors = [
            f"--flex-prob-{head}-{source}"
            for head in range(HEADS)
            for source in range(TOKEN_COUNT)
        ]
        normalizers = []
        for head in range(HEADS):
            items = "".join(
                f'<i style="anchor-name:--flex-prob-{head}-{source};'
                f'flex-grow:exp(var(--score-{head}-{source}) - '
                f'var(--score-max-{head}))"></i>'
                for source in range(TOKEN_COUNT)
            )
            normalizers.append(f'<div class="flex-normalizer">{items}</div>')

        if args.mix_backend == "flex-prob":
            timeline_names = [
                f"--flex-prob-t-{head}-{source}"
                for head in range(HEADS)
                for source in range(TOKEN_COUNT)
            ]
            progress_names = [
                f"--flex-prob-p-{head}-{source}"
                for head in range(HEADS)
                for source in range(TOKEN_COUNT)
            ]
            keyframe_names = [
                f"flex-prob-k-{head}-{source}"
                for head in range(HEADS)
                for source in range(TOKEN_COUNT)
            ]
            css_parts.append(timeline_rules(progress_names, keyframe_names))
            readback_viewport = 2 ** math.ceil(
                math.log2(FLEX_NORMALIZER_WIDTH * 1.25)
            )
            readers = []
            declarations = []
            cursor = 0
            for head in range(HEADS):
                for source in range(TOKEN_COUNT):
                    readers.append(
                        f'<i class="flex-reader" style="width:calc(1 * '
                        f'anchor-size(--flex-prob-{head}-{source} width));'
                        f'view-timeline:{timeline_names[cursor]} inline"></i>'
                    )
                    declarations.append(
                        f"--prob-{head}-{source}:calc(({readback_viewport} / "
                        f"var({progress_names[cursor]}) - {readback_viewport}) / "
                        f"{FLEX_NORMALIZER_WIDTH})"
                    )
                    cursor += 1
            for index in range(WIDTH):
                head = index // HEAD_WIDTH
                value_index = 2 * WIDTH + index
                declarations.append(
                    f"--context-1-{index:03d}:calc(var(--prob-{head}-0) * "
                    f"var(--qkv-0-{value_index:04d}) + var(--prob-{head}-1) * "
                    f"var(--qkv-1-{value_index:04d}))"
                )
            css_parts.append(
                ".flex-result-0{animation-name:"
                + ",".join(keyframe_names)
                + ";animation-duration:1s;animation-timing-function:linear;"
                + "animation-fill-mode:both;animation-timeline:"
                + ",".join(timeline_names)
                + ";animation-range:cover;"
                + ";".join(declarations)
                + "}"
            )
            flex_consumer_count = 1
        else:
            timeline_names = [f"--flex-context-t-{index}" for index in range(WIDTH)]
            progress_names = [f"--flex-context-p-{index}" for index in range(WIDTH)]
            keyframe_names = [f"flex-context-k-{index}" for index in range(WIDTH)]
            css_parts.append(timeline_rules(progress_names, keyframe_names))
            maximum_encoded_width = FLEX_NORMALIZER_WIDTH * float(
                np.max(value_offsets[:, None] + np.max(value, axis=0))
            )
            readback_viewport = 2 ** math.ceil(
                math.log2(max(1024.0, maximum_encoded_width * 1.25))
            )
            readers = []
            declarations = []
            for index in range(WIDTH):
                head = index // HEAD_WIDTH
                value_index = 2 * WIDTH + index
                offset = float(value_offsets[head])
                width_terms = " + ".join(
                    f"({css_number(offset)} + var(--qkv-{source}-"
                    f"{value_index:04d})) * anchor-size(--flex-prob-{head}-{source} width)"
                    for source in range(TOKEN_COUNT)
                )
                readers.append(
                    f'<i class="flex-reader" style="width:calc({width_terms});'
                    f'view-timeline:{timeline_names[index]} inline"></i>'
                )
                declarations.append(
                    f"--context-1-{index:03d}:calc(({readback_viewport} / "
                    f"var({progress_names[index]}) - {readback_viewport}) / "
                    f"{FLEX_NORMALIZER_WIDTH} - {css_number(offset)})"
                )
            flex_consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
            for consumer in range(flex_consumer_count):
                start = consumer * OUTPUTS_PER_CONSUMER
                stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
                css_parts.append(
                    f".flex-result-{consumer}{{"
                    f"animation-name:{','.join(keyframe_names[start:stop])};"
                    "animation-duration:1s;animation-timing-function:linear;"
                    "animation-fill-mode:both;"
                    f"animation-timeline:{','.join(timeline_names[start:stop])};"
                    "animation-range:cover;"
                    + ";".join(declarations[start:stop])
                    + "}"
                )

        css_parts.append(
            ".flex-attention-stage{anchor-scope:"
            + ",".join(probability_anchors)
            + ";timeline-scope:"
            + ",".join(timeline_names)
            + "}"
            + ".flex-normalizer{position:absolute;left:0;top:0;display:flex;"
            + f"width:{FLEX_NORMALIZER_WIDTH}px;height:1px}}"
            + ".flex-normalizer>i{display:block;flex-basis:0;flex-shrink:1;"
            + "min-width:0;height:1px}"
            + ".flex-readback-scroller{position:fixed;left:0;top:-66000px;"
            + f"width:{readback_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
            + f".flex-readback-track{{position:relative;width:{readback_viewport * 3}px;"
            + "height:1px}"
            + ".flex-reader{position:absolute;left:0;top:0;display:block;height:1px}"
        )
        flex_stage_html = (
            '<div class="flex-attention-stage">'
            + '<div class="flex-readback-scroller"><div class="flex-readback-track">'
            + "".join(normalizers)
            + "".join(readers)
            + "</div></div>{child}</div>"
        )

    projection_stages: list[str] = []
    for token in range(TOKEN_COUNT):
        timeline_names = [f"--pt-{token}-{index}" for index in range(WIDTH)]
        progress_names = [f"--pp-{token}-{index}" for index in range(WIDTH)]
        keyframe_names = [f"pk-{token}-{index}" for index in range(WIDTH)]
        css_parts.append(timeline_rules(progress_names, keyframe_names))
        context_names = [f"--context-{token}-{index:03d}" for index in range(WIDTH)]
        families = ",".join(
            f"attnoutS{index}" for index in range(len(projection_fonts.names))
        )
        css_parts.append(
            f'.projection-stage-{token}{{timeline-scope:{",".join(timeline_names)};'
            f"font:normal {FONT_SIZE}px attnoutS0;font-family:{families};font-kerning:none;"
            f"font-variation-settings:{pack_font_settings(context_names, context_range, 0)}}}"
        )
        declarations = []
        for output_index, progress in enumerate(progress_names):
            raw_name = f"--praw-{token}-{output_index:03d}"
            factor = context_range * q_projection.scales[output_index]
            declarations.extend(
                (
                    f"{raw_name}:calc(({projection_viewport} / var({progress}) - "
                    f"{projection_viewport}) * {UNITS_PER_EM} / {FONT_SIZE} - "
                    f"{int(projection_bases[output_index])})",
                    f"--attn-out-{token}-{output_index:03d}:calc(var({raw_name}) * "
                    f"{css_number(factor)} + ({css_number(projection_bias[output_index])}))",
                    f"--r1-{token}-{output_index:03d}:calc("
                    f"{css_number(x[token, output_index])} + "
                    f"var(--attn-out-{token}-{output_index:03d}))",
                )
            )
        consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
        for consumer in range(consumer_count):
            start = consumer * OUTPUTS_PER_CONSUMER
            stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
            css_parts.append(
                f".projection-result-{token}-{consumer}{{"
                f"animation-name:{','.join(keyframe_names[start:stop])};"
                "animation-duration:1s;animation-timing-function:linear;"
                "animation-fill-mode:both;"
                f"animation-timeline:{','.join(timeline_names[start:stop])};"
                "animation-range:cover;"
                + ";".join(declarations[start * 3 : stop * 3])
                + "}"
            )
        metrics = shared_metrics(
            class_name="projection-metric",
            timeline_names=timeline_names,
            codepoint_starts=projection_fonts.codepoint_starts,
            output_count=WIDTH,
        )
        projection_stages.append(
            f'<div class="projection-stage-{token}"><div class="projection-scroller">'
            f'<div class="projection-track">{metrics}</div></div>{{child}}</div>'
        )
    css_parts.append(
        ".projection-scroller{position:fixed;left:0;top:-60000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".projection-track{{position:relative;width:{projection_viewport * 3}px;height:1px}}"
        ".projection-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}body{margin:2rem}"
        "h1{font:600 1.25rem system-ui,sans-serif}"
    )

    child = '<output id="attention-result"></output>'
    for token in reversed(range(TOKEN_COUNT)):
        count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
        child = consumer_tree(f"projection-result-{token}", count, child)
        child = projection_stages[token].replace("{child}", child)
    if flex_stage_html is not None:
        child = consumer_tree("flex-result", flex_consumer_count, child)
        child = flex_stage_html.replace("{child}", child)
    child = f'<div class="attention-mix">{child}</div>'
    if score_stage_html is not None:
        child = f'<div class="score-result">{child}</div>'
        child = score_stage_html.replace("{child}", child)
    for token in reversed(range(TOKEN_COUNT)):
        if args.qkv_transport == "timeline":
            count = math.ceil(QKV_WIDTH / OUTPUTS_PER_CONSUMER)
            child = consumer_tree(f"qkv-result-{token}", count, child)
        child = qkv_stage_html[token].replace("{child}", child)

    css_path.write_text("".join(css_parts))
    css_tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Two-token GPT-2 attention in CSS</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={css_tag}">'
        '<h1>Two-token, 12-head causal GPT-2 attention in HTML/CSS</h1>'
        '<p>No JavaScript. Prompt tokens: Hello world.</p>'
        + child
    )
    reference_path.write_text(
        json.dumps(
            {
                "token_ids": TOKENS,
                "heads": HEADS,
                "head_width": HEAD_WIDTH,
                "normalized": normalized.tolist(),
                "qkv": qkv.tolist(),
                "qkv_unpacked": qkv_unpacked.tolist(),
                "qkv_transport": args.qkv_transport,
                "qkv_output_ranges": qkv_output_ranges.tolist(),
                "scores": np.where(np.isfinite(scores), scores, -1e30).tolist(),
                "probabilities": probabilities.tolist(),
                "context": context.tolist(),
                "projected": projected.tolist(),
                "residual": residual.tolist(),
                "score_backend": args.score_backend,
                "mix_backend": args.mix_backend,
                "flex_normalizer_width": (
                    FLEX_NORMALIZER_WIDTH
                    if args.mix_backend in ("flex-prob", "flex-anchor")
                    else None
                ),
                "flex_value_offsets": (
                    value_offsets.tolist() if args.mix_backend == "flex-anchor" else None
                ),
                "attention_range": attention_range,
                "html_bytes": html_path.stat().st_size,
                "css_bytes": css_path.stat().st_size,
                "font_bytes": sum(
                    (OUT / f"{name}.woff2").stat().st_size
                    for name in (*qkv_fonts.names, *projection_fonts.names)
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "score_backend": args.score_backend,
            "qkv_transport": args.qkv_transport,
            "mix_backend": args.mix_backend,
            "html_bytes": html_path.stat().st_size,
            "css_bytes": css_path.stat().st_size,
            "font_count": len(qkv_fonts.names) + len(projection_fonts.names),
            "font_bytes": sum(
                (OUT / f"{name}.woff2").stat().st_size
                for name in (*qkv_fonts.names, *projection_fonts.names)
            ),
        }
    )


if __name__ == "__main__":
    main()
