#!/usr/bin/env python3
"""Build a dependency-driven SMIL scheduler for two blocks and staged head."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE_STEM = "view-timeline-two-block-with-selective-gpt2-output-head-internally-staged"
OUTPUT_STEM = SOURCE_STEM + "-event-scheduled"
CONTROLS = (
    "selective-head-run",
    "fine-stage-run",
    "near-stage-run",
    "dither-stage-run",
)


def svg_event_bridge(
    scheduler_id: str,
    css_ready_id: str,
    signal_id: str,
    event: str,
) -> str:
    return (
        f'<svg id="{scheduler_id}" class="inference-event-scheduler" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<g id="{css_ready_id}"></g><g id="{signal_id}">'
        f'<set attributeName="class" to="ready" begin="{event}+0.05s" '
        'fill="freeze" /></g></svg>'
    )


def main() -> None:
    source = (OUT / f"{SOURCE_STEM}.html").read_text()
    for control in CONTROLS:
        unchecked = f'<input id="{control}" type="checkbox">'
        if source.count(unchecked) != 1:
            raise RuntimeError(f"missing control {control}")
        source = source.replace(unchecked, unchecked[:-1] + " checked>", 1)

    b1_bridge = svg_event_bridge(
        "b1-event-scheduler", "b0-css-ready", "b1-smil-signal",
        "b0-css-ready.animationend",
    )
    if source.count('<div class="b1-norm">') != 1:
        raise RuntimeError("missing block-1 boundary")
    source = source.replace('<div class="b1-norm">', b1_bridge + '<div class="b1-norm">', 1)

    head_bridge = svg_event_bridge(
        "head-event-scheduler", "b1-css-ready", "head-smil-signal",
        "b1-css-ready.animationend",
    )
    if source.count('<span class="selective-head-gate">') != 1:
        raise RuntimeError("missing head boundary")
    source = source.replace(
        '<span class="selective-head-gate">',
        head_bridge + '<span class="selective-head-gate">',
        1,
    )

    coarse_bridge = svg_event_bridge(
        "coarse-event-scheduler", "coarse-css-ready", "fine-smil-signal",
        "coarse-css-ready.animationend",
    )
    if source.count('<span id="fine-stage" class="fine-stage">') != 1:
        raise RuntimeError("missing fine-stage boundary")
    source = source.replace(
        '<span id="fine-stage" class="fine-stage">',
        coarse_bridge + '<span id="fine-stage" class="fine-stage">',
        1,
    )

    fine_bridge = svg_event_bridge(
        "fine-event-scheduler", "fine-css-ready", "near-smil-signal",
        "fine-css-ready.animationend",
    )
    fine_result = '<i id="fine-result" class="fine-result"></i>'
    if source.count(fine_result) != 1:
        raise RuntimeError("missing fine result")
    source = source.replace(fine_result, fine_result + fine_bridge, 1)

    near_bridge = svg_event_bridge(
        "near-event-scheduler", "near-css-ready", "dither-smil-signal",
        "near-css-ready.animationend",
    )
    dither_stage = '<span id="dither-stage" class="dither-stage">'
    if source.count(dither_stage) != 1:
        raise RuntimeError("missing dither-stage boundary")
    source = source.replace(dither_stage, near_bridge + dither_stage, 1)

    stylesheet = f"{OUTPUT_STEM}.css"
    css = (
        "@keyframes inference-stage-ready{from{opacity:.99}to{opacity:1}}"
        ".inference-event-scheduler{position:fixed;left:-10000px;top:0;width:1px;height:1px}"
        "#b0-css-ready{animation:inference-stage-ready 1s linear both;"
        "animation-timeline:--ot767;animation-range:cover}"
        "#b1-css-ready{animation:inference-stage-ready 1s linear both;"
        "animation-timeline:--b1pt767;animation-range:cover}"
        "@container selected-result (min-width:0px){#coarse-css-ready{"
        "animation:inference-stage-ready 1ms linear both}}"
        "@container fine-result (min-width:0px){#fine-css-ready{"
        "animation:inference-stage-ready 1ms linear both}}"
        "@container near-result (min-width:0px){#near-css-ready{"
        "animation:inference-stage-ready 1ms linear both}}"
        "html:not(:has(#b1-smil-signal.ready)) .b1-norm{display:none}"
        "html:not(:has(#head-smil-signal.ready)) .selective-head-gate{"
        "content-visibility:hidden;contain-intrinsic-size:1px}"
        "html:not(:has(#fine-smil-signal.ready)) :is(.fine-stage,.fine-reader),"
        "html:not(:has(#near-smil-signal.ready)) :is(.near-carriers,.near-reader),"
        "html:not(:has(#dither-smil-signal.ready)) :is(.dither-stage,.dither-reader){"
        "content-visibility:hidden;contain-intrinsic-size:1px}"
    )
    source = source.replace(
        "</title>", f'</title><link rel="stylesheet" href="{stylesheet}">', 1
    )
    if source.lower().count("<script"):
        raise RuntimeError("runtime fixture unexpectedly contains JavaScript")
    (OUT / stylesheet).write_text(css)
    (OUT / f"{OUTPUT_STEM}.html").write_text(source)
    reference = json.loads((OUT / f"{SOURCE_STEM}-reference.json").read_text())
    reference.update({
        "source": SOURCE_STEM,
        "output": OUTPUT_STEM,
        "scheduler": "CSS animationend -> SVG SMIL class -> HTML :has()",
    })
    (OUT / f"{OUTPUT_STEM}-reference.json").write_text(
        json.dumps(reference, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
