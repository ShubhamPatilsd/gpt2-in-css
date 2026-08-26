#!/usr/bin/env python3
"""Screen a fixed-depth q10 -> q12 -> q16 uncertainty closure."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane" / "reference.json"
SERIAL = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-cascade" / "homogeneous-group-counts.npy"
OUTPUT = ROOT / "experiments" / "gpt2-progressive-precision-closure"
VOCABULARY = 50_257
WIDTH = 768
AXIS_STEPS = 16_384
SCORE_SCALE = 256
GROUP_SIZE = 256
BATCH = 16
BLOCK_SIZES = (1, 2, 4, 8, 16)
ALLOWANCES = (1, 4, 27)


def distribution(values: np.ndarray) -> dict[str, float | int]:
    return {
        "minimum": int(np.min(values)),
        "median": int(np.percentile(values, 50, method="higher")),
        "p95": int(np.percentile(values, 95, method="higher")),
        "p99": int(np.percentile(values, 99, method="higher")),
        "maximum": int(np.max(values)),
        "mean": float(np.mean(values)),
    }


def rowwise(weights: np.ndarray, bits: int) -> tuple[np.ndarray, np.ndarray]:
    maximum = 2 ** (bits - 1) - 1
    scales = np.max(np.abs(weights), axis=1) / maximum
    scales[scales == 0] = 1.0
    represented = (
        np.rint(weights / scales[:, None]).clip(-maximum, maximum)
        * scales[:, None]
    )
    return represented, scales


def block_mask(token_mask: np.ndarray, block_size: int) -> tuple[np.ndarray, np.ndarray]:
    padding = math.ceil(VOCABULARY / block_size) * block_size - VOCABULARY
    padded = np.pad(token_mask, ((0, 0), (0, padding)), constant_values=False)
    blocks = np.any(
        padded.reshape(len(token_mask), -1, block_size), axis=2
    )
    rows = np.repeat(blocks, block_size, axis=1)[:, :VOCABULARY]
    return blocks, rows


def main() -> None:
    started = time.perf_counter()
    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(hidden))) * 1.01
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    query_norms = np.linalg.norm(realized, axis=1)
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    fine_scale = float(json.loads(FINE.read_text())["weightScale"])
    target = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    q10, _ = rowwise(weights, 10)
    q12, _ = rowwise(weights, 12)
    error10 = np.linalg.norm(target - q10, axis=1)
    error12 = np.linalg.norm(target - q12, axis=1)

    screens: dict[tuple[int, int], dict[str, np.ndarray]] = {}
    for allowance in ALLOWANCES:
        for block_size in BLOCK_SIZES:
            screens[(allowance, block_size)] = {
                "q10ActiveTokens": np.empty(len(hidden), dtype=np.int64),
                "q12Rows": np.empty(len(hidden), dtype=np.int64),
                "q12ActiveTokens": np.empty(len(hidden), dtype=np.int64),
                "q16Rows": np.empty(len(hidden), dtype=np.int64),
                "winnerRetained": np.empty(len(hidden), dtype=bool),
            }

    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        query = realized[start:stop]
        centers10 = query @ q10.T * SCORE_SCALE
        centers12 = query @ q12.T * SCORE_SCALE
        target_buckets = np.rint(query @ target.T * SCORE_SCALE).astype(np.int64)
        winners = np.argmax(target_buckets, axis=1)
        radii10 = query_norms[start:stop, None] * error10[None, :] * SCORE_SCALE
        radii12 = query_norms[start:stop, None] * error12[None, :] * SCORE_SCALE

        for allowance in ALLOWANCES:
            lower10 = centers10 - radii10 - allowance
            upper10 = centers10 + radii10 + allowance
            active10 = upper10 >= np.max(lower10, axis=1)[:, None]
            for block_size in BLOCK_SIZES:
                destination = screens[(allowance, block_size)]
                blocks10, rows10 = block_mask(active10, block_size)
                masked_lower12 = np.where(
                    rows10, centers12 - radii12 - allowance, -np.inf
                )
                lower12_max = np.max(masked_lower12, axis=1)
                active12 = rows10 & (
                    centers12 + radii12 + allowance >= lower12_max[:, None]
                )
                blocks12, _rows12 = block_mask(active12, block_size)
                retained = active12[np.arange(stop - start), winners]
                if not np.all(retained):
                    raise RuntimeError(
                        f"allowance={allowance} block={block_size} lost winners "
                        f"{(start + np.flatnonzero(~retained)).tolist()}"
                    )
                destination["q10ActiveTokens"][start:stop] = np.sum(active10, axis=1)
                destination["q12Rows"][start:stop] = np.sum(blocks10, axis=1) * block_size
                destination["q12ActiveTokens"][start:stop] = np.sum(active12, axis=1)
                destination["q16Rows"][start:stop] = np.sum(blocks12, axis=1) * block_size
                destination["winnerRetained"][start:stop] = retained

    if SERIAL.exists():
        serial_groups = np.load(SERIAL).astype(np.int64)
    else:
        serial_groups = np.full(len(hidden), -1, dtype=np.int64)
    serial_rows = serial_groups * GROUP_SIZE
    variants = []
    for (allowance, block_size), values in screens.items():
        q12_rows = values["q12Rows"]
        q16_rows = values["q16Rows"]
        # Row-shaping proxy: the retained q16 backend uses 12 glyphs/row;
        # radix-64 rowwise q12 uses 6. The global q10 scan is common.
        progressive_glyphs = q12_rows * 6 + q16_rows * 12
        direct_closure_glyphs = q12_rows * 12
        serial_glyphs = serial_rows * 12
        variants.append({
            "allowanceBucketsPerPrecision": allowance,
            "blockSize": block_size,
            "staticBlockGates": math.ceil(VOCABULARY / block_size),
            "q10ActiveTokens": distribution(values["q10ActiveTokens"]),
            "q12Rows": distribution(q12_rows),
            "q12ActiveTokens": distribution(values["q12ActiveTokens"]),
            "q16Rows": distribution(q16_rows),
            "progressiveDynamicGlyphs": distribution(progressive_glyphs),
            "directQ10ToQ16ClosureGlyphs": distribution(direct_closure_glyphs),
            "serialExactRows": distribution(serial_rows),
            "serialExactGlyphs": distribution(serial_glyphs),
            "meanDynamicGlyphRatioVersusSerialExact": float(
                np.mean(progressive_glyphs) / np.mean(serial_glyphs)
            ),
            "meanDynamicGlyphRatioVersusDirectClosure": float(
                np.mean(progressive_glyphs) / np.mean(direct_closure_glyphs)
            ),
            "winnerRetainedStates": int(np.sum(values["winnerRetained"])),
            "dependentPrecisionWaves": 2,
        })

    result = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "states": len(hidden),
        "target": "browser-realized global-int16 q16 buckets with lower-token ties",
        "productionInputRange": production_range,
        "axisSteps": AXIS_STEPS,
        "algorithm": [
            "global rowwise-q10 lower/upper intervals",
            "rowwise-q12 scores only for q10-competitive contiguous blocks",
            "global-int16 q16 scores only for q12-competitive contiguous blocks",
            "one final exact argmax",
        ],
        "variants": variants,
        "seconds": time.perf_counter() - started,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    best_conservative = min(
        (item for item in variants if item["allowanceBucketsPerPrecision"] == max(ALLOWANCES)),
        key=lambda item: item["progressiveDynamicGlyphs"]["mean"],
    )
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "bestConservative": best_conservative,
        "seconds": result["seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
