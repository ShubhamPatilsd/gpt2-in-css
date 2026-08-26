#!/usr/bin/env python3
"""Build a compact HVAR scorer connected to hierarchical CSS Grid argmax."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_output_head_benchmark as output_head
import build_hvar_embedding_qkv_chain as feedback
from analyze_output_head_search import generate_hidden_states
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "hvar-grid-output-head"
FONT_PATH = OUTPUT / "output-head.ttf"
VOCABULARY = 50_257
HIDDEN_WIDTH = 64
GROUP_SIZE = 256
LAYOUT_UNITS_PER_PX = 64
SCORE_SCALE = 1_024
SCORE_STRIDE_PX = GROUP_SIZE // LAYOUT_UNITS_PER_PX
INPUT_RANGE = 16.0
WEIGHT_MAX = 127
BASE_ADVANCE = 20_000
FONT_SIZE = 1_000
CODEPOINT_START = 0xF0000
LOOKUP_CODEPOINT_START = 0xE000
LOOKUP_BASE_ADVANCE = 20_000
LOOKUP_EMBEDDING_SCALE = 4_096


def feedback_transport_css(lower: np.ndarray, span: np.ndarray) -> str:
    levels = 4_095
    pack_rules = []
    decode_rules = []
    for group in range(HIDDEN_WIDTH // feedback.GROUP_SIZE):
        start = group * feedback.GROUP_SIZE
        declarations = ";".join(
            f"--feedback-code{place}:"
            f"{feedback.source_code(dimension, lower[dimension], span[dimension], levels)}"
            for place, dimension in enumerate(
                range(start, start + feedback.GROUP_SIZE)
            )
        )
        low_terms = [
            f"{feedback.RADIX ** place} * "
            f"mod(var(--feedback-code{place})/1px,{feedback.RADIX}) * 1px"
            for place in range(feedback.GROUP_SIZE)
        ]
        high_terms = [
            f"{feedback.RADIX ** place} * "
            f"round(down,var(--feedback-code{place})/1px/{feedback.RADIX},1) * 1px"
            for place in range(feedback.GROUP_SIZE)
        ]
        pack_rules.append(
            f".feedback-pack-{group}{{{declarations};"
            f"width:calc({' + '.join(low_terms)});"
            f"height:calc({' + '.join(high_terms)})}}"
        )
        progress = [
            f"({feedback.packed_digit('i', place)} + {feedback.RADIX} * "
            f"{feedback.packed_digit('b', place)})/{levels}"
            for place in range(feedback.GROUP_SIZE)
        ]
        decode_rules.append(
            f".feedback-decode-{group}{{"
            + ";".join(
                f"--feedback-v{start + place:03d}:calc({value})"
                for place, value in enumerate(progress)
            )
            + "}"
        )
    registrations = "".join(
        f'@property --feedback-v{dimension:03d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for dimension in range(HIDDEN_WIDTH)
    )
    sink_settings = ",".join(
        f'"{feedback.axis_tag(dimension)}" var(--feedback-v{dimension:03d})'
        for dimension in range(HIDDEN_WIDTH)
    )
    return registrations + "".join(pack_rules + decode_rules) + (
        ".feedback-source{position:absolute;display:inline-block;width:max-content;"
        "height:1px;overflow:hidden;white-space:pre;font-family:EmbeddingLookup;"
        f"font-size:{FONT_SIZE}px;font-variation-settings:"
        '"GRUP" var(--group),"LOCL" var(--local);'
        "font-kerning:none;font-style:normal}"
        ".feedback-carrier{position:absolute;container-type:size}"
        f"#qkv-result{{position:absolute;font-family:QKVFeedback;"
        f"font-size:{FONT_SIZE}px;line-height:1;font-kerning:none;white-space:pre;"
        f"height:1px;font-variation-settings:{sink_settings}}}"
        ".qkv-metric{display:inline-block;height:1px;overflow:hidden;"
        "font-style:normal}"
    )


def feedback_markup() -> str:
    metrics = "".join(
        f'<i class="qkv-metric" data-dimension="{dimension}">'
        f'&#x{0xF0000 + dimension:X};</i>'
        for dimension in range(feedback.QKV_WIDTH)
    )
    groups = HIDDEN_WIDTH // feedback.GROUP_SIZE
    chain = (
        f'<span id="qkv-result" class="feedback-decode-{groups - 1}">'
        f'{metrics}</span>'
    )
    for group in reversed(range(groups)):
        start = group * feedback.GROUP_SIZE
        sources = "".join(
            f'<i class="feedback-source" style="anchor-name:--e{dimension:02d}">'
            f'&#x{LOOKUP_CODEPOINT_START + dimension:X};</i>'
            for dimension in range(start, start + feedback.GROUP_SIZE)
        )
        classes = f"feedback-carrier feedback-pack-{group}"
        if group:
            classes += f" feedback-decode-{group - 1}"
        chain = (
            sources
            + f'<span class="{classes}" style="position-anchor:--e{start:02d}">'
            + chain
            + "</span>"
        )
    return chain


def css_number(value: float) -> str:
    return output_head.css_number(float(value))


def render_css(
    hidden_vectors: np.ndarray,
    row_scales: np.ndarray,
    embedding_lower: np.ndarray,
    embedding_span: np.ndarray,
    floor: int,
    groups: int,
) -> str:
    settings = ",".join(
        f'"X{dimension:03d}" calc((var(--h{dimension}) / {INPUT_RANGE:g} + 1) / 2)'
        for dimension in range(hidden_vectors.shape[1])
    )
    group_rules = [
        f".group-{group}{{anchor-name:--group-{group}}}"
        for group in range(groups)
    ]
    carrier_rules = [
        f".carrier-{group}{{--flag:clamp(0,1 - abs(var(--group) - {group}),1);"
        f"position-anchor:--group-{group};anchor-name:--carrier-{group};"
        f"width:calc(anchor-size(--group-{group} width) * var(--flag))}}"
        for group in range(groups)
    ]
    carrier_sizes = ",".join(
        f"anchor-size(--carrier-{group} width)" for group in range(groups)
    )
    return "\n".join(
        [
            '@font-face{font-family:OutputHeadHVAR;src:url("output-head.woff2") format("woff2")}',
            '@font-face{font-family:EmbeddingLookup;src:url("../hvar-token-embedding-lookup/embedding-lookup.woff2") format("woff2")}',
            '@font-face{font-family:QKVFeedback;src:url("../hvar-embedding-qkv-chain/qkv.woff2") format("woff2")}',
            '@property --bucket{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --group{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --local{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --winner{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --flag{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --embedding-value{syntax:"<number>";inherits:true;initial-value:-999}',
            output_head.query_rules(hidden_vectors),
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".model{position:fixed;inset:0 auto auto 0;display:grid;"
            "grid-template-columns:max-content;grid-template-rows:1px;"
            "width:max-content;height:1px;anchor-name:--outer-winner;"
            f"font-family:OutputHeadHVAR;font-size:{FONT_SIZE}px;line-height:1;"
            f"font-variation-settings:{settings};font-kerning:none}}",
            ".group-wrapper{grid-area:1/1;display:block;"
            f"width:calc-size(max-content,calc(round(down,size,{SCORE_STRIDE_PX}px) + "
            f"var(--group-tie)/{LAYOUT_UNITS_PER_PX}*1px))}}",
            ".group-grid{display:grid;grid-template-columns:max-content;"
            "grid-template-rows:1px;width:max-content;height:1px}",
            ".candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
            "overflow:hidden;white-space:pre;font-style:normal;"
            f"width:calc-size(max-content,calc(round(nearest,"
            f"(size - {BASE_ADVANCE}px) * var(--factor) + {-floor * SCORE_SCALE * SCORE_STRIDE_PX}px,"
            f"{SCORE_STRIDE_PX}px) + var(--local-tie)/{LAYOUT_UNITS_PER_PX}*1px))}}",
            "".join(group_rules),
            ".outer-reader{position:fixed;position-anchor:--outer-winner;"
            "inset:2px auto auto 0;width:anchor-size(--outer-winner width);height:1px;"
            "container:outer-result/inline-size}",
            "@container outer-result (width >= 0px){.selection{"
            f"--group:calc({GROUP_SIZE - 1} - round(nearest,"
            f"mod(100cqi,{SCORE_STRIDE_PX}px)/1px*{LAYOUT_UNITS_PER_PX},1));"
            f"--bucket:round(down,100cqi/{SCORE_STRIDE_PX}px,1)}}",
            ".carrier,.selected,.selected-reader{position:fixed;height:1px}",
            "".join(carrier_rules),
            ".selected{position-anchor:--carrier-0;anchor-name:--selected-group;"
            f"width:max({carrier_sizes})}}",
            ".selected-reader{position-anchor:--selected-group;"
            "width:anchor-size(--selected-group width);container:selected-result/inline-size}",
            "@container selected-result (width >= 0px){.result{"
            f"--local:calc({GROUP_SIZE - 1} - round(nearest,"
            f"mod(100cqi,{SCORE_STRIDE_PX}px)/1px*{LAYOUT_UNITS_PER_PX},1));"
            f"--winner:calc(var(--group)*{GROUP_SIZE} + var(--local));"
            "display:block;width:calc(var(--winner)*1px);height:1px}}",
            feedback_transport_css(embedding_lower, embedding_span),
        ]
    ) + "\n"


def render_html(row_scales: np.ndarray, groups: int) -> str:
    group_markup = []
    for group in range(groups):
        start = group * GROUP_SIZE
        stop = min(len(row_scales), start + GROUP_SIZE)
        items = []
        for token in range(start, stop):
            # A font-unit change represents INPUT_RANGE * row_scale logits.
            factor = INPUT_RANGE * row_scales[token] * SCORE_SCALE * SCORE_STRIDE_PX
            items.append(
                f'<i class="candidate" style="--factor:{css_number(factor)};'
                f'--local-tie:{GROUP_SIZE - 1 - token % GROUP_SIZE}">'
                f'&#x{CODEPOINT_START + token:X};</i>'
            )
        group_markup.append(
            f'<section class="group-wrapper" style="--group-tie:{GROUP_SIZE - 1 - group}">'
            f'<div class="group-grid group-{group}">{"".join(items)}</div></section>'
        )
    carriers = "".join(
        f'<i class="carrier carrier-{group}"></i>' for group in range(groups)
    )
    controls = "".join(
        f'<input type="radio" name="query" id="q{query}"{(" checked" if query == 0 else "")}>'
        for query in range(len(output_head.PROMPTS))
    )
    feedback_chain = feedback_markup()
    return f"""<!doctype html>
<meta charset="utf-8">
<title>HVAR + Grid TinyStories output head</title>
<link rel="stylesheet" href="index.css">
{controls}
<main id="model" class="model">{"".join(group_markup)}</main>
<div class="outer-reader"><div class="selection">
{carriers}<i class="selected"></i>
<div class="selected-reader"><output id="result" class="result">
{feedback_chain}</output></div>
</div></div>
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state = output_head.load_torch_zip(output_head.download_checkpoint())
    tokenizer = output_head.BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )
    hidden_vectors = np.stack(
        [output_head.final_hidden(tokenizer.encode(prompt), state)
         for prompt in output_head.PROMPTS]
    ).astype(np.float64)
    embeddings = state["transformer.wte.weight"][:VOCABULARY].astype(np.float64)
    feedback_font = ROOT / "experiments" / "hvar-embedding-qkv-chain" / "qkv.woff2"
    if not feedback_font.exists():
        feedback.main()
    embedding_lower = np.min(embeddings, axis=0)
    embedding_span = np.max(embeddings, axis=0) - embedding_lower
    qkv_weight = state["transformer.h.0.attn.c_attn.weight"].astype(np.float64)
    qkv_bias = state["transformer.h.0.attn.c_attn.bias"].astype(np.float64)
    qkv_coefficient = qkv_weight.T * embedding_span[None, :]
    qkv_row_scale = np.max(np.abs(qkv_coefficient), axis=1) / 127
    qkv_row_scale[qkv_row_scale == 0] = 1
    qkv_codes = np.rint(qkv_coefficient / qkv_row_scale[:, None]).astype(np.int16)
    qkv_base = embedding_lower @ qkv_weight + qkv_bias
    lookup_embeddings = (
        np.rint(embeddings * LOOKUP_EMBEDDING_SCALE) / LOOKUP_EMBEDDING_SCALE
    )
    normalized_embeddings = np.clip(
        (lookup_embeddings - embedding_lower) / embedding_span, 0, 1
    )
    transported_embeddings = np.rint(normalized_embeddings * 4_095) / 4_095
    row_scales = np.max(np.abs(embeddings), axis=1) / WEIGHT_MAX
    row_scales[row_scales == 0] = 1
    codes = np.rint(embeddings / row_scales[:, None]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * row_scales[:, None]

    # Shift signed inputs into nonnegative font axes: with u=(h/R+1)/2,
    # base=B-sum(q), and HVAR delta=2q, advance=B+q·h/R.
    base_advances = BASE_ADVANCE - codes.astype(np.int32).sum(axis=1)
    hvar_deltas = (codes * 2).astype(np.int16)
    if not FONT_PATH.with_suffix(".woff2").exists():
        build_direct_font_backend(
            hvar_deltas,
            FONT_PATH,
            signed_axes=False,
            base_advance=base_advances,
            codepoint_start=CODEPOINT_START,
        )
    lookup_font = ROOT / "experiments" / "hvar-token-embedding-lookup" / "embedding-lookup.woff2"
    if not lookup_font.exists():
        from build_hvar_token_embedding_lookup import build_font as build_lookup_font

        build_lookup_font(embeddings)

    logits = hidden_vectors @ embeddings.T
    quantized_logits = hidden_vectors @ quantized_embeddings.T
    winners = logits.argmax(axis=1).astype(int)
    quantized_winners = quantized_logits.argmax(axis=1).astype(int)
    floor = math.floor(float(quantized_logits.min())) - 1
    buckets = np.rint(
        np.clip((quantized_logits - floor) * SCORE_SCALE, 0, 65_535)
    ).astype(int)
    bucket_winners = buckets.argmax(axis=1)
    if not np.array_equal(quantized_winners, bucket_winners):
        raise RuntimeError("score bucket quantization changed a winner")
    if int(buckets.max()) >= 65_535:
        raise RuntimeError("score quantizer clipped at its upper bound")

    # Broader offline check across 72 genuine recurrent hidden states.
    generated_hidden, _ = generate_hidden_states(state, 24)
    dense_generated = generated_hidden @ embeddings.T
    quantized_generated = generated_hidden @ quantized_embeddings.T
    dense_generated_winners = dense_generated.argmax(axis=1)
    quantized_generated_winners = quantized_generated.argmax(axis=1)

    groups = math.ceil(len(embeddings) / GROUP_SIZE)
    (OUTPUT / "index.css").write_text(
        render_css(
            hidden_vectors,
            row_scales,
            embedding_lower,
            embedding_span,
            floor,
            groups,
        )
    )
    (OUTPUT / "index.html").write_text(render_html(row_scales, groups))
    reference = {
        "model": "calum/tinystories-gpt2-3M",
        "backend": "per-row-int8-hvar-plus-hierarchical-grid-argmax",
        "prompts": output_head.PROMPTS,
        "vocabulary": len(embeddings),
        "width": embeddings.shape[1],
        "groups": groups,
        "inputRange": INPUT_RANGE,
        "scoreFloor": floor,
        "scoreScale": SCORE_SCALE,
        "denseWinners": winners.tolist(),
        "quantizedWinners": quantized_winners.tolist(),
        "winnerBuckets": buckets[np.arange(len(winners)), quantized_winners].tolist(),
        "winnerEmbeddings": embeddings[quantized_winners].tolist(),
        "qkvBase": qkv_base.tolist(),
        "qkvRowScale": qkv_row_scale.tolist(),
        "winnerQkv": (
            embeddings[quantized_winners] @ qkv_weight + qkv_bias
        ).tolist(),
        "winnerTransportedQkv": (
            qkv_base
            + (transported_embeddings[quantized_winners] @ qkv_codes.T)
            * qkv_row_scale
        ).tolist(),
        "generatedDenseMatches": int(np.count_nonzero(
            dense_generated_winners == quantized_generated_winners
        )),
        "generatedCases": len(generated_hidden),
        "weightRmse": float(np.sqrt(np.mean(
            (quantized_embeddings - embeddings) ** 2
        ))),
        "generatedLogitRmse": float(np.sqrt(np.mean(
            (quantized_generated - dense_generated) ** 2
        ))),
        "fontBytes": FONT_PATH.with_suffix(".woff2").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
