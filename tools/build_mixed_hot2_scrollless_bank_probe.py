#!/usr/bin/env python3
"""Remove the dead scroll surface around the direct-max score bank."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-scrollless"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text().replace(
        "Mixed hot-two block-flow group maximum",
        "Mixed hot-two block-flow scrollless bank",
        1,
    )
    topology = (SOURCE / "topology.css").read_text() + (
        "\n/* Direct anchor maxima no longer need the original view-timeline "
        "scroll range. Keep this ancestor for query-norm inheritance only. */"
        ".group-scroller{width:0;height:0;overflow:visible}"
        ".group-track{width:0;height:0}"
        "\n"
    )
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": "mixed-hot2-blockflow-scrollless",
        "sourceBlockflowGroupMax": SOURCE.name,
        "scoreBankScrollSurface": False,
        "topologyStrategy": (
            source_reference["topologyStrategy"]
            + "; collapse the now-dead timeline scroll wrapper to zero size and "
            "visible overflow while retaining its query-norm inheritance"
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
