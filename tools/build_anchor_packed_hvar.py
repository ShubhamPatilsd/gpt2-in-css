#!/usr/bin/env python3
"""Build an HVAR -> anchor-size pack -> additive-vector transport probe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "anchor-packed-hvar"
LEVELS = 63
CASES = np.array(
    [[17, 31, 20, 33], [58, 43, 30, 35]],
    dtype=np.int16,
)


def settings(codes: np.ndarray) -> str:
    return ",".join(
        f'"X{index:03d}" {int(code) / LEVELS:.12g}'
        for index, code in enumerate(codes)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights = np.eye(4, dtype=np.int16) * LEVELS
    build_direct_font_backend(weights, OUT / "matrix.ttf", base_advance=64)
    source_markup = "".join(
        f'<i class="source s{index}">&#x{0xE000 + index:x};</i>'
        for index in range(4)
    )
    (OUT / "index.html").write_text(
        "<!doctype html><meta charset=\"utf-8\">"
        "<title>Packed real-HVAR vector probe</title>"
        "<link rel=\"stylesheet\" href=\"style.css\">"
        f'<div id="scope">{source_markup}'
        '<div id="packed"><output id="result">result</output></div></div>'
    )
    (OUT / "style.css").write_text(f'''@font-face {{
  font-family: Matrix;
  src: url("matrix.woff2") format("woff2");
}}
@property --zero {{
  syntax: "*";
  inherits: true;
  initial-value: "A000" 0, "A001" 0, "A002" 0, "A003" 0;
}}
@keyframes c0 {{ from {{ font-variation-settings: var(--zero) }} to {{ font-variation-settings: "A000" 1, "A001" 0, "A002" 0, "A003" 0 }} }}
@keyframes c1 {{ from {{ font-variation-settings: var(--zero) }} to {{ font-variation-settings: "A000" 0, "A001" 1, "A002" 0, "A003" 0 }} }}
@keyframes c2 {{ from {{ font-variation-settings: var(--zero) }} to {{ font-variation-settings: "A000" 0, "A001" 0, "A002" 1, "A003" 0 }} }}
@keyframes c3 {{ from {{ font-variation-settings: var(--zero) }} to {{ font-variation-settings: "A000" 0, "A001" 0, "A002" 0, "A003" 1 }} }}
#scope {{
  position: relative;
  font-variation-settings: {settings(CASES[0])};
}}
.source {{
  position: absolute;
  display: inline-block;
  width: max-content;
  height: 1px;
  overflow: hidden;
  white-space: pre;
  font-family: Matrix;
  font-size: 1000px;
  font-kerning: none;
}}
.s0 {{ anchor-name: --a0 }}
.s1 {{ anchor-name: --a1 }}
.s2 {{ anchor-name: --a2 }}
.s3 {{ anchor-name: --a3 }}
#packed {{
  position: absolute;
  position-anchor: --a0;
  container-type: inline-size;
  height: 1px;
  width: calc(
    round(nearest, anchor-size(--a0 width) - 64px, 1px)
    + 64 * round(nearest, anchor-size(--a1 width) - 64px, 1px)
    + 4096 * round(nearest, anchor-size(--a2 width) - 64px, 1px)
    + 262144 * round(nearest, anchor-size(--a3 width) - 64px, 1px)
  );
}}
#result {{
  position: absolute;
  animation-name: c0, c1, c2, c3;
  animation-duration: 1s;
  animation-delay:
    calc(-1s * mod(round(nearest, 100cqi / 1px, 1), 64) / 63),
    calc(-1s * mod(round(down, 100cqi / 1px / 64, 1), 64) / 63),
    calc(-1s * mod(round(down, 100cqi / 1px / 4096, 1), 64) / 63),
    calc(-1s * round(down, 100cqi / 1px / 262144, 1) / 63);
  animation-play-state: paused;
  animation-timing-function: linear;
  animation-fill-mode: both;
  animation-composition: add;
}}
''')
    (OUT / "reference.json").write_text(json.dumps({
        "codes": CASES.tolist(),
        "settings": [settings(row) for row in CASES],
        "vectors": (CASES / LEVELS).tolist(),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
