#!/usr/bin/env python3
"""Build the bounded CMAP format-14 indexed GPT-2 fine-scorer probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_matrix_backend_prototypes import (
    UNITS_PER_EM,
    build_direct_font_backend,
    output_glyph,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "cmap14-indexed-fine-scorer"
FINE_ROOT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BASELINE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
BASELINE_ROOT = ROOT / "experiments" / BASELINE_NAME
GSUB_ROOT = ROOT / "experiments" / "gsub-indexed-fine-scorer"
GROUPS = (0, 1, 2, 17, 64, 96, 128, 195)
BASE_CODEPOINT_START = 0xE000
FACE_COUNT = 2 * ((head.WIDTH + fine.SHARD - 1) // fine.SHARD)
SCORE_ROWS = len(GROUPS) * head.GROUP_SIZE
DEFAULT_DISPLAY_SCALE = 0.05
CHROME_ADVANCE_CEILING_PX = 32_768


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--display-scale",
        type=float,
        default=DEFAULT_DISPLAY_SCALE,
        help="CSS pixels per font unit (default: 0.05, i.e. 50px at 1000 UPEM)",
    )
    args = parser.parse_args()
    if not 0 < args.display_scale <= 1:
        raise ValueError("--display-scale must be in (0, 1]")
    return args


def variation_selectors() -> tuple[int, ...]:
    selectors = (*range(0xFE00, 0xFE10), *range(0xE0100, 0xE01F0))
    if len(selectors) != head.GROUP_SIZE or len(set(selectors)) != head.GROUP_SIZE:
        raise AssertionError("expected exactly 256 unique Unicode variation selectors")
    return selectors


def face_base_codepoints(face: int) -> tuple[int, ...]:
    """Return eight face-unique, BMP-PUA base characters in group order."""
    return tuple(
        BASE_CODEPOINT_START + face * len(GROUPS) + group_index
        for group_index in range(len(GROUPS))
    )


def install_cmap14(font_path: Path, face: int) -> None:
    """Replace input cmaps with eight bases and 8x256 non-default UVSes."""
    font = TTFont(font_path, recalcTimestamp=False)
    bases = face_base_codepoints(face)
    selectors = variation_selectors()
    cmap = font["cmap"]
    cmap.tables = [table for table in cmap.tables if table.format != 14]
    unicode_tables = [table for table in cmap.tables if table.isUnicode()]
    if not unicode_tables:
        raise RuntimeError(f"{font_path.name} has no Unicode cmap to retain")
    for table in unicode_tables:
        table.cmap = {base: output_glyph(SCORE_ROWS) for base in bases}
        # Loaded cmap subtables retain their original compiled bytes in `data`;
        # clear that cache so compile() serializes the replacement mapping.
        table.data = None

    format14 = CmapSubtable.newSubtable(14)
    format14.platformID = 0
    format14.platEncID = 5
    format14.language = 0xFF
    format14.cmap = {}
    format14.uvsDict = {
        selector: [
            (
                base,
                output_glyph(group_index * head.GROUP_SIZE + local),
            )
            for group_index, base in enumerate(bases)
        ]
        for local, selector in enumerate(selectors)
    }
    cmap.tables.append(format14)
    font.recalcTimestamp = False
    font.save(font_path)

    compressed = TTFont(font_path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(font_path.with_suffix(".woff2"))

    check = TTFont(font_path, lazy=True)
    tables14 = [table for table in check["cmap"].tables if table.format == 14]
    if len(tables14) != 1:
        raise RuntimeError(f"{font_path.name} did not retain exactly one format-14 cmap")
    observed = sum(len(entries) for entries in tables14[0].uvsDict.values())
    if observed != len(GROUPS) * head.GROUP_SIZE:
        raise RuntimeError(
            f"{font_path.name} retained {observed} UVS mappings, expected 2048"
        )
    regular_mapping = {}
    for table in check["cmap"].tables:
        if table.format != 14 and table.isUnicode():
            regular_mapping.update(table.cmap)
    expected_regular = {base: output_glyph(SCORE_ROWS) for base in bases}
    if regular_mapping != expected_regular:
        raise RuntimeError(f"{font_path.name} did not retain its eight sentinel bases")
    for local, selector in enumerate(selectors):
        expected_uvs = {
            base: output_glyph(group_index * head.GROUP_SIZE + local)
            for group_index, base in enumerate(bases)
        }
        if dict(tables14[0].uvsDict[selector]) != expected_uvs:
            raise RuntimeError(
                f"{font_path.name} has an incorrect mapping for U+{selector:04X}"
            )


def render_html() -> str:
    selectors = variation_selectors()
    candidates = []
    for local, selector in enumerate(selectors):
        face_spans = "".join(
            f'<span class="face-sequence face-{face}" data-face="{face}"></span>'
            for face in range(FACE_COUNT)
        )
        candidates.append(
            f'<i class="cmap-candidate" data-local="{local}" '
            f"style='--local-tie:{head.GROUP_SIZE - 1 - local};"
            f'--selector:"\\{selector:x}"\'>{face_spans}</i>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>CMAP14-indexed global-int16 GPT-2 fine scorer</title>
<link rel="stylesheet" href="index.css">
<main id="cmap14-stage" class="fine-stage" data-group="0">{"".join(candidates)}</main>
"""


def render_css(reference: dict, face_bases: list[int], display_scale: float) -> str:
    faces = []
    families = []
    for shard in range(reference["shards"]):
        for plane_name, plane_letter in (("high", "h"), ("low", "l")):
            family = f"CMAP14Score{plane_letter.upper()}{shard}"
            adjustment = ";size-adjust:25600%" if plane_name == "high" else ""
            faces.append(
                f'@font-face{{font-family:{family};src:url("score-{plane_letter}{shard}.woff2") '
                f'format("woff2"){adjustment}}}'
            )
            families.append(family)
    settings = ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f'calc(var(--h{dimension})/{head.css_number(reference["inputRange"])})'
        for dimension in range(head.WIDTH)
    )
    equivalent_base = sum(
        face_bases[2 * shard] * 256 + face_bases[2 * shard + 1]
        for shard in range(reference["shards"])
    )
    factor = (
        reference["inputRange"]
        * reference["weightScale"]
        * reference["scoreScale"]
        * reference["scoreStridePx"]
        / display_scale
    )
    font_size = display_scale * UNITS_PER_EM
    group_rules = "".join(
        f'.fine-stage[data-group="{group_index}"]{{' + "".join(
            f'--base-{face}:"\\{face_base_codepoints(face)[group_index]:x}";'
            for face in range(FACE_COUNT)
        ) + "}"
        for group_index in range(len(GROUPS))
    )
    face_rules = "".join(
        f'.face-{face}{{font-family:{families[face]}}}'
        f'.face-{face}::before{{content:var(--base-{face}) var(--selector)}}'
        for face in range(FACE_COUNT)
    )
    return "\n".join((
        "".join(faces),
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
        ".fine-stage{position:fixed;left:0;top:0;display:grid;"
        "grid-template-columns:max-content;grid-template-rows:1px;"
        "width:max-content;height:1px;"
        f"font-family:{','.join(families)};"
        f"font-size:{head.css_number(font_size)}px;line-height:1;"
        f"font-variation-settings:{settings};font-kerning:none;font-synthesis:none;"
        "--score-offset:0px}",
        ".cmap-candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal;"
        "width:calc-size(max-content,calc(round(nearest,"
        f"(size - {head.css_number(equivalent_base * display_scale)}px)"
        f"*{head.css_number(factor)} + var(--score-offset),4px)"
        " + var(--local-tie)/64*1px))}",
        # Avoid Chromium's 32768px clamp on each high-plane inline box while
        # retaining one declarative generated-content carrier per face.
        ".face-sequence{display:contents}",
        group_rules,
        face_rules,
    )) + "\n"


def fixture_oracle(
    fine_reference: dict,
    quantized_embeddings: np.ndarray,
    baseline_reference: dict,
) -> dict:
    fixtures = baseline_reference["certifiedFixtures"]
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=int)
    cases = []
    for fixture, vector in enumerate(hidden):
        group_cases = []
        for group_index, group in enumerate(GROUPS):
            start = group * head.GROUP_SIZE
            stop = start + head.GROUP_SIZE
            scores = vector @ quantized_embeddings[start:stop].T
            buckets = np.rint(
                (scores - floors[fixture]) * fine_reference["scoreScale"]
            ).astype(int)
            winner_bucket = int(np.max(buckets))
            tied_locals = np.flatnonzero(buckets == winner_bucket).astype(int).tolist()
            winner_local = tied_locals[0]
            group_cases.append({
                "group": group,
                "groupIndex": group_index,
                "validCandidates": head.GROUP_SIZE,
                "buckets": buckets.tolist(),
                "winnerLocal": winner_local,
                "winnerToken": start + winner_local,
                "winnerBucket": winner_bucket,
                "tiedWinnerLocals": tied_locals,
            })
        cases.append({"fixture": fixture, "groups": group_cases})
    return {
        "hiddenVectors": fixtures["hiddenVectors"],
        "scoreFloors": fixtures["scoreFloors"],
        "cases": cases,
    }


def main() -> None:
    args = parse_args()
    display_scale = args.display_scale
    fine_reference = json.loads((FINE_ROOT / "reference.json").read_text())
    baseline_reference = json.loads((BASELINE_ROOT / "reference.json").read_text())
    gsub_results = json.loads((GSUB_ROOT / "browser-results.json").read_text())
    if fine_reference["groups"] != 197:
        raise RuntimeError("unexpected source fine-scorer group count")
    if tuple(gsub_results["groups"]) != GROUPS:
        raise RuntimeError("GSUB bounded-probe spread no longer matches this probe")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    codes = np.rint(embeddings / fine_reference["weightScale"]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * fine_reference["weightScale"]
    fixture_hidden = np.asarray(
        baseline_reference["certifiedFixtures"]["hiddenVectors"], dtype=np.float64
    ) / fine_reference["inputRange"]
    selected_tokens = np.concatenate([
        np.arange(group * head.GROUP_SIZE, (group + 1) * head.GROUP_SIZE)
        for group in GROUPS
    ])

    font_paths = []
    face_bases = []
    face_ranges = []
    face = 0
    for shard, start in enumerate(range(0, head.WIDTH, fine.SHARD)):
        stop = min(start + fine.SHARD, head.WIDTH)
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        for plane, values in enumerate((high, residual)):
            selected = values[selected_tokens]
            l1 = np.sum(np.abs(selected.astype(np.int64)), axis=1).astype(np.int32)
            common_base = int(np.max(l1 + 32))
            if common_base + int(np.max(l1)) > 65_535:
                raise RuntimeError(f"shard {shard} plane {plane} exceeds uint16 advance")
            letter = "h" if plane == 0 else "l"
            destination = OUTPUT / f"score-{letter}{shard}.ttf"
            # The last zero-width, zero-HVAR glyph is the ordinary cmap target.
            # A supported UVS replaces it with one of the preceding score glyphs;
            # an unsupported or split sequence therefore remains measurably zero.
            font_rows = np.vstack((selected, np.zeros((1, selected.shape[1]), dtype=np.int16)))
            base_advances = np.concatenate((
                np.full(len(selected), common_base, dtype=np.int32),
                np.zeros(1, dtype=np.int32),
            ))
            build_direct_font_backend(
                font_rows,
                destination,
                signed_axes=True,
                base_advance=base_advances,
                codepoint_start=0x20000,
                axis_tags=[
                    head.global_axis_tag(dimension)
                    for dimension in range(start, stop)
                ],
            )
            install_cmap14(destination, face)
            font_paths.append(destination)
            face_bases.append(common_base)
            face_ranges.append({
                "face": face,
                "shard": shard,
                "plane": plane,
                "scoreRows": int(len(selected)),
                "fontRows": int(len(font_rows)),
                "baseCodepoints": list(face_base_codepoints(face)),
                "maximumL1": int(np.max(l1)),
                "commonBase": common_base,
                "fixtureMinimumCssWidth": float(
                    np.min(common_base + fixture_hidden[:, start:stop] @ selected.T)
                    * display_scale
                    * (256 if plane == 0 else 1)
                ),
                "fixtureMaximumCssWidth": float(
                    np.max(common_base + fixture_hidden[:, start:stop] @ selected.T)
                    * display_scale
                    * (256 if plane == 0 else 1)
                ),
                "theoreticalMaximumCssWidth": float(
                    (common_base + int(np.max(l1)))
                    * display_scale
                    * (256 if plane == 0 else 1)
                ),
                "cmap14Mappings": len(GROUPS) * head.GROUP_SIZE,
            })
            face += 1

    (OUTPUT / "index.html").write_text(render_html())
    maximum_fixture_face_width = max(
        face_range["fixtureMaximumCssWidth"] for face_range in face_ranges
    )
    if maximum_fixture_face_width >= CHROME_ADVANCE_CEILING_PX:
        raise RuntimeError(
            f"display scale {display_scale} reaches {maximum_fixture_face_width}px, "
            f"above Chrome's {CHROME_ADVANCE_CEILING_PX}px ceiling"
        )
    (OUTPUT / "index.css").write_text(
        render_css(fine_reference, face_bases, display_scale)
    )
    oracle = fixture_oracle(fine_reference, quantized_embeddings, baseline_reference)
    ttf_bytes = sum(path.stat().st_size for path in font_paths)
    woff2_bytes = sum(path.with_suffix(".woff2").stat().st_size for path in font_paths)
    reference = {
        "model": "openai-community/gpt2",
        "backend": "cmap14-uvs-global-int16-high-residual-hvar",
        "groupIds": list(GROUPS),
        "groupIndexById": {str(group): index for index, group in enumerate(GROUPS)},
        "groups": len(GROUPS),
        "fullVocabularyGroups": fine_reference["groups"],
        "groupSize": head.GROUP_SIZE,
        "glyphPositions": head.GROUP_SIZE,
        "scoreGlyphRowsPerFace": SCORE_ROWS,
        "glyphRowsPerFace": SCORE_ROWS + 1,
        "shards": fine_reference["shards"],
        "planes": fine_reference["planes"],
        "inputRange": fine_reference["inputRange"],
        "weightScale": fine_reference["weightScale"],
        "sourceDisplayScale": fine_reference["displayScale"],
        "displayScale": display_scale,
        "fontSizePx": display_scale * UNITS_PER_EM,
        "decodeScaleMultiplier": fine_reference["displayScale"] / display_scale,
        "chromeAdvanceCeilingPx": CHROME_ADVANCE_CEILING_PX,
        "maximumFixtureFaceWidthPx": maximum_fixture_face_width,
        "maximumTheoreticalFaceWidthPx": max(
            face_range["theoreticalMaximumCssWidth"] for face_range in face_ranges
        ),
        "scoreScale": fine_reference["scoreScale"],
        "scoreStridePx": fine_reference["scoreStridePx"],
        "baselineDirectory": BASELINE_NAME,
        "baselineFineWoff2Bytes": fine_reference["fontBytes"],
        "baselineDispatchCssBytes": baseline_reference["cssBytes"],
        "existingBoundedBucketDelta": gsub_results["maximumAbsoluteCandidateDelta"],
        "variationSelectors": list(variation_selectors()),
        "baseCodepointRange": [
            BASE_CODEPOINT_START,
            BASE_CODEPOINT_START + FACE_COUNT * len(GROUPS) - 1,
        ],
        "topology": {
            "candidateElements": head.GROUP_SIZE,
            "faceSpans": FACE_COUNT * head.GROUP_SIZE,
            "groupSpecificDomElements": 0,
            "groupRuleBaseDeclarations": len(GROUPS) * FACE_COUNT,
            "domOrder": "O(faces*candidates)",
            "groupRuleOrder": "O(groups*faces)",
        },
        "fontTtfBytes": ttf_bytes,
        "fontWoff2Bytes": woff2_bytes,
        "expandedToWoff2Ratio": ttf_bytes / woff2_bytes,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
        "faceRanges": face_ranges,
        "fixtures": oracle,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in {"faceRanges", "fixtures", "variationSelectors"}
    }, indent=2))


if __name__ == "__main__":
    main()
