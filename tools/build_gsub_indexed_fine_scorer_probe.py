#!/usr/bin/env python3
"""Build a GSUB-indexed reusable global-int16 GPT-2 fine-scorer probe."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph

import build_gpt2_hvar_grid_output_head as head
import build_gpt2_hvar_grid_output_head_twoplane as fine
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_matrix_backend_prototypes import (
    build_direct_font_backend,
    build_master,
    output_glyph,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "experiments" / "gsub-indexed-fine-scorer"
FINE_ROOT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BASELINE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
BASELINE_ROOT = ROOT / "experiments" / BASELINE_NAME
DEFAULT_GROUPS = (0, 1, 2, 17, 64, 96, 128, 195)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="build all 197 groups under experiments/gsub-indexed-fine-scorer/full",
    )
    parser.add_argument(
        "--groups",
        help="comma-separated global group IDs (default: eight spread full groups)",
    )
    parser.add_argument(
        "--targeted-dummy-first",
        action="store_true",
        help="patch only the full h3 pair with a dummy cv01 alternate for groups 0/1/2 testing",
    )
    return parser.parse_args()


def selected_groups(args: argparse.Namespace, group_count: int) -> tuple[int, ...]:
    if args.full and args.groups:
        raise ValueError("--full and --groups are mutually exclusive")
    if args.full:
        return tuple(range(group_count))
    groups = (
        tuple(int(value) for value in args.groups.split(","))
        if args.groups
        else DEFAULT_GROUPS
    )
    if len(groups) < 8:
        raise ValueError("the gate requires at least eight token groups")
    if len(set(groups)) != len(groups):
        raise ValueError("group IDs must be unique")
    if any(group < 0 or group >= group_count for group in groups):
        raise ValueError(f"group IDs must be in 0..{group_count - 1}")
    return groups


def add_numbered_feature(
    font_path: Path,
    substitutions: list[tuple[np.ndarray, np.ndarray]],
    *,
    dummy_glyph: str | None = None,
) -> None:
    font = TTFont(font_path, recalcTimestamp=False)
    if "GSUB" in font:
        del font["GSUB"]
    rules = []
    for base_rows, alternate_rows in substitutions:
        for local in range(head.GROUP_SIZE):
            alternates = " ".join(
                output_glyph(int(row)) for row in alternate_rows[:, local]
            )
            if dummy_glyph is not None:
                alternates = f"{dummy_glyph} {alternates}"
            rules.append(
                f"sub {output_glyph(int(base_rows[local]))} "
                f"from [{alternates}];"
            )
    addOpenTypeFeaturesFromString(
        font,
        "feature cv01 {\n" + "\n".join(rules) + "\n} cv01;",
    )
    font.recalcTimestamp = False
    font.save(font_path)
    font.flavor = "woff2"
    font.save(font_path.with_suffix(".woff2"))


def add_real_dummy_glyph(font_path: Path, glyph_name: str) -> None:
    font = TTFont(font_path, recalcTimestamp=False)
    if glyph_name in font.getGlyphOrder():
        raise ValueError(f"dummy glyph already exists: {glyph_name}")
    font.setGlyphOrder([*font.getGlyphOrder(), glyph_name])
    font["glyf"].glyphs[glyph_name] = Glyph()
    font["hmtx"].metrics[glyph_name] = (0, 0)
    font["maxp"].numGlyphs = len(font.getGlyphOrder())
    font.recalcTimestamp = False
    font.save(font_path)


def compiled_alternates(font_path: Path, source: str) -> list[str]:
    font = TTFont(font_path, recalcTimestamp=False)
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            if hasattr(subtable, "alternates") and source in subtable.alternates:
                return list(subtable.alternates[source])
    raise ValueError(f"no AlternateSet for {source} in {font_path}")


def build_targeted_dummy_first() -> None:
    """Shift just the suspect full h3 pair without duplicating the full bank."""
    full = OUTPUT_ROOT / "full"
    output = OUTPUT_ROOT / "dummy-first-targeted"
    output.mkdir(parents=True, exist_ok=True)
    full_reference = json.loads((full / "reference.json").read_text())
    groups = full_reference["fullVocabularyGroups"]
    token_rows = np.arange(groups * head.GROUP_SIZE).reshape(
        groups, head.GROUP_SIZE
    )
    token_rows[-1, head.VOCABULARY % head.GROUP_SIZE :] = head.VOCABULARY - 1

    score = output / "score-h3.ttf"
    shutil.copyfile(full / score.name, score)
    add_real_dummy_glyph(score, "probeDummy")
    add_numbered_feature(
        score,
        [(np.arange(head.GROUP_SIZE), token_rows)],
        dummy_glyph="probeDummy",
    )

    correction = output / "base-h3.ttf"
    shutil.copyfile(full / correction.name, correction)
    add_real_dummy_glyph(correction, "probeDummy")
    add_numbered_feature(
        correction,
        [(
            np.arange(head.GROUP_SIZE),
            head.GROUP_SIZE + np.arange(groups * head.GROUP_SIZE).reshape(
                groups, head.GROUP_SIZE
            ),
        )],
        dummy_glyph="probeDummy",
    )
    compiled_score_prefix = compiled_alternates(score, output_glyph(0))[:4]
    compiled_correction_prefix = compiled_alternates(correction, output_glyph(0))[:4]
    expected_score_prefix = ["probeDummy", "y000", "y256", "y512"]
    expected_correction_prefix = ["probeDummy", "y256", "y512", "y768"]
    if compiled_score_prefix != expected_score_prefix:
        raise RuntimeError(f"score AlternateSet prefix {compiled_score_prefix}")
    if compiled_correction_prefix != expected_correction_prefix:
        raise RuntimeError(f"correction AlternateSet prefix {compiled_correction_prefix}")

    candidates = []
    for local in range(head.GROUP_SIZE):
        spans = []
        for shard in range(full_reference["shards"]):
            for plane, letter in enumerate(("h", "l")):
                face = 2 * shard + plane
                start = fine.CODEPOINT_STARTS[face]
                shifted = " shifted" if shard == 3 and letter == "h" else ""
                spans.append(
                    f'<span class="probe-face face-{letter}{shard}{shifted}">'
                    f'&#x{start + local:X};&#x{start + 0x8000 + local:X};</span>'
                )
        candidates.append(
            f'<i class="candidate" data-local="{local}" '
            f'style="--local-tie:{head.GROUP_SIZE - 1 - local}">'
            f'{"".join(spans)}</i>'
        )
    (output / "index.html").write_text(
        "<!doctype html>\n<meta charset=\"utf-8\">\n"
        "<title>Targeted dummy-first GSUB probe</title>\n"
        "<link rel=\"stylesheet\" href=\"index.css\">\n"
        f'<main id="gsub-stage" class="fine-stage">{"".join(candidates)}</main>\n'
    )

    css = (full / "index.css").read_text().replace(
        'url("', 'url("../full/'
    )
    for name in ("score-h3.woff2", "base-h3.woff2"):
        css = css.replace(f'url("../full/{name}")', f'url("{name}")')
    face_rules = []
    for shard in range(full_reference["shards"]):
        for letter in ("h", "l"):
            upper = letter.upper()
            face_rules.append(
                f'.face-{letter}{shard}'
                f'{{font-family:GSUBBase{upper}{shard},GSUBScore{upper}{shard}}}'
            )
    css += "\n" + "".join(face_rules) + (
        '\n.probe-face{font-feature-settings:"cv01" '
        'calc(var(--probe-feature) - 1)}'
        '\n.probe-face.shifted{font-feature-settings:"cv01" '
        'var(--probe-feature)}\n'
    )
    (output / "index.css").write_text(css)

    fixtures = full_reference["fixtures"]
    targeted_reference = dict(full_reference)
    targeted_reference.update({
        "backend": "targeted-dummy-first-full-h3",
        "groupIds": [0, 1, 2],
        "featureValues": {"0": 2, "1": 3, "2": 4},
        "groups": 3,
        "targetedDummyFirst": True,
        "targetedShiftedFaces": ["score-h3", "base-h3"],
        "compiledScoreAlternatePrefix": compiled_score_prefix,
        "compiledCorrectionAlternatePrefix": compiled_correction_prefix,
        "fontTtfBytes": sum(
            (output / name).stat().st_size
            for name in ("score-h3.ttf", "base-h3.ttf")
        ),
        "fontWoff2Bytes": sum(
            (output / name).stat().st_size
            for name in ("score-h3.woff2", "base-h3.woff2")
        ),
        "htmlBytes": (output / "index.html").stat().st_size,
        "cssBytes": (output / "index.css").stat().st_size,
        "fixtures": {
            "hiddenVectors": fixtures["hiddenVectors"][:3],
            "scoreFloors": fixtures["scoreFloors"][:3],
            "cases": [
                {
                    "fixture": case["fixture"],
                    "groups": [
                        {**group, "feature": group["feature"] + 1}
                        for group in case["groups"][:3]
                    ],
                }
                for case in fixtures["cases"][:3]
            ],
        },
    })
    (output / "reference.json").write_text(
        json.dumps(targeted_reference, indent=2) + "\n"
    )
    print(json.dumps({
        "output": str(output),
        "groups": targeted_reference["groupIds"],
        "fixtures": len(targeted_reference["fixtures"]["cases"]),
        "woff2BytesPatched": targeted_reference["fontWoff2Bytes"],
        "compiledScoreAlternatePrefix": compiled_score_prefix,
        "compiledCorrectionAlternatePrefix": compiled_correction_prefix,
    }, indent=2))


def keep_local_cmap(font_path: Path, start: int) -> None:
    """Keep only the 256 input characters; alternates remain GSUB-only."""
    font = TTFont(font_path, recalcTimestamp=False)
    stop = start + head.GROUP_SIZE
    for table in font["cmap"].tables:
        table.cmap = {
            codepoint: glyph
            for codepoint, glyph in table.cmap.items()
            if start <= codepoint < stop
        }
    font.recalcTimestamp = False
    font.save(font_path)


def render_html(correction_offset: int) -> str:
    candidates = []
    for local in range(head.GROUP_SIZE):
        glyphs = "".join(
            f"&#x{codepoint_start + local:X};"
            f"&#x{codepoint_start + correction_offset + local:X};"
            for codepoint_start in fine.CODEPOINT_STARTS
        )
        candidates.append(
            f'<i class="candidate" data-local="{local}" '
            f'style="--local-tie:{head.GROUP_SIZE - 1 - local}">{glyphs}</i>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GSUB-indexed global-int16 GPT-2 fine scorer</title>
<link rel="stylesheet" href="index.css">
<main id="gsub-stage" class="fine-stage">{''.join(candidates)}</main>
"""


def render_css(
    reference: dict,
    face_bases: list[int],
    separate_corrections: bool,
) -> str:
    faces = []
    families = []
    for shard in range(reference["shards"]):
        for plane_name, plane_letter in (("high", "h"), ("low", "l")):
            family = f"GSUBScore{plane_letter.upper()}{shard}"
            adjustment = ";size-adjust:25600%" if plane_name == "high" else ""
            if separate_corrections:
                correction_family = f"GSUBBase{plane_letter.upper()}{shard}"
                faces.append(
                    f'@font-face{{font-family:{correction_family};'
                    f'src:url("base-{plane_letter}{shard}.woff2") '
                    f'format("woff2"){adjustment}}}'
                )
                families.append(correction_family)
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


def fixture_oracle(
    groups: tuple[int, ...],
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
        for feature, group in enumerate(groups, start=1):
            start = group * head.GROUP_SIZE
            stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
            scores = vector @ quantized_embeddings[start:stop].T
            buckets = np.rint(
                (scores - floors[fixture]) * fine_reference["scoreScale"]
            ).astype(int)
            # Pad the partial final vocabulary group. Its missing positions are
            # never eligible and use a sentinel solely to keep a 256-wide oracle.
            padded = np.full(head.GROUP_SIZE, -1, dtype=int)
            padded[: len(buckets)] = buckets
            local = int(np.argmax(buckets))
            group_cases.append({
                "group": group,
                "feature": feature,
                "validCandidates": len(buckets),
                "buckets": padded.tolist(),
                "winnerLocal": local,
                "winnerToken": start + local,
                "winnerBucket": int(buckets[local]),
            })
        cases.append({"fixture": fixture, "groups": group_cases})
    return {
        "hiddenVectors": fixtures["hiddenVectors"],
        "scoreFloors": fixtures["scoreFloors"],
        "cases": cases,
    }


def main() -> None:
    args = parse_args()
    if args.targeted_dummy_first:
        if args.full or args.groups:
            raise ValueError("--targeted-dummy-first cannot be combined with --full/--groups")
        build_targeted_dummy_first()
        return
    fine_reference = json.loads((FINE_ROOT / "reference.json").read_text())
    baseline_reference = json.loads((BASELINE_ROOT / "reference.json").read_text())
    groups = selected_groups(args, fine_reference["groups"])
    output = OUTPUT_ROOT / "full" if args.full else OUTPUT_ROOT
    output.mkdir(parents=True, exist_ok=True)

    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    codes = np.rint(embeddings / fine_reference["weightScale"]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * fine_reference["weightScale"]

    selected_tokens = np.concatenate([
        np.arange(
            group * head.GROUP_SIZE,
            min((group + 1) * head.GROUP_SIZE, head.VOCABULARY),
            dtype=int,
        )
        for group in groups
    ])
    # The last vocabulary group is partial. Repeat its last real token in the
    # structurally required but ineligible alternate slots.
    if len(selected_tokens) != len(groups) * head.GROUP_SIZE:
        rows = []
        for group in groups:
            tokens = np.arange(
                group * head.GROUP_SIZE,
                min((group + 1) * head.GROUP_SIZE, head.VOCABULARY),
                dtype=int,
            )
            rows.append(np.pad(tokens, (0, head.GROUP_SIZE - len(tokens)), mode="edge"))
        selected_tokens = np.concatenate(rows)

    font_paths = []
    face_bases = []
    face_ranges = []
    for shard, start in enumerate(range(0, head.WIDTH, fine.SHARD)):
        stop = min(start + fine.SHARD, head.WIDTH)
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        for plane, values in enumerate((high, residual)):
            selected = values[selected_tokens]
            l1 = np.sum(np.abs(selected.astype(np.int64)), axis=1).astype(np.int32)
            score_bases = l1 + 32
            common_base = int(np.max(score_bases))
            correction_bases = common_base - score_bases
            # Each local position shapes a real score glyph and a zero-HVAR
            # complement glyph. Their bases sum to max(base), removing the CSS
            # dispatch while preserving the source row/base on the score glyph.
            selected_by_group = selected.reshape(
                len(groups), head.GROUP_SIZE, selected.shape[1]
            )
            score_bases_by_group = score_bases.reshape(len(groups), head.GROUP_SIZE)
            correction_by_group = correction_bases.reshape(
                len(groups), head.GROUP_SIZE
            )
            zero_group = np.zeros_like(selected_by_group[0])
            alternate_rows = np.concatenate([
                np.concatenate((selected_by_group[group], zero_group), axis=0)
                for group in range(len(groups))
            ])
            alternate_bases = np.concatenate([
                np.concatenate((score_bases_by_group[group], correction_by_group[group]))
                for group in range(len(groups))
            ])
            base_rows = np.concatenate((selected_by_group[0], zero_group), axis=0)
            base_advances = np.concatenate(
                (score_bases_by_group[0], correction_by_group[0])
            )
            font_rows = np.concatenate((base_rows, alternate_rows), axis=0)
            font_bases = np.concatenate((base_advances, alternate_bases), axis=0)
            maximum_l1 = int(l1.max())
            if common_base + maximum_l1 > 65_535:
                raise RuntimeError(f"shard {shard} plane {plane} exceeds uint16 advance")
            letter = "h" if plane == 0 else "l"
            destination = output / f"score-{letter}{shard}.ttf"
            if args.full:
                shutil.copyfile(FINE_ROOT / destination.name, destination)
                token_rows = selected_tokens.reshape(len(groups), head.GROUP_SIZE)
                add_numbered_feature(destination, [(
                    np.arange(head.GROUP_SIZE),
                    token_rows,
                )])
                base_destination = output / f"base-{letter}{shard}.ttf"
                base_widths = np.concatenate((
                    correction_by_group[0],
                    correction_bases,
                ))
                build_master(
                    base_destination,
                    base_widths,
                    "Regular",
                    codepoint_start=(
                        fine.CODEPOINT_STARTS[2 * shard + plane] + 0x8000
                    ),
                )
                keep_local_cmap(
                    base_destination,
                    fine.CODEPOINT_STARTS[2 * shard + plane] + 0x8000,
                )
                add_numbered_feature(base_destination, [(
                    np.arange(head.GROUP_SIZE),
                    head.GROUP_SIZE + np.arange(
                        len(groups) * head.GROUP_SIZE
                    ).reshape(len(groups), head.GROUP_SIZE),
                )])
                font_paths.extend((destination, base_destination))
            else:
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
                pair_stride = 2 * head.GROUP_SIZE
                alternate_score_rows = np.stack([
                    pair_stride + group * pair_stride + np.arange(head.GROUP_SIZE)
                    for group in range(len(groups))
                ])
                alternate_base_rows = alternate_score_rows + head.GROUP_SIZE
                add_numbered_feature(destination, [
                    (np.arange(head.GROUP_SIZE), alternate_score_rows),
                    (
                        head.GROUP_SIZE + np.arange(head.GROUP_SIZE),
                        alternate_base_rows,
                    ),
                ])
                font_paths.append(destination)
            face_bases.append(common_base)
            face_ranges.append({
                "shard": shard,
                "plane": plane,
                "rows": int(len(font_rows)),
                "maximumL1": maximum_l1,
                "commonBase": common_base,
                "maximumScoreBase": common_base,
                "maximumAdvance": int(np.max(score_bases + l1)),
            })

    correction_offset = 0x8000 if args.full else head.GROUP_SIZE
    (output / "index.html").write_text(render_html(correction_offset))
    (output / "index.css").write_text(
        render_css(fine_reference, face_bases, args.full)
    )
    oracle = fixture_oracle(
        groups, fine_reference, quantized_embeddings, baseline_reference
    )
    ttf_bytes = sum(path.stat().st_size for path in font_paths)
    woff2_bytes = sum(path.with_suffix(".woff2").stat().st_size for path in font_paths)
    reference = {
        "model": "openai-community/gpt2",
        "backend": "cv01-numbered-gsub-global-int16-high-residual-hvar",
        "feature": "cv01",
        "groupIds": list(groups),
        "featureValues": {
            str(group): feature for feature, group in enumerate(groups, start=1)
        },
        "groups": len(groups),
        "fullVocabularyGroups": fine_reference["groups"],
        "groupSize": head.GROUP_SIZE,
        "glyphPositions": head.GROUP_SIZE,
        "glyphRowsPerFace": (
            head.VOCABULARY if args.full
            else 2 * head.GROUP_SIZE * (len(groups) + 1)
        ),
        "separateCorrectionFaces": args.full,
        "shards": fine_reference["shards"],
        "planes": fine_reference["planes"],
        "inputRange": fine_reference["inputRange"],
        "weightScale": fine_reference["weightScale"],
        "displayScale": fine_reference["displayScale"],
        "scoreScale": fine_reference["scoreScale"],
        "scoreStridePx": fine_reference["scoreStridePx"],
        "baselineDirectory": BASELINE_NAME,
        "baselineFineWoff2Bytes": fine_reference["fontBytes"],
        "baselineDispatchCssBytes": baseline_reference["cssBytes"],
        "fontTtfBytes": ttf_bytes,
        "fontWoff2Bytes": woff2_bytes,
        "expandedToWoff2Ratio": ttf_bytes / woff2_bytes,
        "htmlBytes": (output / "index.html").stat().st_size,
        "cssBytes": (output / "index.css").stat().st_size,
        "faceRanges": face_ranges,
        "fixtures": oracle,
    }
    (output / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in {"faceRanges", "fixtures", "featureValues"}
    }, indent=2))


if __name__ == "__main__":
    main()
