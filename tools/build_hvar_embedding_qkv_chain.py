#!/usr/bin/env python3
"""Build token lookup -> packed CSS vector -> real TinyStories QKV probes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import build_output_head_benchmark as output_head
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "hvar-embedding-qkv-chain"
LOOKUP_BASE = 20_000
LOOKUP_SCALE = 4_096
QKV_BASE = 20_000
FONT_SIZE = 1_000
WIDTH = 64
QKV_WIDTH = 192
GROUP_SIZE = 4
RADIX = 64
TOKENS = [11, 373, 0, 1, 255, 256, 612, 257, 15_899, 50_256]


def css_number(value: float) -> str:
    return output_head.css_number(float(value))


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def settings(values: np.ndarray) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {css_number(value)}'
        for index, value in enumerate(values)
    )


def source_code(dimension: int, lower: float, span: float, levels: int) -> str:
    raw = (
        f"((anchor-size(--e{dimension:02d} width) - {LOOKUP_BASE}px) / "
        f"{LOOKUP_SCALE} - ({css_number(lower)}px))"
    )
    return (
        f"round(nearest,clamp(0px,{raw} * {levels} / "
        f"{css_number(span)},{levels}px),1px)"
    )


def packed_digit(axis: str, place: int) -> str:
    size = "100cqi" if axis == "i" else "100cqb"
    power = RADIX ** place
    if place == 0:
        return f"mod(round(nearest,{size}/1px,1),{RADIX})"
    if place == GROUP_SIZE - 1:
        return f"round(down,{size}/1px/{power},1)"
    return f"mod(round(down,{size}/1px/{power},1),{RADIX})"


def render_page(
    bits: int,
    lower: np.ndarray,
    span: np.ndarray,
    qkv_codes: np.ndarray,
) -> str:
    levels = (1 << bits) - 1
    zero = settings(np.zeros(WIDTH))
    keyframes = []
    for dimension in range(WIDTH):
        endpoint = np.zeros(WIDTH)
        endpoint[dimension] = 1
        keyframes.append(
            f"@keyframes c{dimension}{{from{{font-variation-settings:var(--zero)}}"
            f"to{{font-variation-settings:{settings(endpoint)}}}}}"
        )

    pack_rules = []
    contribution_rules = []
    for group in range(WIDTH // GROUP_SIZE):
        start = group * GROUP_SIZE
        codes = [
            source_code(dimension, lower[dimension], span[dimension], levels)
            for dimension in range(start, start + GROUP_SIZE)
        ]
        declarations = ";".join(
            f"--code{place}:{code}" for place, code in enumerate(codes)
        )
        if bits == 6:
            inline_terms = [
                f"{RADIX ** place} * var(--code{place})"
                for place in range(GROUP_SIZE)
            ]
            dimensions = f"width:calc({' + '.join(inline_terms)});height:1px"
            progress = [
                f"{packed_digit('i', place)}/{levels}"
                for place in range(GROUP_SIZE)
            ]
        else:
            low_terms = [
                f"{RADIX ** place} * mod(var(--code{place})/1px,{RADIX}) * 1px"
                for place in range(GROUP_SIZE)
            ]
            high_terms = [
                f"{RADIX ** place} * round(down,var(--code{place})/1px/{RADIX},1) * 1px"
                for place in range(GROUP_SIZE)
            ]
            dimensions = (
                f"width:calc({' + '.join(low_terms)});"
                f"height:calc({' + '.join(high_terms)})"
            )
            progress = [
                f"({packed_digit('i', place)} + {RADIX} * "
                f"{packed_digit('b', place)})/{levels}"
                for place in range(GROUP_SIZE)
            ]
        pack_rules.append(f".pack-{group}{{{declarations};{dimensions}}}")
        contribution_rules.append(
            f".contrib-{group}{{animation-name:"
            + ",".join(f"c{start + place}" for place in range(GROUP_SIZE))
            + ";animation-delay:"
            + ",".join(f"calc(-1s * {value})" for value in progress)
            + "}"
        )

    qkv_metrics = "".join(
        f'<i class="qkv-metric" data-dimension="{dimension}">'
        f'&#x{0xF0000 + dimension:X};</i>'
        for dimension in range(QKV_WIDTH)
    )
    chain = f'<output id="result" class="contribution contrib-15">{qkv_metrics}</output>'
    for group in reversed(range(WIDTH // GROUP_SIZE)):
        start = group * GROUP_SIZE
        sources = "".join(
            f'<i class="embedding-source" style="anchor-name:--e{dimension:02d}">'
            f'&#x{0xE000 + dimension:X};</i>'
            for dimension in range(start, start + GROUP_SIZE)
        )
        classes = f"packed-carrier pack-{group}"
        if group:
            classes += f" contribution contrib-{group - 1}"
        chain = (
            sources
            + f'<div class="{classes}" style="position-anchor:--e{start:02d}">'
            + chain
            + "</div>"
        )

    controls = "".join(
        f'<input type="radio" name="token" id="t{index}"'
        f'{" checked" if index == 0 else ""}>'
        for index in range(len(TOKENS))
    )
    selectors = "".join(
        f"body:has(#t{index}:checked) #scope{{--group:{token // 256};"
        f"--local:{token % 256}}}"
        for index, token in enumerate(TOKENS)
    )
    container_type = "size" if bits == 12 else "inline-size"
    return f'''<!doctype html><meta charset="utf-8">
<title>HVAR embedding to QKV chain ({bits}-bit)</title>
<style>
@font-face{{font-family:EmbeddingLookup;src:url("../hvar-token-embedding-lookup/embedding-lookup.woff2") format("woff2")}}
@font-face{{font-family:QKV;src:url("qkv.woff2") format("woff2")}}
{selectors}
{''.join(keyframes)}
html,body{{margin:0;overflow:clip}}
#scope{{--group:0;--local:0;--zero:{zero};position:relative}}
.embedding-source{{position:absolute;display:inline-block;width:max-content;height:1px;
overflow:hidden;white-space:pre;font-family:EmbeddingLookup;font-size:{FONT_SIZE}px;
font-variation-settings:"GRUP" var(--group),"LOCL" var(--local);font-kerning:none;font-style:normal}}
.packed-carrier{{position:absolute;container-type:{container_type}}}
.pack-0{{font-family:serif;font-variation-settings:var(--zero)}}
.contribution{{position:absolute;animation-duration:1s;animation-play-state:paused;
animation-timing-function:linear;animation-fill-mode:both;animation-composition:add}}
#result{{font-family:QKV;font-size:{FONT_SIZE}px;line-height:1;font-kerning:none;
white-space:pre;height:1px}}
.qkv-metric{{display:inline-block;height:1px;overflow:hidden;font-style:normal}}
{''.join(pack_rules)}
{''.join(contribution_rules)}
</style>
{controls}<main id="scope">{chain}</main>
'''


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state = output_head.load_torch_zip(output_head.download_checkpoint())
    embeddings = state["transformer.wte.weight"].astype(np.float64)
    weight = state["transformer.h.0.attn.c_attn.weight"].astype(np.float64)
    bias = state["transformer.h.0.attn.c_attn.bias"].astype(np.float64)
    if embeddings.shape[1] != WIDTH or weight.shape != (WIDTH, QKV_WIDTH):
        raise ValueError("unexpected TinyStories model dimensions")

    lower = np.min(embeddings, axis=0)
    upper = np.max(embeddings, axis=0)
    span = upper - lower
    coefficient = weight.T * span[None, :]
    row_scale = np.max(np.abs(coefficient), axis=1) / 127
    row_scale[row_scale == 0] = 1
    qkv_codes = np.rint(coefficient / row_scale[:, None]).astype(np.int16)
    build_direct_font_backend(
        qkv_codes,
        OUTPUT / "qkv.ttf",
        base_advance=QKV_BASE,
        codepoint_start=0xF0000,
        axis_tags=[axis_tag(index) for index in range(WIDTH)],
    )
    base = lower @ weight + bias
    dense = embeddings[TOKENS] @ weight + bias

    variants = {}
    lookup_quantized = np.rint(embeddings[TOKENS] * LOOKUP_SCALE) / LOOKUP_SCALE
    for bits in (6, 12):
        levels = (1 << bits) - 1
        normalized = np.clip((lookup_quantized - lower) / span, 0, 1)
        transported = np.rint(normalized * levels) / levels
        reconstructed = base + (transported @ qkv_codes.T) * row_scale
        name = f"b{bits}"
        page = render_page(bits, lower, span, qkv_codes)
        (OUTPUT / f"{name}.html").write_text(page)
        variants[name] = {
            "bits": bits,
            "levels": levels,
            "expected": reconstructed.tolist(),
            "transportRmseVsDense": float(np.sqrt(np.mean((reconstructed - dense) ** 2))),
            "htmlBytes": len(page.encode()),
        }

    reference = {
        "model": "calum/tinystories-gpt2-3M",
        "tokens": TOKENS,
        "width": WIDTH,
        "qkvWidth": QKV_WIDTH,
        "lookupBase": LOOKUP_BASE,
        "lookupScale": LOOKUP_SCALE,
        "qkvBase": QKV_BASE,
        "rowScale": row_scale.tolist(),
        "base": base.tolist(),
        "dense": dense.tolist(),
        "variants": variants,
        "fontBytes": (OUTPUT / "qkv.woff2").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference) + "\n")
    print(json.dumps({
        "fontBytes": reference["fontBytes"],
        "variants": {
            name: {
                "htmlBytes": variant["htmlBytes"],
                "transportRmseVsDense": variant["transportRmseVsDense"],
            }
            for name, variant in variants.items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
