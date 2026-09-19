# R2E design — hop-gated view-timeline animations (design report BEFORE building, as requested)

Agent R2C→R2E, 2026-09-19 03:0x. Base: `work/2026-09-19/R2C/tools` (= F4 tools + R2C hoist; the hoist is flag-off-able and irrelevant here).
Sources read: R2A.md §0, §1, §5, §6; `probe_native_reused_loop.py:15-118` (loop banks, reader, phase rules, handshake);
`browser_gpt2_reused_core.py:130-400` (stage gates, bridge, final export); `browser_gpt2_reused_adapter.py:47, 72-90`;
`browser_gpt2_runtime.py:336-372` (head-input latch); `build_hybrid_twelve_block.py:106-257` (carriers + consumer animations);
`bundles/combined/index.html` (carrier census); F4.md §2.1; C2 §2.

## 0. Verdict

**Hop-gating as specified is not semantics-preserving, and even where it were, its toggling cost is of the same order as its saving.**
The premise "only one hop's carriers change per frame" is true of *activity* but liveness is a *dependency* property: every hop's
animated outputs are read live through `var()` by all downstream hops until the loop-bank latch at the `--loop-phase` flip
(frame F), so detaching any compute-chain timeline before frame F zeroes `--out` before it is latched. The only variant that
could preserve values is pause-and-hold (§4), whose net is ≤ −3 s/token (not −6 to −7) and hinges on one Blink behaviour a
fixture must confirm first. I have NOT built the 2-layer smoke bundle; I request a go/no-go on §4/§5.

## 1. Census of the 10,858 view-timelines (`index.html`, inline `view-timeline:` per carrier)

| carriers (timelines) | count | animations reading them | values produced | consumed by (live `var()` chain) | latched by |
|---|---:|---|---|---|---|
| `i.metric` qkv | 2,304 | `.shared-qkv-c0..4` (2,304) | `--qkv-*` | `.fvs-query` (`--fqs`, `--fq-q`/`--fvn`, live K/V lists), score glyphs (frame B) | K/V lists only: bank write rule un-match at the NEXT layer (F4 §2.1) |
| `i.metric.fvs-score-H-S` (+stamp) | 97 | `.fvs-score-reader` (96) | `--fe-H-S`, `--fb-H`, `--fw-H-S` | V glyph weights (`"P000" var(--fw)`), frame B | nothing |
| `span.fvs-value-row` | 768 | `.cache-bridge-c0/c1` (768) | `--ctx-*` | `.shared-attn` list (frame C) | nothing |
| `i.metric` attn | 768 | `.shared-attn-c0/c1` | `--r-i = x + attn` | `.shared-ln2` → `--n2` → `.shared-fc` list; `--out-i = r + proj` (frame D) | nothing |
| `i.metric` fc | 3,072 | `.shared-fc-c0..5` (3,072 + inline GELU) | `--hidden-*` | `.shared-proj` list (frame C/D) | nothing |
| `i.metric` proj | 768 | `.shared-proj-c0/c1` | `--out-*` → `.reused-output{--loop-out}` | write bank `--saved-b-i:var(--loop-out-i)` (live while `--loop-phase:b`) | **phase flip** (frame F): write rule un-matches → 769 × 86,400 s transitions hold |
| `i.loop-metric` (2 banks) | 1,538 | `.loop-reader` (1,538; `selective=False`, all attached) | `--lp-b-i` → `--loop-in-i` (read bank) | `.core-reset{--x-i:var(--loop-in-i)}` → the whole next layer (A–F) | the bank's own transitions (the carrier WIDTH is the held value) |
| `i.embedding-metric` (+epoch) | 769 | `.embedding-consumer-*` (768) | `--embed-*` → `.position-embedding{--x-i}` (d10, 90k descendants) → `--input-i` → `--loop-in-i:var(--initial-i)` at `--pass:1` | layer 0, frames A–F of pass 1 | nothing (live until the pass-1 phase flip) |
| `i.metric` b11-bridge (+stamp) | 769 | `.b11-bridge-c0/c1` | `--final-h-*` → `--hq`/`--head-fvs` | head frame | head bank: `transition-property:none` while `--bridge-ready:1`, holds when it drops. **Already `display:none` except at layer 11** (`adapter.py:90`) → no ComputedStyle → no timeline object outside layer 11 (consistent with the trace's ≈10 k serviced timelines vs 10,858 in HTML) |
| feedback | 32 | `.feedback-reader` | `--feedback-N` → `--token` | token frame | `--frozen-prompt` / slot latches |
| 5 stage `pass-reader` stamps | 5 | receipts | `--gate-kind` | gates | — |

Within a layer, frames A–D each need their own hop live AND every upstream hop of the same layer still live (B needs qkv; C needs
qkv+scores+V+ctx; D needs all of them plus attn+fc). Nothing between qkv and `--out` is latched: **all 7,782 compute timelines are
needed from frame A through frame F of every layer** (6 of the 7 frames/layer). The 1,538 loop timelines are needed D→F (write bank,
live) and A→F of the next layer (read bank). Only the embedding (768, needed in pass 1 only) and feedback (32) are idle for most of the
token; the b11 bridge is already detached by `display:none`.

## 2. Why a detached timeline loses the value (the semantic blocker)

css-animations-2 / web-animations-2: a CSS animation whose `animation-timeline` names a timeline that does not resolve (carrier
`view-timeline: none`, or the consumer's `animation-timeline: none`) gets an inactive/null timeline → current time unresolved → the
effect is not in effect → the animated registered `<number>` reverts to its base value (0 / `initial`). Blink follows this
(`Animation::CurrentTimeInternal`: unresolved when the timeline is inactive unless a hold time is set). `animation: none` removes the
animation outright — same result. So "detach after the hop's frame" = "set that hop's outputs to 0 for the rest of the layer", which
propagates through every downstream `var()` and reaches `--saved` before frame F. The predicted −6 to −7 s assumed the values survive
detachment; they do not.

A second, cheaper-looking route also fails: gating the *consumers'* animations via the existing stage gates (`.{stem}-gate{display:none}`)
does not remove the TIMELINES (they live on the carriers outside the gates), and R2A §1 attributes the per-frame cost to timeline
servicing/snapshot validation (per `ScrollSnapshotClient`), not to animations.

## 3. Cost model of toggling (even if values were preserved)

- Saving: ≈11 µs × (timelines off) × (frames off) — R2A §1/§0.1 (F3a: −3,842 timelines → −46 ms per empty frame).
- Cost per timeline per on/off cycle: re-creating the `ViewTimeline` + `Animation::setTimeline` → `PendingAnimations` add
  (26.7 µs measured per pending add, R2A §0.2) + the carrier's own restyle to flip `view-timeline` (≈5–40 µs) + the consumer's
  animation update on detach (another pending update) ≈ 60–100 µs per cycle.
- Break-even: ≈6–9 frames off per cycle. A layer has 7 frames; the compute timelines are needed in 6 of them. **Negative for every
  compute population even with perfect semantics** (e.g. fc: 3,072 × 11 µs × 1 frame = 34 ms saved vs ≥ 180 ms of toggling per layer).

| population | timelines | frames off / layer (max) | gross saving / token | toggle cost / token | net |
|---|---:|---:|---:|---:|---:|
| qkv / scores+V / attn / fc / proj | 7,782 | 1 (frame G only) | 12 × 7,782 × 11 µs × 1 ≈ 1.0 s | 12 × 7,782 × 60–100 µs ≈ 5.6–9.3 s | **+4.6 to +8.3 s (worse)** |
| loop banks (write bank idle A–C, read bank never) | 769 | 3 | 12 × 769 × 11 × 3 ≈ 0.30 s | 12 × 769 × 60–100 µs ≈ 0.55–0.9 s | worse |
| embedding | 768 | 78 of 85 frames/token (passes 2–12) | 768 × 11 µs × 78 ≈ 0.66 s | 1 cycle/token ≈ 50–80 ms | **−0.6 s** — but see §5 (its detachment changes `--x-i` on `.position-embedding`, a 90k-descendant inherited write = +2 whole-DOM passes ≈ +1.3 s) |
| feedback | 32 | ~80 | 0.03 s | ~0 | −0.03 s |
| b11 bridge | 768 | already off | 0 | — | 0 |

## 4. The only viable variant: pause-and-hold (needs a fixture answer before any bundle)

Web Animations: an animation's hold time takes precedence over its timeline. If Blink keeps the hold time of a **paused** CSS
animation when its named view-timeline disappears (spec "setting the timeline of an animation" preserves progress for paused
animations; Blink's `CSSAnimations::CalculateAnimationUpdate` → `Animation::setTimeline(nullptr)` path — unverified), then:
consumers get `animation-play-state: paused` and their carriers `view-timeline: none !important` once the layer's `--out` is latched
(frame F, keyed on the existing `--loop-phase` / `--pass` container stamps), and `running` + timelines restored at the next layer's frame
A (`--loop-ready`). Values would then survive the F→A window. Gross: 7,782 × 11 µs × ≤2 frames ≈ 0.17 s/layer ≈ 2 s/token; toggling
(pause + un-pause + re-attach ≈ 3 pending updates × 26.7 µs × 8.5 k animations ≈ 0.7 s/layer) **exceeds it**. Per-hop pausing inside the
layer (hold qkv after B, ctx/scores after C, …) would raise the gross to ≈0.72 s/layer (8.6 s/token) but the toggling to ≈0.46–0.7 s/layer,
so the best case is ≈ −0.25 s/layer ≈ **−3 s/token**, conditional on three unknowns:
(1) hold time survives timeline removal for CSS animations (else values zero → correctness failure);
(2) un-pause + re-attach delivers the NEW value in the same frame as the carrier width change (else +1 frame per hop ≈ +105 ms, more than
    the hop saves);
(3) the pause/play toggle costs ≈ the 26.7 µs pending-add figure and not more (the figure was measured for timeline-moved re-queues).
Fixture (one Chrome slot, ≈15 min, under `CHROME.lock`): a 1,024-carrier page (F5/F4 latch-harness pattern), arms: live / detached /
paused+detached / paused+detached then re-attached; read back the consumer's registered numbers after each mutation and record
`serviceAnimations` calls, animate ms and `PendingAnimations` adds per frame from a light trace.

## 5. Recommendation

- **Do not build R2E as specified**; the mechanism cannot preserve values and its toggling costs exceed its savings (§1–§3).
- If a conditional −3 s/token is worth it, approve the §4 fixture (I can run it next; it needs no emitter change). If the fixture answers
  (1)–(3) favourably, R2E becomes "per-hop pause-and-hold keyed on the stage gate stamps", predicted ≈ −2 to −3 s/token, 2-layer smoke first.
- Otherwise the per-frame timeline cost is attackable only by **fewer frames** (R2A R1: the 24 E/G pulse-end frames, −2.5 s; folding F
  into D, −1 s) or a **different transport** for the largest population (fc, 3,072 timelines) that does not re-lay out a deep container
  chain (F3's failure mode). R2A's R3 (harness mouse off the page, −1.0 s) and R4 (`overflow:clip`, −1.5 to −2.5 s) remain the cheapest
  safe wins.
- Embedding-only gating (768 timelines, −0.6 s gross) is not worth it either: `--embed-*` → `.position-embedding{--x-i}` is an inherited
  write at depth 10 (90k descendants); detaching/re-attaching once per token would add two whole-DOM passes (≈ +1.3 s) unless the
  embedding consumers are ALSO pause-held — the same unknown (1).

Status of R2C: bundle built and offline-verified; Chrome correctness run in progress under the lock (started 03:03 after a 675 s wait).
Per the pivot message, READY will be created on 8/8 (var()/calc counts on the consumer lists did drop: 768/0 vs 1,536/768 per stage
list, 64 calc parses removed per score glyph), with the honest note that it cannot move the token (R2A R7, my §1.4 in R2C.md).

## 6. Pause-and-hold fixture — results and verdict (2026-09-20 13:26–13:35, coordinator-approved run)

Harness: `R2C/hold/{gen_hold.py,run_hold.mjs,run_hold.sh,analyze.py}`, results `R2C/hold/results/{hold.jsonl,summary.md,trace-*.json.gz}`.
Chrome 153.0.8010.48 headless, AC, caffeinate, under `CHROME.lock` (waited 3,795 s; touched every 30 s), load 2.5 → 2.0 during the run
(the contended-machine condition had passed), no other headless Chrome. Page = the demo's shapes: `.stage{timeline-scope}` > `.scroller`
(fixed, overflow:scroll, 524,288 px) > `.track` > 1,024 `i.metric` with inline `width:calc(262144px + (i + var(--in)) * 128px); view-timeline:--t{i} inline`,
sibling `.consumer` with 1,024 view-timeline animations (`animation-range:cover`, fill both) publishing registered `--o-i = (524288/var(--p-i) − 524288 − 262144)/128`
(= i + in); a 1 s infinite custom-property animation forces a main-thread frame per vsync (60/s) so idle windows measure per-frame cost;
control page with 0 carriers. 2 trials × 16 states; states set by CDP attribute writes (no JS). Value check = computed `--o-*` on the consumer.
Caveat: the tick animation defeats the harness's quiescence detector (RecalcStyleCount changes every frame), so every step ran to the 30 s
cap and the `mutateMs` cycle numbers in `summary.md` are invalid; cycle costs below come from the traces (the mutation frame's
`UpdateLayoutTree`, 1,024–1,028 elements).

### (1) Hold semantics — FAIL for every form that removes the timeline cost

| state (after `animation-play-state:paused` holding i+7 / i+21 / i+33) | consumer values read back | verdict |
|---|---|---|
| paused, timeline attached; then input `--in` changes 7→13 | held at i+7 (sample 6.99984 / 519.001 / 1030), 2/2 trials | pause holds and isolates from input ✓ |
| paused + subjects `view-timeline:none !important` | **all 1,024 → −2048** (= progress forced to 100 %, `--p`=1) | value LOST ✗ |
| paused + `.scroller{display:none}` | **all → −2048** | value LOST ✗ |
| paused + `.scroller{content-visibility:hidden}` | held (33.0006 / 544.996 / 1056), 2/2 | holds ✓ — but the timelines stay alive (see (2)): no saving |
| `view-timeline:none` without pause (control) | `--p` unresolved → 1/0 → 1.79769e308 | value LOST (as predicted in §2) |
| `display:none` without pause (control) | 1.79769e308 | value LOST |

Blink does not carry a paused scroll-driven CSS animation's hold time across the loss of its named view-timeline: the animation is
re-created against a null timeline and lands at its end value (fill both), not at the held progress. Only a display lock keeps the
subject's frozen geometry (and therefore the value) — and keeps the ScrollSnapshotClient.

### (2) Per-frame servicing cost (idle windows, 120 frames each; base frame with 0 carriers = 0.24 ms)

| state | ms/frame (1,024 carriers) | µs per carrier per frame |
|---|---:|---:|
| live (timeline + running animation) — fresh page, first state | 2.2 (trial 0) / 4.2 (trial 1) | 1.9 / 3.9 |
| live after any pause cycle | 4.0–4.3 | 3.7 |
| paused, timeline attached | 4.2 | 3.9 |
| paused + `view-timeline:none` | 2.0–2.5 | 2.0 |
| paused + `display:none` | 1.9–3.1 | 2.2 |
| paused + `content-visibility:hidden` | 4.2–4.8 | 4.1 |
| detached (`view-timeline:none`), not paused | 2.2–3.0 | 2.3 |
| `display:none`, not paused | 2.2–3.4 | 2.5 |

`AnimationTimeline::serviceAnimations`: 2,045 calls per frame for 1,024 live timelines (once in the animate step, once in the tick's style
pass — R2A's pattern). Removing the timelines while the animations remain (paused or not) saves only ≈1.7 µs per carrier per frame; the
remaining ≈2 µs is the Animation objects themselves. The demo's 11 µs/timeline/frame (R2A §1) is NOT reproduced by this shallow fixture
(carriers at depth 5 vs 20–47 in the demo, one style pass per frame vs two): the fixture bounds the timeline share at ≈1.7–2 µs and leaves
the rest of the demo's per-frame cost unattributed to timelines.

### (3) Cycle cost (mutation frame `UpdateLayoutTree`, 1,024 carriers, from traces)

| transition | style ms | per carrier |
|---|---:|---:|
| ordinary input change while live (`--in` 0→7) | 3.4 | 3.3 µs |
| resume + re-attach from paused+detached (`pd-none` / `pd-display` / `pd-cv` → live, new input) | 50.1 / 50.5 / 41.9 | **≈46 µs extra** |
| re-attach from detached, not paused (`d-none` / `d-display` → live) | 8.8 / 8.4 | ≈5 µs extra |
| pause / detach steps | untraced (assumed ≥ the un-pause's ≈46 µs; the pause is the same play-state flip) | ≥ 5–46 µs |

Off/on cycle per carrier ≈ 50–95 µs; per-frame saving live → paused-detached ≈ 1.7 µs ⇒ **break-even ≈ 30–55 frames off per cycle**.
The demo offers 1–3 frames per layer for compute carriers and 78 per token for token-level carriers.

### Predicted demo effect (7,782 compute timelines needed 6 of 7 frames; 1,570 token-level carriers)

| variant | saving (fixture 1.7 µs/frame) | saving if the demo's 11 µs/frame held | toggling cost | net |
|---|---:|---:|---:|---|
| compute, off 1–3 frames/layer, 12 cycles/token | 0.16–0.48 s | 1.0–3.1 s | 7,782 × 12 × 50–95 µs = 4.7–8.9 s | **+4 to +9 s/token (worse)** even at 11 µs |
| token-level 1,570, off 78 frames, 1 cycle/token | 0.21 s | 1.35 s | 0.08–0.15 s | −0.1 s (fixture) to −1.2 s (11 µs) — but the values do not survive (1) except under `content-visibility:hidden`, which saves nothing |

### Verdict: NO-GO for R2E in every form

(1) fails (values lost on timeline removal; only a display lock holds, and it keeps the cost); (2) the timeline share of the per-frame cost
is ≈1.7–2 µs per carrier here, not 11; (3) re-attaching a paused hop costs ≈46 µs/carrier in style alone, break-even ≈30–55 frames vs
1–3 available. No emitter design (§2 of this file) is written. The per-frame cost the demo pays is better attacked by fewer frames
(R2A R1: E/G pulse frames, F folded into D) and by finding what the deep-DOM demo pays per timeline that this fixture does not
(depth of the snapshot geometry walk; two style passes per frame) — a follow-up fixture with carriers at depth 40 would settle whether
"11 µs per timeline" is geometry or bookkeeping.
