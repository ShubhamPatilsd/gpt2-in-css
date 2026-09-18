"""Connect the reusable native core to the existing autonomous token loop.

One rendering graph executes all layers. A completed last-layer pass cannot
advance into the next token until the full head captures that token. No external
ticks, cached reference activations, or JavaScript participate in this handshake.
"""

import re

import build_hybrid_twelve_block as hybrid
from browser_gpt2_reused_core import compile_reused


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
    for token in range(1, capacity):
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
    source, receiver, bridge_css, _ = hybrid.bridge(last, 512)
    source = source.replace("var(--epoch)", "var(--position)")
    export = (
        '<div class="reused-final-export">'
        + hybrid.probe(f"block-{last}-probe", "out", 768).replace(
            "var(--epoch)", "var(--position)"
        )
        + source
        + "</div>"
    )
    needle = '<div class="reused-output" id="reused-result">'
    if body.count(needle) != 1:
        raise ValueError("Missing unique shared-core output")
    body = body.replace(needle, needle + export)
    css += bridge_css
    # Center the added output transport just like the shared context bridge.
    css = re.sub(
        r"524288 / var\((--bridge-p-\d+)\)",
        r"1572864 / (var(\1) + 2)",
        css,
    )
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
        + hybrid.probe("core-probe", "x", 768)
        + "{child}</div>",
    )
    body = (
        '<div class="core-controller"><div class="core-block" id="block-0">'
        + body
        + "</div></div>"
        + receiver
    )
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
        "kvStorage": "native remembered layout"
        if codec == "geometry"
        else "native delayed whole-head font settings"
        if codec == "font-vector"
        else "native delayed transitions",
    }
    return body, css, metadata
