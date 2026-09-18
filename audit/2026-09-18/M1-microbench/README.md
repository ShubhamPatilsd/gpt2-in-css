# M1 micro-benchmarks: isolating the atomic Blink costs

Sixteen prior audit reports agree on the symptoms of the CSS-only GPT-2 page —
~119 style recalcs and ~71 layouts per generated token, stage arithmetic that
sums to ~9 s against 78–143 s of wall time, and a suspiciously constant
~43 MB/s of "re-evaluated CSS declaration text" in the pure `calc()` pipeline
(C1 §7) — but nobody has measured the atoms. These pages each change ONE
registered custom property (`--in`) and let Chromium's own trace tell us what
that single mutation costs, with the page structure varied one axis at a time.

Everything here is self-contained: `gen.py` (pages), `run.mjs` (harness),
`parse_trace.mjs` (trace → atoms), `pages/` (81 generated pages, 477 MB,
seed 20260918), `results/`, `traces/`. No `<script>` anywhere in the pages.

## How to run

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/audit/2026-09-18/M1-microbench
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node

# (re)generate pages -- deterministic for a given --seed
python3 gen.py                       # all families; or --only mb3,mb5

# preflight + list what would run, without launching Chromium
$NODE run.mjs --dry-run

# the full run (≈81 variants × 5 trials; budget 1.5–3 h, most of it page loads)
caffeinate -dims $NODE run.mjs --trials 5 --warmup 1

# recommended first pass: the small, fast families
caffeinate -dims $NODE run.mjs --filter 'mb3-|mb5-|mb2-a-var-N0' --trials 5

# variants: inline random value per trial instead of pre-baked class values;
# no warm-up so the traced mutation is the very first one after load
caffeinate -dims $NODE run.mjs --trigger inline --warmup 0 --filter 'mb1a-'

# re-parse a saved trace
$NODE parse_trace.mjs traces/mb3-container-S12.trace.json.gz
```

Preflight refuses to run when not on AC power (`--allow-battery` to override)
or when other Chrome/Chromium renderer/headless processes are alive
(`--force` to override — do NOT while another agent is tracing). It warns if
`caffeinate` is not running. Environment (Chrome version from Info.plist, CPU,
`pmset -g therm` CPU speed limit, git HEAD, flags) goes to
`results/run-<timestamp>.env.json`; the thermal line is re-sampled per variant.

Toolchain assumed (from the repo's other harnesses): playwright 1.62.1 from
`$CODEX_NODE_MODULES` (default the codex runtime node_modules), Google Chrome
153.0.8010.48 at `$CHROME_PATH`, node v24. Launch = `chromium.launch({executablePath, headless:true, args})`
with only anti-throttling args added (`--disable-background-timer-throttling`,
`--disable-renderer-backgrounding`, `--disable-backgrounding-occluded-windows`).

## What one trial does

1. Fresh `BrowserContext` (`javaScriptEnabled:false`, 800×600), fresh CDP session; `Performance.enable`, `DOM.enable`, `CSS.enable`.
2. `page.goto(file://…)` until `load`, then poll `Performance.getMetrics` every 50 ms until `RecalcStyleCount` and `LayoutCount` are unchanged for 500 ms.
3. `--warmup W` (default 1) untraced mutations, each followed by the same quiescence wait. (Use `--warmup 0` to measure the cold first mutation.)
4. Read the verify property (`CSS.getComputedStyleForNode`, e.g. `--p0` on the element under test).
5. `Tracing.start` with `blink,blink.style,blink.animations,devtools.timeline,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.invalidationTracking,cc,loading` (`recordContinuously`, `ReportEvents`); sleep 150 ms; `Performance.getMetrics` (before).
6. THE mutation, via CDP only:
   * `--trigger class` (default): `DOM.setAttributeValue(<html>, class, "go-k")`. Each page carries 16 pre-baked random values in `html.go-0…15 [target]{--in:v}` rules; the harness cycles k so no trial repeats the previous value.
   * `--trigger inline`: `DOM.setAttributeValue(target, style, "--in:<fresh random>")` — fully random per trial.
7. Quiescence wait (as in 2) but requiring at least one recalc; if none is seen for 3 s, `DOM.getBoxModel(target)` forces a lifecycle and the trial is flagged `forced`.
8. `Performance.getMetrics` (after), `Tracing.end`, parse, read the verify property again (`verified = changed`), sample renderer RSS (`SystemInfo.getProcessInfo` + `ps`).
9. One JSON line → `results/<variant>.jsonl`; trial 0's trace → `traces/<variant>.trace.json.gz` (`--save-all-traces` for all). `results/summary.md` / `summary.json` are rewritten after every variant.

Per trial the parser reports, on the renderer main thread and inside the
[before, after] window: every `UpdateLayoutTree` (dur, `elementCount`), every
`Layout` (dur, `dirtyObjects`, `totalObjects`, `partialLayout`), `PrePaint`,
`Paint`, `UpdateLayerTree`, `Layerize`, `Commit`, `ParseAuthorStyleSheet`
(should be 0 — nonzero means a stylesheet was re-parsed), invalidation-tracking
counts by reason (`StyleRecalcInvalidationTracking`,
`StyleInvalidatorInvalidationTracking`, `ScheduleStyleInvalidationTracking`,
`LayoutInvalidationTracking`), async `Animation` events by state plus self time
of every event whose name matches `Animation|Timeline|Keyframe|…`, top-level
main-thread busy time, and the 60 largest self-time event names. Cross-check:
`Performance.getMetrics` deltas (`RecalcStyleCount/Duration`,
`LayoutCount/Duration`, `ThreadTime`, `JSHeapUsedSize`, `Nodes`, …).

## The benchmarks, hypotheses, and what each result decides

Notation: ULT = `UpdateLayoutTree` total ms in the window; "MB/s" in the
summary = page bytes / ULT ms (the whole page, so it is only meaningful where
the whole page is the element under test — MB1a, MB5).

### MB1 — is per-element re-evaluation O(declared bytes)? (16 pages, 140 MB)

One element E carries K registered `<number>` properties
`--pI: calc(var(--in)*w + var(--c2)*w + … M terms)`; `--in` changes on `<html>`.

* **MB1a** K ∈ {1000, 10000, 40000} × M ∈ {1, 16, 64} ((40000,64) replaced by (20000,64) to stay < 30 MB).
  Hypothesis H1: ULT ms is linear in K·M (bytes) at ≈43 MB/s and independent of K at fixed bytes.
  Holds → the atom is "bytes of `var()`-bearing declaration text on restyled elements"; every design must minimize declared bytes on any element that is ever dirtied.
  Fails (time ∝ K, not K·M) → per-declaration overhead dominates (cascade/hash/registration lookup); pack many terms per declaration.
  Fails (time ≪ 43 MB/s) → the GPT-2 43 MB/s is not this path; look at MB2/MB3.
* **MB1b** only `--p0` references `--in`; the other K−1 are `calc(lit*lit + …)` of the same byte length.
  H1b: Blink re-applies all K declarations when E is restyled, but literal-only declarations were parsed once at sheet load, so cost ≈ MB1a's K=1 case + small per-declaration constant.
  MB1b ≈ MB1a → Blink re-tokenizes/re-parses everything regardless of `var()`: nothing but byte count matters.
  MB1b ≪ MB1a → `var()` substitution + re-parse is the cost; weights should live in parsed-once literal form (or `@function` bodies), and dependent text should be minimized.
* **MB1c** K properties spread over K/200 siblings; `--in` changes on the common parent (`…-parent`) vs on one sibling only (`…-sibling`).
  H1c: parent ≈ n × sibling (all siblings inherit `--in`, so all are restyled). Also compare `elementCount` in `UpdateLayoutTree`.
  Holds → dirtying is by inheritance, cost is additive per dirtied element: partitioning without isolation does not help.

### MB2 — inheritance dirtying of unrelated descendants (25 pages, 240 MB)

`--in` on `<html>`; N flat descendants each carry b bytes of declarations that
do NOT reference `--in` (`var` flavour: `--qJ: calc(var(--cX)*w)` referencing a
constant root property; `lit` flavour: plain literals). Sizes: N ∈ {1000, 10000, 40000}, b ∈ {200, 2000} (largest 24 MB); baseline N=0.

* **(a) plain** — H2a: the `var` flavour costs ≈ N·b at the MB1 rate: Blink has no per-declaration dependency tracking, every dirtied element re-substitutes all its `var()`s. The `lit` flavour should be far cheaper if Blink's independent-inherited-property fast path (children without `var()` references get a cloned style) engages.
  If `lit` ≈ `var` → the fast path does not apply to registered custom properties; the cost is restyle itself, not substitution.
* **(b) `--in` registered `inherits:false`** — H2b: ≈ baseline (descendants are never dirtied). This is the "correct" control; if it is NOT ≈ baseline, something else (e.g. the `html` element's own declarations or the `#vis` consumer) is being charged.
* **(c) descendants inside `content-visibility:hidden`** — H2c: ≈ baseline (display-locked subtrees skip style recalc). Holds → locking inactive stages is sufficient and the GPT-2 nested `content-visibility` gate is the right primitive; the per-token cost must come from the *unlocked* stage(s). Fails → locking does not stop restyle and a different isolation (b or a separate document) is required.
* **(d) each descendant `contain:style`** — H2d: no effect (style containment scopes counters/quotes only). If it helps, that is a cheap win worth confirming.
* **(e) declarative shadow root** — H2e: no effect (inheritance crosses shadow boundaries). If shadow DOM DOES reduce cost, it is via style-scoping/rule-matching, which would indicate selector matching rather than cascade is the cost.
* **(f) depth-100 chains instead of flat** — H2f: ≥ (a) with the same N·b; the excess (if any) is the inherited-variable-map copy-on-write per level (C1 §4.3 estimated 5–20 ms per copy of ~29k entries). If (f) ≫ (a), depth is a first-order cost and the nested stage chain should be flattened.

Decision rule from the brief: "if MB2(c) ≈ 0 then locking inactive stages is sufficient; if MB2(a) is linear in N×b at ~43 MB/s then root-bank writes are the atom" (every inherited write to a root bank restyles everything under it at that rate).

### MB3 — passes per boundary mechanism (12 pages, tiny)

S ∈ {1, 4, 12} stages, each a 64-term `calc`, chained through one of four
boundary mechanisms. Per-boundary cost = (S=12 − S=4)/8 for each metric.

* **style** (control) — H3s: exactly one `UpdateLayoutTree`, zero `Layout`, for any S.
* **container** — nested size containers, `width: calc(var(--y)*1px)`, child reads `--x: calc(100cqi / 1px)`. H3c: Blink interleaves style and layout per container: expect +1 `Layout` (possibly +1 `UpdateLayoutTree`) per boundary, all within one frame.
* **anchor** — `position-anchor` + `width: anchor-size(--a width)` on an abspos size container, child reads `100cqi`. H3a: ≥ container cost, likely 2 layout passes per boundary (anchor resolution + container).
* **viewtimeline** — metric width inside an off-screen 100 px scroller, `view-timeline`, reader animates `--p` over `animation-range: cover`, recovers `100/p − 100`. H3v: each boundary requires a *frame* (scroll-timeline progress is sampled in the animation update), so S boundaries ≈ S frames ≈ S × (vsync interval) of wall time even when the work is microseconds, plus `Animation` events per stage.

What it decides: the GPT-2 page's ~119 recalcs / ~71 layouts per token are (C1 §4.1) a consequence of boundary mechanisms; MB3 gives the per-boundary atom (events and ms) for each mechanism so the 12-layer × (attention+MLP) boundary count can be priced and the mechanism with the fewest passes chosen. If `viewtimeline` costs a frame per boundary, any design that chains ≥60 timeline hops per token has a ≥1 s floor regardless of arithmetic. `verified` must be true for the mechanism to count; a false there means the geometry hop did not resolve (e.g. anchor not acceptable) and the timing is void.

### MB4 — retained animation servicing (20 pages, 57 MB)

A ∈ {1000, 10000, 100000} elements each with a finished 1 ms `forwards`
animation on registered `--a` (unique `@keyframes` per element), or the same
with `animation-play-state: paused`, or the same values as static declarations.
Scope `sib`: `--in` changes on a sibling `#target` (the A elements are NOT
restyled) — measures pure per-mutation/per-frame animation bookkeeping. Scope
`inh`: `--in` changes on `<html>` — the A elements are restyled with their
animation effect stack applied. Baselines A=0 for both scopes.

* H4: `sib`/`fwd` and `sib`/`paused` ≈ A=0 (finished/paused animations are not serviced per frame) — if instead cost grows with A, the GPT-2 page's 129k retained transitions (E1 §H) are a per-token tax even when untouched, and KV retention must move to static declarations or a locked subtree.
* `inh`: expect `fwd` > `static` by the effect-application cost per element; the gap is the price of "animation as latch".

### MB5 — what the 43 MB/s is (7 pages, 41 MB)

K = 10000 properties on `#target` (the mutated element itself, so nothing else is restyled; constants live on `<body>`, which is not restyled). Every declaration is padded to 320 bytes (extra digits spread over all numeric literals; token count unchanged) except `lit-short` (12 B) and `calc-varw` (~454 B, naturally longer).

| spelling | var() per decl | typed eval | what it isolates |
|---|---:|---|---|
| `lit-short` | 0 | yes | floor: K registered declarations, no arithmetic |
| `lit-calc` | 0 | yes | 16-term literal `calc` parsed once at sheet load: cascade + apply only |
| `calc-var16` | 16 | yes | reference: substitute 16 `var()` → re-parse → evaluate |
| `calc-var1` | 1 | yes | 1 `var()` + 15 literal products, same bytes: cost ∝ var count or ∝ bytes? |
| `calc-varw` | 32 | yes | weights via `var(--wI_j)`: 2× var count, +40% bytes |
| `func16` | 16 (inside body) | yes | one `@function` invoked K times with 16 args |
| `unreg-var16` | 16 | no | substitution only, no typed parse/eval |

* H5: `lit-calc` ≈ `lit-short` ≪ `calc-var1` < `calc-var16` < `calc-varw`, and `unreg-var16` ≈ `calc-var16` minus the evaluation share.
  * `calc-var1` ≈ `calc-var16` → cost ∝ bytes re-tokenized, not var count: "43 MB/s = tokenizer + parser". Shorten text (fewer digits, `@function` bodies, packed weights).
  * `calc-var1` ≪ `calc-var16` and `calc-varw` ≈ 2× → cost ∝ `var()` substitutions: reduce var count (bake weights as literals, hoist shared sub-expressions).
  * `unreg-var16` ≪ `calc-var16` → typed parse+evaluate is the cost: use fewer, larger evaluations (`@function` with internal locals) — check `func16`.
  * `func16` ≫ `calc-var16` → per-invocation overhead (argument binding) dominates; the GPT-2 head's 12.5k invocations/token are paying it.

## Reading the results

`results/summary.md` has one row per variant with medians [min–max] over
trials. Compare within a family only; compare families only after subtracting
the family's baseline (MB2 N=0, MB4 A=0, MB3 S=1). Trust a difference only if
the min–max ranges do not overlap (S7: run-to-run variance has repeatedly
exceeded effect sizes in this project). The `verified` column must read n/n;
`err` must be empty; a `FORCED` trial means no frame was produced by the
mutation alone and its timing includes a synchronous forced lifecycle.

Sanity checks the parser exposes: `parseAuthorStyleSheet.count` must be 0 in
the window; `invalidation.styleRecalc.byReason` should be dominated by
"Inherited style change"/attribute or class reasons (anything else means the
mutation is not what we think); `updateLayoutTree.elementCounts` should equal
the number of elements you expect dirtied (MB2 (b)/(c) ≈ 2; (a) ≈ N+3).
