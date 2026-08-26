#!/usr/bin/env python3
"""Probe whether Chromium executes GETVARIATION TrueType glyph bytecode."""

from __future__ import annotations

import json
from array import array
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables._f_v_a_r import Axis


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "truetype-bytecode"
UPM = 64
CODEPOINT = 0xE000
AXIS_TAG = "TEST"


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def axis() -> Axis:
    value = Axis()
    value.axisTag = AXIS_TAG
    value.minValue = -1
    value.defaultValue = 0
    value.maxValue = 1
    value.flags = 0
    value.axisNameID = 256
    return value


def computed_width_program() -> ttProgram.Program:
    # At UPM=font-size=64, one font unit is one CSS pixel. GETVARIATION
    # returns -1..1 as 2.14 fixed point (-16384..16384). DIV by 256
    # converts it to F26.6 (-64..64); multiplying by 8px and adding 16px
    # produces a target x coordinate of 8..24px. SCFS moves both right-edge
    # outline points to that x coordinate.
    assembly = ["SVTCA[1]"]
    for point in (1, 2):
        assembly.extend(
            [
                f"PUSHB[ ] {point}",
                "GETVARIATION[ ]",
                "PUSHW[ ] 16384",
                "DIV[ ]",
                "PUSHW[ ] 512",
                "MUL[ ]",
                "PUSHW[ ] 1024",
                "ADD[ ]",
                "SCFS[ ]",
            ]
        )
    program = ttProgram.Program()
    program.fromAssembly(assembly)
    return program


def constant_width_program() -> ttProgram.Program:
    # A control case that does not depend on variable-font support. If this
    # does not render 24px wide, Chromium is not running glyph bytecode here.
    program = ttProgram.Program()
    program.fromAssembly(
        [
            "SVTCA[1]",
            "PUSHB[ ] 1",
            "PUSHW[ ] 1536",
            "SCFS[ ]",
            "PUSHB[ ] 2",
            "PUSHW[ ] 1536",
            "SCFS[ ]",
        ]
    )
    return program


def add_fvar_and_gvar(font: TTFont) -> None:
    fvar = newTable("fvar")
    fvar.axes = [axis()]
    fvar.instances = []
    font["fvar"] = fvar
    buildStatTable(font, [{"tag": AXIS_TAG, "name": "Test", "ordering": 0}])

    # A zero delta is sufficient to make this a structurally ordinary glyf
    # variable font while ensuring only the glyph program can alter width.
    support = {AXIS_TAG: (0, 1, 1)}
    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {
        ".notdef": [],
        "plain": [TupleVariation(support, [(0, 0)] * 8)],
        "constant": [TupleVariation(support, [(0, 0)] * 8)],
        "computed": [TupleVariation(support, [(0, 0)] * 8)],
    }
    font["gvar"] = gvar


def build_font(path: Path) -> None:
    glyph_order = [".notdef", "plain", "constant", "computed"]
    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(
        {CODEPOINT: "plain", CODEPOINT + 1: "constant", CODEPOINT + 2: "computed"}
    )
    builder.setupGlyf({name: rectangle(16, 32) for name in glyph_order})
    builder.setupHorizontalMetrics({name: (32, 0) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=40, descent=-8)
    builder.setupNameTable(
        {
            "familyName": "TrueType Bytecode Probe",
            "styleName": "Regular",
            "uniqueFontIdentifier": "TrueTypeBytecodeProbe-Regular",
            "fullName": "TrueType Bytecode Probe Regular",
            "psName": "TrueTypeBytecodeProbe-Regular",
        }
    )
    builder.setupOS2(
        version=4,
        sTypoAscender=40,
        sTypoDescender=-8,
        usWinAscent=40,
        usWinDescent=8,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(
        unitsPerEm=UPM,
        created=2_082_844_800,
        modified=2_082_844_800,
    )

    builder.font["glyf"]["constant"].program = constant_width_program()
    builder.font["glyf"]["computed"].program = computed_width_program()
    maxp = builder.font["maxp"]
    maxp.maxSizeOfInstructions = max(
        len(constant_width_program().getBytecode()),
        len(computed_width_program().getBytecode()),
    )
    maxp.maxStackElements = 8
    maxp.maxZones = 2
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 1
    cvt = newTable("cvt ")
    cvt.values = array("h", [0])
    builder.font["cvt "] = cvt
    fpgm = newTable("fpgm")
    fpgm.program = ttProgram.Program()
    fpgm.program.fromAssembly(
        [
            # Required fallback for rasterizers that do not implement the
            # variable-font opcode. Supporting engines ignore this IDEF.
            "PUSHB[ ] 145",
            "IDEF[ ]",
            "NPUSHW[ ] 1 0",
            "ENDF[ ]",
        ]
    )
    builder.font["fpgm"] = fpgm
    prep = newTable("prep")
    prep.program = ttProgram.Program()
    prep.program.fromAssembly(["SVTCA[1]"])
    builder.font["prep"] = prep
    gasp = newTable("gasp")
    # Request grid fitting at every size; without a gasp table a platform
    # rasterizer is free to skip the glyph programs entirely.
    gasp.gaspRange = {65_535: 0x000F}
    builder.font["gasp"] = gasp
    builder.save(path)

    font = TTFont(path, recalcTimestamp=False)
    add_fvar_and_gvar(font)
    font.recalcTimestamp = False
    font.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font_path = OUT / "probe.ttf"
    build_font(font_path)
    cases = []
    for size in (16, 32, 64):
        for value in (-1, 0, 1):
            cases.append((size, value))
    nodes = "".join(
        f'<div class="case" data-size="{size}" data-axis="{value}" '
        f'style="font-variation-settings:\'{AXIS_TAG}\' {value}">'
        f'<svg class="plain" viewBox="0 0 32 40"><text x="0" y="36" '
        f'font-size="{size}">&#x{CODEPOINT:X};</text></svg>'
        f'<svg class="constant" viewBox="0 0 32 40"><text x="0" y="36" '
        f'font-size="{size}">&#x{CODEPOINT + 1:X};</text></svg>'
        f'<svg class="computed" viewBox="0 0 32 40"><text x="0" y="36" '
        f'font-size="{size}">&#x{CODEPOINT + 2:X};</text></svg></div>'
        for size, value in cases
    )
    html = f'''<!doctype html><meta charset="utf-8"><title>TrueType bytecode probe</title>
<link rel="icon" href="data:,">
<style>
@font-face{{font-family:TTBytecodeProbe;src:url("probe.ttf") format("truetype")}}
html,body{{margin:0;background:white}}
.case{{font-family:TTBytecodeProbe;color:black;white-space:nowrap;height:40px;text-rendering:optimizeLegibility}}
.case svg{{display:inline-block;width:32px;height:40px;overflow:hidden}}
.case text{{font-family:TTBytecodeProbe;fill:black}}
</style>
{nodes}
'''
    (OUT / "index.html").write_text(html)
    reference = {
        "upm": UPM,
        "cases": [{"size": size, "axis": value} for size, value in cases],
        "plainFontUnits": 16,
        "constantPixels": 24,
        "computedPixelsAt64": {-1: 8, 0: 16, 1: 24},
        "fontBytes": font_path.stat().st_size,
        "htmlBytes": len(html.encode()),
        "runtimeJavascript": False,
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(reference)


if __name__ == "__main__":
    main()
