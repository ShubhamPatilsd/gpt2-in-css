#!/usr/bin/env python3
"""Build probes for additional variable-font values exposed to CSS."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_font_multimetric_probe import build_font  # noqa: E402


OUT = ROOT / "experiments" / "font-extra-numeric-probe"
FONT_SIZE = 512
BASE = 2_000
UNITS_PER_EM = 1_000
AXIS_VALUES = (-1, -0.5, 0, 0.5, 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights = np.zeros((7, 32), dtype=np.int16)
    # VVAR advance-height row for U+6C34. All horizontal metrics stay fixed.
    weights[6, 0] = 100
    build_font(weights, OUT / "extra-metrics.ttf")
    nodes = "".join(
        f'<div class="probe p{index}" id="p{index}"><div class="sink">probe</div></div>'
        for index in range(len(AXIS_VALUES)))
    rules = "".join(
        f'.p{index}{{font-variation-settings:"X000" {value};}}'
        for index, value in enumerate(AXIS_VALUES))
    html = f'''<!doctype html><meta charset="utf-8"><title>CSS extra font metrics</title>
<style>
@font-face{{font-family:ExtraMetrics;src:url("extra-metrics.ttf") format("truetype")}}
@property --vheight{{syntax:"<number>";inherits:true;initial-value:-99999}}
.probe{{font-family:ExtraMetrics;font-size:{FONT_SIZE}px;font-size-adjust:ic-height 1;
--vheight:calc({BASE} * {FONT_SIZE} / (1ch / 1px) - {BASE})}}
{rules}
.sink{{font:14px monospace}}
</style>{nodes}
'''
    (OUT / "ic-height.html").write_text(html)
    (OUT / "ic-height.json").write_text(json.dumps({
        "axis_values": AXIS_VALUES,
        "expected": [100 * value for value in AXIS_VALUES],
        "base": BASE,
        "font_size": FONT_SIZE,
        "units_per_em": UNITS_PER_EM,
    }, indent=2) + "\n")
    print({"font_bytes": (OUT / "extra-metrics.ttf").stat().st_size,
           "html_bytes": (OUT / "ic-height.html").stat().st_size})


if __name__ == "__main__":
    main()
