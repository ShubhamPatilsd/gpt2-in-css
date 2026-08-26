#!/usr/bin/env python3
"""Build one connected 12-block, one-token GPT-2 page with flat MLP stages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from build_geometry_streaming_full_tail import extract_div
from build_gpt2_block_css import (
    OUT as BLOCK_OUT,
    QUANT_BITS,
    WIDTH,
    gelu_new,
    layer_norm,
    model_data,
)
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-flat-12block-chain"


def block_forward(layer: int, vector: np.ndarray) -> np.ndarray:
    data = model_data(layer, input_vector=vector)
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    attention = quantize_float_rows(
        composed_weight, bits=QUANT_BITS
    ).reconstructed @ layer_norm(
        vector, data["ln1_gamma"], data["ln1_beta"]
    ) + composed_bias
    residual = vector + attention
    hidden = gelu_new(
        quantize_float_rows(
            data["fc_weight"], bits=QUANT_BITS
        ).reconstructed @ layer_norm(
            residual, data["ln2_gamma"], data["ln2_beta"]
        ) + data["fc_bias"]
    )
    return (
        residual
        + quantize_float_rows(
            data["mlp_proj_weight"], bits=QUANT_BITS
        ).reconstructed @ hidden
        + data["mlp_proj_bias"]
    )


def forward_trace(initial: np.ndarray) -> list[np.ndarray]:
    trace = [np.asarray(initial, dtype=np.float64)]
    for layer in range(12):
        trace.append(block_forward(layer, trace[-1]))
    return trace


def rewrite_layer_assets(layer: int, directory: Path) -> tuple[str, str]:
    attention_css = directory / "view-timeline-two-block-attention-probe-exact.css"
    full_css = directory / "view-timeline-two-block-full-exact.css"
    isolated_html = directory / "view-timeline-block1-full-isolated-exact.html"
    css = attention_css.read_text() + full_css.read_text()
    html = isolated_html.read_text()

    for path in sorted(directory.glob("b1-*.woff2")):
        renamed = path.with_name(path.name.replace("b1", f"b{layer}", 1))
        path.replace(renamed)
    for path in sorted(directory.glob("b1-*.ttf")):
        renamed = path.with_name(path.name.replace("b1", f"b{layer}", 1))
        path.replace(renamed)

    css = css.replace("b1", f"b{layer}").replace(
        "two-block", f"block{layer}"
    )
    html = html.replace("b1", f"b{layer}").replace(
        "two-block", f"block{layer}"
    )
    stage = extract_div(html, f'<div class="b{layer}-norm">')
    if layer > 1:
        aliases = ";".join(
            f"--out-{index:03d}:var(--b{layer - 1}-final-{index:03d})"
            for index in range(WIDTH)
        )
        stage = stage.replace(
            f'<div class="b{layer}-norm">',
            f'<div class="b{layer}-norm" style="{aliases}">',
            1,
        )
    (directory / "layer.css").write_text(css)
    (directory / "stage.html").write_text(stage)
    standalone = re.sub(
        r'<link rel="stylesheet" href="[^"]+">',
        "",
        html,
    ).replace(
        "</title>", '</title><link rel="stylesheet" href="layer.css">', 1
    )
    (directory / "standalone.html").write_text(standalone)
    return css, stage


def attach_next(stage: str, layer: int, child: str) -> str:
    pattern = re.compile(
        rf'<output id="block{layer}-full" '
        rf'class="(b{layer}proj-result-\d+)">.*?</output>'
    )
    match = pattern.search(stage)
    if not match:
        raise ValueError(f"missing block {layer} output leaf")
    replacement = (
        f'<div id="block{layer}-full" class="{match.group(1)}">'
        f"{child}</div>"
    )
    return stage[: match.start()] + replacement + stage[match.end() :]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    initial = np.asarray(model_data(0)["x"], dtype=np.float64)
    alternate = initial.copy()
    alternate[0] += 0.125
    baseline_trace = forward_trace(initial)
    alternate_trace = forward_trace(alternate)

    stages: dict[int, str] = {}
    source_dir = Path(os.environ.get("FLAT_12BLOCK_SOURCE_DIR", BLOCK_OUT))
    for layer in range(1, 12):
        directory = OUT / f"layer{layer:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        input_path = directory / "input.json"
        input_path.write_text(json.dumps(baseline_trace[layer].tolist()) + "\n")
        environment = os.environ.copy()
        environment.update(
            {
                "GPT2_BLOCK_CSS_OUT": str(directory),
                "TWO_BLOCK_SOURCE_DIR": str(source_dir),
                "TWO_BLOCK_SOURCE_MODE": "exact",
                "TWO_BLOCK_TARGET_LAYER": str(layer),
                "TWO_BLOCK_INPUT_JSON": str(input_path),
                "TWO_BLOCK_REBUILD_FONTS": "1",
                "PYTHONPATH": str(ROOT / "tools"),
            }
        )
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_view_timeline_two_block_probe.py")],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        _css, stages[layer] = rewrite_layer_assets(layer, directory)
        print(f"built flat block {layer}", flush=True)

    nested = stages[11]
    for layer in reversed(range(1, 11)):
        nested = attach_next(stages[layer], layer, nested)

    source = (source_dir / "view-timeline-block-hybrid.html").read_text()
    source = re.sub(
        r'href="(view-timeline-block-hybrid\.css[^\"]*)"',
        r'href="../gpt2-block-css/\1"',
        source,
        count=1,
    )
    links = "".join(
        f'<link rel="stylesheet" href="layer{layer:02d}/layer.css?'
        f'v={hashlib.sha256((OUT / f"layer{layer:02d}" / "layer.css").read_bytes()).hexdigest()[:12]}">' 
        for layer in range(1, 12)
    )
    source = source.replace("</title>", f"</title>{links}", 1)
    leaf = '<output id="final" class="proj-result-5"></output>'
    if source.count(leaf) != 1:
        raise ValueError("missing block-0 flat output leaf")
    source = source.replace(
        leaf,
        f'<div id="final" class="proj-result-5">{nested}</div>',
        1,
    )
    source = source.replace(
        "Complete one-token GPT-2 block in CSS",
        "Connected twelve-block flat-MLP GPT-2",
        1,
    )
    (OUT / "index.html").write_text(source)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "runtimeJavaScript": False,
                "context": 1,
                "blocks": 12,
                "quantizedWeightBits": QUANT_BITS,
                "input": initial.tolist(),
                "alternateInput": alternate.tolist(),
                "baselineTrace": [value.tolist() for value in baseline_trace],
                "alternateTrace": [value.tolist() for value in alternate_trace],
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "htmlBytes": (OUT / "index.html").stat().st_size,
                "layers": 12,
                "output": str(OUT / "index.html"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
