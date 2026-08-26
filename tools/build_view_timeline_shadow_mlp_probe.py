#!/usr/bin/env python3
"""Wrap block 1's MLP in declarative Shadow DOM for lifecycle isolation."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE = OUT / (
    "view-timeline-two-block-full-exact-b0-global-projection-"
    "fc-easing-gelu-s513-projection-easing-s257-global-projection.html"
)
OUTPUT = OUT / "view-timeline-two-block-shadow-mlp.html"
REFERENCE = OUT / "view-timeline-two-block-shadow-mlp-reference.json"
MLP_START = '<div class="b1-ln2">'
LEAF = (
    '<output id="two-block-full" class="b1proj-result-5">'
    "two complete blocks</output>"
)


def balanced_div(source: str, start: int) -> str:
    depth = 0
    for match in re.finditer(r"<div\b[^>]*>|</div>", source[start:], re.I):
        depth += -1 if match.group(0).startswith("</") else 1
        if depth == 0:
            return source[start : start + match.end()]
    raise ValueError("unterminated MLP stage")


def main() -> None:
    source = SOURCE.read_text()
    mlp_offset = source.index(MLP_START)
    mlp = balanced_div(source, mlp_offset)
    if mlp.count(LEAF) != 1:
        raise ValueError("MLP output leaf was not found exactly once")
    if not mlp.startswith(MLP_START) or not mlp.endswith("</div>"):
        raise ValueError("unexpected MLP wrapper")

    linked_css = re.findall(r'<link rel="stylesheet" href="([^"]+)', source)
    full_css = next(
        href for href in linked_css
        if "two-block-full" in href
    )
    shadow_inner = mlp[len(MLP_START) : -len("</div>")].replace(
        LEAF,
        '<slot name="b1-mlp-next" class="b1proj-result-5"></slot>',
        1,
    )
    replacement = (
        '<css-mlp class="b1-ln2" style="display:block">'
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{full_css}">'
        f"{shadow_inner}</template>"
        '<output id="two-block-full" slot="b1-mlp-next">'
        "two complete blocks</output></css-mlp>"
    )
    page = source.replace(mlp, replacement, 1).replace(
        "</title>", " — shadow MLP isolation</title>", 1
    )
    if page.count("shadowrootmode=\"open\"") < 2:
        raise ValueError("expected attention and MLP declarative shadow roots")
    if "<script" in page.lower() or "javascript:" in page.lower():
        raise ValueError("runtime fixture must remain HTML/CSS-only")
    OUTPUT.write_text(page)
    REFERENCE.write_text(
        json.dumps(
            {
                "source": SOURCE.name,
                "shadow_boundary": "block-1-mlp",
                "html_bytes": OUTPUT.stat().st_size,
                "runtime_javascript": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.loads(REFERENCE.read_text()))


if __name__ == "__main__":
    main()
