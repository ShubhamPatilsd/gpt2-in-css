# Round 6 (2026-09-30) — shareable demo: prompt input, progress UI, load time (plan: PLAN-round6.md)

## R6L — load time and distribution (R6L.md)

**The 34 s load is 90 % one thing**: Chromium blocks painting while the head `<link>` stylesheet is pending, but still lays
out the body with UA styles — 84,592 `<i>` elements holding 780k characters in Unicode planes 2–7 (head rows, V leaves,
witnesses) trigger a system font-fallback lookup per distinct code point (≈300k × ≈100 µs) = **30.8 s of unstyled layout**
before the 50 MB sheet even parses. CSS parse + first styled recalc ≈1.0 s; 283 font fetches + brotli decode + paint ≈1.5 s;
settle → Ready 2.4 s. Fix (`bundles/combined8-c32-fast`): the `<link>` becomes the first child of `<body>` (parser-blocking,
so the model markup is not parsed until the sheet is in) plus a 280 B inline boot style ("Loading the model stylesheet…",
`body{display:none}` until the sheet's last rule). Flag-on == mechanical transform of combined8-c32 (no model rule, element
or font changed); flag-off byte-identical. Expected load 34 → ≈3–5 s, first paint 33 → ≈0.2 s; 3-load measurement and the
32/32 acceptance run are armed behind the machine gate. Not worth doing: .ttf fonts (decode window 1.5 s), CSS dedupe (−0.2 s).
R6V independently built the same split with the loading panel before the link — the merge takes ONE (R6L/split-point.md).

Distribution: 296 MB to ship (html 7.1 + css 50.2 + 283 woff2 239.1; embedding font 56.9 MB largest); ≈243 MB on the wire
with brotli text. GitHub Pages fits the limits (100 MB/file, 1 GB site) but its 100 GB/month soft cap ≈ 330–400 first-time
visitors; Cloudflare Pages (25 MiB/asset) cannot; S3/CloudFront/nginx fine with precompressed `.br` + `Content-Encoding`.
Fonts same-origin → no CORS. Chrome/Edge ≥ 139 only (@function 139, if() 137, calc-size() 129, anchor positioning 125,
view timelines 115, @container style() 111); Firefox/Safari do nothing. 50 Mbit/s download ≈40–47 s. Memory ≈2 GB after
load, 4.4 GB RSS / 6.2 GB footprint while generating → 16 GB machines minimum, warn. Recipe: `R6L/pack_bundle.py
bundles/<b> <out> --br` → zip with the launcher; recipient runs `python3 tools/launch_browser_gpt2.py --directory model`.

Machine during R6L: swap grew 5 → 9.4 GB, disk 7 → 1 GB (user apps) — gate closed the whole session; runs armed.

## R6V — pure-CSS progress UI (R6V.md; bundles/combined8-ui, combined8-c32-ui; offline PASS, Chrome gated)

- Exact per-token progress: an 8-element reader `.pg` as the first child of `.core-controller` (inside the `corestate`
  container, sibling of the model root, no inline styles/custom properties, inherits the parent trie by pointer); 12
  `@container corestate style(--layer:k)` rules → "· layer k+1 of 12" + k/12 fill; `style(--held:1)` → "12 layers done ·
  vocabulary head". Only 3 container-dependent elements → predicted ≈0.25 ms/token (the 163-element per-layer pass → 166).
- Token counter "token t of 8/32" from body's `--epoch` (`@container runtime style(--epoch:t)`).
- Cosmetic within-layer fill: compositor-only `transform:scaleX()` animation restarted per layer, duration = measured mean
  s/layer (1.17 s at cap 8; per-epoch (12.05 + 0.975t − 1.9)/12 at cap 32); labelled as an estimate; width animations
  avoided (main-thread frames × R4T's ≈28 ms servicing floor). `R6V_SMOOTH=0` twin exists to isolate its frame cost.
- Load indicator: exact "Loading model weights: N of 283 fonts" from the 283 `.font-proof-i` widths summed by a 16-fan-in
  anchor-size() tree → inline-size container read by 283 `(min-width:N px)` range rules; plus early paint: 1 KB inline
  head style (controls + "Loading the model's stylesheet…" panel), the `<link>` moved into `<body>` after the panel, and
  `body>:not(.controls):not(.ld){content-visibility:hidden}` until runtime.css lifts it (avoids R6L's 31 s unstyled layout
  while keeping the panel visible). Merge decision: take R6V's early-paint variant, R6L flags off (R6L/split-point.md).
- Offline: flag-off twins byte-identical to combined8 / combined8-c32; model-rule multiset and order identical; UI adds
  396/452 rules (+48/54 KB) and 31 elements; no JS. Bug caught in emitted CSS (`\00b7 layer` hex escape ate the space).
- Chrome plan (armed, gated): smoke trio with trace + screenshots (acceptance: identical pass counts except +3 elements in
  the per-layer pass, no new frames), load-paint probe with screenshots at 0.5/1/2/4/8 s, ONE 8-token correctness run.

## R6P — prompt echo fix + typed prompts (R6P.md; bundles/combined8-c32-prompt, combined8-prompt; offline PASS, Chrome gated)

- **Why the dropdown "did nothing"**: `#visible-output::before` renders `counter(prompt, gpt2-vocabulary)` from
  `--frozen-prompt`, which is registered `inherits:false`; a pseudo-element only inherits inherited properties, so inside
  `::before` the value is the registration's initial 0 → token 0 = "!" for every prompt. The model itself did receive the
  selection (harness-verified in rounds 4–5); only the echo was broken. Fix: 2 rules (`--display-prompt` relay on
  `.visible-output`), zero per-token cost.
- **Typed prompt**: TinyStories' CSS-only tokenizer ported. An editable `<style contenteditable>` sets a private
  `--draft-prompt`; the two existing GPT-2 token-id fonts (vocab dict-equal to data/gpt2) render the text at 1 px where each
  glyph advance encodes the token id in base-32767 digits → `anchor-size()` → inline-size container → `round()` → ids;
  4 prompt slots (N = 4, fonts built for 4 positions; ≤ 8 practical). Typing restyles ≈25 elements, never the model; the
  model-facing ids are armed only on Run and frozen by the 86,400 s latch. Prefill = teacher-forcing epochs 1..N through the
  SAME full-vocabulary HVAR embedding lookup that fed-back ids use → exact class (TinyStories' approximation came from its
  8-bit feedback table, absent here). Cost: each prompt token is a full step (≈65 s before the first new token for a 4-token
  prompt); 33 − N new tokens. Tokenizer vs Python BPE: 22/26 prompts identical ("Once upon a time" → 7454, 2402, 257, 640;
  "I" → 40); mismatches only newline / double space / non-ASCII (documented).
- References: typed "I" == R4P/reference_ids_32_40.json; "Once upon a time" → R6P/reference_ids_once_upon_a_time.json
  (", the world was a place of great beauty and great danger…"; quantized == float all 32 steps).
- Offline: flags-off twins byte-identical to combined8-c32 / combined8; +2 tokenizer faces (285 witnesses), +33 elements,
  css +1.0 MB; no JS. Chrome armed: 2-layer smoke, cap-8 Hello 8/8, typed "I" 32/32, typed "Once upon a time" 32/32.
  Residual risk: the model now sits inside 4 absolutely positioned inline-size containers — the smoke/correctness runs test it.

## R6X — merged demo bundles (R6X.md; bundles/demo-c32, demo-8; offline PASS; Chrome gated)

demo-c32 = combined8-c32 + R6P (echo fix, typed prompt N=4) + R6V (progress UI, early paint, smooth fill, font-count loader);
R6L flags off (R6V's early-paint variant taken). Merge: 1 import reject, 3 semantic conflicts resolved as exact-string edits
(panel rows 52/118/146/184; early-paint lock excludes `.tk-panel`; the editable `<style>`'s visual rules moved into the inline
head style). Offline: all-flags-off twins byte-identical to combined8-c32 / combined8; single-owner twins identical to the
owners' bundles; model rules identical (66,711 / 62,077) and ordered; witnesses 285 (271 F4 + 12 dot + 2 tokenizer); NumPy
Hello 8/8, prompt 40 32/32, "Once upon a time" == R6P reference; no JS (287 files); pack dry-run resolves every url():
demo-c32 = 299.9 MB (fonts 242.4 MB). README.txt for recipients written. Chrome chain armed: demo-8 Hello 8/8 → READY;
demo-c32 load-paint screenshots (0.5/1/2/4/8 s); typed "I" 32/32 with mid-token screenshots; typed "Once upon a time" 32/32
→ READY. View: `python3 tools/launch_browser_gpt2.py --directory work/2026-09-19/bundles/demo-c32`; pack:
`R6X/pack_demo.sh demo-c32 <out> --br`.

## Round 6 — Chrome verification (2026-09-30 18:31–19:07, gate finally open: swap 3.6 GB, disk 6 GB)

| Check | Result |
|---|---|
| demo-8, dropdown Hello | **8/8 ids**, verify rc 0, RSS peak 4.6 GB → READY |
| demo-c32 load | load event 2.16 s, **Ready (285 fonts) at 2.32 s** (was 34 s); prompt echo shows "Hello" (was "!") |
| demo-c32 typed "I" | **32/32** == R4P reference; 922.0 s (R5X's combined8-c32 905.6 → the UI costs nothing measurable); RecalcStyle ≈102/token (72 + the progress reader), Layout 64; RSS peak 4.5 GB; screenshots show "token 3 of 32 · layer 1 of 12" with the bar |
| demo-c32 typed "Once upon a time" | **32/32** == R6P reference; 887.8 s; output "Once upon a time, the world was a place of great beauty and great danger. The world was a place of great danger, and the world was a place of"; RSS peak 7.3 GB → READY |

Cosmetic bug found in the final screenshot: a 2-line output overlaps the footer paragraph (fixed rows); R6X is fixing it with
a layout-only change (model rules byte-identical) and re-verifying with a load-paint probe + one cap-8 correctness run.
Deliverable: `bundles/demo-c32` (view: `python3 tools/launch_browser_gpt2.py --directory work/2026-09-19/bundles/demo-c32`;
pack: `R6X/pack_demo.sh demo-c32 <out> --br`, ≈300 MB, Chrome/Edge ≥ 139, 16 GB RAM).

## Round 6 — final (2026-09-30 22:00)

- **v4 bundles swapped in atomically** (`bundles/demo-c32`, `bundles/demo-8`; `.prev` kept): output box `max-height:
  calc(100vh − 280px); min-height:4lh; overflow:auto`, footer follows it; head-phase 13th segment (orange, pulse + ≈2.8 s
  estimated fill, label "vocabulary head: 50,257 rows → next token…"). Model rules identical in multiset and order.
- Guards after v4: "Once upon a time" to Complete at 900×300 and 1100×700 (no overlap, screenshots); demo-8 Hello 8/8.
- **User report "Shubham was → blank, then 't'": NOT reproduced.** hb-shape: fonts give [2484, 549, 2763, 373] = Python
  BPE. NumPy reference: "Shubham was a member of the U.S. House of Representatives from 1994 to 1999. He was a member of
  the U.S. Senate from 1994". HEADED Chrome 154, 1100×700, the user's launcher: 2-layer smoke 32/32; demo-c32 **32/32 in
  975.7 s**; dumps at 5/30/90 s/Complete show readout "[Sh][ub][ham][ was]", prompt-count 4, correct ids and display tokens;
  screenshots show the prompt echoed during prefill and the full text at Complete. Readback and display relay ruled out.
  Most likely cause: the user's tab had files from two different builds (demo-c32 was rebuilt IN PLACE at 19:23 / 20:06 /
  21:15 while they were testing) — now prevented by the `.next`/`.prev` swap protocol. Other candidates: Run pressed before
  Ready (→ dropdown fallback, not blank), hand-typing artefacts (→ fallback, not blank).
- Rule adopted: never rebuild a bundle a human may have open; build to `.next` and swap.
- Deliverable: `bundles/demo-c32` READY (Hello/dropdown path, typed "I", "Once upon a time", "Shubham was" all 32/32; load
  Ready ≈2.2 s; progress UI exact per layer/token; head-phase indicator estimated). Pack: `R6X/pack_demo.sh demo-c32 <out>
  --br` (≈300 MB, Chrome/Edge ≥ 139, 16 GB RAM). Open item: RecalcStyleCount 102/token vs 72 before the UI (no measurable
  s/token change; R6V smoke trio can attribute it).

## Round 6 — typed-prompt race (2026-10-01, R6X.md §10)

User (fresh load → type "Shubham was" → mouse-click Run): model ran the dropdown prompt (comma = Hello's 5th token) while
the display showed the typed prompt. **Root cause**: the core's layer 0 is gated by an embedding receipt whose stamp encodes
only the EPOCH (`20000px + epoch·1024px`). Before Run, `--epoch:1` and `--token` falls back to the dropdown token, so the idle
Hello embedding is already stamped "1"; at Run `--token` switches to the typed id but the receipt is already satisfied, so
layer 0 can consume the stale Hello embedding before the 768 `--embed-t*` view-timeline readbacks land (≥ 2 frames; likelier
with slow frames under memory pressure / 150 % zoom). Dropdown runs never change `--token` at Run → immune; the harness won
the race 10/10 with fast frames. Secondary: the 86,400 s latch freezes the before-change value when arming and latch land in
the same pass. **Fix (v5)**: token-fresh receipt (`(epoch − 1 + --prompt-live)·1024px`, `--prompt-live` 0 → 1 at arming);
sticky arming via `#run:checked` / `#run-latched.done` (latch removed); editor read-only from Run; Run enabled only after
fonts-loaded; display keyed on the armed model-facing values (live preview before Run, the model's actual prompt after).
Model core rules identical (identity check PASS). Verification armed (per-frame ordering probes old vs fixed, atomic swap,
demo-8 8/8, headed keystrokes + mouse "Shubham was" 32/32, "Once upon a time" 32/32) — waiting on AC power (battery since 02:28).
Reset = form GET navigation (fresh document); a browser Reload restores the checked Run box and autostarts the dropdown run.

## R7P — parallel prefill and the 32-new-token budget (R7P.md; research, models on measured constants)

- Prefill cannot be parallelised cheaply: frames are per geometry→number hop per position, not per step, so reordering
  work amortises nothing; N parallel core copies would save ≈7.7 s beyond the cheap fix for +31k elements / +25k timelines
  and probably +2.3 s on every token from servicing locked copies' timelines. **Cheap exact win: skip the 50,257-row head on
  prefill epochs 1..N−1 (its winners are discarded): 64.4 → ≈56.6 s for a 4-token prompt (−12 %), ≈40 lines** (head stays
  content-visibility:hidden on prefill epochs; token-captured SMIL gets a second begin condition from `--held:1`).
- Budget: capacity is build-time but fully parameterised except one argparse guard (`2 <= capacity <= 32`). Per slot
  +788 elements, +462 KB CSS, +768 V leaves; c36 ≈ 89.7k elements, 52 MB CSS, depth 186/512. Marginal epochs 33–36 cost
  44–47 s each; a 4-token prompt with 32 NEW tokens = 35 epochs ≈ 1,045 s (17.4 min), +0.4–0.6 GB. **Recommendation: one
  capacity-36 build + a prompt-count-dependent stop rule at epoch 31 + max(N,1)** (dropdown runs stay 32 epochs ≈ 906 s;
  typed 4-token runs take 35) — "32 + N dynamically" from a single build.

## R7S — sampling in pure CSS (R7S.md; fixture verified on the real 50,257-row head)

**Yes, zero JS, no model change.** Gumbel-max inside the existing head: argmax_i(score_i + T·g_i) samples softmax(logit/T)
exactly, and the head already is a 50,257-row argmax. Noise = a build-time table (64 seed columns × 50,257 rows,
rint(clip(Gumbel,−3,12)·SCORE_GAIN·256), rng seed 20261001) shipped as a 7th "noise font" (one glyph per row at
U+80000+token; HVAR axes `SEED` (64 exact tent regions) and `TEMP`); each head row gets one extra character and
`"SEED" col,"TEMP" T` appended to the latched `--head-fvs`; `size-adjust` puts one font unit = 1 q on the head's lattice;
T=0 is bit-identical to greedy (default + reference). Entropy: a free-running `--clock` animation 0→64 over 0.97 s frozen
by `animation-play-state:paused` on `#run:checked` (the click time is the seed; displayed; overridable from a 64-entry
`<select>`); per-step column = mod(seed + epoch − 1, 64) + 1 — same seed replays identically. Probe PASS (seeds stable
over 1.8 s; override works). **Fixture: 21/21 browser winners == NumPy argmax(q + rint(n[col]·T)) over 3 states × greedy /
3 seeds × T ∈ {1.0, 0.7}, incl. a 12-q margin case.** Cost: +10 % on the head's style+layout (projected +0.2–0.3 s/token),
0 new head elements, +7.9 MB TTF (≈6.5 MB woff2), ≈75 UI rules. Fidelity over 38 states: greedy frequency across columns
0.080 vs softmax mass 0.085; lattice vs float Gumbel winners agree 99.75 %. Top-k/nucleus: exact infeasible (ranks /
prefix sums over 50k rows); cheap substitute = clipping the noise table (min-p-like). Reference protocol: run = (prompt,
seed, T), verifier scores() → rint(raw_q + n[col]·T), sampled ids teacher-forced. Caveat: browser Reload restarts the
clock (seed 1) — use Reset. Not yet: a 32-token sampled demo run; hooks: f4_packing.py:136-165, browser_gpt2_head.py:compile_head.

## The real cause of the id flips (R7H, 2026-10-01 13:4x) — a scrollbar

`.feedback-scroller{width:524288px;height:1px;overflow:scroll}` carries the winner id as `.feedback-metric-e{width:
65536px + (id+1)·8px}` read back by a view-timeline; the decode hardcodes scrollport = 524288 px. In HEADED Chrome on a Mac
with "Show scroll bars: Always" a classic vertical scrollbar takes 15 px of the scrollport → the decoded id is biased by
(65536 + 8(id+1))·2.86e-5/8, which rounds to **+1 for every id ≥ 9283** and 0 below. Fits every run: Hello max id 7926
(bias 0.46, passes barely), "Once upon a time" max 8737 (0.49, passes barely), "Shubham was" ids 1–13 < 2888 then
17132 → 17133 (both headed runs), 2-layer smokes max 6646 (never flip), v4 "Shubham" 32/32 was headless (no classic
scrollbar). Only this scroller is affected (the `--embed-*` readbacks use no hardcoded scrollport). The user's own blank /
"EARTH" outputs are this bug. Withdrawn: the load theory (§10.M) and the v5-wiring theory. Fix: `.feedback-scroller
{scrollbar-width:none}` (R6X v6) + R7H's calibration metric (a constant 50256 that must decode exactly, gating
#token-e-ready with a visible message) and an echo-vs-latched agreement gate. Protocol: headless harness runs cannot see
scrollbar effects — a HEADED acceptance run on a prompt whose reference contains an id ≥ 9283 is now mandatory.

**v6 (scrollbar fix) verified, 2026-10-01 14:09**: positive control = OLD build headed with scrollbars shown, typed "I" → flipped
at position 16 (bug reproduced on purpose); v6 headed + scrollbars: typed "I" **32/32**, "Shubham was" **32/32**; demo-8 Hello
8/8. `bundles/demo-c32` and `demo-8` are v6 (atomic swap). Lesson for the protocol: the harness's `--hide-scrollbars` had
hidden an environmental bug from every headless run; headed + scrollbars-shown is now a mandatory acceptance arm.

## R7T — below 15 s/token? (R7T.md; parsed R5A's time8 trace + fixtures on the real fc stage and real head)

**Answer: ≈13.5–14 s/token is reachable exactly; the architecture's floor is ≈12.5; 10–12 is not reachable in stock Chrome.**
Key finding: R5A's "45 µs per carrier" in the fc/qkv/attn write passes is not the carriers (3 µs each, +4 µs as a timeline
subject) — ≈70 % of the write pass is the R4T consumer chunk chain (48 elements × 64 unchanged animations ≈25 ms + 192 var()
decode declarations ≈28 ms) being re-cascaded because it sits ABOVE the stage's receipt/gate. Fixture: moving the chain INSIDE
the existing content-visibility gate cuts the fc write pass 69–87 → 16–26 ms with bit-identical outputs (sibling placement
does nothing).
Levers (exact): (1) chunk chains inside the stage gates **−1.0…−1.2 s/token** (emitter build_hybrid_twelve_block.py:254,293,
reused_core.py:175); (2) token-boundary SMIL handshake → style stamps −0.2 s; (3) declaration-identical head rows −0.2…−0.3 s
and −150…−280 MB (needs a lattice screen; 6 head faces rebuilt); (4) clean-memory session −0.5 (GC); (5) K-list text at the
96 score elements 0.5 s at p=8 / ≈2 s at p=32 if lossless; (6) stage rule text −0.1.
Closed with numbers: PrePaint is ink-overflow ∝ changed glyphs (no CSS knob); per-frame fixed = animate + lifecycle ≈60–70 ms
= 6.5–7 µs per live timeline per frame → 2.2 s/token, reducible only by fewer timelines/frames (all routes closed); 2 values
per timeline via subject position+size is lossy (×5–10 error); metric (font-instance) transport wall stands (≥200 µs/value
for instance creation vs ≈55 µs/value glyph path); 768-axis Fontations font loses the precision class; head two-level argmax
via metrics impossible (group maxima are layout results). Floor table: servicing 2.0 + changed-animation application 1.9 +
pending updates 1.5 + carrier layout/shaping 1.9 + ink overflow 0.8 + carrier restyle 0.7 + head 2.3 + KV/scores/V 1.2 +
per-pass fixed 0.45 + token start/export 0.5 + GC 1.0 ≈ **12.5 s/token** after levers 1–3.

## R7B — capacity 36 + prefill head-skip + sampling (in progress; Chrome results so far)

- 2-layer typed smoke "Once upon a time" T=0: 35/35 epochs, 32 NEW tokens identical; prefill epochs 1..3 = 6.8 / 2.3 / 2.3 s
  (head skipped on epochs ≥ 2 of the prefill).
- **demo-c36 typed "Once upon a time" T=0: 35/35 ids (32 new tokens == reference); prefill epochs 16.3 / 10.8 / 12.9 s
  (head-skip ≈ −3 s per prefill epoch); total 1,034.9 s for 35 epochs** (R7P predicted ≈1,037); median 33.0, first 16.3,
  last 49.7 s. Sampled runs (seed 17 T=1.0, seed 42 T=0.7) queued behind the gate.

## R7H — self-checking id transport (R7H.md; bundles/demo-c32.r7h, demo-8.r7h; not yet swapped in)

Guard `R7H_ID_GUARD`: a calibration metric (constant id 50256, max sensitivity) must decode exactly or `#token-e-ready` is
blocked and a red "Geometry self-check failed" panel shows; plus a per-slot echo-vs-latched `--saved-token-e` agreement gate
on `#token-e-ack` so the model never consumes a disagreeing id. +2 elements, +1 timeline, +34 animations, +16.4 KB CSS, no
model rule, **zero new frames (measured: per-token ΔRecalcStyle/ΔLayout identical to guard-off)**. Chrome: 2-layer smoke
guard off 32/32; guard on headless 32/32; guard on HEADED with classic scrollbars 32/32 (calibration 0.52858 exact;
clientWidth 524288 with v6's fix); **fault injection (scrollbar fix off, guard on, headed + scrollbars): clientWidth 524273,
calibration decodes 50257.7 → --fb-ok 0, run held before token 1 with the panel visible** — the exact failure environment is
caught, not silently corrupted. Pending: stress (6×yes), demo-8 Hello, demo-c32 headed "Shubham was", headless "I".
Inventory of other environment-sensitive constants: 13 overflow-x scrollers safe; 100vw/100vh display-only; Chrome's
"minimum font size" setting would break the 1 px tokenizer metrics; device scale factor 2 untested by the harness.

## R7B — final (R7B.md): capacity 36 + prefill head-skip + Gumbel sampling, on R6X v6

Module `r7b_features.py` + 8 call sites (93-line diff). Offline: flags-off twins byte-identical to demo-c32 v6 / demo-8;
model core rules identical modulo exactly the intended head-row glyph/axis additions; no JS; 286 fonts resolve. NumPy
references: "Once upon a time" T=0 35 epochs; sampled seed 17 T=1.0 ("…the questions and answers about your child and much
more to choose, were written into the book…", 23/32 steps differ from greedy); seed 42 T=0.7 ("…the thought of such a
country is unthinkable. But it is not possible because of the favoritism…", 17/32 differ). Chrome: demo-8.r7b Hello 8/8
(14.3 s/token median); **demo-c36 typed "Once upon a time" T=0 35/35, 1,034.9 s** (prefill epochs 16.3/10.8/12.9 s = −2.6…−3 s
per skipped head); 2-layer smoke Hello seed 17 T=1.0 **32/32 vs the sampled reference** (seed override + temperature + column
rule + noise glyph verified end to end). Note: the 2-layer smoke Hello T=0 is 31/32 at epoch 19 (1-q margin) on BOTH the new
and the flags-off bundle — pre-existing, smoke-only. Pending: the two 12-layer sampled runs (armed; machine on battery since
16:52). Costs: cap-32 flags-on +264 KB CSS, +204 KB HTML, +8.3 MB noise font; cap 36 vs 32 +3 MB CSS. Deliverables:
bundles/demo-c36.next (READY), demo-8.r7b (READY). Found/fixed: R6V's `.pg` show rule outranked every hide rule (pre-existing).
- **Sampling verified on the 12-layer model: demo-c36 typed "Once upon a time", seed 17, T=1.0 → 35/35 ids == the sampled
  NumPy reference** (Gumbel-max via the noise font; "…the questions and answers about your child and much more to choose, were
  written into the book…"). 1,533 s on BATTERY (throttled; timing not comparable). Seed 42 T=0.7 next.
- **Second sampled run: demo-c36 typed "Once upon a time", seed 42, T=0.7 → 35/35 ids == reference** ("…the thought of such a
  country is unthinkable. But it is not possible because of the favoritism…"); 1,543 s on battery. R7B's chain complete.

## Round 7 close (2026-10-01 21:18) — live demo = capacity 36 + prefill head-skip + sampling + id guard (R7X.md)

`bundles/demo-c32` (name kept; capacity 36 → 32 new tokens) and `bundles/demo-8` swapped atomically at 21:17:50 (v6 → .prev).
Merge = R7B/tools + R7H guard (3-line diff); guard-off twin == demo-c36.next byte-identical; R7B-off twins == the .r7h bundles;
model core rules identical; 286 fonts, no JS, pack dry-run 312 MB. Chrome acceptance (all on battery or swap-loaded → no
timing claims): demo-8 Hello 8/8; **headed + scrollbars typed "Shubham was" T=0: 35/35 (32 new tokens; position 14 = 17132;
"…House of Representatives from 1994 to 1999. He was a member of the U.S. Senate from 1994 to 1999.")**; headed + scrollbars
Hello seed 17 T=1.0 via the selects: 32/32 vs the sampled reference; headless typed "I" T=0: 32/32; load-event 2.03 s, Ready
2.2 s, controls painted at 0.5 s, "absorbing prompt token 2 of 4" shown mid-prefill. Known nits: footer says "at most 36
generated tokens" (prints the capacity); clean AC timing arms still owed; README documents Reset vs Reload and the
geometry self-check panel. Permission note: a detached (nohup) relaunch of R7X's chain was denied by the permission system;
the agent ran steps one at a time instead — no effect on results.
