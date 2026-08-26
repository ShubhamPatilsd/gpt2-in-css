#!/usr/bin/env python3
"""Nest bounded max() calls in one direct outer-maximum width expression."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-direct-outer-max-pruned"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
FAN_IN = int(os.environ.get("NESTED_MAX_FAN_IN", "16"))
if FAN_IN < 2:
    raise ValueError("NESTED_MAX_FAN_IN must be at least 2")
OUTPUT = ROOT / "experiments" / f"gpt2-mixed-hot2-nested-functional-max{FAN_IN}"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text().replace(
        "Mixed hot-two direct outer maximum, timeline graph pruned",
        f"Mixed hot-two nested functional maximum, fan-in {FAN_IN}",
        1,
    )
    chunk_terms = []
    for start in range(0, GROUPS, FAN_IN):
        stop = min(start + FAN_IN, GROUPS)
        terms = ",".join(
            f"anchor-size(--score-group-{group} width)"
            for group in range(start, stop)
        )
        chunk_terms.append(f"max({terms})")
    topology = (SOURCE / "topology.css").read_text() + (
        f"\n.direct-outer-max{{width:max({','.join(chunk_terms)})}}\n"
    )
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": f"mixed-hot2-nested-functional-max{FAN_IN}",
        "sourcePrunedDirectMax": SOURCE.name,
        "nestedMaximumFanIn": FAN_IN,
        "nestedMaximumChunks": len(chunk_terms),
        "topologyStrategy": (
            "group the 197 anchor-size operands into nested max functions of "
            f"at most {FAN_IN} terms inside the original single width property; "
            "add no boxes, anchors, or readback levels"
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
        "fanIn": FAN_IN,
        "chunks": len(chunk_terms),
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
