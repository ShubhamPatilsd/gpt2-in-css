#!/usr/bin/env python3
"""Build a six-stage exact head with root-precomputed groups 0 and 1."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_NAME = (
    "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-hot2-precomputed"
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
FINE_FONT_BANK = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
)
STAGES = 6
HOT_GROUPS = (0, 1)
SLACK_BUCKETS = 24


def property_registration(name: str) -> str:
    return f'@property --{name}{{syntax:"<number>";inherits:true;initial-value:0}}'


def extract_between(text: str, start: str, stop: str) -> str:
    begin = text.index(start) + len(start)
    return text[begin : text.index(stop, begin)]


def exact_candidates() -> str:
    return extract_between(
        (ONE_STEP / "index.html").read_text(),
        '<span id="fine-stage" class="fine-stage">',
        '</span><span class="fine-reader">',
    )


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


def hot_cache_markup(candidates: str) -> str:
    return "".join(
        f'<span id="hot-cache-grid-{group}" '
        f'class="fine-stage hot-cache-grid hot-cache-grid-{group}">'
        f"{candidates}</span>"
        f'<span class="hot-cache-reader hot-cache-reader-{group}">'
        f'<i id="hot-cache-result-{group}" '
        f'class="hot-cache-result hot-cache-result-{group}"></i></span>'
        for group in HOT_GROUPS
    )


def stage_markup(stage: int, candidates: str, child: str) -> str:
    result_id = "fine-result" if stage == 0 else f"fine-result-{stage}"
    return (
        f'<span id="hot2-stage-{stage}" class="hot2-stage hot2-stage-{stage}">'
        f'<span id="dynamic-fine-stage-{stage}" '
        f'class="fine-stage dynamic-fine-stage dynamic-fine-stage-{stage}">'
        f"{candidates}</span>"
        f'<i id="hot2-choice-source-{stage}" '
        f'class="hot2-choice-source hot2-choice-source-{stage}"></i>'
        f'<span class="hot2-final-reader hot2-final-reader-{stage}">'
        f'<i id="{result_id}" class="hot2-fine-result '
        f'hot2-fine-result-{stage}">{child}</i>'
        "</span></span>"
    )


def hot_cache_css(group: int) -> str:
    top = -96_000 + group * 200
    return (
        f".hot-cache-grid-{group}{{--group:{group};top:{top}px;"
        f"anchor-name:--hot-cache-winner-{group}}}"
        f".hot-cache-reader-{group}{{position:fixed;left:0;top:{top + 100}px;"
        f"height:1px;position-anchor:--hot-cache-winner-{group};"
        f"width:anchor-size(--hot-cache-winner-{group} width);"
        f"container:hot-cache-readback-{group}/inline-size}}"
        f"@container hot-cache-readback-{group} (width >= 0px){{"
        f".hot-cache-result-{group}{{"
        f"--hot-fine-bucket-{group}:round(down,(100cqi + .001px)/4px,1);"
        f"--hot-fine-local-{group}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--hot-fine-winner-{group}:calc({group}*256 + "
        f"var(--hot-fine-local-{group}));display:block;"
        f"width:calc(var(--hot-fine-winner-{group})*1px);height:1px}}}}"
    )


def stage_css(stage: int) -> str:
    top = -92_000 + stage * 300
    gate = "display:contents;" if stage == 0 else (
        f"display:if(style(--done-{stage - 1}:1):none;else:contents);"
    )
    group_binding = "" if stage == 0 else f"--group:var(--remaining-group-{stage});"
    selected_group = "var(--group)" if stage == 0 else (
        f"var(--remaining-group-{stage})"
    )
    result_group = (
        "--search-root-group:var(--group);--selected-group-0:var(--group);"
        if stage == 0
        else (
            "--group:var(--search-root-group);"
            f"--selected-group-{stage}:var(--remaining-group-{stage});"
        )
    )
    if stage == 0:
        state = (
            "--best-bucket-0:var(--fine-bucket-0);"
            "--best-winner-0:var(--fine-winner-0);"
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
        f".hot2-stage-{stage}{{{gate}}}"
        f".dynamic-fine-stage-{stage}{{{group_binding}top:{top}px;"
        f"anchor-name:--dynamic-fine-winner-{stage};"
        "display:if(style(--group:0):none;style(--group:1):none;else:grid)}"
        f".hot2-choice-source-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{top + 100}px;height:1px;anchor-name:--hot2-winner-{stage};"
        "width:if(style(--group:0):"
        "anchor-size(--hot-cache-winner-0 width);style(--group:1):"
        "anchor-size(--hot-cache-winner-1 width);else:"
        f"anchor-size(--dynamic-fine-winner-{stage} width))}}"
        f".hot2-final-reader-{stage}{{position:fixed;left:0;top:{top + 200}px;"
        f"height:1px;position-anchor:--hot2-winner-{stage};"
        f"width:anchor-size(--hot2-winner-{stage} width);"
        f"container:hot2-fine-result-{stage}/inline-size}}"
        f"@container hot2-fine-result-{stage} (width >= 0px){{"
        f".hot2-fine-result-{stage}{{{result_group}"
        f"--fine-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--fine-local-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--fine-winner-{stage}:calc({selected_group}*256 + "
        f"var(--fine-local-{stage}));{state}display:block;"
        f"width:calc(var(--best-winner-{stage})*1px);height:1px}}}}"
    )


def property_registrations() -> str:
    names: list[str] = []
    for group in HOT_GROUPS:
        names.extend(
            [
                f"hot-fine-bucket-{group}",
                f"hot-fine-local-{group}",
                f"hot-fine-winner-{group}",
            ]
        )
    for stage in range(STAGES):
        names.extend(
            [
                f"selected-group-{stage}",
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


def build_html(candidates: str, groups: int) -> str:
    tail = router_markup(STAGES, groups, "")
    for stage in range(STAGES - 1, 0, -1):
        tail = router_markup(stage, groups, stage_markup(stage, candidates, tail))
    replacement = stage_markup(0, candidates, tail)

    html = (ONE_STEP / "index.html").read_text()
    old = (
        '<span id="fine-stage" class="fine-stage">'
        + candidates
        + '</span><span class="fine-reader">'
        + '<i id="fine-result" class="fine-result"></i></span>'
    )
    if html.count(old) != 1:
        raise RuntimeError("one-step fine stage insertion point changed")
    html = html.replace(old, replacement, 1)
    cache_insertion = '<div class="cascade"><main id="model" class="model">'
    if html.count(cache_insertion) != 1:
        raise RuntimeError("cascade root insertion point changed")
    html = html.replace(
        cache_insertion,
        '<div class="cascade">'
        + hot_cache_markup(candidates)
        + '<main id="model" class="model">',
        1,
    )
    html = html.replace(
        '<link rel="stylesheet" href="index.css">',
        '<link rel="stylesheet" '
        'href="../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">'
        '<link rel="stylesheet" href="topology.css">',
        1,
    )
    return html.replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Six-stage exact output head with root-precomputed hot groups 0 and 1",
        1,
    )


def main() -> None:
    required = [
        ONE_STEP / name for name in ("index.html", "index.css", "reference.json")
    ] + [
        BASELINE / name for name in ("index.html", "index.css", "reference.json")
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    baseline = json.loads((BASELINE / "reference.json").read_text())
    groups = int(baseline["groups"])
    if groups != 197:
        raise RuntimeError("expected the complete 197-group baseline")
    if baseline["exactStages"] != STAGES or not baseline["stageGating"]:
        raise RuntimeError("baseline must be the gated exact six-stage head")
    fixtures = baseline["certifiedFixtures"]
    stage_groups = fixtures["unrolledStageGroups"]
    if not any(groups_[0:2] == [1, 0] for groups_ in stage_groups):
        raise RuntimeError("fixture corpus no longer covers group order 1 then 0")
    if not any(any(group > 1 for group in groups_[:3]) for groups_ in stage_groups):
        raise RuntimeError("fixture corpus no longer covers an active non-hot stage")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates = exact_candidates()
    candidate_count = len(re.findall(r'<i class="fine-candidate"', candidates))
    if candidate_count != 256:
        raise RuntimeError(f"expected 256 exact candidates, found {candidate_count}")
    (OUTPUT / "index.html").write_text(build_html(candidates, groups))

    css = [
        property_registrations(),
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
    ]
    for group in HOT_GROUPS:
        css.append(hot_cache_css(group))
    selected_properties = ["selected-group-0"]
    for router_stage in range(1, STAGES + 1):
        css.append(router_css(router_stage, groups, selected_properties))
        selected_properties.append(f"selected-group-{router_stage}")
    for fine_stage in range(STAGES):
        css.append(stage_css(fine_stage))
    (OUTPUT / "topology.css").write_text("".join(css) + "\n")

    font_files = sorted(FINE_FONT_BANK.glob("score-*.woff2"))
    reference = {
        "backend": "certified-int10-six-stage-gated-hot2-root-precomputed-exact",
        "sourceBaseline": BASELINE.name,
        "sourceOneStep": ONE_STEP.name,
        "stages": STAGES,
        "groups": groups,
        "groupSize": baseline["groupSize"],
        "hotGroups": list(HOT_GROUPS),
        "precomputedRowsPerInput": len(HOT_GROUPS) * baseline["groupSize"],
        "stageGating": True,
        "javascriptSelectsWinner": False,
        "javascriptRole": "select fixture, mutate hidden input, and observe layout only",
        "topologyStrategy": (
            "two fixed exact global-int16 fine grids precede the cascade; each serial "
            "stage references their shared score-plus-local-tie anchor for groups 0/1 "
            "and conditionally renders its own exact fine grid for all other groups"
        ),
        "anchorGeometry": (
            "round(score, 4px) + (255-local)/64px; serial decode restores the exact "
            "score bucket and combines the local with the selected global group"
        ),
        "certifiedFixtures": fixtures,
        "reusedAssets": {
            "fontDirectory": "../gpt2-hvar-grid-output-head-global16-twoplane",
            "fontFiles": [path.name for path in font_files],
            "fontWoff2Bytes": sum(path.stat().st_size for path in font_files),
            "fontsCopiedOrRebuilt": False,
        },
        "generatedBytes": {},
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("index.html", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "stages": STAGES,
                "groups": groups,
                "precomputedRowsPerInput": reference["precomputedRowsPerInput"],
                "htmlBytes": (OUTPUT / "index.html").stat().st_size,
                "topologyCssBytes": (OUTPUT / "topology.css").stat().st_size,
                "fontWoff2Bytes": reference["reusedAssets"]["fontWoff2Bytes"],
                "fontsCopiedOrRebuilt": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
