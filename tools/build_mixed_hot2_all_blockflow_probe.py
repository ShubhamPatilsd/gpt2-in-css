#!/usr/bin/env python3
"""Use block-flow maxima for both coarse groups and dynamic fine stages."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-all-blockflow"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text().replace(
        "Mixed hot-two block-flow group maximum",
        "Mixed hot-two all-block-flow maxima",
        1,
    )
    topology = (SOURCE / "topology.css").read_text()
    if topology.count("else:grid)") != 6:
        raise RuntimeError("expected six conditional dynamic fine-stage Grids")
    topology = topology.replace("else:grid)", "else:block)")
    topology += (
        "\n.fine-stage{grid-template-columns:none;grid-template-rows:none;height:0;"
        "overflow:visible}"
        ".fine-stage>.fine-candidate{grid-area:auto;justify-self:auto;height:0}"
        "\n"
    )
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": "mixed-hot2-all-blockflow",
        "sourceBlockflowGroupMax": SOURCE.name,
        "fineMaximumLayout": "conditionally displayed zero-height block flow",
        "topologyStrategy": (
            source_reference["topologyStrategy"]
            + "; use the same block-flow maximum for each active non-hot "
            "256-row exact fine stage"
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
        "fineStages": 6,
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
