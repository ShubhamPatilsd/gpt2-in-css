#!/usr/bin/env python3
"""Calibrate and apply block-0 output packing ranges on multi-token attention states."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_geometry_streaming_attention import TOKENS, softmax
from build_gpt2_block_css import QUANT_BITS, WIDTH, gelu_new, layer_norm
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "multitoken-block0-ranges"
CSS_DIR = ROOT / "experiments" / "gpt2-block-css"
SOURCE_CSS = CSS_DIR / "view-timeline-block-hybrid-packed4-chain-channel89-h15.css"
OUTPUT_CSS = CSS_DIR / "view-timeline-block-hybrid-packed4-chain-multitoken.css"
LENGTHS = (2, 4, 8, 16, 32)
CALIBRATION_PER_LENGTH = 48
EVALUATION_PER_LENGTH = 24
HEADROOM = 1.5
HEADS = 12
HEAD_WIDTH = WIDTH // HEADS


def block0_states(sequences: list[np.ndarray]) -> np.ndarray:
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    positions = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    ln1_gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    ln1_beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    qkv_weight = quantize_float_rows(
        np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T,
        bits=QUANT_BITS,
    ).reconstructed
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    attn_weight = quantize_float_rows(
        np.asarray(tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64).T,
        bits=QUANT_BITS,
    ).reconstructed
    attn_bias = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    ln2_gamma = np.asarray(tensors.tensor("h.0.ln_2.weight"), dtype=np.float64)
    ln2_beta = np.asarray(tensors.tensor("h.0.ln_2.bias"), dtype=np.float64)
    fc_weight = quantize_float_rows(
        np.asarray(tensors.tensor("h.0.mlp.c_fc.weight"), dtype=np.float64).T,
        bits=QUANT_BITS,
    ).reconstructed
    fc_bias = np.asarray(tensors.tensor("h.0.mlp.c_fc.bias"), dtype=np.float64)
    projection_weight = quantize_float_rows(
        np.asarray(tensors.tensor("h.0.mlp.c_proj.weight"), dtype=np.float64).T,
        bits=QUANT_BITS,
    ).reconstructed
    projection_bias = np.asarray(tensors.tensor("h.0.mlp.c_proj.bias"), dtype=np.float64)
    results = []
    for tokens in sequences:
        states = embeddings[tokens] + positions[: len(tokens)]
        normalized = np.stack([layer_norm(row, ln1_gamma, ln1_beta) for row in states])
        qkv = normalized @ qkv_weight.T + qkv_bias
        query = qkv[-1, :WIDTH].reshape(HEADS, HEAD_WIDTH)
        keys = qkv[:, WIDTH:2 * WIDTH].reshape(len(tokens), HEADS, HEAD_WIDTH)
        values = qkv[:, 2 * WIDTH:].reshape(len(tokens), HEADS, HEAD_WIDTH)
        scores = np.einsum("hd,shd->hs", query, keys) / math.sqrt(HEAD_WIDTH)
        context = np.einsum("hs,shd->hd", softmax(scores), values).reshape(WIDTH)
        residual = states[-1] + attn_weight @ context + attn_bias
        normalized2 = layer_norm(residual, ln2_gamma, ln2_beta)
        hidden = gelu_new(fc_weight @ normalized2 + fc_bias)
        results.append(residual + projection_weight @ hidden + projection_bias)
    return np.stack(results)


def make_sequences(rng: np.random.Generator, count_per_length: int) -> list[np.ndarray]:
    sequences = [
        rng.integers(0, 50257, size=length, dtype=np.int64)
        for length in LENGTHS
        for _ in range(count_per_length)
    ]
    sequences.extend(np.asarray(TOKENS[:length], dtype=np.int64) for length in LENGTHS)
    return sequences


def patch_css(bounds: np.ndarray) -> tuple[int, int]:
    css = SOURCE_CSS.read_text()
    encode_count = 0
    decode_count = 0
    for output, bound in enumerate(bounds):
        marker = f".qod-{output:03d}{{"
        start = css.find(marker)
        stop = css.find("}", start)
        if start < 0 or stop < 0:
            raise ValueError(f"missing output encoder {output}")
        segment = css[start:stop]
        replaced, count = re.subn(
            r"(clamp\(-1,\(size / 1px - 256\) / )[-+.0-9eE]+(,1\) \+ 1\))",
            rf"\g<1>{bound:.12g}\g<2>",
            segment,
            count=1,
        )
        if count != 1:
            raise ValueError(f"failed to patch output encoder {output}")
        css = css[:start] + replaced + css[stop:]
        encode_count += count

        marker = f"--out-{output:03d}:calc("
        start = css.find(marker)
        if start < 0:
            raise ValueError(f"missing output decoder {output}")
        semicolon = css.find(";", start)
        brace = css.find("}", start)
        stop = min(value for value in (semicolon, brace) if value >= 0)
        segment = css[start:stop]
        replaced, count = re.subn(
            r"(\) \* )[-+.0-9eE]+(\))$",
            rf"\g<1>{bound:.12g}\g<2>",
            segment,
            count=1,
        )
        if count != 1:
            raise ValueError(f"failed to patch output decoder {output}")
        css = css[:start] + replaced + css[stop:]
        decode_count += count
    OUTPUT_CSS.write_text(css)
    return encode_count, decode_count


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    calibration = block0_states(make_sequences(
        np.random.default_rng(0x4B564341), CALIBRATION_PER_LENGTH
    ))
    evaluation = block0_states(make_sequences(
        np.random.default_rng(0x4B564542), EVALUATION_PER_LENGTH
    ))
    bounds = np.maximum(np.max(np.abs(calibration), axis=0) * HEADROOM, 0.5)
    clipped = np.abs(evaluation) > bounds
    encode_count, decode_count = patch_css(bounds)
    report = {
        "sequenceLengths": LENGTHS,
        "calibrationSequences": len(calibration),
        "evaluationSequences": len(evaluation),
        "headroom": HEADROOM,
        "bounds": bounds.tolist(),
        "minimumBound": float(np.min(bounds)),
        "maximumBound": float(np.max(bounds)),
        "evaluationClippedFraction": float(np.mean(clipped)),
        "evaluationSequencesWithAnyClip": int(np.count_nonzero(np.any(clipped, axis=1))),
        "patchedEncoders": encode_count,
        "patchedDecoders": decode_count,
        "sourceCss": SOURCE_CSS.name,
        "outputCss": OUTPUT_CSS.name,
    }
    (OUT / "reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print({
        "calibration": len(calibration),
        "evaluation": len(evaluation),
        "minimumBound": report["minimumBound"],
        "maximumBound": report["maximumBound"],
        "clippedFraction": report["evaluationClippedFraction"],
        "sequencesWithClip": report["evaluationSequencesWithAnyClip"],
    })


if __name__ == "__main__":
    main()
