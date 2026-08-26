#!/usr/bin/env python3
"""Add a manually committed lifecycle boundary between two live HVAR blocks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE_STEM = (
    "view-timeline-two-block-full-exact-b0-global-projection-"
    "fc-easing-gelu-s513-projection-easing-s257-global-projection"
)
OUTPUT_STEM = SOURCE_STEM + "-manual-stage-boundary"


def main() -> None:
    source = (OUT / f"{SOURCE_STEM}.html").read_text()
    if source.count('<div class="b1-norm">') != 1:
        raise RuntimeError("expected exactly one block-1 boundary")
    css = (
        "#b1-stage-run{position:fixed;left:-10000px;top:0}"
        "html:not(:has(#b1-stage-run:checked)) .b1-norm{"
        "content-visibility:hidden;contain-intrinsic-size:1px}"
    )
    html = source.replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{OUTPUT_STEM}.css">',
        1,
    ).replace(
        "<css-stage ",
        '<input id="b1-stage-run" type="checkbox"><css-stage ',
        1,
    )
    (OUT / f"{OUTPUT_STEM}.css").write_text(css)
    (OUT / f"{OUTPUT_STEM}.html").write_text(html)
    print(OUT / f"{OUTPUT_STEM}.html")


if __name__ == "__main__":
    main()
