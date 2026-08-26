#!/usr/bin/env python3
"""Sweep contiguous token-block sizes for the fixed-group uncertainty gate."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-token-uncertainty-block-sweep"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
FIXTURES = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
    / "reference.json"
)
GROUP_SIZE = 256
WIDTH = 768
SCORE_SCALE = 256
TOTAL_ALLOWANCE_BUCKETS = 27
BLOCK_SIZES = (1, 2, 4, 8, 16, 32, 64, 128, 256)


def distribution(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values)
    return {
        "minimum": int(np.min(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95, method="higher")),
        "maximum": int(np.max(values)),
        "mean": float(np.mean(values)),
    }


def screen(
    name: str,
    hidden: np.ndarray,
    query_norms: np.ndarray,
    represented: np.ndarray,
    target: np.ndarray,
    error_norms: np.ndarray,
) -> dict[str, object]:
    centers = hidden @ represented.T * SCORE_SCALE
    radii = query_norms[:, None] * error_norms[None, :] * SCORE_SCALE
    lower = centers - radii - TOTAL_ALLOWANCE_BUCKETS
    upper = centers + radii + TOTAL_ALLOWANCE_BUCKETS
    lower_max = np.max(lower, axis=1)
    token_active = upper >= lower_max[:, None]
    exact_winners = np.argmax(hidden @ target.T, axis=1)
    retained = token_active[np.arange(len(hidden)), exact_winners]
    if not np.all(retained):
        raise RuntimeError(
            f"{name}: token gate lost exact winners "
            f"{np.flatnonzero(~retained).tolist()}"
        )

    token_rows = np.sum(token_active, axis=1).astype(np.int64)
    variants = []
    for block_size in BLOCK_SIZES:
        blocks = GROUP_SIZE // block_size
        block_active = np.max(
            upper.reshape(len(hidden), blocks, block_size), axis=2
        ) >= lower_max[:, None]
        active_blocks = np.sum(block_active, axis=1).astype(np.int64)
        shaped_rows = active_blocks * block_size
        block_retained = block_active[
            np.arange(len(hidden)), exact_winners // block_size
        ]
        if not np.all(block_retained):
            raise RuntimeError(f"{name}: B={block_size} lost an exact winner")
        variants.append(
            {
                "blockSize": block_size,
                "gateCount": blocks,
                "activeBlocks": distribution(active_blocks),
                "shapedRows": distribution(shaped_rows),
                "extraRowsVersusTokenGate": distribution(shaped_rows - token_rows),
                "meanRowInflation": float(np.mean(shaped_rows) / np.mean(token_rows)),
                "meanExactGlyphs": float(np.mean(shaped_rows) * 12),
                "winnerRetainedStates": int(np.sum(block_retained)),
            }
        )
    return {
        "name": name,
        "states": len(hidden),
        "tokenGateActiveRows": distribution(token_rows),
        "exactWinnerRetainedStates": int(np.sum(retained)),
        "variants": variants,
    }


def markdown(result: dict[str, object]) -> str:
    corpus = result["screens"][0]
    fixtures = result["screens"][1]
    rows = []
    for corpus_row, fixture_row in zip(corpus["variants"], fixtures["variants"]):
        rows.append(
            "| {b} | {gates} | {ca:.2f} | {cr:.2f} | {ci:.2f}× | "
            "{fr:.2f} | {fi:.2f}× |".format(
                b=corpus_row["blockSize"],
                gates=corpus_row["gateCount"],
                ca=corpus_row["activeBlocks"]["mean"],
                cr=corpus_row["shapedRows"]["mean"],
                ci=corpus_row["meanRowInflation"],
                fr=fixture_row["shapedRows"]["mean"],
                fi=fixture_row["meanRowInflation"],
            )
        )
    return f"""# Token uncertainty block-size sweep

## Result

Contiguous block gating preserves the exact winner for every tested state, as expected from the inclusive `max(block upper) >= max(token lower)` rule. It exposes a tunable tradeoff between fewer container-query gates and more exact rows. This is an offline structural screen; browser timing decides whether any point beats the retained full 256-row grid.

The token-granular baseline shapes a mean **{corpus['tokenGateActiveRows']['mean']:.2f}** rows over the 1,024-state corpus and **{fixtures['tokenGateActiveRows']['mean']:.2f}** rows over the ten browser fixtures.

| Block size | Static gates | Mean active blocks (corpus) | Mean shaped rows (corpus) | Row inflation | Mean shaped rows (fixtures) | Fixture inflation |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Interpretation

The browser probe should focus on the knee rather than every size: the smallest candidates that materially reduce the 256 gate carriers while keeping exact-row inflation bounded. The raw JSON records minimum, median, p95, maximum, and mean active blocks and shaped rows for every size on both screens.

## Contract

- Group: fixed GPT-2 vocabulary group 0, 256 tokens.
- Target: retained global-int16 head.
- Coarse bound: row-wise signed int10 center plus/minus the Cauchy radius to the global-int16 target.
- Outward allowance: 27 score buckets, matching the token-level browser probe.
- Corpus hidden vectors are snapped to the production axis grid and use the conservative query-norm upper bound.
- A block is active iff any token upper bound in that block is at least the global maximum token lower bound.

Generated in **{result['runtimeSeconds']:.2f}s** by `tools/analyze_token_uncertainty_block_sweep.py`.
"""


def main() -> None:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fine_reference = json.loads((FINE / "reference.json").read_text())
    fine_scale = float(fine_reference["weightScale"])
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:GROUP_SIZE],
        dtype=np.float64,
    )
    target = np.rint(weights / fine_scale) * fine_scale
    maximum_code = 2 ** 9 - 1
    row_scales = np.max(np.abs(target), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    represented = np.rint(target / row_scales[:, None]) * row_scales[:, None]
    error_norms = np.linalg.norm(target - represented, axis=1)

    saved = np.load(STATES)
    corpus_hidden = np.asarray(saved["hidden"], dtype=np.float64)
    maximum_coordinate = float(np.max(np.abs(corpus_hidden)))
    production_range = maximum_coordinate * 1.01
    realized_hidden = (
        np.rint(corpus_hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    axis_l2_bound = production_range * math.sqrt(WIDTH) / (2 * AXIS_STEPS)
    corpus_norm_upper = np.linalg.norm(corpus_hidden, axis=1) + axis_l2_bound

    fixture_reference = json.loads(FIXTURES.read_text())["certifiedFixtures"]
    fixture_hidden = np.asarray(fixture_reference["hiddenVectors"], dtype=np.float64)
    fixture_norms = np.linalg.norm(fixture_hidden, axis=1)

    screens = [
        screen(
            "1,024-state snapped router corpus",
            realized_hidden,
            corpus_norm_upper,
            represented,
            target,
            error_norms,
        ),
        screen(
            "ten browser fixtures",
            fixture_hidden,
            fixture_norms,
            represented,
            target,
            error_norms,
        ),
    ]
    result = {
        "model": "openai-community/gpt2",
        "group": 0,
        "groupSize": GROUP_SIZE,
        "blockSizes": list(BLOCK_SIZES),
        "scoreScale": SCORE_SCALE,
        "totalOutwardAllowanceBuckets": TOTAL_ALLOWANCE_BUCKETS,
        "screens": screens,
        "runtimeSeconds": time.perf_counter() - started,
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(markdown(result))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
