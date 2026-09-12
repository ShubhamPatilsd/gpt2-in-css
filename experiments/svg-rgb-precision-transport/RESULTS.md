# RGB coarse-plus-correction transport

This no-JavaScript page compares one, two, and three independently scaled SVG
color channels. The external test harness screenshots the rendered pixels and
reconstructs each scalar.

The channels represent:

```text
value = coarse + correction + fine correction
scales = 2, 2/255, 2/255^2
```

Each affine calculation is followed by an identity `feConvolveMatrix`. This
forces a real filter-image boundary instead of allowing Chromium to fold a run
of color matrices into one expression.

| Boundaries | 1-channel RMSE | 2-channel RMSE | 3-channel RMSE |
| ---: | ---: | ---: | ---: |
| 0 | 0.004579 | 0.00001753 | 0.00000006893 |
| 1 | 0.005982 | 0.004314 | 0.004314 |
| 2 | 0.006705 | 0.005632 | 0.005632 |
| 4 | 0.007618 | 0.006897 | 0.006897 |
| 8 | 0.008953 | 0.008723 | 0.008722 |
| 12 | 0.010529 | 0.010438 | 0.010438 |

Before computation, two channels are about 261 times more accurate than one,
and three channels are about 66,000 times more accurate. After the first
calculated image boundary, the second and third channels have the same error.
By twelve boundaries they improve RMSE by less than one percent over one
channel.

The low channels retain the correction for the original input. They cannot
receive the new remainder discarded when Chromium materializes the newly
calculated coarse result. A third byte therefore increases storage precision
but does not create reusable 24-bit computation.

The generated page is 26,399 bytes. The measured Chromium run loaded in 24.6
ms and rendered the screenshot in 121.7 ms; those figures are probe overhead,
not GPT-2 token latency.

Raw measurements are in `results.json`.
