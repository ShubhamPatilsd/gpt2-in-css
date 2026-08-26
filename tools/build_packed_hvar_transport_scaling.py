#!/usr/bin/env python3
"""Build 12-bit packed HVAR vector-transport scaling fixtures."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "packed-hvar-transport-scaling"
SIZES = (64, 128, 256, 512, 768)
OUTPUT_WIDTH = 64
GROUP_SIZE = 4
RADIX = 64
LEVELS = 4_095
SOURCE_BASE = 20_000
MATRIX_BASE = 20_000
FONT_SIZE = 1_000


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def vector_settings(size: int, active: int | None = None) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {1 if index == active else 0}'
        for index in range(size)
    )


def packed_digit(axis: str, place: int) -> str:
    size = "100cqi" if axis == "i" else "100cqb"
    power = RADIX ** place
    if place == 0:
        return f"mod(round(nearest,{size}/1px,1),{RADIX})"
    if place == GROUP_SIZE - 1:
        return f"round(down,{size}/1px/{power},1)"
    return f"mod(round(down,{size}/1px/{power},1),{RADIX})"


def build_size(size: int) -> dict[str, object]:
    directory = OUTPUT / f"n{size}"
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(10_000 + size)
    source_codes = rng.integers(0, LEVELS + 1, size=(2, size), dtype=np.int16)
    source_bases = SOURCE_BASE + source_codes[0].astype(np.int32)
    source_deltas = (source_codes[1] - source_codes[0]).reshape(size, 1)
    build_direct_font_backend(
        source_deltas,
        directory / "source.ttf",
        base_advance=source_bases,
        codepoint_start=0xE000,
        axis_tags=["CASE"],
    )

    weights = rng.integers(-16, 17, size=(OUTPUT_WIDTH, size), dtype=np.int16)
    shards = math.ceil(size / 256)
    font_faces = []
    matrix_characters = [[] for _ in range(OUTPUT_WIDTH)]
    matrix_font_bytes = 0
    for shard in range(shards):
        start = shard * 256
        stop = min(size, start + 256)
        codepoint_start = 0xF0000 + shard * 0x1000
        font_path = directory / f"matrix-{shard}.ttf"
        build_direct_font_backend(
            weights[:, start:stop],
            font_path,
            base_advance=MATRIX_BASE,
            axis_offset=start,
            codepoint_start=codepoint_start,
        )
        woff2 = font_path.with_suffix(".woff2")
        matrix_font_bytes += woff2.stat().st_size
        font_faces.append(
            f'@font-face{{font-family:MatrixS{shard};src:url("{woff2.name}") '
            f'format("woff2");unicode-range:U+{codepoint_start:X}-'
            f'U+{codepoint_start + OUTPUT_WIDTH - 1:X}}}'
        )
        for output in range(OUTPUT_WIDTH):
            matrix_characters[output].append(
                f"&#x{codepoint_start + output:X};"
            )

    zero = vector_settings(size)
    keyframes = "".join(
        f"@keyframes c{dimension}{{from{{font-variation-settings:var(--zero)}}"
        f"to{{font-variation-settings:{vector_settings(size, dimension)}}}}}"
        for dimension in range(size)
    )
    pack_rules = []
    contribution_rules = []
    decode_rules = []
    for group in range(size // GROUP_SIZE):
        start = group * GROUP_SIZE
        declarations = ";".join(
            f"--code{place}:round(nearest,clamp(0px,"
            f"anchor-size(--s{dimension:03d} width) - {SOURCE_BASE}px,"
            f"{LEVELS}px),1px)"
            for place, dimension in enumerate(range(start, start + GROUP_SIZE))
        )
        low_terms = [
            f"{RADIX ** place} * mod(var(--code{place})/1px,{RADIX}) * 1px"
            for place in range(GROUP_SIZE)
        ]
        high_terms = [
            f"{RADIX ** place} * round(down,var(--code{place})/1px/{RADIX},1) * 1px"
            for place in range(GROUP_SIZE)
        ]
        pack_rules.append(
            f".pack-{group}{{{declarations};"
            f"width:calc({' + '.join(low_terms)});"
            f"height:calc({' + '.join(high_terms)})}}"
        )
        progress = [
            f"({packed_digit('i', place)} + {RADIX} * "
            f"{packed_digit('b', place)})/{LEVELS}"
            for place in range(GROUP_SIZE)
        ]
        contribution_rules.append(
            f".contrib-{group}{{animation-name:"
            + ",".join(f"c{start + place}" for place in range(GROUP_SIZE))
            + ";animation-delay:"
            + ",".join(f"calc(-1s * {value})" for value in progress)
            + "}"
        )
        decode_rules.append(
            f".decode-{group}{{"
            + ";".join(
                f"--v{start + place:03d}:calc({value})"
                for place, value in enumerate(progress)
            )
            + "}"
        )

    result = "".join(
        f'<i class="metric" data-dimension="{output}">'
        f'{"".join(matrix_characters[output])}</i>'
        for output in range(OUTPUT_WIDTH)
    )
    groups = size // GROUP_SIZE
    chain = f'<output id="result" class="contribution contrib-{groups - 1}">{result}</output>'
    for group in reversed(range(groups)):
        start = group * GROUP_SIZE
        sources = "".join(
            f'<i class="source" style="anchor-name:--s{dimension:03d}">'
            f'&#x{0xE000 + dimension:X};</i>'
            for dimension in range(start, start + GROUP_SIZE)
        )
        classes = f"carrier pack-{group}"
        if group:
            classes += f" contribution contrib-{group - 1}"
        chain = (
            sources
            + f'<div class="{classes}" style="position-anchor:--s{start:03d}">'
            + chain
            + "</div>"
        )

    html = (
        '<!doctype html><meta charset="utf-8">'
        f'<title>Packed HVAR transport n={size}</title>'
        '<link rel="stylesheet" href="style.css">'
        '<input type="radio" name="case" id="case0" checked>'
        '<input type="radio" name="case" id="case1">'
        f'<main id="scope">{chain}</main>'
    )
    css = (
        '@font-face{font-family:Source;src:url("source.woff2") format("woff2")}'
        + "".join(font_faces)
        + keyframes
        + "html,body{margin:0;overflow:clip}"
        + f"#scope{{--case:0;--zero:{zero};position:relative}}"
        + "body:has(#case1:checked) #scope{--case:1}"
        + ".source{position:absolute;display:inline-block;width:max-content;height:1px;"
        + f"overflow:hidden;white-space:pre;font-family:Source;font-size:{FONT_SIZE}px;"
        + 'font-variation-settings:"CASE" var(--case);font-kerning:none;font-style:normal}'
        + ".carrier{position:absolute;container-type:size}"
        + ".pack-0{font-family:serif;font-variation-settings:var(--zero)}"
        + ".contribution{position:absolute;animation-duration:1s;"
        + "animation-play-state:paused;animation-timing-function:linear;"
        + "animation-fill-mode:both;animation-composition:add}"
        + f"#result{{font-family:{','.join(f'MatrixS{shard}' for shard in range(shards))};"
        + f"font-size:{FONT_SIZE}px;line-height:1;font-kerning:none;white-space:pre;height:1px}}"
        + ".metric{display:inline-block;height:1px;overflow:hidden;font-style:normal}"
        + "".join(pack_rules)
        + "".join(contribution_rules)
    )
    (directory / "index.html").write_text(html)
    (directory / "style.css").write_text(css)

    registered_chain = '<output id="result" class="decode-{group}">{result}</output>'.format(
        group=groups - 1,
        result=result,
    )
    for group in reversed(range(groups)):
        start = group * GROUP_SIZE
        sources = "".join(
            f'<i class="source" style="anchor-name:--s{dimension:03d}">'
            f'&#x{0xE000 + dimension:X};</i>'
            for dimension in range(start, start + GROUP_SIZE)
        )
        classes = f"carrier pack-{group}"
        if group:
            classes += f" decode-{group - 1}"
        registered_chain = (
            sources
            + f'<div class="{classes}" style="position-anchor:--s{start:03d}">'
            + registered_chain
            + "</div>"
        )
    registered_html = (
        '<!doctype html><meta charset="utf-8">'
        f'<title>Registered packed HVAR transport n={size}</title>'
        '<link rel="stylesheet" href="registered.css">'
        '<input type="radio" name="case" id="case0" checked>'
        '<input type="radio" name="case" id="case1">'
        f'<main id="scope">{registered_chain}</main>'
    )
    registrations = "".join(
        f'@property --v{dimension:03d}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for dimension in range(size)
    )
    sink_settings = ",".join(
        f'"{axis_tag(dimension)}" var(--v{dimension:03d})'
        for dimension in range(size)
    )
    registered_css = (
        '@font-face{font-family:Source;src:url("source.woff2") format("woff2")}'
        + "".join(font_faces)
        + registrations
        + "html,body{margin:0;overflow:clip}#scope{--case:0;position:relative}"
        + "body:has(#case1:checked) #scope{--case:1}"
        + ".source{position:absolute;display:inline-block;width:max-content;height:1px;"
        + f"overflow:hidden;white-space:pre;font-family:Source;font-size:{FONT_SIZE}px;"
        + 'font-variation-settings:"CASE" var(--case);font-kerning:none;font-style:normal}'
        + ".carrier{position:absolute;container-type:size}"
        + f"#result{{position:absolute;font-family:"
        + ",".join(f"MatrixS{shard}" for shard in range(shards))
        + f";font-size:{FONT_SIZE}px;line-height:1;font-kerning:none;white-space:pre;"
        + f"height:1px;font-variation-settings:{sink_settings}}}"
        + ".metric{display:inline-block;height:1px;overflow:hidden;font-style:normal}"
        + "".join(pack_rules)
        + "".join(decode_rules)
    )
    (directory / "registered.html").write_text(registered_html)
    (directory / "registered.css").write_text(registered_css)
    progress = source_codes.astype(np.float64) / LEVELS
    expected = shards * MATRIX_BASE + progress @ weights.T
    result = {
        "size": size,
        "outputWidth": OUTPUT_WIDTH,
        "groups": groups,
        "shards": shards,
        "expectedWidths": expected.tolist(),
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
        "registeredHtmlBytes": len(registered_html.encode()),
        "registeredCssBytes": len(registered_css.encode()),
        "sourceFontBytes": (directory / "source.woff2").stat().st_size,
        "matrixFontBytes": matrix_font_bytes,
    }
    (directory / "reference.json").write_text(json.dumps(result) + "\n")
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = [build_size(size) for size in SIZES]
    (OUTPUT / "reference.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps([
        {key: result[key] for key in (
            "size", "groups", "shards", "htmlBytes", "cssBytes",
            "sourceFontBytes", "matrixFontBytes",
        )}
        for result in results
    ], indent=2))


if __name__ == "__main__":
    main()
