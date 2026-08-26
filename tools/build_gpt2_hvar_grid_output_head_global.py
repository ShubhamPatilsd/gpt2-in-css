#!/usr/bin/env python3
"""Build a compact-DOM GPT-2 head with one global weight scale."""

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
OUTPUT_NAME = os.environ.get(
    "GPT2_HVAR_GLOBAL_HEAD_DIR", "gpt2-hvar-grid-output-head-global11"
)
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
INLINE_OUTPUT = (
    ROOT / "experiments" / f"{OUTPUT_NAME}-inline-tie"
)
SOURCE_REFERENCE = ROOT / "experiments" / "svg-filter-full-block" / "reference.json"
WEIGHT_BITS = 11
WEIGHT_MAX = 2 ** (WEIGHT_BITS - 1) - 1


def compact_html(groups: int, *, inline_ties: bool = False) -> str:
    group_markup: list[str] = []
    for group in range(groups):
        start = group * baseline.GROUP_SIZE
        stop = min(baseline.VOCABULARY, start + baseline.GROUP_SIZE)
        items = []
        for token in range(start, stop):
            # Raw UTF-8 code points are much smaller and cheaper to parse than
            # five hexadecimal HTML entities plus three inline declarations.
            characters = "".join(
                chr(codepoint_start + token)
                for codepoint_start in baseline.CODEPOINT_STARTS[
                    :baseline.SHARD_COUNT
                ]
            )
            tie = baseline.GROUP_SIZE - 1 - token % baseline.GROUP_SIZE
            style = f" style=--local-tie:{tie}" if inline_ties else ""
            items.append(f"<i{style}>{characters}</i>")
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
    controls = (
        '<input type="radio" name="query" id="q0" checked>'
        '<input type="radio" name="query" id="q1">'
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Compact global-int11 GPT-2 HVAR + Grid output head</title>
<link rel="stylesheet" href="index.css">
{controls}
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
    INLINE_OUTPUT.mkdir(parents=True, exist_ok=True)
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
        tensors.tensor("wte.weight")[:baseline.VOCABULARY],
        dtype=np.float64,
    )
    global_scale = float(np.max(np.abs(embeddings)) / WEIGHT_MAX)
    codes = np.rint(embeddings / global_scale).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * global_scale

    row_bases_by_shard: list[int] = []
    font_paths: list[Path] = []
    rebuild = os.environ.get("GPT2_HVAR_HEAD_REBUILD_FONTS", "0") == "1"
    for shard, start in enumerate(range(0, baseline.WIDTH, baseline.SHARD)):
        stop = min(start + baseline.SHARD, baseline.WIDTH)
        shard_codes = codes[:, start:stop]
        maximum_l1 = int(np.max(np.sum(
            np.abs(shard_codes.astype(np.int64)), axis=1
        )))
        base_advance = maximum_l1 + 32
        if base_advance + maximum_l1 > 65_535:
            raise RuntimeError(
                f"shard {shard} exceeds OpenType advance range: "
                f"{base_advance + maximum_l1}"
            )
        row_bases = np.full(
            baseline.VOCABULARY, base_advance, dtype=np.int32
        )
        destination = OUTPUT / f"score-d{shard}.ttf"
        if rebuild or not destination.with_suffix(".woff2").exists():
            build_direct_font_backend(
                shard_codes,
                destination,
                signed_axes=True,
                base_advance=row_bases,
                codepoint_start=baseline.CODEPOINT_STARTS[shard],
                axis_tags=[
                    global_axis_tag(dimension)
                    for dimension in range(start, stop)
                ],
            )
        row_bases_by_shard.append(base_advance)
        font_paths.append(destination.with_suffix(".woff2"))

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
    total_base = sum(row_bases_by_shard)
    factor = (
        input_range * global_scale * baseline.SCORE_SCALE
        * baseline.SCORE_STRIDE_PX
    )
    base_css = baseline.render_css(
        hidden_vectors, shared_scales, input_range, floors, groups
    )
    base_css = base_css.replace(".candidate", ".group-grid>i")
    # Keep these shared constants literal inside calc-size(). Chromium did not
    # reliably reevaluate the intrinsic-size expression when the same values
    # arrived through stylesheet custom properties on all 50,257 grid items.
    base_css = base_css.replace("var(--base)", str(total_base))
    base_css = base_css.replace("var(--factor)", baseline.css_number(factor))
    tie_rules = "".join(
        f".group-grid>i:nth-child({local + 1})"
        f"{{--local-tie:{baseline.GROUP_SIZE - 1 - local}}}"
        for local in range(baseline.GROUP_SIZE)
    ) + "\n"
    # The baseline reducer deliberately nests its later rules inside container
    # queries. Candidate rules must precede that nesting because candidates are
    # not descendants of the reducer's size-query containers.
    reducer_start = base_css.index(".outer-reader{")
    css = base_css[:reducer_start] + tie_rules + base_css[reducer_start:]
    (OUTPUT / "index.css").write_text(css)
    (OUTPUT / "index.html").write_text(compact_html(groups))
    inline_css = base_css.replace(
        'url("score-d',
        f'url("../{OUTPUT_NAME}/score-d',
    )
    (INLINE_OUTPUT / "index.css").write_text(inline_css)
    (INLINE_OUTPUT / "index.html").write_text(
        compact_html(groups, inline_ties=True)
    )

    reference = {
        "model": "openai-community/gpt2",
        "backend": (
            f"{baseline.SHARD_COUNT}-shard-global-int11-hvar-"
            "compact-dom-grid-argmax"
        ),
        "weightBits": WEIGHT_BITS,
        "weightScale": global_scale,
        "vocabulary": baseline.VOCABULARY,
        "width": baseline.WIDTH,
        "shardDimensions": baseline.SHARD,
        "glyphsPerToken": baseline.SHARD_COUNT,
        "estimatedShapedGlyphs": baseline.VOCABULARY * baseline.SHARD_COUNT,
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
        "rowBaseMaximums": row_bases_by_shard,
        "fontBytes": sum(path.stat().st_size for path in font_paths),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    inline_reference = dict(reference)
    inline_reference.update({
        "backend": (
            f"{baseline.SHARD_COUNT}-shard-global-int11-hvar-compact-dom-"
            "inline-tie-grid-argmax"
        ),
        "htmlBytes": (INLINE_OUTPUT / "index.html").stat().st_size,
        "cssBytes": (INLINE_OUTPUT / "index.css").stat().st_size,
    })
    (INLINE_OUTPUT / "reference.json").write_text(
        json.dumps(inline_reference, indent=2) + "\n"
    )
    print(json.dumps({
        key: value for key, value in reference.items()
        if key != "validation"
    }, indent=2))
    print(json.dumps({
        "inlineTieHtmlBytes": inline_reference["htmlBytes"],
        "inlineTieCssBytes": inline_reference["cssBytes"],
        "inlineTieRuntimeBytes": (
            inline_reference["htmlBytes"] + inline_reference["cssBytes"]
            + inline_reference["fontBytes"]
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
