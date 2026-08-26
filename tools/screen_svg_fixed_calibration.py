#!/usr/bin/env python3
"""Cross-validate fixed W8A8 SVG surface scales on real GPT-2 token inputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_svg_quantization_strategies import (
    Block,
    exact_forward,
    gelu_new,
    layer_norm,
    load_checkpoint,
    log_uniform,
    png_weight_quantized,
)


@dataclass(frozen=True)
class SurfacePlan:
    ids: np.ndarray
    scales: np.ndarray


@dataclass(frozen=True)
class LinearPlan:
    smooth: np.ndarray
    weight: np.ndarray


@dataclass(frozen=True)
class CorrectionPlan:
    blocks: list[tuple[np.ndarray, np.ndarray, np.ndarray]]
    final: np.ndarray


def fit_surface(values: np.ndarray, groups: int, headroom: float) -> SurfacePlan:
    bounds = np.maximum(np.max(np.abs(values), axis=0) * headroom, 1e-9)
    ids = log_uniform(bounds, groups)
    scales = np.empty_like(bounds)
    for group in range(groups):
        mask = ids == group
        if np.any(mask):
            scales[mask] = float(np.max(bounds[mask]))
    return SurfacePlan(ids=ids, scales=scales)


def apply_surface(
    values: np.ndarray, plan: SurfacePlan
) -> tuple[np.ndarray, int]:
    raw = 128.0 + values / (2 * plan.scales) * 255.0
    clipped = int(np.count_nonzero((raw < 0) | (raw > 255)))
    encoded = np.clip(np.rint(raw), 0, 255)
    return (encoded - 128.0) / 255.0 * (2 * plan.scales), clipped


def fit_linear(
    activations: np.ndarray,
    weight: np.ndarray,
    alpha: float,
) -> LinearPlan:
    activation_max = np.maximum(np.max(np.abs(activations), axis=0), 1e-8)
    weight_max = np.maximum(np.max(np.abs(weight), axis=0), 1e-8)
    if alpha == 0:
        smooth = np.ones_like(activation_max)
    else:
        smooth = activation_max**alpha / weight_max ** (1.0 - alpha)
        smooth = np.clip(smooth, 1e-5, 1e5)
    return LinearPlan(
        smooth=smooth,
        weight=png_weight_quantized(weight * smooth[None, :]),
    )


def fit_plans(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    groups: int,
    headroom: float,
    alpha: float,
) -> tuple[list[SurfacePlan], list[tuple[LinearPlan, LinearPlan, LinearPlan]]]:
    surfaces: list[SurfacePlan] = []
    linears: list[tuple[LinearPlan, LinearPlan, LinearPlan]] = []
    states = inputs.copy()
    surfaces.append(fit_surface(states, groups, headroom))
    for block in blocks:
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        attention_plan = fit_linear(normalized1, block.attention_weight, alpha)
        attention_input = normalized1 / attention_plan.smooth
        surfaces.append(fit_surface(attention_input, groups, headroom))
        learned = attention_input @ attention_plan.weight.T + block.attention_bias
        surfaces.append(fit_surface(learned, groups, headroom))
        residual = states + learned
        surfaces.append(fit_surface(residual, groups, headroom))

        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        fc_plan = fit_linear(normalized2, block.fc_weight, alpha)
        fc_input = normalized2 / fc_plan.smooth
        surfaces.append(fit_surface(fc_input, groups, headroom))
        pre = fc_input @ fc_plan.weight.T + block.fc_bias
        surfaces.append(fit_surface(pre, groups, headroom))
        hidden = gelu_new(pre)
        surfaces.append(fit_surface(hidden, groups, headroom))

        projection_plan = fit_linear(hidden, block.projection_weight, alpha)
        projection_input = hidden / projection_plan.smooth
        surfaces.append(fit_surface(projection_input, groups, headroom))
        projected = projection_input @ projection_plan.weight.T + block.projection_bias
        surfaces.append(fit_surface(projected, groups, headroom))
        states = residual + projected
        surfaces.append(fit_surface(states, groups, headroom))
        linears.append((attention_plan, fc_plan, projection_plan))

    final = np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    surfaces.append(fit_surface(final, groups, headroom))
    return surfaces, linears


def run_fixed(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    surfaces: list[SurfacePlan],
    linears: list[tuple[LinearPlan, LinearPlan, LinearPlan]],
    corrections: CorrectionPlan | None = None,
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
    zero_wide = np.zeros(768, dtype=np.float64)
    zero_hidden = np.zeros(3072, dtype=np.float64)
    block_corrections = (
        corrections.blocks
        if corrections is not None
        else [(zero_wide, zero_hidden, zero_wide) for _ in blocks]
    )
    for block, (attention_plan, fc_plan, projection_plan), correction in zip(
        blocks, linears, block_corrections
    ):
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        attention_input = materialize(normalized1 / attention_plan.smooth)
        learned = materialize(
            attention_input @ attention_plan.weight.T
            + block.attention_bias
            + correction[0]
        )
        residual = materialize(states + learned)

        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        fc_input = materialize(normalized2 / fc_plan.smooth)
        pre = materialize(
            fc_input @ fc_plan.weight.T + block.fc_bias + correction[1]
        )
        hidden = materialize(gelu_new(pre))
        projection_input = materialize(hidden / projection_plan.smooth)
        projected = materialize(
            projection_input @ projection_plan.weight.T
            + block.projection_bias
            + correction[2]
        )
        states = materialize(residual + projected)

    final_correction = corrections.final if corrections is not None else zero_wide
    final = materialize(
        np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
        + final_correction
    )
    assert surface_index == len(surfaces)
    return final, clipped


def fit_bias_corrections(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    surfaces: list[SurfacePlan],
    linears: list[tuple[LinearPlan, LinearPlan, LinearPlan]],
) -> CorrectionPlan:
    """Fit zero-cost affine offsets on calibration inputs only."""
    surface_index = 0

    def materialize(values: np.ndarray) -> np.ndarray:
        nonlocal surface_index
        result, _ = apply_surface(values, surfaces[surface_index])
        surface_index += 1
        return result

    exact_states = inputs.copy()
    states = materialize(inputs)
    corrections: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for block, (attention_plan, fc_plan, projection_plan) in zip(blocks, linears):
        exact_normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in exact_states]
        )
        exact_learned = (
            exact_normalized1 @ block.attention_weight.T + block.attention_bias
        )
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        attention_input = materialize(normalized1 / attention_plan.smooth)
        raw_learned = attention_input @ attention_plan.weight.T + block.attention_bias
        attention_correction = np.mean(exact_learned - raw_learned, axis=0)
        learned = materialize(raw_learned + attention_correction)
        exact_residual = exact_states + exact_learned
        residual = materialize(states + learned)

        exact_normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in exact_residual]
        )
        exact_pre = exact_normalized2 @ block.fc_weight.T + block.fc_bias
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        fc_input = materialize(normalized2 / fc_plan.smooth)
        raw_pre = fc_input @ fc_plan.weight.T + block.fc_bias
        fc_correction = np.mean(exact_pre - raw_pre, axis=0)
        pre = materialize(raw_pre + fc_correction)
        exact_hidden = gelu_new(exact_pre)
        hidden = materialize(gelu_new(pre))

        exact_projected = (
            exact_hidden @ block.projection_weight.T + block.projection_bias
        )
        projection_input = materialize(hidden / projection_plan.smooth)
        raw_projected = (
            projection_input @ projection_plan.weight.T + block.projection_bias
        )
        projection_correction = np.mean(exact_projected - raw_projected, axis=0)
        projected = materialize(raw_projected + projection_correction)
        exact_states = exact_residual + exact_projected
        states = materialize(residual + projected)
        corrections.append(
            (attention_correction, fc_correction, projection_correction)
        )

    exact_final = np.stack(
        [layer_norm(x, final_gamma, final_beta) for x in exact_states]
    )
    raw_final = np.stack(
        [layer_norm(x, final_gamma, final_beta) for x in states]
    )
    final_correction = np.mean(exact_final - raw_final, axis=0)
    materialize(raw_final + final_correction)
    assert surface_index == len(surfaces)
    return CorrectionPlan(blocks=corrections, final=final_correction)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--groups", type=int)
    parser.add_argument("--headroom", type=float, default=1.1)
    parser.add_argument("--alpha", type=float, default=0.0)
    parser.add_argument("--compare-bias", action="store_true")
    parser.add_argument(
        "--export-corrections",
        type=Path,
        help="Fit on every supplied case and export affine bias corrections.",
    )
    args = parser.parse_args()
    case_payload = json.loads(args.cases.read_text())
    inputs = np.asarray(
        [case["input_expected"] for case in case_payload["cases"]], dtype=np.float64
    )
    _, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    expected = exact_forward(inputs, blocks, final_gamma, final_beta)
    expected_winners = np.argmax(expected @ embedding.T, axis=1)

    configs = [
        (groups, headroom, 0.0)
        for groups in (4, 8, 16, 32)
        for headroom in (1.05, 1.1, 1.2, 1.4)
    ] + [
        (groups, 1.1, alpha)
        for groups in (8, 16, 32)
        for alpha in (0.25, 0.5)
    ]
    if args.groups is not None:
        configs = [(args.groups, args.headroom, args.alpha)]
    results: list[dict[str, object]] = []
    correction_modes = (False, True) if args.compare_bias else (False,)
    for groups, headroom, alpha in configs:
        for bias_correction in correction_modes:
            predictions = np.empty_like(expected)
            clipped = 0
            # Two-fold cross-validation: no evaluated token chooses its own scales.
            for parity in (0, 1):
                calibration_indices = np.arange(parity, len(inputs), 2)
                evaluation_indices = np.arange(1 - parity, len(inputs), 2)
                surfaces, linears = fit_plans(
                    inputs[calibration_indices],
                    blocks,
                    final_gamma,
                    final_beta,
                    groups,
                    headroom,
                    alpha,
                )
                corrections = (
                    fit_bias_corrections(
                        inputs[calibration_indices],
                        blocks,
                        final_gamma,
                        final_beta,
                        surfaces,
                        linears,
                    )
                    if bias_correction
                    else None
                )
                predicted, fold_clipped = run_fixed(
                    inputs[evaluation_indices],
                    blocks,
                    final_gamma,
                    final_beta,
                    surfaces,
                    linears,
                    corrections,
                )
                predictions[evaluation_indices] = predicted
                clipped += fold_clipped
            winners = np.argmax(predictions @ embedding.T, axis=1)
            error = predictions - expected
            result = {
                "groups": groups,
                "headroom": headroom,
                "alpha": alpha,
                "biasCorrection": bias_correction,
                "winnerMatches": int(np.count_nonzero(winners == expected_winners)),
                "cases": len(inputs),
                "rmse": float(np.sqrt(np.mean(error**2))),
                "maxError": float(np.max(np.abs(error))),
                "clippedValues": clipped,
                "winnerIds": winners.tolist(),
            }
            results.append(result)
            print(
                json.dumps(
                    {key: value for key, value in result.items() if key != "winnerIds"}
                )
            )

    results.sort(key=lambda item: (-item["winnerMatches"], item["rmse"]))
    payload = {
        "method": "two-fold fixed calibration; each token evaluated with scales fit on the other fold",
        "referenceWinnerIds": expected_winners.tolist(),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")

    if args.export_corrections:
        if args.groups is None:
            parser.error("--export-corrections requires an explicit --groups")
        surfaces, linears = fit_plans(
            inputs,
            blocks,
            final_gamma,
            final_beta,
            args.groups,
            args.headroom,
            args.alpha,
        )
        corrections = fit_bias_corrections(
            inputs,
            blocks,
            final_gamma,
            final_beta,
            surfaces,
            linears,
        )
        correction_payload = {
            "method": "mean affine error fitted over every calibration case",
            "groups": args.groups,
            "headroom": args.headroom,
            "alpha": args.alpha,
            "calibrationTokenIds": [
                int(case["token_id"]) for case in case_payload["cases"]
            ],
            "blocks": [
                {
                    "attention": attention.tolist(),
                    "fc": fc.tolist(),
                    "projection": projection.tolist(),
                }
                for attention, fc, projection in corrections.blocks
            ],
            "final": corrections.final.tolist(),
        }
        args.export_corrections.parent.mkdir(parents=True, exist_ok=True)
        args.export_corrections.write_text(
            json.dumps(correction_payload, separators=(",", ":")) + "\n"
        )
        print(json.dumps({"corrections": str(args.export_corrections)}))


if __name__ == "__main__":
    main()
