#!/usr/bin/env python3
"""Add one gated 17-group parallel exact wave after the production prefix."""

from __future__ import annotations

import json
import re
from pathlib import Path

from build_certified_int10_batched_tail_probe import (
    merge_css,
    merge_markup,
    registration,
    router_css,
    router_markup,
    scorer_css,
    scorer_markup,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "experiments"
    / "gpt2-groupwise-cauchy-blockflow-production-range-prefix6"
)
OUTPUT = (
    ROOT
    / "experiments"
    / "gpt2-groupwise-cauchy-blockflow-production-batch17"
)
GROUPS = 197
PREFIX = 6
BATCH = 17


def exact_candidates(document: str) -> str:
    marker = (
        '<span id="dynamic-fine-stage-0" '
        'class="fine-stage dynamic-fine-stage dynamic-fine-stage-0">'
    )
    start = document.index(marker) + len(marker)
    stop = document.index('</span><i id="mixed-choice-source-0"', start)
    candidates = document[start:stop]
    if candidates.count('class="fine-candidate"') != 256:
        raise RuntimeError("expected one 256-row dynamic exact candidate bank")
    return candidates


def build_tail(candidates: str) -> tuple[str, str]:
    prefix_selected = [f"selected-group-{stage}" for stage in range(PREFIX)]
    batch_selected = ["batch-group-0"]
    certificate = router_markup(
        BATCH,
        "batch-next-group",
        "",
        result_id="batch-certificate-result",
    )
    child = merge_markup(BATCH, certificate, candidates)
    for slot in range(BATCH - 1, 0, -1):
        child = router_markup(slot, f"batch-group-{slot}", child)
    markup = f'<span id="batch-start" class="batch-start">{child}</span>'

    registrations = [
        registration("tail-allowance", 49),
        registration("batch-merged-bucket"),
        registration("batch-winning-group"),
        registration("batch-final-winner"),
        registration("batch-certificate-gap"),
        registration("batch-done"),
        registration("batch-certified-winner"),
    ]
    for slot in range(BATCH):
        registrations.extend((
            registration(f"batch-group-{slot}"),
            registration(f"batch-upper-{slot}"),
            registration(f"batch-bucket-{slot}"),
            registration(f"batch-local-{slot}"),
            registration(f"batch-winner-{slot}"),
        ))
    registrations.extend((
        registration("batch-next-group"),
        registration("batch-next-upper"),
    ))
    fixed = (
        "body{anchor-scope:all}"
        ".batch-start,.batch-router-source,.batch-router-max,"
        ".batch-router-upper-reader,.batch-router-match,.batch-router-choice,"
        ".batch-router-group-reader,.batch-router-result,.batch-compute,"
        ".batch-fine-stage,.batch-fine-reader,.batch-fine-result,"
        ".batch-score-carrier,.batch-token-carrier,.batch-prefix-score,"
        ".batch-prefix-token,.batch-score-max,.batch-score-reader,"
        ".batch-score-result,.batch-token-source,.batch-token-max,"
        ".batch-token-reader,.batch-final-result{"
        "position:fixed;left:0;top:-30000px;height:1px}"
        ".batch-start{--batch-group-0:var(--remaining-group-6);"
        "--batch-upper-0:var(--upper-bucket-6);"
        "display:if(style(--done-0:1):none;style(--done-1:1):none;"
        "style(--done-2:1):none;style(--done-3:1):none;"
        "style(--done-4:1):none;style(--done-5:1):none;else:block)}"
        ".batch-fine-reader{width:0;top:-27500px}"
        ".batch-score-carrier,.batch-token-carrier,.batch-token-source{width:0}"
    )
    parts = ["".join(registrations), fixed]
    for slot in range(1, BATCH):
        selected = [*prefix_selected, *batch_selected]
        parts.append(router_css(
            slot,
            selected,
            f"batch-group-{slot}",
            f"batch-upper-{slot}",
        ))
        batch_selected.append(f"batch-group-{slot}")
    for slot in range(BATCH):
        parts.append(scorer_css(slot))
    parts.append(merge_css(BATCH))
    parts.append(router_css(
        BATCH,
        [*prefix_selected, *batch_selected],
        "batch-next-group",
        "batch-next-upper",
        certificate=True,
    ))
    return markup, "".join(parts) + "\n"


def main() -> None:
    for path in (SOURCE / "index.html", SOURCE / "reference.json"):
        if not path.exists():
            raise FileNotFoundError(path)
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    if int(source_reference["stages"]) != PREFIX:
        raise RuntimeError("batch source is not the six-stage production prefix")
    if int(source_reference["stopGapBuckets"]) != 49:
        raise RuntimeError("batch source does not use the calibrated stop gap")

    source_html = (SOURCE / "index.html").read_text()
    candidates = exact_candidates(source_html)
    tail, css = build_tail(candidates)
    marker = '<output id="remaining-result-6" class="remaining-result-6"></output>'
    if source_html.count(marker) != 1:
        raise RuntimeError("empty sixth-prefix result insertion point missing")
    html = source_html.replace(
        marker,
        '<output id="remaining-result-6" class="remaining-result-6">'
        + tail
        + "</output>",
        1,
    )
    html = html.replace(
        'href="coarse-production.css"',
        'href="../gpt2-groupwise-cauchy-blockflow-production-range-prefix6/'
        'coarse-production.css"',
    ).replace(
        'href="fine-stage-production.css"',
        'href="../gpt2-groupwise-cauchy-blockflow-production-range-prefix6/'
        'fine-stage-production.css"',
    ).replace(
        'href="topology.css"',
        'href="../gpt2-groupwise-cauchy-blockflow-production-range-prefix6/'
        'topology.css"><link rel="stylesheet" href="batch-tail.css"',
    ).replace(
        "Production-range groupwise-Cauchy 6-stage block-flow cascade",
        "Production-range groupwise-Cauchy six-stage plus batch-17 tail",
    )
    if html.count('href="batch-tail.css"') != 1:
        raise RuntimeError("batch stylesheet insertion failed")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "batch-tail.css").write_text(css)
    reference = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "runtimeContainsJavaScript": False,
        "backend": "production-groupwise-six-serial-plus-batch17-exact-tail",
        "source": SOURCE.name,
        "prefixGroups": PREFIX,
        "batchSize": BATCH,
        "maximumExactGroups": PREFIX + BATCH,
        "stopGapBuckets": 49,
        "upperTransportShortfallBuckets": 1,
        "productionInputRange": source_reference["productionInputRange"],
        "scoreGain": source_reference["scoreGain"],
        "fontBankStrategy": source_reference["fontBankStrategy"],
        "largeFontBytesGenerated": 0,
        "candidateRowsPerBatch": 256 * BATCH,
        "serialUpperRoutersInBatch": BATCH,
        "htmlBytes": len(html.encode()),
        "batchCssBytes": len(css.encode()),
        "domElements": len(re.findall(
            r"<(?:div|span|i|main|section|output|input|label)\b", html
        )),
        "sourceReference": "../" + SOURCE.name + "/reference.json",
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "batch": BATCH,
        "htmlBytes": reference["htmlBytes"],
        "batchCssBytes": reference["batchCssBytes"],
        "domElements": reference["domElements"],
        "largeFontBytesGenerated": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
