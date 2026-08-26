#!/usr/bin/env python3
"""Wrap block 1 of the exact two-block fixture in an SVG SMIL display gate."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE_STEM = (
    "view-timeline-two-block-full-exact-b0-global-projection-"
    "fc-easing-gelu-s513-projection-easing-s257-global-projection"
)
VARIANTS = {
    "foreignobject-connected": None,
    "smil-svg-load-50ms": 0.05,
    "smil-svg-load-250ms": 0.25,
    "smil-svg-load-1000ms": 1.0,
    "smil-svg-load-2000ms": 2.0,
}
BOUNDARY = '<div class="b1-norm">'
DIV = re.compile(r"<div\b[^>]*>|</div\s*>", re.IGNORECASE)


def matching_div_end(source: str, start: int) -> int:
    depth = 0
    for match in DIV.finditer(source, start):
        if match.group(0).lower().startswith("</div"):
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1
    raise RuntimeError("could not find the end of the block-1 subtree")


def wrap(source: str, delay: float | None) -> str:
    if source.count(BOUNDARY) != 1:
        raise RuntimeError("expected exactly one block-1 boundary")
    start = source.index(BOUNDARY)
    end = matching_div_end(source, start)
    display = "inline" if delay is None else "none"
    scheduler = ""
    if delay is not None:
        scheduler = (
            '<set href="#b1-smil-gate" attributeName="display" to="inline" '
            f'begin="b1-smil-scheduler.load+{delay:g}s" fill="freeze" />'
        )
    prefix = (
        '<svg id="b1-smil-scheduler" xmlns="http://www.w3.org/2000/svg" '
        'width="1" height="1" overflow="visible">'
        f'<g id="b1-smil-gate" display="{display}">'
        '<foreignObject x="0" y="0" width="1" height="1" overflow="visible">'
        '<div xmlns="http://www.w3.org/1999/xhtml" class="b1-smil-html">'
    )
    suffix = f"</div></foreignObject></g>{scheduler}</svg>"
    return source[:start] + prefix + source[start:end] + suffix + source[end:]


def main() -> None:
    source = (OUT / f"{SOURCE_STEM}.html").read_text()
    fixtures = []
    for name, delay in VARIANTS.items():
        stem = f"{SOURCE_STEM}-{name}"
        html = wrap(source, delay)
        if html.lower().count("<script"):
            raise RuntimeError("runtime fixture unexpectedly contains JavaScript")
        (OUT / f"{stem}.html").write_text(html)
        fixtures.append({"name": name, "stem": stem, "delaySeconds": delay})
    manifest = {"sourceStem": SOURCE_STEM, "fixtures": fixtures}
    (OUT / "two-block-smil-stage-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
