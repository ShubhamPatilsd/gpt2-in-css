#!/usr/bin/env python3
"""Check post-training row-wise output-score quantization end to end."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "tools" / "build_clustered_output_head_benchmark.py"
SPEC = importlib.util.spec_from_file_location("row_score_builder", BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {BUILDER_PATH}")
BUILDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILDER
SPEC.loader.exec_module(BUILDER)

PROMPTS = [
    "Once upon a time",
    "The little girl",
    "One day",
    "There was a",
    "The boy",
    "A little dog",
    "Lily was",
    "Tom wanted to",
    "In a small village",
    "The cat",
    "She went to",
    "He saw a",
    "It was a sunny day",
    "Once there was",
    "The princess",
    "The farmer",
    "A big bear",
    "Mia and her mom",
    "Jack had a",
    "The children",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=16)
    parser.add_argument("--bits", type=int, default=8)
    parser.add_argument("--require-exact", action="store_true")
    arguments = parser.parse_args()

    state = BUILDER.BUILDER.load_torch_zip(BUILDER.BUILDER.download_checkpoint())
    embeddings = state["transformer.wte.weight"].astype(np.float64)
    _codes, _scales, quantized = BUILDER.quantize_token_rows(
        embeddings, arguments.bits
    )
    tokenizer = BUILDER.BUILDER.BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )

    tested_tokens = 0
    divergences = []
    for prompt in PROMPTS:
        context = tokenizer.encode(prompt)
        for step in range(arguments.steps):
            hidden = BUILDER.BUILDER.final_hidden(context, state)
            reference = int((embeddings @ hidden).argmax())
            candidate = int((quantized @ hidden).argmax())
            tested_tokens += 1
            if candidate != reference:
                divergences.append(
                    {
                        "prompt": prompt,
                        "step": step,
                        "reference": reference,
                        "candidate": candidate,
                        "reference_text": tokenizer.decode_token(reference),
                        "candidate_text": tokenizer.decode_token(candidate),
                    }
                )
                break
            context.append(reference)

    result = {
        "bits": arguments.bits,
        "prompts": len(PROMPTS),
        "steps_per_prompt": arguments.steps,
        "tested_matching_prefix_tokens": tested_tokens,
        "divergent_prompts": len(divergences),
        "divergences": divergences,
        "maximum_embedding_error": float(np.max(np.abs(quantized - embeddings))),
        "mean_squared_embedding_error": float(
            np.mean((quantized - embeddings) ** 2)
        ),
    }
    print(json.dumps(result, indent=2))
    if arguments.require_exact and divergences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
