#!/usr/bin/env python3
"""Screen zero-runtime-cost output-head correction for the SVG backend.

The correction is fitted on disjoint calibration tokens. A diagonal hidden
correction can be folded into the tied embedding rows, and its intercept becomes
one scalar bias per vocabulary token. Per-token affine calibration is also
screened as an upper bound with the same runtime shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_svg_quantization_strategies import exact_forward, load_checkpoint
from screen_svg_asymmetric_ranges import (
    CALIBRATION_CASES,
    EVALUATION_CASES,
    NATURAL_TOKEN_IDS,
    fit_plans,
    run_fixed,
    winners,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-output-head-calibration" / "results.json"


def summarize(
    name: str,
    predicted: np.ndarray,
    expected: np.ndarray,
) -> dict[str, object]:
    natural = len(NATURAL_TOKEN_IDS)
    return {
        "name": name,
        "winnerMatches": int(np.count_nonzero(predicted == expected)),
        "winnerMatchFraction": float(np.mean(predicted == expected)),
        "naturalWinnerMatches": int(
            np.count_nonzero(predicted[:natural] == expected[:natural])
        ),
        "naturalWinnerMatchFraction": float(
            np.mean(predicted[:natural] == expected[:natural])
        ),
    }


def main() -> None:
    _, embedding64, blocks, final_gamma, final_beta = load_checkpoint()
    tensors = SafeTensors(MODEL_PATH)
    position = np.asarray(tensors.tensor("wpe.weight")[0], dtype=np.float64)
    excluded = set(NATURAL_TOKEN_IDS)
    candidates = np.asarray(
        [index for index in range(len(embedding64)) if index not in excluded],
        dtype=np.int64,
    )
    rng = np.random.default_rng(0x4153594D)
    sampled = rng.choice(
        candidates,
        size=CALIBRATION_CASES + EVALUATION_CASES - len(NATURAL_TOKEN_IDS),
        replace=False,
    )
    calibration_inputs = embedding64[sampled[:CALIBRATION_CASES]] + position
    evaluation_inputs = np.concatenate(
        (
            embedding64[np.asarray(NATURAL_TOKEN_IDS)] + position,
            embedding64[sampled[CALIBRATION_CASES:]] + position,
        )
    )

    surfaces, linears = fit_plans(
        calibration_inputs,
        blocks,
        final_gamma,
        final_beta,
        groups=32,
        asymmetric=False,
        headroom=1.10,
    )
    exact_calibration = exact_forward(
        calibration_inputs, blocks, final_gamma, final_beta
    )
    exact_evaluation = exact_forward(
        evaluation_inputs, blocks, final_gamma, final_beta
    )
    quantized_calibration, _ = run_fixed(
        calibration_inputs,
        blocks,
        final_gamma,
        final_beta,
        surfaces,
        linears,
    )
    quantized_evaluation, _ = run_fixed(
        evaluation_inputs,
        blocks,
        final_gamma,
        final_beta,
        surfaces,
        linears,
    )
    expected_winners = winners(exact_evaluation, embedding64)
    rows = [
        summarize(
            "uncorrected",
            winners(quantized_evaluation, embedding64),
            expected_winners,
        )
    ]

    q_mean = np.mean(quantized_calibration, axis=0)
    e_mean = np.mean(exact_calibration, axis=0)
    centered_q = quantized_calibration - q_mean
    centered_e = exact_calibration - e_mean
    variance = np.mean(centered_q**2, axis=0)
    covariance = np.mean(centered_q * centered_e, axis=0)
    median_variance = float(np.median(variance))
    for relative_ridge in (0.0, 0.01, 0.1, 1.0, 10.0):
        ridge = relative_ridge * median_variance
        slope = (covariance + ridge) / np.maximum(variance + ridge, 1e-12)
        slope = np.clip(slope, 0.5, 1.5)
        intercept = e_mean - slope * q_mean
        corrected = quantized_evaluation * slope + intercept
        row = summarize(
            f"diagonal-hidden-ridge-{relative_ridge:g}",
            winners(corrected, embedding64),
            expected_winners,
        )
        row.update(
            {
                "correctedHiddenRmse": float(
                    np.sqrt(np.mean((corrected - exact_evaluation) ** 2))
                ),
                "slopeMinimum": float(np.min(slope)),
                "slopeMaximum": float(np.max(slope)),
                "biasMaximum": float(np.max(np.abs(intercept))),
            }
        )
        rows.append(row)

    # Fit only the systematic final-state error and retain the original state
    # as an identity path. The resulting (I + correction) transform can be
    # multiplied into the output-head weights offline, so runtime dimensions do
    # not change.
    error_calibration = exact_calibration - quantized_calibration
    q_centered = quantized_calibration - q_mean
    error_mean = np.mean(error_calibration, axis=0)
    error_centered = error_calibration - error_mean
    u, singular, vt = np.linalg.svd(q_centered, full_matrices=False)
    median_energy = float(np.median(singular**2))
    for rank in (32, 128, 255):
        selected_u = u[:, :rank]
        selected_s = singular[:rank]
        selected_vt = vt[:rank]
        ridge = 0.01 * median_energy
        inverse = selected_s / np.maximum(selected_s**2 + ridge, 1e-12)
        correction_map = (
            selected_vt.T * inverse[None, :]
        ) @ selected_u.T @ error_centered
        predicted_error = (
            quantized_evaluation - q_mean
        ) @ correction_map + error_mean
        corrected = quantized_evaluation + predicted_error
        row = summarize(
            f"low-rank-state-error-{rank}",
            winners(corrected, embedding64),
            expected_winners,
        )
        row.update(
            {
                "rank": rank,
                "relativeRidge": 0.01,
                "correctedHiddenRmse": float(
                    np.sqrt(np.mean((corrected - exact_evaluation) ** 2))
                ),
                "foldableIntoOutputHead": True,
            }
        )
        rows.append(row)

    # The vocabulary-sized arrays are kept in float32 to cap this screen near
    # 300 MB rather than materializing several float64 256x50,257 matrices.
    embedding = embedding64.astype(np.float32)
    q_cal_logits = quantized_calibration.astype(np.float32) @ embedding.T
    e_cal_logits = exact_calibration.astype(np.float32) @ embedding.T
    q_eval_logits = quantized_evaluation.astype(np.float32) @ embedding.T
    q_logit_mean = np.mean(q_cal_logits, axis=0)
    e_logit_mean = np.mean(e_cal_logits, axis=0)
    q_logit_centered = q_cal_logits - q_logit_mean
    e_logit_centered = e_cal_logits - e_logit_mean
    logit_variance = np.mean(q_logit_centered**2, axis=0)
    logit_covariance = np.mean(q_logit_centered * e_logit_centered, axis=0)
    median_logit_variance = float(np.median(logit_variance))
    for relative_ridge in (0.0, 0.01, 0.1, 1.0, 10.0):
        ridge = relative_ridge * median_logit_variance
        slope = (logit_covariance + ridge) / np.maximum(
            logit_variance + ridge, 1e-12
        )
        slope = np.clip(slope, 0.5, 1.5)
        raw_bias = e_logit_mean - slope * q_logit_mean
        for bias_fraction in (0.0, 0.25, 0.5, 1.0):
            calibrated_logits = q_eval_logits * slope + raw_bias * bias_fraction
            predicted = np.argmax(calibrated_logits, axis=1)
            row = summarize(
                f"token-affine-ridge-{relative_ridge:g}-bias-{bias_fraction:g}",
                predicted,
                expected_winners,
            )
            row.update(
                {
                    "slopeMinimum": float(np.min(slope)),
                    "slopeMaximum": float(np.max(slope)),
                    "biasMaximum": float(np.max(np.abs(raw_bias * bias_fraction))),
                }
            )
            rows.append(row)

    rows.sort(key=lambda row: (-row["winnerMatches"], -row["naturalWinnerMatches"]))
    payload = {
        "model": str(MODEL_PATH),
        "calibrationCases": CALIBRATION_CASES,
        "evaluationCases": EVALUATION_CASES,
        "naturalCases": len(NATURAL_TOKEN_IDS),
        "scope": "symmetric 32-group 8-bit SVG numerical screen; correction fitted only on disjoint calibration tokens",
        "results": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    for row in rows:
        print(json.dumps(row))


if __name__ == "__main__":
    main()
