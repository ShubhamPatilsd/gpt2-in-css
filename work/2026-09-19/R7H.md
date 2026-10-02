# R7H — the winner → token-id hop: map, the off-by-one, and a self-checking guard (round 7, 2026-10-01)

Agent R7H. Inputs: R6X.md §10/§10.M/§10.R, R3H.md, R6X/tools (v5 → v6), bundles/demo-c32 (grep only), the headed run records
`R6X/runs/ordering-demo-c32-keys-mouse-load30/`, `R6X/run-demo-c32/headed-shubham*`. Scratch `R7H/` (tools copy, harness, twins, runs),
log `R7H.log.md`. No repo `tools/`/`experiments/` edits, no git, no live bundle written.

## 0. Headline

1. **The flip was not a race and not v5's wiring: it is a hardcoded scrollport constant meeting a classic scrollbar.** The id leaves the head
   exactly; the ONE hop without a receipt is the view-timeline readback of `.feedback-metric-e` inside
   `.feedback-scroller{width:524288px;height:1px;overflow:scroll}`, decoded as `round((524288/p − 524288 − 65536)/8 − 1)`. A space-taking
   (non-overlay) vertical scrollbar makes the scrollport 524288 − 15 px, so the decode is biased by +W·15/524273 px = +(65536 + 8(id+1))·2.86e-5/8
   ids: **+1 for every id ≥ 9283, +0 below**. This Mac has "Show scroll bars: Always" (`defaults read -g AppleShowScrollBars` = Always); the
   harnesses that passed `--hide-scrollbars` (bench_native, correctness_run, headless) never saw it, `R6X/ordering.mjs` (headed, no flag) and
   the user's real Chrome did. Every run on record fits: Hello max id 7926 → bias 0.46 (passes, barely); "Once upon a time" max 8737 → 0.49
   (passes headed, barely); the 2-layer smokes max 6646 (never flip — a 2-layer bisect cannot reproduce it); "Shubham was" ids 1–13 < 2888,
   id 14 = 17132 → 17132.72 → **17133** in both headed runs (load 30 and load 4); typed "I" has 16918 at position 15, 12912 at 22, 32132 at 23
   → a headed run without `--hide-scrollbars` must flip at 15 (prediction for R6X's control). Root-cause fix (R6X v6): `.feedback-scroller
   {scrollbar-width:none}` (one declaration, Chrome ≥ 121).
2. **Guard (flag `R7H_ID_GUARD`, default on; `R7H/tools/r7h_id_guard.py`, 2 elements + 1 timeline + 34 scroll-driven animations + ~70 control
   rules, zero inherited properties, zero new frames, model core rules untouched):** (G2) a *calibration metric* of constant width (id 50256) is
   read back through the same scroller/timeline mechanism; `--fb-ok` = 1 only if it decodes to exactly 50256 (a 15 px scrollbar gives 50257.7 →
   0; the check trips from ≈4.5 px of stolen scrollport); `#token-e-ready` is blocked while `--fb-ok` ≠ 1 and a visible panel says why. (G3) the
   `headstate` container `.token-state` reads every slot's id back through its own animation on the slot's view-timeline and compares it with
   the inherited, *latched* `--saved-token-e` (the exact cq/anchor value); `#token-e-ack` — the epoch advance, i.e. the moment the model consumes
   `--feedback-e` — is blocked while they disagree. A biased decode or a timeline sampled a frame early therefore holds the run instead of
   feeding a neighbouring/stale id; the echo lands one frame after the head frame and the ack needs the captured frame (≥ 2 frames later), so
   the gate costs no frame in the normal path.
3. Other hardcoded geometry in the decode chains (§5): the 13 other scrollers are `overflow-x:scroll;overflow-y:hidden` (only a horizontal bar,
   which cannot shrink an inline scrollport) — safe by construction; viewport units only in display rules (`.tk-bridge` 100vw, `.visible-output`
   100vh); Chrome's *minimum font size* setting is the one remaining user setting that could break arithmetic (tokenizer metrics at 1 px).

## 1. Hop map: how the winning row becomes the next input (per token e, `bundles/demo-c32`)

| # | from → to | carrier | resolved | receipt covering it |
|---|---|---|---|---|
| H1 | 50,257 `.head-row` widths (q16 score, 4 px lattice) → group max → `.head-score-g` → 16-fan-in `anchor-size()` max trees → `.head-match-g` (winning group's rank) → `.head-coarse-reader{container-type:size}` → `.head-score-state{--head-group-index:197 − round(100cqi/4px); --head-max-score:round(100cqb/1px)}` | anchor-size + cq units | inside the head frame's single Layout (interleaved style/layout) | none needed: pure integer geometry (px multiples of 4; LayoutUnit exact) |
| H2 | 256 `.head-fine-row` (glyphs/base of local k in the chosen group, width = `clamp(0,score − max + 1px,1px)·rank`, rank = 256 − k) → `.head-fine` grid max-content → `.head-final-reader` (anchor-size) → `.head-result{--winner: g·256 + 256 − round(100cqi/1px)}` | anchor-size + cq | same Layout | none; exact integers (ties: lowest local index) |
| H3 | `--winner`, `--head-output-epoch` → `i.detached-head-source{width:epoch px;height:max(0,winner) px}` → across the isolation wall → `.detached-head-reader{container-type:size; anchor-size(…)}` → `.detached-head-state{--winner:round(100cqb/1px); --head-output-epoch:round(100cqi/1px)}` | anchor-size + cq | same frame | the epoch travels WITH the value (width = epoch): `.token-slot-e` only accepts `--winner` while `style(--head-output-epoch:e)` |
| H4 | `.token-slot-e{--saved-token-e: if(style(--head-output-epoch:e): var(--winner); else −1)}` + 86,400 s transition latch (off during `--epoch:e`, on from `#token-e-captured.done`; freezes the before-change value when the head re-locks → anchor fallback 0 → −1) | style query + transition | same frame; latch arms at capture | the SMIL order (ready → captured) |
| **H5** | `.feedback-metric-e{width:65536px + (saved+1)·8px; view-timeline:--feedback-te inline}` in `.feedback-scroller{width:524288px; overflow:scroll}` → `@keyframes feedback-e{--feedback-p-e:0→1}` on `.feedback-reader` (an ANCESTOR of the whole model: the only way a value flows upward) → `--feedback-e: round((524288/p − 524288 − 65536)/8 − 1)` | **view-timeline progress → number** | **next frame** (timeline snapshot of the previous layout) | **none** — the decode assumes scrollport = 524288 px and scroll offset 0; nothing compares the result with the head's value |
| H6 | `.feedback-select{--token: if(style(--epoch:e+1): var(--feedback-e) …)}` → `.embedding-source{--token:inherit}` → embedding fonts → 768 `--embed-t*` view-timelines → `.embedding-receipt{--embed-ready}` | style query, then view-timelines | at `--epoch:e+1` (≥ 3 frames after H1: ready → captured → ack → advanced, each a SMIL/animation hop) | the embedding receipt stamps epoch (+ `--prompt-live`), not the token |
| S | `@container runtime style(--epoch:e){@container headstate style(--head-output-epoch:e){#token-e-ready{animation}}}` → SMIL `token-e-captured` (class done) → display `--display-token-e: var(--feedback-e)` and latch on → `#token-e-ack` (if winner ≠ EOS) → `token-e-advanced` → `body{--epoch:e+1}` | CSS animation → SMIL `<set>` | 1 frame each | — |

What `--feedback-e` is used for: the model's next input (H6) **and** the displayed word (`--display-token-e`); so a biased H5 shows the wrong word
and feeds the wrong id consistently (the "House ofEARTH" screenshots: 17133 "EAR" fed, then 4221 "TH" — the correct continuation of the wrong id).

## 2. The mechanism of the off-by-one (deterministic, value-dependent, environment-dependent)

View-timeline `cover` range in the inline axis with scroll offset 0: progress p = S′/(S′ + W), S′ = the scroller's **scrollport** inline size,
W = the metric's width 65536 + 8(id+1). The decode uses the literal 524288 for S′. With a classic vertical scrollbar S′ = 524288 − 15:

  decoded = (524288·(S′+W)/S′ − 524288 − 65536)/8 − 1 = id + W·15/(8·524273) = id + (65536 + 8(id+1))·3.58e-6

  id 11 → +0.23 · 7926 → +0.46 · 8737 → +0.49 · 9283 → +0.500 (first flip) · 17132 → +0.72 → 17133 · 50256 → +1.67

The `--embed-*` / `--shared-*` readbacks are unaffected: their scrollers are `overflow-x:scroll;overflow-y:hidden` (a horizontal scrollbar eats
block size, not the inline scrollport), so every winner was right and only the id was +1. The ordering harness's forced `getComputedStyle` reads
(R6X hypothesis ii) and v5's wiring (hypothesis i) are both exonerated by the arithmetic; the discriminating variable is `--hide-scrollbars`
(present in every 32/32 run's launch args, absent in `ordering.mjs` and in the user's Chrome). A "frame landing early/late" cannot produce id+1 at
H1–H5: every hop is integer geometry except H5, and a stale H5 yields the previous slot value (−1), not a neighbour.

## 3. Guard design (`r7h_id_guard.py`, applied right after `feedback()` in `browser_gpt2_runtime.py`)

- **G2 calibration.** `<i class="feedback-metric feedback-metric-cal">` appended to `.feedback-track`, `width:calc(65536px + 50257*8px)`,
  `view-timeline:--feedback-tcal inline` (added to `html{timeline-scope}`). `@keyframes fbcal{--fb-cal-p:0→1}` runs on `.feedback-reader`
  (its existing 32-animation list extended by one) and on `.token-state`; both compute `--fb-ok: 1 − min(1, |round(decode(--fb-cal-p)) − 50256|)`
  (non-inherited). Gate: `@container headstate not style(--fb-ok:1){#token-1-ready,…,#token-32-ready{animation:none!important}}` — nothing is
  captured, so nothing is latched or displayed, until the constant reads back exactly. Panel: `<small class="fb-warn">` (fixed, top 184 px),
  `display:block` only under `@container style(--fb-ok:0)` on `.feedback-reader` and after `#fonts-loaded.done` (no flash during load).
  Fail-closed: before the animation applies `--fb-cal-p` is 0 → the decode is ∞ → `--fb-ok` 0.
- **G3 agreement.** `.token-state{animation-name:fbcal,fbecho1…32; animation-timeline:--feedback-tcal,--feedback-t1…32; --fb-agree-e:
  1 − min(1, |round(decode(--fb-echo-p-e)) − var(--saved-token-e)|)}` (`--saved-token-e` is registered inherited and reaches `.token-state`
  through the slot chain; during the 86,400 s latch the inherited value is the frozen one). Gate per slot: `@container headstate not
  style(--fb-agree-e:1){#token-e-ack{animation:none!important}}`. Normal path: head frame A sets saved/metric; A+1 echo = winner → agree 1;
  A+2 captured; ack unblocked already → **no added frame**. Stale timeline (echo = −1 ≠ winner) → ack waits one frame (self-healing). Biased
  decode (echo = winner+1) → ack never fires → run holds at that token with the exact winner latched (and, since the calibration constant fails
  first, with the panel shown before the first token).
- **Why two checks.** G2 catches an environment fault before any token and explains it; G3 catches per-value faults the constant cannot
  represent (a scroll offset, a late sample, precision at a particular W) at the exact hop where the model consumes the id.
- **Not changed:** the decode itself (self-calibrating it from the cal metric would make every `--feedback-e` depend on a second animated
  value and change the control arithmetic of a verified bundle; v6's `scrollbar-width:none` removes the cause, the guard makes any recurrence
  a visible hold rather than wrong text).
- **Costs.** +2 elements, +1 timeline, +34 scroll-driven animations (serviced only when the timeline moves; ≈0.65 µs each per frame if
  serviced), +35 non-inherited `@property`, +16.4 KB CSS (`.token-state` carries 32 decode declarations ≈ 6 KB of `var()` text → ≈0.2 ms per
  restyle of that one element, a few times per token). Predicted s/token change: < 0.01 s. Frames per token: unchanged (verified in §6).

## 4. Offline verification (`R7H/logs/`, builds 14:14–14:31 under the lock, tools = R6X/tools v6 edit 7 + guard)

- **Flag-off twins are byte-identical to the shipped v6 bundles**: `compare_rules.py R7H/twin-demo-c32-off bundles/demo-c32` → index.html IDENTICAL
  (7,130,245 B), 67,176 rules, only-in-new 0 / only-in-ref 0, order IDENTICAL; demo-8: IDENTICAL (6,464,515 B), 62,486 rules, 0/0, order IDENTICAL.
- **Guard-on vs shipped** (`check_guard_diff.py`, `logs/guard-diff-{demo-c32,demo-8,smoke}.log`, all **PASS**): index.html identical after removing the
  two guard elements (`.feedback-metric-cal`, `.fb-warn`); css: 175 (c32) / 55 (demo-8) rules only in the guard build, every one a guard rule
  (66 `@property` + 66 `@keyframes` + 34 `@container headstate not style(...)` gates + `.token-state`, `.feedback-reader{--fb-ok}`,
  `.feedback-metric-cal`, `.fb-warn`, `.fb-warn::after`, the R2G-scoped `body:has(…#fonts-loaded.done) .feedback-reader>.fb-warn` rule); exactly 3
  rules modified (the `html{timeline-scope}` list gains `--feedback-tcal`, the `.feedback-reader` animation list gains `fbcal`, and the R5E
  `.head-isolation` wall gains `--fb-cal-p:initial;--fb-ok:initial` — the same class of change as v5's `--prompt-live:initial`); relative order of all
  shared rules identical; **model core rules untouched**.
- Witnesses: `font-witnesses.json` of guard-on == flag-off bytewise; vs the shipped bundle identical after normalising the agent-dir path in the
  font-path keys (R6X/… → R7H/… through identical symlinks). Manifest differs only in `r2gScopedHas` (+2 scoped `:has` rules), `r5eLeanWallStats`
  (+2 kept on the wall) and the two tokenizer-font paths.
- Static no-JS check (`tools/launch_browser_gpt2.py --check`): rc 0 for both guard builds (287 static files; 299,896,573 / 288,115,592 B).
- Bundles: `bundles/demo-c32.r7h`, `bundles/demo-8.r7h` (guard on, v6 scrollbar fix on; BUILD.md copied; not swapped in, no READY).

## 5. Inventory: hardcoded geometry constants and environment-dependent inputs on the compute paths (`bundles/demo-c32`)

| where | constant / dependency | perturbable by | status |
|---|---|---|---|
| `.feedback-scroller{width:524288px;height:1px;overflow:scroll}` + 32 decodes `524288/p − 524288 − 65536` | scrollport = 524288 px, scroll offset 0 | **classic scrollbars** (macOS "Always"/mouse attached, Windows 17 px, Linux GTK), `--hide-scrollbars` absent | **was the bug**; v6 `scrollbar-width:none`; R7H cal/agree guards |
| `.shared-proj>.scroller{width:524288px;overflow-x:scroll;overflow-y:hidden}` ×12, `.track{width:1572864px}`; `.shared-proj-receipt{--gate-proj: … 524288/stamp − 524288 − 131072)/1024 − epoch}`; `.loop-input{--loop-in-i:(1572864/(lp+2) − 524288 − 262144)/128}` | scrollport 524288, track 1572864 | a horizontal scrollbar only (block axis) → inline scrollport intact; no vertical bar possible (`overflow-y:hidden`) | safe by construction; the receipt stamps the epoch; consider `scrollbar-width:none` for symmetry |
| `.embedding-scroller{width:65536px;overflow-x:scroll;overflow-y:hidden}`, `.embedding-receipt{--embed-ready: … 65536/stamp − 65536 − 20000)/1024 − epoch}` | scrollport 65536 | same | safe (horizontal bar only); stamp = epoch (+ `--prompt-live`) |
| view-timeline readbacks generally | scroll offset of hidden scrollers = 0 | find-in-page / focus scrolling into an off-screen scroller could change `scrollLeft` | not observed; all scrollers are `position:fixed; top:−50000…−100000px; visibility:hidden`; G3 would hold the run |
| `.tk-bridge{width:calc(100vw − 48px)}` (tokenizer chain containers) | viewport width | window narrower than the prompt's metric text; windows < 48 px | display/containment only (the probes read `anchor-size()` of the metrics, not the bridge); untested below ≈320 px |
| `html .visible-output{max-height:calc(100vh − 280px)}`, `.tk-aside{top:calc(192px + max(128px,100vh − 280px))}` | viewport height | window height | display only |
| `.tk-metric{font-size:1px}` tokenizer metrics; `font:12px/13px` UI | **Chrome "Minimum font size"** (chrome://settings/fonts) / Android font scaling | a minimum ≥ 2 px rescales the 1 px tokenizer metrics → wrong token ids typed; the model's carriers (`font:512px/1024px`, head 62.5 px) are far above any minimum | document; a tokenizer self-check (known word → known id) is the cheap guard |
| `--force-device-scale-factor=1` in every harness run | device scale factor (Retina 2×, user zoom) | the user's Chrome runs at DSF 2 and arbitrary zoom; layout is in CSS px so transports are DSF-invariant; R6X's 150 % zoom probes passed 5/5; the LayoutUnit (1/64 px) snapping of font advances is zoom-invariant in CSS px | believed safe; not harness-tested at DSF 2 with 12 layers |
| `round(nearest,…,4px)` head lattice, `size-adjust:25600%`, anchor fallbacks `0px` | LayoutUnit precision, 33,554,432 px cap | none environmental | fine |

## 6. Chrome results (auto-appended by R7H/run_chain.sh)

## 7. README paragraph (proposed; `R7H/README-scrollbars.txt`, to go under "Known limits" or a new "If something looks wrong" heading)

```
Scrollbars, headed vs headless Chrome, and the geometry self-check
  The page does its arithmetic with layout geometry: hidden measuring elements whose widths encode numbers are read back
  through CSS scroll-driven animations, and one such element was decoded with the assumption that its scrolling box is
  exactly 524,288 px wide. A classic, space-taking scrollbar (macOS with "Show scroll bars: Always" or with a mouse
  attached, Windows, most Linux desktops) makes that box 15–17 px narrower, which shifted every read-back token id
  above ≈9,300 by +1 — the model then continued from the wrong word ("House ofEARTH" instead of "House of
  Representatives"). Headless Chrome, and Chrome started with --hide-scrollbars, never showed it; overlay scrollbars
  (macOS default with a trackpad only) take no space and are also unaffected. Since v6 the measuring box declares
  scrollbar-width:none (Chrome 121+), so the scrollbar policy of the OS no longer matters, and the page now
  self-checks the mechanism: a constant of known value is read back the same way before every token and each fed-back
  id is compared with the exact winner; if either check fails the run is HELD (no token appears) and a red panel
  "Geometry self-check failed" is shown instead of wrong text. If you see that panel: use Chrome/Edge 121 or newer
  (139+ is required anyway), do not run with a browser "minimum font size" set, keep the window at 100 % zoom
  if in doubt, then press Reset.
```

## 8. Merge notes for the next bundle

- Tools: `R7H/tools` = `R6X/tools` (v6, 13:21) + `r7h_id_guard.py` (new file) + the two-line hook in `browser_gpt2_runtime.py`
  (`import r7h_id_guard as r7h`; `front, output, control_css, timeline_names = r7h.apply(...)` right after `feedback(capacity)`), applied by
  `python3 R7H/apply_guard.py` onto any later R6X/tools (idempotent, anchors asserted unique). Flag `R7H_ID_GUARD` (default on); flag-off is
  byte-identical to the base build (§6). `R7H/compile.sh` = `R6X/compile.sh` with the R7H tools dir and the `R7H_ID_GUARD` / `R6X_SCROLLBAR_FIX`
  passthroughs; build command for demo-c32: `VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R7H/compile.sh <out> 32 12`, demo-8: `R7H/compile.sh <out> 8 12`.
- Bundles: `bundles/demo-c32.r7h`, `bundles/demo-8.r7h` (guard on; BUILD.md copied from the shipped bundle — append the R7H paragraph when
  swapping). Not swapped in. Twins/logs: `R7H/twin-*`, `R7H/logs/`, runs `R7H/run-*/`.
- Harness: `R7H/bench_r7h.mjs` = `R6X/bench_native.mjs` + `R7H_SHOW_SCROLLBARS=1` (omit `--hide-scrollbars`; **every headed acceptance run should
  set it** — headless+hidden is not the user's configuration) + a final `guard-state` dump (`.feedback-scroller` clientWidth/offsetWidth tells
  directly whether a scrollbar took space) + `guard-held` stop. Suggest folding the switch into B0's harness.
- Keep `R6X_SCROLLBAR_FIX=1` (the cause) AND the guard (the alarm). If a user reports the red panel: the dump's `scroller.clientWidth` ≠ 524288 →
  scrollbar (Chrome < 121 ignores `scrollbar-width`); `= 524288` with `--fb-ok` 0 → a new decode fault, read `--fb-cal-p`.
- Follow-ups (not done here): `scrollbar-width:none` on the 13 other scrollers for symmetry (safe today); a tokenizer self-check for the
  minimum-font-size setting (§5); the stress protocol (6 busy loops) is in `R7H/stress.sh` for reuse.

### 6.1 2-layer smoke, headless, typed "Shubham was", 32 tokens (R7H/run-twin-smoke-2L-{off,on}/smoke-*-headless.*)

| build | ids | whole-run RecalcStyleCount / LayoutCount | style / layout s | total s (median s/token) | load1 at end | guard state at end |
|---|---|---|---|---|---|---|
| guard OFF (= shipped v6 rules) | **32/32** | 901 / 450 | 68.5 / 47.4 | 169.8 (5.0) | 2.6 | n/a (properties absent) |
| guard ON | **32/32** | 900 / 450 | 75.7 / 52.6 | 185.9 (5.6) | 8.1 | `--fb-ok` 1, `--fb-cal-p` 0.52858 (= 524288/(524288+467600) exactly), all 32 `--fb-agree-e` 1, `.feedback-scroller` clientWidth = offsetWidth = 524288, scrollbar-width none |

Per-token ΔRecalcStyle / ΔLayout are identical token by token (k=1: 35/18 both; k=2: 25/12; k=3–6: 28/14; k=32: 25/11; sums over tokens 2–32:
860 vs 859 recalcs, 427 vs 427 layouts) → **the guard adds no frame and no style pass**. The +10 % style/layout time of the ON run coincided with
load1 8.1 (other agents' builds) vs 2.6 for the OFF run; the stress and demo-8 steps below give the cleaner cost comparison.

### 6.2 Headed Chrome with classic scrollbars shown (R7H_SHOW_SCROLLBARS=1, 1100×700, typed "Shubham was", 2-layer smoke twins)

| build | ids | guard state | `.feedback-scroller` | result |
|---|---|---|---|---|
| guard ON + v6 fix (`twin-smoke-2L-on`, `run-twin-smoke-2L-on/smoke-on-headed-scrollbars.*`) | **32/32** (193 s, median 5.6 s/token) | `--fb-ok` 1, `--fb-cal-p` 0.52858, all `--fb-agree-e` 1 | clientWidth 524288 = offsetWidth, `scrollbar-width:none` | v6's fix holds under the user's configuration; the guard stays silent |
| **fault injection**: guard ON, `R6X_SCROLLBAR_FIX=0` (`twin-smoke-2L-fault`, `run-twin-smoke-2L-fault/smoke-fault-headed-scrollbars.*`) | **0 tokens captured** (summarize32's "1/32" is the live, un-captured slot-1 value) | `--fb-ok` **0**, `--fb-cal-p` 0.528573 (the biased progress; decodes to 50257.7), `--fb-agree-e` all 1 (slot 1 had not been fed back yet) | **clientWidth 524273** (15 px scrollbar), offsetWidth 524288, clientHeight 0, `scrollbar-width:auto` | **guard held the run**: head computed token 1 (progress line "token 1 of 32 · vocabulary head"), `#token-1-ready` blocked, red panel visible (`smoke-fault-headed-scrollbars-final.png`), harness stop `guard-held` at 90 s |

So the exact failure environment of the user's runs (headed, classic scrollbars) is caught by the calibration check before the first token; with
the v6 fix in place the same environment runs 32/32 with the guard silent.

### 6.3 Stress test (R7H/stress.sh: six `yes > /dev/null` busy loops for the whole step, killed afterwards; 2-layer smoke twins, typed "Shubham was", 8 tokens, 2 repeats each; headless, hidden scrollbars; `run-twin-smoke-2L-{off,on}/stress-*.{json,summary.md}`)

| run | ids | s/token |
|---|---|---|
| guard OFF #1 | 8/8 | 5.7 |
| guard OFF #2 | 8/8 | 5.6 |
| guard ON #1 | 8/8 | 5.6 |
| guard ON #2 | 8/8 | 5.7 |

The unguarded build did not flip under CPU load (load1 ≈ 9–10 during the step) — consistent with §2: the flip is environmental (scrollport), not a
timing race; the guarded build costs nothing measurable (5.6–5.7 vs 5.6–5.7 s/token). Caveat: six busy loops on this many-core machine raise the
smoke's s/token only from ≈5.0–5.6 (quiet) to 5.7, so this is a mild stress; a frame-starving load would need more loops or renderer-pinned ones.

### 6.4 demo-8.r7h (12 layers, guard ON), dropdown Hello, headless, quiet load (`run-demo-8.r7h/hello-headless.*`)

**ids 8/8** = 11, 314, 1101, 7926, 11, 475, 314, 1101; `--fb-ok` 1 (cal progress 0.52858 exact), all 8 `--fb-agree-e` 1, panel hidden, scroller
clientWidth 524288.
timing: total 151.0 s for 8 tokens; median 19.1; first 17.8; last 20.6; min 16.3; max 20.6

### 6.5 demo-c32.r7h (12 layers, capacity 32, guard ON), HEADED 1100×700 with classic scrollbars shown, typed "Shubham was" (`run-demo-c32.r7h/shubham-headed-scrollbars.*`)

**ids 32/32** vs `R6X/reference_ids_shubham_was.json` — position 14 = **17132** (" Represent"), the position that read 17133 in both of R6X's headed
runs; `--fb-ok` 1, all 32 `--fb-agree-e` 1, panel hidden, scroller clientWidth 524288. This is the user's exact configuration (headed, OS scrollbars
always on, typed prompt) on the guarded v6 build.
timing: linear fit s/token = 15.65 + 0.955·k  (rmse 3.18); tokens 2..32: 15.21 + 0.975·k (rmse 3.18)
timing: total 1005.1 s for 32 tokens; median 34.3; first 19.7; last 47.0; min 15.3; max 47.0
scroller: "scroller":{"clientWidth":524288,"offsetWidth":524288,"clientHeight":1,"scrollLeft":0,"scrollbarWidth":"none","overflow":"scroll"}
