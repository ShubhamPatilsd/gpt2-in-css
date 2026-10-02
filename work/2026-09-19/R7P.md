# R7P — parallel prefill and the "32 new tokens" budget (2026-10-01)

Agent R7P. Research only: emitter sources `R6X/tools` (`browser_gpt2_runtime.py`, `browser_gpt2_reused_core.py`, `browser_gpt2_reused_adapter.py`,
`browser_gpt2_font_vector_cache.py`, `r3r_fold_hop.py`, `r2f_lean_handshake.py`, `r2d_knobs.py`, `r5h_ch_scores.py`, `r6p_prompt.py`, `browser_gpt2_embedding.py`,
`browser_gpt2_head_receipts.py`), the built `bundles/demo-c32` (census by grep), and the measured numbers in R4C/R4D/R5A/R5X/R6P/RESULTS-round5/6. **No Chrome run,
no build** (R6X's verification chain has priority); every time figure below is a model on measured constants, labelled as such. Log `R7P.log.md`.

## 0. Headline

- **Q1 — parallel prefill.** The N prompt positions cannot be folded into "one forward pass" cheaply: the frames a step costs are per *geometry→number hop per
  position*, not per step, so re-ordering work (option b) saves no frames, and true parallelism (option a, N copies of the layer core) only amortises the ≈4.4 s
  of genuinely per-epoch cost (head 2.6 s + per-pass fixed 0.9 s + idle frame servicing 0.85 s) while multiplying every per-element cost by N.
  Model (c32, k ≤ 4): sequential today **64.4 s** (measured 18.5/14.1/15.1/16.7); **(c) skip the head on prefill epochs ≈ 56.6 s** (−7.8 s, exact, ≈40 lines of
  emitter); **(a) N = 4 copies ≈ 49 s** (−15 s; +31k elements, +25k view-timelines, +0.2–0.3 GB, a multi-day rewrite, and a real risk of +2.3 s on *every* token
  if the locked copies' timelines are still serviced); **(b) ≈ 62–66 s** (no gain: needs the per-position residual store R3R removed, +9 s of latch transitions);
  (d) nothing exists that does not precompute the prompt. **Recommendation: do (c) now; do not do (a)/(b).**
- **Q2 — budget.** Capacity is a build-time constant, but everything that depends on it is parameterised: the only hard cap is the argparse guard
  `browser_gpt2_runtime.py:770` (`2 <= capacity <= 32`). A capacity-36 build is that one-line guard change plus the unchanged recipe (`compile.sh <out> 36 12`;
  tokenizer fonts/`--positions` are prompt slots, not capacity). Per slot: +788 elements, +74 `@property`, +768 V leaves, +12 score elements, +12 bank write rules,
  +12 pass rules, +1 token slot/feedback timeline, +462 KB CSS (c36 ≈ 89.7k elements, 52.2 MB CSS, depth 186/512). Time: the per-position slope makes the extra
  epochs the most expensive ones — fit 12.05 + 0.975·k gives epochs 33/34/35/36 = 44.2/45.2/46.2/47.2 s; capacity overhead on the first 32 ≈ +0.1 s/token.
  Memory +0.4–0.6 GB at the end of the run. **Recommend one capacity-36 build with a prompt-count-dependent stop at epoch 31 + max(N,1)** (so a dropdown run is
  still 32 epochs ≈ 906 s, a 4-token typed run is 35 epochs ≈ 1,040 s ≈ 17.3 min for 32 new tokens, −8 s with (c)) — not "N fixed at 4", which would waste
  3 × 45 s on every dropdown run. "32 + N" at run time is exactly what the stop rule gives from the single 36 build; it cannot be done by changing capacity at run time.

## 1. Mechanism — why a prompt token is a full step today

One rendering graph (`browser_gpt2_reused_core.py:compile_reused`) holds ONE set of layer carriers (7,680 view-timeline carriers + 768 V rows at depth 7–163).
The controller (`r3r_fold_hop.py:loop_parts`) derives everything from one monotone clock: `--pass = min(decode(proj marker) + 1, --pass-cap)`,
`--layer = mod(pass − 1, 12)`, `--position = floor((pass − 1)/12) + 1` (`reused_core.py:281–286`, stamped onto readers by `reused_adapter.py:160–166`). The
residual stream of the position in flight lives only in the 768 proj carriers' widths (R3R: carriers hold out_P until the next pass's layout). Per layer the data
makes 5 hops / ≈2.5 frames (LN1→qkv fonts → qkv readback + KV write + scores → ctx → attn → LN2/fc → proj); per epoch the head (50,257 rows, ≈2.6 s) and the
SMIL handshake (`#token-e-ready` → captured → ack → advanced → `--epoch:e+1`, `--pass-cap:(e+1)·12`) add ≈3–4 frames. The KV cache is 12 nested banks
(`font_vector_cache.py:661–667`); bank L writes slot `--fvs-write-slot = position − 1` during layer L's qkv pass (`:337–338`) and the 86,400 s transition list
latches it when the rule stops matching; masks `--fv-S = sign(position − S − 1)` (`:484–491`) give causal attention. R6P's prefill (`r6p_prompt.py:138–151`)
feeds `--prompt-token-id-(e−1)` into `--token` at epochs e ≤ N; nothing else changes, so each prompt token costs one full step including the head, whose winner
is discarded (`display_token_rule`, `prefill_handshake_css`). Epochs 1..N−1 are discarded, epoch N's winner is new token 1 → 32 epochs give 33 − N new tokens.

## 2. Q1 — options (c32, 4-token prompt; constants from R5A §1/§1b, R5X §4, R4T; model in Appendix A)

| option | wall for N = 4 (today 64.4 s) | exactness | elements / timelines / memory | emitter work | verdict |
|---|---:|---|---|---|---|
| (c) head off on prefill epochs 1..N−1 | **≈ 56.6 s** (−3 × 2.6); optional bridge-export gate −1…−1.5 s more | exact (the skipped head outputs were discarded; `--saved-token-e` becomes −1 instead of the discarded id) | 0 / 0 / 0 (+3 `<g>` elements) | ≈40 lines in `r6p_prompt.py` + 2 string edits in `browser_gpt2_runtime.py` (Appendix B) | **do it** |
| (a) N parallel core copies, shared KV reader/banks above sibling copies | ≈ 49 s (N=4), 38 s (N=3), 27 s (N=2) — if locked copies' timelines are free; else **+2.3 s on every one of the 32 tokens (+74 s/run)** | exact in principle (same fonts, same lists) | +≈31k elements (copy p: 8.7k + 780·p), +25.3k view-timelines/animations/keyframes, +≈1.5k registered props per copy, +6–8 MB CSS, +0.2–0.3 GB static, ×N transient garbage during prefill | rewrite of `compile_reused` (N copies, per-copy stage/receipt classes), `font_vector_cache.attention` (shared `.fvs-query` fed by N chunked qkv readers, N slots written per pass, per-copy masks), adapter pass readers; a fixture first | not worth it: −7.7 s beyond (c) for the largest structural change since R3R |
| (b) per layer, positions 1..N as sub-steps | ≈ 62–66 s (frames unchanged; +9.2 s of residual-store latch transitions; −7.8 s if combined with (c)) | exact | +N × 768 latched numbers (the loop-bank structure R3R deleted) | new controller arithmetic (`--layer/--position/--fvs-write-slot/--pass-cap`), a residual store, per-sub-step embedding receipts | **no**: the reused graph does not permit sub-steps without the 12-layer loop (Appendix D) |
| (d) cheaper prompt K/V | — | — | — | — | nothing: K/V of position p at layer L needs the full layers 0..L−1 of p; without build-time knowledge of the prompt there is nothing to precompute. Only the tail of layer 11 (attention → fc → proj) and the final LN are not needed for p < N (≈ −1 s/epoch) — but the proj marker is the clock, so skipping layer-11's proj needs a second clock source; listed as a follow-up, not recommended now |

Where (c)'s 2.6 s comes from (R5A §1, cap 8; the head is capacity-independent): head style pass 50,898 elements 0.37–0.42 s + head layout ≈1.3 s (50k-row
shaping) + its PrePaint/frame ≈0.9 s. R3H measured the exact head at ≈2.9 s on an earlier bundle. The SMIL handshake frames (≈0.35 s) stay — they are what advances
`--epoch` and they are needed to keep the epoch state sticky.

## 3. Q2 — capacity

**What scales with capacity C** (emitter sites; measured per-slot deltas from `R4C/populations.txt`, c8→c32): `feedback()` (`runtime.py:69–165`): C nested
`.token-slot-i`, C feedback metrics + view-timelines + keyframes + animations, 3C registrations, 4C SMIL `<g>`, C−1 `--epoch` rules, the C-branch `--token`
chain, C display rules; `.position-embedding` (`:426–440`): 768 declarations × C-branch `if()` (891 KB at 32 → ≈1.0 MB); KV cache (`font_vector_cache.py`):
74·C `@property` (37 latched fields × fc/fr), 12·C bank write rules each with an O(C) retained list, C lean-latch rules, 12·C filled-alias rules, 768·C V leaves
+ 12·C `.fvs-v` rules + C hide rules, 12·C score elements (R5H chain depth C+1 per head), 12·C `--fs/--fe/--fw`, C `--fv/--fvq`; core: C `--valid-S`, C−1
`--pass-cap` rules, 12·C `@container loopcontrol style(--pass:P)` reader stamps; R2G rewrites the token `:has()` chains (98 → 110). Net per slot: **+788
elements, +462 KB CSS, +28 KB HTML, +105 `@property`, +13 keyframes, +25 timeline names**. demo-c32 → c36: 86,510 → ≈89,660 elements, 50.37 → ≈52.2 MB CSS,
max depth 182 → 186 (R5H chains +4; token-slot nesting +4; cap 512). No layout cap is approached: pass markers at pass 432 are 573,440 px in a 1,572,864 px
track (progress −0.567, decode margin 1,000×); the head epoch transport is already the >8 "separate geometry" form; wpe has 1,024 rows.

**Time.** R5X's c32 fit (prompt 40, swap-loaded state) 12.05 + 0.975·k reproduces the 905.9 s total; epochs 33/34/35/36 = 44.2/45.2/46.2/47.2 s. Capacity
overhead on the first 32 tokens: the unfilled `display:none` leaves are still style-resolved when their row is dirtied (R5E: 0.65 s/token at p = 1 of a cap-32
run, decaying) → +12.5 % ≈ +0.08 s/token ≈ +3 s/run; bank list text +12.5 % of the 163-element pass's lists, negligible. **A 4-token run with 32 new tokens
(35 epochs) ≈ 906 + 135.6 + 3 ≈ 1,045 s ≈ 17.4 min; with (c) ≈ 1,037 s.** A dropdown run stays 32 epochs ≈ 909 s if the run stops at 31 + max(N,1).
Risk in the extrapolation: R4C saw a +9 s step at positions 19–22 (cache-threshold hypothesis); R5X's curve is linear to 32 with rmse 0.87; a further
threshold between 32 and 36 cannot be excluded without a run.

**Memory.** +130–210 MB Oilpan per additional filled position (R5A §2) → +0.4–0.6 GB at the end of a 35-epoch run; demo-c32 peaked 4.5 GB (typed "I") and
7.3 GB RSS ("Once upon a time", RESULTS-round6) → up to ≈7.9 GB. Still a 16 GB machine, with more swap pressure in the last three tokens.

**Epochs 36 with the typed-prompt wiring:** yes — `r6p.token_select_css(capacity)`, `display_token_rule`, `regs` (`SLOTS < capacity`), the EOS/ack prefill
rules and R6V's counter all take `capacity`; the tokenizer fonts encode 4 prompt positions and are unrelated to capacity. Nothing in the 2.4k-line emitter chain
hard-codes 32 except the guard (`grep '\b32\b'` over the chain: only `runtime.py:770–771`, the dropdown option id 32 = "A", and comments).

**Flag change or emitter work?** Flag change plus the guard: `browser_gpt2_runtime.py:770` `2 <= capacity <= 32` → `<= 64`; then
`R6P_PROMPT_SLOTS=4 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6X/compile.sh bundles/demo-c36 36 12`. The *stop rule* (31 + N epochs) is new emitter work
(≈15 lines, `r6p_prompt.py`). Recommendation: **capacity 36 always + stop rule** (36 rather than the exact minimum 35 for one slot of margin / N = 5 later;
the 36th slot costs ≈0.1 s/token and 0.5 MB).

## 4. Recommended plan (file:function, risk)

1. **(c) head skip on prefill epochs** — `r6p_prompt.py`: new `prefill_head_skip_css(capacity)` emitting, for e in 1..SLOTS−1 and c in e+1..SLOTS,
   (i) `@container tkprompt style(--prompt-count:c){@container runtime style(--epoch:e){.full-head{content-visibility:hidden}}}` (appended after
   `r2d.head_lock_css`'s unlock rule at `runtime.py:417` and the detached-output unlock at `:463`; same specificity, later wins — no `!important`), and
   (ii) `… {@container corestate style(--held:1){body:has(#run:checked) #prefill-ready-e{animation:native-handshake 1ms both}}}`;
   `browser_gpt2_runtime.py:feedback` line 139: the `#token-e-captured` `<set>` gets `begin="token-e-ready.animationend+0.001s;prefill-ready-e.animationend+0.001s"`
   for e < SLOTS; the `<g id="prefill-ready-e">` elements go into the `<svg class="loop-signals">` inside `.loop-input` (string insert after
   `compile_reused_runtime_core` returns, as `r3r.move_export` does) — that svg is inside the `corestate` container and outside the display-locked
   `.loop-compute`, so `--held:1` is queryable there (R6V's `.pg` uses the same container). `--saved-token-e` latches −1 (head-output-epoch never equals e while
   the head is locked), `--pf-(e+1)` ignores it, `display_token_rule` already hides it, EOS cannot fire (winner 0 while locked; R6P's ack rules remain).
   Cosmetic: R6V's head-phase label at `--held:1` should read "prefill: K/V stored" on those epochs (`runtime.py:r6x_head_phase_css`). Harness:
   `R6P/summarize32.py` must compare only e ≥ N (today the reference lists the discarded predictions). **Risk: low–moderate** — the only new ordering is
   ready-at-held instead of ready-after-head; the KV latch of bank 11 is already complete when `--held` rises (it is written in layer 11's qkv pass), and the
   epoch advance path is unchanged. Verify: 2-layer smoke typed "Once upon a time" (ids e ≥ 4 vs the 2-layer reference), one c32 32/32 run.
2. **Capacity 36 + stop rule** — `browser_gpt2_runtime.py:770` guard; `r6p_prompt.py`: `stop_css(capacity, new_tokens=32)`: for c in 0..SLOTS, with
   t = 31 + max(c,1): `@container tkprompt style(--prompt-count:c){body:has(#token-t-captured.done) #token-t-ack{animation:none!important}
   body:has(#token-t-captured.done) .status::after{content:"Complete • 32 new tokens"} body:has(#token-t-captured.done) .pg{display:none}}`
   (the `#token-*-ack` elements sit under `.tk-high-3` = `tkprompt`, as R6P's EOS rules already rely on); R6V `progress_css` label "token t of 36" → optional
   "new token t−N+1 of 32" per (c, e). References: `R6P/reference_prompt.py` to 31+N steps; `summarize32.py` to 36 slots. **Risk: low** (all paths are
   parameterised; R2G verifies the new `:has()` chains against the page at build and fails loudly). Build ≈ 20 s; the usual offline gates (flags-off twin
   byte-identical to demo-c32 at capacity 32, NumPy 35-step reference, static check) then the 32/32-type run at 35 epochs.
3. Do not pursue (a)/(b). If prefill latency matters more later, the next exact lever is skipping layer 11's tail + final LN for p < N (−1 s/epoch), which needs a
   second clock source for `--pass` and is the first change that touches R3R's controller invariant.

## 5. Not verifiable without a build / Chrome

- (c): that `content-visibility:hidden` on `.full-head` during a `--bridge-ready:1` window has no side effect on `.head-input-bank`'s `--head-fvs` latch (argued:
  the bank is outside the locked subtree and only the unlocked head reads it); the SMIL two-condition `begin` list on `<set>`; the −1 `--saved-token-e` values in
  the harness comparison. All three are covered by the 2-layer smoke.
- (a): whether view-timelines whose subject is inside a `content-visibility:hidden` subtree are serviced per frame (R4T's 3.06 µs/timeline/frame) — the decisive
  fixture (≈25k timelines in a locked subtree, idle frame cost) was not run; without it the (a) estimate is a lower bound.
- Capacity 36: the per-token curve beyond position 32 (threshold steps), the RSS peak at 35 filled positions on the 16 GB machine, and that the R2G/F5/R5E build
  assertions pass at 36 (all are capacity-parameterised; none inspected hard-codes 32).

---

## Appendix A — cost model for (a)

Per epoch at c32, k = 2..4: 15.5 s = style 7.0 + layout 4.0 + other 4.5 (R5X table). Genuinely per-epoch (does not scale with copies): per-pass fixed 72 ×
12.7 ms = 0.9 s (R3A), head 2.6 s (R5A), idle frame servicing 30 frames × ≈28 ms = 0.85 s (R4T floor) → 4.35 s. Everything else is per restyled element /
per changed carrier / per shaped glyph / per dirty layout object (M1 4.45 µs/element, R4T 14–17 µs per changed carrier, R5A 45 µs per fc carrier restyle,
R3A 9.3 µs per dirty object in PrePaint, GC ∝ garbage) → 11.15 s × N. T(N) = 4.35 + 11.15·N: N = 2 → 26.6, 3 → 37.8, 4 → 48.9 s, vs sequential 15.5·N and
sequential-with-(c) 15.5·N − 2.6·(N−1). Token 1's +2.3 s first-instantiation surcharge (R5X k = 1) would be paid by each copy's carriers as well (not in the
model). Idle servicing of the extra 25,344 timelines if they stay live while locked: 3.06 µs × 25,344 = 77.6 ms/frame → ≈2.3 s/token → ≈74 s over 32 tokens.

Structure that makes (a) possible at all: the N copies must be *siblings* (nesting N cores of ≈150 levels each exceeds Chromium's 512-level cap at N ≥ 3; the
page is already 182 deep), so K/V lists computed from one copy's qkv values cannot reach another copy by inheritance. The fix is to move the qkv readback
(`.fvs-query`, `font_vector_cache.py:210–302`) and the 12 banks above all copies: each copy's 1,536 K/V carriers are read by chunked consumers on that shared
element (R4T chunks of 64 → 24·N wrappers), the banks write N slots per layer pass (lean-latch lists 0..W+N−1), the per-copy score chains read `--fr-k-S` for
S ≤ p − 1 through per-copy `--fv-S`/`--fvq-S` masks (causal), and Q lists are per copy (`--fvs-query-H-p`). The write and the reads are style dependencies of
the same pass today (R5A's 163-element "qkv readback → KV write → scores" pass), so simultaneous processing of N positions keeps 5 passes/2.5 frames per layer.
Element budget per extra copy p (serving prompt position p only): carriers 7,680 + V rows 768 + chunk consumers 144 + stage wrappers/receipts/gates ≈60 +
V leaves 768·p + score elements 12·p + 12 softmax bottoms ≈ 8.7k + 780·p; N = 4 → 30.7k; timelines +8,448 per copy.

## Appendix B — (c) rule set and ordering argument

Today at epoch e the sequence is: pass 12e's proj marker lands → `--held:1` → `.reused-final-export` shown → b11-bridge carriers → `--bridge-ready:1` → head
unlocked, restyled (50,898 el.), laid out, painted → `.head-result` publishes `--winner` / `--head-output-epoch:e` through the detached anchor →
`#token-e-ready` → captured → `.token-slot-e` latch + `#token-e-ack` → advanced → `--epoch:e+1`, `--pass-cap:(e+1)·12`. With (c) on prefill epochs the head
stays locked (so `--head-output-epoch` stays 0, `--winner` 0) and `#prefill-ready-e` fires at `--held:1`; the rest is unchanged. Bank 11's slot e−1 was written
in pass 12e's qkv pass and is latched when `--layer` leaves 11, i.e. at the pass advance — identical to today. Values: `--saved-token-e = if(style(--head-output-
epoch:e):var(--winner);else:-1)` → −1; `--feedback-e` → −1; consumers: `--pf-(e+1)` (ignores it when count > e), `--display-token-e` (already −1 when count >
e), `#capture-epoch-observer` height max(0,−1) = 0. Optional second gate: `.reused-final-export{display:none}` on prefill epochs removes the 768-carrier bridge
pass and its frame (≈0.3–0.5 s/epoch); `--bridge-ready` then never rises on those epochs, which nothing needs once the head is skipped — slightly more risk
(the `.head-input-bank` latch keeps the previous list, harmless), so second priority.

## Appendix C — capacity scaling evidence

`R4C/populations.txt` (cap 8 → 32, per slot): elements +788.1, runtime.css +462 KB, index.html +28.5 KB, `@property` +105, `@keyframes` +13, timeline names
+25, `--fc-` tokens +19,994 (the O(C²) literal lists: F5 literal `transition-property` lists, 310k names at c32), `fvs-v-N-N` +768, `fvs-score-N-N` +12,
`token-slot-N`/`feedback-metric-N` +1. demo-c32 census (grep over `bundles/demo-c32/index.html`): 86,510 elements; `fvs-v-` 24,576; `fvs-score-` 396
(384 + 12 bottoms); `.metric` 8,454; `head-row` 50,257; `token-slot-` 32; depth 182. runtime.css 50,366,721 B: `@property` 42,330, `@container fvscache
style(--fvs-write-slot:` 800, `@container loopcontrol style(--pass:` 384, `--pass-cap:` 32, `.position-embedding` rule 891,088 B.
Sites: `runtime.py:69–165` (`feedback`), `:426–440` (wpe), `:491–492` (epoch stamps), `:544–550` (display/status), `font_vector_cache.py:89–107` (storage
names), `:210–238` (write slot, lean latch), `:337–356` (write/alias rules), `:377–383` (score regs), `:457–533` (softmax/weights), `:534–578` (V rules),
`:582–614` (rows/leaves/chains), `:675–685` (fill flags/hide), `reused_core.py:132–140` (`--valid`), `r3r_fold_hop.py:164–165` (`--pass-cap`),
`reused_adapter.py:160–166` (pass stamps), `r5h_ch_scores.py:132–140` (chain depth), `r6v_progress_ui.py:86–116`, `r6p_prompt.py:114–151, 262–283`.

## Appendix D — why (b) cannot amortise frames

A frame is needed each time a laid-out width must become a number (view-timeline readback) and the next computation depends on it. Within one position's layer
that happens 5 times (qkv → scores → ctx → fc → proj; 2.5 frames/layer with R5H's `ch` scores). Processing position p+1 at layer L after position p at layer L
needs p+1's own qkv widths laid out and read back before its scores etc. — the same 5 hops — so N sub-steps per layer cost N × 2.5 frames, exactly as N
sequential steps do. The per-epoch frames that would be saved (head frame, 3–4 handshake frames, ≥2 embedding-receipt frames) are ≈0.8 s/epoch, of which the
head's 2.6 s is already taken by (c), and the embedding receipt is needed per position anyway. Meanwhile the reused graph has no place to keep N residual
streams: the 768 proj carrier widths hold one position (R3R), so (b) needs a latched 768-number store per position (768 transition starts × ≈250 µs =
0.19 s per write, N writes per layer → ≈9.2 s per 4-token prefill), a new pass → (layer, sub-position) mapping in `r3r_fold_hop.py:loop_parts` /
`reused_core.py:281–286` / `reused_adapter.py:160–166`, and a per-sub-step `--token`/embedding receipt instead of the body-level `--epoch`. Net ≈ 62–66 s.
