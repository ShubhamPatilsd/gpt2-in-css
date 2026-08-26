#!/usr/bin/env python3
"""Build the focused source-scale GSUB split-complement scorer probe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gsub_indexed_fine_scorer_probe import (
    add_numbered_feature,
    fixture_oracle,
)
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gsub-split-complement-fine-scorer"
FINE_ROOT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
FULL_GSUB_ROOT = ROOT / "experiments" / "gsub-indexed-fine-scorer" / "full"
BASELINE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
BASELINE_ROOT = ROOT / "experiments" / BASELINE_NAME
GROUPS = (0, 1)
SPLIT_SHARD = 3
SPLIT_PLANE = 0
ADJUSTED_ADVANCE_CAP_PX = 32_768
HIGH_PLANE_SIZE_ADJUST = 256
FONT_SIZE_PX = 100
UNITS_PER_EM = 1_000


def render_html() -> str:
    candidates = []
    for local in range(head.GROUP_SIZE):
        glyphs = []
        for face, codepoint_start in enumerate(fine.CODEPOINT_STARTS):
            shard, plane = divmod(face, 2)
            glyphs.extend((
                f"&#x{codepoint_start + local:X};",
                f"&#x{codepoint_start + head.GROUP_SIZE + local:X};",
            ))
            if (shard, plane) == (SPLIT_SHARD, SPLIT_PLANE):
                glyphs.append(
                    f"&#x{codepoint_start + 2 * head.GROUP_SIZE + local:X};"
                )
        candidates.append(
            f'<i class="candidate" data-local="{local}" '
            f'style="--local-tie:{head.GROUP_SIZE - 1 - local}">'
            f'{"".join(glyphs)}</i>'
        )
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<title>GSUB split-complement fine scorer</title>\n'
        '<link rel="stylesheet" href="index.css">\n'
        f'<main id="gsub-stage" class="fine-stage">{"".join(candidates)}</main>\n'
    )


def render_css(reference: dict, face_bases: list[int]) -> str:
    faces = []
    families = []
    for shard in range(reference["shards"]):
        for plane_name, plane_letter in (("high", "h"), ("low", "l")):
            family = f"SplitScore{plane_letter.upper()}{shard}"
            adjustment = ";size-adjust:25600%" if plane_name == "high" else ""
            faces.append(
                f'@font-face{{font-family:{family};'
                f'src:url("score-{plane_letter}{shard}.woff2") '
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
        / reference["displayScale"]
    )
    return "\n".join((
        "".join(faces),
        '@property --probe-feature{syntax:"<integer>";inherits:true;initial-value:1}',
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
        ".fine-stage{position:fixed;left:0;top:0;display:grid;"
        "grid-template-columns:max-content;grid-template-rows:1px;"
        "width:max-content;height:1px;"
        f"font-family:{','.join(families)};font-size:100px;line-height:1;"
        f"font-variation-settings:{settings};"
        'font-feature-settings:"cv01" var(--probe-feature);font-kerning:none;'
        "--score-offset:0px}",
        ".candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal;"
        "width:calc-size(max-content,calc(round(nearest,"
        f"(size - {head.css_number(equivalent_base * reference['displayScale'])}px)"
        f"*{head.css_number(factor)} + var(--score-offset),4px)"
        " + var(--local-tie)/64*1px))}",
    )) + "\n"


def main() -> None:
    fine_reference = json.loads((FINE_ROOT / "reference.json").read_text())
    full_gsub_reference = json.loads((FULL_GSUB_ROOT / "reference.json").read_text())
    baseline_reference = json.loads((BASELINE_ROOT / "reference.json").read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)

    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    codes = np.rint(embeddings / fine_reference["weightScale"]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * fine_reference["weightScale"]
    selected_tokens = np.concatenate([
        np.arange(group * head.GROUP_SIZE, (group + 1) * head.GROUP_SIZE)
        for group in GROUPS
    ])

    font_paths = []
    face_bases = []
    face_ranges = []
    exact_split_checks = 0
    original_overflowing_rows = []
    for shard, start in enumerate(range(0, head.WIDTH, fine.SHARD)):
        stop = min(start + fine.SHARD, head.WIDTH)
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        for plane, values in enumerate((high, residual)):
            selected = values[selected_tokens]
            l1 = np.sum(np.abs(selected.astype(np.int64)), axis=1).astype(np.int32)
            score_bases = l1 + 32
            source_face = next(
                face for face in full_gsub_reference["faceRanges"]
                if face["shard"] == shard and face["plane"] == plane
            )
            common_base = int(source_face["commonBase"])
            if common_base < int(np.max(score_bases)):
                raise RuntimeError(
                    f"full-bank common base is too small for face {(shard, plane)}"
                )
            corrections = common_base - score_bases
            selected_by_group = selected.reshape(
                len(GROUPS), head.GROUP_SIZE, selected.shape[1]
            )
            score_bases_by_group = score_bases.reshape(
                len(GROUPS), head.GROUP_SIZE
            )
            correction_by_group = corrections.reshape(
                len(GROUPS), head.GROUP_SIZE
            )
            zero_group = np.zeros_like(selected_by_group[0])
            split = (shard, plane) == (SPLIT_SHARD, SPLIT_PLANE)

            group_rows = []
            group_bases = []
            split_a_by_group = []
            split_b_by_group = []
            for group_index in range(len(GROUPS)):
                if split:
                    split_a = correction_by_group[group_index] // 2
                    split_b = correction_by_group[group_index] - split_a
                    if not np.array_equal(
                        split_a + split_b, correction_by_group[group_index]
                    ):
                        raise RuntimeError("split complements do not sum exactly")
                    exact_split_checks += int(len(split_a))
                    split_a_by_group.append(split_a)
                    split_b_by_group.append(split_b)
                    group_rows.append(np.concatenate(
                        (selected_by_group[group_index], zero_group, zero_group),
                        axis=0,
                    ))
                    group_bases.append(np.concatenate((
                        score_bases_by_group[group_index], split_a, split_b,
                    )))
                else:
                    group_rows.append(np.concatenate(
                        (selected_by_group[group_index], zero_group), axis=0
                    ))
                    group_bases.append(np.concatenate((
                        score_bases_by_group[group_index],
                        correction_by_group[group_index],
                    )))

            base_rows = group_rows[0]
            base_advances = group_bases[0]
            font_rows = np.concatenate((base_rows, *group_rows), axis=0)
            font_bases = np.concatenate((base_advances, *group_bases), axis=0)
            letter = "h" if plane == 0 else "l"
            destination = OUTPUT / f"score-{letter}{shard}.ttf"
            build_direct_font_backend(
                font_rows,
                destination,
                signed_axes=True,
                base_advance=font_bases,
                codepoint_start=fine.CODEPOINT_STARTS[2 * shard + plane],
                axis_tags=[
                    head.global_axis_tag(dimension)
                    for dimension in range(start, stop)
                ],
            )
            position_count = 3 if split else 2
            stride = position_count * head.GROUP_SIZE
            substitutions = []
            for position in range(position_count):
                substitutions.append((
                    position * head.GROUP_SIZE + np.arange(head.GROUP_SIZE),
                    np.stack([
                        stride + group_index * stride
                        + position * head.GROUP_SIZE
                        + np.arange(head.GROUP_SIZE)
                        for group_index in range(len(GROUPS))
                    ]),
                ))
            add_numbered_feature(destination, substitutions)
            font_paths.append(destination)
            face_bases.append(common_base)

            maximum_component = int(np.max(corrections))
            component_count = 1
            split_a_max = None
            split_b_max = None
            if split:
                component_count = 2
                split_a_max = int(np.max(np.concatenate(split_a_by_group)))
                split_b_max = int(np.max(np.concatenate(split_b_by_group)))
                maximum_component = max(split_a_max, split_b_max)
                for group_index, group in enumerate(GROUPS):
                    for local, correction in enumerate(
                        correction_by_group[group_index]
                    ):
                        adjusted_px = (
                            int(correction)
                            * FONT_SIZE_PX
                            / UNITS_PER_EM
                            * HIGH_PLANE_SIZE_ADJUST
                        )
                        if adjusted_px >= ADJUSTED_ADVANCE_CAP_PX:
                            original_overflowing_rows.append({
                                "group": group,
                                "local": local,
                                "correction": int(correction),
                                "adjustedPx": adjusted_px,
                            })
            adjusted_static_px = (
                maximum_component
                * FONT_SIZE_PX
                / UNITS_PER_EM
                * (HIGH_PLANE_SIZE_ADJUST if plane == 0 else 1)
            )
            face_ranges.append({
                "shard": shard,
                "plane": plane,
                "splitComplement": split,
                "glyphPositionsPerCandidate": position_count,
                "rows": int(len(font_rows)),
                "commonBase": common_base,
                "fullBankCommonBase": int(source_face["commonBase"]),
                "commonBaseMatchesFullBank": (
                    common_base == int(source_face["commonBase"])
                ),
                "maximumL1": int(np.max(l1)),
                "maximumOriginalCorrection": int(np.max(corrections)),
                "maximumComplementComponent": maximum_component,
                "maximumSplitA": split_a_max,
                "maximumSplitB": split_b_max,
                "maximumAdjustedStaticComplementPx": adjusted_static_px,
                "adjustedAdvanceCapPx": ADJUSTED_ADVANCE_CAP_PX,
                "complementComponentsIndependentlySafe": (
                    adjusted_static_px < ADJUSTED_ADVANCE_CAP_PX
                ),
            })

    (OUTPUT / "index.html").write_text(render_html())
    (OUTPUT / "index.css").write_text(render_css(fine_reference, face_bases))
    oracle = fixture_oracle(
        GROUPS, fine_reference, quantized_embeddings, baseline_reference
    )
    ttf_bytes = sum(path.stat().st_size for path in font_paths)
    woff2_bytes = sum(path.with_suffix(".woff2").stat().st_size for path in font_paths)
    reference = {
        "model": "openai-community/gpt2",
        "backend": "cv01-numbered-source-scale-split-h3-complement",
        "feature": "cv01",
        "groupIds": list(GROUPS),
        "featureValues": {
            str(group): feature
            for feature, group in enumerate(GROUPS, start=1)
        },
        "groups": len(GROUPS),
        "groupSize": head.GROUP_SIZE,
        "validCandidateComparisons": (
            len(GROUPS) * head.GROUP_SIZE
            * len(baseline_reference["certifiedFixtures"]["hiddenVectors"])
        ),
        "shards": fine_reference["shards"],
        "planes": fine_reference["planes"],
        "inputRange": fine_reference["inputRange"],
        "weightScale": fine_reference["weightScale"],
        "displayScale": fine_reference["displayScale"],
        "scoreScale": fine_reference["scoreScale"],
        "scoreStridePx": fine_reference["scoreStridePx"],
        "baselineDirectory": BASELINE_NAME,
        "sourceFullGsubDirectory": "gsub-indexed-fine-scorer/full",
        "baselineFineWoff2Bytes": fine_reference["fontBytes"],
        "baselineDispatchCssBytes": baseline_reference["cssBytes"],
        "fontTtfBytes": ttf_bytes,
        "fontWoff2Bytes": woff2_bytes,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
        "candidateElements": head.GROUP_SIZE,
        "glyphsPerCandidate": 2 * fine_reference["shards"] + 1,
        "baselineGsubGlyphsPerCandidate": 2 * fine_reference["shards"],
        "splitFace": {"shard": SPLIT_SHARD, "plane": SPLIT_PLANE},
        "splitFormula": "floor(c/2) + (c - floor(c/2))",
        "exactSplitChecks": exact_split_checks,
        "originalOverflowingRows": original_overflowing_rows,
        "allComplementsIndependentlySafe": all(
            face["complementComponentsIndependentlySafe"]
            for face in face_ranges
        ),
        "faceRanges": face_ranges,
        "fixtures": oracle,
    }
    (OUTPUT / "reference.json").write_text(
        json.dumps(reference, indent=2) + "\n"
    )
    print(json.dumps({
        key: value
        for key, value in reference.items()
        if key not in {"faceRanges", "fixtures", "featureValues"}
    }, indent=2))


if __name__ == "__main__":
    main()
