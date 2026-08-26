#!/usr/bin/env python3
"""Build integer CSS-counter matrix reduction probes.

Each input is a geometry width. A child consumes that width through `cqi` and
increments every output counter by a weighted integer. An additive counter
style renders the final integer as power-of-two glyphs whose advances recover
the counter value as geometry.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "counter-matrix"
UPEM = 1_000
FONT_SIZE = 10
INPUT_BASE = 1_000
COUNTER_BASE = 1_000
CODE_MAX = 31
MAX_POWER = 14
SIZES = (4, 16, 64, 256, 768)


def empty_glyph():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def build_counter_font(path: Path) -> None:
    names = [".notdef", *[f"bit-{power}" for power in range(MAX_POWER + 1)]]
    cmap = {0xE300 + power: f"bit-{power}" for power in range(MAX_POWER + 1)}
    glyphs = {name: empty_glyph() for name in names}
    metrics = {".notdef": (0, 0)}
    metrics.update({f"bit-{power}": (1 << power, 0) for power in range(MAX_POWER + 1)})
    builder = FontBuilder(UPEM, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=UPEM, descent=0)
    builder.setupNameTable({
        "familyName": "CSS Counter Width",
        "styleName": "Regular",
        "uniqueFontIdentifier": "CSS-Counter-Width",
        "fullName": "CSS Counter Width",
        "psName": "CSSCounterWidth",
    })
    builder.setupOS2(
        sTypoAscender=UPEM,
        sTypoDescender=0,
        usWinAscent=UPEM,
        usWinDescent=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.save(path)
    font = TTFont(path, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(path.with_suffix(".woff2"))


def number(value: float) -> str:
    return f"{value:.9g}"


def counter_style() -> str:
    symbols = ",".join(
        f'{1 << power} "\\{0xE300 + power:x}"'
        for power in reversed(range(MAX_POWER + 1))
    )
    return f'''@counter-style binary-width{{system:additive;
additive-symbols:{symbols};fallback:decimal}}'''


def build_page(size: int) -> dict[str, object]:
    rng = np.random.default_rng(20260913 + size)
    weights = rng.integers(-3, 4, size=(size, size), dtype=np.int16)
    # Avoid empty declarations/constant rows in the small probes.
    for output in range(size):
        if not np.any(weights[output]):
            weights[output, output % size] = 1
    codes = rng.integers(0, CODE_MAX + 1, size=(2, size), dtype=np.int16)
    sums = codes.astype(np.int64) @ weights.astype(np.int64).T
    resets = COUNTER_BASE - np.minimum(0, np.min(sums, axis=0))
    expected_counters = sums + resets
    if np.min(expected_counters) <= 0:
        raise ValueError("counter base is too small")

    reset_list = " ".join(f"y{output} {int(resets[output])}" for output in range(size))
    case_rules = []
    for case in range(2):
        case_rules.extend(
            f'body:has(#case-{case}:checked) .s{index}'
            f'{{width:{INPUT_BASE + int(codes[case, index])}px}}'
            for index in range(size)
        )

    source_rules = []
    increment_rules = []
    for input_index in range(size):
        anchor = f"--x{input_index}"
        source_rules.append(f".s{input_index}{{anchor-name:{anchor}}}")
        increments = []
        for output, weight in enumerate(weights[:, input_index]):
            if weight:
                increments.append(
                    f"y{output} calc((100cqi / 1px - {INPUT_BASE}) * {int(weight)})"
                )
        increment_rules.append(
            f".i{input_index}{{counter-increment:{' '.join(increments)}}}"
        )

    result_rules = []
    result_nodes = []
    for output in range(size):
        result_rules.append(
            f'.r{output}::before{{content:counter(y{output},binary-width)}}'
        )
        result_nodes.append(
            f'<i class="result r{output}" data-output="{output}"></i>'
        )

    flat_sources = "".join(f'<i class="source s{index}"></i>' for index in range(size))
    flat_bridges = "".join(
        f'<i class="bridge" style="position-anchor:--x{index};'
        f'width:anchor-size(--x{index} width)"><i class="increment i{index}"></i></i>'
        for index in range(size)
    )
    shared_css = f'''
@font-face{{font-family:CounterWidth;src:url("counter-width.woff2") format("woff2")}}
{counter_style()}
html,body{{margin:0}}
input{{position:fixed;left:-10000px}}
.matrix{{position:relative;counter-reset:{reset_list}}}
.source,.bridge{{position:absolute;left:0;top:0;height:1px}}
.source{{display:block}}
.increment{{display:block;position:relative;width:1px;height:1px}}
.bridge{{container-type:inline-size}}
.result{{position:absolute;left:0;top:0;display:inline-block;width:max-content;
  white-space:pre;font-family:CounterWidth;font-size:{FONT_SIZE}px;line-height:1;
  font-kerning:none;letter-spacing:0}}
{''.join(case_rules)}
{''.join(source_rules)}
{''.join(increment_rules)}
{''.join(result_rules)}
'''
    html = f'''<!doctype html><meta charset="utf-8"><title>flat counter matrix {size}</title>
<style>
{shared_css}
</style>
<input id="case-0" name="case" type="radio" checked>
<input id="case-1" name="case" type="radio">
<main class="matrix" data-size="{size}">
{flat_sources}{flat_bridges}{''.join(result_nodes)}
</main>'''
    path = OUT / f"n{size}.html"
    path.write_text(html)

    chain = "".join(result_nodes)
    for input_index in reversed(range(size)):
        anchor = f"--x{input_index}"
        chain = (
            f'<i class="source s{input_index}"></i>'
            f'<i class="bridge" style="position-anchor:{anchor};'
            f'width:anchor-size({anchor} width)"><i class="increment i{input_index}">'
            f'{chain}</i></i>'
        )
    xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>nested counter matrix {size}</title>
<style>{shared_css}</style></head><body>
<input id="case-0" name="case" type="radio" checked="checked" />
<input id="case-1" name="case" type="radio" />
<main class="matrix" data-size="{size}">{chain}</main>
</body></html>'''
    (OUT / f"n{size}.xhtml").write_text(xhtml)

    timelines = [f"--t{index}" for index in range(size)]
    progresses = [f"--p{index}" for index in range(size)]
    timeline_case_rules = "".join(
        f'body:has(#case-{case}:checked) .ts{index}'
        f'{{width:{1 + int(codes[case, index])}px}}'
        for case in range(2)
        for index in range(size)
    )
    timeline_rules = []
    timeline_nodes = []
    counter_nodes = []
    for input_index in range(size):
        timeline = timelines[input_index]
        progress = progresses[input_index]
        animation = f"tk{input_index}"
        code_expr = f"round(nearest,100 / var({progress}) - 101,1)"
        increments = " ".join(
            f"y{output} calc(({code_expr}) * {int(weight)})"
            for output, weight in enumerate(weights[:, input_index])
            if weight
        )
        timeline_rules.append(
            f'@property {progress}{{syntax:"<number>";inherits:false;initial-value:.5}}'
            f'@keyframes {animation}{{from{{{progress}:0}}to{{{progress}:1}}}}'
            f'.ts{input_index}{{view-timeline:{timeline} inline}}'
            f'.ti{input_index}{{animation:{animation} 1s linear both;'
            f'animation-timeline:{timeline};animation-range:cover;'
            f'counter-increment:{increments}}}'
        )
        timeline_nodes.append(f'<i class="timeline-subject ts{input_index}"></i>')
        counter_nodes.append(f'<i class="timeline-increment ti{input_index}"></i>')
    timeline_html = f'''<!doctype html><meta charset="utf-8"><title>timeline counter matrix {size}</title>
<style>
@font-face{{font-family:CounterWidth;src:url("counter-width.woff2") format("woff2")}}
{counter_style()}
{''.join(timeline_rules)}
html,body{{margin:0}}
input{{position:fixed;left:-10000px}}
.matrix{{position:relative;counter-reset:{reset_list};timeline-scope:{','.join(timelines)}}}
.scroller{{position:fixed;left:0;top:-20000px;width:100px;height:1px;overflow-x:scroll}}
.track{{position:relative;width:200px;height:1px}}
.timeline-subject{{position:absolute;left:0;top:0;display:block;height:1px}}
.timeline-increment{{position:absolute;left:0;top:0;width:1px;height:1px}}
.result{{position:absolute;left:0;top:0;display:inline-block;width:max-content;
  white-space:pre;font-family:CounterWidth;font-size:{FONT_SIZE}px;line-height:1;
  font-kerning:none;letter-spacing:0}}
{timeline_case_rules}
{''.join(result_rules)}
</style>
<input id="case-0" name="case" type="radio" checked>
<input id="case-1" name="case" type="radio">
<main class="matrix" data-size="{size}">
<div class="scroller"><div class="track">{''.join(timeline_nodes)}</div></div>
{''.join(counter_nodes)}{''.join(result_nodes)}
</main>'''
    (OUT / f"n{size}-timeline.html").write_text(timeline_html)
    reference = {
        "size": size,
        "codes": codes.tolist(),
        "weights": weights.tolist(),
        "counterResets": resets.tolist(),
        "expectedCounters": expected_counters.tolist(),
        "expectedWidths": (expected_counters * FONT_SIZE / UPEM).tolist(),
        "terms": int(np.count_nonzero(weights)),
        "denseTerms": size * size,
        "htmlBytes": len(html.encode()),
        "xhtmlBytes": len(xhtml.encode()),
        "timelineBytes": len(timeline_html.encode()),
    }
    (OUT / f"n{size}.json").write_text(json.dumps(reference) + "\n")
    return {
        "size": size,
        "terms": reference["terms"],
        "denseTerms": reference["denseTerms"],
        "htmlBytes": reference["htmlBytes"],
        "xhtmlBytes": reference["xhtmlBytes"],
        "timelineBytes": reference["timelineBytes"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_counter_font(OUT / "counter-width.ttf")
    manifest = [build_page(size) for size in SIZES]
    (OUT / "manifest.json").write_text(json.dumps({"sizes": manifest}, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
