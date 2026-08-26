#!/usr/bin/env python3
"""Build a no-JS probe that assembles a font-axis vector with additive animations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from build_matrix_backend_prototypes import build_direct_font_backend
from build_variable_font_scaling import inputs_for_size


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "experiments" / "additive-font-vector"
VIEWPORT = 100
WIDTH_BASE = 20
WIDTH_SCALE = 100
FONT_SIZE = 32
UNITS_PER_EM = 1_000


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def axis_list(values: list[float]) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(values)
    )


def inverse_easing(samples: int = 256) -> str:
    """Map cover progress p back to x where p=V/(V+B+S*x)."""
    points = []
    # CSS linear() input positions must be ascending, hence x descends.
    for step in reversed(range(samples + 1)):
        x = step / samples
        progress = VIEWPORT / (VIEWPORT + WIDTH_BASE + WIDTH_SCALE * x)
        points.append(f"{x:.9g} {progress * 100:.9g}%")
    return "linear(" + ",".join(points) + ")"


def font_markup(size: int) -> tuple[str, str, int]:
    if size <= 256:
        face = (
            '@font-face{font-family:MatrixVF;'
            f'src:url("../../matrix-scaling/{size}/variable-matvec.woff2?v=4") '
            'format("woff2")}'
        )
        return face, '&#xe000;', 1
    if size % 256:
        raise ValueError("sharded probe sizes must be divisible by 256")
    shard_count = size // 256
    faces = ''.join(
        f'@font-face{{font-family:MatrixVF{shard};'
        f'src:url("vector-shard-{shard}.woff2?v=1") format("woff2")}}'
        for shard in range(shard_count)
    )
    glyphs = ''.join(
        f'<i style="font-family:MatrixVF{shard}">&#xe000;</i>'
        for shard in range(shard_count)
    )
    return faces, glyphs, shard_count


def build_html(size: int, vector: list[float], expected: list[float]) -> str:
    zeros = [0.0] * size
    zero_axes = axis_list(zeros)
    keyframes = []
    subjects = []
    names = []
    timelines = []
    for index, value in enumerate(vector):
        endpoint = zeros.copy()
        endpoint[index] = 1.0
        keyframes.append(
            f"@keyframes a{index}{{from{{font-variation-settings:{zero_axes}}}"
            f"to{{font-variation-settings:{axis_list(endpoint)}}}}}"
        )
        width = WIDTH_BASE + WIDTH_SCALE * value
        subjects.append(
            '<div class="scroller"><div class="track">'
            f'<i class="subject" style="width:{width:g}px;'
            f'view-timeline:--t{index} inline"></i></div></div>'
        )
        names.append(f"a{index}")
        timelines.append(f"--t{index}")

    expected_axes = axis_list(vector)
    expected_output = expected[0]
    faces, consumer_glyphs, shard_count = font_markup(size)
    expected_width = (
        shard_count * 8_000 + expected_output
    ) * FONT_SIZE / UNITS_PER_EM
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Additive font-axis vector transport</title>
<style>
{faces}
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
  font-variation-settings:{zero_axes};
  animation-name:{','.join(names)};
  animation-duration:1s;
  animation-timing-function:{inverse_easing()};
  animation-fill-mode:both;
  animation-timeline:{','.join(timelines)};
  animation-range:cover;
  animation-composition:add;
  width:max-content;
  white-space:pre;
}}
.consumer i{{font-style:normal}}
</style>
<h1>{size} geometry values → one {size}-axis font vector</h1>
<p>No JavaScript. {size} view timelines add into one font-variation-settings list.</p>
<div class="scope">
{''.join(subjects)}
<div class="consumer" id="consumer" data-expected-axes='{expected_axes}' data-expected-width="{expected_width:.9g}">{consumer_glyphs}</div>
</div>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("size", nargs="?", type=int, default=64)
    args = parser.parse_args()
    size = args.size
    source = ROOT / "experiments" / "matrix-scaling" / str(size) / "reference.json"
    out = OUT_ROOT / str(size)
    metadata = json.loads(source.read_text())
    vector = metadata["input"]
    expected = metadata["expected"]
    if len(vector) != size or len(expected) != size:
        raise SystemExit(f"the matrix-scaling/{size} reference has an unexpected shape")
    out.mkdir(parents=True, exist_ok=True)
    if size > 256:
        weights, regenerated_vector = inputs_for_size(size)
        if not np.array_equal(regenerated_vector, np.asarray(vector)):
            raise SystemExit("the deterministic matrix input does not match the reference")
        for shard, start in enumerate(range(0, size, 256)):
            destination = out / f"vector-shard-{shard}.ttf"
            build_direct_font_backend(
                weights[:, start:start + 256],
                destination,
                axis_offset=start,
            )
    html = build_html(size, vector, expected)
    (out / "index.html").write_text(html)
    (out / "reference.json").write_text(
        json.dumps(
            {
                "size": size,
                "input": vector,
                "expected_first_output": expected[0],
                "expected_first_glyph_width_px": (8_000 + expected[0])
                * FONT_SIZE
                / UNITS_PER_EM,
                "inverse_easing_samples": 256,
                "html_bytes": len(html.encode()),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "size": size,
            "expected_first_output": expected[0],
            "html_bytes": len(html.encode()),
            "no_javascript": "<script" not in html.lower(),
        }
    )


if __name__ == "__main__":
    main()
