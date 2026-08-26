#!/usr/bin/env python3
"""Build all 12 real GPT-2 block-0 QK heads using GSUB-selected HVAR sums."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT
from build_feature_selected_qk import (
    CODEPOINT_BASE,
    CONTEXT,
    HEAD_WIDTH,
    LEVELS,
    QUERY_BITS,
    SHARD,
    TARGET_DELTA,
    axis_tag,
    build_shard_font,
    feature_tag,
    quantize,
)
from build_gpt2_block_css import FONT_SIZE, QUANT_BITS, WIDTH, layer_norm
from build_geometry_streaming_attention import TOKENS
from build_signed_hvar_chain import quantize_float_rows
from build_pretrained_gpt2 import css_number


ROOT = Path(__file__).resolve().parents[1]
BASE_OUT = ROOT / "experiments" / "feature-selected-qk-all-heads"
HEADS = WIDTH // HEAD_WIDTH
FEATURE_CHUNK = 5


def range_tag(value: float) -> str:
    return f"{value:.4g}".replace(".", "p")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range-scale", type=float, default=1.0)
    args = parser.parse_args()
    if not 0 < args.range_scale <= 1.5:
        parser.error("range scale must be in (0, 1.5]")
    out = (
        BASE_OUT if args.range_scale == 1.0
        else BASE_OUT.with_name(f"{BASE_OUT.name}-range-{range_tag(args.range_scale)}")
    )
    out.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    positions = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    states = np.stack([
        embeddings[token] + positions[position]
        for position, token in enumerate(TOKENS[:CONTEXT])
    ])
    normalized = np.stack([layer_norm(row, gamma, beta) for row in states])
    qkv_weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    quantized = quantize_float_rows(qkv_weight, bits=QUANT_BITS)
    qkv = normalized @ quantized.reconstructed.T + qkv_bias
    precision = json.loads(PRECISION_REPORT.read_text())
    all_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    input_range = float(precision["inputAbsMaxCalibration"] * 1.05)

    face_rules: list[str] = []
    head_rules: list[str] = []
    score_elements: list[str] = []
    heads_reference: list[dict[str, object]] = []
    total_font_bytes = 0
    for head in range(HEADS):
        query_slice = slice(head * HEAD_WIDTH, (head + 1) * HEAD_WIDTH)
        key_rows = np.arange(WIDTH + head * HEAD_WIDTH, WIDTH + (head + 1) * HEAD_WIDTH)
        query_ranges = all_ranges[query_slice] * args.range_scale
        _, query8 = quantize(qkv[-1, query_slice], query_ranges, 8)
        choices, query5 = quantize(query8, query_ranges, QUERY_BITS)
        key_codes = quantized.codes[key_rows]
        key_scales = quantized.scales[key_rows]
        key_bias = qkv_bias[key_rows]

        maximum_unscaled_delta = 0.0
        for coordinate in range(HEAD_WIDTH):
            for start in range(0, WIDTH, SHARD):
                stop = min(start + SHARD, WIDTH)
                bias_margin = (
                    abs(query_ranges[coordinate] * key_bias[coordinate])
                    if start == 0 else 0.0
                )
                maximum_unscaled_delta = max(
                    maximum_unscaled_delta,
                    float(
                        query_ranges[coordinate]
                        * key_scales[coordinate]
                        * input_range
                        * np.sum(np.abs(key_codes[coordinate, start:stop]))
                        + bias_margin
                    ),
                )
        dot_scale = max(1, math.floor(TARGET_DELTA / maximum_unscaled_delta))
        base = math.ceil(maximum_unscaled_delta * dot_scale) + 32

        font_paths: list[Path] = []
        for shard, start in enumerate(range(0, WIDTH, SHARD)):
            stop = min(start + SHARD, WIDTH)
            path = out / f"feature-qk-h{head}-s{shard}.ttf"
            build_shard_font(
                head=head,
                shard=shard,
                codes=key_codes[:, start:stop],
                row_scales=key_scales,
                row_bias=key_bias,
                query_ranges=query_ranges,
                input_range=input_range,
                dot_scale=dot_scale,
                base=base,
                destination=path,
            )
            font_path = path.with_suffix(".woff2")
            font_paths.append(font_path)
            total_font_bytes += font_path.stat().st_size
            face_rules.append(
                f'@font-face{{font-family:FQKH{head}S{shard};src:url("{font_path.name}?v='
                f'{hashlib.sha256(font_path.read_bytes()).hexdigest()[:12]}") format("woff2");'
                f'unicode-range:U+{CODEPOINT_BASE + shard * HEAD_WIDTH:X}-'
                f'{CODEPOINT_BASE + (shard + 1) * HEAD_WIDTH - 1:X}}}'
            )

        q_settings = ";".join(
            f"--q-{coordinate:03d}:{css_number(query8[coordinate])}"
            for coordinate in range(HEAD_WIDTH)
        )
        head_rules.append(f".head-{head}{{{q_settings}}}")
        families = ",".join(f"FQKH{head}S{shard}" for shard in range(len(font_paths)))
        head_rules.append(f".head-{head} .score{{font-family:{families}}}")
        for chunk, start in enumerate(range(0, HEAD_WIDTH, FEATURE_CHUNK)):
            settings = ",".join(
                f'"{feature_tag(coordinate)}" calc(1 + round(nearest,'
                f'clamp(0,(var(--q-{coordinate:03d}) + {css_number(query_ranges[coordinate])})'
                f' * {LEVELS - 1} / {css_number(2 * query_ranges[coordinate])},{LEVELS - 1}),1))'
                for coordinate in range(start, min(start + FEATURE_CHUNK, HEAD_WIDTH))
            )
            head_rules.append(
                f".head-{head} .chunk-{chunk}{{font-feature-settings:{settings}}}"
            )

        chunks = "".join(
            f'<b class="chunk-{chunk}">'
            + "".join(
                f"&#x{CODEPOINT_BASE + shard * HEAD_WIDTH + coordinate:X};"
                for shard in range(len(font_paths))
                for coordinate in range(start, min(start + FEATURE_CHUNK, HEAD_WIDTH))
            )
            + "</b>"
            for chunk, start in enumerate(range(0, HEAD_WIDTH, FEATURE_CHUNK))
        )
        for source in range(CONTEXT):
            variations = ",".join(
                f'"{axis_tag(shard, local)}" '
                f'{css_number(normalized[source, shard * SHARD + local] / input_range)}'
                for shard in range(len(font_paths))
                for local in range(SHARD)
            )
            score_elements.append(
                f'<i class="score score-{source}" style=\'font-variation-settings:{variations}\'>'
                f"{chunks}</i>"
            )

        keys = qkv[:, WIDTH + head * HEAD_WIDTH:WIDTH + (head + 1) * HEAD_WIDTH]
        expected_scores = keys @ query5 / math.sqrt(HEAD_WIDTH)
        baseline_scores = keys @ query8 / math.sqrt(HEAD_WIDTH)
        heads_reference.append({
            "head": head,
            "queryRanges": query_ranges.tolist(),
            "query8": query8.tolist(),
            "queryChoices": choices.tolist(),
            "biasCorrection": float(query5 @ key_bias),
            "biasFoldedIntoGlyphAdvance": True,
            "expectedScores": expected_scores.tolist(),
            "baselineScores": baseline_scores.tolist(),
            "queryBinningScoreRmse": float(
                np.sqrt(np.mean((expected_scores - baseline_scores) ** 2))
            ),
            "dotScale": dot_scale,
            "base": base,
            "fontBytes": [path.stat().st_size for path in font_paths],
        })

    head_divs = "".join(
        f'<div class="head head-{head}">'
        + "".join(score_elements[head * CONTEXT:(head + 1) * CONTEXT])
        + "</div>"
        for head in range(HEADS)
    )
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>Feature-selected real GPT-2 QK all heads</title>
<style>
{"".join(face_rules)}
{"".join(head_rules)}
.score{{position:fixed;display:inline-flex;width:max-content;height:1px;overflow:hidden;
white-space:pre;font:normal {FONT_SIZE}px sans-serif;font-kerning:none;font-feature-settings:normal}}
.score b{{font:inherit;font-feature-settings:inherit}}
</style>
{head_divs}
'''
    html_path = out / "index.html"
    html_path.write_text(html)
    reference = {
        "context": CONTEXT,
        "heads": HEADS,
        "headWidth": HEAD_WIDTH,
        "queryBits": QUERY_BITS,
        "queryRangeScale": args.range_scale,
        "featureChunkSize": FEATURE_CHUNK,
        "baseGlyphs": HEAD_WIDTH * (WIDTH // SHARD),
        "fontSize": FONT_SIZE,
        "totalFontBytes": total_font_bytes,
        "htmlBytes": html_path.stat().st_size,
        "runtimeJavaScript": False,
        "headsReference": heads_reference,
    }
    (out / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "heads": HEADS,
        "queryRangeScale": args.range_scale,
        "fonts": HEADS * (WIDTH // SHARD),
        "totalFontBytes": total_font_bytes,
        "htmlBytes": html_path.stat().st_size,
        "maximumQueryBinningScoreRmse": max(
            head["queryBinningScoreRmse"] for head in heads_reference
        ),
    })


if __name__ == "__main__":
    main()
