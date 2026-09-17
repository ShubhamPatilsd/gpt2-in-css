# Native value capture and producer retirement

September 16, 2026. Chrome 153.0.8010.48. No JavaScript in page or harness;
`Emulation.setScriptExecutionDisabled` enabled and CSP `script-src 'none'`.

## Result

**A separate delayed-transition bank can retain real HVAR outputs after their
producing timelines are removed, and a subsequent real HVAR matrix can consume
those retained values. A one-shot native capture/retire handshake passes all
four existing QKV input fixtures.**

This removes a previously unproven prerequisite for a timeline-lifetime
optimization. It does **not** demonstrate a twelve-block speedup, a reusable
recurrent scheduler, or completed GPT-2 text generation.

## Storage controls

The scalar control changes 17.125 to 89.0625 while held, then resumes.

| Mechanism | Scalar | Composed real-font test |
| --- | --- | --- |
| Paused registered-property animation | Does not retain the old value | Rejected at scalar gate |
| Filled, completed registered-property animation | Does not retain the old value | Rejected at scalar gate |
| Paused unregistered animation bank, like older recurrent pages | Retains/resumes scalar | Invalid initial vector and downstream result; rejected in this topology |
| Delayed transition on registered values | Retains/resumes scalar | Passes capture, detach, fresh-input isolation, and restart |

The delayed-transition bank follows source values with
`transition-property:none`. Hold enables a step-end transition with a one-day
delay. When source values subsequently change/disappear, the bank keeps the old
start values. Explicitly restoring `transition-property:none` releases storage.
This is a bounded hold, not an indefinite-memory guarantee.

The real test copies all 2,304 block-0 QKV outputs. A second real GPT-2
768→768 attention-output font matrix consumes captured Q divided by 64 with zero
residual. This second matrix deliberately tests transport; Q→output projection
is not presented as the full attention calculation.

In the delayed-transition fixture:

- Initial captured values exactly match the live QKV values exposed by CDP.
- Hold, detach, changing input while detached, and reattaching while held each
  preserve all 2,304 captured coordinates and all 768 downstream outputs with
  **zero observed difference** from their respective pre-retirement values.
- Reattach while still held, wait for the new source, then release: QKV RMSE
  0.0002118, maximum error 0.0010100 against the independent quantized matrix.
  Downstream RMSE 0.0003712, maximum error 0.0024951 against its independent
  quantized matrix, evaluated on the actually captured Q vector.
- Releasing the bank changes the downstream output (maximum change 0.374),
  excluding an accidentally constant downstream circuit.

These manual phases use Python/CDP attribute changes as diagnostic controls.
No output vector is copied back into the page. They are not an automatic scheduler.

## Automatic one-shot handoff

The automatic fixture performs:

`current-epoch QKV receipt → CSS animationend → SVG hold signal →`
`CSS hold-ack animationend → SVG retire signal → producer removal`

Each tiny CSS handshake animation is 1 ms. Each SVG event bridge uses a 1 ms
positive offset to defer the event. The initial zero-offset attempt did not
activate the hold signal; adding positive event deferral passed. This is an
observed behavior on this Chromium build, not a general explanation of the engine.
No guessed matrix-computation delay controls readiness.

After navigation, the automatic harness only observes. It performs zero DOM
input/control writes. It verifies source metric `view-timeline-name:none`, source
scroller `display:none`, and source receiver `animation-name:none`, alongside all
stored and downstream coordinates.

An additional run leaves Chromium entirely unobserved for five seconds after
navigation. It is already retired at the first observation and produces the same
correct values. The later automatic fixtures also gate the downstream subtree
until the producer-retirement signal, so the next matrix starts from stored state.

| Input fixture | QKV RMSE | Downstream RMSE | Maximum downstream error | Retired and correct |
| --- | ---: | ---: | ---: | --- |
| 0 | 0.0002173 | 0.0004260 | 0.0045455 | Yes |
| 1 | 0.0002118 | 0.0003712 | 0.0024951 | Yes |
| 2 | 0.0002101 | 0.0004177 | 0.0026075 | Yes |
| 3 | 0.0002127 | 0.0004170 | 0.0034153 | Yes |

Errors here include the existing font/geometry arithmetic, not just storage.
Recorded cold times include page setup and full-vector observations; they are
not performance comparisons. No speed claim is drawn from them.

## Next gate

Repeated **native** rearm/reset with generation acknowledgements, then one MLP,
two blocks, and twelve blocks in paired live-versus-retired benchmarks. The
one-shot SVG signals freeze; resetting/rearming those signals has not yet been
implemented. The one-day delayed transition also requires an explicit bounded
pause policy. Preserve the existing working core until those tests pass.

Source: `tools/probe_native_value_latch.py`. Raw results: `results.json` for the
full control suite and `automatic-results.json` for the separate native screen.
Regression checks: `tools/test_native_value_latch.py` (saved evidence and fixture
structure, not a substitute for rerunning Chromium).
