#!/usr/bin/env python3
"""Build a 768x768 CSS matvec from three browser-safe variable fonts."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import brotli
import numpy as np

from build_matrix_backend_prototypes import (
    FONT_BASE_ADVANCE,
    FONT_SIZE,
    ROOT,
    UNITS_PER_EM,
    axis_tag,
    build_direct_font_backend,
    output_glyph,
)
from build_variable_font_scaling import inputs_for_size


SIZE = 768
SHARD_SIZE = 256
SHARD_COUNT = SIZE // SHARD_SIZE
OUT = ROOT / "experiments" / "matrix-scaling" / "768-sharded"


def settings(values: np.ndarray) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(values)
    )


def sharded_html(vector: np.ndarray, expected: np.ndarray) -> str:
    registrations = [
        f'@property --vf-y-{output:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for output in range(SIZE)
    ]
    term_rules = []
    for shard in range(SHARD_COUNT):
        shard_values = vector[shard * SHARD_SIZE:(shard + 1) * SHARD_SIZE]
        term_rules.append(
            f'.term-s{shard}'
            f'{{font-family:MatrixVF{shard};font-variation-settings:{settings(shard_values)}}}'
        )

    metric_rules = []
    probe_rules = []
    query_rules = []
    chains = []
    for block in range(SHARD_COUNT):
        start = block * SHARD_SIZE
        stop = start + SHARD_SIZE
        chain = f'<div class="vf-result vf-result-{block}" id="vf-result-{block}"></div>'
        for output in reversed(range(start, stop)):
            terms = ''.join(
                f'<i class="term term-s{shard}" aria-hidden="true"></i>'
                for shard in range(SHARD_COUNT)
            )
            chain = (
                f'<span class="metric metric-{output:03d}" aria-hidden="true">{terms}</span>'
                f'<div class="probe probe-{output:03d}">{chain}</div>'
            )
        chains.append(chain)

        for output in range(start, stop):
            metric_rules.append(
                f'.metric-{output:03d}'
                f'{{anchor-name:--metric-{output:03d}}}'
                f'.metric-{output:03d} .term::before'
                f'{{content:"\\{0xE000 + output:x}"}}'
            )
            probe_rules.append(
                f'.probe-{output:03d}'
                f'{{position-anchor:--metric-{output:03d};'
                f'container:y{output:03d}/inline-size;'
                f'width:anchor-size(--metric-{output:03d} width)}}'
            )
            target = (
                f'.probe-{output + 1:03d}' if output + 1 < stop
                else f'.vf-result-{block}'
            )
            query_rules.append(
                f'@container y{output:03d} (width > 0px){{{target}'
                f'{{--vf-y-{output:03d}:calc('
                f'100cqi / 1px * {UNITS_PER_EM} / {FONT_SIZE} '
                f'- {SHARD_COUNT * FONT_BASE_ADVANCE})}}}}'
            )

    expected_data = ",".join(f"{value:g}" for value in expected)
    expected_text = ", ".join(f"{value:g}" for value in expected[:8])
    faces = "\n".join(
        f'@font-face{{font-family:MatrixVF{shard};src:url("shard-{shard}.woff2?v=1") format("woff2")}}'
        for shard in range(SHARD_COUNT)
    )
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sharded variable-font 768×768 matvec</title>
  <style>
    {faces}
    {''.join(registrations)}
    html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
    body{{margin:2rem;max-width:52rem}}
    h1{{font:600 1.25rem system-ui,sans-serif}}
    .metrics{{position:relative;min-height:1px}}
    .metric{{position:absolute;display:inline-flex;width:max-content;height:1px;
      overflow:hidden;white-space:pre}}
    .term{{display:inline-block;width:max-content;font-size:{FONT_SIZE}px;font-kerning:none}}
    .probe{{position:absolute;inset:0 auto auto 0;height:1px}}
    {''.join(term_rules)}
    {''.join(metric_rules)}
    {''.join(probe_rules)}
    {''.join(query_rules)}
    .status{{padding:1rem;border:1px solid #aaa}}
  </style>
</head>
<body>
  <h1>Three-font 768×768 matrix–vector multiplication</h1>
  <p class="status" data-expected="{expected_data}">No JavaScript. Expected first outputs: {expected_text}</p>
  <div class="metrics">{''.join(chains)}</div>
</body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    weights, vector = inputs_for_size(SIZE)
    expected = weights.astype(np.float64) @ vector

    build_times = []
    if not args.html_only:
        for shard in range(SHARD_COUNT):
            started = time.perf_counter()
            font_path = OUT / f"shard-{shard}.ttf"
            start = shard * SHARD_SIZE
            build_direct_font_backend(weights[:, start:start + SHARD_SIZE], font_path)
            build_times.append(time.perf_counter() - started)
    else:
        previous = json.loads((OUT / "reference.json").read_text())
        build_times = previous["build_seconds_by_shard"]

    html_path = OUT / "index.html"
    html_path.write_text(sharded_html(vector, expected))
    font_paths = [OUT / f"shard-{shard}.woff2" for shard in range(SHARD_COUNT)]
    raw_bytes = html_path.stat().st_size + sum(path.stat().st_size for path in font_paths)
    brotli_bytes = len(brotli.compress(html_path.read_bytes(), quality=11)) + sum(
        len(brotli.compress(path.read_bytes(), quality=11)) for path in font_paths
    )
    metadata = {
        "size": SIZE,
        "compiler": "direct-hvar",
        "shards": SHARD_COUNT,
        "axes_per_shard": SHARD_SIZE,
        "weights": SIZE * SIZE,
        "expected": expected.tolist(),
        "input": vector.tolist(),
        "build_seconds_by_shard": build_times,
        "font_bytes": [path.stat().st_size for path in font_paths],
        "html_bytes": html_path.stat().st_size,
        "runtime_raw_bytes": raw_bytes,
        "runtime_brotli_bytes": brotli_bytes,
    }
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print({key: metadata[key] for key in ("size", "shards", "axes_per_shard", "build_seconds_by_shard", "font_bytes", "html_bytes", "runtime_raw_bytes", "runtime_brotli_bytes")})


if __name__ == "__main__":
    main()
