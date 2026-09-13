# SVG output-head calibration

This screen tests corrections that can be folded into the existing output-head
weights and per-token biases, adding no runtime stage. All corrections are fitted
on 256 calibration tokens and measured on 512 disjoint tokens.

| Correction | Held-out top-1 | Natural top-1 | Final-state RMSE |
| --- | ---: | ---: | ---: |
| none | 482/512 | 53/64 | 0.2254 |
| diagonal hidden affine | 487/512 | 54/64 | 0.1256 |
| rank-32 state-error map | 484/512 | 53/64 | 0.1013 |
| rank-128 state-error map | **488/512** | **55/64** | 0.0948 |
| rank-255 state-error map | 479/512 | 54/64 | 0.0890 |

Per-token affine logit calibration was worse than the uncorrected head except
under very strong shrinkage, where it reached 487/512. Lower state RMSE does not
reliably restore token order, and the higher-rank map begins overfitting.

This rejects output-head calibration as the missing accuracy fix. A rank-128 map
is a valid optional refinement because it can be folded into stored head weights,
but a 1.17 percentage-point top-1 gain does not justify changing the checkpoint's
head for the primary demo.

```sh
uv run --with numpy python tools/screen_svg_output_head_calibration.py
```
