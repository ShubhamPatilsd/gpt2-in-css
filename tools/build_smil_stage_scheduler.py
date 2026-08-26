#!/usr/bin/env python3
"""Build CSS-only fixtures for testing SVG SMIL as a rendering-stage scheduler."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "smil-stage-scheduler"
SIZES = (1000, 5000, 20000)
MODES = (
    "connected", "smil", "smil-load", "smil-html-target",
    "smil-svg-class-selector", "smil-css-animation-event", "hidden",
)


def document(size: int, mode: str) -> str:
    gate_display = "inline" if mode == "connected" else "none"
    begin = {
        "smil-load": "b1-scheduler.load+0.05s",
    }.get(mode, "0.15s")
    smil = (
        '<set href="#gate" attributeName="display" to="inline" '
        f'begin="{begin}" fill="freeze" />'
        if mode.startswith("smil")
        else ""
    )
    work = "\n".join(
        f'<i class="work" style="--offset:{index % 31}"></i>'
        for index in range(size)
    )
    if mode == "smil-html-target":
        return f"""<!doctype html>
<meta charset="utf-8"><title>SMIL targeting HTML: {size} nodes</title>
<style>
  @property --upstream {{ syntax: '<number>'; inherits: true; initial-value: 0; }}
  @keyframes drive {{ from {{ --upstream: 0; }} to {{ --upstream: 37; }} }}
  .root {{ --upstream:0; animation:drive 100ms linear both }}
  #gate.closed {{ display:none }}
  .work {{ display:block;height:.25px;width:calc((var(--upstream) + var(--offset))*1px) }}
  #result {{ display:block;height:1px;width:calc(var(--upstream)*1px) }}
</style>
<div class="root" id="root">
  <div id="gate" class="closed">{work}<b id="result"></b></div>
  <svg id="b1-scheduler" xmlns="http://www.w3.org/2000/svg" width="1" height="1">
    <set href="#gate" attributeName="class" to="open" begin="0.15s" fill="freeze" />
  </svg>
</div>"""
    if mode == "smil-svg-class-selector":
        return f"""<!doctype html>
<meta charset="utf-8"><title>SMIL SVG class selector: {size} nodes</title>
<style>
  @property --upstream {{ syntax: '<number>'; inherits: true; initial-value: 0; }}
  @keyframes drive {{ from {{ --upstream: 0; }} to {{ --upstream: 37; }} }}
  .root {{ --upstream:0; animation:drive 100ms linear both }}
  .root:not(:has(#signal.ready)) #gate {{ display:none }}
  .work {{ display:block;height:.25px;width:calc((var(--upstream) + var(--offset))*1px) }}
  #result {{ display:block;height:1px;width:calc(var(--upstream)*1px) }}
</style>
<div class="root" id="root">
  <svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">
    <g id="signal"><set attributeName="class" to="ready" begin="0.15s" fill="freeze" /></g>
  </svg>
  <div id="gate">{work}<b id="result"></b></div>
</div>"""
    if mode == "smil-css-animation-event":
        return f"""<!doctype html>
<meta charset="utf-8"><title>CSS animation event to SMIL: {size} nodes</title>
<style>
  @property --upstream {{ syntax: '<number>'; inherits: true; initial-value: 0; }}
  @keyframes drive {{ from {{ --upstream: 0; }} to {{ --upstream: 37; }} }}
  @keyframes readiness {{ from {{ opacity:.99 }} to {{ opacity:1 }} }}
  .root {{ --upstream:0; animation:drive 100ms linear both }}
  #css-ready {{ animation:readiness 1ms 100ms linear both }}
  .root:not(:has(#signal.ready)) #gate {{ display:none }}
  .work {{ display:block;height:.25px;width:calc((var(--upstream) + var(--offset))*1px) }}
  #result {{ display:block;height:1px;width:calc(var(--upstream)*1px) }}
</style>
<div class="root" id="root">
  <svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">
    <g id="css-ready"></g>
    <g id="signal"><set attributeName="class" to="ready"
      begin="css-ready.animationend+0.05s" fill="freeze" /></g>
  </svg>
  <div id="gate">{work}<b id="result"></b></div>
</div>"""
    return f"""<!doctype html>
<meta charset="utf-8">
<title>SMIL stage scheduler: {mode}, {size} nodes</title>
<style>
  @property --upstream {{ syntax: '<number>'; inherits: true; initial-value: 0; }}
  @keyframes drive {{ from {{ --upstream: 0; }} to {{ --upstream: 37; }} }}
  html, body {{ margin: 0; }}
  .root {{
    --upstream: 0;
    animation: drive 100ms linear both;
    width: 400px;
  }}
  svg {{ display: block; overflow: hidden; width: 400px; height: 400px; }}
  .stage {{ color: black; font: 10px/1 sans-serif; width: 300px; }}
  .work {{
    display: block;
    height: 0.25px;
    width: calc((var(--upstream) + var(--offset)) * 1px);
    border-right: calc((var(--upstream) / 37) * 0.01px) solid currentColor;
  }}
  #result {{
    display: block;
    height: 1px;
    width: calc(var(--upstream) * 1px);
  }}
</style>
<body id="runtime-body"><div class="root" id="root">
  <svg id="b1-scheduler" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
    <g id="gate" display="{gate_display}">
      <foreignObject x="0" y="0" width="400" height="400">
        <div xmlns="http://www.w3.org/1999/xhtml" class="stage">
          {work}
          <b id="result"></b>
        </div>
      </foreignObject>
    </g>
    {smil}
  </svg>
</div>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for size in SIZES:
        for mode in MODES:
            filename = f"n{size}-{mode}.html"
            (OUT / filename).write_text(document(size, mode))
            fixtures.append({"size": size, "mode": mode, "file": filename})
    manifest = {
        "sizes": list(SIZES),
        "modes": list(MODES),
        "upstreamDurationMilliseconds": 100,
        "smilBeginMilliseconds": 150,
        "fixtures": fixtures,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
