# A streaming font machine fails the downloaded-font support gate

A different execution model is worth screening before building another large
arithmetic compiler. Apple's AAT `morx` format supports state-machine processing
of a glyph stream. That suggests a possible running accumulator which visits
inputs in order, rather than expressing each step as a new GSUB lookup pass.
This is a design hypothesis, not an implemented accumulator or speed claim.
See Apple's [table specification](https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6morx.html)
and the [HarfBuzz AAT API](https://harfbuzz.github.io/harfbuzz-hb-aat-layout.html).

The support gate is deliberately simpler than arithmetic. Three otherwise
equivalent fonts contain an input glyph of width 100 and an answer glyph of
width 700. One font has no substitution; another maps the input to the answer
using `morx`; a third performs that mapping with GSUB. A directly encoded
answer glyph checks that the font really loaded. Both TTF and WOFF2 are tested.

| Font | Standalone HarfBuzz 14.2.1 input width | Chrome 153 TTF | Chrome 153 WOFF2 |
| --- | ---: | ---: | ---: |
| No substitution | 100 | 100 | 100 |
| AAT `morx` substitution | 700 | 100 | 100 |
| GSUB substitution | 700 | 700 | 700 |

All six final browser fonts load, every directly encoded answer glyph measures
700, and there are zero document scripts. The same `morx` font that executes in
standalone HarfBuzz does not execute its substitution as a downloaded font in
this Chrome. This stops the proposed backend at its first gate.

Source inspection supports table removal as the explanation: Chromium's
[downloaded-font decoder](https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/platform/fonts/web_font_decoder.cc)
passes several layout tables through but does not list `morx`; the upstream
[OpenType Sanitizer](https://raw.githubusercontent.com/khaledhosny/ots/main/src/ots.cc)
defaults to dropping unsupported tables and its supported set does not include
`morx`. These are current source observations, not a capture of the installed
browser's post-sanitization bytes. The actual tested claim is the substitution
behavior above. Local installed fonts, other browsers and custom decoders were
not tested.

This is a useful rejection, not a new solution. We avoided investing in a
streaming arithmetic compiler whose entry point does not work in the current
downloadable-page setting. Installing fonts or changing browser handling would
change the deployment assumptions and needs a separate evaluation.

## Evidence and reproduction

[reference.json](reference.json) records font hashes and standalone results;
[browser-results.json](browser-results.json) records the browser, harness hash,
all six loaded-font checks and observed widths. No timings were collected.

An initial fixture gave every glyph an empty outline. Its TTF controls worked,
but every WOFF2 font failed to load, including the plain and GSUB controls.
That cannot establish an AAT-specific WOFF2 failure. The complete failed
fixture and source snapshot are retained in [attempt-empty-outlines](attempt-empty-outlines/browser-results.json).
Adding a tiny outline to `.notdef` repaired all three WOFF2 loading controls;
the main table uses only that repaired fixture.

```sh
python3 tools/run_unconventional_isolated.py --label aat-support-build -- uv run tools/build_aat_support_probe.py
python3 tools/run_unconventional_isolated.py --label aat-support-browser -- node tools/test_aat_support_probe.mjs
```

The scripts require the existing local FontTools/WOFF2 dependencies, Homebrew
`hb-shape`, the workspace Playwright runtime, and Chrome. They do not install
fonts, patch the browser, or change its font validation rules.
