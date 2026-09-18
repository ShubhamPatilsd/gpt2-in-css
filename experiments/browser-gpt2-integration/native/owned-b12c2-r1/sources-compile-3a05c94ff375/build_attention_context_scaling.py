#!/usr/bin/env python3
"""Build HTML/CSS-only last-token attention pages at several context lengths."""

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
from build_multitoken_attention_css import (
    FONT_SIZE,
    HEADS,
    HEAD_WIDTH,
    OUTPUTS_PER_CONSUMER,
    QKV_WIDTH,
    consumer_tree,
    container_qkv_stage,
    registrations,
    shared_metrics,
    softmax,
    timeline_rules,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


TOKENS = (
    15496, 995, 11, 428, 318, 257, 1332, 13,
    0, 1, 2, 3, 4, 5, 6, 7,
    8, 9, 10, 12, 14, 15, 16, 17,
    18, 19, 20, 21, 22, 23, 24, 25,
)
PRECISION_REPORT = OUT / "qkv-transport-precision.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=int, choices=(1, 2, 4, 8, 16), required=True)
    parser.add_argument(
        "--qkv-transport", choices=("container", "timeline"), default="container"
    )
    args = parser.parse_args()
    token_ids = TOKENS[: args.context]
    target = len(token_ids) - 1
    stem = f"attention-context-{len(token_ids)}-qkv-{args.qkv_transport}"
    html_path = OUT / f"{stem}.html"
    css_path = OUT / f"{stem}.css"
    reference_path = OUT / f"{stem}-reference.json"

    precision = json.loads(PRECISION_REPORT.read_text())
    calibrated = precision["margins"]["1.2"]
    output_ranges = np.asarray(calibrated["perChannelRanges"], dtype=np.float64)
    input_range = float(precision["inputAbsMaxCalibration"] * 1.05)
    if output_ranges.shape != (QKV_WIDTH,):
        raise ValueError("QKV calibration does not contain 2,304 ranges")

    tensors = SafeTensors(MODEL_PATH)
    token_embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position_embeddings = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    x = np.stack(
        [token_embeddings[token] + position_embeddings[position]
         for position, token in enumerate(token_ids)]
    )
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    normalized = np.stack([layer_norm(row, gamma, beta) for row in x])
    if float(np.max(np.abs(normalized))) > input_range:
        raise ValueError("fixture exceeds the calibrated QKV input range")

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
    qkv = qkv_packed if args.qkv_transport == "container" else qkv_unpacked
    query, key, value = np.split(qkv, 3, axis=1)
    query = query.reshape(len(token_ids), HEADS, HEAD_WIDTH)
    key = key.reshape(len(token_ids), HEADS, HEAD_WIDTH)
    value = value.reshape(len(token_ids), HEADS, HEAD_WIDTH)

    scores = np.empty((HEADS, len(token_ids)))
    probabilities = np.empty_like(scores)
    context = np.empty((HEADS, HEAD_WIDTH))
    for head in range(HEADS):
        scores[head] = np.asarray(
            [np.dot(query[target, head], key[source, head]) / math.sqrt(HEAD_WIDTH)
             for source in range(len(token_ids))]
        )
        probabilities[head] = softmax(scores[head])
        context[head] = sum(
            probabilities[head, source] * value[source, head]
            for source in range(len(token_ids))
        )
    context = context.reshape(WIDTH)

    projection_weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    projection_bias = np.asarray(
        tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64
    )
    q_projection = quantize_float_rows(projection_weight, bits=QUANT_BITS)
    projected = q_projection.reconstructed @ context + projection_bias
    residual = x[target] + projected

    qkv_fonts = build_font_group(
        "qkv-rowbase",
        q_qkv.codes,
        rebuild=False,
        row_specific_bases=True,
    )
    projection_fonts = build_font_group(
        "attn-out-rowbase",
        q_projection.codes,
        rebuild=False,
        row_specific_bases=True,
    )
    if qkv_fonts.row_bases is None or projection_fonts.row_bases is None:
        raise ValueError("row-specific bases are required")
    qkv_bases = np.sum(np.stack(qkv_fonts.row_bases), axis=0)
    projection_bases = np.sum(np.stack(projection_fonts.row_bases), axis=0)
    context_range = float(max(np.max(np.abs(context)) * 1.05, 0.05))
    projection_viewport = 2 ** math.ceil(
        math.log2(max(
            1024,
            int(np.max(projection_bases)) * FONT_SIZE / UNITS_PER_EM * 1.25,
        ))
    )
    qkv_viewport = 2 ** math.ceil(
        math.log2(max(
            1024,
            int(np.max(qkv_bases)) * FONT_SIZE / UNITS_PER_EM * 1.25,
        ))
    )

    properties = []
    for token in range(len(token_ids)):
        properties.extend(f"--qkv-{token}-{index:04d}" for index in range(QKV_WIDTH))
    properties.extend(f"--score-{head}-{source}" for head in range(HEADS)
                      for source in range(len(token_ids)))
    properties.extend(f"--context-{index:03d}" for index in range(WIDTH))
    properties.extend(f"--attn-out-{index:03d}" for index in range(WIDTH))
    properties.extend(f"--r1-{index:03d}" for index in range(WIDTH))
    css_parts = [
        font_faces("qkv", qkv_fonts),
        font_faces("attnout", projection_fonts),
        registrations(properties),
    ]

    qkv_stages = []
    if args.qkv_transport == "container":
        for token in range(len(token_ids)):
            qkv_stages.append(container_qkv_stage(
                token=token,
                normalized=normalized[token],
                qkv_fonts=qkv_fonts,
                qkv_bases=qkv_bases,
                qkv_range=input_range,
                q_qkv=q_qkv,
                qkv_bias=qkv_bias,
                output_ranges=output_ranges,
                css_stem=f"attention-context-qkv-token-{token}",
                element_name=f"context-qkv-token-{token}",
            ))
    else:
        for token in range(len(token_ids)):
            timelines = [f"--qt-{token}-{index}" for index in range(QKV_WIDTH)]
            progress = [f"--qp-{token}-{index}" for index in range(QKV_WIDTH)]
            keyframes = [f"qk-{token}-{index}" for index in range(QKV_WIDTH)]
            css_parts.append(timeline_rules(progress, keyframes))
            input_names = [f"--n1-{token}-{index:03d}" for index in range(WIDTH)]
            inputs = ";".join(
                f"{name}:{css_number(value)}"
                for name, value in zip(input_names, normalized[token], strict=True)
            )
            families = ",".join(f"qkvS{index}" for index in range(len(qkv_fonts.names)))
            css_parts.append(
                f'.qkv-stage-{token}{{{inputs};timeline-scope:{",".join(timelines)};'
                f"font:normal {FONT_SIZE}px qkvS0;font-family:{families};font-kerning:none;"
                f"font-variation-settings:{pack_font_settings(input_names, input_range, 0)}}}"
            )
            declarations = []
            for index, value in enumerate(progress):
                raw = f"--qraw-{token}-{index:04d}"
                factor = input_range * q_qkv.scales[index]
                declarations.extend((
                    f"{raw}:calc(({qkv_viewport} / var({value}) - {qkv_viewport}) * "
                    f"{UNITS_PER_EM} / {FONT_SIZE} - {int(qkv_bases[index])})",
                    f"--qkv-{token}-{index:04d}:calc(var({raw}) * "
                    f"{css_number(factor)} + ({css_number(qkv_bias[index])}))",
                ))
            consumer_count = math.ceil(QKV_WIDTH / OUTPUTS_PER_CONSUMER)
            for consumer in range(consumer_count):
                start = consumer * OUTPUTS_PER_CONSUMER
                stop = min(start + OUTPUTS_PER_CONSUMER, QKV_WIDTH)
                css_parts.append(
                    f".qkv-result-{token}-{consumer}{{"
                    f"animation-name:{','.join(keyframes[start:stop])};"
                    "animation-duration:1s;animation-timing-function:linear;"
                    "animation-fill-mode:both;"
                    f"animation-timeline:{','.join(timelines[start:stop])};"
                    "animation-range:cover;"
                    + ";".join(declarations[start * 2:stop * 2]) + "}"
                )
            metrics = shared_metrics(
                class_name="qkv-metric",
                timeline_names=timelines,
                codepoint_starts=qkv_fonts.codepoint_starts,
                output_count=QKV_WIDTH,
            )
            qkv_stages.append(
                f'<div class="qkv-stage-{token}"><div class="qkv-scroller">'
                f'<div class="qkv-track">{metrics}</div></div>{{child}}</div>'
            )
        css_parts.append(
            ".qkv-scroller{position:fixed;left:0;top:-50000px;"
            f"width:{qkv_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
            f".qkv-track{{position:relative;width:{qkv_viewport * 3}px;height:1px}}"
            ".qkv-metric{position:absolute;left:0;top:0;display:inline-flex;"
            "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        )

    mix = []
    for head in range(HEADS):
        q_start = head * HEAD_WIDTH
        k_start = WIDTH + head * HEAD_WIDTH
        for source in range(len(token_ids)):
            dot = " + ".join(
                f"var(--qkv-{target}-{q_start + local:04d}) * "
                f"var(--qkv-{source}-{k_start + local:04d})"
                for local in range(HEAD_WIDTH)
            )
            mix.append(
                f"--score-{head}-{source}:calc(({dot}) / {math.sqrt(HEAD_WIDTH)})"
            )
        score_vars = [f"var(--score-{head}-{source})"
                      for source in range(len(token_ids))]
        mix.append(f"--score-max-{head}:max({','.join(score_vars)})")
        denominator = " + ".join(
            f"exp(var(--score-{head}-{source}) - var(--score-max-{head}))"
            for source in range(len(token_ids))
        )
        mix.append(f"--score-den-{head}:calc({denominator})")
        for source in range(len(token_ids)):
            mix.append(
                f"--prob-{head}-{source}:calc(exp(var(--score-{head}-{source}) - "
                f"var(--score-max-{head})) / var(--score-den-{head}))"
            )
    for index in range(WIDTH):
        head = index // HEAD_WIDTH
        value_index = 2 * WIDTH + index
        weighted = " + ".join(
            f"var(--prob-{head}-{source}) * "
            f"var(--qkv-{source}-{value_index:04d})"
            for source in range(len(token_ids))
        )
        mix.append(f"--context-{index:03d}:calc({weighted})")
    css_parts.append(f'.attention-mix{{{";".join(mix)}}}')

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
    declarations = []
    for index, value in enumerate(progress):
        raw = f"--praw-{index:03d}"
        factor = context_range * q_projection.scales[index]
        declarations.extend((
            f"{raw}:calc(({projection_viewport} / var({value}) - {projection_viewport}) "
            f"* {UNITS_PER_EM} / {FONT_SIZE} - {int(projection_bases[index])})",
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
            + ";".join(declarations[start * 3:stop * 3]) + "}"
        )
    metrics = shared_metrics(
        class_name="projection-metric",
        timeline_names=timelines,
        codepoint_starts=projection_fonts.codepoint_starts,
        output_count=WIDTH,
    )
    css_parts.append(
        ".projection-scroller{position:fixed;left:0;top:-60000px;"
        f"width:{projection_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".projection-track{{position:relative;width:{projection_viewport * 3}px;height:1px}}"
        ".projection-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
    )

    child = '<output id="attention-result"></output>'
    child = consumer_tree("projection-result", consumer_count, child)
    child = (
        '<div class="projection-stage"><div class="projection-scroller">'
        f'<div class="projection-track">{metrics}</div></div>{child}</div>'
    )
    child = f'<div class="attention-mix">{child}</div>'
    for token, stage in reversed(list(enumerate(qkv_stages))):
        if args.qkv_transport == "timeline":
            child = consumer_tree(
                f"qkv-result-{token}",
                math.ceil(QKV_WIDTH / OUTPUTS_PER_CONSUMER),
                child,
            )
        child = stage.replace("{child}", child)

    css_path.write_text("".join(css_parts))
    tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        f'<title>{len(token_ids)}-token GPT-2 attention scaling</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={tag}">'
        f'<h1>{len(token_ids)}-token GPT-2 attention scaling fixture</h1>' + child
    )
    stage_bytes = (
        sum(
            (OUT / f"attention-context-qkv-token-{token}.css").stat().st_size
            for token in range(len(token_ids))
        )
        if args.qkv_transport == "container" else 0
    )
    reference_path.write_text(json.dumps({
        "tokenIds": token_ids,
        "contextLength": len(token_ids),
        "target": target,
        "qkvTransport": args.qkv_transport,
        "rangeCalibration": "4096 random token/position states, 1.2 margin",
        "qkvPackingRmse": float(np.sqrt(np.mean((qkv - qkv_unpacked) ** 2))),
        "qkvClippedFraction": (
            float(np.mean(np.abs(qkv_unpacked) > output_ranges))
            if args.qkv_transport == "container" else 0.0
        ),
        "scores": scores.tolist(),
        "probabilities": probabilities.tolist(),
        "context": context.tolist(),
        "residual": residual.tolist(),
        "htmlBytes": html_path.stat().st_size,
        "cssBytes": css_path.stat().st_size,
        "stageCssBytes": stage_bytes,
        "fontBytes": sum(
            (OUT / f"{name}.woff2").stat().st_size
            for name in (*qkv_fonts.names, *projection_fonts.names)
        ),
    }, indent=2) + "\n")
    print({
        "context": len(token_ids),
        "qkv_transport": args.qkv_transport,
        "qkv_rmse": float(np.sqrt(np.mean((qkv - qkv_unpacked) ** 2))),
        "clipped": float(np.mean(np.abs(qkv_unpacked) > output_ranges)),
        "html_bytes": html_path.stat().st_size,
        "css_bytes": css_path.stat().st_size,
        "stage_css_bytes": stage_bytes,
    })


if __name__ == "__main__":
    main()
