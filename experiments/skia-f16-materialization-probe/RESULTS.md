# Standalone Skia materialization precision probe

This tests a prerequisite for the custom-Chromium idea using skia-python's real CPU renderer. It does not patch Chromium, exercise Blink, demonstrate SVG GPU precision, or measure token speed. The normal browser/model was not modified.

64 interior uniformly separated numbers (step 1/65535), plus two guard pixels, are computed from a ramp by Skia, then passed through multiply → three-neighbor reduction → x+x² → residual addition → display amplification. Each stage is rendered into a fresh surface and snapshotted. Actual surface/snapshot types are recorded. Readback does not feed results into subsequent computation. A saved encoded branch feeds residual addition. Only the 64 interior samples are scored, avoiding the renderer's padded-source edge behavior in convolution. The float32 control must match the analytical oracle within 0.0002 at every stage. Permuted-input cases independently test nontrivial spatial reduction: unlike the ramp, their interior values change under neighborhood averaging. Their mathematically expected distinct-value counts can be below 64 after averaging and are included in JSON; uniqueness alone is not their accuracy gate. The RGBA32F path is an accuracy control; it is not proposed as available in stock SVG.

| Input base | Spatial input | Format | Extra barrier after encoding | Distinct levels at successive stages | Diagnostic CPU ms |
|---|---|---|---|---|---|
| 0.0 | ramp | RGBA8 | none | 1 → 1 → 1 → 1 → 1 → 1 | 0.149 |
| 0.0 | ramp | RGBA16F | none | 64 → 64 → 64 → 64 → 64 → 64 | 0.171 |
| 0.0 | ramp | RGBA32F | none | 64 → 64 → 64 → 64 → 64 → 64 | 0.171 |
| 0.0 | ramp | RGBA16F | byte-table | 64 → 1 → 1 → 1 → 1 → 64 → 64 | 0.199 |
| 0.0 | ramp | RGBA16F | one-rgba8-surface | 64 → 1 → 1 → 1 → 1 → 64 → 64 | 0.183 |
| 0.5 | ramp | RGBA8 | none | 1 → 1 → 1 → 1 → 1 → 1 | 0.135 |
| 0.5 | ramp | RGBA16F | none | 3 → 3 → 3 → 3 → 3 → 3 | 0.175 |
| 0.5 | ramp | RGBA32F | none | 64 → 64 → 64 → 64 → 64 → 64 | 0.181 |
| 0.5 | ramp | RGBA16F | byte-table | 3 → 1 → 1 → 1 → 1 → 1 → 1 | 0.207 |
| 0.5 | ramp | RGBA16F | one-rgba8-surface | 3 → 1 → 1 → 1 → 1 → 1 → 1 | 0.182 |
| 0.0 | permuted | RGBA8 | none | 1 → 1 → 1 → 1 → 1 → 1 | 0.152 |
| 0.0 | permuted | RGBA16F | none | 64 → 64 → 52 → 52 → 62 → 62 | 0.254 |
| 0.0 | permuted | RGBA32F | none | 64 → 64 → 52 → 52 → 64 → 64 | 0.232 |
| 0.5 | permuted | RGBA8 | none | 1 → 1 → 1 → 1 → 1 → 1 | 0.177 |
| 0.5 | permuted | RGBA16F | none | 3 → 3 → 3 → 3 → 4 → 4 | 0.191 |
| 0.5 | permuted | RGBA32F | none | 64 → 64 → 52 → 52 → 59 → 59 | 0.186 |

These timings include NumPy fixture/oracle arithmetic, Python dispatch and allocation of explicit tiny surfaces; they are diagnostic and cannot predict browser or full-matrix performance. Sixty samples follow five warmups. A later residual branch can restore levels lost in the main branch, so the pass condition must inspect every stage rather than only the final pixel count. Numerical errors and all values are in results.json.

F16 has limited relative precision; densely spaced numbers around 0.5 are a deliberately hard case. Even if near-zero samples survive, this does not guarantee GPT-2 accuracy. A single byte table or RGBA8 allocation is independently tested, because changing only a destination format cannot fix those. A real Chromium experiment would require equivalent format instrumentation in the SVG filter path and full-model numerical checks.

Two construction corrections are important. The initial embedded-image filter children lost precision when passed through skia-python's cloning bindings; source-relative filters plus a two-row residual source avoid that extra serialization path. The initial convolution error metric also included source edges, where Skia's padded filter input differs from the analytical edge-clamp assumption. Guard pixels and the float32 numerical assertion correct that test-fixture error. Earlier artifacts are retained under binding-image-clone-attempt-* and unguarded-attempt-*; they are not evidence that arithmetic itself cannot preserve float values. The binding uses CloneImage/CloneFlattenable in its [source](https://raw.githubusercontent.com/kyamagu/skia-python/main/src/skia/ImageFilter.cpp).

Reproduce:

```sh
python3 tools/run_unconventional_isolated.py --label skia-f16 -- uv run --python 3.12 --with skia-python==144.0.post2 --with numpy python tools/probe_skia_f16_materialization.py
```
