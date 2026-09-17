# Getting GPT-2 generation working in Chromium, without JavaScript

September 16, 2026. This is an implementation plan with explicit correctness
gates, not a claim that the complete generator is already working.

## Decision

Keep HVAR fonts for dense matrices and typed CSS for normalization, attention,
GELU, and residual arithmetic. Use native geometry for transfer and native CSS
state for storage. Build a **bounded, complete generator first**, then improve
reuse and throughput. Do not restart the SVG arithmetic search or replace the
model while the existing accurate core still lacks its runtime state loop.

The immediate optimization target is **retiring completed font timelines after
capturing their outputs**. The next functionality target is **one native token
decision through all twelve blocks and the full vocabulary head**. Neither should
wait for speculative improvements to the other.

Constraints:

- Chromium only; HTML/CSS/OpenType and, where tested, native SVG/SMIL control.
- No JavaScript, WASM, WebGPU compute, extensions, or server-side inference.
- Python may compile static weights/assets, calculate independent test oracles,
  and inspect/control tests through CDP. It may not transfer intermediate vectors
  or advance individual stages in a claimed autonomous inference run.
- CSP `script-src 'none'`, script execution disabled in every new browser test,
  and a harness that rejects Runtime/Debugger/Profiler commands.
- Fixed build-time prompt choices are acceptable input fixtures. Precomputed KV
  caches, future tokens, hidden vectors, or oracle-chosen head candidates are not
  acceptable substitutes for the corresponding parts of general inference.

## What exists, and what does not

| Component | Evidence | Integration work still required |
| --- | --- | --- |
| Twelve-block current-token core | Correct small screen; about 39.7 s warm, 46.5 s cold | Fixed 15-token Python-prefilled cache; only four calibration inputs |
| Final LayerNorm + vocabulary selection | Several native full-vocabulary head experiments | Connect live 768-dimensional output; remove fixture-specific input constants and score floors |
| Token feedback, KV storage, rendering | Working smaller-model generators in `README.md` | Port width 64/2 mechanisms to width 768 and font-driven, variable-latency execution |
| Token → embedding | TinyStories two-axis HVAR lookup and packed CSS tables | Build/test GPT-2-small's actual 50,257 × 768 table; do not reuse TinyStories weights |
| Editable prompt | Existing font BPE tokenizer and dynamic TinyStories page | Initial scope is printable ASCII and bounded prompt length; token picker is the simpler first UI |
| Producer retirement | New delayed-transition bank; four one-shot autonomous QKV retirements pass | Repeated native epochs and connected-model speed remain unproven |

The core's 39.7 s is **not seconds per generated token**. Prefill, final norm,
head, cache writes, feedback, and visible painting are excluded. The old 13 s
estimate is not a target justified by current measurements.

Head integration is a substantial task, not a one-second add-on. The broader-range
groupwise cascade reports 1.86–14.20 s for four mutations; its hard case explores
23 groups. The six-font variant repairs an independently identified scorer
failure but is not the fastest warm variant. Start from its stronger correctness
contract, then compare warm alternatives on actual outputs of this core.

## Ordered milestones and stop/go tests

### 1. Turn the storage primitive into a reusable native stage boundary

Existing pause-the-view-animation-and-delete-the-timeline failed. The new probe
instead copies output numbers into a separate bank before removing the producer.

The strongest small candidate so far is a **registered-value delayed transition**:
follow the producer while computing; enable a long, step-end transition before
retirement; subsequent producer changes preserve the captured start values;
explicitly set `transition-property:none` to capture fresh values again. The
test delay is 86,400 s: this is bounded storage, not an indefinite memory claim.

Current test status: controlled retention/restart and a second real font consumer
pass. The one-shot CSS-animation/SMIL capture/retire handshake passes all four
existing QKV states with no harness writes after navigation. Native rearming,
multi-block integration, and speedup are still open. Details are in
`value-latch/RESULTS.md`.

Implement the following handshake, driven by generation/readiness signals:

`compute → ready(epoch) → capture → capture acknowledged → retire producer`

Restart must reattach the producer while the old bank remains held, wait for the
new epoch, and only then release/update the bank. Never use a fixed model-compute
timeout. A tiny animation used to separate acknowledged style passes is different
from assuming that a matrix finishes in a specified number of milliseconds.

Acceptance gates, in order:

1. Capture all 2,304 real QKV values. Remove source timeline names, source scroller,
   and source receiver animations. Change upstream input while retired: all saved
   values and all 768 downstream HVAR outputs must remain unchanged.
2. Reattach, await readiness, release, and repeat with fresh states. Check every
   coordinate against independent matrix references, not just a checksum.
3. Make capture/retirement automatic with no CDP writes after initial input.
   Test cold fonts, reset, duplicate/stale signals, and repeated epochs. If the
   CSS-animation/SMIL bridge fails with script execution disabled, reject that
   bridge and use a tested CSS-only state gate instead.
4. Integrate one MLP and then two complete blocks. Compare live-timeline control
   versus retirement, including capture overhead and end-of-step cleanup.
5. Only promote to all twelve blocks if full-vector accuracy survives and paired
   fresh-input timing improves by at least 10% over three alternating runs.

Do not promote the old unregistered animation bank based on scalar retention:
the new composed probe found a downstream correctness failure even when reading
the bank itself appeared correct. Do not claim delayed transitions are faster
until the connected benchmark demonstrates it.

Fallback: keep the validated live-timeline core and proceed to bounded generation.
Retirement is an optimization branch, not permission to stall the functional path.

### 2. Close the single-token browser path

Connect `block 11 output → final LayerNorm → full-vocabulary head → token ID → text`.

- Use the existing block builder and production-range head assets; isolate their
  scratch variables, animation names, font settings, and anchor scopes.
- Feed all 768 live normalized coordinates. Compute range/score offsets in CSS
  or use conservative input-independent bounds; do not import a Python-computed
  per-state floor or a preselected candidate group.
- Carry the core's epoch into head completion and visible output. A stale head
  winner must never acknowledge a new core input.
- Exhausting a search-stage budget without the head's stop condition is an
  explicit “not certified” state, not a token. The 23-stage corpus maximum is not
  a guarantee for arbitrary hidden vectors. Add further native search stages or
  a correct bounded fallback before calling that case supported.
- Compare the six-font q16 scorer to the independent mathematical q16 target.
  Separately report rounded-bucket/lower-ID tie decisions versus raw-logit argmax.

First test the four existing connected states. Then use at least 32 diverse real
states, including low-margin, non-hot-group, and long-search cases. Pass only if
the browser token matches the declared numerical contract and every state finishes
without external scheduling. Measure input change → visibly painted token; report
cold font load separately. This milestone may retain the fixed prefix, but must
be labelled **cached-prefix next-token inference**, not general prompt generation.

### 3. Build actual two-token feedback and browser-owned KV

Start with one selected prompt token, zero past cache, and two generated tokens.
This is the smallest test that exposes missing feedback and cache ownership.

- Support context length one and empty prefix in the builder/reference.
- Convert the live winning token ID into GPT-2's 768 embedding coordinates and
  add the correct learned positional embedding. Verify token IDs 0, 255, 256,
  50,256, non-hot groups, and arbitrary winners; no hardcoded output shortlist.
- Each block stores its current K/V into its own cache before retiring QKV.
  The next token reads those actual stored K/V values, not fresh Python literals.
- Keep residual/input banks distinct from immutable past-cache entries. Commit
  embedding, position, cache length, and generation epoch atomically.
- Render the decoded winning piece through the existing full-vocabulary CSS
  decoder. Stop on EOS, preserve completed text on Pause, and clear state on Reset.

Acceptance: one initial native Run action, then two correct visible generated
tokens and correct per-layer cache contents with **zero subsequent CDP writes**.
Change the initial prompt and repeat. Perturb a cached value in a separate
diagnostic to prove the next result really depends on browser-owned history.

Prefer a two-step predeclared graph as the correctness fallback if reuse is not
ready. It is finite and potentially memory-heavy, but genuine inference. Share
font assets and keep DOM nesting below the parser limit. Do not present its
throughput/memory as that of a reusable recurrent core.

### 4. Scale the state loop without copying the whole cache every token

First prefill up to four prompt tokens in the browser; then generate eight tokens
with a small declared context. Advance to a 16-token context only after memory,
reset, and repeated-epoch tests pass.

A 16-position cache has `12 × 16 × 2 × 768 = 294,912` scalar K/V values. Naively
double-buffering the entire cache creates 589,824 bank entries before other state.
Avoid the old execute/store scheme's full-cache copy on every token.

Use block-local, write-once cache slots for the initial bounded stream. A ring
buffer can later overwrite only the chosen slot: 18,432 new K/V values per token
across all layers. Read and write phases must not expose partially updated slots.
Measure the actual style/inheritance footprint; scalar counts are not byte estimates.

Declare the context policy. A 16-token rolling cache with increasing absolute
positions is not the checkpoint's unrestricted 1,024-token context. Test the first
eviction and position lookup; stop visibly at the supported positional limit rather
than silently clamping/repeating positions. Verify Pause/Resume/Reset/EOS mid-run.

Only then connect the existing editable ASCII tokenizer. A native token picker
keeps tokenizer uncertainty out of the initial inference tests. Do not promise
arbitrary Unicode or unlimited output from a finite predeclared graph.

### 5. Optimize the complete generator, with numerical guardrails

Priority from the current profile:

1. Timeline lifetime and stage scheduling: about 30% animation servicing and 27%
   paint/compositing preparation in the traced core. These are targets, not a
   guaranteed removable 57%.
2. FC/GELU, QKV, and MLP projection: 45%, 23%, and 16% of isolated stage work.
   Re-test shared FC easing only after fixing lifecycle overhead: it saved about
   37% locally but did not meaningfully improve the full twelve-block run.
3. Full head's hard search tail and native cache/feedback cost, measured after
   integration. Keep head and core optimization decisions separate.
4. Softmax/LN last: attention mixing was only 3.6% of isolated work. The existing
   typed-CSS attention is the current baseline, not flexbox for every operation.

Expand beyond the four calibration states before approving further quantization.
Evaluate at least 128 teacher-forced positions from held-out prompts and 16
free-running continuations. Maintain two references: original checkpoint float
and the explicitly represented quantized/ranged browser model. Record where
quantization changes a token separately from browser implementation error.

Replace fixture-fitted activation ranges with measured-independent bounds or
native per-stage scaling. Add visible range/overflow guards; silently clipping
unseen prompts is not acceptable. LayerNorm's pre-affine coordinates admit the
bound `abs(z_i) <= sqrt(767)` for width 768, but the learned affine factors,
residuals, later maps, and geometry offsets still require their own analysis.
Do not assume the current four-state easing range is general.

Benchmark one Chromium instance at a time, with fresh inputs and alternating
control/candidate order. Report median/p95, cold load, prefill, first visible token,
subsequent visible tokens, font bytes, renderer memory, and numerical failures.
Keep the low-volume exclusive trace analysis; do not add inclusive nested event
times or extrapolate a token time by summing isolated matrix microbenchmarks.

## Deliverable definition

A static browser page that accepts a declared supported prompt, performs its own
prefill, emits at least eight live greedy tokens through all twelve GPT-2-small
blocks and the full vocabulary head, maintains its own declared-size KV cache,
and supports Run/Pause/Reset/EOS without script execution or external intermediate
transfer. Numerical approximation, input/context limits, and measured speed are
visible and documented. No latency is promised before that page is measured.

## Reproduction and source map

Core baseline/profile: `RESULTS.md`, `tools/build_hybrid_twelve_block.py`,
`tools/profile_hybrid_twelve_block.py`, `tools/analyze_hybrid_profile.py`.

New storage tests:

```sh
uv run -q --with pillow --with numpy --with fonttools --with brotli \
  python tools/probe_native_value_latch.py
```

Run from the repository root. Outputs are under
`experiments/hybrid-12block-profile/value-latch/`. Controlled diagnostic phases
are explicitly distinguished from the attempted autonomous-retirement fixture.

Relevant existing implementations:

- `tools/build_tinystories_recurrent.py`: block-local K/V calculations and old banks.
- `tools/build_tinystories_nested.py`: finite native handoff/streaming fallback.
- `tools/build_tinystories_dynamic.py`: input/decoder/EOS/reset patterns.
- `tools/build_hvar_token_embedding_lookup.py`: smaller-model lookup prototype.
- `tools/build_gpt2_groupwise_production_q16_sixfont.py`: broader-range head integration.
- `experiments/gpt2-groupwise-cauchy-blockflow-production-range/RESULTS.md` and
  its `-q16-sixfont` counterpart: head correctness/range/timing limitations.

Older experiments sometimes used JavaScript measurement harnesses. They are
historical evidence only; new acceptance tests must use the Python/CDP harness.
