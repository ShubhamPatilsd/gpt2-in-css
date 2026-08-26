#!/usr/bin/env python3
"""Build no-JS probes for using CSS compositing as a vector accumulator."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "css-compositor-vector"
COUNTS = (64, 256, 1024, 3072)
GEOMETRY_SCALE = 65536
BASE_SUM = 0.5


def amounts(count: int) -> list[float]:
    # Deliberately non-uniform positive contributions. Their exact sum is
    # BASE_SUM, so the expected red channel is independent of vector width.
    raw = [1 + ((index * 37 + 11) % 31) for index in range(count)]
    total = sum(raw)
    return [BASE_SUM * value / total for value in raw]


def page(count: int) -> str:
    carriers = "".join(
        '<i class="carrier" style="--amount:'
        f'{value:.12g}"><i class="term"></i></i>'
        for value in amounts(count)
    )
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CSS compositor vector accumulator: {count}</title>
<style>
html{{--gain:1;background:white}}
body{{margin:0}}
.case{{position:relative;width:32px;height:32px;background:#000;isolation:isolate;
  contain:strict;overflow:hidden}}
.carrier{{position:absolute;left:0;top:0;width:calc(var(--amount) * var(--gain) * {GEOMETRY_SCALE}px);
  height:1px;container-type:inline-size;overflow:visible}}
.term{{position:absolute;left:0;top:0;width:32px;height:32px;background:#f00;
  opacity:calc(100cqi / {GEOMETRY_SCALE}px);mix-blend-mode:plus-lighter}}
</style>
<div id="case" class="case" data-count="{count}">{carriers}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "counts": list(COUNTS),
        "geometryScale": GEOMETRY_SCALE,
        "baseSum": BASE_SUM,
        "expectedRedAtGain1": round(255 * BASE_SUM),
        "expectedRedAtGain08": round(255 * BASE_SUM * 0.8),
        "runtimeJavascript": False,
        "pages": {},
    }
    for count in COUNTS:
        html = page(count)
        path = OUT / f"n{count}.html"
        path.write_text(html)
        manifest["pages"][str(count)] = {
            "htmlBytes": len(html.encode()),
            "elements": count * 2 + 1,
        }
    (OUT / "reference.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(manifest)


if __name__ == "__main__":
    main()
