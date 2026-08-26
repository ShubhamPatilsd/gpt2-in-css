#!/usr/bin/env python3
"""Build full-vocabulary hierarchical Grid argmax group-size variants."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "grid-argmax-group-sweep"
VOCABULARY = 50_257
GROUP_SIZES = (64, 128, 256, 512, 1_024, 2_048, 4_096)
LAYOUT_UNITS_PER_PX = 64


def next_power_of_two(value: int) -> int:
    return 1 << (value - 1).bit_length()


def css_px(value: float) -> str:
    return f"{value:g}px"


def build_variant(group_size: int) -> dict[str, object]:
    groups = math.ceil(VOCABULARY / group_size)
    outer_radix = next_power_of_two(groups)
    score_bits = 24 - max(group_size.bit_length() - 1, outer_radix.bit_length() - 1)
    score_levels = 1 << score_bits
    rng = random.Random(0xA26A_600D + group_size)
    scores_a = [rng.randrange(0, score_levels - 2_000) for _ in range(VOCABULARY)]
    scores_b = [rng.randrange(0, score_levels - 2_000) for _ in range(VOCABULARY)]
    winner_a = VOCABULARY * 3 // 7
    winner_b = VOCABULARY * 5 // 9
    scores_a[winner_a] = score_levels - 100
    scores_b[winner_b] = score_levels - 50

    group_rules = []
    group_markup = []
    carrier_rules = []
    carrier_markup = []
    carrier_sizes = []
    inner_stride = group_size / LAYOUT_UNITS_PER_PX
    outer_stride = outer_radix / LAYOUT_UNITS_PER_PX
    outer_multiplier = outer_radix / group_size

    for group in range(groups):
        start = group * group_size
        stop = min(VOCABULARY, start + group_size)
        group_rules.append(f".group-{group}{{anchor-name:--group-{group}}}")
        items = []
        for token in range(start, stop):
            local = token - start
            a = scores_a[token] * group_size + group_size - 1 - local
            b = scores_b[token] * group_size + group_size - 1 - local
            items.append(
                f'<i class="candidate" style="--a:{a};--d:{b - a}"></i>'
            )
        group_markup.append(
            f'<section class="group-wrapper" style="--group-tie:{outer_radix - 1 - group}">'
            f'<div class="group-grid group-{group}">{"".join(items)}</div></section>'
        )
        carrier_rules.append(
            f".carrier-{group}{{--flag:clamp(0,1 - abs(var(--group) - {group}),1);"
            f"position-anchor:--group-{group};anchor-name:--carrier-{group};"
            f"width:calc(anchor-size(--group-{group} width)*var(--flag))}}"
        )
        carrier_markup.append(f'<i class="carrier carrier-{group}"></i>')
        carrier_sizes.append(f"anchor-size(--carrier-{group} width)")

    css = f"""
@property --mode{{syntax:"<number>";inherits:true;initial-value:0}}
@property --group{{syntax:"<number>";inherits:true;initial-value:0}}
@property --local{{syntax:"<number>";inherits:true;initial-value:0}}
@property --winner{{syntax:"<number>";inherits:true;initial-value:0}}
@property --score{{syntax:"<number>";inherits:true;initial-value:0}}
@property --flag{{syntax:"<number>";inherits:true;initial-value:0}}
*{{box-sizing:border-box}}html,body{{margin:0;overflow:clip}}body{{anchor-scope:all}}
.outer{{--mode:0;position:fixed;inset:0 auto auto 0;display:grid;
grid-template-columns:max-content;grid-template-rows:1px;width:max-content;height:1px;
anchor-name:--outer-winner}}
.group-wrapper{{grid-area:1/1;display:block;width:calc-size(max-content,calc(
round(down,size,{css_px(inner_stride)})*{outer_multiplier:g} +
var(--group-tie)/{LAYOUT_UNITS_PER_PX}*1px))}}
.group-grid{{display:grid;grid-template-columns:max-content;grid-template-rows:1px;
width:max-content;height:1px}}
.candidate{{grid-area:1/1;display:block;justify-self:start;height:1px;
width:calc((var(--a) + var(--mode)*var(--d))/{LAYOUT_UNITS_PER_PX}*1px)}}
{''.join(group_rules)}
.outer-reader{{position:fixed;position-anchor:--outer-winner;inset:2px auto auto 0;
width:anchor-size(--outer-winner width);height:1px;container:outer-result/inline-size}}
@container outer-result (width >= 0px){{.selection{{--group:calc({outer_radix - 1} -
round(nearest,mod(100cqi,{css_px(outer_stride)})/1px*{LAYOUT_UNITS_PER_PX},1));
--score:round(down,100cqi/{css_px(outer_stride)},1)}}}}
.carrier,.selected,.selected-reader{{position:fixed;height:1px}}
{''.join(carrier_rules)}
.selected{{position-anchor:--carrier-0;anchor-name:--selected-group;
width:max({','.join(carrier_sizes)})}}
.selected-reader{{position-anchor:--selected-group;width:anchor-size(--selected-group width);
container:selected-result/inline-size}}
@container selected-result (width >= 0px){{.result{{--local:calc({group_size - 1} -
round(nearest,mod(100cqi,{css_px(inner_stride)})/1px*{LAYOUT_UNITS_PER_PX},1));
--winner:calc(var(--group)*{group_size} + var(--local));display:block;
width:calc(var(--winner)*1px);height:1px}}}}
"""
    html = f"""<!doctype html><meta charset="utf-8">
<title>Grid argmax group {group_size}</title><style>{css}</style>
<main id="bank" class="outer">{''.join(group_markup)}</main>
<div class="outer-reader"><div class="selection">{''.join(carrier_markup)}
<i class="selected"></i><div class="selected-reader">
<output id="result" class="result"></output></div></div></div>
"""
    directory = OUTPUT / f"g{group_size}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(html)
    reference = {
        "vocabulary": VOCABULARY,
        "groupSize": group_size,
        "groups": groups,
        "outerRadix": outer_radix,
        "scoreBits": score_bits,
        "winnerA": winner_a,
        "winnerB": winner_b,
        "scoreA": scores_a[winner_a],
        "scoreB": scores_b[winner_b],
        "htmlBytes": len(html.encode()),
    }
    (directory / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    return reference


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = [build_variant(group_size) for group_size in GROUP_SIZES]
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
