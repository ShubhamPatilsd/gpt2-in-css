#!/usr/bin/env python3
"""Build the exhaustive 197-group declarative GSUB hybrid certification."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gsub-certified-hybrid" / "full-screen"
GSUB = ROOT / "experiments" / "gsub-indexed-fine-scorer" / "full"
EXACT = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
)
MARGIN_THRESHOLD = 6


def extract_between(text: str, start: str, stop: str) -> str:
    begin = text.index(start) + len(start)
    return text[begin : text.index(stop, begin)]


def exact_candidates() -> str:
    html = (EXACT / "index.html").read_text()
    return extract_between(
        html,
        '<span id="fine-stage" class="fine-stage">',
        '</span><span class="fine-reader">',
    )


def gsub_candidates() -> str:
    html = (GSUB / "index.html").read_text()
    raw = extract_between(
        html,
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


def bank_css(feature_values: dict[str, int], groups: tuple[int, ...]) -> dict:
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

    css = css.replace('url("', 'url("../../gsub-indexed-fine-scorer/full/')
    css = css.replace(".fine-stage", ".gsub-stage")
    css = css.replace(".candidate", ".gsub-candidate")
    mapping = ";".join(
        f"style(--group:{group}):{feature_values[str(group)]}" for group in groups
    )
    css += (
        f".gsub-stage{{--score-offset:inherit;--probe-feature:if({mapping};else:1)}}"
        "#gsub-runner .gsub-candidate{"
        "--winner-mask:clamp(0,1 - abs(var(--top-local) - var(--local)),1);"
        "width:calc-size(max-content,calc(round(nearest,"
        f"{source_expression},4px) + var(--local-tie)/64*1px "
        "- var(--winner-mask)*100000px))}\n"
    )
    (OUTPUT / "bank.css").write_text(css)
    return {
        "basePx": float(base),
        "factor": float(factor),
        "mappedGroups": len(groups),
    }


def topology_css() -> str:
    return f"""
@property --top-bucket{{syntax:"<number>";inherits:true;initial-value:0}}
@property --top-local{{syntax:"<number>";inherits:true;initial-value:0}}
@property --runner-bucket{{syntax:"<number>";inherits:true;initial-value:0}}
@property --runner-local{{syntax:"<number>";inherits:true;initial-value:0}}
@property --margin{{syntax:"<number>";inherits:true;initial-value:0}}
@property --forced-fallback{{syntax:"<number>";inherits:true;initial-value:0}}
@property --near-fallback{{syntax:"<number>";inherits:true;initial-value:0}}
@property --fallback{{syntax:"<number>";inherits:true;initial-value:0}}
*{{box-sizing:border-box}}
html,body{{margin:0;overflow:clip}}
.hybrid-root{{--group:0;--score-offset:0px;anchor-scope:all}}
.gsub-stage{{top:-90000px}}
#gsub-top{{anchor-name:--gsub-top-winner}}
.top-reader,.runner-reader{{position:fixed;left:0;height:1px}}
.top-reader{{position-anchor:--gsub-top-winner;top:-89000px;
 width:anchor-size(--gsub-top-winner width);container:gsub-top-readback/inline-size}}
@container gsub-top-readback (width >= 0px){{
 .top-decode{{--top-bucket:round(down,100cqi/4px,1);
  --top-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1))}}
}}
.probe-result{{display:block;height:1px}}
.top-token{{width:calc((var(--group)*256 + var(--top-local))*1px)}}
#gsub-runner{{top:-88000px;anchor-name:--gsub-runner-winner}}
#gsub-runner .gsub-candidate{{
 --winner-mask:clamp(0,1 - abs(var(--top-local) - var(--local)),1)
}}
.runner-reader{{position-anchor:--gsub-runner-winner;top:-87000px;
 width:anchor-size(--gsub-runner-winner width);
 container:gsub-runner-readback/inline-size}}
@container gsub-runner-readback (width >= 0px){{
 .decision{{--runner-bucket:round(down,100cqi/4px,1);
  --runner-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1));
  --margin:calc(var(--top-bucket) - var(--runner-bucket));
  --forced-fallback:clamp(0,2 - var(--group),1);
  --near-fallback:clamp(0,{MARGIN_THRESHOLD + 1} - var(--margin),1);
  --fallback:max(var(--forced-fallback),var(--near-fallback))}}
}}
.top-bucket-result{{width:calc(var(--top-bucket)*1px)}}
.runner-local-result{{width:calc(var(--runner-local)*1px)}}
.runner-bucket-result{{width:calc(var(--runner-bucket)*1px)}}
.margin-result{{width:calc(var(--margin)*1px)}}
.fallback-result{{width:calc(var(--fallback)*1px)}}
#exact-stage{{display:if(style(--fallback:1):grid;else:none)}}
#exact-result{{anchor-name:--exact-token}}
.final-stage{{position:fixed;position-anchor:--exact-token;left:0;top:-50000px;
 display:block;height:1px;width:if(style(--fallback:1):
 anchor-size(--exact-token width);else:calc((var(--group)*256 + var(--top-local))*1px))}}
""".strip() + "\n"


def hybrid_html(candidates: str, fine: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Full-screen GSUB certified hybrid</title>
<link rel="stylesheet" href="../../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">
<link rel="stylesheet" href="bank.css">
<link rel="stylesheet" href="topology.css">
<div id="hybrid-root" class="hybrid-root">
 <span id="gsub-top" class="gsub-stage">{candidates}</span>
 <span class="top-reader"><span id="top-decode" class="top-decode">
  <output id="top-token" class="probe-result top-token"></output>
  <output id="top-bucket-result" class="probe-result top-bucket-result"></output>
  <span id="gsub-runner" class="gsub-stage">{candidates}</span>
  <span class="runner-reader"><span id="decision" class="decision">
   <output id="runner-local-result" class="probe-result runner-local-result"></output>
   <output id="runner-bucket-result" class="probe-result runner-bucket-result"></output>
   <output id="margin-result" class="probe-result margin-result"></output>
   <output id="fallback-result" class="probe-result fallback-result"></output>
   <span id="exact-stage" class="fine-stage">{fine}</span>
   <span class="fine-reader"><i id="exact-result" class="fine-result"></i></span>
   <output id="final-result" class="final-stage"></output>
  </span></span>
 </span></span>
</div>
"""


def exact_html(fine: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Separate exact CSS-dispatched baseline</title>
<link rel="stylesheet" href="../../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">
<div id="exact-root"><span id="baseline-exact-stage" class="fine-stage">{fine}</span>
<span class="fine-reader"><i id="baseline-exact-result" class="fine-result"></i></span></div>
"""


def main() -> None:
    required = (
        GSUB / "reference.json",
        GSUB / "browser-results.json",
        GSUB / "index.css",
        GSUB / "index.html",
        EXACT / "reference.json",
        EXACT / "index.css",
        EXACT / "index.html",
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    source_reference = json.loads((GSUB / "reference.json").read_text())
    source_results = json.loads((GSUB / "browser-results.json").read_text())
    exact_reference = json.loads((EXACT / "reference.json").read_text())
    groups = tuple(source_reference["groupIds"])
    if groups != tuple(range(197)):
        raise RuntimeError("full GSUB bank must contain contiguous groups 0..196")
    feature_values = source_reference["featureValues"]
    if tuple(feature_values[str(group)] for group in groups) != tuple(range(1, 198)):
        raise RuntimeError("expected the full numbered cv01 mapping 1..197")
    certification = source_results["hybridCertification"]
    if certification["winnerMarginThresholdBuckets"] != MARGIN_THRESHOLD:
        raise RuntimeError("source empirical margin threshold changed")

    fixtures = source_reference["fixtures"]
    if len(fixtures["hiddenVectors"]) != 10 or len(fixtures["cases"]) != 10:
        raise RuntimeError("expected ten hidden fixtures")
    oracle = {
        (case["fixture"], item["group"]): item
        for case in fixtures["cases"]
        for item in case["groups"]
    }
    rendered = {
        (item["fixture"], item["group"]): item
        for item in source_results["comparisons"]
    }
    if len(oracle) != 1970 or len(rendered) != 1970:
        raise RuntimeError("expected 10 fixtures x 197 groups")

    cases = []
    for fixture in range(10):
        for group in groups:
            expected = oracle[(fixture, group)]
            source = rendered[(fixture, group)]
            margin = source["gsubRunnerUp"]["winnerMarginBuckets"]
            fallback = group <= 1 or margin <= MARGIN_THRESHOLD
            cases.append(
                {
                    "fixture": fixture,
                    "group": group,
                    "feature": feature_values[str(group)],
                    "validCandidates": expected["validCandidates"],
                    "oracleWinnerToken": expected["winnerToken"],
                    "sourceExactWinnerToken": (
                        group * 256 + source["baselineWinner"]["winnerLocal"]
                    ),
                    "sourceGsubTopLocal": source["gsubWinner"]["winnerLocal"],
                    "sourceGsubTopBucket": source["gsubWinner"]["winnerBucket"],
                    "sourceGsubRunnerLocal": source["gsubRunnerUp"]["runnerLocal"],
                    "sourceGsubRunnerBucket": source["gsubRunnerUp"]["runnerBucket"],
                    "sourceMarginBuckets": margin,
                    "expectedFallback": fallback,
                }
            )

    accepted = sum(not item["expectedFallback"] for item in cases)
    fallback = len(cases) - accepted
    forced = sum(item["group"] <= 1 for item in cases)
    near = sum(
        item["group"] > 1 and item["sourceMarginBuckets"] <= MARGIN_THRESHOLD
        for item in cases
    )
    if (accepted, fallback, forced, near) != (
        certification["certifiableCases"],
        certification["fallbackCases"],
        20,
        certification["nearTieFallbackCases"],
    ):
        raise RuntimeError("source certification route counts are inconsistent")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates = gsub_candidates()
    fine = exact_candidates()
    geometry = bank_css(feature_values, groups)
    topology = topology_css()
    if topology.count("#exact-stage{display:if(style(--fallback:1):grid;else:none)}") != 1:
        raise RuntimeError("exact scorer must be conditionally absent on accepted cases")
    (OUTPUT / "topology.css").write_text(topology)
    hybrid = hybrid_html(candidates, fine)
    if hybrid.count('class="gsub-stage"') != 2:
        raise RuntimeError("top-1 and runner-up must share the GSUB mapping")
    (OUTPUT / "index.html").write_text(hybrid)
    (OUTPUT / "exact.html").write_text(exact_html(fine))

    reference = {
        "backend": "full-screen-declarative-gsub-top-two-margin-gated-exact-fallback",
        "groups": list(groups),
        "groupSize": source_reference["groupSize"],
        "feature": "cv01",
        "featureValues": feature_values,
        "marginThresholdBuckets": MARGIN_THRESHOLD,
        "fallbackRule": "group <= 1 or rendered GSUB top-two margin <= 6 buckets",
        "empiricalOnly": certification["empiricalOnly"],
        "portableBoundProved": certification["portableBoundProved"],
        "empiricalCandidateDeltaBound": certification["empiricalCandidateDeltaBound"],
        "hiddenVectors": fixtures["hiddenVectors"],
        "scoreFloors": fixtures["scoreFloors"],
        "cases": cases,
        "expectedRoutes": {
            "accepted": accepted,
            "fallback": fallback,
            "forcedFallback": forced,
            "nearTieFallback": near,
            "acceptedRate": accepted / len(cases),
            "fallbackRate": fallback / len(cases),
        },
        "reusedAssets": {
            "gsubDirectory": "gsub-indexed-fine-scorer/full",
            "gsubWoff2Bytes": source_reference["fontWoff2Bytes"],
            "exactDirectory": "gpt2-hvar-grid-output-head-certified-upper-int10-one-step",
            "exactWoff2Bytes": source_reference["baselineFineWoff2Bytes"],
            "exactDispatchCssBytes": source_reference["baselineDispatchCssBytes"],
            "fontsCopiedOrRebuilt": False,
        },
        "sourceChrome": source_results["chrome"],
        "sourceExactBackend": exact_reference["backend"],
        "candidateGeometry": geometry,
        "topology": {
            "gsubCandidateElements": 512,
            "exactCandidateElementsWhenActive": 256,
            "javascriptSelectsWinner": False,
            "javascriptRole": "mutate inputs and observe layout only",
            "generatedBytes": {},
        },
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["topology"]["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("index.html", "exact.html", "bank.css", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "groups": len(groups),
                "cases": len(cases),
                "accepted": accepted,
                "fallback": fallback,
                "gsubWoff2BytesReused": source_reference["fontWoff2Bytes"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
