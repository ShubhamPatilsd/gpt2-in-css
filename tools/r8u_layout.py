"""R8U: production page layout (display only). Flag R8U_LAYOUT (default on; 0 -> byte-identical to the R7X build).

v5 (user feedback via the coordinator, 4 rounds): the generated text is the hero; one main row; everything else quiet.

  header   title "GPT-2 in CSS" + one muted line; the status ("Ready • 12-block native compute") small and muted at the title's right
  row      Prompt [dropdown] or type: [the unchanged `.tk-root { --draft-prompt: "…"; }` editor] [Run / continue] [Reset]
           (.controls DOM unchanged except one <details class="r8u-opt"><summary>Options</summary></details> after Reset;
           #run stays body>.controls>label>#run, label:nth-of-type(2) stays Run, the seed/temperature selects stay
           body>.controls>label>#r7b-seed/#r7b-temp; .tk-panel keeps left/right 24px, the editor is offset inside it)
  chips    token chips under the editor, small and muted (count 0 -> a one-line hint)
  options  quiet "Options ▸" line (native <details>, closed by default, no box): Seed, Sampling, readout
  progress smaller text + 4 px bar; the head-phase text shortened, prefill epochs say "absorbed" (UI-only overrides)
  story    .visible-output: 22 px, directly under the progress row
  footer   practical notes (browser, speed, limits) — replaces the old footer text
  Run / continue: page colours inverted (ink pill, paper text, visible checkbox)

The tokenizer chain (.tk-root/.tk-probe/.tk-bridge{width:calc(100vw - 48px)}/.tk-metric 1px), body{margin:24px}, every model
rule and every handshake/control rule are untouched; flag off -> byte-identical.
"""
from __future__ import annotations

import os

ON = os.environ.get("R8U_LAYOUT", "1") not in ("0", "false", "no", "off")

# row tops (px) — v5
HEAD_TOP = 22  # title 22-50 (status small/muted at its right), one-line lede 54-72
CONTROLS_TOP = 90  # main row 90-118: Prompt [dropdown] or type: [editor] [Run / continue] [Reset]
PANEL_TOP = 90  # .tk-panel shares the main row (editor at x = 24 + PROMPT_W + 10)
PROMPT_W = 200  # width of the "Prompt [Hello] or type:" label
EDITOR_W = "clamp(350px,calc(100vw - 560px),560px)"
TOKENS_TOP = 124  # token chips under the editor 124-140
OPTIONS_TOP = 148  # quiet Options line 148-172 (second flex line of .controls)
PROGRESS_TOP = 190  # text 190-206, bar 210-214
OUTPUT_TOP = 230
FOOTER_RESERVE = 80  # 8 px gap + up to 3 footer lines of 18 px + 18 px bottom margin
HIDE_SELECTOR = "body>:not(.controls):not(.ld):not(.tk-panel):not(.r8u-head)"
TITLE = "GPT-2 in CSS"
PROMPT_SLOTS = 4  # R6P_PROMPT_SLOTS (set by the runtime)
INK, PAPER, MUTED, LINE = "#222", "#f7f5ef", "#7a746a", "#d6cfbf"


def output_css():
    """Replaces R6X v4's two sizing rules (same selectors, same order)."""
    return (
        f"html .visible-output{{max-height:calc(100vh - {OUTPUT_TOP + FOOTER_RESERVE}px);min-height:4lh;overflow:auto}}",
        f"html .tk-aside{{top:calc({OUTPUT_TOP + 8}px + max(128px,100vh - {OUTPUT_TOP + FOOTER_RESERVE}px))!important;bottom:auto}}",
    )


def header_html():
    return (
        '<header class="r8u-head">'
        f'<h1 class="r8u-title">{TITLE}</h1>'
        '<p class="r8u-lede">GPT-2 small (124M parameters) running entirely in HTML and CSS — weights in variable fonts, no JavaScript.</p>'
        "</header>"
    )


def footer_html(capacity, new_tokens, prompt_slots):
    per_token = "about 15–45 s per token" if capacity > 8 else "about 15–25 s per token"
    gen = f"{new_tokens} new tokens per run" if new_tokens else f"{capacity} positions per run (prompt + new tokens)"
    return (
        f"Chrome or Edge 139+ · {per_token} · prompts up to {prompt_slots} GPT-2 tokens (ASCII, single spaces; each prompt token "
        f"takes one step) · {gen} · greedy by default, seed and temperature under Options · Reset starts over.<br>"
        "Experimental q9/q16 GPT-2 small: OpenType variable fonts, CSS layout and native SVG timing — no JavaScript, no server compute."
    )


OPTIONS_HTML = '<details class="r8u-opt"><summary>Options</summary></details>'


def ui_css():
    """Presentation rules; emitted in the inline <head> style AND at the end of runtime.css (later -> wins over the older
    .controls{top:16px} rule). No body-anchored :has (the one :has is anchored on .controls and has no #id argument)."""
    opened = ".controls:has(>.r8u-opt[open])"
    ex = PROMPT_W + 10  # editor offset inside .tk-panel (whose box keeps left:24px/right:24px)
    return (
        # header
        f".r8u-head{{position:fixed;left:24px;right:24px;top:{HEAD_TOP}px;margin:0;z-index:100}}"
        f".r8u-title{{display:inline-block;margin:0;font:650 22px/28px system-ui;letter-spacing:-.01em;color:#1a1a1a}}"
        f".r8u-lede{{margin:4px 0 0;font:13.5px/18px system-ui;color:{MUTED};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
        # editor: unchanged look; placed in the main row after "Prompt [Hello] or type:"; its long label kept for a11y only
        ".tk-panel{pointer-events:none}"
        ".tk-panel label{position:absolute;width:1px;height:1px;margin:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}"
        f".tk-editor{{margin-left:{ex}px;width:{EDITOR_W};max-width:none;pointer-events:auto}}"
        # controls: main row + a quiet Options line (second flex line forced by ::before); no cards, page background
        f".controls{{top:{CONTROLS_TOP}px;right:24px;display:flex;flex-wrap:wrap;align-items:center;column-gap:10px;row-gap:0;"
        f"font:13px/1.4 system-ui;color:#444}}"
        ".controls>label{display:inline-flex;align-items:center;gap:8px;white-space:nowrap}"
        f".controls>label:nth-of-type(1){{order:1;box-sizing:border-box;width:{PROMPT_W}px;gap:8px}}"
        f'.controls>label:nth-of-type(1)::after{{content:"or type:";color:{MUTED}}}'
        ".controls>label:nth-of-type(1)>select{width:84px}"
        f".controls>label:nth-of-type(2){{order:2;margin-left:calc({EDITOR_W} + 10px);height:28px;box-sizing:border-box;padding:0 12px 0 10px;"
        f"gap:6px;border-radius:6px;background:{INK};color:{PAPER};font-weight:600;cursor:pointer}}"
        f".controls>label:nth-of-type(2)>input{{margin:0;width:15px;height:15px;accent-color:{PAPER};cursor:pointer}}"
        ".controls>form{order:3}"
        f".controls>.status{{position:absolute;right:0;top:{HEAD_TOP - CONTROLS_TOP + 6}px;font-size:12px;color:{MUTED};white-space:nowrap}}"
        f'.controls::before{{content:"";order:4;flex-basis:100%;height:{OPTIONS_TOP - CONTROLS_TOP - 28}px}}'
        ".controls>.r8u-opt{order:5}"
        f".r8u-opt>summary{{display:block;font:12px/24px system-ui;color:{MUTED};cursor:pointer;list-style:none}}"
        ".r8u-opt>summary::-webkit-details-marker{display:none}"
        '.r8u-opt>summary::after{content:" ▸"}'
        '.r8u-opt[open]>summary::after{content:" ▾"}'
        ".r8u-opt>summary:hover{color:#333}"
        ".controls>label:nth-of-type(3){order:6}.controls>label:nth-of-type(4){order:7}"
        f".controls>.r7b-seed-out{{order:8;margin-left:0;font-size:12px;color:{MUTED};white-space:nowrap}}"
        ".controls>label:nth-of-type(3),.controls>label:nth-of-type(4),.controls>.r7b-seed-out{display:none}"
        f"{opened}>label:nth-of-type(3),{opened}>label:nth-of-type(4){{display:inline-flex;margin-left:8px;font-size:12px;color:{MUTED}}}"
        f"{opened}>.r7b-seed-out{{display:inline;margin-left:8px}}"
        f"{opened}>label:nth-of-type(3)>select,{opened}>label:nth-of-type(4)>select{{height:24px;font-size:12px}}"
        ".controls select,.controls button{box-sizing:border-box;height:28px;font:13px/1 system-ui;color:#222;background:#fff;"
        f"border:1px solid {LINE};border-radius:6px}}"
        ".controls select{padding:0 6px}"
        ".controls button{padding:0 14px;cursor:pointer}"
        ".controls button:hover{background:#efebe2}"
        # loading bars in the page's ink instead of blue (the CSS-phase slide is inline; .ld2-fill lives in the sheet)
        ".ld-slide,.ld2-fill{background:#3d3a35}"
    )


def sheet_css():
    """Sheet-only overrides of display rules that live in runtime.css (token readout, progress, story)."""
    return (
        f"html .tk-tokens{{padding-left:{PROMPT_W + 10}px;font:12px/16px ui-monospace,SFMono-Regular,Menlo,monospace;color:{MUTED};white-space:pre;overflow:hidden;"
        '--tk-label:if(style(--tk-count:0):"nothing typed — Run uses the dropdown prompt";else:"")}'
        f"html .pg{{font-size:12px;color:{MUTED}}}html .pg-text{{height:16px}}html .pg-bar{{height:4px}}"
        "html .pg::before,html .pg::after{top:20px;height:4px}"
        "html .pg-exact{background:#3d3a35}html .pg-est{background:#cfc8b8}html .pg::after{background:#b9864a}"
        '@container corestate style(--held:1){html .pg-lay::after{content:" · vocabulary head (choosing the next token)"}}'
    ) + "".join(  # prefill epochs skip the head (R7B): say so, and keep the head segment idle (R6X's head rule otherwise wins on order)
        f"@container tkprompt style(--prompt-count:{c}){{@container runtime style(--epoch:{e}){{@container corestate style(--held:1){{"
        'html body .pg-lay::after{content:" · absorbed"}html body .pg::after{animation:none}}}}'
        for c in range(2, PROMPT_SLOTS + 1) for e in range(1, c)
    ) + (
        "html .visible-output{font-size:22px;line-height:1.55;color:#1a1a1a}"
        # Run / continue ticked: slightly lighter ink + subtle inset (body-anchored :has like every handshake rule -> R2G-scoped)
        "body:has(#run:checked) .controls>label:nth-of-type(2){background:#4a4743;box-shadow:inset 0 1px 3px rgba(0,0,0,.35)}"
    )


def inline_css():
    return ui_css()
