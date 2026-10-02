# I1 — "How it actually works": the data path of one token through demo-c32

Agent I1, 2026-10-02. Read-only. Process log: `audit/2026-10-02/I1-how-it-works-datapath.log.md`.
Subject: the live bundle `work/2026-09-19/bundles/demo-c32/` (index.html 7,445,896 B, runtime.css 53,627,357 B, 286 font faces / 250.7 MB),
built by `work/2026-09-19/R7X/compile.sh` (flags: `--reuse-core --cache-codec font-vector --value-layout widths --font-backend original`,
F4 packed banks, R3R fold hop, R5H `1ch` scores, R7B sampling).

**Citation conventions.** `runtime.css` is a single 53.6 MB line, so CSS citations are `runtime.css@<byte offset>` (from `grep -boF`).
Python citations are `file:line` under `work/2026-09-19/R7X/tools/` (abbreviated `tools/`). Things not read directly in code are marked **(inferred)**.

---

## 0. The one idea you need first

Browsers will do a lot of arithmetic for you, but only in three places that a page can feed numbers into and read numbers out of:

1. **CSS math** (`calc()`, `exp()`, `pow()`, `sqrt()`, `max()`, `round()`, `if(style(...))`) on **registered custom properties** (`@property --x{syntax:"<number>"}`).
   Good for element-wise work (LayerNorm, softmax, GELU, residual adds). Bad for big sums: a 768×2304 matrix as `calc()` text would be gigabytes.
2. **Font shaping.** A variable font's glyph advance (width) is `default + Σ deltas × region-scalars`, where the scalars come from axis values you set with
   `font-variation-settings`. That is a dot product computed by HarfBuzz/Skia in native code. **This is where all the matrix multiplies happen.**
3. **Layout geometry.** Widths of boxes can be read back into CSS numbers through **scroll-driven animations** (`view-timeline`: a box's width changes how
   far through its timeline it is, and an animation on that timeline writes a `<number>`), through **anchor positioning** (`anchor-size()`), through
   **container query units** (`100cqi`), and through the `ch` unit. Layout also gives you a free **max()**: a `max-content` box is as wide as its widest child.

Also important: CSS custom properties only flow **down** the DOM (inheritance). Anything that must flow **up** or **sideways** (the layer output back to the top
of the loop, the chosen token back to the embedding) goes through geometry, because `timeline-scope` / anchors let any element read any other box's size.

So every stage of GPT-2 is: *numbers in CSS → axis values on a font → glyph widths → layout → read widths back as numbers → CSS math → next stage*.

---

## 1. Token id → embedding (the 56.9 MB font)

**Plain English.** The token-embedding table (50,257 rows × 768 numbers) is stored as a single variable font with **768 glyphs** (one per embedding
dimension) and **two axes**, `GRUP` (token id ÷ 256) and `LOCL` (token id mod 256). Setting those two axes to a token's coordinates "dials in" that token:
every glyph's advance width becomes `20000 + round(4096 × wte[token][i])` font units. The page lays the 768 glyphs out as 768 invisible `<i>` elements and
reads each width back with a view timeline.

**How the font encodes it** (`tools/build_hvar_token_embedding_lookup.py`):
- 197 × 256 grid of tokens; each token gets its own OpenType **variation region** (a 2-D "tent" peaked at its (group, local) coordinate, half-width 0.45 of a
  step so neighbours never overlap) — `:46-51`, `:80-87`. Axis minimum/default is −1 so that token 0 is not at the "neutral" zero coordinate (`:36-41`).
- HVAR deltas: `deltas = np.rint(embeddings.T * EMBEDDING_SCALE).astype(np.int16)` with `EMBEDDING_SCALE = 4096`, base advance `20000` — `:24-27`, `:88`.
  That is 768 × 50,257 ≈ 38.6 M int16 deltas: the .ttf is 100 MB, the woff2 56,853,724 B. Glyphs are empty (no outlines); only `hmtx`+`HVAR` matter
  (`build_matrix_backend_prototypes.py:65-110`, UPM 1000 at `:27`).

**In the page** (emitter `tools/browser_gpt2_embedding.py:38-89`):

```css
/* runtime.css@45851466 and preceding hoist rule */
.embedding-source{--fq-token-group:round(down,calc(var(--token) / 256),1);--fq-token-local:mod(var(--token),256)}
.embedding-source{font:1000px EmbeddingLookup;font-kerning:none;
  font-variation-settings:"GRUP" var(--fq-token-group),"LOCL" var(--fq-token-local); timeline-scope:--embed-t0,…}
.embedding-scroller{position:fixed;left:0;top:-50000px;width:65536px;height:1px;overflow-x:scroll;…}
/* runtime.css@45929477 — one of 768 decoders on .embedding-consumer-* */
--embed-000:calc((65536 / var(--embedp-000) - 65536 - 20000) / 4096)
```
```html
<!-- index.html: 768 of these, one glyph each (U+E000 + i) -->
<i class="embedding-metric" style="view-timeline:--embed-t0 inline">&#xE000;</i>
```

At `font-size:1000px` with UPM 1000, one font unit = 1 px, so the box is `20000 + 4096·e` px wide. A box of width `w` at the start of a `V = 65536` px
scroller sits `p = V/(V+w)` of the way through its `view-timeline` (inferred from the decode formula; it is the standard "cover" range), and the keyframe
`embedk_i` animates `--embedp-i` from 0→1, so `w = 65536/p − 65536` and `e = (w − 20000)/4096`.

**Position embedding** is not a font: one rule adds a 36-way `if(style(--epoch:N): wpe[N-1][i])` constant per dimension (`tools/browser_gpt2_runtime.py:444-450`):
```css
/* runtime.css@51827422 */
.position-embedding{--x-000:calc(var(--embed-000) + if(style(--epoch:1):-0.0188207197934;style(--epoch:2):0.0239594336599;…
```

**Where `--token` comes from.** For prompt tokens: the typed prompt is tokenized by two OpenType fonts that *are* GPT-2's BPE (cmap = byte tokens,
`rlig` = the full merge table in rank order, a position feature erases all but the k-th token; the token id leaks out as an advance width read via
`anchor-size()` and `100cqi`) — R6P.md §2 (`work/2026-09-19/R6P.md:38-54`). For generated tokens: the feedback path in §5.

---

## 2. How a vector lives in CSS between operations

- **As 768 (or 2,304 / 3,072) registered `<number>` custom properties**, e.g. `--x-000…--x-767`, `--n1-*`, `--qkv-*` (2,304), `--ctx-*`, `--r-*`,
  `--hidden-*` (3,072). Registration (`@property … syntax:"<number>"`) is what makes them real doubles that `calc()` can do math on; the bundle has
  42,875 `@property` rules. They are declared on wrapper elements that are **ancestors** of everything downstream, so the next stage just inherits them
  (C2 §2, `audit/2026-09-18/C2-demo-cost-model.md:111`).
- **As a font-axis list** when it is about to be multiplied: `font-variation-settings:"A000" var(--fq-qkv-000),"A001" …` — each value pre-divided by the
  vector's max-abs (`--range-*`) so it lies in [−1, 1]. Fonts store axis positions as **F2Dot14** (1/16,384 steps), so this is where activations get
  quantized (R3P.md:22, :111).
- **As box widths** in transit (the "carriers"): `262144px + 128px × value` for the loop/context/feedback encodings, or raw glyph-advance sums for matvec
  outputs. There are 9,223 `view-timeline` carriers in index.html.
- **As `*`-typed string lists** for the KV cache (§4.3): a whole 768-entry `"K000" -0.515166,"K001" …` list is one custom-property value.
- **The layer index is also CSS state:** one graph is reused 12×, and every layer's weights/constants sit inside `@container corestate style(--layer:L){…}`
  blocks (e.g. layer 0 LN1 at `runtime.css@1666594`, layer 1 at `@4793690`). Changing `--layer` swaps which fonts and constants match.

---

## 3. Matrix–vector multiply as a font

**Plain English.** For a weight matrix `W` (out × in), each **output row** is one **glyph**, each **input element** is one **font axis**, and each weight is
an **HVAR delta**. Set the axes to the input vector, and each glyph's advance width *is* that row's dot product (plus a constant). Put the glyph in an
invisible `<i>`; its width is the answer; read it back with a view timeline.

**Font construction** (`tools/build_matrix_backend_prototypes.py:178-275`, called from `tools/build_gpt2_block_css.py:133-188`):
- Weights are quantized per output row to **9-bit signed integers**: `scale_i = max|W_i|/255`, `c_ij = rint(W_ij/scale_i)`
  (`tools/build_signed_hvar_chain.py:46-54`; `QUANT_BITS = 9` at `build_gpt2_block_css.py:45`; `bits=9` at `browser_gpt2_core.py:202`).
- At most **256 axes per font** (the tested Chrome limit, `build_matrix_backend_prototypes.py:193-194`), so 768 inputs = 3 "shard" fonts
  (tags `A000–A255`, `B…`, `C…`), and the 3,072-input MLP down-projection = 12 shard fonts (global tags `X000…`).
- Signed axes in [−1, 1]: each axis gets two one-sided regions, `(−1,−1,0)` with delta `−c` and `(0,1,1)` with delta `+c`, so the contribution is
  exactly `c·x` on both sides of zero (`:242-250`). Glyph default advance = `Σ|c_ij| + 32` so the width never goes negative (`build_gpt2_block_css.py:151-153`).

**The arithmetic identity** (one output row i, input x, per-vector range R = max|x|·1.001, font size FS = 512 px, UPM = 1000):

```
width_i [px] = (FS/UPM) · ( B_i + Σ_j c_ij · x_j / R )            ← HarfBuzz/Skia (HVAR)
y_i          = b_i + s_i · R · ( width_i · UPM/FS − B_i )          ← CSS calc()
             = b_i + Σ_j (s_i·c_ij) · x_j   ≈   b_i + Σ_j W_ij · x_j
```
(`B_i` = summed row bases of the shards, `s_i` = row scale, `b_i` = bias.)

**In the page** (emitter `tools/build_hybrid_twelve_block.py:108-296`):
```css
/* runtime.css@1958563 — the input vector becomes 768 axis values on the stage wrapper (layer 0) */
.shared-qkv{font-family:b0qkvS0,b0qkvS1,b0qkvS2;
  font-variation-settings:"A000" var(--fq-qkv-000),"A001" var(--fq-qkv-001),…}
.shared-qkv{--fq-qkv-000:calc(var(--n1-000) / var(--range-qkv));…}
.shared-qkv{--range-qkv:calc(max(.000001,abs(var(--n1-000)),abs(var(--n1-001)),…)}   /* @1901079 */
/* runtime.css@2317339 — decode of output 0 from its carrier's timeline progress */
--qkv-000:calc(((65536 / var(--qkvp-000) - 65536) * 1000 / 512 - 41929) * .003635605 * var(--range-qkv) + (.48033914))
```
```html
<!-- index.html: one carrier per output row; 3 codepoints = row 0 in shard fonts S0/S1/S2 (unicode-range routes each to its font) -->
<i class="metric" style="view-timeline:--shared-qkv-t0 inline">&#xF0000;&#xF0900;&#xF1200;</i>
```
The three shard glyphs sit in one inline run, so the box width is the **sum** over all 768 inputs — layout does the final addition.

**Per layer:** qkv 768→2,304 (3 fonts, 2,304 carriers), attn-out 768→768 (3 fonts, 768), fc 768→3,072 (3 fonts, 3,072), proj 3,072→768 (12 fonts, 768).
21 fonts × 12 layers = **252 weight fonts, 103.8 MB**, ≈ 85 M weights. Readback is a view-timeline per carrier, consumed by `animation-name` lists on
chunked consumer elements (`.shared-qkv-c0…`, runtime.css@2315672; 64 animations per chunk, R4T).

**Variant: `calc-size()` folds the affine decode into layout.** For the proj stage (R3R) the carrier width is set so the *box itself* already equals the
residual-stream encoding `262144 + 128·(r_i + proj_i)` px, using `calc-size(max-content, … + size * k)` (`size` = the shaped glyph width):
```css
/* index.html carrier + runtime.css@4686871 constants (layer 0) — tools/r3r_fold_hop.py:15-21, 81-95 */
width:calc-size(max-content,262144px + var(--pc-000) * 1px + size * var(--pk-000))
--pk-000:calc(var(--range-proj) * .577904781);--pc-000:calc((var(--r-000) + (.04502327) - 94243 * .002311619 * var(--range-proj)) * 128)
```

---

## 4. The other operations

| Op | Primitive | Where |
|---|---|---|
| LayerNorm (ln_1, ln_2, ln_f) | Pure CSS math: 768-term `calc()` sum for mean, 768-term sum of squares for variance, `sqrt()`, then `(x−μ)/σ·γ+β` per element with γ,β inlined | `tools/build_gpt2_block_css.py:230-258`; runtime.css@1727355 |
| QKV, attn-out, fc, proj | Variable-font HVAR matvec + view-timeline readback (§3) | §3 |
| Q·K scores | **Bilinear** variable font: one glyph whose advance is `base + c·Σ q_i·k_i`; read with the `ch` unit | §4.1 |
| softmax | CSS math: `max()`, `exp()`, sum, divide, masked by `if(style(--fv-S:1))` | runtime.css@44907522 |
| weighted V sum | Value-font glyph widths scaled by softmax weight via `calc-size()`, summed by an `inline-flex` row, read by view-timeline | §4.2 |
| KV cache | `*`-typed custom-property lists held by 24-hour-delayed CSS **transitions** | §4.3 |
| GELU | CSS math: tanh-approx GELU with `exp()`/`pow()`/`clamp()` | runtime.css@3996810 |
| residual adds | CSS `calc(var(--x-i) + …)` in the decoder (attn), or folded into the carrier width (proj, R3R) | runtime.css@2596703; §3 |
| layer loop back to the top | proj carrier widths → `.loop-reader` view-timelines → `--loop-in-i` | runtime.css@45297543 |

```css
/* LayerNorm, layer 0, dimension 0 — runtime.css@1727355 */
--n1-000:calc((var(--x-000) - var(--mean1)) / sqrt(var(--var1) + 1e-05) * .223220333 + (-.003677325))
/* GELU (tanh form; tanh(t) = (e^2t − 1)/(e^2t + 1)) — runtime.css@3996810, @3996927, @3997025 */
--fz-000:calc(((65536 / var(--fcp-000) - 65536) * 1000 / 512 - 25588) * .001864073 * var(--range-fc) + (.039619479))
--ft-000:clamp(-20,calc(.7978845608028654 * (var(--fz-000) + .044715 * pow(var(--fz-000),3))),20)
--hidden-000:calc(.5 * var(--fz-000) * (1 + (exp(2 * var(--ft-000)) - 1) / (exp(2 * var(--ft-000)) + 1)))
/* attention residual folded into the attn-out decoder — runtime.css@2596703 */
--r-000:calc(var(--x-000) + calc(((65536 / var(--attnp-000) - 65536) * 1000 / 512 - 41216) * .004069718 * var(--range-attn) + (.150291592)))
```
Note on "@function math": the sheet contains exactly one `@function` (`--gelu`, runtime.css@1661685) and **zero call sites** — the emitter
inlines GELU instead (`INLINE_GELU = True`, `tools/build_hybrid_twelve_block.py:35`, `:271-277`). So `@function` is present but not on the data path.

### 4.1 Attention scores: a font that multiplies two vectors

`tools/build_bilinear_projected_kv_qk.py:47-166` builds a font with 128 axes (`Q000–Q063`, `K000–K063`) and one glyph. For each i there are four
**two-axis** regions (Q−K−, Q−K+, Q+K−, Q+K+) with deltas `+c, −c, −c, +c`. An OpenType region's scalar is the *product* of its per-axis scalars, so each
region contributes `c·q_i·k_i`; the glyph advance is `29984 + 468·Σ_i q̂_i·k̂_i` (constants in
`experiments/browser-gpt2/font-vector-operators-v2/operators.json`). F4 re-tags the K axes per head (`K000–K2FF`) so one 768-entry K list can be stored per
slot (`work/2026-09-19/F4.md` §2.2). R5H maps U+0030 ("0") to the dot glyph so the advance can be read with the **`ch` unit** — no layout readback at all
(`work/2026-09-19/R5H.md` §0; `tools/r5h_ch_scores.py:19, 128`):

```css
/* runtime.css@44770607 — head 0, cache slot 0. 15351.808 = 29984·512/1000; 0.000521668 = 1/(468·0.512·8)  (÷8 = ÷√64) */
.fvs-score-0-0{display:block;font:512px FvsDot0;line-height:1;font-kerning:none;
  font-variation-settings:var(--fr-k-0),var(--fvs-query-0);
  --fs-0-0:calc((1ch / 1px - 15351.808) * var(--fqs-0) * var(--fr-ks-0-0) * 0.000521668002137)}
```
`--fqs-H` / `--fr-ks-S-H` are the per-head max-abs scales that normalised q and k into [−1, 1]; multiplying them back gives `q·k/√64` exactly as GPT-2.

Softmax (`tools/browser_gpt2_font_vector_cache.py:461-479`), per head, over the filled cache slots only (`--fv-S` = 1 if slot S ≤ current position, runtime.css@44905741):
```css
/* runtime.css@44907522, @44909324, @45007655 */
.fvs-sr-0{--fm-0:max(if(style(--fv-0:1):var(--fs-0-0);else:-1000000),if(style(--fv-1:1):var(--fs-0-1);else:-1000000),…)
--fe-0-0:if(style(--fv-0:1):exp(calc(var(--fs-0-0) - var(--fm-0)));else:0) …
--fw-0-0:calc(var(--fe-0-0) * var(--fr-vs-0-0) / var(--fb-0))      /* unnormalised weight × V scale / max V scale */
```

### 4.2 Weighted sum of V: widths × weights, summed by flexbox

The value font (`FvsValueH`) has 64 glyphs; glyph d's advance is `12032 + 12000·v̂_d` for the slot's (normalised) V vector set on 64 axes (operators.json;
`P000` collapse at `browser_gpt2_font_vector_cache.py:52-85`). In the `widths` layout the font location is fixed and the **softmax weight scales the shaped
width** via `calc-size()` (`:554-560`). For each output coordinate d of each head, an `inline-flex` row holds one such glyph per cache slot (36), so the row's
width is `Σ_slots w_s·v_{s,d}` plus constants; it is read back by a view timeline exactly like a matvec carrier. 768 rows × 36 slots = **27,648 V glyphs**.
```css
/* runtime.css@45035775, @45119079 — 12320.768 = 12032·1.024 px (font 1024 px) */
.fvs-v-0-0{font-family:FvsValue0;font-variation-settings:var(--fr-v-0-0),"P000" 1;
  width:calc-size(max-content,calc(12320.768px + (size - 12320.768px) * var(--fw-0-0)));min-width:0;flex:none}
.fvs-value-row{display:inline-flex;gap:0;font:1024px FvsValue0;line-height:1;font-kerning:none;white-space:pre}
```
```html
<!-- index.html: 0.0104166… = 128/12288; result width = 262144 + 128·ctx_d -->
<span class="metric fvs-value-row" style="width:calc-size(max-content,calc(262144px + (size - var(--fvs-nbase)) * var(--fb-0) / var(--fd-0) * 0.0104166666667));view-timeline:--cache-bridge-t0 inline">
  <i class="fvs-v-0-0">&#xF5800;</i><i class="fvs-v-0-1">…</i>…</span>
```
Decoded by `--ctx-000:calc((1572864 / (var(--bridge-p-000) + 2) - 524288 - 262144) / 128)` (runtime.css@30922830; the "centred" encoding: keyframes −2→1,
524,288 px viewport, `tools/r3r_fold_hop.py:61-67`).

### 4.3 KV cache: values parked in a transition that never finishes

Each layer has a bank element `.fvs-bank-L`; for each cache slot S it stores `--fc-k-S` (one 768-entry K list, all 12 heads), 12 × `--fc-v-S-H`
(64-entry V lists), and 24 per-head scales — registered with `syntax:"*"` / `<number>`, `inherits:false` (F4.md §2.2; `browser_gpt2_font_vector_cache.py:89-113`).
- **Write:** while `@container fvscache style(--fvs-write-slot:S)` matches (and the layer matches), the slot's fields are set to the *live* lists computed
  from the current token's qkv output (runtime.css@31839945).
- **Hold:** the bank's base rule lists every field in `transition-property` with `transition-delay:86400s` (24 h) and `steps(1,end)`. When the write rule
  stops matching, the declared value falls back to the initial value, but the transition to it sits in its delay phase forever, so the **old value is what
  computes** — the transition *is* the memory (C2 §4, `audit/2026-09-18/C2-demo-cost-model.md:190`).
- **Read:** alias rules publish `--fr-k-S:var(--fc-k-S)` (inheriting) to the score/V glyphs below.
```css
/* runtime.css@31117905, @30927822, @31455254, @31458977 */
.fvs-bank{transition-property:…,--fc-vs-35-11;transition-duration:1ms;transition-delay:86400s;
  transition-timing-function:steps(1,end);transition-behavior:allow-discrete}
@property --fc-k-0{syntax:"*";inherits:false;initial-value:"K000" 0}
--fvs-live-k-0:"K000" var(--fvn-k-0-0),"K001" var(--fvn-k-0-1),…          /* head 0's 64 K coords, head-tagged */
--fvn-k-0-0:calc(var(--qkv-768) / var(--fvs-live-ks-0))                    /* k / max|k_head| */
--fvs-live-ks-0:max(.000001,abs(var(--qkv-768)),abs(var(--qkv-769)),…)
```
Capacity 36 slots × 12 layers. Because the stored list is fed straight into `font-variation-settings`, CSS never unpacks the 64 numbers — the font consumes
the list directly (docstring, `browser_gpt2_font_vector_cache.py:1-6`).

---

## 5. Output head, sampling, and back to text

**Final LayerNorm** in CSS (runtime.css@51614088), then each of the 768 values is **rounded to an integer axis step**:
`--hq-i = round(nearest, h_i / 266.248 × 16384, 1)` and packed into one 768-axis list `--head-fvs` that is latched by a transition
(`tools/f4_packing.py:136-170`; runtime.css@51756417, @51810835).

**Scoring all 50,257 rows.** The tied embedding matrix is re-quantized to **16 bits** (`WEIGHT_SCALE = 5.448e-5`,
`tools/build_gpt2_groupwise_production_q16_sixfont.py:32-37`) and split into **six fonts**: 3 shards (256 axes each) × 2 byte-planes, a "high" plane
declared with `size-adjust:25600%` (×256) and a "residual" plane (`:242-252`). Each vocabulary row is an `<i class="head-row">` containing 6 glyphs (plus a
7th noise glyph, below); its shaped width is therefore `256·hi + lo` = the q16 dot product with the hidden state (the radix-256 reading is **(inferred)**
from the `radix: 256`, `glyphsPerRow: 6` contract at `:101-106` and the size-adjust). Each row's width is converted to an integer bucket:
```css
/* runtime.css@45995623 (+ later override) — 120.777… = score gain; 211968px = positive floor; 4px buckets */
.head-row{…;width:calc-size(max-content,round(nearest,(size - var(--base)*1px)*120.777609693 + 211968px,4px))}
```
```html
<section class="head-group" style="anchor-name:--head-group-0">
  <i class="head-row" data-token="0" style="--base:3200.5625;--tie:255">𠀀𰀀񀀀񐀀񠀀񰀀򀀀</i> … 256 rows per group, 197 groups
```
**Argmax via layout:** each of the 197 groups is a `max-content` block whose rows are zero-height, so the group's width = **max** of its 256 row widths
(`tools/r3h_blockflow_max.py:1-27`). The 197 group maxima are reduced by a tree of `anchor-size()`-driven `max()` boxes, fan-in 16
(`tools/browser_gpt2_head.py:56-74`); the winning group is located by "match" boxes, and a second, 256-row **fine pass** finds the winner inside the group
using a rank-weighted width, read through container-query units (`:179-221`):
```css
.head-result{--winner:calc(var(--head-group-index)*256 + 256 - round(nearest,100cqi/1px,1)); …}
```

**Sampling = Gumbel-max inside the same argmax.** A 7th font `NoiseQ` (8.3 MB) has one glyph per vocabulary row (U+80000+id) whose advance carries a
precomputed Gumbel sample `n = rint(clip(G,−3,12) × 0.508 × 256)` for one of 64 seed columns, selected by axis `SEED` (64 tents) and scaled by axis `TEMP`
(`tools/build_noise_font_r7b.py:1-90`). Argmax of `logit + T·g` = sampling from softmax(logit/T). `SEED`/`TEMP` are appended to the latched head list; the
seed is a paused CSS animation clock frozen when you tick Run, or a select box (`tools/r7b_features.py:18-29`, `:260-284`). With T = 0 the noise glyph is a
constant 800 units on every row, so greedy is bit-identical.

**Winner → text.** One `@counter-style gpt2-vocabulary{system:fixed -1; symbols: "" "!" "\22 " …}` with **50,258 symbols** (−1 → empty, then every GPT-2
token string; 470,917 B rule, runtime.css@52991424) turns a number into text: `content:counter(token1,gpt2-vocabulary) counter(token2,…)…`
(runtime.css@53465616; `tools/browser_gpt2_runtime.py:538-561`).

**Winner → next input (the upward channel).** The winner is latched into `--saved-token-N`, written as a width in a 524,288 px scroller and read back at the
top of the document, where `.feedback-select` picks the right one for the current epoch:
```css
/* runtime.css@51140721, @51140845, @51389073 — tools/browser_gpt2_runtime.py:82-102 */
.feedback-metric-1{width:calc(65536px + (var(--saved-token-1) + 1)*8px);view-timeline:--feedback-t1 inline}
--feedback-1:round(nearest,(524288 / var(--feedback-p-1) - 524288 - 65536) / 8 - 1,1)
.feedback-select{--token:if(style(--epoch:1):var(--pf-1);style(--epoch:2):var(--pf-2);…;style(--epoch:5):var(--feedback-4);…
```
`--token` then drives the embedding font's `GRUP`/`LOCL` axes (§1) — the loop is closed. (This readback assumed an exactly 524,288 px scroll box; a
classic scrollbar shifted ids ≥ ≈9,300 by +1, fixed with `scrollbar-width:none` plus a self-check — README.txt:63-77.)

---

## 6. Precision and verification

| Quantity | Representation | Source |
|---|---|---|
| Token embedding | int16 HVAR deltas, `rint(wte·4096)` (abs error ≤ 1.2e-4) | `build_hvar_token_embedding_lookup.py:26, 88` |
| Position embedding | 12-significant-digit CSS constants | `browser_gpt2_runtime.py:444-450` |
| 48 block matrices | 9-bit symmetric per-output-row (codes ±255) | `build_signed_hvar_chain.py:46-54`, `browser_gpt2_core.py:202` |
| Activations entering a font | value/max-abs on an F2Dot14 axis (≈15 bits + sign of the per-vector range) | R3P.md:22, :111 |
| Glyph-width transport | float32 widths, view-timeline progress → registered number serialised to **6 significant digits** | R3P.md:37-45 |
| LN / softmax / GELU / residual | double-precision CSS math (with the 6-digit `var()` substitution) | R3P.md:43, R2C.md:64 |
| Output head | q16 weights (`WEIGHT_SCALE` 5.448e-5), hidden state rounded to 1/16,384 of ±266.25, 4 px score buckets | `build_gpt2_groupwise_production_q16_sixfont.py:32-37`; `browser_gpt2_head.py:100-103` |
| Sampling noise | int Gumbel table, seed 20261001, 64 columns | `build_noise_font_r7b.py:22-37` |

**How correctness was checked.**
- A NumPy reference re-implements the forward pass with the **same 9-bit weights** (float64 otherwise) and the same q16 head and noise table
  (`work/2026-09-19/R7B/reference_r7b.py:1-50`, `tools/browser_gpt2_core.py:426-471`). It also runs the unquantized float model: for the stored references
  where it was computed ("Shubham was", "Once upon a time"), `quantizedEqualsFloat` = true (same greedy ids as float GPT-2).
- Chrome runs of the live build (R7X.md §3, `work/2026-09-19/R7X.md:12, 55-58`): typed "Shubham was" T=0 **35/35** ids equal to the reference (headed, OS
  scrollbars shown); dropdown "Hello" seed 17 T=1.0 **32/32** vs a new 12-layer NumPy sampled reference (25/32 steps differ from greedy, so sampling
  really changes the output); headless "I" **32/32**; demo-8 "Hello" **8/8**.
- Numeric closeness, read back from Chrome on the F4 build (cap 8): final residual RMSE **0.0193** (max 0.187), KV cache RMSE **0.0029**, 8/8 ids
  (`work/2026-09-19/F4.md` §5). R3P's error model attributes ≈half of Chrome's 0.0201 residual RMSE to F2Dot14 axes + 1/64 px advances + 6-digit
  numbers, the rest to font-engine rounding (R3P.md:56-69).
- The live page guards itself: before every token it reads back a known constant (id 50256) and checks every fed-back id against the winner; on mismatch
  the run is held with a red "Geometry self-check failed" panel (BUILD.md "Guard"; README.txt:72-77).

---

## 7. Proposed diagrams

**D1 — "A matrix row is a glyph"** (the core trick, §3)
```
 input vector x (768 CSS numbers)            variable font  b0qkvS0..S2  (one glyph per output row)
 --n1-000 ... --n1-767                        ┌──────────────────────────────────────────────┐
     │ ÷ max|x|                               │ axis A000 ──┐                                 │
     ▼                                        │ axis A001 ──┤ HVAR deltas c_i0 c_i1 ... c_i767│
 font-variation-settings:                     │   ...       ├──► advance_i = B_i + Σ c_ij·x̂_j │
  "A000" x̂0, "A001" x̂1, ... ───────────────► │ axis C255 ──┘   (HarfBuzz does the dot product)│
                                              └──────────────────────────────────────────────┘
                                                                 │ glyph in <i class=metric>
                                                                 ▼
   hidden scroller (65,536 px)  [|<------ box width = advance_i ------>|]
                                                                 │ view-timeline progress p = V/(V+w)
                                                                 ▼
   @keyframes → --qkvp-i = p  →  y_i = b_i + s_i·R·(w·1000/512 − B_i)      (CSS calc)
```

**D2 — One token through one layer** (which primitive does what; repeat 12× by flipping `--layer`)
```
 --token ─► [EmbeddingLookup font: GRUP,LOCL axes] ─► 768 widths ─► --embed-i ─► + wpe(if(style(--epoch))) ─► --x
   ┌──────────────────────────────── layer L  (@container corestate style(--layer:L)) ───────────────────────────┐
   │ --x ─► LN1 (calc Σ, sqrt) ─► --n1 ─► [qkv fonts ×3] ─► widths ─► --qkv (2,304)                              │
   │                                          │ K,V lists ──► KV bank slot S (86,400 s delayed transition = memory)│
   │   Q list + K lists(all slots) ─► [bilinear dot font] ─► 1ch ─► scores ─► softmax (max/exp/sum in calc)      │
   │   weights × [value font widths] ─► inline-flex row sum ─► widths ─► --ctx (768)                             │
   │ --ctx ─► [attn fonts ×3] ─► widths ─► --r = x + attn                                                         │
   │ --r ─► LN2 ─► [fc fonts ×3] ─► widths ─► GELU (exp/pow) ─► --hidden (3,072)                                  │
   │ --hidden ─► [proj fonts ×12] ─► width = 262144 + 128·(r + proj)  (calc-size folds the residual)             │
   └──────────────────────────────── loop-reader view-timelines ─► --x for layer L+1 ────────────────────────────┘
```

**D3 — Choosing the next word with layout** (§5)
```
 final LN ─► 768 ints on axes ─► 50,257 rows <i class=head-row> (6 weight glyphs + 1 Gumbel glyph each)
   group 0:  [row0 ████████      ]                group widths = max of 256 rows (max-content)
             [row1 ██████████████]  ──► ████████████████
             ...256 rows
   group 1 ... group 196                        ──► anchor-size() max-tree (fan-in 16) ─► winning group
                                                ──► fine pass (256 rows) ─► --winner = id
   --winner ─┬─► counter(tokenN, gpt2-vocabulary)  → " Representatives"   (50,258-symbol @counter-style)
             └─► width 65536+8·(id+1) px ─► view-timeline at the top ─► --token for the next step
```

---

## 8. Open points / caveats for the blog text
- The README's "@function math" is technically true (one `@function` exists) but nothing calls it; GELU is inlined `calc()` (§4).
- "Arithmetic is anchor positioning": anchors are used for the head's max-reduction tree, the tokenizer readback, and container plumbing — not for the
  matvecs, which are fonts + view timelines.
- The radix-256 split of the q16 head into high/residual planes is inferred from build constants (§5); the sha-pinned font bank itself was not re-opened.
- The view-timeline progress formula `p = V/(V+w)` is inferred from the decode expressions, not from Chromium source.
