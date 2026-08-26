#!/usr/bin/env python3
"""Build an exact two-level CSS Grid argmax for GPT-2 vocabulary scale."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "experiments" / "grid-hierarchical-argmax"
SIZES = (256, 4_096, 50_257)
GROUP_SIZE = 256
SCORE_LEVELS = 65_536
LAYOUT_UNITS_PER_PX = 64
SCORE_STRIDE_PX = GROUP_SIZE // LAYOUT_UNITS_PER_PX


def code(score_bucket: int, local_id: int) -> int:
    return score_bucket * GROUP_SIZE + (GROUP_SIZE - 1 - local_id)


def build_case(size: int) -> dict[str, object]:
    rng = random.Random(0xB16B00B5 + size)
    scores_a = [rng.randrange(0, 58_000) for _ in range(size)]
    scores_b = [rng.randrange(0, 58_000) for _ in range(size)]
    winner_a = size * 7 // 17
    winner_b = size * 11 // 19
    scores_a[winner_a] = 64_000
    scores_b[winner_b] = 65_000
    candidates = [
        (code(scores_a[token], token % GROUP_SIZE),
         code(scores_b[token], token % GROUP_SIZE))
        for token in range(size)
    ]
    return {
        "size": size,
        "groups": math.ceil(size / GROUP_SIZE),
        "winnerA": winner_a,
        "winnerB": winner_b,
        "scoreA": scores_a[winner_a],
        "scoreB": scores_b[winner_b],
        "maximumCode": max(max(pair) for pair in candidates),
        "candidates": candidates,
    }


def render(case: dict[str, object]) -> str:
    size = int(case["size"])
    groups = int(case["groups"])
    candidates = case["candidates"]
    group_rules = []
    group_markup = []
    carrier_rules = []
    carrier_markup = []
    carrier_sizes = []

    for group in range(groups):
        start = group * GROUP_SIZE
        stop = min(size, start + GROUP_SIZE)
        group_rules.append(f".group-{group}{{anchor-name:--group-{group}}}")
        items = "".join(
            f'<i class="candidate" style="--a:{candidates[token][0]};'
            f'--d:{candidates[token][1] - candidates[token][0]}"></i>'
            for token in range(start, stop)
        )
        group_markup.append(
            f'<section class="group-wrapper" style="--group-tie:{GROUP_SIZE - 1 - group}">'
            f'<div class="group-grid group-{group}">{items}</div></section>'
        )
        carrier_rules.append(
            f".carrier-{group}{{--flag:clamp(0,1 - abs(var(--group) - {group}),1);"
            f"position-anchor:--group-{group};anchor-name:--carrier-{group};"
            f"width:calc(anchor-size(--group-{group} width) * var(--flag))}}"
        )
        carrier_markup.append(f'<i class="carrier carrier-{group}"></i>')
        carrier_sizes.append(f"anchor-size(--carrier-{group} width)")

    return f"""<!doctype html>
<meta charset="utf-8">
<title>Hierarchical Grid argmax {size}</title>
<style>
@property --mode {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --group {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --local {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --winner {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --score {{ syntax:"<number>"; inherits:true; initial-value:0 }}
@property --flag {{ syntax:"<number>"; inherits:true; initial-value:0 }}
* {{ box-sizing:border-box }}
html,body {{ margin:0; overflow:clip }}
body {{ anchor-scope:all }}
.outer {{
  --mode:0;
  position:fixed;
  inset:0 auto auto 0;
  display:grid;
  grid-template-columns:max-content;
  grid-template-rows:1px;
  width:max-content;
  height:1px;
  anchor-name:--outer-winner;
}}
.group-wrapper {{
  grid-area:1/1;
  display:block;
  width:calc-size(max-content,calc(
    round(down,size,{SCORE_STRIDE_PX}px) + var(--group-tie) / {LAYOUT_UNITS_PER_PX} * 1px
  ));
}}
.group-grid {{
  display:grid;
  grid-template-columns:max-content;
  grid-template-rows:1px;
  width:max-content;
  height:1px;
}}
.candidate {{
  grid-area:1/1;
  display:block;
  justify-self:start;
  width:calc((var(--a) + var(--mode) * var(--d)) / {LAYOUT_UNITS_PER_PX} * 1px);
  height:1px;
}}
{''.join(group_rules)}
.outer-reader {{
  position:fixed;
  position-anchor:--outer-winner;
  inset:2px auto auto 0;
  width:anchor-size(--outer-winner width);
  height:1px;
  container:outer-result/inline-size;
}}
@container outer-result (width >= 0px) {{
  .selection {{
    --group:calc({GROUP_SIZE - 1} - round(nearest,
      mod(100cqi,{SCORE_STRIDE_PX}px) / 1px * {LAYOUT_UNITS_PER_PX},1));
    --score:round(down,100cqi / {SCORE_STRIDE_PX}px,1);
  }}
}}
.carrier,.selected,.selected-reader {{ position:fixed; height:1px }}
{''.join(carrier_rules)}
.selected {{
  position-anchor:--carrier-0;
  anchor-name:--selected-group;
  width:max({','.join(carrier_sizes)});
}}
.selected-reader {{
  position-anchor:--selected-group;
  width:anchor-size(--selected-group width);
  container:selected-result/inline-size;
}}
@container selected-result (width >= 0px) {{
  .result {{
    --local:calc({GROUP_SIZE - 1} - round(nearest,
      mod(100cqi,{SCORE_STRIDE_PX}px) / 1px * {LAYOUT_UNITS_PER_PX},1));
    --winner:calc(var(--group) * {GROUP_SIZE} + var(--local));
    display:block;
    width:calc(var(--winner) * 1px);
    height:1px;
  }}
}}
</style>
<main id="bank" class="outer">{''.join(group_markup)}</main>
<div class="outer-reader"><div class="selection">
{''.join(carrier_markup)}<i class="selected"></i>
<div class="selected-reader"><output id="result" class="result"></output></div>
</div></div>
"""


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for size in SIZES:
        case = build_case(size)
        output_dir = OUTPUT_ROOT / str(size)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text(render(case))
        reference = {key: value for key, value in case.items() if key != "candidates"}
        (output_dir / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
        manifest.append(reference)
    (OUTPUT_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built hierarchical Grid argmax probes for: {', '.join(map(str, SIZES))}")


if __name__ == "__main__":
    main()
