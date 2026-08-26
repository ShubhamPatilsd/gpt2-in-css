#!/usr/bin/env python3
"""Build an isolated position-try replacement for the certified upper router."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "position-try-upper-router"
SOURCE_REFERENCE = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
    / "reference.json"
)
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = (VOCABULARY + GROUP_SIZE - 1) // GROUP_SIZE
WEIGHT_MAX = 511
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4


def source_markup() -> str:
    return "".join(
        f'<i class="score-source score-source-{group}"></i>'
        for group in range(GROUPS)
    )


def position_markup() -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Position-try certified upper-router probe</title>
<link rel="stylesheet" href="style.css">
<main id="probe" class="probe position-probe" data-fixture="0">
  <span class="score-sources">{source_markup()}</span>
  <output id="result" class="position-router"></output>
</main>
"""


def baseline_markup() -> str:
    matches = "".join(
        f'<i class="baseline-match baseline-match-{group}"></i>'
        for group in range(GROUPS)
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Existing two-pass certified upper-router control</title>
<link rel="stylesheet" href="style.css">
<main id="probe" class="probe baseline-probe" data-fixture="0">
  <span class="score-sources">{source_markup()}</span>
  <i class="baseline-score-max"></i>
  <span class="baseline-score-reader">
    <span class="baseline-selection">{matches}<i class="baseline-group-max"></i>
      <span class="baseline-group-reader"><output id="result" class="baseline-router"></output></span>
    </span>
  </span>
</main>
"""


def build_css(group_buckets: np.ndarray) -> str:
    source_rules = "\n".join(
        f".score-source-{group}{{anchor-name:--score-{group}}}"
        for group in range(GROUPS)
    )
    fixture_rules = "\n".join(
        f'.probe[data-fixture="{fixture}"] .score-source-{group}'
        f'{{--score:{int(group_buckets[fixture, group])}}}'
        for fixture in range(group_buckets.shape[0])
        for group in range(GROUPS)
    )
    fallback_names = ",".join(f"--upper-{group}" for group in range(GROUPS))
    exclusion_rules = "\n".join(
        f"@container router-state style(--excluded-group:{excluded}){{"
        ".position-router{--active-fallbacks:"
        + ",".join(
            f"--upper-{group}" for group in range(GROUPS) if group != excluded
        )
        + "}}"
        for excluded in range(GROUPS)
    )
    position_rules = "\n".join(
        f"@position-try --upper-{group}{{"
        f"position-anchor:--score-{group};left:0;"
        f"right:calc(-1 * anchor-size(width));top:0;"
        f"width:anchor-size(width);height:{group + 1}px}}"
        for group in range(GROUPS)
    )
    source_sizes = ",".join(
        f"anchor-size(--score-{group} width)" for group in range(GROUPS)
    )
    match_rules = "\n".join(
        f".baseline-match-{group}{{position-anchor:--score-{group};"
        f"anchor-name:--baseline-match-{group};"
        f"width:calc(clamp(0px,anchor-size(--score-{group} width) - "
        f"(var(--baseline-bucket) - .5)*{SCORE_STRIDE_PX}px,1px)"
        f"*{GROUPS - group})}}"
        for group in range(GROUPS)
    )
    match_sizes = ",".join(
        f"anchor-size(--baseline-match-{group} width)"
        for group in range(GROUPS)
    )
    return f"""*{{box-sizing:border-box}}
html,body{{margin:0}}
@property --score{{syntax:"<number>";inherits:true;initial-value:0}}
@property --enabled{{syntax:"<number>";inherits:false;initial-value:1}}
@property --baseline-bucket{{syntax:"<number>";inherits:true;initial-value:0}}
@property --excluded-group{{syntax:"<integer>";inherits:true;initial-value:-1}}
@property --router-epoch{{syntax:"<integer>";inherits:true;initial-value:0}}
.probe{{--excluded-group:-1;--router-epoch:0;container-name:router-state}}
.score-source{{position:fixed;left:0;top:-1000px;height:1px;
  width:calc(var(--score) * {SCORE_STRIDE_PX}px * var(--enabled))}}
{source_rules}
{fixture_rules}

/* The base position deliberately overflows. Blink then orders the fallbacks by
   their inset-modified containing-block width. A negative right inset makes
   that width viewport + anchor score, so most-width is an exact max. */
.position-router{{position:fixed;left:calc(100vw + 1px);top:0;width:1px;height:1px;
  --active-fallbacks:{fallback_names};position-try-order:most-width;
  position-try-fallbacks:var(--active-fallbacks)}}
/* Blink does not re-sort when only anchor sizes change. Alternating list order
   explicitly invalidates ordering; exclusion rules replace
   the list with every candidate except the masked group. */
@container router-state style(--router-epoch:1){{.position-router{{
  --active-fallbacks:{fallback_names},--router-rearm-sentinel}}}}
{exclusion_rules}
{position_rules}

/* Control: the certified head's current max / equality-match / max router. */
.baseline-score-max,.baseline-score-reader,.baseline-match,.baseline-group-max,
.baseline-group-reader,.baseline-router{{position:fixed;left:0;top:0;height:1px}}
.baseline-score-max{{position-anchor:--score-0;anchor-name:--baseline-score-max;
  width:max({source_sizes})}}
.baseline-score-reader{{position-anchor:--baseline-score-max;
  width:anchor-size(--baseline-score-max width);container:baseline-score/inline-size}}
@container baseline-score (width >= 0px){{
  .baseline-selection{{--baseline-bucket:round(nearest,100cqi/{SCORE_STRIDE_PX}px,1)}}
  {match_rules}
  .baseline-group-max{{position-anchor:--baseline-match-0;
    anchor-name:--baseline-group-max;width:max({match_sizes})}}
  .baseline-group-reader{{position-anchor:--baseline-group-max;
    width:anchor-size(--baseline-group-max width);container:baseline-group/inline-size}}
}}
@container baseline-group (width >= 0px){{
  .baseline-router{{width:calc(var(--baseline-bucket)*{SCORE_STRIDE_PX}px);
    height:calc(({GROUPS + 1} - round(nearest,100cqi/1px,1))*1px)}}
}}
"""


def compute_group_buckets(fixtures: dict[str, list]) -> np.ndarray:
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float64
    )
    scales = np.max(np.abs(weights), axis=1) / WEIGHT_MAX
    scales[scales == 0] = 1.0
    represented = np.rint(weights / scales[:, None]) * scales[:, None]
    error_norms = np.linalg.norm(weights - represented, axis=1)
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.float64)
    upper = (
        hidden @ represented.T
        + np.linalg.norm(hidden, axis=1)[:, None] * error_norms
    )
    token_buckets = np.floor(
        (upper - floors[:, None]) * SCORE_SCALE
    ).astype(np.int64) + 1
    return np.stack(
        [
            np.max(
                token_buckets[
                    :, group * GROUP_SIZE : min((group + 1) * GROUP_SIZE, VOCABULARY)
                ],
                axis=1,
            )
            for group in range(GROUPS)
        ],
        axis=1,
    )


def main() -> None:
    source = json.loads(SOURCE_REFERENCE.read_text())
    fixtures = source["certifiedFixtures"]
    group_buckets = compute_group_buckets(fixtures)
    order = np.argsort(-group_buckets, axis=1, kind="stable")
    fixture_count = len(fixtures["hiddenVectors"])
    if fixture_count != 10:
        raise RuntimeError(f"expected ten certified fixtures, found {fixture_count}")
    if not np.array_equal(order[:, 0], np.asarray(fixtures["upperGroups"])):
        raise RuntimeError("recomputed first groups disagree with certified fixtures")
    first_buckets = group_buckets[np.arange(fixture_count), order[:, 0]]
    if not np.array_equal(first_buckets, np.asarray(fixtures["upperWinnerBuckets"])):
        raise RuntimeError("recomputed first buckets disagree with certified fixtures")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(position_markup())
    (OUTPUT / "baseline.html").write_text(baseline_markup())
    (OUTPUT / "style.css").write_text(build_css(group_buckets))
    reference = {
        "source": str(SOURCE_REFERENCE.relative_to(ROOT)),
        "fixtures": fixture_count,
        "groups": GROUPS,
        "scoreStridePixels": SCORE_STRIDE_PX,
        "positionTryOrder": "most-width",
        "dynamicRearm": "toggle --router-epoch between 0 and 1 when scores mutate",
        "masking": "set --excluded-group to remove that fallback from the candidate list",
        "firstGroups": order[:, 0].astype(int).tolist(),
        "firstBuckets": first_buckets.astype(int).tolist(),
        "maskedNextGroups": order[:, 1].astype(int).tolist(),
        "maskedNextBuckets": group_buckets[
            np.arange(fixture_count), order[:, 1]
        ].astype(int).tolist(),
        "groupBuckets": group_buckets.astype(int).tolist(),
        "positionRouterElements": GROUPS + 1,
        "baselineRouterElements": GROUPS * 2 + 5,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "fixtures": fixture_count,
        "groups": GROUPS,
        "firstGroups": reference["firstGroups"],
        "maskedNextGroups": reference["maskedNextGroups"],
        "positionRouterElements": reference["positionRouterElements"],
        "baselineRouterElements": reference["baselineRouterElements"],
    }, indent=2))


if __name__ == "__main__":
    main()
