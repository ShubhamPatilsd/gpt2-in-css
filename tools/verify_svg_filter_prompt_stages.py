#!/usr/bin/env python3
"""Identify the exact intra-block surface that first changes token ranking."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from analyze_svg_quantization_strategies import exact_forward, load_checkpoint
from build_gpt2_block_css import gelu_new, layer_norm


CASES = Path(os.environ.get("SVG_PROMPT_CASES", "/tmp/gpt2-css-prompt-cases/cases.json"))
OUTPUT = Path(os.environ.get("SVG_STAGE_OUTPUT", "/tmp/svg-filter-prompt-stages.json"))
REPORT = os.environ.get("SVG_STAGE_REPORT")
COUNTS = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 768, 1536, 3072)
STAGE_NAMES = {
    1: "layer_norm_1",
    2: "attention_residual",
    3: "layer_norm_2",
    4: "mlp_hidden",
    5: "block_output",
}


def main() -> None:
    cases = {
        item["token_id"]: item for item in json.loads(CASES.read_text())["cases"]
    }
    traces = json.loads(OUTPUT.read_text())["outputs"]
    _, embedding, blocks, final_gamma, final_beta = load_checkpoint()

    def finish_block(values: dict[str, np.ndarray], stage: int, block_index: int) -> np.ndarray:
        block = blocks[block_index]
        if stage == 1:
            residual = (
                values["input"]
                + values["normalized"] @ block.attention_weight.T
                + block.attention_bias
            )
            normalized2 = layer_norm(residual, block.ln2_gamma, block.ln2_beta)
            hidden = gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias)
            return residual + hidden @ block.projection_weight.T + block.projection_bias
        if stage == 2:
            residual = values["residual"]
            normalized2 = layer_norm(residual, block.ln2_gamma, block.ln2_beta)
            hidden = gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias)
            return residual + hidden @ block.projection_weight.T + block.projection_bias
        if stage == 3:
            hidden = gelu_new(values["normalized"] @ block.fc_weight.T + block.fc_bias)
            return values["residual"] + hidden @ block.projection_weight.T + block.projection_bias
        if stage == 4:
            return (
                values["residual"]
                + values["hidden"] @ block.projection_weight.T
                + block.projection_bias
            )
        return values["output"]

    def downstream_winner(values: dict[str, np.ndarray], stage: int, block_index: int) -> int:
        state = finish_block(values, stage, block_index)
        final = exact_forward(
            state[None, :], blocks[block_index + 1 :], final_gamma, final_beta
        )[0]
        return int(np.argmax(embedding @ final))

    reports = []
    for trace in traces:
        case = cases[trace["token_id"]]
        block_index = int(trace["target_block"]) - 1
        block = blocks[block_index]
        exact_input = np.asarray(
            case["input_expected"]
            if block_index == 0
            else case["block_expected"][block_index - 1],
            dtype=np.float64,
        )
        exact_n1 = layer_norm(exact_input, block.ln1_gamma, block.ln1_beta)
        exact_residual = (
            exact_input + exact_n1 @ block.attention_weight.T + block.attention_bias
        )
        exact_n2 = layer_norm(exact_residual, block.ln2_gamma, block.ln2_beta)
        exact_hidden = gelu_new(exact_n2 @ block.fc_weight.T + block.fc_bias)
        exact_output = (
            exact_residual
            + exact_hidden @ block.projection_weight.T
            + block.projection_bias
        )
        exact_primary = {
            1: exact_n1,
            2: exact_residual,
            3: exact_n2,
            4: exact_hidden,
            5: exact_output,
        }
        primary_key = {1: "normalized", 2: "residual", 3: "normalized", 4: "hidden", 5: "output"}
        stage_reports = []
        for captured in trace["stages"]:
            stage = int(captured["stage"])
            values = {
                key: np.asarray(value, dtype=np.float64)
                for key, value in captured["values"].items()
            }
            key = primary_key[stage]
            error = values[key] - exact_primary[stage]
            stage_reports.append(
                {
                    "stage": STAGE_NAMES[stage],
                    "downstream_winner": downstream_winner(values, stage, block_index),
                    "primary_rmse": float(np.sqrt(np.mean(error**2))),
                    "primary_max_error": float(np.max(np.abs(error))),
                }
            )
        expected_winner = int(case["expected_winner"])
        first_failure_index = next(
            (
                index
                for index, stage in enumerate(stage_reports)
                if stage["downstream_winner"] != expected_winner
            ),
            None,
        )
        correction = None
        if first_failure_index is not None:
            captured = trace["stages"][first_failure_index]
            stage = int(captured["stage"])
            values = {
                key: np.asarray(value, dtype=np.float64)
                for key, value in captured["values"].items()
            }
            key = primary_key[stage]
            target = exact_primary[stage]
            order = np.argsort(np.abs(target - values[key]))[::-1]
            attempts = []
            for count in COUNTS:
                if count > len(order):
                    continue
                candidate = {name: value.copy() for name, value in values.items()}
                candidate[key][order[:count]] = target[order[:count]]
                token = downstream_winner(candidate, stage, block_index)
                attempts.append({"dimensions": count, "winner": token})
                if token == expected_winner:
                    break
            correction = {
                "surface": STAGE_NAMES[stage],
                "component": key,
                "attempts": attempts,
                "selected_dimensions": order[: attempts[-1]["dimensions"]]
                .astype(int)
                .tolist(),
            }
        reports.append(
            {
                "token_id": case["token_id"],
                "token": case["token"],
                "target_block": trace["target_block"],
                "expected_winner": expected_winner,
                "first_failing_surface": (
                    stage_reports[first_failure_index]["stage"]
                    if first_failure_index is not None
                    else None
                ),
                "stages": stage_reports,
                "correction_screen": correction,
            }
        )
    payload = {"reports": reports}
    if REPORT:
        Path(REPORT).write_text(json.dumps(payload, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "report": REPORT,
                    "surfaces": [
                        {
                            "token_id": item["token_id"],
                            "token": item["token"],
                            "block": item["target_block"],
                            "first_failing_surface": item["first_failing_surface"],
                        }
                        for item in reports
                    ],
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
