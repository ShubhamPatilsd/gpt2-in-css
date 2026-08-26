#!/usr/bin/env python3
"""Build the bounded 0.03125-scale GSUB lattice experiment.

This deliberately reuses the existing eight-group GSUB fonts.  It generates a
matched exact CSS-dispatch page from the source two-plane font metrics instead
of comparing against either predecessor page.
"""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gsub-lattice-scale-fine-scorer"
GSUB_SOURCE = ROOT / "experiments" / "gsub-indexed-fine-scorer"
FINE_SOURCE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
FULL_GSUB_SOURCE = GSUB_SOURCE / "full"
DISPLAY_SCALE = 0.03125
FONT_SIZE_PX = DISPLAY_SCALE * 1_000
CHROME_ADVANCE_CEILING_PX = 32_768
EXPECTED_GROUPS = (0, 1, 2, 17, 64, 96, 128, 195)
EXPECTED_CANDIDATE_BUCKETS = 10 * len(EXPECTED_GROUPS) * head.GROUP_SIZE
HISTORICAL_MAXIMUM_BUCKET_DELTA = 2
HISTORICAL_DIFFERING_BUCKETS = 4_553
HISTORICAL_WINNER_BUCKET_AGREEMENT = 0.825


def css_number(value: float) -> str:
    return head.css_number(float(value))


def font_settings(reference: dict) -> str:
    return ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f'calc(var(--h{dimension})/{css_number(reference["inputRange"])})'
        for dimension in range(head.WIDTH)
    )


def source_font_faces(prefix: str, source: str) -> tuple[str, str]:
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


def gsub_html() -> str:
    candidates: list[str] = []
    for local in range(head.GROUP_SIZE):
        glyphs = "".join(
            chr(start + local) + chr(start + head.GROUP_SIZE + local)
            for start in fine.CODEPOINT_STARTS
        )
        candidates.append(
            f'<i class="candidate" data-local="{local}" '
            f'style="--local-tie:{head.GROUP_SIZE - 1 - local}">{glyphs}</i>'
        )
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<title>GSUB lattice-scale fine scorer</title>\n'
        '<link rel="stylesheet" href="index.css">\n'
        f'<main id="gsub-stage" class="score-stage">{"".join(candidates)}</main>\n'
    )


def gsub_css(reference: dict) -> tuple[str, float, float]:
    faces, families = source_font_faces("LatticeGSUB", "../gsub-indexed-fine-scorer")
    equivalent_base_units = sum(
        reference["faceRanges"][2 * shard]["commonBase"] * 256
        + reference["faceRanges"][2 * shard + 1]["commonBase"]
        for shard in range(reference["shards"])
    )
    base_px = equivalent_base_units * DISPLAY_SCALE
    factor = (
        reference["inputRange"]
        * reference["weightScale"]
        * reference["scoreScale"]
        * reference["scoreStridePx"]
        / DISPLAY_SCALE
    )
    css = "\n".join((
        faces,
        '@property --probe-feature{syntax:"<integer>";inherits:true;initial-value:1}',
        '*{box-sizing:border-box}html,body{margin:0;overflow:clip}',
        '.score-stage{position:fixed;left:0;top:0;display:grid;'
        'grid-template-columns:max-content;grid-template-rows:1px;'
        'width:max-content;height:1px;'
        f'font-family:{families};font-size:{css_number(FONT_SIZE_PX)}px;line-height:1;'
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
    """Regenerate exact per-token base constants from source font hmtx data."""
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
            pair[0][token] * 256 + pair[1][token]
            for token in range(head.VOCABULARY)
        ])
    return advances


def exact_html() -> str:
    candidates = "".join(
        f'<i class="exact-candidate" data-local="{local}" '
        f'style="--local-tie:{head.GROUP_SIZE - 1 - local}"></i>'
        for local in range(head.GROUP_SIZE)
    )
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<title>Matched lattice-scale exact CSS dispatch</title>\n'
        '<link rel="stylesheet" href="exact.css">\n'
        f'<main id="exact-stage" class="score-stage">{candidates}</main>\n'
    )


def css_if(branches: list[tuple[int, str]]) -> str:
    return "if(" + ";".join(
        f"style(--group:{group}):{value}" for group, value in branches
    ) + f";else:{branches[0][1]})"


def exact_css(reference: dict, advances: list[list[int]]) -> tuple[str, float]:
    faces, families = source_font_faces(
        "LatticeExact", "../gpt2-hvar-grid-output-head-global16-twoplane"
    )
    factor = (
        reference["inputRange"]
        * reference["weightScale"]
        * reference["scoreScale"]
        * reference["scoreStridePx"]
        / DISPLAY_SCALE
    )
    candidate_rules: list[str] = []
    for local in range(head.GROUP_SIZE):
        base_branches: list[tuple[int, str]] = []
        glyph_branches: list[tuple[int, str]] = []
        for group in EXPECTED_GROUPS:
            token = group * head.GROUP_SIZE + local
            equivalent_base = sum(face[token] for face in advances)
            glyphs = "".join(chr(start + token) for start in fine.CODEPOINT_STARTS)
            base_branches.append((group, f"{css_number(equivalent_base * DISPLAY_SCALE)}px"))
            glyph_branches.append((group, json.dumps(glyphs, ensure_ascii=False)))
        candidate_rules.append(
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
        + f'font-family:{families};font-size:{css_number(FONT_SIZE_PX)}px;line-height:1;'
        + f'font-variation-settings:{font_settings(reference)};'
        + 'font-kerning:none;font-synthesis:none;--score-offset:0px}\n'
        + '.exact-candidate{grid-area:1/1;display:block;justify-self:start;height:1px;'
        + 'overflow:hidden;white-space:pre;font-style:normal;'
        + 'width:calc-size(max-content,calc(round(nearest,'
        + f'(size - var(--exact-base))*{css_number(factor)} '
        + '+ var(--score-offset),4px) + var(--local-tie)/64*1px))}\n'
        + '.exact-candidate::before{content:var(--exact-glyphs)}\n'
        + "".join(candidate_rules)
        + "\n"
    )
    return css, factor


def maximum_bounded_complement(reference: dict) -> dict:
    maximum: dict | None = None
    for shard in range(reference["shards"]):
        for plane, letter in ((0, "h"), (1, "l")):
            font = TTFont(GSUB_SOURCE / f"score-{letter}{shard}.ttf", recalcTimestamp=False)
            cmap = font.getBestCmap()
            metrics = font["hmtx"].metrics
            alternates: dict[str, list[str]] = {}
            for lookup in font["GSUB"].table.LookupList.Lookup:
                for subtable in lookup.SubTable:
                    alternates.update(getattr(subtable, "alternates", {}))
            start = fine.CODEPOINT_STARTS[2 * shard + plane]
            for local in range(head.GROUP_SIZE):
                source = cmap[start + head.GROUP_SIZE + local]
                for alternate_index, glyph in enumerate([source, *alternates[source]]):
                    units = int(metrics[glyph][0])
                    adjusted_px = units * DISPLAY_SCALE * (256 if plane == 0 else 1)
                    record = {
                        "shard": shard,
                        "plane": plane,
                        "local": local,
                        "alternateIndexIncludingDefault": alternate_index,
                        "fontUnits": units,
                        "adjustedPx": adjusted_px,
                    }
                    if maximum is None or adjusted_px > maximum["adjustedPx"]:
                        maximum = record
    assert maximum is not None
    return maximum


def known_full_h3_complement() -> dict:
    font = TTFont(FULL_GSUB_SOURCE / "base-h3.ttf", recalcTimestamp=False)
    units, glyph = max((advance, name) for name, (advance, _lsb) in font["hmtx"].metrics.items())
    return {
        "source": "existing full/base-h3.ttf (read-only; full bank not rebuilt)",
        "glyph": glyph,
        "fontUnits": int(units),
        "adjustedPx": int(units) * DISPLAY_SCALE * 256,
    }


def main() -> None:
    source_reference = json.loads((GSUB_SOURCE / "reference.json").read_text())
    fine_reference = json.loads((FINE_SOURCE / "reference.json").read_text())
    historical = json.loads((GSUB_SOURCE / "browser-results.json").read_text())
    if tuple(source_reference["groupIds"]) != EXPECTED_GROUPS or source_reference["groups"] != 8:
        raise RuntimeError("source is not the exact bounded eight-group GSUB bank")
    if source_reference["displayScale"] != 0.1 or fine_reference["displayScale"] != 0.1:
        raise RuntimeError("source display scale changed; regenerate formulas deliberately")
    if len(source_reference["fixtures"]["cases"]) != 10:
        raise RuntimeError("expected ten bounded fixtures")
    for name in [f"score-{letter}{shard}.woff2" for shard in range(6) for letter in ("h", "l")]:
        if not (GSUB_SOURCE / name).is_file():
            raise FileNotFoundError(GSUB_SOURCE / name)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    gsub_style, gsub_base_px, gsub_factor = gsub_css(source_reference)
    advances = fine_face_advances()
    exact_style, exact_factor = exact_css(fine_reference, advances)
    if gsub_factor != exact_factor:
        raise RuntimeError("lattice GSUB and exact baseline geometry factors differ")
    (OUTPUT / "index.html").write_text(gsub_html())
    (OUTPUT / "index.css").write_text(gsub_style)
    (OUTPUT / "exact.html").write_text(exact_html())
    (OUTPUT / "exact.css").write_text(exact_style)

    bounded_complement = maximum_bounded_complement(source_reference)
    full_h3 = known_full_h3_complement()
    if full_h3["fontUnits"] != 1_317 or full_h3["adjustedPx"] != 10_536:
        raise RuntimeError(f"unexpected known full h3 complement: {full_h3}")
    if full_h3["adjustedPx"] >= CHROME_ADVANCE_CEILING_PX:
        raise RuntimeError("lattice scale does not clear the known full h3 complement")

    source_high_maximum = max(
        face["maximumAdvance"] for face in fine_reference["faceRanges"]
        if face["plane"] == 0
    )
    source_low_maximum = max(
        face["maximumAdvance"] for face in fine_reference["faceRanges"]
        if face["plane"] == 1
    )
    theoretical_advances = {
        "source": "global16-twoplane reference faceRanges",
        "highPlaneMaximumFontUnits": source_high_maximum,
        "highPlaneAdjustedPx": source_high_maximum * DISPLAY_SCALE * 256,
        "lowPlaneMaximumFontUnits": source_low_maximum,
        "lowPlaneAdjustedPx": source_low_maximum * DISPLAY_SCALE,
    }
    theoretical_advances["maximumAdjustedPx"] = max(
        theoretical_advances["highPlaneAdjustedPx"],
        theoretical_advances["lowPlaneAdjustedPx"],
    )
    if source_high_maximum != 3_662 or theoretical_advances["maximumAdjustedPx"] != 29_296:
        raise RuntimeError(f"unexpected source theoretical advance: {theoretical_advances}")
    if theoretical_advances["maximumAdjustedPx"] >= CHROME_ADVANCE_CEILING_PX:
        raise RuntimeError("source glyph theoretical maximum does not clear Chrome's ceiling")

    generated_bytes = sum(
        (OUTPUT / name).stat().st_size
        for name in ("index.html", "index.css", "exact.html", "exact.css")
    )
    reference = {
        "model": source_reference["model"],
        "backend": "bounded-cv01-gsub-score-plus-complement-lattice-scale",
        "baselineBackend": "matched-bounded-exact-css-dispatch-lattice-scale",
        "boundedOnly": True,
        "fullBuildPerformed": False,
        "groupIds": list(EXPECTED_GROUPS),
        "feature": source_reference["feature"],
        "featureValues": source_reference["featureValues"],
        "groups": 8,
        "groupSize": head.GROUP_SIZE,
        "fixtures": source_reference["fixtures"],
        "expectedCandidateBuckets": EXPECTED_CANDIDATE_BUCKETS,
        "inputRange": source_reference["inputRange"],
        "weightScale": source_reference["weightScale"],
        "scoreScale": source_reference["scoreScale"],
        "scoreStridePx": source_reference["scoreStridePx"],
        "sourceDisplayScale": source_reference["displayScale"],
        "displayScale": DISPLAY_SCALE,
        "fontSizePx": FONT_SIZE_PX,
        "lowPlaneUnitPx": DISPLAY_SCALE,
        "lowPlaneUnitLayout64": DISPLAY_SCALE * 64,
        "highPlaneUnitPx": DISPLAY_SCALE * 256,
        "highPlaneUnitLayout64": DISPLAY_SCALE * 256 * 64,
        "gsubEquivalentBasePx": gsub_base_px,
        "geometryFactor": gsub_factor,
        "exactGeometryFactor": exact_factor,
        "chromeAdvanceCeilingPx": CHROME_ADVANCE_CEILING_PX,
        "maximumBoundedStaticComplement": bounded_complement,
        "knownFullH3Complement": full_h3,
        "sourceTheoreticalAdvances": theoretical_advances,
        "sourceGsubDirectory": "gsub-indexed-fine-scorer",
        "sourceExactFontDirectory": "gpt2-hvar-grid-output-head-global16-twoplane",
        "reusedGsubWoff2Bytes": source_reference["fontWoff2Bytes"],
        "reusedGsubTtfBytes": source_reference["fontTtfBytes"],
        "reusedExactWoff2Bytes": fine_reference["fontBytes"],
        "gsubHtmlBytes": (OUTPUT / "index.html").stat().st_size,
        "gsubCssBytes": (OUTPUT / "index.css").stat().st_size,
        "exactHtmlBytes": (OUTPUT / "exact.html").stat().st_size,
        "exactCssBytes": (OUTPUT / "exact.css").stat().st_size,
        "generatedBytes": generated_bytes,
        "historicalPointOneScale": {
            "informationalOnly": True,
            "pageUsedAsBaseline": False,
            "maximumAbsoluteCandidateDelta": historical["maximumAbsoluteCandidateDelta"],
            "differingCandidateBuckets": sum(
                count for delta, count in historical["candidateDeltaHistogram"].items()
                if int(delta) != 0
            ),
            "winnerTokenAgreement": historical["winnerTokenAgreement"],
            "winnerBucketAgreement": historical["winnerBucketAgreement"],
            "expectedMaximumAbsoluteCandidateDelta": HISTORICAL_MAXIMUM_BUCKET_DELTA,
            "expectedDifferingCandidateBuckets": HISTORICAL_DIFFERING_BUCKETS,
            "expectedWinnerBucketAgreement": HISTORICAL_WINNER_BUCKET_AGREEMENT,
        },
        "limitations": [
            "Only the existing eight spread groups and ten fixtures are exercised.",
            "No full-vocabulary fonts were built or loaded; the full h3 complement value is projected from its existing metric.",
            "Timing is local headless Chrome wall-clock layout timing and is not portable across machines or Chrome builds.",
        ],
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in {"fixtures", "limitations"}
    }, indent=2))


if __name__ == "__main__":
    main()
