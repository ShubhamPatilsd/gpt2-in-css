# R6V — pure-CSS progress UI for `combined8` / `combined8-c32`: exact "token t of N · layer k of 12" bar, cosmetic within-layer fill, "N of 283 fonts" load bar, first paint before the 37–50 MB sheet

Agent R6V, 2026-09-30. Tools copy `work/2026-09-19/R6V/tools` = `R5X/tools` + `r6v_progress_ui.py` + 6 exact-string edits to
`browser_gpt2_runtime.py` (`R6V/patch_runtime.py`; `R6V/tools-vs-R5X.diff`, 275 lines). Bundles `bundles/combined8-ui` (cap 8) and
`bundles/combined8-c32-ui` (cap 32, widths) — each `BUILD.md` = recipe + flag table + offline results + the embedded diff. Scratch,
checkers, harness copies, runs: `work/2026-09-19/R6V/`. Append-only log `R6V.log.md`. No repo `tools/` or `experiments/` edits, no
other agent's directory touched, no git. Status of the Chrome work: **§4** (gated: the machine sat at swap 5.4 → 8.5 GB used and
2 GB of free disk from 15:10 on; the chain `R6V/run_chain.sh` is armed and polls the gate every 60 s).

## 0. Headline

- **What the user sees now** (all exact unless marked *estimate*): from the first ≈100 ms a styled header with the prompt controls and
  a panel "Loading the model's stylesheet (37 MB of CSS)…" with a moving bar (*indeterminate*); when the sheet applies, "Loading model
  weights: N of 283 fonts" with a bar filling as the weight fonts decode (exact, from the page's own font barrier); during generation
  "token t of 8 · layer k of 12" over a 12-segment bar whose dark part is the exact number of finished layers (from the controller's
  `--layer`), a lighter part sliding through the current segment at the measured mean layer time (*estimate*, compositor-only), and
  "12 layers done · vocabulary head" while the 50k-row head runs (from the controller's `--held`). The panel disappears on the last token.
- **Cost, by construction**: the per-token reader is 8 elements, first child of `.core-controller` (the `corestate` container; the
  reader is a SIBLING of `.core-block`, the model), with no inline styles and no custom properties; 3 of them depend on the corestate
  style queries and 1 on body's `runtime` query. Predicted from the cost law (SYNTHESIS §8.1): ≈3 × (4.45 µs + ≈200 B × 36.5 ns) ≈
  **20 µs per layer change, ≈0.25 ms per token (0.002 % of 15.9 s)**. Nothing in the model's rules, registrations, timelines,
  handshakes, fonts or DOM order changes: `R6V/offline_check.py` proves the two bundles are `combined8` / `combined8-c32` plus the UI
  subtree (§3). Chrome confirmation (pass/frame/element counts on the 2-layer smoke trio, ONE 8-token correctness run): §4.
- **Load time**: the `<link>` is moved into `<body>` behind a 1 KB inline `<style>` (controls + CSS-phase panel); everything after the
  panel is `content-visibility:hidden` until runtime.css lifts it. R6L found the same structure independently (`R6L/split-point.md`:
  the 34 s load is ONE 30.8 s task laying out the UA-styled model markup while the head sheet is pending); per that note the merge
  takes R6V's variant (`R6L_BODY_LINK=0 R6L_BOOT=0`) and R6L's load numbers transfer because every byte after the link is identical.

## 1. Where the model's progress state lives (bundles/combined8; rule index `R6V/cssindex.py`)

| state | element / container | property (all registered `<number>`, `inherits:false`) | how it changes |
|---|---|---|---|
| current layer | `.core-controller` (depth 21; `container-name:loopcontrol corestate` — its earlier `runtime` names are overridden by the last declaration) | `--layer:mod(calc(var(--pass) - 1),12)`; `--pass:min(decoded(--pr-stamp) + 1, var(--pass-cap))` where `--pr-stamp` is the proj-generation view-timeline stamp read by `.core-pass-reader` | one step per completed layer (proj stage) → the `@container corestate style(--layer:k)` variants of the fc/qkv/attn rules |
| all 12 layers of this token done | same | `--held:clamp(0, decoded − var(--pass-cap) + 1, 1)`; `--pass-cap` = 12·t via `:where(body:has(#token-(t−1)-advanced.done)) .core-controller{--pass-cap:12t}` | 1 while the head + token handshake run; back to 0 when the cap moves |
| token being generated | `body` (`container-name:runtime loopcontrol`) | `--epoch` (1 → 8): `body:has(#token-(t−1)-advanced.done){--epoch:t}` | once per token |
| fonts loaded | 283 `.font-witness` (fixed, one PUA glyph in face i) → 283 `.font-proof-i{width:clamp(0px, 1px − max(0, abs(anchor-size(--font-witness-i width) − expected) − .125px)·1024, 1px)}` → 21 `.font-all-L-J{width:min(…16 anchors…)}` → `.font-status{container:fontready/inline-size;width:anchor-size(--font-all-2-0 width)}` → `@container fontready (min-width:.99px) #fonts-detected` (SMIL → `#fonts-loaded.done`) | geometry | each proof is exactly 1 px once its face is decoded |
| output text | `.visible-output::before/::after` `counter(…, gpt2-vocabulary)` from `--frozen-prompt` / `--display-token-t` | | |

Ancestry of `.core-controller`: `body > .feedback-reader > .feedback-select > .embedding-source > 12 × .embedding-consumer-N >
.embedding-receipt > #embedding-result > .position-embedding > .core-pass-reader`. None of these has `transform`, `filter`,
`contain:paint/strict`, `overflow` clipping, `visibility:hidden` or `content-visibility` (checked against every rule that matches them),
so a `position:fixed` child of `.core-controller` renders at the viewport. Inherited text properties to reset there:
`.embedding-source{font:1000px EmbeddingLookup;font-kerning:none;font-variation-settings:…}`, `.position-embedding{font:12px monospace}`.

## 2. Design (`R6V/tools/r6v_progress_ui.py`; flags default on, `R6V_PROGRESS_UI=0` → flag-off bundle byte for byte)

### 2.1 Per-token reader — 8 elements, sibling of the model, inside the container's scope

```html
<div class="core-controller">
  <div class="pg"><span class="pg-text"><i class="pg-tok"></i><i class="pg-lay"></i></span>
                  <span class="pg-bar"><i class="pg-est"></i><i class="pg-exact"></i><i class="pg-seg"></i></span></div>
  <div class="core-block" id="block-0">…the model…</div></div>
```

- `@container corestate style(--layer:k){.pg-lay::after{content:" · layer k+1 of 12"}.pg-exact{width:k/12·100%}.pg-est{animation-name:pg-est-k}}`
  (12 rules) and `@container corestate style(--held:1){.pg-lay::after{content:" · 12 layers done · vocabulary head"}.pg-exact{width:100%}.pg-est{animation-name:none}}`
  (placed after the layer rules: same specificity, later wins). `@container runtime style(--epoch:t){.pg-tok::after{content:"token t of 8"}}` (8 rules).
- `.pg{position:fixed;left:24px;top:52px;width:480px;display:none;font:13px/1.4 system-ui;font-kerning:auto;font-variation-settings:normal;…}`;
  shown by `body:has(#fonts-loaded.done):has(#run-latched.done) .pg{display:block}`, hidden again by `body:has(#token-8-captured.done) .pg,
  body:has(#eos-done.done) .pg{display:none}` — these 3 body-anchored `:has()` rules go through R2G's fixed-depth rewrite and page
  verification like every handshake rule (manifest `r2gScopedHas.total` 79 → 84).
- `.pg-seg` draws the 12 segment gaps with a `repeating-linear-gradient` (one declaration, no elements); `.pg-bar{overflow:hidden}`.
- **Why it is cheap.** (i) `--layer`/`--held`/`--epoch` are `inherits:false`, so a change dirties only elements whose style depends on
  the container query (Blink's `kRecalcContainerQueryDependent` traversal visits `.core-controller`'s 14.9k descendants checking one
  flag each — that traversal exists today, R5E measured the per-layer pass at 163 recomputed elements — and recomputes only the
  dependents: `.pg-lay` (+::after), `.pg-exact`, `.pg-est` → 163 → 166). (ii) The reader declares no custom properties, so its
  ComputedStyles share the parent's inherited-variable trie by pointer (no new HashTrie nodes, no copies of the 4.1 KB maps). (iii) It
  is outside `.core-block`, so it is not inside any per-layer `content-visibility` gate, scroller, or R4T chunk chain, and no model rule
  can match it (`.pg*` classes are new; the checker asserts no model rule mentions them). (iv) It has no inline style and no view-timeline,
  so the R4T per-frame servicing term is untouched. Predicted: 3 × (4.45 µs + ≈200 B × 36.5 ns) ≈ 20 µs per layer, 0.25 ms per token.

### 2.2 Cosmetic within-layer fill (`R6V_SMOOTH`, *estimate*, clearly separated from the exact part)

`.pg-est{will-change:transform;transform-origin:0 50%;animation-duration:1.17s;animation-timing-function:linear;animation-fill-mode:forwards}`
with `@keyframes pg-est-k{from{transform:scaleX(k/12)}to{transform:scaleX((k+1)/12)}}` (12 keyframes). The layer rule swaps
`animation-name`, which restarts the animation from the segment's start; it saturates at the segment boundary if the layer runs long
and snaps forward when the exact `--layer` catches up. `transform` on a `will-change:transform` layer is a compositor-only animation:
no main-thread frames while it runs (a `width` animation would have forced ≈60 BeginMainFrames/s × the ≈28 ms/frame R4T servicing
floor of 9.2k live view-timelines ≈ 1.7 s of CPU per second — that variant is exactly what must NOT be built). Duration: cap 8 =
(15.9 s/token − 1.9 s head) / 12 = 1.17 s (RESULTS-round5 B6 medians, R5A head attribution); cap 32 = (12.05 + 0.975·t − 1.9)/12 per
epoch from combined8-c32's fit (R5X.md §4), set by 32 `@container runtime style(--epoch:t){.pg-est{animation-duration:…}}` rules
(0.93 s at t=1 floored to 1.0 s, 3.4 s at t=32). Whether the animation start costs main-thread frames is checked on the smoke trio
(`smoke-R6V-2L-nosmooth` isolates it); if it does, ship with `R6V_SMOOTH=0`.

### 2.3 Load-time indicator (`R6V_FONT_COUNT`) — exact N of 283 from the font barrier

- `R6V.sum_tree`: like `reduce_geometry` but `width:calc(Σ anchor-size(--font-proof-i width,0px))`, fan-in 16 → 18 + 2 + 1 = 21
  `.ld-sum-L-J` elements (fixed, off-screen) → `--ld-sum-1-0` = number of decoded faces in px (each proof is exactly 0 or 1 px, integer sums are exact in LayoutUnits).
- Panel (`.ld2`, after the barrier so its anchors precede it in tree order; every anchored child is `position:fixed`, i.e. the same
  anchor case as the barrier's own `.font-status` reader): `.ld2-fill{width:calc(anchor-size(--ld-sum-1-0 width,0px)*480/283)}` and
  `.ld-probe{width:anchor-size(--ld-sum-1-0 width,0px);container:fontload/inline-size}` whose child `.ld-n::after` gets its text from
  283 `@container fontload (min-width:Npx){.ld-n::after{content:"Loading model weights: N of 283 fonts"}}` range rules (last matching wins).
  Hidden by `body:has(#fonts-loaded.done) .ld2{display:none}`. Cost: only during load (the sum tree is static afterwards; its 21 fixed
  boxes are never dirtied by the model).

### 2.4 First paint before the sheet (`R6V_EARLY_PAINT`)

`<head>` gets a 1 KB `<style>` (body/controls styles, `.status::after{content:"Loading stylesheet…"}`, the `.ld` panel with an
indeterminate `translateX` slide — compositor-only, keeps moving while the main thread parses the sheet — and
`body>:not(.controls):not(.ld){content-visibility:hidden}`); the `<link rel=stylesheet href=runtime.css>` moves to `<body>` right after
the `.ld` panel; runtime.css ends with `.ld{display:none}` (in the fonts-panel block) and `body>:not(.controls):not(.ld){content-visibility:visible}`
(same selector, later sheet → wins; all model values are restored exactly — `content-visibility` is `visible` initially and no model
rule sets it on a body child). Why the lock: a parser-inserted body `<link>` is not render-blocking (HTML: only sheets inserted while
`<body>` is null are), so without it Chrome would style and lay out the ≈67k UA-styled model elements once before the sheet arrives —
the very 31 s task R6L attributed. With the lock the 618 body children are laid out as empty boxes (the 283 `<i>` witnesses are
`display:inline` in the UA sheet, where containment does not apply, so their single glyph each may still be shaped — 283 glyphs, not 780k
characters). Same structure as R6L's `R6L_BODY_LINK`+`R6L_BOOT` minus their `body{display:none}` belt (which would hide the controls and
panel); if R6L's session-1 loads show `display:none` is required, swap the two strings (`R6L/split-point.md`).

## 3. Offline verification (`R6V/offline_check.py`, `R5X/compare_bundles.py`; logs `R6V/logs/`)

| bundle | flag-off twin == reference | offline_check vs reference | static check |
|---|---|---|---|
| `bundles/combined8-ui` (cap 8, runs) | `R6V/scratch/p8-off` == `bundles/combined8`: index.html IDENTICAL, runtime.css url-normalised IDENTICAL, manifest +4 `r6v*` keys, witnesses 283/283 (twin deleted) | **PASS**: HTML identical after removing head `<style>`, body `<link>`, `.ld`/`.ld2`, 21 `.ld-sum`, `.pg`; model rules identical in multiset AND order (61,964 rules); 396 UI rules, +48,218 B (283 fontload, 39 corestate, 8 runtime, 24 keyframes, 42 plain); manifest only `r6v*` + `r2gScopedHas.*` (79 → 84); witnesses 283/283 | 285 files, no JS |
| `bundles/combined8-c32-ui` (cap 32, widths, R4S off) | `R6V/scratch/p32w-off` == `bundles/combined8-c32`: same result (twin deleted) | **PASS**: 66,598 model rules identical; 452 UI rules, +53,552 B (64 runtime: 32 token labels + 32 durations); `r2gScopedHas.total` 295 → 300 | 285 files, no JS |
| `bundles/smoke-R6V-2L` / `-ref` / `-nosmooth` (2 layers, cap 2) | ref = flag-off | PASS (115 UI rules) | 75 files, no JS |

`.pg` reader = 8 elements (checker asserts it is the first child of `.core-controller`); DOM +31 elements at cap 8 (8 + 21 + 2 panels), +1 `<link>` moved.

Post-build fix (15:50): the emitted `content:" \00b7 layer k of 12"` would have rendered "·layer" (a CSS hex escape consumes the following
space). The emitter now writes the literal "·"; because the machine had 1 GB of free disk and 8.8 GB of swap in use, the four built sheets
were patched in place with exactly that string instead of being rebuilt, and `R6V/check_emitted.py` verifies per bundle that every rule and
HTML fragment the current `r6v_progress_ui.py` emits is present verbatim (smoke 107/107, nosmooth 104/104, combined8-ui 358/358,
combined8-c32-ui 414/414) — i.e. the shipped bundles equal a rebuild. The flag-off code path was not touched by the fix.

## 4. Chrome (gated; `R6V/run_chain.sh`, lock owner "R6V <label> <pid> <time>")

Plan, each under its own lock hold after the machine gate opens (AC AND ((disk ≥ 4 GB AND swap < 4,000 MB) OR (≥ 3 GB AND < 3,000 MB))):
1. smoke trio `smoke-R6V-2L-ref` / `smoke-R6V-2L` / `smoke-R6V-2L-nosmooth` (R5H's `run_bundle.mjs` + 2 screenshots per run at the same
   poll positions in every arm, light trace) → `R6V/runs/<b>/frames.md`: identical ids, per-token `UpdateLayoutTree` / `Layout` / frame
   counts and per-pass elementCounts (expected: identical except +3 elements in the per-layer pass; SMOOTH: no extra main frames).
2. load-paint probe `R6V/loadpaint.mjs` on `combined8-ui` (screenshots at 0.5/1/2/4/8/… s after navigation, paint timings, panel texts;
   then Run with screenshots at +3…+36 s = mid token 1 / start of token 2) and on `combined8` (load only) → `R6V/runs/loadpaint-*/`.
3. ONE passive 8-token correctness run of `combined8-ui` (R5X protocol) → ids 8/8 + `verify rc 0` → `bundles/combined8-ui/READY`; per-token
   capture times vs combined8's 15.7–16.1 s/token (B6 pairs are B7's job).

Results: PENDING at hand-back (gate closed all session: swap used 5,449 → 8,800 MB with swap files growing 6 → 10 GB, free disk 6 → 1 GB;
no Chrome of any agent could run). `R6V/run_chain.sh` stays armed (nohup; polls the gate every 60 s; `R6V/logs/run_chain.out`) and, when
the gate opens, appends its results to this file as §4a (smoke trio: ids, per-token frames/ULT/Layout, ΔRecalcStyle/ΔLayout, per-pass
elementCount multiset ref vs ui vs nosmooth via `R6V/compare_smoke.py`), §4b (load-paint states + screenshot list) and §4c (correctness
run: per-token capture times, metrics, verify rc, READY). Acceptance for the UI: identical ids; ΔRecalcStyle/ΔLayout per token equal to
the ref's; per-pass elementCounts equal except the per-layer pass +3 (and no new frames in `smoke-R6V-2L` vs `-nosmooth`, otherwise ship
`R6V_SMOOTH=0`); correctness 8/8 + verify rc 0 with capture times in combined8's 15.7–16.1 s/token band (5-s poll granularity).
Screenshots to look at once §4b exists: `R6V/runs/loadpaint-combined8-ui/shot-load-{0.5,1,2,4,8}s.png` (CSS-phase panel → fonts N of 283),
`shot-ready.png`, `shot-run-{6,12,18}s.png` (mid-token bar), and `R6V/runs/smoke-R6V-2L/shot-mid-token1.png`.

## 5. Exact vs estimated, limits, follow-ups

- Exact: token counter (`--epoch`), finished-layer count and "vocabulary head" phase (`--layer`, `--held`), fonts decoded N of 283
  (proof widths). Estimate (labelled by its lighter colour and by this note): the within-layer slide (mean s/layer; per-epoch slope at
  cap 32), the CSS-phase indeterminate slide.
- The layer counter advances when a layer's proj stage completes, so "layer k of 12" means layers 1..k−1 are done and k is running; the
  head phase (≈1.9 s/token at cap 8, more at cap 32 as the head input grows) is shown as its own state.
- Not done: a prompt-selection echo (R6P) and stylesheet splitting/dedup beyond the link move (R6L). The inline sheet's copy of the
  body/controls rules is the only duplicated CSS (≈300 B).

## 4a. Chrome results — smoke trio (auto-appended by R6V/run_chain.sh 2026-09-30 20:03:09; runs R6V/runs/smoke-R6V-2L{-ref,,-nosmooth}/: harness.log, frames.md, shot-*.png)

| run | ids | token: frames / ULT / Layout | ΔRecalcStyle / ΔLayout per token | capture s |
|---|---|---|---|---|
| smoke-R6V-2L-ref | [11, 3387] | t1: 19/39/25; t2: 6/8/2 | t1: 45/26; t2: 13/2 | 10.6; 13.9 |
| smoke-R6V-2L | [11, 3387] | t1: 20/44/26; t2: 4/4/1 | t1: 54/27; t2: 6/1 | 10.6; 13.4 |
| smoke-R6V-2L-nosmooth | [11, 3387] | t1: 20/42/26; t2: 4/4/1 | t1: 51/27; t2: 6/1 | 10.5; 13.4 |

per-pass elementCount multiset smoke-R6V-2L-ref vs smoke-R6V-2L: identical 37 passes; only in smoke-R6V-2L-ref: [0, 0, 2, 20, 20, 20, 25, 789, 789, 862, 2366, 2366, 2403, 2406]; only in smoke-R6V-2L: [1, 1, 1, 1, 22, 22, 23, 26, 795, 795, 872, 2372, 2372, 2407, 2417]

per-pass elementCount multiset smoke-R6V-2L-ref vs smoke-R6V-2L-nosmooth: identical 38 passes; only in smoke-R6V-2L-ref: [0, 2, 2, 20, 20, 20, 25, 789, 789, 862, 2366, 2366, 2403]; only in smoke-R6V-2L-nosmooth: [1, 1, 22, 22, 23, 26, 794, 794, 871, 2371, 2371, 2417]

## 4b. Chrome results — load-paint probe (auto-appended 2026-09-30 20:03:55; screenshots R6V/runs/loadpaint-combined8-ui/shot-*.png, R6V/runs/loadpaint-combined8/shot-*.png)

```
== combined8-ui
{"t":2248,"event":"load-event","sinceNavMs":1804}
{"t":2388,"event":"screenshot","file":"shot-load-0.5s.png","sinceNavMs":1944}
{"t":2395,"event":"state","tag":"load-0.5s","sinceNavMs":1951,"readyState":"complete","elements":67563,"fonts":283,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 283 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 8\""},"pglay":{"display":"inline","after"
{"t":2396,"event":"fonts-loaded","sinceNavMs":1951,"readyState":"complete","elements":67563,"fonts":283,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 283 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 8\""},"pglay":{"display":"inline","after":"\" · laye
{"t":8891,"event":"screenshot","file":"shot-run-3s.png","sinceRunMs":6457}
{"t":9917,"event":"state","tag":"run-3s","sinceRunMs":7483,"pgtok":{"display":"inline","after":"\"token 1 of 8\""},"pglay":{"display":"inline","after":"\" · layer 3 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":false,"tok2":false}
{"t":11951,"event":"screenshot","file":"shot-run-6s.png","sinceRunMs":9517}
{"t":13038,"event":"state","tag":"run-6s","sinceRunMs":10604,"pgtok":{"display":"inline","after":"\"token 1 of 8\""},"pglay":{"display":"inline","after":"\" · layer 7 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":false,"tok2":false}
{"t":15081,"event":"screenshot","file":"shot-run-9s.png","sinceRunMs":12647}
{"t":15985,"event":"state","tag":"run-9s","sinceRunMs":13551,"pgtok":{"display":"inline","after":"\"token 1 of 8\""},"pglay":{"display":"inline","after":"\" · layer 10 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":false,"tok2":false}
{"t":19998,"event":"screenshot","file":"shot-run-12s.png","sinceRunMs":17564}
{"t":20439,"event":"state","tag":"run-12s","sinceRunMs":18005,"pgtok":{"display":"inline","after":"\"token 1 of 8\""},"pglay":{"display":"inline","after":"\" · 12 layers done · vocabulary head\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":true,"tok2":false}
{"t":22582,"event":"screenshot","file":"shot-run-15s.png","sinceRunMs":20148}
{"t":23716,"event":"state","tag":"run-15s","sinceRunMs":21282,"pgtok":{"display":"inline","after":"\"token 2 of 8\""},"pglay":{"display":"inline","after":"\" · layer 3 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":true,"tok2":false}
{"t":25893,"event":"screenshot","file":"shot-run-18s.png","sinceRunMs":23459}
{"t":27034,"event":"state","tag":"run-18s","sinceRunMs":24600,"pgtok":{"display":"inline","after":"\"token 2 of 8\""},"pglay":{"display":"inline","after":"\" · layer 7 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":true,"tok2":false}
{"t":29200,"event":"screenshot","file":"shot-run-24s.png","sinceRunMs":26766}
{"t":30356,"event":"state","tag":"run-24s","sinceRunMs":27922,"pgtok":{"display":"inline","after":"\"token 2 of 8\""},"pglay":{"display":"inline","after":"\" · layer 11 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":true,"tok2":false}
{"t":34663,"event":"screenshot","file":"shot-run-30s.png","sinceRunMs":32229}
{"t":35931,"event":"state","tag":"run-30s","sinceRunMs":33497,"pgtok":{"display":"inline","after":"\"token 3 of 8\""},"pglay":{"display":"inline","after":"\" · layer 1 of 12\""},"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"tok1":true,"tok2":true}
== combined8
{"t":2884,"event":"load-event","sinceNavMs":2436}
{"t":3019,"event":"screenshot","file":"shot-load-0.5s.png","sinceNavMs":2571}
{"t":3023,"event":"state","tag":"load-0.5s","sinceNavMs":2575,"readyState":"complete","elements":67524,"fonts":283,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"ld":null,"ldn":null,"pgtok":null,"pglay":null,"fontsLoaded":true,"paints":[{"name":"first-paint","t":1124},{"name":"first-contentful-paint","t":1124}]}
{"t":3025,"event":"fonts-loaded","sinceNavMs":2575,"readyState":"complete","elements":67524,"fonts":283,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"ld":null,"ldn":null,"pgtok":null,"pglay":null,"fontsLoaded":true,"paints":[{"name":"first-paint","t":1124},{"name":"first-contentful-paint","t":1124}]}
```

## 4c. Chrome results — ONE 8-token correctness run of combined8-ui (auto-appended 2026-09-30 20:06:11; R6V/run-combined8-ui/)

```
{"t":2332,"event":"loaded","elements":67563,"fonts":283}
{"t":25968,"event":"token-captured","token":1,"sinceRunMs":21573}
{"t":38849,"event":"token-captured","token":2,"sinceRunMs":34454}
{"t":52282,"event":"token-captured","token":3,"sinceRunMs":47887}
{"t":63903,"event":"token-captured","token":4,"sinceRunMs":59508}
{"t":75653,"event":"token-captured","token":5,"sinceRunMs":71258}
{"t":92770,"event":"token-captured","token":6,"sinceRunMs":88375}
{"t":110818,"event":"token-captured","token":7,"sinceRunMs":106423}
{"t":122166,"event":"token-captured","token":8,"sinceRunMs":117771}
{"t":124173,"event":"metrics-after","RecalcStyleCount":842,"RecalcStyleDuration":57.069598,"LayoutCount":526,"LayoutDuration":29.360597,"Nodes":132240}
{"t":125855,"event":"final","packedBanks":true,"packedHead":true,"headSample":"\"X000\" -12,\"X001\" -4,\"X002\" 4,\"X003\" -13,\"X004\" 8,\"X005\" -20,\"X006\" 89,\"X007\" -5,\"X008\" 5,\"X009\" 9,\"X00A\" -3,\"X00B\" -11,","tokens":[11,314,1101,7926,11,475,314,1101],"tokensText":"","bodyProps":{"--epoch":"8","--winner":"-1","--head-output-epoch":"0","--token":"15496"},"doneMarkers":{"1":true,"2":true,"3":true,"4":true,"5":true,"6":true,"7":true,"8":true},"rawSample":{"k":{"list":"\"K000\" -0.5
verify: verify rc=0 {'tokens': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceQ9Q16': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceAttentionMask': 'full causal', 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.016997776885828732, 'maximum': 0.14188476906986125}, 'finalHeadActualInputWinner': 1101, 'finalHeadMatchesActualInpu
RSS renderer peak MB: 5727
READY: combined8-ui READY 2026-09-30 20:06:11: ids 8/8 [11,314,1101,7926,11,475,314,1101], verify rc=0, run R6V/run-combined8-ui (harness.log, verify.log); = combined8 + R6V progress UI (display-only)
```
