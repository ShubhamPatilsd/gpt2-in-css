#!/usr/bin/env python3
"""Build the real GPT-2-small 768-wide output head as HVAR + CSS Grid."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

import build_output_head_benchmark as output_head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors, final_hidden_one_token
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_NAME = os.environ.get(
    "GPT2_HVAR_HEAD_DIR", "gpt2-hvar-grid-output-head"
)
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
SOURCE_REFERENCE = ROOT / "experiments" / "svg-filter-full-block" / "reference.json"
VOCABULARY = 50_257
WIDTH = 768
SHARD = int(os.environ.get("GPT2_HVAR_HEAD_SHARD", "160"))
if not 1 <= SHARD <= 256:
    raise ValueError("GPT2_HVAR_HEAD_SHARD must be between 1 and 256")
SHARD_COUNT = math.ceil(WIDTH / SHARD)
ALLOW_OUT_OF_RANGE_RESULT = (
    os.environ.get("GPT2_HVAR_HEAD_ALLOW_OUT_OF_RANGE_RESULT", "0") == "1"
)
GROUP_SIZE = 256
LAYOUT_UNITS_PER_PX = 64
# 1/1024-logit buckets make calc-size's intermediate intrinsic multiplication
# hit Chrome's 33,554,432px layout ceiling at width 768, even though the final
# base-subtracted score is small. The tightest validation margin is still over
# 100 buckets at 1/256, so this scale preserves the winner without overflow.
SCORE_SCALE = 256
SCORE_STRIDE_PX = GROUP_SIZE // LAYOUT_UNITS_PER_PX
WEIGHT_BITS = int(os.environ.get("GPT2_HVAR_HEAD_BITS", "10"))
if not 2 <= WEIGHT_BITS <= 16:
    raise ValueError("GPT2_HVAR_HEAD_BITS must be between 2 and 16")
WEIGHT_MAX = 2 ** (WEIGHT_BITS - 1) - 1
FONT_SIZE = 1_000
# Five 160-axis faces keep direct 10-bit rows inside OpenType's 16-bit advance
# range. These ranges avoid complex-script combining characters.
CODEPOINT_STARTS = (
    0x20000, 0x30000, 0x40000, 0xF0000, 0x100000,
    0x50000, 0x60000, 0x70000, 0x80000, 0x90000,
)
if SHARD_COUNT > len(CODEPOINT_STARTS):
    raise ValueError(
        f"{SHARD_COUNT} shards exceed the {len(CODEPOINT_STARTS)} safe codepoint ranges"
    )
GROUP_VIEWPORT = 262_144
# 11776 is a deliberately difficult state: global int11 chooses token 13 while
# dense GPT-2 and global int16 choose token 11. Keeping it in the browser suite
# proves that coarse-to-fine refinement actually repairs a coarse-head error.
VALIDATION_TOKEN_IDS = (0, 1, 11, 13, 257, 464, 612, 15496, 11776)


def css_number(value: float) -> str:
    return output_head.css_number(float(value))


def render_css(
    hidden_vectors: np.ndarray,
    row_scales: np.ndarray,
    input_range: float,
    floors: np.ndarray,
    groups: int,
) -> str:
    settings = ",".join(
        f'"{global_axis_tag(dimension)}" '
        f"calc(var(--h{dimension}) / {css_number(input_range)})"
        for dimension in range(WIDTH)
    )
    group_rules = "".join(
        f".group-{group}{{anchor-name:--group-{group}}}"
        for group in range(groups)
    )
    group_timeline_names = [f"--ogt{group}" for group in range(groups)]
    group_progress_names = [f"--ogp{group}" for group in range(groups)]
    group_timeline_rules = "".join(
        f'@property {progress}{{syntax:"<number>";inherits:false;initial-value:-1}}'
        f"@keyframes ogk{group}{{from{{{progress}:0}}to{{{progress}:1}}}}"
        for group, progress in enumerate(group_progress_names)
    )
    proxy_rules = "".join(
        f".group-proxy-{group}{{animation:ogk{group} 1s linear both;"
        f"animation-timeline:{group_timeline_names[group]};animation-range:cover;"
        f"width:calc({GROUP_VIEWPORT}px/var({group_progress_names[group]}) - "
        f"{GROUP_VIEWPORT}px)}}"
        for group in range(groups)
    )
    match_rules = "".join(
        f".match-carrier-{group}{{position-anchor:--score-group-{group};"
        f"anchor-name:--match-carrier-{group};"
        f"width:calc(clamp(0px,anchor-size(--score-group-{group} width) - "
        f"(var(--bucket) - .5)*{SCORE_STRIDE_PX}px,1px)*{groups - group})}}"
        for group in range(groups)
    )
    match_sizes = ",".join(
        f"anchor-size(--match-carrier-{group} width)" for group in range(groups)
    )
    carrier_rules = "".join(
        f".carrier-{group}{{--flag:clamp(0,1 - abs(var(--group) - {group}),1);"
        f"position-anchor:--group-{group};anchor-name:--carrier-{group};"
        f"width:calc(anchor-size(--group-{group} width) * var(--flag))}}"
        for group in range(groups)
    )
    carrier_sizes = ",".join(
        f"anchor-size(--carrier-{group} width)" for group in range(groups)
    )
    font_faces = "".join(
        f'@font-face{{font-family:Score{shard};src:url("score-d{shard}.woff2") '
        'format("woff2")}'
        for shard in range(SHARD_COUNT)
    )
    font_families = ",".join(
        f"Score{shard}" for shard in range(SHARD_COUNT)
    )
    score_offsets = "\n".join(
        f"body:has(#q{query}:checked) .model{{--score-offset:"
        f"{-int(floor) * SCORE_SCALE * SCORE_STRIDE_PX}px}}"
        for query, floor in enumerate(floors)
    )
    return "\n".join((
        font_faces,
        '@property --bucket{syntax:"<number>";inherits:true;initial-value:0}',
        '@property --group{syntax:"<number>";inherits:true;initial-value:0}',
        '@property --local{syntax:"<number>";inherits:true;initial-value:0}',
        '@property --winner{syntax:"<number>";inherits:true;initial-value:0}',
        '@property --flag{syntax:"<number>";inherits:true;initial-value:0}',
        group_timeline_rules,
        output_head.query_rules(hidden_vectors) + "\n" + score_offsets,
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}"
        "body{anchor-scope:all}",
        ".model{position:fixed;inset:0 auto auto 0;display:grid;"
        "grid-template-columns:max-content;grid-template-rows:1px;"
        "width:max-content;height:1px;anchor-name:--outer-winner;"
        f"timeline-scope:{','.join(group_timeline_names)};"
        f"font-family:{font_families};"
        f"font-size:{FONT_SIZE}px;line-height:1;font-variation-settings:{settings};"
        "font-kerning:none}",
        ".group-scroller{position:fixed;left:0;top:-90000px;"
        f"width:{GROUP_VIEWPORT}px;height:1px;overflow-x:scroll;overflow-y:hidden}}",
        f".group-track{{position:relative;width:{GROUP_VIEWPORT * 2}px;height:1px}}",
        ".group-wrapper{position:absolute;left:0;top:0;display:block;"
        f"width:calc-size(max-content,round(down,size,{SCORE_STRIDE_PX}px))}}",
        ".group-proxy{position:relative;grid-area:1/1;display:block;height:1px}",
        proxy_rules,
        ".group-grid{display:grid;grid-template-columns:max-content;"
        "grid-template-rows:1px;width:max-content;height:1px}",
        ".candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal;"
        f"width:calc-size(max-content,calc(round(nearest,"
        f"(size - var(--base)*1px) * var(--factor) + "
        "var(--score-offset),"
        f"{SCORE_STRIDE_PX}px) + var(--local-tie)/{LAYOUT_UNITS_PER_PX}*1px))}}",
        group_rules,
        ".outer-reader{position:fixed;position-anchor:--outer-winner;"
        "inset:2px auto auto 0;width:anchor-size(--outer-winner width);height:1px;"
        "container:outer-result/inline-size}",
        "@container outer-result (width >= 0px){.selection{"
        f"--bucket:round(nearest,100cqi/{SCORE_STRIDE_PX}px,1)}}",
        ".match-carrier,.group-choice,.group-choice-reader,.carrier,.selected,.selected-reader{"
        "position:fixed;height:1px}",
        match_rules,
        ".group-choice{position-anchor:--match-carrier-0;"
        "anchor-name:--selected-group-index;"
        f"width:max({match_sizes})}}",
        ".group-choice-reader{position-anchor:--selected-group-index;"
        "width:anchor-size(--selected-group-index width);"
        "container:group-choice-result/inline-size}",
        "@container group-choice-result (width >= 0px){.group-selection{"
        f"--group:calc({groups} - round(nearest,100cqi/1px,1))}}",
        carrier_rules,
        ".selected{position-anchor:--carrier-0;anchor-name:--selected-group;"
        f"width:max({carrier_sizes})}}",
        ".selected-reader{position-anchor:--selected-group;"
        "width:anchor-size(--selected-group width);container:selected-result/inline-size}",
        "@container selected-result (width >= 0px){.result{"
        f"--local:calc({GROUP_SIZE - 1} - round(nearest,"
        f"mod(100cqi,{SCORE_STRIDE_PX}px)/1px*{LAYOUT_UNITS_PER_PX},1));"
        f"--winner:calc(var(--group)*{GROUP_SIZE} + var(--local));"
        "display:block;width:calc(var(--winner)*1px);height:1px}}",
    )) + "\n"


def render_html(
    row_scales: np.ndarray,
    row_bases: np.ndarray,
    input_range: float,
    groups: int,
) -> str:
    group_markup: list[str] = []
    for group in range(groups):
        start = group * GROUP_SIZE
        stop = min(VOCABULARY, start + GROUP_SIZE)
        items: list[str] = []
        for token in range(start, stop):
            factor = (
                input_range * row_scales[token] * SCORE_SCALE * SCORE_STRIDE_PX
            )
            characters = "".join(
                f"&#x{codepoint_start + token:X};"
                for codepoint_start in CODEPOINT_STARTS[:SHARD_COUNT]
            )
            items.append(
                f'<i class="candidate" style="--base:{int(row_bases[token])};'
                f'--factor:{css_number(factor)};'
                f'--local-tie:{GROUP_SIZE - 1 - token % GROUP_SIZE}">'
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
    controls = "".join(
        f'<input type="radio" name="query" id="q{query}"'
        f'{" checked" if query == 0 else ""}>'
        for query in range(2)
    )
    proxies = "".join(
        f'<i class="group-proxy group-proxy-{group}"></i>'
        for group in range(groups)
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2-small HVAR + Grid output head</title>
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
    source = json.loads(SOURCE_REFERENCE.read_text())
    hidden_vectors = np.stack((
        source["bucket_final_ln_expected"],
        source["bucket_final_ln_expected_alt"],
    )).astype(np.float64)
    tensors = SafeTensors(MODEL_PATH)
    validation_vectors = np.stack([
        final_hidden_one_token(token_id, tensors)
        for token_id in VALIDATION_TOKEN_IDS
    ]).astype(np.float64)
    observed_input_range = float(np.max(np.abs(np.concatenate(
        (hidden_vectors, validation_vectors), axis=0
    ))) * 1.01)
    requested_input_range = float(os.environ.get("GPT2_HVAR_HEAD_INPUT_RANGE", "0"))
    input_range = max(observed_input_range, requested_input_range)
    embeddings = np.asarray(
        tensors.tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    row_scales = np.max(np.abs(embeddings), axis=1) / WEIGHT_MAX
    row_scales[row_scales == 0] = 1
    codes = np.rint(embeddings / row_scales[:, None]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * row_scales[:, None]

    row_bases_by_shard: list[np.ndarray] = []
    font_paths: list[Path] = []
    rebuild = os.environ.get("GPT2_HVAR_HEAD_REBUILD_FONTS", "0") == "1"
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        stop = min(start + SHARD, WIDTH)
        shard_codes = codes[:, start:stop]
        row_bases = (
            np.sum(np.abs(shard_codes.astype(np.int64)), axis=1) + 32
        ).astype(np.int32)
        destination = OUTPUT / f"score-d{shard}.ttf"
        if rebuild or not destination.with_suffix(".woff2").exists():
            build_direct_font_backend(
                shard_codes,
                destination,
                signed_axes=True,
                base_advance=row_bases,
                codepoint_start=CODEPOINT_STARTS[shard],
                axis_tags=[global_axis_tag(dimension) for dimension in range(start, stop)],
                allow_out_of_range_result=ALLOW_OUT_OF_RANGE_RESULT,
            )
        row_bases_by_shard.append(row_bases)
        font_paths.append(destination.with_suffix(".woff2"))

    row_bases = np.sum(np.stack(row_bases_by_shard), axis=0)
    logits = hidden_vectors @ embeddings.T
    quantized_logits = hidden_vectors @ quantized_embeddings.T
    validation_logits = validation_vectors @ embeddings.T
    validation_quantized_logits = validation_vectors @ quantized_embeddings.T
    dense_winners = logits.argmax(axis=1).astype(int)
    quantized_winners = quantized_logits.argmax(axis=1).astype(int)
    floors = np.floor(np.min(quantized_logits, axis=1)).astype(int) - 1
    validation_floors = (
        np.floor(np.min(validation_quantized_logits, axis=1)).astype(int) - 1
    )
    buckets = np.rint(
        np.clip(
            (quantized_logits - floors[:, None]) * SCORE_SCALE,
            0,
            65_535,
        )
    ).astype(int)
    validation_buckets = np.rint(
        np.clip(
            (validation_quantized_logits - validation_floors[:, None])
            * SCORE_SCALE,
            0,
            65_535,
        )
    ).astype(int)
    bucket_winners = buckets.argmax(axis=1)
    if not np.array_equal(quantized_winners, bucket_winners):
        raise RuntimeError("score bucket quantization changed a winner")
    if int(buckets.max()) >= 65_535:
        raise RuntimeError("score quantizer clipped at its upper bound")
    validation_quantized_winners = validation_quantized_logits.argmax(axis=1)
    if not np.array_equal(
        validation_quantized_winners, validation_buckets.argmax(axis=1)
    ):
        raise RuntimeError("validation score buckets changed a winner")
    if int(validation_buckets.max()) >= 65_535:
        raise RuntimeError("validation score quantizer clipped")

    groups = math.ceil(VOCABULARY / GROUP_SIZE)
    (OUTPUT / "index.css").write_text(
        render_css(hidden_vectors, row_scales, input_range, floors, groups)
    )
    (OUTPUT / "index.html").write_text(
        render_html(row_scales, row_bases, input_range, groups)
    )
    reference = {
        "model": "openai-community/gpt2",
        "backend": (
            f"{SHARD_COUNT}-shard-direct-int{WEIGHT_BITS}-hvar-plus-"
            "hierarchical-grid-argmax"
        ),
        "weightBits": WEIGHT_BITS,
        "vocabulary": VOCABULARY,
        "width": WIDTH,
        "shardDimensions": SHARD,
        "allowOutOfRangeShapedResult": ALLOW_OUT_OF_RANGE_RESULT,
        "glyphsPerToken": SHARD_COUNT,
        "estimatedShapedGlyphs": VOCABULARY * SHARD_COUNT,
        "groups": groups,
        "inputRange": input_range,
        "observedFixtureInputRange": observed_input_range,
        "scoreFloors": floors.tolist(),
        "scoreScale": SCORE_SCALE,
        "scoreStridePx": SCORE_STRIDE_PX,
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
            "tokenIds": list(VALIDATION_TOKEN_IDS),
            "hiddenVectors": validation_vectors.tolist(),
            "scoreFloors": validation_floors.tolist(),
            "denseWinners": validation_logits.argmax(axis=1).astype(int).tolist(),
            "quantizedWinners": validation_quantized_winners.astype(int).tolist(),
            "winnerBuckets": validation_buckets[
                np.arange(len(validation_quantized_winners)),
                validation_quantized_winners,
            ].tolist(),
            "logitRmse": np.sqrt(np.mean(
                (validation_quantized_logits - validation_logits) ** 2,
                axis=1,
            )).tolist(),
        },
        "rowBaseMaximums": [
            int(np.max(values)) for values in row_bases_by_shard
        ],
        "fontBytes": sum(path.stat().st_size for path in font_paths),
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
