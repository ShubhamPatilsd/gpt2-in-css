#!/usr/bin/env python3
"""Compare one packed 2D SVG convolution with per-row dense dot products."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-packed-kernel-matrix"
CENTER = 128 / 255
WIDTH = int(os.environ.get("SVG_PACKED_KERNEL_WIDTH", "64"))


def save_rgb(path: Path, values: np.ndarray) -> None:
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    code = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    rgba[..., :3] = code[..., None]
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def kernel_row(
    row: np.ndarray,
    bias: float,
    input_range: float,
    output_range: float,
) -> np.ndarray:
    ratio = input_range / output_range
    weights = row * ratio
    intercept = (
        CENTER
        - CENTER * float(np.sum(weights))
        + bias / (2 * output_range)
    )
    # SVG convolution reverses the kernel in both axes. The constant white
    # source pixel is the final input coordinate before reversal.
    return np.concatenate(([intercept], weights[::-1]))


def page(title: str, body: str, output: str) -> str:
    return f'''<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>html,body{{margin:0;background:#000}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="1" height="{WIDTH}" viewBox="0 0 1 {WIDTH}" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="probe" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
 x="0" y="0" width="{WIDTH + 1}" height="{WIDTH}" color-interpolation-filters="sRGB">
<feFlood flood-color="black" flood-opacity="1" x="0" y="0" width="{WIDTH + 1}" height="{WIDTH}" result="background"/>
<feImage href="input.png" x="0" y="0" width="{WIDTH + 1}" height="1" result="input-row"/>
<feMerge result="input"><feMergeNode in="background"/><feMergeNode in="input-row"/></feMerge>
{body}<feOffset in="{output}" dx="-{WIDTH}" x="0" y="0" width="1" height="{WIDTH}"/>
</filter></defs><rect width="{WIDTH + 1}" height="{WIDTH}" fill="white" filter="url(#probe)"/></svg>'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads(
        (
            ROOT
            / "experiments/gpt2-block-css/view-timeline-attention-2token-reference.json"
        ).read_text()
    )
    tensors = SafeTensors(MODEL_PATH)
    vector = np.asarray(reference["context"], dtype=np.float64)[1, :WIDTH]
    weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    )[:WIDTH, :WIDTH].T
    bias = np.asarray(
        tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64
    )[:WIDTH]
    expected = weight @ vector + bias
    input_range = max(float(np.max(np.abs(vector))) * 1.08, 1e-9)
    output_range = max(float(np.max(np.abs(expected))) * 1.08, 1e-9)

    encoded = np.empty(WIDTH + 1, dtype=np.float64)
    encoded[:WIDTH] = CENTER + vector / (2 * input_range)
    encoded[WIDTH] = 1
    save_rgb(OUT / "input.png", encoded.reshape(1, WIDTH + 1))

    rows = [
        kernel_row(row, float(row_bias), input_range, output_range)
        for row, row_bias in zip(weight, bias)
    ]
    packed_kernel = " ".join(
        f"{value:.12g}" for row in rows for value in row
    )
    packed_body = (
        f'<feConvolveMatrix in="input" order="{WIDTH + 1} {WIDTH}" '
        f'kernelMatrix="{packed_kernel}" divisor="1" bias="0" '
        f'targetX="{WIDTH}" targetY="{WIDTH - 1}" edgeMode="none" '
        f'preserveAlpha="true" x="{WIDTH}" y="0" width="1" '
        f'height="{WIDTH}" result="packed"/>'
    )

    direct_parts = []
    direct_outputs = []
    for output, row in enumerate(rows):
        result = f"direct-{output}-raw"
        placed = f"direct-{output}"
        direct_parts.extend(
            (
                f'<feConvolveMatrix in="input" order="{WIDTH + 1} 1" '
                f'kernelMatrix="{" ".join(f"{value:.12g}" for value in row)}" '
                f'divisor="1" bias="0" targetX="{WIDTH}" targetY="0" '
                f'edgeMode="none" preserveAlpha="true" x="{WIDTH}" y="0" '
                f'width="1" height="1" result="{result}"/>',
                f'<feOffset in="{result}" dy="{output}" x="{WIDTH}" y="{output}" '
                f'width="1" height="1" result="{placed}"/>',
            )
        )
        direct_outputs.append(placed)
    direct_parts.append(
        '<feMerge result="direct">'
        + "".join(f'<feMergeNode in="{name}"/>' for name in direct_outputs)
        + "</feMerge>"
    )
    direct_body = "".join(direct_parts)

    packed_html = page("Packed 2D dense matrix", packed_body, "packed")
    direct_html = page("Per-row dense matrix", direct_body, "direct")
    (OUT / "packed.html").write_text(packed_html)
    (OUT / "direct.html").write_text(direct_html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "center": CENTER,
                "width": WIDTH,
                "input_range": input_range,
                "output_range": output_range,
                "expected": expected.tolist(),
                "packed_html_bytes": len(packed_html.encode()),
                "direct_html_bytes": len(direct_html.encode()),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "output": str(OUT),
            "packed_html_bytes": len(packed_html.encode()),
            "direct_html_bytes": len(direct_html.encode()),
        }
    )


if __name__ == "__main__":
    main()
