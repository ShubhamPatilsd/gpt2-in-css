#!/usr/bin/env python3
"""Can paused HVAR output animations retain values after producers detach?

This is a diagnostic control experiment, NOT an automatic runtime scheduler.
Only Python/CDP DOM mutations are used; page JavaScript remains disabled.
"""

import json
from pathlib import Path
import time

from profile_hybrid_twelve_block import browser, load, query, settle, error

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/hybrid-12block-profile"


def main():
    source = OUT / "content-gated/b0-qkv.html"
    reference = json.loads((source.parent / "reference.json").read_text())["layers"][0]
    css = (
        ".frozen .b0-qkv div{animation-play-state:paused!important}"
        ".detached .b0-qkv .metric{view-timeline-name:none!important}"
        ".detached .b0-qkv>.scroller{display:none!important}"
    )
    path = OUT / "timeline-latch.html"
    path.write_text(source.read_text().replace("</style>", css + "</style>"))
    result = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "automaticScheduler": False,
        "phases": [],
    }
    with browser() as cdp:
        node, initial, cold, reads = load(cdp, path, "#b0-qkv-result", "qkv", 2304)
        body = query(cdp, "body")
        receipt = query(cdp, ".b0-qkv-receipt")
        metric = query(cdp, ".b0-qkv .metric")
        result["initialError"] = error(initial, reference["qkv"][0])
        for phase, cls, state in [
            ("pause", "frozen", 0),
            ("detach-producers", "frozen detached", 0),
            ("resume-new-input", "", 1),
        ]:
            if state:
                cdp.command(
                    "DOM.setAttributeValue",
                    {
                        "nodeId": body,
                        "name": "style",
                        "value": reference["stageInputStyles"]["qkv"][state],
                    },
                )
            cdp.command(
                "DOM.setAttributeValue", {"nodeId": body, "name": "class", "value": cls}
            )
            time.sleep(0.1)
            values, reads = settle(cdp, node, "qkv", 2304, limit=20)
            props = {
                p["name"]: p["value"]
                for p in cdp.command(
                    "CSS.getComputedStyleForNode", {"nodeId": receipt}
                )["computedStyle"]
            }
            source_props = {
                p["name"]: p["value"]
                for p in cdp.command("CSS.getComputedStyleForNode", {"nodeId": metric})[
                    "computedStyle"
                ]
            }
            row = {
                "phase": phase,
                "error": error(values, reference["qkv"][state]),
                "gate": props.get("--gate-qkv"),
                "playState": props.get("animation-play-state"),
                "sourceTimeline": source_props.get("view-timeline-name"),
            }
            result["phases"].append(row)
            print(row, flush=True)
    (OUT / "timeline-latch-results.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
