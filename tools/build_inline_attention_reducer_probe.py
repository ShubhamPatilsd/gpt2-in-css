#!/usr/bin/env python3
"""Build a CSS-only inline-shaping attention value-reduction gate."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT, TOKENS
from build_gpt2_block_css import QUANT_BITS, layer_norm
from build_matrix_backend_prototypes import build_direct_font_backend
from build_multitoken_attention_css import HEADS, HEAD_WIDTH, softmax
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "inline-attention-reducer"
CONTEXTS = (8, 16, 32)
WIDTH = HEADS * HEAD_WIDTH
UNITS_PER_EM = 1_000
BASE_ADVANCE = 4_000
VALUE_DELTA = 2_000
SHAPING_FONT_SIZE = 1_024
OUTPUT_BASE_PX = 10_000
OUTPUT_SCALE_PX = 256
CODEPOINT_START = 0xE000


def alternate_tokens(count: int) -> tuple[int, ...]:
    source = tuple(TOKENS)
    shifted = source[1:] + source[:1]
    return shifted[:count]


def real_attention_case(
    tensors: SafeTensors,
    token_ids: tuple[int, ...],
    output_ranges: np.ndarray,
    qkv_reconstructed: np.ndarray,
    qkv_bias: np.ndarray,
) -> dict[str, object]:
    token_embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position_embeddings = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    x = np.stack(
        [token_embeddings[token] + position_embeddings[position]
         for position, token in enumerate(token_ids)]
    )
    normalized = np.stack([layer_norm(row, gamma, beta) for row in x])
    qkv_unpacked = normalized @ qkv_reconstructed.T + qkv_bias
    codes = np.rint(
        np.clip((qkv_unpacked + output_ranges) * 255 / (2 * output_ranges), 0, 255)
    )
    qkv_packed = -output_ranges + codes * (2 * output_ranges / 255)
    query = qkv_packed[:, :WIDTH].reshape(len(token_ids), HEADS, HEAD_WIDTH)
    key = qkv_unpacked[:, WIDTH:2 * WIDTH].reshape(len(token_ids), HEADS, HEAD_WIDTH)
    value = qkv_unpacked[:, 2 * WIDTH:].reshape(len(token_ids), HEADS, HEAD_WIDTH)
    target = len(token_ids) - 1
    scores = np.empty((HEADS, len(token_ids)), dtype=np.float64)
    probabilities = np.empty_like(scores)
    context = np.empty((HEADS, HEAD_WIDTH), dtype=np.float64)
    for head in range(HEADS):
        scores[head] = np.asarray([
            np.dot(query[target, head], key[source, head]) / math.sqrt(HEAD_WIDTH)
            for source in range(len(token_ids))
        ])
        probabilities[head] = softmax(scores[head])
        context[head] = probabilities[head] @ value[:, head]
    return {
        "tokens": list(token_ids),
        "scores": scores.tolist(),
        "probabilities": probabilities.tolist(),
        "values": value.tolist(),
        "expected": context.reshape(WIDTH).tolist(),
    }


def probability_css(context: int, heads: int = HEADS) -> str:
    declarations: list[str] = []
    for head in range(heads):
        scores = [f"var(--s-{head}-{source})" for source in range(context)]
        declarations.append(f"--m-{head}:max({','.join(scores)})")
        terms = [f"exp(var(--s-{head}-{source}) - var(--m-{head}))"
                 for source in range(context)]
        declarations.append(f"--l-{head}:calc({' + '.join(terms)})")
        declarations.extend(
            f"--p-{head}-{source}:calc({terms[source]} / var(--l-{head}))"
            for source in range(context)
        )
    return ";".join(declarations)


def input_style(case: dict[str, object], ranges: np.ndarray) -> str:
    scores = np.asarray(case["scores"], dtype=np.float64)
    values = np.asarray(case["values"], dtype=np.float64)
    local_width = values.shape[2]
    declarations: list[str] = []
    for head in range(scores.shape[0]):
        for source in range(scores.shape[1]):
            declarations.append(f"--s-{head}-{source}:{css_number(scores[head, source])}")
            for local in range(local_width):
                dimension = head * local_width + local
                normalized = values[source, head, local] / ranges[dimension]
                declarations.append(
                    f"--v-{head}-{source}-{local}:{css_number(normalized)}"
                )
    return ";".join(declarations)


def output_rule(variant: str, context: int, dimension: int, value_range: float) -> str:
    head, local = divmod(dimension, HEAD_WIDTH)
    if variant == "control":
        terms = [
            f"var(--p-{head}-{source})*var(--v-{head}-{source}-{local})"
            for source in range(context)
        ]
        width = (
            f"calc({OUTPUT_BASE_PX}px + {OUTPUT_SCALE_PX * value_range:.12g}px"
            f" * ({' + '.join(terms)}))"
        )
    else:
        factor = OUTPUT_SCALE_PX * value_range / VALUE_DELTA
        width = (
            "calc-size(max-content,calc("
            f"{OUTPUT_BASE_PX}px + (size*{UNITS_PER_EM}/{SHAPING_FONT_SIZE}"
            f" - {BASE_ADVANCE}px)*{factor:.12g}))"
        )
    return f".d-{dimension}{{width:{width}}}"


def span_markup(variant: str, head: int, local: int, source: int) -> str:
    probability = f"var(--p-{head}-{source})"
    if variant == "font-size":
        scale = f"font-size:calc({probability}*{SHAPING_FONT_SIZE}px)"
    elif variant == "zoom":
        scale = f"font-size:{SHAPING_FONT_SIZE}px;zoom:{probability}"
    else:
        raise ValueError(variant)
    return (
        f'<span style="{scale};font-variation-settings:&quot;X{local:03d}&quot; '
        f'var(--v-{head}-{source}-{local})">&#x{CODEPOINT_START + local:X};</span>'
    )


def page(variant: str, context: int, case: dict[str, object], ranges: np.ndarray) -> str:
    rules = "".join(
        output_rule(variant, context, dimension, float(ranges[dimension]))
        for dimension in range(WIDTH)
    )
    outputs: list[str] = []
    for dimension in range(WIDTH):
        head, local = divmod(dimension, HEAD_WIDTH)
        if variant == "control":
            content = ""
        else:
            content = "".join(
                span_markup(variant, head, local, source)
                for source in range(context)
            )
        outputs.append(
            f'<i class="output d-{dimension}" data-dimension="{dimension}">{content}</i>'
        )
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inline attention reducer: {variant}, context {context}</title>
<style>
@font-face{{font-family:InlineValue;src:url("inline-value.woff2") format("woff2")}}
html,body{{margin:0}}
.bank{{position:fixed;left:-20000px;top:0;{probability_css(context)}}}
.output{{display:block;height:1px;overflow:hidden;white-space:pre;line-height:1px;
font-family:InlineValue;font-kerning:none;font-style:normal}}
.output span{{font-family:InlineValue;font-kerning:none;font-style:normal;line-height:1px}}
{rules}
</style>
<main id="fixture" class="bank" data-variant="{variant}" data-context="{context}"
 style="{input_style(case, ranges)}">{''.join(outputs)}</main>
'''


def primitive_page(reference: dict[str, object]) -> str:
    context = 4
    dimensions = 4
    ranges = np.asarray(reference["ranges"], dtype=np.float64)
    case = reference["cases"][0]
    outputs: list[str] = []
    for variant in ("control", "font-size", "zoom"):
        for local in range(dimensions):
            dimension = local
            content = "" if variant == "control" else "".join(
                span_markup(variant, 0, local, source) for source in range(context)
            )
            outputs.append(
                f'<i class="output {variant} d-{dimension}" data-variant="{variant}" '
                f'data-dimension="{dimension}">{content}</i>'
            )
    # Scope otherwise-colliding dimension rules to the bank variant.
    scoped_rules = []
    for variant in ("control", "font-size", "zoom"):
        for local in range(dimensions):
            scoped_rules.append(
                f'.output.{variant}.d-{local}' + "{" + output_rule(
                    variant, context, local, float(ranges[local])
                ).split("{", 1)[1]
            )
    return f'''<!doctype html><meta charset="utf-8">
<title>Inline attention reducer primitive</title>
<style>
@font-face{{font-family:InlineValue;src:url("inline-value.woff2") format("woff2")}}
html,body{{margin:0}}.bank{{position:fixed;left:-20000px;top:0;{probability_css(context, heads=1)}}}
.output{{display:block;height:1px;overflow:hidden;white-space:pre;line-height:1px;
font-family:InlineValue;font-kerning:none;font-style:normal}}
.output span{{font-family:InlineValue;font-kerning:none;font-style:normal;line-height:1px}}
{''.join(scoped_rules)}
</style>
<main id="fixture" class="bank" style="{input_style(case, ranges)}">{''.join(outputs)}</main>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights = np.eye(HEAD_WIDTH, dtype=np.int16) * VALUE_DELTA
    build_direct_font_backend(
        weights,
        OUT / "inline-value.ttf",
        signed_axes=True,
        base_advance=BASE_ADVANCE,
        codepoint_start=CODEPOINT_START,
    )

    precision = json.loads(PRECISION_REPORT.read_text())
    output_ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    tensors = SafeTensors(MODEL_PATH)
    qkv_weight = np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    ).T
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    qkv_reconstructed = quantize_float_rows(qkv_weight, bits=QUANT_BITS).reconstructed

    reference: dict[str, object] = {
        "model": str(MODEL_PATH.relative_to(ROOT)),
        "contexts": {},
        "constants": {
            "heads": HEADS,
            "headWidth": HEAD_WIDTH,
            "unitsPerEm": UNITS_PER_EM,
            "baseAdvance": BASE_ADVANCE,
            "valueDelta": VALUE_DELTA,
            "shapingFontSize": SHAPING_FONT_SIZE,
            "outputBasePx": OUTPUT_BASE_PX,
            "outputScalePx": OUTPUT_SCALE_PX,
        },
    }
    for context in CONTEXTS:
        cases = [
            real_attention_case(
                tensors, tuple(TOKENS[:context]), output_ranges,
                qkv_reconstructed, qkv_bias,
            ),
            real_attention_case(
                tensors, alternate_tokens(context), output_ranges,
                qkv_reconstructed, qkv_bias,
            ),
        ]
        values = np.concatenate(
            [np.asarray(case["values"], dtype=np.float64).reshape(-1, WIDTH)
             for case in cases],
            axis=0,
        )
        ranges = np.maximum(np.max(np.abs(values), axis=0) * 1.05, 0.25)
        for case in cases:
            value = np.asarray(case["values"], dtype=np.float64)
            case["normalizedValues"] = (
                value / ranges.reshape(1, HEADS, HEAD_WIDTH)
            ).tolist()
        context_reference = {
            "ranges": ranges.tolist(),
            "cases": cases,
        }
        reference["contexts"][str(context)] = context_reference
        for variant in ("control", "font-size", "zoom"):
            (OUT / f"{variant}-{context}.html").write_text(
                page(variant, context, cases[0], ranges)
            )

    primitive_source = reference["contexts"]["8"]
    primitive_cases = []
    for source_case in primitive_source["cases"]:
        primitive_cases.append({
            "tokens": source_case["tokens"][:4],
            "scores": [source_case["scores"][0][:4]],
            "probabilities": [softmax(np.asarray(source_case["scores"][0][:4])).tolist()],
            "values": [[source_case["values"][source][0][:4]]
                       for source in range(4)],
        })
    primitive_ranges = np.asarray(primitive_source["ranges"][:4], dtype=np.float64)
    for primitive_case in primitive_cases:
        values = np.asarray(primitive_case["values"], dtype=np.float64).reshape(4, 4)
        probabilities = np.asarray(primitive_case["probabilities"][0], dtype=np.float64)
        primitive_case["expected"] = (probabilities @ values).tolist()
        primitive_case["normalizedValues"] = (
            values / primitive_ranges.reshape(1, 4)
        ).reshape(4, 1, 4).tolist()
    primitive = {
        "ranges": primitive_ranges.tolist(),
        "cases": primitive_cases,
    }
    reference["primitive"] = primitive
    (OUT / "primitive.html").write_text(primitive_page(primitive))
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUT),
        "contexts": list(CONTEXTS),
        "fontBytes": (OUT / "inline-value.woff2").stat().st_size,
        "pages": len(list(OUT.glob("*.html"))),
    }, indent=2))


if __name__ == "__main__":
    main()
