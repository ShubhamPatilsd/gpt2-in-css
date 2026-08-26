#!/usr/bin/env python3
"""Build last-token attention that streams K/V through a fixed CSS state bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import math

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT, TOKENS
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
from build_multitoken_attention_css import (
    FONT_SIZE,
    HEADS,
    HEAD_WIDTH,
    OUTPUTS_PER_CONSUMER,
    QKV_WIDTH,
    consumer_tree,
    registrations,
    shared_metrics,
    softmax,
    timeline_rules,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


def selected_container_stage(
    *,
    stage_name: str,
    normalized: np.ndarray,
    output_indices: list[int],
    output_names: list[str],
    fonts,
    bases: np.ndarray,
    input_range: float,
    quantized,
    bias: np.ndarray,
    output_ranges: np.ndarray,
    leading_metrics: list[str] | None = None,
    slot_declarations: list[str] | None = None,
    extra_rules: list[str] | None = None,
    wrapper_class: str | None = None,
) -> str:
    """Encode selected HVAR matrix outputs six at a time into width and height."""
    if len(output_indices) != len(output_names) or len(output_indices) % 6:
        raise ValueError("selected container stages require complete six-value packets")
    input_names = [f"--{stage_name}-i-{index:03d}" for index in range(WIDTH)]
    inputs = ";".join(
        f"{name}:{css_number(value)}"
        for name, value in zip(input_names, normalized, strict=True)
    )
    families = ",".join(f"qkvS{index}" for index in range(len(fonts.names)))
    rules = [
        f":host{{display:block;position:relative;{inputs};font:normal {FONT_SIZE}px qkvS0;"
        f"font-family:{families};font-kerning:none;"
        f"font-variation-settings:{pack_font_settings(input_names, input_range, 0)}}}",
        ".metric{position:fixed;inset:0 auto auto 0;display:inline-flex;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}",
        ".packet{position:fixed;inset:0 auto auto 0;display:block;container-type:size}",
    ]
    metric_groups = []
    dimensions = []
    declarations = []
    for packet_start in range(0, len(output_indices), 6):
        metrics = []
        packet_dimensions = []
        packet_declarations = []
        for axis, unit in enumerate(("w", "h")):
            codes = []
            packed = f"round(nearest,100cq{unit} / 1px,1)"
            for digit in range(3):
                local = packet_start + axis * 3 + digit
                output = output_indices[local]
                anchor = f"--{stage_name}-m-{local}"
                characters = "".join(
                    f"&#x{start + output:X};" for start in fonts.codepoint_starts
                )
                metrics.append(
                    f'<i class="metric" style="anchor-name:{anchor}">{characters}</i>'
                )
                factor = input_range * quantized.scales[output]
                value_range = float(output_ranges[output])
                value = (
                    f"((anchor-size({anchor} width) / 1px * {UNITS_PER_EM} / "
                    f"{FONT_SIZE} - {int(bases[output])}) * {css_number(factor)} + "
                    f"({css_number(bias[output])}))"
                )
                codes.append(
                    "round(nearest,clamp(0px,calc((" + value +
                    f" + {css_number(value_range)}) * 255 / "
                    f"{css_number(2 * value_range)} * 1px),255px),1px)"
                )
                if digit == 0:
                    code = f"mod({packed},256)"
                elif digit == 1:
                    code = f"mod(round(down,{packed}/256,1),256)"
                else:
                    code = f"round(down,{packed}/65536,1)"
                packet_declarations.append(
                    f"{output_names[local]}:calc(-{css_number(value_range)} + "
                    f"{code} * {css_number(2 * value_range / 255)})"
                )
            packet_dimensions.append(
                "calc(" + " + ".join(
                    f"{code} * {256 ** digit}" for digit, code in enumerate(codes)
                ) + ")"
            )
        metric_groups.append(metrics)
        dimensions.append(packet_dimensions)
        declarations.append(packet_declarations)
    for packet, (width, height) in enumerate(dimensions):
        inherited = [] if packet == 0 else declarations[packet - 1]
        rules.append(
            f".packet-{packet}{{width:{width};height:{height};"
            + ";".join(inherited) + "}"
        )
    rules.extend(extra_rules or [])
    rules.append(
        "slot{" + ";".join(declarations[-1] + (slot_declarations or [])) + "}"
    )
    css_path = OUT / f"{stage_name}.css"
    css_path.write_text("".join(rules))
    tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    child = "<slot></slot>"
    for packet in reversed(range(len(dimensions))):
        child = (
            "".join(metric_groups[packet])
            + f'<i class="packet packet-{packet}">{child}</i>'
        )
    element = stage_name.replace("_", "-")
    content = f"{''.join(leading_metrics or [])}{child}"
    if wrapper_class:
        content = f'<div class="{wrapper_class}">{content}</div>'
    return (
        f'<{element}><template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{css_path.name}?v={tag}">'
        f"{content}</template>{{child}}</{element}>"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=int, choices=(1, 2, 4, 8, 16), required=True)
    parser.add_argument(
        "--key-transport", choices=("container", "anchor"), default="container"
    )
    args = parser.parse_args()
    token_ids = TOKENS[: args.context]
    token_count = len(token_ids)
    target = token_count - 1
    transport_name = "streaming" if args.key_transport == "container" else "streaming-key-anchor"
    stem = f"attention-context-{token_count}-qkv-{transport_name}"
    html_path = OUT / f"{stem}.html"
    css_path = OUT / f"{stem}.css"
    reference_path = OUT / f"{stem}-reference.json"

    precision = json.loads(PRECISION_REPORT.read_text())
    output_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    input_range = float(precision["inputAbsMaxCalibration"] * 1.05)
    tensors = SafeTensors(MODEL_PATH)
    token_embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position_embeddings = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    x = np.stack([
        token_embeddings[token] + position_embeddings[position]
        for position, token in enumerate(token_ids)
    ])
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    normalized = np.stack([layer_norm(row, gamma, beta) for row in x])
    if float(np.max(np.abs(normalized))) > input_range:
        raise ValueError("fixture exceeds the calibrated input range")

    qkv_weight = np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    ).T
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    q_qkv = quantize_float_rows(qkv_weight, bits=QUANT_BITS)
    qkv_unpacked = normalized @ q_qkv.reconstructed.T + qkv_bias
    codes = np.rint(
        np.clip((qkv_unpacked + output_ranges) * 255 / (2 * output_ranges), 0, 255)
    )
    qkv_packed = -output_ranges + codes * (2 * output_ranges / 255)
    qkv = qkv_packed.copy()
    if args.key_transport == "anchor":
        qkv[:, WIDTH:2 * WIDTH] = qkv_unpacked[:, WIDTH:2 * WIDTH]
    query, key, value = np.split(qkv, 3, axis=1)
    query = query.reshape(token_count, HEADS, HEAD_WIDTH)
    key = key.reshape(token_count, HEADS, HEAD_WIDTH)
    value = value.reshape(token_count, HEADS, HEAD_WIDTH)
    scores = np.empty((HEADS, token_count))
    probabilities = np.empty_like(scores)
    context = np.empty((HEADS, HEAD_WIDTH))
    for head in range(HEADS):
        scores[head] = np.asarray([
            np.dot(query[target, head], key[source, head]) / math.sqrt(HEAD_WIDTH)
            for source in range(token_count)
        ])
        probabilities[head] = softmax(scores[head])
        context[head] = sum(
            probabilities[head, source] * value[source, head]
            for source in range(token_count)
        )
    context = context.reshape(WIDTH)

    projection_weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    projection_bias = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    q_projection = quantize_float_rows(projection_weight, bits=QUANT_BITS)
    projected = q_projection.reconstructed @ context + projection_bias
    residual = x[target] + projected

    qkv_fonts = build_font_group(
        "qkv-rowbase", q_qkv.codes, rebuild=False, row_specific_bases=True
    )
    projection_fonts = build_font_group(
        "attn-out-rowbase", q_projection.codes, rebuild=False, row_specific_bases=True
    )
    if qkv_fonts.row_bases is None or projection_fonts.row_bases is None:
        raise ValueError("row-specific font bases are required")
    qkv_bases = np.sum(np.stack(qkv_fonts.row_bases), axis=0)
    projection_bases = np.sum(np.stack(projection_fonts.row_bases), axis=0)

    properties = [f"--q-{index:03d}" for index in range(WIDTH)]
    if args.key_transport == "container":
        properties += [f"--kv-{index:04d}" for index in range(2 * WIDTH)]
    else:
        properties += [f"--kv-{WIDTH + index:04d}" for index in range(WIDTH)]
    for bank in ("a", "b"):
        properties += [f"--m-{bank}-{head}" for head in range(HEADS)]
        properties += [f"--l-{bank}-{head}" for head in range(HEADS)]
        properties += [f"--acc-{bank}-{index:03d}" for index in range(WIDTH)]
    properties += [f"--r1-{index:03d}" for index in range(WIDTH)]
    css_parts = [
        font_faces("qkv", qkv_fonts),
        font_faces("attnout", projection_fonts),
        registrations(properties),
    ]

    q_stage = selected_container_stage(
        stage_name=f"stream-q-{token_count}",
        normalized=normalized[target],
        output_indices=list(range(WIDTH)),
        output_names=[f"--q-{index:03d}" for index in range(WIDTH)],
        fonts=qkv_fonts,
        bases=qkv_bases,
        input_range=input_range,
        quantized=q_qkv,
        bias=qkv_bias,
        output_ranges=output_ranges,
    )
    def update_declarations(
        source: int, key_values: list[str] | None
    ) -> list[str]:
        declarations = []
        if key_values is not None:
            for head in range(HEADS):
                start = head * HEAD_WIDTH
                dot = " + ".join(
                    f"var(--q-{start + local:03d}) * {key_values[start + local]}"
                    for local in range(HEAD_WIDTH)
                )
                declarations.append(
                    f"--score-{head}:calc(({dot}) / {math.sqrt(HEAD_WIDTH)})"
                )
        out_bank = "a" if source % 2 == 0 else "b"
        if source == 0:
            for head in range(HEADS):
                declarations.extend((
                    f"--m-{out_bank}-{head}:var(--score-{head})",
                    f"--l-{out_bank}-{head}:1",
                ))
            for index in range(WIDTH):
                declarations.append(
                    f"--acc-{out_bank}-{index:03d}:var(--kv-{WIDTH + index:04d})"
                )
        else:
            old_bank = "b" if out_bank == "a" else "a"
            for head in range(HEADS):
                declarations.extend((
                    f"--m-{out_bank}-{head}:max(var(--m-{old_bank}-{head}),"
                    f"var(--score-{head}))",
                    f"--old-w-{head}:exp(var(--m-{old_bank}-{head}) - "
                    f"var(--m-{out_bank}-{head}))",
                    f"--new-w-{head}:exp(var(--score-{head}) - "
                    f"var(--m-{out_bank}-{head}))",
                    f"--l-{out_bank}-{head}:calc(var(--l-{old_bank}-{head}) * "
                    f"var(--old-w-{head}) + var(--new-w-{head}))",
                ))
            for index in range(WIDTH):
                head = index // HEAD_WIDTH
                declarations.append(
                    f"--acc-{out_bank}-{index:03d}:calc("
                    f"var(--acc-{old_bank}-{index:03d}) * var(--old-w-{head}) + "
                    f"var(--kv-{WIDTH + index:04d}) * var(--new-w-{head}))"
                )
        return declarations

    kv_stages = []
    external_mix = args.key_transport == "container"
    for source in range(token_count):
        stage_name = (
            f"stream-kv-{token_count}-{source}"
            if external_mix else f"stream-ka-v-{token_count}-{source}"
        )
        if external_mix:
            declarations = update_declarations(
                source, [f"var(--kv-{index:04d})" for index in range(WIDTH)]
            )
            css_parts.append(f'.mix-source-{source}{{{";".join(declarations)}}}')
            output_indices = list(range(WIDTH, QKV_WIDTH))
            output_names = [f"--kv-{index:04d}" for index in range(2 * WIDTH)]
            leading_metrics = None
            slot_declarations = None
            extra_rules = None
        else:
            leading_metrics = []
            key_metrics = []
            key_anchors = []
            for index in range(WIDTH):
                output = WIDTH + index
                anchor = f"--{stage_name}-k-{index}"
                key_anchors.append(anchor)
                characters = "".join(
                    f"&#x{start + output:X};" for start in qkv_fonts.codepoint_starts
                )
                key_metrics.append(
                    f'<i class="metric" style="anchor-name:{anchor}">{characters}</i>'
                )
            score_range = float(max(np.max(np.abs(scores)) * 1.2, 1.0))
            score_scale = 64
            score_base = math.ceil(score_range * score_scale) + 128
            score_viewport = 4096
            score_timelines = [f"--{stage_name}-st-{head}" for head in range(HEADS)]
            score_progress = [f"--{stage_name}-sp-{head}" for head in range(HEADS)]
            score_keyframes = [f"{stage_name}-sk-{head}" for head in range(HEADS)]
            css_parts.append("".join(
                f'@property {name}'
                '{syntax:"<number>";inherits:true;initial-value:-1}'
                for name in score_progress
            ))
            extra_rules = ["".join(
                f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
                for progress, keyframe in zip(
                    score_progress, score_keyframes, strict=True
                )
            )]
            score_metrics = []
            for head in range(HEADS):
                start = head * HEAD_WIDTH
                terms = []
                for local in range(HEAD_WIDTH):
                    index = start + local
                    output = WIDTH + index
                    factor = input_range * q_qkv.scales[output]
                    key_length = (
                        f"((anchor-size({key_anchors[index]} width) * {UNITS_PER_EM} / "
                        f"{FONT_SIZE} - {int(qkv_bases[output])}px) * "
                        f"{css_number(factor)} + {css_number(qkv_bias[output])}px)"
                    )
                    terms.append(f"var(--q-{index:03d}) * {key_length}")
                extra_rules.append(
                    f".score-{head}{{width:calc({score_base}px + {score_scale} * "
                    f"(({' + '.join(terms)}) / {math.sqrt(HEAD_WIDTH)}))}}"
                )
                score_metrics.append(
                    f'<i class="score-metric score-{head}" '
                    f'style="view-timeline:{score_timelines[head]} inline"></i>'
                )
            leading_metrics.append(
                '<div class="score-scroller"><div class="score-track">'
                + "".join(key_metrics) + "".join(score_metrics) + "</div></div>"
            )
            extra_rules.extend((
                f".score-scope{{timeline-scope:{','.join(score_timelines)}}}",
                ".score-scroller{position:fixed;left:0;top:-58000px;"
                f"width:{score_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}",
                f".score-track{{position:relative;width:{score_viewport * 3}px;height:1px}}",
                ".score-track>.metric{position:absolute}",
                ".score-metric{position:absolute;left:0;top:0;display:block;height:1px}",
            ))
            slot_declarations = [
                f"animation-name:{','.join(score_keyframes)}",
                "animation-duration:1s",
                "animation-timing-function:linear",
                "animation-fill-mode:both",
                f"animation-timeline:{','.join(score_timelines)}",
                "animation-range:cover",
            ]
            slot_declarations.extend(
                f"--score-{head}:calc(({score_viewport} / "
                f"var({score_progress[head]}) - {score_viewport} - {score_base}) / "
                f"{score_scale})"
                for head in range(HEADS)
            )
            slot_declarations.extend(update_declarations(source, None))
            output_indices = list(range(2 * WIDTH, QKV_WIDTH))
            output_names = [f"--kv-{WIDTH + index:04d}" for index in range(WIDTH)]
        kv_stages.append(selected_container_stage(
            stage_name=stage_name,
            normalized=normalized[source],
            output_indices=output_indices,
            output_names=output_names,
            fonts=qkv_fonts,
            bases=qkv_bases,
            input_range=input_range,
            quantized=q_qkv,
            bias=qkv_bias,
            output_ranges=output_ranges,
            leading_metrics=leading_metrics,
            slot_declarations=slot_declarations,
            extra_rules=extra_rules,
            wrapper_class="score-scope" if not external_mix else None,
        ))

    final_bank = "a" if (token_count - 1) % 2 == 0 else "b"
    css_parts.append(
        ".finalize{" + ";".join(
            f"--context-{index:03d}:calc(var(--acc-{final_bank}-{index:03d}) / "
            f"var(--l-{final_bank}-{index // HEAD_WIDTH}))"
            for index in range(WIDTH)
        ) + "}"
    )

    context_range = float(max(np.max(np.abs(context)) * 1.05, 0.05))
    viewport = 2 ** math.ceil(math.log2(max(
        1024,
        int(np.max(projection_bases)) * FONT_SIZE / UNITS_PER_EM * 1.25,
    )))
    timelines = [f"--pt-{index}" for index in range(WIDTH)]
    progress = [f"--pp-{index}" for index in range(WIDTH)]
    keyframes = [f"pk-{index}" for index in range(WIDTH)]
    css_parts.append(timeline_rules(progress, keyframes))
    context_names = [f"--context-{index:03d}" for index in range(WIDTH)]
    families = ",".join(f"attnoutS{index}" for index in range(len(projection_fonts.names)))
    css_parts.append(
        f'.projection-stage{{timeline-scope:{",".join(timelines)};'
        f"font:normal {FONT_SIZE}px attnoutS0;font-family:{families};font-kerning:none;"
        f"font-variation-settings:{pack_font_settings(context_names, context_range, 0)}}}"
    )
    output_declarations = []
    for index, value_name in enumerate(progress):
        raw = f"--praw-{index:03d}"
        factor = context_range * q_projection.scales[index]
        output_declarations.extend((
            f"{raw}:calc(({viewport} / var({value_name}) - {viewport}) * "
            f"{UNITS_PER_EM} / {FONT_SIZE} - {int(projection_bases[index])})",
            f"--attn-out-{index:03d}:calc(var({raw}) * {css_number(factor)} + "
            f"({css_number(projection_bias[index])}))",
            f"--r1-{index:03d}:calc({css_number(x[target, index])} + "
            f"var(--attn-out-{index:03d}))",
        ))
    consumer_count = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
        css_parts.append(
            f".projection-result-{consumer}{{"
            f"animation-name:{','.join(keyframes[start:stop])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[start:stop])};"
            "animation-range:cover;"
            + ";".join(output_declarations[start * 3:stop * 3]) + "}"
        )
    metrics = shared_metrics(
        class_name="projection-metric",
        timeline_names=timelines,
        codepoint_starts=projection_fonts.codepoint_starts,
        output_count=WIDTH,
    )
    css_parts.append(
        ".projection-scroller{position:fixed;left:0;top:-60000px;"
        f"width:{viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".projection-track{{position:relative;width:{viewport * 3}px;height:1px}}"
        ".projection-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
    )

    child = '<output id="attention-result"></output>'
    child = consumer_tree("projection-result", consumer_count, child)
    child = (
        '<div class="projection-stage"><div class="projection-scroller">'
        f'<div class="projection-track">{metrics}</div></div>{child}</div>'
    )
    child = f'<div class="finalize">{child}</div>'
    for source in reversed(range(token_count)):
        if external_mix:
            child = f'<div class="mix-source-{source}">{child}</div>'
        child = kv_stages[source].replace("{child}", child)
    child = q_stage.replace("{child}", child)

    css_path.write_text("".join(css_parts))
    tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        f'<title>{token_count}-token streaming GPT-2 attention</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={tag}">'
        f'<h1>{token_count}-token streaming GPT-2 attention fixture</h1>{child}'
    )
    kv_prefix = "stream-kv" if external_mix else "stream-ka-v"
    stage_paths = [OUT / f"stream-q-{token_count}.css"] + [
        OUT / f"{kv_prefix}-{token_count}-{source}.css" for source in range(token_count)
    ]
    reference = {
        "tokenIds": token_ids,
        "contextLength": token_count,
        "target": target,
        "qkvTransport": transport_name,
        "rangeCalibration": "4096 random token/position states, 1.2 margin",
        "qkvPackingRmse": float(np.sqrt(np.mean((qkv - qkv_unpacked) ** 2))),
        "qkvClippedFraction": float(np.mean(np.abs(qkv_unpacked) > output_ranges)),
        "scores": scores.tolist(),
        "probabilities": probabilities.tolist(),
        "context": context.tolist(),
        "residual": residual.tolist(),
        "htmlBytes": html_path.stat().st_size,
        "cssBytes": css_path.stat().st_size,
        "stageCssBytes": sum(path.stat().st_size for path in stage_paths),
        "fontBytes": sum(
            (OUT / f"{name}.woff2").stat().st_size
            for name in (*qkv_fonts.names, *projection_fonts.names)
        ),
        "qOutputs": WIDTH,
        "kvOutputsPerSource": 2 * WIDTH,
        "keyOutputsTransportedPerSource": WIDTH if external_mix else 0,
        "valueOutputsTransportedPerSource": WIDTH,
        "liveAttentionStateValues": 2 * WIDTH + 4 * HEADS,
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "context": token_count,
        "qkv_rmse": reference["qkvPackingRmse"],
        "clipped": reference["qkvClippedFraction"],
        "html_bytes": reference["htmlBytes"],
        "css_bytes": reference["cssBytes"],
        "stage_css_bytes": reference["stageCssBytes"],
    })


if __name__ == "__main__":
    main()
