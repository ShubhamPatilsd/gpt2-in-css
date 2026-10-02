# N3: From 40 s/token research to a shareable demo (rounds 2026-09-19 → 2026-10-01)

Blog research brief. Covers `work/2026-09-19/` (RESULTS-round1/2/3/5/6, agent reports B*, F*, R*; bundle docs
`bundles/demo-c32/BUILD.md`, `README.txt`), with `audit/2026-09-18/SYNTHESIS.md` §1–3 as the starting point.
Unless a path says otherwise, citations are relative to `work/2026-09-19/`. Claims marked **(inferred)** are my reading
and are not stated in the sources. Process log: `audit/2026-10-02/N3-rounds-sep19-oct01.log.md`.
Out of scope but adjacent: R8H (hosting research) and R8U are dated 2026-10-02, so they fall just after this slice.

---

## 0. The arc in one table

| Date | Round | Best exact bundle (cap 8) | s/token | Main move | Source |
|---|---|---|---:|---|---|
| 09-18 | start | pinned `demo-font-vector-twelve` | 40.7 (passive) | (Codex had claimed 78 s with an observer attached) | audit/2026-09-18/SYNTHESIS.md:14-16 |
| 09-18/19 | 1 | baseline (v2 rebuild) → `combined` | 40.2 → **30.3** | narrower inherited writes, fewer elements, shorter latch lists | RESULTS-round1.md:10-13 |
| 09-19/20 | 2 | `R2F` / `combined3` | **23.6** / 24.6 | removed the pure-handshake frames | RESULTS-round2.md:4-6,19-20 |
| 09-20 | 3 | `R3R` → `combined4` | 19.4 → **18.2** | removed one geometry hop per layer | RESULTS-round3.md:50-54 |
| 09-21 | 4 | `combined7` | **≈16.0** | consumer chunking (64 animations per element), small-hop anchor chain, capacity fixes; first verified 32-token runs | RESULTS-round3.md:96-101 |
| 09-24 | 5 | `combined8` | **≈15.3** best totals (paired −1.0) | `1ch` score readback, dead declarations removed; memory anatomy | RESULTS-round5.md:71,104-106 |
| 09-30 | 6 | `demo-c32` (cap 32) | UI adds no measurable cost | productization: 2 s load, typed prompt, progress UI, echo fix | RESULTS-round6.md:81-93 |
| 10-01 | 7 | live `demo-c32` = capacity 36 | demo-8.r7b 14.3 median (one run) | prefill head-skip, 32 new tokens, Gumbel sampling, scrollbar fix + id guard | RESULTS-round6.md:229,241-252 |

32-token runs: Codex took 3,177 s, measured as 57→143 s/token (audit/2026-09-18/SYNTHESIS.md:17). Here: 1,133 s (R4C) → 905.9 s (R4D) → **758.7 s**
(c32c, clean memory) → 905.6 s (combined8-c32, memory-pressured) → 922.0 s (demo-c32 with UI) → **1,034.9 s for 35 epochs** (cap 36,
typed 4-token prompt, AC) (RESULTS-round3.md:80-82,129-136; RESULTS-round5.md:83; RESULTS-round6.md:87,205-207).

Exactness was the hard constraint the whole way. Every bundle had to reproduce the NumPy q9/q16 reference ids exactly
(8/8 or 32/32), and every flag had to be removable to give a byte-identical twin. That rule, rather than speed, is what closed most routes.

---

## 1. Starting point (SYNTHESIS §1–3, 2026-09-18)

- Measured 40.7 s/token for the 12-layer bundle (passive, AC). Codex's "78 s" figure included its own 100 ms `DOM.getBoxModel` observer,
  which inflated it by about 22 % (audit/2026-09-18/SYNTHESIS.md:14-16,21-23).
- Breakdown: style recalc 55.6 %, layout 13.6 %, paint lifecycle 12.4 %, animation 8 %. **The arithmetic itself (font shaping) is about 5 % of a
  token.** Per-frame overhead is about 27 % across 85 frames per token (SYNTHESIS.md:28-48).
- "The atom" (SYNTHESIS.md:78-82): when an element is style-dirtied, Blink re-resolves all of its custom-property declarations at about
  45 MB/s. It also dirties every descendant of a changed inherited property unless a display lock (`content-visibility:hidden`) stops it.
  Cost per token is the sum over passes of dirtied elements × declaration bytes.
- Blog framing: the previous week had optimized the 5 % (fonts, glyphs, GSUB) while the other 95 % was transport and frames
  (SYNTHESIS.md:38-41,95-98).

---

## 2. Round by round

### Round 1 (09-18/19): narrow the writes. 40.2 → 30.3 s/token (−25 %)
Hypothesis: shrink what each style pass dirties (SYNTHESIS fixes 1–6; PLAN.md:1-60). Goal at the time: ≤ 12 s/token (PLAN.md:5).
- **Baseline surprise.** The rebuild did not reproduce the pinned bundle byte for byte (v1 vs v2 operator fonts, and no v1 source exists). Two references were therefore benched (B0.md:9-15).
- **F5, scoped inherited writes.** `--loop-ack`/`--loop-ready` had **zero readers**, yet they dirtied about 12.3k elements 24× per token. The body-level `--epoch` dirtied
  the whole 63.9k-element document once per token (F5.md:18,20). Fix: register them `inherits:false` and stamp them only onto the reader elements.
  F5 also replaced 1,538 `:nth-child` forwarding rules (a 1,538² selector bucket, about 2.7 s/token) with inline forwards (F5.md:29). Result: −7.4 s (RESULTS-round1.md:11).
- **F2, fewer elements.** 3,072 proj-pack leaves, each carrying 39 KB of declarations, were collapsed into one 3,072-axis list on one element, and GELU `@function` calls were inlined (F2.md:9-15).
  −3.3 s. Side finding: declared bytes on *identical* leaves are free, because Blink's MatchedPropertiesCache shares them (F2.md:30-33).
- **F4, shorter latch lists.** Latch cost tracks retained-list bytes (about 8 ns/B), not transition count. KV latches went from 48 to 26 per slot and the head latch from 769 names to 2 (RESULTS-round1.md:25-26).
- **Failed: F3/F3b anchor→container chains** for the MLP. They are exact and remove 2 frames per layer, but chained size containers restyle quadratically
  (Σ depth²/2), so layout cost equals the frames saved. Chains only pay below about 500 values (RESULTS-round1.md:32-38).
- `combined` = F2+F5+F4 gives **30.3 s** (RESULTS-round1.md:13).

### Round 2 (09-19/20): kill the handshake frames. 30.3 → 23.6 s (−41 % vs baseline)
- **R2A trace.** A frame costs about 105–120 ms of bookkeeping per live timeline. 3 of the 7 frames in each layer were pure handshake (RESULTS-round1.md:46).
- **R2F, lean handshake (the big win).** The old layer loop ran A B C D + E F G. E and G were 1 ms SMIL pulse frames whose only job was to move one fact
  *upward* through `:has()`, because without JS "only SMIL can turn an animation event into DOM state" (R2F.md:23-27). The controller now reads bank markers
  directly. Frames per token went 85 → 46.9; paired result **−7.1 s/token [−7.8…−6.6]** (RESULTS-round2.md:4,19).
- **Harness artifact, mouse hover.** The pointer was left on `#run`, so Blink hit-tested the whole document on 61 of 85 frames (≈1.07 s/token).
  Fix: park the pointer off-page (B1.md:13). In round 3, R3K replaced the click with a keyboard Space: no mouse event at all means
  `IsMousePositionUnknown()` stays true and no hover pass runs, saving about 0.7 s more (R3K.md:12; RESULTS-round3.md:5-7).
- **Failed: R2C hoisting.** The microbench predicted −4.9 s (a `calc()` inside a font-variation-settings list re-instantiates the font). It was neutral in the real page,
  because the lists change on every hop anyway (RESULTS-round2.md:18).
- **Failed: R2E, pausing idle timelines.** NO-GO: Blink drops a paused animation's hold time when its timeline is removed. Only a display lock keeps the value, and the lock keeps the cost
  too (R2E-design.md:11; RESULTS-round2.md:22).
- **Method change, paired bench (B3).** The same bundle drifted 31–40 s with machine load, so from here on only paired candidate−reference deltas count
  (B3.md:6-10; RESULTS-round2.md:3).

### Round 3 (09-20): one hop less per layer. → 18.2 s (−55 %)
- **R3R, fold the loop-transport hop.** The 7th hop did no arithmetic. It existed only to carry 768 numbers *upward* (depth 47 → 13) and to hold them in two latch banks.
  Now the proj carriers publish the next layer's input themselves, and the stage gates already provide the hold. Per layer that is 3.0 frames, −9,228 transition starts per token
  and −1,538 elements; paired **−5.0 s** (R3R.md:10-19; RESULTS-round3.md:42,50).
- **Failed, precision wall: R3P, two values per carrier.** Every field crosses one `var()` substitution as 6-significant-digit text (≤ ~10 exact bits).
  Packing flips ids on qkv/fc/proj/loop, and the pinned run's token 4 is 4 q-units from a flip (R3P.md:9-16; RESULTS-round3.md:43).
- **Failed: R4A fused MLP font.** It needs 768 axes, and stock Chrome rejects more than 256. An exact Fontations variant would need about 15 GB of font tables
  (RESULTS-round3.md:61-64).
- R3F found frames already at Blink's floor of 2 passes per frame (RESULTS-round3.md:22).

### Round 4 (09-21): 32 tokens, chunking, and a memory ghost. → 16.0 s (−60 %)
- **First verified 32-token run (R4C).** 32/32 ids in 1,133 s against Codex's 3,177. The slope is 1.14 s/token per filled position (RESULTS-round3.md:80-86).
- **R4D capacity fixes.** Empty lists for unfilled slots, hidden unfilled V glyphs and leaner per-position latches gave 905.9 s. Adding `widths` value layout (c32c) gave **758.7 s**
  (RESULTS-round3.md:129-136).
- **R4T, consumer chunking.** Fixture law: each changed carrier costs 14.1 µs + 45.8 ns × (animations on its consumer element) (R² 0.996).
  Splitting 512-animation consumers into 64-animation chunks cut paint-lifecycle time by 61 % on the smoke (RESULTS-round3.md:105-118).
  - **Bug beat:** the first chunked smoke emitted tokens [44873, 9890] instead of [11, 3387]. Cause: the `--lp-*` properties are `inherits:false` and were forwarded only one
    level with `inherit`, so the innermost of 12 nested chunk wrappers saw 64 of 768 values (RESULTS-round3.md:113-121).
- **R4S.** The 97-value score hop moved onto an anchor chain: −0.6 s at cap 8, but a loss at cap 32 (recalcs grow by 70.8·k) (RESULTS-round3.md:92,246-249).
- **combined7** (R4S+R4D+R4T): paired −2.3 s, **≈16.0 s/token**, best 8-token total 120.0 s (RESULTS-round3.md:96,233-237).
- **Memory-state ghost (R4V).** The same bundle took 758.7 s and later 969.7 s on the same prompt. The slope tracked the renderer's RSS / system swap (corr −0.84…−0.88), not the prompt
  (RESULTS-round3.md:147-163,188-192). R4W removed 99 % of the leaf substitution garbage and the slope did not move (RESULTS-round3.md:178-187).
- **R4X, the catalog is complete.** Style can read geometry through exactly four channels: cq units, font-metric units, anchor-size(), and scroll/view-timelines.
  `container-progress()` parses but evaluates to 0, and `random()` is absent (R4X.md:12; RESULTS-round3.md:137-146).
- **R4P, a prompt anecdote.** The demo's "Hello" loops after 14 distinct tokens ("I'm not sure if you're aware of this" ×N). The prompt screen picked 40 "I"
  (the grocery-store / frozen-yogurt story) (R4P.md:75; RESULTS-round3.md:212-218,250-253).

### Round 5 (09-24): the floor shows. → ≈15.3 s best totals
- **R5A attribution.** The renderer footprint is 6.24 GB, of which Oilpan is 3.9 GB with **only 0.92 GB live**. About 3 GB is swept var()-substitution garbage that stays committed.
  Decoded webfonts take 872 MB–1.23 GB (RESULTS-round5.md:13-20,40-46).
- **R5H, `1ch` readback.** Scores are read via the `ch` unit of the dot font, using a cmap trick ('0' maps to the dot glyph). Recalcs went 436 → 71 per token, and the gain is at cap 32 (918 s) (RESULTS-round5.md:30,67).
- **R5E.** Dead declarations removed (16,156 no-op `--p:initial`, etc.). Neutral within noise; kept as hygiene (RESULTS-round5.md:33,70).
- **Failed: R5C** moved the 768-value hop onto chains. A real regression of +1.6 s: every size container costs an interleaved recalc of about 0.35 ms.
  Chains are only viable for ≲100 values per layer (RESULTS-round5.md:69).
- **Failed: R5M** literal head widths cost **+239 MB**. **Failed: R5G** launcher flags; low-end-device mode cuts 2.8 GB but runs 17 → 77 s/token (RESULTS-round5.md:68,92-100).
- **combined8** = combined7 + R5E + R5H: paired −1.0 [−1.6…−0.5]. combined8-c32 took 905.6 s on prompt 40 (RESULTS-round5.md:71,83).

### Round 6 (09-30): make it shareable
Triggered by four user reports (PLAN-round6.md:7-13): the dropdown shows "!", the user wants a text box, wants a progress bar, and the load takes 34 s with a blank tab.
- **Load 34 s → 2.2 s (R6L / R6V).** 90 % of the load was **30.8 s of unstyled layout**. While the 50 MB `<head>` stylesheet was pending, Chrome laid out
  84,592 `<i>` elements whose 780k private-use-plane characters each triggered a system font-fallback lookup. The fix is to put the `<link>` inside `<body>` (parser-blocking),
  add a tiny inline boot style, and keep the rest of the body under `content-visibility:hidden` until the sheet's last rule lifts it (R6L.md:11-17,42; RESULTS-round6.md:5-13,36-40,86).
- **Progress UI (R6V).** An exact "token t of 32 · layer k of 12" comes from 12 `@container corestate style(--layer:k)` rules on an 8-element reader.
  The within-layer fill is a compositor-only `scaleX` animation, labelled as an estimate. A font-count loader sums 283 font-proof widths through an anchor-size() tree (RESULTS-round6.md:26-40).
- **"!" bug (R6P).** `::before` only inherits *inherited* properties. `--frozen-prompt` was `inherits:false`, so the pseudo-element always saw initial 0, which is token 0, "!".
  The model got the right prompt; only the echo was broken. Fixed with 2 rules (R6P.md:32-35; RESULTS-round6.md:48-52).
- **Typed prompts (R6P).** See trick T14. Prefill is exact-class (RESULTS-round6.md:53-66).
- **Merge (R6X) and Chrome verification.** typed "I" 32/32 in 922 s, "Once upon a time" 32/32 in 887.8 s, Ready 2.32 s (RESULTS-round6.md:81-88).
- **Bug saga** (§4 below): an overlapping footer, the "Shubham was" report, the typed-prompt race (v5), and the scrollbar (v6).

### Round 7 (10-01): sampling, 32 new tokens, self-checks
- **R7P prefill model.** Prefill cannot be parallelized cheaply, because frames are per hop per position. The cheap exact win is skipping the head on prefill epochs 1..N−1.
  Recommendation: capacity 36 plus a stop rule at epoch 31+max(N,1) (R7P.md:10-25).
- **R7S sampling** via Gumbel-max with a noise font and a clock seed (tricks T17/T18). **R7H** found the scrollbar bug and designed the id guard.
  **R7T** set a floor of ≈12.5 s/token (RESULTS-round6.md:144-199).
- **R7B build.** demo-c36 typed "Once upon a time" T=0: 35/35 in 1,034.9 s on AC, matching R7P's prediction. Two sampled 12-layer runs matched 35/35 (seed 17 T=1.0, seed 42 T=0.7), both on battery (RESULTS-round6.md:201-239).
- **R7X close.** Live `bundles/demo-c32` = capacity 36 + head-skip + sampling + guard, swapped atomically at 21:17:50 (RESULTS-round6.md:241-252; bundles/demo-c32/BUILD.md:1-19,31-32).

---

## 3. Trick catalog

Format: name, date, problem, mechanism, outcome, blog-worthiness (1–5), citations.

**T1. Scoped inherited writes (`inherits:false` + stamp onto readers)**, 09-18/19. *Problem:* handshake properties with zero readers dirtied
12k–64k descendants per write. *How:* register the property as non-inherited and copy it only onto the handful of elements that read it, so a change
dirties a few elements instead of a subtree. *Outcome:* −7.4 s/token (−18 %), the biggest round-1 item. **4**. F5.md:18-29; RESULTS-round1.md:11,22-24.

**T2. Global projection list (3,072 leaves → 1 element)**, 09-18/19. *Problem:* 3,072 leaves each restyled with 39 KB of declarations. *How:*
retag 12 shard fonts to disjoint axis tags and put one 3,072-entry `font-variation-settings` list on a single element. Fonts ignore tags they do not define,
so each shard picks out its own axes. *Outcome:* −3,072 elements, −3.3 s. **3**. F2.md:9-15; RESULTS-round1.md:12.

**T3. Matched-properties-cache insight**, 09-18. *Problem:* the 4,005 B → 225 B leaf rule change did not move the time. *How:* identical-declaration
siblings share one cached computed result, so bytes only cost when they are unique per element. *Outcome:* the optimization target moved to unique work. **3**. F2.md:30-33.

**T4. Packed latch lists**, 09-19. *Problem:* 86,400 s "hold" transitions cost about 8 ns per byte of retained list. *How:* latch whole `*`-typed lists
(per-slot K/V lists, a pre-rounded head list) instead of hundreds of individual numbers. Integers serialize exactly. *Outcome:* per-token slope halved (0.80 → 0.49). **3**.
F4.md (§2.1–2.2); RESULTS-round1.md:13,25-26.

**T5. Lean handshake: delete the SMIL pulse frames**, 09-19. *Problem:* 3 of 7 frames per layer existed only to send a fact upward via
pulse → `animationend` → SMIL `<set class=done>` → `:has()`. *How:* let the controller read bank markers directly and fold the pass advance into the hop frame.
*Outcome:* 85 → 46.9 frames per token, **−7.1 s paired**, the largest single win in the project. **5**: shows how control flow works without JS. R2F.md:23-27; RESULTS-round2.md:4,19.

**T6. Keyboard-triggered Run (no mouse = no hover pass)**, 09-20. *Problem:* after a click, Blink re-hit-tests the document on every frame.
*How:* focus `#run` and send Space. With no mouse position known, the post-layout hover update is skipped. *Outcome:* about −0.7 s (after mouse-park −1 s). Harness-side only;
a real user clicks (inferred: real users pay part of this). **3**. B1.md:13; R3K.md:12; RESULTS-round3.md:5-7.

**T7. Fold a hop: carriers publish the next layer's input**, 09-20. *Problem:* a transport hop that did no math, only lifting 768 values upward and holding them.
*How:* the proj carriers encode `262144px + 128·out` themselves (residual and bias folded into per-layer constants). The `content-visibility` stage gates already
guarantee a single restyle per pass, so they serve as the hold. *Outcome:* −5.0 s paired, −9,228 transition starts per token. **4**. R3R.md:10-19; RESULTS-round3.md:31,42,50.

**T8. Display-lock gates (`content-visibility:hidden` until a receipt matches)**, inherited from the design and leaned on throughout. *Problem:* a write dirties everything
below it. *How:* each stage sits under a gate that opens only when its receipt's stamp equals the current epoch/pass. Blink skips child restyle and layout of a locked subtree in that pass.
R7T found that putting the chunk chains *inside* the gate is worth another −1.0…−1.2 s (not yet built). **4**. SYNTHESIS.md:78-80; R3R.md:73; R2D.md:10-12; R7T.md:25.

**T9. Consumer chunking (64 animations per consumer)**, 09-21. *Problem:* each changed carrier re-walks its consumer element's whole animation list
(PendingAnimations::Update), at 107 µs per carrier with 2,000 animations. *How:* split 512–1,538-animation consumers into nested 64-animation wrappers.
*Outcome:* paint-lifecycle −61 % on the smoke; −1.0…−1.3 s paired at cap 8; part of combined7's −2.3 s. At cap 32 it was first excluded because the slope grew, then re-included in combined8-c32 (and so in the live demo). **3**.
RESULTS-round3.md:105-112,238-242,263-266. *Note:* R5X's combined8-c32 lists "R4T 64" (RESULTS-round5.md:77).

**T10. Capacity hygiene (empty unfilled slots, widths value layout)**, 09-21. *Problem:* 24,576 V leaves substituted 8–10 KB lists even for empty slots. *How:* empty lists and hidden glyphs for unfilled slots.
The softmax weight goes into a `calc-size` width instead of a font instance per slot. *Outcome:* 1,133 → 758.7 s for 32 tokens (−33 %). **2**. RESULTS-round3.md:129-136.

**T11. `1ch` readback (font metric as transport)**, 09-24. *Problem:* score readback through timelines or chains cost frames or interleaved recalcs. *How:* an empty element carries the dot-font
instance and its `ch` unit (the advance of '0', remapped to the dot glyph) is the score. No layout and no frame. *Outcome:* recalcs 436 → 71 per token; the gain is at cap 32. **4**: a delightful hack.
RESULTS-round5.md:30,67; R4X discovery RESULTS-round3.md:137-146.

**T12. Paired interleaved benchmarking + machine gate**, 09-20 onward. *Problem:* same-bundle drift (31–40 s) was larger than the fixes. *How:* run reference and candidate back to back,
judge by paired deltas, gate runs on AC/swap/disk, and allow one Chrome at a time (`CHROME.lock`). *Outcome:* separated real wins from noise; overturned R4T's "0.0 ± 2.4". **3**.
B3.md:6-10; RESULTS-round3.md:224-242; RESULTS-round5.md:117-118.

**T13. Early paint / parser-blocking body `<link>`**, 09-30. *Problem:* a 34 s blank tab. *How:* move the stylesheet `<link>` into `<body>` so the model markup is not parsed until the CSS
is in. An inline 1 KB head style paints the controls and a "Loading the model's stylesheet…" panel, and `content-visibility:hidden` keeps everything else unlaid-out.
*Outcome:* Ready at **2.2 s** (was 34 s); controls at 0.5 s. **4** (the font-fallback detail is a good beat). R6L.md:11-17,42; RESULTS-round6.md:5-13,86.

**T14. Typed prompts via an editable `<style>` + tokenizer fonts**, 09-30. *Problem:* only 6 dropdown prompts. *How:* a `<style contenteditable>` holds
`.tk-root{--draft-prompt:"…"}`, so typing re-parses a real stylesheet. Two OpenType fonts implement GPT-2's BPE: `rlig` holds the merge table in rank order and
position features erase all but the k-th token. Each glyph's advance encodes a base-32767 digit of the id at 1 px. `anchor-size()` passes the width to a container,
and `round()` turns it into an integer. *Outcome:* 22/26 prompts match Python BPE (newlines, double spaces and non-ASCII fail); up to 4 tokens; prefill uses the same exact embedding lookup. **5**.
R6P.md:38-55; RESULTS-round6.md:53-66; README.txt:33-43.

**T15. Pure-CSS progress bar**, 09-30. *How:* style queries on the controller's `--layer`/`--epoch` print the exact layer and token. The intra-layer fill is a compositor-only estimate.
The font-load counter uses 283 `(min-width:N px)` rules over a summed anchor-size tree. *Outcome:* no measurable s/token cost (RecalcStyle 72 → 102 per token, unexplained). **3**.
RESULTS-round6.md:26-40,87,112-113.

**T16. Prefill head-skip**, 10-01. *Problem:* each prompt token ran the 50,257-row head (≈2.6–3 s) and threw the winner away. *How:* on prefill epochs 1..N−1,
`.full-head` stays `content-visibility:hidden` (a later, same-specificity rule wins), and a separate handshake animation advances the epoch. *Outcome:* about −2.6…−3 s per prefill epoch;
1,034.9 s for 35 epochs, as predicted. **3**. R7P.md:10-16; R7B.md:32; RESULTS-round6.md:201-207.

**T17. Gumbel-max sampling with a noise font**, 10-01. *Problem:* greedy-only output (the "Hello" text loops). *How:* argmax(score + T·g) with Gumbel g is an exact sample from softmax(logit/T),
and the head is already an argmax. The g table (64 seed columns × 50,257 rows) is shipped as a variable font: each head row gets one extra glyph whose advance adds T·g. A `SEED` axis with 64 tent
regions selects the column and a `TEMP` axis scales it. `size-adjust` makes one font unit equal one score quantum. T=0 is bit-identical to greedy. *Outcome:* fixture 21/21 matches NumPy;
12-layer runs 35/35 for two seed/T pairs; about +0.2–0.3 s/token; +8.3 MB. **5**. R7S.md:8-23,40-79; RESULTS-round6.md:144-160,235-239.

**T18. Seed from a clock**, 10-01. *Problem:* `random()` is not implemented (it parses but evaluates to 0). *How:* a free-running animation sweeps `--clock` 0→64 every 0.97 s
(chosen to avoid 60 Hz aliasing). `animation-play-state:paused` on `#run:checked` freezes it at the click, so human timing jitter is the entropy. The seed is displayed and can be replayed from a select.
Caveat: browser Reload restores the checked box, so the restarted clock gives seed 1; use Reset. **4**. R7S.md:25-38; README.txt:44-48,59-61.

**T19. Capacity 36 + "32 new tokens" stop rule**, 10-01. *Problem:* a 4-token prompt left only 29 new tokens. *How:* the only hard cap was an argparse guard. Capacity 36 adds +788 elements per slot,
and a stop rule at epoch 31+max(N,1) means dropdown runs still take 32 epochs. *Outcome:* 89.7k elements, about 52 MB CSS, always 32 new tokens. **2**. R7P.md:17-25; BUILD.md:16.

**T20. `scrollbar-width:none` + geometry self-check (id guard)**, 10-01. *Problem:* the scrollbar bug (§4.4). *How:* hide the scrollbar on the id scroller. The guard reads back a calibration
metric of known value (50256) through the same mechanism. If it does not decode exactly, `#token-e-ready` is blocked and a red "Geometry self-check failed" panel appears.
Each fed-back id must also equal the latched winner before the epoch advances. *Outcome:* zero added frames. Fault injection: the decode came out 50257.7, so the run was held instead of corrupted. **5**.
R7H.md:7-25; RESULTS-round6.md:162-179,209-220.

**Closed routes worth one line each in the blog:** anchor/container chains for hops above about 100 values (R5C); two values per carrier (R3P, precision);
hop-gated timelines (R2E); fused 768-axis MLP font (R4A); hoisting calc() (R2C, did not transfer); memory flags (R5G); head literal widths (R5M).

---

## 4. Bug stories (blog beats)

1. **The deleted fonts (09-20).** An external disk cleanup working from a hand-written keep-list deleted 360 live weight fonts. They were regenerated byte-identically from GPT-2 weights
   (pinned font timestamps, fontTools 4.63 vs 4.65 identical), and verified against `?v=` digests. Lesson saved to memory: derive keep-lists mechanically (RESULTS-round2.md:55-58; R2I.md:6-9).
   Side find: `css.replace("b1", …)` silently mangled 5 hex digests (R2I.md:25-30).
2. **The 3-hour lock (09-19/20).** A hung playwright `browser.close()` held `CHROME.lock` for 3 h. A lock race then nearly launched two Chromes (B1.md:26-29; RESULTS-round2.md:53-54).
3. **The `inherits:false` wrapper bug (09-21).** Chunk wrappers starved the innermost consumer of 704 of its 768 values, which produced garbage tokens (RESULTS-round3.md:113-121).
4. **The scrollbar that corrupted token ids (09-30 → 10-01). The best story.**
   - Symptom: users saw "House ofEARTH" instead of "House of Representatives", or blank output.
   - Wrong theories, in order: rebuild-in-place mixed files (v4); a typed-prompt race (v5, a real race but not this bug); system load (10.M, withdrawn) (RESULTS-round6.md:101-108,115-129; R6X.md:546-590).
   - Real cause: the fed-back id is a width `65536px + 8(id+1)` read through a view-timeline whose decode hard-codes the scrollport as 524,288 px. With macOS "Show scroll bars: Always",
     a 15 px classic scrollbar shrinks the scrollport, biasing every id ≥ 9283 by +1. 17132 "Representatives" became 17133 "EAR", and the model fluently continued "TH".
   - Why nobody saw it: every harness passed `--hide-scrollbars`, and Hello's max id 7926 sits just under the threshold (bias 0.46).
   - Positive control: the old build headed with scrollbars flipped at exactly the predicted position 16. The fix is one declaration (R7H.md:7-17,48-62; RESULTS-round6.md:162-179).
5. **The "!" prompt (09-30).** Every dropdown option showed "!" because a `::before` pseudo-element cannot inherit a non-inherited property, and token 0 is "!" (R6P.md:32-35).
6. **Typed-prompt race (10-01).** The embedding receipt stamped only the epoch. The idle Hello embedding was already stamped "1", so layer 0 could consume it before the typed token's readbacks landed.
   Fix: a token-fresh receipt and sticky arming without a latch (RESULTS-round6.md:115-129; R6X.md:568-583).
7. **Memory state masquerading as a prompt effect (09-21).** A slope difference blamed on the prompt was actually the renderer's swap state (RESULTS-round3.md:147-163).
8. **Rebuild under a live tab (09-30).** demo-c32 was rebuilt in place while the user had it open. New rule: build to `.next`, then swap atomically (RESULTS-round6.md:106-109).

---

## 5. Honest current numbers and caveats (as of 10-01 close)

- **Live bundle** `bundles/demo-c32`: capacity 36, 32 new tokens, up to 4 typed prompt tokens, greedy or sampled (64 seeds, T ∈ {0, 0.7, 1.0}).
  286 fonts, 7.45 MB HTML + 53.6 MB CSS, about 312 MB raw. Chrome/Edge ≥ 139; 16 GB RAM (BUILD.md:5; README.txt:12-18; RESULTS-round6.md:245).
- **Speed:** cap-8 exact ≈15.3–16 s/token (combined8, paired). demo-8.r7b Hello median 14.3 s/token is a single run, not paired. 32 new tokens after a 4-token prompt took **1,034.9 s ≈ 17.2 min** on AC
  (first 16.3 s, median 33.0 s, last 49.7 s). README says "about 15 s per token at the start, growing to about 50 s", and "15–20 minutes" (RESULTS-round5.md:104-106; RESULTS-round6.md:205-207,229; README.txt:55-58).
- **Load:** Ready ≈2.2 s locally (was 34 s). On a first remote visit, the download of about 250 MB dominates (RESULTS-round6.md:86,249; R6L.md:15-17).
- **Caveats:**
  - Every R7X acceptance run was on **battery or with 4.7–5.7 GB swap**, so no timing claims are made. The sampled 12-layer runs took 1,533/1,543 s on battery. "Clean AC timing arms still owed" (BUILD.md:32; RESULTS-round6.md:237,246-250).
  - Cap-32 wall-clock depends on the machine's memory state (about 210 s of a 250 s gap) (RESULTS-round3.md:188-192).
  - Footprint is 6.2 GB while generating, about 3 GB of it committed garbage (RESULTS-round5.md:111-116).
  - The 2-layer smoke Hello T=0 is 31/32 at epoch 19 (1-q margin, smoke only) (RESULTS-round6.md:230-231).
  - RecalcStyle rose 72 → 102 per token with the UI, unexplained (RESULTS-round6.md:112-113).
  - The footer says "at most 36 generated tokens" (BUILD.md:32).
  - Remaining environment risks: the "minimum font size" setting, device scale factor 2 untested, zoom (RESULTS-round6.md:219-220; README.txt:75-77).
  - Benchmarks use a keyboard trigger and `--js-flags=--heap-growing-percent=10` (inferred: a user clicking in default Chrome may see somewhat slower tokens).
- **Floor:** R7T estimates ≈13.5–14 s reachable exactly (chunk chains inside gates −1.0…−1.2, and others), with a structural floor of **≈12.5 s/token**. 10–12 s is not reachable in stock Chrome with this architecture
  (R7T.md:10-18; RESULTS-round6.md:181-199). The original round-1 goal of ≤ 12 s (PLAN.md:5) was not met.

---

## 6. Suggested chapters for this period

1. **"The math was 5 %": finding the atom and narrowing the blast radius** (09-18/19). The style-recalc law; inherited writes with zero readers;
   MatchedPropertiesCache; 40 → 30 s. Short failure aside: anchor chains.
2. **"Frames are the clock": deleting handshakes and hops** (09-19/21). SMIL-pulse frames as the only upward channel without JS; the hover artifact and the keyboard trick;
   folding a hop; consumer chunking; the precision wall (6-digit `var()` text) that rules out packing; paired benchmarking. 30 → 16 s.
3. **"Hitting the floor": memory ghosts and closed doors** (09-21/24). The memory-state ghost; 3 GB of committed garbage; `1ch` readback; the four channels;
   why ≈12.5 s is the floor. Optional; could be folded into chapter 2.
4. **"Making it a thing people can use": 2-second load, typing, dice, and a scrollbar** (09-30/10-01). Font-fallback load stall; the tokenizer in a font;
   Gumbel noise in a font and a clock seed; the "!" bug; the scrollbar off-by-one and the self-checking page.

## 7. Five best anecdotes

1. **The scrollbar that turned "Representatives" into "EARTH".** One 15 px classic scrollbar against a hard-coded 524,288 px gave +1 on every id ≥ 9283.
   Hidden from every harness by `--hide-scrollbars`; Hello's ids sat just below the threshold. Fixed with one declaration plus a page that checks its own geometry (R7H.md:7-17,48-62).
2. **Dice in a font.** Sampling uses a 64-column Gumbel table stored as a variable font's HVAR deltas. The seed comes from the moment you click, frozen from a spinning CSS animation,
   because `random()` parses but returns 0 (R7S.md:8-38).
3. **A BPE tokenizer in OpenType**, fed by a `<style contenteditable>` the user types into. Token ids leave the font as glyph widths in base 32767 (R6P.md:38-55).
4. **34 seconds of looking up fonts for characters nobody would ever see.** Unstyled layout of 780k private-use characters ran before the CSS arrived. Moving one `<link>` brought load from 34 s to 2 s (R6L.md:11-17,42).
5. **The biggest speedup was deleting frames that did nothing.** Without JS, the only way to move a fact *up* the DOM was a 1 ms animation → SMIL `<set>` → `:has()`.
   Removing two of those per layer saved 7 s/token (R2F.md:23-27). Runner-up: the "!" prompt echo, where a pseudo-element could not inherit a non-inherited property (R6P.md:32-35).
