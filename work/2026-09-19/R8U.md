# R8U — production page layout for demo-c32 / demo-8 (round 8, 2026-10-02)

Agent R8U. Display-only redesign on the live round-7 bundles (R7X §4 recipe). Tools `R8U/tools` = `R7X/tools` + `r8u_layout.py` + flagged hooks
(`R8U_LAYOUT`, default 1). No repo tools/experiments edits, no git, zero JavaScript, no model rule touched. Log `R8U.log.md`.
**Status: built and fully verified, NOT swapped** — the coordinator asked to see the screenshots first. Swap with `R8U/swap.sh`.

## 0. Iterations (user feedback relayed by the coordinator during the round)
v1 `bundles/demo-c32.next` (header + 2 control rows) → v2 `.next-v2` (prompt block under row 1, boxed Seed/Sampling row) → v3 `.next-v3`
(Run pill no longer blue) → v4 `.next-v4` (TinyStories-style simplification; one-line prompt field, Options card) → **v5 `bundles/demo-c32.next-v5` = candidate**
(editor kept exactly as before, no cards, Prompt dropdown visible next to the editor, only Seed/Sampling in a quiet Options disclosure).
v1–v4 left in place in case someone has one open; delete after the swap.

## 1. What v5 changes (all UI)
- Title "GPT-2 in CSS" + one muted line: "GPT-2 small (124M parameters) running entirely in HTML and CSS — weights in variable fonts, no JavaScript."
  Status ("Ready • 12-block native compute" / "Complete • 32 new tokens") small and muted at the top right. <title> "GPT-2 in CSS — no JavaScript".
- One main row: **Prompt [Hello ▾] or type: [`.tk-root { --draft-prompt: "…"; }` editor, unchanged look] [Run / continue] [Reset]**.
  The editor width is clamp(350px, 100vw − 560px, 560px); its long label stays only for a11y.
- Token chips under the editor, small/muted ("[Sh][ub][ham][ was]"; empty → "nothing typed — Run uses the dropdown prompt").
- "Options ▸": a native `<details>` (closed by default, no box) revealing Seed, Sampling and the "greedy (T = 0) · seed N" readout on the same quiet line.
- Run / continue: same pill + visible checkbox + text, page colours inverted (#222 bg, #f7f5ef text/accent); ticked → #4a4743 + inset; dimmed before Ready (existing rule). Reset: light outlined button.
- Progress: 12 px muted text, 4 px bar in the page's ink (estimate light, head segment amber); head phase text " · vocabulary head (choosing the next token)";
  prefill epochs now say " · absorbed" and no longer animate the head segment (fixes a pre-existing display bug: R6X's head text/fill won on prefill epochs).
- Generated text 22 px directly under the progress row (top 230); max-height calc(100vh − 310px); footer top calc(238px + max(128px, 100vh − 310px)).
- Footer = practical notes ("Chrome or Edge 139+ · about 15–45 s per token · prompts up to 4 GPT-2 tokens … · 32 new tokens per run · greedy by default, seed and temperature under Options · Reset starts over." + one line on what it is). The old "at most 36 generated tokens" text is gone.
- Fixed tops: header 22, row 90 (.controls and .tk-panel), chips 124, Options 148, .ld/.ld2/.pg 190, .visible-output and .fb-warn 230.
- How the DOM constraints were kept: `#run` stays body>.controls>label>#run (R2G chains unchanged), label:nth-of-type(2) is still Run, the seed/temperature selects stay
  body>.controls>label>#r7b-seed/#r7b-temp (R7B selectors unchanged). The only new elements are `<header class="r8u-head">` (body child, exempt from the early-paint lock:
  `body>:not(.controls):not(.ld):not(.tk-panel):not(.r8u-head)`, styled in the inline head style) and `<details class="r8u-opt">` inside .controls. .tk-panel keeps
  left/right 24 px (editor offset inside it, panel pointer-events none, editor auto); .tk-bridge, .tk-metric, body margin untouched.
- Implementation: module constants (`r6p.PANEL_TOP/TOKENS_TOP/OUTPUT_TOP`, `r6v.TOP_PX/HIDE_SELECTOR`, `r7h.WARN_TOP`; defaults = old literals) set in the
  R8U block of `browser_gpt2_runtime.py`, plus `r8u.ui_css()` (inline + sheet), `r8u.sheet_css()` (sheet only), header/Options/footer HTML.
- TinyStories study (`R8U/tinystories-study/*.png`): dynamic.html = centred column, title + one muted line, prompt field ("Prompt: \"Once upon a time\"",
  the CSS syntax hidden by translating a 5-line <style>), one row Generate/Edit-reset/Pause + status text + "Show token IDs", story in large monospace below,
  limits note at the bottom; streaming-packed8.html = big title, explanation, Pause + status, the story in large serif, measurement notes below; no dropdown,
  no sampling controls. v4 copied the syntax-hiding field; the user then asked to keep the visible CSS editor, so v5 keeps it.

## 2. Offline verification (logs R8U/logs/) — ALL PASS
| check | result |
|---|---|
| flag-off twins (final tools) | `R8U/twin-c32-off` == bundles/demo-c32, `R8U/twin-8-off` == bundles/demo-8: index.html + runtime.css **byte-identical**; witnesses/manifest identical (agent dir normalised) (flagoff-c32-final.log, flagoff-8-final.log) |
| flag-on vs live (`R8U/check_layout_diff.py`) | c32 v5, demo-8.next, smoke-2L: html after the body <link> byte-identical; pre-link part identical except <title>, inline style, header, Options element, footer text; 64–68 UI rules new/modified (each listed with its declaration diff; positional ones only top/max-height); **model core rules identical in multiset and order** (68,582 / 62,827 / 65,402); witnesses identical; manifest differs only in r2gScopedHas +1 (the Run ticked-state rule, R2G-scoped like every handshake rule) |
| R6X checkers | compare_rules.py: common rules identical in multiset+order; check_v5_identity (copy with .r8u-/.fb-warn/.controls allow-listed): core 67,417 == 67,417 IDENTICAL |
| static no-JS | launch_browser_gpt2.py --check rc 0 (runtimeJavaScript false); 0 <script, 0 on*=, 0 javascript:, CSP script-src 'none' |
| pack dry-run | demo-c32.next-v5 311,787,664 B, demo-8.next 296,896,046 B; all 286 url() resolve |

## 3. Chrome (CHROME.lock via R8U/with_lock.sh; AC power, swap 4.7–7.2 GB from other work → timings labelled, not comparable)
| run | result |
|---|---|
| demo-c32.next-v5 **HEADED 1100×700, classic scrollbars shown, typed "Shubham was" T = 0, full run** (R8U/run-demo-c32.next-v5/) | **35/35** vs R7B/reference_shubham-was_s0_t0.json (32 new 32/32, position 14 = 17132), "Complete • 32 new tokens", --fb-ok 1, agree 36/36, scroller clientWidth 524288; 1,121 s |
| demo-8.next dropdown Hello headless (R8U/run-demo-8.next/) | **8/8** [11 314 1101 7926 11 475 314 1101], fb-ok 1, agree 8/8, "Complete • 8 new tokens" |
| R8U/smoke-r8u-2L (R8U_LAYOUT=1, 2 layers, cap 36) typed "Once upon a time" headless | **35/35** vs R7B/reference_once-upon-a-time_s0_t0_2L.json, fb-ok 1, agree 36/36 |
| layout probes v5, HEADED + scrollbars, typed "Shubham was" (R8U/run-layout-v5-{1100x700,1440x900,900x600}/) | no overlaps, nothing outside the viewport, no ellipsis at any size/shot; early paint at ≈0.5 s (screencast frames cast-*.png show title, row, editor, loading bar); Run started by **keyboard** (focus + Space, 1100) and by **mouse click on the label** (1440, 900): #run:checked + #run-latched.done both true; Options opens/closes by clicking its summary |

## 4. Screenshots to show (v5)
- Idle / Ready: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-1440x900/shot-ready.png`, `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-1100x700/shot-ready.png`, `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-900x600/shot-ready.png`
- Typed prompt + chips: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-*/shot-typed.png`; Options open: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-*/shot-options-open.png`
- Loading (early paint): `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-900x600/cast-00788ms.png` (and cast-*.png in each dir)
- Mid-prefill: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-*/shot-run-25s.png`, `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-demo-c32.next-v5/shubham-headed-scrollbars-run-30s.png`
- Mid-generation: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-layout-v5-*/shot-run-70s.png`, `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-demo-c32.next-v5/shubham-headed-scrollbars-run-150s.png`, `…-run-600s.png`
- Complete: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/run-demo-c32.next-v5/shubham-headed-scrollbars-final.png` (1100×700), `…-final-1440x900.png`, `…-final-900x600.png`
- TinyStories references: `/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/tinystories-study/dynamic-idle.png`, `dynamic-run-30s.png`, `streaming-packed8-run-15s.png`

## 5. Swap (pending approval)
`R8U/swap.sh`: refuses while CHROME.lock is held; demo-c32 → demo-c32.prev (old .prev → .prev2), demo-c32.next-v5 → demo-c32; same for demo-8.next → demo-8.
README.txt / BUILD.md already written into both sources (R8U/make_docs.py: page description, Options, progress texts; BUILD.md = R8U recipe + round-7 history); READY written.
Recipe: `cd R8U && export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32 R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1 R8U_LAYOUT=1;
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh <out> 36 12` (demo-8: `./compile.sh <out> 8 12`).
