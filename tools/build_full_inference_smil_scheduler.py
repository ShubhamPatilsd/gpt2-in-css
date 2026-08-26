#!/usr/bin/env python3
"""Build automatic SMIL/:has staging for two blocks plus selective GPT-2 head."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE_STEM = "view-timeline-two-block-with-selective-gpt2-output-head"
HEAD_DELAYS = (2.0, 3.0, 4.0, 5.0)
B1_DELAY = 0.25
BOUNDARY = '<div class="b1-norm">'
HEAD_INPUT = '<input id="selective-head-run" type="checkbox">'
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
    raise RuntimeError("could not find the end of block 1")


def main() -> None:
    source = (OUT / f"{SOURCE_STEM}.html").read_text()
    if source.count(BOUNDARY) != 1 or source.count(HEAD_INPUT) != 1:
        raise RuntimeError("unexpected source boundaries")
    connected_stem = SOURCE_STEM + "-connected-control"
    connected = source.replace(HEAD_INPUT, HEAD_INPUT[:-1] + " checked>", 1)
    (OUT / f"{connected_stem}.html").write_text(connected)

    start = source.index(BOUNDARY)
    end = matching_div_end(source, start)
    fixtures = [{
        "name": "connected-control",
        "stem": connected_stem,
        "b1DelaySeconds": None,
        "headDelaySeconds": None,
    }]
    for head_delay in HEAD_DELAYS:
        suffix = f"head-{head_delay:g}s"
        stem = f"{SOURCE_STEM}-smil-{suffix}"
        stylesheet = f"{stem}.css"
        css = (
            "#inference-smil-scheduler{position:fixed;left:-10000px;top:0;width:1px;height:1px}"
            "html:not(:has(#b1-smil-signal.ready)) .b1-norm{display:none}"
            "html:not(:has(#head-smil-signal.ready)) .selective-head-gate{"
            "content-visibility:hidden;contain-intrinsic-size:1px}"
        )
        signal = (
            '<svg id="inference-smil-scheduler" xmlns="http://www.w3.org/2000/svg">'
            '<g id="b1-smil-signal"><set id="b1-smil-open" attributeName="class" '
            f'to="ready" begin="inference-smil-scheduler.load+{B1_DELAY:g}s" '
            'fill="freeze" /></g>'
            '<g id="head-smil-signal"><set attributeName="class" to="ready" '
            f'begin="b1-smil-open.begin+{head_delay:g}s" fill="freeze" /></g></svg>'
        )
        html = source.replace(HEAD_INPUT, HEAD_INPUT[:-1] + " checked>", 1)
        # Locate the boundary again after adding `checked`, then append both
        # timers outside the subtree whose display they control.
        staged_start = html.index(BOUNDARY)
        staged_end = matching_div_end(html, staged_start)
        html = html[:staged_end] + signal + html[staged_end:]
        html = html.replace(
            "</title>", f'</title><link rel="stylesheet" href="{stylesheet}">', 1
        )
        if html.lower().count("<script"):
            raise RuntimeError("runtime fixture unexpectedly contains JavaScript")
        (OUT / stylesheet).write_text(css)
        (OUT / f"{stem}.html").write_text(html)
        fixtures.append({
            "name": suffix,
            "stem": stem,
            "b1DelaySeconds": B1_DELAY,
            "headDelaySeconds": head_delay,
        })
    manifest = {"sourceStem": SOURCE_STEM, "fixtures": fixtures}
    (OUT / "full-inference-smil-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
