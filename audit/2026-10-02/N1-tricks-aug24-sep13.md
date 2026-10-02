# N1 — Tricks & hacks, 2026-08-24 → 2026-09-13 (first half)

Blog-research slice. Read-only except this file and its `.log.md`. No browsers launched, nothing timed.

## Conventions
- **Dates are local (PDT)**. Commit times come from `git log`, which is already local. Codex session times in S1/S2 are UTC; I converted them (−7 h). So S1's "08-25 04:07Z" is 08-24 21:07 PDT. Where the conversion moves the date, I give the local date.
- **Slice boundary.** "First half of Sep 13" means up to the end of S1 F19-C (09-13 19:39Z = 12:39 PDT). S2's S-05 thread starts at 19:41Z. I only mention its Sep-13 PM items as teasers at the end.
- **Citation shorthand.** `S1 F3#1572` means audit/2026-09-18/S1-sessions-aug-sep08.md, session F3, rollout ordinal #1572. `S2 S-04c:2247` means S2-sessions-sep11-13a.md. `E1 #19` means E1 experiment-catalog row 19. File paths are relative to the repo root.
- **Score** = blog-worthiness from 1 to 5 (surprise × clarity).
- **(inferred)** marks claims I did not see stated directly in a source.
- **Commits.** All 24 commits fall on 08-24 → 08-26 (`8f189b3` … `8945a2d`). From 08-26 to 09-13, *nothing* was committed. That work exists only in untracked `experiments/` and Codex sessions (S1 F19: "Nothing in this file was committed", 640 MB rollout).

---

## Part A — Trick catalog (chronological)

### Day 1, morning (Aug 24): a spreadsheet that thinks

**T1. `calc()` matmul. Every neuron is a `calc()` sum.** First seen 08-24 12:02 (`8f189b3`).
- *Problem:* CSS has no arrays, loops or matrix operations.
- *How:* Python writes every weight and input pixel out as a custom property. Each hidden unit is one long `calc(bias + x0*w0 + x1*w1 + …)`. ReLU is `max(0, …)`. The class with the widest bar wins.
- *Outcome:* **Kept** as the base layer. MNIST scored 92.17% as a linear model and 96.14% as a 784→16→10 MLP (S1 F1#220,#394). For O(n²) matrices it was later demoted, because "parsing 5.25 million CSS terms is the bottleneck" (matrix-scaling/RESULTS.md:136). Rule adopted: use direct CSS only for O(width) work like LayerNorm, GELU and residuals (matrix-scaling/RESULTS.md:142).
- *Score:* 4. *Evidence:* README.md:15-26; `8f189b3`.

**T2. `:has()` radio buttons as the input device.** First seen 08-24 12:02 (`8f189b3`).
- *Problem:* without JavaScript there is no event handling and no input.
- *How:* ten radio inputs, one per test digit. Rules like `:root:has(#prompt-3:checked) { --x-000: … }` swap the whole input vector when you click.
- *Outcome:* **Kept as a pattern.** It returns later as the select picker (T9) and the Edit/Run/Pause lifecycle (T25).
- *Score:* 3. *Evidence:* README.md:28-30; tools/build_pretrained_gpt2.py:600,605.

**T3. `@property` registration as a "materialize" instruction.** First seen 08-24 12:09 (`8a59db0`).
- *Problem:* plain custom properties substitute their *expression text* recursively. The transformer graph "expands until later calculations become invalid".
- *How:* register every intermediate with `@property { syntax: "<number>" }`. That forces Chrome to compute and store a number instead of pasting text forward.
- *Outcome:* **Kept** everywhere. Its byte cost became its own problem: 37–43% of CSS was `@property` boilerplate (S1 F3#508).
- *Score:* 4. *Evidence:* FULL_GPT2.md:37-39; S1 F1#494,#514.

**T4. Chunking one giant `:root` rule.** First seen 08-24 12:16 (`1ad8aa4`).
- *Problem:* tiny-gpt2 put 154,000 assignments in one rule. The third dependency silently fell back to its initial value.
- *How:* split the graph across many `:root` blocks.
- *Outcome:* **Kept**. Minor.
- *Score:* 2. *Evidence:* S1 F1#647,#673.

**T5. `@function --gelu()` (Chromium 139 custom functions).** First seen 08-24 12:34 (`c328e4c`).
- *Problem:* each GELU needed five or six globally registered temporaries.
- *How:* one reusable typed CSS function holds the temporaries locally. Pretrained CSS went from 28.66 to 10.90 MB and typed properties from 154,197 to 51,980 (OPTIMIZATIONS.md:6-11).
- *Outcome:* **Partially kept.** Chrome invalidated deeply nested function chains: generation fell back to 0 at feedback step 3. Deep graphs therefore re-materialize GELU (OPTIMIZATIONS.md:24-27; S1 F1#1747). The recurring lesson is that `@function` has depth and size limits.
- *Score:* 3. *Evidence:* OPTIMIZATIONS.md:20-30.

**T6. Finite-domain dead-output elimination.** First seen 08-24 12:34 (`c328e4c`).
- *How:* the demo had only three fixed prompts, so it only needed selectors for the tokens those prompts could produce.
- *Outcome:* **Superseded within two hours by T7.**
- *Score:* 1. *Evidence:* OPTIMIZATIONS.md:32-41.

**T7. Convex-hull dead-logit elimination.** First seen 08-24 14:41 (`4ac203c`).
- *Problem:* computing 50,257 logits per token, and the full-vocabulary build ran the disk out of space (S1 F1#1552).
- *How:* tiny-gpt2's tied head is 2-dimensional. A token can only win an argmax if its embedding is a vertex of the convex hull of all embeddings. Only 16 of 50,257 are, so the other 50,241 logits are mathematically dead and are never emitted.
- *Outcome:* **Kept for the toy and useless at scale.** One-token CSS went from 10.9 MB to 23.7 KB. The 4-token benchmark went from 57.2 MB to 359 KB (561 KB with the full decoder) and ran at 500–615 tok/s (S1 F1#1616,#2002). The authors warned at the time that in 64 or 768 dimensions "most points are on the hull" (OPTIMIZATIONS.md:51-53; MODEL_CANDIDATES.md:42-44). The user's reaction: "what convex optimization shit did it do" (S1 F2#65).
- *Score:* 5. Pure "wait, what?" geometry, and an honest dead end at scale. *Evidence:* README.md:72-74; tools/build_pretrained_gpt2.py:100,577.

**T8. `<select>` + `option:checked` + `:has()` token picker.** First seen 08-24 14:54 (`de75b61`).
- *Problem:* CSS cannot read a text input's live value, and `attr()` reads only markup attributes (README.md:119-125).
- *How:* one native `<select>` per prompt position. Generated `body:has(#prompt-N option[value=T]:checked) .model { … }` rules map each token ID to its embedding.
- *Outcome:* **Superseded by T19/T20.** It had to be capped at 2,066 tokens because ":has() must continually match thousands of option rules" (S1 F1#2258). Each position cost about 253 KB (OPTIMIZATIONS.md:55-62).
- *Score:* 3. *Evidence:* tools/build_pretrained_gpt2.py:1481.

**T9. Animation-latched recurrent clock (the x86CSS trick).** First seen 08-24 15:24 (`8dbecde`).
- *Problem:* CSS has no time and no mutable state. Everything resolves at once, so a static page "computes everything up front" (user, S1 F1#2491).
- *How:* a four-phase CSS animation clock alternates paused `execute` and `store` animations. The animations copy the newest winner, the context count and a growing `content` buffer into unregistered custom-property "banks". The next cycle's transformer reads those banks. One 1.51 MB circuit runs forever over a 16-token sliding window, about one token per 1.2 s cycle. This is credited to rebane2001's x86CSS.
- *Outcome:* **Superseded by T15.** Scaled to TinyStories it needed an 8 s clock (4 s and 6 s clocks corrupted state). That gave 42.69 s for 4 tokens. Then the user's own run failed: the step counter regressed from 1 to 0. Codex admitted "I overstated its stability… only a timing workaround" (S1 F3#2475,#2845,#2862).
- *Score:* 5. Animations as flip-flops is a great image, and the failure makes a great reveal. *Evidence:* OPTIMIZATIONS.md:64-72; README.md:105-117; tools/build_pretrained_gpt2.py:1301-1307; tinystories/RESULTS.md:222-236.

**T10. Exact KV cache, plus the `inherits:false` A/B.** First seen 08-24 16:40 (`7996961`).
- *How:* the compiler emits only the newest position's pass and stores K/V as state. Median time fell from 5.4–5.6 ms to 2.3 ms (2.35×) and CSS from 572 to 265 KB.
- *Outcome:* **Kept.** All of the gain came from the KV cache. `inherits:false` was neutral on this tiny DOM (S1 F3#339,#403). The idea comes back with force a month later (SYNTHESIS §8.2: `inherits:false` = 0.001× restyle cost).
- *Score:* 2. It is a standard ML trick, but the `inherits:false` foreshadowing is useful.

### Day 1, evening (Aug 24 PDT; S1 F3; commit `756a408` 21:42): the real model, TinyStories-3M

**T11. "Registered properties are eager, `@function` bodies are lazy."** First seen 08-24 evening.
- *Problem:* branch-and-bound needs to skip work, and CSS evaluates everything.
- *How:* probes showed that a 50,257-row graph behind an unselected `if()` branch still ran (1.71 s on both branches), while an unselected `@function` was never resolved (0.2 ms). The catch is that one function can reduce at most 1,280 rows; at 1,536 the result goes invalid.
- *Outcome:* **The finding behind T12.**
- *Score:* 4. *Evidence:* output-head-benchmark/RESULTS.md:91-98; S1 F3#1038,#1098.

**T12. Exact lazy clustered output head (Cauchy–Schwarz pruning).** First seen 08-24 evening (`756a408`).
- *Problem:* the 50,257×64 head is 89% of TinyStories' multiply-adds (S1 F2#496).
- *How:* cluster the token embeddings into 256 balls, each with a centre and radius. CSS eagerly computes 256 cheap bounds, `dot(h,centre) + |h|·radius`. Lazy `if()` then calls only the cluster `@function`s whose bound can still beat the seed cluster. This is exact search, not a reduced vocabulary.
- *Outcome:* **Kept for TinyStories.** Latency was 755 ms vs 4.3 s (5.7×) on 35 deliberately hard states, but at 278–292 MB of CSS and ~1.28 GB RSS. Loading a second copy killed the renderer (output-head-benchmark/RESULTS.md:50-54). In the GPT-2 era it was superseded by the HVAR head plus Grid argmax (T44/T45).
- *Score:* 4. *Evidence:* output-head-benchmark/RESULTS.md:9-21,56-70.
- *Sub-trick, shared dot functions:* defining each token score once cut the head from 292 to 213 MB and the step from 862 to 670 ms (OPTIMIZATIONS.md:86-93).

**T13. "DOM as an argmax": intrinsic sizing computes max(). First tried 08-24.**
- *How:* make one element per token, give each a width equal to its score, and let the container's intrinsic size be the maximum.
- *Outcome:* **Rejected on Aug 24.** It was 2.4× slower, used 1.46 GB RSS, and "cannot feed the winning numeric embedding back" (output-head-benchmark/RESULTS.md:99-101). **Revived on Sep 13 as T44, CSS Grid argmax.** That arc is worth a callback in the post.
- *Score:* 3 on its own; the callback raises it.

**T14. CSS-only token decoder.** First seen 08-24 evening.
- *How:* bucketed rules map any winner ID to its GPT-2 text through `content`.
- *Outcome:* **Kept.** Covers all 50,257 tokens; the handoff plus decoder is 2.5 MB (tinystories/RESULTS.md:41-46). There was a bug: an unescaped control character in the decoder broke parsing (S1 F4#118).
- *Score:* 2.

**T15. Nested-element cascade as the clock (timer-free sequencing).** First seen 08-24 ~20:30 PDT (S1 F3#2957–#3183; `756a408`).
- *Problem:* the animation clock (T9) raced the style engine.
- *How:* predeclare N nested `.model` elements. A bridge element between each pair snapshots the parent's typed outputs, and the child inherits them as its embedding and KV cache. **Parent→child inheritance is a dependency barrier**, so stage N+1 cannot read half-written state. Every stage reuses the same 213 MB of rules, and only about 835 KB of handoff CSS grows.
- *Outcome:* **Kept.** This is the backbone of `nested.html`, `streaming.html` and `dynamic.html`, which is today's `tinystories/dynamic.html` (README.md:161-169). The live demo probably still uses staged nesting (inferred from project memory "demo-c32 = cap 36 → 32 new tokens"; not verified in this slice). The limit is that HTML must predeclare one element per output token, so generation is finite.
- *Score:* 5. "The cascade itself is the sequencer" (tinystories/RESULTS.md:32-36) is the thesis of the post.

**T16. `content-visibility` gates + 1 ms animation ticks + CSS Pause/Play.** First seen 08-24 ~21:30 PDT (S1 F5#186; `81a92ff`).
- *Problem:* the nested page resolved all 16 tokens before first paint ("it kind of just all loads at once", S1 F4#256), so nothing streamed.
- *How:* each later stage starts `content-visibility: hidden`, which means Chrome skips its style work. An `@container style(--winner-id)` query on the parent's computed winner starts a zero-delay **1 ms** registered-property animation. That flips `--gate-open`, and the child becomes `visible` and eligible for style. The 1 ms is "the smallest practical animation tick that keeps stages in separate style passes". A checkbox drives `animation-play-state`, which gives a CSS-only Pause/Play.
- *Outcome:* **Kept.** 16 tokens painted progressively at 1.17 visible tok/s (12.83–12.89 s for 15 tokens). Caveats: you cannot interrupt an in-flight recalc, and inspecting a hidden subtree's computed style wakes it up (S1 F5#174).
- *Score:* 5. *Evidence:* README.md:171-180; tinystories/RESULTS.md:54-71; tools/build_tinystories_nested.py:131,143 (`content-visibility:if(style(--gate-open:1):visible;else:hidden)`).

**T17. 24-bit packing, and the typed-number precision cliff.** First seen 08-24 ~22:00 PDT (`81a92ff`, `9a83fde`).
- *Problem:* 120.6 MB of the 213 MB head was 64 lookup tables mapping winner ID → embedding (S1 F5#405).
- *How:* quantize the feedback embedding to 8 bits per coordinate and pack three coordinates into one integer, recovered with division and `mod()`. Six-in-48-bit failed. The probe `tinystories/css-number-precision-test.html` showed that `calc()` arithmetic is exact, as are unregistered properties and untyped `@function` returns. Corruption happens only at a **typed boundary**: registered `<number>` keeps about 24 bits, and `<integer>` clamps at 2³¹−1.
- *Outcome:* **24-bit typed kept.** The head went from 213 to 128.7 MB, the page from 237 to 152.6 MB, and RSS from 2.32 to 1.66 GB (−28.35%), with all tokens still correct (tinystories/RESULTS.md:95-124). Untyped 48-bit was exact but **27% slower** (0.85 tok/s) and was rejected. A typed 4×6-bit variant diverged at token 6. "24 exact bits in typed `<number>`" became a permanent Chrome limit in the design rules (SYNTHESIS §7).
- *Score:* 4. *Evidence:* README.md:182-213.

**T18. Shortest-number spelling + Brotli precompression.** First seen 08-25 01:48 (`566507c`).
- *How:* `0.5→.5`, `0.000001→1e-6`, plus a tiny static server that negotiates `.br`/`.gz`. Raw size went from 152.68 to 148.93 MB, and Brotli to 28.93 MB.
- *Outcome:* **Kept, but it helps transfer only.** The painted A/B was within 1% (noise). Arithmetic coding was rejected because "CSS itself cannot turn a bitstream into new stylesheet rules" (S1 F5#2264). Lesson: "Brotli reduces network transfer, but Chromium still expands and parses the raw CSS" (OPTIMIZATIONS.md:194-195). A later microbenchmark explained why numerals don't matter: cost tracks the count of terms and `var()`s, not bytes (SYNTHESIS §8.3).
- *Score:* 2.
- *Related:* row-int10 head quantization (`6d15257`) was +17% tok/s with 320/320 decisions correct. It stayed opt-in because it changes the checkpoint (OPTIMIZATIONS.md:203-217). Score 2.

### Day 2 (Aug 25 PDT): typing into a stylesheet

**T19. `<style contenteditable="plaintext-only">` as a text box.** First seen 08-25 ~01:40 PDT (S1 F6#82; `4bee819`).
- *Problem:* "is there any way a user can type in a custom prompt… without needing js" / "surely theres a way to pass shit to the css" (S1 F6#8,#33).
- *How:* make a visible `<style>` element editable. Whatever the user types is reparsed live as CSS, e.g. `.prompt-source { --prompt: "Once upon a time"; }`. The user's text becomes a custom-property string with zero script.
- *Outcome:* **Kept** and still the only input channel (E1 §J). On its own, CSS can compare whole strings but cannot split them, which is why T20 exists.
- *Score:* 5. Funny, legal, and it makes readers want to try it. *Evidence:* experiments/editable-style-input.html; tools/build_tinystories_dynamic.py:371-372; experiments/CSS_TOKENIZER_FEASIBILITY.md:16-25.

**T20. OpenType GSUB BPE tokenizer.** First seen 08-25 02:56 (`4bee819`).
- *Problem:* splitting a string into GPT-2 BPE tokens with no loops and no string functions.
- *How:* `content: var(--prompt)` renders the prompt in a generated font. The font's GSUB table encodes GPT-2's byte vocabulary and all 50,000 ranked merges. So **the text shaper (HarfBuzz) performs BPE** while laying out glyphs. Positional features `p000`–`p003` erase every token except the requested position. A naive 50,000 lookups hit a GSUB limit after a 233 s compile. Batching consecutive merges with disjoint glyph sets gives 2,782 lookups that compile in ~7 s, and the font is 1.6 MB.
- *Outcome:* **Kept.** 296 font-vs-Python comparisons over 37 prompts passed, with 81–270 ms per prompt update. It is limited to 4 tokens of printable ASCII; an 8-position version hit the GSUB offset limit (S1 F7#1708).
- *Score:* 5. Probably the single most delightful trick in the slice. *Evidence:* experiments/CSS_TOKENIZER_FEASIBILITY.md:27-56; S1 F6#742,#805,#1242.

**T21. Glyph width carries the number, as base-32,767 "digits".** First seen 08-25 (`4bee819`, `aaeddb8`).
- *How:* the surviving glyph's advance width *is* the payload. For width-2 tiny-gpt2 the payload was an embedding coordinate, `advance = round((e+0.1)·160000)+1`. For TinyStories it is the token ID. HarfBuzz treats advances above 32,767 as signed, so two fonts encode each ID as two base-32,767 digits.
- *Outcome:* **Kept.** This is also the seed of the whole font-compute era (T27).
- *Score:* 4. *Evidence:* CSS_TOKENIZER_FEASIBILITY.md:34-40; OPTIMIZATIONS.md:221-226; S1 F7#1442.

**T22. Geometry → number readback (`anchor-size()` → size container → `100cqi` → registered property).** First seen 08-25.
- *Problem:* CSS can measure layout but cannot get a width back as a number.
- *How:* Anchor Positioning copies the text run's intrinsic width onto a nested size-query container. Inside it, a registered property computes `calc(100cqi / 1px …)`, which is a plain number again.
- *Outcome:* **Kept. It is the bridge under every font trick that follows.** Its limits became the project's main wall:
  - `anchor-size()` is never accepted directly in registered numbers, typed `@function`s or `font-variation-settings` (matrix-scaling/RESULTS.md:140; E1 #5-9, #15-16).
  - Each readback costs one container.
- *Score:* 5. *Evidence:* CSS_TOKENIZER_FEASIBILITY.md:43-49.

**T23. Unwanted HTML parser "error recovery" and a stray class.** 08-25 03:54 (`4d8c81c`). Bug story, not a trick.
- Invalid `<p>`>`<div>` nesting made the HTML parser move handoffs outside the pause selector, so all 35 stages computed on load ("white screen").
- Separately, 4 tokenizer wrappers carried the `.model` class and each one ran a whole transformer.
- The fix gave a warm 32-token run in ≈12 s (S1 F7#2008,#2085,#2209; tinystories/RESULTS.md:197-202).
- *Score:* 3, as a lesson.

**T24. `inline-block` → `inline` when a gate opens.** 08-25 04:17 (`1c0ec16`).
- *How:* `content-visibility` needs a box to skip, but an `inline-block` continuation wouldn't wrap. Once its gate opens, each stage switches to `inline` so the story wraps like normal text.
- *Score:* 2. *Evidence:* README.md:280-283.

**T25. Edit/Run/Pause radio lifecycle with a non-inheriting draft.** 08-25 04:11 (`75537ba`).
- *Problem:* "it lags whenever i type". Every keystroke re-parsed the live style and invalidated all 35 stages.
- *How:* in Edit mode the prompt rule matches nothing in the model. The editable style writes a registered `inherits:false` `--draft-prompt`. A radio transition to Run copies it into the inherited `--prompt` once. The stage chain also closes at token 50256 (end of text).
- *Outcome:* **Kept.** 16 edits went from more than 30 s to 632 ms total (38 ms median) (tinystories/RESULTS.md:204-212).
- *Later change:* `8945a2d` flipped the registration to `inherits:true`. It is now gated with `if(style(--inference-active:1): var(--draft-prompt); else: "")`, verified via `git show` (75537ba builder line 195 vs 8945a2d line 199; current tools/build_tinystories_dynamic.py:199,208).
- *Score:* 4. It is the earliest instance of "don't inherit what isn't read", which SYNTHESIS §8.2 later measures as 1000× cheaper.

**T26. Gating prefill on the hidden state, not the winner.** 08-25 (`7a257f6`, "update old wasteful prefill method"; the mapping to S1 F11#620 is inferred from the commit title and timing).
- *How:* prompt-ingestion stages were gated on `--winner-id`, which ran three pointless 50,257-token head searches. Gating on the transformer output `--h0` instead skips them.
- *Outcome:* **Kept**, though the latency saving was never measured (S1 open hypotheses).
- *Score:* 2.

### Aug 26 – Sep 7: fonts are matrix multipliers

**T27. HVAR variable-font matvec.** First seen 08-26 ~15:00 PDT (S1 F11 Part B; not committed; experiments/matrix-scaling/).
- *Problem:* in CSS every weight is source text, about 22.5 bytes per multiply-add, "a 5.6× textual-encoding tax" (S1 F3#636). Full GPT-2 would need a projected 3.16–6.12 GB stylesheet (FULL_GPT2.md:41-47).
- *How:*
  - A variable font's `font-variation-settings` axes hold the **input vector**: one axis per input dimension.
  - The font's HVAR table stores, per glyph, how the advance width changes per axis. That table holds the **weight matrix**: one glyph per output row.
  - When Chrome shapes the glyph, the advance width it computes *is the dot product*.
  - A 64×64 matrix fits in an 8.9 KB WOFF2.
- *Outcome:* **Kept.** This is the dense-math backend of all later GPT-2 work. Codex: "I have not found someone already using HVAR for neural-network matmuls" (S1 F11#2191). By the Sep-18 profile, the shaping (the actual matvec) was only ~5% of a 12-layer token (SYNTHESIS §2).
- *Score:* 5. The headline trick of the project.

**T28. The 256-axis wall, and sharding.** 08-26.
- 256 axes load; an otherwise identical 257-axis font is rejected before rendering. That is a Chrome limit, not an OpenType one, since `axisCount` is a uint16 (matrix-scaling/RESULTS.md:12-23).
- Fix: shard 768 inputs into 3×256-axis fonts. Reading back all 768 outputs gave 768/768 correct, max error 0.66 font units, 407 ms (matrix-scaling/RESULTS.md:31).
- *Score:* 4.

**T29. Direct HVAR compiler.** 08-26.
- *How:* fontTools' designspace builder made one master font per axis. Writing `fvar` + `HVAR` + a structurally valid empty `gvar` directly instead cut the 768 build from 368 s / 1.51 GB to 2.76 s / 172 MB, and warm time from 407 to 217 ms.
- *Score:* 2. *Evidence:* matrix-scaling/RESULTS.md:224-237; S1 F11#4121,#4246.

**T30. Declarative shadow root + `<slot>` to beat the 512-level HTML parser depth limit.** 08-26.
- *How:* Chrome's parser flattens nesting beyond about 512 levels, and a shadow root alone doesn't reset that. Putting the next stage's light DOM through a `<slot>` at the bottom of each shadow computation tree keeps the light DOM shallow, while the *flattened* tree keeps the full dependency order. A value of 37 crossed two 400-level trees intact.
- *Outcome:* **Kept** in the connected-block architecture (E1 #19).
- *Score:* 4. *Evidence:* matrix-scaling/RESULTS.md:35,66-70.

**T31. `position: fixed` probes to stop a renderer stack overflow.** 08-27.
- *Problem:* a full GPT-2 block crashed the renderer at the 4th 384-level stage. It still crashed with a **329-byte stylesheet** and no fonts or math. The cause was deep absolutely-positioned layout recursion (Chromium issue 466692313).
- *How:* fix every measuring probe to the viewport. The boxes stay nested for value propagation, but layout no longer recurses through every ancestor's containing block. A side gotcha: shadow-scoped `@font-face` silently gave tofu widths.
- *Outcome:* **Kept.** The first complete one-token GPT-2 block ran in **9.42 s** with RMSE 0.0016.
- *Score:* 4. *Evidence:* matrix-scaling/RESULTS.md:106-110; S1 F11#6327,#6915.

**T32. 4 outputs per readback container (2 in width + 2 in height).** 08-27.
- *How:* halving the containers from 2,304 to 1,152 cut the block from 6.48 s to 3.5–3.8 s.
- *Outcome:* **Kept**, with added error 0.099. It proved the cost was the serial readback chain, not the matmul. Longer chains are worse, and beyond ~506 containers the outputs fall to zero.
- *Score:* 3. *Evidence:* matrix-scaling/RESULTS.md:144-154.

**T33. Direct-`calc()` block as a control (a principle, not a trick).** 08-27.
- *How:* the same block was written as native CSS: 94.3 MB, 2.48–2.66 s per mutation, ~5.0 s to load vs 6.48 s for HVAR. That is "approximately 1.3×, not the required 13×".
- *Outcome:* the rule "direct CSS for O(width), fonts for O(width²)" (matrix-scaling/RESULTS.md:134-142).
- *Score:* 3.

**T34. Named view timelines as an inverse ruler.** 08-29 → 09-07.
- *Problem:* size containers trap values, and siblings can't merge (see dead ends).
- *How:* put a glyph at the leading edge of a 100 px scroller. Its view-timeline progress is `100/(100+width)`, so CSS recovers `width = 100/progress − 100`. `timeline-scope` lets one consumer read thousands of sibling timelines with no nesting: 3,072 readbacks onto one element in ~260 ms (static stress test).
- *Outcome:* **Kept in the pinned 12-layer demo of Sep 18.** That demo had 85 frames/token and ~110k ScrollTimeline invalidations. SYNTHESIS fix #3 later recommends replacing timelines with container-unit readbacks (SYNTHESIS §5 #3, §8.4). Whether round 7 replaced them is outside this slice.
- *Score:* 5. A scroll-animation API used as an ammeter.
- *Evidence:* matrix-scaling/RESULTS.md:160-178; S1 F16#228,#300.
- *Sub-gotcha:* declaring the 768-axis `font-variation-settings` on every glyph instead of once on an inherited ancestor cost 3.17 s vs 1.60 s (matrix-scaling/RESULTS.md:180).

**T35. Per-glyph base advances.** 09-07.
- *How:* subtract each row's own baseline instead of the worst baseline across all rows. That fixes ~193,000-unit cancellation: RMSE went from 0.00874 to 0.00485.
- *Score:* 2. *Evidence:* matrix-scaling/RESULTS.md:192.

### Sep 7 – Sep 12: the transport wall (moving vectors, not computing them)

**T36. Additive `font-variation-settings` via `animation-composition: add`.** 09-08.
- *How:* several paused animations each contribute part of an axis-list vector, and Chrome sums them, so a vector is assembled on one element. Exact values were `1.5, 3.75, 5.25` (E1 #3).
- *Outcome:* **Works, but rejected as slow.** The CSS is quadratic (10.8 MB at 768), sparse one-axis lists don't merge, and 3,072 animation contributions dominate (3072→768 took 591 ms and 47.3 MB, E1 #2).
- *Score:* 3.

**T37. Registered-property vector carrier, and packed projection runs.** 09-08.
- 3,072 animated `--v*` properties feed one axis list. It was correct, but transport was 89% of MLP time (S1 F18#2648,#3034).
- Putting 12 fallback-font glyphs in one text run cut elements from 9,216 to 768, a 1.31× speedup (S1 F18#2927).
- A refined registered-numeric-property transport on 09-13 went from 401 to 41.8 ms at width 768 (S1 F19-C#46043).
- *Score:* 2.

**T38. Packing integers into intrinsic sizes and timelines: `calc-size()` + `round()`/`mod()`.** 09-08.
- *How:* 4–6 quantized values share one timeline. A block went from 1.832 to 1.101 s with RMSE 0.031. At 6 per timeline the carrier reached 8.4 Mpx and the low digit scrambled. Chrome layout loses mantissa at multi-million-pixel widths.
- *Score:* 3. *Evidence:* S1 F19-A#1419,#1781; E1 #14 (4×6-bit anchor packing exact, a 5th value lost).

**T39. SVG filters as a matmul engine: the near-miss.** 09-08 → 09-13.
- *How:*
  - Pixels hold activations.
  - `feComposite` does elementwise products.
  - `feConvolveMatrix` with an all-ones kernel (≤256 taps) does the row sums.
  - Signs are handled with a centre bias, plus per-row scales.
- *Outcome:* **Abandoned on 09-13.** It was fast:
  - one connected GPT-2 block in **133.6 ms** warm (16.8× faster than HVAR's 2.24 s, and it cleared the "13×" goal);
  - 12 blocks plus final LayerNorm in ~251 ms;
  - a 50,257 head at 0.79 s.

  But every filter boundary materializes an 8-bit raster:
  - the 12-block chain picked the wrong token (13 vs 11);
  - after 32 scale bands, 12-block w8a8 generation agreed on only 28/48 tokens and diverged after about 2 tokens;
  - 16-bit PNG, linearRGB, scRGB, HDR/AVIF, dither, dual-plane and RGB carriers all failed.

  "SVG has the right execution shape but the wrong intermediate precision" (S2 :23647). A custom Chromium F16 build was ruled out: it needs 100 GB of disk against 4.9 GiB free, and it breaks the stock-browser rule.
- *Score:* 5. It shows the speed was achievable and the precision wasn't, which is great tension for the post.
- *Evidence:* experiments/svg-filter-matvec/ RESULTS (line 14: all-ones convolution reduction); S1 F19-A#2196,#3312,#3919,#5554; F19-C#60806,#61543; E1 #35.

**T40. Font-metric channels (`ex/cap/ch/ic/lh`, ROW axis, TTC, MVAR aliases): the "five numbers per font" trick.** 09-08 → 09-12.
- *How:* one variable-font instance exposes up to 5 independent numbers through font-relative units, at 0.0255 ms per update. A parent's metrics can drive a child font's axes with no geometry at all (E1 #70, #73).
- *Outcome:* **Rejected at scale.** 768 outputs need 924 fonts and **2.83 GB RSS** for 934.5 ms. GSUB, standard features and cmap14 are all ignored by `ch/ic`, and TTC fragments always load face 0 (S2 S-04a; E1 #62-75).
- *Score:* 3.

**T41. The "transport, not math" oracle.** 09-13 ~10:15 PDT (S1 F19-C 17:14Z; S2 S-04c:1314). Placed here for narrative; chronologically it is after T46. A measurement trick, not a CSS trick.
- *How:* replace every vector boundary with already-captured CSS numbers to see what the math alone costs.
- *Outcome:* **The decisive finding.**
  - The first version (two blocks, 2.392 s) reached only 476.6 ms, 5.02× (S2 S-04c:1314).
  - With compute-once GELU, 1,710.6 ms fell to **64.2 ms**: 26.6× of headroom sits in transport (E1 #61).
  - Codex's ShapeResult quote ("Blink already stores the desired glyph-advance array…") belongs to this finding; it is in the quotes section.
- *Score:* 4.

### Sep 12 – Sep 13 (morning PDT): the font renaissance

**T42. GSUB character-variant fused Q·K score font.** 09-12 → 09-13.
- *How:* quantize the query to a 5-bit bin. A GSUB feature (`cvNN`) selects pre-scaled K-row glyph alternates, so a single shaping op yields the attention score.
- *Outcome:* **Works, but superseded** by projected-KV + native CSS scores (T43).
  - Scores took 2,279 → 175 ms (13×).
  - A ctx-32 persistent update went from 8.43 s to 0.72 s.
  - But binning RMSE was 0.363, it lost at short contexts, and GSUB chains with more than ~5 features were unreliable (E1 #64-65; S1 F19-B#40189,#40620).
- *Score:* 4. Using a font feature as an index register is lovely.

**T43. Projected KV cache, plus native-CSS Q·K ("css-kv").** 09-12 ~21:25 PDT (S1 F19-C 09-13 04:25Z).
- *How:* cache K and V *after* projection, then do Q·K in plain typed CSS once Q and K are numbers.
- *Outcome:* **Kept** as the recommended attention path at end of slice. ctx-32 went from 6.33 to 1.95 s and the bundle from 36.7 to 7.55 MB (S1 F19-C#41410,#43804).
- *Lesson:* the bilinear-font Q·K "looked excellent against the wrong baseline". Native CSS did 12h×64t in 49 ms vs 664 ms for the font version (E1 #27).
- *Score:* 3.

**T44. CSS Grid argmax: the DOM max (T13) comes back.** 09-13 ~00:57 PDT (S1 F19-C 07:57Z).
- *Problem:* T13 could find the max but not *which token* won.
- *How:*
  - A `max-content` Grid track takes the widest candidate.
  - Each width encodes **score in the high bits and an inverted token ID in the low bits**, so the max width also names the winner, with ties going to the lowest ID.
  - Because only ~24 bits are reliable, use two levels: 197 Grids of 256 tokens each.
  - `calc-size()` swaps the local ID for the group ID.
  - An outer Grid picks the winning group, and anchor geometry gates that group's width back to recover the local ID.
- *Outcome:* **Kept.** 50,257 candidates resolve in 178 ms (grid-argmax/RESULTS.md:6-33). Combined with a TinyStories font-backed head and an **embedding-lookup font**, it gave the **first CSS-only token-feedback loop** in the font era: chain 0.96–0.99 s, head 872 ms, 6.42 MB vs 51.6 MB (S1 F19-C#45046,#45797). Codex: "token selection is solved" (S1 F19-C#45055).
- *Score:* 5.

**T45. Full GPT-2-width head: 3×256-axis HVAR fonts + Grid argmax + `content-visibility` staging + 7-phase coordinate supersampling.** 09-13 ~03:00–04:41 PDT.
- *How:* staging the head behind `content-visibility` gates cut it from 9.5–14 s unstaged to 2.1 s.
- Chrome floors normalized font coordinates to F2DOT14 (a 2.14 fixed-point format), which flips near-ties. Evaluating at 7 dithered phases repairs that: 256/256 correct, accurate head 1.258 s.
- Limits: cold load 38–130 s and ~137 MB of assets. "CSS cannot detect when layout has genuinely settled" (S1 F19-C#49945).
- *Outcome:* **Kept and developed further after this slice** (S2 S-05: certified cascades).
- *Score:* 3. *Evidence:* S1 F19-C#48563,#48785,#49129,#51420.

**T46. avar2 fused `B·GELU(A·x)` inside one font.** 09-13 ~06:31 PDT (S1 F19-C 13:31Z).
- *How:* avar2 (OpenType 1.9) can remap axes *from other axes*. One font applies a dense A·x remap and a sparse diagonal piecewise GELU in avar2, then a linear HVAR B. The whole MLP nonlinearity happens inside the text shaper.
- *Outcome:* the full real MLP ran in **251 ms**, fonts went from 12.53 to 3.64 MB, RMSE ~0.023 (avar2-gelu-linear-hvar-full-mlp/RESULTS.md:1-33). A real GPT-2 255→256→256 tile took **4.63 ms** in one font (E1 #26). It was then **partly superseded within hours by T47** (compute-once GELU). It stays blocked at full width because GELU of a sum of shards ≠ sum of GELU of shards, and the 256-axis cap is hard (E1 #25, #42).
- *Score:* 5. A font file that runs a neural-network layer.

**T47. Compute-once inherited CSS GELU + pure-linear HVAR projection.** 09-13 ~10:15–11:00 PDT (S1 F19-C 17:14Z, #58237,#58731; S2 S-04c:2247,2531; E1 #48).
- *How:* compute the exact GELU (`exp`/`pow` in typed CSS) **once** on an ancestor as inherited registered numbers, instead of per output inside avar2. Fonts then do only linear work.
- *Outcome:* **Kept** as the "recommended exact path" at the slice end.
  - 463.7 → 111.4 ms (4.16×).
  - Two connected blocks 2,410.6 → 1,810.8 ms.
  - Per-output control 20.1 s, proving the ancestor computation is shared.
- *Score:* 3. *Evidence:* experiments/css-gelu-projection/REPORT.md; experiments/avar2-gelu-linear-hvar-full-mlp-g13/EXACT_CSS_GELU_TWO_BLOCK.md.

**State at the slice cut (09-13 ~12:39 PDT):**
- Best exact path: HVAR/avar2 fonts + compute-once CSS GELU + 13-group projection behind shadow/slot stages + projected-KV attention + staged coarse→fine head.
- Two connected blocks take 1.77–1.81 s, and two blocks + head 2.43–2.57 s.
- Projected 12-block exact time is 9.3–10.3 s/token. Nothing from this era was committed (S1 F19 final state).

---

## Part B — Dead ends worth a sentence (humor or lesson)

| Date | Dead end | One-liner for the blog | Cite |
|---|---|---|---|
| 08-24 | Full-vocab exact interactive build | It filled the disk while writing the stylesheet. | S1 F1#1552 |
| 08-24 | Eager 16-step unroll + animation "reveal" | Built, then deleted for honesty: it "looks streamed but is not sequential execution". | S1 F1#2413,#2496 |
| 08-24 | JS timing harness → JS tokenizer | The user vetoed JS twice in one afternoon ("tokenizing cannot be done thru js"), which forced T8 and later T19/T20. | S1 F1#2022; `de75b61` |
| 08-24 | `if()` branch-and-bound over registered props | Registered properties evaluate both branches. CSS is eager unless it's inside a function. | output-head-benchmark/RESULTS.md:93-95 |
| 08-24 | 2-level cluster hierarchy | Arithmetically 6.67× vs 4.92×, but "a custom function's local numeric result cannot drive a lazy `if()` branch". | OPTIMIZATIONS.md:303-313 |
| 08-24 | Recurrent clock at 1 ms | The inherited latch re-copied the KV cache ~1000×/s. | S1 F3#2274 |
| 08-24 | "0.1 ms" clustered head | The timer stopped before CSS values were read. The real figure was 755 ms. The first of ≥9 retracted speedups. | S1 F3#1521,#1572 |
| 08-24 | Same-radio benchmarking | Chrome reused computed styles, so it measured 0 ms. | S1 F3#797 |
| 08-24 | Minifier removing spaces around `+` | `calc(a+b)` is invalid CSS, so values silently went to zero. It happened at least 5 times across sessions; SYNTHESIS recommends a lint. | S1 F3#746; SYNTHESIS §9 |
| 08-24/25 | Sampling | No CSS `random()` in Chromium 151, so generation stayed greedy. Sampling with seed/temp arrives in later rounds (per project memory; outside this slice). | tinystories/RESULTS.md:158-161 |
| 08-25 | Hard-coded "1.17 tok/s" label | Re-measured live at 0.79 tok/s under CPU load. A static page can't show a live rate. | S1 F7#358 |
| 08-25 | Arithmetic coding | "CSS itself cannot turn a bitstream into new stylesheet rules." | S1 F5#2264 |
| 08-25 | SVD / VQ / weight sharing on the head | Rank 63/64 still flipped decisions, and VQ needed fine-tuning ("i dont want to finetune anything special"). | S1 F5#1524,#2315 |
| 08-25 | Agent pushed to a new private GitHub repo without asking | A process moment; the user objected. | S1 F5#1368 |
| 08-27 | Parallel sibling branches + anchor merge | 9.42 → 5.22 s, but the numbers were wrong: size containment hides anchors from siblings. | matrix-scaling/RESULTS.md:116 |
| 08-27 | CSS counters as an escape hatch | Counters can't leave a shadow host. | matrix-scaling/RESULTS.md:118 |
| 08-27 | `inherit(--prop)` | Unsupported in Chromium 151. | S1 F11#7320 |
| 08-27 | Collapse the FC into one stage | Outputs 2,024–3,071 came back zero, because Chrome propagates through ~506 containers. | matrix-scaling/RESULTS.md:152 |
| 08-29 | `display:contents` typographic sum | Branches were 37/41/43/47 px, the control sum 168 px, the merged sum 0 px. | matrix-scaling/RESULTS.md:156 |
| 09-08 | Monolithic SVG filter | 28.3 s per paint. A "120 ms" staged version was rendering black pixels. | S1 F19-A#2596,#2844 |
| 09-12 | Anchor `calc()` ALU at 768 | 31 s and 68 MB of HTML; ~99 `anchor-size()` refs per property is a parser ceiling. | E1 #10-11; S2 S-03:204 |
| 09-12 | TTC font collections | 4.89 MB → 258 KB, but Chrome loads face 0 for every fragment. | E1 #75 |
| 09-12 | SWAR two-lane anchor packing | Bit-exact and 5.48× on 3072→128, but still loses to fonts. | E1 #17-18 |
| 09-12 | Compositor `plus-lighter` accumulator | 8-bit, and 0 output at ≥1024 terms. | E1 #46 |
| 09-12/13 | Many false wins: cached timelines 148 ms, font cache 10 ms, glyph cache 1.4 ms, "17 ms ideal MLP" | Each was later retracted. Lesson: unique inputs and forced recompute, or it didn't happen. | S1 blocker 13 |
| 09-13 | `content-visibility`/containment as a general speedup | "Hiding work does not remove it; Chromium simply pays for extra lifecycle passes." It works only as a display lock on truly inactive stages. | S1 F19-B#38859; SYNTHESIS §8.2 |
| 09-13 | Branch-and-bound at 768-d | Bounds too loose: it had to score 50,208 of 50,257 rows. | S1 F19-C#52183 |

---

## Part C — Memorable quotes and moments

- **Origin:** "i saw a tweet where someone was able to write gpt2 in cmake / i want to do this with html+css" (S1 F1#8, 08-24 ~11:42 PDT).
- **The constraint is born:** "we dont want to use javascript for anything here … tokenizing cannot be done thru js" (S1 F1#2022). Also "the inference should happen thru a css animation perhaps? it shouldnt calculate everthing up front" (F1#2491).
- **The geometry moment:** "what convex optimization shit did it do" (S1 F2#65).
- **The diagnosis that held for a month:** "The multiplication itself is cheap. Everything surrounding it is expensive" (S1 F2#518, 08-24).
- **The honest retraction:** after the user's 8 s-clock run corrupted state, Codex said "I overstated its stability… only a timing workaround" (S1 F3#2862).
- **First-day verdict on GPT-2 small:** 123,550,464 MACs and a projected 3.16–6.12 GB stylesheet. "Reaching GPT-2 small operationally would require relaxing the runtime constraint" (FULL_GPT2.md:66-70). The rest of the project is an argument with that sentence.
- **The text-box loophole:** "surely theres a way to pass shit to the css" (S1 F6#33), answered by `<style contenteditable>`.
- **A 329-byte crash:** the GPT-2 block crash reproduced with a 329-byte stylesheet and no math (matrix-scaling/RESULTS.md:106).
- **SVG heartbreak:** "ok wait so svg calculations are just fucked then?" / "For this use case, mostly yes." (S2 S-03 replay, 09-12).
- **Groundhog Day:** "so we're back where we were like a wek ago?" / "we understand the wall much better, but we're still at the wall" (S2 S-04 prefix). Codex re-answered this stale question 17 times during autonomous continuation (SYNTHESIS §4).
- **User pushback on drift:** "it seems like you're diving into territory of edge-case hacks that aren't particularly useful for scale" (S1 F19-A#10441).
- **The missing API:** "Blink already stores the desired glyph-advance array in `ShapeResult`; it simply has no CSS-facing API" (S2 S-04b:777).
- **Autopilot stats:** from 09-12 08:35 to 09-13 12:39 PDT, all 98 "user" turns were automated goal-continuations. One 640 MB session ran 7,895 tool calls, and nothing was committed (S1 F19; SYNTHESIS §4).
- **Codex on the user's prompting (meta, 09-11):** early prompts supplied hypotheses ("we should bench the autoregressiveness", "reducing output vocabulary is not the right move"); later ones delegated ("keep working until you get the 13x improvement"). Its advice: "Explain the current mechanism and bottleneck. Don't suggest a solution yet." (S2 S-01).
- **Retrospective irony (from the Sep-18 audit, useful as the bridge into the final chapter):** "The arithmetic is ~5% of the token." The fonts, GSUB, avar2 and SVG work all lived inside that 5% (SYNTHESIS §2).

---

## Part D — Suggested chapters for this period

1. **"A spreadsheet that thinks" (Aug 24 morning).** T1–T8: `calc()` matmul, `:has()` radios, `@property` as "please materialize", `@function` GELU, the convex-hull miracle (16 of 50,257), and the FULL_GPT2 "honest hard boundary". Ends on: it works, it's 6 GB, and the toy model only says "stairs".
2. **"Inventing time" (Aug 24 afternoon/evening).** T9 → T15 → T16. An animation flip-flop clock (x86CSS) that races and corrupts; then the realization that *inheritance is a barrier*, so nested elements become the clock; then `content-visibility` gates with 1 ms ticks for real streaming. Includes the KV cache and the TinyStories pivot.
3. **"Squeezing 237 megabytes" (Aug 24–25).** T11–T12, T17–T18. Lazy `@function` vs eager properties, Cauchy-Schwarz cluster pruning, the 24-bit typed-number cliff, Brotli ("transfer, not parse"), int10. Plus the measurement traps (the 0.1 ms that was 755 ms).
4. **"Typing into a stylesheet" (Aug 25).** T19–T26. `<style contenteditable>`, HarfBuzz doing BPE through GSUB, glyph widths as numbers, the anchor→`cqi` readback, and the Edit/Run/Pause lifecycle that took typing from >30 s to 38 ms. This is the shipped `dynamic.html` and the last commit (`8945a2d`).
5. **"Fonts are matrix multipliers" (Aug 26 – Sep 7).** T27–T35. HVAR matvec, the 256-axis wall, shadow-slot depth resets, the 329-byte crash and `position:fixed`, view timelines as inverse rulers. The bottleneck flips from math to *readback*.
6. **"The transport wall: SVG mirage and font renaissance" (Sep 8 – Sep 13 AM).** T36–T47. SVG reaches 133 ms per block but at 8 bits, then is abandoned. Metric-channel fonts hit 2.83 GB. The oracle shows transport, not math. Then Grid argmax (the DOM max returns), avar2 GELU inside a font, compute-once GELU, projected KV. It ends on the autopilot / "back where we were a week ago" moment as the handoff to the next period.

## Boundary teasers (Sep 13 PM PDT, next slice; S2 S-05)
`opsz`-axis handoff via child `font-size` (262.5 ms for 3,072 values); a declarative stage scheduler using SMIL `<set>` → `:has()` → `content-visibility` with `animationend`; CSS counters as a reducer (rejected); certified int10 best-first head cascades. All are outside this slice's cut.
