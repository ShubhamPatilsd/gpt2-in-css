#!/usr/bin/env python3
"""Probe underused, script-free Chromium numeric primitives.

The generated runtime fixtures contain HTML/CSS/images only.  This Python
harness launches Chromium's headless screenshot mode and inspects the pixels;
it does not inject or execute JavaScript in the pages.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
from pathlib import Path
import random
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "browser-native-compute"
CHROME_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
)


def chrome_path() -> Path:
    override = os.environ.get("CHROME_BIN")
    if override:
        return Path(override)
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise SystemExit("Chromium/Chrome not found; set CHROME_BIN")


def png_data_url(values: list[int]) -> str:
    image = Image.new("RGB", (len(values), 1))
    image.putdata([(value, value, value) for value in values])
    payload = io.BytesIO()
    image.save(payload, format="PNG")
    encoded = base64.b64encode(payload.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def color_precision_html() -> tuple[str, dict]:
    depths = (0, 32, 128)
    deltas = tuple(range(-8, 9))
    registrations = []
    chain = []
    for index in range(1, max(depths) + 1):
        registrations.append(
            f'@property --c{index} {{ syntax: "<color>"; inherits: false; '
            "initial-value: color(srgb 0 0 0); }"
        )
        chain.append(
            f"--c{index}: color(from var(--c{index - 1}) srgb r g b);"
        )

    swatches = []
    expected = {}
    for row, depth in enumerate(depths):
        expected[str(depth)] = []
        for column, delta in enumerate(deltas):
            source = 0.5 + delta / 65536.0
            target = 0.5 + delta / 16.0
            red = round(255 * min(1.0, max(0.0, target)))
            expected[str(depth)].append(red)
            swatches.append(
                '<div class="swatch" '
                f'style="grid-row:{row + 1};grid-column:{column + 1};'
                f"--c0:color(srgb {source:.12f} 0 0);"
                f"background:color(from var(--c{depth}) srgb "
                'calc(.5 + (r - .5) * 4096) 0 0)"></div>'
            )

    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
{''.join(registrations)}
html,body{{margin:0;background:white}}
body{{display:grid;grid-template-columns:repeat(17,16px);grid-template-rows:repeat(3,16px)}}
.swatch{{width:16px;height:16px;{' '.join(chain)}}}
</style>
{''.join(swatches)}
"""
    return html, {
        "depths": depths,
        "deltasInUnitsOf65536": deltas,
        "expectedRed": expected,
        "sampleCellPixels": 16,
    }


def balanced_color_mix(leaves: list[tuple[str, float]]) -> tuple[str, float]:
    if len(leaves) == 1:
        return leaves[0]
    midpoint = len(leaves) // 2
    left, left_weight = balanced_color_mix(leaves[:midpoint])
    right, right_weight = balanced_color_mix(leaves[midpoint:])
    total = left_weight + right_weight
    percentage = 100.0 * left_weight / total
    return (
        f"color-mix(in srgb, {left} {percentage:.10f}%, {right})",
        total,
    )


def color_dot_html() -> tuple[str, dict]:
    rng = random.Random(0xC0105)
    case_count = 24
    term_count = 32
    cases = []
    for _ in range(case_count):
        inputs = [rng.uniform(0.1, 0.9) for _ in range(term_count)]
        weights = [rng.uniform(-1.0, 1.0) for _ in range(term_count)]
        dot = sum(value * weight for value, weight in zip(inputs, weights))
        cases.append((inputs, weights, dot))
    scale = 2.2 * max(abs(case[2]) for case in cases)

    swatches = []
    expected_red = []
    for index, (inputs, weights, dot) in enumerate(cases):
        negative_weight = sum(-weight for weight in weights if weight < 0)
        leaves = []
        for value, weight in zip(inputs, weights):
            channel = value if weight >= 0 else 1.0 - value
            leaves.append((f"color(srgb {channel:.12f} 0 0)", abs(weight)))
        mix, total_weight = balanced_color_mix(leaves)
        output = 0.5 + dot / scale
        expected_red.append(round(255 * output))
        swatches.append(
            '<div class="swatch" style="background:'
            f"color(from {mix} srgb "
            f"calc(.5 + (r * {total_weight:.12f} - {negative_weight:.12f}) / {scale:.12f}) "
            '0 0)"></div>'
        )

    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
html,body{{margin:0;background:white}}
body{{display:grid;grid-template-columns:repeat({case_count},16px)}}
.swatch{{width:16px;height:32px}}
</style>
{''.join(swatches)}
"""
    return html, {
        "cases": case_count,
        "termsPerDot": term_count,
        "scale": scale,
        "expectedRed": expected_red,
        "sampleCellPixels": 16,
    }


def color_simd_matmul_html(size: int) -> tuple[str, dict]:
    """Pack three dense-matrix output rows into each computed CSS color."""
    if size % 3:
        raise ValueError("SIMD matmul size must be divisible by three")
    rng = random.Random(0x51D000 + size)
    inputs = [rng.uniform(-1.0, 1.0) for _ in range(size)]
    weights = [
        [rng.uniform(-0.35, 0.35) for _ in range(size)] for _ in range(size)
    ]
    outputs = [
        sum(weight * value for weight, value in zip(row, inputs))
        for row in weights
    ]
    scale = max(abs(value) for value in outputs) * 2.1
    variables = "".join(f"--x{index}:{value:.12f};" for index, value in enumerate(inputs))
    alternate_x0 = -inputs[0] + 0.03125
    swatches = []
    expected_rgb = []
    for group in range(size // 3):
        rows = weights[group * 3 : group * 3 + 3]
        leaves = []
        for input_index in range(size):
            channels = [row[input_index] for row in rows]
            leaves.append(
                (
                    "color(srgb "
                    + " ".join(
                        f"calc(var(--x{input_index}) * {channel:.12f})"
                        for channel in channels
                    )
                    + ")",
                    1.0,
                )
            )
        mix, _ = balanced_color_mix(leaves)
        expected_rgb.append(
            [round(255 * (0.5 + outputs[group * 3 + lane] / scale)) for lane in range(3)]
        )
        swatches.append(
            '<div class="swatch" style="background:'
            f"color(from {mix} srgb "
            f"calc(.5 + r * {size} / {scale:.12f}) "
            f"calc(.5 + g * {size} / {scale:.12f}) "
            f'calc(.5 + b * {size} / {scale:.12f}))"></div>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
html,body{{margin:0;background:white}}
body{{{variables}display:grid;grid-template-columns:repeat({size // 3},4px)}}
body.alternate{{--x0:{alternate_x0:.12f}}}
.swatch{{width:4px;height:32px}}
</style>
{''.join(swatches)}
"""
    return html, {
        "size": size,
        "outputColorCount": size // 3,
        "weights": size * size,
        "scale": scale,
        "expectedRGB": expected_rgb,
        "sampleCellPixels": 4,
        "htmlBytes": len(html.encode("utf-8")),
        "alternateX0": alternate_x0,
    }


def gelu_channel(channel: str, size: int) -> str:
    value = f"({channel} * {size})"
    cubic = f"({value} * {value} * {value})"
    inner = f"(.7978845608 * ({value} + .044715 * {cubic}))"
    tanh = f"((exp(2 * {inner}) - 1) / (exp(2 * {inner}) + 1))"
    return f"calc(.5 * {value} * (1 + {tanh}))"


def color_simd_chain_html(size: int = 24) -> tuple[str, dict]:
    """Two RGB-packed matmuls separated by GELU, entirely in computed colors."""
    if size % 3:
        raise ValueError("SIMD chain size must be divisible by three")
    rng = random.Random(0xC4A10 + size)
    inputs = [rng.uniform(-1.0, 1.0) for _ in range(size)]
    first = [
        [rng.uniform(-0.3, 0.3) for _ in range(size)] for _ in range(size)
    ]
    second = [
        [rng.uniform(-0.3, 0.3) for _ in range(size)] for _ in range(size)
    ]
    hidden = [sum(w * x for w, x in zip(row, inputs)) for row in first]

    def gelu(value: float) -> float:
        return 0.5 * value * (
            1.0
            + math.tanh(math.sqrt(2.0 / math.pi) * (value + 0.044715 * value**3))
        )

    activated = [gelu(value) for value in hidden]
    outputs = [sum(w * x for w, x in zip(row, activated)) for row in second]
    scale = max(abs(value) for value in outputs) * 2.1

    registrations = []
    declarations = [
        f"--x{index}:{value:.12f};" for index, value in enumerate(inputs)
    ]
    for group in range(size // 3):
        registrations.extend(
            (
                f'@property --h{group} {{ syntax:"<color>"; inherits:true; initial-value:black; }}',
                f'@property --a{group} {{ syntax:"<color>"; inherits:true; initial-value:black; }}',
            )
        )
        rows = first[group * 3 : group * 3 + 3]
        leaves = []
        for input_index in range(size):
            leaves.append(
                (
                    "color(srgb "
                    + " ".join(
                        f"calc(var(--x{input_index}) * {row[input_index]:.12f})"
                        for row in rows
                    )
                    + ")",
                    1.0,
                )
            )
        mix, _ = balanced_color_mix(leaves)
        declarations.append(f"--h{group}:{mix};")
        declarations.append(
            f"--a{group}:color(from var(--h{group}) srgb "
            f"{gelu_channel('r', size)} {gelu_channel('g', size)} {gelu_channel('b', size)});"
        )

    swatches = []
    expected_rgb = []
    for output_group in range(size // 3):
        rows = second[output_group * 3 : output_group * 3 + 3]
        leaves = []
        for input_index in range(size):
            source_group, lane = divmod(input_index, 3)
            channel = "rgb"[lane]
            leaves.append(
                (
                    f"color(from var(--a{source_group}) srgb "
                    + " ".join(
                        f"calc({channel} * {row[input_index]:.12f})" for row in rows
                    )
                    + ")",
                    1.0,
                )
            )
        mix, _ = balanced_color_mix(leaves)
        expected_rgb.append(
            [round(255 * (0.5 + outputs[output_group * 3 + lane] / scale)) for lane in range(3)]
        )
        swatches.append(
            '<div class="swatch" style="background:'
            f"color(from {mix} srgb "
            f"calc(.5 + r * {size} / {scale:.12f}) "
            f"calc(.5 + g * {size} / {scale:.12f}) "
            f'calc(.5 + b * {size} / {scale:.12f}))"></div>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
{''.join(registrations)}
html,body{{margin:0;background:white}}
#state{{{''.join(declarations)}display:grid;grid-template-columns:repeat({size // 3},16px)}}
.swatch{{width:16px;height:32px}}
</style>
<div id="state">{''.join(swatches)}</div>
"""
    return html, {
        "size": size,
        "matmuls": 2,
        "nonlinearity": "tanh-approximate GELU",
        "expectedRGB": expected_rgb,
        "outputColorCount": size // 3,
        "sampleCellPixels": 16,
        "htmlBytes": len(html.encode("utf-8")),
    }


def flex_softmax_html() -> tuple[str, dict]:
    score_cases = (
        (-2.0, -1.0, 0.0, 1.0),
        (-7.0, -0.25, 0.0, 3.0),
        (0.125, 0.126, 0.127, 0.128),
    )
    colors = ("#ff0000", "#00ff00", "#0000ff", "#ffff00")
    width = 4096
    rows = []
    expected = []
    for row, scores in enumerate(score_cases):
        exponentials = [math.exp(score) for score in scores]
        denominator = sum(exponentials)
        boundaries = []
        position = 0.0
        children = []
        for color, score, value in zip(colors, scores, exponentials):
            position += width * value / denominator
            boundaries.append(position)
            children.append(
                f'<i style="background:{color};flex-grow:exp({score:.12f})"></i>'
            )
        expected.append(boundaries)
        rows.append(f'<div class="row row-{row}">{"".join(children)}</div>')

    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
html,body{{margin:0;background:white}}
.row{{display:flex;width:{width}px;height:16px}}
.row i{{display:block;flex-basis:0;flex-shrink:1;min-width:0}}
</style>
{''.join(rows)}
"""
    return html, {
        "scores": score_cases,
        "expectedBoundaries": expected,
        "width": width,
        "colors": colors,
    }


def flex_anchor_attention_html() -> tuple[str, dict]:
    """Use flex normalization plus anchor-size terms for an attention-weighted sum."""
    cases = (
        ((-2.0, -1.0, 0.0, 1.0), (-0.8, 0.3, 1.2, -0.4)),
        ((-7.0, -0.25, 0.0, 3.0), (1.5, -0.9, 0.1, 0.7)),
        ((0.125, 0.126, 0.127, 0.128), (-1.0, 1.0, -0.5, 0.5)),
    )
    flex_width = 2048
    offset = 1.25
    markup = []
    expected = []
    for case_index, (scores, values) in enumerate(cases):
        exponentials = [math.exp(score) for score in scores]
        probabilities = [value / sum(exponentials) for value in exponentials]
        weighted = sum(p * value for p, value in zip(probabilities, values))
        expected_width = flex_width * (offset + weighted)
        expected.append(
            {
                "scores": scores,
                "values": values,
                "probabilities": probabilities,
                "weightedValue": weighted,
                "expectedEncodedWidth": expected_width,
            }
        )
        anchors = [f"--p{case_index}-{lane}" for lane in range(4)]
        items = "".join(
            f'<i style="anchor-name:{anchor};flex-grow:exp({score:.12f})"></i>'
            for anchor, score in zip(anchors, scores)
        )
        terms = " + ".join(
            f"{offset + value:.12f} * anchor-size({anchor} width)"
            for anchor, value in zip(anchors, values)
        )
        top = case_index * 40
        markup.append(
            f'<div class="case" style="top:{top}px;anchor-scope:{", ".join(anchors)}">'
            f'<div class="normalizer">{items}</div>'
            f'<div class="context" style="width:calc({terms})"></div>'
            "</div>"
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
html,body{{margin:0;background:#ff00ff}}
.case{{position:absolute;left:0;width:{flex_width}px;height:36px}}
.normalizer{{display:flex;width:{flex_width}px;height:12px}}
.normalizer i{{display:block;flex-basis:0;flex-shrink:1;min-width:0}}
.context{{position:absolute;left:0;top:16px;height:16px;background:#00ffff}}
</style>
{''.join(markup)}
"""
    return html, {
        "flexWidth": flex_width,
        "offset": offset,
        "cases": expected,
        "rowStride": 40,
        "sampleYWithinRow": 24,
        "contextColor": [0, 255, 255],
    }


def transform_animation_matmul_html(size: int) -> tuple[str, dict]:
    """Accumulate paused translate animations as signed dot products."""
    rng = random.Random(0x7A45F0 + size)
    input_codes = [rng.randint(-7, 7) for _ in range(size)]
    alternate_codes = [rng.randint(-7, 7) for _ in range(size)]
    inputs = [code / 8 for code in input_codes]
    weights = [[rng.randint(-4, 4) for _ in range(size)] for _ in range(size)]
    scale = 8
    base = 2048
    keyframes = "".join(
        f"@keyframes w{weight + 4}{{from{{transform:translateX(0)}}"
        f"to{{transform:translateX({16 * weight}px)}}}}"
        for weight in range(-4, 5)
    )
    delays = ",".join(f"-{(code + 8) / 16:.8f}s" for code in input_codes)
    alternate_delays = ",".join(
        f"-{(code + 8) / 16:.8f}s" for code in alternate_codes
    )
    markers = []
    expected_x = []
    for row_index, row in enumerate(weights):
        dot = sum(weight * value for weight, value in zip(row, inputs))
        position = base + scale * dot
        expected_x.append(round(position))
        names = ",".join(f"w{weight + 4}" for weight in row)
        underlying_left = base - scale * sum(row)
        markers.append(
            f'<i class="marker swatch" style="top:{row_index * 3}px;left:{underlying_left}px;'
            f'animation-name:{names}"></i>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
{keyframes}
html,body{{margin:0;background:white;--delays:{delays}}}
body.alternate{{--delays:{alternate_delays}}}
.marker{{position:absolute;width:2px;height:2px;background:black;will-change:transform;
animation-duration:1s;animation-delay:var(--delays);animation-timing-function:linear;
animation-fill-mode:both;animation-play-state:paused;animation-iteration-count:1;
animation-composition:add}}
</style>
{''.join(markers)}
"""
    return html, {
        "size": size,
        "effects": size * size,
        "htmlBytes": len(html.encode("utf-8")),
        "expectedMarkerX": expected_x,
        "rowStride": 3,
    }


def transform_dynamic_dot_html(term_count: int = 64, case_count: int = 24) -> tuple[str, dict]:
    """Use animation progress times a custom-property endpoint for dynamic dots."""
    rng = random.Random(0xD07D07)
    scale = 256
    base = 4096
    keyframes = "".join(
        f"@keyframes m{index}{{from{{transform:translateX(0)}}"
        f"to{{transform:translateX(calc(var(--k{index}) * {2 * scale}px))}}}}"
        for index in range(term_count)
    )
    names = ",".join(f"m{index}" for index in range(term_count))
    q_codes = [rng.randint(-15, 15) for _ in range(term_count)]
    alternate_q_codes = [rng.randint(-15, 15) for _ in range(term_count)]
    q_values = [code / 16 for code in q_codes]
    delays = ",".join(f"-{(code + 16) / 32:.8f}s" for code in q_codes)
    alternate_delays = ",".join(
        f"-{(code + 16) / 32:.8f}s" for code in alternate_q_codes
    )
    markers = []
    expected_x = []
    for case_index in range(case_count):
        k_codes = [rng.randint(-15, 15) for _ in range(term_count)]
        k_values = [code / 16 for code in k_codes]
        dot = sum(q * k for q, k in zip(q_values, k_values))
        expected_x.append(round(base + scale * dot))
        variables = "".join(
            f"--k{index}:{value:.12f};" for index, value in enumerate(k_values)
        )
        correction = " + ".join(f"var(--k{index})" for index in range(term_count))
        markers.append(
            f'<i class="dynamic-marker swatch" style="top:{case_index * 3}px;{variables}'
            f"left:calc({base}px - {scale}px * ({correction}));"
            f'"></i>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
{keyframes}
html,body{{margin:0;background:white;--qdelays:{delays}}}
body.alternate{{--qdelays:{alternate_delays}}}
.dynamic-marker{{position:absolute;width:2px;height:2px;background:black;will-change:transform;
animation-name:{names};animation-duration:1s;animation-timing-function:linear;
animation-fill-mode:both;animation-play-state:paused;animation-iteration-count:1;
animation-composition:add;animation-delay:var(--qdelays)}}
</style>
{''.join(markers)}
"""
    return html, {
        "termsPerDot": term_count,
        "cases": case_count,
        "effects": term_count * case_count,
        "htmlBytes": len(html.encode("utf-8")),
        "expectedMarkerX": expected_x,
        "rowStride": 3,
        "scalePixelsPerDotUnit": scale,
    }


def transform_shear_anchor_html(term_count: int = 16, case_count: int = 8) -> tuple[str, dict]:
    """Try to expose an additive matrix-shear dot through transformed anchor width."""
    rng = random.Random(0x5AEA12)
    height = 256
    box_width = 2
    baseline_shear = 4
    keyframes = "".join(
        f"@keyframes s{index}{{from{{transform:matrix(1,0,0,1,0,0)}}"
        f"to{{transform:matrix(1,0,calc(2 * var(--k{index})),1,0,0)}}}}"
        for index in range(term_count)
    )
    names = ",".join(f"s{index}" for index in range(term_count))
    markup = []
    expected_widths = []
    for case_index in range(case_count):
        q_codes = [rng.randint(-7, 7) for _ in range(term_count)]
        k_codes = [rng.randint(-7, 7) for _ in range(term_count)]
        q_values = [code / 16 for code in q_codes]
        k_values = [code / 16 for code in k_codes]
        dot = sum(q * k for q, k in zip(q_values, k_values))
        expected_widths.append(round(box_width + height * (baseline_shear + dot)))
        variables = "".join(
            f"--k{index}:{value:.12f};" for index, value in enumerate(k_values)
        )
        delays = ",".join(f"-{(code + 16) / 32:.8f}s" for code in q_codes)
        correction = " + ".join(f"var(--k{index})" for index in range(term_count))
        anchor = f"--shear-dot-{case_index}"
        top = case_index * (height + 16)
        markup.append(
            f'<i class="shear" style="top:{top}px;anchor-name:{anchor};{variables}'
            f"transform:matrix(1,0,calc({baseline_shear} - ({correction})),1,0,0);"
            f'animation-delay:{delays}"></i>'
            f'<b class="reader" style="top:{top + height + 4}px;position-anchor:{anchor};'
            f'width:anchor-size({anchor} width)"></b>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
{keyframes}
html,body{{margin:0;background:#ff00ff;anchor-scope:all}}
.shear{{position:absolute;left:0;width:{box_width}px;height:{height}px;background:black;
transform-origin:left top;animation-name:{names};animation-duration:1s;
animation-timing-function:linear;animation-fill-mode:both;animation-play-state:paused;
animation-iteration-count:1;animation-composition:add}}
.reader{{position:absolute;left:0;height:8px;background:#00ffff}}
</style>
{''.join(markup)}
"""
    return html, {
        "termsPerDot": term_count,
        "cases": case_count,
        "effects": term_count * case_count,
        "height": height,
        "rowStride": height + 16,
        "readerY": height + 8,
        "expectedReaderWidths": expected_widths,
        "htmlBytes": len(html.encode("utf-8")),
    }


def css_dynamic_dot_html(term_count: int = 64, case_count: int = 24) -> tuple[str, dict]:
    """Direct CSS calc() control for the dynamic transform-dot experiment."""
    rng = random.Random(0xD07D07)
    scale = 256
    base = 4096
    q_codes = [rng.randint(-15, 15) for _ in range(term_count)]
    alternate_q_codes = [rng.randint(-15, 15) for _ in range(term_count)]
    q_values = [code / 16 for code in q_codes]
    q_variables = "".join(
        f"--q{index}:{value:.12f};" for index, value in enumerate(q_values)
    )
    alternate_variables = "".join(
        f"--q{index}:{code / 16:.12f};"
        for index, code in enumerate(alternate_q_codes)
    )
    markers = []
    expected_x = []
    for case_index in range(case_count):
        k_codes = [rng.randint(-15, 15) for _ in range(term_count)]
        k_values = [code / 16 for code in k_codes]
        dot = sum(q * k for q, k in zip(q_values, k_values))
        expected_x.append(round(base + scale * dot))
        variables = "".join(
            f"--k{index}:{value:.12f};" for index, value in enumerate(k_values)
        )
        terms = " + ".join(
            f"var(--q{index}) * var(--k{index})" for index in range(term_count)
        )
        markers.append(
            f'<i class="calc-marker swatch" style="top:{case_index * 3}px;{variables}'
            f'left:calc({base}px + {scale}px * ({terms}))"></i>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
html,body{{margin:0;background:white;{q_variables}}}
body.alternate{{{alternate_variables}}}
.calc-marker{{position:absolute;width:2px;height:2px;background:black}}
</style>
{''.join(markers)}
"""
    return html, {
        "termsPerDot": term_count,
        "cases": case_count,
        "multiplications": term_count * case_count,
        "htmlBytes": len(html.encode("utf-8")),
        "expectedMarkerX": expected_x,
        "rowStride": 3,
        "scalePixelsPerDotUnit": scale,
    }


def resample_html() -> tuple[str, dict]:
    patterns = {
        "alternating": [0, 255] * 32,
        "halves": [0] * 32 + [255] * 32,
        "impulse": [255] + [0] * 63,
    }
    rows = []
    expected = {}
    for row, (name, values) in enumerate(patterns.items()):
        expected[name] = sum(values) / len(values)
        children = "".join(
            f'<i style="background:rgb({value} {value} {value})"></i>'
            for value in values
        )
        data_url = png_data_url(values)
        rects = "".join(
            f'<rect x="{index}" y="0" width="1" height="16" fill="rgb({value} {value} {value})"/>'
            for index, value in enumerate(values)
        )
        rows.append(
            f'<div class="probe" style="top:{row * 20}px;left:0"><div class="html-source">{children}</div></div>'
            f'<img class="probe image-source" style="top:{row * 20}px;left:8px" src="{data_url}">'
            f'<svg class="probe svg-source" style="top:{row * 20}px;left:16px" viewBox="0 0 64 16" preserveAspectRatio="none">{rects}</svg>'
        )
    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
html,body{{margin:0;background:#ff00ff}}
.probe{{position:absolute;width:1px;height:16px;overflow:visible}}
.html-source{{display:flex;width:64px;height:16px;transform:scaleX(.015625);transform-origin:left top;will-change:transform;contain:paint}}
.html-source i{{display:block;width:1px;height:16px;flex:none}}
.image-source{{object-fit:fill;image-rendering:auto}}
.svg-source{{overflow:hidden}}
</style>
{''.join(rows)}
"""
    return html, {
        "patterns": list(patterns),
        "expectedMean": expected,
        "techniques": {"htmlTransform": 0, "imageResample": 8, "inlineSvg": 16},
        "rowStride": 20,
    }


def screenshot(chrome: Path, html_path: Path, png_path: Path, size: tuple[int, int]) -> float:
    png_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="chrome-native-probe-") as profile:
        command = [
            str(chrome),
            "--headless=new",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={size[0]},{size[1]}",
            f"--screenshot={png_path}",
            html_path.resolve().as_uri(),
        ]
        started = time.perf_counter()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = started + 45
        stable_since = None
        previous_size = -1
        while time.perf_counter() < deadline:
            if png_path.exists():
                size_now = png_path.stat().st_size
                if size_now > 0 and size_now == previous_size:
                    if stable_since is None:
                        stable_since = time.perf_counter()
                    elif time.perf_counter() - stable_since >= 0.2:
                        break
                else:
                    stable_since = None
                    previous_size = size_now
            if process.poll() is not None and not png_path.exists():
                stderr = process.stderr.read().decode("utf-8", "replace")
                raise RuntimeError(f"Chrome failed for {html_path.name}: {stderr.strip()}")
            time.sleep(0.05)
        else:
            process.kill()
            process.wait(timeout=5)
            raise RuntimeError(f"Chrome timed out for {html_path.name}")
        elapsed = time.perf_counter() - started
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        return elapsed


def _read_exact(connection: socket.socket, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("WebSocket closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class CdpSocket:
    """Tiny standard-library WebSocket client sufficient for local CDP."""

    def __init__(self, url: str):
        parsed = urllib.parse.urlparse(url)
        self.connection = socket.create_connection((parsed.hostname, parsed.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request_target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = (
            f"GET {request_target} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.connection.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.connection.recv(4096)
        if not response.startswith(b"HTTP/1.1 101"):
            raise ConnectionError(response.decode("utf-8", "replace"))
        self.next_id = 1

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.connection.sendall(bytes(header) + masked)

    def _receive_frame(self) -> tuple[int, bytes]:
        first, second = _read_exact(self.connection, 2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", _read_exact(self.connection, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _read_exact(self.connection, 8))[0]
        mask = _read_exact(self.connection, 4) if second & 0x80 else None
        payload = _read_exact(self.connection, length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def command(self, method: str, params: dict | None = None) -> dict:
        command_id = self.next_id
        self.next_id += 1
        message = {"id": command_id, "method": method}
        if params:
            message["params"] = params
        self._send_frame(1, json.dumps(message).encode("utf-8"))
        while True:
            opcode, payload = self._receive_frame()
            if opcode == 9:
                self._send_frame(10, payload)
                continue
            if opcode == 8:
                raise ConnectionError("CDP closed the WebSocket")
            if opcode != 1:
                continue
            response = json.loads(payload)
            if response.get("id") != command_id:
                continue
            if "error" in response:
                raise RuntimeError(f"CDP {method}: {response['error']}")
            return response.get("result", {})

    def close(self) -> None:
        try:
            self._send_frame(8, b"")
        except OSError:
            pass
        self.connection.close()


def metric_map(response: dict) -> dict[str, float]:
    return {metric["name"]: metric["value"] for metric in response["metrics"]}


def warm_mutation_profile(
    chrome: Path, html_path: Path, size: tuple[int, int], rounds: int = 5
) -> dict:
    """Change a class with CDP (not script evaluation) and force a screenshot."""
    with tempfile.TemporaryDirectory(prefix="chrome-native-cdp-") as profile:
        command = [
            str(chrome),
            "--headless=new",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            f"--window-size={size[0]},{size[1]}",
            html_path.resolve().as_uri(),
        ]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            deadline = time.perf_counter() + 30
            while not port_file.exists() and time.perf_counter() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Chrome exited before opening its debugging port")
                time.sleep(0.05)
            if not port_file.exists():
                raise RuntimeError("Chrome did not open its debugging port")
            port = int(port_file.read_text().splitlines()[0])
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10))
            target = next(item for item in targets if item.get("type") == "page")
            cdp = CdpSocket(target["webSocketDebuggerUrl"])
            try:
                cdp.command("Page.enable")
                cdp.command("DOM.enable")
                cdp.command("CSS.enable")
                cdp.command("Performance.enable")
                # The debugging endpoint is available before the file URL has
                # necessarily completed its first style calculation.
                time.sleep(1.0)
                cdp.command("Page.getLayoutMetrics")
                root = cdp.command("DOM.getDocument", {"depth": 1})["root"]["nodeId"]
                body = cdp.command("DOM.querySelector", {"nodeId": root, "selector": "body"})["nodeId"]
                swatch = cdp.command(
                    "DOM.querySelector", {"nodeId": root, "selector": ".swatch"}
                )["nodeId"]
                samples = []
                for round_index in range(rounds):
                    before = metric_map(cdp.command("Performance.getMetrics"))
                    started = time.perf_counter()
                    if round_index % 2:
                        cdp.command("DOM.removeAttribute", {"nodeId": body, "name": "class"})
                    else:
                        cdp.command(
                            "DOM.setAttributeValue",
                            {"nodeId": body, "name": "class", "value": "alternate"},
                        )
                    computed = cdp.command("CSS.getComputedStyleForNode", {"nodeId": swatch})
                    elapsed = time.perf_counter() - started
                    after = metric_map(cdp.command("Performance.getMetrics"))
                    samples.append(
                        {
                            "wallClockSeconds": elapsed,
                            "recalcStyleSeconds": after.get("RecalcStyleDuration", 0)
                            - before.get("RecalcStyleDuration", 0),
                            "layoutSeconds": after.get("LayoutDuration", 0)
                            - before.get("LayoutDuration", 0),
                            "taskSeconds": after.get("TaskDuration", 0)
                            - before.get("TaskDuration", 0),
                            "firstBackgroundColor": next(
                                item["value"]
                                for item in computed["computedStyle"]
                                if item["name"] == "background-color"
                            ),
                        }
                    )
                medians = {
                    key: sorted(sample[key] for sample in samples)[len(samples) // 2]
                    for key in (
                        "wallClockSeconds",
                        "recalcStyleSeconds",
                        "layoutSeconds",
                        "taskSeconds",
                    )
                }
                return {"rounds": rounds, "median": medians, "samples": samples}
            finally:
                cdp.close()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


def sampled_reds(image: Image.Image, count: int, cell: int, y: int) -> list[int]:
    rgb = image.convert("RGB")
    return [rgb.getpixel((index * cell + cell // 2, y))[0] for index in range(count)]


def flex_boundaries(image: Image.Image, y: int, width: int) -> list[int]:
    rgb = image.convert("RGB")
    expected_colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))
    pixels = [rgb.getpixel((x, y)) for x in range(width)]
    boundaries = []
    current = expected_colors[0]
    for x, pixel in enumerate(pixels):
        if pixel != current:
            boundaries.append(x)
            if len(boundaries) == len(expected_colors) - 1:
                break
            current = expected_colors[len(boundaries)]
    boundaries.append(width)
    return boundaries


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = chrome_path()
    version = subprocess.run(
        [str(chrome), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()

    builders = {
        "color-precision": (color_precision_html, (320, 100)),
        "color-dot": (color_dot_html, (420, 80)),
        "color-simd-96": (lambda: color_simd_matmul_html(96), (320, 80)),
        "color-simd-192": (lambda: color_simd_matmul_html(192), (320, 80)),
        "color-simd-384": (lambda: color_simd_matmul_html(384), (520, 80)),
        "color-simd-768": (lambda: color_simd_matmul_html(768), (1100, 80)),
        "color-simd-chain": (color_simd_chain_html, (180, 80)),
        "flex-softmax": (flex_softmax_html, (4096, 100)),
        "flex-anchor-attention": (flex_anchor_attention_html, (5000, 140)),
        "transform-dot-32": (lambda: transform_animation_matmul_html(32), (4096, 120)),
        "transform-dot-64": (lambda: transform_animation_matmul_html(64), (4096, 220)),
        "transform-dot-128": (lambda: transform_animation_matmul_html(128), (4096, 420)),
        "transform-dot-256": (lambda: transform_animation_matmul_html(256), (4096, 800)),
        "transform-dot-384": (lambda: transform_animation_matmul_html(384), (4096, 1180)),
        "transform-dynamic-dot": (transform_dynamic_dot_html, (8192, 100)),
        "transform-shear-anchor": (transform_shear_anchor_html, (4096, 2200)),
        "css-dynamic-dot": (css_dynamic_dot_html, (8192, 100)),
        "resample": (resample_html, (64, 100)),
    }
    metadata = {}
    timings = {}
    images = {}
    for name, (builder, size) in builders.items():
        html, meta = builder()
        html_path = OUT / f"{name}.html"
        png_path = OUT / f"{name}.png"
        html_path.write_text(html, encoding="utf-8")
        timings[name] = screenshot(chrome, html_path, png_path, size)
        metadata[name] = meta
        images[name] = Image.open(png_path)

    color_meta = metadata["color-precision"]
    color_rows = {}
    for row, depth in enumerate(color_meta["depths"]):
        actual = sampled_reds(images["color-precision"], 17, 16, row * 16 + 8)
        expected = color_meta["expectedRed"][str(depth)]
        color_rows[str(depth)] = {
            "actualRed": actual,
            "expectedRed": expected,
            "maximumError": max(abs(a - b) for a, b in zip(actual, expected)),
            "distinctLevels": len(set(actual)),
        }

    dot_meta = metadata["color-dot"]
    dot_actual = sampled_reds(images["color-dot"], dot_meta["cases"], 16, 16)
    dot_errors = [
        actual - expected
        for actual, expected in zip(dot_actual, dot_meta["expectedRed"])
    ]

    simd_results = {}
    for name in ("color-simd-96", "color-simd-192", "color-simd-384", "color-simd-768"):
        simd_meta = metadata[name]
        rgb = images[name].convert("RGB")
        actual_rgb = [
            list(rgb.getpixel((group * simd_meta["sampleCellPixels"] + simd_meta["sampleCellPixels"] // 2, 16)))
            for group in range(simd_meta["outputColorCount"])
        ]
        errors = [
            actual - expected
            for actual_triplet, expected_triplet in zip(actual_rgb, simd_meta["expectedRGB"])
            for actual, expected in zip(actual_triplet, expected_triplet)
        ]
        simd_results[str(simd_meta["size"])] = {
            "weights": simd_meta["weights"],
            "htmlBytes": simd_meta["htmlBytes"],
            "screenshotWallClockSecondsIncludingStartup": timings[name],
            "maximumChannelError": max(abs(error) for error in errors),
            "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        }

    for name, viewport in (
        ("color-simd-96", (320, 80)),
        ("color-simd-192", (320, 80)),
        ("color-simd-384", (520, 80)),
        ("color-simd-768", (1100, 80)),
    ):
        size = str(metadata[name]["size"])
        simd_results[size]["warmClassMutation"] = warm_mutation_profile(
            chrome, OUT / f"{name}.html", viewport
        )

    chain_meta = metadata["color-simd-chain"]
    chain_image = images["color-simd-chain"].convert("RGB")
    chain_actual = [
        list(chain_image.getpixel((group * chain_meta["sampleCellPixels"] + chain_meta["sampleCellPixels"] // 2, 16)))
        for group in range(chain_meta["outputColorCount"])
    ]
    chain_errors = [
        actual - expected
        for actual_triplet, expected_triplet in zip(chain_actual, chain_meta["expectedRGB"])
        for actual, expected in zip(actual_triplet, expected_triplet)
    ]

    flex_meta = metadata["flex-softmax"]
    flex_rows = []
    for row, expected_boundaries in enumerate(flex_meta["expectedBoundaries"]):
        actual_boundaries = flex_boundaries(
            images["flex-softmax"], row * 16 + 8, flex_meta["width"]
        )
        errors = [
            actual - expected
            for actual, expected in zip(actual_boundaries, expected_boundaries)
        ]
        flex_rows.append(
            {
                "scores": flex_meta["scores"][row],
                "actualBoundaries": actual_boundaries,
                "expectedBoundaries": expected_boundaries,
                "maximumBoundaryErrorPixels": max(abs(error) for error in errors),
            }
        )

    resample_meta = metadata["resample"]
    resample_results = {}
    resample_image = images["resample"].convert("RGB")
    for row, pattern in enumerate(resample_meta["patterns"]):
        values = {}
        for technique, x in resample_meta["techniques"].items():
            values[technique] = resample_image.getpixel(
                (x, row * resample_meta["rowStride"] + 8)
            )[0]
        resample_results[pattern] = {
            "expectedMean": resample_meta["expectedMean"][pattern],
            "actualRed": values,
        }

    attention_meta = metadata["flex-anchor-attention"]
    attention_image = images["flex-anchor-attention"].convert("RGB")
    attention_results = []
    for row, case in enumerate(attention_meta["cases"]):
        y = row * attention_meta["rowStride"] + attention_meta["sampleYWithinRow"]
        actual_width = 0
        for x in range(attention_image.width):
            if list(attention_image.getpixel((x, y))) != attention_meta["contextColor"]:
                break
            actual_width += 1
        attention_results.append(
            {
                **case,
                "actualEncodedWidthPixels": actual_width,
                "errorPixels": actual_width - case["expectedEncodedWidth"],
            }
        )

    transform_results = {}
    for name in (
        "transform-dot-32",
        "transform-dot-64",
        "transform-dot-128",
        "transform-dot-256",
        "transform-dot-384",
    ):
        transform_meta = metadata[name]
        transform_image = images[name].convert("RGB")
        actual_x = []
        for row in range(transform_meta["size"]):
            y = row * transform_meta["rowStride"] + 1
            black = [
                x
                for x in range(transform_image.width)
                if transform_image.getpixel((x, y)) == (0, 0, 0)
            ]
            actual_x.append(black[0] if black else -1)
        errors = [
            actual - expected
            for actual, expected in zip(actual_x, transform_meta["expectedMarkerX"])
        ]
        transform_results[str(transform_meta["size"])] = {
            "effects": transform_meta["effects"],
            "htmlBytes": transform_meta["htmlBytes"],
            "screenshotWallClockSecondsIncludingStartup": timings[name],
            "missingMarkers": sum(value < 0 for value in actual_x),
            "maximumPositionErrorPixels": max(abs(error) for error in errors),
            "rmsePixels": math.sqrt(sum(error * error for error in errors) / len(errors)),
        }

    dynamic_meta = metadata["transform-dynamic-dot"]
    dynamic_image = images["transform-dynamic-dot"].convert("RGB")
    dynamic_actual_x = []
    for row in range(dynamic_meta["cases"]):
        y = row * dynamic_meta["rowStride"] + 1
        black = [
            x
            for x in range(dynamic_image.width)
            if dynamic_image.getpixel((x, y)) == (0, 0, 0)
        ]
        dynamic_actual_x.append(black[0] if black else -1)
    dynamic_errors = [
        actual - expected
        for actual, expected in zip(dynamic_actual_x, dynamic_meta["expectedMarkerX"])
    ]
    dynamic_warm = warm_mutation_profile(
        chrome, OUT / "transform-dynamic-dot.html", (8192, 100)
    )
    calc_meta = metadata["css-dynamic-dot"]
    calc_image = images["css-dynamic-dot"].convert("RGB")
    calc_actual_x = []
    for row in range(calc_meta["cases"]):
        y = row * calc_meta["rowStride"] + 1
        black = [
            x for x in range(calc_image.width) if calc_image.getpixel((x, y)) == (0, 0, 0)
        ]
        calc_actual_x.append(black[0] if black else -1)
    calc_errors = [
        actual - expected
        for actual, expected in zip(calc_actual_x, calc_meta["expectedMarkerX"])
    ]
    calc_warm = warm_mutation_profile(chrome, OUT / "css-dynamic-dot.html", (8192, 100))

    shear_meta = metadata["transform-shear-anchor"]
    shear_image = images["transform-shear-anchor"].convert("RGB")
    shear_actual_widths = []
    for row in range(shear_meta["cases"]):
        y = row * shear_meta["rowStride"] + shear_meta["readerY"]
        width = 0
        for x in range(shear_image.width):
            if shear_image.getpixel((x, y)) != (0, 255, 255):
                break
            width += 1
        shear_actual_widths.append(width)
    shear_errors = [
        actual - expected
        for actual, expected in zip(shear_actual_widths, shear_meta["expectedReaderWidths"])
    ]

    results = {
        "chrome": version,
        "runtimeJavascript": False,
        "wallClockSecondsIncludingChromeStartup": timings,
        "colorPrecision": color_rows,
        "colorDot": {
            "cases": dot_meta["cases"],
            "termsPerDot": dot_meta["termsPerDot"],
            "actualRed": dot_actual,
            "expectedRed": dot_meta["expectedRed"],
            "maximumError": max(abs(error) for error in dot_errors),
            "rmse": math.sqrt(sum(error * error for error in dot_errors) / len(dot_errors)),
        },
        "colorSimdMatmul": simd_results,
        "colorSimdTwoLayerChain": {
            "size": chain_meta["size"],
            "matmuls": chain_meta["matmuls"],
            "nonlinearity": chain_meta["nonlinearity"],
            "htmlBytes": chain_meta["htmlBytes"],
            "actualRGB": chain_actual,
            "expectedRGB": chain_meta["expectedRGB"],
            "maximumChannelError": max(abs(error) for error in chain_errors),
            "rmse": math.sqrt(sum(error * error for error in chain_errors) / len(chain_errors)),
        },
        "flexSoftmax": flex_rows,
        "flexAnchorAttention": attention_results,
        "transformAnimationMatmul": transform_results,
        "transformDynamicDot": {
            "termsPerDot": dynamic_meta["termsPerDot"],
            "cases": dynamic_meta["cases"],
            "effects": dynamic_meta["effects"],
            "htmlBytes": dynamic_meta["htmlBytes"],
            "screenshotWallClockSecondsIncludingStartup": timings["transform-dynamic-dot"],
            "scalePixelsPerDotUnit": dynamic_meta["scalePixelsPerDotUnit"],
            "missingMarkers": sum(value < 0 for value in dynamic_actual_x),
            "maximumPositionErrorPixels": max(abs(error) for error in dynamic_errors),
            "rmsePixels": math.sqrt(
                sum(error * error for error in dynamic_errors) / len(dynamic_errors)
            ),
            "warmSharedQueryMutation": dynamic_warm,
        },
        "cssCalcDynamicDotControl": {
            "termsPerDot": calc_meta["termsPerDot"],
            "cases": calc_meta["cases"],
            "multiplications": calc_meta["multiplications"],
            "htmlBytes": calc_meta["htmlBytes"],
            "screenshotWallClockSecondsIncludingStartup": timings["css-dynamic-dot"],
            "missingMarkers": sum(value < 0 for value in calc_actual_x),
            "maximumPositionErrorPixels": max(abs(error) for error in calc_errors),
            "rmsePixels": math.sqrt(
                sum(error * error for error in calc_errors) / len(calc_errors)
            ),
            "warmSharedQueryMutation": calc_warm,
        },
        "transformShearAnchorHandoff": {
            "termsPerDot": shear_meta["termsPerDot"],
            "cases": shear_meta["cases"],
            "effects": shear_meta["effects"],
            "htmlBytes": shear_meta["htmlBytes"],
            "actualReaderWidths": shear_actual_widths,
            "expectedReaderWidths": shear_meta["expectedReaderWidths"],
            "maximumWidthErrorPixels": max(abs(error) for error in shear_errors),
            "rmsePixels": math.sqrt(
                sum(error * error for error in shear_errors) / len(shear_errors)
            ),
        },
        "transformAnimationFull768Stress": {
            "effects": 768 * 768,
            "result": "did not render before the 45 second timeout",
        },
        "resampling": resample_results,
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
