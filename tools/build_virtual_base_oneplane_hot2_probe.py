#!/usr/bin/env python3
"""Replace the retained hot-two exact rows with six virtual-base int16 glyphs."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_master


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-virtual-base-oneplane-hot2"
CONTROL = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
HOT_ROWS = 2 * head.GROUP_SIZE
SHARD = 128
DISPLAY_SCALE = 0.1
# FontBuilder derives OS/2.xAvgCharWidth as signed int16. Keeping the physical
# hmtx base here avoids a separate table patch; the effective HVAR base is not
# limited by this choice.
PHYSICAL_BASE_MAX = 32_767
BIAS_DELTA_MAX = 32_767
SAFETY_BASE = 32
CODEPOINT_STARTS = tuple(0xF0000 + shard * 0x1000 for shard in range(6))


def add_axis(font: TTFont, tag: str, minimum: float, maximum: float) -> Axis:
    axis = Axis()
    axis.axisTag = tag
    axis.minValue = minimum
    axis.defaultValue = 0
    axis.maxValue = maximum
    axis.flags = 0
    axis.axisNameID = font["name"].addName(tag)
    return axis


def build_virtual_base_font(
    values: np.ndarray,
    destination: Path,
    *,
    codepoint_start: int,
    dimension_start: int,
) -> dict[str, object]:
    row_count, dimensions = values.shape
    l1 = np.sum(np.abs(values.astype(np.int64)), axis=1)
    virtual_bases = l1 + SAFETY_BASE
    physical_bases = np.minimum(virtual_bases, PHYSICAL_BASE_MAX).astype(np.int32)
    bias_remainders = virtual_bases - physical_bases.astype(np.int64)
    bias_count = int(math.ceil(int(bias_remainders.max()) / BIAS_DELTA_MAX))
    bias_tags = [f"B{index:03d}" for index in range(bias_count)]
    input_tags = [global_axis_tag(dimension_start + index) for index in range(dimensions)]

    build_master(
        destination,
        physical_bases,
        "Regular",
        codepoint_start=codepoint_start,
    )
    font = TTFont(destination, recalcTimestamp=False)
    fvar = newTable("fvar")
    fvar.instances = []
    fvar.axes = [add_axis(font, tag, -1, 1) for tag in input_tags]
    fvar.axes.extend(add_axis(font, tag, 0, 1) for tag in bias_tags)
    font["fvar"] = fvar
    buildStatTable(
        font,
        [
            {"tag": axis.axisTag, "name": axis.axisNameID, "ordering": index}
            for index, axis in enumerate(fvar.axes)
        ],
    )

    supports = []
    for tag in input_tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    supports.extend({tag: (0, 1, 1)} for tag in bias_tags)
    rows = [[0] * len(supports)]
    for row, remainder in zip(values.astype(np.int64), bias_remainders):
        deltas = [component for weight in row for component in (-int(weight), int(weight))]
        remaining = int(remainder)
        for _tag in bias_tags:
            chunk = min(remaining, BIAS_DELTA_MAX)
            deltas.append(chunk)
            remaining -= chunk
        if remaining != 0:
            raise RuntimeError("virtual base did not fit allocated bias regions")
        rows.append(deltas)
    region_list = buildVarRegionList(supports, input_tags + bias_tags)
    var_data = buildVarData(range(len(supports)), rows, optimize=True)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [var_data])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in font.getGlyphOrder()}
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(destination)
    compressed = TTFont(destination, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(destination.with_suffix(".woff2"))
    return {
        "virtualBases": virtual_bases,
        "biasAxes": bias_count,
        "maximumL1": int(l1.max()),
        "maximumVirtualBase": int(virtual_bases.max()),
        "minimumSafetyAdvance": int(np.min(virtual_bases - l1)),
        "regions": 2 * dimensions + bias_count,
        "axes": dimensions + bias_count,
    }


def model_settings(input_range: float, bias_count: int) -> str:
    hidden = [
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension}) / {head.css_number(input_range)})"
        for dimension in range(head.WIDTH)
    ]
    hidden.extend(f'"B{index:03d}" 1' for index in range(bias_count))
    return ",".join(hidden)


def main() -> None:
    for path in (CONTROL / "index.html", CONTROL / "topology.css", CONTROL / "reference.json"):
        if not path.exists():
            raise FileNotFoundError(path)
    fine_reference = json.loads((FINE / "reference.json").read_text())
    control_reference = json.loads((CONTROL / "reference.json").read_text())
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[:HOT_ROWS], dtype=np.float64
    )
    scale = float(fine_reference["weightScale"])
    codes = np.rint(embeddings / scale).astype(np.int16)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    shard_reports = []
    virtual_bases = []
    fonts = []
    for shard, start in enumerate(range(0, head.WIDTH, SHARD)):
        destination = OUTPUT / f"score-oneplane-{shard}.ttf"
        report = build_virtual_base_font(
            codes[:, start : start + SHARD],
            destination,
            codepoint_start=CODEPOINT_STARTS[shard],
            dimension_start=start,
        )
        virtual_bases.append(report.pop("virtualBases"))
        shard_reports.append({"shard": shard, **report})
        fonts.append(destination.with_suffix(".woff2"))
    row_bases = np.sum(np.stack(virtual_bases), axis=0) * DISPLAY_SCALE

    candidates = []
    factor = (
        float(fine_reference["inputRange"])
        * scale
        * head.SCORE_SCALE
        * head.SCORE_STRIDE_PX
        / DISPLAY_SCALE
    )
    for token in range(HOT_ROWS):
        characters = "".join(chr(start + token) for start in CODEPOINT_STARTS)
        candidates.append(
            f'<i class="candidate mixed-hot-candidate" style="--base:'
            f'{head.css_number(row_bases[token])};--factor:{head.css_number(factor)};'
            f'--local-tie:{head.GROUP_SIZE - 1 - token % head.GROUP_SIZE}">'
            f"{characters}</i>"
        )

    html = (CONTROL / "index.html").read_text()
    replacement_index = 0

    def replace_candidate(match: re.Match[str]) -> str:
        nonlocal replacement_index
        value = candidates[replacement_index]
        replacement_index += 1
        return value

    html = re.sub(
        r'<i class="candidate mixed-hot-candidate"[^>]*>.*?</i>',
        replace_candidate,
        html,
    )
    if replacement_index != HOT_ROWS:
        raise RuntimeError(f"expected {HOT_ROWS} hot candidates, found {replacement_index}")
    html = html.replace(
        "Mixed-precision hot-two certified upper head",
        "Virtual-base one-plane hot-two upper head",
        1,
    )
    (OUTPUT / "index.html").write_text(html)

    topology = (CONTROL / "topology.css").read_text()
    old_faces = r"^(?:@font-face\{.*?\}){12}"
    face_css = "".join(
        f'@font-face{{font-family:OnePlane{shard};src:url("{font.name}") format("woff2")}}'
        for shard, font in enumerate(fonts)
    )
    topology, count = re.subn(old_faces, face_css, topology, count=1)
    if count != 1:
        raise RuntimeError("could not replace the twelve exact font faces")
    old_families = ",".join(
        f"Score{plane}{shard}" for shard in range(6) for plane in ("H", "L")
    )
    new_families = ",".join(f"OnePlane{shard}" for shard in range(6))
    if old_families not in topology:
        raise RuntimeError("could not find the old hot candidate family chain")
    topology = topology.replace(old_families, new_families, 1)
    maximum_bias_axes = max(report["biasAxes"] for report in shard_reports)
    topology = (
        face_css
        + f".model{{font-variation-settings:{model_settings(float(fine_reference['inputRange']), maximum_bias_axes)}}}"
        + topology[len(face_css) :]
    )
    (OUTPUT / "topology.css").write_text(topology)

    reference = {
        **control_reference,
        "backend": "virtual-base-oneplane-global-int16-hot2-upper-six-stage",
        "control": CONTROL.name,
        "glyphsPerHotRow": 6,
        "controlGlyphsPerHotRow": 12,
        "hotGlyphReductionPercent": 50,
        "virtualBase": {
            "physicalBaseMaximum": PHYSICAL_BASE_MAX,
            "biasDeltaMaximum": BIAS_DELTA_MAX,
            "safetyBase": SAFETY_BASE,
            "maximumBiasAxes": maximum_bias_axes,
            "shards": shard_reports,
        },
        "assets": {
            **control_reference["assets"],
            "onePlaneFontFiles": len(fonts),
            "onePlaneFontWoff2Bytes": sum(path.stat().st_size for path in fonts),
            "exactFontFiles": len(fonts),
            "exactFontWoff2Bytes": sum(path.stat().st_size for path in fonts),
            "fontsCopiedOrRebuilt": True,
            "exactFontsAreCurrentlyFullVocabulary": False,
        },
        "generatedBytes": {},
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("index.html", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(
        "# Virtual-base one-plane hot-2 exact rows\n\n"
        "Browser status: **pending**.\n\n"
        "The probe preserves the retained mixed-precision hot-2 topology but "
        "replaces each hot exact row's twelve high/residual glyphs with six "
        "direct int16 glyphs. Always-on HVAR bias regions keep every resulting "
        "advance nonnegative.\n"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "hotRows": HOT_ROWS,
                "glyphsPerHotRow": 6,
                "controlGlyphsPerHotRow": 12,
                "maximumBiasAxes": maximum_bias_axes,
                "shards": shard_reports,
                "fontWoff2Bytes": reference["assets"]["onePlaneFontWoff2Bytes"],
                "generatedBytes": reference["generatedBytes"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
