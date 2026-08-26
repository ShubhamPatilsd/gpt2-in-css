#!/usr/bin/env python3
"""Add explicit lifecycle gates between selective output-head stages."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = os.environ.get(
    "GPT2_STAGED_HEAD_SOURCE",
    "gpt2-hvar-grid-output-head-cascade-near-dither7",
)
OUTPUT_NAME = os.environ.get("GPT2_STAGED_HEAD_DIR", SOURCE_NAME + "-staged")
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = (SOURCE / "index.html").read_text()
    controls = (
        '<input id="fine-stage-run" type="checkbox">'
        '<input id="near-stage-run" type="checkbox">'
        '<input id="dither-stage-run" type="checkbox">'
    )
    html = source.replace(
        '<link rel="stylesheet" href="index.css">',
        f'<link rel="stylesheet" href="../{SOURCE_NAME}/index.css">'
        '<link rel="stylesheet" href="index.css">',
        1,
    ).replace('<div class="cascade">', controls + '<div class="cascade">', 1)
    css = (
        "#fine-stage-run,#near-stage-run,#dither-stage-run{"
        "position:fixed;left:-10000px;top:0}"
        "body:not(:has(#fine-stage-run:checked)) .fine-stage,"
        "body:not(:has(#fine-stage-run:checked)) .fine-reader,"
        "body:not(:has(#near-stage-run:checked)) .near-carriers,"
        "body:not(:has(#near-stage-run:checked)) .near-reader,"
        "body:not(:has(#dither-stage-run:checked)) .dither-stage,"
        "body:not(:has(#dither-stage-run:checked)) .dither-reader{"
        "content-visibility:hidden;contain-intrinsic-size:1px}"
    )
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    print(OUTPUT / "index.html")


if __name__ == "__main__":
    main()
