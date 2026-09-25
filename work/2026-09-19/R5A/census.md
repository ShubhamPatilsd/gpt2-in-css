# R5A census — `bundles/combined7` (capacity 8, 12 layers), 2026-09-24

Sources: `R5A/census.py` over `index.html` (6,517,186 B) and `runtime.css` (39,979,812 B); font url()s resolved on disk (query strings stripped);
untraced reference numbers from B5's paired runs `bench/runs/combined7/paired5-{1..4}.json`. Raw: `R5A/census.json`, `R5A/census.out`.

## 1. DOM — 67,569 elements (harness `navInfo.elements` agrees: 67,569; `Performance.Nodes` at idle 132,081 incl. text nodes), 66,294 leaves, max depth 164, mean depth 55.6

| subtree / population | elements | where (depth) | notes |
|---|---:|---|---|
| **head** `.full-head` (inside `.head-isolation` → `.head-input-bank` → `.final-normalization`) | **51,138** | 38–43 | 50,257 `.head-row` (`<i>`, inline `--base;--tie`, 6-char text each) + 197 `.head-group` (+197 `.head-score`, 197 `.head-match`) + 256 `.head-fine-row` + 21 `.font-all` + 14 `.head-max` + 14 `.head-choice` + readers |
| **V glyph leaves** `.fvs-v-H-S` | **6,144** | 97 | 768 rows × 8 slots; one U+F5800 glyph each; live per pass: 768·p |
| **V rows** `.metric.fvs-value-row` (`<span>`, view-timeline `--cache-bridge-tN`) | 768 | 96 | ctx hop carriers (they ARE the cache-bridge timelines) |
| **carriers** `.metric` (`<i>`, inline `width:calc(...)`; `view-timeline: --X-tN inline`) | **7,680** | 163 (stage tracks), 7, 39 | shared-fc 3,072 + shared-qkv 2,304 + shared-attn 768 + shared-proj 768 + b11-bridge 768 |
| embedding carriers `.embedding-metric` | 768 (+1 epoch-reader) | 7 | `--embed-tN` |
| **view-timelines total** (inline `view-timeline:` decls) | **9,223** | | + 8 in CSS (feedback, stamps); `timeline-scope` on `html`: 41 decls, 79,923 names, **9,231 distinct** |
| **consumers / R4T chunks** | 144 | 41–157 (nested!) | `.shared-fc-cN` 48, `.shared-qkv-cN` 36, `.shared-attn-cN` 12, `.cache-bridge-cN` 12, `.b11-bridge-cN` 12, `.loop-reader-cN` 12, `.embedding-consumer-N` 12; each carries 64 animations (48×64 = 3,072 fc …) → **≈9,216 live carrier animations** (+8 feedback +7 stamps) |
| score glyphs `.fvs-score-H-S` | 96 | ~140 | 12 heads × 8 slots (`FvsDotH`, `var(--fr-k-S),var(--fvs-query-H)` ≈ 12.7 KB packed K list each) |
| R4S score chain `.fvs-sc` / `#fvs-scN` | 48 elements / 95 rules | 92 | anchor→size-container chain (`width:anchor-size(--fsa-N-N width)`) |
| KV banks `.fvs-bank.fvs-bank-L` | 12 (nested wrappers) | 80–91 | 172 `transition-*` decls in CSS; 8 write rules with ≈100-property `transition-property` lists |
| controller / handshake | ≈120 | 1–38 | `.core-controller`, `.core-pass-reader`, `.loop-reader`, `.loop-input`, `.reused-input`, `.core-valid`, 8 `.token-slot-N`, 8 `.feedback-metric`, 4 `<svg>` (38 `<g>`, 19 `<set>`), receipts/gates 4×12 (`content-visibility:hidden` gates), 3 `.readback` (inline styles 50 KB: `#block-11-probe` has a 768-term anchor width) |
| font barrier (static) | 587 | 2 | 283 `.font-witness` + 283 `.font-proof-N` + 21 `.font-all-N-N` (anchor-size chain → `fontready` container) |
| controls / output | ≈20 | 1–2 | `<select>` 6 options, `#run`, `<output>` ×3 |

Inline style text: **1,854,714 B** — `.head-row` 1,235,157 (24.6 B each), `.metric` 395,164 (51 B), `.fvs-value-row` 121,490 (158 B), `.readback` 50,532, `.embedding-metric` 25,234.
Depth histogram peaks: 51,028 elements at depth 40 (head rows), 2,307 at 43, 771 at 96 (V rows), 7 (embedding metrics 771), 599 at depth 2 (font barrier).
The layer chain is a single nested spine: `.shared-qkv`(40) → 36 nested `.shared-qkv-cN` (41–76) → receipt/gate (77–78) → `.fvs-query` (79) → 12 nested banks (80–91) → `.fvs-sc` (92) → … → `.shared-attn` (93) → 12 nested `.shared-attn-cN` → `.shared-fc` (109) → **48 nested `.shared-fc-cN` (110–157)** → `.shared-proj` (160) → scroller/track (161–162) → 3,072 metrics (163). R4T's chunk wrappers are nested, not siblings: every chunk element's subtree contains all later chunks and the whole downstream stage.

## 2. CSS — 71,939 rules, 39.07 M chars

| feature | count | detail |
|---|---:|---|
| `@property` | **39,513** | `inherits:true` 16,123 / `false` 23,390; syntax `<number>` 39,303, `*` 209, `<length>` 1. Biggest families: `--hidden-N`, `--fcp-N`, `--fq-proj-N`, `--fz-N`, `--ft-N` 3,072 each; `--qkv-N`, `--qkvp-N` 2,304; `--nN-N` 1,536; 30 families × 768 |
| `@keyframes` | **9,232** | `fckN` 3,072, `qkvkN` 2,304, `bridgekN`/`attnkN`/`projkN`/`lpkN`/`embedkN` 768 each, 16 misc — one 2-stop keyframes per carrier value |
| animation names declared | 76,809 (in 1,279 `animation-name`/`animation` decls) | per-layer `@container corestate style(--layer:L)` variants ×12 for fc/qkv/attn; **live ≈ 9,231** (one per timeline) |
| `view-timeline` | 8 in CSS + 9,223 inline | `timeline-scope` 41 decls / 79,923 names / 9,231 distinct |
| `anchor-name` / `anchor-size()` | 728 css + 582 inline / **3,213** | head reduction tree (197 scores → max/choice), R4S chain, font barrier, readback probes |
| `@container` rules | 675 | `corestate style(--layer:N)` 265, `fvscache style(--fvs-write-slot:N)` 200, `loopcontrol style(--pass:N)` 96, `runtime style(--epoch:N)` 24, gates 48, `fvscache style(--fvq-N:N)` 8, `headstate` 24 … ; `container-type` 4 |
| `transition*` decls | 172 | banks (8 write rules ≈100 props each), `.token-slot-N` 8, feedback |
| `var(` occurrences | **701,072** | `:has(` 85, `content-visibility` 108, `calc-size` 99, `font-variation-settings` 247, `@function` 1 |
| `@font-face` | 283 | 252 with `unicode-range` |

Rule families by bytes (normalised selector; rules; declarations; bytes; `var()`):

| family | rules | decls | MB | var() | what |
|---|---:|---:|---:|---:|---|
| `@container corestate style(--layer:L) >> .shared-fc-cN` | 576 | 114,048 | **13.09** | 258,048 | fc consumer chunks: 64 `animation-name` + 64 decode decls per chunk per layer (`--fcp-N` → `--fz-N`/`--ft-N`) |
| `… >> .shared-qkv-cN` | 432 | 30,240 | 4.16 | 55,296 | qkv consumer chunks |
| `.head-fine-row:nth-child(N)` | 256 | 101,632 | 3.89 | 0 | 15 KB each: `--fine-base: if(style(--head-group-index:0):…;×197)` |
| `… >> .shared-lnN` | 24 | 18,480 | 3.32 | 147,456 | LN1/LN2 per layer: 768-term sums, 138 KB per rule |
| `… >> .shared-proj` | 60 | 18,504 | 3.14 | 101,376 | proj range/decodes per layer |
| `… >> .shared-attn-cN` | 144 | 10,080 | 1.58 | 27,648 | attn consumer chunks |
| `… >> .shared-fc` / `.shared-qkv` / `.shared-attn` | 48 / 48 / 48 | 84 each | 1.05 / 0.92 / 0.60 | 18,432 each | `--range-*: max(abs(…×768))` + font-family per layer |
| `@container fvscache … >> .fvs-bank-N` | 192 | 19,632 | 0.74 | 20,592 | bank write rules |
| `.head-isolation` | 1 | **24,107** | 0.46 | 0 | `--attnp-N:initial …` resets (one element, 24 k declarations) |
| `.core-reset` | 1 | 16,158 | 0.31 | 0 | `--n1-N:initial …` resets |
| `.fvs-query` | 96 | 2,396 | 0.25 | 9,227 | |
| `.position-embedding` | 1 | 6,914 | 0.24 | 768 | 8-branch `if(style(--epoch:k))` per value |
| `.shared-proj` (base) / `.final-normalization` / `.head-input-bank` | 1 / 1 / 2 | 3,072 / 770 / 776 | 0.18 / 0.16 / 0.07 | | |
| `@keyframes` bodies (from/to) | 18,464 | 18,464 | 0.27 | 0 | |
| everything else (≈150 families) | | | ≈0.9 | | |

## 3. Fonts — 283 faces, **239.1 MB woff2 on disk**, 283 distinct family names (one per face), 0 missing

| family group | faces | MB on disk | used by | unicode-range |
|---|---:|---:|---|---|
| `EmbeddingLookup` | 1 | 56.85 | `.embedding-source` (`font:Npx EmbeddingLookup`) | no |
| head `ProdQ16R{0,1,2}` / `ProdQ16H{0,1,2}` | 3 + 3 | 49.15 + 29.26 = **78.41** | `.full-head`, `.head-fine` (`font: 62.5px ProdQ16H0,ProdQ16R0,…`) → 50,257 + 256 rows | no |
| stage weights `b{L}projS{s}` | 144 | 34.63 | `.shared-proj` per layer (12-family list) | yes |
| `b{L}fcS{s}` | 36 | 34.50 | `.shared-fc` per layer (3-family list) | yes |
| `b{L}qkvS{s}` | 36 | 25.81 | `.shared-qkv` | yes |
| `b{L}attnS{s}` | 36 | 8.84 | `.shared-attn` | yes |
| `FvsValue{H}` / `FvsDot{H}` | 12 + 12 | 0.035 + 0.029 | 6,144 V leaves / 96 score glyphs (F4 operator fonts, HVAR) | no |

Directories: `experiments/gpt2-global-q16-layernorm-integer-full` 78.4 MB, `experiments/browser-gpt2/embedding` 56.9 MB, `F2/global-projection-assets` 34.6 MB,
`experiments/hybrid-12block-profile/fonts` 34.6 MB, `experiments/gpt2-flat-12block-chain/layer01…11` 11 × 2.87 MB, `experiments/gpt2-block-css` 2.85 MB, `F4/assets` 64 KB.
All 283 faces are force-loaded at start by the 283 `.font-witness` elements (fonts-loaded gate), so `unicode-range` defers nothing here.
Harness `navInfo` at load: 249 font resource entries, `document.fonts.size` 283, `resourceBytes` 143–206 MB (decodedBodySize sum, unreliable between runs).

## 4. Untraced reference (B5 paired runs of this exact bundle, keyboard trigger, heap flag on, load 3.6–3.9)

| run | s/token 1…8 | total | RSS MB: load end → tok1 → tok2 → … → tok8 |
|---|---|---:|---|
| paired5-1 | 17.1 13.2 13.9 14.3 14.7 15.2 16.1 15.5 | 120.0 | 1,673 → 3,701 → 4,653 → 4,657 → 5,267 → 5,704 → 5,931 → 5,888 → 5,954 |
| paired5-2 | 18.6 14.4 15.0 15.4 15.8 16.4 16.8 16.8 | 129.2 | 1,689 → 3,669 → 4,557 → 5,189 → 5,382 → 5,425 → 5,580 → 5,642 → 5,951 |
| paired5-3 | 19.0 14.4 15.1 15.3 15.7 16.1 16.9 17.2 | 129.7 | 1,857 → 3,890 → 4,608 → 4,865 → 4,971 → 5,134 → 5,483 → 5,776 → 5,595 |
| paired5-4 | 19.0 14.3 15.0 15.4 15.8 16.3 17.1 17.3 | 130.2 | 1,843 → 3,487 → 4,565 → 4,871 → 4,906 → 5,235 → 5,479 → 5,627 → 5,718 |

Per run: RecalcStyleCount +3,486 (436/token), LayoutCount +512 (64/token), JS heap 0.7 MB, browser process ≤ 220 MB, GPU ≤ 145 MB.
Shape: token 1 costs +3–4 s (first instantiation of everything) and **+2.0 GB RSS**; tokens 2–8 climb 13.2 → 16–17 s (≈ +0.5 s/token) while RSS climbs
≈ +300 MB/token (4.6 → 5.95 GB) with no release. The renderer's 6 GB is therefore: ≈1.7 GB after load (decoded fonts + DOM + 40 MB CSS parsed), ≈2 GB
allocated during token 1, ≈2.3 GB accumulated over tokens 2–8 (garbage that is not collected, or retained per-token state) — the memory-infra dumps
(`R5A/run-combined7/mem8-*`) split these by allocator.

## 5. Restyle-root lookup (subtree size incl. root, depth) — to translate `UpdateLayoutTree elementCount` values into subtrees

| root (normalised class) | elements in subtree | depth |
|---|---:|---:|
| `<body>` | 67,563 | 1 |
| `feedback-reader` | 66,872 | 2 |
| `embedding-source` | 66,869 | 4 |
| `embedding-consumer-N` | 66,097 | 5 |
| `position-embedding` | 66,082 | 19 |
| `bN-bridge-cN` | 51,160 | 20 |
| `final-normalization` | 51,143 | 35 |
| `head-isolation` | 51,140 | 37 |
| `full-head` | 51,139 | 38 |
| `head-fine` | 257 | 41 |
| `core-controller` | 14,920 | 21 |
| `core-block` | 14,919 | 22 |
| `loop-reader` | 14,918 | 23 |
| `loop-reader-cN` | 14,917 | 24 |
| `loop-input` | 14,905 | 36 |
| `loop-compute` | 14,129 | 37 |
| `shared-qkv` | 14,126 | 40 |
| `shared-qkv-cN` | 11,818 | 41 |
| `shared-qkv-receipt` | 11,782 | 77 |
| `fvs-query` | 7,075 | 79 |
| `fvs-bank fvs-bank-N` | 7,074 | 80 |
| `fvs-sc` | 6,965 | 92 |
| `fvs-score-reader` | 6,917 | 140 |
| `fvs-softmax` | 6,916 | 141 |
| `scroller cache-bridge-source` | 6,915 | 142 |
| `cache-bridge-cN` | 4,705 | 79 |
| `shared-attn` | 4,691 | 93 |
| `shared-attn-cN` | 3,919 | 94 |
| `shared-fc` | 3,904 | 109 |
| `shared-fc-cN` | 828 | 110 |
| `shared-proj` | 778 | 160 |
| `reused-final-export` | 774 | 37 |
| `scroller bN-bridge-source` | 771 | 38 |
| `embedding-scroller` | 771 | 5 |
| `head-coarse-reader` | 262 | 39 |
| `shared-lnN` | 18,031 | 108 |

Note: the whole document = 67,569; body 67,563; `.feedback-reader` 66,872 (everything below the prompt/feedback select); `.core-block` 14,919 = the 12-layer core (one
physical layer, re-used); `.full-head` 51,139; `.shared-fc` 3,904 = 3,072 fc carriers + the 48-deep chunk chain (828) incl. `.shared-proj` (778 = 768 proj carriers + wrappers);
`.fvs-softmax` 6,916 = 768 V rows × (1 + 8 leaves) + 4. Elementcounts seen in R4V's c32c trace (25,351 / 3,089 / 2,324 / 984 / 782 / 780 / 414) will differ here (cap 8, R4S chain, R4T chunks).
