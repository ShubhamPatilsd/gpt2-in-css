#!/usr/bin/env python3
"""Replace each 256-row Grid maximum with a zero-height block-flow maximum."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-hierarchical-outer-max16"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    topology = (SOURCE / "topology.css").read_text()
    source_reference = json.loads((SOURCE / "reference.json").read_text())

    html = html.replace(
        "Mixed hot-two hierarchical outer maximum, fan-in 16",
        "Mixed hot-two block-flow group maximum",
        1,
    )
    topology += (
        "\n/* A block container's max-content inline size is the maximum of its "
        "in-flow block children. Zero block-size keeps all rows at one offscreen "
        "position while preserving their intrinsic inline contributions. */"
        ".group-grid{display:block;grid-template-columns:none;height:0;overflow:visible}"
        ".group-grid>.candidate{grid-area:auto;justify-self:auto;height:0}"
        "\n"
    )
    reference = {
        **source_reference,
        "backend": "mixed-hot2-blockflow-group-max",
        "sourceHierarchicalOuterMax": SOURCE.name,
        "groupMaximumLayout": "zero-height block flow",
        "topologyStrategy": (
            "keep the retained fan-in-16 outer router, score rows, and decoders; "
            "replace each 256-row overlapping Grid reducer with an in-flow block "
            "container whose max-content width is the maximum child width"
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
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
