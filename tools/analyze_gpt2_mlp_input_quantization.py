#!/usr/bin/env python3
"""Test packed-axis-friendly uniform quantization of every GPT-2 MLP input."""

from __future__ import annotations

import json
import time

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_fc_lowrank import CHECKPOINT, OUTPUT, PROMPTS, forward
from build_pretrained_gpt2 import Gpt2Tokenizer


BITS = (2, 3, 4, 5, 6, 8)
RANGES = (2.0, 3.0, 4.0, 6.0)


def main() -> None:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    tokenizer = Gpt2Tokenizer(CHECKPOINT / "vocab.json", CHECKPOINT / "merges.txt")
    exact_cases = []
    for prompt in PROMPTS:
        token_ids = tokenizer.encode(prompt)
        logits = forward(token_ids, tensors, [], None)
        exact_cases.append((prompt, token_ids, logits, int(np.argmax(logits))))

    summary = []
    cases = []
    for quantization_range in RANGES:
        for bits in BITS:
            values = []
            for prompt, token_ids, exact, exact_winner in exact_cases:
                approximate = forward(
                    token_ids,
                    tensors,
                    [],
                    None,
                    quantization_bits=bits,
                    quantization_range=quantization_range,
                )
                winner = int(np.argmax(approximate))
                values.append({
                    "prompt": prompt,
                    "winner": winner,
                    "exactWinner": exact_winner,
                    "top1Matches": winner == exact_winner,
                    "exactWinnerRank": int(1 + np.sum(approximate > approximate[exact_winner])),
                    "logitRmse": float(np.sqrt(np.mean((approximate - exact) ** 2))),
                })
            maximum_code = 2 ** (bits - 1) - 1
            statesPerActivation = 2 * maximum_code + 1
            result = {
                "bits": bits,
                "range": quantization_range,
                "statesPerActivation": statesPerActivation,
                "packedStatesPerAxis": statesPerActivation**3,
                "avarRegionsFor256Axes": 256 * statesPerActivation**3,
                "avarDeltasPer256HiddenShard": 256 * 256 * statesPerActivation**3,
                "top1Matches": sum(item["top1Matches"] for item in values),
                "cases": len(values),
                "medianExactWinnerRank": float(np.median([item["exactWinnerRank"] for item in values])),
                "maximumExactWinnerRank": max(item["exactWinnerRank"] for item in values),
                "meanLogitRmse": float(np.mean([item["logitRmse"] for item in values])),
            }
            summary.append(result)
            cases.append({**result, "prompts": values})
    report = {
        "model": "gpt2-small",
        "quantizedBoundary": "input to every MLP c_fc",
        "prompts": len(PROMPTS),
        "summary": summary,
        "cases": cases,
        "elapsedSeconds": time.perf_counter() - started,
    }
    path = OUTPUT / "input-quantization-results.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    best_by_bits = []
    for bits in BITS:
        candidates = [item for item in summary if item["bits"] == bits]
        best_by_bits.append(max(candidates, key=lambda item: (
            item["top1Matches"], -item["medianExactWinnerRank"], -item["meanLogitRmse"]
        )))
    print(json.dumps({
        "bestByBits": best_by_bits,
        "elapsedSeconds": report["elapsedSeconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
