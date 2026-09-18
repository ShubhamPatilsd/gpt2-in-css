# Why the CSS GPT-2 plateaued, where the time really goes, and the atomic fix

Orchestrator synthesis, 2026-09-18. Evidence: S0–S7 (Codex session digests), E1–E6 (451 experiment
catalog), C1/C2 (structural cost models), P1/P2 (Chromium traces), M1 (micro-benchmarks, see §8).
Every number below is tagged with its source report; "Codex" numbers are Codex's own claims, "measured"
numbers were re-measured today on Chrome 153, M2 Pro, AC power, caffeinated, no observers.

---

## 1. The honest numbers

| Artifact | Codex's number | Measured today | Source |
|---|---:|---:|---|
| TinyStories 3M, 16 stages (`streaming-packed8.html`) | 1.17 tok/s | **0 tokens** as shipped (missing gate rule); **1.30–1.35 tok/s** with the rule restored in a scratch copy | P1 §1, §4 |
| GPT-2 small, 12 layers, pinned bundle `demo-font-vector-twelve` | 78 s/token (397 s / 8 tok, with observer) | **40.7 s/token** (325 s / 8 tok, passive) | P2 §3 |
| GPT-2 small, ctx-32 bundle, 32 tokens | 3,177 s, 57→143 s/token | not re-run | S7 #2, C2 §0 |
| Sum of isolated stage costs, 12 layers | ~9.2 s | — | S6 #10 |
| Font matvec alone (768→3072, 9,216 glyphs) | 100–140 ms | — | S1 #7, S6 #2 |

Two corrections to the record. (a) Codex's 100 ms `DOM.getBoxModel` observer inflated every 12-layer
number by ~22 % (P2 #3; S7 #7 had estimated ~60 s of a 97 s token). (b) The shipped TinyStories page
cannot generate past token 1 because `tools/build_tinystories_dynamic.py:441` rewrites
`tinystories/streaming.css` without the `@container style(--winner-id)` gate after the nested build
(C1 #11, P1 #1). The README's throughput claim refers to an Aug-25 build.

## 2. Where a 12-layer token goes (P2, traced tokens 1–4, mean 44.0 s; shares hold untraced)

| Phase | Share | ≈ s | What it is |
|---|---:|---:|---|
| Style recalc | 55.6 % | 24.5 | 171 passes/token; see histogram below |
| Layout | 13.6 % | 6.0 | of which text shaping (the actual matvec) 5.0 % ≈ 2.2 s |
| Paint lifecycle | 12.4 % | 5.5 | 85 frames × 64 ms; actual `Paint` is 0.03 % |
| Animation servicing | 8.0 % | 3.5 | 7.4 M `serviceAnimations` calls; 12.3k live timeline animations |
| PrePaint / compositing inputs | 4.6 % | 2.0 | 85 frames × 24 ms |
| Fake-mousemove hit test | 3.0 % | 1.3 | 85 frames × 15 ms |
| Unattributed / idle | 3.0 % | 1.3 | |

Three structural facts fall out:

1. **The arithmetic is ~5 % of the token.** Everything Codex spent Sep 12–17 optimizing (font
   shards, glyph counts, GSUB, avar2, SVG) lives inside that 5 %. E1–E6 catalog ~450 experiments;
   the ones that measured well in isolation never transferred (S7 #3) because they were shaving the
   wrong term.
2. **~27 % is per-frame overhead that is independent of any computation** (paint lifecycle + animation
   + prepaint + hit-test ≈ 144 ms per frame × 85 frames). Frames exist because the design uses
   view/scroll-timeline readbacks and animation-driven handshakes, each of which needs a frame tick.
3. **The per-token slowdown (57→143 s in Codex's 32-token run) is garbage collection, not the model.**
   GC inside style/layout grows from 3.5 % to 16 % of the token; style-minus-GC is flat at 20.4 ± 0.6 s
   (P2 #6). Codex's `--heap-growing-percent=10` flag (added to halve RSS, S6 #12) is implicated.

### 2.1 Style-pass histogram (the key table; P2 Table 3)

| Elements per pass | Passes/token | Share of style | µs/element | Matches (C2 §2) |
|---|---:|---:|---:|---|
| ≥ 50 % of DOM (63.9k) | 2 | 11.8 % | 24 | gate/handshake writes on the stage chain |
| ~12.27k | 7.8 | 15.7 % | 43 | 3,072 proj-pack leaves × 4 elements (39 KB of declarations each) |
| 1k–9,999 (populations 3,089 / 3,545 / 3,856 / 2,935 / 3,544 ≈ 3,072 carriers) | 77 | 53.4 % | 40–90 | per-layer readback carriers |
| ~1,553 | 11.5 | 10.4 % | 153 | KV-bank republish of 1,536 inherited aliases |
| ~126 | 12.5 | 5.6 % | 933 | the dense font elements (256-axis `font-variation-settings`) |
| 0–1 elements | 63 | 4 % | fixed 15.6 ms/pass | per-pass fixed cost (≈2.7 s/token) |

µs per element spans 200×. Element count alone predicts nothing; **elements × declaration bytes applied**
does (C2 §3, P1 #8). Of the ~2.25 M element recomputations per 4 tokens only 442k are invalidation
roots; the rest is inherited / container-query propagation (P2 #10).

### 2.2 The same law on the TinyStories page (P1, C1)

One token = one recalc of 5 elements ≈ 709 ms, 97.5 % style, layout 0.03 %. Any recalc that reaches a
`.model` element costs the same 650–790 ms whether its winner changed, an unrelated property changed,
or the body colour changed (P1 #8). C1 counts ≈36.6 MB of declaration text re-evaluated per stage
(28k registered props + 10.4k `@function` calls + 1.18 M `var()`), i.e. ≈50 MB/s. This page is already
at the minimum pass count; its only lever is bytes per stage (head lazy dots 47 %, transformer 37 %,
of which 51 % is KV shift plumbing; the seed cluster is evaluated twice and the winner cluster three
times, C1 #4).

## 3. The atom

**Blink re-resolves an element's entire declared custom-property set whenever that element is style-dirtied,
at ≈40–50 MB of declaration text per second, and it dirties every descendant of a changed inherited
property unless a display lock stops it.** Cost per pass = Σ over dirtied elements of
(fixed per-element cost + bytes of that element's declarations ÷ ~45 MB/s). Cost per token = Σ passes.

Everything observed follows from this one rule:

- TinyStories: 5 elements × 36.6 MB → 0.7 s (P1/C1).
- GPT-2: 171 passes whose dirtied populations carry 4–39 KB of declarations each → 24 s (P2/C2).
- "Connected graph 4× the sum of isolated stages" (S5 #3, S6 #10, E5 #4): in isolation a stage's
  write dirties only its own leaves; connected, the same write sits on the shared stage chain and
  dirties every downstream population that is not locked.
- "Component wins never transfer" (S7 #3): a component benchmark removes bytes from one population;
  natively the pass still dirties the other populations and the frames still tick.
- "Anything that adds a dependent pass costs more than it saves" (S6 #13, E3 #5): each pass carries a
  15.6 ms floor plus a frame (144 ms) when animation-driven, so gating/progressive schemes lose unless
  they remove more bytes than that.

Codex diagnosed the symptom correctly on Sep 13 ("transport, not math", S2 #2) but attacked it by
inventing new carriers (fonts, anchors, timelines, counters, grids, SVG — E1–E6) instead of shrinking
what each carrier makes Blink re-evaluate. The carriers were never the atom; the declarations on them
and the frames between them were.

## 4. Why the process stalled (so it does not repeat)

- From 09-12 15:35Z to 09-13 19:39Z all 98 "user" turns were automated goal-continuation prompts
  (S1 #15, S3 note); Codex re-answered a stale "are we back at square one?" 17 times.
- Measurement hygiene: ≥9 headline speedups retracted as cache artifacts (S1 #14); observers added
  22 %; runs overlapped other Chromes, a 99 %-CPU MCP process, display sleep and battery (S3 #12,
  S7 #6); many A/Bs were 2-sample; no Chromium trace was taken until Sep 15, and none passive.
- Three inconsistent "current" builds and no commits since Aug 25 (S7 #10, S1 #1); 41,301 untracked
  files / 11.95 GB (S6 #1).
- ~80 % of Sep 13–14 effort went into the output head, which is ~3–10 % of a token (S4 #1, S6 #11).

## 5. Ranked atomic fixes (no JS, no model change, stock Chromium)

Predicted savings are against the measured 40.7 s/token; confidence is stated per item.
Items 1–3 need no new browser primitive and change only emitter output.

| # | Fix | Attacks | Predicted | Confidence / prior evidence |
|---|---|---|---:|---|
| 1 | **Drop `--heap-growing-percent=10`** in the harness (and re-measure without it); if RSS must be bounded, prefer fewer retained objects (fix 4) over GC pressure | GC 3.5→16 % + the position slope | −2 to −7 s/token, flat per-token time | High (P2 #6). Trade: RSS 3.6→5.5 GB |
| 2 | **Slim the dense leaf populations**: (a) V glyph rule 4,005 B → ~300 B via the v2 single `P000` axis + hoisted per-(H,S) weights (C2 §6 #1b); (b) proj-pack leaves 39 KB → one pre-materialised settings list (C2 §6 #4 fallback) | the 12.27k- and ~3k-element passes = 69 % of style ≈ 17 s | −8 to −12 s → **revised −1 to −4 s** | **Downgraded 2026-09-19 (B0):** the v2 rebuild already has the V glyph rule at 225 B on all 24,576 leaves and runs at the same 40.2 s/token as the 4,005 B pinned build. Blink's MatchedPropertiesCache shares applied results across elements with identical declaration sets, so the byte law holds only for per-element UNIQUE declarations; P2's 43–90 µs/element on these populations (≈1 KB of unique `var()` work each, not 39 KB) is the real cost. Lever = unique var()/calc() per leaf, not bytes |
| 3 | **Take frames out of the loop**: replace view/scroll-timeline readbacks with container-query-unit readbacks (interleaved style/layout, no frame tick) and make stage handshakes style-container stamps rather than animation events; keep compute subtrees `contain: paint` and pointer-inert | 85 frames × 144 ms ≈ 12 s; 110k ScrollTimeline invalidations; 3.5 s animation servicing | −6 to −10 s | **High for the mechanism (M1 MB3, §8.4: containers/anchors resolve a 12-deep chain in one pass and one frame; timelines cost one frame + one pass + one layout per boundary).** Residual risk is per-element container cost at 3,072 carriers; Codex's single-stage probe (S1 #9 "277→185 ms") hit deep nesting, not frames |
| 4 | **Stop retaining finished animations**: the 12 banks hold 86,400 s-delay transitions that are never removed (C2 §4); 12.3k live timeline animations are serviced every frame | animation servicing, part of the 15.6 ms/pass floor, RSS growth | −1 to −3 s, kills the memory slope | Medium. M1 MB4 quantifies per-animation cost |
| 5 | **Narrow the write points**: `inherits:false` on `--loop-ready/--loop-ack/--native-pass` with explicit republish to their ~8 readers; un-nest the KV banks to siblings and alias only the 48·p filled fields, not 1,536 (C2 §6 #2, #3) | the 2 whole-DOM passes (3 s) and the 1,553-element bank passes (2.7 s) | −3 to −5 s | Medium. `inherits:false` was neutral once on TinyStories (S1 #4) where there was nothing downstream to protect; here there is. M1 MB2 is the designed probe |
| 6 | **Cut the fixed per-pass cost**: 171 passes × 15.6 ms; collapse the 4-recalc SMIL handshake to one style-container flip per boundary (C2 §5) | 2.7 s floor + fewer frames | −1 to −2 s | Medium; depends on what the 15.6 ms is (M1 MB4/MB3) |

Combined, 1–6 predict **≈12–16 s/token (2.5–3.5×)** with the existing architecture (revised 2026-09-19: fix 2 contributes less than first predicted, so the weight is on fixes 3 and 5; see work/2026-09-19/bench/results.md for measured outcomes). The next floor is
Codex's isolated-stage sum (~9 s): reaching it means fewer carriers per layer (avar2 fused
`B·GELU(A·x)` halves MLP boundaries — 251 ms isolated but +17–19 % connected and 1.8× RSS, unexplained,
S7 #4; 4-values-per-container packing — 2× fewer carriers, decode cost ~9 %, S1 §6). Below ~5 s/token
needs a vector-level transport primitive Chromium does not expose (S2 #2, #15), or the excluded options
(JS `getComputedStyle`, a Chromium F16 build, a retrained model).

TinyStories-specific atomic fixes (same law, different page): restore the gate rule / stop the two
builders sharing `streaming.css` (build fix); evaluate the seed and winner clusters once (−20 % of head
bytes, C1 #4); replace the 7,168 `if()` KV shifts with a ring pointer (−25 % of transformer bytes,
C1 #5). Predicted 0.7 s → ~0.45 s per token.

## 6. Experiments, precisely defined

Common protocol (from P2's harness, `audit/2026-09-18/P2-scratch/trace_native.mjs`): headless
Chrome 153, AC + `caffeinate -dims`, no other Chrome, no geometry reads during generation, completion
by polling the page's own `#token-N-captured.done` marker every 5 s, 3 runs per arm, report the
untraced run as the number and a light trace for shares. Every arm rebuilds from one emitter flag so
the diff is one variable.

| ID | Hypothesis | Arms | Metric | Passes if | Prior related result |
|---|---|---|---|---|---|
| X0 | The pinned bundle is reproducible passively | pinned `demo-font-vector-twelve`, 3 runs | s/token, RSS | 40.7 ± 2 s | P2 (done, 5 runs) |
| X1 | GC flag causes the slope | with / without `--heap-growing-percent=10` | s/token for tokens 1–8, GC share | slope < 0.5 s/token without flag | P2 #6 |
| X2 | Leaf bytes set per-layer pass cost | V rule 4 KB vs ~300 B (`P000` + hoisted weights) | duration of the ~3k-element passes; token total | passes ≥ 3× faster; token −6 s | C2 §6 #1; prior −11 % component (S7 #3) |
| X3 | Proj-pack bytes set the 12.27k-element pass | 39 KB/leaf vs materialised settings list | duration of 12,274-element passes | 530 ms → < 120 ms | C2 §6 #4; `global-projection` neutral natively |
| X4 | Frames are removable | timeline readback vs cq-unit readback, 2-layer variant first | frames/token, ScrollTimeline invalidations, animation ms, total | frames ≤ 3 per layer; total −25 % | S1 #9 single-stage comparison; M1 MB3 |
| X5 | Handshake writes dirty the whole DOM | `inherits:true` (current) vs `inherits:false` + republish | count of ≥50 %-DOM passes per token | 2 → 0 | C2 §6 #2; M1 MB2 |
| X6 | Retained transitions cost per frame | current 24 h-delay transitions vs paused / vs removed after latch (page variants) | animation servicing ms, 15.6 ms floor | −50 % animation ms | C2 §4; M1 MB4 |
| X7 | Fixes compose | all of X1–X6 | s/token | ≤ 16 s | — |
| X8 | TinyStories head dedupe | seed/winner single evaluation | ms/token | 709 → ≤ 570 | C1 #4 |

Order: X0 (done) → X1 (one flag) → X5 (one registration change, settles scenario A/B from C2 §3.2)
→ X2/X3 (emitter changes, largest predicted gain) → X4 (design change, largest risk) → X6 → X7.

## 7. Closed lines — do not re-open without new browser primitives

Each was measured, most several times (report and item):

- Exact/approximate vocabulary search for the head: HNSW needs ~24k row scores + 1,028 sequential hops
  at 99.2 % recall; IVF/LSH/ball-tree/routers all fail under a ~2k-row budget (S2 #11, S4 #3, E3 §B).
- Any batched/parallel head tail: exact but slower every time (S3 #7, E2 #6, E3 §C).
- SVG filters as the compute engine: 12 blocks in 251 ms but 8-bit at every boundary → 28/48 tokens,
  diverges after 2; 16-bit PNG, HDR/AVIF, dither, dual-plane, alpha all fail (E5 #1–3, E6 #4, S1 #12).
- Font-metric (`ch/ic/ex/cap/lh`) transport at width 768: 924 faces, 2.83 GB RSS, no faster (E1 #5, S2 #6).
- Anchor-based ALUs / counters / additive animations / colour-mix / grid gathers at 768²: all 5–35×
  slower than fonts or blocked (E1 #3–4, E2 #3, E4 #3–6).
- GSUB circuits and compact digit fonts: 5–250× slower; 16,384 subtable-reference cap (S7 #8, E4 #1).
- Chrome hard limits to design around, not against: 256 axes/font, 512 DOM nesting, 32,768 px glyph
  advance, 33,554,432 px layout, 99-term `calc()`/`max()`, 24 exact bits in typed `<number>`,
  128 MB decompressed font, 1/64 px advance snapping (S2 #12, S3 #4–5, S4 #5).

## 8. Micro-benchmark results (M1) — the atom measured in isolation

81 synthetic no-JS pages (`audit/2026-09-18/M1-microbench/`), one CDP mutation each, Chrome 153
headless, median of 3, spread ~1 %, exactly one `UpdateLayoutTree` and zero `Layout` per mutation, every
trial verified by reading the changed computed value. MB1/MB2/MB5 ran on AC + caffeinate; MB3/MB4
(§8.4) ran after the machine switched to battery and are flagged.

### 8.1 Blink's style-cost law (MB2, MB1)

Restyle cost when one inherited property changes on a root with N descendants that carry b bytes of
declarations **none of which reference the changed property**:

| Descendant declarations | Fit (R² ≥ 0.999) | Example |
|---|---|---|
| `var()`-bearing calc | −2.35 ms + **4.45 µs/element + 36.5 ns/byte** | 10k × 2 KB → 771 ms |
| literal values only | −0.33 ms + **2.83 µs/element + 18.7 ns/byte** | 10k × 2 KB → 402 ms |

Same law on a single element with K declarations (MB1a): cost is independent of K per declaration,
linear in terms (≈0.42 µs per `var()·w` product), 46–51 MB/s for ≥16-term calcs — C1's 43 MB/s
reproduced from first principles. MB1b: if only 1 of K declarations depends on the changed input, the
other K−1 still cost 60–70 % of their dependent equivalents. MB1c: writing to one of 50 siblings costs
exactly 1/50 of writing to their parent (0.021× vs 1/n = 0.020).

**Reading:** Blink re-applies and re-evaluates every declaration of every dirtied element; dependency is
irrelevant, declared bytes and element count are everything; cost is additive over dirtied elements.

### 8.2 What stops the cascade (MB2 b–f)

| Mechanism | Cost vs plain inherited write |
|---|---:|
| property registered `inherits: false` | **0.001×** (one element restyled) |
| descendants under a `content-visibility: hidden` wrapper | **≤ 0.002×** (4 elements restyled) |
| `contain: style` on descendants | 1.00× (no effect) |
| declarative shadow root | 0.98–1.03× (no effect) |
| depth-100 chain instead of flat | 1.00× (depth is not a cost) |

Only two tools exist: do not inherit what is not read, and display-lock what is not active.
Containment, encapsulation and flattening buy nothing.

### 8.3 What the 45 MB/s is made of (MB5; 10k declarations × 320 B on the mutated element)

| Spelling | µs per declaration | vs 16-term `var()` calc |
|---|---:|---:|
| short literal | 0.72 | 0.09× (cascade floor) |
| 16-term calc, literals only (parsed once) | 4.09 | 0.50× |
| 16 `var()` substitutions, unregistered, no eval | 3.71 | 0.45× |
| 16-term calc with 1 `var()` | 6.52 | 0.80× |
| 16-term calc with 16 `var()` | 8.17 | 1.00× (25.5 ns/B) |
| one `@function` invoked per declaration, 16 args | 17.99 | **2.20×** |

(The 32-`var()` variant was invalid: Blink did not apply its 160k-declaration weight rule; excluded.)

Decomposition: ≈0.7 µs cascade + ≈3.4 µs typed evaluation of a 16-term calc + ≈0.25 µs per `var()`;
a `@function` call adds ≈10 µs over the inline calc. Consequences: shortening numerals (Codex's 1 %
result, S1 #4) cannot help because bytes are not the driver, terms and `var()` count are; the
TinyStories head's ~10.4k `@function` invocations per token pay ≈100–125 ms in call overhead alone
(C1 #1, fix in §5); typed calc arithmetic runs at ≈5 M products/s, so a full 768→3072→768 MLP as
inline calc would cost ≈0.5 s if nothing else were restyled — the same order as the font path's
per-MLP cost once its carriers are counted, which is why the font pivot bought less than expected.

### 8.4 Passes and frames per boundary (MB3; battery run, counts are power-independent)

Chain of S = 1/4/12 stages, each a 64-term calc, stage s+1 reading stage s's result through a
transport mechanism; one root mutation; marginal cost per boundary = (S12 − S4)/8.

| Transport | extra `UpdateLayoutTree` events / boundary | extra `Layout` / boundary | extra wall / boundary | Invalidation reason |
|---|---:|---:|---:|---|
| pure style (`var()` chain, control) | 0 | 0 | 0.05 ms | Related style rule |
| **container-query units** (`100cqi`) | **0** | 0 | **≈ 0 ms** | Related style rule (13 interleaved recalcs inside ONE pass) |
| **`anchor-size()`** | **0** | 0 | 0.1 ms | Related style rule |
| view-timeline readback | **+1.0** | **+1.0** | **+6.6 ms (one frame)** | ScrollTimeline ×12 |

A 12-deep geometry→number chain through container units or anchors resolves inside one lifecycle
update and one frame. Through view/scroll timelines every boundary needs its own frame, its own
style pass and its own layout, and each frame re-restyles the whole downstream chain (element counts
52, 45, … 1 for S = 12: quadratic in depth) — which is exactly the 85 frames, ~110k ScrollTimeline invalidations
and 171 passes per token that P2 measured on the demo. Fix 3 in §5 is therefore upgraded to high
confidence for the mechanism (the remaining risk is only the per-element cost of containers at
3,072 carriers, which Codex's single-stage probe hit at 512-deep nesting, S1 #9). Container units are
also numerically better than timelines (48 exact bits per container vs ~14, E1 #2, E4 #4).

### 8.5 Retained animations (MB4; battery run)

| A retained animations on custom properties | unrelated sibling mutation: style ms / busy ms | animated elements restyled: µs per element |
|---|---|---:|
| 0 | 0.1 / 1.8 | — |
| 10,000 fill-forwards | 0.8 / 5.2 | 5.6 |
| 10,000 paused | 0.9 / 10.3 (5 ms animation servicing) | 5.2 |
| 10,000 static values (no animation) | 0.3 / 3.9 | 2.2 |
| 100,000 fill-forwards | 7.4 / 35.6 | 6.0 |
| 100,000 paused | 7.7 / 102 (69 ms animation servicing) | 5.2 |
| 100,000 static | 1.7 / 19.7 | 2.3 |

An element that carries a retained animation costs ≈2.6× as much to restyle as the same element with
a static value; paused animations add ~0.7 µs per animation of servicing to every lifecycle. For the
demo's ≈12.3k live timeline animations that is ≈1 ms of style plus ≈4 ms of busy time per pass ×
171 passes ≈ 0.9 s/token, plus the 2.6× surcharge on every restyle of the ≈24k animated glyph
leaves. Fix 4 is real but second-order in time (≈1–3 s/token) — unless the timelines go away with fix 3,
in which case most of it disappears for free. It is first-order in memory: 100k retained animations
cost 1.9 GB RSS versus 0.65 GB for the same values as static declarations (≈12.5 KB each), so the
demo's 129k retained transitions by position 8 account for roughly 1.6 GB of its 3.9–5.5 GB.
The cold/inline cross-check reproduced the AC numbers within −15…+21 % with identical rank order,
so none of the above is a warm-cache artifact.

### 8.6 What decides the order of work

§8.1–8.2: bytes and element count on dirtied populations are the cost; only `inherits:false` and
display locks stop it → fixes 2 and 5 first. §8.4: timelines, not CSS, impose a frame per boundary
→ fix 3 removes ~27 % of the token and most of fix 4 with it. §8.3: `@function` and `var()` count,
not numerals, set the per-byte constant → the TinyStories head fix and "bake weights as literals".

### 8.5 How the law re-derives the measured pages

- TinyStories: one `.model` element, ≈28k registered declarations + 10.4k function calls ≈ 36.6 MB
  → 0.70 s per stage (P1 measured 0.65–0.79 s).
- GPT-2 demo: P2's per-pass µs/element (24–933) is the law's slope for populations whose declared
  bytes range from ~100 B (propagation-only carriers) to 4–39 KB (V glyph and proj-pack leaves, C2).
  The two whole-DOM passes (64k elements × 24 µs ≈ 1.5 s each) are the 4.45 µs/element term plus the
  light declarations of the bulk; the 12,274-element passes at 530 ms are 3,072 × 39 KB ≈ 120 MB of
  declarations at ~40 ns/B minus MPC sharing.

## 9. Repo defects found along the way

- `tinystories/streaming.css` overwritten without the winner gate (build order / shared file).
- `nested-runtime.css`, page byte counts and MAC counts drift from the docs (C1 #12).
- Two "validated" bundles; current source cannot reproduce either without the v1 fonts (C2 §0).
- `calc()` emitted without spaces around `+` silently invalidated declarations at least five times
  across sessions (S4 #14, S5 #11) — worth a build-time lint.
