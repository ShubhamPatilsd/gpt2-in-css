"""R6V: pure-CSS progress UI (per-token layer bar, token counter, load-time font counter, early first paint).

Everything here is display-only: no model rule, property registration, timeline, handshake or geometry read by the
model changes. Flags (env, default on; `R6V_PROGRESS_UI=0` reproduces the flag-off bundle byte for byte):

  R6V_PROGRESS_UI   master switch (0 -> none of the below is emitted)
  R6V_SMOOTH        cosmetic per-layer fill estimate: a compositor-only `transform:scaleX()` animation restarted by the
                    `--layer` container rule (animation-name keyed to the layer), duration = estimated s/layer
  R6V_EARLY_PAINT   tiny inline <style> in <head> + `<link rel=stylesheet>` moved into <body> after the loading panel,
                    so the loading UI paints before the 37-50 MB sheet is fetched/parsed (Blink: a body sheet blocks the
                    parser/rendering only for content AFTER it)
  R6V_FONT_COUNT    "loading model weights N of 283 fonts": the 283 `.font-proof-i` widths (1px when face i's witness
                    advance matches) are summed by a 16-fan-in anchor-size() calc tree -> `--ld-sum` anchor -> a
                    fixed panel's fill width and an inline-size container whose child reads `N` via 284 range rules

Where the per-token reader lives and why it is cheap (R6V.md §2): `--layer`, `--held` (registered `<number>`,
`inherits:false`) live on `.core-controller`, the `corestate` style container. `@container corestate style(...)` rules
apply only to its descendants, so the reader is inserted as the FIRST CHILD of `.core-controller` (a sibling of
`.core-block`, depth 22, five elements, no inline styles, no custom properties of its own). It is outside `.core-block`
(the model), declares no inherited custom properties (so it shares its parent's inherited-variable trie by pointer),
and is restyled only when a style query result on `.core-controller` changes (Blink recalcs container-query-DEPENDENT
descendants, not the whole subtree) -> +3-5 elements x a few microseconds per layer change.
"""
from __future__ import annotations

import os


def _flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


ON = _flag("R6V_PROGRESS_UI")
SMOOTH = ON and _flag("R6V_SMOOTH")
EARLY_PAINT = ON and _flag("R6V_EARLY_PAINT")
FONT_COUNT = ON and _flag("R6V_FONT_COUNT")

BAR_PX = 480  # bar width; 12 segments of 40 px
HIDE_SELECTOR = "body>:not(.controls):not(.ld)"
LEFT_PX, TOP_PX = 24, 52  # under .controls (top 16), above .visible-output (top 110)
HEAD_SECONDS = 1.9  # R5A: head pass 0.4 + head layout ~1.3 + handshake 0.2 per token (cap 8)


def seconds_per_layer(capacity, epoch):
    """Estimated wall seconds per layer for the token generated at `epoch` (1-based). Cosmetic only.
    cap 8: combined8 15.7-16.1 s/token (RESULTS-round5 B6) minus the head ~1.9 s, /12.
    cap 32: combined8-c32 fit 12.05 + 0.975*k s/token (R5X.md §4, prompt 40) minus the head, /12."""
    if capacity <= 8:
        return round((15.9 - HEAD_SECONDS) / 12, 2)
    return round(max(1.0, (12.05 + 0.975 * epoch - HEAD_SECONDS) / 12), 2)


# ---------------------------------------------------------------- per-token progress (reader inside .core-controller)
def progress_html():
    return (
        '<div class="pg"><span class="pg-text"><i class="pg-tok"></i><i class="pg-lay"></i></span>'
        '<span class="pg-bar"><i class="pg-est"></i><i class="pg-exact"></i><i class="pg-seg"></i></span></div>'
    )


def insert_progress(model_html):
    marker = '<div class="core-controller">'
    if model_html.count(marker) != 1:
        raise ValueError(f"R6V: expected exactly one .core-controller, found {model_html.count(marker)}")
    return model_html.replace(marker, marker + progress_html(), 1)


def progress_css(blocks, capacity):
    seg = BAR_PX / blocks
    css = (
        # The box: fixed to the viewport (no ancestor of .core-controller is transformed / contain:paint / clipped),
        # all font properties reset (ancestors set font:1000px EmbeddingLookup / 12px monospace / font-kerning:none).
        f".pg{{position:fixed;left:{LEFT_PX}px;top:{TOP_PX}px;width:{BAR_PX}px;display:none;z-index:90;"
        "font:13px/1.4 system-ui;font-kerning:auto;font-variation-settings:normal;font-feature-settings:normal;"
        "white-space:nowrap;color:#555;letter-spacing:normal;word-spacing:normal;text-align:left;text-transform:none;"
        "pointer-events:none}"
        ".pg-text{display:block;height:18px}"
        ".pg-tok,.pg-lay{font-style:normal}"
        f".pg-bar{{position:relative;display:block;height:8px;width:{BAR_PX}px;margin-top:4px;background:#e3ded2;overflow:hidden}}"
        ".pg-est,.pg-exact,.pg-seg{position:absolute;left:0;top:0;height:100%;display:block}"
        f".pg-est{{width:100%;background:#b7d0ea;transform-origin:0 50%;transform:scaleX(0)}}"
        ".pg-exact{width:0;background:#2b6cb0}"
        f".pg-seg{{width:100%;background:repeating-linear-gradient(to right,transparent 0 {seg - 2:g}px,#f7f5ef {seg - 2:g}px {seg:g}px)}}"
        # visible only while generating (fonts loaded AND run latched), hidden again when the run completes
        "body:has(#fonts-loaded.done):has(#run-latched.done) .pg{display:block}"
        f"body:has(#token-{capacity}-captured.done) .pg,body:has(#eos-done.done) .pg{{display:none}}"
    )
    # token counter: --epoch lives on body (container `runtime`, inherits:false); epoch k = generating token k
    for e in range(1, capacity + 1):
        css += f'@container runtime style(--epoch:{e}){{.pg-tok::after{{content:"token {e} of {capacity}"}}}}'
    # exact layer progress: --layer = mod(pass-1, blocks) on .core-controller (container `corestate`)
    for k in range(blocks):
        css += (
            f"@container corestate style(--layer:{k}){{"
            f'.pg-lay::after{{content:" · layer {k + 1} of {blocks}"}}'
            f".pg-exact{{width:{k * 100 / blocks:.6g}%}}"
            + (f".pg-est{{animation-name:pg-est-{k}}}" if SMOOTH else "")
            + "}"
        )
    # --held:1 = all `blocks` passes of this token done, waiting for the head + token handshake
    css += (
        '@container corestate style(--held:1){.pg-lay::after{content:" · 12 layers done · vocabulary head"}'
        ".pg-exact{width:100%}" + (".pg-est{animation-name:none}" if SMOOTH else "") + "}"
    ).replace("12 layers", f"{blocks} layers")
    if SMOOTH:
        # Estimate: a compositor-only transform animation from k/blocks to (k+1)/blocks over the estimated s/layer;
        # restarted by the animation-name change above; saturates at the segment boundary if the layer runs long.
        css += (
            f".pg-est{{will-change:transform;animation-duration:{seconds_per_layer(capacity, 1)}s;"
            "animation-timing-function:linear;animation-fill-mode:forwards}"
        )
        for k in range(blocks):
            css += f"@keyframes pg-est-{k}{{from{{transform:scaleX({k / blocks:.6g})}}to{{transform:scaleX({(k + 1) / blocks:.6g})}}}}"
        if capacity > 8:
            for e in range(1, capacity + 1):
                css += f"@container runtime style(--epoch:{e}){{.pg-est{{animation-duration:{seconds_per_layer(capacity, e)}s}}}}"
    return css


# ---------------------------------------------------------------- load-time indicator (font barrier -> N of 283)
def sum_tree(anchors, prefix="ld-sum", fan_in=16):
    """Like browser_gpt2_head.reduce_geometry but width = calc(sum of the anchor widths). Returns html, css, anchor."""
    html, css, level = [], [], 0
    current = list(anchors)
    while len(current) > 1:
        following = []
        for start in range(0, len(current), fan_in):
            group = current[start : start + fan_in]
            name = f"--{prefix}-{level}-{start // fan_in}"
            cls = name[2:]
            terms = " + ".join(f"anchor-size({a} width,0px)" for a in group)
            html.append(f'<i class="{prefix} {cls}"></i>')
            css.append(f".{cls}{{anchor-name:{name};width:calc({terms})}}")
            following.append(name)
        current = following
        level += 1
    css.insert(0, f".{prefix}{{position:fixed;top:-100000px;left:0;height:1px}}")
    return "".join(html), "".join(css), current[0]


def load_panel_html(faces):
    """Fonts-phase panel; placed AFTER the font barrier so its anchor-size() reads precede it in tree order.
    Every anchored child is position:fixed (containing block = the initial containing block, exactly like the barrier's
    own `.font-status` reader), so no new anchor-acceptability case is introduced."""
    return (
        '<div class="ld2"><i class="ld-probe"><i class="ld-n"></i></i>'
        '<i class="ld-track"></i><i class="ld2-fill"></i></div>'
    )


def load_panel_css(sum_anchor, faces):
    css = (
        ".ld2{display:block;pointer-events:none}"
        f".ld-probe{{position:fixed;left:{LEFT_PX}px;top:{TOP_PX}px;height:18px;width:anchor-size({sum_anchor} width,0px);"
        "container:fontload/inline-size;z-index:90}"
        f".ld-n{{position:absolute;left:0;top:0;width:{BAR_PX}px;display:block;font:13px/1.4 system-ui;color:#555;white-space:nowrap;font-style:normal}}"
        f'.ld-n::after{{content:"Loading model weights: 0 of {faces} fonts"}}'
        f".ld-track{{position:fixed;left:{LEFT_PX}px;top:{TOP_PX + 22}px;display:block;height:8px;width:{BAR_PX}px;background:#e3ded2;z-index:90}}"
        f".ld2-fill{{position:fixed;left:{LEFT_PX}px;top:{TOP_PX + 22}px;display:block;height:8px;background:#2b6cb0;z-index:91;"
        f"width:calc(anchor-size({sum_anchor} width,0px)*{BAR_PX / faces:.6g})}}"
        "body:has(#fonts-loaded.done) .ld2{display:none}"
        ".ld{display:none}"  # the CSS-phase panel (inline <style>) disappears once this sheet applies
    )
    for n in range(1, faces + 1):
        css += f'@container fontload (min-width:{n}px){{.ld-n::after{{content:"Loading model weights: {n} of {faces} fonts"}}}}'
    return css


def early_panel_html(css_bytes):
    mb = css_bytes / 1e6
    return (
        '<div class="ld"><span class="ld-label">Loading the model’s stylesheet '
        f"({mb:.0f} MB of CSS)…</span><span class=\"ld-track\"><i class=\"ld-slide\"></i></span></div>"
    )


def inline_style(css_bytes):
    """Head <style>: only what the pre-sheet content needs. Everything here is repeated/overridden by runtime.css."""
    return (
        "<style>"
        "body{margin:24px;font:16px/1.5 system-ui;background:#f7f5ef;color:#222}"
        ".controls{position:fixed;left:24px;top:16px;z-index:100}"
        '.status::after{content:"Loading stylesheet…"}'
        f".ld{{position:fixed;left:{LEFT_PX}px;top:{TOP_PX}px;width:{BAR_PX}px;font:13px/1.4 system-ui;color:#555;white-space:nowrap}}"
        ".ld-label{display:block;height:18px}"
        f".ld-track{{position:relative;display:block;height:8px;width:{BAR_PX}px;margin-top:4px;background:#e3ded2;overflow:hidden}}"
        # indeterminate slide; transform-only so it keeps moving on the compositor while the main thread parses the sheet
        ".ld-slide{position:absolute;left:0;top:0;height:100%;width:25%;display:block;background:#2b6cb0;will-change:transform;"
        "animation:ld-slide 1.6s linear infinite}"
        "@keyframes ld-slide{from{transform:translateX(-100%)}to{transform:translateX(400%)}}"
        # A body <link> is not render-blocking in Blink (HTML: only parser-inserted sheets in <head> are), so until
        # runtime.css applies the ~67k model elements would be styled and laid out UNSTYLED once. Lock every other body
        # child (content-visibility:hidden skips style+layout of the subtree; the children themselves are ~600 empty
        # boxes); runtime.css lifts the lock with the same selector (later sheet wins). Exactly the state the head
        # <link> gives today: nothing of the model is laid out before the sheet.
        + HIDE_SELECTOR + "{content-visibility:hidden}"
        "</style>"
    )


def early_paint_runtime_css():
    """Appended to runtime.css: lifts the inline sheet's lock (same selector, later in cascade order -> wins)."""
    return HIDE_SELECTOR + "{content-visibility:visible}"


def manifest():
    return {
        "r6vProgressUi": ON,
        "r6vSmooth": SMOOTH,
        "r6vEarlyPaint": EARLY_PAINT,
        "r6vFontCount": FONT_COUNT,
    }
