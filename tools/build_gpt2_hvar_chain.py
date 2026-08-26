#!/usr/bin/env python3
"""Build two chained, signed 768x768 GPT-2 matrices in HTML/CSS only."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

try:
    import brotli
except ModuleNotFoundError:
    brotli = None
import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_matrix_backend_prototypes import (
    ROOT,
    UNITS_PER_EM,
    axis_tag,
    build_direct_font_backend,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows, safe_base_advance


OUT = ROOT / "experiments" / "gpt2-hvar-chain"
WIDTH = 768
SHARD_SIZE = 256
SHARDS = WIDTH // SHARD_SIZE
L2_BLOCKS = 4
L2_BLOCK_SIZE = WIDTH // L2_BLOCKS
CHAIN_FONT_SIZE = 512
QUANT_BITS = 9
TOKEN_ID = 15496  # "Hello" in the GPT-2 tokenizer.


def model_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    tensors = SafeTensors(MODEL_PATH)
    vector = np.asarray(
        tensors.tensor("wte.weight")[TOKEN_ID] + tensors.tensor("wpe.weight")[0],
        dtype=np.float64,
    )
    weight_1 = np.asarray(tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64).T
    bias_1 = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    weight_2 = np.asarray(tensors.tensor("h.1.attn.c_proj.weight"), dtype=np.float64).T
    bias_2 = np.asarray(tensors.tensor("h.1.attn.c_proj.bias"), dtype=np.float64)
    return vector, weight_1, bias_1, weight_2, bias_2


def settings(values: list[str]) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {value}' for index, value in enumerate(values)
    )


def pair_chain(layer: int, start: int, stop: int, child: str) -> str:
    term_class = "term" if layer == 1 else "partial"
    for first in reversed(range(start, stop, 2)):
        metrics = []
        for output in (first, first + 1):
            terms = "".join(
                f'<i class="{term_class} {term_class}-s{shard} output-{output:03d}" '
                'aria-hidden="true"></i>'
                for shard in range(SHARDS)
            )
            metrics.append(
                f'<span class="metric metric-l{layer}-{output:03d}" '
                f'aria-hidden="true">{terms}</span>'
            )
        child = (
            "".join(metrics)
            + f'<div class="probe probe-pair-l{layer}-{first // 2:03d}">{child}</div>'
        )
    return child


def page(
    vector: np.ndarray,
    quantized_1,
    bias_1: np.ndarray,
    range_0: float,
    bases_1: list[int],
    quantized_2,
    bias_2: np.ndarray,
    range_1: float,
    bases_2: list[int],
    expected: np.ndarray,
    font_tags: list[list[str]],
    *,
    direct_cqi: bool = False,
) -> str:
    faces = []
    for layer in (1, 2):
        for shard in range(SHARDS):
            faces.append(
                f'@font-face{{font-family:G{layer}S{shard};'
                f'src:url("layer-{layer}-shard-{shard}.woff2?v={font_tags[layer - 1][shard]}") '
                'format("woff2")}'
            )

    registrations = []
    for layer in (1, 2):
        for output in range(WIDTH):
            registrations.append(
                f'@property --l{layer}-raw-{output:03d}'
                '{syntax:"<number>";inherits:true;initial-value:0}'
            )
            registrations.append(
                f'@property --l{layer}-y-{output:03d}'
                '{syntax:"<number>";inherits:true;initial-value:0}'
            )

    font_rules = []
    for shard in range(SHARDS):
        start = shard * SHARD_SIZE
        stop = start + SHARD_SIZE
        first_settings = settings(
            [css_number(value / range_0) for value in vector[start:stop]]
        )
        second_settings = settings(
            [
                f'calc(var(--l1-y-{index:03d}) / {css_number(range_1)})'
                for index in range(start, stop)
            ]
        )
        font_rules.append(
            f'.term-s{shard}{{font-family:G1S{shard};font-variation-settings:{first_settings}}}'
        )
        font_rules.append(
            f'.partial-s{shard}{{font-family:G2S{shard};font-variation-settings:{second_settings}}}'
        )

    glyph_rules = []
    probe_rules = []
    query_rules = []
    rescale_1: list[str] = []
    rescale_2: list[list[str]] = [[] for _ in range(L2_BLOCKS)]
    base_total_1 = sum(bases_1)
    base_total_2 = sum(bases_2)

    for output in range(WIDTH):
        glyph_rules.append(
            f'.output-{output:03d}::before{{content:"\\{0xE000 + output:x}"}}'
        )

    layer_2_branches = []
    for block in range(L2_BLOCKS):
        start = block * L2_BLOCK_SIZE
        stop = start + L2_BLOCK_SIZE
        result = f'<div class="final-result final-result-{block}" id="final-{block}"></div>'
        layer_2_branches.append(pair_chain(2, start, stop, result))
        for first in range(start, stop, 2):
            second = first + 1
            probe_rules.append(
                f'.metric-l2-{first:03d}{{anchor-name:--metric-l2-{first:03d}}}'
                f'.metric-l2-{second:03d}{{anchor-name:--metric-l2-{second:03d}}}'
                f'.probe-pair-l2-{first // 2:03d}'
                f'{{width:anchor-size(--metric-l2-{first:03d} width);'
                f'height:anchor-size(--metric-l2-{second:03d} width);'
                f'container:l2p{first // 2:03d}/size}}'
            )
            target = (
                f'.probe-pair-l2-{first // 2 + 1:03d}'
                if second + 1 < stop
                else f'.final-result-{block}'
            )
            width_value = (
                f'calc(100cqi / 1px * {UNITS_PER_EM} / {CHAIN_FONT_SIZE} '
                f'- {base_total_2})'
            )
            height_value = (
                f'calc(100cqb / 1px * {UNITS_PER_EM} / {CHAIN_FONT_SIZE} '
                f'- {base_total_2})'
            )
            if direct_cqi:
                query_rules.append(
                    f'{target}{{--l2-raw-{first:03d}:{width_value};'
                    f'--l2-raw-{second:03d}:{height_value}}}'
                )
            else:
                query_rules.append(
                    f'@container l2p{first // 2:03d} (width > 0px){{{target}'
                    f'{{--l2-raw-{first:03d}:{width_value}}}}}'
                )
                query_rules.append(
                    f'@container l2p{first // 2:03d} (height > 0px){{{target}'
                    f'{{--l2-raw-{second:03d}:{height_value}}}}}'
                )
            for output in (first, second):
                factor = range_1 * quantized_2.scales[output]
                rescale_2[block].append(
                    f'--l2-y-{output:03d}:calc('
                    f'var(--l2-raw-{output:03d}) / {css_number(1 / factor)}'
                    f' + ({css_number(bias_2[output])}))'
                )

    l1_result = f'<div class="l1-result">{"".join(layer_2_branches)}</div>'
    layer_1_chain = pair_chain(1, 0, WIDTH, l1_result)
    for first in range(0, WIDTH, 2):
        second = first + 1
        probe_rules.append(
            f'.metric-l1-{first:03d}{{anchor-name:--metric-l1-{first:03d}}}'
            f'.metric-l1-{second:03d}{{anchor-name:--metric-l1-{second:03d}}}'
            f'.probe-pair-l1-{first // 2:03d}'
            f'{{width:anchor-size(--metric-l1-{first:03d} width);'
            f'height:anchor-size(--metric-l1-{second:03d} width);'
            f'container:l1p{first // 2:03d}/size}}'
        )
        target = (
            f'.probe-pair-l1-{first // 2 + 1:03d}'
            if second + 1 < WIDTH
            else '.l1-result'
        )
        width_value = (
            f'calc(100cqi / 1px * {UNITS_PER_EM} / {CHAIN_FONT_SIZE} '
            f'- {base_total_1})'
        )
        height_value = (
            f'calc(100cqb / 1px * {UNITS_PER_EM} / {CHAIN_FONT_SIZE} '
            f'- {base_total_1})'
        )
        if direct_cqi:
            query_rules.append(
                f'{target}{{--l1-raw-{first:03d}:{width_value};'
                f'--l1-raw-{second:03d}:{height_value}}}'
            )
        else:
            query_rules.append(
                f'@container l1p{first // 2:03d} (width > 0px){{{target}'
                f'{{--l1-raw-{first:03d}:{width_value}}}}}'
            )
            query_rules.append(
                f'@container l1p{first // 2:03d} (height > 0px){{{target}'
                f'{{--l1-raw-{second:03d}:{height_value}}}}}'
            )
        for output in (first, second):
            factor = range_0 * quantized_1.scales[output]
            rescale_1.append(
                f'--l1-y-{output:03d}:calc('
                f'var(--l1-raw-{output:03d}) / {css_number(1 / factor)}'
                f' + ({css_number(bias_1[output])}))'
            )

    expected_data = ",".join(css_number(value) for value in expected)
    rescale_rules = [f'.l1-result{{{";".join(rescale_1)}}}']
    for block in range(L2_BLOCKS):
        rescale_rules.append(
            f'.final-result-{block}{{{";".join(rescale_2[block])}}}'
        )

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Two chained GPT-2 768×768 matrices in CSS</title>
  <style>
    {''.join(faces)}
    {''.join(registrations)}
    html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
    body{{margin:2rem;max-width:52rem}}
    h1{{font:600 1.25rem system-ui,sans-serif}}
    .stage{{position:relative;min-height:1px}}
    .metric{{position:absolute;display:inline-flex;width:max-content;height:1px;overflow:hidden;white-space:pre}}
    .term,.partial{{display:inline-block;width:max-content;height:1px;overflow:hidden;white-space:pre;font-size:{CHAIN_FONT_SIZE}px;font-kerning:none}}
    .probe{{position:absolute;inset:0 auto auto 0;overflow:visible}}
    {''.join(font_rules)}
    {''.join(glyph_rules)}
    {''.join(probe_rules)}
    {''.join(query_rules)}
    {''.join(rescale_rules)}
    .status{{padding:1rem;border:1px solid #aaa}}
  </style>
</head>
<body>
  <h1>Two signed GPT-2-small matrix layers in HTML/CSS</h1>
  <p class="status" data-expected="{expected_data}">No JavaScript. Two real 768×768 GPT-2 matrices with signed {QUANT_BITS}-bit row quantization.</p>
  <div class="stage">{layer_1_chain}</div>
</body>
</html>
'''


def compressed_size(path: Path) -> int:
    contents = path.read_bytes()
    if brotli is not None:
        return len(brotli.compress(contents, quality=11))
    return len(
        subprocess.run(
            ["/opt/homebrew/bin/brotli", "-q", "11", "-c"],
            input=contents,
            check=True,
            capture_output=True,
        ).stdout
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    vector, weight_1, bias_1, weight_2, bias_2 = model_inputs()
    quantized_1 = quantize_float_rows(weight_1, bits=QUANT_BITS)
    quantized_2 = quantize_float_rows(weight_2, bits=QUANT_BITS)
    original_1 = weight_1 @ vector + bias_1
    reconstructed_1 = quantized_1.reconstructed @ vector + bias_1
    original_2 = weight_2 @ original_1 + bias_2
    reconstructed_2 = quantized_2.reconstructed @ reconstructed_1 + bias_2
    range_0 = float(np.max(np.abs(vector)) * 1.01)
    range_1 = float(np.max(np.abs(reconstructed_1)) * 1.01)

    build_started = time.perf_counter()
    bases: list[list[int]] = [[], []]
    quantized_layers = (quantized_1, quantized_2)
    for layer, quantized in enumerate(quantized_layers, start=1):
        for shard in range(SHARDS):
            start = shard * SHARD_SIZE
            stop = start + SHARD_SIZE
            codes = quantized.codes[:, start:stop]
            base = safe_base_advance(codes)
            bases[layer - 1].append(base)
            ttf_path = OUT / f"layer-{layer}-shard-{shard}.ttf"
            woff_path = OUT / f"layer-{layer}-shard-{shard}.woff2"
            if not (
                os.environ.get("HVAR_REUSE_FONTS") == "1"
                and ttf_path.exists()
                and woff_path.exists()
            ):
                build_direct_font_backend(
                    codes,
                    ttf_path,
                    signed_axes=True,
                    base_advance=base,
                )
    build_seconds = time.perf_counter() - build_started
    font_paths = [
        OUT / f"layer-{layer}-shard-{shard}.woff2"
        for layer in (1, 2)
        for shard in range(SHARDS)
    ]
    font_tags = [
        [
            hashlib.sha256(
                (OUT / f"layer-{layer}-shard-{shard}.woff2").read_bytes()
            ).hexdigest()[:12]
            for shard in range(SHARDS)
        ]
        for layer in (1, 2)
    ]
    html_path = OUT / "index.html"
    html_path.write_text(
        page(
            vector,
            quantized_1,
            bias_1,
            range_0,
            bases[0],
            quantized_2,
            bias_2,
            range_1,
            bases[1],
            reconstructed_2,
            font_tags,
        )
    )
    direct_html_path = OUT / "direct-cqi.html"
    direct_html_path.write_text(
        page(
            vector,
            quantized_1,
            bias_1,
            range_0,
            bases[0],
            quantized_2,
            bias_2,
            range_1,
            bases[1],
            reconstructed_2,
            font_tags,
            direct_cqi=True,
        )
    )
    runtime_paths = [html_path, *font_paths]
    metadata = {
        "width": WIDTH,
        "shards": SHARDS,
        "bits": QUANT_BITS,
        "build_seconds": build_seconds,
        "input_range": range_0,
        "intermediate_range": range_1,
        "base_advances": bases,
        "weight_sha256": [
            hashlib.sha256(weight_1.tobytes()).hexdigest(),
            hashlib.sha256(weight_2.tobytes()).hexdigest(),
        ],
        "row_scales": [quantized_1.scales.tolist(), quantized_2.scales.tolist()],
        "input": vector.tolist(),
        "biases": [bias_1.tolist(), bias_2.tolist()],
        "quantized_intermediate": reconstructed_1.tolist(),
        "original_output": original_2.tolist(),
        "quantized_output": reconstructed_2.tolist(),
        "layer_1_max_error": float(np.max(np.abs(reconstructed_1 - original_1))),
        "layer_2_max_error": float(np.max(np.abs(reconstructed_2 - original_2))),
        "font_bytes": [path.stat().st_size for path in font_paths],
        "html_bytes": html_path.stat().st_size,
        "direct_cqi_html_bytes": direct_html_path.stat().st_size,
        "runtime_raw_bytes": sum(path.stat().st_size for path in runtime_paths),
        "runtime_brotli_bytes": sum(compressed_size(path) for path in runtime_paths),
    }
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print({key: metadata[key] for key in ("build_seconds", "layer_1_max_error", "layer_2_max_error", "font_bytes", "html_bytes", "runtime_raw_bytes", "runtime_brotli_bytes")})


if __name__ == "__main__":
    main()
