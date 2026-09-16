# QKV projection and transport comparison

This probe computes the real GPT-2-small block-0 `768 → 2,304` QKV projection
for two token states with the same signed 9-bit weights. Runtime pages are
HTML/CSS-only. The external Playwright harness mutates the inputs and reads all
2,304 outputs.

Measured in headless Chrome 153 on macOS on September 12, 2026:

| Backend | Warm mutation | RMSE | Numeric carriers |
| --- | ---: | ---: | ---: |
| native CSS, 1,757,322 products | 955 ms | 0.0000014 | none |
| HVAR + ordinary timelines | 262 ms | 0.000189 | 2,304 timelines |
| HVAR + shared easing | 245 ms | 0.000107 | 2,304 timelines |
| timeline packet, four 7-bit outputs | 202 ms | 0.00498 | 1,152 timelines |
| timeline packet, six 6-bit outputs | 173 ms | 0.0100 | 768 timelines |
| container packet, six 8-bit outputs | **168–197 ms** | **0.00353** | **384 size containers** |

The container packet is the scaling winner in this fixture. Each HVAR dot
product is rounded to an 8-bit per-output code. Three codes are radix-packed
into an element's width and three into its height. A nested descendant reads
the two dimensions with `100cqw` and `100cqh`, decodes six registered CSS
numbers, and carries them to the next packet by inheritance. This removes all
view timelines and animations from the transport.

Compared with ordinary HVAR timeline capture, it is about 1.36–1.56x faster and
uses 384 geometry carriers instead of 2,304 animation samples. It is about
5x faster and roughly 8x smaller than the 30.9 MB direct-CSS matrix.

## Precision limits found

- Three 7-bit values in one timeline axis require a 21-bit carrier. Inverting
  serialized animation progress corrupts the low digit. Four-value 7-bit
  packing works; six-value 6-bit packing works but is coarse.
- Direct container units avoid that inversion and reliably expose about 24
  packed integer bits per physical axis. Three 8-bit values therefore fit.
- Fractional geometry does not extend the limit. Packing three 10-bit values
  into 1/64-pixel units produced 0.0179 RMSE because large layout dimensions
  lose the fractional bits.
- Four 12-bit outputs require 576 nested size containers. Chrome stops
  propagating this fixture after roughly 512 levels, leaving the tail unset.

The displayed 8-bit result uses ranges calibrated to the two browser cases.
A separate deterministic stress test calibrates per-channel ranges on 4,096
random token/position states and evaluates 1,024 held-out states. With a 20%
range margin, 8-bit packing gives 0.01062 RMSE and clips 0.00114% of values;
10-bit would give 0.00304 RMSE, but does not fit the reliable 24-bit geometry
budget at six outputs per container. See `qkv-transport-precision.json`.

## Decision

Use HVAR for the dense matrix, native CSS numbers for attention arithmetic,
and direct 8-bit width/height container packets when the downstream accuracy
test tolerates them.

Two downstream integrations now establish the useful boundary:

- Packing all values through a complete block is a loss: the six-output packed
  block takes 2.26 s versus 436 ms for the older four-output raw-dot block. The
  `3,072 -> 768` projection's dependency graph erases the carrier reduction.
- Packing only QKV inside real two-token causal attention is a win: the warm
  full-page median falls from 2,691 ms to 1,420 ms, a **1.90x speedup**. Final
  residual RMSE against the packed reference is 0.001330.

Therefore retain direct packets as a localized QKV transport, not as a global
numeric backend. Each token uses its own declarative shadow root to reset the
384-container nesting depth. Next test context-length scaling and general range
calibration before connecting this hybrid attention path to the MLP.
