#!/usr/bin/env python3
"""Stage block 1 through an SVG SMIL class signal observed by HTML :has()."""

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
VARIANTS = (
    ("display-50ms", "display", 0.05),
    ("display-250ms", "display", 0.25),
    ("display-1000ms", "display", 1.0),
    ("display-2000ms", "display", 2.0),
    ("content-250ms", "content", 0.25),
    ("content-1000ms", "content", 1.0),
)
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
    raise RuntimeError("could not find the end of block 1")


def main() -> None:
    source = (OUT / f"{SOURCE_STEM}.html").read_text()
    if source.count(BOUNDARY) != 1:
        raise RuntimeError("expected exactly one block-1 boundary")
    start = source.index(BOUNDARY)
    end = matching_div_end(source, start)
    fixtures = []
    for name, gate, delay in VARIANTS:
        stem = f"{SOURCE_STEM}-smil-selector-{name}"
        stylesheet = f"{stem}.css"
        if gate == "display":
            hidden = "display:none"
        else:
            hidden = "content-visibility:hidden;contain-intrinsic-size:1px"
        css = (
            "#b1-smil-scheduler{position:fixed;left:-10000px;top:0;width:1px;height:1px}"
            "html:not(:has(#b1-smil-signal.ready)) .b1-norm{" + hidden + "}"
        )
        signal = (
            '<svg id="b1-smil-scheduler" xmlns="http://www.w3.org/2000/svg">'
            '<g id="b1-smil-signal">'
            '<set attributeName="class" to="ready" '
            f'begin="b1-smil-scheduler.load+{delay:g}s" fill="freeze" />'
            "</g></svg>"
        )
        html = source[:end] + signal + source[end:]
        html = html.replace(
            "</title>", f'</title><link rel="stylesheet" href="{stylesheet}">', 1
        )
        if html.lower().count("<script"):
            raise RuntimeError("runtime fixture unexpectedly contains JavaScript")
        (OUT / stylesheet).write_text(css)
        (OUT / f"{stem}.html").write_text(html)
        fixtures.append({
            "name": name,
            "stem": stem,
            "gate": gate,
            "delaySeconds": delay,
        })
    event_name = "view-timeline-event-50ms"
    event_stem = f"{SOURCE_STEM}-smil-selector-{event_name}"
    event_stylesheet = f"{event_stem}.css"
    event_css = (
        "@keyframes b0-scheduler-ready{from{opacity:.99}to{opacity:1}}"
        "#b1-smil-scheduler{position:fixed;left:-10000px;top:0;width:1px;height:1px}"
        "#b0-css-ready{animation:b0-scheduler-ready 1s linear both;"
        "animation-timeline:--ot767;animation-range:cover}"
        "html:not(:has(#b1-smil-signal.ready)) .b1-norm{display:none}"
    )
    event_signal = (
        '<svg id="b1-smil-scheduler" xmlns="http://www.w3.org/2000/svg">'
        '<g id="b0-css-ready"></g><g id="b1-smil-signal">'
        '<set attributeName="class" to="ready" '
        'begin="b0-css-ready.animationend+0.05s" fill="freeze" /></g></svg>'
    )
    event_html = source[:start] + event_signal + source[start:]
    event_html = event_html.replace(
        "</title>",
        f'</title><link rel="stylesheet" href="{event_stylesheet}">',
        1,
    )
    (OUT / event_stylesheet).write_text(event_css)
    (OUT / f"{event_stem}.html").write_text(event_html)
    fixtures.append({
        "name": event_name,
        "stem": event_stem,
        "gate": "display",
        "delaySeconds": None,
        "trigger": "--ot767 animationend + 50ms",
    })
    manifest = {"sourceStem": SOURCE_STEM, "fixtures": fixtures}
    (OUT / "two-block-smil-selector-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
