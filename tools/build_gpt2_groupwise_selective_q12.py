#!/usr/bin/env python3
"""Build a production-range cascade with selected rowwise-q12 coarse groups."""

from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_groupwise_cauchy_head import upper_block_norms
from build_gpt2_block_css import global_axis_tag
from build_gpt2_groupwise_cauchy_blockflow_cascade import (
    AXIS_STEPS,
    BLOCK_COUNT,
    BLOCK_WIDTH,
    BOUND_CODEPOINT_START,
    BOUND_FONT,
    BOUND_QUANTIZATION,
    HOT_GROUPS,
    predicted_bounds,
)
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
ALLOCATION = ROOT / "experiments" / "gpt2-groupwise-precision-allocation" / "results.json"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BOUND = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
SELECTIVE_COUNT = int(os.environ.get("SELECTIVE_Q12_GROUPS", "32"))
OUTPUT = ROOT / "experiments" / os.environ.get(
    "SELECTIVE_Q12_OUTPUT",
    f"gpt2-groupwise-cauchy-blockflow-production-selective-q12-top{SELECTIVE_COUNT}",
)
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
SHARD = 256
SHARDS = 3
RADIX = 64
DISPLAY_SCALE = 0.1
SAFETY = 32
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
Q10_MAXIMUM = 511
Q12_MAXIMUM = 2047
Q12_TRANSPORT_ALLOWANCE_BUCKETS = 27
CODEPOINT_STARTS = tuple(0x50000 + face * 0x10000 for face in range(6))


def css_number(value: float) -> str:
    text = f"{float(value):.12g}"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def represented_rows(weights: np.ndarray, maximum: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scales = np.max(np.abs(weights), axis=1) / maximum
    scales[scales == 0] = 1.0
    codes = np.rint(weights / scales[:, None]).clip(-maximum, maximum).astype(np.int16)
    return codes, scales, codes.astype(np.float64) * scales[:, None]


def selected_row_indices(groups: list[int]) -> np.ndarray:
    return np.concatenate([
        np.arange(
            group * GROUP_SIZE,
            min((group + 1) * GROUP_SIZE, VOCABULARY),
            dtype=np.int64,
        )
        for group in groups
    ])


def build_q12_fonts(codes: np.ndarray) -> tuple[np.ndarray, list[dict[str, object]], list[Path]]:
    equivalent_bases: list[np.ndarray] = []
    reports: list[dict[str, object]] = []
    fonts: list[Path] = []
    for shard, start in enumerate(range(0, head.WIDTH, SHARD)):
        stop = min(start + SHARD, head.WIDTH)
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / RADIX).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * RADIX).astype(np.int16)
        if not np.array_equal(
            high.astype(np.int32) * RADIX + residual.astype(np.int32),
            shard_codes,
        ):
            raise RuntimeError(f"shard {shard} two-plane split is not exact")
        plane_bases = []
        for plane, (plane_name, values) in enumerate((
            ("high", high), ("residual", residual)
        )):
            l1 = np.sum(np.abs(values.astype(np.int64)), axis=1)
            bases = (l1 + SAFETY).astype(np.int32)
            if int(np.max(bases + l1)) > 65_535:
                raise RuntimeError(
                    f"shard {shard} {plane_name} exceeds shaped uint16 advance"
                )
            letter = "h" if plane_name == "high" else "l"
            destination = OUTPUT / f"selective-q12-{letter}{shard}.ttf"
            font = destination.with_suffix(".woff2")
            if not font.exists():
                build_direct_font_backend(
                    values,
                    destination,
                    signed_axes=True,
                    base_advance=bases,
                    codepoint_start=CODEPOINT_STARTS[2 * shard + plane],
                    axis_tags=[
                        global_axis_tag(dimension) for dimension in range(start, stop)
                    ],
                )
            fonts.append(font)
            plane_bases.append(bases.astype(np.int64))
            reports.append({
                "shard": shard,
                "plane": plane_name,
                "dimensions": [start, stop],
                "rows": len(codes),
                "codeAbsoluteMaximum": int(np.max(np.abs(values))),
                "maximumL1": int(l1.max()),
                "maximumBaseAdvance": int(bases.max()),
                "maximumShapedAdvance": int(np.max(bases + l1)),
                "woff2Bytes": font.stat().st_size,
            })
        equivalent_bases.append(plane_bases[0] * RADIX + plane_bases[1])
    return np.sum(np.stack(equivalent_bases), axis=0), reports, fonts


def selective_css() -> str:
    faces = []
    families = []
    for shard in range(SHARDS):
        for plane_name, letter in (("H", "h"), ("L", "l")):
            family = f"SelectiveQ12{plane_name}{shard}"
            size_adjust = f";size-adjust:{RADIX * 100}%" if letter == "h" else ""
            faces.append(
                f'@font-face{{font-family:{family};src:url("selective-q12-{letter}{shard}.woff2") '
                f'format("woff2"){size_adjust}}}'
            )
            families.append(family)
    return "".join(faces) + (
        ".candidate.selective-q12{font-family:"
        + ",".join(families)
        + f"!important;font-size:{css_number(head.FONT_SIZE * DISPLAY_SCALE)}px!important}}\n"
    )


def replace_selected_candidates(
    document: str,
    selected_rows: np.ndarray,
    equivalent_bases: np.ndarray,
    q12_scales: np.ndarray,
    source_range: float,
) -> tuple[str, int]:
    row_for_token = {int(token): row for row, token in enumerate(selected_rows)}
    seen = 0
    replaced = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal seen, replaced
        token = len(HOT_GROUPS) * GROUP_SIZE + seen
        seen += 1
        row = row_for_token.get(token)
        if row is None:
            return match.group(0)
        replaced += 1
        characters = "".join(chr(start + row) for start in CODEPOINT_STARTS)
        base = equivalent_bases[row] * DISPLAY_SCALE
        factor = (
            source_range * q12_scales[token] * SCORE_SCALE * SCORE_STRIDE_PX
            / DISPLAY_SCALE
        )
        return (
            '<i class="candidate selective-q12" style="--base:'
            f'{css_number(base)};--factor:{css_number(factor)};'
            f'--local-tie:{GROUP_SIZE - 1 - token % GROUP_SIZE}">'
            f"{characters}</i>"
        )

    result = re.sub(
        r'<i class="candidate" style="[^"]*">[^<]*</i>',
        replace,
        document,
    )
    expected_seen = VOCABULARY - len(HOT_GROUPS) * GROUP_SIZE
    if seen != expected_seen:
        raise RuntimeError(f"expected {expected_seen} q10 rows, found {seen}")
    if replaced != len(selected_rows):
        raise RuntimeError(f"expected {len(selected_rows)} replacements, made {replaced}")
    return result, replaced


def build_bound_font(group_norms: np.ndarray, block_axis_range: float) -> np.ndarray:
    coefficients = np.ceil(
        group_norms * block_axis_range * BOUND_QUANTIZATION
    ).astype(np.int16)
    coefficients[list(HOT_GROUPS)] = 0
    bases = np.sum(coefficients.astype(np.int64), axis=1)
    if np.any(coefficients < 0) or int(coefficients.max()) > 32_767:
        raise RuntimeError("mixed q10/q12 bound coefficients exceed int16")
    if int(bases.max()) > 65_535:
        raise RuntimeError("mixed q10/q12 bound base exceeds uint16")
    destination = OUTPUT / f"{BOUND_FONT}.ttf"
    build_direct_font_backend(
        coefficients,
        destination,
        signed_axes=False,
        base_advance=bases,
        codepoint_start=BOUND_CODEPOINT_START,
        axis_tags=[f"b{block:03d}" for block in range(BLOCK_COUNT)],
        allow_out_of_range_result=True,
    )
    font = TTFont(destination, recalcTimestamp=False)
    for glyph, (_advance, lsb) in font["hmtx"].metrics.items():
        font["hmtx"].metrics[glyph] = (0, lsb)
    font["hhea"].advanceWidthMax = 0
    font.recalcTimestamp = False
    font.save(destination)
    compressed = TTFont(destination, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(destination.with_suffix(".woff2"))
    return coefficients


def corpus_route(
    hidden: np.ndarray,
    represented: np.ndarray,
    target: np.ndarray,
    group_norms: np.ndarray,
    production_range: float,
    score_gain: float,
    hot_allowance: int,
    stop_gap: int,
    selected_groups: list[int],
) -> dict[str, np.ndarray]:
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    block_norms = upper_block_norms(realized, BLOCK_WIDTH)
    upper = np.empty((len(hidden), GROUPS), dtype=np.int64)
    exact = np.empty_like(upper)
    coarse_widths = np.empty_like(upper)
    winners = np.empty(len(hidden), dtype=np.int64)
    floors = np.empty(len(hidden), dtype=np.int64)
    padded_rows = GROUPS * GROUP_SIZE
    for start in range(0, len(hidden), 32):
        stop = min(start + 32, len(hidden))
        coarse_scores = realized[start:stop] @ represented.T * score_gain
        target_scores = realized[start:stop] @ target.T * score_gain
        target_score_buckets = np.rint(
            target_scores * SCORE_SCALE
        ).astype(np.int64)
        # The CSS fine scorer resolves bucket ties by the lower token id. Match
        # that browser-realized q16 target instead of the pre-bucket float argmax.
        winners[start:stop] = np.argmax(target_score_buckets, axis=1)
        floors[start:stop] = np.floor(np.minimum(
            np.min(coarse_scores, axis=1), np.min(target_scores, axis=1)
        )).astype(np.int64) - 2
        coarse_padded = np.full((stop - start, padded_rows), -np.inf)
        target_padded = np.full_like(coarse_padded, -np.inf)
        coarse_padded[:, :VOCABULARY] = coarse_scores
        target_padded[:, :VOCABULARY] = target_scores
        coarse_group = coarse_padded.reshape(
            stop - start, GROUPS, GROUP_SIZE
        ).max(axis=2)
        target_group = target_padded.reshape(
            stop - start, GROUPS, GROUP_SIZE
        ).max(axis=2)
        exact[start:stop] = np.rint(target_group * SCORE_SCALE).astype(np.int64)
        coarse_widths[start:stop] = (
            np.floor(coarse_group * SCORE_SCALE).astype(np.int64)
            + 1
            - floors[start:stop, None] * SCORE_SCALE
        ) * SCORE_STRIDE_PX
        radius = block_norms[start:stop] @ group_norms.T * score_gain
        upper[start:stop] = (
            np.floor(coarse_group * SCORE_SCALE).astype(np.int64)
            + 1
            + np.ceil(radius * SCORE_SCALE).astype(np.int64)
        )
    upper[:, list(HOT_GROUPS)] = exact[:, list(HOT_GROUPS)] + hot_allowance
    upper[:, selected_groups] += Q12_TRANSPORT_ALLOWANCE_BUCKETS
    order = np.argsort(-upper, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(upper, order, axis=1)
    ordered_exact = np.take_along_axis(exact, order, axis=1)
    incumbent = np.maximum.accumulate(ordered_exact, axis=1)
    done = incumbent[:, :-1] - ordered_upper[:, 1:] > stop_gap
    has_done = np.any(done, axis=1)
    counts = np.where(has_done, np.argmax(done, axis=1) + 1, GROUPS).astype(np.int64)
    return {
        "realized": realized,
        "blockNorms": block_norms,
        "upper": upper,
        "exact": exact,
        "coarseWidths": coarse_widths,
        "order": order,
        "counts": counts,
        "winners": winners,
        "floors": floors,
    }


def distribution(values: np.ndarray) -> dict[str, float | int]:
    return {
        "mean": float(np.mean(values)),
        "median": int(np.percentile(values, 50, method="higher")),
        "p95": int(np.percentile(values, 95, method="higher")),
        "p99": int(np.percentile(values, 99, method="higher")),
        "maximum": int(np.max(values)),
    }


def choose_fixtures(counts: np.ndarray, count: int = 6) -> np.ndarray:
    order = np.argsort(-counts, kind="stable")
    chosen = []
    used_counts = set()
    for state in order:
        value = int(counts[state])
        if value not in used_counts:
            chosen.append(int(state))
            used_counts.add(value)
        if len(chosen) == count - 1:
            break
    easy = int(np.flatnonzero(counts == counts.min())[0])
    if easy not in chosen:
        chosen.append(easy)
    for state in order:
        if len(chosen) == count:
            break
        if int(state) not in chosen:
            chosen.append(int(state))
    return np.asarray(chosen[:count], dtype=np.int64)


def main() -> None:
    started = time.perf_counter()
    for path in (
        SOURCE / "index.html",
        SOURCE / "topology.css",
        SOURCE / "reference.json",
        ALLOCATION,
        STATES,
        FINE / "reference.json",
        BOUND / "reference.json",
    ):
        if not path.exists():
            raise FileNotFoundError(path)
    if SELECTIVE_COUNT not in (2, 4, 8, 16, 32, 64, 96, 128, 195):
        raise ValueError("unsupported SELECTIVE_Q12_GROUPS")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    allocation = json.loads(ALLOCATION.read_text())
    allocation_row = next(
        item for item in allocation["selectiveQ12"]
        if item["name"] == f"tail-frequency-top-{SELECTIVE_COUNT}"
    )
    selected_groups = [int(group) for group in allocation_row["upgradedGroups"]]
    selected_rows = selected_row_indices(selected_groups)
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    q10_codes, _q10_scales, q10 = represented_rows(weights, Q10_MAXIMUM)
    q12_codes, q12_scales, q12 = represented_rows(weights, Q12_MAXIMUM)
    fine_scale = float(json.loads((FINE / "reference.json").read_text())["weightScale"])
    target = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    represented = q10.copy()
    represented[selected_rows] = q12[selected_rows]
    residual = target - represented
    row_norms = upper_block_norms(residual, BLOCK_WIDTH)
    padding = GROUPS * GROUP_SIZE - VOCABULARY
    group_norms = np.nextafter(
        np.max(
            np.pad(row_norms, ((0, padding), (0, 0))).reshape(
                GROUPS, GROUP_SIZE, BLOCK_COUNT
            ),
            axis=1,
        ),
        np.inf,
    )

    equivalent_bases, plane_reports, fonts = build_q12_fonts(q12_codes[selected_rows])
    source_range = float(source_reference["sourceInputRange"])
    document, replacement_count = replace_selected_candidates(
        (SOURCE / "index.html").read_text(),
        selected_rows,
        equivalent_bases,
        q12_scales,
        source_range,
    )
    def relink(document: str) -> str:
        return document.replace(
        'href="coarse-production.css"',
        f'href="../{SOURCE.name}/coarse-production.css"',
        1,
    ).replace(
        'href="fine-stage-production.css"',
        f'href="../{SOURCE.name}/fine-stage-production.css"',
        1,
    ).replace(
        '<link rel="stylesheet" href="topology.css">',
        '<link rel="stylesheet" href="selective-q12.css">'
        '<link rel="stylesheet" href="topology.css">',
        1,
        )

    document = relink(document).replace(
        "Production-range groupwise-Cauchy 23-stage block-flow cascade",
        f"Production mixed-q10/selective-q12-top{SELECTIVE_COUNT} cascade",
        1,
    )
    (OUTPUT / "index.html").write_text(document)
    control, control_replacements = replace_selected_candidates(
        (SOURCE / "control.html").read_text(),
        selected_rows,
        equivalent_bases,
        q12_scales,
        source_range,
    )
    if control_replacements != replacement_count:
        raise RuntimeError("candidate/control replacement counts differ")
    (OUTPUT / "control.html").write_text(relink(control))
    (OUTPUT / "selective-q12.css").write_text(selective_css())
    topology = (SOURCE / "topology.css").read_text() + (
        "\n.group-wrapper:has(>.group-grid>.selective-q12)>.group-bound{"
        "width:calc-size(max-content,round(down,size + "
        f"{(Q12_TRANSPORT_ALLOWANCE_BUCKETS + 1) * SCORE_STRIDE_PX}px,"
        f"{SCORE_STRIDE_PX}px))}}\n"
    )
    (OUTPUT / "topology.css").write_text(topology)

    bound_reference = json.loads((BOUND / "reference.json").read_text())
    source_block_range = float(bound_reference["blockAxisRange"])
    coefficients = build_bound_font(group_norms, source_block_range)
    np.save(OUTPUT / "group-q16-minus-mixed-q10-q12-norms-96.npy", group_norms)

    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(source_reference["productionInputRange"])
    score_gain = float(source_reference["scoreGain"])
    hot_allowance = int(source_reference["hotUpperAllowanceBuckets"])
    stop_gap = int(source_reference["stopGapBuckets"])
    corpus = corpus_route(
        hidden, represented, target, group_norms, production_range,
        score_gain, hot_allowance, stop_gap, selected_groups,
    )
    if int(corpus["counts"].max()) > int(source_reference["stages"]):
        raise RuntimeError("selective q12 corpus exceeds retained stage budget")
    fixture_indices = choose_fixtures(corpus["counts"])
    fixture_hidden = hidden[fixture_indices]
    production_block_range = float(source_reference["productionBlockAxisRange"])
    axis_pad = float(bound_reference["boundAxisPad"])
    fixture_block_norms, bound_widths, certified_full_gain = predicted_bounds(
        fixture_hidden,
        coefficients,
        group_norms,
        production_block_range,
        axis_pad,
    )
    certified = certified_full_gain * score_gain
    bound_widths[:, selected_groups] += (
        Q12_TRANSPORT_ALLOWANCE_BUCKETS * SCORE_STRIDE_PX
    )
    if np.any(bound_widths[:, 2:] + 1e-9 < certified[:, 2:]):
        raise RuntimeError("selective q12 bound prediction rounded inward")

    count_distribution = distribution(corpus["counts"])
    reference = {
        **source_reference,
        "backend": "production-range-groupwise-mixed-rowwise-q10-selective-q12",
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "runtimeContainsJavaScript": False,
        "sourceRetained": SOURCE.name,
        "exactControl": SOURCE.name,
        "exactControlFilename": "exact-control.html",
        "groupwiseResidual": "global-int16 target minus mixed rowwise-q10/selective-rowwise-q12 coarse",
        "groupwiseBoundFont": f"{BOUND_FONT}.woff2",
        "groupwiseBoundFontBytes": (OUTPUT / f"{BOUND_FONT}.woff2").stat().st_size,
        "groupwiseCoefficientMaximum": int(coefficients.max()),
        "selectivePrecision": {
            "bits": 12,
            "selectionRule": "groups most often visited by baseline-q10 tail states",
            "groupCount": SELECTIVE_COUNT,
            "groups": selected_groups,
            "rows": int(len(selected_rows)),
            "q10RowsReplaced": replacement_count,
            "quantization": "rowwise symmetric q12",
            "transport": "radix-64 high/residual, three 256-axis shards per plane",
            "radix": RADIX,
            "planes": 2,
            "shardsPerPlane": SHARDS,
            "glyphsPerSelectedRow": 6,
            "incrementalGlyphsPerSelectedRowOverQ10": 3,
            "incrementalShapedGlyphs": int(len(selected_rows) * 3),
            "displayScale": DISPLAY_SCALE,
            "transportAllowanceBuckets": Q12_TRANSPORT_ALLOWANCE_BUCKETS,
            "planeReports": plane_reports,
            "woff2Bytes": sum(path.stat().st_size for path in fonts),
        },
        "largeFontBytesGenerated": sum(path.stat().st_size for path in fonts),
        "corpusRoute": {
            "states": len(hidden),
            "groups": count_distribution,
            "withinOne": int(np.sum(corpus["counts"] <= 1)),
            "withinSix": int(np.sum(corpus["counts"] <= 6)),
            "withinTwelve": int(np.sum(corpus["counts"] <= 12)),
            "withinFourteen": int(np.sum(corpus["counts"] <= 14)),
            "tailExcessAfterSix": int(np.sum(np.maximum(corpus["counts"] - 6, 0))),
        },
        "certifiedFixtures": {
            "sourceStateIndices": fixture_indices.astype(int).tolist(),
            "requiredGroupsAtCalibratedStop": corpus["counts"][fixture_indices].astype(int).tolist(),
            "hiddenVectors": fixture_hidden.tolist(),
            "scoreFloors": corpus["floors"][fixture_indices].astype(int).tolist(),
            "denseWinners": corpus["winners"][fixture_indices].astype(int).tolist(),
        },
        "groupwiseFixtures": {
            "blockNorms": fixture_block_norms.tolist(),
            "predictedCoarseWidths": corpus["coarseWidths"][fixture_indices].tolist(),
            "predictedBoundWidths": bound_widths.tolist(),
            "certifiedRadiusPixels": certified.tolist(),
        },
        "assets": {
            **source_reference["assets"],
            "selectiveQ12FontFiles": len(fonts),
            "selectiveQ12Woff2Bytes": sum(path.stat().st_size for path in fonts),
            "selectiveQ12FontsBuilt": True,
        },
        "generatedBytes": {
            "index.html": (OUTPUT / "index.html").stat().st_size,
            "control.html": (OUTPUT / "control.html").stat().st_size,
            "selective-q12.css": (OUTPUT / "selective-q12.css").stat().st_size,
            "topology.css": (OUTPUT / "topology.css").stat().st_size,
            "reference.json": 0,
        },
        "offlineSeconds": time.perf_counter() - started,
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    for _pass in range(2):
        reference["generatedBytes"]["reference.json"] = reference_path.stat().st_size
        reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "selectedGroups": SELECTIVE_COUNT,
        "selectedRows": len(selected_rows),
        "fontBytes": sum(path.stat().st_size for path in fonts),
        "incrementalShapedGlyphs": len(selected_rows) * 3,
        "corpusGroups": count_distribution,
        "fixtures": reference["certifiedFixtures"]["requiredGroupsAtCalibratedStop"],
        "offlineSeconds": reference["offlineSeconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
