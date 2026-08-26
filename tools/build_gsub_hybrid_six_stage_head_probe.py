#!/usr/bin/env python3
"""Build a six-stage certified head with GSUB top-two/exact hybrid fine stages."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_NAME = (
    "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hybrid"
)
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
ONE_STEP = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
)
BASELINE = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated"
)
GSUB = ROOT / "experiments" / "gsub-indexed-fine-scorer" / "full"
SPLIT_GSUB = ROOT / "experiments" / "gsub-split-complement-fine-scorer"
HYBRID_SCREEN = ROOT / "experiments" / "gsub-certified-hybrid" / "full-screen"
STAGES = 6
MARGIN_THRESHOLD = 6
SPLIT_MARGIN_THRESHOLD = 4
FINAL_PARTIAL_GROUP = 196
SLACK_BUCKETS = 24


def property_registration(name: str) -> str:
    return f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'


def router_markup(stage: int, groups: int, child: str) -> str:
    sources = "".join(
        f'<i class="upper-source-{stage} upper-source-{stage}-{group}"></i>'
        for group in range(groups)
    )
    matches = "".join(
        f'<i class="upper-match-{stage} upper-match-{stage}-{group}"></i>'
        for group in range(groups)
    )
    return (
        f'<span class="upper-sources-{stage}">{sources}</span>'
        f'<i class="upper-max-{stage}"></i>'
        f'<span class="upper-reader-{stage}"><span class="upper-selection-{stage}">'
        + matches
        + f'<i class="upper-group-choice-{stage}"></i>'
        f'<span class="upper-group-reader-{stage}">'
        f'<output id="remaining-result-{stage}" class="remaining-result-{stage}">'
        + child
        + "</output></span></span></span>"
    )


def router_css(stage: int, groups: int, selected_properties: list[str]) -> str:
    def mask_value(group: int) -> str:
        selected_terms = ",".join(
            f"abs(var(--{name}) - {group})" for name in selected_properties
        )
        return f"clamp(0,min({selected_terms}),1)"

    source_rules = "".join(
        f".upper-source-{stage}-{group}{{"
        f"--upper-mask-{stage}:{mask_value(group)};"
        f"position-anchor:--score-group-{group};"
        f"anchor-name:--upper-source-{stage}-{group};"
        f"width:calc(anchor-size(--score-group-{group} width) * "
        f"var(--upper-mask-{stage}))}}"
        for group in range(groups)
    )
    source_sizes = ",".join(
        f"anchor-size(--upper-source-{stage}-{group} width)"
        for group in range(groups)
    )
    match_rules = "".join(
        f".upper-match-{stage}-{group}{{"
        f"position-anchor:--upper-source-{stage}-{group};"
        f"anchor-name:--upper-match-{stage}-{group};"
        f"width:calc(clamp(0px,anchor-size(--upper-source-{stage}-{group} width) - "
        f"(var(--upper-bucket-{stage}) - .5)*4px,1px)*{groups - group})}}"
        for group in range(groups)
    )
    match_sizes = ",".join(
        f"anchor-size(--upper-match-{stage}-{group} width)"
        for group in range(groups)
    )
    threshold = 2 * SLACK_BUCKETS
    fixed = (
        f".upper-source-{stage},.upper-max-{stage},.upper-reader-{stage},"
        f".upper-match-{stage},.upper-group-choice-{stage},"
        f".upper-group-reader-{stage},.remaining-result-{stage}{{"
        f"position:fixed;left:0;top:{-60_000 + stage * 20}px;height:1px}}"
    )
    return (
        fixed
        + source_rules
        + f".upper-max-{stage}{{position-anchor:--upper-source-{stage}-0;"
        f"anchor-name:--upper-max-anchor-{stage};width:max({source_sizes})}}"
        + f".upper-reader-{stage}{{position-anchor:--upper-max-anchor-{stage};"
        f"width:anchor-size(--upper-max-anchor-{stage} width);"
        f"container:upper-result-{stage}/inline-size}}"
        + f"@container upper-result-{stage} (width >= 0px){{"
        f".upper-selection-{stage}{{--upper-bucket-{stage}:"
        "round(down,100cqi/4px,1)}"
        + match_rules
        + f".upper-group-choice-{stage}{{position-anchor:--upper-match-{stage}-0;"
        f"anchor-name:--upper-group-choice-anchor-{stage};"
        f"width:max({match_sizes})}}"
        + f".upper-group-reader-{stage}{{"
        f"position-anchor:--upper-group-choice-anchor-{stage};"
        f"width:anchor-size(--upper-group-choice-anchor-{stage} width);"
        f"container:upper-group-result-{stage}/inline-size}}"
        + f"@container upper-group-result-{stage} (width >= 0px){{"
        f".remaining-result-{stage}{{"
        f"--remaining-group-{stage}:calc({groups} - "
        "round(nearest,100cqi/1px,1));"
        f"--certificate-gap-{stage - 1}:calc(var(--best-bucket-{stage - 1}) - "
        f"var(--upper-bucket-{stage}));"
        f"--done-{stage - 1}:clamp(0,sign(var(--certificate-gap-{stage - 1}) - "
        f"{threshold + 1}) + 1,1);display:block;"
        f"width:calc(var(--remaining-group-{stage})*1px);height:1px}}}}}}"
    )


def extract_between(text: str, start: str, stop: str) -> str:
    begin = text.index(start) + len(start)
    return text[begin : text.index(stop, begin)]


def exact_candidates() -> str:
    return extract_between(
        (ONE_STEP / "index.html").read_text(),
        '<span id="fine-stage" class="fine-stage">',
        '</span><span class="fine-reader">',
    )


def gsub_candidates() -> str:
    raw = extract_between(
        (GSUB / "index.html").read_text(),
        '<main id="gsub-stage" class="fine-stage">',
        "</main>",
    )
    candidates = re.findall(r'<i class="candidate"[^>]*>.*?</i>', raw)
    if len(candidates) != 256:
        raise RuntimeError(f"expected 256 GSUB candidates, found {len(candidates)}")
    rendered = []
    for local, candidate in enumerate(candidates):
        candidate = candidate.replace('class="candidate"', 'class="gsub-candidate"')
        candidate = candidate.replace(
            'style="--local-tie:', f'style="--local:{local};--local-tie:'
        )
        rendered.append(candidate)
    return "".join(rendered)


def split_gsub_candidates() -> str:
    raw = extract_between(
        (SPLIT_GSUB / "index.html").read_text(),
        '<main id="gsub-stage" class="fine-stage">',
        "</main>",
    )
    candidates = re.findall(r'<i class="candidate"[^>]*>.*?</i>', raw)
    if len(candidates) != 256:
        raise RuntimeError(f"expected 256 split GSUB candidates, found {len(candidates)}")
    rendered = []
    for local, candidate in enumerate(candidates):
        candidate = candidate.replace(
            'class="candidate"', 'class="split-gsub-candidate"'
        )
        candidate = candidate.replace(
            'style="--local-tie:', f'style="--local:{local};--local-tie:'
        )
        rendered.append(candidate)
    return "".join(rendered)


def build_bank_css(feature_values: dict[str, int], groups: int) -> dict:
    css = (GSUB / "index.css").read_text()
    geometry = re.search(
        r"\(size - ([0-9.]+)px\)\*([0-9.]+) \+ var\(--score-offset\)", css
    )
    if not geometry:
        raise RuntimeError("GSUB candidate geometry is missing")
    base, factor = geometry.groups()
    source_expression = f"(size - {base}px)*{factor} + var(--score-offset)"
    if css.count(source_expression) != 1:
        raise RuntimeError("GSUB candidate geometry is not unique")

    # CSS is generated locally, but every font URL remains pointed at the existing bank.
    css = css.replace('url("', 'url("../gsub-indexed-fine-scorer/full/')
    css = css.replace(".fine-stage", ".gsub-stage")
    css = css.replace(".candidate", ".gsub-candidate")
    mapping = ";".join(
        f"style(--group:{group}):{feature_values[str(group)]}"
        for group in range(groups)
    )
    css += (
        f".gsub-stage{{--score-offset:inherit;--probe-feature:if({mapping};else:1)}}"
        ".gsub-stage .gsub-candidate{"
        "--invalid-mask:if(style(--group:196):clamp(0,var(--local) - 80,1);else:0);"
        "width:calc-size(max-content,calc(round(nearest,"
        f"{source_expression},4px) + var(--local-tie)/64*1px "
        "- var(--invalid-mask)*100000px))}"
        ".gsub-runner .gsub-candidate{"
        "--winner-mask:clamp(0,1 - abs(var(--stage-top-local) - var(--local)),1);"
        "width:calc-size(max-content,calc(round(nearest,"
        f"{source_expression},4px) + var(--local-tie)/64*1px "
        "- max(var(--winner-mask),var(--invalid-mask))*100000px))}\n"
    )
    (OUTPUT / "bank.css").write_text(css)
    return {"basePx": float(base), "factor": float(factor)}


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


def hybrid_markup(
    stage: int, gsub: str, split_gsub: str, exact: str, child: str
) -> str:
    result_id = "fine-result" if stage == 0 else f"fine-result-{stage}"
    return (
        f'<span id="hybrid-stage-{stage}" class="hybrid-stage hybrid-stage-{stage}">'
        f'<span id="gsub-top-{stage}" class="gsub-stage full-gsub-stage '
        f'gsub-top gsub-top-{stage}">'
        f"{gsub}</span>"
        f'<span id="split-gsub-top-{stage}" class="split-gsub-stage '
        f'split-gsub-top split-gsub-top-{stage}">{split_gsub}</span>'
        f'<span class="hybrid-top-reader hybrid-top-reader-{stage}">'
        f'<span id="hybrid-top-decode-{stage}" class="hybrid-top-decode-{stage}">'
        f'<span id="gsub-runner-{stage}" class="gsub-stage full-gsub-stage '
        f'gsub-runner '
        f'gsub-runner-{stage}">{gsub}</span>'
        f'<span id="split-gsub-runner-{stage}" class="split-gsub-stage '
        f'split-gsub-runner split-gsub-runner-{stage}">{split_gsub}</span>'
        f'<span class="hybrid-runner-reader hybrid-runner-reader-{stage}">'
        f'<span id="hybrid-decision-{stage}" class="hybrid-decision-{stage}">'
        f'<span id="exact-stage-{stage}" class="fine-stage exact-stage '
        f'exact-stage-{stage}">{exact}</span>'
        f'<i id="hybrid-choice-source-{stage}" '
        f'class="hybrid-choice-source hybrid-choice-source-{stage}"></i>'
        f'<span class="hybrid-final-reader hybrid-final-reader-{stage}">'
        f'<i id="{result_id}" class="hybrid-fine-result '
        f'hybrid-fine-result-{stage}">{child}</i>'
        "</span></span></span></span></span></span>"
    )


def hybrid_stage_css(stage: int) -> str:
    top = -95_000 + stage * 600
    runner = top + 200
    choice = top + 400
    gate = "display:contents;" if stage == 0 else (
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
        state = (
            f"--best-bucket-0:var(--fine-bucket-0);"
            f"--best-winner-0:var(--fine-winner-0);"
        )
    else:
        previous = stage - 1
        state = (
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
    return (
        f".hybrid-stage-{stage}{{{gate}}}"
        f".gsub-top-{stage}{{{group_binding}top:{top}px;"
        f"anchor-name:--gsub-top-winner-{stage};"
        f"display:if(style(--group:0):none;style(--group:1):none;else:grid)}}"
        f".split-gsub-top-{stage}{{{group_binding}top:{top}px;"
        f"anchor-name:--gsub-top-winner-{stage};"
        f"display:if(style(--group:0):grid;style(--group:1):grid;else:none)}}"
        f".hybrid-top-reader-{stage}{{position:fixed;left:0;top:{top + 100}px;"
        f"height:1px;position-anchor:--gsub-top-winner-{stage};"
        f"width:anchor-size(--gsub-top-winner-{stage} width);"
        f"container:gsub-top-readback-{stage}/inline-size}}"
        f"@container gsub-top-readback-{stage} (width >= 0px){{"
        f".hybrid-top-decode-{stage}{{{group_binding}"
        f"--top-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--top-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--stage-top-local:var(--top-local-{stage})}}"
        f".gsub-runner-{stage}{{{group_binding}top:{runner}px;"
        f"anchor-name:--gsub-runner-winner-{stage};"
        f"display:if(style(--group:0):none;style(--group:1):none;else:grid)}}"
        f".split-gsub-runner-{stage}{{{group_binding}top:{runner}px;"
        f"anchor-name:--gsub-runner-winner-{stage};"
        f"display:if(style(--group:0):grid;style(--group:1):grid;else:none)}}"
        f".hybrid-runner-reader-{stage}{{position:fixed;left:0;top:{runner + 100}px;"
        f"height:1px;position-anchor:--gsub-runner-winner-{stage};"
        f"width:anchor-size(--gsub-runner-winner-{stage} width);"
        f"container:gsub-runner-readback-{stage}/inline-size}}"
        f"@container gsub-runner-readback-{stage} (width >= 0px){{"
        f".hybrid-decision-{stage}{{{group_binding}"
        f"--runner-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--runner-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--margin-{stage}:calc(var(--top-bucket-{stage}) - "
        f"var(--runner-bucket-{stage}));"
        f"--partial-fallback-{stage}:clamp(0,1 - "
        f"abs(var(--group) - {FINAL_PARTIAL_GROUP}),1);"
        f"--split-route-{stage}:clamp(0,2 - var(--group),1);"
        f"--margin-threshold-{stage}:calc(var(--split-route-{stage})*"
        f"{SPLIT_MARGIN_THRESHOLD} + (1 - var(--split-route-{stage}))*"
        f"{MARGIN_THRESHOLD});"
        f"--near-fallback-{stage}:clamp(0,var(--margin-threshold-{stage}) + 1 - "
        f"var(--margin-{stage}),1);"
        f"--forced-fallback-{stage}:var(--partial-fallback-{stage});"
        f"--fallback-{stage}:max(var(--partial-fallback-{stage}),"
        f"var(--near-fallback-{stage}))}}"
        f".exact-stage-{stage}{{{group_binding}top:{choice}px;"
        f"anchor-name:--exact-winner-{stage};"
        f"display:if(style(--fallback-{stage}:1):grid;else:none)}}"
        f".hybrid-choice-source-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{choice + 100}px;"
        f"height:1px;anchor-name:--hybrid-winner-{stage};"
        f"width:if(style(--fallback-{stage}:1):"
        f"anchor-size(--exact-winner-{stage} width);else:"
        f"anchor-size(--gsub-top-winner-{stage} width))}}"
        f".hybrid-final-reader-{stage}{{position:fixed;left:0;top:{choice + 200}px;"
        f"height:1px;position-anchor:--hybrid-winner-{stage};"
        f"width:anchor-size(--hybrid-winner-{stage} width);"
        f"container:hybrid-fine-result-{stage}/inline-size}}"
        f"@container hybrid-fine-result-{stage} (width >= 0px){{"
        f".hybrid-fine-result-{stage}{{{result_group}"
        f"--fine-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--fine-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--fine-winner-{stage}:calc({fine_group}*256 + "
        f"var(--fine-local-{stage}));{state}"
        f"display:block;width:calc(var(--best-winner-{stage})*1px);height:1px}}"
        "}}}}"
    )


def property_registrations(groups: int) -> str:
    names: list[str] = []
    for stage in range(STAGES):
        names.append(f"selected-group-{stage}")
        names.extend(
            [
                f"top-bucket-{stage}",
                f"top-local-{stage}",
                f"runner-bucket-{stage}",
                f"runner-local-{stage}",
                f"margin-{stage}",
                f"forced-fallback-{stage}",
                f"partial-fallback-{stage}",
                f"split-route-{stage}",
                f"margin-threshold-{stage}",
                f"near-fallback-{stage}",
                f"fallback-{stage}",
                f"fine-bucket-{stage}",
                f"fine-local-{stage}",
                f"fine-winner-{stage}",
                f"best-bucket-{stage}",
                f"best-winner-{stage}",
            ]
        )
        if stage:
            names.extend([f"score-delta-{stage}", f"use-stage-{stage}"])
    for stage in range(1, STAGES + 1):
        names.extend(
            [
                f"upper-mask-{stage}",
                f"upper-bucket-{stage}",
                f"remaining-group-{stage}",
                f"certificate-gap-{stage - 1}",
                f"done-{stage - 1}",
            ]
        )
    return "".join(property_registration(name) for name in names)


def build_html(gsub: str, split_gsub: str, exact: str, groups: int) -> str:
    tail = router_markup(STAGES, groups, "")
    for stage in range(STAGES - 1, 0, -1):
        tail = router_markup(
            stage, groups, hybrid_markup(stage, gsub, split_gsub, exact, tail)
        )
    replacement = hybrid_markup(0, gsub, split_gsub, exact, tail)

    html = (ONE_STEP / "index.html").read_text()
    old = (
        '<span id="fine-stage" class="fine-stage">'
        + exact
        + '</span><span class="fine-reader">'
        + '<i id="fine-result" class="fine-result"></i></span>'
    )
    if html.count(old) != 1:
        raise RuntimeError("one-step fine stage insertion point changed")
    html = html.replace(old, replacement, 1)
    html = html.replace(
        '<link rel="stylesheet" href="index.css">',
        '<link rel="stylesheet" href="../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">'
        '<link rel="stylesheet" href="bank.css">'
        '<link rel="stylesheet" href="split-bank.css">'
        '<link rel="stylesheet" href="topology.css">',
        1,
    )
    return html.replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Six-stage certified int10 GSUB hybrid output head",
        1,
    )


def main() -> None:
    required = [
        ONE_STEP / name for name in ("index.html", "index.css", "reference.json")
    ] + [
        BASELINE / name for name in ("reference.json", "index.html", "index.css")
    ] + [
        GSUB / name for name in ("index.html", "index.css", "reference.json")
    ] + [
        HYBRID_SCREEN / "reference.json",
        SPLIT_GSUB / "reference.json",
        SPLIT_GSUB / "browser-results.json",
        SPLIT_GSUB / "index.html",
        SPLIT_GSUB / "index.css",
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    baseline = json.loads((BASELINE / "reference.json").read_text())
    gsub_reference = json.loads((GSUB / "reference.json").read_text())
    hybrid_reference = json.loads((HYBRID_SCREEN / "reference.json").read_text())
    split_reference = json.loads((SPLIT_GSUB / "reference.json").read_text())
    split_results = json.loads((SPLIT_GSUB / "browser-results.json").read_text())
    groups = int(baseline["groups"])
    if groups != 197 or gsub_reference["groupIds"] != list(range(groups)):
        raise RuntimeError("expected one full contiguous 197-group GSUB bank")
    feature_values = gsub_reference["featureValues"]
    if [feature_values[str(group)] for group in range(groups)] != list(range(1, 198)):
        raise RuntimeError("expected numbered cv01 feature values 1..197")
    if baseline["exactStages"] != STAGES or not baseline["stageGating"]:
        raise RuntimeError("baseline must be the gated exact six-stage head")
    if split_reference["groupIds"] != [0, 1]:
        raise RuntimeError("split-complement bank must cover exactly groups 0 and 1")
    split_gate = split_results["conservativeGate"]
    if (
        split_results["winnerTokenMatches"] != 20
        or split_gate["winnerMarginThresholdBuckets"] != SPLIT_MARGIN_THRESHOLD
        or split_gate["unsafeAccepts"] != 0
    ):
        raise RuntimeError("split-complement source certification changed")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    gsub = gsub_candidates()
    split_gsub = split_gsub_candidates()
    exact = exact_candidates()
    geometry = build_bank_css(feature_values, groups)
    split_geometry = build_split_bank_css()
    html = build_html(gsub, split_gsub, exact, groups)
    (OUTPUT / "index.html").write_text(html)

    css = [
        property_registrations(groups),
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
    ]
    selected_properties = ["selected-group-0"]
    for router_stage in range(1, STAGES + 1):
        css.append(router_css(router_stage, groups, selected_properties))
        selected_properties.append(f"selected-group-{router_stage}")
    for fine_stage in range(STAGES):
        css.append(hybrid_stage_css(fine_stage))
    (OUTPUT / "topology.css").write_text("".join(css) + "\n")

    source_cases = {
        (item["fixture"], item["group"]): item
        for item in hybrid_reference["cases"]
    }
    fixtures = baseline["certifiedFixtures"]
    selected_routes = []
    for fixture, stage_groups in enumerate(fixtures["unrolledStageGroups"]):
        routes = []
        for group in stage_groups:
            source = source_cases[(fixture, group)]
            partial = group == FINAL_PARTIAL_GROUP
            if group <= 1:
                split_case = next(
                    item for item in split_results["comparisons"]
                    if item["fixture"] == fixture and item["group"] == group
                )
                margin = split_case["gsubWinner"]["marginBuckets"]
                near = margin <= SPLIT_MARGIN_THRESHOLD
            else:
                split_case = None
                margin = source["sourceMarginBuckets"]
                near = margin <= MARGIN_THRESHOLD
            source_top_local = (
                split_case["gsubWinner"]["winnerLocal"]
                if split_case else source["sourceGsubTopLocal"]
            )
            source_top_bucket = (
                split_case["gsubWinner"]["winnerBucket"]
                if split_case else source["sourceGsubTopBucket"]
            )
            source_runner_local = (
                split_case["gsubWinner"]["runnerLocal"]
                if split_case else source["sourceGsubRunnerLocal"]
            )
            source_runner_bucket = (
                split_case["gsubWinner"]["runnerBucket"]
                if split_case else source["sourceGsubRunnerBucket"]
            )
            routes.append(
                {
                    "group": group,
                    "bank": "split-complement" if group <= 1 else "full",
                    "sourceTopLocal": source_top_local,
                    "sourceTopBucket": source_top_bucket,
                    "sourceRunnerLocal": source_runner_local,
                    "sourceRunnerBucket": source_runner_bucket,
                    "sourceMarginBuckets": margin,
                    "expectedFallback": partial or near,
                    "forcedGroup01": False,
                    "forcedPartialGroup": partial,
                }
            )
        selected_routes.append(routes)

    reference = {
        "backend": "certified-int10-six-stage-gated-gsub-top-two-exact-hybrid",
        "sourceBaseline": BASELINE.name,
        "sourceOneStep": ONE_STEP.name,
        "sourceGsub": "gsub-indexed-fine-scorer/full",
        "stages": STAGES,
        "groups": groups,
        "groupSize": baseline["groupSize"],
        "marginThresholdBuckets": MARGIN_THRESHOLD,
        "splitMarginThresholdBuckets": SPLIT_MARGIN_THRESHOLD,
        "fallbackRule": (
            "rendered split-complement margin <= 4 for groups 0/1; rendered "
            "full-GSUB margin <= 6 for groups 2..195; force partial group 196"
        ),
        "stageGating": True,
        "javascriptSelectsWinner": False,
        "javascriptRole": "select fixture, mutate hidden input, and observe layout only",
        "candidateGeometry": geometry,
        "splitCandidateGeometry": split_geometry,
        "certifiedFixtures": fixtures,
        "selectedStageSourceRoutes": selected_routes,
        "reusedAssets": {
            "gsubFontDirectory": "../gsub-indexed-fine-scorer/full",
            "gsubWoff2Bytes": gsub_reference["fontWoff2Bytes"],
            "splitGsubFontDirectory": "../gsub-split-complement-fine-scorer",
            "splitGsubWoff2Bytes": split_reference["fontWoff2Bytes"],
            "exactFontDirectory": (
                "../gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
            ),
            "exactWoff2Bytes": gsub_reference["baselineFineWoff2Bytes"],
            "fontsCopiedOrRebuilt": False,
        },
        "empiricalBound": {
            "empiricalOnly": hybrid_reference["empiricalOnly"],
            "portableBoundProved": hybrid_reference["portableBoundProved"],
            "candidateDeltaBuckets": hybrid_reference["empiricalCandidateDeltaBound"],
            "splitCandidateDeltaBuckets": split_results[
                "maximumAbsoluteCandidateDelta"
            ],
        },
        "topologyStrategy": (
            "per-stage conditional grids: split-complement GSUB only for groups "
            "0/1, full 197-group GSUB only for groups 2..196; shared top/runner "
            "anchors and one conditional exact fallback grid"
        ),
        "generatedBytes": {},
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in (
            "index.html", "bank.css", "split-bank.css", "topology.css",
            "reference.json",
        )
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "stages": STAGES,
                "groups": groups,
                "htmlBytes": (OUTPUT / "index.html").stat().st_size,
                "topologyCssBytes": (OUTPUT / "topology.css").stat().st_size,
                "gsubCssBytes": (OUTPUT / "bank.css").stat().st_size,
                "splitGsubCssBytes": (OUTPUT / "split-bank.css").stat().st_size,
                "fontsCopiedOrRebuilt": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
