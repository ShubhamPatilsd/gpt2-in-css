# R6P — (A) the prompt dropdown shows "!" / no echo; (B) typed free-text prompt for `combined8-c32` (bundle `combined8-c32-prompt`)

Agent R6P, 2026-09-30. Work dir `work/2026-09-19/R6P/` (tools copy `R6P/tools` = `R5X/tools` + `r6p_prompt.py` + 7 conditional edits in
`browser_gpt2_runtime.py`, `R6P/tools-vs-R5X.diff` 431 lines; new fonts only under `R6P/assets-r6p/`). Log `R6P.log.md`. No repo `tools/` / `experiments/`
edits, no git. Bundles: **`bundles/combined8-c32-prompt`** (cap 32, the deliverable) and **`bundles/combined8-prompt`** (cap 8, for the 8/8 check), each with `BUILD.md`.
Machine state during the whole session: disk 6 → 1–2 GB free, swap used 5.4 → 8.7 GB (other processes; my builds are 55 MB each) → the Chrome gate (AC AND
((disk ≥ 4 GB AND swap < 4,000 MB) OR (disk ≥ 3 GB AND swap < 3,000 MB))) was **closed the entire time**; the four Chrome runs are armed behind it (`R6P/run_chain.sh`, §5) and
nothing below has been observed in Chrome yet — every result in §4 is offline (byte compares, hb-shape, NumPy).

## 0. Headline

- **A (diagnosed + fixed offline):** before Run the output area renders `counter(prompt, gpt2-vocabulary)` from `.visible-output::before{counter-reset:prompt var(--frozen-prompt)}`.
  `--frozen-prompt` has been registered `inherits:false` since F5 (`f5.make_private_prefix(css, ["--feedback-", "--frozen-prompt", "--token"])`), and a pseudo-element
  only inherits *inherited* properties from its originating element → inside `::before` the property is its registration's **initial value 0 → GPT-2 token 0 = "!"**, for every
  prompt, before and after Run (so choosing "A" changes `--prompt-token` on body — the harness verified that in R4M/R5X — but the echo cannot show it). The generated tokens
  display correctly because `--display-token-i` are *unregistered* (and therefore inherited by `::after`). Fix = 2 rules: `.visible-output{--display-prompt:var(--frozen-prompt)}`
  and `::before{counter-reset:prompt var(--display-prompt)}` (`R6P_ECHO_FIX`); an echo-only twin differs from `combined8-c32` by exactly those two rules (index.html identical).
  Zero per-token cost: `.visible-output` is a leaf already restyled once per token (it forwards the 32 `--feedback-i` by explicit `inherit`); one more var() on it.
- **B (built, offline-verified, Chrome pending):** the TinyStories editable-`<style>` + OpenType-BPE-tokenizer mechanism ported into the emitter behind `R6P_TYPED_PROMPT`
  (N = 4 slots; the two existing GPT-2 token-id fonts reused byte-identically — same vocabulary as `data/gpt2`, checked). Typed text → ≤4 ids live (pre-Run, restyling ≈25
  chain elements per keystroke, never the model) → at Run the ids are armed into `--prompt-token-id-k` / `--prompt-count` (inherited by the model) → `.feedback-select{--token}`
  reads `--prompt-token-id-(e−1)` at epochs e ≤ N and `--feedback-(e−1)` after → **the same full-vocabulary HVAR embedding lookup as fed-back ids → exact class, no approximation**
  (the TinyStories 8-bit feedback-table loss does not exist in this runtime). Flags-off twins are byte-identical to `combined8-c32` and `combined8`. NumPy references:
  typed "I" == `R4P/reference_ids_32_40.json`; "Once upon a time" → `R6P/reference_ids_once_upon_a_time.json` (4 prefilled + 29 generated, quantized == float).
- **Cost:** each prefilled prompt token is a full 12-layer step (c32 measured k=1..4: 18.5 / 14.1 / 15.1 / 16.7 s → ≈65 s before the first new token for a 4-token prompt);
  the run still takes 32 epochs (≈906 s at c32), producing 33−N new tokens. Dropdown kept as the fallback (empty editor = the old path exactly).

## 1. Part A — diagnosis

| question | answer (from `bundles/combined8-c32/runtime.css` + the emitter) |
|---|---|
| What does the output element render before Run? | `#visible-output` (`<output class="visible-output">`, child of `.feedback-reader`): `::before` = `counter(prompt,gpt2-vocabulary)` with `counter-reset:prompt var(--frozen-prompt)`; `::after` = `counter(token1..32,gpt2-vocabulary)` with `counter-reset: tokenI var(--display-token-I)`, `--display-token-I:-1` until `#token-I-captured.done` → symbol "" (the counter style is `fixed -1; symbols:"" "!" …`). |
| Which variable, and why "!"? | `--frozen-prompt`, `@property{syntax:"<number>";inherits:false;initial-value:0}`. `.feedback-reader{--frozen-prompt:var(--prompt-token)}` and `.visible-output{--frozen-prompt:inherit}` are correct on the elements; the `::before` pseudo-element is not a descendant that gets `inherit` — it takes the initial value 0. Token 0 is `!`. |
| Why is the chosen prompt not echoed? | It is set correctly (`body:has(option[value="32"]:checked){--prompt-token:32}` → `.feedback-reader --frozen-prompt` → the model), only the echo path is broken as above; the user sees the same "!" for every option. |
| Fix | `R6P_ECHO_FIX` (default on): copy into an unregistered property on `.visible-output` itself, which the pseudo inherits. Rule-level diff of the echo-only twin vs `combined8-c32` (`R6P/logs/compare-c32-echo-vs-combined8-c32.log`): `-.visible-output::before{counter-reset:prompt var(--frozen-prompt);…}` `+.visible-output{--display-prompt:var(--frozen-prompt)}` `+.visible-output::before{counter-reset:prompt var(--display-prompt);…}`; nothing else, index.html identical. |
| Cost / placement | Stays inside `.visible-output` because the prompt and the tokens must share one inline formatting context to wrap as a paragraph; the element is a leaf whose only per-token work is the 32 `inherit`s it already does. The alternative (a separate echo element under body) would not flow with the tokens. |

## 2. How the TinyStories mechanism works (what was ported)

`tinystories/dynamic.html` (`tools/build_tinystories_dynamic.py`) has no script. The prompt lives in an editable `<style contenteditable="plaintext-only">` element whose
text is a real stylesheet, `.prompt-source { --draft-prompt: "Once upon a time"; }`; every keystroke re-parses that one-rule sheet and changes the registered `<string>`
property on body. Two generated fonts (`tools/build_metric_tokenizer_font.py --full --token-ids --positions 4`) are GPT-2's tokenizer as OpenType: the cmap maps every
ASCII byte to the glyph of its byte token; the required-ligature feature `rlig` holds GPT-2's full merge table as `sub gLEFT gRIGHT by gMERGED` lookups in rank order
(rank-ordered global sweeps are equivalent to the BPE loop because a merge's rank is always higher than the ranks that created its parts); a position feature `p00k` then
erases every glyph except the k-th token (contextual `ignore sub @SEEN^k @TOKENS'` / `sub … by zero`). The only information the font leaks to CSS is the advance width:
glyph advance = (digit of the token id in base 32767) + 1, low digit in font 0, high digit in font 1 (+1 so that digit 0 differs from an erased token; two digits because
HarfBuzz treats advances > 32767 as negative). At `font-size:1px` with 64 units/em an advance of d+1 units is exactly (d+1)/64 px = one LayoutUnit multiple, so the metric
`<i>` element's `max-content` width is exact. `anchor-size()` copies that width onto an absolutely positioned inline-size query container, whose child reads
`round(100cqi/1px*64 − 1)` = d into a registered `<integer>`; the slot combines `low + 32767·high`. Four such slots are nested (each slot's metrics live inside the previous
slot's container so the anchors are acceptable), and the model sits under the innermost so it inherits the ids and the count. TinyStories prefills by feeding those ids into
its 35 predeclared stages' input properties, but its prompt embeddings go through the output head's 8-bit packed feedback table — an approximation the README acknowledges
("first nine ids matched, then diverged"). The GPT-2 runtime has no such table: `--token` (a number) drives the GRUP/LOCL axes of the full-vocabulary HVAR embedding font
for prompt and fed-back ids alike, so here the prefill is exact-class.

Offline check of the fonts against `Gpt2Tokenizer` (`R6P/hb_check.py`, hb-shape 14.2.1, both fonts, positions 0..3): 22/26 prompts identical, including "Once upon a
time" → [7454, 2402, 257, 640], "I" → [40], "it's", "don't", "abc123", "Hello, world!", "2023", "A.J.", "Why is the sky blue?"; the 4 mismatches are the mechanism's known
limits — newline, runs of ≥2 spaces (GPT-2's `\s+(?!\S)` pre-tokeniser rule), and non-ASCII (`café`, `naïve`: the cmap holds single-byte characters only). The vocabulary
the fonts were built from (`data/tiny-gpt2/vocab.json`) is dict-equal to `data/gpt2/vocab.json` (merges identical) — they ARE GPT-2 BPE.

## 3. Part B — design in the `combined8-c32` emitter (`R6P/tools/r6p_prompt.py`)

DOM (flag on): `body ▸ .controls (+ .tk-panel: label + <style id="tk-editor" contenteditable>) ▸ font barrier ▸ .tk-root ▸ [slot 0: <i .tk-metric .tk-pos-0 .tk-part-0>,
.tk-probe-0-0 ▸ .tk-low-0 ▸ [<i .tk-metric .tk-pos-0 .tk-part-1>, .tk-probe-0-1 ▸ .tk-high-0 ▸ [slot 1 … ▸ .tk-high-3 ▸ [<i .tk-tokens>, .feedback-reader (the model),
.detached-head-reader]]]]`. +33 elements, max depth 165 → 182 (cap 512), +1.0 MB CSS (R2G's fixed-depth `:has()` chains gain the 17 chain levels in 3,437 rule occurrences).

Properties. Private (`inherits:false`, hopped by explicit `inherit` along the chain only): `--draft-prompt <string>` (set by the editable rule on `.tk-root`),
`--prompt-armed <integer>` (`body:has(#run:checked){--prompt-armed:1}`, hopped `.tk-root → .tk`), `--pt-low-k`, `--pt-high-k`, `--pt-present-k` (written by
`@container tk-k-{0,1} (width > 0px)` on the bridges), `--pt-id-k = if(present) low + 32767·high else −1`, `--tk-count`, `--pf-1..4 <number>` (on `.feedback-select`).
Inherited by the model (`inherits:true`, constant until Run, frozen after): `--prompt-token-id-k = if(style(--prompt-armed:1)) --pt-id-k else −1`,
`--prompt-has-k = if(armed) --pt-present-k else 0`, `--prompt-count = Σ --prompt-has-k` (on `.tk-high-3`, `container-name:tkprompt`). All registrations are emitted with
the feedback CSS so the head-isolation wall resets them before the 50k head rows (checked: `.head-isolation` carries `--prompt-token-id-*:initial` etc.).

Prefill (replaces `.feedback-select{--token}`): `--pf-1 = if(style(--prompt-count:0)) var(--frozen-prompt) else var(--prompt-token-id-0)`;
`--pf-e = if(count ∈ 0..e−1) var(--feedback-(e−1)) else var(--prompt-token-id-(e−1))` for e = 2..4; `--token = if(epoch 1..4: --pf-e; epoch 5..32: --feedback-(e−1); else --frozen-prompt)`.
Numerics: `--token` is a `<number>` holding an integer either way (`round(nearest, …)` of a view-timeline readback for fed-back ids, `round(nearest, 100cqi…)` sums for
typed ids) → `round(down, --token/256)` / `mod(--token, 256)` → the same GRUP/LOCL axes → identical embedding. **No bit is lost anywhere in the typed path**; the only
approximations in the run are the runtime's own (q9 weights, q16 head, HVAR rounding), which are exactly those of a dropdown run — hence typed "I" must reproduce
`R4P/reference_ids_32_40.json` and the NumPy reference for a multi-token prompt is simply teacher-forcing (positions 1..N) followed by free running.

Epoch bookkeeping: the head still runs at prefill epochs 1..N−1 and produces winners that are captured (`--saved-token-e`, `--feedback-e`) like any other — they are never
consumed (`--pf-(e+1)` ignores them) and are hidden in the display (`--display-token-e = if(count > e) −1 else var(--feedback-e)`). An EOS winner at a prefill epoch would
stop the run today, so for e < N: `@container tkprompt style(--prompt-count:c>e){ @container headstate style(--winner:50256){… #token-e-ack{animation}} @container runtime
style(--epoch:e){… #eos-ready{animation:none!important}} }` (the pattern of the diagnostic teacher-forced mode). Total: 32 epochs, N prompt + (33−N) generated tokens.

Display (`.visible-output`, all rules on the existing leaf; `.feedback-reader` and `.visible-output` hop `--draft-prompt` and `--pt-present-0`): pre-Run `::before` shows
the typed text itself (`--draft-echo = if(count 0) var(--draft-prompt) else ""`), or the dropdown token when the editor is empty (`--display-prompt = if(--pt-present-0:1) −1
else var(--frozen-prompt)`); from Run it shows `counter(tkp0..3, gpt2-vocabulary)` from `--prompt-token-id-k` — the N tokens the model actually consumed (a longer typed
text is truncated to them) — followed by the generated tokens. A live readout `<i class="tk-tokens">` (leaf sibling of the model root, private hops) prints
"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [Once][ upon][ a][ time]" while typing, or "none — the dropdown prompt is used".

Ordering at Run. Arming flips in the same style pass as `#run:checked`; the embedding metrics are laid out in that frame, their view timelines deliver `--embed-*` in the next
frame, and the core unlocks no earlier than `#run-latched.done` = SMIL `run-start.animationend + 1 ms` → ≥ 2 frames later; the epoch-1 embedding is therefore fresh when
layer 0 first reads it (the same margin the dropdown path has had since epoch stamps were introduced). The ids are then frozen by the runtime's 86400 s transition latch
on `.tk-high-k` once `#fonts-loaded.done` AND `#run-latched.done` (so a Run pressed before the tokenizer fonts have loaded still ends with the correct ids), and the editor
becomes `-webkit-user-modify:read-only`. Per keystroke the restyle is: `.tk-root` (stylesheet rule change) → the ≈25 chain elements with explicit `inherit` →
`.feedback-reader`/`.visible-output`/`.feedback-select` (own style only; their inherited data is unchanged so the 86k descendants are skipped) + layout of 8 one-pixel metrics.

Font barrier: the two tokenizer faces are `@font-face`s and join the 283-face barrier (285). The barrier's default witness pick (first cmap codepoint with advance > 1) would
have been U+0009 in the low-digit font (TAB is laid out at tab stops in `white-space:pre`, so fonts-loaded would never fire) and does not exist in the high-digit font; for
these two faces the witness is the printable ASCII glyph with the largest advance (`~` = token 93 → 94 units → 5.875 px at 4 px; `!` → 1 unit → 0.0625 px).

N's ceiling: structurally N < capacity (each prefilled token consumes an epoch; 33−N generated). The shipped fonts encode 4 positions; more needs
`build_metric_tokenizer_font.py --full --token-ids --positions N --output R6P/assets-r6p` (GSUB grows ≈ linearly: 2×50 erase lookups per position over 1,024-glyph
chunks; 1.6 MB per font at 4) and `R6P_PROMPT_SLOTS=N` (checked against the fonts at build). Practical ceiling is the user's patience: ≈15–17 s per prefilled token at
c32 (and the machine gate) — 4 (≈1 min) is the demo default, 8 (≈2 min before the first new token) is the most I would ship.

## 4. Verification done (offline)

| check | result |
|---|---|
| flags-off twins (`R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0`) | cap 32: `index.html` **byte-identical** to `bundles/combined8-c32` (7,125,736 B), `runtime.css` identical after URL-depth normalisation, manifest +8 R6P keys, witnesses 283/283; cap 8: identical likewise to `bundles/combined8` (6,460,006 B) — `R6P/logs/compare-c32-off-vs-combined8-c32.log`, `compare-c8-off-vs-combined8.log` |
| echo-only twin (`R6P_TYPED_PROMPT=0`) vs `combined8-c32` | index.html identical; runtime.css differs by exactly the two `.visible-output` rules of §1 (rule-level diff after URL normalisation) |
| `combined8-c32-prompt` vs `combined8-c32` | elements 86,438 → 86,471; depth 165 → 182; css 49.31 → 50.31 MB; html 7,125,736 → 7,127,853 B; witnesses 283/285 identical (+2 tokenizer faces); `launch_browser_gpt2.py --check` 287 static files, 299,822,634 B, `runtimeJavaScript:false`; 0 `<script>`, 0 `on*=` |
| `combined8-prompt` vs `combined8` | elements 67,524 → 67,557; css 38.27 → 39.21 MB; witnesses 283/285; `--check` 287 files, `runtimeJavaScript:false` |
| generated CSS forms (2-layer smoke + 12-layer bundle, `R6P/inspect_css.py`) | `.tk-*` chain, `@container tk-k-*` digit readers, hops, `--pf-1..4`, `--token` chain over 32 epochs, `.visible-output` rules, 3 hidden-winner `if()` rules, 6 prefill EOS/ack rules, R2G chains rewritten through the 17 new levels, tokenizer faces relative `../../R6P/assets-r6p/…`, wall resets present |
| tokenizer fonts vs Python tokenizer (hb-shape) | 22/26 prompts identical; mismatches only newline / double space / non-ASCII (`R6P/logs/hb_check.log`) |
| NumPy "I" (`reference_prompt.py`, 12 layers) | winners == `R4P/reference_ids_32_40.json` free-running == teacher-forced (validates the script) |
| NumPy "Once upon a time" (`R6P/reference_ids_once_upon_a_time.json`) | prompt [7454, 2402, 257, 640]; winners = `[262, 257, 640 │ 11, 262, 995, 373, 257, 1295, 286, 1049, 8737, 290, 1049, 3514, 13, 383, 995, 373, 257, 1295, 286, 1049, 3514, 11, 290, 262, 995, 373, 257, 1295, 286]` (3 discarded prefill predictions │ 29 generated); one teacher-forced pass over the 32 inputs reproduces them; quantized == float at every step (no fragile margin); text `Once upon a time, the world was a place of great beauty and great danger. The world was a place of great danger, and the world was a place of`. Key `freeRunningReference` = the 32 winners so `summarize32.py` compares all 32 `--saved-token-e`. 2-layer twins (`*_2layers.json`) for the smoke. |
| bug found by inspection, fixed before any run | `.tk-root` lacked `--prompt-armed:inherit` (the body → chain hop) — the ids could never have armed; all three flag-on bundles rebuilt (flag-off twins unaffected) |

## 5. Chrome runs (armed, gate closed all session: AC, disk 1–2 GB, swap used 5.4 → 8.7 GB)

`R6P/run_chain.sh` (nohup, `R6P/logs/run_chain.out`) waits for the gate (poll 60 s) and then, under `CHROME.lock` (`R6P/with_lock.sh`: owner "R6P <label> <pid> <time>",
touch -c 30 s, 5 s poll, rmdir only own, refuses while a foreign headless Chrome runs, power re-checked every 30 s), runs one after another:

1. 2-layer smoke `R6P/scratch/smoke2-on` (cap 32) typed "Once upon a time" → all 32 winners vs `reference_ids_once_upon_a_time_2layers.json` (`R6P/run-smoke2-on/`);
2. `bundles/combined8-prompt` (cap 8), nothing typed, dropdown Hello → `[11, 314, 1101, 7926, 11, 475, 314, 1101]` + `verify_browser_gpt2_runtime.py` rc 0 → `READY`;
3. `bundles/combined8-c32-prompt` typed "I" → 32/32 vs `R4P/reference_ids_32_40.json` (per-token s, RecalcStyle/Layout counts, RSS in `run-combined8-c32-prompt/typed-I.summary.md`);
4. `bundles/combined8-c32-prompt` typed "Once upon a time" → 32/32 vs `R6P/reference_ids_once_upon_a_time.json` → `READY` only if 3 and 4 are both 32/32.

Harness `R6P/bench_native.mjs` = R4M's + `B0_TYPED_PROMPT`: after load + idle, Playwright `locator("#tk-editor").fill('.tk-root { --draft-prompt: "…"; }')` (harness-side
select-all + insertText; the page stays JS-free), 1.5 s, one pre-Run read of `--draft-prompt`, the live `--pt-id-k` (asserted == `B0_TYPED_IDS`), and the model-facing
`--prompt-token-id-k` / `--prompt-count` (asserted still −1 / 0 = unarmed), then `DOM.focus(#run)` + Space as before; final readback adds `--prompt-count`, the armed ids,
`#visible-output` `::before`/`::after` and `.feedback-select --token`. `summarize32.py` reads the 32 `--saved-token-e` and compares them with `freeRunningReference`.
Results will be appended to `R6P.log.md` by the chain; the per-token time / RSS tables requested for §6 come from those summaries. Expected: the smoke exposes any
mechanism error within ≈3 min (typed ids, arming, prefill, display, in-flow width change) before the two 15-minute c32 runs.

## 6. Costs

- Prefill: each prompt token is one full step; from `R5X.md` §4 (c32, prompt 40): k=1 18.5 s, k=2 14.1, k=3 15.1, k=4 16.7 → a 4-token prompt shows nothing new for ≈65 s
  (plus the ≈35 s load). The run still has 32 epochs (≈906 s in the swap-loaded state), so the visible yield is 33−N tokens; time per token is unchanged by construction —
  the chain adds no per-token work (typed values are constant/frozen during the run; `.feedback-select` evaluates 4 extra `if()`s once per epoch; `.visible-output` 3 extra
  `if()`s). To be confirmed by run 3's per-token table vs R5X's 905.6 s / 12.05 + 0.975·k fit.
- Typing: ≈25 element restyles + 8 one-pixel layouts per keystroke; no model restyle (private properties + explicit `inherit`). Run: one whole-model restyle when the armed
  ids flip (same size as a dropdown change), then the usual unlock.
- Size: +1.0 MB CSS (R2G chains), +2 KB HTML, +3.3 MB of tokenizer fonts (uncompressed .ttf; served as static assets), +2 faces in the barrier; memory: +12 registered
  integers in the inherited maps below `.tk-high-3` (reset at the head wall), negligible.

## 7. Risks and what is still unverified

1. **Nothing Chrome-verified yet** (gate closed). The structural change with the largest blast radius is that the model is now in-flow inside four absolutely positioned
   inline-size containers at (0,0): `.tk-bridge{width:calc(100vw − 48px)}` keeps the in-flow containing-block width equal to body's content width, and everything the
   model measures lives in fixed scrollers / anchors / `1ch`, but an in-flow-width dependence somewhere in 50 MB of CSS would show up as changed ids — run 1 (smoke, 2 layers,
   32 winners vs NumPy) and run 3 (typed "I" vs the 32/32 reference) are the tests. TinyStories runs its whole app inside the same container structure (its `main{position:
   fixed;inset:0}` renders full-screen), which is the evidence that `container-type:inline-size` does not impose layout containment on fixed descendants in this Chrome.
2. CSS features assumed to work as in TinyStories/this runtime: `if(style(--x:N))` on registered integers (same-element and inherited), nested `if()` in `content`
   avoided (strings are produced by `if()` in unregistered custom properties, as TinyStories' `--prompt`), `round(100cqi/1px*64 − 1)` into `<integer>`, `anchor-size()`
   from an `opacity:0` inline-block anchor, `-webkit-user-modify:read-only` overriding `contenteditable` after Run (UI guard only; the transition latch is the real freeze).
3. Race at Run (§3): argued from the existing handshake (core unlock ≥ 2 frames after arming); if run 3 shows a wrong first id with correct later ids, the fix is a
   token-aware embedding receipt (make the epoch marker width depend on `--prompt-armed`), not a redesign.
4. Tokenizer limits (documented in the panel label): ASCII, single spaces, no newlines; text beyond the first N tokens is ignored (the display truncates to what the model saw
   once Run is pressed); breaking the CSS syntax in the editor (e.g. deleting a quote) makes the rule invalid → empty prompt → dropdown fallback, silently.
5. The bundle depends on `work/2026-09-19/R6P/assets-r6p/` (and `R5X/assets-r5h/`) staying in place; a shareable build should copy the fonts into the bundle directory.
6. Not done: a `BUILD.md`-level patch of the READY `bundles/combined8-c32` itself (not mine to modify); the two-rule part-A fix is `R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=0` with the
   R6P tools, or the literal two rules in §1 appended to its `runtime.css` (they only add `--display-prompt` and re-declare `::before`).
