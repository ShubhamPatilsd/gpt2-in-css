#!/usr/bin/env python3
"""Add a second reusable 256-token exact stage to the certified head."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-remaining-upper"
OUTPUT_NAME = "gpt2-hvar-grid-output-head-certified-upper-int10-two-step"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    fixtures = reference["certifiedFixtures"]
    html = (SOURCE / "index.html").read_text()

    stage_marker = '<span id="fine-stage" class="fine-stage">'
    stage_start = html.index(stage_marker) + len(stage_marker)
    stage_end = html.index('</span><span class="fine-reader">', stage_start)
    candidate_markup = html[stage_start:stage_end]
    second_stage = (
        '<span id="fine-stage-2" class="fine-stage fine-stage-2">'
        + candidate_markup
        + '</span><span class="fine-reader fine-reader-2">'
        '<i id="fine-result-2" class="fine-result-2"></i></span>'
    )
    result_marker = '<output id="remaining-result" class="remaining-result"></output>'
    if html.count(result_marker) != 1:
        raise RuntimeError("remaining result insertion point missing")
    html = html.replace(
        result_marker,
        '<output id="remaining-result" class="remaining-result">'
        + second_stage + '</output>',
        1,
    ).replace(
        "Certified int10 remaining-upper-group probe",
        "Certified int10 two-step exact probe",
        1,
    )

    registrations = (
        '@property --fine-bucket-2{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --fine-local-2{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --refined-winner-2{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --score-delta-2{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --use-second{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --best-two-winner{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --best-two-bucket{syntax:"<number>";inherits:true;initial-value:0}'
    )
    css = (SOURCE / "index.css").read_text() + registrations + (
        '.fine-stage-2{--group:var(--remaining-group);top:-50000px;'
        'anchor-name:--fine-winner-2}'
        '.fine-reader-2{position-anchor:--fine-winner-2;top:-49000px;'
        'width:anchor-size(--fine-winner-2 width);'
        'container:fine-result-2/inline-size}'
        '@container fine-result-2 (width >= 0px){.fine-result-2{'
        '--fine-bucket-2:round(down,100cqi/4px,1);'
        '--fine-local-2:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));'
        '--refined-winner-2:calc(var(--remaining-group)*256 + var(--fine-local-2));'
        '--score-delta-2:calc(var(--fine-bucket-2) - var(--fine-bucket));'
        '--use-second:max(clamp(0,sign(var(--score-delta-2)),1),'
        'calc((1 - abs(sign(var(--score-delta-2)))) * '
        'clamp(0,sign(var(--refined-winner) - var(--refined-winner-2)),1)));'
        '--best-two-winner:calc(var(--refined-winner) * (1 - var(--use-second)) + '
        'var(--refined-winner-2) * var(--use-second));'
        '--best-two-bucket:max(var(--fine-bucket),var(--fine-bucket-2));'
        'display:block;width:calc(var(--best-two-winner)*1px);height:1px}}'
    ) + "\n"

    fine_reference = json.loads(FINE_REFERENCE.read_text())
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[:head.VOCABULARY], dtype=np.float64
    )
    fine_codes = np.rint(weights / fine_reference["weightScale"]).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_reference["weightScale"]
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=int)
    fine_scores = hidden @ fine_weights.T
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * fine_reference["scoreScale"]
    ).astype(int)
    second_winners: list[int] = []
    second_buckets: list[int] = []
    best_winners: list[int] = []
    best_buckets: list[int] = []
    for fixture, group in enumerate(fixtures["remainingUpperGroups"]):
        start = int(group) * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        winner = start + int(np.argmax(fine_buckets[fixture, start:stop]))
        bucket = int(fine_buckets[fixture, winner])
        second_winners.append(winner)
        second_buckets.append(bucket)
        first_winner = int(fixtures["selectedGroupFineWinners"][fixture])
        first_bucket = int(fixtures["selectedGroupFineBuckets"][fixture])
        if bucket > first_bucket or (bucket == first_bucket and winner < first_winner):
            best_winners.append(winner)
            best_buckets.append(bucket)
        else:
            best_winners.append(first_winner)
            best_buckets.append(first_bucket)
    fixtures["secondGroupFineWinners"] = second_winners
    fixtures["secondGroupFineBuckets"] = second_buckets
    fixtures["bestTwoFineWinners"] = best_winners
    fixtures["bestTwoFineBuckets"] = best_buckets

    updated = {
        **reference,
        "backend": reference["backend"] + "-plus-reused-second-fine-stage",
        "source": SOURCE_NAME,
        "secondFineCandidateElements": head.GROUP_SIZE,
        "certifiedFixtures": fixtures,
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    updated["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    updated["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(updated, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "secondFineCandidateElements": head.GROUP_SIZE,
        "htmlByteIncrease": updated["htmlBytes"] - reference["htmlBytes"],
        "cssByteIncrease": updated["cssBytes"] - reference["cssBytes"],
        "denseWinnersCoveredByTwoGroups": int(np.sum(
            np.asarray(best_winners) == np.asarray(fixtures["denseWinners"])
        )),
        "fixtures": len(hidden),
    }, indent=2))


if __name__ == "__main__":
    main()
