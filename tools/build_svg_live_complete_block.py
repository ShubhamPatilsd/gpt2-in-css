#!/usr/bin/env python3
"""Build one complete live GPT-2 block from the optimized SVG stages."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from build_gpt2_block_css import gelu_new, layer_norm, model_data


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "SVG_LIVE_BLOCK_SOURCE", ROOT / "experiments" / "svg-live-layernorm"
    )
).resolve()
MLP = Path(
    os.environ.get(
        "SVG_LIVE_BLOCK_MLP",
        ROOT / "experiments" / "svg-filter-gpt2-fc-live-calibrated",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_LIVE_BLOCK_OUT", ROOT / "experiments" / "svg-live-complete-block"
    )
).resolve()
WIDTH = 768
HIDDEN = 3072
SHARD = 256
CENTER = 128 / 255
LN_X = int(os.environ.get("SVG_LIVE_BLOCK_LN_X", "63"))
RESIDUAL_X = LN_X - 1
OUTPUT_X = SHARD - 1
BLOCK_INDEX = int(os.environ.get("SVG_LIVE_BLOCK_INDEX", "0"))
GPU_VETO_PATHS = int(os.environ.get("SVG_LIVE_BLOCK_GPU_VETO_PATHS", "0"))


def svg_parts(page: str) -> tuple[str, str]:
    defs_marker = page.index("<defs")
    defs_start = page.index(">", defs_marker) + 1
    defs_end = page.index("</defs>", defs_start)
    content_start = defs_end + len("</defs>")
    content_end = page.rindex("</svg>")
    return page[defs_start:defs_end], page[content_start:content_end]


def transpose_image(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        image.transpose(Image.Transpose.TRANSPOSE).save(destination, optimize=True)


def save_gray(path: Path, values: np.ndarray) -> None:
    pixels = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("mlp-*.png"):
        stale.unlink()

    source_page = (SOURCE / "index.html").read_text()
    source_relative = os.path.relpath(SOURCE, OUT)
    source_defs, source_content = svg_parts(source_page)
    source_defs = source_defs.replace('href="', f'href="{source_relative}/')
    live_reference = json.loads((SOURCE / "reference.json").read_text())
    fc_reference = json.loads((MLP / "reference.json").read_text())
    full_reference = json.loads((MLP / "full-reference.json").read_text())
    expected = np.asarray(full_reference["expected"], dtype=np.float64)
    residual_scales = np.asarray(
        live_reference["residualScales"], dtype=np.float64
    )
    data = model_data(block_index=BLOCK_INDEX)
    next_block = model_data(block_index=BLOCK_INDEX + 1, input_vector=expected)
    next_ln_expected = layer_norm(
        expected, next_block["ln1_gamma"], next_block["ln1_beta"]
    )

    for shard in range(WIDTH // SHARD):
        transpose_image(
            MLP / f"weights-centered-{shard}.png",
            OUT / f"mlp-fc-weights-{shard}.png",
        )
    transpose_image(MLP / "bias.png", OUT / "mlp-fc-bias.png")
    transpose_image(MLP / "pre-scales.png", OUT / "mlp-pre-scales.png")
    for shard in range(HIDDEN // SHARD):
        transpose_image(
            MLP / f"projection-weights-{shard}.png",
            OUT / f"mlp-projection-weights-{shard}.png",
        )

    fc_divisor = float(fc_reference["divisor"])
    fc_units = np.asarray(fc_reference["units"], dtype=np.float64)
    fc_input_scale = float(fc_reference["input_scale"])
    fc_gain = float(fc_reference["centered_gain"])
    ln_output_range = float(live_reference["outputRange"])
    pre_range = float(full_reference["pre_range"])
    hidden_range = float(full_reference["hidden_range"])
    projection_divisor = float(full_reference["projection_divisor"])
    projection_magnitude_divisor = float(
        full_reference["projection_magnitude_divisor"]
    )
    projection_units = np.asarray(
        full_reference["projection_units"], dtype=np.float64
    )
    final_scales = projection_divisor * projection_units

    center_css = f"{CENTER:.12g}"
    kernel = " ".join("1" for _ in range(SHARD))
    copy_red = "1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"
    sum_channels = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_channels = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    swap_red_green = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"

    primitives: list[str] = []
    input_ratio = ln_output_range / fc_input_scale
    centered_parts: list[str] = []
    centered_convolution_divisor = fc_gain * fc_divisor / 2
    centered_convolution_bias = (
        CENTER - SHARD * CENTER / centered_convolution_divisor
    )
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        prefix = f"mlp-fc-{shard}"
        primitives.extend(
            (
                f'<feOffset in="SourceGraphic" dx="-{LN_X}" dy="-{start}" '
                f'x="0" y="0" width="1" height="{SHARD}" '
                f'result="{prefix}-column"/>',
                f'<feColorMatrix in="{prefix}-column" values="'
                f'{input_ratio} 0 0 0 {CENTER * (1 - input_ratio)}  '
                f'{input_ratio} 0 0 0 {CENTER * (1 - input_ratio)}  '
                f'{input_ratio} 0 0 0 {CENTER * (1 - input_ratio)}  '
                f'0 0 0 0 1" result="{prefix}-normalized"/>',
                f'<feTile in="{prefix}-normalized" x="0" y="0" '
                f'width="{HIDDEN}" height="{SHARD}" '
                f'result="{prefix}-values"/>',
                f'<feImage href="mlp-fc-weights-{shard}.png" x="0" y="0" '
                f'width="{HIDDEN}" height="{SHARD}" '
                f'preserveAspectRatio="none" result="{prefix}-weights"/>',
                f'<feComposite in="{prefix}-weights" in2="{prefix}-values" '
                f'operator="arithmetic" k1="{fc_gain}" '
                f'k2="{-fc_gain * CENTER}" k3="{-fc_gain * CENTER}" '
                f'k4="{CENTER + fc_gain * CENTER * CENTER}" '
                f'result="{prefix}-products"/>',
                f'<feConvolveMatrix in="{prefix}-products" order="1 {SHARD}" '
                f'kernelMatrix="{kernel}" divisor="{centered_convolution_divisor}" '
                f'bias="{centered_convolution_bias}" targetX="0" '
                f'targetY="{SHARD - 1}" edgeMode="none" '
                f'kernelUnitLength="1 1" preserveAlpha="false" '
                f'x="0" y="{SHARD - 1}" width="{HIDDEN}" height="1" '
                f'result="{prefix}-dot"/>',
            )
        )
        centered_parts.append(f"{prefix}-dot")
    dot = centered_parts[0]
    for shard, part in enumerate(centered_parts[1:], 1):
        result = f"mlp-fc-dot-{shard}"
        primitives.append(
            f'<feComposite in="{dot}" in2="{part}" operator="arithmetic" '
            f'k1="0" k2="1" k3="1" k4="-{center_css}" result="{result}"/>'
        )
        dot = result
    primitives.extend(
        (
            f'<feImage href="mlp-fc-bias.png" x="0" y="{OUTPUT_X}" '
            f'width="{HIDDEN}" height="1" preserveAspectRatio="none" '
            'result="mlp-fc-bias"/>',
            f'<feComposite in="{dot}" in2="mlp-fc-bias" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="mlp-fc-affine"/>',
        )
    )

    max_unit = float(np.max(fc_units))
    pre_scale_coefficient = fc_divisor * max_unit / pre_range
    primitives.extend(
        (
            f'<feImage href="mlp-pre-scales.png" x="0" y="{OUTPUT_X}" '
            f'width="{HIDDEN}" height="1" preserveAspectRatio="none" '
            'result="mlp-pre-scales"/>',
            '<feComposite in="mlp-fc-affine" in2="mlp-pre-scales" '
            f'operator="arithmetic" k1="{pre_scale_coefficient}" k2="0" '
            f'k3="{-pre_scale_coefficient * CENTER}" k4="{center_css}" '
            'result="mlp-pre-normalized-alpha"/>',
            f'<feColorMatrix in="mlp-pre-normalized-alpha" values="{copy_red}" '
            'result="mlp-pre-normalized"/>',
        )
    )
    table_input = np.linspace(0, 1, 256)
    table_pre = (table_input - CENTER) * 2 * pre_range
    table_hidden = gelu_new(table_pre)
    positive_table = " ".join(
        f"{value:.8g}" for value in np.clip(table_hidden, 0, None) / hidden_range
    )
    negative_table = " ".join(
        f"{value:.8g}" for value in np.clip(-table_hidden, 0, None) / hidden_range
    )
    primitives.append(
        '<feComponentTransfer in="mlp-pre-normalized" result="mlp-hidden">'
        f'<feFuncR type="table" tableValues="{positive_table}"/>'
        f'<feFuncG type="table" tableValues="{negative_table}"/>'
        '<feFuncB type="table" tableValues="0 0"/>'
        '<feFuncA type="identity"/></feComponentTransfer>'
    )

    projection_signed_coefficient = projection_magnitude_divisor / (
        2 * projection_divisor
    )
    projection_signed_gray = (
        f"{projection_signed_coefficient} -{projection_signed_coefficient} 0 0 {center_css}  "
        f"{projection_signed_coefficient} -{projection_signed_coefficient} 0 0 {center_css}  "
        f"{projection_signed_coefficient} -{projection_signed_coefficient} 0 0 {center_css}  "
        "0 0 0 0 1"
    )
    projected_parts: list[str] = []
    for shard, start in enumerate(range(0, HIDDEN, SHARD)):
        prefix = f"mlp-projection-{shard}"
        primitives.extend(
            (
                f'<feOffset in="mlp-hidden" dx="-{start}" dy="-{OUTPUT_X}" '
                f'x="0" y="0" width="{SHARD}" height="1" '
                f'result="{prefix}-row"/>',
                f'<feTile in="{prefix}-row" x="0" y="0" width="{SHARD}" '
                f'height="{WIDTH}" result="{prefix}-values"/>',
                f'<feColorMatrix in="{prefix}-values" '
                f'values="{swap_red_green}" result="{prefix}-swapped"/>',
                f'<feImage href="mlp-projection-weights-{shard}.png" '
                f'x="0" y="0" width="{SHARD}" height="{WIDTH}" '
                f'preserveAspectRatio="none" result="{prefix}-weights"/>',
                f'<feComposite in="{prefix}-weights" in2="{prefix}-values" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-same"/>',
                f'<feComposite in="{prefix}-weights" in2="{prefix}-swapped" '
                f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                f'result="{prefix}-cross"/>',
                f'<feColorMatrix in="{prefix}-same" values="{sum_channels}" '
                f'result="{prefix}-positive"/>',
                f'<feColorMatrix in="{prefix}-cross" '
                f'values="{negative_channels}" result="{prefix}-negative"/>',
                f'<feComposite in="{prefix}-positive" '
                f'in2="{prefix}-negative" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="0" '
                f'result="{prefix}-split"/>',
                f'<feConvolveMatrix in="{prefix}-split" order="{SHARD} 1" '
                f'kernelMatrix="{kernel}" divisor="{projection_magnitude_divisor}" '
                f'bias="0" targetX="{SHARD - 1}" targetY="0" '
                f'edgeMode="none" kernelUnitLength="1 1" preserveAlpha="true" '
                f'x="{OUTPUT_X}" y="0" width="1" height="{WIDTH}" '
                f'result="{prefix}-sum"/>',
                f'<feColorMatrix in="{prefix}-sum" '
                f'values="{projection_signed_gray}" '
                f'result="{prefix}-projected"/>',
            )
        )
        projected_parts.append(f"{prefix}-projected")
    projected = projected_parts[0]
    for shard, part in enumerate(projected_parts[1:], 1):
        result = f"mlp-projected-total-{shard}"
        primitives.append(
            f'<feComposite in="{projected}" in2="{part}" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="{result}"/>'
        )
        projected = result

    save_gray(
        OUT / "mlp-projection-bias.png",
        (CENTER + np.asarray(data["mlp_proj_bias"]) / (2 * final_scales)).reshape(
            WIDTH, 1
        ),
    )
    residual_ratios = residual_scales / final_scales
    residual_ratio_max = float(np.max(residual_ratios))
    save_gray(
        OUT / "mlp-residual-ratios.png",
        (residual_ratios / residual_ratio_max).reshape(WIDTH, 1),
    )
    primitives.extend(
        (
            f'<feImage href="mlp-projection-bias.png" x="{OUTPUT_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="mlp-projection-bias"/>',
            f'<feComposite in="{projected}" in2="mlp-projection-bias" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="mlp-projected-biased"/>',
            f'<feOffset in="SourceGraphic" dx="{OUTPUT_X - RESIDUAL_X}" '
            f'x="{OUTPUT_X}" y="0" width="1" height="{WIDTH}" '
            'result="mlp-live-residual-encoded"/>',
            f'<feImage href="mlp-residual-ratios.png" x="{OUTPUT_X}" y="0" '
            f'width="1" height="{WIDTH}" preserveAspectRatio="none" '
            'result="mlp-residual-ratios"/>',
            '<feComposite in="mlp-live-residual-encoded" '
            'in2="mlp-residual-ratios" operator="arithmetic" '
            f'k1="{residual_ratio_max}" k2="0" '
            f'k3="{-CENTER * residual_ratio_max}" k4="{center_css}" '
            'result="mlp-live-residual"/>',
            '<feComposite in="mlp-projected-biased" in2="mlp-live-residual" '
            f'operator="arithmetic" k1="0" k2="1" k3="1" '
            f'k4="-{center_css}" result="mlp-final"/>',
        )
    )

    mlp_filter = (
        '<filter id="mlp-stage" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" '
        f'width="{HIDDEN}" height="{WIDTH}" '
        f'color-interpolation-filters="sRGB">{"".join(primitives)}</filter>'
    )
    veto_markup = ""
    if GPU_VETO_PATHS:
        # Chromium can veto GPU rasterization for pages containing many
        # non-convex SVG paths. Keep these sub-pixel and visually inert while
        # testing whether that page-level heuristic benefits filter inference.
        path = (
            f'<path d="M {OUTPUT_X + .1} .1 L {OUTPUT_X + .9} .9 '
            f'L {OUTPUT_X + .1} .9 L {OUTPUT_X + .9} .1 Z" '
            'fill="black" opacity=".000001"/>'
        )
        veto_markup = f'<g aria-hidden="true">{path * GPU_VETO_PATHS}</g>'
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>One complete live GPT-2 block in HTML and CSS</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="1" height="{WIDTH}" viewBox="{OUTPUT_X} 0 1 {WIDTH}" '
        f'xmlns="http://www.w3.org/2000/svg"><defs>{source_defs}{mlp_filter}</defs>'
        f'<g filter="url(#mlp-stage)">{source_content}</g>{veto_markup}</svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "width": WIDTH,
                "blockIndex": BLOCK_INDEX,
                "gpuVetoPaths": GPU_VETO_PATHS,
                "outputX": OUTPUT_X,
                "surfaceCenter": CENTER,
                "finalScales": final_scales.tolist(),
                "expected": expected.tolist(),
                "nextLnGamma": next_block["ln1_gamma"].tolist(),
                "nextLnBeta": next_block["ln1_beta"].tolist(),
                "nextLnExpected": next_ln_expected.tolist(),
                "source": os.path.relpath(SOURCE, OUT),
                "mlp": os.path.relpath(MLP, OUT),
                "mlpPrimitiveCount": len(primitives),
                "htmlBytes": len(html.encode()),
            }
        )
        + "\n"
    )
    print(
        {
            "html_bytes": len(html.encode()),
            "mlp_primitives": len(primitives),
            "asset_bytes": sum(path.stat().st_size for path in OUT.glob("*.png")),
        }
    )


if __name__ == "__main__":
    main()
