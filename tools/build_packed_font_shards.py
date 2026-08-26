#!/usr/bin/env python3
"""Test summing three HVAR shards inside one fallback-font text run."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from build_matrix_backend_prototypes import (
    FONT_SIZE,
    ROOT,
    UNITS_PER_EM,
    build_direct_font_backend,
)
from build_signed_hvar_chain import safe_base_advance
INPUTS = 3072
OUTPUTS = 8
SHARD = 256
SHARDS = INPUTS // SHARD
PACK_SHARDS = 3
CODEPOINT_BASE = 0xF0000
OUT = ROOT / "experiments" / "packed-font-shards"


def packed_axis_tag(shard: int, local: int) -> str:
    return f"{chr(ord('A') + shard)}{local:03d}"


def pack_settings(vector: np.ndarray, pack: int) -> str:
    first_shard = pack * PACK_SHARDS
    return ",".join(
        f'"{packed_axis_tag(shard % PACK_SHARDS, local)}" '
        f'{vector[shard * SHARD + local]:g}'
        for shard in range(first_shard, min(first_shard + PACK_SHARDS, SHARDS))
        for local in range(SHARD)
    )


def html(vector: np.ndarray, bases: list[int], expected: np.ndarray) -> str:
    faces = []
    for shard in range(SHARDS):
        start = CODEPOINT_BASE + shard * OUTPUTS
        stop = start + OUTPUTS - 1
        faces.append(
            f'@font-face{{font-family:Packed{shard};src:url("shard-{shard}.woff2?v={SHARDS}-packed") '
            f'format("woff2");unicode-range:U+{start:X}-{stop:X}}}'
        )
    registrations = "".join(
        f'@property --y-{index:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(OUTPUTS)
    )
    pack_rules = []
    for pack, first_shard in enumerate(range(0, SHARDS, PACK_SHARDS)):
        pack_families = ",".join(
            f"Packed{shard}"
            for shard in range(first_shard, min(first_shard + PACK_SHARDS, SHARDS))
        )
        pack_rules.append(
            f'.pack-{pack}{{font-family:{pack_families};'
            f'font-variation-settings:{pack_settings(vector, pack)}}}'
        )
    metric_rules = []
    probe_rules = []
    query_rules = []
    chain = '<output id="result"></output>'
    base_total = sum(bases)
    for output in reversed(range(OUTPUTS)):
        runs = "".join(
            f'<i class="pack pack-{pack}">'
            + "".join(
                f'&#x{CODEPOINT_BASE + shard * OUTPUTS + output:X};'
                for shard in range(first_shard, min(first_shard + PACK_SHARDS, SHARDS))
            )
            + "</i>"
            for pack, first_shard in enumerate(range(0, SHARDS, PACK_SHARDS))
        )
        metric_rules.append(
            f'.metric-{output:03d}{{anchor-name:--m{output:03d}}}'
        )
        probe_rules.append(
            f'.probe-{output:03d}{{width:anchor-size(--m{output:03d} width);'
            f'container:y{output:03d}/inline-size}}'
        )
        target = f'.probe-{output + 1:03d}' if output + 1 < OUTPUTS else '#result'
        query_rules.append(
            f'@container y{output:03d} (width > 0px){{{target}'
            f'{{--y-{output:03d}:calc(100cqi / 1px * {UNITS_PER_EM} / '
            f'{FONT_SIZE} - {base_total})}}}}'
        )
        chain = (
            f'<span class="metric metric-{output:03d}">{runs}</span>'
            f'<div class="probe probe-{output:03d}">{chain}</div>'
        )
    return (
        '<!doctype html><meta charset="utf-8"><title>Packed HVAR shards</title><style>'
        + "".join(faces)
        + registrations
        + 'html{font:14px monospace}body{margin:2rem}.metric{position:absolute;'
        + 'display:inline-block;width:max-content;height:1px;overflow:hidden;white-space:pre;'
        + f'font-size:{FONT_SIZE}px;font-kerning:none}}.pack{{display:inline-block;'
        + 'width:max-content;height:1px;overflow:hidden;white-space:pre}'
        + "".join(pack_rules)
        + '.probe{position:absolute;inset:0 auto auto 0;height:1px}'
        + "".join(metric_rules + probe_rules + query_rules)
        + '</style><h1>One text run per output</h1><p>Three font shards, no JavaScript.</p>'
        + f'<main data-expected="{",".join(str(value) for value in expected)}">{chain}</main>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0x5041434B)
    weights = rng.integers(-32, 33, size=(OUTPUTS, INPUTS), dtype=np.int16)
    vector = rng.integers(0, 5, size=INPUTS).astype(np.float64) / 4
    expected = weights.astype(np.float64) @ vector
    bases: list[int] = []
    for shard in range(SHARDS):
        start = shard * SHARD
        codes = weights[:, start : start + SHARD]
        base = safe_base_advance(codes)
        bases.append(base)
        build_direct_font_backend(
            codes,
            OUT / f"shard-{shard}.ttf",
            base_advance=base,
            codepoint_start=CODEPOINT_BASE + shard * OUTPUTS,
            axis_tags=[
                packed_axis_tag(shard % PACK_SHARDS, local)
                for local in range(SHARD)
            ],
        )
    (OUT / "index.html").write_text(html(vector, bases, expected))
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "inputs": INPUTS,
                "outputs": OUTPUTS,
                "shards": SHARDS,
                "bases": bases,
                "input": vector.tolist(),
                "expected": expected.tolist(),
                "term_elements_old": OUTPUTS * SHARDS,
                "term_elements_packed": 0,
            },
            indent=2,
        )
        + "\n"
    )
    print({"outputs": OUTPUTS, "shards": SHARDS, "bases": bases})


if __name__ == "__main__":
    main()
