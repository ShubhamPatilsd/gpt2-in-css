#!/usr/bin/env python3
"""Merge the retained hot-two exact rows into three 256-axis shard pairs."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import global_axis_tag


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-twoplane-256axis-hot2"
CONTROL = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
HOT_GROUPS = (0, 1)
HOT_ROWS = len(HOT_GROUPS) * head.GROUP_SIZE
SHARD = 256
SAFETY = 32
DISPLAY_SCALE = 0.1
UINT16_MAX = 65_535
CODEPOINT_STARTS = tuple(0xF0000 + face * 0x1000 for face in range(6))
EXPECTED_HIGH_L1_MAXIMA = (2_672, 2_643, 2_562)
EXPECTED_RESIDUAL_L1_MAXIMA = (35_682, 35_999, 35_803)
EXPECTED_MAXIMUM_POSITIVE_RESULT = 72_030


def glyph():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def build_base_font(
    destination: Path,
    bases: np.ndarray,
    *,
    family: str,
    codepoint_start: int,
) -> None:
    """Build a base whose hmtx widths may use the full uint16 domain."""
    order = [".notdef", *[f"y{row:03d}" for row in range(len(bases))]]
    builder = FontBuilder(1_000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(
        {codepoint_start + row: f"y{row:03d}" for row in range(len(bases))}
    )
    builder.setupGlyf({name: glyph() for name in order})
    metrics = {".notdef": (0, 0)}
    metrics.update(
        {f"y{row:03d}": (int(base), 0) for row, base in enumerate(bases)}
    )
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=1_000, descent=0)
    builder.setupNameTable(
        {
            "familyName": family,
            "styleName": "Regular",
            "uniqueFontIdentifier": f"{family}-regular",
            "fullName": f"{family} Regular",
            "psName": f"{family}-Regular",
        }
    )
    builder.setupOS2(
        sTypoAscender=1_000,
        sTypoDescender=0,
        usWinAscent=1_000,
        usWinDescent=0,
    )
    # OS/2.xAvgCharWidth is signed int16 even though hmtx advances are uint16.
    builder.font["OS/2"].xAvgCharWidth = min(
        32_767, max(0, int(np.rint(np.mean(bases))))
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(destination)


def build_face(
    values: np.ndarray,
    bases: np.ndarray,
    destination: Path,
    *,
    family: str,
    codepoint_start: int,
    dimension_start: int,
) -> None:
    if values.shape != (HOT_ROWS, SHARD):
        raise ValueError(f"unexpected face shape {values.shape}")
    if np.any(values < -32_768) or np.any(values > 32_767):
        raise ValueError("HVAR deltas escaped int16")
    if np.any(bases < 0) or np.any(bases > UINT16_MAX):
        raise ValueError("stored hmtx base escaped uint16")

    build_base_font(
        destination,
        bases,
        family=family,
        codepoint_start=codepoint_start,
    )
    font = TTFont(destination, recalcTimestamp=False)
    tags = [global_axis_tag(dimension_start + offset) for offset in range(SHARD)]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for ordering, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": ordering})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    rows = [[0] * len(supports)]
    for row in values.astype(np.int64):
        rows.append([delta for value in row for delta in (-int(value), int(value))])
    region_list = buildVarRegionList(supports, tags)
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
    gvar.variations = {name: [] for name in font.getGlyphOrder()}
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(destination)
    compressed = TTFont(destination, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(destination.with_suffix(".woff2"))


def prepare_planes(codes: np.ndarray) -> tuple[list[dict[str, object]], list[np.ndarray]]:
    """Validate every merged plane before any font is emitted."""
    reports: list[dict[str, object]] = []
    equivalent_bases: list[np.ndarray] = []
    for shard, start in enumerate(range(0, head.WIDTH, SHARD)):
        shard_codes = codes[:, start : start + SHARD].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        reconstructed = high.astype(np.int32) * 256 + residual.astype(np.int32)
        if not np.array_equal(reconstructed, shard_codes):
            raise RuntimeError(f"shard {shard} high/residual split is not exact")
        if int(np.max(np.abs(high))) > 127:
            raise RuntimeError(f"shard {shard} high plane escaped signed int8")
        if int(np.max(np.abs(residual))) > 255:
            raise RuntimeError(f"shard {shard} residual escaped signed byte magnitude")

        plane_bases = []
        for plane_name, values in (("high", high), ("residual", residual)):
            l1 = np.sum(np.abs(values.astype(np.int64)), axis=1)
            bases = l1 + SAFETY
            fits = bases <= UINT16_MAX
            if not np.all(fits):
                bad = np.flatnonzero(~fits)
                raise RuntimeError(
                    f"shard {shard} {plane_name} has {len(bad)} hot rows whose "
                    f"negative L1 excursion plus safety exceeds {UINT16_MAX}; "
                    f"first rows {bad[:8].tolist()}"
                )
            positive_results = bases + l1
            reports.append(
                {
                    "shard": shard,
                    "plane": plane_name,
                    "dimensionStart": start,
                    "dimensionStop": start + SHARD,
                    "axes": SHARD,
                    "regions": SHARD * 2,
                    "rowsChecked": HOT_ROWS,
                    "rowsWhoseL1FitsBase": int(np.sum(l1 <= bases)),
                    "minimumL1": int(l1.min()),
                    "maximumL1": int(l1.max()),
                    "minimumBase": int(bases.min()),
                    "maximumBase": int(bases.max()),
                    "minimumSafetyAdvance": int(np.min(bases - l1)),
                    "maximumPositiveResultingAdvance": int(positive_results.max()),
                    "rowsPositiveResultExceedsUint16": int(
                        np.sum(positive_results > UINT16_MAX)
                    ),
                    "values": values,
                    "bases": bases.astype(np.int32),
                }
            )
            plane_bases.append(bases.astype(np.int64))
        equivalent_bases.append(plane_bases[0] * 256 + plane_bases[1])
    return reports, equivalent_bases


def main() -> None:
    started = time.perf_counter()
    for path in (
        CONTROL / "index.html",
        CONTROL / "topology.css",
        CONTROL / "reference.json",
        FINE / "reference.json",
    ):
        if not path.exists():
            raise FileNotFoundError(path)
    control_reference = json.loads((CONTROL / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight")[:HOT_ROWS], dtype=np.float64)
    scale = float(fine_reference["weightScale"])
    codes = np.rint(embeddings / scale).astype(np.int16)

    # This gate runs before OUTPUT is created or any font is serialized.
    plane_reports, equivalent_bases = prepare_planes(codes)
    if len(plane_reports) != 6 or any(
        report["rowsWhoseL1FitsBase"] != HOT_ROWS for report in plane_reports
    ):
        raise RuntimeError("not every hot-two 256-axis plane row passed the L1/base gate")
    high_maxima = tuple(
        report["maximumL1"] for report in plane_reports if report["plane"] == "high"
    )
    residual_maxima = tuple(
        report["maximumL1"]
        for report in plane_reports
        if report["plane"] == "residual"
    )
    maximum_positive_result = max(
        report["maximumPositiveResultingAdvance"] for report in plane_reports
    )
    if (
        high_maxima != EXPECTED_HIGH_L1_MAXIMA
        or residual_maxima != EXPECTED_RESIDUAL_L1_MAXIMA
        or maximum_positive_result != EXPECTED_MAXIMUM_POSITIVE_RESULT
    ):
        raise RuntimeError(
            "offline L1 confirmation changed: "
            f"high={high_maxima}, residual={residual_maxima}, "
            f"maximum positive result={maximum_positive_result}"
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    fonts: list[Path] = []
    face_css: list[str] = []
    family_names: list[str] = []
    for face, report in enumerate(plane_reports):
        shard = int(report["shard"])
        plane_name = str(report["plane"])
        plane_letter = "H" if plane_name == "high" else "L"
        family = f"Score256{plane_letter}{shard}"
        destination = OUTPUT / f"score-{'h' if plane_name == 'high' else 'l'}{shard}.ttf"
        build_face(
            report.pop("values"),
            report.pop("bases"),
            destination,
            family=family,
            codepoint_start=CODEPOINT_STARTS[face],
            dimension_start=int(report["dimensionStart"]),
        )
        font = destination.with_suffix(".woff2")
        fonts.append(font)
        family_names.append(family)
        size_adjust = ";size-adjust:25600%" if plane_name == "high" else ""
        face_css.append(
            f'@font-face{{font-family:{family};src:url("{font.name}") '
            f'format("woff2"){size_adjust}}}'
        )

    row_bases = np.sum(np.stack(equivalent_bases), axis=0) * DISPLAY_SCALE
    factor = (
        float(fine_reference["inputRange"])
        * scale
        * head.SCORE_SCALE
        * head.SCORE_STRIDE_PX
        / DISPLAY_SCALE
    )
    candidates = []
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
        raise RuntimeError(f"expected {HOT_ROWS} retained hot rows, found {replacement_index}")
    html = html.replace(
        "Mixed-precision hot-two certified upper head",
        "Three-pair 256-axis two-plane hot-two upper head",
        1,
    )
    (OUTPUT / "index.html").write_text(html)

    topology = (CONTROL / "topology.css").read_text()
    topology, face_count = re.subn(
        r"^(?:@font-face\{.*?\}){12}", "".join(face_css), topology, count=1
    )
    if face_count != 1:
        raise RuntimeError("could not replace the retained twelve exact font faces")
    old_families = ",".join(
        f"Score{plane}{shard}" for shard in range(6) for plane in ("H", "L")
    )
    new_families = ",".join(family_names)
    if topology.count(old_families) != 1:
        raise RuntimeError("retained twelve-family hot-row chain changed")
    topology = topology.replace(old_families, new_families, 1)
    (OUTPUT / "topology.css").write_text(topology)

    font_checks = []
    for font_path, report in zip(fonts, plane_reports):
        font = TTFont(font_path, recalcTimestamp=False)
        font_checks.append(
            {
                "file": font_path.name,
                "axes": len(font["fvar"].axes),
                "regions": len(font["HVAR"].table.VarStore.VarRegionList.Region),
                "glyphs": len(font.getGlyphOrder()) - 1,
                "maximumStoredAdvance": max(
                    advance for advance, _lsb in font["hmtx"].metrics.values()
                ),
                "expectedMaximumBase": report["maximumBase"],
            }
        )
    if any(
        item["axes"] != SHARD
        or item["regions"] != SHARD * 2
        or item["glyphs"] != HOT_ROWS
        or item["maximumStoredAdvance"] != item["expectedMaximumBase"]
        for item in font_checks
    ):
        raise RuntimeError(f"serialized font invariant failed: {font_checks}")

    reference = {
        **control_reference,
        "backend": "global-int16-high-residual-256axis-hot2-upper-six-stage",
        "control": CONTROL.name,
        "hotGroups": list(HOT_GROUPS),
        "glyphsPerHotRow": 6,
        "controlGlyphsPerHotRow": 12,
        "hotGlyphReductionPercent": 50,
        "virtualBiasAxes": 0,
        "decomposition": {
            "source": "the retained global-int16 codes and global scale",
            "formula": "code = trunc(code / 256) * 256 + residual",
            "shardAxes": SHARD,
            "shardsPerPlane": head.WIDTH // SHARD,
            "planes": 2,
            "safety": SAFETY,
            "baseRule": "per-row base = 256-axis L1 + safety",
            "storedBaseMaximum": UINT16_MAX,
            "positiveResultingAdvanceMayExceedStoredUint16": True,
            "planeChecks": plane_reports,
            "serializedFontChecks": font_checks,
        },
        "assets": {
            **control_reference["assets"],
            "controlExactFontFiles": control_reference["assets"]["exactFontFiles"],
            "controlExactFontWoff2Bytes": control_reference["assets"]["exactFontWoff2Bytes"],
            "exactFontFiles": len(fonts),
            "exactFontWoff2Bytes": sum(path.stat().st_size for path in fonts),
            "fontsCopiedOrRebuilt": True,
            "exactFontsAreCurrentlyFullVocabulary": False,
        },
        "generatedBytes": {},
        "offlineSeconds": time.perf_counter() - started,
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    # The second pass stabilizes reference.json's self-reported byte count.
    for _pass in range(2):
        reference["generatedBytes"] = {
            name: (OUTPUT / name).stat().st_size
            for name in ("index.html", "topology.css", "reference.json")
        }
        reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    maximum_l1 = max(report["maximumL1"] for report in plane_reports)
    maximum_base = max(report["maximumBase"] for report in plane_reports)
    over_range_rows = sum(
        report["rowsPositiveResultExceedsUint16"] for report in plane_reports
    )
    (OUTPUT / "RESULTS.md").write_text(
        "# Three-pair 256-axis two-plane hot-2 rows\n\n"
        "Browser status: **pending two-fixture falsification**.\n\n"
        "The exact retained global-int16 high/residual decomposition is unchanged, "
        "but adjacent 128-axis shards are merged. Each hot row now uses three high/"
        "residual font pairs (six glyphs) and no virtual-bias axes.\n\n"
        f"All {len(plane_reports) * HOT_ROWS:,} plane-row checks passed: maximum "
        f"256-axis L1 {maximum_l1:,}, maximum stored base {maximum_base:,}. "
        f"{over_range_rows:,} positive endpoint results exceed 65,535 by design.\n"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "hotRows": HOT_ROWS,
                "glyphsPerHotRow": 6,
                "controlGlyphsPerHotRow": 12,
                "virtualBiasAxes": 0,
                "planeChecks": plane_reports,
                "fontWoff2Bytes": reference["assets"]["exactFontWoff2Bytes"],
                "generatedBytes": reference["generatedBytes"],
                "offlineSeconds": reference["offlineSeconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
