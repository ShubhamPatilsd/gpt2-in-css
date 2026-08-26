#!/usr/bin/env python3
"""Split the direct 197-way outer maximum into a two-level reduction tree."""

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
FAN_IN = int(os.environ.get("OUTER_MAX_FAN_IN", "16"))
if FAN_IN < 2:
    raise ValueError("OUTER_MAX_FAN_IN must be at least 2")
CONTAIN_CHUNKS = os.environ.get("OUTER_MAX_CONTAIN", "0") == "1"
OUTPUT = ROOT / "experiments" / (
    f"gpt2-mixed-hot2-hierarchical-outer-max{FAN_IN}"
    + ("-contained" if CONTAIN_CHUNKS else "")
)
CHUNKS = math.ceil(GROUPS / FAN_IN)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    marker = '<i class="direct-outer-max"></i>'
    if html.count(marker) != 1:
        raise RuntimeError("direct maximum node changed")
    chunk_markup = "".join(
        f'<i class="outer-max-chunk outer-max-chunk-{chunk}"></i>'
        for chunk in range(CHUNKS)
    )
    html = html.replace(marker, chunk_markup + marker, 1).replace(
        "Mixed hot-two direct outer maximum, timeline graph pruned",
        "Mixed hot-two hierarchical outer maximum, fan-in 16",
        1,
    )

    chunk_rules = []
    for chunk in range(CHUNKS):
        start = chunk * FAN_IN
        stop = min(start + FAN_IN, GROUPS)
        terms = ",".join(
            f"anchor-size(--score-group-{group} width)"
            for group in range(start, stop)
        )
        chunk_rules.append(
            f".outer-max-chunk-{chunk}{{anchor-name:--outer-max-chunk-{chunk};"
            f"width:max({terms})}}"
        )
    root_terms = ",".join(
        f"anchor-size(--outer-max-chunk-{chunk} width)"
        for chunk in range(CHUNKS)
    )
    topology = (SOURCE / "topology.css").read_text() + (
        "\n.outer-max-chunk{position:fixed;left:0;top:-94300px;height:1px"
        + (";contain:size layout style" if CONTAIN_CHUNKS else "")
        + "}"
        + "".join(chunk_rules)
        + ".direct-outer-max{width:max("
        + root_terms
        + ")}\n"
    )

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": (
            f"mixed-hot2-hierarchical-outer-max{FAN_IN}"
            + ("-contained" if CONTAIN_CHUNKS else "")
        ),
        "sourcePrunedDirectMax": SOURCE.name,
        "outerMaximumFanIn": FAN_IN,
        "outerMaximumChunks": CHUNKS,
        "outerMaximumChunkContainment": CONTAIN_CHUNKS,
        "topologyStrategy": (
            f"materialize {CHUNKS} maxima over at most {FAN_IN} group-score "
            "anchors, then take one maximum over those chunk anchors; keep the "
            "original score rows and all winner decoders unchanged"
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
        "groups": GROUPS,
        "fanIn": FAN_IN,
        "chunks": CHUNKS,
        "contained": CONTAIN_CHUNKS,
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
