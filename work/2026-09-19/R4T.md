# R4T — per-frame view-timeline servicing vs DOM depth / scroller structure (step 1 done; R4T READY 01:38; mechanism fixture done 03:05: no ≥0.5 ms/element mechanism -> R4T stands at capacity 8; R4T2 smoke/correctness running; cap-32 slope = open question)

Status: sweep1 (24 variants x 3 trials, lock 23:53–00:02, load 4–8) DONE -> fitted model below. sweep2 (cost per changing carrier vs animations per
consumer element; 10 variants x 3) RUNNING under the lock since 00:12 -> `R4T/fixture/results/sweep2.jsonl`; analyse with
`python3 R4T/fixture/analyze.py R4T/fixture/results/sweep2.jsonl`.

## Demo topology measured from bundles/combined4 (index.html / runtime.css)
- ≈9.3k live view-timelines in 9 scrollers (`.scroller{position:fixed;top:-60000px;overflow-x:scroll;contain:strict;visibility:hidden}`) at DOM depths
  5, 13, 17, 20, 32, 38, 40, 44, 47; subjects `.metric{position:absolute;display:inline-flex;height:1px;overflow:clip}` two levels below the scroller
  (scroller > track > metric); carrier counts 769/769/2305/769/3073/97/768(span)/769 (+8 feedback).
- `timeline-scope`: 1,635 names on `html` (embedding, b11 bridge, folded proj, stamps) + per-stage scopes on `.shared-qkv/.shared-attn/.shared-fc`.
- Scroller is a child of the stage element (`build_hybrid_twelve_block.py:293`); the stage sits inside the previous stage's `*-gate`
  (`content-visibility:hidden` until its receipt's style query opens it). Carriers read the stage's inherited computed font + inherited numbers,
  so scrollers cannot be hoisted above the stage element without re-publishing the stage inputs: a depth hoist = moving whole stages.

## Fixture (R4T/fixture/gen_r4t.py, run_r4t.mjs, run_r4t.sh, analyze.py)
N=2,000 carriers (demo shapes), 1 s tick animation forcing 60 frames/s; knobs: scroller depth `above` 2/20/40/60, subject depth `below` 0/5/20/40/60,
scrollers 1/12/96, subject abs/inline-block/inline, `contain:layout` / `content-visibility:auto` on wrappers, scope near/root, consumers 1/16,
half the carriers changing every frame (`change50`, the two-passes-per-frame hop shape), 100k inert DOM, heavy wrappers (200 inherited numbers each),
a demo-like combo (above 40, 12 scrollers, scope root, 12 consumers) ± contain/cv/below20/change50. Per trial: values check (exact i+in round trip),
2 s idle metrics window, 1.5 s light trace parsed per frame (frame = RunTask containing WebFrameWidgetImpl::BeginMainFrame; animate, serviceScriptedAnimations
self, serviceAnimations X+I count, UpdateLifecycle self, UpdateLayoutTree/Layout/paint lifecycle).

 (72 trials; medians of per-frame medians; `R4T/fixture/results/sweep1-summary.md`)

Idle servicing of N=2,000 live view-timelines, all variants at 60 fps, values exact (3/3 samples every trial):

| knob | busy ms/frame | vs base | verdict |
|---|---:|---:|---|
| control (0 carriers) | 0.14 | | frame floor |
| base (depth 2, 1 scroller, abs subjects) | 6.25 | 1.00 | 3.06 µs/carrier/frame (n1000: 3.36 ms -> linear, 3.06 µs/carrier + 0.19 ms) |
| scroller depth 20 / 40 / 60 | 6.54 / 6.90 / 6.17 | 1.05 / 1.10 / 0.99 | **no depth term** (fit 0.23 ns/carrier/level, R² 0.00) |
| wrappers between scroller and subject 5 / 20 / 40 / 60 | 6.73 / 8.79 / 11.02 / 16.33 | 1.08 / 1.41 / 1.76 / 2.61 | **80 ns/carrier/level (R² 0.96)** = the subject->scroller geometry walk (UL self 1.16 -> 5.40 ms, ssa self 2.7 -> 6.3, paintLC 0.74 -> 2.77); the demo has exactly 1 (track) |
| 12 / 96 scrollers | 6.35 / 7.59 | 1.02 / 1.21 | none / small |
| inline-block / inline subjects | 6.01 / 6.42 | 0.96 / 1.03 | none |
| timeline-scope on html | 5.82 | 0.93 | none |
| 16 consumer elements | 5.68 | 0.91 | none (idle) |
| 40 wrappers x 200 inherited numbers | 5.86 | 0.94 | none |
| +100k inert elements | 5.92 | 0.95 | none |
| demo-like (depth 40, 12 scrollers, scope root, 12 consumers) ± contain:layout / content-visibility:auto | 5.83 / 5.88 / 5.83 | 0.93 | none |
| **1,000 of 2,000 carriers change width every frame, 1 consumer** | **127.0** (8 fps) | 20.3 | 63 µs per changed carrier: paint lifecycle self 95.7 ms + recalcStyle 21.2 ms (2 passes: 2002 + 1 elements) |
| same, spread over 6 of 12 consumer elements (≈167 animations each) | **29.8** | 4.8 | 15 µs per changed carrier: paintLC 11.0 ms + recalc 9.9 ms |

Per-frame anatomy of base (2,000 idle timelines): animate 3.98 ms (serviceScriptedAnimations self 2.70 + 4,001 serviceAnimations 1.25 ms),
UpdateLifecycle self 1.16 (snapshot validation), paint lifecycle 0.74, style 0.09. = 3.06 µs/timeline/frame; the traced serviceAnimations part is
0.62 µs, the rest is untraced self time of the two sweeps + snapshot validation + PendingAnimations::Update.

### Fitted cost model (idle frame, N live view-timelines, per frame)

    ms/frame = 0.14 + N x (3.06 µs + 0.08 µs x wrappers_between_scroller_and_subject) + 0.5 µs x scroller_depth (≈0) + 13 µs x scrollers
    hop frame adds, per carrier whose width changed: ≈15 µs (167 anims/consumer) … 63 µs (2,000 anims/consumer)  <- sweep2 fits this curve

For combined4 (≈9.3k timelines, 1 wrapper, 9 scrollers, ≈40 frames/token): idle servicing ≈ 0.14 + 9.3k x 3.14 µs ≈ 29 ms/frame ≈ 1.2 s/token —
about a third of R3A's ≈95 ms/frame (117 minus the hover pass); the remaining ≈65 ms/frame of the demo's "fixed" cost is not idle servicing of deep
subjects but the hop's changed carriers (R3A's 40 µs/changed animation + 28 µs/pending add), which this fixture reproduces at 15–63 µs depending
on how many animations share the consumer element.

### Verdict on the round-4 question
DOM depth of the subject/scroller does NOT drive per-frame servicing (≤10 % at depth 40–60); scroller count, subject display, scope placement,
containment, DOM size do not either. Flattening carriers would save ≤ 0.1 s/token -> **no flat-carrier bundle** (and a hoist is structurally
blocked: carriers inherit the stage's computed font and numbers, so they must stay under the stage element).

## The knob that does move the cost: animations per consumer element (sweeps 2–3, 42 trials; `R4T/fixture/results/curve.md`)

Each frame in which a carrier's width changed costs, per changed carrier, an amount that grows with the number of animations sharing its
consumer element (the element whose `animation-name`/`animation-timeline` lists reference the carriers):

| variant | carriers | consumers | changing | nested | changing anims per element | busy ms/frame | paintLC ms | style ms | µs per changed carrier (busy − idle model) | of which paintLC | of which style |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| c100-cons1 | 2000 | 1 | 100 % |  | 2000 | 220.6 | 187.7 | 23.1 | **107.1** | 93.8 | 11.5 |
| n1000-c100-cons1 | 1000 | 1 | 100 % |  | 1000 | 61.0 | 46.7 | 10.1 | **57.8** | 46.7 | 10.1 |
| change50 | 2000 | 1 | 50 % |  | 1000 | 127.0 | 95.1 | 23.3 | **120.7** | 95.1 | 23.3 |
| n500-c100-cons1 | 500 | 1 | 100 % |  | 500 | 18.2 | 11.8 | 4.4 | **33.0** | 23.6 | 8.7 |
| c100-cons4-nested | 2000 | 4 | 100 % | y | 500 | 85.1 | 51.6 | 23.3 | **39.4** | 25.8 | 11.7 |
| c50-cons4 | 2000 | 4 | 50 % |  | 250 | 47.8 | 25.7 | 14.4 | **41.6** | 25.7 | 14.4 |
| c100-cons8-nested | 2000 | 8 | 100 % | y | 250 | 58.2 | 28.7 | 20.0 | **26.0** | 14.3 | 10.0 |
| c100-cons16 | 2000 | 16 | 100 % |  | 125 | 46.3 | 16.1 | 20.2 | **20.0** | 8.0 | 10.1 |
| c100-cons16-nested | 2000 | 16 | 100 % | y | 125 | 45.3 | 15.9 | 20.5 | **19.5** | 7.9 | 10.2 |
| demo-change50 | 2000 | 12 | 50 % |  | 83 | 29.8 | 10.8 | 11.8 | **23.6** | 10.8 | 11.8 |
| c50-cons16 | 2000 | 16 | 50 % |  | 62 | 30.6 | 8.4 | 14.4 | **24.3** | 8.4 | 14.4 |
| c100-cons32-nested | 2000 | 32 | 100 % | y | 62 | 39.3 | 9.9 | 20.6 | **16.5** | 5.0 | 10.3 |
| c100-cons64 | 2000 | 64 | 100 % |  | 31 | 38.4 | 7.2 | 20.3 | **16.1** | 3.6 | 10.1 |
| c100-cons64-nested | 2000 | 64 | 100 % | y | 31 | 38.1 | 7.0 | 21.2 | **15.9** | 3.5 | 10.6 |
| c50-cons64 | 2000 | 64 | 50 % |  | 16 | 26.4 | 4.1 | 14.4 | **20.1** | 4.1 | 14.4 |
| c100-cons128-nested | 2000 | 128 | 100 % | y | 16 | 39.6 | 5.8 | 22.8 | **16.7** | 2.9 | 11.4 |

Fit over the 100 %-changing rows: **µs per changed carrier per frame = 14.1 + 45.8 ns × changing animations on its consumer element** (R² 0.996); at 512 (combined4) → 38 µs (R3A measured 40 µs/changed animation + 28 µs/pending add ≈ same frame work), at 64 → 17 µs, at 32 → 16 µs. Knee ≈ 64: the 62/31/15 rows are flat within noise ([16.5, 16.1, 15.9, 16.7]).

Where it goes: `RunPaintLifecyclePhase` self (PendingAnimations::Update, untraced) 3.5 → 94 ms, i.e. ≈46 ns × animations-on-the-element per changed
carrier — Blink re-walks the element's whole animation list for every changed animation (quadratic per element); the style pass is a flat ≈10 µs per
changed carrier (2 passes/frame: carriers restyled + the consumers' effect application) and does not depend on the split. Nesting the chunk elements
(demo shape: c0 > c1 > … > readers) costs nothing extra vs siblings. The idle servicing (3.06 µs/timeline/frame) is unchanged by the split
(cons16 idle: 0.91× base).

combined4 puts 512 animations on every matvec/bridge consumer, 768 on `.loop-reader`, 256 on the embedding consumers => 38 µs per changed carrier
by this fit = R3A's measured 40 µs "per changed-timeline animation". At 64 per element: 17 µs. Per token combined4 changes ≈8.3k carriers per layer x 12
+ ≈1.5k token-level ≈ 100k => predicted **−2.0 to −2.3 s/token** (100k × 21 µs; R3A's separately fitted 28 µs "per pending add" is the same paint-lifecycle
work seen from the other side, so the two are not additive).

## Step 2 — R4T_CONSUMER_CHUNK (default 64; 0 = off) — `R4T/tools` (diff `R4T/tools-vs-R3M.diff`, 169 lines)

- `tools/r4t_consumer_chunk.py` (new): flag, `chunk(default)`, `loop_reader_classes(width)`.
- `browser_gpt2_reused_core.py`: `h.matvec(..., r4t.chunk(512), ...)` (qkv/attn/fc consumers → 36/12/48 nested `.shared-KIND-cN` elements) and
  `h.bridge(100, r4t.chunk(512))` (cache-bridge → 12).
- `browser_gpt2_reused_adapter.py`: `hybrid.bridge(last, r4t.chunk(512))` (b11-bridge → 12); manifest `r4tConsumerChunk`.
- `r3r_fold_hop.py`: the 768 `.loop-reader` animations move to 12 nested `.loop-reader-cK` elements between `.loop-reader` and `.loop-input`
  (`--lp-*` are inherited registered numbers; `.loop-reader` keeps its class for the position/epoch rules and the uncached-style selector).
- `browser_gpt2_embedding.py`: `.embedding-consumer-N` step 256 → 64 (12 elements).
- `r2g_has_scope.py`: `LOOP_CHAIN` gains the `.loop-reader-cK` steps (R3F's fixed-depth `:has()` chain is verified against the page at build time).
- Left alone: `.fvs-score-reader` (24 animations in the 2-layer build / 96 at capacity 8 → predicted 18.5 vs 17 µs), `browser_gpt2_core.py:335`
  (non-reused scalar path, not built here), `.feedback-reader` (2).
- Pass/frame structure: unchanged by construction — the chunk elements are restyled in the same pass as their parent consumer (same
  `animation-timeline` changes, same `@container` context); verified in the 2-layer smoke below (same UpdateLayoutTree / Layout / frame counts).

### 2-layer smoke (`bundles/smoke-R4T-2L` vs `bundles/smoke-R4T-2L-ref` = chunk 0, same tools; `R4T/offline_check_r4t.py`: PASS)
max animations/element 64 (ref 512/768/256); consumer elements 240 vs 34 (elements 62,352 vs 62,228); non-consumer CSS byte-identical; HTML identical
modulo the wrapper elements; manifest differs only in `r4tConsumerChunk`; font witnesses identical. Chrome run 01:37–01:40 (lock after R4D, load ≈6): **ref `[11, 3387]` OK; R4T `[44873, 9890]` WRONG** — see §Failure below.

### 12-layer bundle `bundles/R4T` — built 01:10, offline verification PASS (`bundles/R4T/BUILD.md`)
Max 64 animations per consumer element (combined4: 512/768/256); 1,200 consumer elements vs 164 (+124 DOM elements); non-consumer CSS byte-identical to
combined4; HTML identical modulo the wrapper elements; manifest differs only by `r4tConsumerChunk`; 283/283 font witnesses identical; static check
285,654,970 B, no JS. runtime.css 39.13 MB (+156 KB of repeated per-chunk timing declarations).

### Chrome runs (pending the lock, held by R4D since 00:10)
`R4T/finish_after_smoke.sh` (running, nohup): waits for the queued paired 2-layer smoke (`R4T/run_smoke.sh smoke2L smoke-R4T-2L smoke-R4T-2L-ref`,
light trace, `frames.py` per bundle -> `R4T/runs/<bundle>/frames.md` for the pass/frame-count comparison), gates on ids `[11, 3387]` in both, then runs
ONE passive 8-token correctness run (`R4T/run_correctness.sh R4T` = R3M's protocol) and writes `bundles/R4T/READY` only on 8/8 ids + verify rc 0.
Log lines land in `R4T.log.md` (`[R4T smoke/…]`, `[R4T correctness/R4T]`, `[R4T finish]`).

### Predicted effect (for B5's paired bench vs combined4)
≈100k changed carriers/token x (38 − 17 µs) ≈ **−2.0 to −2.3 s/token** -> ≈16 s/token from 18.2; idle servicing unchanged; no new passes or frames.
For R4D (capacity 32): the same flag applies unchanged (the chunk elements are inside the reused core); the per-changed-carrier constant is what grows
with more animations per element, so any capacity-32 consumer that gains animations should also be chunked to ≤ 64.

## Step-2 failure, diagnosis, fix (01:44–01:52)

- Symptom: 2-layer smoke of `smoke-R4T-2L` gave ids `[44873, 9890]` (ref, same tools with chunk 0: `[11, 3387]`); token 1 already wrong.
  Frame structure of the wrong run: 27 frames / 54 UpdateLayoutTree / 32 Layout vs ref 26 / 53 / 32 (one extra frame+pass; re-compared after the fix).
- `verification-vectors.json` diff (`R4T/runs/smoke-R4T-2L{,-ref}`): `finalResidual` (`#core-result --x-000..767`) is **0 for all 768** in the R4T run
  vs real values in the ref; `finalHidden` identical. `0` is exactly `decode(--lp-i = initial 0)` = `(1572864/(0+2) − 524288 − 262144)/128` — the
  layer-11 export reads `--loop-in-*`, which `.loop-input` decodes from `--lp-*`. The embedding, matvec and bridge chunks decode on the same
  element that carries the animation, so they cannot be affected; the loop reader is the only site where the decode (`.loop-input`) sits on a
  *different* element from the animations.
- Mechanism: the core's `scoped_state` re-registers `--lp-*` as `inherits:false` and forwards them with `.loop-input{--lp-i:inherit}` — a one-level
  copy from the parent. With the chunk chain the parent of `.loop-input` is `.loop-reader-c11`, which holds only `--lp-704..767`; the other 704
  values were the initial 0.
- Fix (`r3r_fold_hop.py`): every `.loop-reader-cK` forwards the earlier chunks' values (`--lp-0..64k−1:inherit`, 4,224 declarations in total) so the
  innermost element holds all 768 for `.loop-input`'s copy. Offline checker: `inherit` forwarding is structural and excluded from the declaration
  multiset (reported separately). 2-layer offline check of the fixed build: PASS.
- Re-verification chain `R4T/finish_v2.sh` (running): smoke of the fixed `smoke-R4T-2L` (ref run kept) -> id gate `[11, 3387]` + frame/ULT/Layout
  counts vs ref -> 12-layer rebuild + offline check vs combined4 -> ONE passive 8-token correctness run -> `bundles/R4T/READY` only on 8/8 + verify rc 0.

### Fixed 2-layer smoke (machine time 01:00:10–01:00:53, load ≈5) — PASS
`smoke-R4T-2L` (chunk 64, fixed): ids **`[11, 3387]`**, done markers 2/2. Whole-session light trace counts vs the kept ref run (`smoke-R4T-2L-ref`, chunk 0):
**frames 26 / UpdateLayoutTree 53 / Layout 32 in both** -> the pass/frame structure is unchanged. Time (ms): UpdateLayoutTree 6,676 vs 6,232 (+7 %,
within load noise on a 2-layer/2-token run), Layout 3,111 vs 3,103, animate 743 vs 715, **paint lifecycle 396 vs 1,018 (−61 %)** — the
PendingAnimations::Update term the fixture predicted (2-layer smoke has 6 hop frames/token with ≈8k changed carriers each; at 12 layers x 8 tokens
the same term is ≈100k changed carriers/token x 21 µs ≈ 2 s/token).
12-layer `bundles/R4T` rebuilt from the fixed tools 01:01, offline check vs combined4 PASS (`R4T/offline_check-R4T.log`); ONE passive 8-token
correctness run queued behind B5's lock (`R4T/finish_v2.sh` -> `R4T/run-R4T/`, READY only on 8/8 + verify rc 0).

### Correctness run of `bundles/R4T` (machine time 01:35:37–01:38:02, load 3.8–5.1, R3M protocol) — READY
ids **`[11, 314, 1101, 7926, 11, 475, 314, 1101]` 8/8**, `verify_browser_gpt2_runtime.py` rc 0 (tokenAgreement 8x True). Token capture times (harness poll, ±5 s):
R4T 22.6 / 10.9 / 17.0 / 11.3 / 17.3 / 16.8 / 17.4 / 17.3 s = **130.6 s total** vs R3M's combined4 correctness run (same harness, load 3.3–4.1, 22:10 yesterday)
22.0 / 17.1 / 17.2 / 18.0 / 24.2 / 17.8 / 24.7 / 17.6 = 158.6 s: **−28 s / 8 tokens ≈ −3.5 s/token** (single uncontended runs each; not a paired bench).

## 12-layer feedback (coordinator, machine 02:20): B5 pair 1 +2.3 s/token AGAINST R4T; combined7-c32 style intercept +3.6 s/token

### (a) Where does the extra style time sit? — from the existing traces/metrics, no new lock time
- 2-layer smoke traces, 53 style passes aligned 1:1 (`R4T.log.md` 02:0x): steady-state passes with +42..52 restyled chunk elements differ by **+0..6 ms**
  (≈0.1 ms per extra element, every site — fc/qkv/attn chunks, bridges, and the `.loop-reader-cK` chain passes (+41/+11 elements: +1..3 ms));
  the whole +444 ms sits in the **first activation of each stage in token 1** (passes 4/5/8/9: +138/+35/+37/+186 ms — one-time creation of the
  1,200 elements' animations/styles). Layout 3,111 vs 3,103 ms, 32 vs 32. So the 2-layer/capacity-2 build shows no steady-state style penalty.
- B5 pair 1 (`bench/runs/{combined4/paired5-ref-R4T-1,R4T/paired5-1}.json`, per-token `Performance.getMetrics` deltas): R4T style 83.0 vs 71.8 s
  (+11.2 s / 8 tok) **and layout 57.5 vs 44.5 s (+13.0 s / 8 tok)** with identical counts (663 recalcs / 607 layouts vs 667 / 608). Consumer chunking
  cannot change layout time (the carriers and the head are untouched; the smoke's layout is identical), so pair 1 is dominated by the contention
  B5 flagged (load 29.8, Messages at 106 % CPU); the pair's own ref was already 37 % slower (71.8 s style) than the ref of the R4S pair an hour earlier (52.4 s).
- The uncontended single runs point the other way: R4T correctness run 130.6 s vs combined4's 158.6 s (above).
- Candidate structural mechanisms a 12-layer/capacity-8 build could still pay per chunk element that the 2-layer smoke does not: (i) the matvec consumer
  rules are per layer inside `@container corestate style(--layer:L)` -> 12 rule variants x 1,200 elements evaluated per restyle vs 12 x 164 (2-layer: 2 x);
  (ii) each publishing element copies the inherited-variables delta (C1 §4.3; ~30k registered props at capacity 8 vs ~5k at capacity 2); (iii) the
  `--lp-*:inherit` fan-out (4,224 declarations ≈ 63 KB on the loop-reader chain, ≈2 ms per full restyle at 36 ns/B). Fixture `R4T/fixture/gen_mech.py`
  (18 variants: nested vs sibling publishers x 1 vs 12 layer rules x 0 vs 30k inherited props x 64 vs 512 animations per element) is queued under the
  lock (`results/mech.jsonl`) to price each.

### (b)/(c) R4T2 — per-site flag `R4T_CHUNK_SITES` (tools default all four; R4T2 = `matvec,bridge`)
Keeps the ≤64 knee on the per-layer hops (qkv 2,304 + attn 768 + fc 3,072 + cache bridge 768 + b11 bridge 768 = 7,680 of the ≈8.3k changed carriers
per layer) and leaves `.loop-reader` (768, 1 element) and `.embedding-consumer-N` (256 x 3) whole -> no `.loop-reader-cK` chain, no `--lp-*:inherit`
fan-out, 1,036 -> 924 extra elements... (built as `bundles/smoke-R4T2-2L` + `bundles/R4T2`, offline-checked vs `smoke-R4T-2L-ref` / `combined4`; smoke +
correctness queued behind the mechanism fixture; B5's pairs 2–3 of R4T awaited before a verdict). Manifest `r4tChunkSites`.

### Capacity-32 data point (coordinator, combined7-c32 run B = combined4-c32c + R4T, load 5–6.5, 32/32 ids)
Total 929.7 s vs c32c's 758.7 s. Fits per filled position k: style 4.00 + **0.555**·k (c32c 4.46 + 0.30·k), layout 3.21 + **0.384**·k (c32c 2.66 + 0.27·k),
total 12.3 + 1.015·k (c32c 13.9 + 0.60·k): the intercept is unchanged (run A's doubled intercept was contention) but the per-position slope nearly
doubles in style and rises 40 % in layout — the R4T cost at capacity 32 scales with filled positions, not with the fixed 1,036 extra chunk elements.

What grows with k and touches a chunked consumer: nothing in the chunked elements themselves (qkv 2,304 / attn 768 / fc 3,072 / bridges 768 /
loop 768 / embedding 768 animations are position-independent). What does grow: the attention branch (12·k score carriers on `.fvs-score-reader`,
768 V rows x k glyph leaves, the KV aliases) — it hangs under the **qkv consumer chain** (now 36 nested chunk elements instead of 5) and feeds the
**cache-bridge consumers** (now 12 instead of 2) whose 768 ctx carriers are the V-row widths. Two candidate mechanisms, neither reproduced by the
mechanism fixture below: (1) the extra nested ancestors between the position-scaled attention subtree and the core (36 + 12 block containers) are on
the layout/style propagation path of every V-row/score pass, whose element counts ∝ k; (2) the inherited-variables delta copy per publishing element
(Blink copies the props declared since the root on every publishing descendant) grows with k if per-position inherited declarations (`--fr-*` aliases,
`--valid-*`) sit above the chunk chains. **Open question for R4D**; safe capacity-32 setting until a c32 trace resolves it:
`R4T_CHUNK_SITES=matvec` (chunks only the qkv/attn/fc consumers; bridges, loop reader and embedding untouched) — or `matvec` minus qkv if the qkv
chain's position under the attention branch is the culprit (would need a `qkv` exclusion; one-line change in `r4t_consumer_chunk.chunk`).

### Mechanism fixture result (machine 03:02–03:05, load 4–6, 17 variants x 2 trials; `R4T/fixture/results/mech-summary.md`, harness `gen_mech.py` / `run_mech.mjs` / `analyze_mech.py`)
Publishers = M elements each declaring 64 inherited registered numbers, restyled by one `--in` change on the stage; knobs: nested chain vs siblings, the
publisher rule wrapped in 12 `@container corestate style(--layer:L)` variants (as the demo's per-layer consumer rules), 30k inherited registered props
declared on an ancestor (the demo's inherited map), and the animated shape (48 x 64 vs 6 x 512 view-timeline animations, 3,072 carriers changed per mutation).

| mechanism | cost per publishing (chunk) element per restyle |
|---|---:|
| a publisher applying its 64 declarations (siblings, 1 rule, small map) | 65 µs |
| nested chain instead of siblings (inherited-map delta copy) | **+21 µs** |
| 12 `@container style(--layer:L)` rule variants | **+33 µs** |
| 30k inherited props on the ancestor | **≈0 per element** (+24–38 ms per restyle PASS at the ancestor, independent of M: 20 vs 160 vs 1,200 publishers) |
| M = 1,200 nested, 12 rules, big map (the R4T element count) | 150 µs (incl. its own 64 declarations) |
| **animated: 48 x 64 vs 6 x 512 (fc split) with 12 rules + big map** | style **84.8 vs 85.3 ms** (equal); task **125.9 vs 197.2 ms** (−71 ms per mutation ≈ −23 µs per changed carrier = the knee) |

**Verdict rule applied**: no structural mechanism prices a chunk element at ≥ 0.5 ms — the worst case is ≈55 µs of extra style per extra element per
restyle (1,036 extra elements ≈ 57 ms if ALL were restyled in one pass; per token far less, since a pass restyles only the dirtied stage's chunks), against
≈23 µs saved per changed carrier (≈100k/token ≈ 2.3 s). The head-to-head animated case shows the split is style-neutral and saves the paint-lifecycle
time under 12-layer conditions. **R4T stands at capacity 8**; B5's lock-held pairs decide empirically. The capacity-32 per-position slope (previous
section) is NOT reproduced by any of these mechanisms -> open question for R4D; use `R4T_CHUNK_SITES=matvec` there until a c32 trace localises it.
R4T2 remains the fallback (fewer extra elements, no loop chain) and is being smoke-tested / correctness-run now.

### R4T2 2-layer smoke (machine 03:24:26–03:25:09, load ≈5.2) — ids **`[11, 3387]`**, done 2/2

| bundle | frames | UpdateLayoutTree | Layout | ULT ms | Layout ms | paint lifecycle ms | animate ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| ref (chunk 0) | 26 | 53 | 32 | 6232 | 3103 | 1018 | 715 |
| R4T (all sites) | 26 | 53 | 32 | 6676 | 3111 | 396 | 743 |
| R4T2 (matvec,bridge) | 27 | 53 | 32 | 6801 | 3248 | 539 | 855 |

Same pass/frame structure as the ref and R4T; the paint-lifecycle saving is retained (the loop reader and embedding consumers are per-token, not per-hop). Correctness run of `bundles/R4T2` queued (`R4T/finish_r4t2.sh`).
