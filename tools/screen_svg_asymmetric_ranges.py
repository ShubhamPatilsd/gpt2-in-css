#!/usr/bin/env python3
"""Screen asymmetric activation ranges for the 8-bit SVG backend.

The current SVG chain centers every materialized activation at code 128.  That
spends half the codes on negative values even for strongly asymmetric tensors
such as post-GELU activations.  This experiment compares that baseline with
fixed min/max ranges learned on a disjoint calibration set.

This is an offline numerical screen.  A winning layout still has to be emitted
as an HTML/SVG graph and measured in Chromium.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_svg_quantization_strategies import (
    Block,
    exact_forward,
    gelu_new,
    layer_norm,
    load_checkpoint,
    log_uniform,
    png_weight_quantized,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-asymmetric-ranges" / "results.json"
CALIBRATION_CASES = 256
EVALUATION_CASES = 512
NATURAL_TOKEN_IDS = (
    7454, 2402, 257, 640, 612, 373, 1310, 2576, 508, 5615, 1474, 262,
    8222, 13, 3198, 1110, 673, 1043, 1402, 3290, 4953, 13970, 2975, 464,
    2933, 4721, 3420, 290, 3114, 2641, 5897, 2119, 32, 1611, 1468, 2415,
    2921, 683, 5814, 9396, 286, 17141, 2990, 6807, 1363, 1978, 739, 6016,
    4171, 6766, 38582, 7812, 7838, 1625, 422, 2157, 7150, 40, 892, 356,
    815, 1037, 674, 1545,
)


@dataclass(frozen=True)
class SurfacePlan:
    """Decode an 8-bit code as ``(code - zero) * step`` per channel."""

    zero: np.ndarray
    step: np.ndarray
    groups_used: int


@dataclass(frozen=True)
class LinearPlan:
    weight: np.ndarray


def _range_kmeans(values: np.ndarray, groups: int) -> np.ndarray:
    lows = np.min(values, axis=0)
    highs = np.max(values, axis=0)
    midpoints = 0.5 * (lows + highs)
    log_spans = np.log2(np.maximum(highs - lows, 1e-12))
    features = np.stack((midpoints, log_spans), axis=1)
    feature_scale = np.maximum(np.std(features, axis=0), 1e-9)
    features = (features - np.mean(features, axis=0)) / feature_scale

    # Deterministic farthest-point seeding avoids making this screen depend on
    # a lucky random initialization.
    median = np.median(features, axis=0)
    first = int(np.argmin(np.sum((features - median) ** 2, axis=1)))
    centers = [features[first]]
    nearest = np.sum((features - centers[0]) ** 2, axis=1)
    for _ in range(1, groups):
        next_index = int(np.argmax(nearest))
        centers.append(features[next_index])
        distance = np.sum((features - centers[-1]) ** 2, axis=1)
        nearest = np.minimum(nearest, distance)
    centers_array = np.asarray(centers)
    ids = np.zeros(len(features), dtype=np.int32)
    for _ in range(50):
        distances = np.sum(
            (features[:, None, :] - centers_array[None, :, :]) ** 2,
            axis=2,
        )
        next_ids = np.argmin(distances, axis=1).astype(np.int32)
        if np.array_equal(next_ids, ids):
            break
        ids = next_ids
        for group in range(groups):
            members = features[ids == group]
            if len(members):
                centers_array[group] = np.mean(members, axis=0)
    return ids


def _group_ids(
    values: np.ndarray,
    groups: int,
    asymmetric: bool,
    clustering: str,
) -> np.ndarray:
    if groups >= values.shape[1]:
        return np.arange(values.shape[1], dtype=np.int32)
    if asymmetric and clustering == "range-kmeans":
        return _range_kmeans(values, groups)
    if asymmetric:
        metric = np.ptp(values, axis=0)
    else:
        metric = np.max(np.abs(values), axis=0)
    return log_uniform(np.maximum(metric, 1e-12), groups).astype(np.int32)


def fit_surface(
    values: np.ndarray,
    *,
    groups: int,
    asymmetric: bool,
    headroom: float,
    clustering: str,
) -> SurfacePlan:
    ids = _group_ids(values, groups, asymmetric, clustering)
    zero = np.empty(values.shape[1], dtype=np.float64)
    step = np.empty(values.shape[1], dtype=np.float64)
    groups_used = 0
    for group in np.unique(ids):
        mask = ids == group
        members = values[:, mask]
        if asymmetric:
            low = float(np.min(members))
            high = float(np.max(members))
            midpoint = 0.5 * (low + high)
            half_span = max(0.5 * (high - low) * headroom, 1e-9)
            low = midpoint - half_span
            high = midpoint + half_span
            group_step = (high - low) / 255.0
            group_zero = -low / group_step
        else:
            scale = max(float(np.max(np.abs(members))) * headroom, 1e-9)
            group_step = 2.0 * scale / 255.0
            group_zero = 128.0
        zero[mask] = group_zero
        step[mask] = group_step
        groups_used += 1
    return SurfacePlan(zero=zero, step=step, groups_used=groups_used)


def apply_surface(values: np.ndarray, plan: SurfacePlan) -> tuple[np.ndarray, int]:
    raw = plan.zero + values / plan.step
    clipped = int(np.count_nonzero((raw < 0.0) | (raw > 255.0)))
    codes = np.clip(np.rint(raw), 0.0, 255.0)
    return (codes - plan.zero) * plan.step, clipped


def fit_plans(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    *,
    groups: int,
    asymmetric: bool,
    headroom: float,
    asymmetric_stages: frozenset[str] | None = None,
    clustering: str = "span-uniform",
) -> tuple[list[SurfacePlan], list[tuple[LinearPlan, LinearPlan, LinearPlan]]]:
    surfaces: list[SurfacePlan] = []
    linears: list[tuple[LinearPlan, LinearPlan, LinearPlan]] = []

    def add(values: np.ndarray, stage: str) -> None:
        use_asymmetric = asymmetric and (
            asymmetric_stages is None or stage in asymmetric_stages
        )
        surfaces.append(
            fit_surface(
                values,
                groups=groups,
                asymmetric=use_asymmetric,
                headroom=headroom,
                clustering=clustering,
            )
        )

    states = inputs.copy()
    add(states, "state")
    for block in blocks:
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        attention_weight = png_weight_quantized(block.attention_weight)
        add(normalized1, "normalized")
        learned = normalized1 @ attention_weight.T + block.attention_bias
        add(learned, "affine")
        residual = states + learned
        add(residual, "state")

        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        fc_weight = png_weight_quantized(block.fc_weight)
        add(normalized2, "normalized")
        pre = normalized2 @ fc_weight.T + block.fc_bias
        add(pre, "affine")
        hidden = gelu_new(pre)
        add(hidden, "hidden")

        projection_weight = png_weight_quantized(block.projection_weight)
        add(hidden, "hidden")
        projected = hidden @ projection_weight.T + block.projection_bias
        add(projected, "affine")
        states = residual + projected
        add(states, "state")
        linears.append(
            (
                LinearPlan(attention_weight),
                LinearPlan(fc_weight),
                LinearPlan(projection_weight),
            )
        )

    final = np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    add(final, "normalized")
    return surfaces, linears


def run_fixed(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    surfaces: list[SurfacePlan],
    linears: list[tuple[LinearPlan, LinearPlan, LinearPlan]],
) -> tuple[np.ndarray, int]:
    surface_index = 0
    clipped = 0

    def materialize(values: np.ndarray) -> np.ndarray:
        nonlocal surface_index, clipped
        result, count = apply_surface(values, surfaces[surface_index])
        surface_index += 1
        clipped += count
        return result

    states = materialize(inputs)
    for block, (attention, fc, projection) in zip(blocks, linears):
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        normalized1 = materialize(normalized1)
        learned = materialize(
            normalized1 @ attention.weight.T + block.attention_bias
        )
        residual = materialize(states + learned)

        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        normalized2 = materialize(normalized2)
        pre = materialize(normalized2 @ fc.weight.T + block.fc_bias)
        hidden = materialize(gelu_new(pre))
        projection_input = materialize(hidden)
        projected = materialize(
            projection_input @ projection.weight.T + block.projection_bias
        )
        states = materialize(residual + projected)

    final = materialize(
        np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    )
    assert surface_index == len(surfaces)
    return final, clipped


def winners(states: np.ndarray, embedding: np.ndarray, batch: int = 32) -> np.ndarray:
    result: list[int] = []
    for start in range(0, len(states), batch):
        result.extend(np.argmax(states[start : start + batch] @ embedding.T, axis=1))
    return np.asarray(result, dtype=np.int64)


def main() -> None:
    _, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    tensors = SafeTensors(MODEL_PATH)
    position = np.asarray(tensors.tensor("wpe.weight")[0], dtype=np.float64)
    excluded = set(NATURAL_TOKEN_IDS)
    candidates = np.asarray(
        [index for index in range(len(embedding)) if index not in excluded],
        dtype=np.int64,
    )
    rng = np.random.default_rng(0x4153594D)
    sampled = rng.choice(
        candidates,
        size=CALIBRATION_CASES + EVALUATION_CASES - len(NATURAL_TOKEN_IDS),
        replace=False,
    )
    calibration = embedding[sampled[:CALIBRATION_CASES]] + position
    natural = embedding[np.asarray(NATURAL_TOKEN_IDS)] + position
    evaluation = np.concatenate(
        (
            natural,
            embedding[sampled[CALIBRATION_CASES:]] + position,
        )
    )
    reference = exact_forward(evaluation, blocks, final_gamma, final_beta)
    reference_winners = winners(reference, embedding)

    configurations = (
        ("symmetric-32", 32, False, 1.10, None, "span-uniform"),
        ("asymmetric-state-16", 16, True, 1.05, frozenset(("state",)), "span-uniform"),
        ("asymmetric-state-32", 32, True, 1.00, frozenset(("state",)), "span-uniform"),
        ("asymmetric-state-32", 32, True, 1.05, frozenset(("state",)), "span-uniform"),
        ("asymmetric-state-32", 32, True, 1.10, frozenset(("state",)), "span-uniform"),
        ("asymmetric-state-64", 64, True, 1.05, frozenset(("state",)), "span-uniform"),
        ("asymmetric-state-32-kmeans", 32, True, 1.00, frozenset(("state",)), "range-kmeans"),
        ("asymmetric-state-32-kmeans", 32, True, 1.05, frozenset(("state",)), "range-kmeans"),
        ("asymmetric-state-32-kmeans", 32, True, 1.10, frozenset(("state",)), "range-kmeans"),
        ("asymmetric-all-32-kmeans", 32, True, 1.05, None, "range-kmeans"),
        ("asymmetric-hidden-32", 32, True, 1.05, frozenset(("hidden",)), "span-uniform"),
        ("asymmetric-affine-32", 32, True, 1.05, frozenset(("affine",)), "span-uniform"),
        ("asymmetric-normalized-32", 32, True, 1.05, frozenset(("normalized",)), "span-uniform"),
        (
            "asymmetric-hidden-affine-32",
            32,
            True,
            1.05,
            frozenset(("hidden", "affine")),
            "span-uniform",
        ),
        ("asymmetric-16", 16, True, 1.05, None, "span-uniform"),
        ("asymmetric-32", 32, True, 1.00, None, "span-uniform"),
        ("asymmetric-32", 32, True, 1.05, None, "span-uniform"),
        ("asymmetric-32", 32, True, 1.10, None, "span-uniform"),
        ("asymmetric-per-channel", 3072, True, 1.05, None, "span-uniform"),
    )
    rows: list[dict[str, object]] = []
    for name, groups, asymmetric, headroom, asymmetric_stages, clustering in configurations:
        surfaces, linears = fit_plans(
            calibration,
            blocks,
            final_gamma,
            final_beta,
            groups=groups,
            asymmetric=asymmetric,
            headroom=headroom,
            asymmetric_stages=asymmetric_stages,
            clustering=clustering,
        )
        actual, clipped = run_fixed(
            evaluation,
            blocks,
            final_gamma,
            final_beta,
            surfaces,
            linears,
        )
        actual_winners = winners(actual, embedding)
        error = actual - reference
        row = {
            "name": name,
            "groups": groups,
            "asymmetric": asymmetric,
            "headroom": headroom,
            "asymmetricStages": (
                sorted(asymmetric_stages) if asymmetric_stages is not None else "all"
            ),
            "clustering": clustering,
            "winnerMatches": int(np.count_nonzero(actual_winners == reference_winners)),
            "winnerMatchFraction": float(np.mean(actual_winners == reference_winners)),
            "naturalWinnerMatches": int(
                np.count_nonzero(
                    actual_winners[: len(NATURAL_TOKEN_IDS)]
                    == reference_winners[: len(NATURAL_TOKEN_IDS)]
                )
            ),
            "naturalWinnerMatchFraction": float(
                np.mean(
                    actual_winners[: len(NATURAL_TOKEN_IDS)]
                    == reference_winners[: len(NATURAL_TOKEN_IDS)]
                )
            ),
            "finalHiddenRmse": float(np.sqrt(np.mean(error**2))),
            "maxError": float(np.max(np.abs(error))),
            "clippedValues": clipped,
            "meanGroupsUsed": float(
                np.mean([surface.groups_used for surface in surfaces])
            ),
        }
        rows.append(row)
        print(json.dumps(row))

    payload = {
        "model": str(MODEL_PATH),
        "calibrationCases": CALIBRATION_CASES,
        "evaluationCases": EVALUATION_CASES,
        "naturalCases": len(NATURAL_TOKEN_IDS),
        "scope": "12 one-token GPT-2-small blocks with every SVG-like activation surface materialized to 8 bits",
        "note": "Offline screen; finalists require a Chromium SVG implementation",
        "results": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
