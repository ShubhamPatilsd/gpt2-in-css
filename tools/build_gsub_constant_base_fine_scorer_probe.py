#!/usr/bin/env python3
"""Build the constant-base, single-glyph GSUB fine-scorer experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine
import build_gsub_indexed_fine_scorer_probe as indexed
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_matrix_backend_prototypes import UNITS_PER_EM, build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "experiments" / "gsub-constant-base-fine-scorer"
FINE_ROOT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BASELINE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
BASELINE_ROOT = ROOT / "experiments" / BASELINE_NAME
DEFAULT_GROUPS = indexed.DEFAULT_GROUPS
BASE_MARGIN = 32
CHROME_ADVANCE_CEILING_PX = 32_768
# Forty-axis shards are the widest bounded partition whose theoretical high-plane
# advance remains below Chromium's 32,768px adjusted-advance clamp. The HVAR
# coefficients themselves are unchanged; only their face partition is narrower.
SHARD = 40
SHARD_COUNT = (head.WIDTH + SHARD - 1) // SHARD
FACE_CODEPOINT_STARTS = tuple(
    0xF0000 + face * head.GROUP_SIZE for face in range(2 * SHARD_COUNT)
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="build all vocabulary groups under the experiment's full/ directory",
    )
    parser.add_argument(
        "--groups",
        help="comma-separated global group IDs (default: eight spread groups)",
    )
    return parser.parse_args()


def selected_token_rows(groups: tuple[int, ...]) -> np.ndarray:
    """Return a rectangular group/local token table, padding the final group."""
    rows = []
    for group in groups:
        tokens = np.arange(
            group * head.GROUP_SIZE,
            min((group + 1) * head.GROUP_SIZE, head.VOCABULARY),
            dtype=int,
        )
        rows.append(np.pad(tokens, (0, head.GROUP_SIZE - len(tokens)), mode="edge"))
    return np.stack(rows)


def verify_numbered_feature(font_path: Path, groups: int, codepoint_start: int) -> dict:
    """Verify every local cmap input has the intended numbered alternate set."""
    font = TTFont(font_path, recalcTimestamp=False)
    cmap = {}
    for table in font["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    expected_cmap = {
        codepoint_start + local: indexed.output_glyph(local)
        for local in range(head.GROUP_SIZE)
    }
    if cmap != expected_cmap:
        raise RuntimeError(f"{font_path.name} local cmap does not line up with y000..y255")
    alternates: dict[str, list[str]] = {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            alternates.update(getattr(subtable, "alternates", {}))
    if len(alternates) != head.GROUP_SIZE:
        raise RuntimeError(
            f"{font_path.name} compiled {len(alternates)} local substitutions"
        )
    for local in range(head.GROUP_SIZE):
        source = indexed.output_glyph(local)
        expected = [
            indexed.output_glyph(group * head.GROUP_SIZE + local)
            for group in range(groups)
        ]
        if alternates.get(source) != expected:
            raise RuntimeError(f"{font_path.name} has an incorrect cv01 row for {source}")
    return {
        "cmapEntries": len(cmap),
        "cmapFirst": [codepoint_start, cmap[codepoint_start]],
        "cmapLast": [
            codepoint_start + head.GROUP_SIZE - 1,
            cmap[codepoint_start + head.GROUP_SIZE - 1],
        ],
        "cv01Sources": len(alternates),
        "alternatesPerSource": groups,
        "firstSourceAlternates": alternates[indexed.output_glyph(0)],
        "lastSourceAlternates": alternates[
            indexed.output_glyph(head.GROUP_SIZE - 1)
        ],
    }


def render_html() -> str:
    candidates = []
    for local in range(head.GROUP_SIZE):
        glyphs = "".join(chr(start + local) for start in FACE_CODEPOINT_STARTS)
        candidates.append(
            f'<i class="candidate" data-local="{local}" '
            f'style="--local-tie:{head.GROUP_SIZE - 1 - local}">{glyphs}</i>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Constant-base GSUB GPT-2 fine scorer</title>
<link rel="stylesheet" href="index.css">
<main id="gsub-stage" class="fine-stage">{''.join(candidates)}</main>
"""


def render_css(reference: dict, face_bases: list[int]) -> str:
    faces = []
    family = "ConstantGSUB"
    for shard in range(SHARD_COUNT):
        for plane_name, plane_letter in (("high", "h"), ("low", "l")):
            face = 2 * shard + (0 if plane_name == "high" else 1)
            codepoint_start = FACE_CODEPOINT_STARTS[face]
            adjustment = ";size-adjust:25600%" if plane_name == "high" else ""
            faces.append(
                f'@font-face{{font-family:{family};src:url("score-{plane_letter}{shard}.woff2") '
                f'format("woff2");unicode-range:U+{codepoint_start:X}-'
                f'U+{codepoint_start + head.GROUP_SIZE - 1:X}{adjustment}}}'
            )
    settings = ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f'calc(var(--h{dimension})/{head.css_number(reference["inputRange"])})'
        for dimension in range(head.WIDTH)
    )
    equivalent_base = sum(
        face_bases[2 * shard] * 256 + face_bases[2 * shard + 1]
        for shard in range(SHARD_COUNT)
    )
    factor = (
        reference["inputRange"]
        * reference["weightScale"]
        * reference["scoreScale"]
        * reference["scoreStridePx"]
        / reference["displayScale"]
    )
    font_size = reference["displayScale"] * UNITS_PER_EM
    return "\n".join((
        "".join(faces),
        '@property --probe-feature{syntax:"<integer>";inherits:true;initial-value:1}',
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
        ".fine-stage{position:fixed;left:0;top:0;display:grid;"
        "grid-template-columns:max-content;grid-template-rows:1px;"
        "width:max-content;height:1px;"
        f"font-family:{family};"
        f"font-size:{head.css_number(font_size)}px;line-height:1;"
        f"font-variation-settings:{settings};"
        'font-feature-settings:"cv01" var(--probe-feature);'
        "font-kerning:none;font-synthesis:none;--score-offset:0px}",
        ".candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal;"
        "width:calc-size(max-content,calc(round(nearest,"
        f"(size - {head.css_number(equivalent_base * reference['displayScale'])}px)"
        f"*{head.css_number(factor)} + var(--score-offset),4px)"
        " + var(--local-tie)/64*1px))}",
    )) + "\n"


def main() -> None:
    args = parse_args()
    fine_reference = json.loads((FINE_ROOT / "reference.json").read_text())
    baseline_reference = json.loads((BASELINE_ROOT / "reference.json").read_text())
    groups = indexed.selected_groups(args, fine_reference["groups"])
    output = OUTPUT_ROOT / "full" if args.full else OUTPUT_ROOT
    output.mkdir(parents=True, exist_ok=True)

    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    codes = np.rint(embeddings / fine_reference["weightScale"]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * fine_reference["weightScale"]
    token_rows = selected_token_rows(groups)
    selected_tokens = token_rows.reshape(-1)

    font_paths: list[Path] = []
    face_bases: list[int] = []
    face_ranges: list[dict] = []
    mapping_audits: list[dict] = []
    fixture_hidden = np.asarray(
        baseline_reference["certifiedFixtures"]["hiddenVectors"], dtype=np.float64
    ) / fine_reference["inputRange"]

    for shard, start in enumerate(range(0, head.WIDTH, SHARD)):
        stop = min(start + SHARD, head.WIDTH)
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        for plane, values in enumerate((high, residual)):
            selected = values[selected_tokens]
            l1 = np.sum(np.abs(selected.astype(np.int64)), axis=1).astype(np.int32)
            maximum_l1 = int(np.max(l1))
            common_base = maximum_l1 + BASE_MARGIN
            maximum_advance = common_base + maximum_l1
            if maximum_advance > 65_535:
                raise RuntimeError(
                    f"shard {shard} plane {plane}: {common_base} + "
                    f"{maximum_l1} exceeds uint16 advance"
                )

            letter = "h" if plane == 0 else "l"
            destination = output / f"score-{letter}{shard}.ttf"
            build_direct_font_backend(
                selected,
                destination,
                signed_axes=True,
                base_advance=common_base,
                codepoint_start=FACE_CODEPOINT_STARTS[2 * shard + plane],
                axis_tags=[
                    head.global_axis_tag(dimension)
                    for dimension in range(start, stop)
                ],
            )
            indexed.keep_local_cmap(
                destination, FACE_CODEPOINT_STARTS[2 * shard + plane]
            )
            indexed.add_numbered_feature(
                destination,
                [(np.arange(head.GROUP_SIZE), np.arange(len(selected)).reshape(
                    len(groups), head.GROUP_SIZE
                ))],
            )
            mapping_audit = verify_numbered_feature(
                destination, len(groups), FACE_CODEPOINT_STARTS[2 * shard + plane]
            )
            font_paths.append(destination)
            face_bases.append(common_base)

            adjusted_scale = fine_reference["displayScale"] * (256 if plane == 0 else 1)
            fixture_widths = (
                common_base + fixture_hidden[:, start:stop] @ selected.T
            ) * adjusted_scale
            face_ranges.append({
                "family": "ConstantGSUB",
                "codepointStart": FACE_CODEPOINT_STARTS[2 * shard + plane],
                "shard": shard,
                "plane": plane,
                "rows": int(len(selected)),
                "maximumL1": maximum_l1,
                "commonBase": common_base,
                "baseMargin": BASE_MARGIN,
                "maximumAdvance": maximum_advance,
                "uint16AdvanceSafe": maximum_advance <= 65_535,
                "fixtureMinimumAdjustedAdvancePx": float(np.min(fixture_widths)),
                "fixtureMaximumAdjustedAdvancePx": float(np.max(fixture_widths)),
                "theoreticalMaximumAdjustedAdvancePx": maximum_advance * adjusted_scale,
            })
            mapping_audits.append({
                "shard": shard,
                "plane": plane,
                **mapping_audit,
            })

    if max(
        item["theoreticalMaximumAdjustedAdvancePx"] for item in face_ranges
    ) >= CHROME_ADVANCE_CEILING_PX:
        raise RuntimeError("narrow faces still reach Chrome's adjusted-advance ceiling")

    (output / "index.html").write_text(render_html())
    (output / "index.css").write_text(render_css(fine_reference, face_bases))
    oracle = indexed.fixture_oracle(
        groups, fine_reference, quantized_embeddings, baseline_reference
    )
    ttf_bytes = sum(path.stat().st_size for path in font_paths)
    woff2_bytes = sum(path.with_suffix(".woff2").stat().st_size for path in font_paths)
    reference = {
        "model": "openai-community/gpt2",
        "backend": "cv01-numbered-gsub-constant-base-single-glyph-global-int16-hvar",
        "feature": "cv01",
        "groupIds": list(groups),
        "featureValues": {
            str(group): feature for feature, group in enumerate(groups, start=1)
        },
        "groups": len(groups),
        "fullVocabularyGroups": fine_reference["groups"],
        "fullBuild": args.full,
        "groupSize": head.GROUP_SIZE,
        "glyphPositions": head.GROUP_SIZE,
        "scoreGlyphRowsPerFace": len(groups) * head.GROUP_SIZE,
        "glyphRowsPerFace": len(groups) * head.GROUP_SIZE,
        "glyphsPerFacePerCandidate": 1,
        "correctionGlyphsPerFacePerCandidate": 0,
        "sourceShards": fine_reference["shards"],
        "shards": SHARD_COUNT,
        "dimensionsPerShard": SHARD,
        "planes": fine_reference["planes"],
        "faces": len(face_ranges),
        "inputRange": fine_reference["inputRange"],
        "weightScale": fine_reference["weightScale"],
        "displayScale": fine_reference["displayScale"],
        "fontSizePx": fine_reference["displayScale"] * UNITS_PER_EM,
        "scoreScale": fine_reference["scoreScale"],
        "scoreStridePx": fine_reference["scoreStridePx"],
        "baseMargin": BASE_MARGIN,
        "chromeAdvanceCeilingPx": CHROME_ADVANCE_CEILING_PX,
        "adjustedAdvanceMitigation": (
            "unchanged signed HVAR coefficients partitioned into 40-axis faces; "
            "every theoretical adjusted glyph advance remains below 32768px"
        ),
        "maximumFixtureAdjustedAdvancePx": max(
            item["fixtureMaximumAdjustedAdvancePx"] for item in face_ranges
        ),
        "maximumTheoreticalAdjustedAdvancePx": max(
            item["theoreticalMaximumAdjustedAdvancePx"] for item in face_ranges
        ),
        "baselineDirectory": BASELINE_NAME,
        "baselineFineWoff2Bytes": fine_reference["fontBytes"],
        "baselineDispatchCssBytes": baseline_reference["cssBytes"],
        "topology": {
            "candidateElements": head.GROUP_SIZE,
            "candidateDescendants": 0,
            "codepointsPerCandidate": len(FACE_CODEPOINT_STARTS),
            "shapedGlyphsPerCandidate": len(FACE_CODEPOINT_STARTS),
            "glyphsPerFacePerCandidate": 1,
            "perFaceInlineBoxes": 0,
        },
        "fontTtfBytes": ttf_bytes,
        "fontWoff2Bytes": woff2_bytes,
        "expandedToWoff2Ratio": ttf_bytes / woff2_bytes,
        "htmlBytes": (output / "index.html").stat().st_size,
        "cssBytes": (output / "index.css").stat().st_size,
        "faceRanges": face_ranges,
        "mappingAudits": mapping_audits,
        "fixtures": oracle,
    }
    (output / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in {"faceRanges", "mappingAudits", "fixtures", "featureValues"}
    }, indent=2))


if __name__ == "__main__":
    main()
