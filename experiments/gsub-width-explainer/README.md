# The width problem: interactive explainer

Open `index.html` directly, or serve the repository and open
`/experiments/gsub-width-explainer/index.html`. Chrome 153 reproduces the embedded
native demo. Other browsers may support the narrative and teaching controls but
not the anchor-size/container-unit numeric decoder; the page reports unsupported
or mismatched native results explicitly.

The HTML is self-contained: actual WOFF2 bytes, measured timing records, the real
neuron slice, styles, and interaction code are embedded. Relative evidence links
require the surrounding repository. External specification links require network
access. No external scripts, fonts, analytics, or asset requests are needed.

## Scope and evidence

This is an explanatory artifact, not another performance experiment or a model
implementation. It distinguishes:

- Actual browser execution of the preserved two-coordinate depth-16 GSUB font.
- A JavaScript teaching replay of the compiler's formula, without claiming to
  observe Chromium's internal glyph buffer.
- Historical timings from the corrected direct-CSS comparison.
- A floating-point illustration of an actual block-0 GPT-2 MLP output.
- Exact combination counts and proposed, untested widening experiments.

The native demo uses CSS fixed counter styles to select private-use characters,
the exact `depth16.woff2` font to run its 16 transitions, a final glyph advance,
and anchor-size/container units to decode that advance into registered numeric
CSS properties. Its JavaScript only supplies inputs and observes the native
result. It independently calculates an expected pair for validation; that pair
is not fed into the decoder. Disabling feature `ss08` breaks the chain and yields
zero source width, which is not decoded as a valid result.

The original experiment's page has CSP `script-src 'none'`. This teaching page
uses JavaScript for explanation controls and observers. Its elapsed time is not
compared with the original benchmarks.

## Provenance of the real model slice

`real-neuron.json` contains 768 input coordinates, 768 weights and one bias:

1. Read `data/gpt2/model.safetensors` using the existing `load_weights()` helper
   in `tools/analyze_css_native_grouped_mlp.py`.
2. Verify the local GPT-2 tokenizer encodes `Hello` as `[15496]`.
3. Run `exact_block0_batch(np.array([[15496]]), weights)` and select its first
   result, the output of block 0's second layer normalization / MLP input.
   This reference computes activations in float32.
4. Select the checkpoint's `h.0.mlp.c_fc.weight[:, 0]` and
   `h.0.mlp.c_fc.bias[0]`. The raw matrix shape is `[768, 3072]`.
5. Convert these stored values to float64 to illustrate one sum. The resulting
   preactivation is approximately `-0.10523400642677186`. This is before GELU.

All 768 selected weights are nonzero. The reference is not an observation from
the quantized HVAR browser model. The hash covers the concatenated little-endian
float64 input vector, weight vector, and bias; its encoding is documented in JSON.

## Rebuild

From the repository root:

```sh
python3 tools/build_gsub_width_explainer.py
```

To re-extract the model slice as well (requires NumPy and the local checkpoint):

```sh
python3 tools/build_gsub_width_explainer.py --refresh-neuron
```

The builder reads the preserved experiment JSON and checks the embedded font's
SHA-256 against the known depth-16 artifact. `manifest.json` records input hashes
and the generated page hash. Edit `simple.template.html`, then rebuild; do not
edit the generated HTML directly.

## Verification

```sh
python3 -m http.server 8765 --bind 127.0.0.1
# In another terminal:
node tools/test_gsub_width_explainer.mjs
```

The harness uses Playwright and local Chrome. `CHROME_PATH` and `EXPLAINER_URL`
can override their defaults. It checks all 256 live native input states, both
decoded coordinates and the dependent consumer width, a disabled-step control,
teaching interactions, the actual 768-input reference sum, timing-data selection,
repository evidence links, and horizontal overflow at five viewport widths.
It saves results and desktop/mobile screenshots in `verification/` for inspection.
These are functional/visual checks, not performance results.

Verified on 2026-09-17 with Chrome 153.0.8010.48:

- All 256 input pairs passed exact native font, x/y decoder, and consumer checks.
- Disabling transition 8 yielded zero width and no displayed decoded pair.
- The 768-input teaching sum matched the extracted reference within `1e-12`.
- All 16 distinct local evidence links resolved.
- No page JavaScript errors or failed page asset requests.
- No horizontal page overflow at 1440, 1024, 768, 390, or 320 CSS pixels.
- The standalone `file:` page reproduced the native result with networking off.
- Desktop/mobile hero, circuit, neuron, and table screenshots were inspected.

Full results are in `verification/results.json`. The checks establish this
explainer's fidelity and operation; they do not establish wider GSUB scalability.
