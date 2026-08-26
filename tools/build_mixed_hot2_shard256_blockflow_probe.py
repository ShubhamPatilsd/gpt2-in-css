#!/usr/bin/env python3
"""Compose retained router/layout optimizations over a selected int10 bank."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / os.environ.get(
    "MIXED_HOT2_COMPOSE_SOURCE", "gpt2-mixed-precision-hot2-upper-shard256"
)
OUTPUT = ROOT / "experiments" / os.environ.get(
    "MIXED_HOT2_COMPOSE_OUTPUT", "gpt2-mixed-hot2-blockflow-group-max-shard256"
)
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
FAN_IN = 16
CHUNKS = math.ceil(GROUPS / FAN_IN)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    topology = (SOURCE / "topology.css").read_text()

    reader = '<div class="outer-reader">'
    if html.count(reader) != 1:
        raise RuntimeError("outer reader insertion point changed")
    chunk_markup = "".join(
        f'<i class="outer-max-chunk outer-max-chunk-{chunk}"></i>'
        for chunk in range(CHUNKS)
    )
    html = html.replace(
        reader,
        chunk_markup + '<i class="direct-outer-max"></i>' + reader,
        1,
    )
    html, removed = re.subn(r'<i class="group-proxy group-proxy-\d+"></i>', "", html)
    if removed != GROUPS:
        raise RuntimeError(f"removed {removed} proxies, expected {GROUPS}")
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    if "coarseShardDimensions" in source_reference:
        shard_dimensions = int(source_reference["coarseShardDimensions"])
        glyphs_per_token = int(source_reference["coarseGlyphsPerToken"])
    else:
        one_step = ROOT / "experiments" / source_reference["sourceOneStep"]
        one_step_reference = json.loads((one_step / "reference.json").read_text())
        coarse = ROOT / "experiments" / one_step_reference["coarseHead"]
        coarse_reference = json.loads((coarse / "reference.json").read_text())
        shard_dimensions = int(coarse_reference["shardDimensions"])
        glyphs_per_token = int(one_step_reference["coarseGlyphsPerToken"])
    html = html.replace(
        "Mixed-precision hot-two certified upper head",
        f"Mixed hot-two {glyphs_per_token}-shard block-flow group maximum",
        1,
    )

    direct_terms = ",".join(
        f"anchor-size(--score-group-{group} width)" for group in range(GROUPS)
    )
    topology += (
        "\nbody{anchor-scope:all}"
        ".direct-outer-max{position:fixed;left:0;top:-94000px;height:1px;"
        f"anchor-name:--direct-outer-max;width:max({direct_terms})}}"
        ".outer-reader{position-anchor:--direct-outer-max;"
        "width:anchor-size(--direct-outer-max width)}"
        ".model{timeline-scope:none!important}"
        ".group-wrapper{view-timeline:none!important}"
        ".group-proxy{display:none!important}"
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
        f"anchor-size(--outer-max-chunk-{chunk} width)" for chunk in range(CHUNKS)
    )
    topology += (
        ".outer-max-chunk{position:fixed;left:0;top:-94300px;height:1px}"
        + "".join(chunk_rules)
        + f".direct-outer-max{{width:max({root_terms})}}"
        + ".group-grid{display:block;grid-template-columns:none;height:0;overflow:visible}"
        + ".group-grid>.candidate{grid-area:auto;justify-self:auto;height:0}\n"
    )

    reference = {
        **source_reference,
        "backend": (
            f"mixed-hot2-shard{shard_dimensions}-hierarchical-max16-blockflow"
        ),
        "sourceMixedCoarseShard": SOURCE.name,
        "coarseShardDimensions": shard_dimensions,
        "coarseGlyphsPerNonHotToken": glyphs_per_token,
        "coarseEstimatedShapedGlyphs": VOCABULARY * glyphs_per_token,
        "removedTimelineProxyElements": removed,
        "outerMaximumFanIn": FAN_IN,
        "outerMaximumChunks": CHUNKS,
        "groupMaximumLayout": "zero-height block flow",
        "topologyStrategy": (
            f"use the {glyphs_per_token}x{shard_dimensions}-axis row-wise int10 "
            "bank; prune timeline proxies; "
            "reduce 197 score anchors through 13 fan-in-16 maxima; use zero-height "
            "block flow for each 256-token group maximum"
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
        "coarseGlyphsPerNonHotToken": glyphs_per_token,
        "removedTimelineProxyElements": removed,
        "outerMaximumChunks": CHUNKS,
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
