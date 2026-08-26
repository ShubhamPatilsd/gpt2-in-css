#!/usr/bin/env python3
"""Pack the first-stage score bucket and winner identity into one direct max."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-hot2-direct-outer-max-pruned"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-packed-direct-argmax"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
SCORE_STEP_PX = 4
PACKED_BUCKET_PX = GROUPS * SCORE_STEP_PX


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    html = html.replace(
        "Mixed hot-two direct outer maximum, timeline graph pruned",
        "Mixed hot-two packed direct argmax",
        1,
    )
    if html.count('<i class="direct-outer-max"></i>') != 1:
        raise RuntimeError("direct maximum node changed")
    html = html.replace(
        '<i class="direct-outer-max"></i>',
        '<i class="packed-direct-argmax"></i>',
        1,
    )
    html, removed_decoder_nodes = re.subn(
        r'<i class="(?:match-carrier match-carrier-\d+|group-choice|'
        r'carrier carrier-\d+|selected)"></i>',
        "",
        html,
    )
    expected_removed = GROUPS * 2 + 2
    if removed_decoder_nodes != expected_removed:
        raise RuntimeError(
            f"removed {removed_decoder_nodes} decoder nodes, expected {expected_removed}"
        )

    packed_terms = []
    for group in range(GROUPS):
        score = f"anchor-size(--score-group-{group} width)"
        group_code = GROUPS - 1 - group
        packed_terms.append(
            f"calc(round(nearest,{score},{SCORE_STEP_PX}px)*{GROUPS}"
            f" + {group_code * SCORE_STEP_PX}px + mod({score},{SCORE_STEP_PX}px))"
        )

    topology = (SOURCE / "topology.css").read_text() + (
        "\n.packed-direct-argmax{position:fixed;left:0;top:-94500px;height:1px;"
        "anchor-name:--packed-direct-argmax;"
        f"width:max({','.join(packed_terms)})}}"
        ".outer-reader{position-anchor:--packed-direct-argmax;"
        "width:anchor-size(--packed-direct-argmax width);"
        "container:packed-direct-result/inline-size}"
        ".group-choice-reader,.selected-reader{position:static!important;"
        "width:auto!important;container:none!important}"
        "@container packed-direct-result (width >= 0px){.selection{"
        f"--bucket:round(down,100cqi/{PACKED_BUCKET_PX}px,1);"
        f"--packed-remainder:mod(100cqi,{PACKED_BUCKET_PX}px);"
        f"--group:calc({GROUPS - 1} - round(down,var(--packed-remainder)/"
        f"{SCORE_STEP_PX}px,1));"
        "--local:calc(255 - round(nearest,mod(var(--packed-remainder),4px)"
        "/1px*64,1));--winner:calc(var(--group)*256 + var(--local))}"
        ".result{display:block;width:calc(var(--winner)*1px);height:1px}}\n"
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
        "backend": "mixed-hot2-packed-direct-argmax",
        "sourcePrunedDirectMax": SOURCE.name,
        "removedFirstStageDecoderNodes": removed_decoder_nodes,
        "packedArgmax": {
            "groups": GROUPS,
            "scoreStepPx": SCORE_STEP_PX,
            "packedBucketPx": PACKED_BUCKET_PX,
            "maxCertifiedFixtureBucket": max_fixture_bucket,
            "maxCertifiedPackedWidthPx": (
                max_fixture_bucket * PACKED_BUCKET_PX + PACKED_BUCKET_PX - 1
            ),
        },
        "topologyStrategy": (
            "negative-control attempt: round each group score to the same "
            "four-pixel bucket, append descending group identity and the score "
            "width modulo four, then decode bucket/group/local from one maximum; "
            "the group-score anchor is already four-pixel quantized, so its "
            "modulo payload is zero and cannot carry local-token identity"
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
        "removedDecoderNodes": removed_decoder_nodes,
        "packedBucketPx": PACKED_BUCKET_PX,
        "maxCertifiedPackedWidthPx": reference["packedArgmax"][
            "maxCertifiedPackedWidthPx"
        ],
        "htmlBytes": len(html.encode()),
        "topologyCssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
