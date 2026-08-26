#!/usr/bin/env python3
"""Build an eight-glyph signed-run hot-two scorer with two compensators."""

from __future__ import annotations

import json
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
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_master


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-compensated-oneplane-hot2"
CONTROL = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BASELINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated"
HOT_ROWS = 2 * head.GROUP_SIZE
SHARD = 128
DISPLAY_SCALE = 0.1
SAFETY = 32
CODEPOINT_STARTS = tuple(0xF6000 + shard * 0x1000 for shard in range(6))


def add_signed_axis(font: TTFont, tag: str) -> Axis:
    axis = Axis()
    axis.axisTag = tag
    axis.minValue = -1
    axis.defaultValue = 0
    axis.maxValue = 1
    axis.flags = 0
    axis.axisNameID = font["name"].addName(tag)
    return axis


def build_score_font(
    values: np.ndarray,
    destination: Path,
    *,
    codepoint_start: int,
    dimension_start: int,
    compensator: int | None = None,
) -> None:
    row_count, dimensions = values.shape
    widths = np.zeros(row_count + (2 if compensator is not None else 0), dtype=np.int32)
    if compensator is not None:
        widths[-2] = compensator // 2
        widths[-1] = compensator - widths[-2]
    build_master(destination, widths, "Regular", codepoint_start=codepoint_start)
    font = TTFont(destination, recalcTimestamp=False)
    tags = [global_axis_tag(dimension_start + index) for index in range(dimensions)]
    fvar = newTable("fvar")
    fvar.instances = []
    fvar.axes = [add_signed_axis(font, tag) for tag in tags]
    font["fvar"] = fvar
    buildStatTable(
        font,
        [{"tag": axis.axisTag, "name": axis.axisNameID, "ordering": index}
         for index, axis in enumerate(fvar.axes)],
    )
    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    rows = [[0] * len(supports)]
    rows.extend(
        [component for weight in row for component in (-int(weight), int(weight))]
        for row in values.astype(np.int64)
    )
    if compensator is not None:
        rows.extend([[0] * len(supports), [0] * len(supports)])
    region_list = buildVarRegionList(supports, tags)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        region_list, [buildVarData(range(len(supports)), rows, optimize=True)]
    )
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


def main() -> None:
    fine = json.loads((FINE / "reference.json").read_text())
    control = json.loads((CONTROL / "reference.json").read_text())
    baseline = json.loads((BASELINE / "reference.json").read_text())
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight")[:HOT_ROWS], dtype=np.float64)
    scale = float(fine["weightScale"])
    codes = np.rint(embeddings / scale).astype(np.int16)

    saved = np.load(STATES)
    corpus = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(corpus))) * 1.01
    realized = np.rint(corpus / production_range * AXIS_STEPS) / AXIS_STEPS * production_range
    fixtures = np.asarray(baseline["certifiedFixtures"]["hiddenVectors"], dtype=np.float64)
    screen = np.concatenate((realized, fixtures), axis=0)
    score_units = screen @ codes.astype(np.float64).T / float(fine["inputRange"])
    minimum = float(score_units.min())
    compensator = int(np.ceil(-minimum + SAFETY))
    if compensator > 65_535:
        raise RuntimeError(f"screen needs {compensator} compensator units")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    fonts = []
    for shard, start in enumerate(range(0, head.WIDTH, SHARD)):
        destination = OUTPUT / f"score-signed-{shard}.ttf"
        build_score_font(
            codes[:, start : start + SHARD],
            destination,
            codepoint_start=CODEPOINT_STARTS[shard],
            dimension_start=start,
            compensator=compensator if shard == 5 else None,
        )
        fonts.append(destination.with_suffix(".woff2"))

    compensation_characters = (
        chr(CODEPOINT_STARTS[5] + HOT_ROWS)
        + chr(CODEPOINT_STARTS[5] + HOT_ROWS + 1)
    )
    factor = (
        float(fine["inputRange"]) * scale * head.SCORE_SCALE
        * head.SCORE_STRIDE_PX / DISPLAY_SCALE
    )
    candidates = []
    for token in range(HOT_ROWS):
        characters = "".join(chr(start + token) for start in CODEPOINT_STARTS)
        candidates.append(
            f'<i class="candidate mixed-hot-candidate" style="--base:'
            f'{head.css_number(compensator * DISPLAY_SCALE)};'
            f'--factor:{head.css_number(factor)};'
            f'--local-tie:{head.GROUP_SIZE - 1 - token % head.GROUP_SIZE}">'
            f"{characters}{compensation_characters}</i>"
        )
    html = (CONTROL / "index.html").read_text()
    replacement_index = 0

    def replace_candidate(_match: re.Match[str]) -> str:
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
        raise RuntimeError(f"expected {HOT_ROWS} hot rows, found {replacement_index}")
    html = html.replace(
        "Mixed-precision hot-two certified upper head",
        "Compensated one-plane hot-two upper head",
        1,
    )
    (OUTPUT / "index.html").write_text(html)

    topology = (CONTROL / "topology.css").read_text()
    families = ",".join(f"SignedScore{shard}" for shard in range(6))
    face_css = "".join(
        f'@font-face{{font-family:SignedScore{shard};src:url("{font.name}") format("woff2")}}'
        for shard, font in enumerate(fonts)
    )
    topology, count = re.subn(r"^(?:@font-face\{.*?\}){12}", face_css, topology, count=1)
    if count != 1:
        raise RuntimeError("could not replace exact face declarations")
    old_families = ",".join(
        f"Score{plane}{shard}" for shard in range(6) for plane in ("H", "L")
    )
    if old_families not in topology:
        raise RuntimeError("could not find retained exact family chain")
    topology = topology.replace(old_families, families, 1)
    (OUTPUT / "topology.css").write_text(topology)

    reference = {
        **control,
        "backend": "screen-compensated-oneplane-global-int16-hot2-upper-six-stage",
        "reportTitle": "Screen-compensated one-plane hot-2 rows",
        "control": CONTROL.name,
        "glyphsPerHotRow": 8,
        "controlGlyphsPerHotRow": 12,
        "hotGlyphReductionPercent": 100 * (12 - 8) / 12,
        "encodingDescription": (
            "The retained hot-2 topology is unchanged. Each exact hot row uses "
            "six unbiased direct-int16 score glyphs followed by two fixed "
            "compensator glyphs in the same inline run. The compensator covers "
            "all 1,024 browser-realized corpus states and ten fixtures."
        ),
        "screenCompensation": {
            "states": int(len(screen)),
            "minimumScoreUnits": minimum,
            "maximumScoreUnits": float(score_units.max()),
            "compensatorUnits": compensator,
            "safetyUnits": SAFETY,
            "scope": "1024 browser-realized corpus states plus 10 certified fixtures",
        },
        "assets": {
            **control["assets"],
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
        "# Screen-compensated one-plane hot-2 exact rows\n\nBrowser status: **pending**.\n"
    )
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "glyphsPerHotRow": 8,
        "compensatorUnits": compensator,
        "minimumScoreUnits": minimum,
        "fontWoff2Bytes": reference["assets"]["onePlaneFontWoff2Bytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
