#!/usr/bin/env python3
"""Finite Chromium-only GPT-2 runtime. Python is a compiler, never the scheduler.

Native font witnesses open the core. CSS/SMIL receipts capture each token,
then advance the root epoch. Retained token geometry closes the feedback loop.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import build_gpt2_block_css as b
import build_hybrid_twelve_block as hybrid
import f4_packing as f4
import r2d_knobs as r2d
import f5_scoping as f5
import r2c_hoist as r2c
import r2g_has_scope as r2g
import r3h_blockflow_max as r3h
import r5e_dead_weight as r5e
import r6p_prompt as r6p  # R6P: pre-Run prompt echo fix + typed free-text prompt (prefill)
import r6v_progress_ui as r6v  # R6V: display-only progress UI
if r6p.TYPED and r6v.ON:  # R6X merge: R6P's prompt panel (top 52) + token readout (118) occupy R6V's panel row -> move the
    r6v.TOP_PX = 146  # loading/progress row below the readout (R6V default 52) ...
    r6p.OUTPUT_TOP = 184  # ... and the output text below that (R6P default 146; base 110)
    r6v.HIDE_SELECTOR = "body>:not(.controls):not(.ld):not(.tk-panel)"  # the early-paint lock must not hide the prompt panel
import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


def r6x_head_phase_css(blocks, head_seconds=2.8):
    """R6X: 13th bar segment for the vocabulary-head phase (--held:1 on the corestate container), pseudo-elements of .pg only."""
    seg = r6v.BAR_PX / blocks
    left = r6v.BAR_PX + 4
    return (
        f".pg::before,.pg::after{{content:\"\";position:absolute;left:{left:g}px;top:22px;width:{seg - 2:g}px;height:8px;display:block}}"
        ".pg::before{background:#e3ded2}"
        ".pg::after{background:#d9822b;transform-origin:0 50%;transform:scaleX(0);will-change:transform,opacity}"
        f"@container corestate style(--held:1){{.pg::after{{animation:pg-head-fill {head_seconds}s linear forwards,pg-head-pulse .7s ease-in-out infinite alternate}}"
        '.pg-lay::after{content:" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"}}'
        "@keyframes pg-head-fill{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        "@keyframes pg-head-pulse{from{opacity:.45}to{opacity:1}}"
    )
from browser_gpt2_core import compile_core
from browser_gpt2_embedding import compile_embedding
from browser_gpt2_head import reduce_geometry
from browser_gpt2_head_receipts import split_head_receipt
from build_pretrained_gpt2 import Gpt2Tokenizer
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/demo"


def css_string(value):
    return (
        '"'
        + "".join(f"\\{ord(c):x} " if ord(c) < 32 or c in '\\"' else c for c in value)
        + '"'
    )


def feedback(capacity, synthetic=False):
    css = hybrid.regs(
        [f"--saved-token-{i}" for i in range(1, capacity + 1)]
        + [f"--feedback-{i}" for i in range(1, capacity + 1)]
        + [f"--feedback-p-{i}" for i in range(1, capacity + 1)]
        + ["--frozen-prompt"]
    )
    css += (
        "body{--epoch:1;--prompt-token:15496;container-name:runtime}"
        "@keyframes native-handshake{from{opacity:.99}to{opacity:1}}"
        ".native-signals{position:fixed;left:0;top:0;width:1px;height:1px}"
        ".feedback-scroller{position:fixed;left:0;top:-100000px;width:524288px;height:1px;overflow:scroll;visibility:hidden}"
        ".feedback-track{position:relative;width:1572864px;height:1px}"
        ".feedback-metric{position:absolute;left:0;top:0;height:1px}"
        ".token-state{container-name:headstate}"
        "#capture-epoch-observer{width:0;height:0}"
        ".token-display{position:fixed;left:24px;top:100px;font:18px/1.5 monospace;white-space:pre-wrap;max-width:800px}"
        ".feedback-reader{--frozen-prompt:var(--prompt-token);transition-property:none}"
        "body:has(#run:checked) .feedback-reader,body:has(#run-latched.done) .feedback-reader{transition-property:--frozen-prompt;transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}"
        "body:has(#run:checked) #run-start{animation:native-handshake 1ms both}"
    )
    timelines = []
    for i in range(1, capacity + 1):
        timelines.append(f"--feedback-t{i}")
        css += (
            f"@keyframes feedback{i}{{from{{--feedback-p-{i}:0}}to{{--feedback-p-{i}:1}}}}"
            f".token-slot-{i}{{--saved-token-{i}:if(style(--head-output-epoch:{i}):var(--winner);else:-1);"
            f"transition-property:--saved-token-{i};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}"
            f"@container runtime style(--epoch:{i}){{.token-slot-{i}{{transition-property:none}}}}"
            f"body:has(#token-{i}-captured.done) .token-slot-{i}{{transition-property:--saved-token-{i}}}"
            f".feedback-metric-{i}{{width:calc(65536px + (var(--saved-token-{i}) + 1)*8px);view-timeline:--feedback-t{i} inline}}"
            f".feedback-reader{{--feedback-{i}:round(nearest,(524288 / var(--feedback-p-{i}) - 524288 - 65536) / 8 - 1,1)}}"
        )
        css += f"body:has(#token-{i}-captured.done) #capture-epoch-observer{{width:{i}px;height:calc(max(0,var(--saved-token-{i}))*1px)}}"
        if i < capacity:
            css += f"body:has(#token-{i}-advanced.done){{--epoch:{i + 1}}}"
        css += (
            f"@container runtime style(--epoch:{i}){{@container headstate style(--head-output-epoch:{i}){{"
            f"body:has(#run:checked) #token-{i}-ready{{animation:native-handshake 1ms both}}"
            "@container headstate style(--winner:50256){body:has(#run:checked) #eos-ready{animation:native-handshake 1ms both}}}}"
            f"@container headstate not style(--winner:50256){{body:has(#run:checked):has(#token-{i}-captured.done) #token-{i}-ack{{animation:native-handshake 1ms both}}}}"
        )
    css += (
        ".feedback-reader{animation-name:"
        + ",".join(f"feedback{i}" for i in range(1, capacity + 1))
        + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
        + ",".join(timelines)
        + "}"
    )
    if r6p.TYPED:
        # R6P: registrations live here so the head-isolation wall resets them; --token becomes the prefill chain
        css += r6p.regs(capacity) + r6p.token_select_css(capacity)
    else:
        css += (
            ".feedback-select{--token:if(style(--epoch:1):var(--frozen-prompt);"
            + ";".join(
                f"style(--epoch:{i}):var(--feedback-{i - 1})"
                for i in range(2, capacity + 1)
            )
            + ";else:var(--frozen-prompt))}"
        )
    signals, metrics = (
        [
            '<g id="eos-ready"></g><g id="eos-done"><set attributeName="class" to="done" begin="eos-ready.animationend+0.001s" fill="freeze"/></g>'
        ],
        [],
    )
    for i in range(1, capacity + 1):
        signals.append(
            f'<g id="token-{i}-ready"></g><g id="token-{i}-ack"></g>'
            f'<g id="token-{i}-captured"><set attributeName="class" to="done" begin="token-{i}-ready.animationend+0.001s" fill="freeze"/></g>'
            f'<g id="token-{i}-advanced"><set attributeName="class" to="done" begin="token-{i}-ack.animationend+0.001s" fill="freeze"/></g>'
        )
        metrics.append(f'<i class="feedback-metric feedback-metric-{i}"></i>')
    output = (
        '<div class="token-state"><svg xmlns="http://www.w3.org/2000/svg" class="native-signals">'
        + "".join(signals)
        + '</svg><div class="feedback-scroller"><div class="feedback-track">'
        + "".join(metrics)
        + '</div></div><i id="head-epoch-observer" style="position:fixed;top:-30px;width:calc(var(--head-output-epoch)*1px);height:calc(max(0,var(--winner))*1px)"></i><i id="capture-epoch-observer" style="position:fixed;top:-100000px;visibility:hidden"></i><output class="token-display" id="tokens"></output></div>'
    )
    for i in reversed(range(1, capacity + 1)):
        output = f'<div class="token-slot-{i}">{output}</div>'
    source = (
        '<div class="feedback-reader"><div class="feedback-select">{child}</div></div>'
    )
    if synthetic:
        css += (
            ".token-display::after{content:"
            + ' " " '.join(f"counter(token{i})" for i in range(1, capacity + 1))
            + ";counter-reset:"
            + " ".join(
                f"token{i} var(--saved-token-{i})" for i in range(1, capacity + 1)
            )
            + "}"
        )
    return source, output, css, timelines


def font_barrier(stylesheet, directory):
    """Default-axis metric witnesses for every face, including size-adjust."""
    manifest_path = directory / "font-witnesses.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifests, anchors, probes, witnesses = {}, [], [], []
    css = ".font-witness{position:fixed;top:-100000px;left:0;display:block;width:max-content;height:1px;font-variation-settings:normal;font-kerning:none;font-style:normal;white-space:pre}.font-proof{position:fixed;top:-100000px;left:0;height:1px}"
    faces = re.findall(r"@font-face\{([^{}]+)\}", stylesheet)
    for i, face in enumerate(faces):
        family = re.search(r"font-family:([^;]+)", face)[1]
        url = re.search(r'url\("([^\"]+)"\)', face)[1]
        path = Path(unquote(urlparse(url).path))
        adjust = re.search(r"size-adjust:([.\d]+)%", face)
        adjust = float(adjust[1]) / 100 if adjust else 1
        key = str(path)
        if key in previous and previous[key]["mtime"] == path.stat().st_mtime_ns:
            info = previous[key]
        else:
            with TTFont(path, lazy=True) as font:
                cmap = font.getBestCmap()
                if r6p.TYPED and r6p.is_tokenizer_font(path):
                    cp = r6p.barrier_codepoint(font, cmap)  # R6P: printable witness glyph (TAB expands to tab stops)
                else:
                    cp = next(c for c in sorted(cmap) if font["hmtx"][cmap[c]][0] > 1)
                info = {
                    "codepoint": cp,
                    "advance": font["hmtx"][cmap[cp]][0],
                    "upem": font["head"].unitsPerEm,
                    "mtime": path.stat().st_mtime_ns,
                }
        manifests[key] = info
        expected = info["advance"] / info["upem"] * 4 * adjust
        anchors.append(f"--font-proof-{i}")
        probes.append(
            f'<i class="font-witness" style="font-family:{family};font-size:4px;anchor-name:--font-witness-{i}">&#x{info["codepoint"]:X};</i>'
        )
        witnesses.append(f'<i class="font-proof font-proof-{i}"></i>')
        css += f".font-proof-{i}{{anchor-name:--font-proof-{i};width:clamp(0px,1px - max(0px,abs(anchor-size(--font-witness-{i} width,0px) - {expected:.8g}px) - .125px)*1024,1px)}}"
    reductions, rules, anchor = reduce_geometry(anchors, "font-all", "min")
    css += rules
    css += f".font-status{{position:fixed;left:0;top:0;container:fontready/inline-size;width:anchor-size({anchor} width,0px);height:1px}}"
    css += "@container fontready (min-width:.99px){#fonts-detected{animation:native-handshake 1ms both}}"
    signals = '<div class="font-status"><svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="fonts-detected"></g><g id="fonts-loaded"><set attributeName="class" to="done" begin="fonts-detected.animationend+0.001s" fill="freeze"/></g></svg></div>'
    if r6v.FONT_COUNT:  # R6V: N-of-283 loaded-fonts counter (sum of the proof widths) + its panel
        sum_html, sum_css, sum_anchor = r6v.sum_tree(anchors)
        reductions += sum_html
        css += sum_css + r6v.load_panel_css(sum_anchor, len(faces))
        signals += r6v.load_panel_html(len(faces))
    manifest_path.write_text(json.dumps(manifests))
    return "".join(probes + witnesses) + reductions + signals, css, len(faces)


def compile_runtime(
    directory,
    blocks,
    capacity,
    autostart=False,
    isolate_head=False,
    cache_layout="nested",
    cache_codec="scalar",
    liveness=False,
    uncached_style=False,
    scoped_state=False,
    reuse_core=False,
    detached_output=False,
    kv_window=None,
    kv_sinks=0,
    isolate_metrics=False,
    teacher_forced_tokens=None,
    font_backend="original",
    value_layout="runs",
    global_projection=False,
    value_weight_once=True,
):
    if global_projection and not reuse_core:
        raise ValueError("Global projection currently requires the reused core")
    if value_layout != "runs" and (not reuse_core or cache_codec != "font-vector"):
        raise ValueError("Fallback value layout requires the reused font-vector core")
    if font_backend not in ("original", "fontations-core", "fontations"):
        raise ValueError("Unknown font backend")
    if teacher_forced_tokens is not None and (
        len(teacher_forced_tokens) < capacity
        or any(type(t) is not int or not 0 <= t < 50257 for t in teacher_forced_tokens)
    ):
        raise ValueError(
            "Teacher-forced fixtures need at least capacity valid input token IDs"
        )
    if isolate_metrics and not reuse_core:
        raise ValueError("Metric state isolation currently requires the reused core")
    if (kv_window is not None or kv_sinks) and (
        not reuse_core or cache_codec != "font-vector"
    ):
        raise ValueError("Bounded KV requires the reused font-vector core")
    if cache_codec in ("geometry", "font-vector") and not reuse_core:
        raise ValueError("Geometry and font-vector caches require the reused core")
    if reuse_core:
        from browser_gpt2_reused_adapter import compile_reused_runtime_core

        if cache_layout != "flat" or liveness or uncached_style:
            raise ValueError(
                "Reusable runtime requires flat cache and no liveness/cache-policy ablations"
            )
        core, core_css, metadata = compile_reused_runtime_core(
            blocks,
            capacity,
            cache_codec,
            scoped_state,
            kv_window,
            kv_sinks,
            isolate_metrics,
            value_layout,
            global_projection,
            value_weight_once,
        )
    else:
        core, core_css, metadata = compile_core(
            blocks,
            capacity,
            cache_layout,
            packed_cache_enabled=False if cache_codec == "scalar" else cache_codec,
            isolate_cache=liveness,
            liveness=liveness,
            uncached_style=uncached_style,
            scoped_state=scoped_state,
        )
    embedding, embed_css = compile_embedding(with_epoch=True)
    head_dir = ROOT / "experiments/browser-gpt2/head-two-pass"
    head = (head_dir / "head-body.html").read_text()
    head_css = (head_dir / "head.css").read_text()
    if capacity > 8:
        head, head_css = split_head_receipt(head, head_css)
    head_bank_regs = head_bank_decls = ""
    if f4.PACKED_HEAD:
        # F4: the head reads its 768 inputs only through two identical
        # font-variation-settings lists; latch that list once instead of 768 numbers.
        head_css, head_bank_regs, head_bank_decls = f4.pack_head_input(head_css)
    if r3h.BLOCKFLOW_MAX:
        # R3H #1 (#176): coarse groups become block containers of in-flow
        # zero-height rows; a block's max-content width is the max child width,
        # i.e. the same quantity the single max-content grid track computed.
        head_css = r3h.blockflow_max(head_css)
    front, output, control_css, timeline_names = feedback(capacity)
    output_receiver = ""
    if detached_output:
        # Keep token retention and feedback outside the scorer's lifecycle.
        # The paired geometry bridge publishes only the winner and its epoch.
        output_receiver = (
            '<div class="detached-head-reader"><div class="detached-head-state">'
            + output
            + "</div></div>"
        )
        output = '<i class="detached-head-source"></i>'
    tensors = SafeTensors(MODEL_PATH)
    if font_backend == "fontations-core":
        from browser_gpt2_font_backend import fontations_stylesheet

        core_css = fontations_stylesheet(core_css)
    css = core_css + embed_css + head_css + control_css
    if font_backend == "fontations":
        from browser_gpt2_font_backend import fontations_stylesheet

        css = fontations_stylesheet(css)
    if reuse_core:
        css += "body{container-name:runtime loopcontrol}"
    # Only the first block waits for the new token embedding receipt. Keep the
    # final head and feedback sources alive throughout subsequent core epochs.
    if isolate_head:
        # Registered h values have already been resolved on the bank. Clear
        # scratch/cache/input inheritance once, before the 50k scoring rows.
        reset = sorted(set(re.findall(r"@property (--[\w-]+)", css)))
        reset += ["--final-mean", "--final-var"] + hybrid.names("final-h", 768)
        reset = [
            p
            for p in reset
            if not re.fullmatch(r"--h\d+", p)
            and p != "--head-input-epoch"
            # F4: the packed head list must cross the wall; --hq-* never inherit
            and p != "--head-fvs"
            and not re.fullmatch(r"--hq-\d+", p)
            and not re.fullmatch(r"--fvn-[kv]-\d+-\d+", p)
            # R2C: hoisted list quotients are inherits:false scratch; no wall needed
            and not p.startswith(r2c.PREFIX)
            # F2: inherits:false fc scratch cannot reach the head; no wall needed
            and not re.fullmatch(r"--f[zt]-\d+", p)
        ]
        css += (
            ".head-isolation{"
            + ";".join(f"{p}:initial" for p in reset)
            + ";font:12px monospace;font-variation-settings:normal}"
        )
        head = '<div class="head-isolation">' + head + "</div>"
    if not reuse_core:
        core = core.replace(
            '<div class="core-block" id="block-0">',
            '<div class="core-block" id="block-0"><div class="input-ready">',
            1,
        )
        # Add the matching close before the next sibling/last receiver, not inside
        # a QKV gate. The additional wrapper is closed at this block's end.
        boundary = core.index("</div>", core.index('id="block-0-result"'))
        # Counting tags gives the exact outer block boundary despite deep nesting.
        depth = 0
        for match in re.finditer(r"</?div\b[^>]*>", core):
            depth += -1 if match[0].startswith("</") else 1
            if depth == 1 and match.start() > boundary:
                core = core[: match.end()] + "</div>" + core[match.end() :]
                break
    css += ".input-ready,.core-block{content-visibility:hidden;contain-intrinsic-size:0px 0px}body:has(#fonts-loaded.done):has(#run-latched.done) .core-block{content-visibility:visible}@container embeddingreceipt style(--embed-ready:1){.input-ready{content-visibility:visible}}"
    css += f".b{blocks - 1}-bridge-gate{{content-visibility:visible!important;display:block!important}}"
    # Final LN uses live residuals, but the scorer retains its completed input
    # until the entire next core result arrives.
    css += hybrid.regs(["--final-mean", "--final-var"] + hybrid.names("final-h", 768))
    norm = b.norm_declarations(
        "x",
        "final-h",
        np.asarray(tensors.tensor("ln_f.weight")),
        np.asarray(tensors.tensor("ln_f.bias")),
        "final-mean",
        "final-var",
    )
    css += ".final-normalization{" + ";".join(norm) + "}"
    if f4.PACKED_HEAD:
        css += head_bank_regs
        css += (
            ".head-input-bank{"
            + head_bank_decls
            + ";--head-input-epoch:calc(var(--epoch)*var(--bridge-ready));transition-property:--head-fvs,--head-input-epoch"
            + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
        )
    else:
        css += (
            ".head-input-bank{"
            + ";".join(f"--h{i}:var(--final-h-{i:03d})" for i in range(768))
            + ";--head-input-epoch:calc(var(--epoch)*var(--bridge-ready));transition-property:"
            + ",".join([f"--h{i}" for i in range(768)] + ["--head-input-epoch"])
            + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}"
        )
    css += f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.head-input-bank{{transition-property:none}}}}"
    # Probes load all head faces independently. Do not lay out the 50k-row
    # scorer on fallback fonts or provisional zero inputs during cold load.
    # The retained epoch never returns to zero after the first complete core,
    # so feedback geometry stays alive throughout subsequent iterations.
    if r2d.HEAD_LOCK:
        # R2D: the head is skipped (style, layout, paint, compositing inputs,
        # hit test) except while --bridge-ready:1, i.e. from the end of layer
        # 11 until the epoch advances. The token slots live outside the head
        # (detached output) and retain the winner by transition, so nothing
        # reads the head's geometry while it is locked.
        if not detached_output:
            raise ValueError("R2D_HEAD_LOCK requires --detached-output")
        css += r2d.head_lock_css(blocks)
    else:
        css += ".head-input-bank{container-name:headinput}.full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}"
    core = core.replace(
        "{child}",
        '<div class="final-normalization"><div class="head-input-bank"><i id="head-input-observer" style="position:fixed;top:-30px;width:calc(var(--head-input-epoch)*1px);height:1px"></i>'
        + head.replace("{child}", output)
        + "</div></div>",
    )
    # Position lookup contains model parameters, not precomputed activations.
    positions = np.asarray(tensors.tensor("wpe.weight")[:capacity], dtype=np.float64)
    css += (
        ".position-embedding{"
        + ";".join(
            f"--x-{i:03d}:calc(var(--embed-{i:03d}) + if("
            + ";".join(
                f"style(--epoch:{e + 1}):{positions[e, i]:.12g}"
                for e in range(capacity)
            )
            + ";else:0))"
            for i in range(768)
        )
        + ";font:12px monospace;font-variation-settings:normal}"
    )
    visible = '<output class="visible-output" id="visible-output"></output>'
    front = front.replace(
        '<div class="feedback-select">', visible + '<div class="feedback-select">'
    )
    model = front.replace(
        "{child}",
        embedding.replace(
            "{child}",
            '<i id="embedding-epoch-observer" style="position:fixed;top:-30px;width:calc(var(--epoch)*var(--embed-ready)*1px);height:1px"></i><div class="position-embedding">'
            + core
            + "</div>",
        ),
    )
    if detached_output:
        model += output_receiver
        css += (
            ".full-head{anchor-scope:none;content-visibility:hidden}"
            ".detached-head-source{position:fixed;left:0;top:-100000px;anchor-name:--detached-head-result;"
            "width:calc(var(--head-output-epoch)*1px);height:calc(max(0,var(--winner))*1px)}"
            ".detached-head-reader{position:fixed;left:0;top:-100000px;container-type:size;"
            "width:anchor-size(--detached-head-result width,0px);height:anchor-size(--detached-head-result height,0px)}"
            ".detached-head-state{--head-output-epoch:round(nearest,100cqi/1px,1);--winner:round(nearest,100cqb/1px,1)}"
            f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.full-head{{content-visibility:visible}}}}"
        )
    if f5.SCOPED_FEEDBACK:
        # F5: the token feedback state lives on .feedback-reader (depth 2,
        # ~71.9k descendants) and is read by two of its children and by
        # .embedding-source. Inherited, every readback restyled the document.
        css = f5.make_private_prefix(
            css, ["--feedback-", "--frozen-prompt", "--token"]
        )
        css += (
            ".feedback-select,.visible-output{--frozen-prompt:inherit;"
            + ";".join(f"--feedback-{i}:inherit" for i in range(1, capacity + 1))
            + "}.embedding-source{--token:inherit}"
        )
    if f5.SCOPED_EPOCH and reuse_core and f5.SCOPED_HANDSHAKE:
        # F5: body{--epoch} inherited into all 72k elements (P2: the whole-DOM
        # pass at token-N-ack). Stamp the epoch onto its nine readers instead.
        # Core-internal readers use the pass counter (pass-reader, adapter).
        epoch_readers = ",".join(
            [
                ".epoch-reader",
                ".embedding-receipt",
                ".position-embedding",
                ".feedback-select",
                ".head-input-bank",
                f".b{blocks - 1}-bridge-receipt",
            ]
        )
        for e in range(1, capacity + 1):
            css += f"@container runtime style(--epoch:{e}){{{epoch_readers}{{--epoch:{e}}}}}"
        css = f5.make_private(css, ["--epoch"])
        model, tagged = f5.tag_inline_readers(
            model, "var(--epoch)", "epoch-reader", skip_class="pass-reader"
        )
        if tagged != (3 if r5e.KEEP_DIAG else 2):  # R5E: #core-probe's epoch twin
            raise ValueError(f"Unexpected inline epoch readers in model: {tagged}")
    r6p_font_info = None
    if r6p.TYPED:
        # R6P: the tokenizer fonts join the font barrier; the model nests under the tokenizer chain
        r6p_font_info = r6p.check_fonts()
        css += r6p.font_faces_css()
        model = r6p.wrap_model(model)
        _marker_old = 'width:calc(20000px + var(--epoch)*1024px)'  # R6X v5: token-fresh receipt (see apply_conflicts.py edit 6)
        _marker_new = 'width:calc(20000px + (var(--epoch) - 1 + var(--prompt-live))*1024px)'
        if model.count(_marker_old) != 1:
            raise ValueError(f'R6X: expected exactly one embedding epoch marker, found {model.count(_marker_old)}')
        model = model.replace(_marker_old, _marker_new, 1)
    font_html, font_css, font_count = font_barrier(css, directory)
    css += font_css
    scopes = re.findall(r"html\{timeline-scope:([^}]+)\}", css)
    all_timelines = sorted(
        set(timeline_names + [t for s in scopes for t in s.split(",")])
    )
    css += "html{timeline-scope:" + ",".join(all_timelines) + "}"
    codec = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
    css += (
        "@counter-style gpt2-vocabulary{system:fixed 0;symbols:"
        + " ".join(css_string(codec.decode_token(t)) for t in range(50257))
        + ';suffix:"";fallback:decimal}'
    )
    css += (
        ".visible-output::after{counter-reset:"
        + " ".join(f"token{i} var(--display-token-{i})" for i in range(1, capacity + 1))
        + ";content:"
        + " ".join(f"counter(token{i},gpt2-vocabulary)" for i in range(1, capacity + 1))
        + "}"
    )
    # Future slots are omitted by writing an empty counter symbol at index -1.
    css = css.replace("system:fixed 0;symbols:", 'system:fixed -1;symbols:"" ')
    css += (
        ".visible-output{position:fixed;top:110px;left:24px;right:24px;font:20px/1.6 system-ui;white-space:pre-wrap;"
        + ";".join(f"--display-token-{i}:-1" for i in range(1, capacity + 1))
        + "}"
    )
    if r6p.TYPED:
        css += r6p.display_css()  # R6P: typed text / decoded prompt tokens + echo fix
    elif r6p.ECHO_FIX:
        css += r6p.echo_fix_css()  # R6P (A): the pseudo-element does not inherit the private --frozen-prompt
    else:
        css += ".visible-output::before{counter-reset:prompt var(--frozen-prompt);content:counter(prompt,gpt2-vocabulary)}"
    css += 'body:has(#eos-done.done) .status::after{content:"Complete • end of text"}'
    for i in range(1, capacity + 1):
        if r6p.TYPED:
            css += r6p.display_token_rule(i)  # R6P: prefill winners hidden
        else:
            css += f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:var(--feedback-{i})}}"
    css += f'body{{margin:24px;font:16px/1.5 system-ui;background:#f7f5ef;color:#222}}.controls{{position:fixed;left:24px;top:16px;z-index:100}}body:has(#run-latched.done) select{{pointer-events:none;opacity:.6}}.status::after{{content:"Loading model fonts…"}}body:has(#fonts-loaded.done) .status::after{{content:"Ready • {blocks}-block native compute"}}'
    css += f'body:has(#token-{capacity}-captured.done) .status::after{{content:"Complete • {capacity} tokens"}}'
    options = [15496, 464, 40, 32, 1212, 2061]
    for token in options:
        css += f'body:has(option[value="{token}"]:checked){{--prompt-token:{token}}}'
    controls = (
        '<div class="controls"><label>Prompt <select>'
        + "".join(
            f'<option value="{t}">{html_lib.escape(codec.decode_token(t))}</option>'
            for t in options
        )
        + '</select></label> <label><input type="checkbox" id="run" '
        + ("checked" if autostart else "")
        + '>Run / continue</label> <form style="display:inline" action="index.html"><button>Reset</button></form><small class="status"></small></div><i id="runtime-epoch-observer" style="position:fixed;top:-20px;width:calc(var(--epoch)*1px);height:1px"></i>'
    )

    controls += '<svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="run-start"></g><g id="run-latched"><set attributeName="class" to="done" begin="run-start.animationend+0.001s" fill="freeze"/></g></svg>'
    if f5.SCOPED_EPOCH and reuse_core and f5.SCOPED_HANDSHAKE:
        controls, tagged_controls = f5.tag_inline_readers(
            controls, "var(--epoch)", "epoch-reader"
        )
        if tagged_controls != 1:
            raise ValueError(f"Unexpected inline epoch readers in controls: {tagged_controls}")
    speed = (
        "Measured warm speed: about 78 seconds/token on M2 Pro."
        if (blocks, capacity) == (12, 8)
        and cache_codec == "scalar"
        and not liveness
        and not uncached_style
        and not scoped_state
        and not reuse_core
        and not detached_output
        else "Speed depends on the block/context configuration."
    )
    controls += f'<aside style="position:fixed;left:24px;right:24px;top:176px;font:13px/1.5 system-ui;color:#666">Experimental q9/q16 GPT-2 • one prompt token • at most {capacity} generated tokens.<br>HTML/CSS/OpenType + native SVG control. No JavaScript. {speed}</aside>'
    if r6p.TYPED:
        # R6P: editable prompt panel, tokenizer chain, prefill handshakes, display layout
        controls = controls.replace(
            "one prompt token",
            f"typed prompt (first {r6p.SLOTS} BPE tokens; each prefilled token costs one full step) or one dropdown token",
        ).replace('<aside style="', '<aside class="tk-aside" style="')
        controls += r6p.panel_html()
        css += r6p.chain_css() + r6p.prefill_handshake_css() + r6p.panel_css(capacity)
    if teacher_forced_tokens is not None:
        # Known evaluation INPUT IDs, not generated answers or activations.
        # The native embedding, 12-layer loop, KV retention and full head still
        # execute every position. This artifact is not free-running generation.
        css += (
            ".feedback-select{--token:if("
            + ";".join(
                f"style(--epoch:{i + 1}):{token}"
                for i, token in enumerate(teacher_forced_tokens[:capacity])
            )
            + ";else:0)}"
        )
        css += f".feedback-reader{{--frozen-prompt:{teacher_forced_tokens[0]}}}#eos-ready{{animation:none!important}}"
        for i in range(1, capacity):
            css += f"@container headstate style(--winner:50256){{body:has(#run:checked):has(#token-{i}-captured.done) #token-{i}-ack{{animation:native-handshake 1ms both}}}}"
        controls = controls.replace("<select>", "<select disabled>").replace(
            "Experimental q9/q16 GPT-2",
            "Teacher-forced quality fixture: fixed input IDs, not a generated continuation",
        )

    # A static HTTP server can serve this output and its existing font assets.
    # There is no local-file URL dependency and no inference API endpoint.
    def relative_asset(match):
        parsed = urlparse(match[1])
        relative = os.path.relpath(
            Path(unquote(parsed.path)).resolve(), directory.resolve()
        )
        return (
            'url("'
            + quote(relative, safe="/.-_")
            + ("?" + parsed.query if parsed.query else "")
            + '")'
        )

    if r6v.ON:  # R6V: per-token progress reader (first child of .core-controller) + token counter
        model = r6v.insert_progress(model)
        css += r6v.progress_css(blocks, capacity)
    if r2d.OVERFLOW_CLIP:
        css = r2d.overflow_clip(css)
    if r2d.POINTER_EVENTS:
        css += r2d.pointer_events_css()
    if r2d.CONTAIN_PAINT:
        css += r2d.contain_paint_css()
    css = re.sub(r'url\("(file:[^\"]+)"\)', relative_asset, css)
    link = '<link rel="stylesheet" href="runtime.css">'
    head_style, early_panel, body_link = '', '', ''
    if r6v.EARLY_PAINT:  # R6V: paint the controls + loading panel before the big sheet is fetched/parsed
        head_style, early_panel, body_link, link = r6v.inline_style(len(css)), r6v.early_panel_html(len(css)), link, ''
        if r6p.TYPED:  # R6X: the prompt panel (a <style contenteditable>, display:none in the UA sheet) must be visible/editable before the sheet arrives
            head_style = head_style.replace("</style>", r6p.panel_inline_css() + "</style>", 1)
        css += r6v.early_paint_runtime_css()
    if r6p.TYPED and r6v.ON:  # R6X: keep the output text above the fixed footer (.tk-aside, bottom 16px); scroll when longer than the box
        css += "html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}"  # v4: box = content, clamped; never shorter than 4 lines
        css += "html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto}"  # v4: footer right below the output's maximum extent (off-screen in very short windows, never overlapping)
        css += r6x_head_phase_css(blocks)
    if os.environ.get("R6X_SCROLLBAR_FIX", "1") not in ("0", "false", "no", "off"):  # R6X v6 (R7H): headed Chrome's classic scrollbar must not shrink the id-readback scrollport
        css += ".feedback-scroller{scrollbar-width:none}"
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><title>Native GPT-2 • Chromium • no JavaScript</title>' + head_style + link + '</head><body>'
        + controls
        + early_panel
        + body_link
        + font_html
        + model
        + (f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>' if r5e.KEEP_DIAG else '')  # R5E
        + "</body></html>"
    )
    r2g_stats = None
    if r2g.SCOPED_HAS:
        # R2G/R3F: fixed-depth `:has()` arguments for every handshake rule (chains verified against the page).
        css, r2g_stats = r2g.scope_has_arguments(css, page, capacity)
    r5e_stats = None
    if r5e.LEAN_WALLS:
        # R5E: shrink the two inheritance walls to the properties that can be non-initial there
        css, r5e_stats = r5e.lean_walls(css, page)
    (directory / "runtime.css").write_text(css)
    (directory / "index.html").write_text(page)
    metadata.update(
        r2gScopedHas=r2g_stats,
        fontFaces=font_count,
        autostart=autostart,
        head="full-vocabulary-q16-two-pass",
        promptTokens=r6p.SLOTS if r6p.TYPED else 1,
        **r6p.manifest(r6p_font_info),
        generatedTokenLimit=capacity,
        kvStorage="native remembered layout"
        if cache_codec == "geometry"
        else "native delayed whole-head font settings"
        if cache_codec == "font-vector"
        else "native delayed transitions",
        scheduler="CSS receipts and SVG SMIL events",
        isolateHead=isolate_head,
        detachedOutput=detached_output,
        **r2d.manifest(),
        r3hBlockflowMax=r3h.BLOCKFLOW_MAX,
        **r5e.manifest(),
        **r6v.manifest(),
        r5eLeanWallStats=r5e_stats,
        headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
        fontBackend=font_backend,
        teacherForcedInputs=teacher_forced_tokens[:capacity]
        if teacher_forced_tokens is not None
        else None,
        teacherForcedTargets=teacher_forced_tokens[1 : capacity + 1]
        if teacher_forced_tokens is not None
        else None,
    )
    (directory / "manifest.json").write_text(json.dumps(metadata, indent=2))
    print(metadata, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--capacity", type=int, default=8)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument(
        "--isolate-head", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--cache-layout", choices=("nested", "flat"), default="flat")
    parser.add_argument("--liveness", action="store_true")
    parser.add_argument("--uncached-style", action="store_true")
    parser.add_argument("--uncached-vectors", action="store_true")
    parser.add_argument("--scoped-state", action="store_true")
    parser.add_argument("--reuse-core", action="store_true")
    parser.add_argument("--detached-output", action="store_true")
    parser.add_argument(
        "--font-backend",
        choices=("original", "fontations-core", "fontations"),
        default="original",
    )
    parser.add_argument(
        "--teacher-forced-tokens",
        type=Path,
        help="Diagnostic only: static evaluation input IDs, with optional next-token target",
    )
    parser.add_argument("--isolate-metric-state", action="store_true")
    parser.add_argument(
        "--value-layout", choices=("runs", "fallback", "widths"), default="runs"
    )
    # F2 round: both leaf-slimming changes default ON; --no-* restores the old emitter.
    parser.add_argument(
        "--global-projection", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--value-weight-once", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--inline-gelu", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--kv-window",
        type=int,
        help="Optional bounded attention context; changes the attention mask",
    )
    parser.add_argument(
        "--kv-sinks",
        type=int,
        default=0,
        help="Keep this many initial positions outside the recent-token ring",
    )
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
        default="scalar",
    )
    args = parser.parse_args()
    hybrid.INLINE_GELU = args.inline_gelu
    if not 1 <= args.blocks <= 12 or not 2 <= args.capacity <= 32:
        parser.error("blocks must be 1–12; capacity must be 2–32")
    args.output.mkdir(parents=True, exist_ok=True)
    compile_runtime(
        args.output,
        args.blocks,
        args.capacity,
        args.autostart,
        args.isolate_head,
        args.cache_layout,
        args.cache_codec,
        args.liveness,
        "vectors" if args.uncached_vectors else args.uncached_style,
        args.scoped_state,
        args.reuse_core,
        args.detached_output,
        args.kv_window,
        args.kv_sinks,
        args.isolate_metric_state,
        json.loads(args.teacher_forced_tokens.read_text())
        if args.teacher_forced_tokens
        else None,
        args.font_backend,
        args.value_layout,
        args.global_projection,
        args.value_weight_once,
    )


if __name__ == "__main__":
    main()
