#!/usr/bin/env python3
"""Build a timeline-free HVAR output bank using Grid/Subgrid track sizes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from build_variable_font_scaling import inputs_for_size


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "matrix-scaling" / "256"
OUT = ROOT / "experiments" / "grid-subgrid-vector"
SIZE = 256


def settings(values: list[float]) -> str:
    return ",".join(
        f'"X{index:03d}" {value:g}' for index, value in enumerate(values)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((SOURCE / "reference.json").read_text())
    if reference["size"] != SIZE:
        raise ValueError("the grid probe requires the 256-axis fixture")
    weights, original_input = inputs_for_size(SIZE)
    if not np.array_equal(original_input, np.asarray(reference["input"])):
        raise ValueError("the deterministic fixture no longer matches reference.json")
    mutation_cases = []
    for round_index in range(7):
        offsets = np.asarray([
            (((index * 17 + (round_index + 1) * 13) % 9) - 4) / 64
            for index in range(SIZE)
        ])
        vector = np.clip(original_input + offsets, 0, 1)
        mutation_cases.append({
            "input": vector.tolist(),
            "expected": (weights.astype(np.float64) @ vector).tolist(),
        })
    metrics = "".join(
        f'<i class="metric m{index:03d}" style="grid-column:{index + 1}">'
        f'&#x{0xE000 + index:X};</i>'
        for index in range(SIZE)
    )
    cells = "".join(
        f'<div class="cell c{index:03d}"><i class="consumer" data-index="{index}"></i></div>'
        for index in range(SIZE)
    )
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>Grid/subgrid HVAR vector transport</title>
<style>
@font-face{{font-family:GridMatrix;src:url("../matrix-scaling/256/variable-matvec.woff2?v=4") format("woff2")}}
@property --v{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --z{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --g{{syntax:"<number>";inherits:true;initial-value:-99999}}
.bank{{display:grid;grid-template-columns:repeat({SIZE},max-content);grid-template-rows:1px 1px;
  width:max-content;font-family:GridMatrix;font-size:{reference["font_size_px"]}px;
  font-variation-settings:{settings(reference["input"])};font-kerning:none;line-height:1;
  position:fixed;left:0;top:0}}
.metric{{grid-row:1;display:block;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.transport{{display:grid;grid-template-columns:subgrid;grid-column:1/-1;grid-row:2}}
.cell{{container-type:inline-size;position:relative;height:1px;min-width:0}}
.consumer{{--v:calc(100cqi / 1px * {reference["units_per_em"]} / {reference["font_size_px"]} - {reference["base_advance"]});
  --z:clamp(-10,.7978845608028654 * (var(--v) + .044715 * var(--v) * var(--v) * var(--v)),10);
  --g:calc(var(--v) / (1 + exp(-2 * var(--z))));
  position:absolute;width:calc((var(--g) + 10000) * 1px);height:1px}}
</style>
<div id="bank" class="bank">{metrics}<div class="transport">{cells}</div></div>
'''
    (OUT / "index.html").write_text(html)
    reference.update({
        "backend": "grid-subgrid",
        "htmlBytes": len(html.encode()),
        "fontPath": "../matrix-scaling/256/variable-matvec.woff2",
        "mutationCases": mutation_cases,
    })
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({"outputs": SIZE, "html_bytes": len(html.encode())})


if __name__ == "__main__":
    main()
