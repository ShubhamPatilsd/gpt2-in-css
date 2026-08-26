#!/usr/bin/env python3
"""Pack the first-stage score bucket and group identity, retaining local readback."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-direct-outer-max-pruned"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-packed-group-argmax"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
SCORE_STEP_PX = 4
PACKED_BUCKET_PX = GROUPS * SCORE_STEP_PX


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    marker = '<i class="direct-outer-max"></i>'
    if html.count(marker) != 1:
        raise RuntimeError("direct maximum node changed")
    html = html.replace(marker, '<i class="packed-group-argmax"></i>', 1).replace(
        "Mixed hot-two direct outer maximum, timeline graph pruned",
        "Mixed hot-two packed group argmax",
        1,
    )
    html, removed_match_nodes = re.subn(
        r'<i class="match-carrier match-carrier-\d+"></i>',
        "",
        html,
    )
    html, removed_group_max = re.subn(
        r'<i class="group-choice"></i>',
        "",
        html,
    )
    if removed_match_nodes != GROUPS or removed_group_max != 1:
        raise RuntimeError({
            "removedMatchNodes": removed_match_nodes,
            "removedGroupMax": removed_group_max,
        })

    packed_terms = []
    for group in range(GROUPS):
        score = f"anchor-size(--score-group-{group} width)"
        group_code_px = (GROUPS - 1 - group) * SCORE_STEP_PX
        packed_terms.append(
            f"calc(round(down,{score},{SCORE_STEP_PX}px)*{GROUPS}"
            f" + {group_code_px}px)"
        )
    topology = (SOURCE / "topology.css").read_text() + (
        "\n.packed-group-argmax{position:fixed;left:0;top:-94500px;height:1px;"
        "anchor-name:--packed-group-argmax;"
        f"width:max({','.join(packed_terms)})}}"
        ".outer-reader{position-anchor:--packed-group-argmax;"
        "width:anchor-size(--packed-group-argmax width);"
        "container:packed-group-result/inline-size}"
        ".group-choice-reader{position:static!important;width:auto!important;"
        "container:none!important}"
        "@container packed-group-result (width >= 0px){.selection{"
        "--packed-slot:round(nearest,(100cqi + .001px)/4px,1);"
        f"--bucket:round(down,var(--packed-slot)/{GROUPS},1);"
        f"--group:calc({GROUPS - 1} - mod(var(--packed-slot),{GROUPS}))}}}}\n"
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
        "backend": "mixed-hot2-packed-group-argmax",
        "sourcePrunedDirectMax": SOURCE.name,
        "removedFirstStageDecoderNodes": removed_match_nodes + removed_group_max,
        "packedGroupArgmax": {
            "groups": GROUPS,
            "scoreStepPx": SCORE_STEP_PX,
            "packedBucketPx": PACKED_BUCKET_PX,
            "maxCertifiedFixtureBucket": max_fixture_bucket,
            "maxCertifiedPackedWidthPx": (
                max_fixture_bucket * PACKED_BUCKET_PX + PACKED_BUCKET_PX - 4
            ),
        },
        "topologyStrategy": (
            "pack the four-pixel score bucket and descending group identity "
            "into one direct maximum; remove the 197 match carriers and their "
            "group-choice maximum, then retain the original selected-group "
            "carrier bank to recover the subpixel local-token identity"
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
        "removedDecoderNodes": removed_match_nodes + removed_group_max,
        "maxCertifiedPackedWidthPx": reference["packedGroupArgmax"][
            "maxCertifiedPackedWidthPx"
        ],
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
