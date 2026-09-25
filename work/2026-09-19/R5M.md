# R5M — what memory can be cut from `combined7` (cap 8) without touching numerics or ids

Agent R5M, 2026-09-24 12:14–. Work under `R5M/` (`fixture.mjs` harness, `gen_fixtures*.py` pages, `fx-results/*.json`, `fx_table.py`, `font_inventory.py/json`,
`woff2_tables.py`, `census.py`, `tools/` = R4M/tools7 + `r5m_flags.py` + runtime.py hook, `compile.sh`, `offline_check_r5m.py`, `correctness_run.mjs`, `run_correctness.sh`,
`run_fixtures.sh`). Log `R5M.log.md`. Bundle `bundles/R5M` (`BUILD.md`). No repo `tools/` or `experiments/` edits, no git. R5A's memory-infra dumps
(`R5A/run-combined7/parsed-3/mem8-3-memdumps.md`) were read, not re-traced.

## 0. Headline

- **Where the 6 GB is (R5A's memory-infra dumps of THIS bundle + my fixtures):** renderer private footprint 1.44 GB after load → 5.3 GB at token 1 → 5.7–6.2 GB by token 7.
  By allocator at token 1: **Oilpan (blink_gc) heap 3.29 GB**, malloc 1.04 GB, PartitionAlloc 0.38 GB, web_cache 0.87 GB (decoded fonts, overlaps malloc), Skia glyph caches < 1 MB,
  V8 4 MB. Oilpan is 150 MB at load and **1.82 GB one second after Run** (the display-locked 50,257-row head becomes visible + first passes), then +0.13–0.5 GB/token.
  The one detailed dump (t = 128 s) has **Oilpan heap 3.90 GB but allocated_objects 0.92 GB** — ¾ of the Oilpan heap is garbage/unswept/fragmentation, not live state.
- **Fixture-measured MB per suspect** (§1): decoded fonts **1,230 MB** (283 faces, 914 MB sfnt of which 881 MB HVAR; not purgeable, needed at cap 8, declared-but-unused faces cost 0);
  font INSTANCES ≈ 0 per new instance for every face incl. the 54 MB head faces (variation instances do not copy tables; 65-axis leaf instances 6–14 KB each, and the page has only
  ≈2.6 k new instances per token — R4V's 144·p/12·p counts are per layer, not per leaf); DOM+style 2.5–2.8 KB per laid-out element (50 k → 140 MB), **`content-visibility:hidden`
  subtree → 0**; 39,513 `@property` registrations alone → 0, but 50 k elements with inline custom properties under those registrations → +279 MB after GC (§1.3, single run);
  live animations: only **9,216** are live (144 consumer elements × 64; the 1,200 declarations are 12 per-layer `@container` variants) ≈ 35–70 MB (10 k fixture); 77 k live would be 596 MB.
- **The real 50 k-row head subtree alone = ≈0.9 GB after load** (partial fixture under the real stylesheet, §1.5) — this is the +2 GB of token 1 (head un-locks) and, restyled once per
  token with 50 k unique inline styles, the largest per-token garbage producer that is not the transformer's own transport.
- **Static census of who owns custom-property tries (`R5M/trie_census.py`, `R5M/trie_census.txt`): of the 50,687 elements that declare inherited custom properties, 50,257 are the
  head rows** (2 inline entries each, inserted under the `.head-isolation` wall's 15,313-entry inherited map → two HAMT path copies ≈ 17 trie nodes per row = R5A's 854 k
  `HashTrieNode<CSSVariableData>` ≈ 220 MB live, re-created as garbage at every head restyle); the other 430 declaring elements are consumers/banks/readers. V leaves, carriers
  and metrics declare nothing (they only read), so the tries above them (12,936 / 3,073 entries) are shared by pointer and cost nothing per element.
- **Cut built (`bundles/R5M`, flag `R5M_HEAD_LITERAL`): head rows carry their width as an inline literal instead of `--base`/`--tie` custom properties** → declaring elements
  50,687 → 430 (≈ −220 MB live trie nodes, ≈ −100 k CSSVariableData, and no per-row
  trie path copy / var() substitution / calc parse per head restyle); exact by construction (§3), offline-verified (§4: flag-off twin byte-identical to combined7; runtime.css,
  witnesses identical; 50,257/50,257 literals equal the reference `--base`; NumPy 8/8; no JS). **Its MB value is NOT yet measured**: the decisive fixtures (`head50k-vars/literal/nowall`)
  and the correctness run are queued behind the coordinator's machine gate (disk ≥ 3 GB, swap < 3 GB; at 13:00 the machine had 295 MB free and 5.35 GB swap in use) — see §5/§7.
- **What cannot be cut without changing numerics**: the decoded fonts (1.23 GB floor; every face is used at cap 8; woff2 is already the cheapest container — the raw 239 MB appears
  to stay resident next to the 914 MB sfnt); the live V-leaf/score/carrier state (small anyway). Oilpan's heap-growth policy has no launcher knob (§1.6).

## 1. Measured MB per suspect (fixtures, `R5M/fixture.mjs`: fresh headless Chrome per page, same launch args as the bench incl. `--js-flags=--heap-growing-percent=10`,
renderer RSS via `ps` after style/layout settle, then `HeapProfiler.collectGarbage`, then `Memory.simulatePressureNotification(critical)`; blank tab ≈ 175 MB; noise ≈ ±40 MB)

Full table: `R5M/fx-table.md` (from `python3 R5M/fx_table.py`). Machine during fixtures: AC, load 4–6, swap 1.8–3.7 GB in use, 48 % free — RSS deltas within one page are robust,
absolute drops after GC/pressure on small pages are partly the blank tab's own release.

### 1.1 Decoded fonts (suspect 1) — 1,230 MB, floor

| page | faces | sfnt MB (woff2 MB) | ΔRSS after load | after GC | after critical pressure |
|---|---:|---:|---:|---:|---:|
| fonts-all (combined7's 283 `@font-face` + the 283 `.font-witness` elements verbatim) | 283 | 914 (239) | **+1,230** | −1 | 0 |
| fonts-big7 (EmbeddingLookup 105 MB + ProdQ16 R/H 3+3) | 7 | 354 (135) | +477 | 0 | 0 |
| fonts-weights (b{L}{qkv,attn,fc,proj}S{n}) | 252 | 556 (104) | +719 | −1 | 0 |
| fonts-fvs (F4 dot/value operator fonts) | 24 | 4.2 (0.07) | 0 | | |
| fonts-all-unused (283 declared, no element uses them) | 283 | | **+1** | | |
| fonts-all-ur (all faces `unicode-range:U+E000`, witness chars outside) | 283 | | +123 (system fallback fonts for uncovered PUA chars, not the faces) | | |

Reading: ΔRSS/sfnt = 1.35× (fonts-all), 1.29× (weights) — consistent with Chrome keeping BOTH the decoded sfnt (914 MB, in malloc; memory-infra `web_cache` = 873 MB) and the raw
woff2 buffers (239 MB) for the document lifetime; neither GC nor a critical memory-pressure notification releases any of it. Lazy loading works (unused faces cost nothing), but
every one of the 283 faces is used at capacity 8 (`R5M/font_inventory.txt`: compute refs > 0 for all; the barrier only front-loads them), the head fonts are used every token,
and 881 of the 914 MB is HVAR (the weights themselves; `R5M/woff2_tables.py`) — no glyph rows are unused. `font-display` cannot change what is resident. **Nothing to cut here
without a smaller model representation.**

### 1.2 Font instances and shape caches (suspect 2) — negligible

| page | ΔRSS after load | Δ per generation (new instances for every element) | after GC / pressure |
|---|---:|---|---:|
| inst-1000 / 4000 / 16000 distinct 65-axis FvsValue0 instances, 1 glyph each, laid out | 0 / +26 / +226 (6.5–14 KB per instance incl. ShapeResult) | | 0 |
| inst-4000-same (identical settings) | 0 | | |
| inst-4000-none (`display:none`, style only) | +13 | | |
| inst-gen-4000 (5 inline 65-axis lists per leaf, 4 generations) | +278 (the 5×1 KB inline lists per element, see 1.3) | +1 +0 +0 +1 | +1 |
| inst-score-400 / inst-score-gen-100 (FvsDot0, 128 axes) | 0 | +0 ×4 | |
| inst-fc-8 / inst-fc-gen (b0fcS0-2, 256 axes, 12 MB sfnt) | 0 | +0 ×4 | |
| inst-proj-gen (b0projS0, 256 axes) | 0 | ≈0 (−69/+23 noise) | |
| inst-embed-gen (EmbeddingLookup 105 MB, 2 axes) | +119 (the face) | +0 ×4 | |
| inst-head-gen (the 6 ProdQ16 faces, 256-axis settings, 64 real rows) | +293 → 189 after the first restyle (decode transient freed) | +1 +3 −6 | +2 / +3 |

Counts in the page at cap 8 (from the bundle): V leaves are 64 per (head, slot) sharing ONE settings list → 96 V instances + 96 score instances per layer, 252 weight-font instances
(one per face per pass) + 6 head + 1 embedding per token ≈ **2.6 k new instances per token**; at ≤ 14 KB each that is ≤ 36 MB/token of short-lived state. A purge of the
FontCache is therefore not what moves RSS in the runs; Oilpan is (§2). R4V §2's "144·p V instances" are per layer and not memory-relevant.

### 1.3 DOM + ComputedStyle + registered properties (suspect 3)

| page (50,000 `<i>` with 6 chars, laid out like head rows) | ΔRSS after load | after GC | notes |
|---|---:|---:|---|
| dom-50k-plain (no inline style) | +140 | +123 | 2.5–2.8 KB per element (Node + ComputedStyle + LayoutObject + shaping) |
| dom-50k-inline (`--base/--tie` inline, width rule with var()) | +320 | +68 | +180 MB of parse/substitution garbage collected by GC (single run; repeat queued) |
| dom-50k-inline-props (same + combined7's 39,513 `@property` block) | +378 | **+347** | +279 MB after GC vs the previous row — per-element inherited-map cost under 16 k inherited registrations (single run; repeat queued) |
| props-only (the `@property` block alone) | 0 | 0 | registrations are free |
| dom-50k-cv (same under `content-visibility:hidden`) | **0** | 0 | LayoutObjects 9; nothing is allocated for a locked subtree |
| dom-50k-none (`display:none`) | 0 | 0 | |

Element populations (R5A census + mine): head 51,138 (50,257 rows with unique inline `--base/--tie`), V leaves 6,144 + 768 rows, carriers 7,680 + 768, font barrier 587, consumers 144,
score glyphs 96, R4S chain 48, banks 12. Only the head rows combine "unique inline custom properties" with "restyled as a whole every token" and sit under the `.head-isolation` wall,
which declares 24,105 custom properties (15,309 inherited) as `initial` — every row therefore owns a StyleInheritedVariables delta under a 16 k-entry inherited map.

### 1.4 Animations and timelines (suspect 4)

| page (T view-timelines on `.metric` elements, 12 consumers per timeline, 64 animations per consumer element, one `@keyframes` per timeline) | animations | ΔRSS | style ms at load |
|---|---:|---:|---:|
| anim-10k | 9,984 | +35 | 198 |
| anim-38k | 38,400 | +276 | 3,368 |
| anim-77k | 76,800 | +596 | 14,679 |

≈ 7.5 KB per live view-timeline animation (KeyframeEffect + timeline attachment + compositor pending state), superlinear at the low end. **combined7 has 9,216 live** (144 consumer
elements × 64; the 76,809 names in the sheet are 12 per-layer `@container` variants of 100 consumer rules) → ≈ 35–70 MB. Not a target; the "≈100 k carriers" is a per-token
change count, not a live population.

### 1.5 The real head subtree and the whole bundle at idle

| page | ΔRSS after load | after GC | after pressure |
|---|---:|---:|---:|
| bundle-load (combined7 index.html, idle after fonts-loaded) | **+1,513** | −28 | 0 |
| head50k-vars-gen (real 197 `.head-group` sections = 50,257 rows, real runtime.css, head un-locked, `--head-fvs` generations) | **+1,360** (before the first generation; the run was cut by the machine gate) | pending | pending |

bundle-load = fonts 1,230 + ≈280 MB for the 40 MB stylesheet, 132 k nodes, 9.2 k animations (the head is display-locked at idle, so its 50 k rows cost only their DOM nodes).
head50k-vars-gen − (6 head faces ≈ 360 MB + stylesheet ≈ 100 MB) ≈ **0.9 GB for the styled, laid-out head** — matching R5A's Oilpan jump 150 MB → 1.82 GB in the first second of Run.

### 1.6 Garbage rate and GC knobs (suspect 5)

Oilpan (cppgc) is where the garbage lives (blink_gc heap 3.3–3.9 GB vs ≤ 0.92 GB live objects in R5A's dumps). `--heap-growing-percent` is a V8 (JS heap, 1–4 MB here) flag; cppgc's
growing factor (1.5× live after the last GC) and PartitionAlloc's decommit policy have **no stock launcher knob**; the only stock levers are `Memory.simulatePressureNotification`
via CDP (harness-side, not the page) and the OS's own pressure. My pressure test on the idle bundle released 0 MB; a per-token pressure arm exists in `R5M/correctness_run.mjs`
(`R5M_PRESSURE=1`, diagnostic only, not run — one Chrome slot). Garbage per token is Σ restyled elements × bytes per restyle: the head (50 k unique styles, 1×/token), the V-leaf
subtree (25,351 elements × 12/token, R4W), the query/bank/reader passes; the cut in §3 removes the head's per-row substitution/parse/delta share of it.

## 2. Reading R5A's memory-infra dumps (`R5A/run-combined7/parsed-3/mem8-3-memdumps.md`, run mem8-3, heap flag on, swap 3.7–5.9 GB in use)

| when | PrivFoot MB | blink_gc heap | malloc | partition_alloc | web_cache |
|---|---:|---:|---:|---:|---:|
| after load (−18 s) | 1,440 | 150 | 424 | 303 | 873 |
| 1 s after Run | 3,342 | 1,817 | 612 | 327 | 873 |
| token 1 (44 s) | 5,301 | 3,289 | 1,044 | 382 | 873 |
| token 3 (82 s) | 5,502 | 3,567 | 961 | 388 | 873 |
| 120 s | 6,240 | 3,903 | 1,356 | 402 | 873 |
| detailed dump (128 s) | 5,666 | 2,975 heap / **924 allocated_objects** | 834 | 344 | 873 |

Renderer RSS in that run (1 Hz ps, `R5A/run-combined7/mem8-3.json`): 1,846 MB after load → 3,268 (k=1) → 4,029–4,265 (k=3–5) → 4,277 peak, with drops to 2.1–2.3 GB at k=6 and k=8
(macOS compressor/purges under 5–6 GB swap use) — versus B5's four clean-state runs of the same bundle: 1.85–2.03 GB → 3.5–3.9 GB (k=1) → 5.7–6.0 GB (k=8), monotone.
So the "before" for this bundle is **peak 5.7–6.0 GB (clean memory state), 1.9 GB idle**; in today's pressured state the same bundle peaks at 4.3 GB.

## 2b. Coordinator's 13:0x priorities (answered offline; Chrome gated)

1. **Garbage rate by pass population** (`R5M/trie_census.py` (A); restyles/token from R4W's pass histogram, KB per restyle from R4W/R5A — estimates, not re-traced):
   V-leaf subtree 25,351 elements × 12 restyles/token × ≈3.5 KB ≈ **1.0 GB/token (≈75 %)**; query/bank/reader passes (414+782+3,089+2,324 elements × 12) ≈ 0.23 GB/token
   (the 12·p score glyphs' 12.7 KB K-list substitutions and the 37·p bank aliases); head 50,257 × 1 × ≈2.5 KB ≈ 0.12 GB/token; carriers/consumers ≈ 0.03. Levers, in order:
   (a) the V-leaf substitution — R4W's per-slot-font wrapper (leaves declare nothing, 8 B substituted) is the template; it exists only for the `widths`/cap-32 family
   (`combined4-c32d`), a port to combined7's `runs` layout needs the emitter's `fallback` value layout + F4 packed banks (`browser_gpt2_font_vector_cache.py:181` raises) and a
   Chrome smoke — not doable under today's gate; R4W also measured +1.5 s/token layout intercept for it at cap 32, so it is a memory-for-time trade until re-benched at cap 8;
   (b) the score glyphs' K lists (12·p × 12.7 KB per restyle) — R5H's `1ch` readback replaces these elements; (c) the head — done here (`R5M_HEAD_LITERAL`).
   Note R4W's evidence: removing 99 % of the leaf-side substituted bytes did not change the RSS trajectory at cap 32 under swap pressure; Oilpan's committed-but-free 3 GB is set
   by GC cadence vs allocation rate, so a rate cut lowers the peak only if GC pauses do not shrink proportionally — B6's paired RSS column decides, not this report.
2. **Custom-property tries (468 MB live)**: see the census in §0 — 50,257 of 50,687 declaring elements are the head rows; `R5M_HEAD_LITERAL` removes them. After that, `inherits:false`
   pruning is not a memory lever (430 declaring elements; the 15,309-entry `.head-isolation` and 6,946-entry `.core-reset` `initial` walls are one trie each, ≈1–3 MB) — it would
   only reduce restyle propagation (time; R5E/R5H territory) and carries the R4T `inherit`-forwarding exactness risk, so I did not change any registration.
3. **Fonts (872 MB resident)**: fixed while faces are referenced (§1.1: GC and critical pressure release 0). Uncompressed-sfnt residency test needs TTF copies of ≥ 150 MB on a disk
   with 300 MB free — not attempted; the woff2 → sfnt decode is a copy that OTS would also make for raw TTF (WebFontDecoder sanitises into a new buffer), so no gain is expected.
   The 283 witnesses only front-load the faces (lazy loading verified: declared-but-unused faces cost 0); all 283 are used at cap 8, so the barrier does not change residency.

## 3. What was cut and why (bundle `bundles/R5M`, `R5M/tools/r5m_flags.py`, hook `browser_gpt2_runtime.py:275–277`)

`R5M_HEAD_LITERAL` (default 1): every coarse head row `<i class="head-row" data-token="t" style="--base:B;--tie:T">` becomes
`style="width:calc-size(max-content,round(nearest,(size - Bpx)*120.777609693 + 211968px,4px))"`. Exactness: combined7's cascade winner for `.head-row{width}` is the two-pass rule
`calc-size(max-content,round(nearest,(size - var(--base)*1px)*120.777609693 + 211968px,4px))` (later in the sheet than the tie-bearing base rule, same specificity — asserted by the
transform and the checker); `var(--base)*1px` with `--base:B` (unregistered, substituted textually) is the length `Bpx` bit-for-bit; `--tie` is dead in that rule; FACTOR/OFFSET are
read from the rule, not retyped. No rule, font, registration or other element changes (runtime.css byte-identical). Effect per head restyle (once per token, 50,257 rows): no
per-row var() substitution + calc-size parse, no per-row StyleInheritedVariables delta under the 16 k-entry wall map; the inline calc tree is parsed once at load instead.
Cost: index.html 6.52 → 9.91 MB (parsed once); ≈50 k parsed calc trees live (≈1 KB each, ≈50 MB) instead of ≈50 k two-entry variable maps. Expected net: less per-token garbage
(and a little less head style time); live memory ≈ unchanged; the fixture pair `head50k-vars-gen` / `head50k-literal-gen` measures it directly (pending, §5).

Considered and NOT cut (numbers do not justify or exactness forbids): dropping `@font-face` entries (none unused); font subsetting/splitting (all rows/glyphs used, 96 % HVAR);
`content-visibility:hidden` on inert subtrees (the only large inert population, the head, is already display-locked when idle and must be live every token; the font barrier is 587
elements); packing registered properties (registrations cost 0; the per-element cost is in elements that declare custom properties, which the head cut addresses); bounding font
instances (≈0 MB each, no reuse exists — R4V); removing the `.head-isolation`/`.core-reset` `initial` walls (they exist to stop inherited-variable propagation; memory effect being
measured by `head50k-nowall-gen`, pending).

## 4. Offline verification (`R5M/offline-checks.txt`)

- `R5M_HEAD_LITERAL=0` twin = `bundles/combined7` byte-for-byte (index.html; runtime.css after url-depth normalisation; witnesses 283/283; manifest +`r5mHeadLiteral:false`).
- `bundles/R5M` vs combined7: runtime.css IDENTICAL, font-witnesses 283/283 identical (no font touched), manifest differs only in `r5mHeadLiteral`, index.html identical modulo the
  50,257 head-row `style` attributes, each literal == the reference row's `--base` with the rule's factor/offset, no `--base`/`--tie` left, cascade order verified (`R5M/offline_check_r5m.py` PASS).
- `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`. NumPy ids with `R5M/tools`: 8/8 (`R5M/reference_ids.log`; the tools diff is runtime.py + r5m_flags.py only).

## 5. Chrome: fixtures fx3 + ONE correctness run (queued behind the coordinator's gate)

STATUS at hand-back (13:1x): three gated background jobs are queued and alive — `R5M/run_fixtures.sh R5M/fx3.list` (pid 1728), `R5M/run_correctness.sh R5M run1` (pid 2959; both
wait for AC ∧ disk ≥ 3.0 GB ∧ swap < 3,000 MB, 60 s poll, re-checked after taking `CHROME.lock`), and `R5M/finish_after_run.sh` (pid 4051) which, once `R5M/run-R5M-run1/DONE`
exists, appends §5.1 (fx3 table, ids, per-token times, per-token RSS, peak) below and to `bundles/R5M/BUILD.md` and creates `bundles/R5M/READY` ONLY on 8/8 ids + verify rc 0.
A fourth waiter deletes the 26 MB of fx3 pages after the fixtures run. Incident 13:05: the correctness chain matched an earlier (killed runner's) "fx3 END" log line and deleted the
fx3 pages early; they were regenerated (deterministic generators) before any Chrome ran. Original plan text follows.
STATUS 13:0x: `R5M/run_fixtures.sh R5M/fx3.list` (dom-50k-inline ×2 repeats, `head50k-{vars,literal,nowall}-gen`, 3 `--head-fvs` generations each) and then
`R5M/run_correctness.sh R5M run1` (R4M's harness + renderer RSS at 1 Hz; ids, verify rc, READY) are waiting for AC ∧ disk ≥ 3.0 GB ∧ swap < 3,000 MB (60 s poll, re-checked after
the lock is taken). At 13:00: disk 295 MB free, swap 5.35 GB used. Results are appended to `R5M.log.md` and `R5M/fx-results/`, `R5M/run-R5M-run1/` when they land; this section
is updated then. Until then `bundles/R5M` has **no READY**.

## 6. Risks

- The cut's MB and s/token are unmeasured until §5 runs; the fixture design (real stylesheet, real 50 k rows, `--head-fvs` generations) is the right instrument, but Blink's
  StyleInheritedVariables may already store only a delta against a root, in which case the saving is the substitution/parse garbage only (≈50 k × ~1.5 KB ≈ 75 MB/token) and live
  memory may rise by the ≈50 MB of parsed calc trees. Either way ids are exact by construction.
- Inline `width` on the rows overrides all three `.head-row` width declarations; if a future emitter change puts a different width rule on `.head-row` (e.g. a capacity-32 receipt
  split or a decoder change), the transform's assertion on the two-pass rule shape fires at build time rather than silently emitting a mismatch.
- RSS on macOS excludes compressed pages: under swap pressure (today) the renderer's RSS drops 1–2 GB without Chrome freeing anything (R5A's run: 4.3 → 2.1 GB at k=6). Compare
  before/after only within one memory state (B6 pairs).

## 7. What I could not measure

- The three decisive head fixtures and the correctness run (machine gate, §5). A partial `head50k-vars-gen` row exists (loaded +1,360 MB, 63 s of first layout).
- Per-allocator attribution inside my fixtures (RSS only); R5A's memory-infra dumps cover the bundle itself.
- Whether Chrome keeps the raw woff2 buffers (inferred from the 1.35× ratio, not from a dump line).
- Any per-token pressure/purge arm (`R5M_PRESSURE=1`) — one Chrome slot only.

### 5.1 Results (appended by `R5M/finish_after_run.sh`)

fx3 fixtures (`R5M/fx-results/*.json`; RSS MB vs blank tab; gens = successive `--head-fvs` changes on the real 50 k-row head):

| fixture | load ms | Δ loaded | Δ per gen | after GC | after pressure | layoutObjects |
|---|---:|---:|---|---:|---:|---:|
| dom-50k-inline | 1396 | +320 |  | 242 | 242 | 100004 |
| dom-50k-inline-props | 1592 | +372 |  | 524 | 524 | 100004 |
| head50k-vars-gen | not run |
| head50k-literal-gen | not run |
| head50k-nowall-gen | not run |

Correctness run `R5M/run_correctness.sh R5M run1` (- 2026-09-24 14:31:31 [R5M correctness/R5M/run1] START correctness run url=http://127.0.0.1:46450/work/2026-09-19/bundles/R5M/index.html waited=546s power=Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 37%; charging; 5:11 remaining present: true load={ 4.42 4.38 4.33 }):
- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.01605519804514142, 'maximum': 0.11651862085027176}, 'text': "Hello, I'm sorry, but I'm".
- Per-token capture times (5 s poll, indicative): 21.8, 34.6, 46.0, 57.5, 74.7, 92.0, 108.9, 127.7 s → per token 21.8, 12.9, 11.4, 11.5, 17.1, 17.3, 16.9, 18.8 s (combined7's R4M correctness run: 22.6, 11.0, 18.2, 16.9, 19.3, 20.4, 20.3, 18.1 = 146.8 s).
- Renderer RSS (MB): pre-run idle 1735, at token captures 1:3399, 2:4356, 3:4237, 4:4129, 5:3684, 6:4318, 7:3683, 8:3903, **peak 4414** (combined7 before: idle 1,846–2,033, token 1 3.5–3.9 GB, peak 5.7–6.0 GB in B5's clean-state runs; 4.3 GB in R5A's swap-pressured run — compare within one memory state only, B6 pairs).
- READY: created.
