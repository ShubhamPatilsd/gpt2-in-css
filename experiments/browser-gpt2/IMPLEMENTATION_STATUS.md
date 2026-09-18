# Browser GPT-2 implementation: bounded deliverable complete

The native twelve-block loop completes eight tokens. The final served-page run
took 662.495 seconds including loading and the initial Run click; subsequent
tokens had a 77.956-second median interval. See `README.md` and `RESULTS.md`.
This is a bounded one-token-input / eight-output prototype, not unrestricted
GPT-2 input, context, or broad held-out model certification.

## Validated this implementation pass

- Bounded epoch-specific CSS/SMIL signals can capture/release fresh inputs through
  real one- and two-block networks. All four tested states retain the existing
  numerical results. Implementation: `tools/native_stage_retirement.py`, optional
  `--retire-stages` / `--retire-blocks` in `build_hybrid_twelve_block.py`.
- Neither retirement topology passes the performance promotion gate. Current
  matched small runs: normal two-block median 2.154 s, every-matrix retirement
  12.295 s, whole-block retirement 6.261 s. Retain the normal core. These are
  three fresh-input samples, not complete-token timings.
- GPT-2-small's full 50,257 × 768 embedding lookup font has been built from the
  actual checkpoint. WOFF2 is 56,853,724 bytes. All 16 browser fixtures pass
  (maximum coordinate error approximately 0.000135).
- A full-vocabulary q16 head is built with 16-way geometry reduction trees,
  reusing the six existing bounded font assets. It removes the old failed
  197-way outer maximum and avoids an incomplete search-stage budget. A fixed
  analytical LayerNorm score floor replaces per-fixture oracle floors. Browser
  correctness screen passes all 38 difficult fixtures. The promoted two-pass
  decoder keeps large scores integral and selects local token identity using
  widths no larger than 256 px; the direct fractional-identity decoder is retained
  only as an experiment. Two-pass warm head-only times were 2.45–3.62 s.
- Four sequential inputs through the two-block native K/V core pass the numerical
  screen. Previously stored K/V vectors are bit-for-bit unchanged on readback.
- A small native feedback fixture advances four times with no post-navigation
  writes. The integrated two-block model also completes four native iterations.
- Both nested and flat cache versions complete eight tokens. The flat version's
  147,456 K/V coordinate readbacks, final residual, and final hidden vector are
  identical to the nested baseline. All eight decisions match both numerical
  references, including the original unquantized checkpoint reference.
- Native Pause/Resume, prompt locking, form Reset, and EOS stopping pass their
  control tests. A blocked-font test keeps the readiness gate closed.
- The real twelve-block page generated two correct tokens during 180 seconds
  without any DOM/style/layout observations after the initial Run click.

## Implementation direction for the recurrent bounded runtime

Keep one twelve-block core; do not duplicate it eight times. Keep independent
stage properties between sibling blocks and pass residuals through the existing
native bridges. Do not retire every matrix just for speed.

Place write-once K/V slot banks between each layer's QKV and attention mix.
Each slot follows that layer's current QKV in its own epoch, then uses registered
delayed transitions to retain those values across later epochs. Attention reads
only valid past slots plus live current K/V. Slot variable names can be reused
across sibling layers; storage lives on distinct elements. Do not copy the full
cache every token. Start with a bounded one-token prompt and eight generated
tokens, so no eviction is needed within the declared small context.

Use eight native output-token storage slots after the head. Earlier slots freeze
as the epoch advances. A handful of globally scoped view timelines carry their
token IDs back to the initial embedding lookup. The current epoch chooses the
previous stored winner (or native prompt picker for epoch one). No external vector
transfer or per-stage scheduler is permitted.

Keep the head's last completed input held while the core calculates a new epoch;
the head/token feedback sources must remain live. Release the head input bank
only after the final residual's current-epoch receipt. Propagate epoch alongside
the head's geometry reductions so old winners cannot acknowledge a new token.
Head completion triggers a native store acknowledgement, then the next epoch.
Predeclare the finite control signals; Reset reloads/recreates their state.

The native font-readiness barrier now uses known default-axis advances and a
bounded geometry reduction over all 259 faces. It opens the causal graph through
a CSS-animation/SMIL event handshake, with no external font-ready callback.

All new measurements use Python/CDP only, CSP prohibits scripts, and Chromium
script execution is disabled. Initial input mutations in component tests are
diagnostics, not claimed autonomous generation. The delivered-page benchmark
uses one initial native Run click and no subsequent writes. Its lightweight
geometry observer avoids enumerating inherited property maps while the core is
still calculating. Phase percentages are coarse observed intervals, not exact
exclusive CPU attribution.
