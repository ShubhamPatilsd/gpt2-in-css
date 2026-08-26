#!/usr/bin/env python3
"""Build CSS-only Grid argmax scaling probes.

Each candidate width encodes a quantized score in the high bits and an inverted
token id in the low bits. All candidates occupy one max-content Grid track, so
the track width is the encoded winner. A query container decodes that width
back into the winning token id with CSS math.
"""

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "experiments" / "grid-argmax"
SIZES = (16, 256, 4096, 50_257)
TOKEN_RADIX = 65_536
LAYOUT_UNITS_PER_PX = 64


def encoded(score_bucket: int, token_id: int) -> int:
    # Inverting the id makes a tied score choose the lowest token id, matching
    # the first-index behavior of a conventional argmax.
    return score_bucket * TOKEN_RADIX + (TOKEN_RADIX - 1 - token_id)


def build_case(size: int) -> dict[str, object]:
    rng = random.Random(0xA26A + size)
    # CSS numeric calculations reliably retain a 24-bit integer here. Sixteen
    # low bits carry the GPT-2 token id, leaving eight bits for the score.
    scores_a = [rng.randrange(0, 240) for _ in range(size)]
    scores_b = [rng.randrange(0, 240) for _ in range(size)]
    winner_a = size * 5 // 11
    winner_b = size * 8 // 13
    scores_a[winner_a] = 254
    scores_b[winner_b] = 255
    codes_a = [encoded(score, token) for token, score in enumerate(scores_a)]
    codes_b = [encoded(score, token) for token, score in enumerate(scores_b)]
    return {
        "size": size,
        "winnerA": winner_a,
        "winnerB": winner_b,
        "scoreA": scores_a[winner_a],
        "scoreB": scores_b[winner_b],
        "maximumCode": max(max(codes_a), max(codes_b)),
        "candidates": list(zip(codes_a, codes_b, strict=True)),
    }


def render(case: dict[str, object]) -> str:
    candidates = "".join(
        f'<i class="candidate" style="--a:{a};--d:{b - a}"></i>'
        for a, b in case["candidates"]
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Grid argmax {case['size']}</title>
<style>
@property --mode {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --encoded {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --tie {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --winner {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --score {{ syntax:"<number>"; inherits:true; initial-value:0 }}
* {{ box-sizing:border-box }}
html,body {{ margin:0; overflow:clip }}
.bank {{
  --mode:0;
  position:fixed;
  inset:0 auto auto 0;
  display:grid;
  grid-template-columns:max-content;
  grid-template-rows:1px;
  width:max-content;
  height:1px;
  anchor-name:--argmax-bank;
}}
.candidate {{ grid-area:1/1; height:1px }}
.candidate {{
  display:block;
  justify-self:start;
  width:calc((var(--a) + var(--mode) * var(--d)) / {LAYOUT_UNITS_PER_PX} * 1px);
}}
.reader {{
  position:fixed;
  position-anchor:--argmax-bank;
  inset:2px auto auto 0;
  width:anchor-size(--argmax-bank width);
  height:1px;
  container:argmax/inline-size;
}}
@container argmax (width >= 0px) {{
  .result {{
    --encoded:round(nearest, 100cqi / 1px * {LAYOUT_UNITS_PER_PX}, 1);
    --tie:round(nearest, mod(100cqi, {TOKEN_RADIX // LAYOUT_UNITS_PER_PX}px) / 1px * {LAYOUT_UNITS_PER_PX}, 1);
    --winner:calc({TOKEN_RADIX - 1} - var(--tie));
    --score:round(down, 100cqi / {TOKEN_RADIX // LAYOUT_UNITS_PER_PX}px, 1);
    display:block;
    width:calc(var(--winner) * 1px);
    height:calc(var(--score) * 1px);
  }}
}}
</style>
<main id="bank" class="bank">{candidates}</main>
<div class="reader"><output id="result" class="result"></output></div>
"""


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for size in SIZES:
        case = build_case(size)
        output_dir = OUTPUT_ROOT / str(size)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text(render(case))
        reference = {key: value for key, value in case.items() if key != "candidates"}
        (output_dir / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
        manifest.append(reference)
    (OUTPUT_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built Grid argmax probes for: {', '.join(map(str, SIZES))}")


if __name__ == "__main__":
    main()
