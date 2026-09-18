#!/usr/bin/env python3
"""Reusable, native GPT-2 core with write-once browser-owned KV slots.

The slot budget is finite. A root epoch selects the current slot; older slots
hold their previous values through registered-property delayed transitions.
No KV values or activation calibration from reference runs enter emitted CSS.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import browser_gpt2_cache as packed_cache
import build_gpt2_block_css as b
import build_hybrid_twelve_block as hybrid
import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_signed_hvar_chain import quantize_float_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/core"
W = 768
TOKENS = [15496, 995, 11, 314, 1101, 257, 3303, 2746]


def cache_names(slot, packed=False):
    if packed and packed != "discrete":
        return packed_cache.storage_names(slot, packed)
    return [f"--kv-{kind}{slot}-{i:03d}" for kind in ("k", "v") for i in range(W)]


def shared_css(capacity, cache_layout="nested", packed=False):
    if packed and cache_layout != "flat":
        raise ValueError("Packed KV is only implemented for flat banks")
    scratch = []
    for name, count in (
        ("x", W),
        ("n1", W),
        ("qkv", 3 * W),
        ("ctx", W),
        ("r", W),
        ("n2", W),
        ("hidden", 4 * W),
        ("out", W),
    ):
        scratch += hybrid.names(name, count)
    scratch += ["--mean1", "--var1", "--mean2", "--var2"]
    for h in range(12):
        scratch += [f"--max-{h}", f"--den-{h}"]
        scratch += [f"--{p}-{h}-{t}" for p in ("s", "e", "p") for t in range(capacity)]
    css = hybrid.regs(scratch + ["--epoch"])
    css += hybrid.regs(
        hybrid.names("bridge-p", W) + ["--bridge-stamp", "--bridge-ready"]
    )
    css += "".join(
        f"@keyframes bridgek{i}{{from{{--bridge-p-{i:03d}:0}}to{{--bridge-p-{i:03d}:1}}}}"
        for i in range(W)
    )
    css += "@keyframes bridgestamp{from{--bridge-stamp:0}to{--bridge-stamp:1}}"
    for kind, count in (("qkv", 3 * W), ("attn", W), ("fc", 4 * W), ("proj", W)):
        props = hybrid.names(kind + "p", count)
        scratch += props
        css += hybrid.regs(props + [f"--stamp-{kind}", f"--gate-{kind}"])
        css += "".join(
            f"@keyframes {kind}k{i}{{from{{--{kind}p-{i:03d}:0}}to{{--{kind}p-{i:03d}:1}}}}"
            for i in range(count)
        )
        css += (
            f"@keyframes {kind}stamp{{from{{--stamp-{kind}:0}}to{{--stamp-{kind}:1}}}}"
        )
    css += (
        "body{container-name:runtime}"
        ".scroller{position:fixed;left:0;top:-60000px;height:1px;overflow-x:scroll;overflow-y:hidden;contain:strict;visibility:hidden}"
        ".track{position:relative;height:1px}"
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:hidden;white-space:pre}"
        ".metric i{font-style:normal}"
        ".readback{position:fixed;left:0;top:0;display:block;visibility:hidden;contain:strict}"
        "@function --gelu(--z <number>) returns <number>{--t:clamp(-20,calc(.7978845608028654 * (var(--z) + .044715 * pow(var(--z),3))),20);"
        "result:calc(.5 * var(--z) * (1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
    )
    css += (
        ".core-reset{"
        + ";".join(f"{p}:initial" for p in scratch if not p.startswith("--x-"))
        + ";font:12px monospace;font-variation-settings:normal}"
    )
    all_cache_props = [p for slot in range(capacity) for p in cache_names(slot, packed)]
    if cache_layout == "flat":
        css += (
            ".kv-bank{transition-property:"
            + ",".join(all_cache_props)
            + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}"
        )
        if packed == "discrete" or (packed and packed_cache.config(packed)[2]):
            css += ".kv-bank{transition-behavior:allow-discrete}"
    for slot in range(capacity):
        props = cache_names(slot, packed)
        if packed == "discrete":
            css += "".join(
                f'@property {name}{{syntax:"*";inherits:true;initial-value:0}}'
                for name in props
            )
        else:
            css += (
                packed_cache.registrations(slot, packed)
                if packed
                else hybrid.regs(props)
            )
        if cache_layout == "nested":
            css += f".kv-slot-{slot}{{transition-property:{','.join(props)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);"
        else:
            excluded = set(props)
            retained = [p for p in all_cache_props if p not in excluded]
            css += f"@container runtime style(--epoch:{slot + 1}){{.kv-bank{{transition-property:{','.join(retained) or 'none'};"
        if packed and packed != "discrete":
            css += packed_cache.declarations(slot, packed)
        for index, name in enumerate([] if packed and packed != "discrete" else props):
            source = f"var(--qkv-{W + index:03d})"
            # Future slots start at zero. Past slots continue to target the
            # live source, but their delayed transitions retain stored values.
            if cache_layout == "flat":
                # Only this epoch's active slot declares a live source. Past
                # slots target inherited zero, holding their captured value.
                css += f"{name}:{source};"
            else:
                css += f"{name}:calc({source} * clamp(0,sign(var(--epoch) - {slot + 1}) + 1,1));"
        css += "}"
        if cache_layout == "nested":
            css += f"@container runtime style(--epoch:{slot + 1}){{.kv-slot-{slot}{{transition-property:none}}}}"
        else:
            css += "}"
    return css


def live_attention(layer, capacity, packed=False):
    def cached(slot, kind, coordinate):
        value = (
            packed_cache.read(slot, kind, coordinate, packed)
            if packed and packed != "discrete"
            else f"var(--kv-{kind}{slot}-{coordinate:03d})"
        )
        if isinstance(packed, str) and packed.startswith("integer"):
            # Computed <integer> calc serializes with six significant digits
            # until its retained transition materializes an integer CSSValue.
            # The current token uses live QKV; only completed tokens decode
            # integer packets. This bypass is required, not an optimization.
            source = W * (1 if kind == "k" else 2) + coordinate
            value = f"if(style(--epoch:{slot + 1}):var(--qkv-{source:03d});else:calc({value}))"
        return value

    rules = []
    for head in range(12):
        offset = head * 64
        for slot in range(capacity):
            terms = " + ".join(
                f"var(--qkv-{offset + d:03d}) * {cached(slot, 'k', offset + d)}"
                for d in range(64)
            )
            # Mask future positions before the stable-softmax maximum.
            rules.append(
                f"--s-{head}-{slot}:if(style(--valid-{slot}:1):calc(({terms}) / 8);else:-1000000)"
            )
        rules.append(
            f"--max-{head}:max({','.join(f'var(--s-{head}-{s})' for s in range(capacity))})"
        )
        for slot in range(capacity):
            rules.append(
                f"--e-{head}-{slot}:exp(calc(var(--s-{head}-{slot}) - var(--max-{head})))"
            )
        rules.append(
            f"--den-{head}:calc({' + '.join(f'var(--e-{head}-{s})' for s in range(capacity))})"
        )
        for slot in range(capacity):
            rules.append(
                f"--p-{head}-{slot}:calc(var(--e-{head}-{slot}) / var(--den-{head}))"
            )
        for d in range(64):
            i = offset + d
            terms = " + ".join(
                f"var(--p-{head}-{s}) * {cached(s, 'v', i)}" for s in range(capacity)
            )
            rules.append(f"--ctx-{i:03d}:calc({terms})")
    return hybrid.wrapper(f"live-mix-{layer}", ";".join(rules))


def layer_matrices(tensors, layer):
    data = b.model_data(layer)
    weights = [
        np.asarray(tensors.tensor(f"h.{layer}.attn.c_attn.weight"), dtype=np.float64).T,
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
    return data, [quantize_float_rows(w, bits=9) for w in weights], biases


def compile_core(
    blocks=12,
    capacity=8,
    cache_layout="nested",
    isolate_cache=False,
    packed_cache_enabled=False,
    liveness=False,
    uncached_style=False,
    scoped_state=False,
):
    tensors = SafeTensors(MODEL_PATH)
    css = shared_css(capacity, cache_layout, packed_cache_enabled)
    if uncached_style:
        selector = (
            ".core-block div:not(.scroller):not(.track)"
            if uncached_style == "vectors"
            else ".core-block,.core-block *"
        )
        css += selector + "{opacity:attr(data-mpc-guard type(<number>),1)}"
    if isolate_cache:
        # Attention's registered --ctx values are computed before this boundary.
        # Later dense layers need that vector, not inherited per-token K/V state.
        css += (
            ".kv-clear{"
            + ";".join(
                f"{p}:initial"
                for slot in range(capacity)
                for p in cache_names(slot, packed_cache_enabled)
            )
            + "}"
        )
    css += hybrid.regs([f"--valid-{s}" for s in range(capacity)])
    css += (
        ".core-valid{"
        + ";".join(
            f"--valid-{s}:clamp(0,sign(var(--epoch) - {s + 1}) + 1,1)"
            for s in range(capacity)
        )
        + "}"
    )
    body, bridge_names = [], []
    dead_after = {
        "mix": hybrid.names("n1", W)
        + hybrid.names("qkv", 3 * W)
        + hybrid.names("qkvp", 3 * W),
        "attn": hybrid.names("ctx", W)
        + hybrid.names("x", W)
        + hybrid.names("attnp", W),
        "fc": hybrid.names("n2", W) + hybrid.names("fcp", 4 * W),
        "proj": hybrid.names("hidden", 4 * W)
        + hybrid.names("r", W)
        + hybrid.names("projp", W),
    }
    if liveness:
        for kind, names in dead_after.items():
            css += (
                f".core-dead-after-{kind}{{"
                + ";".join(f"{p}:initial" for p in names)
                + ";font:12px monospace;font-variation-settings:normal}"
            )
    previous_receiver = None
    for layer in range(blocks):
        data, matrices, biases = layer_matrices(tensors, layer)
        parts = [
            f'<div class="core-block" id="block-{layer}"><div class="core-reset"><div class="core-valid">{{child}}</div></div></div>'
        ]
        for kind in hybrid.STAGES:
            if kind in ("ln1", "ln2"):
                n = 1 if kind == "ln1" else 2
                source = "x" if n == 1 else "r"
                html, rule = hybrid.wrapper(
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
                if cache_layout == "flat":
                    classes = " ".join(f"kv-slot-{s}" for s in range(capacity))
                    parts.append(
                        f'<div class="kv-bank {classes}" data-layer="{layer}">{{child}}</div>'
                    )
                else:
                    for slot in range(capacity):
                        parts.append(
                            f'<div class="kv-slot-{slot}" data-layer="{layer}">{{child}}</div>'
                        )
                html, rule = live_attention(layer, capacity, packed_cache_enabled)
                if scoped_state:
                    # A cache is private to its bank and this one attention
                    # consumer. Do not copy it through every later matvec.
                    rule += (
                        f".live-mix-{layer}{{"
                        + ";".join(
                            f"{p}:inherit"
                            for slot in range(capacity)
                            for p in cache_names(slot, packed_cache_enabled)
                        )
                        + "}"
                    )
            else:
                i = ("qkv", "attn", "fc", "proj").index(kind)
                src, count = (("n1", W), ("ctx", W), ("n2", W), ("hidden", 4 * W))[i]
                target = ("qkv", "r", "hidden", "out")[i]
                html, rule = hybrid.matvec(
                    layer,
                    kind,
                    matrices[i],
                    biases[i],
                    hybrid.names(src, count),
                    hybrid.names(target, len(biases[i])),
                    1,
                    512,
                    compact=True,
                    gated=True,
                    dynamic_range=True,
                )
            css += rule
            parts.append(html)
            if liveness and kind in dead_after:
                parts.append(f'<div class="core-dead-after-{kind}">{{child}}</div>')
            if kind == "mix" and isolate_cache:
                parts.append('<div class="kv-clear">{child}</div>')
        source, receiver, rule, names = hybrid.bridge(layer, 512)
        css += rule
        bridge_names += names
        finish = (
            f'<div id="block-{layer}-result">'
            + hybrid.probe(f"block-{layer}-probe", "out", W)
            + source
            + "</div>"
        )
        inner = finish
        for part in reversed(parts):
            inner = part.replace("{child}", inner)
        if previous_receiver:
            inner = previous_receiver.replace("{child}", inner)
        body.append(inner)
        previous_receiver = receiver
        print(f"compiled native KV block {layer + 1}/{blocks}", flush=True)
    css += "html{timeline-scope:" + ",".join(bridge_names) + "}"
    if scoped_state:
        private = set(
            hybrid.names("bridge-p", W)
            + ["--bridge-stamp"]
            + [
                p
                for slot in range(capacity)
                for p in cache_names(slot, packed_cache_enabled)
            ]
        )
        for kind, count in (("qkv", 3 * W), ("attn", W), ("fc", 4 * W), ("proj", W)):
            private.update(hybrid.names(kind + "p", count))
            private.update([f"--stamp-{kind}", f"--gate-{kind}"])
        css = re.sub(
            r"@property (--[\w-]+)\{[^{}]+\}",
            lambda m: (
                m[0].replace("inherits:true", "inherits:false")
                if m[1] in private
                else m[0]
            ),
            css,
        )
        # Non-inherited scratch automatically starts at its initial value.
        css = re.sub(
            r"(--[\w-]+):initial;?",
            lambda m: "" if m[1] in private else m[0],
            css,
        )
    css = css.replace(
        "-gate{display:none}",
        "-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}",
    ).replace("-gate{display:block}", "-gate{content-visibility:visible}")
    # Final receiver exposes the same x convention as inter-block handoffs.
    body.append(
        previous_receiver.replace(
            "{child}",
            '<div id="core-result">'
            + hybrid.probe("core-probe", "x", W)
            + "{child}</div>",
        )
    )
    return (
        "".join(body),
        css,
        {
            "blocks": blocks,
            "capacity": capacity,
            "dynamicActivationRange": True,
            "runtimeJavaScript": False,
            "cacheLayout": cache_layout,
            "isolateCache": isolate_cache,
            "cacheCodec": packed_cache_enabled or "scalar",
            "liveness": liveness,
            "uncachedStyle": uncached_style,
            "scopedState": scoped_state,
            "packedCacheBits": packed_cache.config(packed_cache_enabled)[0]
            if packed_cache_enabled and packed_cache_enabled != "discrete"
            else None,
        },
    )


def attention_positions(position, window=None, sinks=0):
    """Indices for a causal prefix, or an explicitly requested bounded mask."""
    if window is not None and (window < 1 or not 0 <= sinks < window):
        raise ValueError("Require 0 <= sinks < positive KV window")
    if window is None or position < window:
        return list(range(position + 1))
    return list(range(sinks)) + list(
        range(position - (window - sinks) + 1, position + 1)
    )


def reference_sequence(tokens, blocks, quantized=True, kv_window=None, kv_sinks=0):
    tensors = SafeTensors(MODEL_PATH)
    inputs = np.asarray(
        tensors.tensor("wte.weight")[tokens], dtype=np.float64
    ) + np.asarray(tensors.tensor("wpe.weight")[: len(tokens)], dtype=np.float64)
    rows = inputs.copy()
    layers = []
    for layer in range(blocks):
        data, matrices, biases = layer_matrices(tensors, layer)
        weights = (
            [m.reconstructed for m in matrices]
            if quantized
            else [
                np.asarray(
                    tensors.tensor(f"h.{layer}.attn.c_attn.weight"), dtype=np.float64
                ).T,
                data["attn_proj_weight"],
                data["fc_weight"],
                data["mlp_proj_weight"],
            ]
        )
        n = np.stack(
            [b.layer_norm(x, data["ln1_gamma"], data["ln1_beta"]) for x in rows]
        )
        qkv = n @ weights[0].T + biases[0]
        q, k, v = np.split(qkv, 3, axis=1)
        ctx = []
        for t in range(len(tokens)):
            retained = attention_positions(t, kv_window, kv_sinks)
            scores = (
                np.einsum(
                    "hd,thd->ht", q[t].reshape(12, 64), k[retained].reshape(-1, 12, 64)
                )
                / 8
            )
            exp = np.exp(scores - scores.max(1, keepdims=True))
            ctx.append(
                np.einsum(
                    "ht,thd->hd",
                    exp / exp.sum(1, keepdims=True),
                    v[retained].reshape(-1, 12, 64),
                ).reshape(W)
            )
        residual = rows + np.asarray(ctx) @ weights[1].T + biases[1]
        n2 = np.stack(
            [b.layer_norm(x, data["ln2_gamma"], data["ln2_beta"]) for x in residual]
        )
        hidden = b.gelu_new(n2 @ weights[2].T + biases[2])
        rows = residual + hidden @ weights[3].T + biases[3]
        layers.append({"qkv": qkv.tolist(), "out": rows.tolist()})
    return {
        "tokens": tokens,
        "inputs": inputs.tolist(),
        "layers": layers,
        "outputs": rows.tolist(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=2)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--cache-layout", choices=("nested", "flat"), default="nested")
    parser.add_argument("--isolate-cache", action="store_true")
    parser.add_argument("--liveness", action="store_true")
    parser.add_argument("--uncached-style", action="store_true")
    parser.add_argument("--uncached-vectors", action="store_true")
    parser.add_argument("--scoped-state", action="store_true")
    parser.add_argument(
        "--tokens-file",
        type=Path,
        help="JSON array of teacher-forced token IDs for component evaluation",
    )
    parser.add_argument(
        "--cache-codec",
        choices=(
            "scalar",
            "discrete",
            "numeric12",
            "numeric9",
            "integer6",
            "integer10",
            "expression8",
            "expression10",
            "expression12",
            "expression16",
        ),
        default="scalar",
    )
    args = parser.parse_args()
    tokens = (
        json.loads(args.tokens_file.read_text())
        if args.tokens_file
        else TOKENS[: args.capacity]
    )
    if not 1 <= args.blocks <= 12 or not 1 <= args.capacity <= 1024:
        parser.error("require 1–12 blocks and 1–1024 positions")
    if len(tokens) != args.capacity or any(
        type(t) is not int or not 0 <= t < 50257 for t in tokens
    ):
        parser.error(
            "supply exactly capacity valid token IDs; use --tokens-file beyond eight positions"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    html, css, metadata = compile_core(
        args.blocks,
        args.capacity,
        args.cache_layout,
        args.isolate_cache,
        False if args.cache_codec == "scalar" else args.cache_codec,
        args.liveness,
        "vectors" if args.uncached_vectors else args.uncached_style,
        args.scoped_state,
    )
    reference = reference_sequence(tokens, args.blocks)
    initial = "--epoch:1;" + hybrid.declarations("x", reference["inputs"][0])
    css += "body{" + initial + "}"
    (args.output / "core.css").write_text(css)
    (args.output / "core-body.html").write_text(html)
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="core.css"><body>'
        + html.replace("{child}", "")
        + '<i class="readback" id="measurement" style="width:anchor-size(--core-probe-epoch width,0px);height:anchor-size(--core-probe width,1px)"></i></body>'
    )
    (args.output / "index.html").write_text(page)
    (args.output / "reference.json").write_text(json.dumps(metadata | reference))


if __name__ == "__main__":
    main()
