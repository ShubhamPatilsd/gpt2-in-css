#!/usr/bin/env python3
"""Pack four group winners at a time under the retained hierarchical maximum."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-hierarchical-outer-max16"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-packed4-hierarchical-argmax"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
PACK_SIZE = 4
PACKS = math.ceil(GROUPS / PACK_SIZE)
SCORE_STEP_PX = 4
PACK_BUCKET_PX = PACK_SIZE * SCORE_STEP_PX


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    html = html.replace(
        "Mixed hot-two hierarchical outer maximum, fan-in 16",
        "Mixed hot-two packed-four hierarchical argmax",
        1,
    )
    direct_marker = '<i class="direct-outer-max"></i>'
    if html.count(direct_marker) != 1:
        raise RuntimeError("direct maximum node changed")
    pack_markup = "".join(
        f'<i class="packed-group-block packed-group-block-{pack}"></i>'
        for pack in range(PACKS)
    )
    html = html.replace(direct_marker, pack_markup + direct_marker, 1)

    html, removed_matches = re.subn(
        r'(?:<i class="match-carrier match-carrier-\d+"></i>)+',
        "".join(
            f'<i class="pack-match pack-match-{pack}"></i>'
            for pack in range(PACKS)
        ),
        html,
        count=1,
    )
    html, removed_carriers = re.subn(
        r'(?:<i class="carrier carrier-\d+"></i>)+',
        "".join(
            f'<i class="pack-carrier pack-carrier-{pack}"></i>'
            for pack in range(PACKS)
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

    pack_rules = []
    for pack in range(PACKS):
        start = pack * PACK_SIZE
        stop = min(start + PACK_SIZE, GROUPS)
        terms = []
        for group in range(start, stop):
            slot = group - start
            group_code_px = (PACK_SIZE - 1 - slot) * SCORE_STEP_PX
            score = f"anchor-size(--score-group-{group} width)"
            local = f"anchor-size(--group-{group} width)"
            terms.append(
                f"calc(round(down,{score},{SCORE_STEP_PX}px)*{PACK_SIZE}"
                f" + {group_code_px}px + mod({local},{SCORE_STEP_PX}px))"
            )
        pack_rules.append(
            f".packed-group-block-{pack}{{anchor-name:--packed-group-block-{pack};"
            f"width:max({','.join(terms)})}}"
        )

    match_rules = []
    carrier_rules = []
    for pack in range(PACKS):
        packed = f"anchor-size(--packed-group-block-{pack} width)"
        match_rules.append(
            f".pack-match-{pack}{{position-anchor:--packed-group-block-{pack};"
            f"anchor-name:--pack-match-{pack};"
            f"width:calc(clamp(0px,round(down,{packed},{PACK_BUCKET_PX}px)"
            f" - (var(--bucket) - .5)*{PACK_BUCKET_PX}px,1px)*{PACKS - pack})}}"
        )
        carrier_rules.append(
            f".pack-carrier-{pack}{{position-anchor:--packed-group-block-{pack};"
            f"anchor-name:--pack-carrier-{pack};width:if(style(--pack:{pack}):"
            f"{packed};else:0px)}}"
        )

    match_terms = ",".join(
        f"anchor-size(--pack-match-{pack} width)" for pack in range(PACKS)
    )
    carrier_terms = ",".join(
        f"anchor-size(--pack-carrier-{pack} width)" for pack in range(PACKS)
    )
    topology = (SOURCE / "topology.css").read_text() + (
        "\n.packed-group-block{position:fixed;left:0;top:-94600px;height:1px}"
        + "".join(pack_rules)
        + ".pack-match,.pack-carrier{position:fixed;left:0;height:1px}"
        + "".join(match_rules)
        + f".group-choice{{width:max({match_terms})}}"
        + ".group-choice-reader{container:pack-choice-result/inline-size}"
        + f"@container pack-choice-result (width >= 0px){{.group-selection{{"
        f"--pack:calc({PACKS} - round(nearest,100cqi/1px,1))}}}}"
        + "".join(carrier_rules)
        + f".selected{{width:max({carrier_terms})}}"
        + ".selected-reader{container:packed-group-result/inline-size}"
        + "@container packed-group-result (width >= 0px){.result{"
        "--packed-slot:round(down,(100cqi + .001px)/4px,1);"
        f"--group:calc(var(--pack)*{PACK_SIZE} + "
        f"({PACK_SIZE - 1} - mod(var(--packed-slot),{PACK_SIZE})));"
        "--local:calc(255 - round(nearest,mod(100cqi + .001px,4px)"
        "/1px*64,1));--winner:calc(var(--group)*256 + var(--local));"
        "display:block;width:calc(var(--winner)*1px);height:1px}}\n"
    )

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    max_fixture_bucket = max(
        max(stage_buckets)
        for stage_buckets in source_reference["certifiedFixtures"][
            "unrolledBestBuckets"
        ]
    )
    reference = {
        **source_reference,
        "backend": "mixed-hot2-packed4-hierarchical-argmax",
        "sourceHierarchicalMax": SOURCE.name,
        "packedGroupBlockSize": PACK_SIZE,
        "packedGroupBlocks": PACKS,
        "removedFlatMatchCarriers": GROUPS,
        "removedFlatSelectedCarriers": GROUPS,
        "replacementDecoderNodes": PACKS * 3 + 2,
        "maxCertifiedPackedWidthPx": (
            max_fixture_bucket * PACK_BUCKET_PX + PACK_BUCKET_PX - 1
        ),
        "topologyStrategy": (
            "pack score bucket, group tie, and original local-token fraction "
            "within fifty blocks of at most four groups; use the retained "
            "fan-in-16 root bucket to select the lowest matching block, then "
            "select and decode its approximately 202k-pixel packed width"
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
        "packs": PACKS,
        "packSize": PACK_SIZE,
        "replacementDecoderNodes": reference["replacementDecoderNodes"],
        "maxCertifiedPackedWidthPx": reference["maxCertifiedPackedWidthPx"],
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
