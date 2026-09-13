# ROW-axis multimetric font bank

## Result

The row-selector axis works. One variable font face can hold many groups of
matrix rows, while nested CSS nodes select different groups through a `ROW `
axis and directly inherit the resulting numbers into one final element.

For each group, the font contains variation regions that are the product of:

- one input-axis positive/negative support, and
- a narrow triangular region centered on that group's `ROW ` coordinate.

At `ROW = N`, only group N's weights contribute. The same font instance then
exposes five rows through `ex`, `cap`, `ch`, `ic`, and `lh`.

## 8-input, 16-group proof

One 60,712-byte TTF returned 80 independent outputs through 16 nested nodes.

| Metric | RMSE | Max error |
| --- | ---: | ---: |
| `ex` | 0.000063 | 0.00011 |
| `cap` | 0.33074 | 0.50010 |
| `ch` | 0.000060 | 0.00011 |
| `ic` | 0.000036 | 0.000072 |
| `lh` | 0.80453 | 1.40625 |
| All 80 | 0.38901 | 1.40625 |

Chrome timing:

- Warm navigation/font/style read: 33.8 ms median.
- Change one input and read all 80 outputs: 0.048 ms per update.

This confirms both row isolation and aggregation: the deepest descendant owns
all 80 inherited registered CSS numbers.

## 64-input, 64-group scale

The scaled font is 6,493,416 bytes and the HTML is 120,207 bytes. It returns
320 CSS numbers through 64 nested nodes.

Four metrics scale correctly without outline variation:

| Metric | RMSE | Max error |
| --- | ---: | ---: |
| `cap` | 0.30137 | 0.50010 |
| `ch` | 0.000056 | 0.00011 |
| `ic` | 0.000060 | 0.00011 |
| `lh` | 0.66573 | 1.31250 |

Warm navigation takes 283 ms median. Changing one input and reading all 320
properties takes 0.178 ms per update.

`ex` is the exception: Chromium derives it from the variable `x` outline, not
from MVAR `xhgt`. It therefore stays at zero without full gvar outline deltas.
Adding one harmless nonzero gvar tuple to mark `x` as variable produced exactly
the same failed `ex` values; it does not make Chrome consult MVAR.

Encoding all 64x64 signed x-height cross-regions in gvar is not viable in one
glyph. Even a shifted-axis version with 4,032 tuples exceeded gvar's 16-bit
per-glyph tuple-header offset during FontTools compilation. This is a format
limit, not a Chrome timeout.

## GPT-width scaling test

The four scalable metrics were then used to expose a full 768-output vector
through 192 row-selector nodes. Shifted nonnegative input axes halve the number
of cross-regions: the font evaluates `2w * (x + 1) / 2`, while CSS subtracts
the fixed sum of weights. One reserved input is added with native CSS math.

Five-round WOFF1 runs in Chrome 153 produced:

| Inputs per font | SFNT size | WOFF size | Warm navigation | Change input + read 768 |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 0.59 MB | 44 KB | 131.8 ms | 0.448 ms |
| 32 | 2.35 MB | 102 KB | 316.7 ms | 0.438 ms |
| 64 | 9.43 MB | 212 KB | 983.2 ms | 0.436 ms |
| 128 | 37.73 MB | 437 KB | 3,216.5 ms | 0.457 ms |
| 256 | 150.96 MB | 953 KB | rejected | rejected |

WOFF1 preserves correctness and makes transfer size small, but it does not
reduce font parsing/shaping cost: Chrome expands the complete SFNT tables.
WOFF2 files were even smaller, but Chrome rejected these large variation stores
with `Failed to convert WOFF 2.0 font to SFNT`. The 256-input font is rejected
in every format because Chromium caps decompressed web fonts at 128 MB.

The table reveals the fundamental tradeoff. Region storage grows approximately
with the square of the input-axis count, so narrow shards save memory. But each
shard needs another 192-node row-selection chain, so narrow shards explode the
number of CSS stages.

Extrapolating the measured fixtures across GPT-2-small's 123,532,032 learned
dense weights, including the output head:

| Inputs per shard | Approx. decompressed fonts | Approx. row nodes |
| ---: | ---: | ---: |
| 16 | 5.9 GB | 1.93 million |
| 32 | 11.8 GB | 0.97 million |
| 64 | 23.7 GB | 0.48 million |
| 128 | 47.4 GB | 0.24 million |

These are order-of-magnitude projections from the real 768-output fixtures,
not claimed full-model benchmarks. They are already large enough to reject the
ROW-axis representation as the general GPT-2 backend. It solves result
readback locally, but duplicates a dense axis-support vector for every selected
row. There is no shard width that makes both browser memory and CSS stage count
acceptable.

The mechanism remains useful for small matrices or a future font format with a
dynamic delta-set selector. It does not replace the packed HVAR/timeline
backend for full inference today.

## Reproduce

```sh
ROW_AXIS_FIXTURES=outputs768-i16shift,outputs768-i32shift,outputs768-i64shift \
ROW_AXIS_FORMATS=woff \
  uv run --with numpy --with fonttools --with brotli \
  python tools/build_row_axis_multimetric.py

ROW_AXIS_FONT_FORMAT=woff ROW_AXIS_NAV_ROUNDS=5 \
ROW_AXIS_TEST_FIXTURES=outputs768-i16shift,outputs768-i32shift,outputs768-i64shift,outputs768-i128 \
  node tools/test_row_axis_multimetric.mjs
```

Both runtime pages contain no JavaScript.
