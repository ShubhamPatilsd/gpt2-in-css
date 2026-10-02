# N2 — Tricks and hacks, 2026-09-13 (evening) → 2026-09-18 (the audit)

Blog-research slice: the scale-up from output-head micro-work to a real, autonomous 12-layer GPT-2-small running with no JavaScript, and the audit that showed most of that effort had targeted the wrong cost. Process log: `audit/2026-10-02/N2-tricks-sep13-sep18.log.md`.

## Citation key

All citations are `file:line` in `audit/2026-09-18/` unless they start with `experiments/` or `tools/`.

| Short | File |
|---|---|
| S3 | `S3-sessions-sep13b.md` (Sep 13, 18:12–23:31 local) |
| S4 | `S4-sessions-sep14a.md` (Sep 14, 00:03–04:48) |
| S5 | `S5-sessions-sep14b.md` (Sep 14, 05:22–15:04) |
| S6 | `S6-sessions-sep15-16.md` (Sep 15 13:04 → Sep 17 00:45) |
| S7 | `S7-sessions-sep17-18.md` (Sep 17 → Sep 18 early) |
| E4/E5/E6 | `E4-experiments-226-300.md`, `E5-…301-375.md`, `E6-…376-451.md` (experiment catalog) |
| SYN | `SYNTHESIS.md` |
| P2 | `P2-trace.md` (passive Chrome trace of the 12-layer bundle) |
| C2 | `C2-demo-cost-model.md` (structural model of the final bundle) |
| M1 | `M1-microbench.md` |
| C1/P1 | TinyStories cost model / profile (used only for the "43 MB/s" law) |

Session reports (S3–S7) are digests of Codex rollouts, so their numbers are *Codex's claims*, not re-measured. The audit files (P2, M1, SYN) were re-measured on 2026-09-18. "(inferred)" marks my own interpretation.

---

## 0. One-paragraph arc of this period

On Sep 13 evening the work was still an output-head contest: dozens of subagents shaving the 50,257-row vocabulary scan with GSUB glyph substitution, mixed-precision rows and certified fallbacks, and they ran into Chrome's hard numeric walls (the 32,768 px glyph-advance clamp, the 1/64 px layout lattice, the 8-bit truncation of numbered font features). On Sep 14 the user's pushback ("are you just drifting sideways… not actually ambitious enough", "dont change gpt 2 model architecture") set off a hunt for an asymptotic escape. Every index and search scheme failed, and an audit concluded the 12-block transformer, not the head, was about 90% of a token. Sep 15–16 measured the real problem ("the handoff, not the font matmul"), tried strange browser subsystems as calculators (relative colours, flexbox, transforms), then built the first autonomous no-JS 12-layer GPT-2 generator. It used 24-hour delayed CSS transitions as memory and one rendering graph reused for all 12 layers, and produced "Hello, I'm sorry, but I'm" at about 78 s/token and 53 minutes for 32 tokens. Sep 17 was a plateau: component wins kept failing to transfer. On Sep 18 the audit took the first passive Chrome trace. Arithmetic was about 5% of a token, style recalculation 55%, and frames, GC and the measuring observer itself made up most of the rest. It reduced everything to one rule, "the atom".

---

## 1. Tricks, chronological

Format per trick: **name** — first appeared · problem · how it works · outcome · blog-worthiness (1–5) · evidence.

### Sep 13 evening — the output-head wars

**1. GSUB numbered-feature row indexing ("let the font pick the row")** — first seen before this slice; the full 197-group build ran Sep 13.
- *Problem:* the exact fine scorer chose which 256-row score group to render via a 5 MB, 197-way `if(style(--group:N))` CSS dispatch.
- *How:* put every group's score glyph into one font as OpenType GSUB alternates and choose among them with `font-feature-settings: "cv01" <N>`, where N is a CSS-computed integer. The font engine does the selection, so the stylesheet no longer needs to branch. A CSS-only margin check certifies the top-two result and otherwise falls back to the exact scorer.
- *Outcome:* **abandoned.** Isolated switching was about 10× faster (21.9 vs 226 ms) and the certified hybrid 1.62× faster on 1,970 cases with zero unsafe accepts. Once composed into the six-stage head it was *slower* (0.73× / 0.84× / 0.66×), because the certificate grid added more layout than it removed. Lesson recorded: "the scalable optimization must remove an existing composed layout stage without adding a parallel certificate graph."
- *Blog:* 4
- *Evidence:* S3:48, S3:93–96, S3:98–108; E4:12, E4:15, E4:86.

**2. Hitting the 32,768 px wall, and "split the complement"** — Sep 13.
- *Problem:* Chrome clamps any single glyph's adjusted advance at exactly 32,768 CSS px (measured as 32,768.016). Big HVAR score glyphs silently saturated and decoded widths collapsed. Even the "exact" production baseline turned out to be clamped on 1,627 measurements, so it was "a different browser function".
- *How:* shrinking `font-size` (lattice-aligned display scales 0.09375 → 0.03125) avoided the clamp but changed which token won. The fix that survived is to split each oversized correction glyph into two glyphs whose integer advances, `floor(c/2) + ceil(c/2)`, sum to the original, each safely under the cap.
- *Outcome:* split-complement **retained (bounded)**: 20/20 winners, 5.5 vs 12.4 ms. The clamp itself became a permanent design constraint. Lattice scaling **rejected**.
- *Blog:* 4 (a concrete "browser has a hidden max-width-of-a-letter" moment)
- *Evidence:* S3:56, S3:64–70, S3:115, S3:118–123, S3:348; S5:91–95 (the same clamp later flipped "state 519").

**3. Display-lock gating ablation (`display:none` vs `content-visibility` vs `visibility`)** — Sep 13.
- *Problem:* the hybrid's fallback stage was expensive to switch on and off.
- *How:* gate whole subtrees with `content-visibility: if(style(--fallback:1): visible; else: hidden)` and compare against `display:none/grid` and `visibility`.
- *Outcome:* `display:none` and `content-visibility:hidden` tied (287 vs 289 ms). `visibility:hidden` was about 1.7× worse because it "keeps the exact grid hot" (still laid out). `content-visibility:hidden` gates later became the stage gates of the final pipeline, and the audit proved them one of only two real cascade cuts (trick 40).
- *Blog:* 3
- *Evidence:* S3:72–88; C2:50 (gate construct in final bundle); M1:188.

**4. Mixed-precision in-place hot rows** — Sep 13.
- *Problem:* best-first search visited groups 0/1 in about a third of states, and each visit cost a separate 256-row exact grid.
- *How:* replace the 512 coarse int10 rows of the two hottest groups *in place* with exact int16 rows carrying `round(score, 4px)` plus a tie code. Add a +24-bucket safety allowance on the outer wrapper so the coarse upper bound stays conservative. When the router picks group 0/1, reuse that anchor's width as the exact answer, with no extra grid.
- *Outcome:* **retained** as "a new best CSS output-head architecture": 0.720× (28% faster, 3.84 vs 5.34 s per argmax), 36/39 fine grids eliminated. The first attempt, with a corpus-fitted tie permutation, was 34% faster but wrong on all 10 fixtures.
- *Blog:* 2 (strong result, niche explanation)
- *Evidence:* S3:161–177, S3:179–192.

**5. Out-of-range HVAR advances + "virtual base"** — Sep 13.
- *Problem:* the two-plane (high/low) score encoding needed 12 glyphs per row. Could the range limits be bent instead?
- *How:* tiny probe fonts showed that HVAR deltas pushing a glyph advance negative (−10,000) or above 65,535 (95,000) are *not* clamped inside a text run. Isolated negative boxes report 0, so a same-run compensator glyph is needed. Stacked always-on bias regions give a ~500k-unit "virtual base".
- *Outcome:* a positive fact, but the downstream payoff died. The 12→6-glyph two-plane row was 2.8% faster and 1 bucket off, so it was rejected.
- *Blog:* 3
- *Evidence:* S3:214–219, S3:247–251; E4:41, E4:46.

**6. Token-level uncertainty gate — the negative result that pointed at the real cost** — Sep 13.
- *Problem:* if glyph shaping is the cost, render only the rows that can still win.
- *How:* 256 lightweight CSS gate carriers. A row is shaped only if `tokenUpper ≥ L`, which comes out to about 8 of 256 rows.
- *Outcome:* **reject-scaling.** Shaping 8 rows took 165 ms and shaping all 256 took 161 ms. The digest's own conclusion: per-mutation cost "is dominated by something other than glyph shaping… Codex did not investigate what". This is five days before the audit found out (style recalc). Building the gate also hit two limits: a 256-term `max(anchor-size())` computes to 0, so a 16×16 two-level reduction was needed; and a `calc()` missing spaces around `+` silently invalidated declarations.
- *Blog:* 5 as a story beat (foreshadowing)
- *Evidence:* S3:239–245, S3:357 (hypothesis H1).

### Sep 14 (early) — anchors, ties and alphabet tricks

**7. `max(anchor-size())` as a hardware-free argmax ("direct outer max")** — Sep 14 (built just before).
- *Problem:* reducing 197 group scores to one winner had gone through view-timeline readbacks.
- *How:* each group's score is an element width. The parent's width is `max(anchor-size(--g0 width), …)`, so layout computes the maximum. Fan-in has to stay ≤ ~98–99 terms (a 256-term `max()` returns 0), hence hierarchical fan-in-16 trees.
- *Outcome:* **kept.** Direct max was 0.772× vs timelines, and the fan-in-16 hierarchy gave a further −2.5%. "Direct anchor max replaced timelines −23%" is listed among the head optimizations that worked.
- *Blog:* 4
- *Evidence:* S4:32, S4:38, S4:44–45, S4:165–167; S6:122.

**8. Tie lanes in the sub-pixel residue ("lowest index wins")** — Sep 14.
- *Problem:* `max()` returns the winning *score*, not *which* element won.
- *How:* put identity in the low bits of the width. Group stride is 4 px and the residue `mod(width, 4px)` (≤ 255/64 px) holds a tie code, e.g. `code(g) = (197−g)·4px + mod(width(g), 4px)`, so equal scores resolve to the lower group. CSS has no `floor()`, so `round(down, …, 1)` is used instead.
- *Outcome:* the tie lane was **kept**. Packing score and full identity into ~10-megapixel widths was **rejected**: subpixel bits are lost (0.234 px error) and it ran 1.15–1.35× slower. G128 groups broke tie transport at every stride, which shows the 1/64 px lattice is the precision floor.
- *Blog:* 3
- *Evidence:* S4:33, S4:45, S4:50, S3:225–226; S3:349.

**9. Automatic optical-size handoff (`opsz`)** — confirmed Sep 13, re-examined Sep 14.
- *Problem:* nothing lets a glyph's measured width become another font's variation-axis value. `anchor-size()` inside `font-variation-settings` computes to `normal`.
- *How:* route width → `anchor-size()` → an inline-size container → `font-size: 100cqi` on a child. The browser's *automatic* optical sizing then sets the child font's `opsz` axis from its font-size, so a width turns into an axis value with no script.
- *Outcome:* exact, and 3,072 lanes ran in 262.5 ms, but it is a scalar handoff that needs one container per value. **Rejected as a bulk carrier.** Later called "the real missing feature" (font output → font input).
- *Blog:* 5 (genuinely surprising)
- *Evidence:* S4:16–20; E4:67; S6:273.

**10. GSUB radix selector (two features to beat 8-bit truncation)** — Sep 14.
- *Problem:* select one arbitrary row out of 50,257 from a CSS integer.
- *How:* first attempt was one base glyph with a 50,257-entry AlternateSet and `"cv01" N`. Chrome accepts the CSS but **shaping uses only the low 8 bits** of the feature value (32,768 → 0, 50,257 → 81). Fix: two features as base-255/198 digits (`cv01` = low+1, `cv02` = high+1) over 54,354 glyphs. The binary GSUB had to be hand-written because feaLib choked on 804k substitutions.
- *Outcome:* **works**: all test indices including 50,256, 0.3 ms warm two-hop switch, 308 KB WOFF2. Orphaned, because every neighbour-list generator that would use it (HNSW/IVF/LSH) failed.
- *Blog:* 4
- *Evidence:* S4:102–108, S4:190–191; E4:14.

**11. `min-content` widest-word argmax** — Sep 14 (idea resurfaced Sep 15 from the user: "isnt putting everything in a div and measuring the intrinsic div's width the best approach? prove me wrong").
- *Problem:* avoid one DOM element per vocabulary token.
- *How:* encode each candidate as an unbreakable "word" of private-use glyphs whose width is its score, separate words with spaces in ONE text node, and set `width: min-content`. Line breaking then makes the box exactly as wide as the widest word, i.e. the max. It needed U+2060 word joiners (min-content broke between PUA glyphs) and still hit the 32,768 px clamp.
- *Outcome:* **rejected**: 15–33% slower than per-element control at 1/4/16/64 groups. The full 197-group page never finished first layout in >180 s, and identity packing failed because a joiner cluster can't be split by `unicode-range`.
- *Blog:* 5 (beautiful idea, clear failure)
- *Evidence:* S4:130–135; S6:111, S6:114.

**12. Inline attention reducer (`font-size` = softmax weight)** — Sep 14.
- *Problem:* compute Σ pᵢ·Vᵢ in layout.
- *How:* each V value is a glyph with an HVAR advance. Set that glyph's `font-size` (or `zoom`) to its softmax probability, so the line's total width is base + Σ pᵢVᵢ.
- *Outcome:* exact (RMSE 3e-5) but **rejected**: 1.30–1.66× slower than flat CSS (`zoom` 4.19×), and still O(context × 768) glyphs. A `calc()` missing spaces around `+` first produced a false rejection.
- *Blog:* 4
- *Evidence:* S4:137–144; E4:50.

**13. Certified bound glyphs (blockwise → groupwise Cauchy)** — Sep 14.
- *Problem:* skip score groups that provably cannot win.
- *How:* one extra 96-axis HVAR "bound glyph" per row (later per 256-row group) whose width is a rigorous upper bound, `hᵀq + Σ_b ‖h_b‖·‖w_b − q_b‖`. Groups whose bound loses never open.
- *Outcome:* per-row version **rejected** (5.29× mutation cost to save about 3 groups). The groupwise version was **retained as coarse-pass only** (halves exact groups at ~0 cost), but every integrated cascade lost to the retained head (2.92 vs 2.71 s; production tails 8–14 s). Building it hit the clamp again: the bound font's base advance clamped before `calc-size`, so every width read 0 while `font-variation-settings` still "changed".
- *Blog:* 2
- *Evidence:* S4:152–158; S5:44–54; S6:124.

**14. Integer variation axes (`fvar` ±16384 + `round(nearest, h/R*16384, 1)`)** — Sep 14.
- *Problem:* Chrome quantizes axis coordinates to F2DOT14 (1/16384) internally, so the exact-int16 scorer drifted by up to 15 buckets.
- *How:* declare axes with integer user ranges ±16384 and round the CSS coordinate to an integer *before* it reaches the font. Chrome's normalization then becomes exact. Confirmed in source at `tools/build_gpt2_global_q16_layernorm_integer_full.py:506` (`"round(nearest, hidden/R*16384, 1)"`).
- *Outcome:* **works** (16/16 winners, 0 collapses). The six-font full-vocab bank (78.4 MB) was kept as an accuracy and cold-start profile, but **rejected as warm default** (+28.7% median).
- *Blog:* 3
- *Evidence:* S5:100–106; S5:188.

**15. SMIL stage scheduler (`<set>` + `:has()` as a no-JS clock)** — Sep 13 (built slightly before this slice; central from here on).
- *Problem:* without JS nothing can say "stage N is done, start stage N+1", and a one-shot evaluation of everything is huge.
- *How:* an SVG `<set attributeName="class" to="done" begin="X.animationend+0.001s">` fires when a CSS animation ends. `:has(#stage-N.done)` on an ancestor then flips a custom property that opens the next gate. CSS animations and SMIL take turns, like a two-phase handshake.
- *Outcome:* **kept.** −22–24% on two-block cold eval and a fully declarative head in 78 s. It is one-shot (it can't re-arm), which the later ping-pong loop solved (trick 30). The final bundle uses 211–835 SMIL `<set>`s.
- *Blog:* 5
- *Evidence:* E5:31, E5:116–117; S5:121; C2:45, C2:114; P2:62.

### Sep 14 (later) — the escape hunt and the moonshots

**16. Vocabulary-index escape attempts (HNSW / IVF / LSH / ball trees)** — Sep 14. *Dead end; one sentence in the blog.*
- Exact 99% recall needed about 24k row scores and **about 1,028 sequential hops** (instrumented hnswlib), which can't be unrolled in CSS. Under a 2k-row budget: IVF 83%, LSH 2.34%.
- *Blog:* 2
- *Evidence:* S4:91–128, S4:235.

**17. Chromium/Skia F16 filter patch (moonshot)** — Sep 14.
- *Problem:* SVG filters were 29× faster than fonts but quantize to 8 bits at every step.
- *How (proposed):* change about two call sites so filter intermediates are RGBA16F. `feComponentTransfer` still uses 256-entry byte LUTs.
- *Outcome:* **abandoned.** A Chromium build needs 100 GB of disk and there was 4.9 GiB free; it also breaks the "stock Chromium" rule. A standalone Skia probe later showed F16 is 20.5× more accurate but still off by 2.46%.
- *Blog:* 3
- *Evidence:* S4:149; S5:60–62; S7:105, S7:113; E5:27–28.

**18. Additive animations as matrix multiply (`animation-composition: add`)** — earlier probes (additive font matvec, Sep 12); researched Sep 14. *Dead end.*
- N animations × M properties sum into a dense projection, but Web Animations does the work on the main thread ∝ N×M, and `var()`-referencing properties can't go to the compositor.
- *Blog:* 2
- *Evidence:* S5:125; S4:68 (3,072→768 in 598 ms with a 47.3 MB stylesheet).

### Sep 15–16 — measuring the handoff, exotic calculators, the first full model

**19. Proving "transport, not math"** — Sep 15 (a measurement, not a trick).
- Splitting one MLP stage: font matmul + layout 134 ms (13%), exposing 3,072 widths +438 ms (42%), decoding to CSS numbers + GELU +480 ms (45%). For the same 9,216 glyphs: plain spans 111 ms → timelines 589 ms → decode 1,074 ms. A user-requested control (zeros vs big numbers) showed magnitude is irrelevant: 261.6 vs 256.6 ms.
- *Blog:* 4
- *Evidence:* S6:75, S6:78–79, S6:285; S7:170.

**20. Width+height packet carrier (48 exact bits per box)** — Sep 15.
- *Problem:* one geometry carrier per number was too many carriers.
- *How:* pack several small integers into an element's width *and* height. Decode with `round()`/`mod()` on `cqi`/`cqb` in a size container. 24 bits per axis are exact; 25 bits fails 510/1,024.
- *Outcome:* exact (0/24,576 failures after a digit-borrow decoder fix), but the packed MLP was **3.3× slower** than flat (986 vs 301 ms). "Nested decoding and dependency chain erase the packing benefit."
- *Blog:* 3
- *Evidence:* S6:69–70, S6:80–81, S6:103, S6:243.

**21. Relative-colour arithmetic (RGB channels as an exact calculator)** — Sep 16.
- *Problem:* find a precise compute primitive besides fonts.
- *How:* CSS relative colour syntax keeps computed channels unclamped at 1/65,536 spacing through 128 typed-colour boundaries. Each channel acts as a typed number, enough for a signed matmul → GELU → matmul.
- *Outcome:* byte-exact up to 384². At 768² it was exact but 533–661 ms with 30 MB of CSS (fonts: about 64 ms). "Precision yes, speed no." Abandoned.
- *Blog:* 5
- *Evidence:* S6:145, S6:212, S6:252.

**22. Flexbox softmax (`flex-grow: exp(score)`)** — Sep 16.
- *Problem:* softmax needs a sum of exponentials to normalize by.
- *How:* give each item `flex-grow: exp(score)`. The flex algorithm divides free space in proportion to the grow factors, which *is* softmax. Read the item sizes with `anchor-size()` to weight V.
- *Outcome:* exact (error < 1.6e-4). It beat untyped CSS but lost about 4× to typed `@property` staging (trick 24) and made no end-to-end difference ("fonts dominate"). Abandoned.
- *Blog:* 5
- *Evidence:* S6:146, S6:153–154, S6:253.

**23. Transform accumulators and shear → `anchor-size()`** — Sep 16.
- *How:* sum products by stacking `translate()`s; or shear an element so its bounding box encodes timeline progress, then read that with `anchor-size()` without materializing a scalar.
- *Outcome:* exact to 384², but 768² didn't render in 45 s and it ran 10× slower than `calc()`. The shear handoff (8/8 exact) was left as a niche idea.
- *Blog:* 3
- *Evidence:* S6:147–148, S6:254.

**24. Typed staging to stop `var()` text explosion** — Sep 16.
- *Problem:* attention's reducer cost 2 ms at 8 tokens, 548 ms at 16, 4.2 s at 32, and was invalid at 64.
- *How:* root cause: *unregistered* custom properties substitute their whole expression text, so the softmax denominator got re-expanded inside every term. Register each stage as a typed `@property` (max → exp → denominator → p) so values are computed once.
- *Outcome:* the 64-token reducer went from 6.56 s to about 55 ms on fresh input. (A claimed 4.4 ms was a cached-toggle artefact, another retraction.) No end-to-end gain at two tokens because fonts dominated; the idea stayed in the toolbox.
- *Blog:* 4 (a real CSS footgun)
- *Evidence:* S6:152–154, S6:255.

**25. Generation gates + `content-visibility` + sibling blocks + GELU easing curve** — Sep 16.
- *Problem:* the first connected 12-block hybrid took 203.8 s per warm update.
- *How:* gate stale intermediates with `content-visibility`, reset scratch variables, compact font runs, make blocks siblings with native residual bridges. Separately, evaluate GELU by sampling a **1,025-stop `linear()` easing curve**, using an animation timing function as a lookup table.
- *Outcome:* the ladder went 203.8 → 47.9 → 39.7 s, so the gates were **kept**. The easing-curve GELU cut isolated FC work 37% but end-to-end was unchanged (39.7 → 39.3 s), with no clear verdict (the later generator rejects easing with dynamic ranges).
- *Blog:* 4 (easing-as-GELU is very blog-worthy)
- *Evidence:* S6:50, S6:157, S6:256–257; S7:194.

**26. Delayed-transition memory (`transition-delay: 86400s`)** — Sep 16. **The core storage trick of the final pipeline.**
- *Problem:* CSS has no variables that *remember*. When the rule that wrote a value stops matching, the value is gone, and there are no JS arrays for a KV cache.
- *How:* register the property, then set `transition-duration: 1ms; transition-delay: 86400s; transition-timing-function: steps(1,end); transition-behavior: allow-discrete`. When the write rule stops matching, the property "transitions" back to its initial value, but the transition is stuck for 24 hours in its before-phase, holding the captured value. The pending transition *is* the memory cell. The same pattern latches tokens (`--saved-token-N`), the head input (`--h`) and loop banks.
- *Outcome:* **kept** (in source today: `tools/browser_gpt2_font_vector_cache.py:174`). Cost found later: 18,432 retained transitions per position in the scalar build (129,024 by position 8). The audit priced a retained animation at about 2.6× the restyle cost of a static value and put about 1.6 GB of RSS at position 8 down to them. Retiring producers through a transition bank (2 blocks 2.15 → 12.3 s) was not promoted.
- *Blog:* 5
- *Evidence:* S6:163, S6:168; C2:45, C2:51, C2:184–193; SYN:122, SYN:271–278; tools/browser_gpt2_font_vector_cache.py:174.

**27. The first autonomous no-JS 12-layer GPT-2** — Sep 16 (milestone).
- Page load → first token 110.8 s; then a median of 78.0 s per token; 8 tokens in 11 min 2.5 s; "Hello, I'm sorry, but I'm", 8/8 matching FP32. Shares: about 80% core+KV, 15% handoff, 3% head, 2% embedding. Before that, the staged 12-block flat chain (9.39 s, with external 768-value transfers) was the first genuine 12-layer measurement. The connected flat chain gave the wrong answer (RMSE 10.36, 217 s cold). Codex admitted "We've proven feasibility, but not practical performance."
- *Blog:* 5 (the payoff of the chapter)
- *Evidence:* S6:86–89, S6:165, S6:222; experiments/browser-gpt2/RESULTS.md:13–17, :46.

**28. One rendering graph reused ×12 via container style state** — Sep 16–17.
- *Problem:* 12 physical blocks meant about 182k elements and a 53-deep nest.
- *How:* emit the block once. The current layer index lives in `--layer` on a `container-name: corestate` element, and every layer's weights sit in `@container corestate style(--layer:L){…}` blocks. Layer L's rules match only while `--layer` is L, so one DOM graph runs 12 different layers.
- *Outcome:* **kept** (final bundle). 8 tokens went from 662 to 458 s at first (later 403 s with trick 29), with peak RSS up to about 6 GiB. 83% of the 88 MB sheet is these layer blocks.
- *Blog:* 5
- *Evidence:* S6:170–171; C2:49, C2:115, C2:118; S7:192–193.

**29. Font-vector KV cache + bilinear HVAR attention** — Sep 16–17 (bilinear primitive from Sep 12).
- *Problem:* 1,536 scalar KV properties per slot per layer.
- *How:* store each head's whole K or V as one `font-variation-settings` *string* (64-axis list) per (head, slot), 48 fields per layer per position. Attention scores come from a **bilinear HVAR font**: a variation region over two axes has support equal to the *product* of the two axis supports, so four sign-quadrant regions per coordinate make a glyph's advance equal Σ qᵢkᵢ. The glyph width is the dot product.
- *Outcome:* **kept**. 8 tokens in 6 min 43 s (from 11 min), RSS 3.86 GiB; the saved v1 run is 402.7 s. It needed a fix for "a Chromium glyph-width cap" (the 32,768 px clamp again, inferred). 32 tokens took 52 min 57 s, slowing from 57 s to 143 s per token.
- *Blog:* 5 (region-product = multiplication is a great reveal)
- *Evidence:* S6:172–173; experiments/bilinear-hvar-attention/RESULTS.md:8–21; C2:51; S7:192–193.

**30. Native ping-pong loop (re-armable no-JS clock)** — Sep 16.
- *Problem:* SMIL handshakes are one-shot. A token loop needs 12 layers × N tokens of repeatable stages.
- *How:* two saved banks hold vectors through delayed transitions, and an `animationend` → SMIL `<set>` → `:has()` handshake alternates between them. Each layer's output is written into the bank the next pass reads, using counters `--pass/--loop-ready/--loop-ack` and 384 pre-emitted SMIL `<g>` signal groups.
- *Outcome:* **kept** (`loop_parts`, reused by the core). About 55 ms per pass at width 2–3, 39 passes. The audit later found these handshake counters are inherited and written while all gates are open, a suspected whole-subtree restyle source.
- *Blog:* 4
- *Evidence:* E4:62–65; C2:48, C2:114, C2:162–163, C2:230.

**31. GC heap-growth flag (`--js-flags=--heap-growing-percent=10`)** — Sep 16. **Kept, then indicted.**
- *Problem:* renderer RSS of 5–6 GiB on a 16 GB Mac.
- *How:* tell V8/Oilpan to collect aggressively as the heap grows.
- *Outcome:* RSS 3,075 → 1,550 MiB (+5.5% latency); 8 tokens 662 → 458 s with the reused graph. It stayed in the validated harness flags. The audit found GC grows from 3.5% to 16% of each token and explains *all* of the per-token slowdown (trick 39).
- *Blog:* 4
- *Evidence:* S6:171; P2:43, P2:179–181, P2:390–392; SYN:47–49, SYN:119.

**32. Other Sep 16 storage/attention variants** — *short mentions.*
- Packed 3×16-bit KV expression cache: 26–33% faster with no RSS win. Compact attention via font-fallback run merging: −11%. Bounded 8-slot window: flat 0.42 s, but it changes the mask. avar2→Fontations engine switch escapes the 256-axis cap but is slower and less exact. SVG causal quality re-check: 2.64–3.9× FP32 perplexity, which closed the SVG line.
- *Blog:* 2
- *Evidence:* S6:169, S6:174–175.

### Sep 17 — local wins that don't transfer

**33. Per-head locality / `inherits:false` private subtrees** — Sep 17.
- *Problem:* changing one head's query restyled 923 elements.
- *How:* give each head a private subtree with `@property … inherits:false`, so a write stays local.
- *Outcome:* in the diagnostic, style time fell 16.4 → 2.7 ms (6×), 923 → 77 elements. Natively, all-12-head ownership was **+20% slower** (99.5 vs 82.7 s), because it added 2,340 geometry channels and 12 completion mechanisms. The selective reader was +29%, rule hoisting neutral. The audit later showed the principle was right (inherits:false is a complete cut) and the implementation had added transport instead of removing ancestry.
- *Blog:* 3
- *Evidence:* S7:54, S7:73, S7:83, S7:97, S7:176–177; C2:231; M1:188.

**34. GSUB glyph circuits (the font as a digital logic chip)** — Sep 17.
- *Problem:* "think very divergently". Could the font *compute* instead of only scaling?
- *How:* glyph identity is state. Ligature/contextual substitution lookups implement adders, nonlinear tables and running totals, e.g. a 4-digit base-16 running total for `3a−2b+5c+d` evaluated entirely during shaping. Only the final glyph's width goes back to CSS.
- *Outcome:* a depth-16 reversible 2×4-bit cell beat direct CSS (6.5 vs 10.2 ms), the only font-circuit win ever. Weighted sums ran 5–250× slower than CSS. HarfBuzz and Chrome reject a font with ≥16,384 subtable references (16,383 ok), and glyph count caps at N≈241 inputs. **Rejected** as a matrix replacement. An explainer page was built.
- *Blog:* 5
- *Evidence:* S7:109, S7:126, S7:134–150, S7:153–154; E4:10–11, E4:19–24, E4:78–81.

**35. SVG Porter-Duff alpha bit-circuits** — Sep 17.
- *How:* Boolean gates out of `feComposite` operators (`in`/`xor`/`out`/`over`) on alpha masks, i.e. an exact ripple adder inside the compositor.
- *Outcome:* 8/16/32-bit adders exact; a 32-bit add took 2,756 ms with **zero style recalcs** and about 2 GB RSS. A connected 2-D matvec painted nothing. **Rejected.**
- *Blog:* 5 (pure hacker joy)
- *Evidence:* S7:111, S7:125; E5:36.

**36. Fused attention font via avar2; learned glyph codes; AAT `morx`; TrueType bytecode; TTC fragments** — Sep 17 (bytecode/TTC probes earlier). *Dead ends, one line each.*
- avar2 attention font: 4–5× slower, and its calibration doesn't carry across layers. Learned glyph codebooks: 35.8% error. AAT `morx` substitution doesn't run in Chrome. TrueType hinting bytecode (`GETVARIATION`, `MUL`…) isn't executed on Chrome/macOS. `url(bank.ttc#Face)` fragments are ignored (always face 0).
- *Blog:* 3 (as a rapid-fire list)
- *Evidence:* S7:110, S7:112, S7:153; E6:81–82.

**37. Connected sparse-avar2 GELU MLP** — Sep 17 (primitive from Sep 13).
- *How:* apply GELU *once per axis* inside the font using avar2's axis-remapping table (piecewise map), then use two linear HVAR regions for the projection. Confirmed 251 ms / 3.64 MB isolated vs 311 ms / 12.53 MB for GELU repeated in HVAR rows (`experiments/avar2-gelu-linear-hvar-full-mlp/RESULTS.md:26–29`).
- *Outcome:* connected in situ it was +17–19% slower, used 1.8× RSS, and failed the layer-1 error bound. **Rejected** for the pipeline.
- *Blog:* 4 (GELU inside a font-axis remap is a great image, despite the loss)
- *Evidence:* S7:163; E4:61; S4:177.

**38. Dense consumer chunk 512→128 / static bank readers** — Sep 17–18.
- Component wins of −15–19% (QKV/MLP) and −9% (loop) were bit-identical, but **no native pair beat baseline** (81.1 vs 75.7 s). The baseline itself swung 75.7 → 47.3 s across pairs on identical bytes, during sleep and battery events.
- *Blog:* 3 (the variance story)
- *Evidence:* S7:199–218.

### Sep 18 — the audit's mechanisms (what actually matters)

**39. View/scroll-timeline readback — the hidden villain** — origin Aug 29. It was the transport throughout this period and is indicted on Sep 18.
- *How it worked:* each producer glyph is the subject of a named `view-timeline`. The consumer runs an animation on that timeline and decodes `width = 100/progress − 100`. This was the standard geometry → number bridge.
- *What the audit found:* each timeline boundary costs **one extra frame, one style pass and one layout**, and every frame re-restyles the downstream chain. Container-query units and `anchor-size()` resolve a 12-deep chain in **one** pass with 0 extra frames. On the demo: about 110k `ScrollTimeline` invalidations, 85 frames and 171 passes per token. Per-frame overhead (paint lifecycle, animation servicing, prepaint, hit test) is about 144 ms × 85 ≈ 12 s of a 44 s token.
- *Blog:* 5
- *Evidence:* E6:87; SYN:44–46, SYN:243–257; P2:23, P2:32, P2:387–389; M1:190–192.

**40. The only two cascade cuts: `inherits:false` and display locks** — measured Sep 18.
- With N descendants not reading the changed property: `inherits:false` costs 0.001× and a `content-visibility:hidden` wrapper ≤ 0.002×, while `contain: style`, shadow roots and flattening all cost 1.00×. "Do not inherit what is not read, and display-lock what is not active."
- *Blog:* 5 (directly actionable for web devs)
- *Evidence:* SYN:204–215; M1:188–189.

---

## 2. The audit's big reveal (story beat)

**Setup.** By Sep 17 there was a working no-JS GPT-2-small, about 78 s/token by Codex's numbers, and a pile of about 450 experiments (SYN:41). Codex's own retrospective said "There is no demonstrated faster combination waiting to be enabled… but no evidence that the current combination is optimal", and it had observed "zero complete six-boundary passes out of 24" when it tried to attribute cost (S7:190, S7:196). Nobody had taken a passive trace.

**Beat 1: the measuring stick was bent.** P2 re-ran the pinned 8-token bundle with no observer and got 325 s, i.e. **40.7 s/token**. Codex's runner had polled `DOM.getBoxModel` every 100 ms, and each poll forced style and layout. That inflated every 12-layer number by about **22%** (P2:8–15, SYN:20–21). The same check found that the "78 s/token" headline came from a *different, unpinned, older* bundle (C2:7–17).

**Beat 2: the math is 5%.** In a traced token (mean 44 s): style recalculation 55.6%, layout 13.6%, and **text shaping, which is where the font matmuls actually happen, 5.0%**. Paint lifecycle was 12.4% (actual `Paint` 0.03%), animation servicing 8%, and **3% was hit-testing Chrome's synthetic mousemove because the cursor was resting where "Run" had been clicked** (SYN:28–36; P2:16–22, P2:384–385). "Everything Codex spent Sep 12–17 optimizing (font shards, glyph counts, GSUB, avar2, SVG) lives inside that 5%… they were shaving the wrong term" (SYN:40–43). About 80% of the Sep 13–14 effort had gone into the output head, which is 3–10% of a token (SYN:110).

**Beat 3: the slowdown was the garbage collector.** Tokens got slower over a run (57 → 143 s in the 32-token run), which everyone had read as context growth. But style minus GC is flat at 20.4 ± 0.6 s per token, and GC grows from 3.5% to 16%. The `--heap-growing-percent=10` flag added on Sep 16 to save RAM is implicated (P2:16–21, P2:390–392; SYN:47–49).

**Beat 4: the atom.** "Blink re-resolves an element's entire declared custom-property set whenever that element is style-dirtied, at ≈40–50 MB of declaration text per second, and it dirties every descendant of a changed inherited property unless a display lock stops it" (SYN:78–81). M1's 81 synthetic no-JS pages fit it with R² ≥ 0.999: about 4.45 µs per element + 36.5 ns per byte. Whether a declaration depends on the changed input barely matters; a `@function` call costs 2.2× an inline calc (SYN:190–236). That one rule explains "connected = 4× isolated", "component wins never transfer" and "every extra dependent pass costs more than it saves" (SYN:83–94).

**Beat 5: the diagnosis had been made, then mis-acted on.** Codex said "transport, not math" on Sep 13 but "attacked it by inventing new carriers (fonts, anchors, timelines, counters, grids, SVG) instead of shrinking what each carrier makes Blink re-evaluate. The carriers were never the atom; the declarations on them and the frames between them were" (SYN:96–99). The token-gate result on Sep 13 (trick 6) and the Sep 15 trace of the head (shaping 21.8%, S6:121) had both pointed there.

**Coda (honesty note).** The audit's own biggest predicted fix (slim the dense leaf declarations, −8 to −12 s) was **downgraded the next day**. Blink's MatchedPropertiesCache shares identical declaration sets, so the byte law applies only to per-element *unique* `var()` work. The weight moved to taking timeline frames out of the loop and to `inherits:false` handshakes (SYN:120, SYN:126). That makes a good blog caveat: even the audit's first law needed a correction.

---

## 3. Dead ends worth one sentence each

- **Vocabulary search (HNSW/IVF/LSH/ball tree):** GPT-2's exact winner is too query-sensitive; 99% recall costs about 1,028 sequential hops (S4:128, S4:235).
- **Position-try as argmax (`position-try-order: most-width`):** 2× faster, but it ranks placement space, not the encoded score, and picked index 4 when index 9 was the max (E5:17).
- **Sibling-index router:** source 48% smaller, cold load only 2.2% better (E5:24).
- **Grouped/low-rank/trained heads and MLPs:** killed mid-run by "GPT-2 architecture must not change" (S4:88).
- **Grid-track readback via `getComputedStyle`:** 3,072 values in about 110 ms, but it needs JavaScript (S4:69).
- **float16 canvas + SVG filter:** precise, but needs a JS driver (S6:140).
- **Progressive precision q10→q12→q16:** 45% fewer glyphs, 5% slower; one extra dependent pass costs more than it saves (S5:86–89; S6:125).
- **Prewarming V before the score gate:** +14% slower (S7:62).
- **LayerNorm folded into weights (uncentered):** 189/264 stress cases fail; the centered version passes offline but was never browser-validated (S7:178, S7:201).
- **SVG as compute engine:** 251 ms for 12 blocks but 8-bit everywhere, 2.6–3.9× perplexity (S6:175; E5:42).
- **Font-metric (`ch/ic/cap/lh`) transport at 768:** 924 fonts, 2.83 GB RSS (S3:148).

---

## 4. Memorable moments (quotes and incidents)

- User, Sep 14: "ok where are things? are you just drifting sideways with supposed fixes… not actually ambitious enough" and "wait uh dont change gpt 2 model architecutre" (S4:138, S4:242).
- User, Sep 15: "isnt putting everything in a div and measuring the intrinsic div's width the best approach? prove me wrong"; later "ok in like 8 words what are we trying to fix here", answered "Speeding up CSS's painfully slow final-token selection." (S6:111).
- User, Sep 16: "with flat mlp what are total times on each step of the flow. dont bullshit me"; "if you dont finish in the next 6 hours you will die… find something that scales right now"; "why is it taking an hour for only 32 tokens?" (S6:63, S6:136).
- User, Sep 17: "uh are you sure this is the case my computer fell aslepe". Sleep and battery events had contaminated runs; baselines swung 60% on identical bytes (S7:187, S7:218).
- **A missing space before `+` in `calc()`** silently invalidated declarations at least five times and produced fake speedups and false rejections. The audit recommends a build-time lint (SYN:303–305; S5:69, S5:213).
- **A Cursor MCP process at 99% CPU for 11+ days** ran in the background of all Sep 13 benchmarks (S3:176).
- **Disk:** 333 MB free on Sep 16. The experiment tree was 11.95 GB in 41,301 untracked files, and 1,204 TTFs took 4.84 GB (S6:43, S6:180).
- **A `display:none` page still downloaded 13 MB of fonts:** font loading follows style matching, not layout (S3:175, S3:359).
- **Even the audit's harness had the classic bug:** M1's quiescence check sampled its baseline after the mutation, so every trial looked like "no recalc" (M1:24–27).
- **The shipped TinyStories page couldn't get past token 1:** two builders overwrote the same `streaming.css` and lost the gate rule (SYN:22–24).

---

## 5. Suggested chapters for this period

1. **"The Head Wars"** (Sep 13 evening – Sep 14 morning). GSUB alternates as row selectors, the 32,768 px glyph clamp, split complements, mixed-precision hot rows, `max(anchor-size())` argmax with sub-pixel tie lanes. End on the token-gate surprise: shaping 8 rows costs the same as shaping 256 (tricks 1–8).
2. **"Escape Velocity"** (Sep 14). `opsz` handoff, the GSUB radix selector, `min-content` widest-word argmax, `font-size`-weighted attention, and vocabulary-search attempts that all failed. "Don't change the architecture", the F16 moonshot that needed 100 GB of disk, and the realization that the transformer is 90% (tricks 9–18).
3. **"Calculators Hiding in the Browser"** (Sep 15–16 morning). Proving "transport, not math", then relative colours, flexbox softmax, transforms and typed `@property` staging as compute primitives (tricks 19–25).
4. **"Twelve Layers, Zero JavaScript"** (Sep 16–17). Delayed transitions as memory, the SMIL/`:has()` clock and ping-pong loop, one graph reused across 12 layers via container style queries, bilinear font attention. 78 s/token and 53 minutes for 32 tokens, then a plateau of local wins (locality, GSUB circuits, alpha circuits) that wouldn't transfer (tricks 15, 26–38).
5. **"The Trace"** (Sep 18). The observer that added 22%, arithmetic at 5%, a mousemove costing 3%, a GC flag behind the slowdown, timelines costing a frame each, and the one-sentence "atom" of Blink style cost, with its next-day correction (tricks 39–40 and §2).
