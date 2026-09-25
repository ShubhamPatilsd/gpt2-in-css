"""Connect the reusable native core to the existing autonomous token loop.

One rendering graph executes all layers. A completed last-layer pass cannot
advance into the next token until the full head captures that token. No external
ticks, cached reference activations, or JavaScript participate in this handshake.
"""

import re

import build_hybrid_twelve_block as hybrid
import f4_packing as f4
import f5_scoping as f5
import r2c_hoist as r2c
from browser_gpt2_reused_core import compile_reused
import r2f_lean_handshake as r2f
import r3r_fold_hop as r3r
import r4s_small_hops as r4s
import r5h_ch_scores as r5h  # R5H: forces r4s.SMALL_HOPS off when R5H_CH_SCORES is on
import r4d_flags as r4d
import r4t_consumer_chunk as r4t
import r5e_dead_weight as r5e


def compile_reused_runtime_core(
    blocks,
    capacity,
    codec="integer10",
    scoped_state=True,
    kv_window=None,
    kv_sinks=0,
    isolate_metrics=False,
    value_layout="runs",
    global_projection=False,
    value_weight_once=True,
):
    body, css = compile_reused(
        blocks,
        capacity,
        codec,
        centered_context=True,
        scoped_state=scoped_state,
        kv_window=kv_window,
        kv_sinks=kv_sinks,
        isolate_metrics=isolate_metrics,
        value_layout=value_layout,
        global_projection=global_projection,
        value_weight_once=value_weight_once,
    )
    # The enclosing token controller owns root --epoch. Only matrix generation
    # receipts use the finer-grained pass counter, scoped to the shared core.
    css = css.replace("--epoch:var(--pass);", "")
    css += (
        ".reused-input{--epoch:var(--pass)}.loop-reader{"
        + ";".join(f"--input-{i}:var(--x-{i:03d})" for i in range(768))
        + "}"
    )
    css = css.replace(
        "@container runtime style(--layer:0){.loop-input{--loop-ready:1;",
        "@container runtime style(--layer:0){.loop-input{--loop-ready:var(--embed-ready);",
    )
    if r3r.FOLD_HOP:
        pass  # R3R: r3r.loop_parts() already emits the lean controller (no relay, --pass-cap)
    elif r2f.LEAN_HANDSHAKE:
        # R2F: the controller reads the bank pass markers itself; no SMIL relay,
        # no pulse-end / pass-advance frames. Token boundaries raise --pass-cap.
        css = r2f.apply_css(css, blocks, capacity)
        body = r2f.apply_body(body)
    for token in range(1, capacity):
        if r2f.LEAN_HANDSHAKE or r3r.FOLD_HOP:
            break
        step = token * blocks
        old = f"body:has(#loop-advanced-{step}.done){{--pass:{step + 1}}}"
        new = f"body:has(#token-{token}-advanced.done){{--pass:{step + 1}}}"
        if css.count(old) != 1:
            raise ValueError(f"Missing unique layer/token boundary at pass {step}")
        css = css.replace(old, new)
        # Capture remains active, but advancing at a token boundary is the
        # head's responsibility. This removes a redundant native event as well.
        css = css.replace(
            f"body:has(#loop-captured-{step}.done) #loop-ack-{step}{{animation:loop-pulse 1ms both}}",
            "",
        )

    last = blocks - 1
    source, receiver, bridge_css, _ = hybrid.bridge(last, r4t.chunk(512))  # R4T: b11-bridge consumers
    source = source.replace("var(--epoch)", "var(--position)")
    export = (
        '<div class="reused-final-export">'
        + (hybrid.probe(f"block-{last}-probe", "out", 768).replace(
            "var(--epoch)", "var(--position)"
        ) if r5e.KEEP_DIAG else "")  # R5E: diagnostic readback only
        + source
        + "</div>"
    )
    needle = '<div class="reused-output" id="reused-result">'
    if body.count(needle) != 1:
        raise ValueError("Missing unique shared-core output")
    if r3r.FOLD_HOP:
        # R3R: the export reads the decoded layer output at .loop-input, outside the
        # display-locked .loop-compute, and is shown only while the pass is held.
        body, css = r3r.move_export(body, css, export, last)
    else:
        body = body.replace(needle, needle + export)
    css += bridge_css
    # Center the added output transport just like the shared context bridge.
    css = re.sub(
        r"524288 / var\((--bridge-p-\d+)\)",
        r"1572864 / (var(\1) + 2)",
        css,
    )
    if not r3r.FOLD_HOP:
        css += f".reused-final-export{{display:none}}@container runtime style(--layer:{last}){{.reused-final-export{{display:block}}}}"
    # Per-layer controller changes must not invalidate the 50k-row vocabulary
    # sibling. Keep root-only query state non-inherited and explicitly publish
    # just the current pass into the core. Token epoch still inherits normally.
    private_control = {
        "--pass",
        "--layer",
        "--loop-phase",
        "--loop-captured-pass",
        "--loop-held",
    }
    css = re.sub(
        r"@property (--[\w-]+)\{[^{}]+\}",
        lambda m: (
            m[0].replace("inherits:true", "inherits:false")
            if m[1] in private_control
            else m[0]
        ),
        css,
    )
    css = css.replace("var(--pass)", "var(--native-pass)")
    css = re.sub(
        r"body\{[^{}]*\}",
        lambda m: m[0].replace("var(--native-pass)", "var(--pass)"),
        css,
    )
    css += hybrid.regs(["--native-pass"])
    if f5.SCOPED_HANDSHAKE:
        # F5: the pass counter and the layer handshake flags are read by a
        # handful of elements but, inherited, restyled the whole open core
        # (P2 Table 3: ~12.27k-element passes). Register them non-inherited
        # and stamp the current pass directly onto every reader.
        receipts = [
            f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
        ] + [".cache-bridge-receipt"] + ([] if r5h.no_score_hop() else [".fvs-score-receipt"])
        pass_readers = ",".join(
            [
                ".loop-input",
            ]
            + ([] if r3r.FOLD_HOP else [".loop-bank-0", ".loop-bank-1"])
            + [
                ".reused-input",
                ".fvs-query",
                ".fvs-score-reader",
                ".pass-reader",
            ]
            + receipts
        )
        for step in range(1, blocks * capacity + 1):
            css += f"@container loopcontrol style(--pass:{step}){{{pass_readers}{{--native-pass:{step}}}}}"
        css += (
            ",".join([".pass-reader"] + receipts) + "{--epoch:var(--native-pass)}"
            ".reused-input,.core-valid,.fvs-query,.fvs-score-reader,.pass-reader{--position:calc(round(down,calc((var(--native-pass) - 1) / "
            + str(blocks)
            + "),1) + 1)}"
        )
        css = f5.make_private(
            css, ["--loop-ready", "--loop-ack", "--native-pass", "--position"]
        )
        body, tagged = f5.tag_inline_readers(body, "var(--epoch)", "pass-reader")
        body, tagged_position = f5.tag_inline_readers(
            body, "var(--position)", "pass-reader"
        )
        # R4S / R5H: the score stamp marker (one inline var(--epoch) reader) no longer exists
        diag = 1 if r5e.KEEP_DIAG else 0  # R5E: the reused-probe / block-11-probe epoch twins
        if tagged != (6 if r5h.no_score_hop() else 7) - 1 + diag or tagged_position != 1 + diag:  # R5X: R5E x R5H union
            raise ValueError(
                f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
            )
    else:
        for step in range(1, blocks * capacity + 1):
            css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
    # Style-container invalidation itself can cross private-property boundaries.
    # Move per-layer containers off body entirely, outside the head's ancestry.
    css = re.sub(r"\bbody(?=[{:\s])", ".core-controller", css)
    css = css.replace("@container runtime ", "@container corestate ")
    for token in range(1, capacity):
        css = css.replace(
            f".core-controller:has(#token-{token}-advanced.done)",
            f":where(body:has(#token-{token}-advanced.done)) .core-controller",
        )
    # Every pass assignment must have identical specificity so later completed
    # steps supersede earlier ones. The external-token selector has one extra
    # ancestor; :where() prevents that permanent rule from pinning the pass.
    css = re.sub(
        r"\.core-controller:has\((#[^)]+)\)",
        r".core-controller:where(:has(\1))",
        css,
    )
    css += ".core-controller{container-name:loopcontrol corestate}"
    receiver = receiver.replace(
        "{child}",
        '<div id="core-result">'
        + (hybrid.probe("core-probe", "x", 768) if r5e.KEEP_DIAG else "")  # R5E
        + "{child}</div>",
    )
    body = (
        '<div class="core-controller"><div class="core-block" id="block-0">'
        + body
        + "</div></div>"
    )
    if r2f.LEAN_HANDSHAKE or r3r.FOLD_HOP:
        body = r2f.wrap_controller(body)
    body += receiver
    metadata = {
        "blocks": blocks,
        "capacity": capacity,
        "renderingGraphs": 1,
        "coreBackend": "reused",
        "cacheLayout": "flat",
        "cacheCodec": codec,
        "kvWindow": kv_window or capacity,
        "kvSinks": kv_sinks,
        "isolatedMetricState": isolate_metrics,
        "valueLayout": value_layout,
        "globalProjection": global_projection,
        "valueWeightOnce": value_weight_once and value_layout == "runs",
        "fontVectorOperatorVersion": 2 if codec == "font-vector" else None,
        "attentionMask": "full causal"
        if not kv_window or kv_window == capacity
        else "initial sinks plus rolling recent context",
        "scopedState": scoped_state,
        "centeredContext": True,
        "dynamicActivationRange": True,
        "runtimeJavaScript": False,
        "liveness": False,
        "uncachedStyle": False,
        "nativeLayerTokenHandshake": True,
        "privateLayerControl": True,
        "localLayerContainer": True,
        "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
        "r3rFoldHop": r3r.FOLD_HOP,
        "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
        "r5hChScores": r5h.CH_SCORES and codec == "font-vector",
        "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
        "f5ScopedEpoch": f5.SCOPED_EPOCH,
        "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
        "f5InlineForward": f5.INLINE_FORWARD,
        "f5BankFilledAliases": f5.BANK_FILLED_ALIASES,
        "f5BankLiteralLists": f5.BANK_LITERAL_LISTS,
        "f4PackedBanks": f4.PACKED_BANKS and codec == "font-vector",
        "f4PackedHead": f4.PACKED_HEAD,
        "f4NumericLists": f4.NUMERIC_LISTS and codec == "font-vector",
        "r4dEmptyUnfilled": r4d.EMPTY_UNFILLED and codec == "font-vector",
        "r4dLeanLatch": r4d.LEAN_LATCH and codec == "font-vector",
        "r4dUnpackV": r4d.UNPACK_V and codec == "font-vector",
        "r4dHideUnfilled": r4d.HIDE_UNFILLED and codec == "font-vector",
        "r4dGateScores": r4d.GATE_SCORES and codec == "font-vector",
        "r2cHoistFvs": r2c.HOIST_FVS,
        "r2cHoistStages": r2c.HOIST_STAGES,
        "r2cHoistQuery": r2c.HOIST_QUERY and codec == "font-vector",
        "r2cHoistEmbedding": r2c.HOIST_EMBEDDING,
        "r4tConsumerChunk": r4t.CHUNK,
        "kvStorage": "native remembered layout"
        if codec == "geometry"
        else "native delayed whole-head font settings"
        if codec == "font-vector"
        else "native delayed transitions",
    }
    return body, css, metadata
