#!/usr/bin/env python3
"""Build matched real GPT-2 QKV projections with direct CSS and HVAR transport."""

from __future__ import annotations

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
    OUTPUTS_PER_CONSUMER,
    consumer_tree,
    registrations,
    shared_metrics,
    timeline_rules,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows
from build_direct_css_block import dot, prop


TOKENS = (15496, 995)
QKV_WIDTH = WIDTH * 3
REFERENCE = OUT / "qkv-transport-reference.json"
EASING_STOPS = 257
PACK_VARIANTS = ((7, 2), (6, 3))
CONTAINER_PACK_VARIANTS = ((8, 3, 1), (10, 3, 64), (12, 2, 1))


def inputs(prefix: str, values: np.ndarray) -> str:
    return ";".join(
        f"{prop(prefix, index)}:{css_number(value)}"
        for index, value in enumerate(values)
    )


def build_direct(
    normalized: np.ndarray,
    quantized,
    bias: np.ndarray,
) -> dict[str, int]:
    output_names = [prop("o", index) for index in range(QKV_WIDTH)]
    declarations = [inputs("i", normalized[0])]
    for output in range(QKV_WIDTH):
        expression = dot(quantized.codes[output], "i")
        declarations.append(
            f"{output_names[output]}:calc(({expression})*"
            f"{css_number(quantized.scales[output])} + "
            f"({css_number(bias[output])}))"
        )
    css = (
        registrations(output_names)
        + "html,body{margin:0}.model{position:fixed;inset:0;"
        + ";".join(declarations)
        + "}"
    )
    css_path = OUT / "qkv-transport-direct.css"
    html_path = OUT / "qkv-transport-direct.html"
    css_path.write_text(css)
    digest = hashlib.sha256(css.encode()).hexdigest()[:12]
    html_path.write_text(
        '<!doctype html><meta charset="utf-8"><title>Direct CSS QKV transport</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={digest}">'
        '<output class="model" id="result"></output>'
    )
    return {"htmlBytes": html_path.stat().st_size, "cssBytes": css_path.stat().st_size}


def build_hvar(
    normalized: np.ndarray,
    quantized,
    bias: np.ndarray,
    expected: np.ndarray,
    *,
    easing: bool = False,
) -> dict[str, int]:
    shards = math.ceil(quantized.codes.shape[1] / 256)
    fonts_exist = all(
        (OUT / f"qkv-rowbase-s{shard}.woff2").exists() for shard in range(shards)
    )
    fonts = build_font_group(
        "qkv-rowbase",
        quantized.codes,
        rebuild=not fonts_exist,
        row_specific_bases=True,
    )
    if fonts.row_bases is None:
        raise ValueError("QKV transport requires row-specific font bases")
    bases = np.sum(np.stack(fonts.row_bases), axis=0)
    input_range = float(np.max(np.abs(normalized)) * 1.01)
    viewport = 2 ** math.ceil(
        math.log2(max(1024, int(np.max(bases)) * FONT_SIZE / UNITS_PER_EM * 1.25))
    )
    output_names = [prop("o", index) for index in range(QKV_WIDTH)]
    timeline_names = [f"--qt-{index}" for index in range(QKV_WIDTH)]
    progress_names = [f"--qp-{index}" for index in range(QKV_WIDTH)]
    keyframe_names = [f"qk-{index}" for index in range(QKV_WIDTH)]
    input_names = [prop("i", index) for index in range(WIDTH)]
    families = ",".join(f"qkvS{index}" for index in range(len(fonts.names)))
    stem = "qkv-transport-hvar-easing" if easing else "qkv-transport-hvar"
    css_parts = [
        font_faces("qkv", fonts),
        registrations(output_names),
    ]
    metric_markup = ""
    declarations = []
    if easing:
        output_min = float(math.floor(np.min(expected)) - 1)
        output_max = float(math.ceil(np.max(expected)) + 1)
        geometry_scale = viewport * 0.5 / (output_max - output_min)
        geometry_offset = viewport * 0.25 - geometry_scale * output_min
        samples = np.linspace(output_max, output_min, EASING_STOPS)
        easing_output = (samples - output_min) / (output_max - output_min)
        easing_progress = viewport / (viewport + geometry_offset + geometry_scale * samples)
        stops = [
            f"{css_number(easing_output[0])} 0%",
            *(
                f"{css_number(value)} {css_number(progress * 100)}%"
                for progress, value in zip(easing_progress, easing_output, strict=True)
            ),
        ]
        css_parts.append(
            "".join(
                f"@keyframes {keyframe}{{"
                f"from{{{output_names[index]}:{css_number(output_min)}}}"
                f"to{{{output_names[index]}:{css_number(output_max)}}}}}"
                for index, keyframe in enumerate(keyframe_names)
            )
        )
        css_parts.append(
            f'.stage{{{inputs("i", normalized[0])};timeline-scope:{",".join(timeline_names)};'
            f"font:normal {FONT_SIZE}px qkvS0;font-family:{families};font-kerning:none;"
            f"font-variation-settings:{pack_font_settings(input_names, input_range, 0)};"
            f"--qkv-ease:linear({','.join(stops)})}}"
        )
        metrics = []
        for output in range(QKV_WIDTH):
            factor = input_range * quantized.scales[output]
            multiplier = geometry_scale * factor * UNITS_PER_EM / FONT_SIZE
            constant = geometry_offset + geometry_scale * (bias[output] - factor * bases[output])
            characters = "".join(
                f"&#x{start + output:X};" for start in fonts.codepoint_starts
            )
            metrics.append(
                f'<i class="metric" style="view-timeline:{timeline_names[output]} inline;'
                f"width:calc-size(max-content,calc(size * {css_number(multiplier)} + "
                f'{css_number(constant)} * 1px))">{characters}</i>'
            )
        metric_markup = "".join(metrics)
    else:
        css_parts.extend(
            [
                timeline_rules(progress_names, keyframe_names),
                f'.stage{{{inputs("i", normalized[0])};timeline-scope:{",".join(timeline_names)};'
                f"font:normal {FONT_SIZE}px qkvS0;font-family:{families};font-kerning:none;"
                f"font-variation-settings:{pack_font_settings(input_names, input_range, 0)}}}",
            ]
        )
        for output, progress in enumerate(progress_names):
            raw = (
                f"(({viewport} / var({progress}) - {viewport}) * "
                f"{UNITS_PER_EM} / {FONT_SIZE} - {int(bases[output])})"
            )
            declarations.append(
                f"{output_names[output]}:calc({raw} * "
                f"{css_number(input_range * quantized.scales[output])} + "
                f"({css_number(bias[output])}))"
            )
        metric_markup = shared_metrics(
            class_name="metric",
            timeline_names=timeline_names,
            codepoint_starts=fonts.codepoint_starts,
            output_count=QKV_WIDTH,
        )
    consumer_count = math.ceil(QKV_WIDTH / OUTPUTS_PER_CONSUMER)
    for consumer in range(consumer_count):
        start = consumer * OUTPUTS_PER_CONSUMER
        stop = min(start + OUTPUTS_PER_CONSUMER, QKV_WIDTH)
        css_parts.append(
            f".result-{consumer}{{animation-name:{','.join(keyframe_names[start:stop])};"
            f"animation-duration:1s;animation-timing-function:{'var(--qkv-ease)' if easing else 'linear'};"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(timeline_names[start:stop])};"
            "animation-range:cover;"
            + ("" if easing else ";".join(declarations[start:stop]))
            + "}"
        )
    css_parts.append(
        ".scroller{position:fixed;left:0;top:-50000px;"
        f"width:{viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".track{{position:relative;width:{viewport * 3}px;height:1px}}"
        ".metric{position:absolute;left:0;top:0;display:inline-flex;"
        "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
    )
    child = '<output id="result"></output>'
    child = consumer_tree("result", consumer_count, child)
    html = (
        '<!doctype html><meta charset="utf-8"><title>HVAR QKV transport</title>'
        f'<link rel="stylesheet" href="{stem}.css">'
        f'<main class="stage"><div class="scroller"><div class="track">{metric_markup}'
        f"</div></div>{child}</main>"
    )
    css_path = OUT / f"{stem}.css"
    html_path = OUT / f"{stem}.html"
    css_path.write_text("".join(css_parts))
    html_path.write_text(html)
    return {
        "htmlBytes": html_path.stat().st_size,
        "cssBytes": css_path.stat().st_size,
        "fontBytes": sum((OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "timelines": QKV_WIDTH,
        "consumers": consumer_count,
        "easingStops": EASING_STOPS if easing else None,
    }


def build_hvar_packed(
    normalized: np.ndarray,
    quantized,
    bias: np.ndarray,
    expected: np.ndarray,
    *,
    bits: int,
    digits: int,
) -> dict[str, int]:
    levels = (1 << bits) - 1
    radix = 1 << bits
    outputs_per_packet = digits * 2
    shards = math.ceil(quantized.codes.shape[1] / 256)
    fonts = build_font_group(
        "qkv-rowbase",
        quantized.codes,
        rebuild=False,
        row_specific_bases=True,
    )
    if fonts.row_bases is None:
        raise ValueError("packed QKV transport requires row-specific font bases")
    bases = np.sum(np.stack(fonts.row_bases), axis=0)
    input_range = float(np.max(np.abs(normalized)) * 1.01)
    output_range = np.maximum(np.max(np.abs(expected), axis=0) * 1.1, 0.05)
    output_names = [prop("o", index) for index in range(QKV_WIDTH)]
    input_names = [prop("i", index) for index in range(WIDTH)]
    families = ",".join(f"qkvS{index}" for index in range(len(fonts.names)))
    packet_count = math.ceil(QKV_WIDTH / outputs_per_packet)
    timeline_names = [
        name
        for packet in range(packet_count)
        for name in (f"--pkt-x-{packet}", f"--pkt-y-{packet}")
    ]
    progress_names = [
        name
        for packet in range(packet_count)
        for name in (f"--pkp-x-{packet}", f"--pkp-y-{packet}")
    ]
    keyframe_names = [
        name
        for packet in range(packet_count)
        for name in (f"pkk-x-{packet}", f"pkk-y-{packet}")
    ]
    css_parts = [
        font_faces("qkv", fonts),
        registrations(output_names),
        timeline_rules(progress_names, keyframe_names),
        f'.stage{{{inputs("i", normalized[0])};anchor-scope:all;'
        f"timeline-scope:{','.join(timeline_names)};font:normal {FONT_SIZE}px qkvS0;"
        f"font-family:{families};font-kerning:none;"
        f"font-variation-settings:{pack_font_settings(input_names, input_range, 0)}}}",
    ]
    metrics = []
    for output in range(QKV_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        metrics.append(
            f'<i class="metric" style="anchor-name:--qm-{output}">{characters}</i>'
        )

    packets = []
    output_declarations: list[list[str]] = []
    viewport = radix**digits
    for packet in range(packet_count):
        dimensions = []
        packet_declarations = []
        for axis in range(2):
            codes = []
            for digit in range(digits):
                output = packet * outputs_per_packet + axis * digits + digit
                if output >= QKV_WIDTH:
                    codes.append("0px")
                    continue
                factor = input_range * quantized.scales[output]
                value = (
                    f"((anchor-size(--qm-{output} width) / 1px * "
                    f"{UNITS_PER_EM} / {FONT_SIZE} - {int(bases[output])}) * "
                    f"{css_number(factor)} + ({css_number(bias[output])}))"
                )
                value_range = float(output_range[output])
                codes.append(
                    "round(nearest,clamp(0px,calc(("
                    + value
                    + f" + {css_number(value_range)}) * {levels} / "
                    + f"{css_number(2 * value_range)} * 1px),{levels}px),1px)"
                )
                progress = progress_names[packet * 2 + axis]
                packed = f"round(nearest,({viewport} / var({progress}) - {viewport}),1)"
                if digit == 0:
                    code = f"mod({packed},{radix})"
                elif digit == digits - 1:
                    code = f"round(down,{packed}/{radix ** digit},1)"
                else:
                    code = (
                        f"mod(round(down,{packed}/{radix ** digit},1),"
                        f"{radix})"
                    )
                packet_declarations.append(
                    f"{output_names[output]}:calc(-{css_number(value_range)} + "
                    f"{code} * {css_number(2 * value_range / levels)})"
                )
            dimensions.append(
                "calc(" + " + ".join(
                    f"{code} * {radix ** digit}"
                    for digit, code in enumerate(codes)
                ) + ")"
            )
        packets.append(
            f'<i class="packet" style="view-timeline:{timeline_names[packet * 2]} inline,'
            f'{timeline_names[packet * 2 + 1]} block;width:{dimensions[0]};'
            f'height:{dimensions[1]}"></i>'
        )
        output_declarations.append(packet_declarations)

    packets_per_consumer = 64
    consumer_count = math.ceil(packet_count / packets_per_consumer)
    for consumer in range(consumer_count):
        first_packet = consumer * packets_per_consumer
        stop_packet = min(first_packet + packets_per_consumer, packet_count)
        first_animation = first_packet * 2
        stop_animation = stop_packet * 2
        declarations = [
            declaration
            for packet in range(first_packet, stop_packet)
            for declaration in output_declarations[packet]
        ]
        css_parts.append(
            f".packed-result-{consumer}{{"
            f"animation-name:{','.join(keyframe_names[first_animation:stop_animation])};"
            "animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(timeline_names[first_animation:stop_animation])};"
            "animation-range:cover;"
            + ";".join(declarations)
            + "}"
        )
    css_parts.append(
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}"
        ".scroller{position:fixed;left:-1000000px;top:-1000000px;"
        f"width:{viewport}px;height:{viewport}px;overflow:scroll;visibility:hidden}}"
        f".track{{position:relative;width:{viewport * 10}px;height:{viewport * 10}px}}"
        ".packet{position:absolute;left:0;top:0;display:block}"
    )
    child = '<output id="result"></output>'
    child = consumer_tree("packed-result", consumer_count, child)
    stem = f"qkv-transport-hvar-packed{bits}x{digits}"
    html = (
        '<!doctype html><meta charset="utf-8"><title>Packed HVAR QKV transport</title>'
        f'<link rel="stylesheet" href="{stem}.css">'
        f'<main class="stage"><div class="scroller"><div class="track">'
        f'{"".join(metrics)}{"".join(packets)}</div></div>{child}</main>'
    )
    css_path = OUT / f"{stem}.css"
    html_path = OUT / f"{stem}.html"
    css_path.write_text("".join(css_parts))
    html_path.write_text(html)
    return {
        "htmlBytes": html_path.stat().st_size,
        "cssBytes": css_path.stat().st_size,
        "fontBytes": sum((OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "timelines": packet_count * 2,
        "packets": packet_count,
        "consumers": consumer_count,
        "bits": bits,
        "digitsPerAxis": digits,
        "calibration": "two-case symmetric per-output",
    }


def build_hvar_container_packed(
    normalized: np.ndarray,
    quantized,
    bias: np.ndarray,
    expected: np.ndarray,
    *,
    bits: int,
    digits: int,
    geometry_fraction: int,
) -> dict[str, int]:
    """Pack HVAR outputs into width/height and read them with container units."""
    levels = (1 << bits) - 1
    radix = 1 << bits
    outputs_per_packet = digits * 2
    shards = math.ceil(quantized.codes.shape[1] / 256)
    fonts_exist = all(
        (OUT / f"qkv-rowbase-s{shard}.woff2").exists() for shard in range(shards)
    )
    fonts = build_font_group(
        "qkv-rowbase",
        quantized.codes,
        rebuild=not fonts_exist,
        row_specific_bases=True,
    )
    if fonts.row_bases is None:
        raise ValueError("container-packed QKV transport requires row-specific bases")
    bases = np.sum(np.stack(fonts.row_bases), axis=0)
    input_range = float(np.max(np.abs(normalized)) * 1.01)
    output_range = np.maximum(np.max(np.abs(expected), axis=0) * 1.1, 0.05)
    output_names = [prop("o", index) for index in range(QKV_WIDTH)]
    input_names = [prop("i", index) for index in range(WIDTH)]
    families = ",".join(f"qkvS{index}" for index in range(len(fonts.names)))
    packet_count = math.ceil(QKV_WIDTH / outputs_per_packet)
    css_parts = [
        font_faces("qkv", fonts),
        registrations(output_names),
        f'.stage{{{inputs("i", normalized[0])};anchor-scope:all;'
        f"position:fixed;left:-1000000px;top:-1000000px;width:1px;height:1px;"
        f"font:normal {FONT_SIZE}px qkvS0;font-family:{families};font-kerning:none;"
        f"font-variation-settings:{pack_font_settings(input_names, input_range, 0)}}}",
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}",
        ".cpacket{position:absolute;left:0;top:0;display:block;container-type:size}",
    ]
    metric_groups: list[list[str]] = [[] for _ in range(packet_count)]
    for output in range(QKV_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fonts.codepoint_starts
        )
        metric_groups[output // outputs_per_packet].append(
            f'<i class="metric" style="anchor-name:--qcm-{output}">{characters}</i>'
        )

    dimensions: list[tuple[str, str]] = []
    decode_declarations: list[list[str]] = []
    for packet in range(packet_count):
        packet_dimensions = []
        packet_declarations = []
        for axis in range(2):
            codes = []
            packed = (
                f"round(nearest,100cq{'w' if axis == 0 else 'h'} / 1px * "
                f"{geometry_fraction},1)"
            )
            for digit in range(digits):
                output = packet * outputs_per_packet + axis * digits + digit
                if output >= QKV_WIDTH:
                    codes.append("0px")
                    continue
                factor = input_range * quantized.scales[output]
                value = (
                    f"((anchor-size(--qcm-{output} width) / 1px * "
                    f"{UNITS_PER_EM} / {FONT_SIZE} - {int(bases[output])}) * "
                    f"{css_number(factor)} + ({css_number(bias[output])}))"
                )
                value_range = float(output_range[output])
                codes.append(
                    "round(nearest,clamp(0px,calc(("
                    + value
                    + f" + {css_number(value_range)}) * {levels} / "
                    + f"{css_number(2 * value_range)} * 1px),{levels}px),1px)"
                )
                if digit == 0:
                    code = f"mod({packed},{radix})"
                elif digit == digits - 1:
                    code = f"round(down,{packed}/{radix ** digit},1)"
                else:
                    code = (
                        f"mod(round(down,{packed}/{radix ** digit},1),{radix})"
                    )
                packet_declarations.append(
                    f"{output_names[output]}:calc(-{css_number(value_range)} + "
                    f"{code} * {css_number(2 * value_range / levels)})"
                )
            packed_dimension = " + ".join(
                    f"{code} * {radix ** digit}"
                    for digit, code in enumerate(codes)
            )
            packet_dimensions.append(
                f"calc(({packed_dimension}) / {geometry_fraction})"
            )
        dimensions.append((packet_dimensions[0], packet_dimensions[1]))
        decode_declarations.append(packet_declarations)

    for packet, (width, height) in enumerate(dimensions):
        declarations = [] if packet == 0 else decode_declarations[packet - 1]
        css_parts.append(
            f".cpacket-{packet}{{width:{width};height:{height};"
            + ";".join(declarations)
            + "}"
        )
    css_parts.append(
        ".container-result{" + ";".join(decode_declarations[-1]) + "}"
    )
    child = '<output class="container-result" id="result"></output>'
    for packet in reversed(range(packet_count)):
        child = (
            "".join(metric_groups[packet])
            + f'<i class="cpacket cpacket-{packet}">{child}</i>'
        )
    fraction_suffix = "" if geometry_fraction == 1 else f"f{geometry_fraction}"
    stem = f"qkv-transport-hvar-container{bits}x{digits}{fraction_suffix}"
    html = (
        '<!doctype html><meta charset="utf-8"><title>Container-packed HVAR QKV</title>'
        f'<link rel="stylesheet" href="{stem}.css">'
        f'<main class="stage">{child}</main>'
    )
    css_path = OUT / f"{stem}.css"
    html_path = OUT / f"{stem}.html"
    css_path.write_text("".join(css_parts))
    html_path.write_text(html)
    return {
        "htmlBytes": html_path.stat().st_size,
        "cssBytes": css_path.stat().st_size,
        "fontBytes": sum((OUT / f"{name}.woff2").stat().st_size for name in fonts.names),
        "containers": packet_count,
        "outputsPerContainer": outputs_per_packet,
        "bits": bits,
        "digitsPerAxis": digits,
        "geometryFraction": geometry_fraction,
        "calibration": "two-case symmetric per-output",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.stack(
        [
            np.asarray(
                tensors.tensor("wte.weight")[token]
                + tensors.tensor("wpe.weight")[position],
                dtype=np.float64,
            )
            for position, token in enumerate(TOKENS)
        ]
    )
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    normalized = np.stack([layer_norm(row, gamma, beta) for row in embeddings])
    weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    quantized = quantize_float_rows(weight, bits=QUANT_BITS)
    expected = np.stack([quantized.reconstructed @ row + bias for row in normalized])
    direct = build_direct(normalized, quantized, bias)
    hvar = build_hvar(normalized, quantized, bias, expected)
    hvar_easing = build_hvar(normalized, quantized, bias, expected, easing=True)
    hvar_packed = {
        f"hvarPacked{bits}x{digits}": build_hvar_packed(
            normalized,
            quantized,
            bias,
            expected,
            bits=bits,
            digits=digits,
        )
        for bits, digits in PACK_VARIANTS
    }
    hvar_container_packed = {
        f"hvarContainer{bits}x{digits}{'' if geometry_fraction == 1 else f'F{geometry_fraction}'}": build_hvar_container_packed(
            normalized,
            quantized,
            bias,
            expected,
            bits=bits,
            digits=digits,
            geometry_fraction=geometry_fraction,
        )
        for bits, digits, geometry_fraction in CONTAINER_PACK_VARIANTS
    }
    metadata = {
        "tokens": TOKENS,
        "width": WIDTH,
        "outputs": QKV_WIDTH,
        "terms": int(np.count_nonzero(quantized.codes)),
        "inputs": normalized.tolist(),
        "expected": expected.tolist(),
        "direct": direct,
        "hvar": hvar,
        "hvarEasing": hvar_easing,
        **hvar_packed,
        **hvar_container_packed,
    }
    REFERENCE.write_text(json.dumps(metadata) + "\n")
    print(json.dumps({key: value for key, value in metadata.items() if key != "inputs" and key != "expected"}, indent=2))


if __name__ == "__main__":
    main()
