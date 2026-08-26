#!/usr/bin/env python3
"""Measure query binning before building feature-selected K-dot fonts."""

from __future__ import annotations

import json
import itertools
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT
from build_gpt2_block_css import QUANT_BITS, WIDTH, layer_norm
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "query-binned-attention"
HEADS = 12
HEAD_WIDTH = 64
LENGTHS = (1, 2, 4, 8, 16)
SEQUENCES_PER_LENGTH = 32


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values, axis=-1, keepdims=True)
    weights = np.exp(shifted)
    return weights / np.sum(weights, axis=-1, keepdims=True)


def quantize(values: np.ndarray, ranges: np.ndarray, bits: int) -> np.ndarray:
    levels = (1 << bits) - 1
    codes = np.rint(np.clip((values + ranges) * levels / (2 * ranges), 0, levels))
    return -ranges + codes * (2 * ranges / levels)


def metrics(errors: list[np.ndarray]) -> dict[str, float]:
    joined = np.concatenate([error.ravel() for error in errors])
    return {
        "rmse": float(np.sqrt(np.mean(joined * joined))),
        "mae": float(np.mean(np.abs(joined))),
        "maxError": float(np.max(np.abs(joined))),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    positions = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    qkv_weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    qkv_weight = quantize_float_rows(qkv_weight, bits=QUANT_BITS).reconstructed
    projection_weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    projection_bias = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    projection_weight = quantize_float_rows(
        projection_weight, bits=QUANT_BITS
    ).reconstructed
    precision = json.loads(PRECISION_REPORT.read_text())
    query_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"][:WIDTH], dtype=np.float64
    )

    rng = np.random.default_rng(0x51554249)
    samples = []
    for length in LENGTHS:
        for _ in range(SEQUENCES_PER_LENGTH):
            tokens = rng.integers(0, embeddings.shape[0], size=length)
            states = embeddings[tokens] + positions[:length]
            normalized = np.stack([layer_norm(row, gamma, beta) for row in states])
            qkv = normalized @ qkv_weight.T + qkv_bias
            query = qkv[-1, :WIDTH]
            keys = qkv[:, WIDTH:2 * WIDTH].reshape(length, HEADS, HEAD_WIDTH)
            values = qkv[:, 2 * WIDTH:].reshape(length, HEADS, HEAD_WIDTH)
            samples.append((length, states[-1], query, keys, values))

    results = {}
    for bits in (2, 3, 4, 5, 6, 8):
        score_errors = []
        probability_errors = []
        context_errors = []
        residual_errors = []
        winner_matches = []
        clipped = []
        by_length: dict[int, list[float]] = {length: [] for length in LENGTHS}
        for length, state, query, keys, values in samples:
            baseline_query = quantize(query, query_ranges, 8).reshape(HEADS, HEAD_WIDTH)
            candidate_query = quantize(query, query_ranges, bits).reshape(HEADS, HEAD_WIDTH)
            baseline_scores = np.einsum("hd,shd->hs", baseline_query, keys) / math.sqrt(
                HEAD_WIDTH
            )
            candidate_scores = np.einsum("hd,shd->hs", candidate_query, keys) / math.sqrt(
                HEAD_WIDTH
            )
            baseline_probabilities = softmax(baseline_scores)
            candidate_probabilities = softmax(candidate_scores)
            baseline_context = np.einsum("hs,shd->hd", baseline_probabilities, values).ravel()
            candidate_context = np.einsum("hs,shd->hd", candidate_probabilities, values).ravel()
            baseline_residual = state + projection_weight @ baseline_context + projection_bias
            candidate_residual = state + projection_weight @ candidate_context + projection_bias
            score_errors.append(candidate_scores - baseline_scores)
            probability_errors.append(candidate_probabilities - baseline_probabilities)
            context_errors.append(candidate_context - baseline_context)
            residual_error = candidate_residual - baseline_residual
            residual_errors.append(residual_error)
            by_length[length].append(float(np.sqrt(np.mean(residual_error * residual_error))))
            winner_matches.append(
                np.argmax(candidate_scores, axis=1) == np.argmax(baseline_scores, axis=1)
            )
            clipped.append(np.abs(query) > query_ranges)
        results[str(bits)] = {
            "score": metrics(score_errors),
            "probability": metrics(probability_errors),
            "context": metrics(context_errors),
            "projectedResidual": metrics(residual_errors),
            "attentionWinnerAgreement": float(np.mean(np.concatenate(winner_matches))),
            "queryClippedFraction": float(np.mean(np.concatenate(clipped))),
            "residualRmseByLength": {
                str(length): float(np.mean(values)) for length, values in by_length.items()
            },
        }

    # Find the best subset of heads to upgrade from five to six query bits.
    # Attention heads are independent until c_proj, so each upgrade contributes a
    # residual delta. The squared error of every one of the 4096 subsets can then
    # be evaluated from a 12x12 Gram matrix instead of rerunning the network.
    five_errors = []
    upgrade_deltas = []
    five_winners = []
    six_winners = []
    for _length, state, query, keys, values in samples:
        baseline_query = quantize(query, query_ranges, 8).reshape(HEADS, HEAD_WIDTH)
        five_query = quantize(query, query_ranges, 5).reshape(HEADS, HEAD_WIDTH)
        six_query = quantize(query, query_ranges, 6).reshape(HEADS, HEAD_WIDTH)
        baseline_scores = np.einsum("hd,shd->hs", baseline_query, keys) / math.sqrt(
            HEAD_WIDTH
        )
        five_scores = np.einsum("hd,shd->hs", five_query, keys) / math.sqrt(HEAD_WIDTH)
        six_scores = np.einsum("hd,shd->hs", six_query, keys) / math.sqrt(HEAD_WIDTH)
        baseline_context = np.einsum("hs,shd->hd", softmax(baseline_scores), values)
        five_context = np.einsum("hs,shd->hd", softmax(five_scores), values)
        six_context = np.einsum("hs,shd->hd", softmax(six_scores), values)
        baseline_residual = state + projection_weight @ baseline_context.ravel() + projection_bias
        five_residual = state + projection_weight @ five_context.ravel() + projection_bias
        five_errors.append(five_residual - baseline_residual)
        head_deltas = []
        for head in range(HEADS):
            head_slice = slice(head * HEAD_WIDTH, (head + 1) * HEAD_WIDTH)
            head_deltas.append(
                projection_weight[:, head_slice]
                @ (six_context[head] - five_context[head])
            )
        upgrade_deltas.append(np.stack(head_deltas))
        baseline_winner = np.argmax(baseline_scores, axis=1)
        five_winners.append(np.argmax(five_scores, axis=1) == baseline_winner)
        six_winners.append(np.argmax(six_scores, axis=1) == baseline_winner)

    five_errors_array = np.stack(five_errors)
    upgrade_deltas_array = np.stack(upgrade_deltas)
    base_sse = float(np.sum(five_errors_array * five_errors_array))
    linear = 2 * np.einsum("so,sho->h", five_errors_array, upgrade_deltas_array)
    gram = np.einsum("sho,sio->hi", upgrade_deltas_array, upgrade_deltas_array)
    five_winners_array = np.stack(five_winners)
    six_winners_array = np.stack(six_winners)
    denominator = five_errors_array.size
    adaptive_pareto = []
    for upgraded_count in range(HEADS + 1):
        best_subset = None
        best_sse = math.inf
        for subset in itertools.combinations(range(HEADS), upgraded_count):
            selected = np.zeros(HEADS, dtype=np.float64)
            selected[list(subset)] = 1
            sse = base_sse + float(linear @ selected + selected @ gram @ selected)
            if sse < best_sse:
                best_sse = sse
                best_subset = subset
        assert best_subset is not None
        selected_errors = five_errors_array.copy()
        selected_winners = five_winners_array.copy()
        for head in best_subset:
            selected_errors += upgrade_deltas_array[:, head]
            selected_winners[:, head] = six_winners_array[:, head]
        adaptive_pareto.append({
            "sixBitHeads": list(best_subset),
            "fiveBitHeads": [head for head in range(HEADS) if head not in best_subset],
            "projectedResidual": metrics([selected_errors]),
            "attentionWinnerAgreement": float(np.mean(selected_winners)),
            "estimatedAlternateGlyphMultiplierVersusAllFiveBit": float(
                (HEADS + upgraded_count) / HEADS
            ),
        })

    five_bit_range_scales = {}
    for range_scale in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2):
        scaled_ranges = query_ranges * range_scale
        score_errors = []
        probability_errors = []
        context_errors = []
        residual_errors = []
        winner_matches = []
        clipped = []
        for _length, state, query, keys, values in samples:
            baseline_query = quantize(query, query_ranges, 8).reshape(HEADS, HEAD_WIDTH)
            candidate_query = quantize(query, scaled_ranges, 5).reshape(HEADS, HEAD_WIDTH)
            baseline_scores = np.einsum("hd,shd->hs", baseline_query, keys) / math.sqrt(
                HEAD_WIDTH
            )
            candidate_scores = np.einsum("hd,shd->hs", candidate_query, keys) / math.sqrt(
                HEAD_WIDTH
            )
            baseline_probabilities = softmax(baseline_scores)
            candidate_probabilities = softmax(candidate_scores)
            baseline_context = np.einsum("hs,shd->hd", baseline_probabilities, values).ravel()
            candidate_context = np.einsum("hs,shd->hd", candidate_probabilities, values).ravel()
            baseline_residual = state + projection_weight @ baseline_context + projection_bias
            candidate_residual = state + projection_weight @ candidate_context + projection_bias
            score_errors.append(candidate_scores - baseline_scores)
            probability_errors.append(candidate_probabilities - baseline_probabilities)
            context_errors.append(candidate_context - baseline_context)
            residual_errors.append(candidate_residual - baseline_residual)
            winner_matches.append(
                np.argmax(candidate_scores, axis=1) == np.argmax(baseline_scores, axis=1)
            )
            clipped.append(np.abs(query) > scaled_ranges)
        five_bit_range_scales[f"{range_scale:.1f}"] = {
            "score": metrics(score_errors),
            "probability": metrics(probability_errors),
            "context": metrics(context_errors),
            "projectedResidual": metrics(residual_errors),
            "attentionWinnerAgreement": float(np.mean(np.concatenate(winner_matches))),
            "queryClippedFraction": float(np.mean(np.concatenate(clipped))),
        }

    report = {
        "checkpoint": str(MODEL_PATH),
        "sequenceLengths": LENGTHS,
        "sequencesPerLength": SEQUENCES_PER_LENGTH,
        "baselineQueryBits": 8,
        "candidate": "per-channel uniform query bins",
        "results": results,
        "adaptiveFiveSixBitPareto": adaptive_pareto,
        "fiveBitRangeScales": five_bit_range_scales,
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
