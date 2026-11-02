# I2 — "How it actually works": the control path and I/O of the live demo

Agent I2, 2026-10-02. Scope: how text gets in, how the page clocks itself through 12 layers, the head and the next token with no
JavaScript, how state survives between tokens, sampling, the safety checks, and the UI. Read-only research. Process log:
`audit/2026-10-02/I2-how-it-works-control.log.md`.

**Which bundle.** `work/2026-09-19/bundles/demo-c32/` was **swapped to round 8 (R8U) at 13:07 today, while this research was running**
(READY: "demo-c32 round 8 (R8U v5) READY 2026-10-02 13:06:08"). R8U only changes the page layout: "model core rules identical to the
round-7 live bundle", the controls DOM is unchanged, and so are the handshakes (`R8U.md` §1–2). Everything below holds for both. Byte offsets
are for the **live R8U files** (index.html 7,449,079 B, runtime.css 53,632,212 B), measured with `LC_ALL=C grep -ob`. Note: in a UTF-8 locale,
grep reports wrong offsets for index.html because of its 4-byte noise glyphs. Both files are a single line, so I cite `runtime.css@<byte>`
instead of a line number. Generator code is cited as `R7X/tools/<file>:<line>`. R8U's tools are R7X's plus layout constants.

Notation: `T = work/2026-09-19/R7X/tools`, `B = work/2026-09-19/bundles/demo-c32`.

---

## 0. The idea in one paragraph (for the blog)

A browser already has an event loop that runs by itself: the rendering pipeline (style, layout, paint, once per frame). The page builds
its clock out of three pieces of that loop:
- **(a) Layout-to-number readbacks.** A hidden element's width encodes a number. A scroll-driven `view-timeline` turns that width into an
  animation progress, which sets a registered custom property in the *next* frame.
- **(b) Style queries.** `@container style(--x:N)` switches rules on and off based on those numbers.
- **(c) A tiny latch made of CSS animations and SVG SMIL.** A 1 ms CSS animation runs on an empty SVG `<g>`. Its `animationend` event
  starts a SMIL `<set attributeName="class" to="done" fill="freeze">`. CSS sees that through `body:has(#id.done)`.

Each step can only start when the previous step's `.done` class exists. Every value that crosses a frame carries a stamp of the epoch it
was computed for. Every latched value is held by a CSS transition with a 24-hour delay. That gives a sequential, race-free state machine.
The 12 layers inside a token are not driven by SMIL at all. They are **self-clocked** by the layer's own output: the last stage's width
also encodes "I am pass P", and the controller sets `--pass` to P+1.

---

## 1. Prompt input: from typed text to token ids

### 1.1 The text gets into CSS through an editable `<style>`
The prompt box *is* a `<style>` element, made visible and `contenteditable`:

```html
<style id="tk-editor" class="tk-editor" contenteditable="plaintext-only" spellcheck="false" role="textbox"
       aria-label="Editable prompt">.tk-root { --draft-prompt: ""; }</style>
```
(`B/index.html@8103`; emitted by `T/r6p_prompt.py:294`.) A `<style>` is `display:none` in the UA sheet; the page sets `.tk-editor{display:block;…}`
(inline head style; `T/r6p_prompt.py:301-309`). Editing the element's text changes the style sheet, so whatever the user types between the
quotes becomes the value of a registered `<string>` property, `--draft-prompt` (`@property --draft-prompt{syntax:"<string>";inherits:false}`, `T/r6p_prompt.py:118`).
This is standard DOM behaviour: changing a `<style>`'s text content re-parses its sheet. Deleting a quote or a brace makes the rule invalid, and the
page silently falls back to the dropdown prompt (README "Known limits").

Once the sheet is loaded, the editor is locked from the moment Run is ticked:
`body:has(#run:checked) .tk-editor, body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}`
(`T/r6p_prompt.py:315`; live `runtime.css@53541795` region, in R2G child-chain form).

### 1.2 Two tokenizer fonts do GPT-2 BPE inside OpenType shaping
For each prompt slot k (0..3), hidden 1 px "metric" elements render the whole draft string with two fonts, `GPT2TokenId0` (the low digit) and
`GPT2TokenId1` (the high digit):

```css
.tk-metric{position:absolute;…;font-size:1px;white-space:pre;font-kerning:none;--tk-text:var(--draft-prompt)}
.tk-metric::before{content:var(--tk-text)}
.tk-part-0{font-family:GPT2TokenId0}.tk-part-1{font-family:GPT2TokenId1}
.tk-pos-0{font-feature-settings:"p000" 1}  …  .tk-pos-3{font-feature-settings:"p003" 1}
```
(`T/r6p_prompt.py:183-194`; live `runtime.css@53525687` for `::before`; `@font-face` GPT2TokenId0 at `runtime.css@52833871`.)

Inside each font (`T/build_metric_tokenizer_font.py`):
- **Byte glyphs.** Each ASCII byte maps to the glyph of its GPT-2 byte token (`:140-146`).
- **`rlig` = BPE.** GPT-2's whole merge table, in rank order, becomes GSUB ligature substitutions `sub left right by merged`. Rules whose
  glyph sets don't overlap are packed into one lookup, which "is equivalent to applying their rank-ordered lookups separately" (`:75-97`, `:219-229`, `:265-267`).
- **`pNNN` = keep token k only.** The position feature k replaces every token glyph before or after position k with a zero-advance glyph
  `zero` (`eraseBefore…`/`eraseAfter…` lookups with `@SEEN` context, `:230-257`).
- **Advance = the id.** The only non-zero advance left is the surviving token's. In `GPT2TokenId<part>` that advance is
  `digit + 1`, where `digit = (id // 32767**part) % 32767`. The +1 tells "digit 0" apart from "no token" (`:153-159`). Base 32,767 is used because
  "HarfBuzz exposes advances above 32,767 as signed values" (`:155-156`).
- **Exact pixels.** upem is 64 and the font size is 1 px, so one font unit is exactly 1/64 px = one Blink LayoutUnit (`T/r6p_prompt.py:17-19`).

### 1.3 Reading the width back as an integer
```css
.tk-probe-0-0{container:tk-0-0/inline-size;width:anchor-size(--tk-a-0-0 width,0px)}
@container tk-0-0 (width > 0px){.tk-low-0{--pt-low-0:round(nearest,calc(100cqi/1px*64 - 1),1)}}
.tk-high-1{--pt-id-1:if(style(--pt-present-1:1):calc(var(--pt-low-1) + 32767*var(--pt-high-1));else:-1);
           --prompt-token-id-1:if(style(--prompt-armed:1):var(--pt-id-1);else:-1);…}
.tk-high-3{container-name:tkprompt;--prompt-count:calc(var(--prompt-has-0) + … + var(--prompt-has-3))}
```
(live `runtime.css@53526023`, `@53526189`, `@53527233`, `@53529324`; generator `T/r6p_prompt.py:177-211`.)
`anchor-size()` copies the metric's width onto an absolutely positioned **size container**. Its child reads `100cqi` (100 % of the container's
inline size) back as a number: digit = width × 64 − 1. The id is `low + 32767·high`. The tokenizer chain is nested HTML:
`metric_k0, probe_k0 > low_k > [metric_k1, probe_k1 > high_k > …]` × 4, and the whole model sits under it (`T/r6p_prompt.py:157-172`).
So `--prompt-token-id-k` and `--prompt-count` are *inherited* by the model.

**Arming / isolation.** The model-facing values are gated by `--prompt-armed`. It is sticky:
`body:has(#run:checked),body:has(#run-latched.done){--prompt-armed:1}` (`T/r6p_prompt.py:182`). So typing restyles only the dozen tokenizer
elements, never the ~90k model elements, and nothing the model reads can change after the click (R6X.md §10 fix item 2).

**Feeding the model.** At epoch e ≤ 4 the model's input token is the prompt id when the prompt has that many tokens. Otherwise it is the
fed-back winner:
```css
.feedback-select{--pf-1:if(style(--prompt-count:0):var(--frozen-prompt);else:var(--prompt-token-id-0));
                 --pf-2:if(style(--prompt-count:0):var(--feedback-1);style(--prompt-count:1):var(--feedback-1);else:var(--prompt-token-id-1));…}
.feedback-select{--token:if(style(--epoch:1):var(--pf-1);…;style(--epoch:5):var(--feedback-4);…;else:var(--frozen-prompt))}
```
(live `runtime.css@51388469`, `@51389073`; `T/r6p_prompt.py:138-151`.) `--token` then drives the embedding font (GRUP/LOCL axes), the same
lookup for prompt ids and generated ids.

**The 4-token limit** is structural. The fonts carry only the position features p000..p003 (`T/r6p_prompt.py:53,64-74`, `R6P_PROMPT_SLOTS=4`),
and the HTML has four slot stages. Tokens 5 and later simply have no slot that reads them. Other limits (no newlines, no double spaces,
ASCII only) come from the font corpus and `white-space:pre` (README "Known limits"; non-ASCII raises in the builder, `:141-142`).

**Display of ids → text.** `@counter-style gpt2-vocabulary{system:fixed -1;symbols:"" "!" "\22 " …}` maps id −1 to "" and id n to the token's text
(`runtime.css@52991424`). The output and the chip readout print `counter(x, gpt2-vocabulary)` (`T/r6p_prompt.py:223-227, 253-257`).

---

## 2. The clock: stepping layer 1 → 12 → head → next token without JS

### 2.1 The primitive: CSS animation → SMIL → `:has()`
```html
<g id="token-3-ready"></g><g id="token-3-ack"></g>
<g id="token-3-captured"><set attributeName="class" to="done"
   begin="token-3-ready.animationend+0.001s;r7b-prefill-ready-3.animationend+0.001s" fill="freeze"/></g>
<g id="token-3-advanced"><set attributeName="class" to="done" begin="token-3-ack.animationend+0.001s" fill="freeze"/></g>
```
(`B/index.html@7436327`; generator `T/browser_gpt2_runtime.py:138-143`.) CSS starts the handshake by giving the empty `<g>` a 1 ms animation:
`@keyframes native-handshake{from{opacity:.99}to{opacity:1}}` (`:80`). SMIL listens for the DOM `animationend` event as an event-based `begin`
and sets `class="done"` with `fill="freeze"`, so the class never goes away. CSS reacts with `body:has(#token-3-captured.done) …`.
Each signal is **write-once and monotone**. The bundle has 80 `<set>` elements: 36 captured + 36 advanced + run-latched + fonts-loaded + eos-done + 5 stop relays.
After build, every `body:has(#id…)` is rewritten into an explicit child chain, `body:has(> :where(.a) > … > #id.done)`, so Blink does not walk
the 90k-element subtree (`T/r2g_has_scope.py:1-16`). That is why the live rules look like
`…> :where(.native-signals) > #token-3-advanced.done){--epoch:4}` (`runtime.css@51157522`).

### 2.2 Starting: fonts-loaded and Run
- **Font barrier.** For each of the 286 faces, a witness glyph's measured width (`anchor-size`) is compared with its expected advance, giving 1 px
  if it matches (`T/browser_gpt2_runtime.py:200-206`). A min-reduction tree feeds `.font-status`, and
  `@container fontready (min-width:.99px){#fonts-detected{animation:native-handshake 1ms both}}` → SMIL `#fonts-loaded.done` (`:207-211`;
  `runtime.css@52903683`, `@52903811`).
- **Run.** The checkbox `#run` is only clickable after `#fonts-loaded.done` (`T/r6p_prompt.py:316`). Then
  `body:has(#run:checked) #run-start{animation:native-handshake 1ms both}` → SMIL `#run-latched.done` (`T/browser_gpt2_runtime.py:90`, `:584`;
  `B/index.html@7317`). The model is locked until both have happened:
  `.core-block{content-visibility:hidden} body:has(#fonts-loaded.done):has(#run-latched.done) .core-block{content-visibility:visible}`
  (`T/browser_gpt2_runtime.py:391`; `runtime.css@51490001`). `content-visibility:hidden` skips style and layout of the whole subtree, so before Run the
  model costs nothing.

### 2.3 Inside a token: 12 layers, self-clocked (no SMIL per layer)
The live bundle uses R3R's "fold hop" controller (`manifest.json`: `r3rFoldHop true`, `r2fLeanHandshake true`). One shared layer graph is reused
12×. Layer-specific weights sit in `@container corestate style(--layer:L){…}` blocks (`T/browser_gpt2_reused_core.py:77-100`).
```css
.core-controller{--pass:min(calc(round(nearest,(1572864 / (var(--pr-stamp) + 2) - 524288 - 131072) / 1024,1) + 1),var(--pass-cap));
  --pass-cap:12;--pr-stamp:inherit;
  --held:clamp(0,calc(round(nearest,(1572864 / (var(--pr-stamp) + 2) - 524288 - 131072) / 1024,1) - var(--pass-cap) + 1),1);
  container-name:loopcontrol}
.core-controller{container-name:runtime loopcontrol;--layer:mod(calc(var(--pass) - 1),12);
  --position:calc(round(down,calc((var(--pass) - 1) / 12),1) + 1)}
@container loopcontrol style(--held:1){.loop-input{--loop-ready:0}}
```
(`runtime.css@45237332`, `@45406908`, `@45355706`; generator `T/r3r_fold_hop.py:119-122, 154-158`, `T/browser_gpt2_reused_core.py:281-285`.)
- `--pr-stamp` is the view-timeline progress of the **proj stage's generation marker**. Its width is `markerbase + pass·1024px`, set when the
  last stage (proj) of pass P is laid out (`T/browser_gpt2_reused_core.py:94-98`; decode constants `T/r3r_fold_hop.py:61-71`). So the
  controller sees "proj finished pass P" and sets `--pass = P+1`. `--layer` and `--position` follow by arithmetic.
- The same proj carriers' widths encode the layer output (`262144px + 128·out_i`). They are read back as the next layer's input `--loop-in-i`
  (`T/r3r_fold_hop.py:12-21, 153-156`). No separate transport hop or latch is needed (`:29-37`).
- Inside a layer, each stage (qkv, attention, attn-proj, fc, proj) sits behind a **gate**: `content-visibility:hidden`, opened by
  `@container shared-KIND-receipt style(--gate-KIND:1)`. Here `--gate-KIND` = 1 only if that stage's marker stamp decodes to the current pass
  (C2 §1 "Dense matvec stage" and §2 "How a stage/layer is gated"). The gates close and open in cascade, so each stage is laid out
  exactly once per pass (`T/r3r_fold_hop.py:29-37`).
- **Layer 0** additionally waits for the new token's embedding:
  `@container runtime style(--layer:0){.loop-input{--loop-ready:var(--embed-ready);…}}` (`runtime.css@45407082`; `T/browser_gpt2_reused_adapter.py:57-60`).
- **Token boundary.** `--pass-cap` is 12·token. When the marker reaches the cap, `--held` = 1, the core locks (`--loop-ready:0`), and the
  layer-11 export becomes visible (`T/r3r_fold_hop.py:39-44, 177-187`). The cap is raised only by the token handshake:
  `body:has(#token-1-advanced.done) .core-controller{--pass-cap:24}` … (`runtime.css@45357430`; `T/r3r_fold_hop.py:164-165`).

### 2.4 From the last layer to the next token
1. **Bridge.** The layer-11 output is read back through the `b11-bridge`. Its receipt is
   `--bridge-ready:calc(1 - min(1,abs(round(nearest,(524288 / var(--bridge-stamp) - 524288 - 262144) / 1024,1) - var(--epoch))))`
   (`runtime.css@45514427`): ready only when the bridge's stamp equals the current epoch.
2. **Head unlock.** `.full-head{content-visibility:hidden}` is opened only under `@container b11-bridge style(--bridge-ready:1)`
   (`T/r2d_knobs.py:73-80`, `T/browser_gpt2_runtime.py:480`). The head's input bank holds the final hidden state with a delayed transition. The
   transition is released only while bridge-ready is 1 (`T/browser_gpt2_runtime.py:405-421`).
3. **Head → winner.** A two-pass argmax over the 50,257 vocabulary rows (geometry max trees; the compute agent's scope) gives `--winner`. The winner leaves the head
   as an element `width: epoch px; height: winner px`. A size container reads it back as `--head-output-epoch` / `--winner`, so **the
   winner travels with its own epoch** (`T/browser_gpt2_runtime.py:473-480`; R7H.md §1 H1–H3).
4. **Token handshake (epoch e):**
   ```css
   @container runtime style(--epoch:e){@container headstate style(--head-output-epoch:e){
       body:has(#run:checked) #token-e-ready{animation:native-handshake 1ms both}
       @container headstate style(--winner:50256){body:has(#run:checked) #eos-ready{animation:native-handshake 1ms both}}}}
   @container headstate not style(--winner:50256){body:has(#run:checked):has(#token-e-captured.done) #token-e-ack{animation:native-handshake 1ms both}}
   body:has(#token-e-advanced.done){--epoch:e+1}
   ```
   (`T/browser_gpt2_runtime.py:105-112`; live `runtime.css@51157703`, `@51159400`, `@51157522`.) ready → (SMIL) captured → latch the winner
   (§3) → ack → (SMIL) advanced → `body{--epoch:e+1}` and `--pass-cap` += 12. `--token` switches to `--feedback-e`, the embedding re-lays out, and
   its stamp matches → layer 0 runs again.
5. **Embedding receipt.** The marker is `width:calc(20000px + (var(--epoch) - 1 + var(--prompt-live))*1024px)` (`B/index.html@118083`). The receipt is
   `--embed-ready:calc(1 - min(1,abs(round(nearest,(65536 / var(--embed-stamp) - 65536 - 20000) / 1024,1) - var(--epoch))))` (`runtime.css@45944021`).

### 2.5 Why the ordering is safe (no race)
- **Stamped values.** Every value that crosses a frame (embedding, each stage's matvec output, the bridge, the head output, the layer
  marker) is accompanied by a geometry stamp of the epoch/pass it was computed for. A consumer opens only when stamp == current counter. A stale value
  is not consumed late; the consumer just waits a frame (C2 §2; R7H.md §1).
- **Monotone, chained signals.** `class="done"` is never removed (`fill="freeze"`). `captured` can only begin on `ready`'s `animationend`;
  `ready` needs **both** `--epoch:e` and `--head-output-epoch:e`; `ack` needs `captured.done`. The token state machine can only go forward, one
  step at a time.
- **Locks.** `content-visibility:hidden` keeps the model (before Run), the layer body (while `--loop-ready` is 0 or `--held` is 1), every stage
  (until its receipt), and the head (except while `--bridge-ready:1`) from computing on provisional inputs.
- **The two real races found were fixed by design, not by timing** (R6X.md §10):
  - R2: the embedding stamp encoded only the epoch, so at Run layer 0 could read the stale dropdown embedding. Fix: `--prompt-live` folded into the marker.
  - R1: a same-style-pass arm+latch could freeze pre-armed values. Fix: the latch was removed; arming is sticky and the editor is locked from the click.
- **The id guard (§5)** adds a check at the one hop that had no receipt.
- **The frame is the tick.** Each readback hop costs at least one frame, because timeline progress from frame N's layout is seen by frame N+1's style
  (C2 §5: ≈16 recalcs and ≈9 layouts per layer, measured 216–266 / 106–114 per token). (inferred) Chrome keeps producing frames by itself because view-timeline-attached
  animations are live and their inputs change. Nothing external ticks.

---

## 3. State latching across tokens

**The latch idiom.** A registered custom property listed in `transition-property` with `transition-delay:86400s; transition-duration:1ms;
steps(1,end)`. When the computed value changes, a transition starts. For 24 hours it shows the *before-change* value. Removing the property from
`transition-property` "opens the write window"; listing it again "closes" it and freezes the last value (C2 §4).

**Winner slots (36).** One nested `div.token-slot-e` per epoch (36 in `B/index.html`):
```css
.token-slot-3{--saved-token-3:if(style(--head-output-epoch:3):var(--winner);else:-1);
  transition-property:--saved-token-3;transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}
@container runtime style(--epoch:3){.token-slot-3{transition-property:none}}
body:has(#token-3-captured.done) .token-slot-3{transition-property:--saved-token-3}
.feedback-metric-3{width:calc(65536px + (var(--saved-token-3) + 1)*8px);view-timeline:--feedback-t3 inline}
.feedback-reader{--feedback-3:round(nearest,(524288 / var(--feedback-p-3) - 524288 - 65536) / 8 - 1,1)}
```
(`runtime.css@51152683`, `@51152928`, `@51154381`, `@51154431`, `@51154538`; `T/browser_gpt2_runtime.py:93-103`.)
The slot is open only during its own epoch and closes at `captured`. The id is then re-encoded as a width (8 px per id) and read back by
`.feedback-reader`, an **ancestor of the whole model**. This is "the only way a value flows upward" (R7H.md §1 H5). That gives `--feedback-e`, which
is both the next input (`--token`) and the displayed word (`body:has(#token-e-captured.done) .visible-output{--display-token-e:var(--feedback-e)}`,
`T/r6p_prompt.py:262-268`).

**KV cache (36 slots × 12 layers).** 12 nested `div.fvs-bank-L` hold `--fc-{k,v,ks,vs}-{slot}-{head}`. They are 64-axis font-variation strings
(`syntax:"*"`), all held by the base latch:
`.fvs-bank{transition-property:<all fields>;transition-duration:1ms;transition-delay:86400s;…;transition-behavior:allow-discrete}`
(`runtime.css@31117905`; `T/browser_gpt2_font_vector_cache.py:216-221`). The write slot is
`.fvs-query{--fvs-write-slot:calc(min(var(--position) - 1,0 + mod(max(0,var(--position) - 1 - 0),36)))}` (`runtime.css@31117779`). Each
(layer, slot) has a write rule
`@container corestate style(--layer:3){@container fvscache style(--fvs-write-slot:5){.fvs-bank-3{transition-property:<others>;--fc-k-5:var(--fvs-live-k-0),…}}}`
(`runtime.css@31996019`; `T/browser_gpt2_font_vector_cache.py:337-338`). The slot being written is left out of the list, so it takes the live value.
When the layer moves on, it is listed again and frozen. `manifest.json`: `kvWindow 36`, `kvStorage "native delayed whole-head font settings"`.

**Capacity 36 and the stop rule.** 36 = up to 4 prompt tokens + 32 new ones. With N = max(prompt count, 1), the run stops at epoch
t = N − 1 + min(32, 36 − N + 1), which gives {0,1: 32, 2: 33, 3: 34, 4: 35} (`T/r7b_features.py:117-124`; manifest `r7bStops`). The stop is a
suppression of the ack plus a SMIL relay to the status line:
```css
@container tkprompt style(--prompt-count:c){ body:has(#token-t-captured.done) #r7b-stop-ready-c{animation:native-handshake 1ms both}
                                             body:has(#token-t-captured.done) #token-t-ack{animation:none!important} }
body:has(#r7b-complete-c.done) .status::after{content:"Complete • 32 new tokens"}
```
(`T/r7b_features.py:139-149`; live `runtime.css@53584371`.) EOS stops the run separately: an ack needs `not style(--winner:50256)`, and
`#eos-ready` → `#eos-done.done` → "Complete • end of text" (`runtime.css@53469850`).

**Prefill head skip.** On prompt epochs e < N, the winner would be discarded anyway, so the head is kept locked by a later, equal-specificity
rule. The capture fires from a signal in the core's SVG instead:
```css
@container tkprompt style(--prompt-count:c){@container runtime style(--epoch:e){ .full-head{content-visibility:hidden}
  @container corestate style(--held:1){ body:has(#run:checked) #r7b-prefill-ready-e{animation:native-handshake 1ms both} … }}}
```
(`T/r7b_features.py:96-111`; live `runtime.css@53555435`; second SMIL begin `r7b-prefill-ready-3.animationend` above.) `--saved-token-e` latches −1,
`--pf-(e+1)` ignores it, and the counter style prints "". Measured saving: ≈2.6–3 s per skipped head (R7B.md §3).

---

## 4. Sampling: Gumbel-max with a noise font

- **Noise font** `gumbel-noise.ttf` (`T/build_noise_font_r7b.py`): 50,257 glyphs at U+80000+id, base advance 800. The HVAR deltas are
  `2·n[s, id]`, where n = rint(clip(Gumbel(0,1), −3, 12) · q_per_logit) and the table rng seed is 20261001 (`:32-37`). The axes are
  `SEED` 0..64, with one *tent* region per column s peaking exactly at SEED = s, and `TEMP` 0..2, with a ramp region (0,1,1) in normalised
  coordinates (`:47-56`). So at TEMP = T the glyph adds 800 + T·n[s] units. At T = 0 it adds a constant 800 to every row, so the argmax is
  unchanged (bit-identical to greedy; R7B.md §0).
- **Where it goes.** The 7th glyph `chr(0x80000+token)` is appended to every `.head-row` and every fine-row string. `NoiseQ` joins the head font
  lists (`T/r7b_features.py:220-238`). Its `size-adjust` makes one font unit equal one score quantum (`:198-210`; `runtime.css@52834095`). Each row's width
  is then score + T·Gumbel, and the head's ordinary argmax computes **argmax(logit + T·g)**, which is a sample from softmax(logit/T) (the
  Gumbel-max trick). The axes ride on the head bank's latched list: `--head-fvs: …,"SEED" var(--noise-col),"TEMP" var(--temp)` (`:241-245`).
- **Per-step column.** `.head-input-bank{--noise-col:calc(mod(var(--seed) + var(--epoch) - var(--r7b-n),64) + 1)}` (`runtime.css@53621179`), where
  `--r7b-n` = max(prompt count, 1) (`runtime.css@53621151`). Step 1 is the first new token, so prefill is unaffected.
- **Seed from a clock.**
  ```css
  @keyframes r7b-clock{from{--clock:0}to{--clock:64}}
  body{animation:r7b-clock .97s linear infinite;animation-play-state:paused;
       --seed-live:calc(mod(round(down,var(--clock),1),64) + 1);
       --seed:if(style(--seed-override:0):var(--seed-live);else:var(--seed-override))}
  body:has(> .controls:hover),body:has(> .controls:focus-within),body:has(> .tk-panel:focus-within){animation-play-state:running}
  body:has(#run:checked),body:has(#run-latched.done){animation-play-state:paused}
  ```
  (`T/r7b_features.py:263-269`; live `runtime.css@53601383`.) The seed is "when you clicked", in 64 bins of about 15 ms. The clock runs only while the
  pointer or focus is at the controls, and it freezes at Run. Picking a seed in the `<select>` overrides it through 64
  `body:has(> .controls > label > #r7b-seed > option[value="k"]:checked){--seed-override:k}` rules. The value reaches the bank through
  `@container runtime style(--seed:k){body:has(#run:checked) .head-input-bank,…{--seed:k}}` relays, sticky from Run (`:271-279`).
  Temperature works the same way with 2 rules. The readout is `.r7b-seed-out::before/::after` via 67 container rules (`:285-289`; e.g. `runtime.css@53622544`).
- **Verified.** 12-layer seed 17 T = 1.0 and seed 42 T = 0.7 matched the NumPy sampled references on all 32 new tokens (R7B.md §3), and so did
  headed seed 17 T = 1.0 (R7X.md §0).

---

## 5. Safety: the scrollbar bug and the id guard

**The bug (R7H.md §0, §2; R6X.md §11).** The winner → next-input hop (H5 in §3) decodes the scrollport as a hard-coded 524,288 px. In headed
Chrome with a classic, space-taking scrollbar (macOS "Show scroll bars: Always", Windows, Linux), the `overflow:scroll` box
`.feedback-scroller` lost 15 px. The decode was then off by `(65536 + 8(id+1))·15/(8·524273)` ids, i.e. **+1 for every id ≥ 9283**.
"Shubham was … House of Representatives" became "House ofEARTH" (17132 → 17133, fed back as "EAR"). Headless runs and `--hide-scrollbars`
never showed it, which is why every earlier 32/32 had passed. It was not a race: under CPU stress the unguarded build still gave 8/8 (R7H.md §6.3).
- **Fix (v6).** `.feedback-scroller{scrollbar-width:none}` (`runtime.css@53627332`; scroller definition `runtime.css@51138023`).
- **Guard G2, calibration.** An extra metric of constant width (id 50256, the most bias-sensitive) is read back the same way.
  `--fb-ok` = 1 only if it decodes exactly. Otherwise every `#token-e-ready` is suppressed and a red panel appears:
  ```css
  .feedback-metric-cal{width:calc(65536px + 50257*8px);view-timeline:--feedback-tcal inline}
  @container headstate not style(--fb-ok:1){#token-1-ready,…,#token-36-ready{animation:none!important}}
  @container style(--fb-ok:0){body:has(#fonts-loaded.done) .feedback-reader>.fb-warn{display:block}}
  ```
  (`T/r7h_id_guard.py:68-93`; live `runtime.css@51398121`, `@51404198`, `@51408181`.) It fails closed: before the animation applies, progress is
  0 → decode ∞ → `--fb-ok` 0 (R7H.md §3).
- **Guard G3, agreement.** `.token-state` echoes every slot's id through its own animation on the same timeline and compares it with the exact
  latched `--saved-token-e`. `@container headstate not style(--fb-agree-e:1){#token-e-ack{animation:none!important}}` (`runtime.css@51405005`;
  `T/r7h_id_guard.py:75-84`). A late timeline sample waits one frame; a biased decode holds the run forever with the correct winner latched. Cost:
  zero added frames (the echo lands before `captured`), 900 vs 901 recalcs on the smoke test (R7H.md §6.1).
- **Fault injection.** With the fix off and scrollbars shown, the guard held before token 1 and showed the panel; with the fix on, the guard stays
  silent and the run is 32/32 (R7H.md §6.2). Remaining environmental risks: Chrome's "minimum font size" setting (the tokenizer metrics are 1 px),
  and DSF 2 at 12 layers, which has not been harness-tested (R7H.md §5).
- **Other self-checks.** The font barrier (§2.2) refuses to start until every face's witness advance matches within 0.125 px.

---

## 6. UI: everything is CSS state

- **Loading.** The inline head `<style>` paints the controls, the editor and an indeterminate compositor bar ("Loading the model's stylesheet (… MB of CSS)…") before
  the 54 MB sheet arrives. `body>:not(.controls):not(.ld):not(.tk-panel):not(.r8u-head){content-visibility:hidden}` stops the unstyled model from
  being laid out, and the sheet lifts that lock with the same selector (`T/r6v_progress_ui.py:177-203`; live head of `B/index.html`). Then "Loading model
  weights: N of 286 fonts". N is the **sum** of the 286 one-pixel font proofs, built from a 16-fan-in `anchor-size()` calc tree, read by an inline-size
  container with 286 `@container fontload (min-width:Npx)` text rules (`T/r6v_progress_ui.py:121-166`; `runtime.css@52917946`).
- **Status text.** This is a `.status::after` content ladder:
  - "Loading model fonts…"
  - `body:has(#fonts-loaded.done)` → "Ready • 12-block native compute" (`runtime.css@53523255`)
  - "Complete • 32 new tokens" (`@53584371`) or "Complete • end of text" (`@53469850`)

  Later `:has()` rules win by order or specificity (`T/browser_gpt2_runtime.py:562-569`).
- **Progress bar.** `.pg` lives as the first child of `.core-controller`, so it can query the `corestate` container (`T/r6v_progress_ui.py:16-22, 61-65`).
  - Per layer: `@container corestate style(--layer:k){.pg-lay::after{content:" · layer k+1 of 12"} .pg-exact{width:k/12·100%} .pg-est{animation-name:pg-est-k}}`.
    The exact part is dark. The light part is an estimate: a compositor `scaleX` animation restarted by the name change, with the duration estimated from s/layer (`:89-117`).
  - Token counter: `@container runtime style(--epoch:e)` → "new token t of 32" / "absorbing prompt token e of N" (`T/r7b_features.py:152`, live strings in the log step 46).
  - Head phase: `@container corestate style(--held:1)` → the 13th, orange segment fills over an estimated 2.8 s and pulses
    (`T/browser_gpt2_runtime.py:39-51`; R8U text " · vocabulary head (choosing the next token)"; `runtime.css@53627002`).
  - It is hidden at completion with `display:none!important` (`T/r7b_features.py:147-148`).
- **Run / continue.** A real `<input type=checkbox id=run>`. It is dimmed and `pointer-events:none` until `#fonts-loaded.done`
  (`T/r6p_prompt.py:316`). Ticking it is the only "event" the user provides. `#run-latched.done` makes the run sticky, and selects are locked from then on
  (`T/browser_gpt2_runtime.py:568`).
- **Reset.** `<form action="index.html"><button>Reset</button></form>`: a GET navigation, so the page restarts with fresh state. A browser Reload would
  instead restore the ticked checkbox, and restart the seed clock at 0 (README; R6X.md §10).
- **Output.** `.visible-output::before/::after` print the prompt and the 36 `--display-token-e` values via `counter(…, gpt2-vocabulary)`; hidden slots are −1 → "".

---

## 7. Diagrams (proposed)

### 7.1 One token's timeline (epoch e, a "new token" epoch)
```
frame →
 body --epoch:e ◄─ #token-(e-1)-advanced.done        .core-controller --pass-cap:12e  (--held 1→0)
   │
   ├─ .feedback-select --token = --feedback-(e-1)  ──► embedding font relayout ──► embed marker stamp == e ? ──► --embed-ready:1
   │                                                                                                            │
   │   ┌──────────────── layer loop, 12× (pass P = 12(e-1)+1 … 12e), no SMIL ────────────────┐                  │
   │   │ --layer = mod(P-1,12) selects @container corestate style(--layer:L) weights          │◄─ layer 0 waits ─┘
   │   │ qkv ─gate─► attention (writes KV slot position-1 in fvs-bank-L) ─gate─► attn ─gate─► │
   │   │ ln2/fc ─gate─► proj carriers: width = 262144+128·out  &  marker width = base+P·1024  │
   │   │        each gate opens when its view-timeline stamp == P   (≥1 frame per hop)        │
   │   │ controller reads marker → --pass = min(P+1, cap)                                     │
   │   └───────────────────────────────── until marker == 12e → --held:1 (core locked) ─────┘
   │
   ├─ layer-11 export → b11 bridge stamp == e → --bridge-ready:1 → head bank latch opens → .full-head visible
   ├─ head: 50,257 rows (+ noise glyph) → coarse max → fine max → --winner ;  detached source  w=e px, h=winner px
   ├─ headstate --head-output-epoch:e  AND --fb-ok:1  ──► #token-e-ready  (1 ms CSS animation)
   ├─ SMIL: token-e-ready.animationend+1ms → #token-e-captured.class="done"
   ├─ .token-slot-e latch closes (holds winner)  →  .feedback-metric-e width = 65536+8(id+1) px
   ├─ next frame: --feedback-e decoded on .feedback-reader ; echo --fb-agree-e:1 on .token-state ; output shows the word
   ├─ winner ≠ 50256 AND agree  ──► #token-e-ack (1 ms)        [stop epoch: ack suppressed → #r7b-stop-ready → "Complete"]
   └─ SMIL: token-e-ack.animationend+1ms → #token-e-advanced.done ──► body --epoch:e+1, --pass-cap:12(e+1)   ⟲
```

### 7.2 The state machine (page level)
```
 [LOADING CSS] ──sheet applies──► [LOADING FONTS: "N of 286"] ──all witnesses match → #fonts-loaded.done──► [READY]
                                                                                                             │ user ticks #run
                                                                                                             ▼
                              #run-start (1 ms) → SMIL #run-latched.done ; --prompt-armed:1 (sticky) ; editor/selects locked ; clock paused
                                                                                                             ▼
   ┌──────────────────────────────────────────── EPOCH e (e = 1 … t) ───────────────────────────────────────────┐
   │ [EMBED] ─stamp==e─► [LAYERS 1..12 self-clocked] ─marker==cap─► [HELD]                                      │
   │     HELD ─ e < N (prompt) ─► #r7b-prefill-ready-e ─────────────────────────┐ (head skipped, slot = −1)       │
   │     HELD ─ e ≥ N ─► [HEAD] ─head-output-epoch==e & fb-ok─► #token-e-ready ─┤                                 │
   │                                                                          ▼                                 │
   │                                                        [CAPTURED] (#token-e-captured.done, slot latched)   │
   │            ┌─ winner = EOS ──────────────► #eos-ready → #eos-done ──► [COMPLETE • end of text]            │
   │            ├─ e = t (stop epoch) ────────► ack suppressed; #r7b-stop-ready-c → #r7b-complete-c ─► [COMPLETE • 32 new tokens]
   │            ├─ echo ≠ latched id ─────────► ack blocked: wait 1 frame (stale) / HOLD forever (bias)            │
   │            └─ else ─► #token-e-ack → [ADVANCED] (#token-e-advanced.done) → --epoch:e+1, --pass-cap += 12 ──┘
   └────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
   fb-ok = 0 at any time ─► every #token-e-ready suppressed + red "Geometry self-check failed" panel  [HELD-ERROR]
   Reset = GET navigation to index.html (new document) ; there is no transition back inside the page ("one run per page load")
```

---

## 8. Things marked uncertain / not verified here
- (inferred) Why Chrome keeps scheduling frames with no input: live, view-timeline-attached animations and changing layout. Not
  traced in Blink source here.
- The head's internal two-pass argmax (coarse groups → fine rows) is summarised from R7H.md §1 H1–H2, not re-derived; it belongs to the compute section.
- Per-stage gate details (exact `--gate-KIND` formulas per stage, F5 scoping of `--native-pass`) are cited from C2 §1–2, which describes an earlier
  ctx32 bundle. The controller rules quoted in §2.3 were re-verified in the live CSS.
- The UI strings are from the live R8U bundle; R8U changed some texts (e.g. prefill " · absorbed") relative to R7B.md.
