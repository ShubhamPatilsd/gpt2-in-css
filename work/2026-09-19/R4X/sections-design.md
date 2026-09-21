### 6.1 Scores hop through `1ch` (the one primitive application the catalog does not contain)

Today (emitter `browser_gpt2_font_vector_cache.py:238-330`): per layer 96 `<i class="metric fvs-score-H-S">` carriers, each
`font: 512px FvsDot; font-variation-settings: var(--fr-k-S-H), var(--fvs-query-H)` (one distinct font *instance* per
(H,S)), width = `calc-size(max-content, …)` scaled by `--fqs-H · --fr-ks-S-H`, `view-timeline: --fvs-score-H-S inline`;
`.fvs-score-reader` carries 96 animations + 1 stamp animation, decodes `--fs-H-S`, runs the softmax on the same element,
then `--fe-H-S` inherit into the V glyph rows. The hop costs 97 timelines (97 × 10.7 µs × 46 frames ≈ 48 ms/token of
servicing + 97 × 40 µs × 12 changed-animation applications ≈ 47 ms/token), one `ScrollTimeline` re-snapshot pass per layer
(the second style pass of frame `0 126 6919`, R3A §1c) and the stamp/receipt/gate trio.

Sketch (no model change, fonts rebuilt by the tools copy, same axes and codes):

1. **Font**: in each `FvsDot` font (one per layer/head pair or the shared one, as built today) add a cmap entry
   `U+0030 → FvsDot_H` (the '0' glyph *is* the dot glyph; today the glyph sits at `CODEPOINT_BASE`). HVAR unchanged.
   `1ch` on an element whose primary font is that instance is then the bilinear score advance in px, at style time.
2. **Producer elements**: replace the 96 in-flow carriers by 12 chains of 8 nested `display:block` empty elements
   `.fvs-score-H-S` with today's `font` and `font-variation-settings` declarations plus
   `--fs-H-S: calc((1ch / 1px - base_px) * var(--fqs-H) * var(--fr-ks-S-H) * k_H)` (the same decode as the width
   expression, minus the `calc-size` offset/viewport terms). `--fs-*` registered `<number>`, `inherits: true` (today
   `inherits: false`) so the 8 slot values reach the chain bottom; the chain bottom is `.fvs-softmax` (today's softmax
   block moves from the reader to here). No `.scroller/.track`, no `view-timeline`, no `timeline-scope` entries, no
   `@keyframes`, no reader/receipt/gate for this hop: the softmax is now a *style dependency* of the same pass that sets
   the score FVS.
3. **Ordering**: `--fs` on the slot element resolves `1ch` against its **own** font (custom properties use the element's
   font; `font-variation-settings` uses the parent's — E1 #70), so the slot's FVS must not itself depend on `--fs` (it
   does not: it depends on `--fr-k-*` and `--fvs-query-H`).
4. **Gate**: the `fvsscore` stamp is not needed — the V rows depend on `--fe-*` directly; the existing
   `--fvs-value-epoch` container-style gate keeps working because `--fe` now updates in the same pass as the query.

Expected effect: −97 timelines/animations per layer (−1,164 of the ≈10.9k live timelines), no separate second style pass
for the scores (the `6919` V-row pass merges into the `126` pass), no `ScrollTimeline` re-snapshot for it. Precision: the
`ch` channel is the shaped advance in float px (§5 measures it against the timeline decode); the 6-digit `var()`
substitution applies to both paths at the softmax. Cost per value: §5. Risk: the chain adds 8 × 12 = 96 extra font
instantiations? No — the 96 (H,S) instances exist today (each carrier has a distinct FVS); the elements merely move.
The bottom element sees 8 inherited numbers; the score reader today inherits nothing from the carriers, so the V rows'
declaration sets are unchanged.

### 6.2 qkv / fc hops — no new primitive; what the inventory says

For a 768-in / 2,304- or 3,072-out hop every channel in §1 has been costed:

| channel | values per unit | units needed for fc (3,072 out) | frameless? | measured cost | who costed it |
|---|---|---|---|---|---|
| view-timeline (today) | 1 | 3,073 timelines | no (+1 frame, +1 pass, +1 layout) | ≈ 560 µs/value/token (40 changed + 28 pending add + 46 × 10.7 servicing) | R3A §1b–2 |
| container chain | 2 | 12 chains × 128 fixed containers | **yes** | 19 µs/value synthetic, ≈ 100 µs/value in the real MLP page, 1 frame per MLP instead of 3 | F3 §2, §3b |
| font metric units | 5 | 615 instances × 3 input shards | yes | ≈ 1.2 ms/value (instance creation ≈ 1–2 ms at 128–256 axes), 2.8 GB RSS | `hvar-five-metric-scale` |
| `opsz` / `font-size` | 1 axis per element | needs the container graph anyway | yes | = container graph | E4 #292 |

So for qkv/fc the only frameless design remains F3's anchor → `position:fixed` size-container chain; nothing enumerated
here adds a channel with > 2 values per element or removes the depth-128 chain. The one thing that would have changed
this — a named-container readback (`container-progress(width of --name)`) or `anchor-size()` accepted in a custom
property — «does-not-exist». R4X therefore hands the qkv/fc hops back to the F3 line unchanged and recommends spending
the fixture budget on §6.1 (scores) and the LN-statistics/small hops where channel 2 is instance-neutral.
