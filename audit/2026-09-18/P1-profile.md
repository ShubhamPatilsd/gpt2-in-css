# P1 — Where the wall-clock goes when `tinystories/streaming-packed8.html` generates tokens

Date: 2026-09-18. Agent P1. Nothing in the repo was modified or rebuilt; all scratch files are under
`audit/2026-09-18/P1-scratch/`. Command log: `audit/2026-09-18/P1-profile.log.md`.

## 0. Headline findings (read this first)

1. **The shipped page does not generate.** `tinystories/streaming.css` on disk has **no**
   `@container style(--winner-id){.streaming-page .handoff{animation:ts-open-gate 1ms steps(1,end) both}}`
   rule. `tools/build_tinystories_nested.py::streaming_css()` emits it, but
   `tools/build_tinystories_dynamic.py:441` later rewrites the same file with `include_winner_gate=False`
   (on-disk mtime Aug 26 14:49 = dynamic build; `streaming-packed8.html` is from Aug 25 02:50).
   Empirically (run `shipped-metrics`): after Play, 0 gate animations in 30 s, computed
   `animation-name` on `.handoff[data-after-token="1"]` is `none`, all later stages stay
   `content-visibility:hidden`. Only the first token (`,`) is ever visible.
2. **Every generation number below therefore comes from a scratch page**,
   `P1-scratch/streaming-packed8-gated.html`: a byte-for-byte copy of the shipped HTML whose four
   `<link>`s point (absolute paths) at the *shipped, unmodified* CSS files, plus one inline `<style>`
   containing exactly the gate rule the nested builder emits. It reproduces all 16 reference token
   IDs. It is labelled "gated" everywhere.
3. **Per token, ~97.5 % of wall-clock is one style recalculation** (`UpdateLayoutTree` /
   `Document::recalcStyle`) that touches **5 elements** (`elementCount: 5`) and takes 650–885 ms.
   Layout (≈0.2 ms), pre-paint/paint (≈0.2 ms), compositor commit, GC (≈0–35 ms of V8/Oilpan
   incremental marking that happens *inside* the recalc) and idle gaps (~10–15 ms between tokens)
   are noise. The main thread is 99.7 % busy during generation.
4. Measured throughput on this machine/Chrome 153 headless: **11.14–11.50 s for 15 post-Play tokens
   = 1.30–1.35 tok/s** (three runs), vs the 12.86 s / 1.17 tok/s reported for Chromium 151.
5. The recalc cost is **per `.model` element, not per changed property**: forcing a recalc of a single
   `.model` element by setting an *unrelated* inline custom property costs the same 650–790 ms as
   changing its winner; a recalc that touches only the `.token-output` decoder costs 0.2–1.8 ms; an
   inherited change on `<body>` (`color`) re-evaluates all 16 stages: **11.5–13.3 s** in one recalc.
   Chromium's trace does not break the recalc down further (no sub-events; release binary is
   stripped so native sampling gives no symbols) — see Caveats.

## 1. Environment

| item | value |
|---|---|
| Machine | Apple M2 Pro, 10 cores, 16 GB, macOS 26.0 (25A354) |
| Browser | Google Chrome **153.0.8010.48** (`/Applications/Google Chrome.app`), launched by Playwright 1.62.1 in new-headless mode, viewport 1000x800, fresh profile each run, flags `--disable-background-timer-throttling --disable-renderer-backgrounding` |
| Node | v24.19.0 at `/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node` (same as Makefile) |
| Playwright | `/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright` (same `createRequire` path the repo's `tools/*.mjs` use). No puppeteer in the repo. |
| Server | `python3 tools/serve_precompressed.py --port 4199` (serves `.br` when accepted; Chrome received the 125 MB head as 25.6 MB br) |
| Prior measurement | RESULTS.md / browser-results.json: Chromium 151, 15 tokens after Play in 12,828 / 12,891 ms, observer = "external browser screenshots until the complete story was painted". **No script for that benchmark exists in `tools/`** (grep for `pause-generation`, `streaming-packed8`, `full_paint` finds none). |

## 2. Method

Scripts (all in `P1-scratch/`):

- `profile_streaming.mjs` — Playwright + raw CDP. Per run: `Performance.enable`, optional
  `Animation.enable`, optional `Tracing` (via `browser.startTracing`), `page.goto(waitUntil:load)`,
  read `performance` navigation/resource/paint entries, wait two rAFs, wait until `RecalcStyleCount`
  is stable 1.5 s ("paused idle"), optional paused-page probes, `performance.mark('P1-play')`,
  `page.click('.pause-control')`, then wait until 16 `Animation.animationStarted` events for
  `ts-open-gate` (handoffs 1–15 gate stages 2–16; handoff 16 is the `completion-marker`, whose
  gate opens only after stage 16's winner exists) or, in `P1_NO_ANIM=1` mode, until
  `RecalcStyleCount` stops changing (the `getMetrics` reply is blocked while a recalc runs, so its
  arrival time is the end of the last recalc). Then two rAFs, `performance.mark('P1-done')`, read the
  16 `::after` contents / `--winner-id`s, screenshot, 3 s idle check, post-completion probes.
  `Performance.getMetrics` is sampled every 200 ms; process RSS every 1 s via
  `SystemInfo.getProcessInfo` + `ps`.
- Probes measure a forced synchronous style update in-page (`performance.now()` around
  `getComputedStyle` after a mutation) and cross-check with the `RecalcStyleDuration` /
  `RecalcStyleCount` deltas from CDP.
- `analyze_trace.py` — parses the gzipped trace, picks the renderer main thread, computes self/inclusive
  time per event name per phase (load+paused / generate / post), per-token windows (each
  `UpdateLayoutTree` > 50 ms after `P1-play`), and what nests inside the big recalcs.
  Output: `gated-trace-analysis.txt`, `gated-trace-summary.json`. (`trace_extra_queries.py` was
  started for finer detail but killed for time; see Caveat 6.)
- Trace categories: `blink, blink.animations, blink.user_timing, blink_style, blink.style,
  devtools.timeline, disabled-by-default-devtools.timeline, disabled-by-default-devtools.timeline.frame,
  v8, disabled-by-default-v8.gc, cc, loading, disabled-by-default-blink.debug`.
  Raw trace: **`P1-scratch/gated-trace-trace.json.gz`** (114 MB uncompressed, 780,372 events).

Runs:

| label | page | trace | notes | files |
|---|---|---|---|---|
| `shipped-metrics` | `tinystories/streaming-packed8.html` (as shipped) | no | paused-page probes, Play, 30 s timeout | `shipped-metrics.json`, `.stdout.log`, `-final.png` |
| `gated-metrics` | scratch gated page | no | clean generation, post probes incl. body-color | `gated-metrics.json` … |
| `gated-trace` | scratch gated page | **yes** | clean generation, post probes (body-color skipped) | `gated-trace.json`, `gated-trace-trace.json.gz`, `gated-trace-analysis.txt`, `gated-trace-summary.json` |
| `gated-noanim` | scratch gated page | no | no CDP Animation domain (perturbation check); macOS `sample` of renderer during the 12 s body-color recalc | `gated-noanim.json`, `gated-noanim-renderer-sample.txt` |
| `nested-shipped` | `tinystories/nested.html` (as shipped; ungated, non-packed 213 MB head) | no | orchestrator-requested cross-check: all 16 stages resolve in one recalc during load | `nested-shipped.json` |

## 3. Results

### 3.1 Page load phases (gated page; shipped page identical within noise)

Network is local; the head arrives as 25.6 MB brotli in ~345 ms. Everything else is CPU.

| phase | gated-trace run | source |
|---|---|---|
| HTML response end | 3–21 ms | `performance` navigation entry |
| CSS downloads complete (4 sheets, 149 MB decoded, 28.9 MB encoded) | 343–372 ms after nav | resource entries |
| Stylesheet parsing (`CSSParserImpl::parseStyleSheet.parse`, 5 events, self time) | **781 ms** (one 836 ms task starting at 343 ms) | trace |
| `StyleEngine::updateActiveStyleSheets` / `RuleSet::addRulesFromSheet` | 20 + 1.6 ms | trace |
| First style recalc (`Document::recalcStyle`, stage 1 = token 1 computed while paused; later stages `content-visibility:hidden`) | **800–805 ms** (one 843 ms BeginMainFrame at 1,179 ms) | trace; CDP `RecalcStyleDuration` after load = 0.822–0.839 s |
| First layout | 10.8 ms | trace |
| `load` event | 2,026–2,126 ms after nav | navigation entry (4 runs) |
| first-paint / first-contentful-paint | 2,088 ms (only reported in one run) | paint entries |
| paused idle (recalc count stable) | ~3.6 s after nav (includes the 1.5 s stability wait) | script |
| main-thread busy during load+paused (3.58 s wall) | 1,924 ms | trace |
| GC during load | ~7 ms (V8 incremental marking) | trace |
| Rule counts (CSSOM) | head 58,819 rules; recurrent 28,388; nested-runtime 7,451; streaming 15 | `document.styleSheets` |

So load = ~0.35 s network + ~0.8 s parse + ~0.8 s first recalc (= one token's worth of work for stage 1) ≈ 2.1 s to `load`.

### 3.2 Per-token phase breakdown (gated-trace run, 15 tokens, Play→done 11,185 ms)

Totals over the generate phase from the trace (renderer main thread):

| bucket | ms | share of wall | count |
|---|---:|---:|---:|
| `UpdateLayoutTree` (style recalc), all | **10,901** | **97.5 %** | 19 (15 of them > 50 ms) |
| of which the 15 token recalcs | 10,869 | 97.2 % | 15, each 649–845 ms, `elementCount: 5` |
| `Document::recalcStyle` self time (no sub-events) | 10,805 (+10,837 incl. tiny ones) | 96.6 % | 18 |
| V8/Oilpan GC nested inside recalcs (`V8.GC_MC_INCREMENTAL*`, `MajorGC` etc.) | ≈60 (0–34 per token) | 0.5 % | 4 MajorGC, ~9k incremental steps |
| Paint lifecycle (`LocalFrameView::RunPaintLifecyclePhase`, PrePaint+Paint+Layerize+Commit) | 178 (mostly 175 ms self) | 1.6 % | 22 frames |
| `Layout` | 3.7 | 0.03 % | 17 |
| `Paint` | 1.5 | 0.01 % | 35 |
| `PrePaint` | 1.5 | 0.01 % | 45 |
| Input/hit-test from the Play click (`handleMouse*`, `HitTest`) | ≈24 | 0.2 % | |
| Script (`EvaluateScript`/`FunctionCall` = the two `performance.mark` calls) | ≈5 | 0.05 % | |
| `RunTask` overhead (self) | 33 | 0.3 % | 7,539 tasks |
| main thread busy | 11,150 | 99.7 % | |
| idle | 35 | 0.3 % | |

Per-token table (trace; `start` = ms after `P1-play`; `window` = to next token's recalc start):

| token | start | recalc ms | elements | layout | prepaint | paint | GC inside | window |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 91 | 649 | 5 | 0.4 | 0.1 | 0.1 | 0 | 661 |
| 2 | 753 | 681 | 5 | 0.1 | 0.1 | 0.1 | 0 | 692 |
| 3 | 1,445 | 709 | 5 | 0.3 | 0.1 | 0.1 | 21 | 721 |
| 4 | 2,166 | 728 | 5 | 0.1 | 0.1 | 0.1 | 32 | 739 |
| 5 | 2,905 | 812 | 5 | 0.1 | 0.1 | 0.1 | 0 | 828 |
| 6 | 3,733 | 845 | 5 | 0.2 | 0.1 | 0.1 | 17 | 857 |
| 7 | 4,590 | 719 | 5 | 0.2 | 0.1 | 0.1 | 32 | 731 |
| 8 | 5,321 | 666 | 5 | 0.2 | 0.1 | 0.1 | 0 | 677 |
| 9 | 5,998 | 732 | 5 | 0.2 | 0.1 | 0.1 | 0 | 748 |
| 10 | 6,746 | 678 | 5 | 0.2 | 0.1 | 0.1 | 17 | 690 |
| 11 | 7,436 | 728 | 5 | 0.2 | 0.1 | 0.1 | 16 | 739 |
| 12 | 8,175 | 845 | 5 | 0.4 | 0.1 | 0.2 | 34 | 858 |
| 13 | 9,033 | 688 | 5 | 0.2 | 0.1 | 0.1 | 0 | 705 |
| 14 | 9,738 | 684 | 5 | 0.2 | 0.1 | 0.1 | 0 | 696 |
| 15 | 10,434 | 704 | 5 | 0.5 | 0.2 | 0.2 | 29 | 752 |

Median token window 721 ms; median recalc 709 ms; the ~12–15 ms per-token gap is the 1 ms gate
animation + frame scheduling + paint lifecycle. Gate-event timings from the other two runs agree
(median interval 748 ms in `gated-metrics`, 722 ms in `gated-noanim`).

Wall-clock end to end (Play → all 16 pieces painted): `gated-metrics` 11,504 ms (1.30 tok/s),
`gated-trace` 11,184 ms (1.34 tok/s, tracing on), `gated-noanim` 11,143 ms (1.35 tok/s, no CDP
Animation domain). Tracing and the Animation domain do not measurably perturb the run.
CDP `Performance.getMetrics` deltas over the same interval: `RecalcStyleDuration` +10.90–11.19 s,
`LayoutDuration` +0.004 s, `ScriptDuration` +0.0007 s, `TaskDuration` +11.15–11.47 s — the same split.

The 5 elements recalculated per token are (by structure) the newly un-hidden `.handoff`, the next
`.model.nested-model`, its `.token-output`, its child `.handoff`, and the `::after` /
completion-marker span. One `.model` element carries every `--ts-*`/`--__1*` custom property
declaration of the transformer (recurrent.css: 28,388 rules / 28,323 `@property`) and evaluates the
head's `@function`s (56,401 functions in the 125 MB head), so "5 elements" ≠ "cheap".

### 3.3 Memory over time (renderer process RSS, MB, from `ps`; JS heap from CDP)

| point | shipped-metrics | gated-metrics | gated-trace | gated-noanim |
|---|---:|---:|---:|---:|
| after launch (about:blank) | 560 | 572 | 576 | 597 |
| after load / paused (stage 1 only) | 1,106–1,124 | 1,009–1,127 | 1,010–1,155 | 1,112–1,223 |
| during generation, max | (probes) 1,521 | 1,879 | 1,983 | 1,934 |
| after generation, idle | — | 1,950 | 1,976–1,982 | 1,740 |
| during post probes (body-color recalc of all 16 stages) | — | **2,691** | 1,892 | **2,999** (`sample` reports 2.6 GB physical footprint) |
| browser process | 170–210 | | | |
| GPU process | 78–140 | | | |
| JS heap used (max) | 1.7 MB | 1.8 MB | 1.8 MB | 1.8 MB |
| DOM nodes / layout objects | 121 / 112 | 124 / 114 | | |

RSS grows ~55 MB per generated token (1.0 → 1.9 GB over 16 stages) and is not returned while the
page is idle; forcing a whole-tree recalc pushes it to 2.7–3.0 GB. JS heap is irrelevant (<2 MB):
all memory is Blink style/CSSOM data. This is consistent with the 1.66 GB "fresh packed renderer RSS"
in browser-results.json only for the *paused/partially generated* state; after all 16 tokens it is ~1.9–2.0 GB here.

### 3.4 Idle recalc vs single-state-change recalc (forced synchronous style updates)

Paused page, only stage 1 visible (run `shipped-metrics`; the paused state is identical on the gated page):

| mutation forcing a recalc | in-page ms (2 iterations) | CDP ΔRecalcStyleDuration | ΔRecalc count |
|---|---:|---:|---:|
| `body.setAttribute('data-p1', …)` (matches no rule) | 0, 0 | 0 | 0 (no recalc at all) |
| `body.style.color = …` (inherited, "independent" property) | 650, 701 | 650, 701 | 1 |
| `body.style.setProperty('--p1-probe-body', …)` (inherited custom prop nobody reads) | 657, 694 | 657, 694 | 1 |
| stage-1 `.token-output` inline unrelated custom prop (decoder-only recalc) | 0.6, 0.1 | 0.2, 0.2 | 1 |
| stage-1 `.model` inline **unrelated** custom prop | 712, 650 | 712, 650 | 1 |
| stage-1 `.model` inline `--winner-id: 612/613` (winning-embedding property changes) | 663, 670 | 663, 670 | 1 |
| restore (remove inline `--winner-id`) | 648 | 647 | 1 |

After all 16 stages are visible (runs `gated-metrics`, `gated-trace`, `gated-noanim`):

| mutation | in-page ms | ΔRecalc |
|---|---:|---:|
| no-op attribute | 0 | 0 |
| `body.style.color` → recalc of the whole tree = all 16 `.model`s | **12,191 / 13,278 / 12,346 / 11,476** | 1 |
| stage-16 `.token-output` unrelated custom prop | 1.8 / 0.2 / 0.4 / 0.3 / 0.3 / 0.2 | 1 |
| stage-16 `.model` unrelated custom prop | 760 / 676 / 688 / 699 / 670 / 673 | 1 |
| stage-16 `.model` `--winner-id` override | 680 / 661 / 715 / 736 / 681 / 676 | 1 |
| stage-16 restore | 725 / 663 / 792 | 1 |
| 3 s idle after generation | 0 recalcs, 0 layouts | |

Conclusion: there is no cheap "nothing changed" recalc for a `.model` element. Any recalc that
reaches a `.model` (inherited change from above, or any inline change on it) re-runs its whole
declared property set — the full transformer step plus output head — for ~650–800 ms, regardless
of whether the winner, an unrelated property, or an inherited colour changed. Only elements below
the model (`.token-output`, ~197-branch `if(style())` decoder) are cheap.

### 3.5 Cross-check on an unmodified page: `tinystories/nested.html` (`nested-shipped`)

Ungated variant (no `content-visibility` gating, non-packed 213 MB head served raw, no Play control):
all 16 stages are resolved in the first style recalcs during load. Three runs (one aborted after
load by a script bug, numbers still valid): `load` at **14,311 / 13,591 / 14,113 ms** after
navigation; cumulative `RecalcStyleDuration` at load **12.55 / 11.94 / 12.29 s** in 2–3 recalcs;
`LayoutDuration` 0.008–0.011 s; no further recalcs afterwards. All 16 winners match the reference
(`, there was a little girl named Lily. She loved to play with her toys`). Renderer RSS peaked at
**3,261 MB** (3,151 MB idle afterwards). I.e. 16 stages ≈ 12.3 s ≈ 0.77 s/stage — the same per-stage
cost as the gated packed8 page and the same as the 11.5–13.3 s whole-tree recalc in §3.4. The 213 MB
head parses in roughly the extra ~1.3 s of load beyond the recalc.

## 4. Interpretation

- **Where does the time go?** Style recalculation: 97–98 % of per-token wall-clock (10.9 s of
  11.2 s). Layout+paint+compositing together ≈ 1.6 %, almost all of it fixed per-frame paint-lifecycle
  overhead rather than actual painting (Paint itself 1.5 ms total). GC ≈ 0.5 % (V8/Oilpan incremental
  marking piggybacking on the recalc; the JS heap is <2 MB, this is Blink heap tracing). Idle ≈ 0.3 %.
  CSS parsing is a one-time ~0.8 s at load. Nothing in the pipeline other than recalc is worth optimising.
- **What is being recalculated?** Per token, 5 elements. The trace's `Document::recalcStyle` has
  **no child events**: Chrome 153's trace instrumentation does not split rule matching, custom-property
  (`var()`/`calc()`) computation, `@function` evaluation or `@container style()` evaluation. The
  `disabled-by-default-blink.debug` `SelectorStats` event appears only 9 times, all in the
  post-generation probe phase, none inside the token recalcs (its args were not extracted, Caveat 6). Native sampling of the renderer (macOS `sample`, 8,240 samples,
  1 ms) resolves only to `ChromeMain + offset` because the release binary is stripped — no
  function-level attribution possible without a symbolized Chromium build.
- **Indirect evidence** about the split: with 58,819 + 28,388 rules but only 3 `.model{}` rules in the
  head and 38 in recurrent.css, selector matching for 5 elements is trivial; the cost is
  evaluating the *declarations* of the matched rules. The probes in §3.4 show the cost is invariant to
  what changed (winner vs unrelated inline property vs inherited colour) and proportional to the
  number of `.model` elements recalculated (1 → ~0.7 s, 16 → ~12 s). Chromium recomputes every
  custom property on an element when its style is recomputed; the `MatchedPropertiesCache` cannot be
  reused because the values depend on inherited custom properties. So the ~700 ms is
  the arithmetic itself (≈28k registered properties per model, `calc()` chains, `if(style())`
  branches and 56k `@function` definitions reachable via `--winner-id` lookups), not invalidation or
  layout. This is an inference, not a trace measurement.
- **Throughput reconciliation**: 1.30–1.35 tok/s here (Chrome 153, headless, no screenshots) vs
  1.17 tok/s reported (Chromium 151, screenshot polling). Screenshot-based observation forces
  extra frames and paint; the gap is plausible but not decomposed here.

## 5. Caveats — what could not be measured, and why

1. **The as-shipped `streaming-packed8.html` was not profiled through generation because it does
   not generate** (missing gate rule, see §0.1). The scratch page differs from the shipped page only
   by the injected rule and absolute CSS URLs; the HTML was served uncompressed (its CSS still came
   from the precompressed `.br`).
2. **Inside-recalc breakdown** (rule matching vs custom-property computation vs `@function`
   evaluation vs container-style queries): not available. `Document::recalcStyle` is a leaf in the
   trace; `blink_style`/`blink.style` categories emit nothing finer in Chrome 153; native stacks
   are unsymbolized. Would require a Chromium build with symbols (or `--enable-tracing` on a
   canary with `disabled-by-default-blink.debug.style`), which is outside "no new installs".
3. **"Visible"**: I did not screenshot per token (the prior method); "done" = the frame after the
   completion-marker gate's animation started (gated runs) or the last `RecalcStyleCount` change
   (`noanim`), then all 16 `::after` contents were read back and a final screenshot saved
   (`*-final.png`). Paint is <2 ms total so the difference to "painted" is negligible.
4. **Headless vs headed**: all runs are Chrome new-headless. RESULTS.md does not say whether its runs
   were headed. Paint-side costs could differ headed, but paint is ~1.6 % here.
5. **Memory**: RSS is a process-level number sampled at 1 Hz with `ps`; peak between samples may be
   higher. Chrome's own `Memory` domain / heap snapshots were not used (the JS heap is irrelevant).
6. A second pass over the trace (`trace_extra_queries.py`: `SelectorStats` args, ancestry of the
   `Blink.ForcedStyleAndLayout.UpdateTime` events, inter-token gap contents, per-sheet parse times)
   exceeded the ~10 min budget and was killed; `trace-extra-queries.txt` is empty. What is known
   from the first pass: `Blink.ForcedStyleAndLayout.UpdateTime` (143 events, 10.89 s inclusive)
   wraps the token recalcs *inside* `ProxyMain::BeginMainFrame` — i.e. the recalc runs during
   animation servicing in the frame, not from script; the trace-level numbers are unaffected by which
   caller triggered it. The 15 `ParseAuthorStyleSheet` / `parseStyleSheet.parse` events total 788 ms
   for the 4 sheets; the per-sheet split was not extracted.
7. `nested.html` uses a different, larger head (203 MB unpacked, raw-served) — its numbers are a
   sanity check on per-stage cost, not a measurement of the packed8 artifact.
8. Single traced run (plus two untraced repeats); variance across runs was ±3 % on total, up to
   ±15 % per token (649–885 ms).

## 6. Files

- Report: this file. Log: `P1-profile.log.md`.
- Scripts: `P1-scratch/profile_streaming.mjs`, `P1-scratch/analyze_trace.py`, `P1-scratch/trace_extra_queries.py`.
- Scratch page: `P1-scratch/streaming-packed8-gated.html`.
- Raw data: `P1-scratch/{shipped-metrics,gated-metrics,gated-trace,gated-noanim,nested-shipped}.json`
  and `.stdout.log`, `P1-scratch/gated-trace-trace.json.gz` (raw Chromium trace),
  `P1-scratch/gated-trace-analysis.txt`, `P1-scratch/gated-trace-summary.json`,
  `P1-scratch/trace-extra-queries.txt`, `P1-scratch/gated-noanim-renderer-sample.txt`,
  `P1-scratch/*-final.png`, `P1-scratch/server.log`.
