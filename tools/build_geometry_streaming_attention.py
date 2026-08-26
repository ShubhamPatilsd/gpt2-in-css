#!/usr/bin/env python3
"""Build attention with K, V, and the running numerator kept as geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import math

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT, TOKENS
from build_gpt2_block_css import (
    OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    font_faces,
    layer_norm,
    pack_font_settings,
    packed_axis_tag,
)
from build_multitoken_attention_css import (
    FONT_SIZE,
    HEADS,
    HEAD_WIDTH,
    OUTPUTS_PER_CONSUMER,
    QKV_WIDTH,
    consumer_tree,
    registrations,
    shared_metrics,
    softmax,
    timeline_rules,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows
from build_streaming_attention_context import selected_container_stage


CONTEXT_PRECISION_REPORT = OUT / "attention-context-precision.json"
FEATURE_QK_BASE_DIR = OUT.parent / "feature-selected-qk-all-heads"
PROJECTED_KV_QK_BASE_DIR = OUT.parent / "projected-kv-qk"
BILINEAR_PROJECTED_KV_QK_DIR = OUT.parent / "bilinear-projected-kv-qk"
BILINEAR_SUM_PROJECTED_KV_QK_DIR = OUT.parent / "bilinear-sum-projected-kv-qk"
FEATURE_QK_CODEPOINT_BASE = 0xF0000
FEATURE_QK_SHARD = 256
FEATURE_QK_CHUNK = 5
FEATURE_QK_BITS = 5
FEATURE_QK_LEVELS = 1 << FEATURE_QK_BITS
FEATURE_QK_FONT_SIZE = 16
PROJECTED_KV_QK_CODEPOINT_BASE = 0xF4000
BILINEAR_PROJECTED_KV_QK_CODEPOINT_BASE = 0xF5800


def range_tag(value: float) -> str:
    return f"{value:.4g}".replace(".", "p")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=int, choices=(1, 2, 4, 8, 16, 32), required=True)
    parser.add_argument("--with-projection", action="store_true")
    parser.add_argument(
        "--projection-transport",
        choices=("timeline", "packet6", "packet8", "packet12"),
        default="timeline",
    )
    parser.add_argument("--context-bits", type=int, choices=(8, 12), default=12)
    parser.add_argument(
        "--reduction", choices=("online", "flat", "inline"), default="online",
        help="Carry a recurrent numerator or reduce all weighted values once.",
    )
    parser.add_argument(
        "--score-backend",
        choices=("font", "css", "css-kv", "feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv"),
        default="font",
        help="Read K glyphs, use CSS math, GSUB/HVAR, or bilinear HVAR QK runs.",
    )
    parser.add_argument(
        "--feature-query-range-scale", type=float, default=1.0,
        help="Scale the calibrated query ranges used by the 5-bit feature backend.",
    )
    parser.add_argument(
        "--feature-query-chunk",
        type=int,
        choices=(5, 8, 16, 32, 64),
        default=FEATURE_QK_CHUNK,
        help="Query coordinates assigned to each feature-selected score text run.",
    )
    parser.add_argument(
        "--metric-markup", choices=("elements", "pseudo"), default="elements",
        help="Use separate K/V elements or two pseudo-elements on one node.",
    )
    parser.add_argument(
        "--value-backend", choices=("per-source", "mixed-input", "cached-v"), default="per-source",
        help="Project V per token, or mix normalized inputs per head before one V projection.",
    )
    parser.add_argument(
        "--cache-state-transport", choices=("embedded", "nested-vars"), default="embedded",
        help="Embed fixed source values or inherit uniquely named cached vectors through wrappers.",
    )
    parser.add_argument(
        "--live-current-kv", action="store_true",
        help="Project the current token's K and V in the live QKV stage instead of fixture constants.",
    )
    parser.add_argument(
        "--source-topology", choices=("nested", "siblings"), default="nested",
        help="Nest source stages or collect their score timelines as siblings.",
    )
    parser.add_argument(
        "--isolate-query-inheritance", action="store_true",
        help="Stop Q custom properties from inheriting into cached K/V metric subtrees.",
    )
    parser.add_argument(
        "--split-query-cache", action="store_true",
        help="Place cached K/V geometry outside the Q-inheriting score subtree.",
    )
    parser.add_argument(
        "--score-track-group-size", type=int, default=0,
        help="Group this many source K/V+score sets into each shared score track.",
    )
    args = parser.parse_args()
    if args.source_topology == "siblings" and args.reduction != "flat":
        parser.error("sibling source topology currently requires --reduction flat")
    if args.score_backend in ("css-kv", "feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv") and (
        args.source_topology != "siblings" or args.reduction != "flat"
    ):
        parser.error("feature scores currently require --source-topology siblings --reduction flat")
    if not 0 < args.feature_query_range_scale <= 1.5:
        parser.error("feature query range scale must be in (0, 1.5]")
    if args.score_backend not in ("feature", "feature-kv") and args.feature_query_range_scale != 1.0:
        parser.error("feature query range scaling requires --score-backend feature")
    if args.value_backend == "mixed-input" and (
        args.score_backend != "feature"
        or args.source_topology != "siblings"
        or args.reduction != "flat"
        or args.metric_markup != "elements"
    ):
        parser.error("mixed-input values currently require feature scores with flat sibling reduction")
    if args.value_backend == "cached-v" and args.score_backend not in ("css-kv", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
        parser.error("cached V values currently require a projected-KV score backend")
    if args.score_backend in ("css-kv", "feature-kv", "bilinear-kv", "bilinear-sum-kv") and args.value_backend != "cached-v":
        parser.error("projected-KV score backends currently require cached V values")
    if args.live_current_kv and args.score_backend not in ("css-kv", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
        parser.error("live current K/V currently requires a projected-KV score backend")
    if args.cache_state_transport == "nested-vars" and args.value_backend not in ("mixed-input", "cached-v"):
        parser.error("nested cached state variables require mixed-input or cached-V values")
    if args.split_query_cache and args.source_topology != "siblings":
        parser.error("split query cache currently requires sibling source topology")
    if args.split_query_cache and args.isolate_query_inheritance:
        parser.error("split query cache and query inheritance isolation are alternatives")
    if args.score_track_group_size < 0:
        parser.error("score track group size must be positive")
    if args.score_track_group_size and args.source_topology != "siblings":
        parser.error("grouped score tracks currently require sibling source topology")
    if args.score_track_group_size and (
        args.split_query_cache or args.isolate_query_inheritance
    ):
        parser.error("grouped score tracks are a separate graph variant")
    token_ids = TOKENS[: args.context]
    token_count = len(token_ids)
    cache_group_size = (
        token_count if args.split_query_cache else args.score_track_group_size
    )
    if cache_group_size > token_count:
        parser.error("score track group size cannot exceed context length")
    target = token_count - 1
    stem = f"attention-context-{token_count}-geometry-streaming"
    if args.reduction != "online":
        stem += f"-{args.reduction}"
    if args.score_backend == "css":
        stem += "-css-score"
    if args.score_backend == "css-kv":
        stem += "-css-kv-score"
    if args.score_backend == "feature":
        stem += "-feature-score"
        if args.feature_query_range_scale != 1.0:
            stem += f"-range-{range_tag(args.feature_query_range_scale)}"
    if args.score_backend == "feature-kv":
        stem += "-projected-kv-score"
        if args.feature_query_range_scale != 1.0:
            stem += f"-range-{range_tag(args.feature_query_range_scale)}"
    if args.score_backend == "bilinear-kv":
        stem += "-bilinear-kv-score"
    if args.score_backend == "bilinear-sum-kv":
        stem += "-bilinear-sum-kv-score"
    if args.score_backend in ("feature", "feature-kv") and args.feature_query_chunk != FEATURE_QK_CHUNK:
        stem += f"-qchunk{args.feature_query_chunk}"
    if args.value_backend == "mixed-input":
        stem += "-mixed-value"
    if args.value_backend == "cached-v":
        stem += "-cached-value"
    if args.live_current_kv:
        stem += "-live-current-kv"
    if args.cache_state_transport == "nested-vars":
        stem += "-nested-cache"
    if args.metric_markup == "pseudo":
        stem += "-pseudo-metrics"
    if args.source_topology == "siblings":
        stem += "-siblings"
    if args.isolate_query_inheritance:
        stem += "-q-isolated"
    if args.split_query_cache:
        stem += "-split-cache"
    if args.score_track_group_size:
        stem += f"-grouped-cache-{args.score_track_group_size}"
    if args.with_projection and args.projection_transport.startswith("packet"):
        stem += f"-projection-{args.projection_transport}"
    if args.with_projection and args.projection_transport == "timeline":
        stem += "-projected"
    html_path = OUT / f"{stem}.html"
    css_path = OUT / f"{stem}.css"
    shadow_path = OUT / f"{stem}-shadow.css"
    reference_path = OUT / f"{stem}-reference.json"

    precision = json.loads(PRECISION_REPORT.read_text())
    output_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    input_range = float(precision["inputAbsMaxCalibration"] * 1.05)
    feature_reference = None
    feature_heads_reference = None
    feature_qk_base_dir = (
        BILINEAR_SUM_PROJECTED_KV_QK_DIR
        if args.score_backend == "bilinear-sum-kv"
        else BILINEAR_PROJECTED_KV_QK_DIR
        if args.score_backend == "bilinear-kv"
        else PROJECTED_KV_QK_BASE_DIR
        if args.score_backend == "feature-kv"
        else FEATURE_QK_BASE_DIR
    )
    feature_qk_dir = (
        feature_qk_base_dir
        if args.feature_query_range_scale == 1.0
        else feature_qk_base_dir.with_name(
            f"{feature_qk_base_dir.name}-range-{range_tag(args.feature_query_range_scale)}"
        )
    )
    feature_qk_reference = feature_qk_dir / "reference.json"
    if args.score_backend in ("feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
        if not feature_qk_reference.exists():
            raise FileNotFoundError(
                f"build {feature_qk_dir.name} before feature-score attention"
            )
        feature_reference = json.loads(feature_qk_reference.read_text())
        if args.score_backend not in ("bilinear-kv", "bilinear-sum-kv") and not math.isclose(
            float(feature_reference.get("queryRangeScale", 1.0)),
            args.feature_query_range_scale,
        ):
            raise ValueError("feature font query range scale does not match requested scale")
        feature_heads_reference = feature_reference["headsReference"]
    tensors = SafeTensors(MODEL_PATH)
    token_embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position_embeddings = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    x = np.stack([
        token_embeddings[token] + position_embeddings[position]
        for position, token in enumerate(token_ids)
    ])
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    normalized = np.stack([layer_norm(row, gamma, beta) for row in x])

    weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    quantized = quantize_float_rows(weight, bits=QUANT_BITS)
    qkv_unpacked = normalized @ quantized.reconstructed.T + bias
    packed_codes = np.rint(
        np.clip((qkv_unpacked + output_ranges) * 255 / (2 * output_ranges), 0, 255)
    )
    qkv_packed = -output_ranges + packed_codes * (2 * output_ranges / 255)
    query = qkv_packed[:, :WIDTH].reshape(token_count, HEADS, HEAD_WIDTH)
    key = qkv_unpacked[:, WIDTH:2 * WIDTH].reshape(token_count, HEADS, HEAD_WIDTH)
    value = qkv_unpacked[:, 2 * WIDTH:].reshape(token_count, HEADS, HEAD_WIDTH)

    scores = np.empty((HEADS, token_count))
    probabilities = np.empty_like(scores)
    context = np.empty((HEADS, HEAD_WIDTH))
    numerator_states = []
    maxima = np.full(HEADS, -np.inf)
    denominators = np.zeros(HEADS)
    numerators = np.zeros((HEADS, HEAD_WIDTH))
    for source in range(token_count):
        source_scores = np.asarray([
            np.dot(query[target, head], key[source, head]) / math.sqrt(HEAD_WIDTH)
            for head in range(HEADS)
        ])
        scores[:, source] = source_scores
        if source == 0:
            maxima = source_scores.copy()
            denominators.fill(1)
            numerators = value[source].copy()
        else:
            new_maxima = np.maximum(maxima, source_scores)
            old_weights = np.exp(maxima - new_maxima)
            new_weights = np.exp(source_scores - new_maxima)
            denominators = denominators * old_weights + new_weights
            numerators = numerators * old_weights[:, None] + value[source] * new_weights[:, None]
            maxima = new_maxima
        numerator_states.append(numerators.copy())
    for head in range(HEADS):
        probabilities[head] = softmax(scores[head])
        context[head] = numerators[head] / denominators[head]
    context = context.reshape(WIDTH)
    baseline_scores = scores.copy()
    baseline_probabilities = probabilities.copy()
    baseline_context = context.copy()
    feature_queries = None
    if args.score_backend in ("feature", "feature-kv"):
        feature_queries = np.empty((HEADS, HEAD_WIDTH))
        feature_scores = np.empty_like(scores)
        feature_probabilities = np.empty_like(probabilities)
        feature_context = np.empty((HEADS, HEAD_WIDTH))
        for head in range(HEADS):
            start = head * HEAD_WIDTH
            ranges = (
                output_ranges[start:start + HEAD_WIDTH]
                * args.feature_query_range_scale
            )
            levels = FEATURE_QK_LEVELS - 1
            choices = np.rint(np.clip(
                (query[target, head] + ranges) * levels / (2 * ranges),
                0,
                levels,
            ))
            feature_query = -ranges + choices * (2 * ranges / levels)
            feature_queries[head] = feature_query
            feature_scores[head] = np.asarray([
                np.dot(feature_query, key[source, head]) / math.sqrt(HEAD_WIDTH)
                for source in range(token_count)
            ])
            feature_probabilities[head] = softmax(feature_scores[head])
            feature_context[head] = sum(
                feature_probabilities[head, source] * value[source, head]
                for source in range(token_count)
            )
        scores = feature_scores
        probabilities = feature_probabilities
        context = feature_context.reshape(WIDTH)
    elif args.score_backend in ("bilinear-kv", "bilinear-sum-kv"):
        assert feature_heads_reference is not None
        bilinear_scores = np.empty_like(scores)
        bilinear_probabilities = np.empty_like(probabilities)
        bilinear_context = np.empty((HEADS, HEAD_WIDTH))
        for head in range(HEADS):
            head_reference = feature_heads_reference[head]
            query_ranges = np.asarray(head_reference["queryRanges"], dtype=np.float64)
            key_ranges = np.asarray(head_reference["keyRanges"], dtype=np.float64)
            coefficients = np.asarray(head_reference["coefficients"], dtype=np.float64)
            dot_scale = float(head_reference["dotScale"])
            query_normalized = np.clip(query[target, head] / query_ranges, -1, 1)
            for source in range(token_count):
                key_normalized = np.clip(key[source, head] / key_ranges, -1, 1)
                bilinear_scores[head, source] = (
                    np.sum(coefficients * query_normalized * key_normalized)
                    / dot_scale / math.sqrt(HEAD_WIDTH)
                )
            bilinear_probabilities[head] = softmax(bilinear_scores[head])
            bilinear_context[head] = sum(
                bilinear_probabilities[head, source] * value[source, head]
                for source in range(token_count)
            )
        scores = bilinear_scores
        probabilities = bilinear_probabilities
        context = bilinear_context.reshape(WIDTH)
    elif args.score_backend == "css-kv":
        css_key = key.copy()
        css_value = value.copy()
        if args.live_current_kv:
            css_key[target] = qkv_packed[target, WIDTH:2 * WIDTH].reshape(HEADS, HEAD_WIDTH)
            css_value[target] = qkv_packed[target, 2 * WIDTH:].reshape(HEADS, HEAD_WIDTH)
        css_scores = np.empty_like(scores)
        css_probabilities = np.empty_like(probabilities)
        css_context = np.empty((HEADS, HEAD_WIDTH))
        for head in range(HEADS):
            css_scores[head] = np.asarray([
                np.dot(query[target, head], css_key[source, head]) / math.sqrt(HEAD_WIDTH)
                for source in range(token_count)
            ])
            css_probabilities[head] = softmax(css_scores[head])
            css_context[head] = sum(
                css_probabilities[head, source] * css_value[source, head]
                for source in range(token_count)
            )
        scores = css_scores
        probabilities = css_probabilities
        context = css_context.reshape(WIDTH)

    projection_fonts = None
    projection_bases = None
    projection_bias = None
    q_projection = None
    projected = None
    residual = None
    if args.with_projection:
        projection_weight = np.asarray(
            tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
        ).T
        projection_bias = np.asarray(
            tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64
        )
        q_projection = quantize_float_rows(projection_weight, bits=QUANT_BITS)

    fonts = build_font_group(
        "qkv-rowbase", quantized.codes, rebuild=False, row_specific_bases=True
    )
    if fonts.row_bases is None:
        raise ValueError("row-specific font bases are required")
    bases = np.sum(np.stack(fonts.row_bases), axis=0)
    if args.with_projection:
        assert q_projection is not None
        projection_fonts = build_font_group(
            "attn-out-rowbase",
            q_projection.codes,
            rebuild=False,
            row_specific_bases=True,
        )
        if projection_fonts.row_bases is None:
            raise ValueError("projection row-specific bases are required")
        projection_bases = np.sum(np.stack(projection_fonts.row_bases), axis=0)
    q_output_indices = list(range(WIDTH))
    q_output_names = [f"--q-{index:03d}" for index in range(WIDTH)]
    if args.live_current_kv:
        q_output_indices += list(range(WIDTH, 3 * WIDTH))
        q_output_names += [f"--current-k-{index:03d}" for index in range(WIDTH)]
        q_output_names += [f"--current-v-{index:03d}" for index in range(WIDTH)]
    q_stage = selected_container_stage(
        stage_name=f"geometry-stream-q-{token_count}",
        normalized=normalized[target],
        output_indices=q_output_indices,
        output_names=q_output_names,
        fonts=fonts,
        bases=bases,
        input_range=input_range,
        quantized=quantized,
        bias=bias,
        output_ranges=output_ranges,
    )

    main_properties = [f"--q-{index:03d}" for index in range(WIDTH)]
    if args.live_current_kv:
        main_properties += [f"--current-k-{index:03d}" for index in range(WIDTH)]
        main_properties += [f"--current-v-{index:03d}" for index in range(WIDTH)]
    if args.reduction == "online":
        for bank in ("a", "b"):
            main_properties += [f"--m-{bank}-{head}" for head in range(HEADS)]
            main_properties += [f"--l-{bank}-{head}" for head in range(HEADS)]
    if args.with_projection:
        main_properties += [f"--context-{index:03d}" for index in range(WIDTH)]
    if args.score_backend in ("css-kv", "feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
        main_properties += [
            f"--score-{source}-{head}"
            for source in range(token_count)
            for head in range(HEADS)
        ]
        main_properties += [f"--flat-m-{head}" for head in range(HEADS)]
        main_properties += [f"--flat-l-{head}" for head in range(HEADS)]
        if args.value_backend == "mixed-input":
            main_properties += [
                f"--prob-{source}-{head}"
                for source in range(token_count)
                for head in range(HEADS)
            ]
    main_properties += [f"--r1-{index:03d}" for index in range(WIDTH)]
    main_css = [font_faces("qkv", fonts)]
    if projection_fonts is not None:
        main_css.append(font_faces("attnout", projection_fonts))
    main_css.append(registrations(main_properties))
    shadow_css = [
        ".metric{position:fixed;inset:0 auto auto 0;display:inline-flex;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre;font-style:normal}",
        ".metric-pair{position:fixed;left:0;top:-60000px;display:inline-grid;"
        "width:max-content;height:max-content;line-height:1px}",
        ".metric-pair::before,.metric-pair::after{position:static;grid-area:1/1;"
        "display:inline;overflow:hidden;white-space:pre;font-style:normal;line-height:1px}",
        ".metric-pair::before{content:var(--key-content)}",
        ".metric-pair::after{content:var(--value-content);writing-mode:vertical-rl;"
        "text-orientation:sideways}",
        ".score-scroller{position:fixed;left:0;top:-58000px;width:4096px;height:1px;"
        "overflow-x:scroll;overflow-y:hidden}",
        ".score-track{position:relative;width:12288px;height:1px}",
        ".score-track>.metric{position:absolute}",
        ".score-track>.metric-pair{position:absolute;left:0;top:0}",
        ".score-metric{position:absolute;left:0;top:0;display:block;height:1px}",
        ".acc{position:fixed;inset:0 auto auto 0;display:block;height:1px}",
        ".context-packet{position:fixed;inset:0 auto auto 0;display:block;container-type:size}",
    ]
    feature_chunks_by_head: list[str] = []
    if args.score_backend in ("feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
        assert feature_reference is not None
        assert feature_heads_reference is not None
        feature_faces = []
        for head in range(HEADS):
            font_names = (
                [f"feature-qk-h{head}-s{shard}.woff2" for shard in range(WIDTH // FEATURE_QK_SHARD)]
                if args.score_backend == "feature"
                else [f"bilinear-sum-projected-kv-qk-h{head}.woff2"]
                if args.score_backend == "bilinear-sum-kv"
                else [f"bilinear-projected-kv-qk-h{head}.woff2"]
                if args.score_backend == "bilinear-kv"
                else [f"projected-kv-qk-h{head}.woff2"]
            )
            for shard, font_name in enumerate(font_names):
                font_path = feature_qk_dir / font_name
                tag = hashlib.sha256(font_path.read_bytes()).hexdigest()[:12]
                codepoint_base = (
                    FEATURE_QK_CODEPOINT_BASE + shard * HEAD_WIDTH
                    if args.score_backend == "feature"
                    else BILINEAR_PROJECTED_KV_QK_CODEPOINT_BASE
                    if args.score_backend in ("bilinear-kv", "bilinear-sum-kv")
                    else PROJECTED_KV_QK_CODEPOINT_BASE
                )
                family = (
                    f"FQKH{head}S{shard}"
                    if args.score_backend == "feature"
                    else f"BSPKVQKH{head}"
                    if args.score_backend == "bilinear-sum-kv"
                    else f"BPKVQKH{head}"
                    if args.score_backend == "bilinear-kv"
                    else f"PKVQKH{head}"
                )
                feature_faces.append(
                    f'@font-face{{font-family:{family};src:url("../'
                    f'{feature_qk_dir.name}/{font_path.name}?v={tag}") format("woff2");'
                    f'unicode-range:U+{codepoint_base:X}-'
                    f'{codepoint_base + HEAD_WIDTH - 1:X}}}'
                )
        main_css.append("".join(feature_faces))
        if args.score_backend in ("bilinear-kv", "bilinear-sum-kv"):
            shadow_css.append(
                ".bilinear-score{display:inline-block;width:max-content;white-space:pre;"
                "font-kerning:none}"
            )
        else:
            shadow_css.append(
                ".feature-score{display:inline-flex;width:max-content;white-space:pre;"
                "font-kerning:none;font-feature-settings:normal;font-variation-settings:inherit}"
                ".feature-score>b{font:inherit;font-feature-settings:inherit}"
            )
        for head in range(HEADS):
            start = head * HEAD_WIDTH
            ranges = (
                output_ranges[start:start + HEAD_WIDTH]
                * args.feature_query_range_scale
            )
            families_for_head = (
                ",".join(
                    f"FQKH{head}S{shard}" for shard in range(WIDTH // FEATURE_QK_SHARD)
                )
                if args.score_backend == "feature"
                else f"BSPKVQKH{head}"
                if args.score_backend == "bilinear-sum-kv"
                else f"BPKVQKH{head}"
                if args.score_backend == "bilinear-kv"
                else f"PKVQKH{head}"
            )
            if args.score_backend in ("bilinear-kv", "bilinear-sum-kv"):
                query_settings = ",".join(
                    f'"Q{coordinate:03d}" clamp(-1,var(--q-{start + coordinate:03d}) / '
                    f'{css_number(ranges[coordinate])},1)'
                    for coordinate in range(HEAD_WIDTH)
                )
                shadow_css.append(
                    f".bilinear-score-h{head}{{font:normal {FEATURE_QK_FONT_SIZE}px "
                    f"{families_for_head};font-family:{families_for_head};"
                    f"--bilinear-q-settings:{query_settings}}}"
                )
                feature_chunks_by_head.append(
                    f"&#x{BILINEAR_PROJECTED_KV_QK_CODEPOINT_BASE:X};"
                    if args.score_backend == "bilinear-sum-kv"
                    else "".join(
                        f"&#x{BILINEAR_PROJECTED_KV_QK_CODEPOINT_BASE + coordinate:X};"
                        for coordinate in range(HEAD_WIDTH)
                    )
                )
                continue
            shadow_css.append(
                f".feature-score-h{head}{{font:normal {FEATURE_QK_FONT_SIZE}px "
                f"{families_for_head};font-family:{families_for_head};"
                "font-variation-settings:inherit}"
            )
            chunks = []
            for chunk, chunk_start in enumerate(range(0, HEAD_WIDTH, args.feature_query_chunk)):
                chunk_stop = min(chunk_start + args.feature_query_chunk, HEAD_WIDTH)
                settings = ",".join(
                    f'"Q{coordinate:03d}" calc(1 + round(nearest,'
                    f'clamp(0,(var(--q-{start + coordinate:03d}) + '
                    f'{css_number(ranges[coordinate])}) * {FEATURE_QK_LEVELS - 1} / '
                    f'{css_number(2 * ranges[coordinate])},{FEATURE_QK_LEVELS - 1}),1))'
                    for coordinate in range(chunk_start, chunk_stop)
                )
                shadow_css.append(
                    f".feature-score-h{head}>.feature-chunk-{chunk}"
                    f"{{font-feature-settings:{settings}}}"
                )
                text = "".join(
                    f"&#x{codepoint:X};"
                    for coordinate in range(chunk_start, chunk_stop)
                    for codepoint in (
                        [
                            FEATURE_QK_CODEPOINT_BASE + shard * HEAD_WIDTH + coordinate
                            for shard in range(WIDTH // FEATURE_QK_SHARD)
                        ]
                        if args.score_backend == "feature"
                        else [PROJECTED_KV_QK_CODEPOINT_BASE + coordinate]
                    )
                )
                chunks.append(f'<b class="feature-chunk-{chunk}">{text}</b>')
            feature_chunks_by_head.append("".join(chunks))
    if args.isolate_query_inheritance:
        shadow_css.append(
            ".kv-no-q{display:contents;"
            + ";".join(f"--q-{index:03d}:initial" for index in range(WIDTH))
            + "}.score-track>.kv-no-q>.metric{position:absolute}"
            ".score-track>.kv-no-q>.metric-pair{position:absolute;left:0;top:0}"
        )
    if cache_group_size:
        shadow_css.append(
            ".geometry-kv-source{display:contents;"
            + ";".join(f"--q-{index:03d}:initial" for index in range(WIDTH))
            + "}.score-track>.geometry-kv-source>.metric{position:absolute}"
            ".score-track>.geometry-kv-source>.metric-pair{position:absolute;left:0;top:0}"
        )

    score_range = float(max(np.max(np.abs(scores)) * 1.2, 1.0))
    score_scale = 64
    score_base = math.ceil(score_range * score_scale) + 128
    score_viewport = 4096
    acc_scale = 256
    acc_absmax = float(max(np.max(np.abs(numerator_states)), 1.0))
    acc_base = math.ceil(acc_absmax * acc_scale) + 1024
    source_templates = []
    source_fragments = []
    all_score_timelines: list[str] = []
    all_score_progress: list[str] = []
    all_score_keyframes: list[str] = []
    acc_anchors: list[str] = []
    all_value_lengths: list[list[str]] = []
    families = ",".join(f"qkvS{index}" for index in range(len(fonts.names)))

    if args.score_backend == "css":
        for head in range(HEADS):
            score_terms = []
            for local in range(HEAD_WIDTH):
                index = head * HEAD_WIDTH + local
                output = WIDTH + index
                key_terms = " + ".join(
                    f"var(--geometry-x-{column:03d}) * {css_number(quantized.reconstructed[output, column])}"
                    for column in range(WIDTH)
                )
                score_terms.append(
                    f"var(--q-{index:03d}) * (({key_terms}) + {css_number(bias[output])})"
                )
            shadow_css.append(
                f".geometry-css-score-{head}{{width:calc({score_base}px + {score_scale}px * "
                f"(({' + '.join(score_terms)}) / {math.sqrt(HEAD_WIDTH)}))}}"
            )
    if args.score_backend == "css-kv":
        for source in range(token_count):
            for head in range(HEADS):
                start = head * HEAD_WIDTH
                score_terms = []
                for local in range(HEAD_WIDTH):
                    index = start + local
                    key_value = (
                        f"var(--current-k-{index:03d})"
                        if args.live_current_kv and source == target
                        else f"var(--kcache-{source}-{index:03d})"
                        if args.cache_state_transport == "nested-vars"
                        else css_number(key[source, head, local])
                    )
                    score_terms.append(f"var(--q-{index:03d}) * {key_value}")
                shadow_css.append(
                    f".geometry-source-{token_count}-{source}-score-{head}{{"
                    f"width:calc({score_base}px + {score_scale}px * "
                    f"(({' + '.join(score_terms)}) / {math.sqrt(HEAD_WIDTH)}))}}"
                )

    for source in range(token_count):
        stage = f"geometry-source-{token_count}-{source}"
        if args.score_backend in ("css-kv", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
            inputs = []
            input_values = ""
        elif args.cache_state_transport == "nested-vars":
            inputs = [f"--cache-{source}-{index:03d}" for index in range(WIDTH)]
            input_values = ""
        else:
            inputs = [
                f"--geometry-x-{index:03d}" if args.score_backend == "css"
                else f"--{stage}-i-{index:03d}"
                for index in range(WIDTH)
            ]
            input_values = ";".join(
                f"{name}:{css_number(value)}"
                for name, value in zip(inputs, normalized[source], strict=True)
            )
        score_timelines = [f"--{stage}-st-{head}" for head in range(HEADS)]
        score_progress = [f"--{stage}-sp-{head}" for head in range(HEADS)]
        score_keyframes = [f"{stage}-sk-{head}" for head in range(HEADS)]
        all_score_timelines.extend(score_timelines)
        all_score_progress.extend(score_progress)
        all_score_keyframes.extend(score_keyframes)
        main_css.append("".join(
            f'@property {name}'
            '{syntax:"<number>";inherits:true;initial-value:-1}'
            for name in score_progress
        ))
        shadow_css.append("".join(
            f"@keyframes {keyframe}{{from{{{progress}:0}}to{{{progress}:1}}}}"
            for progress, keyframe in zip(score_progress, score_keyframes, strict=True)
        ))
        local_timeline_scope = (
            f"timeline-scope:{','.join(score_timelines)};"
            if args.source_topology == "nested" else ""
        )
        if args.score_backend in ("feature-kv", "bilinear-kv"):
            shadow_css.append(f".{stage}{{{local_timeline_scope}display:contents}}")
        else:
            shadow_css.append(
                f".{stage}{{{input_values};{local_timeline_scope}"
                f"font:normal {FONT_SIZE}px qkvS0;font-family:{families};font-kerning:none;"
                f"font-variation-settings:{pack_font_settings(inputs, input_range, 0)}}}"
            )

        key_metrics = []
        value_metrics = []
        pair_metrics = []
        key_anchors = []
        value_anchors = []
        for index in range(WIDTH):
            key_output = WIDTH + index
            value_output = 2 * WIDTH + index
            key_anchor = f"--{stage}-k-{index}"
            value_anchor = (
                key_anchor if args.metric_markup == "pseudo"
                else f"--{stage}-v-{index}"
            )
            key_anchors.append(key_anchor)
            value_anchors.append(value_anchor)
            key_chars = "".join(
                f"&#x{start + key_output:X};" for start in fonts.codepoint_starts
            )
            value_chars = "".join(
                f"&#x{start + value_output:X};" for start in fonts.codepoint_starts
            )
            if args.metric_markup == "pseudo":
                key_content = "'" + "".join(
                    f"\\{start + key_output:X} " for start in fonts.codepoint_starts
                ) + "'"
                value_content = "'" + "".join(
                    f"\\{start + value_output:X} " for start in fonts.codepoint_starts
                ) + "'"
                pair_metrics.append(
                    f'<i class="metric-pair" style="anchor-name:{key_anchor};'
                    f'--key-content:{key_content};'
                    f'--value-content:{value_content}"></i>'
                )
            elif args.score_backend == "font":
                key_metrics.append(
                    f'<i class="metric" style="anchor-name:{key_anchor}">{key_chars}</i>'
                )
            if args.metric_markup != "pseudo" and args.value_backend == "per-source":
                value_metrics.append(
                    f'<i class="metric" style="anchor-name:{value_anchor}">{value_chars}</i>'
                )

        score_metrics = []
        for head in range(HEADS):
            score_class = f"{stage}-score-{head}"
            if args.score_backend == "font":
                start = head * HEAD_WIDTH
                terms = []
                for local in range(HEAD_WIDTH):
                    index = start + local
                    output = WIDTH + index
                    factor = input_range * quantized.scales[output]
                    key_length = (
                        f"((anchor-size({key_anchors[index]} width) * {UNITS_PER_EM} / "
                        f"{FONT_SIZE} - {int(bases[output])}px) * {css_number(factor)} + "
                        f"{css_number(bias[output])}px)"
                    )
                    terms.append(f"var(--q-{index:03d}) * {key_length}")
                shadow_css.append(
                    f".{score_class}{{width:calc({score_base}px + {score_scale} * "
                    f"(({' + '.join(terms)}) / {math.sqrt(HEAD_WIDTH)}))}}"
                )
            else:
                if args.score_backend in ("css", "css-kv"):
                    score_class += f" geometry-css-score-{head}"
                elif args.score_backend in ("feature", "feature-kv"):
                    score_class += f" feature-score feature-score-h{head}"
                    if args.score_backend == "feature-kv":
                        assert feature_heads_reference is not None
                        key_ranges = np.asarray(
                            feature_heads_reference[head]["keyRanges"], dtype=np.float64
                        )
                        key_settings = ",".join(
                            f'"K{local:03d}" clamp(-1,'
                            + (
                                f"var(--current-k-{head * HEAD_WIDTH + local:03d})"
                                if args.live_current_kv and source == target
                                else f"var(--kcache-{source}-{head * HEAD_WIDTH + local:03d})"
                                if args.cache_state_transport == "nested-vars"
                                else css_number(key[source, head, local])
                            )
                            + f" / {css_number(key_ranges[local])},1)"
                            for local in range(HEAD_WIDTH)
                        )
                        shadow_css.append(
                            f".{stage}-score-{head}{{font-variation-settings:{key_settings}}}"
                        )
                else:
                    assert args.score_backend in ("bilinear-kv", "bilinear-sum-kv")
                    assert feature_heads_reference is not None
                    score_class += f" bilinear-score bilinear-score-h{head}"
                    key_ranges = np.asarray(
                        feature_heads_reference[head]["keyRanges"], dtype=np.float64
                    )
                    key_settings = ",".join(
                        f'"K{local:03d}" clamp(-1,'
                        + (
                            f"var(--current-k-{head * HEAD_WIDTH + local:03d})"
                            if args.live_current_kv and source == target
                            else f"var(--kcache-{source}-{head * HEAD_WIDTH + local:03d})"
                            if args.cache_state_transport == "nested-vars"
                            else css_number(key[source, head, local])
                        )
                        + f" / {css_number(key_ranges[local])},1)"
                        for local in range(HEAD_WIDTH)
                    )
                    shadow_css.append(
                        f".{stage}-score-{head}{{--bilinear-k-settings:{key_settings};"
                        "font-variation-settings:var(--bilinear-q-settings),"
                        "var(--bilinear-k-settings)}"
                    )
            score_metrics.append(
                f'<i class="score-metric {score_class}" '
                f'style="view-timeline:{score_timelines[head]} inline">'
                f'{feature_chunks_by_head[head] if args.score_backend in ("feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv") else ""}'
                "</i>"
            )

        result_declarations = [
            f"animation-name:{','.join(score_keyframes)}",
            "animation-duration:1s",
            "animation-timing-function:linear",
            "animation-fill-mode:both",
            f"animation-timeline:{','.join(score_timelines)}",
            "animation-range:cover",
        ]
        score_names = [
            f"--score-{source}-{head}" if args.reduction != "online" else f"--score-{head}"
            for head in range(HEADS)
        ]
        result_declarations += [
            f"{score_names[head]}:calc(({score_viewport} / var({score_progress[head]}) - "
            f"{score_viewport} - {score_base}) / {score_scale})"
            for head in range(HEADS)
        ]
        out_bank = "a" if source % 2 == 0 else "b"
        if args.reduction == "online":
            if source == 0:
                for head in range(HEADS):
                    result_declarations += [
                        f"--m-{out_bank}-{head}:var(--score-{head})",
                        f"--l-{out_bank}-{head}:1",
                    ]
            else:
                old_bank = "b" if out_bank == "a" else "a"
                for head in range(HEADS):
                    result_declarations += [
                        f"--m-{out_bank}-{head}:max(var(--m-{old_bank}-{head}),var(--score-{head}))",
                        f"--old-w-{head}:exp(var(--m-{old_bank}-{head}) - var(--m-{out_bank}-{head}))",
                        f"--new-w-{head}:exp(var(--score-{head}) - var(--m-{out_bank}-{head}))",
                        f"--l-{out_bank}-{head}:calc(var(--l-{old_bank}-{head}) * "
                        f"var(--old-w-{head}) + var(--new-w-{head}))",
                    ]
        elif source == token_count - 1:
            for head in range(HEADS):
                head_scores = [f"var(--score-{item}-{head})" for item in range(token_count)]
                result_declarations += [
                    f"--flat-m-{head}:max({','.join(head_scores)})",
                    f"--flat-l-{head}:calc(" + " + ".join(
                        f"exp(var(--score-{item}-{head}) - var(--flat-m-{head}))"
                        for item in range(token_count)
                    ) + ")",
                ]
        if args.source_topology == "nested":
            shadow_css.append(
                f".{stage}-result{{{';'.join(result_declarations)}}}"
            )

        new_acc_anchors = []
        acc_elements = []
        source_value_lengths = []
        for index in range(WIDTH):
            head = index // HEAD_WIDTH
            if args.value_backend == "cached-v":
                value_length = (
                    f"calc(var(--current-v-{index:03d}) * 1px)"
                    if args.live_current_kv and source == target
                    else f"calc(var(--vcache-{source}-{index:03d}) * 1px)"
                    if args.cache_state_transport == "nested-vars"
                    else f"{css_number(value[source].reshape(WIDTH)[index])}px"
                )
                source_value_lengths.append(value_length)
                continue
            value_output = 2 * WIDTH + index
            factor = input_range * quantized.scales[value_output]
            value_length = (
                f"((anchor-size({value_anchors[index]} "
                f"{'height' if args.metric_markup == 'pseudo' else 'width'}) * {UNITS_PER_EM} / "
                f"{FONT_SIZE} - {int(bases[value_output])}px) * {css_number(factor)} + "
                f"{css_number(bias[value_output])}px)"
            )
            source_value_lengths.append(value_length)
            if args.reduction != "online":
                continue
            acc_anchor = f"--{stage}-acc-{index}"
            new_acc_anchors.append(acc_anchor)
            if source == 0:
                width = f"calc({acc_base}px + {acc_scale} * {value_length})"
            else:
                width = (
                    f"calc({acc_base}px + var(--old-w-{head}) * "
                    f"(anchor-size({acc_anchors[index]} width) - {acc_base}px) + "
                    f"var(--new-w-{head}) * {acc_scale} * {value_length})"
                )
            shadow_css.append(f".{stage}-acc-{index}{{width:{width}}}")
            acc_elements.append(
                f'<i class="acc {stage}-acc-{index}" style="anchor-name:{acc_anchor}"></i>'
            )
        acc_anchors = new_acc_anchors
        all_value_lengths.append(source_value_lengths)
        key_markup = "".join(key_metrics) + "".join(pair_metrics)
        value_markup = "".join(value_metrics)
        if args.isolate_query_inheritance:
            key_markup = f'<span class="kv-no-q">{key_markup}</span>'
            value_markup = f'<span class="kv-no-q">{value_markup}</span>'
        if not cache_group_size:
            source_content = (
                f'<div class="score-scroller"><div class="score-track">'
                + key_markup + "".join(score_metrics)
                + "</div></div>" + value_markup
            )
        if cache_group_size:
            source_fragments.append(
                f'<span class="{stage} geometry-kv-source">'
                + key_markup + value_markup + "</span>"
                + "".join(score_metrics)
            )
        elif args.source_topology == "nested":
            source_templates.append(
                f'<div class="{stage}">{source_content}'
                + f'<div class="{stage}-result">' + "".join(acc_elements)
                + "{child}</div></div>"
            )
        else:
            source_fragments.append(f'<div class="{stage}">{source_content}</div>')

    if args.source_topology == "siblings":
        global_declarations = [
            f"animation-name:{','.join(all_score_keyframes)}",
            "animation-duration:1s",
            "animation-timing-function:linear",
            "animation-fill-mode:both",
            f"animation-timeline:{','.join(all_score_timelines)}",
            "animation-range:cover",
        ]
        for source in range(token_count):
            for head in range(HEADS):
                progress = all_score_progress[source * HEADS + head]
                if args.score_backend in ("feature", "feature-kv", "bilinear-kv", "bilinear-sum-kv"):
                    assert feature_heads_reference is not None
                    head_reference = feature_heads_reference[head]
                    base_units = int(head_reference["base"]) * int(
                        head_reference.get("glyphCount", HEAD_WIDTH)
                    ) * (WIDTH // FEATURE_QK_SHARD if args.score_backend == "feature" else 1)
                    dot_scale = int(head_reference["dotScale"])
                    global_declarations.append(
                        f"--score-{source}-{head}:calc((({score_viewport} / "
                        f"var({progress}) - {score_viewport}) * {UNITS_PER_EM} / "
                        f"{FEATURE_QK_FONT_SIZE} - {base_units}) / {dot_scale} / "
                        f"{math.sqrt(HEAD_WIDTH)})"
                    )
                else:
                    global_declarations.append(
                        f"--score-{source}-{head}:calc(({score_viewport} / var({progress}) - "
                        f"{score_viewport} - {score_base}) / {score_scale})"
                    )
        for head in range(HEADS):
            head_scores = [f"var(--score-{source}-{head})" for source in range(token_count)]
            global_declarations += [
                f"--flat-m-{head}:max({','.join(head_scores)})",
                f"--flat-l-{head}:calc(" + " + ".join(
                    f"exp(var(--score-{source}-{head}) - var(--flat-m-{head}))"
                    for source in range(token_count)
                ) + ")",
            ]
            if args.value_backend == "mixed-input":
                global_declarations += [
                    f"--prob-{source}-{head}:calc(exp(var(--score-{source}-{head}) - "
                    f"var(--flat-m-{head})) / var(--flat-l-{head}))"
                    for source in range(token_count)
                ]
        shadow_css.append(
            f".geometry-sibling-sources{{timeline-scope:{','.join(all_score_timelines)}}}"
            f".geometry-flat-result{{{';'.join(global_declarations)}}}"
        )

    mixed_value_markup = ""
    mixed_value_lengths: list[str] = []
    if args.value_backend == "mixed-input":
        mixed_head_markup = []
        for head in range(HEADS):
            settings = []
            for dimension in range(WIDTH):
                shard = dimension // FEATURE_QK_SHARD
                local = dimension % FEATURE_QK_SHARD
                weighted = " + ".join(
                    f"var(--prob-{source}-{head}) * "
                    + (
                        f"var(--cache-{source}-{dimension:03d})"
                        if args.cache_state_transport == "nested-vars"
                        else css_number(normalized[source, dimension])
                    )
                    for source in range(token_count)
                )
                settings.append(
                    f'"{packed_axis_tag(shard, local)}" '
                    f"calc(({weighted}) / {css_number(input_range)})"
                )
            shadow_css.append(
                f".mixed-v-head-{head}{{font:normal {FONT_SIZE}px qkvS0;"
                f"font-family:{families};font-kerning:none;"
                f"font-variation-settings:{','.join(settings)}}}"
            )
            head_metrics = []
            for local_output in range(HEAD_WIDTH):
                index = head * HEAD_WIDTH + local_output
                value_output = 2 * WIDTH + index
                anchor = f"--mixed-v-{index}"
                chars = "".join(
                    f"&#x{start + value_output:X};" for start in fonts.codepoint_starts
                )
                head_metrics.append(
                    f'<i class="metric" style="anchor-name:{anchor}">{chars}</i>'
                )
                factor = input_range * quantized.scales[value_output]
                mixed_value_lengths.append(
                    f"((anchor-size({anchor} width) * {UNITS_PER_EM} / {FONT_SIZE} - "
                    f"{int(bases[value_output])}px) * {css_number(factor)} + "
                    f"{css_number(bias[value_output])}px)"
                )
            mixed_head_markup.append(
                f'<div class="mixed-v-head-{head}">{"".join(head_metrics)}</div>'
            )
        mixed_value_markup = "".join(mixed_head_markup)

    flat_acc_markup = ""
    flat_value_expressions: list[str] = []
    if args.reduction != "online":
        acc_anchors = []
        flat_acc_elements = []
        for index in range(WIDTH):
            head = index // HEAD_WIDTH
            if args.value_backend == "mixed-input":
                value_expression = f"({mixed_value_lengths[index]} / 1px)"
            else:
                weighted_values = " + ".join(
                    f"exp(var(--score-{source}-{head}) - var(--flat-m-{head})) * "
                    f"{all_value_lengths[source][index]}"
                    for source in range(token_count)
                )
                value_expression = f"(({weighted_values}) / 1px / var(--flat-l-{head}))"
            flat_value_expressions.append(value_expression)
            if args.reduction == "flat":
                acc_anchor = f"--geometry-flat-acc-{index}"
                acc_anchors.append(acc_anchor)
                shadow_css.append(
                    f".geometry-flat-acc-{index}{{width:calc({acc_base}px + {acc_scale} * "
                    f"({value_expression} * 1px))}}"
                )
                flat_acc_elements.append(
                    f'<i class="acc geometry-flat-acc-{index}" '
                    f'style="anchor-name:{acc_anchor}"></i>'
                )
        flat_acc_markup = mixed_value_markup + "".join(flat_acc_elements)

    final_bank = "a" if (token_count - 1) % 2 == 0 else "b"
    context_precision = json.loads(CONTEXT_PRECISION_REPORT.read_text())
    context_ranges = np.asarray(
        context_precision["margins"]["2.0"]["perChannelRanges"],
        dtype=np.float64,
    )
    context_levels = (1 << args.context_bits) - 1
    context_codes = np.rint(
        np.clip(
            (context + context_ranges) * context_levels / (2 * context_ranges),
            0,
            context_levels,
        )
    )
    context_decoded = (
        -context_ranges + context_codes * (2 * context_ranges / context_levels)
    )
    context_radix = 1 << args.context_bits
    context_digits_per_axis = 24 // args.context_bits
    context_outputs_per_packet = context_digits_per_axis * 2
    packet_metrics = []
    packet_dimensions = []
    packet_declarations = []
    for packet_start in range(0, WIDTH, context_outputs_per_packet):
        dimensions = []
        declarations = []
        for axis, unit in enumerate(("w", "h")):
            codes = []
            packed = f"round(nearest,100cq{unit} / 1px,1)"
            for digit in range(context_digits_per_axis):
                index = packet_start + axis * context_digits_per_axis + digit
                head = index // HEAD_WIDTH
                if args.reduction == "inline":
                    value_expression = flat_value_expressions[index]
                else:
                    value_expression = (
                        f"((anchor-size({acc_anchors[index]} width) / 1px - {acc_base}) / "
                        f"{acc_scale})"
                    )
                if args.reduction == "online":
                    value_expression = value_expression[:-1] + f" / var(--l-{final_bank}-{head}))"
                value_range = float(context_ranges[index])
                codes.append(
                    f"round(nearest,clamp(0px,calc(({value_expression} + "
                    f"{css_number(value_range)}) * {context_levels} / "
                    f"{css_number(2 * value_range)} * 1px),{context_levels}px),1px)"
                )
                if digit == 0:
                    code = f"mod({packed},{context_radix})"
                elif digit < context_digits_per_axis - 1:
                    code = (
                        f"mod(round(down,{packed}/{context_radix ** digit},1),"
                        f"{context_radix})"
                    )
                else:
                    code = f"round(down,{packed}/{context_radix ** digit},1)"
                output_name = "context" if args.with_projection else "r1"
                declarations.append(
                    f"--{output_name}-{index:03d}:calc(-{css_number(value_range)} + {code} * "
                    f"{css_number(2 * value_range / context_levels)})"
                )
            dimensions.append(
                "calc(" + " + ".join(
                    f"{code} * {context_radix ** digit}"
                    for digit, code in enumerate(codes)
                ) + ")"
            )
        packet_dimensions.append(dimensions)
        packet_declarations.append(declarations)
    for packet, (width, height) in enumerate(packet_dimensions):
        inherited = [] if packet == 0 else packet_declarations[packet - 1]
        shadow_css.append(
            f".context-packet-{packet}{{width:{width};height:{height};"
            + ";".join(inherited) + "}"
        )
    shadow_css.append("slot{" + ";".join(packet_declarations[-1]) + "}")
    light_child = '<output id="attention-result"></output>'
    if args.with_projection and args.projection_transport.startswith("packet"):
        assert projection_fonts is not None
        assert projection_bases is not None
        assert projection_bias is not None
        assert q_projection is not None
        projection_ranges = np.asarray(
            context_precision["projectionMargins"]["1.5"]["perChannelRanges"],
            dtype=np.float64,
        )
        context_range = float(np.max(context_ranges))
        context_names = [f"--context-{index:03d}" for index in range(WIDTH)]
        projection_families = ",".join(
            f"attnoutS{index}" for index in range(len(projection_fonts.names))
        )
        main_css.append(
            f'.geometry-projection{{font:normal {FONT_SIZE}px attnoutS0;'
            f"font-family:{projection_families};font-kerning:none;"
            f"font-variation-settings:{pack_font_settings(context_names, context_range, 0)}}}"
            ".geometry-projection-metric{position:fixed;inset:0 auto auto 0;"
            "display:inline-flex;width:max-content;height:1px;overflow:hidden;"
            "white-space:pre;font-style:normal}"
            ".geometry-projection-packet{position:fixed;inset:0 auto auto 0;"
            "display:block;container-type:size}"
        )
        projection_metrics = []
        projection_anchors = []
        for index in range(WIDTH):
            anchor = f"--geometry-projection-output-{index}"
            projection_anchors.append(anchor)
            characters = "".join(
                f"&#x{start + index:X};"
                for start in projection_fonts.codepoint_starts
            )
            projection_metrics.append(
                f'<i class="geometry-projection-metric" '
                f'style="anchor-name:{anchor}">{characters}</i>'
            )

        projection_values = q_projection.reconstructed @ context_decoded + projection_bias
        projection_bits = int(args.projection_transport.removeprefix("packet"))
        projection_levels = (1 << projection_bits) - 1
        projection_codes = np.rint(
            np.clip(
                (projection_values + projection_ranges) * projection_levels
                / (2 * projection_ranges),
                0,
                projection_levels,
            )
        )
        projection_decoded = (
            -projection_ranges
            + projection_codes * (2 * projection_ranges / projection_levels)
        )
        projected = projection_decoded
        residual = x[target] + projection_decoded

        projection_packet_dimensions = []
        projection_packet_declarations = []
        projection_radix = 1 << projection_bits
        digits_per_axis = 24 // projection_bits
        outputs_per_packet = digits_per_axis * 2
        for packet_start in range(0, WIDTH, outputs_per_packet):
            dimensions = []
            declarations = []
            for axis, unit in enumerate(("w", "h")):
                codes = []
                packed = f"round(nearest,100cq{unit} / 1px,1)"
                for digit in range(digits_per_axis):
                    index = packet_start + axis * digits_per_axis + digit
                    factor = context_range * q_projection.scales[index]
                    value = (
                        f"((anchor-size({projection_anchors[index]} width) / 1px * "
                        f"{UNITS_PER_EM} / {FONT_SIZE} - {int(projection_bases[index])}) * "
                        f"{css_number(factor)} + ({css_number(projection_bias[index])}))"
                    )
                    value_range = float(projection_ranges[index])
                    codes.append(
                        f"round(nearest,clamp(0px,calc(({value} + "
                        f"{css_number(value_range)}) * {projection_levels} / "
                        f"{css_number(2 * value_range)} * 1px),"
                        f"{projection_levels}px),1px)"
                    )
                    shifted = (
                        packed
                        if digit == 0
                        else f"round(down,{packed}/{projection_radix ** digit},1)"
                    )
                    code = f"mod({shifted},{projection_radix})"
                    declarations.append(
                        f"--r1-{index:03d}:calc({css_number(x[target, index])} - "
                        f"{css_number(value_range)} + {code} * "
                        f"{css_number(2 * value_range / projection_levels)})"
                    )
                dimensions.append(
                    "calc(" + " + ".join(
                        f"{code} * {projection_radix ** digit}"
                        for digit, code in enumerate(codes)
                    ) + ")"
                )
            projection_packet_dimensions.append(dimensions)
            projection_packet_declarations.append(declarations)
        for packet, (width, height) in enumerate(projection_packet_dimensions):
            inherited = [] if packet == 0 else projection_packet_declarations[packet - 1]
            main_css.append(
                f".geometry-projection-packet-{packet}{{width:{width};height:{height};"
                + ";".join(inherited) + "}"
            )
        main_css.append(
            ".geometry-projection-result{"
            + ";".join(projection_packet_declarations[-1]) + "}"
        )
        projection_child = '<output class="geometry-projection-result" id="attention-result"></output>'
        for packet in reversed(range(len(projection_packet_dimensions))):
            projection_child = (
                f'<i class="geometry-projection-packet geometry-projection-packet-{packet}">'
                f"{projection_child}</i>"
            )
        light_child = (
            '<div class="geometry-projection">'
            + "".join(projection_metrics)
            + projection_child
            + "</div>"
        )
    if args.with_projection and args.projection_transport == "timeline":
        assert projection_fonts is not None
        assert projection_bases is not None
        assert projection_bias is not None
        assert q_projection is not None
        projected = q_projection.reconstructed @ context_decoded + projection_bias
        residual = x[target] + projected
        context_range = float(max(np.max(np.abs(context_decoded)) * 1.05, 0.05))
        viewport = 2 ** math.ceil(math.log2(max(
            1024,
            int(np.max(projection_bases)) * FONT_SIZE / UNITS_PER_EM * 1.25,
        )))
        timelines = [f"--gpt-{token_count}-{index}" for index in range(WIDTH)]
        progress = [f"--gpp-{token_count}-{index}" for index in range(WIDTH)]
        keyframes = [f"gpk-{token_count}-{index}" for index in range(WIDTH)]
        main_css.append(timeline_rules(progress, keyframes))
        context_names = [f"--context-{index:03d}" for index in range(WIDTH)]
        projection_families = ",".join(
            f"attnoutS{index}" for index in range(len(projection_fonts.names))
        )
        main_css.append(
            f'.geometry-projection{{timeline-scope:{",".join(timelines)};'
            f"font:normal {FONT_SIZE}px attnoutS0;font-family:{projection_families};"
            f"font-kerning:none;font-variation-settings:"
            f"{pack_font_settings(context_names, context_range, 0)}}}"
        )
        projection_declarations = []
        for index, value_name in enumerate(progress):
            raw = f"--gpraw-{token_count}-{index:03d}"
            factor = context_range * q_projection.scales[index]
            projection_declarations.extend((
                f"{raw}:calc(({viewport} / var({value_name}) - {viewport}) * "
                f"{UNITS_PER_EM} / {FONT_SIZE} - {int(projection_bases[index])})",
                f"--r1-{index:03d}:calc({css_number(x[target, index])} + "
                f"var({raw}) * {css_number(factor)} + "
                f"({css_number(projection_bias[index])}))",
            ))
        projection_consumers = math.ceil(WIDTH / OUTPUTS_PER_CONSUMER)
        for consumer in range(projection_consumers):
            start = consumer * OUTPUTS_PER_CONSUMER
            stop = min(start + OUTPUTS_PER_CONSUMER, WIDTH)
            main_css.append(
                f".geometry-projection-result-{consumer}{{"
                f"animation-name:{','.join(keyframes[start:stop])};"
                "animation-duration:1s;animation-timing-function:linear;"
                "animation-fill-mode:both;"
                f"animation-timeline:{','.join(timelines[start:stop])};"
                "animation-range:cover;"
                + ";".join(projection_declarations[start * 2:stop * 2]) + "}"
            )
        projection_metrics = shared_metrics(
            class_name="geometry-projection-metric",
            timeline_names=timelines,
            codepoint_starts=projection_fonts.codepoint_starts,
            output_count=WIDTH,
        )
        main_css.append(
            ".geometry-projection-scroller{position:fixed;left:0;top:-62000px;"
            f"width:{viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
            f".geometry-projection-track{{position:relative;width:{viewport * 3}px;height:1px}}"
            ".geometry-projection-metric{position:absolute;left:0;top:0;"
            "display:inline-flex;width:max-content;height:1px;overflow:hidden;"
            "white-space:pre;font-style:normal}"
        )
        projected_child = consumer_tree(
            "geometry-projection-result", projection_consumers, light_child
        )
        light_child = (
            '<div class="geometry-projection"><div class="geometry-projection-scroller">'
            f'<div class="geometry-projection-track">{projection_metrics}</div></div>'
            f"{projected_child}</div>"
        )

    child = "<slot></slot>"
    for packet in reversed(range(len(packet_dimensions))):
        child = f'<i class="context-packet context-packet-{packet}">{child}</i>'
    child = flat_acc_markup + child
    if args.source_topology == "siblings":
        if cache_group_size:
            grouped_tracks = "".join(
                '<div class="score-scroller"><div class="score-track">'
                + "".join(source_fragments[start:start + cache_group_size])
                + "</div></div>"
                for start in range(0, token_count, cache_group_size)
            )
            child = (
                '<div class="geometry-sibling-sources">' + grouped_tracks
                + f'<div class="geometry-flat-result">{child}</div></div>'
            )
        else:
            child = (
                '<div class="geometry-sibling-sources">'
                + "".join(source_fragments)
                + f'<div class="geometry-flat-result">{child}</div></div>'
            )
    else:
        for template in reversed(source_templates):
            child = template.replace("{child}", child)

    if args.cache_state_transport == "nested-vars":
        shadow_css.append(".state-cache{display:contents}")
        for source in reversed(range(token_count)):
            if args.value_backend == "cached-v":
                flat_key = key[source].reshape(WIDTH)
                flat_value = value[source].reshape(WIDTH)
                declarations = ";".join([
                    *(
                        f"--kcache-{source}-{index:03d}:{css_number(flat_key[index])}"
                        for index in range(WIDTH)
                    ),
                    *(
                        f"--vcache-{source}-{index:03d}:{css_number(flat_value[index])}"
                        for index in range(WIDTH)
                    ),
                ])
            else:
                declarations = ";".join(
                    f"--cache-{source}-{index:03d}:{css_number(normalized[source, index])}"
                    for index in range(WIDTH)
                )
            child = (
                f'<span class="state-cache state-cache-{source}" style="{declarations}">'
                f"{child}</span>"
            )

    css_path.write_text("".join(main_css))
    shadow_path.write_text("".join(shadow_css))
    main_tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    shadow_tag = hashlib.sha256(shadow_path.read_bytes()).hexdigest()[:12]
    attention = (
        '<geometry-stream-attention><template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{shadow_path.name}?v={shadow_tag}">{child}'
        f"</template>{light_child}</geometry-stream-attention>"
    )
    body = q_stage.replace("{child}", attention)
    html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        f'<title>{token_count}-token geometry streaming attention</title>'
        f'<link rel="stylesheet" href="{css_path.name}?v={main_tag}">{body}'
    )
    q_css = OUT / f"geometry-stream-q-{token_count}.css"
    reference = {
        "tokenIds": token_ids,
        "contextLength": token_count,
        "qkvTransport": "geometry-streaming",
        "attentionReduction": args.reduction,
        "scoreBackend": args.score_backend,
        "valueBackend": args.value_backend,
        "cacheStateTransport": args.cache_state_transport,
        "metricMarkup": args.metric_markup,
        "sourceTopology": args.source_topology,
        "scoreTrackGroupSize": cache_group_size or None,
        "scores": scores.tolist(),
        "probabilities": probabilities.tolist(),
        "context": context.tolist(),
        "baselineScores": baseline_scores.tolist(),
        "baselineProbabilities": baseline_probabilities.tolist(),
        "baselineContext": baseline_context.tolist(),
        "featureQueryBits": (
            FEATURE_QK_BITS if args.score_backend in ("feature", "feature-kv") else None
        ),
        "featureQueryChunk": (
            args.feature_query_chunk
            if args.score_backend in ("feature", "feature-kv") else None
        ),
        "featureQueryRangeScale": (
            args.feature_query_range_scale
            if args.score_backend in ("feature", "feature-kv") else None
        ),
        "kvCacheRepresentation": (
            "projected-key-value" if args.value_backend == "cached-v" else None
        ),
        "liveCurrentKv": args.live_current_kv,
        "residual": (
            residual.tolist() if residual is not None else context_decoded.tolist()
        ),
        "contextPackingRmse": float(np.sqrt(np.mean((context_decoded - context) ** 2))),
        "contextPackingBits": args.context_bits,
        "contextPackingContainers": len(packet_dimensions),
        "contextClippedFraction": float(np.mean(np.abs(context) > context_ranges)),
        "contextRangeCalibration": "1024 random sequences of length 1/2/4/8/16/32, 2.0 margin",
        "htmlBytes": html_path.stat().st_size,
        "cssBytes": css_path.stat().st_size + shadow_path.stat().st_size,
        "stageCssBytes": q_css.stat().st_size,
        "fontBytes": sum(
            (OUT / f"{name}.woff2").stat().st_size
            for name in (
                *fonts.names,
                *((projection_fonts.names) if projection_fonts is not None else ()),
            )
        ) + (
            int(feature_reference["totalFontBytes"])
            if feature_reference is not None else 0
        ),
        "withProjection": args.with_projection,
        "projectionTransport": args.projection_transport if args.with_projection else None,
        "accumulatorBase": acc_base,
        "accumulatorScale": acc_scale,
    }
    if args.with_projection:
        assert q_projection is not None
        assert projection_bias is not None
        high_precision_residual = (
            x[target] + q_projection.reconstructed @ context + projection_bias
        )
        baseline_high_precision_residual = (
            x[target] + q_projection.reconstructed @ baseline_context + projection_bias
        )
        reference["backendVsBaselineResidualRmse"] = float(np.sqrt(np.mean(
            (high_precision_residual - baseline_high_precision_residual) ** 2
        )))
        reference["backendVsBaselineResidualMaxError"] = float(np.max(np.abs(
            high_precision_residual - baseline_high_precision_residual
        )))
        reference["residualContextQuantizationRmse"] = float(
            np.sqrt(np.mean((residual - high_precision_residual) ** 2))
        )
        if args.projection_transport.startswith("packet"):
            high_precision_projection = (
                q_projection.reconstructed @ context_decoded + projection_bias
            )
            reference["projectionTransportRmse"] = float(
                np.sqrt(np.mean((projected - high_precision_projection) ** 2))
            )
            reference["projectionTransportClippedFraction"] = float(
                np.mean(np.abs(high_precision_projection) > projection_ranges)
            )
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "context": token_count,
        "context_rmse": reference["contextPackingRmse"],
        "html_bytes": reference["htmlBytes"],
        "css_bytes": reference["cssBytes"],
        "stage_css_bytes": reference["stageCssBytes"],
    })


if __name__ == "__main__":
    main()
