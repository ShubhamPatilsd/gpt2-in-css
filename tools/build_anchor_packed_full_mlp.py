#!/usr/bin/env python3
"""Build full GPT-2 FC -> GELU -> projection via packed anchor transport."""

from __future__ import annotations

import json
import math
import os
import time

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
    packed_axis_tag,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


SOURCE_LAYOUT = os.environ.get("ANCHOR_PACKED_MLP_LAYOUT", "local")
if SOURCE_LAYOUT not in {"local", "local-2d", "flat-scope", "flat-fixed"}:
    raise ValueError(
        "ANCHOR_PACKED_MLP_LAYOUT must be local, local-2d, flat-scope, "
        "or flat-fixed"
    )
ZERO_ENCODING = os.environ.get("ANCHOR_PACKED_ZERO", "shared")
if ZERO_ENCODING not in {"shared", "literal"}:
    raise ValueError("ANCHOR_PACKED_ZERO must be shared or literal")
LAYOUT_SUFFIX = "" if SOURCE_LAYOUT == "local" else f"-{SOURCE_LAYOUT}"
PACK_BITS = int(os.environ.get("ANCHOR_PACKED_BITS", "6"))
if PACK_BITS not in {3, 4, 6, 8, 9, 10, 12}:
    raise ValueError("ANCHOR_PACKED_BITS must be 3, 4, 6, 8, 9, 10, or 12")
BIT_SUFFIX = "" if PACK_BITS == 6 else f"-b{PACK_BITS}"
SINK_MODE = os.environ.get("ANCHOR_PACKED_SINK", "distributed")
if SINK_MODE not in {"distributed", "single", "packet", "hvar"}:
    raise ValueError(
        "ANCHOR_PACKED_SINK must be distributed, single, packet, or hvar"
    )
SINK_SUFFIX = {
    "distributed": "",
    "single": "-single-sink",
    "packet": "-packet-sink",
    "hvar": "-hvar-sink",
}[SINK_MODE]
HVAR_PROJECTION_BITS = int(os.environ.get("ANCHOR_PACKED_HVAR_BITS", "11"))
HVAR_PROJECTION_SHARD = int(os.environ.get("ANCHOR_PACKED_HVAR_SHARD", "256"))
ZERO_SUFFIX = "" if ZERO_ENCODING == "shared" else "-literal-zero"
SUFFIX = LAYOUT_SUFFIX + BIT_SUFFIX + SINK_SUFFIX + ZERO_SUFFIX
HTML = OUT / f"anchor-packed-full-mlp{SUFFIX}.xhtml"
CSS = OUT / f"anchor-packed-full-mlp{SUFFIX}.css"
REFERENCE = OUT / f"anchor-packed-full-mlp{SUFFIX}-reference.json"
PACK_DIMENSIONS = 2 if SOURCE_LAYOUT == "local-2d" else 1
DUAL_PLANE = PACK_BITS in {8, 10, 12}
BITSTREAM = PACK_BITS == 9
if (DUAL_PLANE or BITSTREAM) and PACK_DIMENSIONS != 2:
    raise ValueError(f"{PACK_BITS}-bit packing requires the local-2d layout")
if BITSTREAM and SINK_MODE == "packet":
    raise ValueError("9-bit bitstream packing does not support the packet sink")
PLANE_BITS = PACK_BITS // 2 if DUAL_PLANE else PACK_BITS
RADIX = 1 << PLANE_BITS
LEVELS = (1 << PACK_BITS) - 1
VALUES_PER_DIMENSION = 24 // PLANE_BITS
PACK = (
    48 // PACK_BITS
    if BITSTREAM
    else VALUES_PER_DIMENSION if DUAL_PLANE
    else VALUES_PER_DIMENSION * PACK_DIMENSIONS
)


def axis_tag(index: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = ""
    value = index
    for _ in range(3):
        digits = alphabet[value % 36] + digits
        value //= 36
    return "A" + digits


def vector_settings(values: np.ndarray) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {css_number(value)}'
        for index, value in enumerate(values)
    )


def input_settings(values: np.ndarray, value_range: float) -> str:
    settings = []
    for index, value in enumerate(values / value_range):
        shard, local = divmod(index, 256)
        settings.append(
            f'"{packed_axis_tag(shard, local)}" {css_number(value)}'
        )
    return ",".join(settings)


def gelu_function() -> str:
    return (
        f"@function --gelu(--z <number>) returns <number>{{"
        f"--t:clamp(-20,calc({css_number(math.sqrt(2 / math.pi))} * "
        "(var(--z) + .044715 * pow(var(--z),3))),20);"
        "result:calc(.5 * var(--z) * "
        "(1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
    )


def digit_expression(
    output: int,
    factor: float,
    bias: float,
    lower: float,
    upper: float,
    base_total: int,
) -> str:
    raw = (
        f"(anchor-size(--a{output:04d} width) * {UNITS_PER_EM} / "
        f"{FONT_SIZE} - {base_total}px)"
    )
    pre = f"({raw} * {css_number(factor)} + ({css_number(bias)}px))"
    return (
        f"round(nearest,clamp(0px,({pre} - ({css_number(lower)}px)) "
        f"* {LEVELS} / {css_number(upper - lower)},{LEVELS}px),1px)"
    )


def decoded_plane(place: int, dimension: str) -> str:
    local_place = place % VALUES_PER_DIMENSION
    unit = "100cqb" if dimension == "block" else "100cqi"
    packed = f"round(nearest,{unit} / 1px,1)"
    if local_place == 0:
        return f"mod({packed},{RADIX})"
    if local_place == VALUES_PER_DIMENSION - 1:
        return f"round(down,{packed}/{RADIX ** local_place},1)"
    return (
        f"mod(round(down,{packed}/{RADIX ** local_place},1),{RADIX})"
    )


def decoded_digit(place: int) -> str:
    if BITSTREAM:
        offset = place * PACK_BITS
        inline = "round(nearest,100cqi / 1px,1)"
        block = "round(nearest,100cqb / 1px,1)"
        if offset + PACK_BITS <= 24:
            return (
                f"mod(round(down,({inline})/{1 << offset},1),"
                f"{1 << PACK_BITS})"
            )
        if offset >= 24:
            return (
                f"mod(round(down,({block})/{1 << (offset - 24)},1),"
                f"{1 << PACK_BITS})"
            )
        low_bits = 24 - offset
        high_bits = PACK_BITS - low_bits
        return (
            f"(mod(round(down,({inline})/{1 << offset},1),"
            f"{1 << low_bits}) + {1 << low_bits} * "
            f"mod({block},{1 << high_bits}))"
        )
    if DUAL_PLANE:
        return (
            f"({decoded_plane(place, 'inline')} + {RADIX} * "
            f"{decoded_plane(place, 'block')})"
        )
    return decoded_plane(
        place,
        "block" if place >= VALUES_PER_DIMENSION else "inline",
    )


def decoded_packet_digit(group: int, place: int) -> str:
    local_place = place % VALUES_PER_DIMENSION
    dimension = "b" if place >= VALUES_PER_DIMENSION else "w"
    if local_place == 0:
        return f"var(--p{dimension}l{group:03d})"
    packed = f"var(--p{dimension}h{group:03d})"
    shifted_place = local_place - 1
    if shifted_place == 0:
        return f"mod(round(nearest,{packed},1),{RADIX})"
    if shifted_place == VALUES_PER_DIMENSION - 2:
        return f"round(down,{packed}/{RADIX ** shifted_place},1)"
    return (
        f"mod(round(down,{packed}/{RADIX ** shifted_place},1),{RADIX})"
    )


def bitstream_dimensions() -> str:
    inline_terms: list[str] = []
    block_terms: list[str] = []
    for place in range(PACK):
        offset = place * PACK_BITS
        digit = f"(var(--d{place}) / 1px)"
        if offset < 24:
            bits_here = min(PACK_BITS, 24 - offset)
            inline_terms.append(
                f"{1 << offset} * mod({digit},{1 << bits_here}) * 1px"
            )
        if offset + PACK_BITS > 24:
            source_shift = max(24 - offset, 0)
            destination_shift = max(offset - 24, 0)
            shifted = (
                digit
                if source_shift == 0
                else f"round(down,{digit}/{1 << source_shift},1)"
            )
            block_terms.append(
                f"{1 << destination_shift} * {shifted} * 1px"
            )
    return (
        f"width:calc({' + '.join(inline_terms)});"
        f"height:calc({' + '.join(block_terms)});"
    )


def main() -> None:
    started = time.perf_counter()
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    attention = q_attention.reconstructed @ n1 + composed_bias
    residual = data["x"] + attention
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    case_inputs = np.stack((n2, np.roll(n2, 1) * 0.8))
    activation_range = float(np.max(np.abs(case_inputs)) * 1.01)

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_projection = quantize_float_rows(
        data["mlp_proj_weight"], bits=QUANT_BITS
    )
    fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    base_total = sum(fonts.bases)
    raw = (case_inputs / activation_range) @ q_fc.codes.T
    factors = activation_range * q_fc.scales
    pre = raw * factors + data["fc_bias"]

    observed_span = np.ptp(pre, axis=0)
    margins = np.maximum(0.05, observed_span * 0.1)
    pre_lo = np.min(pre, axis=0) - margins
    pre_hi = np.max(pre, axis=0) + margins
    codes = np.rint(
        np.clip(
            (pre - pre_lo) * LEVELS / (pre_hi - pre_lo),
            0,
            LEVELS,
        )
    ).astype(np.int16)
    steps = (pre_hi - pre_lo) / LEVELS
    reconstructed_pre = pre_lo + codes * steps
    hidden = gelu_new(reconstructed_pre)

    levels = np.arange(LEVELS + 1)[:, None]
    hidden_grid = gelu_new(pre_lo[None, :] + levels * steps[None, :])
    hidden_lo = np.min(hidden_grid, axis=0)
    hidden_hi = np.max(hidden_grid, axis=0)
    hidden_span = hidden_hi - hidden_lo
    progress = (hidden - hidden_lo) / hidden_span

    projection_weight = q_projection.reconstructed
    projection_base = (
        data["mlp_proj_bias"] + projection_weight @ hidden_lo
    )
    expected = hidden @ projection_weight.T + data["mlp_proj_bias"]
    full_precision_expected = (
        gelu_new(pre) @ projection_weight.T + data["mlp_proj_bias"]
    )
    contribution_matrix = projection_weight * hidden_span[None, :]
    projection_scale = np.maximum.reduce((
        np.maximum(np.abs(projection_base), 1e-6),
        np.max(np.abs(expected), axis=0),
        np.max(np.abs(contribution_matrix), axis=1),
    )) * 1.01
    scaled_base = projection_base / projection_scale
    scaled_expected = expected / projection_scale
    scaled_full_precision_expected = full_precision_expected / projection_scale

    hvar_projection = None
    hvar_fonts = None
    hvar_expected = None
    hvar_base_total = None
    if SINK_MODE == "hvar":
        scaled_contribution = contribution_matrix / projection_scale[:, None]
        hvar_projection = quantize_float_rows(
            scaled_contribution, bits=HVAR_PROJECTION_BITS
        )
        hvar_name = (
            f"mlp-proj-global-a{PACK_BITS}-b{HVAR_PROJECTION_BITS}-"
            f"s{HVAR_PROJECTION_SHARD}"
        )
        hvar_fonts = build_font_group(
            hvar_name,
            hvar_projection.codes,
            shard_size=HVAR_PROJECTION_SHARD,
            rebuild=not (OUT / f"{hvar_name}-s0.woff2").exists(),
            global_axis_offset=0,
        )
        hvar_expected = (
            scaled_base
            + progress @ hvar_projection.reconstructed.T
        )
        hvar_base_total = sum(hvar_fonts.bases)

    zero = vector_settings(np.zeros(WIDTH))
    group_count = math.ceil(MLP_WIDTH / PACK)
    if SINK_MODE in {"single", "hvar"}:
        progress_registrations = "".join(
            f'@property --p{index:04d}{{syntax:"<number>";'
            "inherits:true;initial-value:0}"
            for index in range(MLP_WIDTH)
        )
    elif SINK_MODE == "packet":
        progress_registrations = "".join(
            f'@property --pwl{group:03d}{{syntax:"<number>";'
            "inherits:true;initial-value:0}"
            f'@property --pwh{group:03d}{{syntax:"<number>";'
            "inherits:true;initial-value:0}"
            + (
                f'@property --pbl{group:03d}{{syntax:"<number>";'
                "inherits:true;initial-value:0}"
                f'@property --pbh{group:03d}{{syntax:"<number>";'
                "inherits:true;initial-value:0}"
                if PACK_DIMENSIONS == 2
                else ""
            )
            for group in range(group_count)
        )
    else:
        progress_registrations = ""
    keyframes = []
    if SINK_MODE != "hvar":
        for column in range(MLP_WIDTH):
            contribution = contribution_matrix[:, column] / projection_scale
            keyframes.append(
                f"@keyframes c{column}{{from{{font-variation-settings:"
                f"{'var(--zero)' if ZERO_ENCODING == 'shared' else zero}}}"
                f"to{{font-variation-settings:{vector_settings(contribution)}}}}}"
            )

    source_markup = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:x};" for start in fonts.codepoint_starts
        )
        source_markup.append(
            f'<i class="source" style="anchor-name:--a{output:04d}">'
            f"{characters}</i>"
        )

    pack_rules = []
    contribution_rules = []
    sink_names = []
    sink_delays = []
    sink_math_declarations = []
    for group in range(group_count):
        start = group * PACK
        group_size = min(PACK, MLP_WIDTH - start)
        digits = []
        math_declarations = []
        delays = []
        for place in range(group_size):
            output = start + place
            code = digit_expression(
                output,
                factors[output],
                data["fc_bias"][output],
                pre_lo[output],
                pre_hi[output],
                base_total,
            )
            digits.append(f"--d{place}:{code}")
            digit = decoded_digit(place)
            z = (
                f"({css_number(pre_lo[output])} + {digit} * "
                f"{css_number(steps[output])})"
            )
            math_declarations.extend((
                f"--z{place}:calc({z})",
                f"--h{place}:--gelu(var(--z{place}))",
                f"--p{place}:calc((var(--h{place}) - "
                f"({css_number(hidden_lo[output])})) / "
                f"{css_number(hidden_span[output])})",
            ))
            delays.append(f"calc(-1s * clamp(0,var(--p{place}),1))")
            if SINK_MODE == "single":
                sink_names.append(f"c{output}")
                sink_delays.append(
                    f"calc(-1s * clamp(0,var(--p{output:04d}),1))"
                )
            elif SINK_MODE == "packet":
                packet_digit = decoded_packet_digit(group, place)
                packet_z = (
                    f"({css_number(pre_lo[output])} + {packet_digit} * "
                    f"{css_number(steps[output])})"
                )
                sink_math_declarations.extend((
                    f"--sz{output:04d}:calc({packet_z})",
                    f"--sh{output:04d}:--gelu(var(--sz{output:04d}))",
                    f"--sp{output:04d}:calc((var(--sh{output:04d}) - "
                    f"({css_number(hidden_lo[output])})) / "
                    f"{css_number(hidden_span[output])})",
                ))
                sink_names.append(f"c{output}")
                sink_delays.append(
                    f"calc(-1s * clamp(0,var(--sp{output:04d}),1))"
                )
        digits.extend(
            f"--d{place}:0px" for place in range(group_size, PACK)
        )
        if BITSTREAM:
            dimensions = bitstream_dimensions()
        elif DUAL_PLANE:
            inline_terms = [
                f"{RADIX ** place} * mod(var(--d{place})/1px,{RADIX}) * 1px"
                for place in range(PACK)
            ]
            block_terms = [
                f"{RADIX ** place} * round(down,var(--d{place})/1px/{RADIX},1) * 1px"
                for place in range(PACK)
            ]
            dimensions = (
                f"width:calc({' + '.join(inline_terms)});"
                f"height:calc({' + '.join(block_terms)});"
            )
        else:
            inline_terms = [
                f"{RADIX ** place} * var(--d{place})" if place else "var(--d0)"
                for place in range(VALUES_PER_DIMENSION)
            ]
            dimensions = f"width:calc({' + '.join(inline_terms)});"
            if PACK_DIMENSIONS == 2:
                block_terms = [
                    f"{RADIX ** place} * var(--d{VALUES_PER_DIMENSION + place})"
                    if place
                    else f"var(--d{VALUES_PER_DIMENSION})"
                    for place in range(VALUES_PER_DIMENSION)
                ]
                dimensions += f"height:calc({' + '.join(block_terms)});"
        pack_rules.append(
            f".pack-{group}{{{';'.join(digits)};{dimensions}}}"
        )
        if SINK_MODE == "distributed":
            contribution_rules.append(
                f".contrib-{group}{{{';'.join(math_declarations)};"
                f"animation-name:{','.join(f'c{start + place}' for place in range(group_size))};"
                f"animation-delay:{','.join(delays)}}}"
            )
        elif SINK_MODE in {"single", "hvar"}:
            progress_declarations = []
            for place in range(group_size):
                output = start + place
                digit = decoded_digit(place)
                z = (
                    f"({css_number(pre_lo[output])} + {digit} * "
                    f"{css_number(steps[output])})"
                )
                progress_declarations.extend((
                    f"--z{place}:calc({z})",
                    f"--h{place}:--gelu(var(--z{place}))",
                    f"--p{output:04d}:calc((var(--h{place}) - "
                    f"({css_number(hidden_lo[output])})) / "
                    f"{css_number(hidden_span[output])})"
                ))
            contribution_rules.append(
                f".decode-{group}{{{';'.join(progress_declarations)}}}"
            )
        else:
            packet_declarations = [
                f"--pwl{group:03d}:mod(round(nearest,100cqi / 1px,1),{RADIX})",
                f"--pwh{group:03d}:round(down,(100cqi / 1px) / {RADIX},1)",
            ]
            if PACK_DIMENSIONS == 2:
                packet_declarations.extend((
                    f"--pbl{group:03d}:mod(round(nearest,100cqb / 1px,1),{RADIX})",
                    f"--pbh{group:03d}:round(down,(100cqb / 1px) / {RADIX},1)",
                ))
            contribution_rules.append(
                f".decode-{group}{{{';'.join(packet_declarations)}}}"
            )

    if SINK_MODE == "hvar":
        assert hvar_fonts is not None
        result_contents = "".join(
            f'<i class="projection-metric" data-output="{output}">'
            + "".join(
                f"&#x{codepoint_start + output:x};"
                for codepoint_start in hvar_fonts.codepoint_starts
            )
            + "</i>"
            for output in range(WIDTH)
        )
        chain = (
            f'<output id="result" class="sink decode-{group_count - 1}">'
            f"{result_contents}</output>"
        )
    elif SINK_MODE == "distributed":
        chain = (
            f'<output id="result" class="contribution contrib-{group_count - 1}">'
            "result</output>"
        )
    else:
        chain = (
            f'<output id="result" class="sink decode-{group_count - 1}">'
            "result</output>"
        )
    for group in reversed(range(group_count)):
        classes = f"packed-carrier pack-{group}"
        if group:
            classes += (
                f" contribution contrib-{group - 1}"
                if SINK_MODE == "distributed"
                else f" decode-{group - 1}"
            )
        local_sources = (
            "".join(source_markup[group * PACK : (group + 1) * PACK])
            if SOURCE_LAYOUT.startswith("local")
            else ""
        )
        chain = local_sources + (
            f'<div class="{classes}" '
            f'style="position-anchor:--a{group * PACK:04d}">{chain}</div>'
        )
    HTML.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
        '<title>Full packed-anchor GPT-2 MLP</title>'
        f'<link rel="stylesheet" href="{CSS.name}" />'
        '</head><body><div id="scope">'
        + (
            "".join(source_markup)
            if not SOURCE_LAYOUT.startswith("local")
            else ""
        )
        + chain
        + "</div></body></html>"
    )

    if SINK_MODE == "distributed":
        sink_css = (
            ".contribution{position:absolute;animation-duration:1s;"
            "animation-play-state:paused;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-composition:add}"
        )
    elif SINK_MODE == "hvar":
        assert hvar_fonts is not None
        hvar_settings = ",".join(
            f'"{global_axis_tag(index)}" var(--p{index:04d})'
            for index in range(MLP_WIDTH)
        )
        sink_css = (
            ".sink{position:absolute;width:1px;height:1px;"
            f"font-family:{','.join(f'mlpglobalS{index}' for index in range(len(hvar_fonts.names)))};"
            f"font-size:{FONT_SIZE}px;font-kerning:none;white-space:pre;"
            f"font-variation-settings:{hvar_settings}}}"
            ".projection-metric{position:absolute;left:0;top:0;display:inline-block;"
            "width:max-content;height:1px;overflow:hidden;font-style:normal}"
        )
    else:
        sink_css = (
            ".sink{position:absolute;animation-duration:1s;"
            "animation-play-state:paused;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-composition:add;"
            f"{';'.join(sink_math_declarations)};"
            f"animation-name:{','.join(sink_names)};"
            f"animation-delay:{','.join(sink_delays)}}}"
        )

    CSS.write_text(
        font_faces("fc", fonts)
        + (font_faces("mlp-global", hvar_fonts) if hvar_fonts is not None else "")
        + gelu_function()
        + progress_registrations
        + "".join(keyframes)
        + f"#scope{{"
        + (f"--zero:{zero};" if ZERO_ENCODING == "shared" else "")
        + f"--fc-settings:{input_settings(case_inputs[0], activation_range)};"
        + (
            "anchor-scope:all;"
            if not SOURCE_LAYOUT.startswith("local")
            else ""
        )
        + "position:relative}"
        + f".source{{position:absolute;display:inline-flex;width:max-content;"
        f"height:1px;overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;"
        f"font-kerning:none;font-family:"
        f"{','.join(f'fcS{i}' for i in range(len(fonts.names)))};"
        "font-variation-settings:var(--fc-settings)}"
        + f".packed-carrier{{position:{'fixed' if SOURCE_LAYOUT == 'flat-fixed' else 'absolute'};"
        + (
            "container-type:size;"
            if PACK_DIMENSIONS == 2
            else "container-type:inline-size;height:1px;"
        )
        + f"}}.pack-0{{font-family:serif;font-variation-settings:"
        + ("normal" if SINK_MODE == "hvar" else vector_settings(scaled_base))
        + "}"
        + sink_css
        + "".join(pack_rules)
        + "".join(contribution_rules)
    )
    REFERENCE.write_text(json.dumps({
        "settings": [input_settings(row, activation_range) for row in case_inputs],
        "codes": codes.tolist(),
        "expected": scaled_expected.tolist(),
        "fullPrecisionExpected": scaled_full_precision_expected.tolist(),
        "unscaledExpected": expected.tolist(),
        "projectionScale": projection_scale.tolist(),
        "progress": progress.tolist(),
        "progressCodes": np.rint(progress * LEVELS).astype(int).tolist(),
        "activationRange": activation_range,
        "baseTotal": base_total,
        "sourceWidths": (
            (base_total + raw) * FONT_SIZE / UNITS_PER_EM
        ).tolist(),
        "groups": group_count,
        "sourceLayout": SOURCE_LAYOUT,
        "packDimensions": PACK_DIMENSIONS,
        "packBits": PACK_BITS,
        "zeroEncoding": ZERO_ENCODING,
        "sinkMode": SINK_MODE,
        "hvarExpected": hvar_expected.tolist() if hvar_expected is not None else None,
        "hvarScales": hvar_projection.scales.tolist() if hvar_projection is not None else None,
        "hvarBase": scaled_base.tolist() if hvar_projection is not None else None,
        "hvarBaseTotal": hvar_base_total,
        "hvarUnitsPerPixel": UNITS_PER_EM / FONT_SIZE if hvar_projection is not None else None,
        "hvarFontBytes": (
            sum((OUT / f"{name}.woff2").stat().st_size for name in hvar_fonts.names)
            if hvar_fonts is not None else None
        ),
        "hvarBits": HVAR_PROJECTION_BITS if hvar_projection is not None else None,
        "hvarShardSize": HVAR_PROJECTION_SHARD if hvar_projection is not None else None,
        "cssBytes": CSS.stat().st_size,
        "htmlBytes": HTML.stat().st_size,
        "buildSeconds": time.perf_counter() - started,
    }, indent=2) + "\n")
    print(json.dumps({
        "cssBytes": CSS.stat().st_size,
        "htmlBytes": HTML.stat().st_size,
        "groups": group_count,
        "buildSeconds": time.perf_counter() - started,
    }, indent=2))


if __name__ == "__main__":
    main()
