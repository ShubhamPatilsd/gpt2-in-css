#!/usr/bin/env python3
"""Derive empirical transport-free GPT-2 timing floors from saved browser runs.

This does not benchmark a new implementation.  It deliberately combines only
matched warm-mutation measurements that already exist in the repository.  The
result is a lower-bound model for the current stage implementations after the
extra cost of connecting attention to the MLP is set to zero.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text())


def main() -> None:
    attention = load("experiments/gpt2-block-css/css-kv-attention-mutation.json")
    mlp = load("experiments/gpt2-block-css/mlp-vector-replay.json")
    connected = load(
        "experiments/gpt2-block-css/projected-kv-block-mutation-css-kv.json"
    )
    qkv = load("experiments/gpt2-block-css/qkv-stage-mutation.json")
    attention_projection = load(
        "experiments/gpt2-block-css/attention-projection-mutation.json"
    )
    coarse_head = load(
        "experiments/gpt2-hvar-grid-output-head-global11-inline-tie/browser-results.json"
    )
    accurate_head = load(
        "experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-staged/"
        "browser-results.json"
    )
    two_block_trace = load(
        "experiments/gpt2-block-css/"
        "view-timeline-two-block-exact-global-current-trace.json"
    )

    contexts = {}
    for context in (16, 32):
        key = str(context)
        attention_trials = [
            trial["milliseconds"]
            for trial in attention["trials"]
            if trial["context"] == context
        ]
        mlp_trials = [
            trial["milliseconds"]
            for trial in mlp["trials"]
            if trial["context"] == context
        ]
        attention_ms = attention["summary"][key][
            "attention-css-kv-live-current-packet12"
        ]["query"]["medianMilliseconds"]
        mlp_ms = mlp["summary"][key]["medianMilliseconds"]
        connected_ms = connected["summary"][key]["medianMilliseconds"]
        isolated_sum_ms = attention_ms + mlp_ms
        sample_minimum_sum_ms = min(attention_trials) + min(mlp_trials)
        connection_tax_ms = connected_ms - isolated_sum_ms
        contexts[key] = {
            "attentionMedianMilliseconds": attention_ms,
            "mlpFullVectorMedianMilliseconds": mlp_ms,
            "isolatedStageSumPerBlockMilliseconds": isolated_sum_ms,
            "connectedBlockMedianMilliseconds": connected_ms,
            "connectionTaxMilliseconds": connection_tax_ms,
            "connectionTaxShareOfConnected": connection_tax_ms / connected_ms,
            "maximumSpeedupFromRemovingOnlyConnectionTax": (
                connected_ms / isolated_sum_ms
            ),
            "twelveBlockStageSumMilliseconds": 12 * isolated_sum_ms,
            "twelveBlockSampleMinimumSumMilliseconds": 12 * sample_minimum_sum_ms,
            "thirteenFoldTargetPerBlockMilliseconds": connected_ms / 13,
            "transportFreeMedianMultipleOfThirteenFoldTarget": (
                isolated_sum_ms / (connected_ms / 13)
            ),
        }

    context_16_attention = contexts["16"]["attentionMedianMilliseconds"]
    qkv_ms = qkv["summary"]["16"]["medianMilliseconds"]
    projection_ms = attention_projection["summary"]["16"]["medianMilliseconds"]
    attention_remainder_ms = context_16_attention - qkv_ms - projection_ms

    coarse_head_ms = coarse_head["settledMutationMedianMilliseconds"]
    accurate_head_ms = accurate_head["medianMilliseconds"]
    for values in contexts.values():
        blocks_ms = values["twelveBlockStageSumMilliseconds"]
        values["plusCoarseHeadMilliseconds"] = blocks_ms + coarse_head_ms
        values["plusAccurateHeadMilliseconds"] = blocks_ms + accurate_head_ms

    block_0_exact_ms = load(
        "experiments/gpt2-block-css/view-timeline-block-hybrid-mutation-browser.json"
    )["medianMilliseconds"]
    block_0_eased_ms = load(
        "experiments/gpt2-block-css/"
        "view-timeline-block-hybrid-fc-projection-easing-mutation-browser.json"
    )["medianMilliseconds"]
    shaping_ms = next(
        event["milliseconds"]
        for event in two_block_trace["topCompleteEvents"]
        if event["name"] == "InlineNode::ShapeTextIncludingFirstLine"
    )

    result = {
        "model": (
            "Sum matched isolated warm-mutation stage medians and set the measured "
            "connected-graph premium to zero. This is an empirical floor for the "
            "current stage implementations, not a hardware or future-backend bound."
        ),
        "contexts": contexts,
        "context16AttentionDiagnostic": {
            "qkvMedianMilliseconds": qkv_ms,
            "attentionCoreAndInternalCarriersBySubtractionMilliseconds": (
                attention_remainder_ms
            ),
            "attentionOutputProjectionMedianMilliseconds": projection_ms,
            "warning": (
                "The remainder is diagnostic only because the three values come "
                "from separate isolated fixtures."
            ),
        },
        "outputHeads": {
            "coarseGlobalInt11MedianMilliseconds": coarse_head_ms,
            "coarseValidation": "63/64 winners in the documented screen",
            "accurateStagedMedianMilliseconds": accurate_head_ms,
            "accurateValidation": "passes the saved browser fixtures",
        },
        "oneTokenEvidence": {
            "block0ExactMedianMilliseconds": block_0_exact_ms,
            "block1ExactDocumentedMedianMilliseconds": 383.4,
            "twoBlockIsolatedDocumentedSumMilliseconds": 746.8,
            "twelveBlockMeanExtrapolationMilliseconds": 12 * (
                (block_0_exact_ms + 383.4) / 2
            ),
            "block0EasedMedianMilliseconds": block_0_eased_ms,
            "twelveBlockEasedBlock0ProxyMilliseconds": 12 * block_0_eased_ms,
            "warning": (
                "One-token attention is degenerate and the eased result was only "
                "measured on block 0, so these are optimistic proxies, not a "
                "full-model estimate."
            ),
        },
        "maximallyOptimisticCurrentBackendTraceFloor": {
            "twoBlockFontShapingMilliseconds": shaping_ms,
            "perBlockFontShapingMilliseconds": shaping_ms / 2,
            "twelveBlockFontShapingMilliseconds": shaping_ms * 6,
            "warning": (
                "This sets layout, style calculation, timelines, nonlinear CSS "
                "math, and every handoff to zero. It is only a one-token trace "
                "floor for the current font-backed architecture, not a prediction."
            ),
        },
        "sources": [
            "experiments/gpt2-block-css/css-kv-attention-mutation.json",
            "experiments/gpt2-block-css/mlp-vector-replay.json",
            "experiments/gpt2-block-css/projected-kv-block-mutation-css-kv.json",
            "experiments/gpt2-block-css/qkv-stage-mutation.json",
            "experiments/gpt2-block-css/attention-projection-mutation.json",
            "experiments/gpt2-hvar-grid-output-head-global11-inline-tie/browser-results.json",
            "experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-staged/browser-results.json",
            "experiments/gpt2-block-css/view-timeline-block-hybrid-mutation-browser.json",
            "experiments/gpt2-block-css/view-timeline-block-hybrid-fc-projection-easing-mutation-browser.json",
            "experiments/gpt2-block-css/view-timeline-two-block-exact-global-current-trace.json",
            "experiments/numeric-backend-decision/RESULTS.md",
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
