#!/usr/bin/env python3
"""Build a no-JS geometry-to-numeric-vector probe using registered properties."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_additive_font_vector_probe import (
    FONT_SIZE,
    OUT_ROOT,
    ROOT,
    UNITS_PER_EM,
    VIEWPORT,
    WIDTH_BASE,
    WIDTH_SCALE,
    axis_list,
    font_markup,
)


def build_html(size: int, vector: list[float], expected: list[float]) -> str:
    properties = []
    keyframes = []
    subjects = []
    names = []
    timelines = []
    settings = []
    for index, value in enumerate(vector):
        prop = f"--v{index}"
        timeline = f"--t{index}"
        name = f"p{index}"
        properties.append(
            f'@property {prop}{{syntax:"<number>";inherits:false;initial-value:0}}'
        )
        keyframes.append(
            f"@keyframes {name}{{from{{{prop}:0}}to{{{prop}:1}}}}"
        )
        width = WIDTH_BASE + WIDTH_SCALE * value
        subjects.append(
            '<div class="scroller"><div class="track">'
            f'<i class="subject" style="width:{width:g}px;view-timeline:{timeline} inline"></i>'
            "</div></div>"
        )
        names.append(name)
        timelines.append(timeline)
        settings.append(f'"X{index:03d}" --decode(var({prop}))')

    faces, glyphs, shard_count = font_markup(size)
    expected_width = (
        shard_count * 8_000 + expected[0]
    ) * FONT_SIZE / UNITS_PER_EM
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registered-property vector transport</title>
<style>
{faces}
@function --decode(--p <number>) returns <number> {{
  result: calc(({VIEWPORT} / var(--p) - {VIEWPORT} - {WIDTH_BASE}) / {WIDTH_SCALE});
}}
{''.join(properties)}
{''.join(keyframes)}
html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
body{{margin:2rem;max-width:55rem}}
.scope{{timeline-scope:{','.join(timelines)}}}
.scroller{{position:fixed;left:-10000px;top:0;width:{VIEWPORT}px;height:1px;overflow-x:scroll;overflow-y:hidden}}
.track{{width:300px;height:1px}}
.subject{{display:block;height:1px}}
.consumer{{
  font-family:MatrixVF;
  font-size:{FONT_SIZE}px;
  font-variation-settings:{','.join(settings)};
  animation-name:{','.join(names)};
  animation-duration:1s;
  animation-timing-function:linear;
  animation-fill-mode:both;
  animation-timeline:{','.join(timelines)};
  animation-range:cover;
  width:max-content;
  white-space:pre;
}}
.consumer i{{font-style:normal}}
</style>
<h1>{size} geometry values → {size} CSS numbers</h1>
<p>No JavaScript. Each timeline writes one registered number; one font consumes the whole vector.</p>
<div class="scope">
{''.join(subjects)}
<div class="consumer" id="consumer" data-expected-axes='{axis_list(vector)}' data-expected-width="{expected_width:.9g}">{glyphs}</div>
</div>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("size", nargs="?", type=int, default=64)
    args = parser.parse_args()
    size = args.size
    source = ROOT / "experiments" / "matrix-scaling" / str(size) / "reference.json"
    metadata = json.loads(source.read_text())
    vector = metadata["input"]
    expected = metadata["expected"]
    out = OUT_ROOT / f"custom-{size}"
    out.mkdir(parents=True, exist_ok=True)
    # Reuse the fonts beside the additive probe. Relative shard URLs are fixed below.
    html = build_html(size, vector, expected)
    if size > 256:
        html = html.replace('url("vector-shard-', 'url("../768/vector-shard-')
    (out / "index.html").write_text(html)
    (out / "reference.json").write_text(
        json.dumps(
            {
                "size": size,
                "input": vector,
                "expected_first_output": expected[0],
                "expected_width": (size // 256 if size > 256 else 1) * 8_000
                * FONT_SIZE
                / UNITS_PER_EM
                + expected[0] * FONT_SIZE / UNITS_PER_EM,
                "html_bytes": len(html.encode()),
            },
            indent=2,
        )
        + "\n"
    )
    print({"size": size, "html_bytes": len(html.encode()), "no_javascript": "<script" not in html.lower()})


if __name__ == "__main__":
    main()
