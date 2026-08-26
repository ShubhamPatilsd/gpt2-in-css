#!/usr/bin/env python3
"""Build a compact global-int16 GPT-2 head from high/residual font planes."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as baseline
from analyze_full_gpt2 import MODEL_PATH, SafeTensors, final_hidden_one_token
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
SOURCE_REFERENCE = ROOT / "experiments" / "svg-filter-full-block" / "reference.json"
WEIGHT_MAX = 32_767
SHARD = 128
DISPLAY_SCALE = 0.1
CODEPOINT_STARTS = tuple(
    [plane * 0x10000 for plane in range(2, 12)] + [0xF0000, 0x100000]
)


def render_html(
    row_bases: np.ndarray,
    global_scale: float,
    input_range: float,
    groups: int,
) -> str:
    factor = (
        input_range * global_scale * baseline.SCORE_SCALE
        * baseline.SCORE_STRIDE_PX / DISPLAY_SCALE
    )
    group_markup: list[str] = []
    for group in range(groups):
        start = group * baseline.GROUP_SIZE
        stop = min(baseline.VOCABULARY, start + baseline.GROUP_SIZE)
        items = []
        for token in range(start, stop):
            characters = "".join(
                chr(codepoint_start + token)
                for codepoint_start in CODEPOINT_STARTS
            )
            tie = baseline.GROUP_SIZE - 1 - token % baseline.GROUP_SIZE
            items.append(
                f'<i class="candidate" style="--base:'
                f'{baseline.css_number(row_bases[token] * DISPLAY_SCALE)};'
                f'--factor:{baseline.css_number(factor)};--local-tie:{tie}">'
                f"{characters}</i>"
            )
        group_markup.append(
            f'<section class="group-wrapper" '
            f'style="anchor-name:--score-group-{group};'
            f'view-timeline:--ogt{group} inline">'
            f'<div class="group-grid group-{group}">{"".join(items)}</div>'
            "</section>"
        )
    carriers = "".join(
        f'<i class="carrier carrier-{group}"></i>' for group in range(groups)
    )
    match_carriers = "".join(
        f'<i class="match-carrier match-carrier-{group}"></i>'
        for group in range(groups)
    )
    proxies = "".join(
        f'<i class="group-proxy group-proxy-{group}"></i>'
        for group in range(groups)
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Global-int16 two-plane GPT-2 HVAR + Grid output head</title>
<link rel="stylesheet" href="index.css">
<input type="radio" name="query" id="q0" checked><input type="radio" name="query" id="q1">
<main id="model" class="model"><div class="group-scroller"><div class="group-track">
{"".join(group_markup)}</div></div>{proxies}</main>
<div class="outer-reader"><div class="selection">
{match_carriers}<i class="group-choice"></i>
<div class="group-choice-reader"><div class="group-selection">
{carriers}<i class="selected"></i>
<div class="selected-reader"><output id="result" class="result"></output></div>
</div></div></div></div>
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE_REFERENCE.read_text())
    tensors = SafeTensors(MODEL_PATH)
    hidden_vectors = np.stack((
        source["bucket_final_ln_expected"],
        source["bucket_final_ln_expected_alt"],
    )).astype(np.float64)
    validation_vectors = np.stack([
        final_hidden_one_token(token_id, tensors)
        for token_id in baseline.VALIDATION_TOKEN_IDS
    ]).astype(np.float64)
    input_range = float(np.max(np.abs(np.concatenate(
        (hidden_vectors, validation_vectors), axis=0
    ))) * 1.01)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[:baseline.VOCABULARY], dtype=np.float64
    )
    global_scale = float(np.max(np.abs(embeddings)) / WEIGHT_MAX)
    codes = np.rint(embeddings / global_scale).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * global_scale

    equivalent_bases: list[np.ndarray] = []
    font_paths: list[Path] = []
    face_rules: list[str] = []
    family_names: list[str] = []
    face_ranges: list[dict[str, int]] = []
    rebuild = os.environ.get("GPT2_HVAR_HEAD_REBUILD_FONTS", "0") == "1"
    for shard, start in enumerate(range(0, baseline.WIDTH, SHARD)):
        stop = min(start + SHARD, baseline.WIDTH)
        shard_codes = codes[:, start:stop].astype(np.int32)
        high = np.trunc(shard_codes / 256).astype(np.int16)
        residual = (shard_codes - high.astype(np.int32) * 256).astype(np.int16)
        if int(np.max(np.abs(high))) > 127:
            raise RuntimeError("high plane escaped signed int8 range")
        if int(np.max(np.abs(residual))) > 255:
            raise RuntimeError("residual plane escaped signed byte-magnitude range")
        reconstructed = high.astype(np.int32) * 256 + residual.astype(np.int32)
        if not np.array_equal(reconstructed, shard_codes):
            raise RuntimeError("two-plane split is not exact")

        plane_bases = []
        for plane, values in enumerate((high, residual)):
            l1 = np.sum(np.abs(values.astype(np.int64)), axis=1)
            bases = (l1 + 32).astype(np.int32)
            if int(np.max(bases + l1)) > 65_535:
                raise RuntimeError(
                    f"shard {shard} plane {plane} exceeds advance range"
                )
            face = 2 * shard + plane
            family = f"Score{'H' if plane == 0 else 'L'}{shard}"
            destination = OUTPUT / f"score-{'h' if plane == 0 else 'l'}{shard}.ttf"
            if rebuild or not destination.with_suffix(".woff2").exists():
                build_direct_font_backend(
                    values,
                    destination,
                    signed_axes=True,
                    base_advance=bases,
                    codepoint_start=CODEPOINT_STARTS[face],
                    axis_tags=[
                        global_axis_tag(dimension)
                        for dimension in range(start, stop)
                    ],
                )
            adjustment = ";size-adjust:25600%" if plane == 0 else ""
            face_rules.append(
                f'@font-face{{font-family:{family};src:url("{destination.with_suffix(".woff2").name}") '
                f'format("woff2"){adjustment}}}'
            )
            family_names.append(family)
            font_paths.append(destination.with_suffix(".woff2"))
            plane_bases.append(bases)
            face_ranges.append({
                "shard": shard,
                "plane": plane,
                "maximumL1": int(l1.max()),
                "maximumBase": int(bases.max()),
                "maximumAdvance": int(np.max(bases + l1)),
            })
        equivalent_bases.append(plane_bases[0] * 256 + plane_bases[1])
    row_bases = np.sum(np.stack(equivalent_bases), axis=0)

    logits = hidden_vectors @ embeddings.T
    quantized_logits = hidden_vectors @ quantized_embeddings.T
    validation_logits = validation_vectors @ embeddings.T
    validation_quantized_logits = validation_vectors @ quantized_embeddings.T
    dense_winners = logits.argmax(axis=1).astype(int)
    quantized_winners = quantized_logits.argmax(axis=1).astype(int)
    validation_dense_winners = validation_logits.argmax(axis=1).astype(int)
    validation_quantized_winners = validation_quantized_logits.argmax(axis=1).astype(int)
    floors = np.floor(np.min(quantized_logits, axis=1)).astype(int) - 1
    validation_floors = (
        np.floor(np.min(validation_quantized_logits, axis=1)).astype(int) - 1
    )
    buckets = np.rint(
        (quantized_logits - floors[:, None]) * baseline.SCORE_SCALE
    ).astype(int)
    validation_buckets = np.rint(
        (validation_quantized_logits - validation_floors[:, None])
        * baseline.SCORE_SCALE
    ).astype(int)
    if not np.array_equal(quantized_winners, buckets.argmax(axis=1)):
        raise RuntimeError("score buckets changed a source winner")
    if not np.array_equal(
        validation_quantized_winners, validation_buckets.argmax(axis=1)
    ):
        raise RuntimeError("score buckets changed a validation winner")

    groups = math.ceil(baseline.VOCABULARY / baseline.GROUP_SIZE)
    shared_scales = np.full(baseline.VOCABULARY, global_scale)
    css = baseline.render_css(
        hidden_vectors, shared_scales, input_range, floors, groups
    )
    _old_faces, css_body = css.split("\n", 1)
    old_families = ",".join(
        f"Score{shard}" for shard in range(baseline.SHARD_COUNT)
    )
    css = "".join(face_rules) + "\n" + css_body.replace(
        f"font-family:{old_families};",
        f"font-family:{','.join(family_names)};",
    )
    css = css.replace(
        f"font-size:{baseline.FONT_SIZE}px;",
        f"font-size:{baseline.css_number(baseline.FONT_SIZE * DISPLAY_SCALE)}px;",
    )
    (OUTPUT / "index.css").write_text(css)
    (OUTPUT / "index.html").write_text(
        render_html(row_bases, global_scale, input_range, groups)
    )

    reference = {
        "model": "openai-community/gpt2",
        "backend": "global-int16-high-residual-hvar-grid-argmax",
        "weightBits": 16,
        "weightScale": global_scale,
        "planes": 2,
        "shards": math.ceil(baseline.WIDTH / SHARD),
        "glyphsPerToken": len(CODEPOINT_STARTS),
        "displayScale": DISPLAY_SCALE,
        "vocabulary": baseline.VOCABULARY,
        "width": baseline.WIDTH,
        "groups": groups,
        "inputRange": input_range,
        "scoreFloors": floors.tolist(),
        "scoreScale": baseline.SCORE_SCALE,
        "scoreStridePx": baseline.SCORE_STRIDE_PX,
        "denseWinners": dense_winners.tolist(),
        "quantizedWinners": quantized_winners.tolist(),
        "winnerBuckets": buckets[
            np.arange(len(quantized_winners)), quantized_winners
        ].tolist(),
        "weightRmse": float(np.sqrt(np.mean(
            (quantized_embeddings - embeddings) ** 2
        ))),
        "logitRmse": np.sqrt(np.mean(
            (quantized_logits - logits) ** 2, axis=1
        )).tolist(),
        "validation": {
            "tokenIds": list(baseline.VALIDATION_TOKEN_IDS),
            "hiddenVectors": validation_vectors.tolist(),
            "scoreFloors": validation_floors.tolist(),
            "denseWinners": validation_dense_winners.tolist(),
            "quantizedWinners": validation_quantized_winners.tolist(),
            "winnerBuckets": validation_buckets[
                np.arange(len(validation_quantized_winners)),
                validation_quantized_winners,
            ].tolist(),
            "logitRmse": np.sqrt(np.mean(
                (validation_quantized_logits - validation_logits) ** 2,
                axis=1,
            )).tolist(),
        },
        "faceRanges": face_ranges,
        "fontBytes": sum(path.stat().st_size for path in font_paths),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items()
        if key not in {"validation", "faceRanges"}
    }, indent=2))


if __name__ == "__main__":
    main()
