# Native inline attention reducer

Decision: **reject**. The corrected primitive works, but both native inline
reducers lose to the retained flat CSS reduction and introduce one DOM value
carrier per context position and output coordinate. This is a speed and
element-scaling rejection, not a correctness rejection.

The probe keeps GPT-2's architecture and weights unchanged. It uses real
block-0 attention scores and V data and compares the retained flat weighted
sum with two script-free ways to make inline layout compute

```text
sum_i softmax(score_i) * V_i
```

- `font-size`: each source glyph has an HVAR advance derived from `V_i`, while
  `font-size` supplies the softmax probability.
- `zoom`: the glyph has a fixed font size, while `zoom` supplies the softmax
  probability.

The generated pages contain no script elements. Chrome 153 reports support for
the required `calc-size()` and variable `zoom` paths.

## Corrected primitive gate

The four-source/four-coordinate primitive independently changes scores and V.
Control, `font-size`, and `zoom` produce the same outputs in all four modes,
showing that dynamic probabilities and dynamic V values compose through both
candidate carriers.

| Mutation | RMSE | Maximum absolute error |
| --- | ---: | ---: |
| Initial | 0.00002915 | 0.00004034 |
| Scores only | 0.00003558 | 0.00005357 |
| V only | 0.00004262 | 0.00005101 |
| Scores and V | 0.00002912 | 0.00004189 |

Every result is comfortably inside the primitive gate of RMSE <= 0.001 and
maximum absolute error <= 0.005. The earlier broken-control rejection was
caused by missing required whitespace around `+` in generated CSS `calc()`
expressions; it is superseded by this corrected run.

## Real block-0 timing

Each completed row is the median of three browser rounds. Accuracy is measured
against the reference attention output.

| Context | Reducer | Median | Relative to flat | Elements | Value spans | Max RMSE | Max abs error |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | Flat control | 105.81 ms | 1.00x | 776 | 0 | 0.0000342 | 0.0000590 |
| 8 | `font-size` | 175.46 ms | 1.66x | 6,920 | 6,144 | 0.0000536 | 0.0003494 |
| 8 | `zoom` | 442.97 ms | 4.19x | 6,920 | 6,144 | 0.0000536 | 0.0003494 |
| 16 | Flat control | 823.03 ms | 1.00x | 776 | 0 | 0.0000344 | 0.0000591 |
| 16 | `font-size` | 1,069.21 ms | 1.30x | 13,064 | 12,288 | 0.0000846 | 0.0005436 |

`zoom` at context 16 and every context-32 page were intentionally not run
after the completed rows made the gate decisive. Browser-close errors emitted
during the stopped invocation are not benchmark evidence and are excluded
from `browser-results.json`.

## Why this does not scale

The inline routes require `context * 768` value spans: 6,144 at context 8 and
12,288 at context 16. Total DOM elements consequently grow from 6,920 to
13,064. The flat control retains 768 output elements and 776 total elements;
its expression size still grows with context, but it avoids materializing a
DOM carrier for every source/output pair.

The candidate therefore changes the representation, not the asymptotic work:
it still performs one contribution per context position per output coordinate,
adds O(context * width) DOM/layout objects, and is already 30-319% slower in
the measured cases. It cannot reduce fixed GPT-2 attention scaling.

## Artifacts and validation

- `browser-results.json` is the authoritative corrected result: primitive
  pass, five completed timing rows, explicit skipped rows, and rejection.
- `browser-progress.json` preserves the same completed progress evidence.
- The builder emits one 64-axis HVAR font, one primitive page, and real
  block-0 control/`font-size`/`zoom` pages for contexts 8, 16, and 32.
- Python compilation, Node syntax checking, JSON parsing, generated-page
  script checks, and result invariants pass. No context pages were run during
  final validation.
