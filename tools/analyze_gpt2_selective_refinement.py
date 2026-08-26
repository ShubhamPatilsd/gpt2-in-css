#!/usr/bin/env python3
"""Screen near-winner selective HVAR coordinate refinement on GPT-2 states."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_global_head_precision import final_hidden_batch


ROOT = Path(__file__).resolve().parents[1]
PRECISION = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global11" / "precision-analysis.json"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane" / "reference.json"
OUTPUT = ROOT / "experiments" / "gpt2-hvar-coordinate-dither" / "selective-analysis.json"
GROUP_SIZE = 256
F2DOT14_STEP = 1 / 16_384
PHASES = 8


def percentile(values: np.ndarray, p: float) -> float:
    return float(np.percentile(values, p, method="higher"))


def main() -> None:
    precision = json.loads(PRECISION.read_text())
    fine = json.loads(FINE.read_text())
    tensors = SafeTensors(MODEL_PATH)
    token_ids = np.asarray(precision["tokenIds"], dtype=np.int64)
    hidden = final_hidden_batch(token_ids, tensors).astype(np.float64)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[:50_257], dtype=np.float64
    )
    dense_logits = hidden @ embeddings.T
    dense_winners = dense_logits.argmax(axis=1)
    scale = fine["weightScale"]
    quantized_weights = (
        np.rint(embeddings / scale).astype(np.int16).astype(np.float64) * scale
    )
    input_range = fine["inputRange"]
    # Chrome floors variation coordinates. This is the ordinary one-phase
    # fine-pass approximation, before the deterministic half-step correction.
    one_phase_hidden = (
        np.floor(hidden / input_range * 16_384) / 16_384 * input_range
    )
    one_phase_logits = one_phase_hidden @ quantized_weights.T

    refined_hidden = np.zeros_like(hidden)
    for phase in range(PHASES):
        offset = phase * F2DOT14_STEP / PHASES
        refined_hidden += (
            np.floor((hidden / input_range + offset) * 16_384) / 16_384
            - offset + F2DOT14_STEP / 2
        ) * input_range
    refined_hidden /= PHASES
    refined_logits = refined_hidden @ quantized_weights.T

    coarse_winners = np.asarray(
        precision["encodings"]["globalInt11"]["winners"], dtype=np.int64
    )
    results: dict[str, object] = {
        "samples": len(token_ids),
        "phases": PHASES,
        "coarseGroupMatches": int(np.sum(
            coarse_winners // GROUP_SIZE == dense_winners // GROUP_SIZE
        )),
        "onePhaseGlobalWinnerMatches": int(np.sum(
            one_phase_logits.argmax(axis=1) == dense_winners
        )),
        "refinedGlobalWinnerMatches": int(np.sum(
            refined_logits.argmax(axis=1) == dense_winners
        )),
        "thresholds": {},
    }
    for threshold in (0.0025, 0.005, 0.01, 0.02, 0.05, 0.1):
        counts = []
        includes_dense = []
        selected_winners = []
        for sample, dense_winner in enumerate(dense_winners):
            group = coarse_winners[sample] // GROUP_SIZE
            start = group * GROUP_SIZE
            stop = min(start + GROUP_SIZE, 50_257)
            scores = one_phase_logits[sample, start:stop]
            active = np.flatnonzero(scores >= scores.max() - threshold)
            counts.append(len(active))
            dense_local = dense_winner - start
            includes_dense.append(bool(dense_local in active))
            refined_active = refined_logits[sample, start + active]
            selected_winners.append(int(start + active[np.argmax(refined_active)]))
        counts_array = np.asarray(counts)
        selected_array = np.asarray(selected_winners)
        results["thresholds"][str(threshold)] = {
            "meanCandidates": float(counts_array.mean()),
            "medianCandidates": percentile(counts_array, 50),
            "p95Candidates": percentile(counts_array, 95),
            "maximumCandidates": int(counts_array.max()),
            "denseWinnerIncluded": int(np.sum(includes_dense)),
            "refinedWinnerMatches": int(np.sum(selected_array == dense_winners)),
        }
    OUTPUT.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
