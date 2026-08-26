#!/usr/bin/env python3
"""Add a masked second-upper-group readback to the certified one-step head."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
OUTPUT_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-remaining-upper"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    fixtures = reference["certifiedFixtures"]
    groups = reference["groups"]

    source_markup = "".join(
        f'<i class="remaining-source remaining-source-{group}"></i>'
        for group in range(groups)
    )
    match_markup = "".join(
        f'<i class="remaining-match remaining-match-{group}"></i>'
        for group in range(groups)
    )
    markup = (
        '<span class="remaining-sources">' + source_markup + '</span>'
        '<i class="remaining-upper"></i><span class="remaining-reader">'
        '<span class="remaining-selection">' + match_markup
        + '<i class="remaining-group-choice"></i>'
        '<span class="remaining-group-reader">'
        '<output id="remaining-result" class="remaining-result"></output>'
        '</span></span></span>'
    )
    html = (SOURCE / "index.html").read_text()
    marker = '<i id="fine-result" class="fine-result"></i>'
    if html.count(marker) != 1:
        raise RuntimeError("fine result insertion point missing")
    html = html.replace(
        marker,
        f'<i id="fine-result" class="fine-result">{markup}</i>',
        1,
    ).replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Certified int10 remaining-upper-group probe",
        1,
    )

    source_rules = "".join(
        f".remaining-source-{group}{{"
        f"--remaining-mask:clamp(0,abs(var(--group) - {group}),1);"
        f"position-anchor:--score-group-{group};"
        f"anchor-name:--remaining-source-{group};"
        f"width:calc(anchor-size(--score-group-{group} width) * "
        "var(--remaining-mask))}"
        for group in range(groups)
    )
    source_sizes = ",".join(
        f"anchor-size(--remaining-source-{group} width)"
        for group in range(groups)
    )
    match_rules = "".join(
        f".remaining-match-{group}{{"
        f"position-anchor:--remaining-source-{group};"
        f"anchor-name:--remaining-match-{group};"
        f"width:calc(clamp(0px,anchor-size(--remaining-source-{group} width) - "
        f"(var(--remaining-bucket) - .5)*4px,1px)*{groups - group})}}"
        for group in range(groups)
    )
    match_sizes = ",".join(
        f"anchor-size(--remaining-match-{group} width)"
        for group in range(groups)
    )
    registrations = (
        '@property --remaining-mask{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --remaining-bucket{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --remaining-group{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --certificate-gap{syntax:"<number>";inherits:true;initial-value:0}'
    )
    css = (SOURCE / "index.css").read_text() + registrations + (
        '.remaining-source,.remaining-upper,.remaining-reader,.remaining-match,'
        '.remaining-group-choice,.remaining-group-reader,.remaining-result{'
        'position:fixed;left:0;top:-60000px;height:1px}'
        + source_rules
        + '.remaining-upper{position-anchor:--remaining-source-0;'
        'anchor-name:--remaining-upper-anchor;'
        f'width:max({source_sizes})}}'
        '.remaining-reader{position-anchor:--remaining-upper-anchor;'
        'width:anchor-size(--remaining-upper-anchor width);'
        'container:remaining-upper-result/inline-size}'
        '@container remaining-upper-result (width >= 0px){'
        '.remaining-selection{--remaining-bucket:round(down,100cqi/4px,1)}'
        + match_rules
        + '.remaining-group-choice{position-anchor:--remaining-match-0;'
        'anchor-name:--remaining-group-choice-anchor;'
        f'width:max({match_sizes})}}'
        '.remaining-group-reader{position-anchor:--remaining-group-choice-anchor;'
        'width:anchor-size(--remaining-group-choice-anchor width);'
        'container:remaining-group-result/inline-size}'
        '@container remaining-group-result (width >= 0px){.remaining-result{'
        f'--remaining-group:calc({groups} - round(nearest,100cqi/1px,1));'
        '--certificate-gap:calc(var(--fine-bucket) - var(--remaining-bucket));'
        'display:block;width:calc(var(--remaining-group)*1px);height:1px}}}'
    ) + "\n"

    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[:head.VOCABULARY], dtype=np.float64
    )
    scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    scales[scales == 0] = 1.0
    represented = np.rint(weights / scales[:, None]) * scales[:, None]
    error_norms = np.linalg.norm(weights - represented, axis=1)
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=int)
    upper = hidden @ represented.T + np.linalg.norm(hidden, axis=1)[:, None] * error_norms
    upper_buckets = np.floor(
        (upper - floors[:, None]) * head.SCORE_SCALE
    ).astype(int) + 1
    group_buckets = np.full((len(hidden), groups), -1, dtype=int)
    for group in range(groups):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        group_buckets[:, group] = np.max(upper_buckets[:, start:stop], axis=1)
    order = np.argsort(-group_buckets, axis=1, kind="stable")
    if not np.array_equal(order[:, 0], np.asarray(fixtures["upperGroups"])):
        raise RuntimeError("offline first upper group disagrees with source probe")
    fixtures["remainingUpperGroups"] = order[:, 1].astype(int).tolist()
    fixtures["remainingUpperBuckets"] = group_buckets[
        np.arange(len(hidden)), order[:, 1]
    ].astype(int).tolist()
    fixtures["offlineFirstCertificateGaps"] = (
        np.asarray(fixtures["selectedGroupFineLowerBuckets"], dtype=int)
        - np.asarray(fixtures["remainingUpperBuckets"], dtype=int)
    ).tolist()

    updated = {
        **reference,
        "backend": reference["backend"] + "-plus-masked-remaining-upper-readback",
        "source": SOURCE_NAME,
        "groupProbeElements": groups * 2 + 5,
        "certifiedFixtures": fixtures,
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    updated["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    updated["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(updated, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "groupProbeElements": updated["groupProbeElements"],
        "htmlBytes": updated["htmlBytes"],
        "cssBytes": updated["cssBytes"],
        "offlineFirstCertificates": int(np.sum(
            np.asarray(fixtures["offlineFirstCertificateGaps"]) >= 0
        )),
        "remainingUpperGroups": fixtures["remainingUpperGroups"],
    }, indent=2))


if __name__ == "__main__":
    main()
