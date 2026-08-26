#!/usr/bin/env python3
"""Build a two-token attention reference for the block after a live SVG block."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

from build_gpt2_block_css import QUANT_BITS, gelu_new, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(
    os.environ.get(
        "SVG_NEXT_BLOCK_BASE_REFERENCE",
        ROOT / "experiments" / "svg-multitoken-attention-rgb-centered" / "reference.json",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_NEXT_BLOCK_REFERENCE_OUT",
        ROOT / "experiments" / "svg-block1-attention-reference.json",
    )
).resolve()
BLOCK_INDEX = int(os.environ.get("SVG_NEXT_BLOCK_INDEX", "1"))
WIDTH = 768
HEADS = 12
HEAD_WIDTH = 64


def main() -> None:
    if BLOCK_INDEX < 1:
        raise ValueError("SVG_NEXT_BLOCK_INDEX must be at least 1")
    base = json.loads(BASE.read_text())
    attention_residual = np.asarray(base["expected_residual"], dtype=np.float64)
    previous = model_data(block_index=BLOCK_INDEX - 1)
    q_fc = quantize_float_rows(previous["fc_weight"], bits=QUANT_BITS)
    q_projection = quantize_float_rows(previous["mlp_proj_weight"], bits=QUANT_BITS)
    previous_states = []
    for residual in attention_residual:
        n2 = layer_norm(residual, previous["ln2_gamma"], previous["ln2_beta"])
        hidden = gelu_new(q_fc.reconstructed @ n2 + previous["fc_bias"])
        previous_states.append(
            residual
            + q_projection.reconstructed @ hidden
            + previous["mlp_proj_bias"]
        )
    previous_states = np.asarray(previous_states)

    block = model_data(block_index=BLOCK_INDEX)
    normalized = np.stack(
        [
            layer_norm(state, block["ln1_gamma"], block["ln1_beta"])
            for state in previous_states
        ]
    )
    # model_data exposes split conveniences for one-token fixtures; read the
    # full c_attn tensors directly through the same SafeTensors-backed module.
    from analyze_full_gpt2 import MODEL_PATH, SafeTensors

    tensors = SafeTensors(MODEL_PATH)
    prefix = f"h.{BLOCK_INDEX}"
    qkv_weight = np.asarray(
        tensors.tensor(f"{prefix}.attn.c_attn.weight"), dtype=np.float64
    )
    qkv_bias = np.asarray(
        tensors.tensor(f"{prefix}.attn.c_attn.bias"), dtype=np.float64
    )
    qkv = normalized @ qkv_weight + qkv_bias
    query, key, value = np.split(qkv, 3, axis=1)
    query = query.reshape(2, HEADS, HEAD_WIDTH)
    key = key.reshape(2, HEADS, HEAD_WIDTH)
    value = value.reshape(2, HEADS, HEAD_WIDTH)
    scores = np.full((2, HEADS, 2), -np.inf)
    probabilities = np.zeros_like(scores)
    context = np.zeros((2, HEADS, HEAD_WIDTH))
    probabilities[0, :, 0] = 1
    context[0] = value[0]
    for head in range(HEADS):
        head_scores = np.asarray(
            [
                np.dot(query[1, head], key[source, head])
                / math.sqrt(HEAD_WIDTH)
                for source in range(2)
            ]
        )
        scores[1, head] = head_scores
        shifted = head_scores - np.max(head_scores)
        probabilities[1, head] = np.exp(shifted) / np.exp(shifted).sum()
        context[1, head] = sum(
            probabilities[1, head, source] * value[source, head]
            for source in range(2)
        )
    context = context.reshape(2, WIDTH)
    projection_weight = np.asarray(
        tensors.tensor(f"{prefix}.attn.c_proj.weight"), dtype=np.float64
    )
    projection_bias = np.asarray(
        tensors.tensor(f"{prefix}.attn.c_proj.bias"), dtype=np.float64
    )
    projected = context @ projection_weight + projection_bias
    residual = previous_states + projected

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "block_index": BLOCK_INDEX,
                "token_ids": [464, 3290],
                "heads": HEADS,
                "head_width": HEAD_WIDTH,
                "previous_states": previous_states.tolist(),
                "normalized": normalized.tolist(),
                "qkv": qkv.tolist(),
                "scores": scores.tolist(),
                "probabilities": probabilities.tolist(),
                "context": context.tolist(),
                "projected": projected.tolist(),
                "residual": residual.tolist(),
            }
        )
        + "\n"
    )
    print(
        {
            "block": BLOCK_INDEX,
            "path": str(OUT),
            "previous_state_range": [
                float(previous_states.min()), float(previous_states.max())
            ],
            "normalized_range": [float(normalized.min()), float(normalized.max())],
        }
    )


if __name__ == "__main__":
    main()
