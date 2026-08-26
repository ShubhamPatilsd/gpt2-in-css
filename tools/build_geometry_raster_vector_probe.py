#!/usr/bin/env python3
"""Build a no-JS geometry-to-raster vector transport probe."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "geometry-raster-vector"
COUNTS = (256, 3072)
BAR_WIDTH = 256


def values(count: int) -> list[float]:
    return [0.08 + 0.84 * (((index * 73 + 19) % 251) / 250) for index in range(count)]


def page(count: int, source: list[float]) -> str:
    bars = "".join(
        f'<i class="bar" style="--value:{value:.12g}"></i>'
        for value in source
    )
    kernel = " ".join(["1"] * BAR_WIDTH)
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Geometry to raster vector: {count}</title>
<style>
html{{--gain:1;background:transparent}}
body{{margin:0}}
svg{{position:fixed;left:0;top:0}}
.bank{{display:grid;grid-template-rows:repeat({count},1px);width:{BAR_WIDTH}px;height:{count}px;
  background:transparent;filter:url(#reduce-bars);contain:strict}}
.bar{{display:block;width:calc(var(--value) * var(--gain) * {BAR_WIDTH}px);height:1px;
  min-width:0;max-width:{BAR_WIDTH}px;background:#f00}}
</style>
<svg width="0" height="0" aria-hidden="true">
  <filter id="reduce-bars" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{BAR_WIDTH}" height="{count}" color-interpolation-filters="sRGB">
    <feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}"
      kernelMatrix="{kernel}" divisor="{BAR_WIDTH}" bias="0" edgeMode="none"
      preserveAlpha="false" x="{BAR_WIDTH - 1}" y="0" width="1" height="{count}" result="strip"/>
    <feColorMatrix in="strip" type="matrix"
      values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"
      x="{BAR_WIDTH - 1}" y="0" width="1" height="{count}" result="scalar"/>
    <feOffset in="scalar" dx="-{BAR_WIDTH - 1}" dy="0" x="0" y="0" width="1" height="{count}"/>
  </filter>
</svg>
<div id="bank" class="bank" data-count="{count}">{bars}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "counts": list(COUNTS),
        "barWidth": BAR_WIDTH,
        "runtimeJavascript": False,
        "pages": {},
    }
    for count in COUNTS:
        source = values(count)
        html = page(count, source)
        path = OUT / f"n{count}.html"
        path.write_text(html)
        manifest["pages"][str(count)] = {
            "htmlBytes": len(html.encode()),
            "values": source,
        }
    (OUT / "reference.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print({
        "counts": list(COUNTS),
        "bar_width": BAR_WIDTH,
        "bytes": {count: manifest["pages"][str(count)]["htmlBytes"] for count in COUNTS},
    })


if __name__ == "__main__":
    main()
