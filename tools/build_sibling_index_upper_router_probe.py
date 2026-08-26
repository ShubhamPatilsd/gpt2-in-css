#!/usr/bin/env python3
"""Build a 197-way sibling-index/local-anchor upper-router probe."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "sibling-index-upper-router"
GROUPS = 197
SCORE_STRIDE_PX = 4
DEFAULT_WINNER = 137


def default_scores() -> list[int]:
    scores = [64 + ((group * 73) % 113) for group in range(GROUPS)]
    scores[DEFAULT_WINNER] = 240
    return scores


def score_sources(scores: list[int], kind: str) -> str:
    if kind == "sibling-index":
        return "".join(
            '<i class="score-source" '
            f'style="--score:{score};--source-anchor:--score-{group}"></i>'
            for group, score in enumerate(scores)
        )
    return "".join(
        f'<i class="score-source score-source-{group}" style="--score:{score}"></i>'
        for group, score in enumerate(scores)
    )


def candidates(scores: list[int], kind: str) -> str:
    if kind == "sibling-index":
        return "".join(
            '<span class="candidate" '
            f'style="--score:{score};--match-anchor:--match-{group}">'
            '<i class="local-source"></i><i class="match"></i></span>'
            for group, score in enumerate(scores)
        )
    return "".join(
        f'<span class="candidate candidate-{group}" style="--score:{score}">'
        f'<i class="local-source local-source-{group}"></i>'
        f'<i class="match match-{group}"></i></span>'
        for group, score in enumerate(scores)
    )


def markup(scores: list[int], kind: str, stylesheet: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>{kind} 197-way upper router</title>
<link rel="stylesheet" href="{stylesheet}">
<main id="probe" data-router="{kind}">
  <span class="score-sources">{score_sources(scores, kind)}</span>
  <i class="score-max"></i>
  <span class="score-reader"><span class="selection">
    <span class="candidates">{candidates(scores, kind)}</span>
    <i class="group-max"></i>
    <span class="group-reader"><output id="result"></output></span>
  </span></span>
</main>
"""


def common_css() -> str:
    score_sizes = ",".join(
        f"anchor-size(--score-{group} width)" for group in range(GROUPS)
    )
    match_sizes = ",".join(
        f"anchor-size(--match-{group} width)" for group in range(GROUPS)
    )
    return f"""*{{box-sizing:border-box}}
html,body{{margin:0}}
@property --candidate-index{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --max-bucket{{syntax:"<number>";inherits:true;initial-value:0}}
@property --score{{syntax:"<number>";inherits:true;initial-value:0}}
@property --active{{syntax:"<number>";inherits:true;initial-value:1}}
.score-source,.local-source,.match,.score-max,.score-reader,.group-max,
.group-reader,#result{{position:fixed;left:0;top:0;height:1px}}
.candidate{{display:block;height:0}}
.score-source,.local-source{{width:calc(var(--score)*{SCORE_STRIDE_PX}px*var(--active))}}
.score-max{{position-anchor:--score-0;anchor-name:--score-max;
  width:max({score_sizes})}}
.score-reader{{position-anchor:--score-max;width:anchor-size(--score-max width);
  container:score-max/inline-size}}
@container score-max (width >= 0px){{
  .selection{{--max-bucket:round(nearest,100cqi/{SCORE_STRIDE_PX}px,1)}}
  .group-max{{position-anchor:--match-0;anchor-name:--group-max;
    width:max({match_sizes})}}
  .group-reader{{position-anchor:--group-max;width:anchor-size(--group-max width);
    container:group-max/inline-size}}
}}
@container group-max (width >= 0px){{
  #result{{width:calc(var(--max-bucket)*{SCORE_STRIDE_PX}px);
    height:calc(({GROUPS + 1} - round(nearest,100cqi/1px,1))*1px)}}
}}
"""


def sibling_css() -> str:
    return common_css() + f"""
.score-source{{anchor-name:var(--source-anchor)}}
.candidate{{anchor-scope:--local-score;--candidate-index:sibling-index()}}
.local-source{{anchor-name:--local-score}}
.match{{position-anchor:--local-score;anchor-name:var(--match-anchor);
  width:calc(clamp(0px,anchor-size(--local-score width) -
    (var(--max-bucket) - .5)*{SCORE_STRIDE_PX}px,1px)*
    ({GROUPS + 1} - var(--candidate-index)))}}
"""


def baseline_css() -> str:
    rules = []
    for group in range(GROUPS):
        factor = GROUPS - group
        rules.append(f".score-source-{group}{{anchor-name:--score-{group}}}")
        rules.append(f".local-source-{group}{{anchor-name:--local-score-{group}}}")
        rules.append(
            f".match-{group}{{position-anchor:--local-score-{group};"
            f"anchor-name:--match-{group};width:calc(clamp(0px,"
            f"anchor-size(--local-score-{group} width) - "
            f"(var(--max-bucket) - .5)*{SCORE_STRIDE_PX}px,1px)*{factor})}}"
        )
    return common_css() + "\n" + "\n".join(rules) + "\n"


def visited_cases(scores: list[int]) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []

    def add(name: str, case_scores: list[int], visited: list[int]) -> None:
        eligible = [group for group in range(GROUPS) if group not in set(visited)]
        best_score = max(case_scores[group] for group in eligible)
        winner = min(group for group in eligible if case_scores[group] == best_score)
        cases.append(
            {
                "name": name,
                "scores": case_scores,
                "visited": visited,
                "expectedGroup": winner,
                "expectedBucket": best_score,
            }
        )

    first = [90] * GROUPS
    first[41], first[87] = 260, 240
    add("mask-single-winner", first, [41])

    second = [80] * GROUPS
    second[0], second[64], second[196] = 300, 280, 270
    add("mask-leading-pair", second, [0, 64])

    third = scores.copy()
    order = sorted(range(GROUPS), key=lambda group: (-third[group], group))
    add("mask-scattered-top-seven", third, sorted(order[:7]))

    fourth = [110 + (group % 9) for group in range(GROUPS)]
    survivor = 193
    add("single-unvisited-survivor", fourth, [g for g in range(GROUPS) if g != survivor])
    return cases


def file_sizes(paths: list[Path]) -> dict[str, int]:
    return {path.name: path.stat().st_size for path in paths}


def main() -> None:
    scores = default_scores()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    sibling_html = OUTPUT / "index.html"
    baseline_html = OUTPUT / "baseline.html"
    sibling_styles = OUTPUT / "sibling-index.css"
    baseline_styles = OUTPUT / "baseline.css"
    sibling_html.write_text(markup(scores, "sibling-index", sibling_styles.name))
    baseline_html.write_text(markup(scores, "explicit-class", baseline_styles.name))
    sibling_styles.write_text(sibling_css())
    baseline_styles.write_text(baseline_css())

    default_bucket = max(scores)
    default_group = min(group for group, score in enumerate(scores) if score == default_bucket)
    source_bytes = {
        "siblingIndex": file_sizes([sibling_html, sibling_styles]),
        "baseline": file_sizes([baseline_html, baseline_styles]),
    }
    source_bytes["siblingIndex"]["total"] = sum(source_bytes["siblingIndex"].values())
    source_bytes["baseline"]["total"] = sum(source_bytes["baseline"].values())
    reference = {
        "groups": GROUPS,
        "scoreStridePixels": SCORE_STRIDE_PX,
        "defaultScores": scores,
        "defaultGroup": default_group,
        "defaultBucket": default_bucket,
        "tieConvention": "lowest zero-based group index wins",
        "tieCases": [[0, 196], [17, 18], [75, 132]],
        "visitedCases": visited_cases(scores),
        "sourceBytes": source_bytes,
        "elementsPerRouter": GROUPS * 4 + 7,
        "materialSourceReductionThreshold": 0.20,
        "materialColdReductionThreshold": 0.10,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "groups": GROUPS,
                "defaultGroup": default_group,
                "defaultBucket": default_bucket,
                "sourceBytes": source_bytes,
                "visitedCases": len(reference["visitedCases"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
