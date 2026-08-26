#!/usr/bin/env python3
"""Pack two signed 8-bit HVAR dot products into each CSS font metric."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-packed-metrics"
INPUT_WIDTH = 16
OUTPUTS = 4
SCALE_OUTPUTS = 1_024
RADIX = 256
DIGIT_BIAS = 128
PACKED_BASE = DIGIT_BIAS * (1 + RADIX)
UNITS_PER_EM = 1_000
FONT_SIZE = 64


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def rectangle():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    # Keep the right-side bearing inside hhea's signed 16-bit range even
    # though the packed advance itself intentionally uses almost all 16 bits.
    pen.lineTo((32_000, 0))
    pen.lineTo((32_000, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def make_data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0x5041434B)
    weights = rng.integers(-3, 4, size=(OUTPUTS, INPUT_WIDTH), dtype=np.int16)
    inputs = rng.choice(np.array([-1.0, 1.0]), size=INPUT_WIDTH)
    expected = weights.astype(np.float64) @ inputs
    assert np.max(np.abs(expected)) < DIGIT_BIAS
    return weights, inputs


def build_font(weights: np.ndarray, destination: Path) -> None:
    glyphs = [".notdef", "zero", "water"]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water"})
    shape = rectangle()
    fb.setupGlyf({name: shape for name in glyphs})
    fb.setupHorizontalMetrics({name: (PACKED_BASE, 0) for name in glyphs})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({
        "familyName": "CSS Packed Metrics",
        "styleName": "Regular",
        "uniqueFontIdentifier": "CSS-Packed-Metrics-Regular",
        "fullName": "CSS Packed Metrics Regular",
        "psName": "CSSPackedMetrics-Regular",
    })
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.font["OS/2"].xAvgCharWidth = 32_000
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    tags = [axis_tag(index) for index in range(INPUT_WIDTH)]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)

    packed_rows = np.stack((
        weights[0].astype(np.int32) + RADIX * weights[1].astype(np.int32),
        weights[2].astype(np.int32) + RADIX * weights[3].astype(np.int32),
    ))

    def encode(values: np.ndarray) -> list[int]:
        return [delta for value in values.tolist() for delta in (-value, value)]

    rows = [[0] * len(supports) for _ in glyphs]
    rows[1] = encode(packed_rows[0])
    rows[2] = encode(packed_rows[1])
    assert max(abs(value) for row in rows for value in row) <= 32_767
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(len(supports)), rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar
    font.recalcTimestamp = False
    font.save(destination)


def build_unpacked_font(weights: np.ndarray, source: Path, destination: Path) -> None:
    """Create a two-output control font with ordinary, unpacked HVAR rows."""
    font = TTFont(source, recalcTimestamp=False)
    for name in font.getGlyphOrder():
        font["hmtx"].metrics[name] = (2_000, 0)
    font["OS/2"].xAvgCharWidth = 2_000
    tags = [axis_tag(index) for index in range(INPUT_WIDTH)]
    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)

    def encode(values: np.ndarray) -> list[int]:
        return [delta for value in values.astype(np.int16).tolist()
                for delta in (-value, value)]

    glyphs = font.getGlyphOrder()
    rows = [[0] * len(supports) for _ in glyphs]
    rows[glyphs.index("zero")] = encode(weights[0])
    rows[glyphs.index("water")] = encode(weights[1])
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(len(supports)), rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar
    font.recalcTimestamp = False
    font.save(destination)


def build_html(inputs: np.ndarray) -> str:
    settings = ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(inputs))
    properties = "".join(
        f'@property --o{index}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for index in range(OUTPUTS)
    )
    return f'''<!doctype html><meta charset="utf-8"><title>Packed font metrics</title>
<style>
@font-face{{font-family:PackedMetrics;src:url("packed-metrics.ttf") format("truetype")}}
@property --p0{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --p1{{syntax:"<number>";inherits:true;initial-value:-99999}}
{properties}
.producer{{font-family:PackedMetrics;font-size:{FONT_SIZE}px;font-variation-settings:{settings};
--p0:round(nearest,calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE}),1);
--p1:round(nearest,calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE}),1);
--o0:calc(mod(var(--p0),{RADIX}) - {DIGIT_BIAS});
--o1:calc((var(--p0) - mod(var(--p0),{RADIX})) / {RADIX} - {DIGIT_BIAS});
--o2:calc(mod(var(--p1),{RADIX}) - {DIGIT_BIAS});
--o3:calc((var(--p1) - mod(var(--p1),{RADIX})) / {RADIX} - {DIGIT_BIAS})}}
#result{{font:14px monospace}}
</style><div class="producer"><output id="result">ready</output></div>
'''


def scale_settings(group: int) -> str:
    values = []
    for index in range(INPUT_WIDTH):
        sign = -1 if ((group * 0x9E3779B1 + index * 17) >> (index % 13)) & 1 else 1
        value = ("var(--flip)" if sign == 1 else "calc(-1 * var(--flip))") \
            if index == 0 else str(sign)
        values.append(f'"{axis_tag(index)}" {value}')
    return ",".join(values)


def scale_html(packed: bool) -> str:
    per_node = 4 if packed else 2
    nodes = SCALE_OUTPUTS // per_node
    font_name = "PackedMetrics" if packed else "UnpackedMetrics"
    font_file = "packed-metrics.ttf" if packed else "unpacked-metrics.ttf"
    properties = "".join(
        f'@property --o{index:04d}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for index in range(SCALE_OUTPUTS)
    )
    rules = []
    for group in range(nodes):
        first = group * per_node
        if packed:
            outputs = (
                f'--p0:round(nearest,calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE}),1);'
                f'--p1:round(nearest,calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE}),1);'
                f'--o{first:04d}:calc(mod(var(--p0),{RADIX}) - {DIGIT_BIAS});'
                f'--o{first + 1:04d}:calc((var(--p0) - mod(var(--p0),{RADIX})) / {RADIX} - {DIGIT_BIAS});'
                f'--o{first + 2:04d}:calc(mod(var(--p1),{RADIX}) - {DIGIT_BIAS});'
                f'--o{first + 3:04d}:calc((var(--p1) - mod(var(--p1),{RADIX})) / {RADIX} - {DIGIT_BIAS});'
            )
        else:
            outputs = (
                f'--o{first:04d}:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} - 2000);'
                f'--o{first + 1:04d}:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} - 2000);'
            )
        rules.append(
            f'.g{group:04d}{{font-variation-settings:{scale_settings(group)};{outputs}}}')
    child = '<output id="result">ready</output>'
    for group in reversed(range(nodes)):
        child = f'<i class="producer g{group:04d}">{child}</i>'
    return f'''<!doctype html><meta charset="utf-8"><title>{font_name} scale probe</title>
<style>
@font-face{{font-family:{font_name};src:url("{font_file}") format("truetype")}}
{properties}
.root{{--flip:1}}.producer{{display:contents;font-family:{font_name};font-size:{FONT_SIZE}px}}
{''.join(rules)}#result{{font:14px monospace}}
</style><div class="root" id="root">{child}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights, inputs = make_data()
    expected = weights.astype(np.float64) @ inputs
    build_font(weights, OUT / "packed-metrics.ttf")
    build_unpacked_font(weights, OUT / "packed-metrics.ttf", OUT / "unpacked-metrics.ttf")
    (OUT / "index.html").write_text(build_html(inputs))
    (OUT / "packed-scale.html").write_text(scale_html(True))
    (OUT / "unpacked-scale.html").write_text(scale_html(False))
    (OUT / "reference.json").write_text(json.dumps({
        "input_width": INPUT_WIDTH,
        "outputs": OUTPUTS,
        "radix": RADIX,
        "digit_bias": DIGIT_BIAS,
        "packed_base": PACKED_BASE,
        "units_per_em": UNITS_PER_EM,
        "font_size": FONT_SIZE,
        "inputs": inputs.tolist(),
        "weights": weights.tolist(),
        "expected": expected.tolist(),
    }, indent=2) + "\n")
    print({"expected": expected.tolist(),
           "font_bytes": (OUT / "packed-metrics.ttf").stat().st_size,
           "html_bytes": (OUT / "index.html").stat().st_size,
           "packed_scale_bytes": (OUT / "packed-scale.html").stat().st_size,
           "unpacked_scale_bytes": (OUT / "unpacked-scale.html").stat().st_size})


if __name__ == "__main__":
    main()
