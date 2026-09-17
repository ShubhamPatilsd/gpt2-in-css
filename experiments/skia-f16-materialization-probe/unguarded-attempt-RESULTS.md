# Standalone Skia materialization precision probe

This tests a prerequisite for the custom-Chromium idea using skia-python's real CPU renderer. It does not patch Chromium, exercise Blink, demonstrate SVG GPU precision, or measure token speed. The normal browser/model was not modified.

64 uniformly separated numbers (step 1/65535) are computed from a ramp by Skia, then passed through multiply → three-neighbor reduction → x+x² → residual addition → display amplification. Each stage is rendered into a fresh surface and snapshotted. Actual surface/snapshot types are recorded. Readback does not feed results into subsequent computation. A saved encoded branch feeds residual addition. The RGBA32F path is an accuracy control; it is not proposed as available in stock SVG.

| Input base | Format | Extra barrier after encoding | Distinct levels at successive stages | Warm CPU chain ms |
|---|---|---|---|---|
| 0.0 | RGBA8 | none | 1 → 1 → 1 → 1 → 1 → 1 | 0.142 |
| 0.0 | RGBA16F | none | 64 → 64 → 64 → 64 → 64 → 64 | 0.170 |
| 0.0 | RGBA32F | none | 64 → 64 → 64 → 64 → 64 → 64 | 0.171 |
| 0.0 | RGBA16F | byte-table | 64 → 1 → 1 → 1 → 1 → 64 → 64 | 0.195 |
| 0.0 | RGBA16F | one-rgba8-surface | 64 → 1 → 1 → 1 → 1 → 64 → 64 | 0.179 |
| 0.5 | RGBA8 | none | 1 → 1 → 2 → 2 → 2 → 2 | 0.135 |
| 0.5 | RGBA16F | none | 3 → 3 → 5 → 5 → 5 → 4 | 0.169 |
| 0.5 | RGBA32F | none | 64 → 64 → 64 → 64 → 64 → 63 | 0.170 |
| 0.5 | RGBA16F | byte-table | 3 → 1 → 1 → 2 → 2 → 2 → 2 | 0.205 |
| 0.5 | RGBA16F | one-rgba8-surface | 3 → 1 → 1 → 2 → 2 → 2 → 2 | 0.178 |

These timings include Python dispatch and allocation of explicit tiny surfaces; they are diagnostic and cannot predict browser or full-matrix performance. Sixty samples follow five warmups. A later residual branch can restore levels lost in the main branch, so the pass condition must inspect every stage rather than only the final pixel count. Numerical errors and all values are in results.json.

F16 has limited relative precision; densely spaced numbers around 0.5 are a deliberately hard case. Even if near-zero samples survive, this does not guarantee GPT-2 accuracy. A single byte table or RGBA8 allocation is independently tested, because changing only a destination format cannot fix those. A real Chromium experiment would require equivalent format instrumentation in the SVG filter path and full-model numerical checks.

Reproduce:

```sh
python3 tools/run_unconventional_isolated.py --label skia-f16 -- uv run --python 3.12 --with skia-python==144.0.post2 --with numpy python tools/probe_skia_f16_materialization.py
```
