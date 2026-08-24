#!/usr/bin/env python3
"""Run GPT-2 small for one token and estimate an equivalent CSS circuit."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

from build_pretrained_gpt2 import Gpt2Tokenizer, css_number, gelu_new, layer_norm


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_DIR = ROOT / "data" / "gpt2"
MODEL_PATH = CHECKPOINT_DIR / "model.safetensors"


class SafeTensors:
    def __init__(self, path: Path) -> None:
        self.path = path
        with path.open("rb") as file:
            header_size = struct.unpack("<Q", file.read(8))[0]
            self.header = json.loads(file.read(header_size))
        self.data_offset = 8 + header_size

    def tensor(self, name: str) -> np.ndarray:
        metadata = self.header[name]
        if metadata["dtype"] != "F32":
            raise ValueError(f"unsupported dtype for {name}: {metadata['dtype']}")
        start, _end = metadata["data_offsets"]
        return np.memmap(
            self.path,
            dtype="<f4",
            mode="r",
            offset=self.data_offset + start,
            shape=tuple(metadata["shape"]),
        )


def forward_one_token(token_id: int, tensors: SafeTensors) -> np.ndarray:
    x = np.asarray(
        tensors.tensor("wte.weight")[token_id] + tensors.tensor("wpe.weight")[0],
        dtype=np.float32,
    )
    for layer in range(12):
        prefix = f"h.{layer}"
        normalized = layer_norm(
            x,
            tensors.tensor(f"{prefix}.ln_1.weight"),
            tensors.tensor(f"{prefix}.ln_1.bias"),
        )
        qkv = (
            normalized @ tensors.tensor(f"{prefix}.attn.c_attn.weight")
            + tensors.tensor(f"{prefix}.attn.c_attn.bias")
        )
        value = qkv[1536:]
        x = (
            x
            + value @ tensors.tensor(f"{prefix}.attn.c_proj.weight")
            + tensors.tensor(f"{prefix}.attn.c_proj.bias")
        )
        normalized = layer_norm(
            x,
            tensors.tensor(f"{prefix}.ln_2.weight"),
            tensors.tensor(f"{prefix}.ln_2.bias"),
        )
        hidden = gelu_new(
            normalized @ tensors.tensor(f"{prefix}.mlp.c_fc.weight")
            + tensors.tensor(f"{prefix}.mlp.c_fc.bias")
        )
        x = (
            x
            + hidden @ tensors.tensor(f"{prefix}.mlp.c_proj.weight")
            + tensors.tensor(f"{prefix}.mlp.c_proj.bias")
        )
    final = layer_norm(
        x, tensors.tensor("ln_f.weight"), tensors.tensor("ln_f.bias")
    )
    return tensors.tensor("wte.weight") @ final


def main() -> None:
    tensors = SafeTensors(MODEL_PATH)
    tokenizer = Gpt2Tokenizer(
        CHECKPOINT_DIR / "vocab.json", CHECKPOINT_DIR / "merges.txt"
    )
    prompt = "Hello"
    encoded = tokenizer.encode(prompt)
    if len(encoded) != 1:
        raise ValueError(f"expected a one-token prompt, received {encoded}")
    logits = forward_one_token(encoded[0], tensors)
    winner = int(logits.argmax())

    d_model = 768
    d_ff = 3072
    vocabulary = 50257
    layers = 12
    matrix_macs_per_layer = (
        d_model * (3 * d_model)
        + d_model * d_model
        + d_model * d_ff
        + d_ff * d_model
    )
    attention_macs_per_layer = 2 * d_model  # score and value at context length 1
    transformer_macs = layers * (matrix_macs_per_layer + attention_macs_per_layer)
    language_head_macs = vocabulary * d_model
    total_macs = transformer_macs + language_head_macs

    sample_weights = np.concatenate(
        [
            np.asarray(tensors.tensor("h.0.attn.c_attn.weight")).reshape(-1)[::4096],
            np.asarray(tensors.tensor("wte.weight")).reshape(-1)[::4096],
        ]
    )
    numeric_bytes = np.mean([len(css_number(value)) for value in sample_weights])
    compact_term_bytes = numeric_bytes + 14  # v(--xN)* plus operator spacing
    readable_term_bytes = numeric_bytes + 38  # var(--descriptive-name)* plus spacing
    property_count = 480_000
    registration_bytes = property_count * 82
    compact_css_bytes = total_macs * compact_term_bytes + registration_bytes
    readable_css_bytes = total_macs * readable_term_bytes + registration_bytes

    print(f"checkpoint: openai-community/gpt2 (124M)")
    print(f"prompt: {prompt!r} -> token {winner} {tokenizer.decode_token(winner)!r}")
    print(f"transformer MACs: {transformer_macs:,}")
    print(f"language-head MACs: {language_head_macs:,}")
    print(f"total CSS MAC terms: {total_macs:,}")
    print(f"estimated typed properties: {property_count:,}")
    print(f"mean serialized weight length: {numeric_bytes:.2f} bytes")
    print(f"compact CSS estimate: {compact_css_bytes / 1e9:.2f} GB")
    print(f"readable CSS estimate: {readable_css_bytes / 1e9:.2f} GB")
    print(
        "estimated browser working set (2x-5x source): "
        f"{2 * compact_css_bytes / 1e9:.1f}-"
        f"{5 * readable_css_bytes / 1e9:.1f} GB"
    )


if __name__ == "__main__":
    main()

