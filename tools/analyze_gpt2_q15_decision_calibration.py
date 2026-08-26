#!/usr/bin/env python3
"""Search one-code q15 output-head calibrations without changing GPT-2's graph."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
PRODUCTION = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
OUTPUT = ROOT / "experiments" / "gpt2-q15-decision-calibration"
VOCABULARY = 50_257
AXIS_STEPS = 16_384
Q15_MAXIMUM = 16_383
BATCH = 16
SCORE_SCALE = 256


def score_summary(
    hidden: np.ndarray,
    represented: np.ndarray,
    score_gain: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    winners = np.empty(len(hidden), dtype=np.int64)
    margins = np.empty(len(hidden), dtype=np.float64)
    bucket_winners = np.empty(len(hidden), dtype=np.int64)
    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        scores = hidden[start:stop] @ represented.T
        winners[start:stop] = np.argmax(scores, axis=1)
        top = np.partition(scores, -2, axis=1)[:, -2:]
        margins[start:stop] = top[:, 1] - top[:, 0]
        buckets = np.rint(scores * score_gain * SCORE_SCALE).astype(np.int64)
        bucket_winners[start:stop] = np.argmax(buckets, axis=1)
    return winners, margins, bucket_winners


def distribution(values: np.ndarray) -> dict[str, float]:
    return {
        "minimum": float(np.min(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95, method="higher")),
        "maximum": float(np.max(values)),
        "mean": float(np.mean(values)),
    }


def main() -> None:
    started = time.perf_counter()
    source_hidden = np.asarray(np.load(STATES)["hidden"], dtype=np.float64)
    production = json.loads((PRODUCTION / "reference.json").read_text())
    production_range = float(production["productionInputRange"])
    score_gain = float(production["scoreGain"])
    hidden = (
        np.rint(source_hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    scale = float(np.max(np.abs(weights)) / Q15_MAXIMUM)
    codes = np.rint(weights / scale).clip(
        -Q15_MAXIMUM, Q15_MAXIMUM
    ).astype(np.int16)
    represented = codes.astype(np.float64) * scale

    float_winners, float_margins, float_bucket_winners = score_summary(
        hidden, weights, score_gain
    )
    q15_winners, q15_margins, q15_bucket_winners = score_summary(
        hidden, represented, score_gain
    )
    mismatch_states = np.flatnonzero(q15_winners != float_winners)
    if mismatch_states.tolist() != [547]:
        raise RuntimeError(
            f"expected nearest-q15 mismatch [547], got {mismatch_states.tolist()}"
        )

    # Search a single integer-code move on either side of each wrong decision.
    # A candidate is accepted only after a full-vocabulary verification below.
    candidates: list[dict[str, object]] = []
    for state in mismatch_states:
        desired = int(float_winners[state])
        incumbent = int(q15_winners[state])
        incumbent_scores = hidden @ represented[incumbent]
        desired_scores = hidden @ represented[desired]
        deficit = float(incumbent_scores[state] - desired_scores[state])
        for token, direction_name in ((desired, "raise-desired"), (incumbent, "lower-incumbent")):
            for dimension, activation in enumerate(hidden[state]):
                if activation == 0:
                    continue
                if direction_name == "raise-desired":
                    delta = 1 if activation > 0 else -1
                else:
                    delta = -1 if activation > 0 else 1
                new_code = int(codes[token, dimension]) + delta
                if not -Q15_MAXIMUM <= new_code <= Q15_MAXIMUM:
                    continue
                improvement = abs(float(activation)) * scale
                if improvement <= deficit:
                    continue
                changed = represented.copy()
                changed[token, dimension] = new_code * scale
                changed_winners, changed_margins, changed_bucket_winners = score_summary(
                    hidden, changed, score_gain
                )
                wrong = np.flatnonzero(changed_winners != float_winners)
                rounded_float_bucket_wrong = np.flatnonzero(
                    changed_bucket_winners != float_bucket_winners
                )
                logit_delta = hidden[:, dimension] * delta * scale
                candidates.append({
                    "token": token,
                    "dimension": dimension,
                    "codeDelta": delta,
                    "oldCode": int(codes[token, dimension]),
                    "newCode": new_code,
                    "direction": direction_name,
                    "mismatchState": int(state),
                    "nearestQ15Deficit": deficit,
                    "stateLogitImprovement": improvement,
                    "stateCorrectedMargin": float(changed_margins[state]),
                    "floatWinnerMismatchStates": wrong.astype(int).tolist(),
                    "roundedFloatBucketWinnerMismatchStates": (
                        rounded_float_bucket_wrong.astype(int).tolist()
                    ),
                    "corpusLogitDeltaRms": float(np.sqrt(np.mean(logit_delta ** 2))),
                    "corpusLogitDeltaMaximum": float(np.max(np.abs(logit_delta))),
                })

    exact = [
        candidate for candidate in candidates
        if not candidate["floatWinnerMismatchStates"]
    ]
    if not exact:
        raise RuntimeError("no single-code q15 calibration preserves all float winners")
    selected = max(exact, key=lambda candidate: candidate["stateCorrectedMargin"])
    calibrated_codes = codes.copy()
    calibrated_codes[selected["token"], selected["dimension"]] = selected["newCode"]
    calibrated = calibrated_codes.astype(np.float64) * scale
    calibrated_winners, calibrated_margins, calibrated_bucket_winners = score_summary(
        hidden, calibrated, score_gain
    )
    calibrated_mismatch = np.flatnonzero(calibrated_winners != float_winners)
    if len(calibrated_mismatch):
        raise RuntimeError(f"calibrated q15 mismatches {calibrated_mismatch.tolist()}")

    q16_maximum = 32_767
    q16_scale = float(np.max(np.abs(weights)) / q16_maximum)
    q16_codes = np.rint(weights / q16_scale).clip(
        -q16_maximum, q16_maximum
    ).astype(np.int16)
    q16 = q16_codes.astype(np.float64) * q16_scale
    q16_winners, _q16_margins, q16_bucket_winners = score_summary(
        hidden, q16, score_gain
    )
    if not np.array_equal(q16_winners, float_winners):
        raise RuntimeError("global q16 mathematical winners differ from float")
    if not np.array_equal(q16_bucket_winners, float_winners):
        raise RuntimeError("global q16 production buckets differ from float winners")

    # The first move fixes q15's quantization decision. Search one additional
    # move against the actual q16 production bucket contract. Cheap state-local
    # filtering precedes full-vocabulary verification of promising moves.
    bucket_mismatch = np.flatnonzero(
        calibrated_bucket_winners != q16_bucket_winners
    )
    if bucket_mismatch.tolist() != [493]:
        raise RuntimeError(
            f"expected calibrated-q15 bucket mismatch [493], got {bucket_mismatch.tolist()}"
        )
    bucket_local_candidates: list[dict[str, object]] = []
    for state in bucket_mismatch:
        desired = int(q16_bucket_winners[state])
        incumbent = int(calibrated_bucket_winners[state])
        desired_score = float(hidden[state] @ calibrated[desired])
        incumbent_score = float(hidden[state] @ calibrated[incumbent])
        desired_bucket = int(np.rint(desired_score * score_gain * SCORE_SCALE))
        incumbent_bucket = int(np.rint(incumbent_score * score_gain * SCORE_SCALE))
        for token, direction_name in ((desired, "raise-desired"), (incumbent, "lower-incumbent")):
            for dimension, activation in enumerate(hidden[state]):
                if activation == 0:
                    continue
                if direction_name == "raise-desired":
                    delta = 1 if activation > 0 else -1
                else:
                    delta = -1 if activation > 0 else 1
                new_code = int(calibrated_codes[token, dimension]) + delta
                if not -Q15_MAXIMUM <= new_code <= Q15_MAXIMUM:
                    continue
                score_delta = float(activation) * delta * scale
                if direction_name == "raise-desired":
                    changed_desired_bucket = int(np.rint(
                        (desired_score + score_delta) * score_gain * SCORE_SCALE
                    ))
                    fixes_state = (
                        changed_desired_bucket > incumbent_bucket
                        or (
                            changed_desired_bucket == incumbent_bucket
                            and desired < incumbent
                        )
                    )
                else:
                    changed_incumbent_bucket = int(np.rint(
                        (incumbent_score + score_delta) * score_gain * SCORE_SCALE
                    ))
                    fixes_state = (
                        desired_bucket > changed_incumbent_bucket
                        or (
                            desired_bucket == changed_incumbent_bucket
                            and desired < incumbent
                        )
                    )
                if not fixes_state:
                    continue
                corpus_delta = hidden[:, dimension] * delta * scale
                bucket_local_candidates.append({
                    "token": token,
                    "dimension": dimension,
                    "codeDelta": delta,
                    "oldCode": int(calibrated_codes[token, dimension]),
                    "newCode": new_code,
                    "direction": direction_name,
                    "mismatchState": int(state),
                    "desiredToken": desired,
                    "incumbentToken": incumbent,
                    "corpusLogitDeltaRms": float(
                        np.sqrt(np.mean(corpus_delta ** 2))
                    ),
                    "corpusLogitDeltaMaximum": float(
                        np.max(np.abs(corpus_delta))
                    ),
                })
    bucket_local_candidates.sort(key=lambda candidate: candidate["corpusLogitDeltaRms"])
    selected_bucket = None
    bucket_candidates_verified = 0
    final_codes = calibrated_codes.copy()
    final = calibrated
    final_winners = calibrated_winners
    final_margins = calibrated_margins
    final_bucket_winners = calibrated_bucket_winners
    for candidate in bucket_local_candidates:
        trial_codes = calibrated_codes.copy()
        trial_codes[candidate["token"], candidate["dimension"]] = candidate["newCode"]
        trial = trial_codes.astype(np.float64) * scale
        trial_winners, trial_margins, trial_bucket_winners = score_summary(
            hidden, trial, score_gain
        )
        bucket_candidates_verified += 1
        if (
            np.array_equal(trial_winners, float_winners)
            and np.array_equal(trial_bucket_winners, q16_bucket_winners)
        ):
            selected_bucket = candidate
            final_codes = trial_codes
            final = trial
            final_winners = trial_winners
            final_margins = trial_margins
            final_bucket_winners = trial_bucket_winners
            break
    if selected_bucket is None:
        raise RuntimeError("no second one-code move preserves q16 production buckets")

    radix = 128
    for candidate in (selected, selected_bucket):
        token = int(candidate["token"])
        dimension = int(candidate["dimension"])
        old_code = int(candidate["oldCode"])
        new_code = int(candidate["newCode"])
        old_high = int(np.trunc(old_code / radix))
        new_high = int(np.trunc(new_code / radix))
        candidate["radix128Digits"] = {
            "old": {"high": old_high, "residual": old_code - old_high * radix},
            "new": {"high": new_high, "residual": new_code - new_high * radix},
            "highPlaneChanged": old_high != new_high,
        }

    result = {
        "model": "openai-community/gpt2",
        "modelArchitectureChanged": False,
        "checkpointChanged": False,
        "quantizedRepresentationCalibrated": True,
        "scope": "two integer-code adjustments to the q15 output-head representation",
        "states": len(hidden),
        "productionInputRange": production_range,
        "scoreGain": score_gain,
        "q15Scale": scale,
        "nearestQ15": {
            "floatWinnerMatches": int(np.sum(q15_winners == float_winners)),
            "floatWinnerMismatchStates": mismatch_states.astype(int).tolist(),
            "roundedFloatBucketWinnerMatches": int(
                np.sum(q15_bucket_winners == float_bucket_winners)
            ),
            "originalFloatWinnerMatchesAfterBucketing": int(
                np.sum(q15_bucket_winners == float_winners)
            ),
            "originalFloatWinnerMismatchStatesAfterBucketing": np.flatnonzero(
                q15_bucket_winners != float_winners
            ).astype(int).tolist(),
            "margins": distribution(q15_margins),
        },
        "search": {
            "singleCodeCandidatesThatCorrectMismatch": len(candidates),
            "candidatesPreservingAllFloatWinners": len(exact),
            "candidates": candidates,
        },
        "selectedCalibration": selected,
        "productionBucketCalibration": {
            "target": "global-q16 production buckets",
            "initialMismatchStates": bucket_mismatch.astype(int).tolist(),
            "stateLocalCandidates": len(bucket_local_candidates),
            "fullVocabularyCandidatesVerified": bucket_candidates_verified,
            "selectedCalibration": selected_bucket,
        },
        "calibratedQ15": {
            "floatWinnerMatches": int(np.sum(final_winners == float_winners)),
            "floatWinnerMismatchStates": np.flatnonzero(
                final_winners != float_winners
            ).astype(int).tolist(),
            "roundedFloatBucketWinnerMatches": int(
                np.sum(final_bucket_winners == float_bucket_winners)
            ),
            "roundedFloatBucketWinnerMismatchStates": np.flatnonzero(
                final_bucket_winners != float_bucket_winners
            ).astype(int).tolist(),
            "originalFloatWinnerMatchesAfterBucketing": int(
                np.sum(final_bucket_winners == float_winners)
            ),
            "originalFloatWinnerMismatchStatesAfterBucketing": np.flatnonzero(
                final_bucket_winners != float_winners
            ).astype(int).tolist(),
            "globalQ16BucketMatches": int(
                np.sum(final_bucket_winners == q16_bucket_winners)
            ),
            "globalQ16BucketMismatchStates": np.flatnonzero(
                final_bucket_winners != q16_bucket_winners
            ).astype(int).tolist(),
            "margins": distribution(final_margins),
            "weightRmse": float(np.sqrt(np.mean((final - weights) ** 2))),
            "nearestQ15WeightRmse": float(
                np.sqrt(np.mean((represented - weights) ** 2))
            ),
        },
        "floatReference": {
            "margins": distribution(float_margins),
            "originalFloatWinnerMatchesAfterBucketing": int(
                np.sum(float_bucket_winners == float_winners)
            ),
            "originalFloatWinnerMismatchStatesAfterBucketing": np.flatnonzero(
                float_bucket_winners != float_winners
            ).astype(int).tolist(),
        },
        "seconds": time.perf_counter() - started,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "nearestQ15": result["nearestQ15"],
        "selectedCalibration": selected,
        "productionBucketCalibration": result["productionBucketCalibration"],
        "calibratedQ15": result["calibratedQ15"],
        "seconds": result["seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
