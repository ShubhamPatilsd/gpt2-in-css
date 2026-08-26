#!/usr/bin/env python3
"""Add dependency-driven SMIL/:has staging to the four-block probe."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-four-block-event-scheduler"
CONNECTED = OUT / "view-timeline-four-block-connected.html"
STAGED = OUT / "view-timeline-four-block-staged.html"
STAGED_CSS = OUT / "view-timeline-four-block-staged.css"
MANIFEST = OUT / "view-timeline-four-block-event-scheduler-manifest.json"


def body(source: str) -> str:
    match = re.search(r"(<svg id=\"four-block-smil-scheduler\".*)", source)
    if not match:
        raise ValueError("four-block SMIL scheduler was not found")
    return match.group(1)


def main() -> None:
    source = CONNECTED.read_text()
    for layer in (1, 2, 3):
        if source.count(f'id="four-block-signal-b{layer}"') != 1:
            raise ValueError(f"missing unique dependency signal for block {layer}")
        if source.count(f'data-four-block-stage="b{layer}"') != 1:
            raise ValueError(f"missing unique computation subtree for block {layer}")

    css = (
        "/* Dependency-driven staging for the one-token/truncated diagnostic. */"
        "html:not(:has(#four-block-signal-b1.ready)) .b1-norm,"
        "html:not(:has(#four-block-signal-b2.ready)) .b2-norm,"
        "html:not(:has(#four-block-signal-b3.ready)) .b3-norm{"
        "display:none;content-visibility:hidden;contain-intrinsic-size:1px}"
    )
    STAGED_CSS.write_text(css)
    tag = hashlib.sha256(STAGED_CSS.read_bytes()).hexdigest()[:12]
    staged = source.replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{STAGED_CSS.name}?v={tag}">',
        1,
    )
    if body(source) != body(staged):
        raise ValueError("connected and staged computation bodies diverged")
    if "<script" in staged.lower() or "javascript:" in staged.lower():
        raise ValueError("runtime fixture must remain HTML/CSS/SMIL-only")
    STAGED.write_text(staged)

    report = {
        "diagnostic": "one-token/truncated four-block diagnostic, not full GPT-2 inference",
        "connected": CONNECTED.name,
        "staged": STAGED.name,
        "staged_stylesheet": STAGED_CSS.name,
        "computation_body_sha256": hashlib.sha256(body(source).encode()).hexdigest(),
        "identical_computation_body": True,
        "dependency_chain": [
            "h.0 animationend -> b1 signal -> h.1",
            "h.1 animationend -> b2 signal -> h.2",
            "h.2 animationend -> b3 signal -> h.3",
        ],
        "gate": "SMIL class mutation observed by CSS :has()",
        "handoff": "nested direct inheritance; zero sibling values",
        "runtime_javascript": False,
        "files": {
            STAGED.name: STAGED.stat().st_size,
            STAGED_CSS.name: STAGED_CSS.stat().st_size,
        },
    }
    MANIFEST.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
