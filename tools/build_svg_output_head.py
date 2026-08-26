#!/usr/bin/env python3
"""Build a full 50,257-row GPT-2 output head with SVG filters only."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "svg-filter-full-block"
OUT = ROOT / "experiments" / "svg-filter-output-head"
REFERENCE = SOURCE / "reference.json"
WIDTH = 768
VOCABULARY = 50_257
SHARD = 256
ROWS_PER_COLUMN = 256
WORK_HEIGHT = max(ROWS_PER_COLUMN, SHARD)
CENTER = 128 / 255
CX = SHARD - 1
CY = SHARD - 1


def save_gray(path: Path, values: np.ndarray) -> None:
    pixels = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(path, optimize=True)


def save_rg(path: Path, positive: np.ndarray, negative: np.ndarray) -> None:
    rgba = np.zeros((*positive.shape, 4), dtype=np.uint8)
    rgba[..., 0] = np.rint(np.clip(positive, 0, 1) * 255).astype(np.uint8)
    rgba[..., 1] = np.rint(np.clip(negative, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale_asset in OUT.glob("head-c*.png"):
        stale_asset.unlink()
    reference = json.loads(REFERENCE.read_text())
    original = np.asarray(reference["bucket_final_ln_expected"], dtype=np.float64)
    alternate = np.asarray(reference["bucket_final_ln_expected_alt"], dtype=np.float64)
    input_scales = np.asarray(reference["bucket_final_ln_scales"], dtype=np.float64)
    embeddings = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight"), dtype=np.float64
    )
    normalized = original / input_scales
    normalized_alternate = alternate / input_scales
    logits = embeddings @ original
    alternate_logits = embeddings @ alternate
    # Subtracting the same query-dependent scalar from every token score cannot
    # change argmax. Centering the embedding rows removes that common offset
    # before the values enter the browser's 8-bit filter surfaces.
    centered_embeddings = embeddings - embeddings.mean(axis=0, keepdims=True)
    centered_logits = centered_embeddings @ original
    centered_alternate_logits = centered_embeddings @ alternate
    output_range = float(
        max(
            np.max(np.abs(centered_logits)),
            np.max(np.abs(centered_alternate_logits)),
        )
        * 1.04
    )
    scaled_embeddings = centered_embeddings * input_scales[None, :]
    row_weight_scales = np.maximum(
        np.max(np.abs(scaled_embeddings), axis=1), 1e-12
    )
    normalized_rows = scaled_embeddings / row_weight_scales[:, None]
    row_error_scale = np.zeros(VOCABULARY, dtype=np.float64)
    for shard in range(0, WIDTH, SHARD):
        weights_shard = normalized_rows[:, shard : shard + SHARD]
        for query in (normalized, normalized_alternate):
            products = weights_shard * query[None, shard : shard + SHARD]
            row_error_scale = np.maximum(
                row_error_scale,
                np.maximum(products, 0).sum(axis=1),
            )
            row_error_scale = np.maximum(
                row_error_scale,
                np.maximum(-products, 0).sum(axis=1),
            )
    row_error_scale *= row_weight_scales
    token_order = np.argsort(row_error_scale, kind="stable")

    save_gray(
        OUT / "input.png",
        (CENTER + original / (2 * input_scales)).reshape(1, WIDTH),
    )
    save_gray(
        OUT / "input-alt.png",
        (CENTER + alternate / (2 * input_scales)).reshape(1, WIDTH),
    )

    center_css = f"{CENTER:.12g}"
    kernel = " ".join("1" for _ in range(SHARD))
    swap_rg = "0 1 0 0 0  1 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    positive_matrix = "1 1 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0 1"
    negative_matrix = "0 0 0 0 0  1 1 0 0 0  0 0 0 0 0  0 0 0 0 1"
    signed_to_common = (
        f".5 -.5 0 0 {center_css}  .5 -.5 0 0 {center_css}  "
        f".5 -.5 0 0 {center_css}  0 0 0 0 1"
    )
    primitives: list[str] = []

    grid = np.linspace(0, 1, 256)
    positive_table = " ".join(
        f"{value:.8g}" for value in np.clip(2 * (grid - CENTER), 0, 1)
    )
    negative_table = " ".join(
        f"{value:.8g}" for value in np.clip(2 * (CENTER - grid), 0, 1)
    )
    primitives.append(
        '<feImage href="input.png" x="0" y="255" width="768" height="1" '
        'preserveAspectRatio="none" result="input-common"/>'
        '<feComponentTransfer in="input-common" result="input-signed">'
        f'<feFuncR type="table" tableValues="{positive_table}"/>'
        f'<feFuncG type="table" tableValues="{negative_table}"/>'
        '<feFuncB type="table" tableValues="0 0"/>'
        '<feFuncA type="identity"/></feComponentTransfer>'
    )

    def matrix_column(start: int, stop: int, column: int) -> str:
        prefix = f"head-c{column:02d}"
        token_ids = token_order[start:stop]
        weights = centered_embeddings[token_ids] * input_scales[None, :]
        outputs = stop - start
        weight_scales = np.maximum(np.max(np.abs(weights), axis=1), 1e-12)
        units = weight_scales
        normalized_weights = weights / weight_scales[:, None]
        partials = np.stack(
            [
                normalized_weights[:, shard : shard + SHARD]
                @ normalized[shard : shard + SHARD]
                for shard in range(0, WIDTH, SHARD)
            ],
            axis=1,
        )
        alternate_partials = np.stack(
            [
                normalized_weights[:, shard : shard + SHARD]
                @ normalized_alternate[shard : shard + SHARD]
                for shard in range(0, WIDTH, SHARD)
            ],
            axis=1,
        )
        cumulative = np.cumsum(partials, axis=1)
        alternate_cumulative = np.cumsum(alternate_partials, axis=1)
        divisor = max(
            float(np.max(np.abs(cumulative))),
            float(np.max(np.abs(alternate_cumulative))),
            1e-12,
        ) * 1.02
        magnitude = 0.0
        for shard in range(0, WIDTH, SHARD):
            products = (
                normalized_weights[:, shard : shard + SHARD]
                * normalized[None, shard : shard + SHARD]
            )
            alternate_products = (
                normalized_weights[:, shard : shard + SHARD]
                * normalized_alternate[None, shard : shard + SHARD]
            )
            magnitude = max(
                magnitude,
                float(np.max(np.maximum(products, 0).sum(axis=1))),
                float(np.max(np.maximum(-products, 0).sum(axis=1))),
                float(np.max(np.maximum(alternate_products, 0).sum(axis=1))),
                float(np.max(np.maximum(-alternate_products, 0).sum(axis=1))),
            )
        magnitude *= 1.02
        coefficient = magnitude / (2 * divisor)
        signed_matrix = (
            f"{coefficient} -{coefficient} 0 0 {center_css}  " * 3
            + "0 0 0 0 1"
        )
        encoded_parts: list[str] = []
        for shard_index, shard in enumerate(range(0, WIDTH, SHARD)):
            weights_image = normalized_weights[:, shard : shard + SHARD]
            save_rg(
                OUT / f"{prefix}-w{shard_index}.png",
                np.maximum(weights_image, 0),
                np.maximum(-weights_image, 0),
            )
            primitives.extend(
                (
                    f'<feOffset in="input-signed" dx="-{shard}" dy="-{CY}" '
                    f'x="0" y="0" width="{SHARD}" height="1" '
                    f'result="{prefix}-row{shard_index}"/>',
                    f'<feTile in="{prefix}-row{shard_index}" x="0" y="0" '
                    f'width="{SHARD}" height="{outputs}" '
                    f'result="{prefix}-values{shard_index}"/>',
                    f'<feColorMatrix in="{prefix}-values{shard_index}" '
                    f'values="{swap_rg}" result="{prefix}-swapped{shard_index}"/>',
                    f'<feImage href="{prefix}-w{shard_index}.png" x="0" y="0" '
                    f'width="{SHARD}" height="{outputs}" preserveAspectRatio="none" '
                    f'result="{prefix}-weights{shard_index}"/>',
                    f'<feComposite in="{prefix}-weights{shard_index}" '
                    f'in2="{prefix}-values{shard_index}" operator="arithmetic" '
                    f'k1="1" k2="0" k3="0" k4="0" '
                    f'result="{prefix}-same{shard_index}"/>',
                    f'<feComposite in="{prefix}-weights{shard_index}" '
                    f'in2="{prefix}-swapped{shard_index}" operator="arithmetic" '
                    f'k1="1" k2="0" k3="0" k4="0" '
                    f'result="{prefix}-cross{shard_index}"/>',
                    f'<feColorMatrix in="{prefix}-same{shard_index}" '
                    f'values="{positive_matrix}" result="{prefix}-pos{shard_index}"/>',
                    f'<feColorMatrix in="{prefix}-cross{shard_index}" '
                    f'values="{negative_matrix}" result="{prefix}-neg{shard_index}"/>',
                    f'<feComposite in="{prefix}-pos{shard_index}" '
                    f'in2="{prefix}-neg{shard_index}" operator="arithmetic" '
                    f'k1="0" k2="1" k3="1" k4="0" '
                    f'result="{prefix}-split{shard_index}"/>',
                    f'<feConvolveMatrix in="{prefix}-split{shard_index}" '
                    f'order="{SHARD} 1" kernelMatrix="{kernel}" '
                    f'divisor="{magnitude}" targetX="{CX}" targetY="0" '
                    f'edgeMode="none" kernelUnitLength="1 1" preserveAlpha="true" '
                    f'x="{CX}" y="0" width="1" height="{outputs}" '
                    f'result="{prefix}-sum{shard_index}"/>',
                    f'<feColorMatrix in="{prefix}-sum{shard_index}" '
                    f'values="{signed_matrix}" result="{prefix}-encoded{shard_index}"/>',
                )
            )
            encoded_parts.append(f"{prefix}-encoded{shard_index}")
        total = encoded_parts[0]
        for part_index, part in enumerate(encoded_parts[1:], 1):
            result = f"{prefix}-total{part_index}"
            primitives.append(
                f'<feComposite in="{total}" in2="{part}" operator="arithmetic" '
                f'k1="0" k2="1" k3="1" k4="-{center_css}" result="{result}"/>'
            )
            total = result
        max_unit = float(np.max(units / output_range))
        save_gray(
            OUT / f"{prefix}-scales.png",
            (units / output_range / max_unit).reshape(outputs, 1),
        )
        primitives.extend(
            (
                f'<feComponentTransfer in="{total}" result="{prefix}-signed">'
                f'<feFuncR type="table" tableValues="{positive_table}"/>'
                f'<feFuncG type="table" tableValues="{negative_table}"/>'
                '<feFuncB type="table" tableValues="0 0"/>'
                '<feFuncA type="identity"/></feComponentTransfer>',
                f'<feImage href="{prefix}-scales.png" x="{CX}" y="0" '
                f'width="1" height="{outputs}" preserveAspectRatio="none" '
                f'result="{prefix}-scales"/>',
                f'<feComposite in="{prefix}-signed" in2="{prefix}-scales" '
                f'operator="arithmetic" k1="{divisor * max_unit}" '
                f'k2="0" k3="0" k4="0" result="{prefix}-scaled"/>',
                f'<feColorMatrix in="{prefix}-scaled" values="{signed_to_common}" '
                f'result="{prefix}-common"/>',
            )
        )
        padded = f"{prefix}-padded"
        primitives.append(
            f'<feOffset in="{prefix}-common" dx="{column - CX}" x="{column}" y="0" '
            f'width="1" height="{outputs}" result="{padded}"/>'
        )
        return padded

    columns = []
    column_count = math.ceil(VOCABULARY / ROWS_PER_COLUMN)
    for column, start in enumerate(range(0, VOCABULARY, ROWS_PER_COLUMN)):
        stop = min(start + ROWS_PER_COLUMN, VOCABULARY)
        print(
            f"building output-head column {column + 1}/{column_count} "
            f"({start}:{stop})",
            flush=True,
        )
        columns.append(matrix_column(start, stop, column))
    primitives.append(
        "<feMerge>"
        + "".join(f'<feMergeNode in="{column}"/>' for column in columns)
        + "</feMerge>"
    )

    html = (
        '<!doctype html><meta charset="utf-8"><title>Full GPT-2 SVG output head</title>'
        '<style>html,body{margin:0;background:black}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{column_count}" height="{ROWS_PER_COLUMN}" '
        f'viewBox="0 0 {column_count} {ROWS_PER_COLUMN}" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        f'<filter id="head" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" '
        f'x="0" y="0" width="{WIDTH}" height="{WORK_HEIGHT}" '
        f'color-interpolation-filters="sRGB">{"".join(primitives)}</filter>'
        f'</defs><rect width="{WIDTH}" height="{ROWS_PER_COLUMN}" fill="white" '
        'filter="url(#head)"/></svg>'
    )
    (OUT / "index.html").write_text(html)

    transformer_html = (SOURCE / "bucket-chain-12blocks-final-ln.html").read_text()
    transformer_defs_match = re.search(r"<defs>(.*)</defs>", transformer_html)
    transformer_filter_match = re.search(
        r'style="filter:([^"]+)"', transformer_html
    )
    if transformer_defs_match is None or transformer_filter_match is None:
        raise ValueError("could not read the generated 12-block filter chain")
    transformer_defs = re.sub(
        r'href="(?!#)([^"]+)"',
        r'href="../svg-filter-full-block/\1"',
        transformer_defs_match.group(1),
    )
    connected_primitives = primitives.copy()
    connected_primitives[0] = connected_primitives[0].replace(
        '<feImage href="input.png" x="0" y="255" width="768" height="1" '
        'preserveAspectRatio="none" result="input-common"/>',
        '<feOffset in="SourceGraphic" dy="255" x="0" y="255" '
        'width="768" height="1" result="input-common"/>',
    )
    connected_head_filter = (
        f'<filter id="head-connected" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{WIDTH}" '
        f'height="{WORK_HEIGHT}" color-interpolation-filters="sRGB">'
        f'{"".join(connected_primitives)}</filter>'
    )
    connected_filter_value = (
        transformer_filter_match.group(1).strip() + " url(#head-connected)"
    )
    connected_html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>GPT-2 12 blocks and full output head in SVG filters</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{column_count}" height="{ROWS_PER_COLUMN}" '
        f'viewBox="0 0 {column_count} {ROWS_PER_COLUMN}" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        f'{transformer_defs}{connected_head_filter}</defs>'
        f'<rect width="3072" height="3072" fill="white" '
        f'style="filter:{connected_filter_value}"/></svg>'
    )
    (OUT / "connected.html").write_text(connected_html)
    payload = {
        "vocabulary": VOCABULARY,
        "width": WIDTH,
        "rows_per_column": ROWS_PER_COLUMN,
        "columns": column_count,
        "surface_center": CENTER,
        "output_range": output_range,
        "original_winner": int(np.argmax(logits)),
        "alternate_winner": int(np.argmax(alternate_logits)),
        "original_top5": np.argsort(logits)[-5:][::-1].astype(int).tolist(),
        "alternate_top5": np.argsort(alternate_logits)[-5:][::-1].astype(int).tolist(),
        "token_order": token_order.astype(int).tolist(),
    }
    (OUT / "reference.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                **payload,
                "html_bytes": len(html.encode()),
                "connected_html_bytes": len(connected_html.encode()),
                "asset_bytes": sum(path.stat().st_size for path in OUT.glob("*.png")),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
