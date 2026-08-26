#!/usr/bin/env python3
"""Screen parallel RGB phase-dithered executions of the SVG GPT-2 chain.

Each color channel uses the same eight-bit range but a different quantization
threshold. SVG filters process RGB channels in parallel, so a useful result may
increase effective precision without multiplying DOM/filter objects by three.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_svg_quantization_strategies import exact_forward, gelu_new, layer_norm, load_checkpoint
from screen_svg_asymmetric_ranges import (
    CALIBRATION_CASES,
    EVALUATION_CASES,
    NATURAL_TOKEN_IDS,
    LinearPlan,
    SurfacePlan,
    fit_plans,
    winners,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-rgb-dither-ensemble" / "results.json"


def run_phase(
    inputs: np.ndarray,
    blocks,
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    surfaces: list[SurfacePlan],
    linears: list[tuple[LinearPlan, LinearPlan, LinearPlan]],
    phases: np.ndarray,
) -> tuple[np.ndarray, int]:
    surface_index = 0
    clipped = 0

    def materialize(values: np.ndarray) -> np.ndarray:
        nonlocal surface_index, clipped
        plan = surfaces[surface_index]
        phase = phases[surface_index]
        raw = plan.zero + values / plan.step + phase
        clipped += int(np.count_nonzero((raw < 0.0) | (raw > 255.0)))
        codes = np.clip(np.rint(raw), 0.0, 255.0)
        surface_index += 1
        return (codes - phase - plan.zero) * plan.step

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


def phase_matrix(channels: int, surfaces: int, rotating: bool) -> np.ndarray:
    base = (np.arange(channels, dtype=np.float64) + 0.5) / channels - 0.5
    result = np.empty((channels, surfaces), dtype=np.float64)
    for channel in range(channels):
        for surface in range(surfaces):
            index = (channel + surface) % channels if rotating else channel
            result[channel, surface] = base[index]
    return result


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
    evaluation = np.concatenate(
        (
            embedding[np.asarray(NATURAL_TOKEN_IDS)] + position,
            embedding[sampled[CALIBRATION_CASES:]] + position,
        )
    )
    reference = exact_forward(evaluation, blocks, final_gamma, final_beta)
    reference_winners = winners(reference, embedding)

    rows: list[dict[str, object]] = []
    for headroom in (1.05, 1.10, 1.20):
        surfaces, linears = fit_plans(
            calibration,
            blocks,
            final_gamma,
            final_beta,
            groups=32,
            asymmetric=False,
            headroom=headroom,
        )
        for channels, rotating in ((1, False), (2, True), (3, False), (3, True), (4, True)):
            phase_sets = phase_matrix(channels, len(surfaces), rotating)
            executions = []
            clipped = 0
            for phases in phase_sets:
                output, count = run_phase(
                    evaluation,
                    blocks,
                    final_gamma,
                    final_beta,
                    surfaces,
                    linears,
                    phases,
                )
                executions.append(output)
                clipped += count
            actual = np.mean(executions, axis=0)
            actual_winners = winners(actual, embedding)
            error = actual - reference
            row = {
                "name": (
                    "ordinary"
                    if channels == 1
                    else f"{channels}-channel-{'rotating' if rotating else 'fixed'}"
                ),
                "channels": channels,
                "rotating": rotating,
                "headroom": headroom,
                "winnerMatches": int(
                    np.count_nonzero(actual_winners == reference_winners)
                ),
                "winnerMatchFraction": float(
                    np.mean(actual_winners == reference_winners)
                ),
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
                "clippedValuesAcrossChannels": clipped,
            }
            rows.append(row)
            print(json.dumps(row))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "model": str(MODEL_PATH),
                "calibrationCases": CALIBRATION_CASES,
                "evaluationCases": EVALUATION_CASES,
                "naturalCases": len(NATURAL_TOKEN_IDS),
                "scope": "ideal channel-parallel simulation of all 110 eight-bit activation boundaries",
                "results": rows,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
