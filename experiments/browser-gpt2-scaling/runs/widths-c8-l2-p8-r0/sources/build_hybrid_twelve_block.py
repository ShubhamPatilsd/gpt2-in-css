#!/usr/bin/env python3
"""Cached-prefix GPT-2 decode: HVAR matvecs + typed CSS attention, no JS.

All twelve current-token residuals stay in one CSS graph. Python prepares the
fixed prefix KV cache and the test oracles, not runtime intermediate values.
Reusing registered scratch names bounds the inherited state; 384-output
consumers keep the HTML tree below Chromium's parser nesting limit.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import build_gpt2_block_css as b
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_pretrained_gpt2 import css_number as num
from build_signed_hvar_chain import quantize_float_rows
from native_stage_retirement import retire_stage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/hybrid-12block-profile"
ASSET_OUT = OUT / "fonts"
W = 768
STAGES = ("ln1", "qkv", "mix", "attn", "ln2", "fc", "proj")


def names(stem, count):
    return [f"--{stem}-{i:03d}" for i in range(count)]


def declarations(stem, values):
    return ";".join(f"{p}:{num(v)}" for p, v in zip(names(stem, len(values)), values))


def regs(properties):
    return "".join(
        f'@property {p}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for p in properties
    )


def wrapper(class_name, rule, child="{child}"):
    return f'<div class="{class_name}">{child}</div>', f".{class_name}{{{rule}}}"


def probe(identifier, stem, count):
    checksum = " + ".join(f"var(--{stem}-{i:03d}) * {i % 11 + 1}" for i in range(count))
    return (
        f'<i class="readback" id="{identifier}" style="anchor-name:--{identifier};width:calc(1048576px + '
        f'({checksum}) * 16px);height:calc(32768px + var(--{stem}-{count - 1:03d}) * 16px)"></i>'
        f'<i class="readback" style="anchor-name:--{identifier}-epoch;width:calc(var(--epoch) * 64px);height:1px"></i>'
    )


def font_group(layer, kind, quantized):
    # Existing MLP assets encode the same row-quantized weights; their input
    # calibration is CSS, not embedded in the fonts.
    candidates = []
    if layer == 0:
        candidates = [
            (
                ROOT / "experiments/gpt2-block-css",
                {
                    "qkv": "qkv-rowbase",
                    "attn": "attn-out-rowbase",
                    "fc": "fc-rowbase",
                    "proj": "mlp-proj-rowbase",
                }[kind],
            )
        ]
    elif kind in ("fc", "proj"):
        candidates = [
            (
                ROOT / f"experiments/gpt2-flat-12block-chain/layer{layer:02d}",
                f"b{layer}-{'fc' if kind == 'fc' else 'mlp-proj'}-rowbase",
            )
        ]
    candidates.append((ASSET_OUT, f"b{layer}-{kind}"))
    for directory, stem in candidates:
        count = math.ceil(quantized.codes.shape[1] / 256)
        exists = all((directory / f"{stem}-s{i}.woff2").exists() for i in range(count))
        if exists or directory == ASSET_OUT:
            directory.mkdir(parents=True, exist_ok=True)
            previous = b.OUT
            b.OUT = directory
            try:
                group = b.build_font_group(
                    stem, quantized.codes, rebuild=not exists, row_specific_bases=True
                )
            finally:
                b.OUT = previous
            return directory, group
    raise AssertionError("no font destination")


def matvec(
    layer,
    kind,
    quantized,
    bias,
    source,
    target,
    activation_range,
    chunk,
    compact=False,
    gated=False,
    easing_bounds=None,
    dynamic_range=False,
    global_axes=False,
):
    directory, group = font_group(layer, kind, quantized)
    if global_axes:
        from browser_gpt2_projection_layout import global_projection_fonts

        directory, group = global_projection_fonts(directory, group)
    count = len(bias)
    stem = f"b{layer}-{kind}"
    family = stem.replace("-", "")
    css = b.font_faces(stem, group).replace('url("', f'url("{directory.as_uri()}/')
    if dynamic_range:
        if easing_bounds is not None:
            raise ValueError("Dynamic input range currently requires exact GELU")
        css += regs([f"--range-{kind}"])
        css += f".{stem}{{--range-{kind}:calc(max(.000001,{','.join(f'abs(var({p}))' for p in source)}) * 1.001)}}"

    def settings(first):
        if global_axes:
            divisor = f"var(--range-{kind})" if dynamic_range else num(activation_range)
            return ",".join(f'"{b.global_axis_tag(i)}" calc(var({name}) / {divisor})' for i, name in enumerate(source))
        fixed = b.pack_font_settings(source, 1 if dynamic_range else activation_range, first)
        return fixed.replace(" / 1)", f" / var(--range-{kind}))") if dynamic_range else fixed
    bases = np.sum(np.stack(group.row_bases), axis=0)
    viewport = 2 ** math.ceil(
        math.log2(max(1024, max(bases) * b.FONT_SIZE / b.UNITS_PER_EM * 1.5))
    )
    timelines = [f"--{stem}-t{i}" for i in range(count)]
    marker = f"--{stem}-generation"
    progress = names(f"{kind}p", count)
    keys = [f"{kind}k{i}" for i in range(count)]
    packs = 1 if global_axes else math.ceil(len(group.names) / 3)
    ease_scale = ease_offset = 0
    if easing_bounds is not None:
        low, high = easing_bounds
        extent = max(abs(low), abs(high))
        ease_scale = viewport / (4 * extent)
        ease_offset = viewport / 2
        z = np.linspace(high, low, 1025)
        hidden = b.gelu_new(z)
        dense = b.gelu_new(np.linspace(low, high, 8193))
        out_low, out_high = float(np.min(dense)), float(np.max(dense))
        stops = [f"{num((hidden[0] - out_low) / (out_high - out_low))} 0%"]
        stops += [
            f"{num((v - out_low) / (out_high - out_low))} {num(100 * viewport / (viewport + ease_offset + ease_scale * x))}%"
            for x, v in zip(z, hidden)
        ]
        css += f".{stem}{{--fc-ease:linear({','.join(stops)});--fc-low:{num(out_low)};--fc-high:{num(out_high)}}}"
    for pack in range(packs):
        first = pack * 3
        families = ",".join(
            f"{family}S{s}" for s in range(first, len(group.names) if global_axes else min(first + 3, len(group.names)))
        )
        selector = f".{stem}" if compact and packs == 1 else f".{stem}-pack{pack}"
        css += f"{selector}{{font-family:{families};font-variation-settings:{settings(first)}}}"
    metrics = []
    for i in range(count):
        content = ""
        for pack in range(packs):
            chars = "".join(
                f"&#x{group.codepoint_starts[s] + i:X};"
                for s in range(pack * 3, len(group.names) if global_axes else min(pack * 3 + 3, len(group.names)))
            )
            content += (
                chars
                if compact and packs == 1
                else f'<i class="{stem}-pack{pack}">{chars}</i>'
            )
        metric_style = f"view-timeline:{timelines[i]} inline"
        if easing_bounds is not None:
            factor = activation_range * quantized.scales[i]
            multiplier = ease_scale * factor * b.UNITS_PER_EM / b.FONT_SIZE
            shift = ease_offset + ease_scale * bias[i] - ease_scale * factor * bases[i]
            metric_style += f";width:calc-size(max-content,size * {num(multiplier)} + {num(shift)}px)"
        metrics.append(f'<i class="metric" style="{metric_style}">{content}</i>')
    css += (
        f".{stem}{{timeline-scope:{','.join(timelines + ([marker] if gated else []))};font:normal {b.FONT_SIZE}px {family}S0;"
        f"font-kerning:none}}.{stem}>.scroller{{width:{viewport}px}}.{stem}>.scroller>.track{{width:{3 * viewport}px}}"
    )
    if compact and packs == 1:
        # The shorthand above resets family; restore the entire shard fallback.
        css += (
            f".{stem}{{font-family:{','.join(f'{family}S{s}' for s in range(len(group.names)))};"
            f"font-variation-settings:{settings(0)}}}"
        )
    inner = "{child}"
    if gated:
        # A generation tag travels through the same layout pass as the glyph
        # widths. New input closes downstream gates before stale font widths
        # can launch the next matvec. No external per-stage scheduler is used.
        metrics.append(
            f'<i class="metric" style="width:calc({viewport // 4}px + var(--epoch) * 1024px);view-timeline:{marker} inline"></i>'
        )
        css += (
            f".{stem}-receipt{{container-name:{stem}-receipt;animation:{kind}stamp 1s linear both;"
            f"animation-timeline:{marker};animation-range:cover;--gate-{kind}:calc(1 - min(1,abs("
            f"round(nearest,({viewport} / var(--stamp-{kind}) - {viewport} - {viewport // 4}) / 1024,1) - var(--epoch))))}}"
            f".{stem}-gate{{display:none}}@container {stem}-receipt style(--gate-{kind}:1){{.{stem}-gate{{display:block}}}}"
        )
        inner = f'<div class="{stem}-receipt"><div class="{stem}-gate">{{child}}</div></div>'
    for start in reversed(range(0, count, chunk)):
        stop = min(count, start + chunk)
        result = []
        for i in range(start, stop):
            if easing_bounds is not None:
                continue
            raw = f"(({viewport} / var({progress[i]}) - {viewport}) * {b.UNITS_PER_EM} / {b.FONT_SIZE} - {int(bases[i])})"
            gain = f"{num(quantized.scales[i])} * var(--range-{kind})" if dynamic_range else num(activation_range * quantized.scales[i])
            value = f"calc({raw} * {gain} + ({num(bias[i])}))"
            if kind == "fc":
                value = f"--gelu({value})"
            elif kind == "attn":
                value = f"calc(var(--x-{i:03d}) + {value})"
            elif kind == "proj":
                value = f"calc(var(--r-{i:03d}) + {value})"
            result.append(f"{target[i]}:{value}")
        consumer = f"{stem}-c{start // chunk}"
        timing = "var(--fc-ease)" if easing_bounds is not None else "linear"
        css += (
            f".{consumer}{{animation-name:{','.join(keys[start:stop])};animation-duration:1s;"
            f"animation-timing-function:{timing};animation-fill-mode:both;"
            f"animation-timeline:{','.join(timelines[start:stop])};animation-range:cover;{';'.join(result)}}}"
        )
        inner = f'<div class="{consumer}">{inner}</div>'
    html = f'<div class="{stem}"><div class="scroller"><div class="track">{"".join(metrics)}</div></div>{inner}</div>'
    return html, css


def attention(layer, keys, values):
    length = len(keys) + 1
    rules = []
    for head in range(12):
        offset = head * 64
        scores = []
        for token in range(length):
            terms = []
            for d in range(64):
                key = (
                    num(keys[token, offset + d])
                    if token < length - 1
                    else f"var(--qkv-{W + offset + d:03d})"
                )
                terms.append(f"var(--qkv-{offset + d:03d}) * ({key})")
            name = f"--s-{head}-{token}"
            rules.append(f"{name}:calc(({' + '.join(terms)}) / 8)")
            scores.append(f"var({name})")
        rules.append(f"--max-{head}:max({','.join(scores)})")
        for token in range(length):
            rules.append(
                f"--e-{head}-{token}:exp(calc(var(--s-{head}-{token}) - var(--max-{head})))"
            )
        rules.append(
            f"--den-{head}:calc({' + '.join(f'var(--e-{head}-{t})' for t in range(length))})"
        )
        for token in range(length):
            rules.append(
                f"--p-{head}-{token}:calc(var(--e-{head}-{token}) / var(--den-{head}))"
            )
        for d in range(64):
            i = offset + d
            terms = [
                f"var(--p-{head}-{t}) * ({num(values[t, i])})"
                for t in range(length - 1)
            ]
            terms.append(f"var(--p-{head}-{length - 1}) * var(--qkv-{2 * W + i:03d})")
            rules.append(f"--ctx-{i:03d}:calc({' + '.join(terms)})")
    return wrapper(f"b{layer}-mix", ";".join(rules))


def bridge(layer, chunk):
    """Carry only the residual and generation between sibling block subtrees."""
    stem = f"b{layer}-bridge"
    viewport, offset, scale = 524288, 262144, 128
    timelines = [f"--{stem}-t{i}" for i in range(W)]
    marker = f"--{stem}-stamp"
    metrics = "".join(
        f'<i class="metric" style="width:calc({offset}px + var(--out-{i:03d}) * {scale}px);view-timeline:{timelines[i]} inline"></i>'
        for i in range(W)
    )
    metrics += f'<i class="metric" style="width:calc({offset}px + var(--epoch) * 1024px);view-timeline:{marker} inline"></i>'
    source = (
        f'<div class="scroller {stem}-source"><div class="track">{metrics}</div></div>'
    )
    css = (
        f"html{{timeline-scope:{','.join(timelines + [marker])}}}"
        f".{stem}-source{{width:{viewport}px}}.{stem}-source>.track{{width:{viewport * 3}px}}"
        f".{stem}-receipt{{container-name:{stem};animation:bridgestamp 1s linear both;animation-timeline:{marker};"
        f"--bridge-ready:calc(1 - min(1,abs(round(nearest,({viewport} / var(--bridge-stamp) - {viewport} - {offset}) / 1024,1) - var(--epoch))))}}"
        f".{stem}-gate{{display:none}}@container {stem} style(--bridge-ready:1){{.{stem}-gate{{display:block}}}}"
    )
    receiver = (
        f'<div class="{stem}-receipt"><div class="{stem}-gate">{{child}}</div></div>'
    )
    for start in reversed(range(0, W, chunk)):
        stop = min(start + chunk, W)
        values = ";".join(
            f"--x-{i:03d}:calc(({viewport} / var(--bridge-p-{i:03d}) - {viewport} - {offset}) / {scale})"
            for i in range(start, stop)
        )
        cls = f"{stem}-c{start // chunk}"
        css += (
            f".{cls}{{animation-name:{','.join(f'bridgek{i}' for i in range(start, stop))};animation-duration:1s;"
            f"animation-timing-function:linear;animation-fill-mode:both;animation-timeline:{','.join(timelines[start:stop])};{values}}}"
        )
        receiver = f'<div class="{cls}">{receiver}</div>'
    return source, receiver, css, timelines + [marker]


def document(css, html, observer=None):
    if observer:
        html += (
            f'<i class="readback" id="measurement" style="width:anchor-size(--{observer}-epoch width,0px);'
            f'height:anchor-size(--{observer} width,1px)"></i>'
        )
    return (
        '<!doctype html><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        "<title>12-block cached-prefix hybrid</title><style>"
        + css
        + "</style><body>"
        + html
        + "</body>"
    )


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--context", type=int, default=16)
    parser.add_argument("--chunk", type=int, default=384)
    parser.add_argument("--reset-scratch", action="store_true")
    parser.add_argument("--contain", action="store_true")
    parser.add_argument("--compact-metrics", action="store_true")
    parser.add_argument("--gated", action="store_true")
    parser.add_argument("--sibling-blocks", action="store_true")
    parser.add_argument("--content-gates", action="store_true")
    parser.add_argument("--fc-easing", action="store_true")
    parser.add_argument("--retire-stages", action="store_true")
    parser.add_argument("--retire-blocks", action="store_true")
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if not 1 <= args.blocks <= 12 or not 2 <= args.context <= 1024 or args.chunk < 1:
        parser.error(
            "require 1..12 blocks, 2..1024 context positions, and positive chunk size"
        )
    if args.sibling_blocks and not args.gated:
        parser.error("--sibling-blocks requires --gated generation propagation")
    if (args.retire_stages or args.retire_blocks) and (not args.gated or args.epochs < 1):
        parser.error("retirement requires --gated and positive --epochs")
    if args.retire_stages and args.retire_blocks:
        parser.error("select either stage or block retirement")
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    # Fixed, explicit token IDs; not a claim about a particular prompt string.
    tokens = (
        [
            15496,
            995,
            11,
            314,
            1101,
            257,
            3303,
            2746,
            13,
            770,
            318,
            257,
            1332,
            286,
            262,
            995,
        ]
        * 64
    )[: args.context]
    embedding = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    positional = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    prefix = embedding[tokens[:-1]] + positional[: args.context - 1]
    # Distinct real token embeddings: no alternating-class cache benchmark.
    current_ids = [tokens[-1], 15496, 13, 262]
    current = np.stack(
        [embedding[t] + positional[args.context - 1] for t in current_ids]
    )
    reference = {
        "blocks": args.blocks,
        "context": args.context,
        "chunk": args.chunk,
        "prefixTokenIds": tokens[:-1],
        "currentTokenIds": current_ids,
        "inputs": current.tolist(),
        "layers": [],
        "runtimeJavaScript": False,
        "resetScratch": args.reset_scratch,
        "contain": args.contain,
        "compactMetrics": args.compact_metrics,
        "generationGates": args.gated,
        "siblingBlocks": args.sibling_blocks,
        "contentGates": args.content_gates,
        "fcEasingStops": 1025 if args.fc_easing else None,
        "externalIntermediateTransfers": 0,
        "retireStages": args.retire_stages,
        "retireBlocks": args.retire_blocks,
        "retirementEpochs": args.epochs if args.retire_stages else None,
        "excludes": [
            "prefix prefill",
            "final LayerNorm",
            "vocabulary head",
            "KV append/token feedback",
        ],
    }
    props = []
    for stem, count in (
        ("x", W),
        ("n1", W),
        ("qkv", 3 * W),
        ("ctx", W),
        ("r", W),
        ("n2", W),
        ("hidden", 4 * W),
        ("out", W),
    ):
        props += names(stem, count)
    props += ["--mean1", "--var1", "--mean2", "--var2"]
    for h in range(12):
        props += [f"--max-{h}", f"--den-{h}"]
        props += [
            f"--{p}-{h}-{t}" for p in ("s", "e", "p") for t in range(args.context)
        ]
    shared = regs(props)
    shared += regs(["--epoch"])
    if args.sibling_blocks:
        shared += regs(names("bridge-p", W) + ["--bridge-stamp", "--bridge-ready"])
        shared += "".join(
            f"@keyframes bridgek{i}{{from{{--bridge-p-{i:03d}:0}}to{{--bridge-p-{i:03d}:1}}}}"
            for i in range(W)
        )
        shared += "@keyframes bridgestamp{from{--bridge-stamp:0}to{--bridge-stamp:1}}"
    for kind, count in (("qkv", 3 * W), ("attn", W), ("fc", 4 * W), ("proj", W)):
        progress_props = names(kind + "p", count)
        if args.fc_easing and kind == "fc":
            shared += "".join(
                f"@keyframes fck{i}{{from{{--hidden-{i:03d}:var(--fc-low)}}to{{--hidden-{i:03d}:var(--fc-high)}}}}"
                for i in range(count)
            )
        else:
            shared += regs(progress_props)
            props += progress_props
            shared += "".join(
                f"@keyframes {kind}k{i}{{from{{--{kind}p-{i:03d}:0}}to{{--{kind}p-{i:03d}:1}}}}"
                for i in range(count)
            )
        if args.gated:
            shared += regs([f"--stamp-{kind}", f"--gate-{kind}"])
            shared += f"@keyframes {kind}stamp{{from{{--stamp-{kind}:0}}to{{--stamp-{kind}:1}}}}"
            props += [f"--stamp-{kind}", f"--gate-{kind}"]
    shared += (
        "html,body{margin:0;font:12px monospace}.scroller{position:fixed;left:0;top:-60000px;"
        "height:1px;overflow-x:scroll;overflow-y:hidden}.track{position:relative;height:1px}"
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;"
        "overflow:hidden;white-space:pre}.metric i{font-style:normal}"
        ".readback{position:fixed;left:0;top:0;display:block;visibility:hidden;contain:strict}"
        "@function --gelu(--z <number>) returns <number>{--t:clamp(-20,calc(.7978845608028654 * "
        "(var(--z) + .044715 * pow(var(--z),3))),20);result:calc(.5 * var(--z) * "
        "(1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
    )
    if args.contain:
        shared += ".scroller{contain:strict;visibility:hidden}"
    if args.reset_scratch:
        shared += (
            ".reset{"
            + ";".join(f"{p}:initial" for p in props if not p.startswith("--x-"))
            + ";font:12px monospace;font-variation-settings:normal}"
        )
    all_css, block_html = [], []
    bridges = []
    for layer in range(args.blocks):
        data = b.model_data(layer)
        qweights = [
            np.asarray(
                tensors.tensor(f"h.{layer}.attn.c_attn.weight"), dtype=np.float64
            ).T,
            data["attn_proj_weight"],
            data["fc_weight"],
            data["mlp_proj_weight"],
        ]
        biases = [
            np.asarray(tensors.tensor(f"h.{layer}.attn.c_attn.bias"), dtype=np.float64),
            data["attn_proj_bias"],
            data["fc_bias"],
            data["mlp_proj_bias"],
        ]
        quantized = [
            quantize_float_rows(weight, bits=b.QUANT_BITS) for weight in qweights
        ]

        def norm(rows, which):
            return np.stack(
                [
                    b.layer_norm(row, data[f"ln{which}_gamma"], data[f"ln{which}_beta"])
                    for row in rows
                ]
            )

        pn = norm(prefix, 1)
        pqkv = pn @ quantized[0].reconstructed.T + biases[0]
        pk, pv = pqkv[:, W : 2 * W], pqkv[:, 2 * W :]

        def mix(qkv, cached_k, cached_v):
            k = np.concatenate([cached_k, qkv[None, W : 2 * W]]).reshape(-1, 12, 64)
            v = np.concatenate([cached_v, qkv[None, 2 * W :]]).reshape(-1, 12, 64)
            scores = np.einsum("hd,thd->ht", qkv[:W].reshape(12, 64), k) / 8
            exps = np.exp(scores - scores.max(axis=1, keepdims=True))
            return np.einsum(
                "ht,thd->hd", exps / exps.sum(axis=1, keepdims=True), v
            ).reshape(W)

        pc = np.stack([mix(pqkv[t], pk[:t], pv[:t]) for t in range(len(prefix))])
        n1 = norm(current, 1)
        qkv = n1 @ quantized[0].reconstructed.T + biases[0]
        ctx = np.stack([mix(row, pk, pv) for row in qkv])
        residual = current + ctx @ quantized[1].reconstructed.T + biases[1]
        n2 = norm(residual, 2)
        preactivation = n2 @ quantized[2].reconstructed.T + biases[2]
        hidden = b.gelu_new(preactivation)
        output = residual + hidden @ quantized[3].reconstructed.T + biases[3]
        layer_ref = {
            "input": current.tolist(),
            "ln1": n1.tolist(),
            "qkv": qkv.tolist(),
            "mix": ctx.tolist(),
            "attn": residual.tolist(),
            "ln2": n2.tolist(),
            "fc": hidden.tolist(),
            "proj": output.tolist(),
        }
        reference["layers"].append(layer_ref)
        stage_parts, stage_css = [], []
        aliases = (
            ";".join(f"--x-{i:03d}:var(--out-{i:03d})" for i in range(W))
            if layer and not args.sibling_blocks
            else ""
        )
        stage_parts.append(
            f'<div class="block" id="block-{layer}" style="{aliases}">{{child}}</div>'
        )
        if args.reset_scratch:
            stage_parts.append('<div class="reset">{child}</div>')
        for kind in STAGES:
            if kind in ("ln1", "ln2"):
                n = 1 if kind == "ln1" else 2
                source = "x" if n == 1 else "r"
                html, css = wrapper(
                    f"b{layer}-{kind}",
                    ";".join(
                        b.norm_declarations(
                            source,
                            f"n{n}",
                            data[f"ln{n}_gamma"],
                            data[f"ln{n}_beta"],
                            f"mean{n}",
                            f"var{n}",
                        )
                    ),
                )
            elif kind == "mix":
                html, css = attention(layer, pk, pv)
            else:
                index = ("qkv", "attn", "fc", "proj").index(kind)
                sources = (n1, ctx, n2, hidden)
                src = ("n1", "ctx", "n2", "hidden")[index]
                dst = ("qkv", "r", "hidden", "out")[index]
                activation_range = float(np.max(np.abs(sources[index])) * 1.25)
                bounds = (
                    (
                        math.floor(float(preactivation.min())) - 2,
                        math.ceil(float(preactivation.max())) + 2,
                    )
                    if args.fc_easing and kind == "fc"
                    else None
                )
                html, css = matvec(
                    layer,
                    kind,
                    quantized[index],
                    biases[index],
                    names(src, sources[index].shape[1]),
                    names(dst, len(biases[index])),
                    activation_range,
                    args.chunk,
                    args.compact_metrics,
                    args.gated,
                    bounds,
                )
                if args.retire_stages or (args.retire_blocks and kind == "proj"):
                    captured = names(dst, len(biases[index]))
                    if args.retire_blocks:
                        captured += names("qkv", 3 * W)[W:]
                    html, retirement_css = retire_stage(
                        html, layer, kind, captured, args.epochs, args.retire_blocks
                    )
                    css += retirement_css
            output_stem = dict(
                zip(STAGES, ("n1", "qkv", "ctx", "r", "n2", "hidden", "out"))
            )[kind]
            check = probe(
                f"b{layer}-{kind}-probe", output_stem, len(layer_ref[kind][0])
            )
            html = html.replace(
                "{child}", f'<div id="b{layer}-{kind}-result">{check}{{child}}</div>'
            )
            stage_parts.append(html)
            stage_css.append(css)
            # Isolated stages for cost attribution. Inputs come from independent
            # reference states, not from a browser output; never an inference run.
            source_stems = {
                "ln1": [("x", current)],
                "qkv": [("n1", n1)],
                "mix": [("qkv", qkv)],
                "attn": [("ctx", ctx), ("x", current)],
                "ln2": [("r", residual)],
                "fc": [("n2", n2)],
                "proj": [("hidden", hidden), ("r", residual)],
            }[kind]
            isolated = html.replace("{child}", "")
            state_styles = [
                f"--epoch:{s + 1};"
                + ";".join(declarations(stem, rows[s]) for stem, rows in source_stems)
                for s in range(len(current))
            ]
            isolated_css = shared + css + "body{" + state_styles[0] + "}"
            if args.content_gates:
                isolated_css = isolated_css.replace(
                    "-gate{display:none}",
                    "-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}",
                ).replace("-gate{display:block}", "-gate{content-visibility:visible}")
            (OUT / f"b{layer}-{kind}.html").write_text(
                document(isolated_css, isolated, f"b{layer}-{kind}-probe")
            )
            layer_ref.setdefault("stageInputStyles", {})[kind] = state_styles
        inner = "{child}"
        for part in reversed(stage_parts):
            inner = part.replace("{child}", inner)
        block_html.append(inner)
        all_css += stage_css
        if args.sibling_blocks:
            bridges.append(bridge(layer, args.chunk))
            all_css.append(bridges[-1][2])
        pr = prefix + pc @ quantized[1].reconstructed.T + biases[1]
        ph = b.gelu_new(norm(pr, 2) @ quantized[2].reconstructed.T + biases[2])
        prefix = pr + ph @ quantized[3].reconstructed.T + biases[3]
        current = output
        (OUT / "reference.json").write_text(json.dumps(reference))
        final = (
            "<output id=final>"
            + probe("final-probe", "out", W)
            + "Current-token block output</output>"
        )
        if args.sibling_blocks:
            siblings = []
            for i, part in enumerate(block_html):
                item = part.replace("{child}", final if i == layer else bridges[i][0])
                if i:
                    item = bridges[i - 1][1].replace("{child}", item)
                siblings.append(item)
            chain = "".join(siblings)
            # All scope names must be in one rule; repeated declarations replace,
            # rather than extend, the prior scope list.
            scoped = (
                "html{timeline-scope:"
                + ",".join(t for br in bridges[:layer] for t in br[3])
                + "}"
                if layer
                else ""
            )
        else:
            chain = final
            for part in reversed(block_html):
                chain = part.replace("{child}", chain)
            scoped = ""
        base_input = "--epoch:1;" + declarations("x", reference["inputs"][0])
        combined_css = shared + "body{" + base_input + "}" + "".join(all_css) + scoped
        if args.content_gates:
            combined_css = combined_css.replace(
                "-gate{display:none}",
                "-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}",
            ).replace("-gate{display:block}", "-gate{content-visibility:visible}")
        (OUT / f"connected-{layer + 1}.html").write_text(
            document(combined_css, chain, "final-probe")
        )
        print(
            f"built {layer + 1}/{args.blocks} blocks; context {args.context}",
            flush=True,
        )


if __name__ == "__main__":
    main()
