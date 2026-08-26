#!/usr/bin/env python3
"""Build a B=4 hot gate whose quartets are clustered by co-activation."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_certified_int10_upper_head as certified
import build_mixed_hot2_reused_upper_block_gate_probe as reused
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-coactivation-block-gate-b4"
BLOCK_SIZE = 4
CALIBRATION_STATES = 512
SWAP_PASSES = 120_000


def bounds(
    hidden: np.ndarray,
    represented: np.ndarray,
    target: np.ndarray,
    float_errors: np.ndarray,
    target_errors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    norms = np.linalg.norm(hidden, axis=1)
    centers = hidden @ represented.T * token_gate.SCORE_SCALE
    paid_upper = np.floor(
        centers + norms[:, None] * float_errors[None, :] * token_gate.SCORE_SCALE
    ) + 1
    float_radius = norms[:, None] * float_errors[None, :] * token_gate.SCORE_SCALE
    target_radius = norms[:, None] * target_errors[None, :] * token_gate.SCORE_SCALE
    lower = (
        paid_upper - float_radius - target_radius - 1
        - token_gate.TOTAL_ALLOWANCE_BUCKETS
    )
    upper = (
        paid_upper - float_radius + target_radius
        + token_gate.TOTAL_ALLOWANCE_BUCKETS
    )
    return lower, upper, hidden @ target.T


def active_signatures(
    lower: np.ndarray,
    upper: np.ndarray,
    group: int,
) -> np.ndarray:
    start = group * token_gate.GROUP_SIZE
    stop = start + token_gate.GROUP_SIZE
    threshold = np.max(lower[:, start:stop], axis=1)
    return upper[:, start:stop] >= threshold[:, None]


def greedy_partition(active: np.ndarray, descending: bool) -> list[list[int]]:
    remaining = set(range(token_gate.GROUP_SIZE))
    frequency = np.sum(active, axis=0)
    blocks = []
    while remaining:
        seed = sorted(
            remaining,
            key=lambda token: ((-1 if descending else 1) * frequency[token], token),
        )[0]
        block = [seed]
        remaining.remove(seed)
        while len(block) < BLOCK_SIZE:
            current = np.any(active[:, block], axis=1)
            choice = min(
                remaining,
                key=lambda token: (
                    int(np.sum(current | active[:, token])),
                    -int(np.sum(current & active[:, token])),
                    token,
                ),
            )
            block.append(choice)
            remaining.remove(choice)
        blocks.append(block)
    return blocks


def partition_cost(active: np.ndarray, blocks: list[list[int]]) -> int:
    return sum(int(np.sum(np.any(active[:, block], axis=1))) for block in blocks)


def improve_partition(
    active: np.ndarray,
    initial: list[list[int]],
    seed: int,
) -> list[list[int]]:
    rng = np.random.default_rng(seed)
    blocks = [list(block) for block in initial]
    costs = [int(np.sum(np.any(active[:, block], axis=1))) for block in blocks]
    for _ in range(SWAP_PASSES):
        left, right = rng.choice(len(blocks), size=2, replace=False)
        left_slot = int(rng.integers(BLOCK_SIZE))
        right_slot = int(rng.integers(BLOCK_SIZE))
        candidate_left = list(blocks[left])
        candidate_right = list(blocks[right])
        candidate_left[left_slot], candidate_right[right_slot] = (
            candidate_right[right_slot], candidate_left[left_slot]
        )
        left_cost = int(np.sum(np.any(active[:, candidate_left], axis=1)))
        right_cost = int(np.sum(np.any(active[:, candidate_right], axis=1)))
        if left_cost + right_cost < costs[left] + costs[right]:
            blocks[left] = candidate_left
            blocks[right] = candidate_right
            costs[left] = left_cost
            costs[right] = right_cost
    normalized = [sorted(block) for block in blocks]
    return sorted(normalized, key=lambda block: (block[0], block))


def choose_partition(active: np.ndarray, group: int) -> list[list[int]]:
    candidates = []
    for index, initial in enumerate((
        greedy_partition(active, descending=True),
        greedy_partition(active, descending=False),
        [list(range(start, start + BLOCK_SIZE)) for start in range(0, 256, 4)],
    )):
        candidates.append(improve_partition(active, initial, 1701 + group * 17 + index))
    return min(candidates, key=lambda blocks: (partition_cost(active, blocks), blocks))


def report_partition(active: np.ndarray, blocks: list[list[int]]) -> dict[str, float | int]:
    active_blocks = np.column_stack([
        np.any(active[:, block], axis=1) for block in blocks
    ])
    shaped = np.sum(active_blocks, axis=1) * BLOCK_SIZE
    return {
        "states": len(active),
        "meanShapedRows": float(np.mean(shaped)),
        "medianShapedRows": float(np.median(shaped)),
        "maximumShapedRows": int(np.max(shaped)),
        "activationCost": int(np.sum(active_blocks)),
    }


def contiguous_report(active: np.ndarray) -> dict[str, float | int]:
    blocks = [list(range(start, start + BLOCK_SIZE)) for start in range(0, 256, 4)]
    return report_partition(active, blocks)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fine_reference = json.loads((token_gate.FINE / "reference.json").read_text())
    source_reference = json.loads((reused.SOURCE / "reference.json").read_text())
    upper_rows = reused.paid_upper_candidates()
    fine_rows = token_gate.records(token_gate.FINE / "index.html")
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: 2 * token_gate.GROUP_SIZE],
        dtype=np.float64,
    )
    maximum_code = 2 ** 9 - 1
    row_scales = np.max(np.abs(weights), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    represented = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale) * fine_scale
    float_errors = np.linalg.norm(weights - represented, axis=1)
    target_errors = np.linalg.norm(target - represented, axis=1)

    recomputed_float_factors = [
        certified.css_number_up(
            value * token_gate.SCORE_SCALE * token_gate.SCORE_STRIDE_PX
        )
        for value in float_errors
    ]
    float_factors = []
    for token, row in enumerate(upper_rows[: 2 * token_gate.GROUP_SIZE]):
        match = re.search(r"--bound-factor:([^;]+);", row)
        if match is None or match.group(1) != recomputed_float_factors[token]:
            raise RuntimeError(f"paid upper factor mismatch at token {token}")
        float_factors.append(match.group(1))
    target_factors = [
        token_gate.outward_number(
            value * token_gate.SCORE_SCALE * token_gate.SCORE_STRIDE_PX
        )
        for value in target_errors
    ]
    float_factors_by_group = np.asarray(float_factors).reshape(2, 256).tolist()
    target_factors_by_group = np.asarray(target_factors).reshape(2, 256).tolist()

    saved = np.load(STATES)
    corpus_hidden = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(corpus_hidden))) * 1.01
    corpus_realized = (
        np.rint(corpus_hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS * production_range
    )
    corpus_lower, corpus_upper, _ = bounds(
        corpus_realized, represented, target, float_errors, target_errors
    )
    fixture_hidden = np.asarray(
        source_reference["certifiedFixtures"]["hiddenVectors"], dtype=np.float64
    )
    fixture_lower, fixture_upper, _ = bounds(
        fixture_hidden, represented, target, float_errors, target_errors
    )

    partitions = []
    screens = []
    for group in reused.HOT_GROUPS:
        corpus_active = active_signatures(corpus_lower, corpus_upper, group)
        calibration = corpus_active[:CALIBRATION_STATES]
        holdout = corpus_active[CALIBRATION_STATES:]
        partition = choose_partition(calibration, group)
        partitions.append(partition)
        fixture_active = active_signatures(fixture_lower, fixture_upper, group)
        screens.append({
            "group": group,
            "calibration": report_partition(calibration, partition),
            "holdout": report_partition(holdout, partition),
            "holdoutContiguous": contiguous_report(holdout),
            "fixtures": report_partition(fixture_active, partition),
            "fixturesContiguous": contiguous_report(fixture_active),
        })

    topology = (reused.SOURCE / "topology.css").read_text().replace(
        "anchor-size(--group-0 width)", "anchor-size(--hot-exact-0 width)"
    ).replace(
        "anchor-size(--group-1 width)", "anchor-size(--hot-exact-1 width)"
    )
    html = reused.build_html(BLOCK_SIZE, upper_rows, fine_rows, partitions)
    html = html.replace(
        "Mixed hot-two reused-upper block gate B=4",
        "Mixed hot-two co-activation block gate B=4",
        1,
    )
    css = topology + reused.gate_css(
        BLOCK_SIZE,
        fine_reference,
        float_factors_by_group,
        target_factors_by_group,
        partitions,
    )
    reference = {
        **source_reference,
        "backend": "mixed-hot2-coactivation-block-gate-b4",
        "sourceMixed": reused.SOURCE.name,
        "blockSize": BLOCK_SIZE,
        "partitionCalibrationStates": CALIBRATION_STATES,
        "partitionSwapPasses": SWAP_PASSES,
        "partitions": partitions,
        "offlineScreens": screens,
        "topologyStrategy": (
            "reuse paid int10 upper widths and the direct 197-way outer maximum; "
            "cluster each hot group's exact rows into fixed quartets that minimize "
            "co-activation on a disjoint 512-state calibration split"
        ),
        "generatedBytes": {
            "index.html": len(html.encode()),
            "topology.css": len(css.encode()),
        },
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "topology.css").write_text(css)
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "directory": OUTPUT.name,
        "screens": screens,
        "generatedBytes": reference["generatedBytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
