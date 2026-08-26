#!/usr/bin/env python3
"""Compare global quantized output targets with original GPT-2 winners."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
OUTPUT = ROOT / "experiments" / "gpt2-global-precision-targets"
VOCABULARY = 50_257
AXIS_STEPS = 16_384
BATCH = 16


def winners_and_margins(hidden: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    winners = np.empty(len(hidden), dtype=np.int64)
    margins = np.empty(len(hidden), dtype=np.float64)
    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        scores = hidden[start:stop] @ weights.T
        winners[start:stop] = np.argmax(scores, axis=1)
        top = np.partition(scores, -2, axis=1)[:, -2:]
        margins[start:stop] = top[:, 1] - top[:, 0]
    return winners, margins


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
    hidden = np.asarray(np.load(STATES)["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(hidden))) * 1.01
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    float_winners, float_margins = winners_and_margins(realized, weights)
    precisions = []
    q15_codes = None
    for bits in range(11, 17):
        maximum = 2 ** (bits - 1) - 1
        scale = float(np.max(np.abs(weights)) / maximum)
        codes = np.rint(weights / scale).clip(-maximum, maximum).astype(np.int16)
        represented = codes.astype(np.float64) * scale
        winners, margins = winners_and_margins(realized, represented)
        mismatch = np.flatnonzero(winners != float_winners)
        precisions.append({
            "bits": bits,
            "scale": scale,
            "weightRmse": float(np.sqrt(np.mean((represented - weights) ** 2))),
            "floatWinnerMatches": int(np.sum(winners == float_winners)),
            "floatWinnerMatchFraction": float(np.mean(winners == float_winners)),
            "mismatchStateIndices": mismatch.astype(int).tolist(),
            "margins": distribution(margins),
        })
        if bits == 15:
            q15_codes = codes.astype(np.int32)

    assert q15_codes is not None
    radix = 128
    high = np.trunc(q15_codes / radix).astype(np.int16)
    residual = (q15_codes - high.astype(np.int32) * radix).astype(np.int16)
    if not np.array_equal(
        high.astype(np.int32) * radix + residual.astype(np.int32), q15_codes
    ):
        raise RuntimeError("q15 radix-128 split is not exact")
    plane_reports = []
    for plane_name, plane in (("high", high), ("residual", residual)):
        shard_reports = []
        for shard, start in enumerate(range(0, weights.shape[1], 256)):
            values = plane[:, start:start + 256]
            l1 = np.sum(np.abs(values.astype(np.int64)), axis=1)
            shard_reports.append({
                "shard": shard,
                "maximumL1": int(l1.max()),
                "maximumBaseAdvance": int(l1.max()) + 32,
                "maximumShapedAdvance": 2 * int(l1.max()) + 32,
            })
        plane_reports.append({
            "plane": plane_name,
            "codeAbsoluteMaximum": int(np.max(np.abs(plane))),
            "shards": shard_reports,
            "allShapedAdvancesFitUint16": all(
                item["maximumShapedAdvance"] <= 65_535 for item in shard_reports
            ),
        })

    result = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "states": len(realized),
        "productionInputRange": production_range,
        "floatMargins": distribution(float_margins),
        "precisions": precisions,
        "q15TransportCandidate": {
            "decomposition": "code = high*128 + residual",
            "radix": radix,
            "shardDimensions": 256,
            "shardsPerPlane": 3,
            "planes": 2,
            "glyphsPerRow": 6,
            "currentGlobalQ16GlyphsPerRow": 12,
            "planeReports": plane_reports,
        },
        "seconds": time.perf_counter() - started,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
