#!/usr/bin/env python3
"""Build the six-stage hot-two split-GSUB/exact output-head probe."""

from __future__ import annotations

import json
import re
from pathlib import Path

import build_gsub_hybrid_six_stage_head_probe as integration


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_NAME = (
    "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hot2"
)
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
ONE_STEP = integration.ONE_STEP
BASELINE = integration.BASELINE
SPLIT_GSUB = integration.SPLIT_GSUB
STAGES = 6
MARGIN_THRESHOLD = 4


def build_split_bank_css() -> dict:
    css = (SPLIT_GSUB / "index.css").read_text()
    geometry = re.search(
        r"\(size - ([0-9.]+)px\)\*([0-9.]+) \+ var\(--score-offset\)", css
    )
    if not geometry:
        raise RuntimeError("split GSUB candidate geometry is missing")
    base, factor = geometry.groups()
    source_expression = f"(size - {base}px)*{factor} + var(--score-offset)"
    if css.count(source_expression) != 1:
        raise RuntimeError("split GSUB candidate geometry is not unique")
    css = css.replace(
        'url("', 'url("../gsub-split-complement-fine-scorer/'
    )
    css = css.replace(".fine-stage", ".split-gsub-stage")
    css = css.replace(".candidate", ".split-gsub-candidate")
    css += (
        ".split-gsub-stage{--score-offset:inherit;"
        "--probe-feature:if(style(--group:0):1;style(--group:1):2;else:1)}"
        ".split-gsub-runner .split-gsub-candidate{"
        "--winner-mask:clamp(0,1 - abs(var(--stage-top-local) - var(--local)),1);"
        "width:calc-size(max-content,calc(round(nearest,"
        f"{source_expression},4px) + var(--local-tie)/64*1px "
        "- var(--winner-mask)*100000px))}\n"
    )
    (OUTPUT / "split-bank.css").write_text(css)
    return {"basePx": float(base), "factor": float(factor)}


def stage_markup(stage: int, split: str, exact: str, child: str) -> str:
    result_id = "fine-result" if stage == 0 else f"fine-result-{stage}"
    return (
        f'<span id="hybrid-stage-{stage}" class="hybrid-stage hybrid-stage-{stage}">'
        f'<span id="split-gsub-top-{stage}" class="split-gsub-stage '
        f'split-gsub-top split-gsub-top-{stage}">{split}</span>'
        f'<span class="hybrid-top-reader hybrid-top-reader-{stage}">'
        f'<span id="hybrid-top-decode-{stage}" class="hybrid-top-decode-{stage}">'
        f'<span id="split-gsub-runner-{stage}" class="split-gsub-stage '
        f'split-gsub-runner split-gsub-runner-{stage}">{split}</span>'
        f'<span class="hybrid-runner-reader hybrid-runner-reader-{stage}">'
        f'<span id="hybrid-decision-{stage}" class="hybrid-decision-{stage}">'
        f'<span id="exact-stage-{stage}" class="fine-stage exact-stage '
        f'exact-stage-{stage}">{exact}</span>'
        f'<i id="hybrid-choice-source-{stage}" class="hybrid-choice-source '
        f'hybrid-choice-source-{stage}"></i>'
        f'<span class="hybrid-final-reader hybrid-final-reader-{stage}">'
        f'<i id="{result_id}" class="hybrid-fine-result '
        f'hybrid-fine-result-{stage}">{child}</i>'
        "</span></span></span></span></span></span>"
    )


def stage_css(stage: int) -> str:
    top = -95_000 + stage * 600
    runner = top + 200
    choice = top + 400
    wrapper = "display:contents;" if stage == 0 else (
        f"display:if(style(--done-{stage - 1}:1):none;else:contents);"
    )
    group_binding = "" if stage == 0 else f"--group:var(--remaining-group-{stage});"
    result_group = (
        "--search-root-group:var(--group);--selected-group-0:var(--group);"
        if stage == 0
        else (
            f"--group:var(--search-root-group);"
            f"--selected-group-{stage}:var(--remaining-group-{stage});"
        )
    )
    fine_group = "var(--group)" if stage == 0 else f"var(--remaining-group-{stage})"
    if stage == 0:
        best_state = (
            "--best-bucket-0:var(--fine-bucket-0);"
            "--best-winner-0:var(--fine-winner-0);"
        )
    else:
        previous = stage - 1
        best_state = (
            f"--score-delta-{stage}:calc(var(--fine-bucket-{stage}) - "
            f"var(--best-bucket-{previous}));"
            f"--use-stage-{stage}:max(clamp(0,sign(var(--score-delta-{stage})),1),"
            f"calc((1 - abs(sign(var(--score-delta-{stage})))) * "
            f"clamp(0,sign(var(--best-winner-{previous}) - "
            f"var(--fine-winner-{stage})),1)));"
            f"--best-winner-{stage}:calc(var(--best-winner-{previous}) * "
            f"(1 - var(--use-stage-{stage})) + var(--fine-winner-{stage}) * "
            f"var(--use-stage-{stage}));"
            f"--best-bucket-{stage}:max(var(--best-bucket-{previous}),"
            f"var(--fine-bucket-{stage}));"
        )
    hot_width = (
        f"if(style(--group:0):anchor-size(--gsub-top-winner-{stage} width);"
        f"style(--group:1):anchor-size(--gsub-top-winner-{stage} width);else:0px)"
    )
    runner_width = (
        f"if(style(--group:0):anchor-size(--gsub-runner-winner-{stage} width);"
        f"style(--group:1):anchor-size(--gsub-runner-winner-{stage} width);else:0px)"
    )
    return (
        f".hybrid-stage-{stage}{{{wrapper}}}"
        f".split-gsub-top-{stage}{{{group_binding}top:{top}px;"
        f"anchor-name:--gsub-top-winner-{stage};"
        "display:if(style(--group:0):grid;style(--group:1):grid;else:none)}"
        f".hybrid-top-reader-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{top + 100}px;height:1px;position-anchor:--gsub-top-winner-{stage};"
        f"width:{hot_width};container:gsub-top-readback-{stage}/inline-size}}"
        f"@container gsub-top-readback-{stage} (width >= 0px){{"
        f".hybrid-top-decode-{stage}{{{group_binding}"
        f"--top-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--top-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--stage-top-local:var(--top-local-{stage})}}"
        f".split-gsub-runner-{stage}{{{group_binding}top:{runner}px;"
        f"anchor-name:--gsub-runner-winner-{stage};"
        "display:if(style(--group:0):grid;style(--group:1):grid;else:none)}"
        f".hybrid-runner-reader-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{runner + 100}px;height:1px;"
        f"position-anchor:--gsub-runner-winner-{stage};width:{runner_width};"
        f"container:gsub-runner-readback-{stage}/inline-size}}"
        f"@container gsub-runner-readback-{stage} (width >= 0px){{"
        f".hybrid-decision-{stage}{{{group_binding}"
        f"--runner-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--runner-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--margin-{stage}:calc(var(--top-bucket-{stage}) - "
        f"var(--runner-bucket-{stage}));"
        f"--hot2-route-{stage}:clamp(0,2 - var(--group),1);"
        f"--margin-fallback-{stage}:clamp(0,{MARGIN_THRESHOLD + 1} - "
        f"var(--margin-{stage}),1);"
        f"--other-group-fallback-{stage}:calc(1 - var(--hot2-route-{stage}));"
        f"--fallback-{stage}:max(var(--other-group-fallback-{stage}),"
        f"var(--margin-fallback-{stage}))}}"
        f".exact-stage-{stage}{{{group_binding}top:{choice}px;"
        f"anchor-name:--exact-winner-{stage};"
        f"display:if(style(--fallback-{stage}:1):grid;else:none)}}"
        f".hybrid-choice-source-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{choice + 100}px;height:1px;anchor-name:--hybrid-winner-{stage};"
        f"width:if(style(--fallback-{stage}:1):"
        f"anchor-size(--exact-winner-{stage} width);else:"
        f"anchor-size(--gsub-top-winner-{stage} width))}}"
        f".hybrid-final-reader-{stage}{{position:fixed;left:0;"
        f"top:{choice + 200}px;height:1px;position-anchor:--hybrid-winner-{stage};"
        f"width:anchor-size(--hybrid-winner-{stage} width);"
        f"container:hybrid-fine-result-{stage}/inline-size}}"
        f"@container hybrid-fine-result-{stage} (width >= 0px){{"
        f".hybrid-fine-result-{stage}{{{result_group}"
        f"--fine-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--fine-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--fine-winner-{stage}:calc({fine_group}*256 + "
        f"var(--fine-local-{stage}));{best_state}display:block;"
        f"width:calc(var(--best-winner-{stage})*1px);height:1px}}"
        "}}}}"
    )


def registrations() -> str:
    names: list[str] = []
    for stage in range(STAGES):
        names.extend((
            f"selected-group-{stage}", f"top-bucket-{stage}",
            f"top-local-{stage}", f"runner-bucket-{stage}",
            f"runner-local-{stage}", f"margin-{stage}",
            f"hot2-route-{stage}", f"margin-fallback-{stage}",
            f"other-group-fallback-{stage}", f"fallback-{stage}",
            f"fine-bucket-{stage}", f"fine-local-{stage}",
            f"fine-winner-{stage}", f"best-bucket-{stage}",
            f"best-winner-{stage}",
        ))
        if stage:
            names.extend((f"score-delta-{stage}", f"use-stage-{stage}"))
    for stage in range(1, STAGES + 1):
        names.extend((
            f"upper-mask-{stage}", f"upper-bucket-{stage}",
            f"remaining-group-{stage}", f"certificate-gap-{stage - 1}",
            f"done-{stage - 1}",
        ))
    return "".join(integration.property_registration(name) for name in names)


def build_html(split: str, exact: str, groups: int) -> str:
    tail = integration.router_markup(STAGES, groups, "")
    for stage in range(STAGES - 1, 0, -1):
        tail = integration.router_markup(
            stage, groups, stage_markup(stage, split, exact, tail)
        )
    replacement = stage_markup(0, split, exact, tail)
    html = (ONE_STEP / "index.html").read_text()
    old = (
        '<span id="fine-stage" class="fine-stage">' + exact
        + '</span><span class="fine-reader">'
        + '<i id="fine-result" class="fine-result"></i></span>'
    )
    if html.count(old) != 1:
        raise RuntimeError("one-step fine stage insertion point changed")
    html = html.replace(old, replacement, 1)
    html = html.replace(
        '<link rel="stylesheet" href="index.css">',
        '<link rel="stylesheet" href="../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">'
        '<link rel="stylesheet" href="split-bank.css">'
        '<link rel="stylesheet" href="topology.css">',
        1,
    )
    return html.replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Six-stage certified int10 hot-two GSUB output head",
        1,
    )


def main() -> None:
    required = [
        ONE_STEP / name for name in ("index.html", "index.css", "reference.json")
    ] + [
        BASELINE / name for name in ("index.html", "index.css", "reference.json")
    ] + [
        SPLIT_GSUB / name for name in (
            "index.html", "index.css", "reference.json", "browser-results.json"
        )
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)
    baseline = json.loads((BASELINE / "reference.json").read_text())
    split_reference = json.loads((SPLIT_GSUB / "reference.json").read_text())
    split_results = json.loads((SPLIT_GSUB / "browser-results.json").read_text())
    if baseline["exactStages"] != STAGES or not baseline["stageGating"]:
        raise RuntimeError("baseline must be the gated exact six-stage head")
    if split_reference["groupIds"] != [0, 1]:
        raise RuntimeError("hot-two bank must cover exactly groups 0 and 1")
    gate = split_results["conservativeGate"]
    if (
        split_results["winnerTokenMatches"] != 20
        or gate["winnerMarginThresholdBuckets"] != MARGIN_THRESHOLD
        or gate["unsafeAccepts"] != 0
    ):
        raise RuntimeError("split-complement source certification changed")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    split = integration.split_gsub_candidates()
    exact = integration.exact_candidates()
    geometry = build_split_bank_css()
    (OUTPUT / "index.html").write_text(
        build_html(split, exact, int(baseline["groups"]))
    )
    css = [registrations(), "*{box-sizing:border-box}html,body{margin:0;overflow:clip}"]
    selected = ["selected-group-0"]
    for router_stage in range(1, STAGES + 1):
        css.append(integration.router_css(router_stage, int(baseline["groups"]), selected))
        selected.append(f"selected-group-{router_stage}")
    css.extend(stage_css(stage) for stage in range(STAGES))
    (OUTPUT / "topology.css").write_text("".join(css) + "\n")

    reference = {
        "backend": "certified-int10-six-stage-gated-hot-two-split-gsub-exact",
        "sourceBaseline": BASELINE.name,
        "sourceOneStep": ONE_STEP.name,
        "sourceSplitGsub": SPLIT_GSUB.name,
        "stages": STAGES,
        "groups": int(baseline["groups"]),
        "groupSize": int(baseline["groupSize"]),
        "marginThresholdBuckets": MARGIN_THRESHOLD,
        "routingRule": (
            "groups 0/1 use split-GSUB top-two and accept at margin >4; "
            "margin <=4 and every group >=2 use exact"
        ),
        "stageGating": True,
        "javascriptSelectsWinner": False,
        "javascriptRole": "select fixture, mutate hidden input, and observe layout only",
        "immutableVisitedGroupProperties": [
            f"--selected-group-{stage}" for stage in range(STAGES)
        ],
        "certifiedFixtures": baseline["certifiedFixtures"],
        "candidateGeometry": geometry,
        "sourceCertification": {
            "winnerTokenMatches": split_results["winnerTokenMatches"],
            "candidateComparisons": split_results["candidateComparisons"],
            "maximumAbsoluteCandidateDelta": split_results[
                "maximumAbsoluteCandidateDelta"
            ],
            "marginThresholdBuckets": gate["winnerMarginThresholdBuckets"],
            "acceptedCases": gate["acceptedCases"],
            "fallbackCases": gate["fallbackCases"],
            "unsafeAccepts": gate["unsafeAccepts"],
            "empiricalOnly": gate["empiricalOnly"],
            "portableBoundProved": gate["portableBoundProved"],
        },
        "reusedAssets": {
            "splitGsubFontDirectory": "../gsub-split-complement-fine-scorer",
            "splitGsubWoff2Bytes": split_reference["fontWoff2Bytes"],
            "exactFontDirectory": (
                "../gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
            ),
            "exactWoff2Bytes": split_reference["baselineFineWoff2Bytes"],
            "fullGsubBankIncludedOrReferenced": False,
            "fontsCopiedOrRebuilt": False,
        },
        "topology": {
            "splitTopCandidateElementsPerStage": 256,
            "splitRunnerCandidateElementsPerStage": 256,
            "exactCandidateElementsPerStageWhenActive": 256,
            "fullGsubCandidateElements": 0,
        },
        "generatedBytes": {},
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("index.html", "split-bank.css", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    generated_text = "\n".join(
        (OUTPUT / name).read_text()
        for name in ("index.html", "split-bank.css", "topology.css")
    )
    forbidden = ("gsub-indexed-fine-scorer/full", "full-gsub-stage")
    if any(value in generated_text for value in forbidden):
        raise RuntimeError("generated hot-two head references the full GSUB bank")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (
            (OUTPUT / "split-bank.css").stat().st_size
            + (OUTPUT / "topology.css").stat().st_size
        ),
        "splitGsubWoff2BytesReused": split_reference["fontWoff2Bytes"],
        "fullGsubBankIncludedOrReferenced": False,
        "fontsCopiedOrRebuilt": False,
    }, indent=2))


if __name__ == "__main__":
    main()
