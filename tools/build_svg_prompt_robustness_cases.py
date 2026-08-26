#!/usr/bin/env python3
"""Build real-token inputs for the retained 32-bucket Chromium graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_svg_quantization_strategies import (
    exact_forward,
    gelu_new,
    layer_norm,
    load_checkpoint,
)
from build_pretrained_gpt2 import Gpt2Tokenizer


CENTER = 128 / 255
BUCKETS = 32
HEADROOM = 1.08
DEFAULT_OUT = Path("/tmp/gpt2-css-prompt-cases")
TOKEN_IDS = (0, 11, 13, 40, 257, 262, 284, 290, 383, 464, 770, 995, 1212, 1310, 15496, 50256)
NATURAL_PROMPTS = (
    "Once upon a time there was a little girl who lived near the forest.",
    "One day she found a small dog waiting beside the road.",
    "The boy opened the door and looked inside the quiet room.",
    "A kind old woman gave him a warm bowl of soup.",
    "They walked home together under the bright blue sky.",
    "Suddenly a loud noise came from behind the trees.",
    "I think we should help our friend before it gets dark.",
    "This was the happiest day of her life, and everyone smiled.",
    "He wanted to build a boat, but he did not have enough wood.",
    "After breakfast, the children ran outside to play in the garden.",
    "The tiny bird could not fly yet, so its mother stayed close.",
    "Please tell me why the moon follows us when we drive at night.",
    "She picked up the red ball and threw it across the field.",
    "There were three cookies left on the plate for the family.",
    "When the rain stopped, a rainbow appeared over the town.",
    "My name is Lily and this is my brother Tom.",
)


def input_scales(vector: np.ndarray) -> np.ndarray:
    desired = np.maximum(np.abs(vector) * HEADROOM, 1e-6)
    logs = np.log2(desired)
    edges = np.linspace(float(np.min(logs)), float(np.max(logs)), BUCKETS + 1)
    ids = np.clip(
        np.searchsorted(edges, logs, side="right") - 1, 0, BUCKETS - 1
    )
    return np.exp2(edges[1:])[ids]


def readable_token(token: str) -> str:
    return token.replace("Ġ", " ").replace("Ċ", "\\n")


def bucket_scales(bound: np.ndarray) -> np.ndarray:
    desired = np.maximum(np.asarray(bound, dtype=np.float64) * HEADROOM, 1e-6)
    logs = np.log2(desired)
    edges = np.linspace(float(np.min(logs)), float(np.max(logs)), BUCKETS + 1)
    ids = np.clip(
        np.searchsorted(edges, logs, side="right") - 1, 0, BUCKETS - 1
    )
    return np.exp2(edges[1:])[ids]


def trace_blocks(inputs: np.ndarray, blocks: list[object]) -> list[np.ndarray]:
    states = np.asarray(inputs, dtype=np.float64).copy()
    trace: list[np.ndarray] = []
    for block in blocks:
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = normalized1 @ block.attention_weight.T + block.attention_bias
        residual = states + learned
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        hidden = gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias)
        projection = hidden @ block.projection_weight.T + block.projection_bias
        states = residual + projection
        trace.append(states.copy())
    return trace


def calibration_block_scales(
    inputs: np.ndarray, blocks: list[object]
) -> list[np.ndarray]:
    """Reproduce the fixed output scale chosen after every generated block."""
    states = np.asarray(inputs, dtype=np.float64).copy()
    scales: list[np.ndarray] = []
    for block in blocks:
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = normalized1 @ block.attention_weight.T + block.attention_bias
        residual = states + learned
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        hidden = gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias)
        projection = hidden @ block.projection_weight.T + block.projection_bias
        output_bound = (
            np.max(np.abs(projection), axis=0)
            + np.max(np.abs(residual), axis=0)
        )
        states = residual + projection
        scales.append(bucket_scales(output_bound))
    return scales


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--natural-suite", action="store_true")
    parser.add_argument("--max-cases", type=int, default=64)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    calibration_inputs, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    position = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wpe.weight")[0], dtype=np.float64
    )
    vocab = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "gpt2" / "vocab.json").read_text()
    )
    reverse_vocab = {int(index): readable_token(token) for token, index in vocab.items()}

    base = embedding[15496] + position
    if args.reference is None:
        scales = input_scales(base)
    else:
        scales = np.asarray(
            json.loads(args.reference.read_text())["bucket_input_scales"],
            dtype=np.float64,
        )
    token_ids = list(TOKEN_IDS)
    if args.natural_suite:
        tokenizer = Gpt2Tokenizer(
            Path(__file__).resolve().parents[1] / "data" / "gpt2" / "vocab.json",
            Path(__file__).resolve().parents[1] / "data" / "gpt2" / "merges.txt",
        )
        token_ids = list(
            dict.fromkeys(
                token_id
                for prompt in NATURAL_PROMPTS
                for token_id in tokenizer.encode(prompt)
            )
        )[: args.max_cases]
    vectors = np.stack([embedding[token_id] + position for token_id in token_ids])
    expected = exact_forward(vectors, blocks, final_gamma, final_beta)
    block_trace = trace_blocks(vectors, blocks)
    block_output_scales = calibration_block_scales(calibration_inputs, blocks)
    expected_scores = expected @ embedding.T
    expected_winners = np.argmax(expected_scores, axis=1)

    cases: list[dict[str, object]] = []
    for index, token_id in enumerate(token_ids):
        raw = CENTER + vectors[index] / (2 * scales)
        clipped = np.count_nonzero((raw < 0) | (raw > 1))
        pixels = np.rint(np.clip(raw, 0, 1) * 255).astype(np.uint8)[None, :]
        filename = f"token-{token_id}.png"
        Image.fromarray(pixels, mode="L").save(args.output / filename, optimize=True)
        order = np.argsort(expected_scores[index])[-2:][::-1]
        cases.append(
            {
                "token_id": token_id,
                "token": reverse_vocab[token_id],
                "image": filename,
                "input_clipped_dimensions": int(clipped),
                "input_expected": vectors[index].tolist(),
                "expected": expected[index].tolist(),
                "expected_winner": int(expected_winners[index]),
                "expected_runner_up": int(order[1]),
                "expected_logit_margin": float(
                    expected_scores[index, order[0]] - expected_scores[index, order[1]]
                ),
                "block_expected": [stage[index].tolist() for stage in block_trace],
            }
        )

    payload = {
        "description": "Real single-token inputs using the retained Hello-calibrated 32-bucket graph",
        "input_scales": scales.tolist(),
        "block_output_scales": [scale.tolist() for scale in block_output_scales],
        "cases": cases,
    }
    (args.output / "cases.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "cases": len(cases),
                "cases_with_input_clipping": sum(
                    case["input_clipped_dimensions"] > 0 for case in cases
                ),
                "maximum_clipped_dimensions": max(
                    case["input_clipped_dimensions"] for case in cases
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
