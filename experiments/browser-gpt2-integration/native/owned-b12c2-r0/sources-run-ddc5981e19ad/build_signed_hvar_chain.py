#!/usr/bin/env python3
"""Build a two-layer CSS-only chain from real TinyStories float matrices."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import brotli
except ModuleNotFoundError:
    brotli = None
import numpy as np

import build_output_head_benchmark as model
from build_matrix_backend_prototypes import (
    FONT_SIZE,
    ROOT,
    UNITS_PER_EM,
    axis_tag,
    build_direct_font_backend,
)


OUT = ROOT / "experiments" / "signed-hvar-chain"
WIDTH = 64
BITS = 8
MAX_CODE = (1 << (BITS - 1)) - 1


@dataclass(frozen=True)
class QuantizedRows:
    codes: np.ndarray
    scales: np.ndarray
    reconstructed: np.ndarray


def css_number(value: float) -> str:
    return model.css_number(float(value))


def quantize_float_rows(weights: np.ndarray, bits: int = BITS) -> QuantizedRows:
    """Symmetric per-output-row quantization for an [output, input] matrix."""
    maximum_code = (1 << (bits - 1)) - 1
    maximums = np.max(np.abs(weights), axis=1)
    scales = np.where(maximums == 0, 1.0, maximums / maximum_code)
    codes = np.rint(weights / scales[:, None]).clip(
        -maximum_code, maximum_code
    ).astype(np.int16)
    return QuantizedRows(codes, scales, codes.astype(np.float64) * scales[:, None])


def safe_base_advance(codes: np.ndarray) -> int:
    maximum = int(np.max(np.sum(np.abs(codes.astype(np.int64)), axis=1)))
    base = maximum + 32
    if base + maximum > 65535:
        raise ValueError("quantized row range cannot fit in a glyph advance")
    return base


def real_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    state = model.load_torch_zip(model.download_checkpoint())
    vector = (
        state["transformer.wte.weight"][11].astype(np.float64)
        + state["transformer.wpe.weight"][0].astype(np.float64)
    )
    # GPT-2 stores Conv1D weights [input, output]; font rows are [output, input].
    weight_1 = state["transformer.h.0.attn.c_proj.weight"].astype(np.float64).T
    bias_1 = state["transformer.h.0.attn.c_proj.bias"].astype(np.float64)
    weight_2 = state["transformer.h.1.attn.c_proj.weight"].astype(np.float64).T
    bias_2 = state["transformer.h.1.attn.c_proj.bias"].astype(np.float64)
    return vector, weight_1, bias_1, weight_2, bias_2


def metric_chain(layer: int, child: str) -> str:
    for output in reversed(range(WIDTH)):
        child = (
            f'<i class="metric metric-l{layer}-{output:03d}" aria-hidden="true"></i>'
            f'<div class="probe probe-l{layer}-{output:03d}">{child}</div>'
        )
    return child


def page(
    vector: np.ndarray,
    quantized_1: QuantizedRows,
    bias_1: np.ndarray,
    range_0: float,
    base_1: int,
    quantized_2: QuantizedRows,
    bias_2: np.ndarray,
    range_1: float,
    base_2: int,
    expected: np.ndarray,
    font_tags: tuple[str, str],
) -> str:
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

    settings_1 = ",".join(
        f'"{axis_tag(index)}" {css_number(value / range_0)}'
        for index, value in enumerate(vector)
    )
    settings_2 = ",".join(
        f'"{axis_tag(index)}" calc(var(--l1-y-{index:03d})/{css_number(range_1)})'
        for index in range(WIDTH)
    )

    metric_rules = []
    probe_rules = []
    query_rules = []
    rescale_rules = {1: [], 2: []}
    layer_data = (
        (1, quantized_1, bias_1, range_0, base_1),
        (2, quantized_2, bias_2, range_1, base_2),
    )
    for layer, quantized, bias, activation_range, base in layer_data:
        for output in range(WIDTH):
            metric_rules.append(
                f'.metric-l{layer}-{output:03d}'
                f'{{anchor-name:--metric-l{layer}-{output:03d}}}'
                f'.metric-l{layer}-{output:03d}::before'
                f'{{content:"\\{0xE000 + output:x}"}}'
            )
            probe_rules.append(
                f'.probe-l{layer}-{output:03d}'
                f'{{position-anchor:--metric-l{layer}-{output:03d};'
                f'container:l{layer}y{output:03d}/inline-size;'
                f'width:anchor-size(--metric-l{layer}-{output:03d} width)}}'
            )
            if output + 1 < WIDTH:
                target = f'.probe-l{layer}-{output + 1:03d}'
            else:
                target = ".l1-result" if layer == 1 else ".final-result"
            factor = activation_range * quantized.scales[output]
            inverse_factor = 1 / factor
            query_rules.append(
                f'@container l{layer}y{output:03d} (width > 0px){{{target}'
                f'{{--l{layer}-raw-{output:03d}:calc('
                f'100cqi / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base})}}}}'
            )
            rescale_rules[layer].append(
                f'--l{layer}-y-{output:03d}:calc('
                f'var(--l{layer}-raw-{output:03d}) / {css_number(inverse_factor)}'
                f' + ({css_number(bias[output])}))'
            )

    final = '<div class="final-result" id="final-result"></div>'
    layer_2 = metric_chain(2, final)
    layer_1_result = f'<div class="l1-result">{layer_2}</div>'
    chain = metric_chain(1, layer_1_result)
    expected_data = ",".join(css_number(value) for value in expected)
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Signed two-layer direct-HVAR chain</title>
  <style>
    @font-face{{font-family:SignedL1;src:url("layer-1.woff2?v={font_tags[0]}") format("woff2")}}
    @font-face{{font-family:SignedL2;src:url("layer-2.woff2?v={font_tags[1]}") format("woff2")}}
    {''.join(registrations)}
    html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
    body{{margin:2rem;max-width:52rem}}
    h1{{font:600 1.25rem system-ui,sans-serif}}
    .metrics{{position:relative;min-height:1px}}
    .metric{{position:absolute;display:inline-block;width:max-content;height:1px;
      overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;font-kerning:none}}
    .metric[class*="metric-l1-"]{{font-family:SignedL1;font-variation-settings:{settings_1}}}
    .metric[class*="metric-l2-"]{{font-family:SignedL2;font-variation-settings:{settings_2}}}
    .probe{{position:absolute;inset:0 auto auto 0;height:1px}}
    {''.join(metric_rules)}
    {''.join(probe_rules)}
    {''.join(query_rules)}
    .l1-result{{{';'.join(rescale_rules[1])}}}
    .final-result{{{';'.join(rescale_rules[2])}}}
    .status{{padding:1rem;border:1px solid #aaa}}
  </style>
</head>
<body>
  <h1>Two signed TinyStories matrix layers in HTML/CSS</h1>
  <p class="status" data-expected="{expected_data}">No JavaScript. Two real 64×64 model matrices, quantized to signed 8-bit rows.</p>
  <div class="metrics">{chain}</div>
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
    vector, weight_1, bias_1, weight_2, bias_2 = real_matrices()
    quantized_1 = quantize_float_rows(weight_1)
    original_1 = weight_1 @ vector + bias_1
    reconstructed_1 = quantized_1.reconstructed @ vector + bias_1
    quantized_2 = quantize_float_rows(weight_2)
    original_2 = weight_2 @ original_1 + bias_2
    reconstructed_2 = quantized_2.reconstructed @ reconstructed_1 + bias_2
    range_0 = float(np.max(np.abs(vector)) * 1.01)
    range_1 = float(np.max(np.abs(reconstructed_1)) * 1.01)
    base_1 = safe_base_advance(quantized_1.codes)
    base_2 = safe_base_advance(quantized_2.codes)

    started = time.perf_counter()
    build_direct_font_backend(
        quantized_1.codes,
        OUT / "layer-1.ttf",
        signed_axes=True,
        base_advance=base_1,
    )
    build_direct_font_backend(
        quantized_2.codes,
        OUT / "layer-2.ttf",
        signed_axes=True,
        base_advance=base_2,
    )
    build_seconds = time.perf_counter() - started
    font_tags = tuple(
        hashlib.sha256((OUT / f"layer-{layer}.woff2").read_bytes()).hexdigest()[:12]
        for layer in (1, 2)
    )
    html_path = OUT / "index.html"
    html_path.write_text(
        page(
            vector,
            quantized_1,
            bias_1,
            range_0,
            base_1,
            quantized_2,
            bias_2,
            range_1,
            base_2,
            reconstructed_2,
            font_tags,
        )
    )
    runtime_paths = [html_path, OUT / "layer-1.woff2", OUT / "layer-2.woff2"]
    metadata = {
        "width": WIDTH,
        "bits": BITS,
        "build_seconds": build_seconds,
        "input_range": range_0,
        "intermediate_range": range_1,
        "base_advances": [base_1, base_2],
        "weight_sha256": [
            hashlib.sha256(weight_1.tobytes()).hexdigest(),
            hashlib.sha256(weight_2.tobytes()).hexdigest(),
        ],
        "row_scales": [quantized_1.scales.tolist(), quantized_2.scales.tolist()],
        "input": vector.tolist(),
        "biases": [bias_1.tolist(), bias_2.tolist()],
        "original_intermediate": original_1.tolist(),
        "quantized_intermediate": reconstructed_1.tolist(),
        "original_output": original_2.tolist(),
        "quantized_output": reconstructed_2.tolist(),
        "layer_1_max_error": float(np.max(np.abs(reconstructed_1 - original_1))),
        "layer_2_max_error": float(np.max(np.abs(reconstructed_2 - original_2))),
        "font_bytes": [(OUT / f"layer-{layer}.woff2").stat().st_size for layer in (1, 2)],
        "html_bytes": html_path.stat().st_size,
        "runtime_raw_bytes": sum(path.stat().st_size for path in runtime_paths),
        "runtime_brotli_bytes": sum(compressed_size(path) for path in runtime_paths),
    }
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print({key: metadata[key] for key in ("build_seconds", "layer_1_max_error", "layer_2_max_error", "font_bytes", "html_bytes", "runtime_raw_bytes", "runtime_brotli_bytes")})


if __name__ == "__main__":
    main()
