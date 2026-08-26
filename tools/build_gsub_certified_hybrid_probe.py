#!/usr/bin/env python3
"""Build the declarative GSUB top-two / exact-fallback composition probe."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gsub-certified-hybrid"
GSUB = ROOT / "experiments" / "gsub-indexed-fine-scorer"
GSUB_FULL = GSUB / "full"
EXACT = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
)
MARGIN_THRESHOLD = 6
GROUPS = (0, 1, 2, 17, 64, 96, 128, 195)
# Includes both forced fallbacks, threshold/near-tie fallbacks, and clear accepts.
CASE_PAIRS = (
    (0, 0, "forced-group-0"),
    (1, 1, "forced-group-1"),
    (0, 2, "clear-accept"),
    (4, 17, "small-accept"),
    (0, 64, "near-tie"),
    (4, 64, "near-tie"),
    (0, 96, "threshold"),
    (9, 96, "near-tie-order"),
    (0, 128, "clear-accept"),
    (2, 195, "clear-accept"),
)


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


def gsub_candidates(source: Path) -> str:
    html = (source / "index.html").read_text()
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


def bank_css(source: Path, destination_name: str, feature_values: dict[str, int]) -> dict:
    css = (source / "index.css").read_text()
    geometry = re.search(
        r"\(size - ([0-9.]+)px\)\*([0-9.]+) \+ var\(--score-offset\)", css
    )
    if not geometry:
        raise RuntimeError(f"candidate geometry missing from {source / 'index.css'}")
    base, factor = geometry.groups()
    source_expression = f"(size - {base}px)*{factor} + var(--score-offset)"
    if css.count(source_expression) != 1:
        raise RuntimeError(f"candidate geometry is not unique in {source / 'index.css'}")
    relative = "../gsub-indexed-fine-scorer"
    if source == GSUB_FULL:
        relative += "/full"
    css = css.replace('url("', f'url("{relative}/')
    css = css.replace(".fine-stage", ".gsub-stage")
    css = css.replace(".candidate", ".gsub-candidate")
    mapping = ";".join(
        f"style(--group:{group}):{feature_values[str(group)]}"
        for group in GROUPS
    )
    css += (
        f".gsub-stage{{--score-offset:inherit;--probe-feature:if({mapping};else:1)}}"
        "#gsub-runner .gsub-candidate{"
        "--winner-mask:clamp(0,1 - abs(var(--top-local) - var(--local)),1);"
        "width:calc-size(max-content,calc(round(nearest,"
        f"{source_expression},4px) + var(--local-tie)/64*1px "
        "- var(--winner-mask)*100000px))}\n"
    )
    (OUTPUT / destination_name).write_text(css)
    return {"basePx": float(base), "factor": float(factor)}


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
.hybrid-root{{--group:2;--score-offset:0px;anchor-scope:all}}
.gsub-stage{{top:-90000px}}
#gsub-top{{anchor-name:--gsub-top-winner}}
.top-reader,.runner-reader{{position:fixed;left:0;height:1px}}
.top-reader{{position-anchor:--gsub-top-winner;top:-89000px;
 width:anchor-size(--gsub-top-winner width);container:gsub-top-readback/inline-size}}
@container gsub-top-readback (width >= 0px){{
 .top-decode{{--top-bucket:round(down,100cqi/4px,1);
  --top-local:calc(255 - round(nearest,mod(100cqi,4px)/1px*64,1))}}
}}
.top-token,.runner-token,.margin-result,.fallback-result{{display:block;height:1px}}
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
.runner-token{{width:calc(var(--runner-local)*1px)}}
.margin-result{{width:calc(var(--margin)*1px)}}
.fallback-result{{width:calc(var(--fallback)*1px)}}
#exact-stage{{display:if(style(--fallback:1):grid;else:none)}}
#exact-result{{anchor-name:--exact-token}}
.final-stage{{position:fixed;position-anchor:--exact-token;left:0;top:-50000px;
 display:block;height:1px;width:if(style(--fallback:1):
 anchor-size(--exact-token width);else:calc((var(--group)*256 + var(--top-local))*1px))}}
""".strip() + "\n"


def hybrid_html(bank: str, candidates: str, fine: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GSUB certified hybrid ({bank})</title>
<link rel="stylesheet" href="../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">
<link rel="stylesheet" href="bank-{bank}.css">
<link rel="stylesheet" href="topology.css">
<div id="hybrid-root" class="hybrid-root">
 <span id="gsub-top" class="gsub-stage">{candidates}</span>
 <span class="top-reader"><span id="top-decode" class="top-decode">
  <output id="top-token" class="top-token"></output>
  <span id="gsub-runner" class="gsub-stage">{candidates}</span>
  <span class="runner-reader"><span id="decision" class="decision">
   <output id="runner-token" class="runner-token"></output>
   <output id="margin-result" class="margin-result"></output>
   <output id="fallback-result" class="fallback-result"></output>
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
<title>Exact CSS-dispatched fine-scorer baseline</title>
<link rel="stylesheet" href="../gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css">
<div id="exact-root"><span id="baseline-exact-stage" class="fine-stage">{fine}</span>
<span class="fine-reader"><i id="baseline-exact-result" class="fine-result"></i></span></div>
"""


def pure_html(bank: str, candidates: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Pure GSUB baseline ({bank})</title>
<link rel="stylesheet" href="bank-{bank}.css">
<div id="pure-root"><main id="pure-gsub-stage" class="gsub-stage">{candidates}</main></div>
"""


def main() -> None:
    for required in (
        GSUB / "reference.json",
        GSUB_FULL / "reference.json",
        GSUB_FULL / "browser-results.json",
        EXACT / "index.css",
        EXACT / "index.html",
    ):
        if not required.exists():
            raise FileNotFoundError(required)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    bounded_reference = json.loads((GSUB / "reference.json").read_text())
    full_reference = json.loads((GSUB_FULL / "reference.json").read_text())
    full_results = json.loads((GSUB_FULL / "browser-results.json").read_text())
    exact_reference = json.loads((EXACT / "reference.json").read_text())
    if tuple(bounded_reference["groupIds"]) != GROUPS:
        raise RuntimeError("bounded GSUB group set changed")
    certification = full_results["hybridCertification"]
    if certification["winnerMarginThresholdBuckets"] != MARGIN_THRESHOLD:
        raise RuntimeError("full-bank empirical threshold changed")

    bounded_candidates = gsub_candidates(GSUB)
    full_candidates = gsub_candidates(GSUB_FULL)
    fine = exact_candidates()
    bounded_geometry = bank_css(
        GSUB, "bank-bounded.css", bounded_reference["featureValues"]
    )
    full_geometry = bank_css(
        GSUB_FULL, "bank-full.css", full_reference["featureValues"]
    )
    topology = topology_css()
    if "239226" in topology or "272549.2" in topology:
        raise RuntimeError("topology must not hardcode bank candidate geometry")
    if '#exact-stage{display:if(style(--fallback:1):grid;else:none)}' not in topology:
        raise RuntimeError("exact fallback must be absent from accepted-path layout")
    (OUTPUT / "topology.css").write_text(topology)
    bounded_html = hybrid_html("bounded", bounded_candidates, fine)
    full_html = hybrid_html("full", full_candidates, fine)
    for name, html in (("bounded", bounded_html), ("full", full_html)):
        if html.count('class="gsub-stage"') != 2:
            raise RuntimeError(f"{name} top and runner must share the GSUB stage mapping")
    (OUTPUT / "index.html").write_text(bounded_html)
    (OUTPUT / "full.html").write_text(full_html)
    (OUTPUT / "exact.html").write_text(exact_html(fine))
    (OUTPUT / "pure-bounded.html").write_text(
        pure_html("bounded", bounded_candidates)
    )
    (OUTPUT / "pure-full.html").write_text(pure_html("full", full_candidates))

    oracle = {
        (case["fixture"], group["group"]): group
        for case in bounded_reference["fixtures"]["cases"]
        for group in case["groups"]
    }
    cases = []
    for fixture, group, label in CASE_PAIRS:
        item = oracle[(fixture, group)]
        buckets = item["buckets"][: item["validCandidates"]]
        order = sorted(range(len(buckets)), key=lambda local: (-buckets[local], local))
        cases.append({
            "fixture": fixture,
            "group": group,
            "label": label,
            "boundedFeature": bounded_reference["featureValues"][str(group)],
            "fullFeature": full_reference["featureValues"][str(group)],
            "offlineWinnerLocal": order[0],
            "offlineRunnerLocal": order[1],
            "offlineMarginBuckets": buckets[order[0]] - buckets[order[1]],
        })

    reference = {
        "backend": "declarative-gsub-top-two-margin-gated-exact-fallback",
        "groups": list(GROUPS),
        "groupSize": bounded_reference["groupSize"],
        "marginThresholdBuckets": MARGIN_THRESHOLD,
        "fallbackRule": "group <= 1 or rendered GSUB top-two margin <= 6 buckets",
        "empiricalOnly": certification["empiricalOnly"],
        "portableBoundProved": certification["portableBoundProved"],
        "empiricalCandidateDeltaBound": certification["empiricalCandidateDeltaBound"],
        "boundedBank": {
            "directory": "gsub-indexed-fine-scorer",
            "featureValues": bounded_reference["featureValues"],
            "woff2Bytes": bounded_reference["fontWoff2Bytes"],
            "candidateGeometry": bounded_geometry,
        },
        "fullBank": {
            "directory": "gsub-indexed-fine-scorer/full",
            "featureValues": {str(group): full_reference["featureValues"][str(group)] for group in GROUPS},
            "woff2Bytes": full_reference["fontWoff2Bytes"],
            "candidateGeometry": full_geometry,
        },
        "exactBaseline": {
            "directory": "gpt2-hvar-grid-output-head-certified-upper-int10-one-step",
            "woff2Bytes": bounded_reference["baselineFineWoff2Bytes"],
            "dispatchCssBytes": bounded_reference["baselineDispatchCssBytes"],
        },
        "hiddenVectors": bounded_reference["fixtures"]["hiddenVectors"],
        "scoreFloors": bounded_reference["fixtures"]["scoreFloors"],
        "cases": cases,
        "topology": {
            "gsubCandidateElements": 512,
            "exactCandidateElementsWhenActive": 256,
            "javascriptSelectsWinner": False,
            "htmlBytes": {},
            "cssBytes": {},
        },
        "sourceExactBackend": exact_reference["backend"],
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["topology"]["htmlBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in (
            "index.html", "full.html", "exact.html",
            "pure-bounded.html", "pure-full.html",
        )
    }
    reference["topology"]["cssBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("bank-bounded.css", "bank-full.css", "topology.css")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT),
        "groups": list(GROUPS),
        "cases": len(cases),
        "threshold": MARGIN_THRESHOLD,
        "generatedBytes": sum(path.stat().st_size for path in OUTPUT.iterdir()),
    }, indent=2))


if __name__ == "__main__":
    main()
