"""Experimental single-rendering-graph GPT-2 core with native layer feedback.

Only one set of dense-matrix elements exists. Each layer selects its own real
font weights and normalization constants. Independent native banks retain its
K/V. The fixture's token IDs are explicit teacher-forced inputs, not generated
outputs; no intermediate activations are embedded in the page.
"""

import argparse
import json
import re
from pathlib import Path

import build_gpt2_block_css as b
import build_hybrid_twelve_block as h
import f5_scoping as f5
import r2c_hoist as r2c
import r3r_fold_hop as r3r
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import (
    TOKENS,
    W,
    cache_names,
    layer_matrices,
    live_attention,
    reference_sequence,
    shared_css,
)
from browser_gpt2_runtime import font_barrier
from probe_native_reused_loop import loop_parts

ROOT = Path(__file__).resolve().parents[1]


def isolate_metric_state(css):
    """Materialize projection axis lists before discarding unused metric inputs.

    Font settings inherit as a computed font value. The metric-only branches
    need no neural vectors once that value is selected; the separate numeric
    consumer branch keeps its normal state and residual connections.
    """

    def projection(match):
        slot, family, settings = match.groups()
        return (
            f".shared-proj{{--proj-settings-{slot}:{settings}}}"
            f".shared-proj-pack{slot}{{font-family:{family};font-variation-settings:var(--proj-settings-{slot})}}"
        )

    css, count = re.subn(
        r"\.shared-proj-pack(\d+)\{font-family:([^;{}]+);font-variation-settings:([^;{}]+)\}",
        projection,
        css,
    )
    if not count:
        raise ValueError("Expected sharded projection font settings")
    fields = []
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
        fields.extend(h.names(stem, count))
    css += ",".join(
        f".shared-{kind}>.scroller" for kind in ("qkv", "attn", "fc", "proj")
    )
    return css + "{" + ";".join(f"{p}:initial" for p in fields) + "}"


def specialize(html, css, layer, kind):
    """Keep layer-specific assets outside conditional reusable layout rules."""
    globals_css = "".join(
        m[0] for m in re.finditer(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", css)
    )
    css = re.sub(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", "", css)
    if r3r.FOLD_HOP:
        # R3R: html-scoped timeline names cannot live inside the layer container block
        scopes = re.findall(r"html\{timeline-scope:[^{}]*\}", css)
        css = re.sub(r"html\{timeline-scope:[^{}]*\}", "", css)
        globals_css += "".join(scopes).replace(f"b{layer}-", "shared-")
    html = html.replace(f"b{layer}-", "shared-")
    css = css.replace(f"b{layer}-", "shared-")
    if r2c.HOIST_STAGES:
        # R2C: the hoisted quotient declarations are layer-independent; one copy.
        css, lifted = r2c.lift_stage_rules(css)
        globals_css += lifted
    marker = re.search(r"width:calc\((\d+)px \+ var\(--epoch\) \* 1024px\)", html)
    if marker:
        css += f".shared-{kind}{{--markerbase-{kind}:{marker[1]}px}}"
        html = html.replace(
            marker[0], f"width:calc(var(--markerbase-{kind}) + var(--epoch) * 1024px)"
        )
    return html, globals_css + f"@container runtime style(--layer:{layer}){{{css}}}"


def compile_reused(
    blocks,
    capacity,
    codec="expression12",
    liveness=False,
    uncached_style=False,
    centered_context=False,
    scoped_state=False,
    kv_window=None,
    kv_sinks=0,
    isolate_metrics=False,
    value_layout="runs",
    global_projection=False,
    value_weight_once=True,
):
    if global_projection and isolate_metrics:
        raise ValueError("Do not combine global projection and metric isolation ablations")
    geometry_cache = codec == "geometry"
    font_vector_cache = codec == "font-vector"
    custom_cache = geometry_cache or font_vector_cache
    if (kv_window is not None or kv_sinks) and not font_vector_cache:
        raise ValueError("Bounded KV currently requires the font-vector cache")
    packed = False if codec in ("scalar", "geometry", "font-vector") else codec
    css = shared_css(0 if custom_cache else capacity, "flat", packed)
    if centered_context:
        css = re.sub(
            r"(@keyframes bridgek\d+\{from\{--bridge-p-\d+:)0", r"\g<1>-2", css
        )
    css = css.replace("style(--epoch:", "style(--position:")
    css += h.regs(["--position", "--layer"] + [f"--valid-{s}" for s in range(capacity)])
    css += (
        ".core-valid{"
        + ";".join(
            f"--valid-{s}:clamp(0,sign(var(--position) - {s + 1}) + 1,1)"
            for s in range(capacity)
        )
        + "}"
    )
    tensors = SafeTensors(MODEL_PATH)
    layouts = {}
    for layer in range(blocks):
        data, matrices, biases = layer_matrices(tensors, layer)
        for kind in h.STAGES:
            if kind == "mix":
                continue
            if kind in ("ln1", "ln2"):
                n = 1 if kind == "ln1" else 2
                html, rule = h.wrapper(
                    f"b{layer}-{kind}",
                    ";".join(
                        b.norm_declarations(
                            "x" if n == 1 else "r",
                            f"n{n}",
                            data[f"ln{n}_gamma"],
                            data[f"ln{n}_beta"],
                            f"mean{n}",
                            f"var{n}",
                        )
                    ),
                )
            else:
                i = ("qkv", "attn", "fc", "proj").index(kind)
                src, count = (("n1", W), ("ctx", W), ("n2", W), ("hidden", 4 * W))[i]
                target = ("qkv", "r", "hidden", "out")[i]
                html, rule = h.matvec(
                    layer,
                    kind,
                    matrices[i],
                    biases[i],
                    h.names(src, count),
                    h.names(target, len(biases[i])),
                    1,
                    512,
                    compact=True,
                    gated=True,
                    dynamic_range=True,
                    global_axes=global_projection and kind == "proj",
                    fold=r3r.FOLD_HOP and kind == "proj",
                )
            html, rule = specialize(html, rule, layer, kind)
            if kind in layouts and html != layouts[kind]:
                raise ValueError(f"Layer {layer} has an incompatible {kind} layout")
            layouts[kind] = html
            css += rule
        print(f"compiled reusable weights {layer + 1}/{blocks}", flush=True)

    if isolate_metrics:
        css = isolate_metric_state(css)
    if h.INLINE_GELU:
        # private scratch of the fc consumers; never inherited, never reset
        css += "".join(
            f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}'
            for stem in ("fz", "ft")
            for p in h.names(stem, 4 * W)
        )

    # Cache storage stays outside the dense MLP subtree. Only the selected
    # layer exports a context vector through layout. Scalar banks are siblings;
    # whole-font-vector banks nest private state around one attention graph.
    ctx_source, ctx_receiver, ctx_css, _ = h.bridge(100, 512)
    ctx_source = ctx_source.replace("b100-bridge", "cache-bridge").replace(
        "--out-", "--ctx-"
    )
    ctx_receiver = ctx_receiver.replace("b100-bridge", "cache-bridge")
    ctx_css = ctx_css.replace("b100-bridge", "cache-bridge").replace("--x-", "--ctx-")
    if centered_context:
        ctx_css = re.sub(
            r"524288 / var\((--bridge-p-\d+)\)", r"1572864 / (var(\1) + 2)", ctx_css
        )
    css += ctx_css
    bank_props = (
        []
        if custom_cache
        else [p for s in range(capacity) for p in cache_names(s, packed)]
    )
    banks = []
    if font_vector_cache:
        from browser_gpt2_font_vector_cache import attention as font_attention

        font_body, font_css, _ = font_attention(
            capacity,
            blocks,
            ctx_source,
            write_epoch="--position",
            kv_window=kv_window,
            kv_sinks=kv_sinks,
            value_layout=value_layout,
            value_weight_once=value_weight_once,
        )
        css += font_css
    if geometry_cache:
        from browser_gpt2_geometry_cache import attention, context_source, in_plane

        geometry_storage, geometry_mix, geometry_css, expressions = attention(
            capacity, epoch="--position", split=True
        )
        css += geometry_css
        geometry_source = context_source(ctx_source, expressions, stem="ctx")
    for layer in range(blocks):
        if font_vector_cache:
            continue
        if geometry_cache:
            banks.append(
                f'<div class="geometry-cache" id="cache-{layer}" data-layer="{layer}">'
                + geometry_storage
                + "</div>"
            )
            css += f"#cache-{layer}{{display:none}}@container runtime style(--layer:{layer}){{#cache-{layer}{{display:block}}}}"
            continue
        mix_html, mix_css = live_attention(layer, capacity, packed)
        css += mix_css.replace("style(--epoch:", "style(--position:")
        banks.append(
            f'<div class="kv-bank" id="cache-{layer}" data-layer="{layer}"><div class="cache-active">'
            + mix_html.replace("{child}", ctx_source)
            + "</div></div>"
        )
        css += f"#cache-{layer}>.cache-active{{display:none}}@container runtime style(--layer:{layer}){{#cache-{layer}>.cache-active{{display:block}}}}"
        css += (
            f"@container runtime not style(--layer:{layer}){{#cache-{layer}{{transition-property:{','.join(bank_props)};"
            + ";".join(f"{p}:initial" for p in bank_props)
            + "}}"
        )
    if font_vector_cache:
        mix_source = font_body
    elif geometry_cache:
        mix_source = in_plane(geometry_source, "".join(banks) + geometry_mix)
    else:
        mix_source = "".join(banks)
    layouts["mix"] = mix_source + ctx_receiver

    if r3r.FOLD_HOP:
        source, output, loop_css = r3r.loop_parts(W, blocks, capacity)
    else:
        source, output, loop_css = loop_parts(
            W, blocks * capacity, centered=True, selective=liveness
        )
    css += loop_css
    css += (
        "body{container-name:runtime loopcontrol;--epoch:var(--pass);--layer:mod(calc(var(--pass) - 1),"
        + str(blocks)
        + ");--position:calc(round(down,calc((var(--pass) - 1) / "
        + str(blocks)
        + "),1) + 1)}"
    )
    # Every token starts from its own input embedding. Only intra-token layers
    # use residual feedback; the KV banks keep all preceding tokens live.
    css += (
        "@container runtime style(--layer:0){.loop-input{--loop-ready:1;"
        + ";".join(f"--loop-in-{i}:var(--input-{i})" for i in range(W))
        + "}}"
    )
    css += (
        ".reused-input{"
        + ";".join(f"--x-{i:03d}:var(--loop-in-{i})" for i in range(W))
        + "}"
    )
    if not r3r.FOLD_HOP:  # R3R: no banks, nothing consumes --loop-out-*
        css += (
            ".reused-output{"
            + ";".join(f"--loop-out-{i}:var(--out-{i:03d})" for i in range(W))
            + "}"
        )
    inner = (
        '<div class="reused-output" id="reused-result">'
        + h.probe("reused-probe", "out", W)
        + output.replace("{child}", '<i id="loop-result"></i>')
        + "</div>"
    )
    dead_after = {
        "mix": h.names("n1", W)
        + h.names("qkv", 3 * W)
        + h.names("qkvp", 3 * W)
        + h.names("bridge-p", W),
        "attn": h.names("ctx", W) + h.names("x", W) + h.names("attnp", W),
        "fc": h.names("n2", W) + h.names("fcp", 4 * W),
        "proj": h.names("hidden", 4 * W) + h.names("r", W) + h.names("projp", W),
    }
    for kind in reversed(h.STAGES):
        if liveness and kind in dead_after:
            css += (
                f".dead-after-{kind}{{"
                + ";".join(f"{p}:initial" for p in dead_after[kind])
                + ";font:12px monospace;font-variation-settings:normal}"
            )
            inner = f'<div class="dead-after-{kind}">' + inner + "</div>"
        inner = layouts[kind].replace("{child}", inner)
    if liveness:
        dead = (
            [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
            + [f"--loop-in-{i}" for i in range(W)]
            + [f"--input-{i}" for i in range(W)]
        )
        css += ".loop-input-clear{" + ";".join(f"{p}:initial" for p in dead) + "}"
        inner = '<div class="loop-input-clear">' + inner + "</div>"
    inner = '<div class="core-reset core-valid reused-input">' + inner + "</div>"
    body = source.replace("{child}", inner)
    if scoped_state:
        # Keep private animation/carrier state out of the recurrent core's
        # inherited maps. Explicit forwarding only at its actual consumers.
        progress = h.names("bridge-p", W) + ["--bridge-stamp"]
        for kind, count in (("qkv", 3 * W), ("attn", W), ("fc", 4 * W), ("proj", W)):
            progress += h.names(kind + "p", count) + [
                f"--stamp-{kind}",
                f"--gate-{kind}",
            ]
        if r3r.FOLD_HOP:
            lp, saved, outputs = r3r.reader_names(W), [], []
        else:
            lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
            saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
            outputs = [f"--loop-out-{i}" for i in range(W)]
        private = set(progress + lp + saved + outputs + bank_props)
        css = re.sub(
            r"@property (--[\w-]+)\{[^{}]+\}",
            lambda m: (
                m[0].replace("inherits:true", "inherits:false")
                if m[1] in private
                else m[0]
            ),
            css,
        )

        def forward(selector, names):
            return selector + "{" + ";".join(f"{p}:inherit" for p in names) + "}"

        css += forward(".loop-input", lp)
        if r3r.FOLD_HOP:
            pass  # no banks, no bank carriers
        elif f5.INLINE_FORWARD:
            css += forward(".loop-bank-0,.loop-bank-1", outputs)
            css += forward(".loop-scroll,.loop-track", saved)

            # F5: 1,538 `.loop-metric:nth-child(N)` rules share one class
            # bucket, so every loop-metric tested all 1,538 selectors on each
            # restyle (P2: 153 us/element on the 1,553-element pass). The
            # same forwarding as an inline declaration costs one rule.
            body, count = re.subn(
                r'<i class="loop-metric" style="width:calc\(262144px \+ var\((--saved-\d-\d+)\) \* 128px\);',
                r'<i class="loop-metric" style="\1:inherit;width:calc(262144px + var(\1) * 128px);',
                body,
            )
            if count != 2 * (W + 1):
                raise ValueError(f"Expected {2 * (W + 1)} loop carriers, found {count}")
        else:
            css += forward(".loop-bank-0,.loop-bank-1", outputs)
            css += forward(".loop-scroll,.loop-track", saved)
            for bank in range(2):
                for i in range(W + 1):
                    css += forward(
                        f".loop-bank-{bank}>.loop-scroll>.loop-track>.loop-metric:nth-child({i + 1})",
                        [f"--saved-{bank}-{i}"],
                    )
        css += forward(".cache-active", bank_props)
        css += forward(
            ",".join(f".live-mix-{layer}" for layer in range(blocks)), bank_props
        )
    if uncached_style:
        # In this Chromium revision HasAttrFunction excludes a style from the
        # MatchedPropertiesCache. The absent attribute's fallback is opacity 1,
        # so it changes caching, not geometry or neural arithmetic.
        selector = (
            ".loop-reader,.loop-reader div:not(.scroller):not(.track):not(.loop-scroll):not(.loop-track)"
            if uncached_style == "vectors"
            else ".loop-reader,.loop-reader *"
        )
        css += selector + "{opacity:attr(data-mpc-guard type(<number>),1)}"
    css = css.replace(
        "-gate{display:none}",
        "-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}",
    ).replace("-gate{display:block}", "-gate{content-visibility:visible}")
    # Multiple global timeline-scope declarations must be merged, not overwritten.
    scopes = re.findall(r"html\{timeline-scope:([^}]+)\}", css)
    css = re.sub(r"html\{timeline-scope:[^}]+\}", "", css)
    css += (
        "html{timeline-scope:"
        + ",".join(dict.fromkeys(t for group in scopes for t in group.split(",")))
        + "}"
    )
    return body, css


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=2)
    parser.add_argument("--capacity", type=int, default=1)
    parser.add_argument(
        "--cache-codec",
        choices=(
            "scalar",
            "geometry",
            "font-vector",
            "numeric9",
            "integer6",
            "integer10",
            "expression8",
            "expression10",
            "expression12",
            "expression16",
        ),
        default="expression12",
    )
    parser.add_argument("--tokens-file", type=Path)
    parser.add_argument("--kv-window", type=int)
    parser.add_argument("--kv-sinks", type=int, default=0)
    parser.add_argument("--isolate-metric-state", action="store_true")
    parser.add_argument("--liveness", action="store_true")
    parser.add_argument("--uncached-style", action="store_true")
    parser.add_argument("--uncached-vectors", action="store_true")
    parser.add_argument("--centered-context", action="store_true")
    parser.add_argument("--scoped-state", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/browser-gpt2/reused-two-block",
    )
    args = parser.parse_args()
    tokens = (
        json.loads(args.tokens_file.read_text())
        if args.tokens_file
        else TOKENS[: args.capacity]
    )
    if (
        not 1 <= args.blocks <= 12
        or not 1 <= args.capacity <= 1024
        or len(tokens) != args.capacity
    ):
        parser.error(
            "require 1–12 blocks, 1–1024 positions, and exactly capacity input token IDs"
        )
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    body, css = compile_reused(
        args.blocks,
        args.capacity,
        args.cache_codec,
        args.liveness,
        "vectors" if args.uncached_vectors else args.uncached_style,
        args.centered_context,
        args.scoped_state,
        args.kv_window,
        args.kv_sinks,
        args.isolate_metric_state,
    )
    reference = reference_sequence(
        tokens, args.blocks, kv_window=args.kv_window, kv_sinks=args.kv_sinks
    )
    for position, inputs in enumerate(reference["inputs"], 1):
        css += (
            f"body{{--input-position-{position}:0}}@container runtime style(--position:{position}){{.loop-reader{{"
            + ";".join(f"--input-{i}:{float(v):.12g}" for i, v in enumerate(inputs))
            + "}}"
        )
    witnesses, barrier_css, faces = font_barrier(css, directory)
    css += (
        barrier_css
        + "@keyframes native-handshake{from{opacity:.99}to{opacity:1}}.head-reduction{position:fixed;left:0;top:-100000px;display:block}.native-signals{position:fixed;left:0;top:0;width:1px;height:1px}.font-ready-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}body:has(#fonts-loaded.done) .font-ready-gate{content-visibility:visible}"
    )
    (directory / "core.css").write_text(css)
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="core.css"><body>'
        + witnesses
        + '<div class="font-ready-gate">'
        + body
        + '</div><i class="readback" id="measurement" style="width:anchor-size(--reused-probe-epoch width,0px);height:anchor-size(--reused-probe width,0px)"></i></body>'
    )
    (directory / "index.html").write_text(page)
    (directory / "reference.json").write_text(
        json.dumps(
            dict(
                blocks=args.blocks,
                capacity=args.capacity,
                cacheCodec=args.cache_codec,
                kvWindow=args.kv_window or args.capacity,
                kvSinks=args.kv_sinks,
                isolatedMetricState=args.isolate_metric_state,
                renderingGraphs=1,
                liveness=args.liveness,
                uncachedStyle="vectors"
                if args.uncached_vectors
                else args.uncached_style,
                centeredContext=args.centered_context,
                scopedState=args.scoped_state,
                fontFaces=faces,
                runtimeJavaScript=False,
                **reference,
            )
        )
    )
    print(
        {
            "htmlBytes": len(page.encode()),
            "cssBytes": len(css.encode()),
            "fontFaces": faces,
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
