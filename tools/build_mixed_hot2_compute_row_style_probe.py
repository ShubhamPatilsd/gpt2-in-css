#!/usr/bin/env python3
"""Screen paint and shaping hints on the retained block-flow score rows."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max"
VARIANT = os.environ.get("MIXED_HOT2_ROW_STYLE", "fast-text")
RULES = {
    "fast-text": (
        ".candidate{font-kerning:none;font-variant-ligatures:none;"
        "font-optical-sizing:none;font-synthesis:none;text-rendering:optimizeSpeed}"
    ),
    "hidden": ".candidate{visibility:hidden}",
    "fast-text-hidden": (
        ".candidate{visibility:hidden;font-kerning:none;font-variant-ligatures:none;"
        "font-optical-sizing:none;font-synthesis:none;text-rendering:optimizeSpeed}"
    ),
}
if VARIANT not in RULES:
    raise ValueError(f"unknown MIXED_HOT2_ROW_STYLE={VARIANT!r}")
OUTPUT = ROOT / "experiments" / f"gpt2-mixed-hot2-blockflow-{VARIANT}"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text().replace(
        "Mixed hot-two block-flow group maximum",
        f"Mixed hot-two block-flow {VARIANT} row style",
        1,
    )
    topology = (SOURCE / "topology.css").read_text() + f"\n{RULES[VARIANT]}\n"
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": f"mixed-hot2-blockflow-{VARIANT}",
        "sourceBlockflow": SOURCE.name,
        "computeRowStyleVariant": VARIANT,
        "computeRowStyleRule": RULES[VARIANT],
        "topologyStrategy": (
            source_reference["topologyStrategy"]
            + f"; apply the {VARIANT} style hint to score candidates"
        ),
        "generatedBytes": {
            "index.html": len(html.encode()),
            "topology.css": len(topology.encode()),
        },
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "topology.css").write_text(topology)
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "directory": OUTPUT.name,
        "variant": VARIANT,
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
