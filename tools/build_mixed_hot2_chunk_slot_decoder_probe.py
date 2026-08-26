#!/usr/bin/env python3
"""Decode the first-stage group through 13 chunks and 16 reusable slots."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-hierarchical-outer-max16"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-chunk-slot-decoder"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
CHUNK_SIZE = 16
CHUNKS = math.ceil(GROUPS / CHUNK_SIZE)
SCORE_STEP_PX = 4


def score_match(group: int) -> str:
    return (
        "clamp(0px,"
        f"anchor-size(--score-group-{group} width)"
        f" - (var(--bucket) - .5)*{SCORE_STEP_PX}px,1px)"
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text().replace(
        "Mixed hot-two hierarchical outer maximum, fan-in 16",
        "Mixed hot-two chunk-slot group decoder",
        1,
    )
    html, removed_matches = re.subn(
        r'(?:<i class="match-carrier match-carrier-\d+"></i>)+',
        "".join(
            f'<i class="chunk-match chunk-match-{chunk}"></i>'
            for chunk in range(CHUNKS)
        ),
        html,
        count=1,
    )
    html, removed_carriers = re.subn(
        r'(?:<i class="carrier carrier-\d+"></i>)+',
        "".join(
            f'<i class="slot-carrier slot-carrier-{slot}"></i>'
            for slot in range(CHUNK_SIZE)
        ),
        html,
        count=1,
    )
    if removed_matches != 1 or removed_carriers != 1:
        raise RuntimeError({
            "matchRunsRemoved": removed_matches,
            "carrierRunsRemoved": removed_carriers,
        })
    if "match-carrier match-carrier-" in html or 'class="carrier carrier-' in html:
        raise RuntimeError("first-stage flat decoder markup remains")

    chunk_rules = []
    for chunk in range(CHUNKS):
        chunk_width = f"anchor-size(--outer-max-chunk-{chunk} width)"
        chunk_rules.append(
            f".chunk-match-{chunk}{{position-anchor:--outer-max-chunk-{chunk};"
            f"anchor-name:--chunk-match-{chunk};"
            f"width:calc(clamp(0px,{chunk_width}"
            f" - (var(--bucket) - .5)*{SCORE_STEP_PX}px,1px)*{CHUNKS - chunk})}}"
        )
    chunk_terms = ",".join(
        f"anchor-size(--chunk-match-{chunk} width)" for chunk in range(CHUNKS)
    )

    slot_rules = []
    for slot in range(CHUNK_SIZE):
        branches = []
        slot_code = (CHUNK_SIZE - slot) * SCORE_STEP_PX
        for chunk in range(CHUNKS):
            group = chunk * CHUNK_SIZE + slot
            if group >= GROUPS:
                continue
            mask = score_match(group)
            local = f"mod(anchor-size(--group-{group} width),{SCORE_STEP_PX}px)"
            branches.append(
                f"style(--chunk:{chunk}):calc({mask}*{slot_code}"
                f" + {local}*({mask}/1px))"
            )
        slot_rules.append(
            f".slot-carrier-{slot}{{anchor-name:--slot-carrier-{slot};"
            f"width:if({';'.join(branches)};else:0px)}}"
        )
    slot_terms = ",".join(
        f"anchor-size(--slot-carrier-{slot} width)" for slot in range(CHUNK_SIZE)
    )

    topology = (SOURCE / "topology.css").read_text() + (
        "\n@property --chunk{syntax:\"<number>\";inherits:true;initial-value:0}"
        ".chunk-match,.slot-carrier{position:fixed;left:0;height:1px}"
        + "".join(chunk_rules)
        + f".group-choice{{position-anchor:--chunk-match-0;width:max({chunk_terms})}}"
        + ".group-choice-reader{container:chunk-choice-result/inline-size}"
        + f"@container chunk-choice-result (width >= 0px){{.group-selection{{"
        f"--chunk:calc({CHUNKS} - round(nearest,100cqi/1px,1))}}}}"
        + "".join(slot_rules)
        + f".selected{{position-anchor:--slot-carrier-0;"
        + f"anchor-name:--selected-group;width:max({slot_terms})}}"
        + ".selected-reader{container:slot-choice-result/inline-size}"
        + "@container slot-choice-result (width >= 0px){.result{"
        f"--slot:calc({CHUNK_SIZE} - round(down,(100cqi + .001px)/"
        f"{SCORE_STEP_PX}px,1));"
        f"--group:calc(var(--chunk)*{CHUNK_SIZE} + var(--slot));"
        "--local:calc(255 - round(nearest,mod(100cqi + .001px,4px)"
        "/1px*64,1));--winner:calc(var(--group)*256 + var(--local));"
        "display:block;width:calc(var(--winner)*1px);height:1px}}\n"
    )

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": "mixed-hot2-chunk-slot-decoder",
        "sourceHierarchicalMax": SOURCE.name,
        "decoderChunkSize": CHUNK_SIZE,
        "decoderChunks": CHUNKS,
        "removedFlatMatchCarriers": GROUPS,
        "removedFlatSelectedCarriers": GROUPS,
        "replacementDecoderLeaves": CHUNKS + CHUNK_SIZE,
        "topologyStrategy": (
            "select one of the existing thirteen score chunks, then reuse "
            "sixteen fixed slot carriers whose style branches map the selected "
            "chunk to original score/local anchors; encode slot identity and "
            "the untouched local fraction in a maximum width below 68 pixels"
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
        "chunkMatchLeaves": CHUNKS,
        "slotLeaves": CHUNK_SIZE,
        "replacementDecoderLeaves": CHUNKS + CHUNK_SIZE,
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
