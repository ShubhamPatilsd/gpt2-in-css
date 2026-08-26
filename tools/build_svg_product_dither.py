#!/usr/bin/env python3
"""Test RGB deterministic dithering at SVG's matrix-product boundary."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-product-dither"
CENTER = 128 / 255
WIDTH = 64
DITHERS = np.asarray([-1 / 3, 0, 1 / 3]) / 255


def save_gray(path: Path, values: np.ndarray) -> None:
    Image.fromarray(
        np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8), mode="L"
    ).save(path, optimize=True)


def channel_matrix(target: int) -> str:
    rows = [[0.0] * 5 for _ in range(4)]
    rows[target][0] = 1
    rows[3][4] = 1
    return " ".join(str(value) for row in rows for value in row)


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
    input_range = max(float(np.max(np.abs(vector))) * 1.02, 1e-9)
    normalized_input = vector / input_range
    weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    )[:WIDTH, :WIDTH].T * input_range
    row_units = np.maximum(np.max(np.abs(weight), axis=1), 1e-12)
    normalized_weight = weight / row_units[:, None]
    expected = normalized_weight @ normalized_input
    output_bound = max(float(np.max(np.abs(expected))) * 1.05, 1e-9)

    save_gray(
        OUT / "input.png", (CENTER + normalized_input / 2).reshape(1, WIDTH)
    )
    save_gray(
        OUT / "weights.png", (CENTER + normalized_weight / 2)
    )

    product_base = 2 * CENTER * CENTER + CENTER
    product_parts = []
    for index, dither in enumerate(DITHERS):
        product_parts.append(
            f'<feComposite in="weights" in2="input-tile" '
            f'operator="arithmetic" k1="2" k2="{-2 * CENTER}" '
            f'k3="{-2 * CENTER}" k4="{product_base + dither:.12g}" '
            f'result="product-{index}"/>'
        )
    pack_parts = []
    for index in range(3):
        pack_parts.append(
            f'<feColorMatrix in="product-{index}" values="{channel_matrix(index)}" '
            f'result="lane-{index}"/>'
        )
    kernel = " ".join("1" for _ in range(WIDTH))
    reduction_bias = CENTER - WIDTH * CENTER / output_bound
    average_matrix = (
        "0.333333333333 0.333333333333 0.333333333333 0 0  " * 3
        + "0 0 0 0 1"
    )
    copy_red = "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
    html = f'''<!doctype html><meta charset="utf-8"><title>SVG product dithering</title>
<style>html,body{{margin:0;background:#000}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="2" height="{WIDTH}" viewBox="0 0 2 {WIDTH}" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="probe" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
 x="0" y="0" width="{WIDTH}" height="{WIDTH}" color-interpolation-filters="sRGB">
<feImage href="input.png" x="0" y="0" width="{WIDTH}" height="1" result="input"/>
<feTile in="input" x="0" y="0" width="{WIDTH}" height="{WIDTH}" result="input-tile"/>
<feImage href="weights.png" x="0" y="0" width="{WIDTH}" height="{WIDTH}" result="weights"/>
{''.join(product_parts)}
<feConvolveMatrix in="product-1" order="{WIDTH} 1" kernelMatrix="{kernel}"
 divisor="{output_bound}" bias="{reduction_bias}" targetX="{WIDTH - 1}" targetY="0"
 edgeMode="none" preserveAlpha="true" x="{WIDTH - 1}" y="0" width="1" height="{WIDTH}"
 result="baseline-sum"/>
<feColorMatrix in="baseline-sum" values="{copy_red}" result="baseline-common"/>
<feOffset in="baseline-common" dx="-{WIDTH - 1}" x="0" y="0" width="1" height="{WIDTH}" result="baseline"/>
{''.join(pack_parts)}
<feBlend in="lane-0" in2="lane-1" mode="screen" result="lanes-01"/>
<feBlend in="lanes-01" in2="lane-2" mode="screen" result="lanes"/>
<feConvolveMatrix in="lanes" order="{WIDTH} 1" kernelMatrix="{kernel}"
 divisor="{output_bound}" bias="{reduction_bias}" targetX="{WIDTH - 1}" targetY="0"
 edgeMode="none" preserveAlpha="true" x="{WIDTH - 1}" y="0" width="1" height="{WIDTH}"
 result="dither-sums"/>
<feColorMatrix in="dither-sums" values="{average_matrix}" result="dither-common"/>
<feOffset in="dither-common" dx="-{WIDTH - 2}" x="1" y="0" width="1" height="{WIDTH}" result="dither"/>
<feMerge><feMergeNode in="baseline"/><feMergeNode in="dither"/></feMerge>
</filter></defs><rect width="{WIDTH}" height="{WIDTH}" fill="white" filter="url(#probe)"/></svg>'''
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "center": CENTER,
                "width": WIDTH,
                "output_bound": output_bound,
                "expected": expected.tolist(),
                "html_bytes": len(html.encode()),
            },
            indent=2,
        )
        + "\n"
    )
    print({"output": str(OUT), "html_bytes": len(html.encode())})


if __name__ == "__main__":
    main()
