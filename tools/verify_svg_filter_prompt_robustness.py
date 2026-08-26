#!/usr/bin/env python3
"""Score browser robustness captures with GPT-2's real tied output head."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


CASES = Path(os.environ.get("SVG_PROMPT_CASES", "/tmp/gpt2-css-prompt-cases/cases.json"))
OUTPUT = Path(os.environ.get("SVG_PROMPT_OUTPUT", "/tmp/svg-filter-prompt-robustness.json"))
REPORT = os.environ.get("SVG_PROMPT_REPORT")


def main() -> None:
    cases = json.loads(CASES.read_text())["cases"]
    outputs = json.loads(OUTPUT.read_text())["outputs"]
    embeddings = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight"), dtype=np.float64
    )
    reports: list[dict[str, object]] = []
    for case, output in zip(cases, outputs, strict=True):
        actual = np.asarray(output["final"], dtype=np.float64)
        expected = np.asarray(case["expected"], dtype=np.float64)
        scores = embeddings @ actual
        top = np.argsort(scores)[-5:][::-1]
        error = actual - expected
        reports.append(
            {
                "token_id": case["token_id"],
                "token": case["token"],
                "expected_winner": case["expected_winner"],
                "browser_winner": int(top[0]),
                "winner_matches": int(top[0]) == case["expected_winner"],
                "browser_top5": top.astype(int).tolist(),
                "reference_margin": case["expected_logit_margin"],
                "input_clipped_dimensions": case["input_clipped_dimensions"],
                "rmse": float(np.sqrt(np.mean(error**2))),
                "max_error": float(np.max(np.abs(error))),
                "milliseconds": output["milliseconds"],
            }
        )
    payload = {
        "matches": sum(item["winner_matches"] for item in reports),
        "total": len(reports),
        "reports": reports,
    }
    if REPORT:
        Path(REPORT).write_text(json.dumps(payload, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "report": REPORT,
                    "matches": payload["matches"],
                    "total": payload["total"],
                    "failed_tokens": [
                        {"id": item["token_id"], "token": item["token"]}
                        for item in reports
                        if not item["winner_matches"]
                    ],
                    "mean_rmse": float(np.mean([item["rmse"] for item in reports])),
                    "mean_milliseconds": float(
                        np.mean([item["milliseconds"] for item in reports])
                    ),
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
