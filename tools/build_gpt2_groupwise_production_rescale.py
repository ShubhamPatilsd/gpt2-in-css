#!/usr/bin/env python3
"""Reuse the q10/q16 font banks at the observed production hidden range."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
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
SOURCE = ROOT / "experiments" / os.environ.get(
    "PRODUCTION_RESCALE_SOURCE",
    "gpt2-groupwise-cauchy-blockflow-cascade-unrolled23",
)
OFFLINE = (
    ROOT
    / "experiments"
    / "gpt2-groupwise-cauchy-blockflow-cascade"
    / "offline-results.json"
)
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-int10-shard256"
COARSE_CSS = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-shard256"
    / "index.css"
)
FINE_STAGE_CSS = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256"
    / "index.css"
)
EXACT = ROOT / "experiments" / os.environ.get(
    "PRODUCTION_RESCALE_EXACT",
    "gpt2-hvar-grid-output-head-certified-int10-unrolled23-gated",
)
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
BOUND = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
OUTPUT = ROOT / "experiments" / os.environ.get(
    "PRODUCTION_RESCALE_OUTPUT",
    "gpt2-groupwise-cauchy-blockflow-production-range",
)
ALLOW_INCOMPLETE = os.environ.get("PRODUCTION_RESCALE_ALLOW_INCOMPLETE") == "1"
GROUPS = 197
SCORE_STRIDE_PX = 4


def css_number(value: float) -> str:
    text = f"{float(value):.12g}"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def rescale_factors(document: str, ratio: float) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"--factor:{css_number(float(match.group(1)) * ratio)}"

    return re.sub(r"--factor:([-+0-9.eE]+)", replace, document), count


def rescale_axis_css(css: str, source_range: float, target_range: float) -> str:
    source = css_number(source_range)
    target = css_number(target_range)
    count = css.count(source)
    if count == 0:
        raise RuntimeError(f"axis denominator {source} not found")
    return css.replace(source, target)


def build_production_bound(
    group_norms: np.ndarray,
    block_axis_range: float,
) -> np.ndarray:
    coefficients = np.ceil(
        group_norms * block_axis_range * BOUND_QUANTIZATION
    ).astype(np.int16)
    coefficients[list(HOT_GROUPS)] = 0
    if np.any(coefficients < 0) or int(coefficients.max()) > 32_767:
        raise RuntimeError("production bound coefficients do not fit int16")
    bases = np.sum(coefficients.astype(np.int64), axis=1)
    if int(bases.max()) > 65_535:
        raise RuntimeError("production bound base advance does not fit uint16")
    font_path = OUTPUT / f"{BOUND_FONT}.ttf"
    build_direct_font_backend(
        coefficients,
        font_path,
        signed_axes=False,
        base_advance=bases,
        codepoint_start=BOUND_CODEPOINT_START,
        axis_tags=[f"b{block:03d}" for block in range(BLOCK_COUNT)],
        allow_out_of_range_result=True,
    )
    font = TTFont(font_path, recalcTimestamp=False)
    for glyph, (_advance, lsb) in font["hmtx"].metrics.items():
        font["hmtx"].metrics[glyph] = (0, lsb)
    font["hhea"].advanceWidthMax = 0
    font.recalcTimestamp = False
    font.save(font_path)
    compressed = TTFont(font_path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(font_path.with_suffix(".woff2"))
    return coefficients


def main() -> None:
    required = (
        SOURCE / "index.html",
        SOURCE / "control.html",
        SOURCE / "topology.css",
        SOURCE / "reference.json",
        OFFLINE,
        STATES,
        COARSE / "reference.json",
        COARSE_CSS,
        FINE_STAGE_CSS,
        EXACT / "index.html",
        EXACT / "index.css",
        FINE / "reference.json",
        BOUND / "reference.json",
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    offline = json.loads(OFFLINE.read_text())
    source_range = float(json.loads((COARSE / "reference.json").read_text())["inputRange"])
    production_range = float(offline["productionInputRange"])
    coordinate_ratio = production_range / source_range
    score_gain = source_range / production_range
    upper_transport_shortfall = 1
    production_stop_gap = (
        int(source_reference["stopGapBuckets"]) + upper_transport_shortfall
    )
    bound_reference = json.loads((BOUND / "reference.json").read_text())
    source_block_range = float(bound_reference["blockAxisRange"])
    production_block_range = math.sqrt(BLOCK_WIDTH) * production_range
    axis_pad = float(bound_reference["boundAxisPad"])
    OUTPUT.mkdir(parents=True, exist_ok=True)

    saved = np.load(STATES)
    fixture_indices = np.asarray(offline["browserFixtureIndices"], dtype=np.int64)
    hidden = np.asarray(saved["hidden"][fixture_indices], dtype=np.float64)
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: head.VOCABULARY],
        dtype=np.float64,
    )
    fine_scale = float(json.loads((FINE / "reference.json").read_text())["weightScale"])
    target = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    row_scales = np.max(np.abs(weights), axis=1) / 511.0
    row_scales[row_scales == 0] = 1.0
    coarse = np.rint(weights / row_scales[:, None]).clip(-511, 511) * row_scales[:, None]
    target_scores = realized @ target.T * score_gain
    coarse_scores = realized @ coarse.T * score_gain
    winners = np.argmax(target_scores, axis=1).astype(np.int64)
    score_floors = np.floor(
        np.minimum(np.min(target_scores, axis=1), np.min(coarse_scores, axis=1))
    ).astype(np.int64) - 2

    group_norms = np.load(SOURCE / "group-q16-minus-q10-norms-96.npy")
    padded_rows = GROUPS * head.GROUP_SIZE
    coarse_padded = np.full((len(hidden), padded_rows), -np.inf)
    target_padded = np.full_like(coarse_padded, -np.inf)
    coarse_padded[:, : head.VOCABULARY] = coarse_scores
    target_padded[:, : head.VOCABULARY] = target_scores
    coarse_group = coarse_padded.reshape(
        len(hidden), GROUPS, head.GROUP_SIZE
    ).max(axis=2)
    target_group = target_padded.reshape(
        len(hidden), GROUPS, head.GROUP_SIZE
    ).max(axis=2)
    radius_scores = (
        np.linalg.norm(
            hidden.reshape(len(hidden), BLOCK_COUNT, BLOCK_WIDTH), axis=2
        )
        @ group_norms.T
        * score_gain
    )
    target_group_buckets = np.rint(target_group * 256).astype(np.int64)
    upper_buckets = (
        np.floor(coarse_group * 256).astype(np.int64)
        + 1
        + np.ceil(radius_scores * 256).astype(np.int64)
    )
    upper_buckets[:, list(HOT_GROUPS)] = (
        target_group_buckets[:, list(HOT_GROUPS)]
        + int(source_reference["hotUpperAllowanceBuckets"])
    )
    order = np.argsort(-upper_buckets, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(upper_buckets, order, axis=1)
    ordered_exact = np.take_along_axis(target_group_buckets, order, axis=1)
    incumbent = np.maximum.accumulate(ordered_exact, axis=1)
    done = (
        incumbent[:, :-1] - ordered_upper[:, 1:]
        > production_stop_gap
    )
    has_done = np.any(done, axis=1)
    required_counts = np.where(
        has_done, np.argmax(done, axis=1) + 1, GROUPS
    ).astype(np.int64)
    if (
        int(required_counts.max()) > int(source_reference["stages"])
        and not ALLOW_INCOMPLETE
    ):
        raise RuntimeError(
            f"production fixtures require {int(required_counts.max())} stages, "
            f"but source has {source_reference['stages']}"
        )
    coefficients = build_production_bound(group_norms, source_block_range)
    block_norms, bound_widths, certified_full_gain = predicted_bounds(
        hidden,
        coefficients,
        group_norms,
        production_block_range,
        axis_pad,
    )
    certified = certified_full_gain * score_gain
    if np.any(bound_widths[:, 2:] + 1e-9 < certified[:, 2:]):
        raise RuntimeError("production bound prediction rounded inward")

    candidate = (SOURCE / "index.html").read_text()
    control = (SOURCE / "control.html").read_text()
    exact = (EXACT / "index.html").read_text()
    candidate_factors = control_factors = exact_factors = 0
    candidate = candidate.replace(
        "../gpt2-hvar-grid-output-head-certified-upper-int10-shard256/index.css",
        "coarse-production.css",
    ).replace(
        "../gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256/index.css",
        "fine-stage-production.css",
    ).replace(
        "Groupwise-Cauchy six-stage block-flow cascade",
        f"Production-range groupwise-Cauchy {source_reference['stages']}-stage "
        "block-flow cascade",
    )
    control = control.replace(
        "../gpt2-hvar-grid-output-head-certified-upper-int10-shard256/index.css",
        "coarse-production.css",
    ).replace(
        "../gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256/index.css",
        "fine-stage-production.css",
    )
    exact = exact.replace('href="index.css"', 'href="exact-control-production.css"')

    topology = rescale_axis_css(
        (SOURCE / "topology.css").read_text(),
        source_block_range,
        production_block_range,
    )
    source_done_term = f" - {int(source_reference['stopGapBuckets']) + 1}) + 1"
    production_done_term = f" - {production_stop_gap + 1}) + 1"
    done_term_count = topology.count(source_done_term)
    if done_term_count != int(source_reference["stages"]):
        raise RuntimeError(
            f"expected {source_reference['stages']} stop terms, found {done_term_count}"
        )
    topology = topology.replace(source_done_term, production_done_term)
    coarse_css = rescale_axis_css(COARSE_CSS.read_text(), source_range, production_range)
    fine_stage_css = rescale_axis_css(
        FINE_STAGE_CSS.read_text(), source_range, production_range
    )
    exact_css = rescale_axis_css(
        (EXACT / "index.css").read_text(), source_range, production_range
    )

    (OUTPUT / "index.html").write_text(candidate)
    (OUTPUT / "control.html").write_text(control)
    (OUTPUT / "exact-control.html").write_text(exact)
    (OUTPUT / "topology.css").write_text(topology)
    (OUTPUT / "coarse-production.css").write_text(coarse_css)
    (OUTPUT / "fine-stage-production.css").write_text(fine_stage_css)
    (OUTPUT / "exact-control-production.css").write_text(exact_css)
    np.save(OUTPUT / "group-q16-minus-q10-norms-96.npy", group_norms)

    required_counts_list = required_counts.astype(int).tolist()
    reference = {
        **source_reference,
        "backend": "zero-copy-production-range-groupwise-cauchy-blockflow",
        "sourceRetained": SOURCE.name,
        "exactControl": OUTPUT.name,
        "exactControlFilename": "exact-control.html",
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "runtimeContainsJavaScript": False,
        "sourceInputRange": source_range,
        "productionInputRange": production_range,
        "productionBlockAxisRange": production_block_range,
        "coordinateRangeRatio": coordinate_ratio,
        "scoreGain": score_gain,
        "factorRescaleRatio": 1.0,
        "upperTransportShortfallBuckets": upper_transport_shortfall,
        "sourceStopGapBuckets": int(source_reference["stopGapBuckets"]),
        "stopGapBuckets": production_stop_gap,
        "fontBankStrategy": (
            "reuse existing q10/q16 WOFF2 banks without rebuilding or copying; "
            "hold the source score gain because argmax is positively homogeneous"
        ),
        "largeFontBytesGenerated": 0,
        "corpusCompleteWithinSourceStages": bool(
            int(required_counts.max()) <= int(source_reference["stages"])
        ),
        "groupwiseCoefficientMaximum": int(coefficients.max()),
        "groupwiseBoundFontBytes": (OUTPUT / f"{BOUND_FONT}.woff2").stat().st_size,
        "certifiedFixtures": {
            "sourceStateIndices": fixture_indices.tolist(),
            "requiredGroupsAtCalibratedStop": required_counts_list,
            "hiddenVectors": hidden.tolist(),
            "scoreFloors": score_floors.tolist(),
            "denseWinners": winners.tolist(),
        },
        "groupwiseFixtures": {
            "blockNorms": block_norms.tolist(),
            "predictedBoundWidths": bound_widths.tolist(),
            "certifiedRadiusPixels": certified.tolist(),
        },
        "rescaledFactorCounts": {
            "candidate": candidate_factors,
            "control": control_factors,
            "exactControl": exact_factors,
        },
        "generatedBytes": {
            "index.html": len(candidate.encode()),
            "control.html": len(control.encode()),
            "exact-control.html": len(exact.encode()),
            "topology.css": len(topology.encode()),
            "coarse-production.css": len(coarse_css.encode()),
            "fine-stage-production.css": len(fine_stage_css.encode()),
            "exact-control-production.css": len(exact_css.encode()),
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "sourceRange": source_range,
        "productionRange": production_range,
        "coordinateRatio": coordinate_ratio,
        "scoreGain": score_gain,
        "fixtures": list(zip(fixture_indices.tolist(), required_counts_list, winners.tolist())),
        "largeFontBytesGenerated": 0,
        "boundFontBytes": reference["groupwiseBoundFontBytes"],
        "factorCounts": reference["rescaledFactorCounts"],
    }, indent=2))


if __name__ == "__main__":
    main()
