# C2 — Structural cost model of the validated 12-layer no-JS GPT-2 bundle(s)

Read-only audit (agent C2). Log: `audit/2026-09-18/C2-demo-cost-model.log.md`. Nothing was built or run in Chromium; all numbers are (a) read from emitter source, (b) counted in the emitted HTML/CSS with `grep`/`dd`/python scans, or (c) quoted from saved measurement JSON in the bundle directories. Statements about Blink internals are tagged **[inference]**; everything else is read from code or files.

---

## 0. Bundle identity — there are two "validated" bundles, not one

The 78 s/token figure and the 3,177 s/32-token figure come from **different bundles** built by the same compiler (`tools/browser_gpt2_runtime.py`, entry `compile_runtime` :178, writes `runtime.css` :478 and `index.html` :479-489) with different flags:

| Run | Directory | HTML / CSS bytes | Core backend | KV codec | Capacity | Pinned in `validated-bundles.json`? | Saved timing |
|---|---|---:|---|---|---:|---|---|
| "78 s/token" (8 tokens, 662.5 s) | `experiments/browser-gpt2/demo/` | 15,965,126 / 41,445,120 | **12 physical blocks** (`compile_core`, `tools/browser_gpt2_core.py:205-412`), no reuse | scalar (`--kv-k{slot}-{i}` 1,536 `<number>` props per slot per block, "native delayed transitions") | 8 | **No** | `demo/timing-summary.json`: `medianFollowupSeconds` 77.956, followups 62.3–91.3 s; style 37.5 %, layout 7.7 %, other 54.8 % |
| "3,177 s / 32 tokens" | `experiments/browser-gpt2/demo-font-vector-context32/` | 7,520,168 / 87,991,151 | **one reused graph** (`compile_reused_runtime_core`, `tools/browser_gpt2_reused_adapter.py:14-175` → `compile_reused`, `tools/browser_gpt2_reused_core.py:90-370`) | font-vector **v1** operators (whole-head `font-variation-settings` lists; 48 fields per layer per slot) | 32 | **Yes** (`experiments/optimization-followups-2026-09-17/validated-bundles.json`, capacity-32 entry, `fontVectorOperatorVersion: v1`, `currentSourceRebuildEquivalent: false`) | `scaling-summary.json`: total 3,177.13 s, warm median 97.69 s, 2nd 57.2 s → 30th 143.3 s; RecalcStyle 68.0 %, Layout 15.1 %, Other 16.9 %; RSS 5,215.7 MiB |
| (8-token sibling) | `demo-font-vector-twelve/` | 6,750,560 / 45,783,674 | reused | font-vector v1 | 8 | Yes (capacity-8 entry) | 402.67 s total; warm median 51.3 s |

Evidence that `demo/` is the scalar non-reused build: its `manifest.json` has no `coreBackend`/`renderingGraphs` keys and says `kvStorage: "native delayed transitions"`; the caption "Measured warm speed: about 78 seconds/token on M2 Pro" is emitted **only** for `(blocks, capacity) == (12, 8) and cache_codec == "scalar" and not reuse_core …` (`browser_gpt2_runtime.py:433-442`). `VALIDATED_RECIPE.md` (optimization-followups) documents that the CLI defaults build this older scalar core and that reproducing the v1 reused bundles requires `--reuse-core --cache-codec font-vector --scoped-state --isolate-head --detached-output` **and** the v1 fonts, which current source no longer emits (`browser_gpt2_font_vector_cache.py:22` now points at `font-vector-operators-v2`; the pinned bundle references `experiments/browser-gpt2/font-vector-operators/dot.woff2`/`value.woff2`, and `grep -c font-vector-operators-v2 runtime.css` = 0).

Two concrete v1-vs-current-source differences visible in the ctx32 bundle (matter for the byte model below):
1. Each retained-V glyph rule `.fvs-v-H-S{…}` is **4,005 B** with a 128-axis `font-variation-settings` (`var(--fr-v-S-H)` = 64 K-axes, plus 64 explicit `"Q000".."Q063" calc(var(--fe-H-S) * var(--fr-vs-S-H) / var(--fb-H))`); current source collapses the 64 probability axes to one `"P000"` (`font_vector_cache.py:45-77, 333`).
2. Each bank write rule inlines the 1,488-name retained `transition-property` list (125,083 B per rule; 384 rules = 48.0 MB of the 88 MB sheet); current source emits `transition-property:var(--fvs-retained-S)` (`font_vector_cache.py:209-224`).

**The rest of this report models the pinned ctx32 bundle (§1–§5) and gives the scalar `demo/` numbers alongside where they differ (§3.3).**

### 0.1 Measured per-token renderer counters (saved in the bundles, previously unreported)

`pipeline-results.json → samples[*].metrics` holds `Performance.getMetrics` snapshots at each captured token. Deltas between consecutive tokens:

| Bundle | Token interval | RecalcStyleCount / token | LayoutCount / token | RecalcStyleDuration / token | LayoutDuration / token | TaskOtherDuration / token |
|---|---|---:|---:|---:|---:|---:|
| ctx32 | epoch 3 (57.2 s) | 216 | 111 | 38.1 s | 5.7 s | 13.9 s |
| ctx32 | epoch 12 (89.0 s) | 239 | 110 | 63.4 s | 10.0 s | 15.5 s |
| ctx32 | epoch 31 (143.3 s) | 262 | 111 | 101.9 s | 19.6 s | 19.8 s |
| demo (scalar) | epoch 2 (62.3 s) | 129 | 64 | 22.5 s | 5.0 s | 35.0 s |
| demo (scalar) | epoch 7 (91.3 s) | 130 | 64 | 35.0 s | 6.1 s | 50.4 s |

So the real 12-layer bundles do **~216–266 style recalcs and ~106–114 layouts per token** (ctx32) and **130 / 64** (scalar demo). The "119 style recalcs and 71 layouts" number that Codex quoted is the renderer delta of the **24-pass loop-handshake fixture** (`experiments/optimization-followups-2026-09-17/loop/summary.json`: `steps: 24`, `rendererDelta.RecalcStyleCount: 119`, `LayoutCount: 71`; fixture `loop/fixtures/baseline-p24/index.html` has 1,700 elements — 1,538 `loop-metric` carriers and a trivial `.compute{--loop-out-i:calc(-.5*var(--loop-in-i)+…)}` — see also `experiments/style-simplification-review/RESULTS.md:27-36`). It measures only the layer-to-layer handshake: ≈5 recalcs + 3 layouts and ≈0.40 s per pass (9.22 s / 23 continuation passes). Multiplied by 12 layers that is ≈60 recalcs, 36 layouts and ≈4.8 s of the per-token budget; the rest is the stage cascade (§5).

---

## 1. The emitter, construct by construct

| Construct | Emitter | What is emitted (verified in bundle) |
|---|---|---|
| Token loop, `--epoch`, feedback | `browser_gpt2_runtime.py:41-152 feedback()` | `body{--epoch:1}` (registered `<number>` inherits:true); `body:has(#token-N-advanced.done){--epoch:N+1}` (:75); 32 nested `div.token-slot-N` each latching `--saved-token-N` with a 1 ms / 86,400 s-delay transition (:65-67); 32 `feedback-metric` widths → view-timelines → `.feedback-reader` 32 animations (:87-93) → `.feedback-select{--token:if(style(--epoch:N):var(--feedback-(N-1))…)}` (:95-102); SMIL `<set attributeName="class" to="done" begin="…animationend+0.001s">` receipts (:103-115) |
| Embedding | `browser_gpt2_embedding.py:36-90` | one `EmbeddingLookup` font (2 axes GRUP/LOCL), 768 `embedding-metric` carriers + 1 marker, three nested `embedding-consumer-*` each with 256 timeline animations and 256 `--embed-*:calc(…)` decls; `embedding-receipt` container publishes `--embed-ready` |
| Position embedding | `runtime.py:346-359` | one `.position-embedding` rule, 768 × 33-case `if(style(--epoch:N):…)` = 891,068 B, 25,346 decls; applied to one element |
| Layer loop controller | `probe_native_reused_loop.py:15-116 loop_parts()` + adapter rewrites `reused_adapter.py:37-131` | `.core-controller{container-name:loopcontrol corestate}` holds `--pass/--layer/--loop-phase/--loop-captured-pass/--loop-held` (re-registered **inherits:false**, adapter :89-104); `--native-pass` (inherits:true) republished onto `.core-block` by 384 rules `@container loopcontrol style(--pass:N){.core-block{--native-pass:N}}` (:111-113); two `loop-bank-b` with 769 `loop-metric` widths each, `.loop-reader` 1,538 timeline animations, `.loop-input{--loop-in-*}` (768 registered inherits:true) + `--loop-ready`/`--loop-ack` (inherits:true); 384 steps × 4 SMIL `<g>` signals; `.core-controller:where(:has(#loop-captured-N.done)){--loop-captured-pass:N}` / `…advanced…{--pass:N+1}` (adapter :118-130) |
| Layer-specialised weights | `reused_core.py:74-88 specialize()` | every per-layer rule wrapped in `@container corestate style(--layer:L){…}` — 12 blocks of 6.07 MB each (72.8 MB total = 83 % of the sheet); inside each block: `.shared-ln1/ln2` (138.6 KB each, 770 decls of 768-term sums, `build_gpt2_block_css.py:230-258`), `.shared-qkv` (5 rules, 128 KB, one 768-axis `font-variation-settings` list built by `pack_font_settings` :365-378), `.shared-qkv-c0..c4` (5 × 68–75 KB: 461–512 `animation-name`s + `animation-timeline`s + `--qkv-i:calc((V/var(--qkvp-i) − V)·… )` decls, `build_hybrid_twelve_block.py:209-232`), `.shared-attn` + `-c0,c1`, `.shared-fc` + `-c0..c5` (6 × 80 KB), `.shared-proj` + **`.shared-proj-pack0..3` (4 × 39,230 B, each a 768-axis settings list)** + `-c0,c1`, and the layer's 32 KV write rules + 1 alias rule (below) |
| Dense matvec stage | `build_hybrid_twelve_block.py:101-240 matvec()` | `<div class="shared-KIND"><div class="scroller"><div class="track">N×<i class="metric" style="view-timeline:--t inline">…</i> + marker</div></div><div class="shared-KIND-c0">…<div class="shared-KIND-receipt"><div class="shared-KIND-gate">{child}</div></div></div></div>`; gate = `content-visibility:hidden;contain-intrinsic-size:0px 0px` opened by `@container shared-KIND-receipt style(--gate-KIND:1)` (:196-207, display→content-visibility swap at `reused_core.py:328-331`); `--gate-KIND:calc(1 − min(1,abs(round(nearest,(V/var(--stamp-KIND) − V − V/4)/1024,1) − var(--epoch))))`, `--stamp-KIND` animated by the marker's view-timeline. For 3,072-input proj, `packs = ceil(12 shards / 3) = 4`, so **every output row `<i class=metric>` contains 4 `<i class="shared-proj-packP">` children each matching a 39 KB settings rule** (:155-158, 173-187) |
| KV cache + attention | `browser_gpt2_font_vector_cache.py:138-424 attention()` | `div.fvs-query` (container `fvscache`, `--fvs-write-slot`, 12 × (`--fqs-H`, `--fvs-query-H` 64-axis string, `--fvs-live-k/v-H` 64-axis strings, `--fvs-live-ks/vs-H`)) → **12 nested `div.fvs-bank.fvs-bank-L`** (:401-407) each registering 1,536 `--fc-{k,v,ks,vs}-{slot}-{head}` (`*` lists for k/v, `<number>` for ks/vs, all **inherits:false**) and 1,536 `--fr-*` aliases (**inherits:true**) (:160-165); base `.fvs-bank{transition-property:<1,536 names>;transition-duration:1ms;transition-delay:86400s;steps(1,end);allow-discrete}` (19,129 B); per (layer, slot) write rule (:223-224) and per-layer alias rule (:225-229). Below the banks: `scroller.fvs-score-source` with **384 `<i class="metric fvs-score-H-S">`** (2,976 B rule each: `font:512px FvsDot; font-variation-settings:var(--fr-k-S-H),<64 Q axes>`; width `calc-size(max-content, …)` :251-253) → `div.fvs-score-reader` (384 timeline animations, 384 `--fs`, softmax `--fm/--fe/--fd/--fb`, `--fv-S` masks :283-319) → `fvs-score-receipt` → **`fvs-score-gate`** (content-visibility, :281) → `div.fvs-softmax` → `scroller.cache-bridge-source` with 768 `<span class="metric fvs-value-row">` rows each containing **32 `<i class="fvs-v-H-S">`** glyphs (:367-371) = 24,576 leaf elements |
| Context transport | `hybrid.bridge(100,512)` renamed `cache-bridge` (`reused_core.py:196-210`) | 768 row widths → view-timelines → `cache-bridge-c0,c1` (768 animations, `--ctx-i` decls) → `cache-bridge-receipt`/`-gate` |
| Layer→token bridge, head | adapter :63-85, runtime :313-345 | `reused-final-export` (`display:none` except `@container corestate style(--layer:11)`) with `b11-bridge-source` (769 carriers) → sibling chain `b11-bridge-c0>c1>receipt>gate>#core-result>final-normalization>head-input-bank>head-isolation>full-head`; `.head-input-bank` latches 768 `--h` by delayed transition (:322-327); `.full-head{content-visibility:hidden}` opened by `@container b11-bridge style(--bridge-ready:1)` (:391); head is the two-pass q16 scorer (`experiments/browser-gpt2/head-two-pass/head-body.html`, 4.8 MB; `split_head_receipt` for capacity>8, `browser_gpt2_head_receipts.py:11-46`): 50,257 `<i class="head-row" data-token style="--base:…;--tie:…">`, 256 `head-fine-row` (each its own `:nth-child(N)` rule, 15.2 KB), 197 `<section>` groups |
| Scratch reset / isolation | `browser_gpt2_core.py:100-103`, runtime :268-283 | `.core-reset{16,158 × --p:initial}` (309 KB, one element at depth 16); `.head-isolation{29,081 × --p:initial}` (573 KB, one element) |

---

## 2. DOM / state topology (ctx32 bundle)

Parsed with `html.parser`: **92,356 elements** (93,191 tags incl. void/`<set>`), **max depth 56**. Tag histogram: 89,549 `<i>`, 1,670 `<g>`, 835 `<set>`, 768 `<span>`, 197 `<section>`, 143 `<div>`.

```
html > body
├ div.controls (13) · #runtime-epoch-observer · svg.native-signals(#run-start,#run-latched)
├ div.font-status (fonts-detected/fonts-loaded SMIL)            + 261 i.font-witness + 261 i.font-proof + 20 font-all reductions (siblings of body)
├ div.feedback-reader   d2  91,579 desc  (--frozen-prompt; 32 view-timeline animations → --feedback-N)
│ └ div.feedback-select d3  (--token = if(style(--epoch:N):var(--feedback-N-1)))
│   └ div.embedding-source d4 (font EmbeddingLookup; timeline-scope 769)
│     ├ embedding-scroller>track: 768 i.embedding-metric + marker
│     └ embedding-consumer-0>-256>-512 d5-7 (3×256 anims, --embed-*)
│       └ embedding-receipt d8 > #embedding-result d9 (--embed-ready)
│         └ div.position-embedding d10  (891 KB rule: --x-*? no: --x-i = embed+pos, 768×33-case if())  90,798 desc
│           ├ div.core-controller d11  [container loopcontrol corestate; --pass,--layer,--loop-phase,… inherits:false]  39,645 desc
│           │ └ div.core-block#block-0 d12 (--native-pass inherits:true, 384 pass rules)
│           │   └ div.loop-reader d13 (1,538 timeline anims → --lp-b-i inherits:false)
│           │     └ div.loop-input d14 [container loopreceipt; --loop-in-* , --loop-ready, --loop-ack  inherits:true]
│           │       ├ svg.loop-signals: 384×(g ready, g ack, g captured>set, g advanced>set) = 1,536 g + 768 set
│           │       └ div.loop-compute d15 [content-visibility gate on --loop-ready]
│           │         └ div.core-reset.core-valid.reused-input d16 (16,158 :initial; --valid-0..31; --x-i:var(--loop-in-i))
│           │           └ div.shared-ln1 d17 (--mean1,--var1,--n1-*)
│           │             └ div.shared-qkv d18 (768-axis font-variation-settings; --range-qkv)
│           │               ├ scroller>track d19-20: 2,304 i.metric[view-timeline] + marker
│           │               └ shared-qkv-c0>c1>c2>c3>c4 d19-23 (5×~461 anims; --qkv-*)
│           │                 └ shared-qkv-receipt d24 > shared-qkv-gate d25 [CV gate]           35,787 desc
│           │                   ├ div.fvs-query d26 [container fvscache]                            25,750 desc  ← attention side-branch
│           │                   │ └ fvs-bank-0 d27 > fvs-bank-1 d28 > … > fvs-bank-11 d38   (12 nested banks, 1,536 --fc each)
│           │                   │   ├ scroller.fvs-score-source>track d39-40: 384 i.metric.fvs-score-H-S + marker
│           │                   │   └ div.fvs-score-reader d39 (384 anims; softmax) > fvs-score-receipt d40 > fvs-score-gate d41 [CV gate]
│           │                   │     └ div.fvs-softmax d42 > scroller.cache-bridge-source d43 > track d44
│           │                   │         └ 768 × span.metric.fvs-value-row d45 [inline width calc-size + view-timeline]
│           │                   │             └ 32 × i.fvs-v-H-S d46  (= 24,576 leaves; 4,005 B rule each)
│           │                   └ div.cache-bridge-c0 d26 > c1 d27 (768 anims → --ctx-*)             10,035 desc  ← downstream chain
│           │                     └ cache-bridge-receipt d28 > cache-bridge-gate d29 [CV]
│           │                       └ shared-attn d30 (768 axes) [768 metrics] > attn-c0>c1 d31-32 > receipt d33 > gate d34 [CV]
│           │                         └ shared-ln2 d35 > shared-fc d36 (768 axes) [3,072 metrics] > fc-c0..c5 d37-42 > receipt d43 > gate d44 [CV]
│           │                           └ shared-proj d45 [768 metrics × 4 i.shared-proj-packP children = 3,072 pack elements] > proj-c0>c1 d46-47 > receipt d48 > gate d49 [CV]
│           │                             └ div.reused-output#reused-result d50 (--loop-out-* inherits:false)
│           │                               ├ 2 i.readback probes · div.reused-final-export d51 (display:none unless layer 11; 769 b11-bridge carriers)
│           │                               └ loop-bank-1 d51 > [loop-scroll>loop-track: 769 loop-metric] + loop-bank-0 d52 > […] > #loop-result
│           └ div.b11-bridge-c0 d11 > c1 > b11-bridge-receipt d13 > b11-bridge-gate d14 [CV]            51,152 desc  ← head side-branch
│               └ #core-result d15 > final-normalization d16 > head-input-bank d17 (768 --h latches) > head-isolation d18 > full-head d19 [CV gate on --bridge-ready]
│                   └ head-coarse-reader > head-score-state > head-epoch-reader > head-group-state … 197 section × 256 i.head-row (50,257) + 256 head-fine-row … > i.detached-head-source
└ div.detached-head-reader d2 > detached-head-state d3 > token-slot-32 d4 > … > token-slot-1 d35 > token-state d36 (svg 32×4 g; feedback-scroller: 32 feedback-metric; #tokens)   203 desc
```

**Answers to the topology questions**

| Question | Answer (ctx32) |
|---|---|
| Where the per-layer KV values live | 12 **nested** `div.fvs-bank-L` (depth 27–38), all ancestors of every attention glyph. Per bank 1,536 registered props `--fc-{k,v}-S-H` (`syntax:"*"`, 64-axis strings ≈1.5 KB each) and `--fc-{ks,vs}-S-H` (`<number>`), **`inherits:false`**, retained by the base `transition-property` list of 1,536 names (delay 86,400 s). Only the selected layer's bank additionally matches (i) the write rule for the current slot (48 `--fc-*:var(--fvs-live-*)` + a 1,488-name list, 125 KB) and (ii) the alias rule (1,536 `--fr-*:var(--fc-*)`, **`inherits:true`**, 45.6 KB) which is what the glyphs read. Registered total 29,848 props: 16,818 inherits:true / 13,074 false. |
| Where the current hidden state lives | `--x-000..767` (`<number>`, inherits:true) declared on `.reused-input` (depth 16) from `--loop-in-*` (loop-input, depth 14); successive vectors `--n1`, `--qkv` (2,304), `--ctx`, `--r`, `--n2`, `--hidden` (3,072), `--out` are inherited registered numbers declared on the stage/consumer elements at depths 17–47, i.e. **always on an ancestor of everything downstream**. The layer output returns via `.reused-output{--loop-out-*}` (inherits:false) → loop-bank widths → view-timelines → `.loop-reader` → `.loop-input`. |
| Where `font-variation-settings` inputs are set | qkv/attn/fc: one 768-axis list on the stage wrapper (`.shared-qkv{…}` 128 KB incl. 5 rules; `.shared-fc` 138 KB; `.shared-attn` 104 KB) inherited as a computed font by 2,304/3,072/768 glyph runs. proj: **3,072 leaf `i.shared-proj-packP`**, each matching a 39,230 B 768-axis list. Scores: 384 leaf `i.fvs-score-H-S` (2,976 B, 128 axes). Values: **24,576 leaf `i.fvs-v-H-S`** (4,005 B, 128 axes). Embedding: 2 axes on `.embedding-source`. Head: 768 axes on `.full-head` (one rule). |
| 3,072 / 768 readback carriers | `i.metric[style="view-timeline:… inline"]` inside `scroller>track`: 2,304 (qkv) + 385 (scores) + 768 (V rows, spans) + 768 (attn) + 3,072 (fc) + 768 (proj) + 769 (b11 bridge) + 6 markers = 8,839 `.metric`; plus 1,538 `loop-metric`, 769 `embedding-metric`, 32 `feedback-metric`. Consumers hold one `animation-name`/`animation-timeline` entry per carrier (87,202 animation names in the sheet; live set ≈12k on ~30 elements). |
| How a stage/layer is gated | Stage: `content-visibility:hidden` on `*-gate`, opened by a **style container query** on the sibling receipt (`@container shared-KIND-receipt style(--gate-KIND:1)`), where `--gate-KIND` compares a view-timeline-driven stamp with `--epoch` (= `--native-pass` inside the core, `adapter.py:41`). Layer: no element toggles; the **layer index is style-container state** (`--layer` on `.core-controller`), and all layer-specific rules sit in `@container corestate style(--layer:L)` blocks. Handshake: animation (`loop-pulse 1ms`) → `animationend` → SMIL `<set class=done>` → `:has()` on `.core-controller` → `--loop-captured-pass`/`--pass`. Token: same pattern on `body` (`--epoch`). |
| Layers nested or siblings? | **Neither — one graph reused 12×.** The 12 KV banks are nested descendants (depth 27→38). In the scalar `demo/` the 12 blocks are nested: block L+1 is inside block L's `bL-bridge-gate` (`browser_gpt2_core.py:381-391`; parse: `#block-0` at depth 12, `#block-1..11` each at depth 16 relative to its bridge, chain depth 53). |
| Nesting depth / element count | ctx32: 56 / 92,356. demo: 53 / 182,269. Loop fixture (119/71): 1,700 elements. |

Byte budget of the ctx32 sheet by rule kind (python brace scan, string literals normalised): `@container corestate style(--layer:N)` 72,828,605 B (470 top-level blocks; 12 × 6.07 MB; of which 48.0 MB = 384 slot write rules, 0.55 MB = 12 alias rules, ≈2.0 MB per layer = weights, consumers, LN); plain rules 9,645,172 B (`.head-fine-row:nth-child` 3.89 MB, `.fvs-v-*` 1.58 MB, `.fvs-score-*` 1.14 MB, `.position-embedding` 0.89 MB, `.head-isolation` 0.57 MB, `.core-reset` 0.31 MB, …); `@property` 2,348,699 B (29,892); `@keyframes` 390,138 B (10,411); `@container loopcontrol style(--pass)` 38.9 KB (385); `@container runtime style(--epoch)` 9.1 KB (64); `@font-face` 261; `@counter-style` 75 KB.

---

## 3. Per-pass dirtied bytes

### 3.1 Method

"Dirtied bytes" = Σ over elements whose style Blink recalculates of the **bytes of declarations that element itself matches** (its class rules under the currently-true container conditions + its inline `style`). Inherited custom properties are *not* counted as bytes on descendants (Blink copies the inherited variable map by reference **[inference]**), but a recalculated element re-substitutes and re-parses every `var()`-bearing declaration it matches (C1 §4.5, M1 README "MB1b"). Per-class active-rule bytes were taken from the sheet with only the `--layer:0`, `--fvs-write-slot:0`, `--pass:1`, `--epoch:1`, `--loop-phase:0` branches counted as matching; each element's own bytes were then summed over the parsed HTML tree (script logged as items 33/37/51). Two corrections were applied by hand where the class→rule mapping over-assigned `:nth-child` rules (`head-fine-row`: 256 × 15.2 KB = 3.89 MB; `loop-metric`: 1,538 × ≈0.2 KB).

**Applied own-declaration bytes, whole ctx32 document if every element were recalculated once ≈ 254 MB** (2.9× the 88 MB sheet), concentrated in:

| Element class | Elements | Active rule bytes each | Applied bytes | Share |
|---|---:|---:|---:|---:|
| `i.shared-proj-packP` | 3,072 | 39,230 (+ pack rule for its layer) | **122.1 MB** | 48 % |
| `i.fvs-v-H-S` | 24,576 | 4,005 (+ 1.5 KB substituted `--fr-v` list) | **101.2 MB** (+37 MB substitution) | 40 % |
| `i.head-row` | 50,257 | 332 + inline ≈25 | 17.9 MB | 7 % |
| `head-fine-row:nth-child(N)` | 256 | 15,196 | 3.9 MB | 1.5 % |
| `i.metric` (carriers) | 8,839 | 113 + inline ≈180 | 2.6 MB | 1 % |
| `i.metric.fvs-score-H-S` | 385 | 2,976 | 1.15 MB | |
| `.position-embedding` | 1 | 891,068 | 0.89 MB | |
| `.head-isolation` | 1 | 572,759 | 0.57 MB | |
| `.shared-fc-cN` | 6 | ≈80,000 | 0.48 MB | |
| `.fvs-bank(-L)` | 12 | 19,120 (+170,718 on the selected bank) | 0.40 MB | |
| `.shared-qkv-cN` | 5 | ≈68,000 | 0.34 MB | |
| `.core-reset` | 1 | 309,078 (+ inline/valid) | 0.33 MB | |
| `.shared-ln1/ln2` | 2 | 138,600 | 0.28 MB | |
| everything else (stage wrappers, consumers, loop, embedding, feedback) | ≈4,900 | | ≈2.4 MB | |

So the "40 MB stylesheet re-evaluated per pass" picture is wrong in both directions: only ≈2.3 MB of sheet text is *matchable* at any moment (one layer block's weights + plain rules; 66.7 MB of other layers' blocks and 3.9 MB of other slots' write rules never match), but two rule populations are applied to 3,072 and 24,576 leaf elements respectively, so a full restyle of the open core costs ≈228 MB of declaration text, not 40.

### 3.2 State writes in one ctx32 layer pass and what they dirty

Subtree sizes below are counted from the parse (elements / applied bytes under the root). "Locked" means inside a `content-visibility:hidden` gate; Blink skips style recalc of display-locked children **[inference; M1 MB2(c) was designed to confirm, no result recorded]**. Whether a gate that *closes* during a recalc also stops that same recalc from descending is the key uncertainty (scenario A = yes; scenario B = the handshake writes restyle the whole open subtree).

| # | Write (emitter location) | Property, registration, element, depth | Elements dirtied (A) | Declaration bytes dirtied (A) | ms @ 43 MB/s | Layout that follows |
|---|---|---|---:|---:|---:|---|
| S1 | pass start: `--pass`→ `--layer`,`--position`,`--loop-phase` on `.core-controller` (`reused_core.py:267-271`, adapter :49-55, :89-104); `--native-pass` republished on `.core-block` (adapter :111-113, inherits:true); `--loop-in-*`→`--x-*` on `.loop-input`/`.reused-input` (loop_parts :56-62; `reused_core.py:281-284`) | inherits:true numbers on ancestors of the whole core (d12–16); style-container flips on `corestate`/`loopcontrol` | core subtree minus locked `shared-qkv-gate` subtree: ≈3,860 (incl. 1,536 `<g>`, 2,305 carriers) | 1.53 MB (core-reset 0.33, ln1 0.14, shared-qkv 0.13, 5 consumers 0.34, loop-input/reader 0.20, 2,305 carriers 0.39) | 36 | shape 2,304 QKV glyph runs (3 shard fonts, 768 axes) + marker |
| S2 | QKV consumers (`--qkvp-*` inherits:false → `--qkv-*` inherits:true, `hybrid.matvec` :209-232) + `--stamp-qkv`→`--gate-qkv` opens `shared-qkv-gate` | on `shared-qkv-c0..c4` d19–23 | gate subtree minus locked `fvs-score-gate` (25,349) and `cache-bridge-gate` (10,032): ≈406 (fvs-query, 12 banks, 385 score glyphs, reader, bridge c0/c1) | 2.06 MB (banks 0.40 incl. 1,536 alias + 1,488-name list on bank L; 385 × 2,976 = 1.15; fvs-query 0.016; reader 0.039; bridge-c 0.084; consumers re-applied 0.34) | 48 | shape 384 FvsDot score glyphs (128-axis instances) + marker |
| S3 | score animations → `--fs`,`--fe`,`--fb`… on `.fvs-score-reader` (:270-280, :309-319) + `--fvs-score-ready` opens `fvs-score-gate` (:281) | inherits:true on d39–41 | `fvs-score-gate` subtree: 25,349 (softmax, 768 row spans, **24,576 V glyphs**) | **101.4 MB** (+≈37 MB of substituted 64-axis `--fr-v` lists) | **2,360 (–3,220)** | shape 24,576 FvsValue glyphs; 768 inline-flex row widths |
| S4 | row widths → `cache-bridge-c0/c1` animations → `--ctx-*` (inherits:true, d26–27) + `--bridge-ready` opens `cache-bridge-gate` | d26–29 | gate subtree minus locked `shared-attn-gate` (9,256): ≈776 | 0.45 MB (shared-attn 0.10, 768 carriers 0.13, attn-c 0.13, bridge-c re-applied 0.08) | 10 | shape 768 attn glyph runs |
| S5 | attn consumers → `--r-*` + `--gate-attn` opens `shared-attn-gate` | d31–34 | minus locked `shared-fc-gate` (6,171): ≈3,085 | 1.41 MB (ln2 0.14, shared-fc 0.14, 3,072 carriers 0.52, fc-c×6 0.48, attn-c re-applied 0.13) | 33 | shape 3,072 fc glyph runs |
| S6 | fc consumers → `--hidden-*` (3,072, inherits:true) + `--gate-fc` opens `shared-fc-gate` | d37–44 | minus locked `shared-proj-gate` (2,323): ≈3,848 | **123.0 MB** (shared-proj 0.09, 768 carriers 0.13, **3,072 packs × 39,230 = 122.1**, proj-c 0.13, fc-c re-applied 0.48) | **2,860** | shape 768 proj glyph runs (4 fallback runs each) |
| S7 | proj consumers → `--out-*` + `--gate-proj` opens `shared-proj-gate` → `.reused-output{--loop-out-*}` → `@container loopcontrol style(--loop-phase:b){.loop-bank-b{--saved-b-i:var(--loop-out-i)}}` (loop_parts :49-52) | d46–52 | `shared-proj-gate` subtree: 2,323 (+774 `reused-final-export` at layer 11) | 0.63 MB (reused-output 0.02, loop-banks 0.10, loop-scroll/track forwarding 0.03, 1,538 loop-metric ≈0.3, proj-c re-applied 0.13) | 15 | 769 loop-metric widths (+769 b11-bridge widths at layer 11) |
| S8 | loop-reader 1,538 animations → `--lp-b-*` (inherits:false) → `.loop-input{--loop-ack}` (`<number>` **inherits:true**, d14) → `#loop-ready-N{animation:loop-pulse}` | inherits:true on d14 while **all six gates are open** | **A:** loop-input + loop-reader only ≈3 · **B:** entire open core subtree 39,642 | A: 0.20 MB · **B: ≈228 MB** | A: 5 · **B: 5,300** | none required (1 ms opacity animation) |
| S9 | `animationend` → SMIL `set class=done` → `:has()` → `.core-controller{--loop-captured-pass:N}` (inherits:false) → `--loop-held:1` flips `@container loopcontrol style(--loop-held:1)` (loop_parts :53) → `#loop-ack-N{animation}` | style-container query result change on `.core-controller` | A: `.core-controller`, banks 2 · **B:** Blink forces recalc of the container's descendants when a `style()` query result changes **[inference]** → 39,645 | A: ≈0.1 MB · **B: ≈228 MB** | A: 2 · **B: 5,300** | none |
| S10 | SMIL → `.core-controller{--pass:N+1}` = next S1 | | | | | |

Sum per layer pass: **scenario A ≈ 231 MB → 5.4 s at 43 MB/s; ×12 = 2.77 GB → 64 s/token.** Scenario B adds 2–3 × 228 MB per pass → 690–915 MB → **8.3–11 GB/token → 190–255 s**.

Token-level writes (once per token): `body{--epoch}` (inherits:true; whole document minus locked subtrees ≈ 3,900 unlocked elements outside the core + core S1 set ≈ 3.3 MB, incl. `.position-embedding` 0.89 MB and 522 font witnesses); embedding consumers + receipt (0.13 MB); `b11-bridge` → `#core-result`/`final-normalization`/`head-input-bank`/`head-isolation` (0.76 MB) → `full-head` opens: 51,141 elements, **22.4 MB** (17.9 head-row + 3.9 fine rows + 0.6) → 0.52 s; detached reader / 32 token slots / feedback (≈0.02 MB). **Token-level total ≈ 27 MB → 0.6 s.** Measured head milestone `headInput→head→capture`: 1.1–7 s.

### 3.3 Predicted vs measured

| Bundle | Model A prediction (style) | Measured `RecalcStyleDuration`/token | Measured total/token |
|---|---:|---:|---:|
| ctx32 (24,576 V glyphs + 3,072 proj packs) | 2.77 GB → **64 s**, position-independent | 38 s (epoch 3) → 63 s (epoch 12) → 102 s (epoch 31) | 57 → 89 → 143 s |
| ctx32 scenario B | 8.3–11 GB → 190–255 s | (same) | |
| demo scalar (12 physical blocks; per block: reset 0.31 + ln1 0.14 + qkv 0.12 + 2,304 carriers 0.39 + qkv-c 0.34 + **kv-bank 0.32** (147 KB list + 172 KB write) + **live-mix 0.46** + attn 0.10 + 768 carriers + attn-c 0.13 + ln2/fc 0.26 + 3,072 carriers 0.52 + fc-c 0.46 + proj 0.08 + **3,072 packs 122.1** + proj-c 0.13 + bridge 0.18 ≈ **126.2 MB** = the measured `#block-0` subtree total) | 12 × 126 MB + head 22 MB = **1.54 GB → 36 s** | 22.5 s (epoch 2) → 35.5 s (epoch 7) | 62 → 91 s |

Reading: for the **scalar demo** — a clean top-down cascade with no per-layer handshake and no ancestor writes while gates are open — the bytes-at-43 MB/s model lands inside the measured style band (36 s predicted vs 22.5–35.5 s). For **ctx32** the flat prediction (64 s) sits inside the measured 38–102 s band but the model has no position dependence, while the measured style time grows ≈2.2 s per position; and the component measurements bound the two heavy populations well below 43 MB/s: the whole fresh MLP stage (fc + proj, incl. the 3,072 pack applications = 122 MB) measures 657–772 ms (S7 :199), i.e. ≥160 MB/s equivalent, and the whole attention update at 32 positions measures 0.83–1.41 s (S7 :62, :237) against 101–138 MB → ≥100 MB/s. The most plausible reason is Blink's MatchedPropertiesCache sharing computed styles between the 64 (V) or 768 (pack) elements that match identical declarations under identical inherited data **[inference; the project's own `uncached_style` ablation exploits `attr()` to defeat exactly this cache, `browser_gpt2_core.py:216-223`, and reported "no help"]**.

**Where the hypothesis stands structurally.** (1) *Number of passes*: real bundles do 216–266 recalcs/token, not 119. (2) *Dirtied bytes per pass*: not "most of the 40 MB sheet" — at most ≈2.3 MB of sheet text is matchable per pass, but two leaf populations fan it out to ≈228 MB of applied declarations per full restyle, with V glyphs (101 MB) and proj packs (122 MB) carrying 98 %. (3) *Common-ancestor state bank*: the KV banks themselves are `inherits:false` and do not fan out; what fans out is (a) every activation vector (`--x`, `--qkv`, `--ctx`, `--hidden`, …) being declared on an ancestor of all downstream stages by design, mitigated only by the content-visibility gates, (b) the selected bank's 1,536 inherited `--fr-*` aliases (all 385 + 24,576 glyphs are descendants of all 12 banks), and (c) the handshake properties `--loop-ack`/`--loop-ready` (inherits:true, depth 14) and `--native-pass` (inherits:true, depth 12), which are written while every gate is open (S8–S10). Whether (c) restyles the whole open subtree (scenario B) is the single largest unknown; it is exactly what M1's MB2(b)/(c) pages test, and no result is recorded yet. (4) *43 MB/s*: fits the scalar demo, over-predicts the two glyph populations by ≥2.5–4× per the component measurements, and cannot produce the ×2.5 growth from position 2 to 31. The growth has structural candidates outside the bytes model: 48·p retained `*`-list transitions per bank whose effect stacks are re-applied on every bank restyle (12 banks × ≥3 restyles/pass × 12 passes ≈ 430 bank restyles/token × 48p interpolations = 660k list applications/token at p=32), distinct FvsValue/FvsDot font instances for filled slots (empty slots share identical settings), and the 5.2 GiB working set.

---

## 4. Retained animations and transitions

| Population | Where emitted | Count (ctx32) | Count (demo scalar) | Property animated | Ever finished / removed / frozen? |
|---|---|---:|---:|---|---|
| Stage carrier readers (`animation-name` lists on consumer elements, `animation-timeline: view-timeline`, `fill-mode: both`) | `hybrid.matvec` :209-232 (qkv 2,304, attn 768, fc 3,072, proj 768) + 4 stamps; `bridge` :283-325 (768+1 ×2); `loop_parts` (1,538); `font_vector_cache` :243-282 (384+1); embedding 768+1; feedback 32 | ≈12,300 live effects on ≈30 elements (87,202 names in the sheet, but only one layer's consumer rules match) | 12 × 7,684 + 12 × 769 + 768 + 8 ≈ **102,000** live effects | registered `<number>` progress props (`--qkvp-i`, `--fcp-i`, `--bridge-p-i`, `--lp-b-i`, `--fsp-h-s`, `--embedp-i`, `--feedback-p-i`) | Never finish: timeline-attached (`animation-duration:1s` on a view timeline, `both`); they are the vector transport. Ticked every frame **[inference: `DocumentAnimations` iterates all animations per frame]** |
| One-shot receipts (`animation:native-handshake/loop-pulse 1ms both`) | runtime :49, :77-81; loop_parts :96-99; adapter :58-61 | 886 rules, ≤1 active at a time | 87 rules | `opacity` .99→1 | finish after 1 ms; `both` fill retained; SMIL `<set fill="freeze">` classes never reset |
| **KV retention transitions** (`transition-duration:1ms; transition-delay:86400s; steps(1,end)`) | `font_vector_cache.py:171-175, 209-224`; scalar: `browser_gpt2_core.py:84-90, 105-128` | `transition-property` lists: 12 banks × 1,536 names (+ 384 write rules × 1,488). New retained transitions **per position: 12 × 48 = 576** (each holding a 64-axis `*` list ≈1.5 KB, or a `<number>` scale); **18,432 = all fields** is the ceiling reached at position 32 | `.kv-bank{transition-property: 8 × 1,536 = 12,288 names}` (147 KB) on 12 elements; **18,432 new transitions per position** (1,536 per slot per block); **129,024 by position 8** — this is the S6 figure, i.e. it describes the scalar demo, not the font-vector bundle | registered custom props: `--fc-{k,v}-S-H` (`*`), `--fc-{ks,vs}-S-H` (`<number>`); scalar `--kv-{k,v}S-i` (`<number>`) | **Never**: delay 86,400 s (24 h) exceeds any run; the transition sits in its before-phase forever, holding the captured value. Nothing cancels or freezes it; there is no removal path in the emitter. When the slot's write rule stops matching, the declared value reverts to `initial-value` (zero list / 0) and the delayed transition from captured→initial is what *is* the memory |
| Other latches (same delayed-transition idiom) | `.head-input-bank` 768 `--h` + epoch (runtime :322-327); `.token-slot-N` `--saved-token-N` (:65-67); `.feedback-reader` `--frozen-prompt` (:58-59); `.loop-bank-b` 769 `--saved-b-i` (loop_parts :36-40) | 768 + 32 + 1 + 1,538 | 768 + 8 + 1 (no loop banks) | `<number>` | never |

38 `86400s` declarations in the ctx32 sheet, 11 in demo. The `transition-property` list on a bank is re-evaluated on every restyle of that bank: Blink walks the list and compares old/new computed values for each listed property **[inference]** → 12 × 1,536 comparisons of 1.5 KB lists per bank restyle (≈18k list compares per S2 restyle), plus application of the running transitions' effect stack (48·p per bank).

---

## 5. Pass count derived from the gating logic vs measured

Minimum frames per layer pass forced by the design (each view-timeline hop needs layout → timeline update → next-frame style):

| Step | Style recalcs | Layouts | Why |
|---|---:|---:|---|
| S1 inputs + gates close | 1 | 1 | new `--x`, new fonts on `.shared-qkv`, 2,304 glyph runs shaped, marker laid out |
| S2 QKV values + gate open | 1 (+1 if the unlock of the gate's children is a separate recalc **[inference]**) | 1 | score glyphs shaped |
| S3 scores → softmax + gate open | 1 (+1) | 1 | 24,576 V glyphs + 768 rows shaped |
| S4 ctx + gate open | 1 (+1) | 1 | attn glyphs |
| S5 r → ln2/fc + gate open | 1 (+1) | 1 | fc glyphs |
| S6 hidden → proj + gate open | 1 (+1) | 1 | proj glyphs (4 fallback runs each) |
| S7 out → loop bank widths | 1 (+1) | 1 | 769 loop-metric widths |
| S8 loop-reader readback, `--loop-ack`, ready pulse | 1 | 0–1 | |
| S9 SMIL captured → `:has()` → `--loop-captured-pass`, ack pulse | 1 | 0–1 | |
| S10 SMIL advanced → `--pass` | (= next S1) | | |
| **Per layer** | **10 minimum, 16 with gate-unlock recalcs** | **7–9** | |
| **12 layers** | 120–192 | 84–108 | |
| Token level: `--epoch`, embedding (2 hops), b11 bridge, head-input latch, full-head open, head two-pass (coarse→fine→epoch), detached reader, token slot, feedback, 2 SMIL pulses | ≈12–20 | ≈8–10 | |
| **Per token, derived** | **≈132–212** | **≈92–118** | |
| **Measured (ctx32, §0.1)** | **216–266** | **106–114** | |
| **Measured (loop fixture, 24 passes)** | 119 → ≈5 per handshake pass | 71 → ≈3 | matches S7–S10 alone |
| **Measured (scalar demo)** | 130 → ≈10 per block + 10 token-level | 64 → ≈5 per block | scalar block: 5 hops (qkv, attn, fc, proj, bridge) × 2 recalcs, 1 layout each; no per-layer handshake |

Reconciliation: 119/71 is the handshake-only fixture; the real ctx32 bundle needs ≈16 recalcs and ≈9 layouts per layer (measured 18–22 / ≈9.2), consistent with two recalcs per view-timeline hop plus one per content-visibility unlock and a four-recalc SMIL handshake. The scalar demo's 130/64 matches exactly two recalcs and one layout per hop with five hops per block.

---

## 6. Top structural changes that cut dirtied bytes per pass ≥5× (no JS, no model change, stock Chromium)

| # | Change | Emitter location | Bytes/pass effect (model A) | Prior experiment & outcome |
|---|---|---|---|---|
| 1 | **Remove the 24,576 leaf V glyphs**: either (a) the `fallback` value layout — 768 row spans carry 32 characters selected by `unicode-range` into 32 slot fonts, with the 32 × 65-axis list on 12 `.fvs-value-head-H` elements; or at minimum (b) the v2 operator (one `P000` weight axis instead of 64 duplicated `Q` axes) plus computing the per-(H,S) weight once as a registered number and referencing it, cutting the per-glyph rule 4,005 B → ≈300 B | `tools/browser_gpt2_font_vector_cache.py:196-204, 232-235, 334-337, 350-352, 359-366` (`value_layout="fallback"`), `:45-77` (P000 collapse), `:322-349` | S3: 101 MB → ≈1.1 MB (a) or ≈7 MB (b): **14–90×** | (a) "Compact attention encoding (font fallback merges runs): −11 % at 32 positions" (S6 :174); `experiments/browser-gpt2/font-vector-fallback-attention32/`, `…-fallback-ring32-window8/`; v2 + fallback listed as "source-only candidates, NOT yet browser-validated" (`experiments/browser-gpt2/SCALING_WORK.md:232-235`). Risk: "Chrome resolves only first 3 variable fonts per fallback run" (E4 #298) — must be re-checked for a 32-font `unicode-range` stack |
| 2 | **Make the handshake and pass-counter properties non-inherited** and publish them only to their readers: `--loop-ready`, `--loop-ack` (read only by `@container loopreceipt style(...)` and the `.loop-compute` gate), `--native-pass` (read only by `--gate-*` formulas and the marker widths) → `inherits:false` + explicit `:inherit`/republish on the ≈8 receipt/marker elements, as `scoped_state` already does for `--qkvp`, `--bridge-p`, `--saved-*` (`reused_core.py:286-306`) | `tools/probe_native_reused_loop.py:17-30` (`regs([...])` all inherits:true), `browser_gpt2_reused_adapter.py:41, 111-113`, `reused_core.py:286-306` (private set) | Eliminates S8/S9/S10 whole-open-subtree restyles if scenario B holds: 690–915 MB → 231 MB per pass (**3–4×**), and it is a prerequisite for #1/#3 to show up at all. If scenario A holds, ≈0 — this is the cheapest way to find out | Nothing tested this. Related: "static bank readers" −9 % continuation and "local timeline scope" neutral (`optimization-followups-2026-09-17/RESULTS.md:41-45`); "selective loop" +28.7 % with identical 119/71 (`style-simplification-review/RESULTS.md:27-36`). M1 MB2(b) is the designed test; no result recorded |
| 3 | **Un-nest the KV banks**: one bank element per layer as *siblings* of the attention graph (like the scalar core's `#cache-L>.cache-active{display:none}` pattern, `reused_core.py:253-260`), with only the selected bank's 48·p filled fields aliased (not 1,536) into a single `--fr` publisher above the score glyphs; keep `inherits:false` storage | `font_vector_cache.py:401-407` (nesting loop), `:225-229` (alias rule), `:209-224` (write rule); replace the 1,488-name inline lists with `var(--fvs-retained-S)` as current source already does | S2: 0.40 MB banks + 11 × 1,536 transition-list evaluations → ≈0.05 MB (**8×** on that step); removes 11 levels of ancestry above 24,961 glyphs; cuts inherited-map copies per bank restyle | Locality diagnostic: one-head local update 16.4 → 2.7 ms style (6×) (`browser-gpt2-scaling/RESULTS.md:27-64`); but all-head "owned attention" **+20 %** native (S7 :97) and "metric-state isolation" 43.2 → 44.8 s (`SCALING_WORK.md:224-226`) — both added new transport rather than removing ancestry |
| 4 | **Proj packs → one inherited axis list** (`--global-projection`: 12 shards re-tagged to disjoint axes, `packs=1`, settings on `.shared-proj`, glyph rows contain all 12 shard characters) so the 3,072 `i.shared-proj-packP` elements and their 4 × 39 KB rules disappear; fallback: `proj-settings` materialisation (`isolate_metric_state`) so each pack element substitutes one pre-computed list instead of 768 `calc()` | `tools/browser_gpt2_projection_layout.py`, `build_hybrid_twelve_block.py:131-134, 160-167, 173-178`; `reused_core.py:33-52` | S6: 122 MB → 0.13 MB (**900×** in bytes) | **Measured neutral**: global projection 39.917 → 40.146 s (12-block, S7 :194); `proj-settings` −0.35 % / −1.34 % (S7 :199). This is direct evidence that per-element bytes are *not* charged at 43 MB/s for this population (MPC sharing) — so #4 is low priority despite the largest byte count |
| 5 | **Shorten what is actually re-parsed per restyled element**: (i) LN sums as `@function` bodies or fewer digits; (ii) V/score weight sub-expressions computed once per (H,S) as registered numbers (`--fw-H-S`) and referenced (cuts `calc(var()*var()/var())` × 64 → `var()` × 64 per glyph); (iii) drop the 64 duplicate `Q` axes (v1 → v2); (iv) `.core-reset`/`.head-isolation` `:initial` walls (16,158 / 29,081 decls) replaced by `inherits:false` registration where the private set allows (`browser_gpt2_core.py:396-400` already deletes `:initial` for private props) | `font_vector_cache.py:322-349`; `build_gpt2_block_css.py:230-258`; `browser_gpt2_core.py:100-103`; runtime :268-283 | 2–4× on S3 if kept as leaves; ≈0.9 MB/pass on resets | "layer-rule hoist −3.3–4 % sheet → neutral" (E5 #319) shows sheet-size cuts alone do nothing; M1 MB5 (`calc-var1` vs `calc-var16`) is the designed discriminator, no result recorded |
| (6) | *Bounded window* `--kv-window 8 --kv-sinks 2`: V glyphs 24,576 → 6,144, scores 384 → 96, bank fields 1,536 → 384, and flat cost per position | `font_vector_cache.py:148-150, 168-169`, runtime CLI `--kv-window/--kv-sinks` | S3 4×, removes the position slope | `font-vector-ring32-window8`: 0.46–0.49 s/update flat, RSS 987 MiB (`SCALING_WORK.md:220-223`); **changes the attention mask** ("quality untested", S6 :174) — excluded from the top 5 as a model change |
| (7) | *`widths` value layout*: V fonts at a fixed location, softmax weight applied to the shaped width (`calc-size`), so glyph font instances stop changing per pass | `font_vector_cache.py:340-349` | no byte change; layout/font-instance change | "shaped-V-width reuse 1.35 → 0.98 s" component; native −6.3 % / **+13.7 %** (S7 :79, :194) |

---

## 7. Bottom line

* The pinned validated bundle is `experiments/browser-gpt2/demo-font-vector-context32/` (v1 font-vector, reused graph, 32 slots) = the 3,177 s run; the 78 s/token figure is the *unpinned* scalar 12-block `experiments/browser-gpt2/demo/`. Neither is reproducible from current source without the v1 fonts.
* State lives on ancestors by construction: hidden-state and every intermediate vector are inherited registered numbers on the stage chain (depths 14–47); KV is 12 nested `inherits:false` banks whose selected member re-publishes 1,536 inherited list aliases above 24,961 glyph leaves; the handshake counters are inherited numbers at depths 12–14 written while all gates are open.
* Per full restyle of the open core ≈228 MB of declarations are applied, 98 % of it by two leaf populations (24,576 V glyphs × 4 KB; 3,072 proj packs × 39 KB), not by the 88 MB sheet (only ≈2.3 MB of which can match at once).
* Model A (gates lock immediately, handshake writes stay local) predicts 64 s/token of style for ctx32 and 36 s for the scalar demo at 43 MB/s; measured style is 38 → 102 s (ctx32) and 22.5 → 35.5 s (demo). The scalar demo fits; ctx32 is under-determined because (i) component measurements imply the two glyph populations are charged ≥2.5–4× cheaper than 43 MB/s (MPC sharing), and (ii) the measured ×2.7 growth with position is invisible to a bytes model — it points at the retained-transition effect stacks (48·p per bank per restyle) and distinct font instances for filled slots.
* Pass counts: the real bundles do 216–266 recalcs / ≈110 layouts per token (ctx32) and 130 / 64 (demo); "119/71" is the 24-pass handshake fixture (≈5/3 per handoff, ≈0.4 s).
* The hypothesis survives in amended form — cost is passes × *applied* declaration bytes of the *dirtied leaf populations*, not stylesheet size — with one decisive unknown (scenario A vs B for the handshake writes) that M1 MB2 and a single `inherits:false` change (§6 #2) would settle.
