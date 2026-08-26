#!/usr/bin/env python3
"""Attach the packed real GPT-2 MLP tail to geometry-streaming attention."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

from build_gpt2_block_css import MLP_WIDTH, QUANT_BITS, gelu_new, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
TAIL_HTML = (
    OUT
    / "view-timeline-block1-full-packed4-isolated-exact.html"
)
TAIL_CSS = "view-timeline-two-block-full-packed4-exact.css"
BOUNDARY_CSS = "geometry-streaming-full-tail-boundary.css"
PACKED_BOUNDARY_CSS = "geometry-streaming-full-tail-packed-boundary.css"
PAIR_BOUNDARY_CSS = "geometry-streaming-full-tail-pair-boundary.css"
DUAL_BOUNDARY_CSS = "geometry-streaming-full-tail-dual-boundary.css"


def extract_div(source: str, marker: str) -> str:
    """Return the balanced div subtree beginning with marker."""
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"missing tail marker: {marker}")
    depth = 0
    for match in re.finditer(r"<div\b[^>]*>|</div\s*>", source[start:], re.I):
        tag = match.group(0).lower()
        depth += -1 if tag.startswith("</") else 1
        if depth == 0:
            return source[start : start + match.end()]
    raise ValueError("unterminated tail div")


def aliases() -> str:
    return ";".join(
        f"--b1-out-{index:03d}:var(--r1-{index:03d})" for index in range(768)
    )


def gated_tail_assets(context: int, tail: str) -> tuple[str, str]:
    """Hold the MLP subtree out of layout until attention projection completes."""
    gate_property = f"--gt-open-{context}"
    gate_keyframes = f"gt-open-{context}"
    gate_container = f"gtgate{context}"
    css = (
        f'@property {gate_property}{{syntax:"<integer>";inherits:false;initial-value:0}}'
        f"@keyframes {gate_keyframes}{{to{{{gate_property}:1}}}}"
        f"#attention-result{{container-type:normal;container-name:{gate_container}}}"
        f".gt-gated-tail{{{gate_property}:0;"
        f"content-visibility:if(style({gate_property}:1):visible;else:hidden);"
        "contain-intrinsic-size:1px}"
        f"@container {gate_container} style(--gpp-{context}-767 > 0){{"
        f".gt-gated-tail{{animation:{gate_keyframes} 1ms steps(1,end) both}}}}"
    )
    return css, f'<div class="gt-gated-tail">{tail}</div>'


def display_gated_tail_assets(context: int, tail: str) -> tuple[str, str]:
    """Exclude the MLP subtree entirely until attention projection completes."""
    gate_container = f"gtdisplay{context}"
    css = (
        f"#attention-result{{container-type:normal;container-name:{gate_container}}}"
        ".gt-display-gated-tail{display:none}"
        f"@container {gate_container} style(--gpp-{context}-767 > 0){{"
        ".gt-display-gated-tail{display:block}}"
    )
    return css, f'<div class="gt-display-gated-tail">{tail}</div>'


def boundary_assets(tail: str) -> tuple[str, str, str]:
    """Build a 768-number timeline boundary and its producer/consumer markup."""
    viewport = 16_384
    offset = 32
    scale = 256
    track_width = 32_768
    timelines = [f"--gtbt{index}" for index in range(768)]
    progress = [f"--gtbp{index}" for index in range(768)]
    keyframes = [f"gtbk{index}" for index in range(768)]
    css = [
        "".join(
            f'@property {name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            for name in progress
        ),
        "".join(
            f"@keyframes {keyframe}{{from{{{name}:0}}to{{{name}:1}}}}"
            for keyframe, name in zip(keyframes, progress, strict=True)
        ),
        f'html{{timeline-scope:{",".join(timelines)}}}',
        f".gtb-scroller{{position:fixed;left:0;top:-85000px;width:{viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}",
        f".gtb-track{{position:relative;width:{track_width}px;height:1px}}",
        ".gtb-metric{position:absolute;left:0;top:0;display:block;height:1px}",
    ]
    metrics = "".join(
        f'<i class="gtb-metric" style="view-timeline:{timeline} inline;'
        f'width:calc((var(--r1-{index:03d}) + {offset}) * {scale}px)"></i>'
        for index, timeline in enumerate(timelines)
    )
    consumer_count = 6
    for consumer in range(consumer_count):
        start = consumer * 128
        stop = min(start + 128, 768)
        css.append(
            f".gtb-result-{consumer}{{animation-name:"
            f"{','.join(keyframes[start:stop])};animation-duration:1s;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[start:stop])};"
            "animation-range:cover;"
            + ";".join(
                f"--b1-out-{index:03d}:calc(({viewport} / var({progress[index]}) - "
                f"{viewport}) / {scale} - {offset})"
                for index in range(start, stop)
            )
            + "}"
        )
    consumer = f'<div class="gtb-result-{consumer_count - 1}">{tail}</div>'
    for index in reversed(range(consumer_count - 1)):
        consumer = f'<div class="gtb-result-{index}">{consumer}</div>'
    producer = f'<div class="gtb-scroller"><div class="gtb-track">{metrics}</div></div>'
    return "".join(css), producer, consumer


def packed_boundary_assets(tail: str) -> tuple[str, str, str, dict[str, list[float]]]:
    """Pack four calibrated residual values into each two-dimensional carrier."""
    calibration = json.loads(
        (
            ROOT
            / "experiments"
            / "packed-activation-precision"
            / "hidden-ranges-headroom2.json"
        ).read_text()
    )["blocks"][0]
    calibrated_low = np.asarray(calibration["state_minimum"], dtype=np.float64) * 1.25
    calibrated_high = np.asarray(calibration["state_maximum"], dtype=np.float64) * 1.25
    low = np.minimum(calibrated_low, -16.0)
    high = np.maximum(calibrated_high, 16.0)
    span = high - low

    radix = 512
    levels = radix - 1
    viewport = 1_048_576
    extent = 300_000
    left_base = viewport - extent
    track_width = 1_600_000
    group_count = 768 // 4
    timelines = [f"--gtb4t{group}" for group in range(group_count)]
    cover = [f"--gtb4c{group}" for group in range(group_count)]
    entry = [f"--gtb4e{group}" for group in range(group_count)]
    keyframes = [f"gtb4k{group}" for group in range(group_count)]

    def encoded(index: int) -> str:
        return (
            f"round(nearest,clamp(0,(var(--r1-{index:03d}) - "
            f"({low[index]:.12g})) / {span[index]:.12g},1) * {levels},1)"
        )

    groups = []
    for group, timeline in enumerate(timelines):
        outputs = [group * 4 + slot for slot in range(4)]
        lead = f"({encoded(outputs[0])} + {radix} * {encoded(outputs[1])})"
        payload = f"({encoded(outputs[2])} + {radix} * {encoded(outputs[3])})"
        groups.append(
            f'<span class="gtb4-pair"><i class="gtb4-lead" '
            f'style="width:calc({lead} * 1px)"></i>'
            f'<i class="gtb4-subject" style="view-timeline:{timeline} inline;'
            f'width:calc(({payload} + {extent}) * 1px)"></i></span>'
        )

    css = [
        "".join(
            f'@property {cover_name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f'@property {entry_name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f"@keyframes {keyframe}{{cover 0%{{{cover_name}:0;{entry_name}:0}}"
            f"entry 100%{{{entry_name}:1}}cover 100%{{{cover_name}:1;{entry_name}:1}}}}"
            for cover_name, entry_name, keyframe in zip(
                cover, entry, keyframes, strict=True
            )
        ),
        f'html{{timeline-scope:{",".join(timelines)}}}',
        f".gtb4-scroller{{position:fixed;left:0;top:-86000px;width:{viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}",
        f".gtb4-track{{position:relative;width:{track_width}px;height:1px}}",
        f".gtb4-pair{{position:absolute;left:{left_base}px;top:0;display:inline-flex;"
        "height:1px}",
        ".gtb4-lead,.gtb4-subject{display:block;flex:none;height:1px}",
    ]
    consumer_count = 6
    groups_per_consumer = group_count // consumer_count
    for consumer_index in range(consumer_count):
        group_start = consumer_index * groups_per_consumer
        group_stop = min(group_start + groups_per_consumer, group_count)
        declarations = []
        for group in range(group_start, group_stop):
            width_name = f"--gtb4w-{group:03d}"
            lead_name = f"--gtb4l-{group:03d}"
            payload_name = f"--gtb4p-{group:03d}"
            declarations.extend((
                f"{width_name}:calc(var({cover[group]}) * {viewport} / "
                f"(var({entry[group]}) - var({cover[group]})))",
                f"{lead_name}:round(nearest,{viewport} - var({entry[group]}) * "
                f"var({width_name}) - {left_base},1)",
                f"{payload_name}:round(nearest,var({width_name}) - {extent},1)",
            ))
            for slot in range(4):
                output = group * 4 + slot
                packed_name = lead_name if slot < 2 else payload_name
                digit = (
                    f"mod(var({packed_name}),{radix})"
                    if slot % 2 == 0
                    else f"round(down,var({packed_name}) / {radix},1)"
                )
                declarations.append(
                    f"--b1-out-{output:03d}:calc({low[output]:.12g} + "
                    f"{digit} / {levels} * {span[output]:.12g})"
                )
        css.append(
            f".gtb4-result-{consumer_index}{{animation-name:"
            f"{','.join(keyframes[group_start:group_stop])};animation-duration:1s;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[group_start:group_stop])};"
            + ";".join(declarations)
            + "}"
        )
    consumer = f'<div class="gtb4-result-{consumer_count - 1}">{tail}</div>'
    for index in reversed(range(consumer_count - 1)):
        consumer = f'<div class="gtb4-result-{index}">{consumer}</div>'
    producer = f'<div class="gtb4-scroller"><div class="gtb4-track">{"".join(groups)}</div></div>'
    return (
        "".join(css),
        producer,
        consumer,
        {"low": low.tolist(), "high": high.tolist()},
    )


def pair_boundary_assets(tail: str) -> tuple[str, str, str]:
    """Pack two calibrated 12-bit residual values into each width carrier."""
    calibration = json.loads(
        (
            ROOT
            / "experiments"
            / "packed-activation-precision"
            / "hidden-ranges-headroom2.json"
        ).read_text()
    )["blocks"][0]
    low = np.minimum(
        np.asarray(calibration["state_minimum"], dtype=np.float64) * 1.25,
        -16.0,
    )
    high = np.maximum(
        np.asarray(calibration["state_maximum"], dtype=np.float64) * 1.25,
        16.0,
    )
    span = high - low
    radix = 4096
    levels = radix - 1
    viewport = 1_048_576
    track_width = 18_000_000
    group_count = 768 // 2
    timelines = [f"--gtb2t{group}" for group in range(group_count)]
    progress = [f"--gtb2p{group}" for group in range(group_count)]
    keyframes = [f"gtb2k{group}" for group in range(group_count)]

    def encoded(index: int) -> str:
        return (
            f"round(nearest,clamp(0,(var(--r1-{index:03d}) - "
            f"({low[index]:.12g})) / {span[index]:.12g},1) * {levels},1)"
        )

    metrics = "".join(
        f'<i class="gtb2-metric" style="view-timeline:{timeline} inline;'
        f'width:calc(({encoded(group * 2)} + {radix} * '
        f'{encoded(group * 2 + 1)}) * 1px)"></i>'
        for group, timeline in enumerate(timelines)
    )
    css = [
        "".join(
            f'@property {name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f"@keyframes {keyframe}{{from{{{name}:0}}to{{{name}:1}}}}"
            for name, keyframe in zip(progress, keyframes, strict=True)
        ),
        f'html{{timeline-scope:{",".join(timelines)}}}',
        f".gtb2-scroller{{position:fixed;left:0;top:-87000px;width:{viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}",
        f".gtb2-track{{position:relative;width:{track_width}px;height:1px}}",
        ".gtb2-metric{position:absolute;left:0;top:0;display:block;height:1px}",
    ]
    consumer_count = 6
    groups_per_consumer = group_count // consumer_count
    for consumer_index in range(consumer_count):
        group_start = consumer_index * groups_per_consumer
        group_stop = min(group_start + groups_per_consumer, group_count)
        declarations = []
        for group in range(group_start, group_stop):
            packed = f"--gtb2v-{group:03d}"
            declarations.append(
                f"{packed}:round(nearest,{viewport} / var({progress[group]}) - "
                f"{viewport},1)"
            )
            for slot in range(2):
                output = group * 2 + slot
                digit = (
                    f"mod(var({packed}),{radix})"
                    if slot == 0
                    else f"round(down,var({packed}) / {radix},1)"
                )
                declarations.append(
                    f"--b1-out-{output:03d}:calc({low[output]:.12g} + "
                    f"{digit} / {levels} * {span[output]:.12g})"
                )
        css.append(
            f".gtb2-result-{consumer_index}{{animation-name:"
            f"{','.join(keyframes[group_start:group_stop])};animation-duration:1s;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[group_start:group_stop])};"
            "animation-range:cover;"
            + ";".join(declarations)
            + "}"
        )
    consumer = f'<div class="gtb2-result-{consumer_count - 1}">{tail}</div>'
    for index in reversed(range(consumer_count - 1)):
        consumer = f'<div class="gtb2-result-{index}">{consumer}</div>'
    producer = f'<div class="gtb2-scroller"><div class="gtb2-track">{metrics}</div></div>'
    return "".join(css), producer, consumer


def dual_boundary_assets(tail: str) -> tuple[str, str, str]:
    """Carry two 12-bit values in independent left and width dimensions."""
    calibration = json.loads(
        (
            ROOT
            / "experiments"
            / "packed-activation-precision"
            / "hidden-ranges-headroom2.json"
        ).read_text()
    )["blocks"][0]
    low = np.minimum(
        np.asarray(calibration["state_minimum"], dtype=np.float64) * 1.25,
        -16.0,
    )
    high = np.maximum(
        np.asarray(calibration["state_maximum"], dtype=np.float64) * 1.25,
        16.0,
    )
    span = high - low
    levels = 4095
    viewport = 1_048_576
    extent = 300_000
    left_base = viewport - extent
    track_width = 1_600_000
    group_count = 768 // 2
    timelines = [f"--gtbdt{group}" for group in range(group_count)]
    cover = [f"--gtbdc{group}" for group in range(group_count)]
    entry = [f"--gtbde{group}" for group in range(group_count)]
    keyframes = [f"gtbdk{group}" for group in range(group_count)]

    def encoded(index: int) -> str:
        return (
            f"round(nearest,clamp(0,(var(--r1-{index:03d}) - "
            f"({low[index]:.12g})) / {span[index]:.12g},1) * {levels},1)"
        )

    metrics = "".join(
        f'<i class="gtbd-metric" style="view-timeline:{timeline} inline;'
        f'left:calc({left_base}px + {encoded(group * 2)} * 1px);'
        f'width:calc({extent}px + {encoded(group * 2 + 1)} * 1px)"></i>'
        for group, timeline in enumerate(timelines)
    )
    css = [
        "".join(
            f'@property {cover_name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f'@property {entry_name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            f"@keyframes {keyframe}{{cover 0%{{{cover_name}:0;{entry_name}:0}}"
            f"entry 100%{{{entry_name}:1}}cover 100%{{{cover_name}:1;{entry_name}:1}}}}"
            for cover_name, entry_name, keyframe in zip(
                cover, entry, keyframes, strict=True
            )
        ),
        f'html{{timeline-scope:{",".join(timelines)}}}',
        f".gtbd-scroller{{position:fixed;left:0;top:-88000px;width:{viewport}px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}",
        f".gtbd-track{{position:relative;width:{track_width}px;height:1px}}",
        ".gtbd-metric{position:absolute;top:0;display:block;height:1px}",
    ]
    consumer_count = 6
    groups_per_consumer = group_count // consumer_count
    for consumer_index in range(consumer_count):
        group_start = consumer_index * groups_per_consumer
        group_stop = min(group_start + groups_per_consumer, group_count)
        declarations = []
        for group in range(group_start, group_stop):
            width_name = f"--gtbdw-{group:03d}"
            left_name = f"--gtbdl-{group:03d}"
            payload_name = f"--gtbdp-{group:03d}"
            declarations.extend((
                f"{width_name}:calc(var({cover[group]}) * {viewport} / "
                f"(var({entry[group]}) - var({cover[group]})))",
                f"{left_name}:round(nearest,{viewport} - var({entry[group]}) * "
                f"var({width_name}) - {left_base},1)",
                f"{payload_name}:round(nearest,var({width_name}) - {extent},1)",
            ))
            for slot, digit in enumerate((left_name, payload_name)):
                output = group * 2 + slot
                declarations.append(
                    f"--b1-out-{output:03d}:calc({low[output]:.12g} + "
                    f"var({digit}) / {levels} * {span[output]:.12g})"
                )
        css.append(
            f".gtbd-result-{consumer_index}{{animation-name:"
            f"{','.join(keyframes[group_start:group_stop])};animation-duration:1s;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[group_start:group_stop])};"
            + ";".join(declarations)
            + "}"
        )
    consumer = f'<div class="gtbd-result-{consumer_count - 1}">{tail}</div>'
    for index in reversed(range(consumer_count - 1)):
        consumer = f'<div class="gtbd-result-{index}">{consumer}</div>'
    producer = f'<div class="gtbd-scroller"><div class="gtbd-track">{metrics}</div></div>'
    return "".join(css), producer, consumer


def packed_tail_reference(residual: np.ndarray) -> dict[str, np.ndarray]:
    """Mirror the packed4 tail's quantized weights and hidden-value encoding."""
    data = model_data(1, input_vector=residual)
    normalized = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    quantized_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    hidden = gelu_new(quantized_fc.reconstructed @ normalized + data["fc_bias"])
    quantized_projection = quantize_float_rows(
        data["mlp_proj_weight"], bits=QUANT_BITS
    )

    # These bounds are deterministically selected by the source packed4 fixture.
    source_reference = json.loads(
        (OUT / "view-timeline-two-block-full-reference.json").read_text()
    )
    source_hidden_max = max(source_reference["block1_hidden"])
    packed_minimum = -0.25
    packed_maximum = max(15.75, math.ceil(source_hidden_max * 4) / 4 + 0.25)
    packed_span = packed_maximum - packed_minimum

    importance = np.linalg.norm(quantized_projection.reconstructed, axis=0)
    ranked = np.argsort(importance)
    low = ranked[: MLP_WIDTH // 2]
    high = ranked[MLP_WIDTH // 2 :]
    groups = np.asarray(
        [
            (low[group * 2], high[group * 2], low[group * 2 + 1], high[group * 2 + 1])
            for group in range(MLP_WIDTH // 4)
        ],
        dtype=np.int64,
    )
    levels = np.full(MLP_WIDTH, 511, dtype=np.int64)
    levels[low] = 255
    clipped = np.clip(hidden, packed_minimum, packed_maximum)
    encoded = np.rint(
        np.sqrt((clipped - packed_minimum) / packed_span) * levels
    )
    packed_hidden = (encoded / levels) ** 2 * packed_span + packed_minimum
    expected = (
        residual
        + quantized_projection.reconstructed @ packed_hidden
        + data["mlp_proj_bias"]
    )
    return {
        "normalized": normalized,
        "hidden": hidden,
        "packedHidden": packed_hidden,
        "expected": expected,
        "packedGroups": groups,
        "packedMinimum": np.asarray(packed_minimum),
        "packedMaximum": np.asarray(packed_maximum),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", type=int, nargs="+", default=[2, 4, 8, 16, 32])
    args = parser.parse_args()

    tail_source = TAIL_HTML.read_text()
    tail = extract_div(tail_source, '<div class="b1-ln2">')
    if tail.count('id="two-block-full"') != 1:
        raise ValueError("expected exactly one packed MLP output")
    boundary_css, boundary_producer, boundary_consumer = boundary_assets(tail)
    (OUT / BOUNDARY_CSS).write_text(boundary_css)
    packed_boundary_css, packed_boundary_producer, packed_boundary_consumer, packed_ranges = (
        packed_boundary_assets(tail)
    )
    (OUT / PACKED_BOUNDARY_CSS).write_text(packed_boundary_css)
    pair_boundary_css, pair_boundary_producer, pair_boundary_consumer = (
        pair_boundary_assets(tail)
    )
    (OUT / PAIR_BOUNDARY_CSS).write_text(pair_boundary_css)
    dual_boundary_css, dual_boundary_producer, dual_boundary_consumer = (
        dual_boundary_assets(tail)
    )
    (OUT / DUAL_BOUNDARY_CSS).write_text(dual_boundary_css)

    generated = []
    for context in args.contexts:
        source_stem = (
            f"attention-context-{context}-geometry-streaming-flat-siblings-projected"
        )
        source_path = OUT / f"{source_stem}.html"
        reference_path = OUT / f"{source_stem}-reference.json"
        source = source_path.read_text()
        reference = json.loads(reference_path.read_text())
        residual = np.asarray(reference["residual"], dtype=np.float64)
        leaf = '<output id="attention-result"></output>'
        if source.count(leaf) != 1:
            raise ValueError(f"expected exactly one attention leaf in {source_path.name}")

        tail_link = f'<link rel="stylesheet" href="{TAIL_CSS}">'
        connected = source.replace("</title>", f"</title>{tail_link}", 1).replace(
            leaf,
            f'<div id="attention-result" style="{aliases()}">{tail}</div>',
            1,
        )
        connected_path = OUT / f"{source_stem}-full-tail.html"
        connected_path.write_text(connected)

        query_variant_connected_paths = []
        for query_variant in ("q-isolated", "split-cache"):
            query_variant_stem = (
                f"attention-context-{context}-geometry-streaming-flat-siblings-"
                f"{query_variant}-projected"
            )
            query_variant_source_path = OUT / f"{query_variant_stem}.html"
            if not query_variant_source_path.exists():
                continue
            query_variant_source = query_variant_source_path.read_text()
            if query_variant_source.count(leaf) != 1:
                raise ValueError(
                    f"expected exactly one attention leaf in {query_variant_source_path.name}"
                )
            query_variant_connected = query_variant_source.replace(
                "</title>", f"</title>{tail_link}", 1
            ).replace(
                leaf,
                f'<div id="attention-result" style="{aliases()}">{tail}</div>',
                1,
            )
            query_variant_connected_path = OUT / f"{query_variant_stem}-full-tail.html"
            query_variant_connected_path.write_text(query_variant_connected)
            query_variant_connected_paths.append(query_variant_connected_path)

        gated_css, gated_tail = gated_tail_assets(context, tail)
        gated = source.replace(
            "</title>", f"</title>{tail_link}<style>{gated_css}</style>", 1
        ).replace(
            leaf,
            f'<div id="attention-result" style="{aliases()}">{gated_tail}</div>',
            1,
        )
        gated_path = OUT / f"{source_stem}-full-tail-gated.html"
        gated_path.write_text(gated)

        display_gated_css, display_gated_tail = display_gated_tail_assets(context, tail)
        display_gated = source.replace(
            "</title>",
            f"</title>{tail_link}<style>{display_gated_css}</style>",
            1,
        ).replace(
            leaf,
            f'<div id="attention-result" style="{aliases()}">{display_gated_tail}</div>',
            1,
        )
        display_gated_path = OUT / f"{source_stem}-full-tail-display-gated.html"
        display_gated_path.write_text(display_gated)

        boundary_link = f'<link rel="stylesheet" href="{BOUNDARY_CSS}">'
        boundary_connected = source.replace(
            "</title>", f"</title>{tail_link}{boundary_link}", 1
        ).replace(
            leaf,
            f'<div id="attention-result">{boundary_producer}</div>',
            1,
        ) + boundary_consumer
        boundary_path = OUT / f"{source_stem}-full-tail-boundary.html"
        boundary_path.write_text(boundary_connected)

        packed_boundary_link = f'<link rel="stylesheet" href="{PACKED_BOUNDARY_CSS}">'
        packed_boundary_connected = source.replace(
            "</title>", f"</title>{tail_link}{packed_boundary_link}", 1
        ).replace(
            leaf,
            f'<div id="attention-result">{packed_boundary_producer}</div>',
            1,
        ) + packed_boundary_consumer
        packed_boundary_path = OUT / f"{source_stem}-full-tail-packed-boundary.html"
        packed_boundary_path.write_text(packed_boundary_connected)

        pair_boundary_link = f'<link rel="stylesheet" href="{PAIR_BOUNDARY_CSS}">'
        pair_boundary_connected = source.replace(
            "</title>", f"</title>{tail_link}{pair_boundary_link}", 1
        ).replace(
            leaf,
            f'<div id="attention-result">{pair_boundary_producer}</div>',
            1,
        ) + pair_boundary_consumer
        pair_boundary_path = OUT / f"{source_stem}-full-tail-pair-boundary.html"
        pair_boundary_path.write_text(pair_boundary_connected)

        dual_boundary_link = f'<link rel="stylesheet" href="{DUAL_BOUNDARY_CSS}">'
        dual_boundary_connected = source.replace(
            "</title>", f"</title>{tail_link}{dual_boundary_link}", 1
        ).replace(
            leaf,
            f'<div id="attention-result">{dual_boundary_producer}</div>',
            1,
        ) + dual_boundary_consumer
        dual_boundary_path = OUT / f"{source_stem}-full-tail-dual-boundary.html"
        dual_boundary_path.write_text(dual_boundary_connected)

        residual_style = ";".join(
            f"--r1-{index:03d}:{value:.12g}"
            for index, value in enumerate(reference["residual"])
        )
        isolated = (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f"<title>Isolated packed MLP tail, context {context}</title>{tail_link}"
            f'<div style="{residual_style};{aliases()}">{tail}</div>'
        )
        isolated_path = OUT / f"{source_stem}-full-tail-isolated.html"
        isolated_path.write_text(isolated)
        numeric_reference = packed_tail_reference(residual)
        tail_reference_path = OUT / f"{source_stem}-full-tail-reference.json"
        tail_reference_path.write_text(
            json.dumps(
                {
                    "context": context,
                    "input": residual.tolist(),
                    **{
                        name: values.tolist()
                        for name, values in numeric_reference.items()
                    },
                },
                indent=2,
            )
            + "\n"
        )
        generated.extend((
            connected_path.name,
            gated_path.name,
            display_gated_path.name,
            boundary_path.name,
            packed_boundary_path.name,
            pair_boundary_path.name,
            dual_boundary_path.name,
            isolated_path.name,
        ))
        generated.extend(path.name for path in query_variant_connected_paths)

    manifest = {
        "contexts": args.contexts,
        "attention": "real block-0 multi-token attention and output projection",
        "tail": "real block-1 LN2, 768x3072 FC, GELU, 3072x768 projection, residual",
        "tailTransport": "four post-GELU values per timeline carrier",
        "gated": "MLP subtree enters layout after the last attention projection timeline resolves",
        "displayGated": "MLP subtree is display:none until the last attention projection timeline resolves",
        "queryInheritanceIsolation": "cached K/V metric subtrees override all inherited Q properties",
        "splitQueryCache": "one global score track with per-source K/V inheritance firewalls",
        "tailCss": TAIL_CSS,
        "boundary": "768 independent view timelines, 1/256-unit geometry scale",
        "packedBoundary": "192 two-dimensional view timelines carrying four 9-bit values each",
        "pairBoundary": "384 width timelines carrying two 12-bit values each",
        "dualBoundary": "384 two-dimensional timelines carrying two independent 12-bit values",
        "packedBoundaryRanges": packed_ranges,
        "runtimeJavaScript": False,
        "generated": generated,
    }
    (OUT / "geometry-streaming-full-tail-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
