# Attention and QKV-transport comparison

The real two-token GPT-2 attention page was generated three ways. The first two
isolate the Q·K score backend while retaining timeline QKV transport. The third
keeps native CSS Q·K but replaces 4,608 QKV timelines with 768 direct size
containers (384 per token). All variants retain native CSS softmax/value mixing,
the HVAR output projection, and the final residual.

Measured in headless Chrome 153 on macOS on September 12, 2026:

| QKV transport | Score backend | Warm full-page median | Score RMSE | Final residual RMSE |
| --- | --- | ---: | ---: | ---: |
| 4,608 timelines | native CSS 64-term `calc()` | 2,691.18 ms | 0.000547 | 0.000340 |
| 4,608 timelines | bilinear HVAR + 24 score timelines | 2,952.24 ms | 0.000746 | 0.000319 |
| 768 direct size containers | native CSS 64-term `calc()` | **1,419.59 ms** | 0.000966 | 0.001330 |

The bilinear font is correct, but it does not speed up the real two-token chain.
Its shaping and geometry-to-number boundary costs more than the small native CSS
score calculation it replaces. Direct QKV container transport is the useful
boundary: it makes this end-to-end attention fixture **1.90x faster** while
remaining numerically close to its packed reference.

A matched score-only scale probe reaches the stronger architectural conclusion:
with Q and K already stored as CSS numbers, native CSS computes 12 heads × 64
keys in 49.43 ms for a cached query, versus 674.66 ms for bilinear HVAR and
8,626.53 ms for packed anchor geometry.

Use direct container capture for QKV followed by native CSS attention math.
Reset the 384-level packet chain in one declarative shadow root per token so the
browser never crosses its roughly 512-level propagation failure. The container
page is also slightly smaller: about 6.24 MB including shared fonts versus 6.37
MB for the timeline page.

The current ranges are calibrated to this two-token fixture, so the measured
0.001330 residual RMSE is a best-case integration result, not yet a general
prompt-accuracy result. The next scaling gate is longer contexts with ranges
calibrated over many token/position states.
