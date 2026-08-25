#!/usr/bin/env python3
"""Compare the generated GSUB tokenizer fonts with the Python GPT-2 tokenizer."""

from __future__ import annotations

import argparse
import random
import re
import string
import subprocess
from pathlib import Path

from build_metric_tokenizer_font import EMBEDDING_OFFSET, EMBEDDING_SCALE
from build_pretrained_gpt2 import CHECKPOINT_DIR, Gpt2Tokenizer, load_torch_legacy


ROOT = Path(__file__).resolve().parents[1]
ADVANCE = re.compile(r"\+(-?\d+)")


def shaped_advance(font: Path, feature: str, text: str) -> int:
    result = subprocess.run(
        ["hb-shape", f"--features={feature}", str(font), text],
        check=True,
        capture_output=True,
        text=True,
    )
    return sum(map(int, ADVANCE.findall(result.stdout)))


def encoded_embedding(value: float) -> int:
    return round((value + EMBEDDING_OFFSET) * EMBEDDING_SCALE) + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-dir", type=Path, default=ROOT / "experiments")
    parser.add_argument("--random", type=int, default=32)
    args = parser.parse_args()

    tokenizer = Gpt2Tokenizer(
        CHECKPOINT_DIR / "vocab.json", CHECKPOINT_DIR / "merges.txt"
    )
    embeddings = load_torch_legacy(CHECKPOINT_DIR / "pytorch_model.bin")[
        "transformer.wte.weight"
    ]
    fonts = [
        args.font_dir / f"gpt2-embedding-{dimension}-full.ttf"
        for dimension in range(2)
    ]
    rng = random.Random(20260825)
    alphabet = string.ascii_letters + string.digits + " .,!?;:'-_/()"
    prompts = [
        "Hello world!",
        "CSS is computing",
        "The dog",
        "A quick brown fox",
        "Once upon a time",
    ]
    prompts.extend(
        "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 48)))
        for _ in range(args.random)
    )

    checks = 0
    for prompt in prompts:
        token_ids = tokenizer.encode(prompt)
        for position in range(4):
            for dimension, font in enumerate(fonts):
                actual = shaped_advance(font, f"p{position:03d}", prompt)
                expected = (
                    encoded_embedding(float(embeddings[token_ids[position], dimension]))
                    if position < len(token_ids)
                    else 0
                )
                if actual != expected:
                    raise AssertionError(
                        f"{prompt=!r} {token_ids=} {position=} {dimension=}: "
                        f"expected advance {expected}, got {actual}"
                    )
                checks += 1
    print(f"ok: {checks} font/tokenizer comparisons across {len(prompts)} prompts")


if __name__ == "__main__":
    main()
