#!/usr/bin/env python3
"""Build 64x64 font-metric and SVG-filter matrix-vector experiments."""

from __future__ import annotations

import json
import hashlib
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.varLib import build as build_variable_font
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "matrix-backends"
SIZE = 64
UNITS_PER_EM = 1_000
FONT_SIZE = 32
FONT_BASE_ADVANCE = 8_000
SVG_WEIGHT_MAX = 15
SVG_DIVISOR = 16


def empty_glyph():
    # WOFF2's transformed glyf stream is rejected by Chromium when every glyph
    # in the font is contourless. A one-unit square keeps the font renderable;
    # only the horizontal advances carry matrix results.
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def output_glyph(index: int) -> str:
    return f"y{index:03d}"


def deterministic_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0x47505432)
    font_weights = rng.integers(-32, 33, size=(SIZE, SIZE), dtype=np.int16)
    font_input = rng.integers(0, 5, size=SIZE).astype(np.float64) / 4
    svg_weights = rng.integers(0, SVG_WEIGHT_MAX + 1, size=(SIZE, SIZE), dtype=np.uint8)
    # Keeping the activation below one half prevents the reduction from clipping.
    svg_input_levels = rng.integers(0, 8, size=SIZE, dtype=np.uint8)
    return font_weights, font_input, svg_weights, svg_input_levels


def build_master(
    path: Path,
    widths: np.ndarray,
    style_name: str,
    *,
    codepoint_start: int = 0xE000,
) -> None:
    size = len(widths)
    glyph_order = [".notdef", *[output_glyph(index) for index in range(size)]]
    font = FontBuilder(UNITS_PER_EM, isTTF=True)
    font.setupGlyphOrder(glyph_order)
    font.setupCharacterMap(
        {codepoint_start + index: output_glyph(index) for index in range(size)}
    )
    font.setupGlyf({name: empty_glyph() for name in glyph_order})
    metrics = {".notdef": (0, 0)}
    metrics.update(
        {
            output_glyph(index): (int(widths[index]), 0)
            for index in range(size)
        }
    )
    font.setupHorizontalMetrics(metrics)
    font.setupHorizontalHeader(ascent=UNITS_PER_EM, descent=0)
    font.setupNameTable(
        {
            "familyName": "CSS Matrix Variable",
            "styleName": style_name,
            "uniqueFontIdentifier": f"css-matrix-variable-{style_name}",
            "fullName": f"CSS Matrix Variable {style_name}",
            "psName": f"CSSMatrixVariable-{style_name}",
        }
    )
    font.setupOS2(
        sTypoAscender=UNITS_PER_EM,
        sTypoDescender=0,
        usWinAscent=UNITS_PER_EM,
        usWinDescent=0,
    )
    font.setupPost()
    font.setupMaxp()
    font.setupHead(created=2_082_844_800, modified=2_082_844_800)
    font.font.recalcTimestamp = False
    font.save(path)


def add_source(
    designspace: DesignSpaceDocument,
    path: Path,
    name: str,
    location: dict[str, float],
    *,
    default: bool = False,
) -> None:
    source = SourceDescriptor()
    source.path = str(path)
    source.name = name
    source.familyName = "CSS Matrix Variable"
    source.styleName = name
    source.location = location
    if default:
        source.copyInfo = True
        source.copyLib = True
        source.copyGroups = True
        source.copyFeatures = True
    designspace.addSource(source)


def build_font_backend(weights: np.ndarray, destination: Path) -> None:
    if weights.ndim != 2:
        raise ValueError("variable-font backend requires a two-dimensional matrix")
    output_size, input_size = weights.shape
    with tempfile.TemporaryDirectory(prefix="css-matrix-font-") as temporary:
        directory = Path(temporary)
        designspace = DesignSpaceDocument()
        for index in range(input_size):
            axis = AxisDescriptor()
            axis.name = axis_tag(index)
            axis.tag = axis_tag(index)
            axis.minimum = 0
            axis.default = 0
            axis.maximum = 1
            designspace.addAxis(axis)

        base_widths = np.full(output_size, FONT_BASE_ADVANCE, dtype=np.int32)
        default_path = directory / "default.ttf"
        build_master(default_path, base_widths, "Regular")
        add_source(designspace, default_path, "Regular", {}, default=True)

        for column in range(input_size):
            master_path = directory / f"axis-{column:03d}.ttf"
            build_master(
                master_path,
                base_widths + weights[:, column],
                f"Axis{column:03d}",
            )
            add_source(
                designspace,
                master_path,
                f"Axis{column:03d}",
                {axis_tag(column): 1},
            )

        variable_font, _model, _masters = build_variable_font(
            designspace, optimize=True
        )
        variable_font.recalcTimestamp = False
        variable_font.save(destination)
        compressed_font = TTFont(destination, recalcTimestamp=False)
        compressed_font.flavor = "woff2"
        compressed_font.save(destination.with_suffix(".woff2"))


def build_direct_font_backend(
    weights: np.ndarray,
    destination: Path,
    *,
    signed_axes: bool = False,
    base_advance: int | np.ndarray = FONT_BASE_ADVANCE,
    axis_offset: int = 0,
    codepoint_start: int = 0xE000,
    axis_tags: list[str] | None = None,
    allow_out_of_range_result: bool = False,
) -> None:
    """Build fvar/HVAR tables directly, without one master font per axis."""
    if weights.ndim != 2:
        raise ValueError("variable-font backend requires a two-dimensional matrix")
    output_size, input_size = weights.shape
    if input_size > 256:
        raise ValueError("the tested browser path accepts at most 256 axes per font")
    if axis_tags is not None:
        if len(axis_tags) != input_size:
            raise ValueError("axis_tags must contain one tag per input column")
        if any(len(tag) != 4 for tag in axis_tags):
            raise ValueError("every OpenType axis tag must contain four characters")
    if np.any(weights < -32768) or np.any(weights > 32767):
        raise ValueError("direct HVAR weights must fit in signed 16-bit deltas")
    maximum_deltas = np.sum(np.abs(weights.astype(np.int64)), axis=1)
    if np.isscalar(base_advance):
        base_widths = np.full(output_size, int(base_advance), dtype=np.int32)
    else:
        base_widths = np.asarray(base_advance, dtype=np.int32)
        if base_widths.shape != (output_size,):
            raise ValueError("base advances must contain one value per output row")
    if np.any(base_widths < maximum_deltas):
        raise ValueError("base advance must cover the maximum negative dot product")
    if not allow_out_of_range_result and np.any(base_widths + maximum_deltas > 65535):
        raise ValueError("base advance plus maximum dot product must fit uint16")

    build_master(
        destination,
        base_widths,
        "Regular",
        codepoint_start=codepoint_start,
    )
    font = TTFont(destination, recalcTimestamp=False)

    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    resolved_axis_tags = []
    for index in range(input_size):
        tag = axis_tags[index] if axis_tags is not None else axis_tag(axis_offset + index)
        resolved_axis_tags.append(tag)
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1 if signed_axes else 0
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    if signed_axes:
        supports = []
        for tag in resolved_axis_tags:
            supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
        weight_rows = []
        for row in weights.astype(np.int16).tolist():
            weight_rows.append(
                [delta for weight in row for delta in (-weight, weight)]
            )
    else:
        supports = [{tag: (0, 1, 1)} for tag in resolved_axis_tags]
        weight_rows = weights.astype(np.int16).tolist()
    region_list = buildVarRegionList(supports, resolved_axis_tags)
    items = [[0] * len(supports), *weight_rows]
    var_data = buildVarData(range(len(supports)), items, optimize=True)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [var_data])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    # TrueType variable fonts require gvar structurally even when all useful
    # variation data lives in HVAR. No outline or phantom-point deltas are needed.
    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in font.getGlyphOrder()}
    font["gvar"] = gvar

    font.recalcTimestamp = False
    font.save(destination)
    compressed_font = TTFont(destination, recalcTimestamp=False)
    compressed_font.flavor = "woff2"
    compressed_font.save(destination.with_suffix(".woff2"))


def variable_font_html(font_input: np.ndarray, expected: np.ndarray) -> str:
    size = len(font_input)
    if len(expected) != size:
        raise ValueError("input and expected output must have equal lengths")
    settings = ",".join(
        f'"{axis_tag(index)}" {value:g}'
        for index, value in enumerate(font_input)
    )
    registrations = "\n".join(
        f'@property --vf-y-{index:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(size)
    )
    metric_rules = "\n".join(
        f'.metric-{index:03d}'
        f'{{anchor-name:--metric-{index:03d}}}'
        f'.metric-{index:03d}::before{{content:"\\{0xE000 + index:x}"}}'
        for index in range(size)
    )
    probe_rules = "\n".join(
        f'.probe-{index:03d}'
        f'{{position-anchor:--metric-{index:03d};'
        f'container:y{index:03d}/inline-size;'
        f'width:anchor-size(--metric-{index:03d} width)}}'
        for index in range(size)
    )
    query_rules = []
    for index in range(size):
        target = f".probe-{index + 1:03d}" if index + 1 < size else ".vf-result"
        query_rules.append(
            f'@container y{index:03d} (width > 0px){{{target}'
            f'{{--vf-y-{index:03d}:calc('
            f'100cqi / 1px * {UNITS_PER_EM} / {FONT_SIZE} '
            f'- {FONT_BASE_ADVANCE})}}}}'
        )
    chain = '<div class="vf-result" id="vf-result"></div>'
    for index in reversed(range(size)):
        chain = (
            f'<i class="metric metric-{index:03d}" aria-hidden="true"></i>'
            f'<div class="probe probe-{index:03d}">{chain}</div>'
        )
    expected_text = ", ".join(f"{value:g}" for value in expected[:8])
    expected_data = ",".join(f"{value:g}" for value in expected)
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Variable-font {size}×{size} matvec</title>
  <style>
    @font-face{{font-family:MatrixVF;src:url("variable-matvec.woff2?v=4") format("woff2")}}
    {registrations}
    html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
    body{{margin:2rem;max-width:52rem}}
    h1{{font:600 1.25rem system-ui,sans-serif}}
    .metrics{{position:relative;min-height:1px}}
    .metric{{position:absolute;display:inline-block;width:max-content;height:1px;
      overflow:hidden;white-space:pre;font-family:MatrixVF;font-size:{FONT_SIZE}px;
      font-variation-settings:{settings};font-kerning:none}}
    .probe{{position:absolute;inset:0 auto auto 0;height:1px}}
    {metric_rules}
    {probe_rules}
    {''.join(query_rules)}
    .status{{padding:1rem;border:1px solid #aaa}}
  </style>
</head>
<body>
  <h1>Variable-font {size}×{size} matrix–vector multiplication</h1>
  <p class="status" data-expected="{expected_data}">No JavaScript. Expected first outputs: {expected_text}</p>
  <div class="metrics">{chain}</div>
</body>
</html>
'''


def build_svg_assets(
    weights: np.ndarray, input_levels: np.ndarray
) -> tuple[str, np.ndarray]:
    # Values 0..15 map exactly to 8-bit grayscale multiples of 17.
    # Raster columns are output neurons and rows are input features because the
    # convolution sums vertically. Transpose the ordinary [output, input]
    # matrix into that layout.
    weight_pixels = (weights.T.astype(np.uint16) * 17).astype(np.uint8)
    Image.fromarray(weight_pixels, mode="L").convert("RGBA").save(
        OUT / "svg-weights.png", optimize=True
    )
    input_pixels = input_levels.astype(np.uint16) * 17
    normalized_input = input_levels.astype(np.float64) / SVG_WEIGHT_MAX
    expected = weights.astype(np.float64) @ normalized_input
    reference_pixels = np.rint(
        np.clip(expected / (SVG_WEIGHT_MAX * SVG_DIVISOR), 0, 1) * 255
    ).astype(np.uint8)
    Image.fromarray(reference_pixels.reshape(1, SIZE), mode="L").convert("RGBA").save(
        OUT / "svg-reference.png", optimize=True
    )

    rows = "".join(
        f'<rect x="0" y="{index}" width="64" height="1" '
        f'fill="rgb({value} {value} {value})"/>'
        for index, value in enumerate(input_pixels)
    )
    kernel = " ".join("1" for _ in range(SIZE))
    stages = "".join(
        f'<use href="#{stage}" transform="translate(0 {offset + copy})"/>'
        for stage, offset in (
            ("product-row", 0),
            ("actual-row", 16),
            ("reference-row", 32),
            ("difference-row", 48),
        )
        for copy in range(16)
    )
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SVG-filter 64×64 matvec</title>
  <style>
    html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
    body{{margin:2rem;max-width:70rem}}
    h1{{font:600 1.25rem system-ui,sans-serif}}
    .svg-stage{{width:128px;height:64px;margin:.75rem 0;border:1px solid #aaa;
      overflow:hidden}}
    svg{{display:block;image-rendering:pixelated}}
  </style>
</head>
<body>
  <h1>SVG-filter 64×64 matrix–vector multiplication</h1>
  <p>No JavaScript. The amplified difference strip should be black.</p>
  <div class="svg-stage">
  <svg id="svg-output" width="128" height="64" viewBox="0 63 64 64"
       preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <clipPath id="row-63"><rect x="0" y="63" width="64" height="1"/></clipPath>
      <filter id="product" x="0" y="0" width="64" height="64"
              filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
              color-interpolation-filters="sRGB">
        <feImage href="svg-weights.png" x="0" y="0" width="64" height="64"
                 preserveAspectRatio="none" result="weights"/>
        <feComposite in="SourceGraphic" in2="weights" operator="arithmetic"
                     k1="1" k2="0" k3="0" k4="0"/>
      </filter>
      <filter id="matvec" x="0" y="0" width="64" height="64"
              filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
              color-interpolation-filters="sRGB">
        <feImage href="svg-weights.png" x="0" y="0" width="64" height="64"
                 preserveAspectRatio="none" result="weights"/>
        <feComposite in="SourceGraphic" in2="weights" operator="arithmetic"
                     k1="1" k2="0" k3="0" k4="0" result="products"/>
        <feConvolveMatrix in="products" order="1 64" kernelMatrix="{kernel}"
                          divisor="{SVG_DIVISOR}" targetX="0" targetY="63"
                          edgeMode="none" preserveAlpha="false" result="sums"/>
      </filter>
      <filter id="difference" x="0" y="0" width="64" height="64"
              filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
              color-interpolation-filters="sRGB">
        <feImage href="svg-weights.png" x="0" y="0" width="64" height="64"
                 preserveAspectRatio="none" result="weights"/>
        <feComposite in="SourceGraphic" in2="weights" operator="arithmetic"
                     k1="1" k2="0" k3="0" k4="0" result="products"/>
        <feConvolveMatrix in="products" order="1 64" kernelMatrix="{kernel}"
                          divisor="{SVG_DIVISOR}" targetX="0" targetY="63"
                          edgeMode="none" preserveAlpha="false" result="sums"/>
        <feImage href="svg-reference.png" x="0" y="63" width="64" height="1"
                 preserveAspectRatio="none" result="reference"/>
        <feBlend in="sums" in2="reference" mode="difference" result="delta"/>
        <feComponentTransfer in="delta">
          <feFuncR type="linear" slope="16"/>
          <feFuncG type="linear" slope="16"/>
          <feFuncB type="linear" slope="16"/>
        </feComponentTransfer>
      </filter>
      <g id="product-row" clip-path="url(#row-63)">
        <g filter="url(#product)">{rows}</g>
      </g>
      <g id="actual-row" clip-path="url(#row-63)">
        <g filter="url(#matvec)">{rows}</g>
      </g>
      <image id="reference-row" href="svg-reference.png" x="0" y="63"
             width="64" height="1" preserveAspectRatio="none"/>
      <g id="difference-row" clip-path="url(#row-63)">
        <g filter="url(#difference)">{rows}</g>
      </g>
    </defs>
    {stages}
  </svg>
  </div>
  <p>Rows: product sample, calculated output, reference, 16× difference.</p>
</body>
</html>
''', expected


def index_html() -> str:
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>CSS matrix backends</title>
<style>body{font:16px system-ui;margin:2rem}li{margin:.75rem 0}</style></head>
<body><h1>64×64 matrix backend experiments</h1><ul>
<li><a href="variable-font.html">Variable-font/HVAR matvec</a></li>
<li><a href="variable-font-direct.html">Direct-HVAR matvec</a></li>
<li><a href="svg-pixel.html">SVG pixel-tensor matvec</a></li>
<li><a href="RESULTS.md">Measured results</a></li>
</ul></body></html>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font_weights, font_input, svg_weights, svg_input = deterministic_inputs()
    font_expected = font_weights.astype(np.float64) @ font_input
    build_font_backend(font_weights, OUT / "variable-matvec.ttf")
    font_html = variable_font_html(font_input, font_expected)
    (OUT / "variable-font.html").write_text(font_html)
    build_direct_font_backend(font_weights, OUT / "variable-matvec-direct.ttf")
    (OUT / "variable-font-direct.html").write_text(
        font_html.replace("variable-matvec.woff2?v=4", "variable-matvec-direct.woff2?v=1")
    )
    svg_html, svg_expected = build_svg_assets(svg_weights, svg_input)
    (OUT / "svg-pixel.html").write_text(svg_html)
    (OUT / "index.html").write_text(index_html())
    metadata = {
        "size": SIZE,
        "font": {
            "input": font_input.tolist(),
            "expected": font_expected.tolist(),
            "weights_sha256": hashlib.sha256(font_weights.tobytes()).hexdigest(),
            "base_advance": FONT_BASE_ADVANCE,
            "units_per_em": UNITS_PER_EM,
            "font_size_px": FONT_SIZE,
            "font_bytes": (OUT / "variable-matvec.ttf").stat().st_size,
            "woff2_bytes": (OUT / "variable-matvec.woff2").stat().st_size,
            "direct_font_bytes": (OUT / "variable-matvec-direct.ttf").stat().st_size,
            "direct_woff2_bytes": (OUT / "variable-matvec-direct.woff2").stat().st_size,
        },
        "svg": {
            "input_levels": svg_input.tolist(),
            "input": (svg_input.astype(np.float64) / SVG_WEIGHT_MAX).tolist(),
            "expected": svg_expected.tolist(),
            "weights_sha256": hashlib.sha256(svg_weights.tobytes()).hexdigest(),
            "weight_max": SVG_WEIGHT_MAX,
            "divisor": SVG_DIVISOR,
            "weight_image_bytes": (OUT / "svg-weights.png").stat().st_size,
        },
    }
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        {
            "size": SIZE,
            "font_bytes": metadata["font"]["font_bytes"],
            "woff2_bytes": metadata["font"]["woff2_bytes"],
            "svg_weight_image_bytes": metadata["svg"]["weight_image_bytes"],
            "output": str(OUT),
        }
    )


if __name__ == "__main__":
    main()
