# R5F — shrinking the decoded weight fonts without changing a single advance

Agent R5F, 2026-09-24 13:1x–. Scratch `R5F/` (`anatomy.py`, `compact.py` = builder + verifier, `projection.py`, `gen_fixtures.py`, `fixture.mjs` + `run_fixtures.sh`
= copies of R5M's harness, `fx/` pages, `fx-results/`), variants ONLY under `R5F/assets-r5f/` (64 MB: 21 stripped layer-0 faces, one merged
face, one re-encoded embedding face; every file has a `.json` sidecar with bytes + verification). Log `R5F.log.md`. No repo `tools/` or `experiments/`
edits, no git. fontTools 4.63.0 via `uv run` (R2I's pinned build environment). Chrome fixtures are gated (§5).

## 0. Headline

- **The 914 MB of decoded sfnt is 883 MB of HVAR, and HVAR is at its format floor for identical math except for two encoding wastes.** Stage faces store
  every 9-bit weight (q9 codes in [−255, 255]) TWICE as 16-bit deltas — a signed axis needs two single-sided regions (`(−1,−1,0)` holding −w and `(0,1,1)`
  holding +w; a region straddling 0 is defined as scalar 1 by the spec, fontTools and HarfBuzz) — and every 256-axis face carries a 786,436-byte
  VarRegionList (512 regions × 256 axis records × 6 B) that encodes 1 KB of information. Region lists are **207 MB (23 %) of the 914 MB**; delta rows are 676 MB.
- **Identical-numerics, font-only swap (no CSS/HTML change): −52 MB (−5.7 %)** = strip outlines/`post` names/`name`/`STAT` (−25 MB over 283 faces, measured
  −1.5…−1.6 % per stage face, −2.1 % per head face) + **fix the embedding face's 32-bit columns (−26.9 MB, 26 % of that face)**. The 32-bit columns are a
  fontTools bug I reproduced: `calculateNumShorts` wrote NumShorts = 50,257 = 0xC451 into a uint16 whose bit 15 is the LONG_WORDS flag, so the face is read
  as "LONG_WORDS, 17,489 int32 columns" (§3b). Both variants are built for layer 0 / the embedding and verified identical (§4). **Below the 20 % bar.**
- **≥ 20 % needs fewer region lists = fewer files: merging same-tag faces (qkv/attn/fc shard s of all layers, proj shard s of all layers) into 18–36 files
  saves 170–184 MB (−19…−20 %), −222…−236 MB (−24…−26 %) with the two items above.** Math is identical by construction (each source keeps its own
  VarData subtable, bytes and region order untouched, addressed through an AdvWidthMap) — demonstrated on layer 0's A-group: 3 faces → 1 file, 8,940,208 →
  7,151,540 B (−20.0 %), 12.4 M advance cells identical. But it needs a **codepoint re-allocation in the emitter** (today every same-tag face maps its rows
  from U+F0000, so two of them cannot share a cmap) — an R5X-level change of `codepoint_start` + `@font-face` url/unicode-range, not a font-only swap (§6).
- **Not levers (measured/derived):** 8-bit columns (every column of every stage/ProdQ16R face has a |δ| ≥ 128 because per-row q9 scaling puts a 255 in each row;
  93 % of individual deltas would fit 8 bits but HVAR widths are per column); splitting rows into 8/16-bit subtables (each row has ≈36 wide columns at random
  positions → ≤ 8–15 % of the items, and it reorders columns = float32 accumulation order in the engine, so not provably identical); redundant regions (0 —
  512/512 and 50,257/50,257 distinct); a single-region signed axis via `default = −1` (halves the F2Dot14 grid the pipeline's arbitrary-decimal `font-variation-
  settings` values are rounded onto → not identical); **serving .ttf instead of .woff2: predicted neutral** — R5A's memory-infra dump shows
  `web_cache/Font_resources/<id>|size` = `decoded_webfont` + 4.7 KB (the raw woff2 is NOT retained; R5M's ×1.35 is something else) and OTS copies either input
  into a fresh buffer; fixture queued (§5).

## 1. Anatomy (fontTools, offline; `R5F/anatomy-stage.txt`, `R5F/anatomy-head.txt`; decoded sizes = woff2 table-directory `origLength`)

| face | woff2 B | decoded sfnt B | ratio | glyphs | axes (min/def/max) | HVAR B | VarRegionList | VarData | NumShorts / LONG_WORDS | max\|δ\| | \|δ\|<128 | other tables |
|---|---:|---:|---:|---:|---|---:|---|---|---|---:|---:|---|
| qkv-rowbase-s0 (b0qkvS0; 36 faces) | 710,344 | 3,224,285 | 4.5 | 2,305 | 256 (−1/0/1), tags A000–A255 | 3,147,818 | 512 single-axis regions × 256 axes = 786,436 B | 1 × 2,305 items × 512 cols | 512 / no → 1,024 B/row | 255 | 93.1 % | glyf 27,988 (all 2,305 outlined), post 2.0 17,468, name 522 recs 9,657, hmtx 9,220, fvar 5,136, gvar 4,632, STAT 2,068, cmap fmt 12 |
| attn-out-rowbase-s0 (b0attnS0; 36) | 236,616 | 1,611,525 | 6.8 | 769 | 256 | 1,574,954 | 786,436 B = **50 % of HVAR** | 1 × 769 × 512 | 512 / no | 255 | 96.2 % | glyf 9,364, post 5,412, name 9,657, … |
| b0-fc-s0 (b0fcS0; 36) | 941,856 | 4,030,781 | 4.3 | 3,073 | 256 | 3,934,250 | 786,436 B | 1 × 3,073 × 512 | 512 / no | 255 | 93.0 % | glyf 37,300, post 23,612, … |
| mlp-proj-rowbase-s0 (F2 global; b0projS0; 144) | 248,980 | 1,609,859 | 6.5 | 769 | 256, tags X000… (per-shard blocks) | 1,573,416 | 786,436 B | 1 × 769 × 512 | 510 / no (2 columns already 8-bit, moved last) | 255 | 97.1 % | as attn |
| score-residual-0 (ProdQ16R0; 3) | 16,386,772 | 53,621,184 | 3.3 | 50,258 | 256 (−16384/0/16384) | 52,251,690 | 786,436 B | 1 × 50,258 × 512 | 512 / no | 255 | 50.8 % | glyf 609,416, post 441,349, hmtx 201,032, gvar 100,538, loca (long) |
| score-high-0 (ProdQ16H0; 3) | 9,773,836 | 27,889,088 | 2.9 | 50,258 | 256 | 26,519,594 | 786,436 B | 1 × 50,258 × 512 | **0 / no → all 8-bit, 512 B/row** | 68 | 100 % | as R |
| embedding-lookup (EmbeddingLookup; 1) | 56,853,724 | 104,925,216 | 1.85 | 769 | 2 (GRUP −1/−1/196, LOCL) | 104,896,988 | 50,257 two-axis tent regions × 2 axes = 603,088 B | 1 × 769 × 50,257 | **17,489 / LONG_WORDS → 135,492 B/row** (int32 × 17,489 + int16 × 32,768) | 7,312 (13 bits) | 17.7 % | glyf 16,918, post 5,412 |
| dot-h0 (FvsDot; 12) / value-h0 (FvsValue; 12) | 2,372 / 2,916 | 207,097 / 142,178 | 87 / 49 | 2 / 65 | 128 / 65 | 198,186 / 133,674 | 256 two-axis regions | 1 × 2 / 65 items × 256 | 256 / no | 468 / 12,000 | | tiny |

No DeltaSetIndexMap anywhere (implicit glyph-id → item), no LsbMap/RsbMap, no GSUB/GPOS, `name` = 522 records (256 axis names × 2 platforms + 10), `post` 2.0 with
glyph names, every glyph has a real outline (never painted by the pipeline: the faces are used on `.font-witness`/metric elements measured by width; empty
outlines keep hmtx/HVAR advances). Totals (`R5F/projection.txt`): 283 faces, sfnt 914.0 MB = HVAR 883.4 (region lists 207.1 + delta rows 676.3) + 30.6 other.

**Information floor vs stored.** Stage weights are the emitter's q9 codes (`QUANT_BITS = 9`, symmetric per row, `tools/build_gpt2_block_css.py:45`,
`build_signed_hvar_chain.quantize_float_rows`): 9 bits/weight needed. Stored: delta rows 32 bits/weight (two regions × int16) — plus the region list:
qkv 43.7 bits/weight per face, fc 41.0, attn/proj 65.5 (the region list is half the face). Head: ProdQ16R 33.3 bits/weight (9-bit codes stored twice ×16),
ProdQ16H 17.3 (8-bit columns), embedding 21.7 (14-bit codes; 16.2 after the LONG_WORDS fix). Whole set: ≈162 M distinct weights (85 M stage + 38.6 M head
× 2 faces + 38.6 M embedding) in 914 MB = 45 bits/weight against a quantisation floor of ≈240 MB (9/16/14 bits). The gap is the HVAR format: two regions per
signed axis (unavoidable at F2Dot14 resolution), 8/16/32-bit column granularity, and `regionAxisCount == fvar.axisCount` (spec-mandated: 6 B × axes per region).

## 2. Candidates — what keeps advances identical, with measured bytes

| # | candidate | identical? | per-face bytes (measured) | all 283 faces | verdict |
|---|---|---|---|---:|---|
| a1 | 8-bit columns via fontTools optimiser | yes if no reorder | 0: every column has max\|δ\| = 255 (anatomy: "cols with max<128: 0" on qkv/attn/fc/proj/ProdQ16R; ProdQ16H already 8-bit) | 0 | dead |
| a2 | row-grouping into 8/16-bit VarData subtables (`VarStore.optimize`) | **no** (reorders columns → engine float32 accumulation order) and ≤ 8–15 % of rows at best | not built | — | rejected |
| a3 | **embedding LONG_WORDS → all-int16** (`NumShorts = 0x8000`: LONG_WORDS flag with 0 int32 columns; same column order) | yes | 104,925,216 → 78,004,516 B (**−26,920,700, −25.7 %**) | −26.9 MB | **built + verified** (§4) |
| b | empty glyph outlines (keep `.notdef`), `post` 3.0 | yes (advances come from hmtx + HVAR) | qkv −45,456 (glyf 27,988 + post 17,436); ProdQ16 −1,050,733 each | −22 MB | built (§4) |
| c | `name` → 6 records + one shared axis nameID, drop `STAT`, no instances | yes | −11,429 per 256-axis face | −3 MB | built (§4) |
| d | redundant regions inside a face | — | none: 512/512, 50,257/50,257 distinct | 0 | dead |
| e | serve .ttf instead of .woff2 | yes (same bytes) | memory: **predicted 0** (raw resource not retained per memory-infra; OTS output = same sfnt) | 0 | fixture queued |
| f | signed axis as one region (`default = −1`, deltas 2w, base −Σw) | **no**: normalised grid becomes 1/8192 instead of 1/16384 | would be −50 % of HVAR | — | rejected |
| g | **merge same-tag faces** (one VarRegionList per file; per-source VarData kept byte/order-identical; AdvWidthMap) | yes (needs codepoint re-allocation → CSS/HTML) | A-group of layer 0: 8,940,208 → 7,151,540 (−20.0 %) | −170 (36 files) … −184 MB (18 files) | **built + verified** (§4), recipe §6 |
| h | fewer axes per face (128-axis shards halve region lists) | no (two roundf's instead of one per row) | — | — | exact-class only, not identical |

## 3. Why the big ones cannot move without touching numerics

- **3a. Two regions per signed axis.** A region's scalar is 1 at its peak, linear to 0 at start/end, and *1 if start < 0 < end* (spec, fontTools
  `supportScalar`, HarfBuzz `VarRegionAxis::evaluate`). A linear-through-zero response on [−1, 1] therefore needs `(−1,−1,0)` and `(0,1,1)`; the only
  single-region alternative moves the axis default to −1, which halves the F2Dot14 grid onto which the engine rounds the pipeline's arbitrary decimal
  `font-variation-settings` values (`AXIS_STEPS = 16_384` is what the head's bounds assume) — different rounding, different advances.
- **3b. The embedding face's 32-bit columns.** fontTools `VarData.calculateNumShorts` computes NumShorts as "index of the last ≥ 16-bit column + 1" =
  50,257 = 0xC451 and stores it in the uint16 whose bit 15 is LONG_WORDS. My first re-encode (`R5F/reencode-emb.out`) reproduced the exact original layout
  (LONG_WORDS | 17,489), proving the origin. The fix is to set 0x8000 explicitly (all columns int16, no reordering) — `R5F/compact.py` does that itself.
- **3c. Column packing is per column.** q9 per-row scaling gives every row a 255 somewhere; with 2,305–50,258 rows every one of the 512 columns sees one.
- **3d. The region list is spec-fixed at `regionAxisCount == fvar.axisCount`.** OTS/HarfBuzz/fontTools all take the count from the table; a smaller record
  would not be able to name axis 255. The only way to pay it less often is fewer faces (g) — or fewer axes per face (h), which changes rounding.

## 4. Built variants (`R5F/assets-r5f/`, woff2 only; `.json` sidecars) and verification (`R5F/compact.py`)

Verification per variant: (i) region lists identical; (ii) for every glyph the delta row is identical **in the same region order** (so any evaluator —
fontTools double, HarfBuzz float32, CoreText — sums the same terms in the same order) and hmtx identical; (iii) advances at 12 corners (all −1, all +1, all 0,
alternating, 8 random sign vectors) + 2,000 random F2Dot14-grid locations (+ 2,000 pipeline token locations for the embedding) for **all glyphs**, computed
with a vectorised copy of fontTools' `supportScalar` + `otRound` (cross-checked against `supportScalar` on 200 samples); (iv) fontTools `VarStoreInstancer`
on 64 locations × 24 glyphs per face; (v) cmap row order identical. Witness advances (`font-witnesses.json` = default advance of the first row) are covered
by (ii)/(iii) at the all-zero corner.

| variant | faces | sfnt before → after (B) | Δ | woff2 before → after | glyphs × locations | mismatches |
|---|---:|---:|---:|---:|---|---:|
| strip, layer 0 (`b0*-strip.woff2`) | 21 | 46,230,228 → 45,177,824 (fontTools re-save basis) ; woff2-directory basis: qkv 3,224,285 → 3,172,292, attn 1,611,525 → 1,587,140, fc 4,030,781 → 3,964,868, proj 1,609,859 → 1,585,472 | −2.3 % / **−1.5…−1.6 %** | 8,625,616 → 8,528,840 | 21 × (769…3,073) × 2,012 | 0 (HVAR bytes identical) |
| merge A-group layer 0 (`b0-A-merged.woff2`: qkv-s0 + attn-s0 + fc-s0 → 6,145 glyphs, 3 VarData, AdvWidthMap, blocks U+F0000–F08FF / F0900–F0BFF / F0C00–F17FF) | 3 → 1 | 8,940,208 → 7,151,540 | **−20.0 %** | 1,888,816 → 1,865,268 | 2,304 + 768 + 3,072 × 2,012 | 0 |
| embedding re-encode + strip (`embedding-lookup-r5f.woff2`) | 1 | 104,925,216 → 78,004,516 | **−25.7 %** | 56,853,724 → 54,032,152 (only −5 %: the int32 high bytes were zeros, so brotli had hidden the waste) | 769 × 3,976 | 0 |

The 21 layer-0 sidecars list every table before/after (qkv-s0 after: HVAR 3,147,818, hmtx 9,220, fvar 5,136, gvar 4,632, loca 4,612, name 296, post 32, glyf 22).

## 5. Chrome fixture (task 4) — queued behind the machine gate

`R5F/run_fixtures.sh R5F/fx.list fixtures` (pid **10497**, started 13:33; `R5F/run_fixtures.out`) = R5M's runner with owner marker `R5F fixtures <pid>
<time>`, touch -c 30 s, rmdir only its own marker, 5 s lock polling, and the coordinator gate (AC ∧ disk ≥ 3.0 GB ∧ swap used < 3,000 MB, re-checked after the
lock). At 13:33 the machine had 1,421 MB free and 3,613 MB swap in use → waiting. Cancel with `kill 10497`. Pages (`R5F/fx/`, R5M's fonts-only skeleton:
`@font-face` + the bundle's `.font-witness` element per face, one laid-out glyph each; fresh headless Chrome per page, RSS after settle / GC / critical pressure):

| pair | measures | expected (sfnt basis) |
|---|---|---|
| `l0-orig21` vs `l0-strip21` (+ repeat pair) | 21 layer-0 faces original vs stripped | −1.0 MB (noise floor ±40 MB → likely invisible; included for completeness) |
| `l0-orig9` vs `l0-ttf9` | qkv/attn/fc ×3 as woff2 vs the existing `.ttf` files | 0 if the raw resource is dropped (memory-infra says so); +26 MB if R5M's "raw kept" reading were right |
| `A-orig3` vs `A-merged` | 3 faces vs one merged file used by 3 `@font-face` rules with unicode-ranges | −1.8 MB, **and** whether Blink decodes a URL shared by 3 rules once (if it decoded per rule, +14 MB instead) |
| `emb-orig` vs `emb-r5f` | embedding face original vs re-encoded | **−27 MB** (the only pair with a signal well above noise) |

Results land in `R5F/fx-results/*.json` and `R5F.log.md`; extrapolation to 283 faces then = measured Δ per face × counts from `R5F/projection.txt`.

## 6. Recipe for R5X

**Tier 1 — font-only swap, identical numerics, −52 MB (−5.7 %), no CSS/HTML changes except url digests:**
1. For each of the 283 faces run `uv run --with fonttools==4.63.0 --with brotli==1.2.0 --with numpy python work/2026-09-19/R5F/compact.py strip <src.woff2> <out.woff2>`
   (`reencode` for `embedding-lookup` — use the `.ttf` next to it as the source to skip decompression). Deterministic (no timestamps are touched; `head`
   is copied), ≈10 s per stage face, ≈8 min for the embedding, output woff2 + a `.json` proof. Disk: outputs are ≈ the input woff2 sizes (239 MB total);
   run per layer and move into place.
2. Bundle: `@font-face` urls keep their paths if the files are swapped in place (NOT in `experiments/` — put them under a bundle-owned assets dir and repoint
   the 283 `url()`s), digests `?v=sha256(woff2)[:12]` recomputed (they are cosmetic for the static server, but the emitter writes them — see
   `rewrite_layer_assets` in `tools/build_flat_twelve_block_chain.py`); `font-witnesses.json` entries stay valid (advance/codepoint/upem unchanged; the
   `mtime` cache key changes → regenerate or copy mtimes as R2I did). `launch_browser_gpt2.py --check` for the static-file count.
3. Before benching: one Chrome smoke on a 2-layer bundle — OTS must accept `post` 3.0 + empty outlines + shared axis nameID + no STAT (all standard; OTS
   only warns on name IDs) and `NumShorts = 0x8000` (HarfBuzz/OTS handle `wordCount == 0`; CoreText already accepts LONG_WORDS since the original face
   uses it). If OTS rejected a variant it would fall back to the next `src`/system font and the witness barrier would stall — visible immediately.

**Tier 2 — merge same-tag faces, identical numerics, −170…−184 MB more (−24…−26 % total), needs the emitter:**
1. Codepoint allocation (today every face starts at U+F0000 with shard offsets; `codepoint_start` in `build_direct_font_backend` /
   `build_font_group(name, codes, row_specific_bases=True)`): give each (layer, stage, shard) a block that is disjoint from the other members of its
   *file* and from its siblings in the same `font-family` list (unicode-range routing). Single-plane plan (PUA-A only, 65,534 codepoints): 3 layers per
   stage file → within file k (layers 3k…3k+2), layer-in-file l: qkv-s rows at `s·18,432 + l·6,144 + r`, attn-s at `s·18,432 + l·6,144 + 2,304 + r`,
   fc-s at `s·18,432 + l·6,144 + 3,072 + r` (max 55,296); proj: 6 layers per file, shard s at `s·4,608 + l·768 + r` (max 55,296). Files: 3 groups
   (A/B/C tags) × 4 + 12 proj shards × 2 = **36 files (−170 MB)**; using PUA-B for a second set of layers gives 18 files (−184 MB). The emitter's content
   strings, `unicode-range`s and witness codepoints follow `codepoint_start` automatically.
2. Build the per-face fonts exactly as today (byte-identical HVAR), then `compact.py merge <out.woff2> <face1> <face2> …` per file (asserts identical
   tags/ranges/region lists; one VarData per source, unchanged; AdvWidthMap; `.notdef` once; cmap 12 with the allocated blocks; strip applied). ≈30 s and
   ≈40 MB peak per file; verify output is in the sidecar.
3. `@font-face`: each of the 252 stage families keeps its name and its own `unicode-range`, `src` → the merged file's url. Blink caches the FontResource by
   URL, so 12–36 rules sharing a file should decode it once — **the `A-merged` fixture is the check for this before scaling up.**
4. Everything else (values, `font-variation-settings` lists, family lists, witnesses) is unchanged; NumPy 8/8 + offline witness check as usual.

## 7. Risks

- Chrome acceptance of the stripped tables and of `NumShorts = 0x8000` is untested (gate). Standard encodings, but the first Chrome smoke must precede any bench.
- Region-order preservation is what makes the variants engine-independent; any future "optimise" step (fontTools `VarStore.optimize`, `buildVarData(optimize=True)`
  on merged items) would reorder columns and void that guarantee — `compact.py` never recompiles a VarData with `optimize`.
- Tier 2 changes the set of characters in the HTML/CSS; a mistake shows up as a witness stall or a wrong layer reading another layer's row — offline checks
  (cmap row order per block, witness advances) catch both, and the merged file's `AdvWidthMap` makes the mapping explicit.
- Blink per-`@font-face` decode of a shared URL would turn tier 2 into a loss (fixture `A-merged`).
- Resident-memory accounting (`ps` RSS) on macOS under swap pressure can hide ±1–2 GB; compare pairs only within one run (R5M §6).

## 8. Not verified / not done

- No Chrome measurement of any variant (renderer RSS, OTS acceptance, shared-URL decode) — all queued behind the machine gate (§5).
- Only layer 0 + the A-group + the embedding were built (disk); the other 11 layers and the 6 ProdQ16 faces are covered by the same code path and by the
  projection, not by built files.
- The origin of R5M's ×1.35 (316 MB beyond the 914 MB sfnt: CoreText/Skia per-face objects, HarfBuzz table copies, or transient decode buffers) remains
  unattributed; memory-infra rules out the raw woff2.
