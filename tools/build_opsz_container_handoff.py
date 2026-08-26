#!/usr/bin/env python3
"""Build width -> container unit -> optical-size axis handoff probes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "opsz-container-handoff"
UPEM = 1_000
SOURCE_FONT_SIZE = 100
SOURCE_BASE = 600
SOURCE_DELTA = 400
OPSZ_MIN = 60
OPSZ_DEFAULT = 60
OPSZ_MAX = 100
CONSUMER_BASE = 500
CONSUMER_DELTA = 400
CASES = (0.0, 0.25, 0.75, 1.0)
SIZES = (16, 64, 256, 768, 1_536, 3_072)
MODES = ("none", "auto", "explicit")
FOUR_AXIS_TAGS = ("wght", "wdth", "slnt", "opsz")
FOUR_AXIS_WEIGHTS = (100, 200, 300, 400)
FOUR_AXIS_BASE = 2_000
FOUR_AXIS_CASES = (
    (0.1, 0.25, 0.4, 0.55),
    (0.7, 0.55, 0.4, 0.25),
)


def compress(path: Path) -> None:
    font = TTFont(path, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(path.with_suffix(".woff2"))


def build_consumer(path: Path) -> None:
    # Reuse the direct HVAR builder for the glyph and then replace its generic
    # 0..1 axis with a standards-recognized optical-size axis.  HVAR regions
    # are normalized, so the existing positive support remains correct.
    build_direct_font_backend(
        np.asarray([[CONSUMER_DELTA]], dtype=np.int16),
        path,
        base_advance=CONSUMER_BASE,
        codepoint_start=0xE100,
        axis_tags=["opsz"],
    )
    font = TTFont(path, recalcTimestamp=False)
    axis: Axis = font["fvar"].axes[0]
    axis.minValue = OPSZ_MIN
    axis.defaultValue = OPSZ_DEFAULT
    axis.maxValue = OPSZ_MAX
    axis.flags = 0
    axis.axisNameID = font["name"].addName("Optical size")
    buildStatTable(
        font,
        [{"tag": "opsz", "name": axis.axisNameID, "ordering": 0}],
    )
    font.recalcTimestamp = False
    font.save(path)
    compress(path)


def build_four_axis_consumer(path: Path) -> None:
    build_direct_font_backend(
        np.asarray([FOUR_AXIS_WEIGHTS], dtype=np.int16),
        path,
        signed_axes=True,
        base_advance=FOUR_AXIS_BASE,
        codepoint_start=0xE200,
        axis_tags=list(FOUR_AXIS_TAGS),
    )
    font = TTFont(path, recalcTimestamp=False)
    ranges = (
        (400, 400, 900, "Weight"),
        (100, 100, 200, "Width"),
        (-20, 0, 0, "Slant"),
        (60, 60, 100, "Optical size"),
    )
    stat_axes = []
    for ordering, (axis, values) in enumerate(zip(font["fvar"].axes, ranges, strict=True)):
        minimum, default, maximum, name = values
        axis.minValue = minimum
        axis.defaultValue = default
        axis.maxValue = maximum
        axis.flags = 0
        axis.axisNameID = font["name"].addName(name)
        stat_axes.append({"tag": axis.axisTag, "name": axis.axisNameID, "ordering": ordering})
    buildStatTable(font, stat_axes)
    font.recalcTimestamp = False
    font.save(path)
    compress(path)


def source_width(value: float) -> float:
    return (SOURCE_BASE + SOURCE_DELTA * value) * SOURCE_FONT_SIZE / UPEM


def effective_opsz(value: float, mode: str) -> float:
    if mode == "none":
        return OPSZ_DEFAULT
    return min(OPSZ_MAX, max(OPSZ_MIN, source_width(value)))


def consumer_advance(value: float, mode: str) -> float:
    opsz = effective_opsz(value, mode)
    normalized = (opsz - OPSZ_DEFAULT) / (OPSZ_MAX - OPSZ_DEFAULT)
    return CONSUMER_BASE + CONSUMER_DELTA * normalized


def consumer_width(value: float, mode: str) -> float:
    size = source_width(value)
    return consumer_advance(value, mode) * size / UPEM


def common_css() -> str:
    case_rules = "".join(
        f"body:has(#case-{index}:checked) .source{{font-variation-settings:"
        f'"X000" {value}}}'
        for index, value in enumerate(CASES)
    )
    return f'''@font-face{{font-family:OpszSource;src:url("source.woff2") format("woff2")}}
@font-face{{font-family:OpszConsumer;src:url("consumer.woff2") format("woff2")}}
html,body{{margin:0}}
body{{font:14px system-ui}}
input{{position:fixed;left:-10000px}}
.source{{display:inline-block;width:max-content;white-space:pre;font-family:OpszSource;
  font-size:{SOURCE_FONT_SIZE}px;line-height:1;font-kerning:none}}
.bridge{{position:absolute;container-type:inline-size;height:1px}}
.sink{{display:inline-block;width:max-content;white-space:pre;font-family:OpszConsumer;
  font-size:100cqi;line-height:1;font-kerning:none}}
.mode-none .sink{{font-optical-sizing:none}}
.mode-auto .sink{{font-optical-sizing:auto}}
.mode-explicit .sink{{font-optical-sizing:none;
  font-variation-settings:"opsz" clamp({OPSZ_MIN},calc(100cqi / 1px),{OPSZ_MAX})}}
{case_rules}
'''


def controls() -> str:
    radios = "".join(
        f'<input id="case-{index}" name="case" type="radio"'
        f'{" checked" if index == 0 else ""}>'
        for index in range(len(CASES))
    )
    labels = "".join(
        f'<label for="case-{index}">x={value}</label>'
        for index, value in enumerate(CASES)
    )
    return radios + "<nav>" + labels + "</nav>"


def lane(
    index: int,
    mode: str,
    *,
    with_ids: bool = False,
    offset: float | None = None,
) -> str:
    anchor = f"--s{index}"
    source_id = ' id="source"' if with_ids else ""
    bridge_id = ' id="bridge"' if with_ids else ""
    sink_id = ' id="sink"' if with_ids else ""
    offset_style = "" if offset is None else f"--offset:{offset:.9g};"
    return (
        f'<span class="lane mode-{mode}">'
        f'<i class="source"{source_id} style="{offset_style}anchor-name:{anchor}">&#xE000;</i>'
        f'<i class="bridge"{bridge_id} style="position-anchor:{anchor};'
        f'width:anchor-size({anchor} width)">'
        f'<i class="sink"{sink_id}>&#xE100;</i></i></span>'
    )


def probe_page() -> str:
    mode_rows = "".join(
        f'<section data-mode="{mode}"><h2>{mode}</h2>{lane(index, mode, with_ids=True)}</section>'
        for index, mode in enumerate(MODES)
    )
    flow_probe = '''<section id="flow-probe"><h2>normal-flow anchor-size</h2>
<i class="flow-source"></i><i class="flow-bridge"><i class="flow-value"></i></i></section>'''
    return f'''<!doctype html><meta charset="utf-8"><title>opsz container handoff</title>
<style>{common_css()}
section{{position:relative;height:90px;border-top:1px solid #ddd}}
section .bridge{{left:0;top:55px;position-anchor:auto}}
section .source{{position:absolute;left:0;top:28px}}
.flow-source{{display:inline-block;width:77px;height:1px;anchor-name:--flow}}
.flow-bridge{{display:inline-block;position:relative;position-anchor:--flow;width:anchor-size(--flow width);
  height:1px;container-type:inline-size}}
.flow-value{{display:block;width:100cqi;height:1px}}
</style>{controls()}{mode_rows}{flow_probe}'''


def scale_page(size: int, mode: str) -> str:
    anchors = "".join(
        f'.scale .source:nth-of-type({index * 2 + 1}){{anchor-name:--s{index}}}'
        for index in range(size)
    )
    # Inline anchor names keep this deliberately simple; every lane is an
    # independent dependency chain and all boxes stay outside visible layout.
    markup = "".join(
        lane(index, mode, offset=0.19 * index / max(1, size - 1))
        for index in range(size)
    )
    scale_cases = (0.0, 0.2, 0.55, 0.8)
    scale_case_rules = "".join(
        f'body:has(#case-{case_index}:checked) .scale .source{{'
        f'font-variation-settings:"X000" calc({value} + var(--offset))}}'
        for case_index, value in enumerate(scale_cases)
    )
    return f'''<!doctype html><meta charset="utf-8"><title>opsz handoff {mode} {size}</title>
<style>{common_css()}
.scale{{position:fixed;left:0;top:-20000px}}
.lane{{position:relative;display:block;width:1px;height:1px}}
.lane .source{{position:absolute;left:0;top:0}}
.lane .bridge{{left:0;top:0}}
{scale_case_rules}
{anchors}
</style>{controls()}<main class="scale" data-size="{size}" data-mode="{mode}">{markup}</main>'''


def four_axis_expected(values: tuple[float, float, float, float]) -> dict[str, object]:
    widths = [source_width(value) for value in values]
    axes = (
        400 + (widths[0] - 60) * 12.5,
        100 + (widths[1] - 60) * 2.5,
        (widths[2] - 100) * 0.5,
        widths[3],
    )
    normalized = (
        (axes[0] - 400) / 500,
        (axes[1] - 100) / 100,
        axes[2] / 20,
        (axes[3] - 60) / 40,
    )
    advance = FOUR_AXIS_BASE + sum(
        weight * coordinate
        for weight, coordinate in zip(FOUR_AXIS_WEIGHTS, normalized, strict=True)
    )
    return {
        "values": values,
        "widths": widths,
        "axes": axes,
        "normalized": normalized,
        "advance": advance,
        "fontSize": widths[3],
        "sinkWidth": advance * widths[3] / UPEM,
    }


def four_axis_group(index: int, groups: int) -> str:
    nested = f'<i class="four-sink" data-group="{index}">&#xE200;</i>'
    offset = 0.19 * index / max(1, groups - 1)
    setter_classes = ("setter-wght", "setter-wdth", "setter-slnt", "setter-opsz")
    for slot, setter_class in reversed(tuple(enumerate(setter_classes))):
        anchor = f"--f{index}-{slot}"
        nested = (
            f'<i class="four-level"><i class="source four-source" '
            f'style="--x:clamp(0,calc(var(--x{slot}) + {offset:.9g}),1);'
            f'anchor-name:{anchor}">&#xE000;</i>'
            f'<i class="capture" style="position-anchor:{anchor};'
            f'width:anchor-size({anchor} width)"><i class="setter {setter_class}">'
            f'{nested}</i></i></i>'
        )
    return f'<span class="four-group">{nested}</span>'


def four_axis_page(groups: int) -> str:
    case_rules = "".join(
        "body:has(#four-case-" + str(case_index) + ":checked){" +
        ";".join(
            f"--x{slot}:{value}" for slot, value in enumerate(values)
        ) + "}"
        for case_index, values in enumerate(FOUR_AXIS_CASES)
    )
    radios = "".join(
        f'<input id="four-case-{index}" name="four-case" type="radio"'
        f'{" checked" if index == 0 else ""}>'
        for index in range(len(FOUR_AXIS_CASES))
    )
    markup = "".join(four_axis_group(index, groups) for index in range(groups))
    return f'''<!doctype html><meta charset="utf-8"><title>four inherited font-axis handoffs</title>
<style>{common_css()}
@font-face{{font-family:FourAxisConsumer;src:url("four-axis.woff2") format("woff2")}}
{case_rules}
.four-root{{position:fixed;left:0;top:-20000px}}
.four-group{{position:relative;display:block;width:1px;height:1px}}
.four-level{{position:relative;display:block;width:1px;height:1px}}
.four-source{{position:absolute;left:0;top:0;font-variation-settings:"X000" var(--x)}}
.capture{{position:absolute;left:0;top:0;container-type:inline-size;height:1px}}
.setter{{display:block;width:1px;height:1px}}
.setter-wght{{font-weight:calc(400 + (100cqi / 1px - 60) * 12.5)}}
.setter-wdth{{font-stretch:calc((100 + (100cqi / 1px - 60) * 2.5) * 1%)}}
.setter-slnt{{font-variation-settings:"slnt" calc((100cqi / 1px - 100) * .5)}}
.setter-opsz{{font-size:100cqi}}
.four-sink{{display:inline-block;width:max-content;white-space:pre;font-family:FourAxisConsumer;
  font-size:inherit;line-height:1;font-optical-sizing:auto;font-kerning:none}}
</style>{radios}<main class="four-root" data-groups="{groups}">{markup}</main>'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_direct_font_backend(
        np.asarray([[SOURCE_DELTA]], dtype=np.int16),
        OUT / "source.ttf",
        base_advance=SOURCE_BASE,
        codepoint_start=0xE000,
        axis_tags=["X000"],
    )
    build_consumer(OUT / "consumer.ttf")
    build_four_axis_consumer(OUT / "four-axis.ttf")
    (OUT / "index.html").write_text(probe_page())
    for size in SIZES:
        for mode in MODES:
            (OUT / f"n{size}-{mode}.html").write_text(scale_page(size, mode))
        (OUT / f"four-axis-n{size // 4}.html").write_text(four_axis_page(size // 4))

    reference = {
        "cases": [
            {
                "input": value,
                "sourceWidth": source_width(value),
                "modes": {
                    mode: {
                        "effectiveOpsz": effective_opsz(value, mode),
                        "consumerAdvance": consumer_advance(value, mode),
                        "consumerWidth": consumer_width(value, mode),
                    }
                    for mode in MODES
                },
            }
            for value in CASES
        ],
        "sizes": SIZES,
        "modes": MODES,
        "fourAxisCases": [four_axis_expected(values) for values in FOUR_AXIS_CASES],
        "constants": {
            "upem": UPEM,
            "sourceFontSize": SOURCE_FONT_SIZE,
            "sourceBase": SOURCE_BASE,
            "sourceDelta": SOURCE_DELTA,
            "opszMin": OPSZ_MIN,
            "opszDefault": OPSZ_DEFAULT,
            "opszMax": OPSZ_MAX,
            "consumerBase": CONSUMER_BASE,
            "consumerDelta": CONSUMER_DELTA,
        },
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")


if __name__ == "__main__":
    main()
