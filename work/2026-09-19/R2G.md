# R2G — why the loop-handshake passes (357 / 485 elements) cost 3–6× the cost model

Agent R2G, 2026-09-19. Files: `work/2026-09-19/R2G/` (`fixture/gen.py` + patched M1 harness `fixture/run.mjs`, `fixture/results/`,
`tools/` = F4/tools + `r2g_has_scope.py`, `emitter.diff`, `static-check.txt`). Log: `R2G.log.md`. Read-only elsewhere; no bundle built.

## 0. Headline (revised after the fixtures, 2026-09-20)

- **Measured verdicts (AC, under the mutex, 3 trials): hypotheses (a) SMIL `<g>/<set>`, (b) 1,538 timeline animations on one element,
  (c) 769-name `transition-property` lists, (d) 769 changed carrier timelines — all NO** (each ≤ 6 ms per pass at the demo's shapes, §3b).
  The one real, new item is `:has()` argument traversal (H-e below): **7.5 ns per visited element, ≈ 28 ms per capture / advance restyle
  of `.core-controller` and ≈ 8 ms per svg restyle ≈ 36 ms/layer ≈ 0.43 s/token traced**; the fixed-depth rewrite (`R2G/emitter.diff`)
  removes ≈ 30 of those 36 ms → **≈ −0.35 s/token** (≈ −0.3 s untraced). That is 10 % of the ≈ 4 s/token residual, not the explanation.
- **The remaining ≈ 150–180 ms per 485/357 pass is NOT produced by anything inside the loop-controller region**: a replica with the demo's
  exact rules/DOM (`pa-*`, `cap-*`), and a fixture cut from the *real* bundle CSS/DOM (`real-cap-nocore`, 46k rules incl. all
  `@property`/`@keyframes`) both restyle the capture in **21–45 ms**, vs 223 ms in the demo trace. Re-reading the frame sequence also
  corrects R2A: the 485 pass (frame F) is the **capture** (`--loop-captured-pass`, `--loop-held`), not the `--pass+1` advance (frame A).
  Candidates that remain for the residual (not testable in a fixture page without the full bundle): the whole-document state the
  controller restyle touches in the real page — ≈10.9 k live view-timelines whose `serviceAnimations` and pending updates run inside
  `UpdateLayoutTree` (R2A §1 attributes ≈13 ms/pass to that, from a light trace), the 12 nested `.fvs-bank-L` with 2,500 in-delay
  transitions (F4 §4: ≈5.7 µs each on *every* style pass ≈ 14 ms), GC inside the pass, and the style-container change propagation over
  the open 16.9k-element core (`kRecalcStyleContainer` descendant scan) — a full-bundle trace with `blink.debug`/style categories, which
  the round's ground rules reserve for the bench agent, is the way to split them.
- Static analysis (§1) and the original H-e reasoning follow; the cross-bundle table (§3a) that seemed to support a 50 ns/visit cost is
  superseded by the direct measurement (7.5 ns/visit).

### Original H-e statement (before measurement)
- **The residual is `:has()` argument traversal, not SMIL, not the 1,538-animation reader, not transition lists.**
  `.core-controller` (16,892 descendants) carries **272** rules `.core-controller:where(:has(#loop-captured-N.done))` /
  `…:has(#loop-advanced-N.done)` (96 + 88, plus 88 with a `#loop-ack-N` subject) and **7** `:where(body:has(#token-N-advanced.done)) .core-controller`
  rules (`body` = 69,521 descendants); `.core-block` has `body:has(#fonts-loaded.done):has(#run-latched.done)`. Blink evaluates
  every `:has()` argument with a **full reverse-order walk of the anchor's subtree once per distinct argument per style pass**
  (`CheckPseudoHasArgumentTraversalIterator`; the bloom fast-reject filter cannot reject `#id.done` once any `.done` exists, and
  the signal svg sits at the *start* of the subtree so the reverse walk always crosses the 16.3k-element `.loop-compute` first).
  Pass-advance restyle (485): 184 × 16,892 + 9 × 69,521 ≈ **3.73 M element visits**; loop-readback restyle (357): the 88
  `#loop-ack-N` `<g>`s each evaluate their ancestor argument: 88 × 16,892 ≈ **1.49 M visits**.
- Fitted per-visit cost and the fixture confirmation are in §3 (measured under the mutex on AC; see status there).
- **Fix (prototyped, `R2G/emitter.diff`, 2 files, +1 module):** rewrite the arguments to exact direct-child chains
  (`:has(> .core-block > .loop-reader > .loop-input > .loop-signals > #loop-advanced-N.done)`, and the 12-deep token chain /
  `.font-status` chain for the body rules). Blink bounds the traversal to the chain depth when the argument has only child
  combinators, so each argument visits the ≈580-element svg instead of 16.9k / 69.5k. Specificity unchanged (`:where()`).
  Verified statically on `bundles/combined` (272 + 7 + 1 rules rewritten, chains checked against the real DOM). Predicted
  −250 ms/layer ≈ **−3.1 s/token traced ≈ −2.5 s untraced** (30.3 → ≈ 27.8 s/token); §4.

## 1. What the two passes restyle (step 1)

Sources: `bundles/combined/runtime.css` (fixed-string scans; the sheet is one 40.7 MB line), `index.html` (html.parser walk),
emitter `F4/tools/probe_native_reused_loop.py:loop_parts`, `browser_gpt2_reused_adapter.py:150-176`, `browser_gpt2_runtime.py:329`.

DOM: `body > .feedback-reader > … > .position-embedding > .core-controller (16,892 desc) > .core-block#block-0 > .loop-reader >
.loop-input > [ svg.loop-signals (384 <g> + 192 <set> = 576) , .loop-compute (16,311; content-visibility:hidden outside the compute) ]`.
Body-level siblings: `svg.native-signals > #run-start/#run-latched`, `.font-status > svg.native-signals > #fonts-detected/#fonts-loaded`,
`.detached-head-reader > .detached-head-state > .token-slot-1 > … > .token-slot-8 > .token-state > svg.native-signals > #token-N-{ready,ack,captured,advanced}`.

| element(s) | rules matched on every restyle of the element | declarations / cost drivers |
|---|---|---|
| `.core-controller` | 4 plain rules (`--pass`, `--loop-phase:mod()`, `--loop-held:calc()`, `--layer:mod()`, `--position:calc()`, `container-name`); **96 + 88 `:where(:has(#loop-captured/advanced-N.done))`** (`--loop-captured-pass:N` / `--pass:N+1`); **7 `:where(body:has(#token-N-advanced.done)) .core-controller`**; no animations, no transitions, 0 `var()` of size | 191 distinct `:has()` arguments: 184 walk the controller subtree (16,892), 7 walk `body` (69,521) |
| `.core-block` | `content-visibility:hidden`; **`body:has(#fonts-loaded.done):has(#run-latched.done)`** → visible | 2 arguments × 69,521 |
| `.loop-reader` | `animation-name` × **1,538** + `animation-timeline` × 1,538 (`--loop-t-b-i` view-timelines, `html{timeline-scope}` 3,181 names), duration 1 s, fill both; `--input-i:var(--x-iii)` × 768 (19 KB) | 1,538 timeline animations: unchanged in the pass-advance, 769 changed in the readback |
| `.loop-input` | `--lp-b-i:inherit` × 1,538 (F5 forward); `@container loopcontrol style(--loop-phase:P){ --loop-in-i:calc((1572864/(var(--lp-B-i)+2) − 786432)/128) × 768 ; --loop-ready ; --loop-ack }` (60 KB × 2); `@container loopcontrol style(--pass:N){ …13 readers… {--native-pass:N} }` × 96; `container-name:loopreceipt` | 768 `calc()` re-evaluated when `--loop-phase` flips; 96 style-query rules |
| `svg.loop-signals` + 384 `<g>` + 192 `<set>` | `#loop-ready-N{animation:loop-pulse 1ms both}` inside `@container loopreceipt style(--loop-ack:1){@container loopcontrol style(--pass:N){…}}` (96); **`.core-controller:where(:has(#loop-captured-N.done)) #loop-ack-N{animation:…}` (88)**; `<set attributeName="class" to="done" begin="loop-ready/ack-N.animationend+0.001s" fill="freeze">` | the 96 `#loop-ready-N` depend on the `loopcontrol` style container (forced recalc on `--pass` change); the 88 `#loop-ack-N` each re-evaluate one `:has()` argument against `.core-controller` |

Populations (R2A §2, this report's reading): **485** = `.core-controller`, `.core-block`, `.loop-reader`, `.loop-input`, `svg` + 384 `<g>` + 96 `<set>`;
**357** = `.loop-reader`, `.loop-input`, ≈354 svg elements (the 96 `#loop-ack-N` are among them).

Cost-model prediction (R2A: 5 µs/element + 40 µs/changed anim + 22 µs/unchanged anim + 218 µs/transition):

| pass | elements | anims changed / unchanged | transitions | model (ms) | measured (ms, traced) | residual (ms) |
|---|---:|---:|---:|---:|---:|---:|
| 485 pass-advance (F) | 485 | 0 / 1,538 | 0 | 2.4 + 33.8 = **36** | 223–237 | **≈ 190** |
| 357 loop readback (2nd pass of D) | 357 | 769 / 769 | 0 | 1.8 + 30.8 + 16.9 = **50** (R2A: 64 with all 1,538 changed) | 208 | **≈ 145–158** |
| per token (× 12) | | | | 1.0 s | 5.2 s | **≈ 4.1 s** |

## 2. Hypotheses and fixtures (step 2)

Fixtures reproduce the demo's shapes exactly (96 passes, 768-wide vectors, 16,311-element locked `.loop-compute`, 51,149-element locked
head sibling, 8 token slots; controller subtree 16,893 vs 16,892 in the demo) and vary one thing at a time. Harness = F4's copy of M1
`run.mjs` + a `--trigger attr` mode that replays the demo's own state changes through CDP `DOM.setAttributeValue` (no JS in the page):
warm-up = `class="done"` on `#loop-captured-k`, traced = `class="done"` on `#loop-advanced-k` (→ `:has()` → `--pass:k+1`). 3 trials, seeded.

| id | varies | tests |
|---|---|---|
| `pa-demo` | exact demo rules + fillers | the 485 pass as-is |
| `pa-nofill` / `pa-corefill` | no filler / core filler only | traversal ∝ subtree size; share of the 9 `body:has()` rules |
| `pa-fixed` | fixed-depth child-chain arguments (the proposed fix) | cost with bounded traversal; pass still advances (verify column) |
| `pa-nohas` / `pa-nohas-nosvg` | no `:has()` at all, `--pass` written inline | container fan-out floor with / without the svg |
| `svg-demo` / `svg-nohas` / `svg-plain` | inherited var on `.loop-input`; svg with / without the 88 ancestor `:has()` rules; 577 `<i>` instead of `<g>/<set>` | (a) SMIL/`<g>` per-element cost; ancestor `:has()` per `<g>` (the 357 pass) |
| `rd-change` / `rd-change-split` / `rd-change-nosvg` / `rd-change-latch` | 769 carrier widths change → snapshot re-run → reader with 1,538 anims (or 2 × 769) restyled; ± demo latch lists on the banks | (b)/(d) per-changed-timeline cost with 1,538 anims on ONE element; (c) 769-name `transition-property` list on the restyled banks |
| `rd-unrelated` / `rd-unrelated-split` | non-inherited var on the reader only | (b) restyle of an element with 1,538 unchanged timeline animations |

Predictions if H-e (`:has()` traversal) is the cause: `pa-demo` ≫ `pa-corefill` > `pa-nofill` ≈ `pa-fixed` ≈ `pa-nohas`, linear in
(arguments × subtree); `svg-demo − svg-nohas` ≈ 88 × 16.9k visits; `rd-*` and `svg-plain` at the model's 5 / 22 / 40 µs.

## 3. Measurements

### 3a. Cross-bundle evidence from existing traces (no Chromium; `R2A/frame_anatomy.py` on `bench/runs/F5`, R2A's F3a table, R2D's A/B table)

All four bundles carry the identical handshake rules (272 loop `:has()` + 7 token + 184 pulses; grep-counted). Pass-advance frame style time
(the `48x:` / `473:` / `3557:` pass; median over the layers of one token):

| bundle | `.core-controller` desc. | `body` desc. | predicted visits per pass-advance (184·C + 9·B) | population | style ms | residual vs model | ns / visit |
|---|---:|---:|---:|---:|---:|---:|---:|
| combined (tok 5) | 16,892 | 69,521 | 3.73 M | 485 | 223–237 | ≈ 190 | 51 |
| R2D ab-all (tok 2; = combined DOM) | 16,892 | 69,515 | 3.73 M | 485 | 197–217 | ≈ 170 | 46 |
| F5 (tok 5; no F2/F4, 3,072 proj leaves also in the pass) | 19,964 | 72,542 | 4.33 M | 3,557 | 275–314 (one 706) | ≈ 220–260 (incl. an unknown share of the 3,072 extra elements) | ≤ 51–60 |
| F3a (tok 5; anchor-chain core) | 27,285 | 79,863 | 5.74 M | 473 | 151–174 | ≈ 129 | **22** |

combined, R2D and F5 are consistent with ≈ 50 ns per visited element; **F3a is not** (a 1.6× larger subtree costs 0.7×). F3a's core is a
different DOM (1,926 nested `position:fixed` anchor containers instead of carrier tracks), so either the per-visit cost depends on the
elements walked (unlikely for an `#id` check) or part of combined's residual is not `:has()` — the fixtures below separate the two
(`pa-nohas-anims` keeps everything of the 485 pass except the `:has()` rules). F3a's *readback* pass is 540 ms vs 208 — the anchor-chain
bundle has its own extra cost there (not analysed here).

### 3b. Fixtures (2026-09-20 15:03–15:10, under `CHROME.lock`, AC, load1 1.5–3.6 with the user's browser open; 3 trials, medians; Chrome 153)

`R2G/fixture/results/summary.md`, `results2/` (locked carriers), `analyze.py` output. ULT = `UpdateLayoutTree` total per traced mutation
(2 passes: the mutation's pass + a 1-element follow-up); "verified" = the pass counter / property changed as in the demo.

| variant | what changes vs. the row above | ULT ms | elements | reading |
|---|---|---:|---:|---|
| `pa-nohas-nosvg` | controller/core-block/reader/input only, `--pass` inline | 2.0 | 3 | fan-out floor |
| `pa-nohas` | + svg (384 `<g>` + 192 `<set>`), 96 `#loop-ready-N` container rules | 3.1 | 292 | svg restyle ≈ 1 ms |
| `pa-nofill` | + all 272 + 9 `:has()` rules, fillers removed (0.11 M visits) | 5.1 | 381 | |
| `pa-fixed` | `:has()` with fixed-depth child chains, full fillers (0.11 M visits) | 7.8 | 381 | **the proposed rewrite: −23 ms** |
| `pa-corefill` | demo `:has()`, core filler only (3.26 M visits) | 27.0 | 381 | |
| `pa-demo` | demo `:has()`, core + head fillers (3.72 M visits) | 31.3 | 381 | **`:has()` = 28 ms = 7.5 ns/visit** (slope demo−nofill 7.3) |
| `pa-nohas-anims` | + `.loop-reader` 1,538 timeline anims + 2×769 live carriers | 12.1 | 2,125 | 1,538 unchanged anims + 1,545 carriers ≈ 9 ms |
| `pa-demo-anims` | + demo `:has()` | 43.0 | 2,126 | additive: 31 ms `:has()` |
| `pa-*-anims-locked` | carriers inside `content-visibility:hidden` (inactive timelines) | 33.9 / 3.3 | 381 / 292 | no inactive-timeline penalty |
| `svg-plain` | inherited var on `.loop-input`, 577 `<i>` children | 4.7 | 3 | |
| `svg-nohas` | 577 svg elements (`<g>`/`<set>`), no `:has()` | 5.2 | 579 | **(a) SMIL/`<g>`: +0.5 ms for 577 elements** |
| `svg-demo` | + the 88 `.core-controller:where(:has()) #loop-ack-N` rules | 13.5 | 579 | 88 ancestor arguments × 16.9k = 8.3 ms (5.6 ns/visit) |
| `rd-unrelated` / `-split` | non-inherited var on the reader: 1,538 (2×769) unchanged anims | 6.5 / 4.1 | 2 | **(b) 4 µs/anim, not 22** |
| `rd-change` | 769 carrier widths change → snapshot re-run → reader + input + svg + open compute (18.4k) | 40.5 (7.8 + 32.7) | 19,209 | **(d) 769 changed timelines + 18k-element pass ≤ 33 ms** |
| `rd-change-split` / `-nosvg` / `-latch` | 2 readers × 769 / no svg / demo 769-name `transition-property` lists on the banks | 39.3 / 44.3 / 39.5 | | **(c) latch list: 0 ms**; split: 0 ms |

Verdicts: (a) no, (b) no, (c) no, (d) no; `:has()` traversal (H-e) is real but small: **≈ 28 ms per capture/advance restyle + 8 ms per svg
restyle ≈ 36 ms/layer ≈ 0.43 s/token** (7.5 ns per visited element, i.e. Blink's flat-tree walk is ~7× cheaper than the 50 ns the
cross-bundle table assumed — which is also why F3a's 27k subtree did not stand out). The loop region's own CSS and DOM, at the demo's exact
shapes, restyle in ≤ 45 ms; **≈ 180 ms of each 485 pass and ≈ 150 ms of each 357 pass are not produced by anything inside that region.**

Two further static eliminations: the sheet has only 2,994 style rules and **none** with a universal/tag-bucket rightmost compound (string-aware
scan), so per-element rule matching is not it either; and re-reading the E→F→G→A frame sequence against the emitted CSS shows the
485 pass (F) is the **capture** (`#loop-captured-N.done` → `--loop-captured-pass:N`, `--loop-held:1` → `#loop-ack-N` pulse), whereas
`--pass+1` (the phase flip) happens in frame A's 2,934 pass — R2A's F row conflates the two. `--loop-held:1` turns the write bank's
`transition-property` from `none` back to the 769-name list on both `.loop-bank-*` while all stage gates are open; a `cap-*` family tracing
exactly that transition (demo bank rules, ablations: no `:has()`, no held rule, no anims, no banks) is queued behind B0's R2F bench —
results land in `R2G/fixture/results3/summary.md` and are appended below when available.

**Capture family (`results3/`, 16:22–16:39, load1 1.7–5.4; traced mutation = `#loop-captured-k.done`, warm-up = `#loop-advanced-(k−1).done`):**

| variant | banks + 769-name lists | `--loop-held` rule | reader anims | `:has()` | ULT ms | elements | reading |
|---|:-:|:-:|:-:|:-:|---:|---:|---|
| `cap-demo` | yes | yes | yes | demo | **37.2** | 385 | the F transition at the demo's shapes |
| `cap-nohas` | yes | yes | yes | none (inline `--loop-captured-pass`) | 5.5 | 295 | everything except `:has()` ≈ 5 ms |
| `cap-noheld` | yes | no | yes | demo | 33.9 | 91 | the held rule adds 294 forced-recalc dependents for ≈ 3 ms |
| `cap-noanims` | yes | yes | no | demo | 43.9 | 385 | (noise band 35–50) |
| `cap-nobanks` | no | no | no | demo | 31.0 | 91 | controller + signals only |
| `real-cap-nocore` | real bundle CSS (46k rules) + real DOM minus the compute subtree | | | demo | **20.9** | 111 | the real rules cost no more than the replica |

Because every hand-built replica stayed ≤ 45 ms, a second family is cut from the **real bundle** (`fixture/extract_real.py`): the actual
`.core-controller` subtree of `bundles/combined/index.html` down to the qkv gate with the `#reused-result` bank subtree spliced in (12,184
elements), every rule of `runtime.css` whose selector targets those elements with its `@container` wrappers (layer-0 blocks; 46k rules,
5.5 MB incl. all `@property`/`@keyframes`/`@font-face`), body-level fillers at the demo's sizes; `real-cap` traces the capture, `real-adv`
the advance, `real-cap-nocore` the capture with the compute subtree removed. Font note (coordinator, 2026-09-20): the deleted layer-01…10
rowbase fonts are referenced by 30 of the 283 copied `@font-face` rules but no element of the truncated page uses those families (it renders
only layer-0 qkv, `b0qkvS0` = `experiments/gpt2-block-css/qkv-rowbase-s0.woff2`, present), so nothing fetches them; all other fixtures load no
fonts at all.

**Real-bundle family (`results4/`, 16:39–16:46, load1 1.6–2.4):**

| variant | traced transition | ULT ms (median) | elements | busy ms | reading |
|---|---|---:|---:|---:|---|
| `real-cap` | capture (`#loop-captured-k.done`) | **33.6** (trial 0 = first capture: 67.8 ms / 440 el.) | 111 | 116 | real CSS + real DOM incl. banks, 1,538 loop + 2,304 qkv consumer anims live |
| `real-adv` | advance (`#loop-advanced-k.done` → `--pass+1`, phase flip) | **34.2** | 400 | 82 | includes the `.loop-input` phase-rule swap (768 calcs) and the `--native-pass` stamps |
| `real-cap-nocore` | capture, compute subtree removed | 16.0 | 111 | 24 | |

**Conclusion of step 2.** With the demo's own CSS and DOM for the whole controller region, the F (capture) and A-controller (advance)
restyles cost **34 ms**, of which ≈ 28 ms is `:has()` traversal. The demo's 223 ms for the same 485-element pass therefore comes from
state the fixture page does not carry: the rest of the 69k-element document and its ≈ 10.9 k live view-timelines / 2.5 k in-delay
transitions / 12 nested KV banks, or the per-pass fixed costs R2A measured only as self time (`UpdateLayoutTree`/`updateStyle` self ≈ 7.5 ms,
timeline servicing ≈ 6.5 ms). Note the `busy` column: in the real-bundle page each mutation costs 82–116 ms of main-thread time for a 34 ms
style pass — the remainder is animation/timeline servicing outside `UpdateLayoutTree` (3.8 k live timelines here; 10.9 k in the demo), i.e.
the per-frame bookkeeping R2A's R2 already targets. Splitting the residual further needs a full-bundle run with style/animation trace
categories (bench agent's domain; not run here per the ground rules).

## 4. Proposed emitter change (step 3)

`R2G/emitter.diff` (vs `F4/tools`): new `r2g_has_scope.py` + 3 lines in `browser_gpt2_runtime.py` at the write site. Flag `R2G_SCOPED_HAS` (default on).
It post-processes the final CSS with the final HTML in hand:

1. `.core-controller:where(:has(#loop-{captured,advanced}-N.done))` → `.core-controller:where(:has(> .core-block > .loop-reader > .loop-input > .loop-signals > #loop-…-N.done))` (272 rules, incl. the 88 `#loop-ack-N` subjects);
2. `:where(body:has(#token-N-advanced.done)) .core-controller` → `:where(body:has(> .detached-head-reader > .detached-head-state > .token-slot-1 > … > .token-slot-8 > .token-state > .native-signals > #token-N-advanced.done)) .core-controller` (7);
3. `body:has(#fonts-loaded.done):has(#run-latched.done) .core-block` → `body:has(> .font-status > .native-signals > #fonts-loaded.done):has(> .native-signals > #run-latched.done) .core-block` (1).

Every chain is derived from and checked against the emitted page (the id's ancestor path must equal the chain; counts asserted), so a DOM
change fails the build instead of emitting a handshake that never fires. Specificity is unchanged (`:where()`), so the "later pass wins"
ordering the adapter relies on is preserved. Static check on `bundles/combined`: `R2G/static-check.txt` (272 / 7 / 1 rewritten, 0 left,
+18 KB). Not applied to any bundle (R2E/R2F own the base); apply with `cp R2G/tools/r2g_has_scope.py …; patch -p1 < R2G/emitter.diff`.

Predicted effect, **measured** (§3b: 7.5 ns/visit; `pa-demo` 31.3 → `pa-fixed` 7.8 ms; `svg-demo` 13.5 → `svg-nohas` 5.2 ms): capture
restyle −23 ms, advance restyle −23 ms (frame A's controller part, same rules), svg/`#loop-ack` restyles −8 ms → **≈ −30 to −35 ms/layer ≈
−0.4 s/token traced ≈ −0.35 s untraced** (30.3 → ≈ 29.9 s/token). Small, safe (specificity unchanged, chains verified at build time),
and it composes with R1 (which removes the pulse frames but keeps the `:has()` rules unless the handshake is redesigned). It is NOT the
explanation of the 3–6× residual; see §0.

Alternatives considered: (i) move `--pass` bookkeeping onto `.loop-input` (anchor with a 16.9k subtree too — no gain); (ii) replace SMIL
`<set>` pulses with container stamps (R1 territory, larger change); (iii) put the signal svg *after* `.loop-compute` so the reverse walk
finds matches early — only helps matched arguments (≤ pass) and still walks 16k for the unmatched ones — rejected.

## 5. Method notes

- Blink `:has()` mechanics quoted from `check_pseudo_has_argument_context.cc` / `selector_checker.cc` (Chromium ≥ 105): traversal scope
  is `kFixedDepthDescendants` only when every combinator in the argument is `>`; any descendant combinator anywhere → `kSubtree`.
  Per-argument caching (`CheckPseudoHasCacheScope`) is keyed by the argument selector, so 191 distinct arguments = 191 walks. This is an
  inference from source structure, checked here by the fixtures (`pa-nofill` vs `pa-demo`, `pa-fixed`).
- No git, no edits outside `R2G/`; Chromium only via `run_fixtures.sh` under the mkdir mutex; AC power enforced by the runner.
