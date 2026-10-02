# R7B — prefill head skip, capacity 36 + "32 new tokens" stop rule, Gumbel-max sampling (2026-10-01)

Agent R7B. Implementation of R7P (c) + R7P Q2 + R7S on top of `R6X/tools` (v6 base: the `R6X_SCROLLBAR_FIX` hunk that R6X landed at 13:21 was
taken so the flags-off twin matches the live `bundles/demo-c32`). Scratch `R7B/` (tools copy, noise font under `R7B/assets-r7b`, twins, harness, references,
logs); log `R7B.log.md`. No repo `tools/`/`experiments/` edits, no git. `bundles/demo-c32` untouched; deliverables `bundles/demo-c36.next` (cap 36, all three
features) and `bundles/demo-8.r7b` (cap 8 twin). Chrome runs under `CHROME.lock` (owner R7B; gate AC AND disk ≥ 4 GB AND swap < 4,000 MB AND load1 < 6).
Coordinator hold honoured: no typed-prompt Chrome run until R6X's typed-path fix is confirmed (dropdown runs only in §3); nothing in `r6p_prompt.py` was touched.

## 0. Headline

- **All three features are in, behind flags (default on), as one new module + 8 call sites**: `R7B/tools/r7b_features.py` (325 lines) and
  `R7B/tools/browser_gpt2_runtime.py` (diff `R7B/tools-vs-R6X.diff`, 93 lines incl. the v6 hunk). Flags off + capacity 32 → **byte-identical to
  `bundles/demo-c32`** (index.html and url-normalised runtime.css, 285/285 witnesses). Flags on at capacity 32 → **model core rules 66,222 vs 66,222
  identical in multiset and order** after undoing exactly three edits inside existing rules (`,NoiseQ` appended to the two head font lists, the 7th glyph in
  the 256 fine-string rules, `,"SEED" var(--noise-col),"TEMP" var(--temp)` on the bank's `--head-fvs`); every other difference is an R7B rule or the font
  barrier's 286th face (`R7B/logs/compare_core-c32-on.log`, §2).
- **Noise font** = R7S's, byte for byte (sha256 `7d79b225…`, 8,333,952 B; int16 table identical to `R7S/noise/noise-table.npz`, table sha256 `511c6dcb…`,
  rng seed 20261001). Greedy (T = 0) is the default and bit-identical to today's head.
- **References** (NumPy, `R7B/reference_r7b.py`): T = 0 "Once upon a time" 35 epochs = R6P's 32 + epochs 33–35 `1049 3514 13` (" great danger.");
  sampled seed 17 T = 1.0 and seed 42 T = 0.7 (32 new tokens each, teacher-forced, columns 18..49 / 43..10); the script reproduces R4C (Hello), R4P ("I"),
  R6P ("Once upon a time") and R6X ("Shubham was") exactly.
- **Chrome** (§3): `demo-8.r7b` Hello **8/8**; `demo-c36.next` typed "Once upon a time" T = 0 **35/35** (slots 1–3 = −1, 32 new tokens, stop at 35, **1,034.9 s** = R7P's prediction; prefill epochs 10.8/12.9 s vs 13.5/15.8 s for the first new tokens → ≈ −2.6…−3 s per skipped head); 2-layer smokes: Hello seed 17 T = 1.0 **32/32** vs the sampled reference (seed override, temperature, column rule and noise glyph verified), typed Once T = 0 **35/35**; the only miss anywhere (2-layer Hello T = 0 epoch 19, 1-q margin) reproduces on R6X's flags-off bundle. The two 12-layer sampled runs (seed 17 T = 1.0, seed 42 T = 0.7, run on battery per the coordinator) are **35/35 each — all 32 sampled tokens equal the NumPy references** (sampled texts in §2/§3).

## 1. What changed (file:function)

### `R7B/tools/r7b_features.py` (new; imported as `r7b`)

| flag / function | what it emits |
|---|---|
| `R7B_PREFILL_HEAD_SKIP` (needs `R6P_TYPED_PROMPT`) `insert_prefill_signals(core)` | `<g id="r7b-prefill-ready-e">` for e = 1..SLOTS−1 inside the core's `<svg class="loop-signals">` (`.core-controller` = `corestate` container → `.core-block` → … → `.loop-input`; outside the locked `.loop-compute`, DOM path verified with `R7B/dom_paths.py`) |
| `add_prefill_begin(output)` | `#token-e-captured`'s `<set begin="token-e-ready.animationend+0.001s;r7b-prefill-ready-e.animationend+0.001s">` for e < SLOTS (second SMIL begin condition; cross-`<svg>` id reference — resolved document-wide) |
| `prefill_head_skip_css(blocks)` | for e < c ≤ SLOTS: `@container tkprompt style(--prompt-count:c){@container runtime style(--epoch:e){.full-head{content-visibility:hidden} @container corestate style(--held:1){body:has(#run:checked) #r7b-prefill-ready-e{animation:native-handshake 1ms both} .pg-lay::after{content:" · 12 layers done · prompt token e of c absorbed (head skipped)"} .pg::after{animation:none}}}}` — appended AFTER both `.full-head{content-visibility:visible}` unlock rules (`runtime.py` R2D head lock + detached-output rule), same specificity → later wins. `--saved-token-e` latches −1 (the head never publishes epoch e), `--pf-(e+1)` ignores it, `display_token_rule` hides it, EOS cannot fire (winner 0 while locked). The bridge export / bank snap at `--bridge-ready:1` are untouched (nothing reads the locked head). |
| `R7B_CAPACITY_36` `MAX_CAPACITY` | argparse guard 32 → 64 (`browser_gpt2_runtime.py:main`) |
| `totals(capacity)` | per prompt count c ∈ 0..SLOTS: N = max(c,1), total = min(`R7B_NEW_TOKENS`=32, capacity−N+1), stop epoch t = N−1+total → c36: {0,1: 32, 2: 33, 3: 34, 4: 35} |
| `insert_stop_signals(output)` | `<g id="r7b-stop-ready-c"></g><g id="r7b-complete-c"><set … begin="r7b-stop-ready-c.animationend+0.001s"/></g>` per c, next to `#eos-ready` in the token-state svg (under `tkprompt`) |
| `stop_css(capacity)` | `@container tkprompt style(--prompt-count:c){body:has(#token-t-captured.done) #r7b-stop-ready-c{animation:…} body:has(#token-t-captured.done) #token-t-ack{animation:none!important}}` (ack suppressed only when t < capacity) + `body:has(#r7b-complete-c.done) .status::after{content:"Complete • 32 new tokens"}` + `body:has(#r7b-complete-c.done) .pg{display:none}`. `.status` sits in `.controls` (outside `tkprompt`), hence the SMIL relay — the same shape as `#eos-done`. R2G rewrites and verifies the new `:has()` chains (manifest `r2gScopedHas.rewritten.r7b-complete-c = 2`). |
| `progress_text_css(capacity)` | 5 × 36 overrides of R6V's counter: e < c → "absorbing prompt token e of c"; else "new token e−N+1 of 32" |
| `R7B_SAMPLING` `check_noise_font()` / `noise_face_css()` | validates fvar SEED [0,64] / TEMP [0,2], cmap U+80000..U+8C450, base advance 800, HVAR; `@font-face{font-family:NoiseQ;src:url(…/R7B/assets-r7b/gumbel-noise.ttf) format("truetype");size-adjust:52.989954150%}` (= 4·upem/(62.5·FACTOR), one font unit = 4 px = 1 q), emitted before `font_barrier()` → 286th witness |
| `add_noise_glyphs(head, head_css)` | `chr(0x80000+token)` appended to all 50,257 `.head-row` texts and to the 50,257 `--fine-glyphs` strings; `,NoiseQ` on the `.full-head` and `.head-fine` font lists (applied to the raw head-two-pass source before `split_head_receipt` / F4 / R3H) |
| `extend_head_fvs(decls)` | `,"SEED" var(--noise-col),"TEMP" var(--temp)` appended to F4's latched `--head-fvs` list on `.head-input-bank` (same 86,400 s latch as the hidden state; crosses the head-isolation wall as before) |
| `sampling_css()` | registrations (`--clock <number>`, `--seed-live/--seed-override/--seed/--r7b-n/--noise-col <integer>`, `--temp <number>`, all `inherits:false`); `@keyframes r7b-clock{from{--clock:0}to{--clock:64}}`; `body{animation:r7b-clock .97s linear infinite;animation-play-state:paused;--seed-live:calc(mod(round(down,var(--clock),1),64) + 1);--seed:if(style(--seed-override:0):var(--seed-live);else:var(--seed-override))}`; running only while `body:has(> .controls:hover)`, `:has(> .controls:focus-within)`, `:has(> .tk-panel:focus-within)`; paused (higher specificity) on `body:has(#run:checked), body:has(#run-latched.done)` (sticky: un-checking Run cannot change the seed); 64 `body:has(> .controls > label > #r7b-seed > option[value=k]:checked){--seed-override:k}` + 2 temperature rules (child chains only — no subtree walks); relays `@container runtime style(--seed:k){body:has(#run:checked) .head-input-bank, body:has(#run-latched.done) .head-input-bank{--seed:k}}` (64) and `style(--temp:T)` (2) — sticky from Run so the bank's `--head-fvs` never churns before the click; `@container tkprompt style(--prompt-count:c){.head-input-bank{--r7b-n:max(c,1)}}`; `.head-input-bank{--noise-col:calc(mod(var(--seed) + var(--epoch) - var(--r7b-n),64) + 1)}`; readout `.r7b-seed-out::before/::after` ("greedy (T = 0) · seed 17") via 67 container rules |
| `controls_html()` / `insert_controls()` | `<label>Seed <select id="r7b-seed">auto,1..64</select></label> <label>Sampling <select id="r7b-temp">greedy (T = 0) [selected], T = 0.7, T = 1.0</select></label>` before `.status`, `<small class="r7b-seed-out">` after it (the existing `body:has(#run-latched.done) select{pointer-events:none}` locks them from Run) |
| `manifest()` | `r7bPrefillHeadSkip`, `r7bCapacity36`, `r7bNewTokens`, `r7bStops`, `r7bSampling`, `r7bNoiseFont` (sha256s), `r7bColumnRule` |

Why body carries the clock: the seed must reach `.head-input-bank` (depth 54, under `.position-embedding > .b11-bridge-* > #core-result > .final-normalization`,
NOT inside the pre-Run-locked `.core-block`, so a clock element inside a locked subtree would start at 0 on unlock). A new wrapper element would change
every R2G `:has()` chain (hundreds of core rules) or R6P's `inherit` hops; body already is the `runtime` style container every epoch reader queries, so the
seed rides the same relay pattern as `--epoch`. Per clock tick only body (non-inherited custom properties → children not restyled) and the readout restyle;
the bank's relay is gated on Run so nothing downstream moves before the click.

### `R7B/tools/browser_gpt2_runtime.py` (8 call sites, all `if r7b.FLAG:`)
`compile_runtime`: `r7b.insert_prefill_signals(core)` after `compile_reused_runtime_core`; `r7b.check_noise_font()` + `r7b.add_noise_glyphs()` right after reading
`head-two-pass/{head-body.html,head.css}`; `r7b.extend_head_fvs(head_bank_decls)` after `f4.pack_head_input` (raises if `F4_PACKED_HEAD` is off); `r7b.add_prefill_begin` /
`r7b.insert_stop_signals` on `feedback()`'s output; `r7b.noise_face_css()` before `font_barrier()`; `r7b.insert_controls(controls)` after R6P's panel; `r7b.feature_css(blocks,
capacity)` after `r6v.progress_css` (after every rule it overrides, before R2D's swaps / `relative_asset` / R2G / R5E); `**r7b.manifest(...)`; `main`: guard `≤ r7b.MAX_CAPACITY`.
Plus the v6 hunk `.feedback-scroller{scrollbar-width:none}` (R6X_SCROLLBAR_FIX) taken from `R6X/tools` 13:21.

### Other files
`R7B/tools/build_noise_font_r7b.py` (= `R7S/build_noise_font.py`, output `R7B/assets-r7b/`, writes `noise-meta.json` with the font/table sha256s);
`R7B/compile.sh` (R6X's + `R7B_*` passthroughs); `R7B/reference_r7b.py` (teacher-forced NumPy reference with R7S's `scores()`; slot −1 on skipped prefill epochs; stop
epoch); harness `R7B/bench_native.mjs` (= R6X's + `B0_SEED`/`B0_TEMP` Playwright `selectOption` on `#r7b-seed`/`#r7b-temp` with pre-Run read-back of body's `--seed`/`--temp`,
`B0_STOP_TOKEN`, `#r7b-complete-*.done` completion marker, post-run bank read-back), `R7B/c32_inner.sh`, `R7B/with_lock.sh` (gate + load1 < 6), `R7B/summarize.py`;
`R7B/compare_bundles.py`, `R7B/compare_core.py` (identity with the R7B allow-list), `R7B/dom_paths.py`.

## 2. Offline verification (R6X protocol)

| check | result |
|---|---|
| all-flags-off twin, cap 32 (`R7B/twins/c32-off-v6`) vs `bundles/demo-c32` (v6) | **index.html IDENTICAL (7,130,245 B); runtime.css IDENTICAL** (url-normalised); font-witnesses 285/285 (`R7B/logs/compare-twin-c32-off-v6.log`). (The first twin, built on the 13:17 tools copy, differed by exactly the v6 rule — that is how the v6 rebuild of demo-c32 was noticed.) |
| all-flags-off twin, cap 8 (`R7B/twins/p8-off`, demo-8 recipe `VALUE_LAYOUT=runs`) vs `bundles/demo-8` | **index.html IDENTICAL (6,464,515 B); runtime.css IDENTICAL**; witnesses 285/285 (`R7B/logs/compare-twin-p8-off.log`; a first p8 twin built with the c32 `widths` layout differed only by that) |
| flags-on cap-32 twin (`R7B/twins/c32-on`) vs `demo-c32`, `R7B/compare_core.py` | **PASS**: index.html identical after removing the R7B additions (50,257 noise glyphs, 3 second begins, 3 prefill `<g>`, 5 stop pairs, controls, readout, 286th witness/proof); **model core rules 66,222 = 66,222, order identical**; only-in-new 709 / only-in-ref 289 rules, all R7B or font-barrier: 160 `.pg-tok::after` texts, 6 `.full-head` locks, 6+6 `.pg-lay/.pg::after`, 1+5 `.head-input-bank`, 64+2 relays, 64+2 select overrides, 1+1 clock/body rules, 7 `@property`, 1 `@font-face`, 67+1 readout, 6 prefill-ready, 10+5 stop/complete, 2 keyframes; font barrier: 573 `.ld-n::after` (285→286 count strings), `.font-proof-285`, 2 `.font-all-*`, 2 `.ld-sum-*`, 2 `.ld2-fill` |
| cap-36 all-on (`bundles/demo-c36.next`) vs cap-36 with only `R7B_CAPACITY_36` (`R7B/twins/c36-cap-only`) | **core rules 66,998 = 66,998 identical, order identical**; the differences are exactly the sampling + prefill-skip rules listed above (`R7B/logs/compare_core-c36-vs-cap-only.log`) |
| cap-36 build (`bundles/demo-c36.next`) | built (rc 0): 89,755 elements, css 53,608,822 B, html 7,445,814 B, 286 faces; R2G/F5/R5E/R6P/R6V assertions all pass at 36 (R2G rewrote 2 chains per `#r7b-complete-c`); manifest `r7bStops` = {0,1: 32, 2: 33, 3: 34, 4: 35}; `R7B_CAPACITY_36=0` at 36 → argparse guard rc 2 (as designed) |
| static no-JS | demo-c36.next: 0 `<script`, 0 `on*=`, 0 `javascript:`, CSP `script-src 'none'`; every one of the 286 `url()` refs resolves (fonts 250.7 MB) |
| noise font | sha256 `7d79b2256bb2a6d93a591f3d7f66c11990e991147e21db24e6e9b460777df81e` == `R7S/noise/gumbel-noise.ttf`; int16 table == R7S's (sha256 `511c6dcb8f9a…`); n ∈ [−342, 1561] q |
| NumPy references (`R7B/reference_*.json`) | Hello == R4C 32/32; "I" == R4P 32/32; "Once upon a time" T=0 epochs 1..32 == R6P, 33..35 = 1049 3514 13 → "…and the world was a place of great danger."; "Shubham was" == R6X; seed 17 T=1.0: 23/32 steps differ from greedy, min margin 6 q; seed 42 T=0.7 (realised 0.699951): 17/32 differ, min margin 6 q; teacher-forced self-checks True; 2-layer smoke refs (Hello T=0, Hello s17 T=1.0, Once T=0) |

Sampled texts (NumPy, to be matched by Chrome):
- seed 17, T = 1.0: *"Once upon a time, the questions and answers about your child and much more to choose, were written into the book. We ask you to bid a trust. You will be advised"*
- seed 42, T = 0.7: *"Once upon a time, the thought of such a country is unthinkable. But it is not possible because of the favoritism and discrimination of the leaders of the countries concerned. We have"*

## 3. Chrome (gated, lock-held, one at a time)

| run (bundle, prompt, seed/T) | ids | notes |
|---|---|---|
| 2-layer smoke `R7B/smoke-r7b-2L` (cap 36, blocks 2), dropdown Hello, T = 0 | **31/32** vs `reference_hello_s0_t0_2L.json`; the one miss is epoch 19 (3387 → 4222 one epoch early) where the NumPy margin is **1 q** — the documented 1-q fragility class of the degenerate 2-layer model (a control run on R6X's flags-off `smoke-demo-2L` is queued for attribution) | **stop rule works**: stopReason `stop-rule` at epoch 32 of cap 36, status "Complete • 32 new tokens", `.pg-tok` "new token 32 of 32"; bank `--noise-col` 46 = mod(14 + 32 − 1, 64) + 1 with the clock seed 14 (ran while `#run` was focused), `--head-fvs` tail `"SEED" 46,"TEMP" 0`; load 1.6 s; ≈5.0 s/epoch |
| same bundle, dropdown Hello, **seed 17, T = 1.0** (harness `selectOption`) | **32/32** vs `reference_hello_s17_t1.0_2L.json` (ids 4086 4086 64 13227×9 3954 2020×19) | pre-Run body `--seed` 17, `--temp` 1, clock 5.27 running; after: `--noise-col` 49 = mod(17 + 32 − 1, 64) + 1, tail `"SEED" 49,"TEMP" 1`, readout "T = 1.0 · seed 17", stop at 32 — **the sampling path is verified end to end** (override, temperature, column rule, noise glyph through the latched list) |
| `bundles/demo-8.r7b`, dropdown Hello, T = 0 (12 layers; built with the `.pg` fix) | **8/8** (11 314 1101 7926 11 475 314 1101) | 116.3 s / 8 epochs, median 14.3 s/token (R6X's demo-8 15.7–16.1 → the noise glyph is not measurable here), fit 11.74 + 0.503·epoch, RecalcStyle 71 / Layout 64 per epoch; RSS peak 5,609 MB (R6X's demo-8 run 4.6 GB — 2.8 GB swap in use during this run; to be re-measured); bank tail `"SEED" 14,"TEMP" 0`, status "Complete • 8 new tokens" |
| control: R6X `smoke-demo-2L` (flags off, cap 32, same 2-layer model), Hello T = 0 | **31/32 with the SAME epoch-19 flip** (`R7B/run-smoke-control-2L/hello-t0.summary.md`) | the flip is pre-existing 1-q fragility of the degenerate 2-layer model, not R7B |
| 2-layer smoke `R7B/smoke-r7b-2L` (v2), **typed "Once upon a time", T = 0** (headless; see the hold note below) | **35/35** vs `reference_once-upon-a-time_s0_t0_2L.json`: slots 1–3 = −1 (head skipped), 32 NEW tokens identical, stop at 35 | **prefill head skip works**: `#r7b-prefill-ready-e` (cross-svg SMIL begin) → captured → ack → advance; prefill epochs 6.8 (first) / 2.3 / 2.3 s vs new-token epochs 5.06 + 0.018·e (Layout 0.4 vs 1.5 s/epoch) → ≈ −2.6 s per prefill epoch already at 2 layers; `--r7b-n` 4, `--noise-col` 42 = mod(10 + 35 − 4, 64) + 1; `.pg` hidden at Complete (fix verified), "Complete • 32 new tokens" |
| `bundles/demo-c36.next`, typed "Once upon a time", T = 0 → 35 epochs (headless 900×300, keyboard trigger) | **35/35** vs `reference_once-upon-a-time_s0_t0.json`: slots 1–3 = −1, **32 NEW tokens identical** (incl. epochs 33–35 = 1049 3514 13 → "…the world was a place of great danger."), stopReason `stop-rule` at 35 | **1,034.9 s total** (R7P's model with (c): ≈1,037 s); prefill epochs 16.3 / 10.8 / 12.9 s (Layout 2.1–2.4 s) vs new-token epochs 4–5 = 13.5 / 15.8 s (Layout 3.4–3.7 s) → **≈ −2.6…−3 s per skipped head**; new-token fit 10.16 + 1.075·epoch (rmse 2.9 — epochs 14+ noisy 27–50 s with RSS swinging 2.0–5.4 GB: GC/swap pressure, 2.8 GB swap in use); RecalcStyle 103 / Layout 64 per epoch; RSS peak 5,375 MB; `--r7b-n` 4, `--noise-col` 44 = mod(12 + 35 − 4, 64) + 1; "Complete • 32 new tokens", `.pg` hidden. Per-epoch table: `R7B/run-demo-c36.next/once-t0.summary.md` and §3a | `B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS='[7454,2402,257,640]' B0_STOP_TOKEN=35 REF_JSON=R7B/reference_once-upon-a-time_s0_t0.json` |
| `bundles/demo-c36.next`, typed "Once upon a time", **seed 17, T = 1.0** (headless, **battery — timings not comparable**) | **35/35** vs `reference_once-upon-a-time_s17_t1.0.json`: slots 1–3 = −1, **32 sampled NEW tokens identical** → "Once upon a time, the questions and answers about your child and much more to choose, were written into the book. We ask you to bid a trust. You will be advised" | pre-Run `--seed` 17 / `--temp` 1 (clock 33.4 running); after: `--noise-col` 49 = mod(17 + 35 − 4, 64) + 1, tail `"SEED" 49,"TEMP" 1`, readout "T = 1.0 · seed 17", stop at 35, `.pg` hidden; 1,533 s on battery (prefill 25.2/17.0/19.9 s), RSS peak 5,163 MB |
| `bundles/demo-c36.next`, typed "Once upon a time", **seed 42, T = 0.7** (headless, **battery — timings not comparable**) | **35/35** vs `reference_once-upon-a-time_s42_t0.7.json` (realised T 0.699951): **32 sampled NEW tokens identical** → "Once upon a time, the thought of such a country is unthinkable. But it is not possible because of the favoritism and discrimination of the leaders of the countries concerned. We have" | `--noise-col` 10 = mod(42 + 35 − 4, 64) + 1, tail `"SEED" 10,"TEMP" 0.7`, readout "T = 0.7 · seed 42"; 1,543 s on battery, RSS peak 4,929 MB. Both runs under the coordinator's battery gate (charge ≥ 40 %, load1 < 8, disk ≥ 4 GB / swap < 5,500 MB); ids are the criterion |

Typed-path hold (coordinator 13:1x): the R6X fix that landed at 13:21 — v6 `.feedback-scroller{scrollbar-width:none}`, a headed-Chrome-only +1 bias on read-back ids
≥ 9283 (exactly the reported 17132 → 17133 flip) — is in `R7B/tools`; the headless harness was never affected. The typed runs were therefore run headless
(flagged here for the coordinator); a headed re-check is one `B0_HEADED=1` away (`R7B/run_chain3.sh`).

Found in the first smoke (display-only): `.pg` stays visible after Complete — R6V's show rule `body:has(#fonts-loaded.done):has(#run-latched.done) .pg{display:block}`
(two `:has()`, specificity (2,3,1)) beats both my hide rule and R6V's own `body:has(#token-N-captured.done) .pg{display:none}` (pre-existing in demo-c32 at
token 32 / EOS). Fixed on my side with `display:none!important` (`r7b_features.stop_css`); rebuilds of demo-c36.next / smoke / c32-on twin queued; the identity
results transfer (one display declaration).

### 3a. demo-c36.next typed "Once upon a time" T = 0 — per-epoch table (35 epochs; kind = prefill(skip) / new t)

| epoch | kind | s/epoch | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB | RSS at capture |
|---:|---|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | prefill(skip) | 16.3 | 16 | -1 | Y | 111 | 72 | 8.9 | 2.4 | 14.6 | 3740 | 3738 |
| 2 | prefill(skip) | 10.8 | 27 | -1 | Y | 91 | 60 | 5.9 | 2.1 | 10.7 | 3947 | 3944 |
| 3 | prefill(skip) | 12.9 | 40 | -1 | Y | 100 | 66 | 6.5 | 2.3 | 11.8 | 4154 | 4154 |
| 4 | new 1 | 13.5 | 53 | 11 | Y | 94 | 58 | 6.8 | 3.4 | 13.9 | 4557 | 4557 |
| 5 | new 2 | 15.8 | 69 | 262 | Y | 103 | 64 | 8.0 | 3.7 | 15.8 | 4773 | 4442 |
| 6 | new 3 | 15.8 | 85 | 995 | Y | 103 | 64 | 8.1 | 3.4 | 15.6 | 5075 | 5075 |
| 7 | new 4 | 17.1 | 102 | 373 | Y | 103 | 64 | 8.3 | 3.8 | 16.2 | 5349 | 5349 |
| 8 | new 5 | 17.0 | 119 | 257 | Y | 103 | 64 | 8.9 | 3.9 | 16.9 | 5375 | 5273 |
| 9 | new 6 | 17.2 | 136 | 1295 | Y | 103 | 64 | 8.8 | 4.9 | 17.9 | 5304 | 4886 |
| 10 | new 7 | 19.5 | 156 | 286 | Y | 103 | 64 | 9.5 | 4.7 | 18.5 | 5284 | 5204 |
| 11 | new 8 | 18.3 | 174 | 1049 | Y | 103 | 64 | 9.8 | 4.9 | 19.1 | 5307 | 4893 |
| 12 | new 9 | 20.5 | 195 | 8737 | Y | 103 | 64 | 9.8 | 5.7 | 20.4 | 5237 | 5184 |
| 13 | new 10 | 21.9 | 217 | 290 | Y | 103 | 64 | 10.6 | 6.8 | 22.2 | 5174 | 3259 |
| 14 | new 11 | 27.8 | 244 | 1049 | Y | 103 | 64 | 16.8 | 5.8 | 27.6 | 4551 | 3230 |
| 15 | new 12 | 29.4 | 274 | 3514 | Y | 104 | 64 | 15.1 | 7.7 | 27.8 | 4127 | 3550 |
| 16 | new 13 | 27.4 | 301 | 13 | Y | 103 | 64 | 14.2 | 9.5 | 28.9 | 4147 | 2940 |
| 17 | new 14 | 36.4 | 338 | 383 | Y | 103 | 64 | 17.1 | 11.0 | 34.4 | 4072 | 3326 |
| 18 | new 15 | 35.8 | 373 | 995 | Y | 103 | 64 | 16.8 | 14.0 | 37.2 | 3038 | 2038 |
| 19 | new 16 | 32.1 | 405 | 373 | Y | 103 | 64 | 17.4 | 8.9 | 31.7 | 4253 | 2839 |
| 20 | new 17 | 34.4 | 440 | 257 | Y | 103 | 64 | 18.3 | 10.0 | 34.1 | 4004 | 3991 |
| 21 | new 18 | 35.8 | 476 | 1295 | Y | 103 | 64 | 22.9 | 7.2 | 35.8 | 3951 | 2819 |
| 22 | new 19 | 33.5 | 509 | 286 | Y | 103 | 64 | 16.1 | 11.2 | 33.0 | 3924 | 3592 |
| 23 | new 20 | 34.0 | 543 | 1049 | Y | 103 | 64 | 15.8 | 12.6 | 33.8 | 4706 | 3774 |
| 24 | new 21 | 35.2 | 578 | 3514 | Y | 103 | 64 | 16.0 | 12.8 | 34.8 | 4367 | 2871 |
| 25 | new 22 | 33.0 | 611 | 11 | Y | 103 | 64 | 18.9 | 8.7 | 32.9 | 4944 | 4316 |
| 26 | new 23 | 39.8 | 651 | 290 | Y | 103 | 64 | 23.5 | 8.2 | 37.7 | 4974 | 4835 |
| 27 | new 24 | 37.0 | 688 | 262 | Y | 103 | 64 | 19.9 | 11.1 | 36.6 | 5142 | 3869 |
| 28 | new 25 | 39.1 | 727 | 995 | Y | 103 | 64 | 19.0 | 13.8 | 38.8 | 5049 | 2648 |
| 29 | new 26 | 42.7 | 770 | 373 | Y | 103 | 64 | 25.5 | 12.0 | 44.0 | 3876 | 3630 |
| 30 | new 27 | 42.2 | 812 | 257 | Y | 103 | 64 | 26.9 | 8.6 | 41.8 | 4260 | 3703 |
| 31 | new 28 | 38.1 | 850 | 1295 | Y | 103 | 64 | 22.1 | 10.0 | 37.7 | 4752 | 4487 |
| 32 | new 29 | 43.5 | 894 | 286 | Y | 103 | 64 | 27.6 | 7.8 | 41.3 | 4556 | 3379 |
| 33 | new 30 | 44.0 | 938 | 1049 | Y | 103 | 64 | 20.8 | 17.9 | 45.4 | 4631 | 1983 |
| 34 | new 31 | 47.6 | 985 | 3514 | Y | 103 | 64 | 31.7 | 9.5 | 48.0 | 4502 | 4502 |
| 35 | new 32 | 49.7 | 1035 | 13 | Y | 101 | 62 | 28.2 | 12.1 | 46.9 | 5372 | 5310 |


## 4. Costs

- Bytes at cap 32 (flags on vs demo-c32): runtime.css +264,195 B (201,028 B of it the 7th glyph in the fine strings; ≈63 KB of R7B rules), index.html +204,365 B
  (201,028 B rows); noise font +8,333,952 B (TTF; ≈6.5 MB as WOFF2 if wanted). Cap 36 vs 32 (all on): css +2,977,866 B, html +111,204 B (+788 elements/slot).
- Time: head skip −2.6 s per prefill epoch (R7P model; measured in §3 when the typed run is allowed); sampling glyph +0.2–0.3 s/token projected by R7S (measured in §3);
  capacity-36 overhead on the first 32 tokens ≈ +0.1 s/token (R7P).

## 5. Risks / open items

- All typed-prompt runs were headless (the headed-only v6 scrollbar bias is fixed in these tools); a headed re-check is one `B0_HEADED=1` away. The two sampled 12-layer runs ran on battery — their timings (1,533 / 1,543 s) are not comparable; the T = 0 run (1,034.9 s) was on AC.
- Cross-`<svg>` SMIL begin (`r7b-prefill-ready-e` in the core's svg, `<set>` in the token-state svg) verified by the three typed runs (slots 1–3 = −1, epochs advance).
- The idle clock restyles body + 1 readout per frame while the pointer is over the controls or the editor is focused (never during a run); `:hover`-driven, so
  keyboard-only users get seed 1 unless they focus a control first (the `focus-within` rules) or pick a seed.
- Browser Reload restores the checked Run box and restarts the clock from 0 → seed 1 (R7S caveat): use Reset or re-select the shown seed to replay.
- Lattice rounding at T ≠ 1: the reference models `rint(raw + n·T_r)`; a near-half case could flip like today's 1-q greedy margins (min margin in both sampled
  references is 6 q).
