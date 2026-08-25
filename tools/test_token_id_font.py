#!/usr/bin/env python3
"""Check that the no-script tokenizer font emits GPT-2 token IDs."""

from __future__ import annotations

import argparse
import random
import string
from pathlib import Path

from build_metric_tokenizer_font import TOKEN_ID_BASE, UNITS_PER_EM
from build_pretrained_gpt2 import CHECKPOINT_DIR, Gpt2Tokenizer
from test_metric_tokenizer_font import shaped_advance


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-dir", type=Path, default=ROOT / "tinystories")
    parser.add_argument("--positions", type=int, default=4)
    parser.add_argument("--random", type=int, default=32)
    arguments = parser.parse_args()
    tokenizer = Gpt2Tokenizer(
        CHECKPOINT_DIR / "vocab.json", CHECKPOINT_DIR / "merges.txt"
    )
    fonts = [
        arguments.font_dir / f"gpt2-token-id-{part}-full.ttf"
        for part in range(2)
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
        for _ in range(arguments.random)
    )
    checks = 0
    for prompt in prompts:
        token_ids = tokenizer.encode(prompt)
        for position in range(arguments.positions):
            advances = [
                shaped_advance(font, f"p{position:03d}", prompt)
                for font in fonts
            ]
            actual = (
                advances[0] - 1 + TOKEN_ID_BASE * (advances[1] - 1)
                if all(advances)
                else None
            )
            expected = token_ids[position] if position < len(token_ids) else None
            if actual != expected:
                raise AssertionError(
                    f"{prompt=!r} {token_ids=} {position=}: "
                    f"expected token {expected}, got {actual} from {advances}"
                )
            checks += 1
    print(
        f"ok: {checks} token-ID font comparisons across {len(prompts)} prompts "
        f"at {UNITS_PER_EM} units/em"
    )


if __name__ == "__main__":
    main()
