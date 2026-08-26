#!/usr/bin/env python3
"""Build a row-selector-axis multimetric HVAR/MVAR proof."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "row-axis-multimetric"
UNITS_PER_EM = 1_000
FONT_SIZE = 512
BASE = 2_000
DEFAULT_CHANNELS = ("ex", "cap", "ch", "ic", "lh")
SCALABLE_CHANNELS = ("cap", "ch", "ic", "lh")


@dataclass(frozen=True)
class Fixture:
    name: str
    inputs: int
    groups: int
    include_outlines: bool
    shifted_axes: bool
    trigger_outline: bool = False
    channels: tuple[str, ...] = DEFAULT_CHANNELS


FIXTURES = (
    Fixture("small", 8, 16, True, False),
    # The full 64x64 scale keeps MVAR/HVAR only. Adding the 8,192 signed gvar
    # cross-regions exceeds gvar's 16-bit per-glyph tuple-header offset.
    Fixture("scale", 64, 64, False, False),
    Fixture("trigger", 64, 64, False, False, True),
    Fixture(
        "outputs768-i64", 64, 192, False, False,
        channels=SCALABLE_CHANNELS,
    ),
    Fixture(
        "outputs768-i16shift", 16, 192, False, True,
        channels=SCALABLE_CHANNELS,
    ),
    Fixture(
        "outputs768-i32shift", 32, 192, False, True,
        channels=SCALABLE_CHANNELS,
    ),
    Fixture(
        "outputs768-i64shift", 64, 192, False, True,
        channels=SCALABLE_CHANNELS,
    ),
    Fixture(
        "outputs768-i128", 128, 192, False, True,
        channels=SCALABLE_CHANNELS,
    ),
    Fixture(
        "outputs768-i256", 256, 192, False, True,
        channels=SCALABLE_CHANNELS,
    ),
)


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def fixture_data(fixture: Fixture) -> tuple[np.ndarray, np.ndarray]:
    seed = 0x524F5700 + fixture.inputs * 257 + fixture.groups
    rng = np.random.default_rng(seed)
    weights = rng.integers(
        -12, 13,
        size=(fixture.groups, len(fixture.channels), fixture.inputs),
        dtype=np.int16,
    )
    inputs = rng.integers(-4, 5, size=fixture.inputs).astype(np.float64) / 4
    return weights, inputs


def row_support(group: int, groups: int) -> tuple[float, float, float]:
    peak = (group + 1) / groups
    start = 0 if group == 0 else (group + 0.5) / groups
    end = 1 if group == groups - 1 else (group + 1.5) / groups
    return start, peak, end


def build_font(fixture: Fixture, weights: np.ndarray, path: Path) -> None:
    glyphs = [".notdef", "zero", "water", "x", "H"]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water", 0x78: "x", 0x48: "H"})
    fb.setupGlyf({
        ".notdef": rectangle(1, 1),
        "zero": rectangle(1, 1),
        "water": rectangle(1, 1),
        "x": rectangle(1, BASE),
        "H": rectangle(1, BASE),
    })
    fb.setupHorizontalMetrics({
        ".notdef": (500, 0), "zero": (BASE, 0), "water": (BASE, 0),
        "x": (500, 0), "H": (500, 0),
    })
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupNameTable({
        "familyName": f"CSS Row Axis {fixture.name}",
        "styleName": "Regular",
        "uniqueFontIdentifier": f"CSS-Row-Axis-{fixture.name}-Regular",
        "fullName": f"CSS Row Axis {fixture.name} Regular",
        "psName": f"CSSRowAxis{fixture.name.title()}-Regular",
    })
    fb.setupOS2(
        version=4, sTypoAscender=BASE, sTypoDescender=0, sTypoLineGap=0,
        usWinAscent=BASE, usWinDescent=0, sxHeight=BASE, sCapHeight=BASE,
        fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(path)

    font = TTFont(path, recalcTimestamp=False)
    # The large fixture reserves one input for native CSS arithmetic. This
    # leaves 64*63=4032 outline tuples, just under gvar's 4095-tuple limit.
    font_input_count = fixture.inputs - 1 if fixture.shifted_axes else fixture.inputs
    input_tags = [axis_tag(index) for index in range(font_input_count)]
    all_tags = [*input_tags, "ROW "]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(all_tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = (0 if fixture.shifted_axes else -1) if tag != "ROW " else 0
        axis.defaultValue = 0
        axis.maxValue = 1 if tag != "ROW " else fixture.groups
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag.strip())
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = []
    encoded = [[] for _ in fixture.channels]
    for group in range(fixture.groups):
        row_region = row_support(group, fixture.groups)
        for input_index, tag in enumerate(input_tags):
            if fixture.shifted_axes:
                supports.append({tag: (0, 1, 1), "ROW ": row_region})
            else:
                supports.extend((
                    {tag: (-1, -1, 0), "ROW ": row_region},
                    {tag: (0, 1, 1), "ROW ": row_region},
                ))
            for channel in range(len(fixture.channels)):
                value = int(weights[group, channel, input_index])
                if fixture.shifted_axes:
                    encoded[channel].append(2 * value)
                else:
                    encoded[channel].extend((-value, value))
    regions = buildVarRegionList(supports, all_tags)

    encoded_by_channel = dict(zip(fixture.channels, encoded, strict=True))
    hvar_rows = [[0] * len(supports) for _ in glyphs]
    if "ch" in encoded_by_channel:
        hvar_rows[1] = encoded_by_channel["ch"]
    if "ic" in encoded_by_channel:
        hvar_rows[2] = encoded_by_channel["ic"]
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(len(supports)), hvar_rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    mvar_channels = [
        channel for channel in ("ex", "cap", "lh")
        if channel in encoded_by_channel
    ]
    mvar_data = buildVarData(
        range(len(supports)),
        [encoded_by_channel[channel] for channel in mvar_channels],
        optimize=True,
    )
    mvar = newTable("MVAR")
    mvar.table = otTables.MVAR()
    mvar.table.Version = 0x00010000
    mvar.table.Reserved = 0
    mvar.table.VarStore = buildVarStore(regions, [mvar_data])
    mvar.table.ValueRecordSize = 8
    mvar.table.ValueRecordCount = 3
    records = []
    mvar_tags = {"ex": "xhgt", "cap": "cpht", "lh": "hasc"}
    for index, channel in enumerate(mvar_channels):
        record = otTables.MetricsValueRecord()
        record.ValueTag = mvar_tags[channel]
        record.VarIdx = index
        records.append(record)
    mvar.table.ValueRecord = sorted(records, key=lambda record: record.ValueTag)
    font["MVAR"] = mvar

    if fixture.include_outlines:
        def tuple_for(support: dict[str, tuple[float, float, float]], delta: int):
            coords = [(0, 0), (0, 0), (0, delta), (0, delta)] + [(0, 0)] * 4
            return TupleVariation(support, coords)

        gvar = newTable("gvar")
        gvar.version = 1
        gvar.reserved = 0
        gvar.variations = {glyph: [] for glyph in glyphs}
        for support, ex_delta, cap_delta in zip(
            supports,
            encoded_by_channel["ex"],
            encoded_by_channel["cap"],
            strict=True,
        ):
            gvar.variations["x"].append(tuple_for(support, ex_delta))
            gvar.variations["H"].append(tuple_for(support, cap_delta))
        font["gvar"] = gvar
    elif fixture.trigger_outline:
        # Does any nonzero gvar entry make Chrome consult MVAR xhgt? Keep the
        # trigger horizontal so it cannot itself change the x-height.
        trigger_coords = [(0, 0), (1, 0), (1, 0), (0, 0)] + [(0, 0)] * 4
        gvar = newTable("gvar")
        gvar.version = 1
        gvar.reserved = 0
        gvar.variations = {glyph: [] for glyph in glyphs}
        gvar.variations["x"] = [
            TupleVariation({input_tags[0]: (0, 1, 1)}, trigger_coords)]
        font["gvar"] = gvar

    font.recalcTimestamp = False
    font.save(path)


def signed_term(value: int, suffix: str = "") -> str:
    operator = "+" if value >= 0 else "-"
    return f" {operator} {abs(value)}{suffix}"


def html(
    fixture: Fixture,
    inputs: np.ndarray,
    weights: np.ndarray,
    font_filename: str,
) -> str:
    font_input_count = fixture.inputs - 1 if fixture.shifted_axes else fixture.inputs
    input_settings = ",".join(
        f'"{axis_tag(index)}" '
        + (f'calc((var(--x{index:03d}) + 1) / 2)' if fixture.shifted_axes
           else f'var(--x{index:03d})')
        for index in range(font_input_count))
    root_values = ";".join(f"--x{index:03d}:{value:g}" for index, value in enumerate(inputs))
    properties = []
    rules = []
    child = '<div id="result">ready</div>'
    unit_by_channel = {
        "ex": "1ex", "cap": "1cap", "ch": "1ch", "ic": "1ic", "lh": "1lh"
    }
    for group in range(fixture.groups):
        outputs = [
            group * len(fixture.channels) + channel
            for channel in range(len(fixture.channels))
        ]
        for output in outputs:
            properties.append(
                f'@property --o{output:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}')
        expressions = []
        for channel, channel_name in enumerate(fixture.channels):
            unit = unit_by_channel[channel_name]
            extra = ""
            if fixture.shifted_axes:
                correction = -int(weights[group, channel, :font_input_count].sum())
                final_weight = int(weights[group, channel, -1])
                extra = signed_term(correction) + signed_term(
                    final_weight, f" * var(--x{fixture.inputs - 1:03d})")
            expressions.append(
                f'--o{outputs[channel]:03d}:calc({unit} / 1px * {UNITS_PER_EM} / '
                f'{FONT_SIZE} - {BASE}{extra})')
        rules.append(
            f'.group-{group:03d}{{font-variation-settings:{input_settings},"ROW " {group + 1};'
            + ";".join(expressions) + "}")
    for group in reversed(range(fixture.groups)):
        child = f'<div class="group group-{group:03d}">{child}</div>'
    return f'''<!doctype html><meta charset="utf-8"><title>ROW-axis multimetric {fixture.name}</title>
<style>@font-face{{font-family:RowAxis;src:url("{font_filename}")}}
{''.join(properties)}
.root{{{root_values};font-family:RowAxis;font-size:{FONT_SIZE}px;line-height:normal}}
{''.join(rules)}
#result{{font:14px monospace}}
</style><div class="root">{child}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    selected = {
        name.strip()
        for name in os.environ.get(
            "ROW_AXIS_FIXTURES", ",".join(fixture.name for fixture in FIXTURES)
        ).split(",")
        if name.strip()
    }
    fixtures = [fixture for fixture in FIXTURES if fixture.name in selected]
    unknown = selected - {fixture.name for fixture in fixtures}
    if unknown:
        raise ValueError(f"unknown ROW_AXIS_FIXTURES: {sorted(unknown)}")
    reuse_ttf = os.environ.get("ROW_AXIS_REUSE_TTF") == "1"
    formats = {
        name.strip()
        for name in os.environ.get("ROW_AXIS_FORMATS", "ttf").split(",")
        if name.strip()
    }
    unknown_formats = formats - {"ttf", "woff", "woff2"}
    if not formats or unknown_formats:
        raise ValueError(f"unknown ROW_AXIS_FORMATS: {sorted(unknown_formats)}")
    for fixture in fixtures:
        weights, inputs = fixture_data(fixture)
        expected = np.einsum("gci,i->gc", weights.astype(np.float64), inputs).reshape(-1)
        ttf_path = OUT / f"{fixture.name}.ttf"
        woff_path = OUT / f"{fixture.name}.woff"
        woff2_path = OUT / f"{fixture.name}.woff2"
        if not reuse_ttf or not ttf_path.exists():
            build_font(fixture, weights, ttf_path)
        if "woff2" in formats and (not reuse_ttf or not woff2_path.exists()):
            compressed_font = TTFont(ttf_path, recalcTimestamp=False)
            compressed_font.flavor = "woff2"
            compressed_font.save(woff2_path)
        if "woff" in formats and (not reuse_ttf or not woff_path.exists()):
            compressed_font = TTFont(ttf_path, recalcTimestamp=False)
            compressed_font.flavor = "woff"
            compressed_font.save(woff_path)
        if "ttf" in formats:
            (OUT / f"{fixture.name}.html").write_text(
                html(fixture, inputs, weights, ttf_path.name)
            )
        if "woff2" in formats:
            (OUT / f"{fixture.name}-woff2.html").write_text(
                html(fixture, inputs, weights, woff2_path.name)
            )
        if "woff" in formats:
            (OUT / f"{fixture.name}-woff.html").write_text(
                html(fixture, inputs, weights, woff_path.name)
            )
        (OUT / f"{fixture.name}.json").write_text(json.dumps({
            "name": fixture.name,
            "inputs_count": fixture.inputs,
            "groups": fixture.groups,
            "channels": list(fixture.channels),
            "inputs": inputs.tolist(),
            "weights": weights.tolist(),
            "expected": expected.tolist(),
        }, indent=2) + "\n")
        sizes = {
            "fixture": fixture.name,
            "outputs": len(expected),
            "sfnt_bytes": ttf_path.stat().st_size,
        }
        if "woff" in formats:
            sizes["woff_bytes"] = woff_path.stat().st_size
        if "woff2" in formats:
            sizes["woff2_bytes"] = woff2_path.stat().st_size
        print(sizes)
        if "ttf" not in formats:
            ttf_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
