#!/usr/bin/env python3
"""Build a static hot-font subset for the mixed-precision hot-two probe.

This builder intentionally does not launch a browser. It preserves the existing
mixed experiment, subsets the exact global-int16 bank to tokens 0..511, and
emits an isolated page whose in-place hot rows use only the local subset faces.
The existing full exact faces remain available to the dynamically gated
non-hot fine stages through the inherited one-step stylesheet.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from fontTools import subset
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head_twoplane as fine_builder
import build_mixed_precision_hot2_upper_probe as mixed


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper-subset"
SOURCE_PROBE = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
ONE_STEP = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
)
FULL_BANK_EXPECTED_BYTES = 79_431_996
HOT_TOKEN_START = min(mixed.HOT_GROUPS) * mixed.head.GROUP_SIZE
HOT_TOKEN_STOP = (max(mixed.HOT_GROUPS) + 1) * mixed.head.GROUP_SIZE
HOT_TOKEN_COUNT = HOT_TOKEN_STOP - HOT_TOKEN_START
FONT_SPECS = tuple(
    (
        f"Score{plane.upper()}{shard}",
        f"HotScore{plane.upper()}{shard}",
        f"score-{plane}{shard}.woff2",
        face,
    )
    for shard in range(6)
    for plane, face in (("h", shard * 2), ("l", shard * 2 + 1))
)


def subset_font(source: Path, destination: Path, unicodes: set[int]) -> None:
    """Subset one WOFF2 while retaining source glyph names and HVAR semantics."""
    if destination.exists() and destination.stat().st_mtime >= source.stat().st_mtime:
        return
    options = subset.Options()
    options.flavor = "woff2"
    options.glyph_names = True
    options.recalc_average_width = False
    options.recalc_max_context = False
    options.notdef_outline = True
    options.recommended_glyphs = True
    options.layout_features = "*"
    font = subset.load_font(str(source), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    subset.save_font(font, str(destination), options)


def axis_contract(font: TTFont) -> list[tuple[str, float, float, float]]:
    return [
        (axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
        for axis in font["fvar"].axes
    ]


def region_contract(font: TTFont) -> list[list[tuple[float, float, float]]]:
    regions = font["HVAR"].table.VarStore.VarRegionList.Region
    return [
        [
            (axis.StartCoord, axis.PeakCoord, axis.EndCoord)
            for axis in region.VarRegionAxis
        ]
        for region in regions
    ]


def validate_subset_font(
    source_path: Path,
    subset_path: Path,
    expected_codepoints: list[int],
) -> dict[str, Any]:
    source = TTFont(source_path, lazy=False)
    reduced = TTFont(subset_path, lazy=False)
    source_cmap = source.getBestCmap()
    reduced_cmap = reduced.getBestCmap()
    expected_set = set(expected_codepoints)
    if set(reduced_cmap) != expected_set:
        missing = sorted(expected_set - set(reduced_cmap))[:8]
        extra = sorted(set(reduced_cmap) - expected_set)[:8]
        raise RuntimeError(
            f"{subset_path.name}: cmap mismatch; missing={missing}, extra={extra}"
        )
    if not expected_set.issubset(source_cmap):
        raise RuntimeError(f"{source_path.name}: source cmap lacks hot codepoints")
    for codepoint in expected_codepoints:
        if reduced_cmap[codepoint] != source_cmap[codepoint]:
            raise RuntimeError(
                f"{subset_path.name}: U+{codepoint:04X} changed glyph mapping"
            )

    expected_glyph_order = [".notdef"] + [
        source_cmap[codepoint] for codepoint in expected_codepoints
    ]
    if reduced.getGlyphOrder() != expected_glyph_order:
        raise RuntimeError(f"{subset_path.name}: selected glyph order changed")
    if axis_contract(reduced) != axis_contract(source):
        raise RuntimeError(f"{subset_path.name}: fvar axis contract changed")
    if region_contract(reduced) != region_contract(source):
        raise RuntimeError(f"{subset_path.name}: HVAR region contract changed")

    source_hvar = source["HVAR"].table
    reduced_hvar = reduced["HVAR"].table
    if source_hvar.AdvWidthMap is not None or reduced_hvar.AdvWidthMap is not None:
        raise RuntimeError(
            f"{subset_path.name}: expected direct glyph-ID HVAR mapping"
        )
    if len(source_hvar.VarStore.VarData) != 1 or len(reduced_hvar.VarStore.VarData) != 1:
        raise RuntimeError(f"{subset_path.name}: unexpected HVAR VarData layout")
    source_data = source_hvar.VarStore.VarData[0]
    reduced_data = reduced_hvar.VarStore.VarData[0]
    if source_data.VarRegionIndex != reduced_data.VarRegionIndex:
        raise RuntimeError(f"{subset_path.name}: HVAR region indexes changed")
    if reduced_data.ItemCount != HOT_TOKEN_COUNT + 1:
        raise RuntimeError(f"{subset_path.name}: unexpected HVAR item count")

    source_order = source.getGlyphOrder()
    reduced_order = reduced.getGlyphOrder()
    source_ids = {name: index for index, name in enumerate(source_order)}
    reduced_ids = {name: index for index, name in enumerate(reduced_order)}
    hvar_rows_checked = 0
    for glyph in expected_glyph_order:
        source_id = source_ids[glyph]
        reduced_id = reduced_ids[glyph]
        if source["hmtx"][glyph] != reduced["hmtx"][glyph]:
            raise RuntimeError(f"{subset_path.name}: {glyph} hmtx changed")
        if source_data.Item[source_id] != reduced_data.Item[reduced_id]:
            raise RuntimeError(f"{subset_path.name}: {glyph} HVAR row changed")
        if source["gvar"].variations.get(glyph, []):
            raise RuntimeError(f"{source_path.name}: {glyph} has unexpected gvar data")
        if reduced["gvar"].variations.get(glyph, []):
            raise RuntimeError(f"{subset_path.name}: {glyph} has unexpected gvar data")
        hvar_rows_checked += 1

    return {
        "source": source_path.name,
        "subset": subset_path.name,
        "sourceBytes": source_path.stat().st_size,
        "subsetBytes": subset_path.stat().st_size,
        "codepoints": len(reduced_cmap),
        "glyphsIncludingNotdef": len(reduced_order),
        "firstCodepoint": f"U+{expected_codepoints[0]:04X}",
        "lastCodepoint": f"U+{expected_codepoints[-1]:04X}",
        "firstGlyph": reduced_cmap[expected_codepoints[0]],
        "lastGlyph": reduced_cmap[expected_codepoints[-1]],
        "axes": len(reduced["fvar"].axes),
        "hvarRegions": reduced_hvar.VarStore.VarRegionList.RegionCount,
        "hvarRowsCheckedIncludingNotdef": hvar_rows_checked,
        "directGlyphIdHvarMapping": True,
        "sha256": hashlib.sha256(subset_path.read_bytes()).hexdigest(),
    }


def subset_face_rules() -> str:
    rules = []
    for _full_family, hot_family, filename, _face in FONT_SPECS:
        subset_name = filename.replace(".woff2", "-hot2.woff2")
        adjustment = ";size-adjust:25600%" if "ScoreH" in hot_family else ""
        rules.append(
            f'@font-face{{font-family:{hot_family};src:url("{subset_name}") '
            f'format("woff2"){adjustment}}}'
        )
    return "".join(rules)


def build_page() -> tuple[str, str, dict[str, Any]]:
    html = (SOURCE_PROBE / "index.html").read_text()
    topology = (SOURCE_PROBE / "topology.css").read_text()
    html = html.replace(
        "Mixed-precision hot-two certified upper head",
        "Mixed-precision hot-two upper head with subset exact fonts",
        1,
    )

    fine_face_line = (FINE / "index.css").read_text().split("\n", 1)[0]
    inherited_full_faces = fine_face_line.replace(
        'url("score-',
        'url("../gpt2-hvar-grid-output-head-global16-twoplane/score-',
    )
    if not topology.startswith(inherited_full_faces):
        raise RuntimeError("mixed topology exact-face prefix changed")
    topology = topology[len(inherited_full_faces) :]

    full_families = ",".join(spec[0] for spec in FONT_SPECS)
    hot_families = ",".join(spec[1] for spec in FONT_SPECS)
    old_usage = f".mixed-hot-candidate{{font-family:{full_families};"
    new_usage = f".mixed-hot-candidate{{font-family:{hot_families};"
    if topology.count(old_usage) != 1:
        raise RuntimeError("mixed hot candidate family rule changed")
    topology = subset_face_rules() + topology.replace(old_usage, new_usage, 1)

    hot_candidate_tags = re.findall(
        r'<i class="candidate mixed-hot-candidate"[^>]*>.*?</i>', html
    )
    hot_candidates = re.findall(
        r'<i class="candidate mixed-hot-candidate"[^>]*>(.*?)</i>', html
    )
    dynamic_stage_count = len(
        re.findall(r'class="fine-stage dynamic-fine-stage[^\"]*"', html)
    )
    codepoints_by_face = [
        {ord(record[face]) for record in hot_candidates}
        for face in range(len(FONT_SPECS))
    ]
    expected_by_face = [
        {
            fine_builder.CODEPOINT_STARTS[face] + token
            for token in range(HOT_TOKEN_START, HOT_TOKEN_STOP)
        }
        for face in range(len(FONT_SPECS))
    ]
    checks = {
        "hotCandidateRows": len(hot_candidates),
        "eachHotRowHasTwelveGlyphs": all(
            len(record) == len(FONT_SPECS) for record in hot_candidates
        ),
        "hotMarkupCodepointsMatchSubset": codepoints_by_face == expected_by_face,
        "localSubsetFaceRules": topology.count("-hot2.woff2"),
        "hotRuleUsesSubsetFamilies": new_usage in topology,
        "hotRuleDoesNotUseFullFamilies": old_usage not in topology,
        "hotTopologyHasNoFullExactUrls": (
            "gpt2-hvar-grid-output-head-global16-twoplane/score-" not in topology
        ),
        "dynamicFineStages": dynamic_stage_count,
        "dynamicHotGateRetained": (
            "display:if(style(--group:0):none;style(--group:1):none;else:grid)"
            in topology
        ),
        "fullExactFallbackStylesheetRetained": (
            "../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css"
            in html
        ),
        "standardLowerTokenTieRetained": (
            "var(--local-tie)/64*1px" in topology
            and all(
                f"--local-tie:{255 - token % 256}" in row
                for token, row in enumerate(hot_candidate_tags)
            )
        ),
    }
    expected = {
        "hotCandidateRows": HOT_TOKEN_COUNT,
        "eachHotRowHasTwelveGlyphs": True,
        "hotMarkupCodepointsMatchSubset": True,
        "localSubsetFaceRules": len(FONT_SPECS),
        "hotRuleUsesSubsetFamilies": True,
        "hotRuleDoesNotUseFullFamilies": True,
        "hotTopologyHasNoFullExactUrls": True,
        "dynamicFineStages": mixed.STAGES,
        "dynamicHotGateRetained": True,
        "fullExactFallbackStylesheetRetained": True,
        "standardLowerTokenTieRetained": True,
    }
    if checks != expected:
        raise RuntimeError(f"static page contract failed: {checks}")
    return html, topology, checks


def main() -> None:
    started = time.perf_counter()
    required = (
        SOURCE_PROBE / "index.html",
        SOURCE_PROBE / "topology.css",
        FINE / "index.css",
        ONE_STEP / "index.css",
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)
    full_fonts = sorted(FINE.glob("score-*.woff2"))
    full_bank_bytes = sum(path.stat().st_size for path in full_fonts)
    if len(full_fonts) != len(FONT_SPECS):
        raise RuntimeError(f"expected 12 full exact fonts, found {len(full_fonts)}")
    if full_bank_bytes != FULL_BANK_EXPECTED_BYTES:
        raise RuntimeError(
            f"full exact bank changed: {full_bank_bytes:,} != "
            f"{FULL_BANK_EXPECTED_BYTES:,}"
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    font_reports = []
    for _full_family, _hot_family, filename, face in FONT_SPECS:
        source = FINE / filename
        destination = OUTPUT / filename.replace(".woff2", "-hot2.woff2")
        codepoints = [
            fine_builder.CODEPOINT_STARTS[face] + token
            for token in range(HOT_TOKEN_START, HOT_TOKEN_STOP)
        ]
        subset_font(source, destination, set(codepoints))
        font_reports.append(validate_subset_font(source, destination, codepoints))

    html, topology, page_checks = build_page()
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "topology.css").write_text(topology)
    subset_bytes = sum(item["subsetBytes"] for item in font_reports)
    reference = {
        "backend": "mixed-rowwise-int10-global-int16-hot2-upper-subset-static",
        "browserStatus": "not-run-by-design",
        "sourceBuilder": "tools/build_mixed_precision_hot2_upper_probe.py",
        "sourceExperiment": SOURCE_PROBE.name,
        "hotGroups": list(mixed.HOT_GROUPS),
        "hotTokens": [HOT_TOKEN_START, HOT_TOKEN_STOP - 1],
        "hotCandidateRows": HOT_TOKEN_COUNT,
        "exactFaces": len(FONT_SPECS),
        "tokenGlyphsPerFace": HOT_TOKEN_COUNT,
        "encodedTokenGlyphsAcrossFaces": HOT_TOKEN_COUNT * len(FONT_SPECS),
        "fullExactBank": {
            "fontFiles": len(full_fonts),
            "woff2Bytes": full_bank_bytes,
        },
        "hotSubsetBank": {
            "fontFiles": len(font_reports),
            "woff2Bytes": subset_bytes,
            "percentOfFullBank": subset_bytes / full_bank_bytes * 100,
            "bytesAvoidedOnHotOnlyRoute": full_bank_bytes - subset_bytes,
        },
        "initialCssFontRouting": {
            "hotRowsUseOnlyLocalSubsetFamilies": True,
            "fullExactFamiliesUsedOnlyByDynamicNonHotFineStages": True,
            "fullExactFontsCanRemainDemandLoadedOnHotOnlyRoute": True,
            "browserNetworkVerification": "not run by instruction",
        },
        "staticPageChecks": page_checks,
        "fontValidation": {
            "allFontsDecoded": True,
            "allCmapsExactly512Codepoints": all(
                item["codepoints"] == HOT_TOKEN_COUNT for item in font_reports
            ),
            "allGlyphOrdersPreserved": True,
            "allFvarAxesPreserved": all(item["axes"] == 128 for item in font_reports),
            "allHvarRegionsPreserved": all(
                item["hvarRegions"] == 256 for item in font_reports
            ),
            "allSelectedHvarRowsPreserved": True,
            "allDefaultAdvancesPreserved": True,
            "allSelectedGvarEntriesEmptyAsSource": True,
            "faces": font_reports,
        },
        "generatedBytes": {},
        "staticBuildSeconds": time.perf_counter() - started,
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("index.html", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    percent = reference["hotSubsetBank"]["percentOfFullBank"]
    avoided = reference["hotSubsetBank"]["bytesAvoidedOnHotOnlyRoute"]
    (OUTPUT / "RESULTS.md").write_text(
        f"""# Mixed-precision hot-2 upper: static exact-font subset

Browser status: **not run by instruction**.

The 512 in-place hot rows now use a local exact global-int16 subset. Each of the 12 high/residual shard faces contains exactly 512 token codepoints (plus `.notdef`), for 6,144 encoded token glyphs across the bank. Dynamic non-hot fallback rows retain the existing full exact-family path.

## Size

- Full exact WOFF2 bank: {full_bank_bytes:,} bytes across 12 files.
- Hot-two subset WOFF2 bank: {subset_bytes:,} bytes across 12 files.
- Subset/full ratio: {percent:.3f}%.
- Bytes avoidable on a hot-only route: {avoided:,}.

## Static loading topology

Yes: the initial hot-row CSS can avoid eagerly using the full exact fonts. `.mixed-hot-candidate` names only the 12 local `HotScore*` subset families. The full `Score*` families remain attached to the six dynamically gated `.fine-stage` fallbacks, which are `display:none` for groups 0 and 1. CSS font faces are demand-loaded, so this structure permits a hot-only route to fetch only the subset bank. Network behavior remains unmeasured because no browser was launched.

## Validation

- All 12 WOFF2 files decoded successfully.
- Every subset cmap is exactly its plane's 512 codepoints for tokens 0..511.
- Source codepoint-to-glyph names and selected glyph order are preserved (`y000` through `y511`).
- Every face retains the source 128-axis `fvar` contract and all 256 HVAR regions.
- All 513 direct glyph-ID HVAR rows per face (including `.notdef`) and all default advances match the source.
- The source and subset selected glyphs both have empty `gvar` entries; metric variation remains exclusively in HVAR.
- The standard lower-token tie geometry `(255 - local) / 64px` is unchanged.
- Static page routing checks pass: 512 hot rows, 12 local subset faces, six gated dynamic fallbacks, no full-bank URL or full-family use in the hot topology rule.
"""
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "browserStatus": reference["browserStatus"],
                "fullExactWoff2Bytes": full_bank_bytes,
                "hotSubsetWoff2Bytes": subset_bytes,
                "percentOfFullBank": percent,
                "bytesAvoidedOnHotOnlyRoute": avoided,
                "fontFiles": len(font_reports),
                "staticPageChecks": page_checks,
                "fontValidation": {
                    key: value
                    for key, value in reference["fontValidation"].items()
                    if key != "faces"
                },
                "staticBuildSeconds": reference["staticBuildSeconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
