# R5A — where combined7's ≈16 s/token and ≈6 GB go (2026-09-24)

STATUS: **PARTIAL (13:0x)** — census final; memory table from ONE traced run `mem8-3` (memory-infra + devtools.timeline, 8/8 ids, no data loss) taken under heavy machine memory pressure (swap 5.9/6.4 GB, disk 0.3 GB): allocator split is solid, absolute footprints include swapped pages; the full-category time run (`time8-3`) was aborted by the coordinator at start (disk); §1 time attribution is therefore per-pass (UpdateLayoutTree/Layout/PrePaint/GC from devtools.timeline) plus the untraced split — paint-lifecycle/animate/UpdateLifecycle self are NOT separated. Launcher gate now AC + disk ≥ 3 GB + swap used < 3,000 MB. — census done (`R5A/census.md`, `R5A/census.json`); traced runs prepared (`R5A/run_trace8.sh`, harness `R5A/bench_native_r5a.mjs`)
and queued behind the machine gate (AC held since 12:14; disk free oscillates 2.3–3.3 GB, gate needs ≥ 3 GB; `R5A/launch_when_ready.sh` retries every 60 s).
Sections 1–2 (time / memory by allocator) will be filled from the traces; §3 (census) and the census-derived parts of §4 are final.

## 0. Headline so far (census + B5's untraced runs of this exact bundle)

- **The DOM is 67,569 elements, not 240 k**: head 51,138 (75.7 %; 50,257 `.head-row`), V glyph leaves 6,144 + 768 rows, carriers 7,680 + 768 embedding,
  consumers 144 (R4T chunks, nested 36/12/48-deep), score glyphs 96, R4S chain 48, banks 12, controller ≈120, font barrier 587. Nodes incl. text = 132,081.
- **Live animated state: 9,231 view-timelines ↔ ≈9,231 carrier animations ↔ 9,232 `@keyframes`, 39,513 registered properties (16,123 inherited), 701 k `var()`.**
- **CSS is 40 MB, 13.1 MB of it the 576 per-layer `.shared-fc-cN` consumer rules** (64 animation-names + 64 decodes × 48 chunks × 12 layers), 4.2 MB `.shared-qkv-cN`,
  3.9 MB `.head-fine-row:nth-child(N)` (256 rules × 15 KB `if()` chains), 3.3 MB LN sums, 3.1 MB proj. Two single elements carry 24,107 (`.head-isolation`) and
  16,158 (`.core-reset`) `--x:initial` declarations.
- **Fonts: 283 faces = 239.1 MB woff2 on disk**: embedding 56.9 MB (1 face), head 78.4 MB (6), stage weights 103.8 MB (252 faces, unicode-range gated but
  force-loaded by the 283 `.font-witness` elements), F4 operator fonts 64 KB. Decoded sfnt size is larger; the memory dumps will give the resident figure.
- **RSS shape (B5 runs, 1 Hz `ps`)**: 1.67–1.86 GB after load → **+2.0 GB during token 1** (3.5–3.9 GB) → +≈300 MB/token with no release → 5.7–5.95 GB at token 8.
  Time shape: token 1 = 17–19 s, tokens 2–8 = 13.2 → 17.3 s (+≈0.5 s/token slope, same sign as RSS growth). 436 style passes and 64 layouts per token.


## 1. Time by mechanism — combined7, run `mem8-3` (tokens 2–5 = the least pressured window; per-pass `UpdateLayoutTree` elementCount → subtree via census.md §5)

Run: 8/8 ids, tokens 18.4 13.8 14.3 15.1 16.2 19.8 19.7 21.4 s (B5 clean-state: 13.2–17.3); 67 `UpdateLayoutTree` + 64 `Layout` + 39 `PrePaint` (= frames) per token;
RecalcStyleCount 227 → 647/token although only 67 style passes are events → **160–580 interleaved container-query recalcs per token (R4S's size-container chain), growing +65 per filled position, executed inside `Layout`.**

| mechanism (pass signature, ×/token) | s/token (k=2–5) | share of style | what it is / fitted constant |
|---|---:|---:|---|
| **fc-stage write** pass, 3,141 elements ×12 | 1.31–1.93 | 24 % | LN2 + fc font-variation-settings → restyle of the 3,072 fc carriers (+48 chunks): **≈45 µs per carrier** (inline `width:calc(var())` + view-timeline) |
| **fc readback → proj write** pass, 824 el. ×12 | 1.27–1.34 | 22 % | 48 fc chunk consumers apply 3,072 changed animations (≈20 µs each ≈ 61 ms) + proj stage (778 el.) restyle: 106–113 ms/pass |
| **qkv readback → KV bank write → 96 score glyphs + R4S chain**, 163 el. ×12 | 0.95–1.30 (2.83 at k=7) | 16–35 % | 67–108 ms/pass at k≤5, up to 236 ms at k=7: the 12·p score-glyph K-list (≈12.7 KB) substitutions + bank aliases; grows with p |
| **loop readback + pass advance + LN1 → qkv fonts**, 2,366 el. ×11 | 0.68–0.96 | 14 % | 62–94 ms/pass (R3A's 2,323-pass was 64 ms) |
| **ctx → attn fonts**, 800 el. ×12 | 0.35–0.38 | 7 % | 29–32 ms/pass (768 attn carriers + 12 chunks) |
| **head pass**, 50,898 el. ×1 | 0.37–0.42 (0.87 at k=8) | 7 % | 7.3 µs per head row; GC stalls land here under pressure |
| token start (2,405 el.) + handshake (895/791/39/6/1) | 0.20–0.25 | 4 % | embedding → S1 of layer 0; SMIL/marker passes |
| **style total (`UpdateLayoutTree`)** | **5.3–6.0** | 100 % | B5 untraced 5.6–6.0 ✓ |
| **layout** (64/token) | **4.26 → 5.90** (k=2→5), 8.9 at k=8 | | head layout ≈1.3 s (50k-row shaping) + **interleaved R4S container recalcs of the V/score subtree (the 6,916-element V pass no longer appears as a style pass)** + 768·p V-leaf shaping + carrier layout (8,448 changed widths/layer). Slope ≈ +0.5 s/token/position in this pressured run (B5: +0.20) |
| **PrePaint incl. compositing inputs** (39 frames) | **1.78** flat | | 46 ms/frame; R3A: 9.3 µs × dirty layout objects, head frame ≈0.9 s of it |
| GC nested in the above (`V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED` 25×/run 6.6 s, incremental embedder tracing 4.3 s, epilogue 1.8 s) | **1.66** (range 1.0–3.0) | | 9.5 % of the run; pressure-inflated (R3A clean: 1.0) |
| memory dumps (my harness, `MemoryDumpManager` 4.9 s/run) | 0.6 | | artefact of this run, not the page |
| **not separable in this trace**: paint lifecycle (`PendingAnimations::Update`), animate step, `UpdateLifecycle` self = wall − busy | **≈2.9** (23 s idle of 141 s) | | R3A/R4T model: 39 frames × ≈75 ms + 8,448 changed carriers/layer × 17 µs ≈ 1.7 s … needs the `blink`-category run |

Versus R3A's R2F attribution (26.1 s traced-light): style 10.4 → 5.7 s (−45 %: R2G/R3R handshake folds, R4T chunking, R4D lean latches, transition latch gone — only 26 KV latches/layer remain, `transition` = 0.1 s), layout 5.6 → 4.9 (but now carries R4S's container recalcs), paint-lifecycle+animate+UL 8.2 → ≈2.9+1.8 (R4S 3.0 → 2.5 frames/layer, R4T 40 → 17 µs per changed carrier), head 3.3 → ≈2.7 (unchanged mechanism), GC 1.0 → 1.7 (memory state).

## 2. Memory by allocator — renderer private footprint (MB; memory-infra light dumps requested by the harness after each token capture; detailed dump 8 s after token 8). Machine: swap 5.9/6.4 GB used, so footprint includes swapped pages (ps RSS ran 3.2–4.3 GB; B5 clean-state RSS 5.95 GB ≈ this footprint)

| dump | footprint | Δ | Oilpan heap (`blink_gc/main/heap`) | Δ | malloc | Δ | PartitionAlloc buffer | web_cache fonts (inside malloc) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| post-load (before Run) | 1,440 | | 150 | | 1,297 | | 305 | 873 |
| token 1 | 3,342 | **+1,902** | 1,817 | **+1,667** | 1,484 | +188 | 328 | 873 |
| token 2 | 4,422 | +1,080 | 2,549 | +731 | 1,749 | +265 | 354 | 873 |
| token 3 | 4,979 | +556 | 3,082 | +533 | 1,817 | +67 | 372 | 873 |
| token 4 | 5,301 | +322 | 3,289 | +207 | 1,917 | +100 | 383 | 873 |
| token 5 | 5,317 | +16 | 3,438 | +149 | 1,963 | +46 | 392 | 873 |
| token 6 | 5,502 | +185 | 3,567 | +129 | 1,834 | −129 (purge) | 389 | 873 |
| token 7 | 5,749 | +246 | 3,695 | +128 | 1,939 | +105 | 403 | 873 |
| token 8 | 6,240 | +491 | 3,903 | +208 | 2,228 | +289 | 403 | 873 |
| final (detailed, idle) | 5,666 | −574 | **3,899 (live objects 924)** | | 1,706 (allocated 1,526) | −522 | 346 (allocated 317) | 873 |

Where the ≈6 GB is (final dump): **Oilpan heap 3.9 GB of which only 0.92 GB are live objects → ≈3.0 GB committed-but-free Oilpan pages** (NormalPageSpace3 1,845 MB committed / 565 live; Space1 573/115; CustomSpace3 386/36; unspecified/pooled 485) — swept garbage of the per-pass `var()` substitution that Oilpan does not decommit (footprint only falls at OS memory-pressure purges: −574 MB here). **malloc 1.7 GB = 872 MB decoded webfonts** (`web_cache/Font_resources/*/decoded_webfont`, 283 faces: EmbeddingLookup 100 MB, ProdQ16R 3 × 52, ProdQ16H 3 × 27 = 338 MB; the 276 stage faces 535 MB = 5.1× their 104 MB woff2) **+ ≈0.83 GB font platform instances / HarfBuzz faces / shape caches** (the purgeable part: −129, −522 MB drops). PartitionAlloc buffer 0.35 GB (strings, vectors). Skia 0.7 MB, discardable 0, V8 4 MB (no JS).
Oilpan live objects (924 MB, 997 types): **`HashTrieNode<CSSVariableData>` 221.5 MB (854 k) + `CSSVariableData` 124.8 MB (999 k) + `HashTrieNode<const CSSValue>` 121.7 MB (469 k) = 468 MB of custom-property state in ComputedStyles** (114,162 ComputedStyle objects → ≈4.1 KB of variable tries each); calc trees 46 MB (`CalculationExpression*Node` 556 k + 326 k + 230 k + 116 k); shaping 63 MB (`ShapeResultRun` 529 k, RunInfoPart, HarfBuzzRunGlyphData); layout fragments/results ≈70 MB; CSSOM (ImmutableCSSPropertyValueSet 10.3 MB/122 k, CSSUnparsedDeclarationValue 9.1/396 k, CSSNumericLiteralValue 12.3/536 k, CSSCustomIdentValue 10.2/269 k, **CSSParserContext 8.5 MB/53 k**); animations 15.6 MB (ElementAnimations 9,427, KeyframeEffect 12,767, CSSAnimation 9,243); DOM ≈15 MB (66 k HTMLElement, 64 k Text).
Growth per token after token 3: Oilpan +130–210 MB, malloc +50–290 MB (purged under pressure), PA +10.

## 1b (untraced, B5). Phase split of THIS bundle from B5's four runs (`Performance.getMetrics` deltas per token, mean of 4 runs)

| k | wall s | style s (RecalcStyleDuration) | layout s | task s | other = task − style − layout | recalcs | layouts |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18.4 | 7.90 | 4.17 | 16.51 | 4.44 | 218 | 67 |
| 2 | 14.1 | 5.64 | 4.12 | 14.07 | 4.31 | 227 | 64 |
| 3 | 14.7 | 5.84 | 4.49 | 14.70 | 4.37 | 359 | 64 |
| 4 | 15.1 | 5.84 | 4.82 | 15.08 | 4.43 | 371 | 64 |
| 5 | 15.5 | 6.02 | 4.94 | 15.38 | 4.42 | 502 | 64 |
| 6 | 16.0 | 5.91 | 5.25 | 15.57 | 4.42 | 514 | 62 |
| 7 | 16.7 | 6.63 | 5.48 | 16.69 | 4.58 | 648 | 64 |
| 8 | 16.7 | 6.35 | 5.17 | 16.36 | 4.83 | 594 | 60 |
| **mean 2–8** | **15.55** | **6.03 (39 %)** | **4.90 (32 %)** | 15.41 | **4.48 (29 %)** | 459 | 63 |
| fit k=2..8 | 13.26 + 0.457·k | 5.35 + 0.136·k | 3.91 + 0.198·k | 13.39 + 0.404·k | ≈4.4 flat | 134 + 65·k | 64 |

Reading: "other" (paint lifecycle = `PendingAnimations::Update`, animate step, `UpdateLifecycle` self = snapshot validation, compositing inputs, GC outside
style) is a flat ≈4.5 s/token — the per-frame fixed cost; **layout carries most of the per-token slope (0.20 s/token/position: shaping of 768·p V leaves +
12·p score glyphs per layer)**; style grows 0.14 s/token/position with **+65 recalcs per filled position** (R4S's interleaved container-query recalcs,
134 + 65·k per token). Token 1 pays +2.3 s of style (first font instantiation / first-pass cascades) and +2.0 GB RSS.

## 3. DOM census — see `R5A/census.md` (tables 1–3). Populations restyled per pass that carry no live values at cap 8 (for R5E):
- 50,257 head rows + 256 fine rows: restyled once per token (the head pass); inert during the 12-layer loop only if nothing inherited changes above them —
  `.head-isolation` (24,107 `initial` resets) exists to stop inheritance; whether the head subtree is still restyled per layer pass is a trace question (§1).
- 6,144 V leaves: at p < 8 the unfilled 768·(8−p) leaves substitute a 12-byte initial list per restyle (R4W §1) — 12 restyles/token each.
- 587 font-barrier elements (283 witnesses + 283 proofs + 21 reductions): static after load; anchored (`anchor-size`) so they sit in the anchor-evaluation set.
- 144 consumer chunks are nested, so each `.shared-fc-cN` restyle covers the 48-deep chain below it plus the proj stage.

## 4. Ranked levers (measured on combined7; exactness = numerics untouched unless stated)

| # | lever | mechanism measured | predicted saving | exact? | owner |
|---|---|---|---:|---|---|
| T1 | **Take the 768-value ctx hop and/or 2 values per carrier off the fc/proj passes** | fc-stage write 3,141-el. pass 1.3–1.9 s + fc→proj 824-el. pass 1.3 s + attn 0.37 s = 3.0–3.6 s/token = 55 % of style; ≈45 µs per restyled carrier, ≈20 µs per changed animation | 2-per-carrier packing: −1.5…−1.8 s; R5C anchor chains for ctx: −0.4 s + 0.5 frame/layer | yes (packing precision per F4) | R5C |
| T2 | **Replace R4S's score chain + 12·p score-glyph K-list substitution by `1ch` readback** | 163-el. pass 0.95–1.3 s at k≤5 (up to 2.8 s at k=7) + 160–580 interleaved container recalcs/token inside Layout (+65/position; layout slope 0.2–0.5 s/token/position) | −0.5…−1.0 s/token at k=8, slope ×0.5 | yes | R5H |
| T3 | **Per-frame fixed** (39 frames/token: PrePaint 1.78 s flat + untraced paint-lifecycle/animate/UL ≈2.9 s) | 46 ms PrePaint/frame + ≈75 ms/frame other | each frame removed ≈ −0.12 s; 2.0 frames/layer (R5C) → −0.7 s | yes | R5C |
| T4 | Head frame (pass 0.4 s + layout ≈1.3 s + prepaint ≈0.9 s ≈ 2.6 s) | 50,257 rows shaped/laid out per token | only structural (fewer rows / sharded head): not this round | – | – |
| T5 | GC 1.66 s/token (pressure-inflated) — follows M1 | sweeping stalls 25×/run | −0.5 s in a clean-memory session, more with M1 | yes | R5M |
| **M1** | **Cut Oilpan garbage per pass** (3.0 GB committed-free heap; +1.67 GB in token 1, +0.13–0.2 GB/token after) | per-pass `var()` substitution garbage (CSSVariableData / hash tries / calc trees); Oilpan never decommits without OS pressure | up to −2…−3 GB footprint if the allocation rate drops enough for the heap to stay near live (0.92 GB); at least −1 GB | yes | R5M (with R4W's precat approach on the fc/proj/attn carriers, not only V leaves) |
| **M2** | **Decoded webfonts 872 MB resident (malloc)**: 535 MB for 276 stage faces (5.1× woff2), 338 MB head+embedding | `web_cache/Font_resources/*/decoded_webfont`, never evicted (all force-loaded by witnesses) | −300…−500 MB (do not witness-load all 283 faces; per-layer lazy faces; or smaller HVAR tables) | yes | R5M |
| **M3** | **Custom-property tries 468 MB live** (854 k + 469 k trie nodes, 999 k CSSVariableData) across 114 k ComputedStyles | 16,123 inherited registered props; `.head-isolation` 24,107 + `.core-reset` 16,158 `initial` resets create per-element trie paths | −100…−300 MB (fewer inherited props reaching the head/leaf populations; `inherits:false` where possible) | yes | R5E/R5M |
| M4 | Font instance / shape caches ≈0.83 GB malloc (purgeable) | 144·p V instances + score instances + carriers' shape results | −0.3 GB by bounding live instances (R4V §5.4) | yes | R5M |
| E1 | dead-element floor | census: 587 font-barrier elements + 6,144·(8−p)/8 unfilled leaves + 50,257 head rows restyled once/token; no separate inert per-pass population found in the 67 passes/token (they are all live subtrees) | ≤ 0.2 s | yes | R5E |

## 4b. Earlier census-only lever notes

| # | lever | mechanism | predicted | exactness | owner |
|---|---|---|---|---|---|
| M1 | fonts: measure decoded residency of the 239 MB (esp. 78 MB head + 57 MB embedding); lazy-load stage faces per layer instead of force-loading all 283 via witnesses | decoded sfnt + HarfBuzz face + Skia typeface per face | up to hundreds of MB (to be measured) | exact | R5M |
| M2 | 9,231 timelines/animations/keyframes → memory per animation (R3A/M1: 100 k retained = 1.9 GB vs 0.65 GB static ⇒ ≈13 KB each ⇒ ≈120 MB here) | ScrollTimeline + KeyframeEffect + Animation objects | ≈100 MB | exact | R5M |
| E1 | `.head-isolation` 24,107 + `.core-reset` 16,158 `initial` declarations: two elements whose cascade applies 40 k custom properties on every restyle | per-declaration cascade cost | small time, large ComputedStyle (2 × 40 k inherited-variable maps) | exact | R5E |
| E2 | nested R4T chunks → flatten to siblings (each chunk currently wraps the rest of the layer) | restyle scope of a chunk element = its subtree | style time per fc/qkv chunk pass | exact | R5C/R5E |

(sections 1, 2 and the ranked time levers follow when the traces land; `R5A.log.md` has the timeline.)

## 6. What could not be measured

- The traced runs did NOT run: the machine gate (AC + ≥ 3 GB free) held only for one poll (12:16, 3.3 GB); disk then fell to 1.5–1.7 GB while R5H/R5E/R5M
  wrote 40 MB bundles. `R5A/launch_when_ready.sh` (nohup) keeps polling every 60 s and will run `R5A/run_trace8.sh` (two runs under one CHROME.lock: `mem8-N`
  memory-infra-only with light dumps post-load/after every token/detailed at end; `time8-N` R3A light set + blink_gc + fonts + memory-infra, 400 MB ring started
  at Run) as soon as both hold; then run `R5A/postprocess.sh N` (summaries, B0/parse_trace.py, anatomy.py w/ cc-less frame fallback, frame_regress.py,
  parse_memdumps.py → `R5A/run-combined7/parsed-N/`). Delete `R5A/run-combined7/*-trace.json.gz` after parsing (disk rule).
- Hence no measured per-mechanism time table (§1 is the untraced style/layout/other split + `R5A/model.py`'s census × R3A/R4T-constant model, which
  over-predicts 21.3 vs 15.6 s — the element-floor and per-pass-fixed terms are the unresolved ones) and no allocator table (§2); RSS per token is known
  from B5's 1 Hz `ps` (§ census.md §4). Frame counts, changed-carrier counts per pass, GC split, font instantiation counts: all await the trace.
- Disk candidates for the coordinator (not mine to delete): `R2I/` 914 MB, `R2H/` 443 MB, `R2C/hold` 107 MB, `R3A/runs` 103 MB, `R3K/runs` 75 MB (old traces).

- Update 13:0x: `mem8-3` ran (memory-infra + devtools.timeline only, under swap pressure) → §2 and the pass-level §1 are measured; `time8-3` (blink categories: paint lifecycle / animate / UpdateLifecycle self, serviceAnimations counts, fonts events, blink_gc names) was killed at start on the coordinator's disk instruction — those rows in §1 remain model-based (≈2.9 s/token lumped). The dump guid→tag join in `parse_memdumps.py` is off by three (Chrome numbers dumps per process); tables above are labelled by time order, which matches the harness's request times to the second. Trace kept: `R5A/run-combined7/mem8-3-trace.json.gz` (15.4 MB < 150 MB). Re-run `R5A/run_trace8.sh <sfx>` (time8 only) when the gate opens; then `R5A/postprocess.sh <sfx>`.
