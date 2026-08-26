#!/usr/bin/env python3
"""Build an eight-group GSUB scorer with score/complement bases merged.

The source scorer emits a variable score glyph followed by a static complement
glyph.  This probe keeps the source GSUB and HVAR tables byte-for-byte, adds the
matching complement advance to every selectable score glyph, and renders only
that score glyph.  A source-scale page exposes Chrome's adjusted-advance cap;
the primary page uses the largest convenient 1/64-pixel-aligned display scale
that clears the cap for all bounded fixtures.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gsub-merged-base-fine-scorer"
SOURCE = ROOT / "experiments" / "gsub-indexed-fine-scorer"
FINE_SOURCE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BASELINE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
BASELINE = ROOT / "experiments" / BASELINE_NAME
EXPECTED_GROUPS = (0, 1, 2, 17, 64, 96, 128, 195)
SOURCE_DISPLAY_SCALE = 0.1
SAFE_DISPLAY_SCALE = 0.0625
CHROME_ADVANCE_CEILING_PX = 32_768


def css_number(value: float) -> str:
    return head.css_number(float(value))


def table_digest(font: TTFont, tag: str) -> str:
    return hashlib.sha256(font.getTableData(tag)).hexdigest()


def alternate_map(font: TTFont) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            result.update(getattr(subtable, "alternates", {}))
    return result


def patch_face(source: Path, destination: Path, codepoint_start: int, groups: int) -> dict:
    """Patch selectable score advances while proving GSUB/HVAR stayed intact."""
    shutil.copyfile(source, destination)
    font = TTFont(destination, recalcTimestamp=False)
    before_hvar = table_digest(font, "HVAR")
    before_gsub = table_digest(font, "GSUB")
    glyph_order = font.getGlyphOrder()
    glyph_ids = {name: index for index, name in enumerate(glyph_order)}
    cmap = font.getBestCmap()
    alternates = alternate_map(font)
    metrics = font["hmtx"].metrics
    hvar = font["HVAR"].table
    if hvar.AdvWidthMap is not None:
        raise RuntimeError(f"{source.name}: expected implicit glyph-to-HVAR mapping")
    if len(hvar.VarStore.VarData) != 1:
        raise RuntimeError(f"{source.name}: expected one HVAR VarData table")
    items = hvar.VarStore.VarData[0].Item
    if len(items) != len(glyph_order):
        raise RuntimeError(f"{source.name}: HVAR item count does not match glyph count")

    common_bases: set[int] = set()
    patched_glyphs = 0
    zero_complements = 0
    mapping_audits = 0
    for local in range(head.GROUP_SIZE):
        source_score = cmap[codepoint_start + local]
        source_complement = cmap[codepoint_start + head.GROUP_SIZE + local]
        score_alternates = alternates[source_score]
        complement_alternates = alternates[source_complement]
        if len(score_alternates) != groups or len(complement_alternates) != groups:
            raise RuntimeError(
                f"{source.name}: local {local} has unexpected AlternateSet lengths "
                f"{len(score_alternates)}/{len(complement_alternates)}"
            )
        pairs = [(source_score, source_complement), *zip(score_alternates, complement_alternates)]
        for score_glyph, complement_glyph in pairs:
            score_width, score_lsb = metrics[score_glyph]
            complement_width, _ = metrics[complement_glyph]
            complement_item = items[glyph_ids[complement_glyph]]
            if any(complement_item):
                raise RuntimeError(
                    f"{source.name}: {complement_glyph} is not a zero-HVAR complement"
                )
            zero_complements += 1
            merged_width = int(score_width + complement_width)
            common_bases.add(merged_width)
            metrics[score_glyph] = (merged_width, score_lsb)
            patched_glyphs += 1
            mapping_audits += 1

    if len(common_bases) != 1:
        raise RuntimeError(f"{source.name}: merged bases are not constant: {sorted(common_bases)}")
    common_base = common_bases.pop()
    font.recalcTimestamp = False
    font.save(destination)
    patched = TTFont(destination, recalcTimestamp=False)
    after_hvar = table_digest(patched, "HVAR")
    after_gsub = table_digest(patched, "GSUB")
    if before_hvar != after_hvar or before_gsub != after_gsub:
        raise RuntimeError(f"{source.name}: GSUB or HVAR changed while patching hmtx")
    patched.flavor = "woff2"
    patched.save(destination.with_suffix(".woff2"))
    return {
        "source": source.name,
        "commonBase": common_base,
        "glyphs": len(glyph_order),
        "patchedSelectableScoreGlyphs": patched_glyphs,
        "zeroHvarComplementsAudited": zero_complements,
        "implicitHvarMappingsAudited": mapping_audits,
        "hvarSha256": after_hvar,
        "gsubSha256": after_gsub,
        "ttfBytes": destination.stat().st_size,
        "woff2Bytes": destination.with_suffix(".woff2").stat().st_size,
    }


def font_settings(reference: dict) -> str:
    return ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f'calc(var(--h{dimension})/{css_number(reference["inputRange"])})'
        for dimension in range(head.WIDTH)
    )


def font_faces(prefix: str, source: str) -> tuple[str, str]:
    rules: list[str] = []
    families: list[str] = []
    for shard in range(6):
        for plane, letter in (("H", "h"), ("L", "l")):
            family = f"{prefix}{plane}{shard}"
            adjustment = ";size-adjust:25600%" if plane == "H" else ""
            rules.append(
                f'@font-face{{font-family:{family};src:url("{source}/score-{letter}{shard}.woff2") '
                f'format("woff2"){adjustment}}}'
            )
            families.append(family)
    return "".join(rules), ",".join(families)


def merged_html(css_name: str, title: str) -> str:
    candidates: list[str] = []
    for local in range(head.GROUP_SIZE):
        glyphs = "".join(chr(start + local) for start in fine.CODEPOINT_STARTS)
        candidates.append(
            f'<i class="candidate" data-local="{local}" '
            f'style="--local-tie:{head.GROUP_SIZE - 1 - local}">{glyphs}</i>'
        )
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f'<link rel="stylesheet" href="{css_name}">\n'
        f'<main id="gsub-stage" class="score-stage">{"".join(candidates)}</main>\n'
    )


def merged_css(reference: dict, face_audits: list[dict], display_scale: float) -> tuple[str, float, float]:
    faces, families = font_faces("MergedGSUB", ".")
    equivalent_base_units = sum(
        face_audits[2 * shard]["commonBase"] * 256
        + face_audits[2 * shard + 1]["commonBase"]
        for shard in range(6)
    )
    base_px = equivalent_base_units * display_scale
    factor = (
        reference["inputRange"]
        * reference["weightScale"]
        * reference["scoreScale"]
        * reference["scoreStridePx"]
        / display_scale
    )
    css = "\n".join((
        faces,
        '@property --probe-feature{syntax:"<integer>";inherits:true;initial-value:1}',
        '*{box-sizing:border-box}html,body{margin:0;overflow:clip}',
        '.score-stage{position:fixed;left:0;top:0;display:grid;'
        'grid-template-columns:max-content;grid-template-rows:1px;'
        'width:max-content;height:1px;'
        f'font-family:{families};font-size:{css_number(display_scale * 1000)}px;line-height:1;'
        f'font-variation-settings:{font_settings(reference)};'
        'font-feature-settings:"cv01" var(--probe-feature);'
        'font-kerning:none;font-synthesis:none;--score-offset:0px}',
        '.candidate{grid-area:1/1;display:block;justify-self:start;height:1px;'
        'overflow:hidden;white-space:pre;font-style:normal;'
        'width:calc-size(max-content,calc(round(nearest,'
        f'(size - {css_number(base_px)}px)*{css_number(factor)} '
        '+ var(--score-offset),4px) + var(--local-tie)/64*1px))}',
    )) + "\n"
    return css, base_px, factor


def fine_face_advances() -> list[list[int]]:
    advances: list[list[int]] = []
    for shard in range(6):
        pair: list[list[int]] = []
        for plane, letter in ((0, "h"), (1, "l")):
            font = TTFont(FINE_SOURCE / f"score-{letter}{shard}.ttf", recalcTimestamp=False)
            cmap = font.getBestCmap()
            metrics = font["hmtx"].metrics
            start = fine.CODEPOINT_STARTS[2 * shard + plane]
            pair.append([
                int(metrics[cmap[start + token]][0]) for token in range(head.VOCABULARY)
            ])
        advances.append([
            pair[0][token] * 256 + pair[1][token] for token in range(head.VOCABULARY)
        ])
    return advances


def css_if(branches: list[tuple[int, str]]) -> str:
    return "if(" + ";".join(
        f"style(--group:{group}):{value}" for group, value in branches
    ) + f";else:{branches[0][1]})"


def matched_exact_html() -> str:
    candidates = "".join(
        f'<i class="exact-candidate" data-local="{local}" '
        f'style="--local-tie:{head.GROUP_SIZE - 1 - local}"></i>'
        for local in range(head.GROUP_SIZE)
    )
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<title>Matched-scale exact CSS-dispatch audit</title>\n'
        '<link rel="stylesheet" href="matched-exact.css">\n'
        f'<main id="exact-stage" class="score-stage">{candidates}</main>\n'
    )


def matched_exact_css(reference: dict, advances: list[list[int]]) -> tuple[str, float]:
    faces, families = font_faces(
        "MergedMatchedExact", "../gpt2-hvar-grid-output-head-global16-twoplane"
    )
    factor = (
        reference["inputRange"]
        * reference["weightScale"]
        * reference["scoreScale"]
        * reference["scoreStridePx"]
        / SAFE_DISPLAY_SCALE
    )
    rules: list[str] = []
    for local in range(head.GROUP_SIZE):
        base_branches: list[tuple[int, str]] = []
        glyph_branches: list[tuple[int, str]] = []
        for group in EXPECTED_GROUPS:
            token = group * head.GROUP_SIZE + local
            equivalent_base = sum(face[token] for face in advances)
            glyphs = "".join(chr(start + token) for start in fine.CODEPOINT_STARTS)
            base_branches.append(
                (group, f"{css_number(equivalent_base * SAFE_DISPLAY_SCALE)}px")
            )
            glyph_branches.append((group, json.dumps(glyphs, ensure_ascii=False)))
        rules.append(
            f'.exact-candidate:nth-child({local + 1}){{'
            f'--exact-base:{css_if(base_branches)};'
            f'--exact-glyphs:{css_if(glyph_branches)}}}'
        )
    css = (
        faces
        + '\n@property --group{syntax:"<integer>";inherits:true;initial-value:0}\n'
        + '*{box-sizing:border-box}html,body{margin:0;overflow:clip}\n'
        + '.score-stage{position:fixed;left:0;top:0;display:grid;'
        + 'grid-template-columns:max-content;grid-template-rows:1px;'
        + 'width:max-content;height:1px;'
        + f'font-family:{families};font-size:{css_number(SAFE_DISPLAY_SCALE * 1000)}px;line-height:1;'
        + f'font-variation-settings:{font_settings(reference)};'
        + 'font-kerning:none;font-synthesis:none;--score-offset:0px}\n'
        + '.exact-candidate{grid-area:1/1;display:block;justify-self:start;height:1px;'
        + 'overflow:hidden;white-space:pre;font-style:normal;'
        + 'width:calc-size(max-content,calc(round(nearest,'
        + f'(size - var(--exact-base))*{css_number(factor)} '
        + '+ var(--score-offset),4px) + var(--local-tie)/64*1px))}\n'
        + '.exact-candidate::before{content:var(--exact-glyphs)}\n'
        + "".join(rules)
        + "\n"
    )
    return css, factor


def bounded_high_advances(reference: dict, face_audits: list[dict]) -> list[dict]:
    hidden = np.asarray(reference["fixtures"]["hiddenVectors"], dtype=np.float64)
    normalized = hidden / reference["inputRange"]
    audits: list[dict] = []
    for shard in range(6):
        font = TTFont(OUTPUT / f"score-h{shard}.ttf", recalcTimestamp=False)
        cmap = font.getBestCmap()
        alternates = alternate_map(font)
        items = font["HVAR"].table.VarStore.VarData[0].Item
        order = {name: index for index, name in enumerate(font.getGlyphOrder())}
        start = fine.CODEPOINT_STARTS[2 * shard]
        maximum_units = float("-inf")
        minimum_units = float("inf")
        for local in range(head.GROUP_SIZE):
            source = cmap[start + local]
            selectable = alternates[source]
            for glyph in selectable:
                item = np.asarray(items[order[glyph]], dtype=np.float64)
                # Signed axes serialize each coefficient as (-w, +w).  For an
                # axis value x, exactly one side contributes abs(x), yielding w*x.
                weights = item.reshape(-1, 2)[:, 1]
                values = face_audits[2 * shard]["commonBase"] + normalized[:, shard * fine.SHARD:(shard + 1) * fine.SHARD] @ weights
                maximum_units = max(maximum_units, float(values.max()))
                minimum_units = min(minimum_units, float(values.min()))
        audits.append({
            "shard": shard,
            "minimumFixtureAdvanceUnits": minimum_units,
            "maximumFixtureAdvanceUnits": maximum_units,
            "sourceScaleMaximumAdjustedPx": maximum_units * SOURCE_DISPLAY_SCALE * 256,
            "safeScaleMaximumAdjustedPx": maximum_units * SAFE_DISPLAY_SCALE * 256,
            "sourceScaleExceedsCeiling": maximum_units * SOURCE_DISPLAY_SCALE * 256 >= CHROME_ADVANCE_CEILING_PX,
            "safeScaleExceedsCeiling": maximum_units * SAFE_DISPLAY_SCALE * 256 >= CHROME_ADVANCE_CEILING_PX,
        })
    return audits


def existing_exact_high_advances(reference: dict) -> list[dict]:
    """Audit cap exposure already present in the 0.1-scale exact comparator."""
    normalized = (
        np.asarray(reference["fixtures"]["hiddenVectors"], dtype=np.float64)
        / reference["inputRange"]
    )
    tokens = np.concatenate([
        np.arange(group * head.GROUP_SIZE, (group + 1) * head.GROUP_SIZE)
        for group in EXPECTED_GROUPS
    ])
    audits: list[dict] = []
    for shard in range(6):
        font = TTFont(FINE_SOURCE / f"score-h{shard}.ttf", recalcTimestamp=False)
        cmap = font.getBestCmap()
        order = {name: index for index, name in enumerate(font.getGlyphOrder())}
        items = font["HVAR"].table.VarStore.VarData[0].Item
        metrics = font["hmtx"].metrics
        start = fine.CODEPOINT_STARTS[2 * shard]
        advances = []
        for token in tokens:
            glyph = cmap[start + int(token)]
            weights = np.asarray(items[order[glyph]], dtype=np.float64).reshape(-1, 2)[:, 1]
            advances.append(
                metrics[glyph][0]
                + normalized[:, shard * fine.SHARD:(shard + 1) * fine.SHARD] @ weights
            )
        values = np.asarray(advances)
        adjusted = values * SOURCE_DISPLAY_SCALE * 256
        overflow = adjusted >= CHROME_ADVANCE_CEILING_PX
        audits.append({
            "shard": shard,
            "candidateFixtureMeasurements": int(overflow.size),
            "overflowingMeasurements": int(overflow.sum()),
            "tokenRowsOverflowingAtLeastOnce": int(np.any(overflow, axis=1).sum()),
            "maximumAdjustedPx": float(adjusted.max()),
        })
    return audits


def main() -> None:
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    fine_reference = json.loads((FINE_SOURCE / "reference.json").read_text())
    baseline_reference = json.loads((BASELINE / "reference.json").read_text())
    if tuple(source_reference["groupIds"]) != EXPECTED_GROUPS or source_reference["groups"] != 8:
        raise RuntimeError("source is not the established bounded eight-group scorer")
    if source_reference["displayScale"] != SOURCE_DISPLAY_SCALE:
        raise RuntimeError("source display scale changed")
    # Cases are the bounded group oracle generated by the source experiment;
    # the hidden vectors and floors must be the exact production fixtures.
    if source_reference["fixtures"]["hiddenVectors"] != baseline_reference["certifiedFixtures"]["hiddenVectors"]:
        raise RuntimeError("fixture hidden vectors differ from the exact baseline")
    if source_reference["fixtures"]["scoreFloors"] != baseline_reference["certifiedFixtures"]["scoreFloors"]:
        raise RuntimeError("fixture score floors differ from the exact baseline")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    face_audits: list[dict] = []
    for shard in range(6):
        for plane, letter in ((0, "h"), (1, "l")):
            source = SOURCE / f"score-{letter}{shard}.ttf"
            destination = OUTPUT / source.name
            face_audits.append(
                patch_face(
                    source,
                    destination,
                    fine.CODEPOINT_STARTS[2 * shard + plane],
                    source_reference["groups"],
                )
            )

    safe_css, safe_base_px, safe_factor = merged_css(
        source_reference, face_audits, SAFE_DISPLAY_SCALE
    )
    source_css, source_base_px, source_factor = merged_css(
        source_reference, face_audits, SOURCE_DISPLAY_SCALE
    )
    matched_css, matched_factor = matched_exact_css(fine_reference, fine_face_advances())
    if safe_factor != matched_factor:
        raise RuntimeError("safe merged and matched exact geometry factors differ")
    (OUTPUT / "index.html").write_text(
        merged_html("index.css", "Safe-scale GSUB merged-base fine scorer")
    )
    (OUTPUT / "index.css").write_text(safe_css)
    (OUTPUT / "source-scale.html").write_text(
        merged_html("source-scale.css", "Source-scale GSUB merged-base cap audit")
    )
    (OUTPUT / "source-scale.css").write_text(source_css)
    (OUTPUT / "matched-exact.html").write_text(matched_exact_html())
    (OUTPUT / "matched-exact.css").write_text(matched_css)

    high_advances = bounded_high_advances(source_reference, face_audits)
    exact_high_advances = existing_exact_high_advances(source_reference)
    if not any(face["sourceScaleExceedsCeiling"] for face in high_advances):
        raise RuntimeError("expected the source-scale merged construction to exceed Chrome's ceiling")
    if any(face["safeScaleExceedsCeiling"] for face in high_advances):
        raise RuntimeError("safe display scale still exceeds Chrome's ceiling on bounded fixtures")
    generated_names = (
        "index.html", "index.css", "source-scale.html", "source-scale.css",
        "matched-exact.html", "matched-exact.css",
    )
    reference = {
        "model": source_reference["model"],
        "backend": "bounded-cv01-gsub-single-glyph-merged-base",
        "boundedOnly": True,
        "fullBuildPerformed": False,
        "groupIds": list(EXPECTED_GROUPS),
        "feature": source_reference["feature"],
        "featureValues": source_reference["featureValues"],
        "groups": len(EXPECTED_GROUPS),
        "groupSize": head.GROUP_SIZE,
        "glyphsPerCandidate": 12,
        "sourceGlyphsPerCandidate": 24,
        "domCandidateNodes": head.GROUP_SIZE,
        "fixtures": source_reference["fixtures"],
        "expectedCandidateBuckets": 10 * len(EXPECTED_GROUPS) * head.GROUP_SIZE,
        "inputRange": source_reference["inputRange"],
        "weightScale": source_reference["weightScale"],
        "scoreScale": source_reference["scoreScale"],
        "scoreStridePx": source_reference["scoreStridePx"],
        "sourceDisplayScale": SOURCE_DISPLAY_SCALE,
        "safeDisplayScale": SAFE_DISPLAY_SCALE,
        "safeScaleLayoutUnitsPerLowFontUnit": SAFE_DISPLAY_SCALE * 64,
        "safeScaleLayoutUnitsPerHighFontUnit": SAFE_DISPLAY_SCALE * 256 * 64,
        "chromeAdvanceCeilingPx": CHROME_ADVANCE_CEILING_PX,
        "safeEquivalentBasePx": safe_base_px,
        "sourceEquivalentBasePx": source_base_px,
        "safeGeometryFactor": safe_factor,
        "sourceGeometryFactor": source_factor,
        "baselineDirectory": BASELINE_NAME,
        "matchedExactPage": "matched-exact.html",
        "sourceScalePage": "source-scale.html",
        "sourceGsubDirectory": "gsub-indexed-fine-scorer",
        "sourceFineDirectory": "gpt2-hvar-grid-output-head-global16-twoplane",
        "faceAudits": face_audits,
        "boundedHighPlaneAdvanceAudit": high_advances,
        "existingExactHighPlaneAdvanceAudit": exact_high_advances,
        "fontTtfBytes": sum(face["ttfBytes"] for face in face_audits),
        "fontWoff2Bytes": sum(face["woff2Bytes"] for face in face_audits),
        "projectedMergedFullWoff2Bytes": source_reference["baselineFineWoff2Bytes"],
        "generatedMarkupCssBytes": sum((OUTPUT / name).stat().st_size for name in generated_names),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
        "limitations": [
            "The cap audit and semantic comparison cover eight spread groups and ten fixtures only.",
            "The safe scale clears the ceiling for observed bounded advances, not every corner of the 768-axis normalized cube.",
            "The matched-scale exact page is diagnostic; the existing production exact CSS-dispatch page remains the primary comparator.",
        ],
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in {"fixtures", "faceAudits", "limitations"}
    }, indent=2))


if __name__ == "__main__":
    main()
