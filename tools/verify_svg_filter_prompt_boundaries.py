#!/usr/bin/env python3
"""Find the first browser state boundary that changes GPT-2's final winner."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_svg_quantization_strategies import exact_forward, load_checkpoint


CASES = Path(os.environ.get("SVG_PROMPT_CASES", "/tmp/gpt2-css-prompt-cases/cases.json"))
OUTPUT = Path(
    os.environ.get("SVG_BOUNDARY_OUTPUT", "/tmp/svg-filter-prompt-boundaries.json")
)
REPORT = os.environ.get("SVG_BOUNDARY_REPORT")
CORRECTION_COUNTS = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 768)


def main() -> None:
    payload = json.loads(CASES.read_text())
    cases = {item["token_id"]: item for item in payload["cases"]}
    traces = json.loads(OUTPUT.read_text())["outputs"]
    _, embedding, blocks, final_gamma, final_beta = load_checkpoint()

    def winner(state: np.ndarray, completed_blocks: int) -> int:
        final = exact_forward(
            state[None, :], blocks[completed_blocks:], final_gamma, final_beta
        )[0]
        return int(np.argmax(embedding @ final))

    reports: list[dict[str, object]] = []
    for trace in traces:
        case = cases[trace["token_id"]]
        expected_winner = int(case["expected_winner"])
        input_pixels = np.asarray(
            Image.open(CASES.parent / case["image"]).convert("L"), dtype=np.float64
        ).reshape(-1)
        input_scales = np.asarray(payload["input_scales"], dtype=np.float64)
        browser_input = (input_pixels / 255 - 128 / 255) * 2 * input_scales
        boundaries: list[dict[str, object]] = [
            {
                "boundary": "input",
                "completed_blocks": 0,
                "downstream_winner": winner(browser_input, 0),
            }
        ]
        for block_output in trace["blocks"]:
            index = int(block_output["block"])
            actual = np.asarray(block_output["state"], dtype=np.float64)
            expected = np.asarray(case["block_expected"][index - 1], dtype=np.float64)
            boundaries.append(
                {
                    "boundary": f"after_block_{index}",
                    "completed_blocks": index,
                    "downstream_winner": winner(actual, index),
                    "rmse": float(np.sqrt(np.mean((actual - expected) ** 2))),
                    "max_error": float(np.max(np.abs(actual - expected))),
                }
            )

        first_failure = next(
            (
                boundary
                for boundary in boundaries
                if boundary["downstream_winner"] != expected_winner
            ),
            None,
        )
        correction: dict[str, object] | None = None
        if first_failure is not None:
            completed = int(first_failure["completed_blocks"])
            if completed == 0:
                actual = browser_input
                expected = np.asarray(case["input_expected"], dtype=np.float64)
            else:
                actual = np.asarray(
                    trace["blocks"][completed - 1]["state"], dtype=np.float64
                )
                expected = np.asarray(
                    case["block_expected"][completed - 1], dtype=np.float64
                )
            error_order = np.argsort(np.abs(expected - actual))[::-1]
            attempts = []
            for count in CORRECTION_COUNTS:
                corrected = actual.copy()
                corrected[error_order[:count]] = expected[error_order[:count]]
                corrected_winner = winner(corrected, completed)
                attempts.append({"dimensions": count, "winner": corrected_winner})
                if corrected_winner == expected_winner:
                    break
            correction = {
                "ordering": "largest absolute boundary errors first",
                "attempts": attempts,
                "selected_dimensions": error_order[: attempts[-1]["dimensions"]]
                .astype(int)
                .tolist(),
            }

        reports.append(
            {
                "token_id": case["token_id"],
                "token": case["token"],
                "expected_winner": expected_winner,
                "first_ranking_failure": (
                    first_failure["boundary"] if first_failure is not None else None
                ),
                "boundaries": boundaries,
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
                    "boundaries": [
                        {
                            "token_id": item["token_id"],
                            "token": item["token"],
                            "first_ranking_failure": item["first_ranking_failure"],
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
