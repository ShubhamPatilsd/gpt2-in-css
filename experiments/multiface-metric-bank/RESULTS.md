# Multi-face metric bank

## Question

Can many small variable-font faces expose a complete matrix output directly as
CSS numbers through `cap`, `ch`, `ic`, and `lh`, avoiding glyph-width timelines?

All runtime fixtures are HTML/CSS-only. The Playwright harness changes inputs
and reads computed properties from outside the page.

## Direct metric result

Yes, functionally. Four independently weighted metric values per face scale to
a full `256 → 768` matrix:

- 192 font faces expose all 768 outputs.
- Shifted axes encode `x` as `(x + 1) / 2`; CSS subtracts each row's fixed
  weight sum. This halves the signed variation regions without approximation.
- The WOFF payload is 1.95 MB and expands to 154.98 MB of SFNT data.
- Output RMSE is approximately 0.35 font units, with 1.45 maximum error.

The fifth `ex` channel is not scalable at 256 axes. Chromium derives `ex` from
the `x` outline, so it needs one `gvar` tuple per input axis. The per-glyph
tuple header exceeds OpenType's 16-bit offset. The four metric-table channels
do not have that limit.

## Cached versus real-input timing

Alternating between two previously evaluated axis locations gives a misleading
8–11 ms update because Chromium reuses cached font instances. With a different
input vector on every round, the same `256 → 768` matrix takes 0.37 seconds.

A structurally complete `768 → 768` test chains three 256-axis partial products:

| Shard width | Shards | Metric producers | Expanded SFNT if weights are unique | Uncached update | Result |
| ---: | ---: | ---: | ---: | ---: | --- |
| 256 | 3 | 576 | about 465 MB | 1.10 s | correct |
| 128 | 6 | 1,152 | about 239 MB | 1.05 s | correct |
| 64 | 12 | 2,304 | about 128 MB | — | page crashed |

The full fixtures reuse one physical font bank across shards to avoid spending
minutes generating duplicate random test weights. Their CSS computation and
producer counts are complete; the expanded-size column multiplies the physical
bank by the number of unique shards a real matrix requires.

Errors accumulate across partials. The 256-axis full matrix has approximately
0.64 RMSE and 2.8 maximum error; the 128-axis version has approximately 0.92
RMSE and 5.4 maximum error.

## Nesting discovery

HTML parsing flattens a normal element chain at 512 ancestors, breaking later
output groups. Serving the same document as XHTML preserves all 582 ancestors
and makes the three-shard result correct. XHTML also preserves 1,161 ancestors
for the 128-axis variant. At 2,304 producers Chromium crashes during page load,
so XML parsing removes the HTML parser cutoff but not the style/layout engine's
practical depth limit.

## OpenType selector probe

`../gsub-metric-bank-32x64/` stores many glyph-advance rows in one shared HVAR
font and selects alternate `0`/`水` glyphs with a numeric `cv01` feature. Chrome
changes shaped text for such features, but `1ch` and `1ic` measure the base
glyph directly and ignore GSUB. The 64-output probe therefore has 82.3 RMSE and
is rejected.

## Decision

Direct font metrics are valuable for small vectors, but reject the multi-face
bank as the dense GPT-2 backend. Its honest uncached time is roughly one second
for one square GPT-width matrix, and its decompressed tables consume hundreds
of megabytes per unique matrix. Narrow shards reduce table memory but add
enough font instances to erase the speed gain and eventually crash Chromium.

The underlying positive result remains useful: XHTML bypasses the normal
512-level HTML parser flattening, and shifted axes reduce signed variation
storage without changing the calculation.

## Reproduce

```sh
MULTIFACE_BANK_DIRECTORY=multiface-metric-bank-256x768-woff \
MULTIFACE_BANK_MUTATION=unique MULTIFACE_BANK_ROUNDS=5 \
node tools/test_multiface_metric_bank.mjs

MULTIFACE_BANK_DIRECTORY=multiface-metric-bank-768x768-reused \
MULTIFACE_BANK_PAGE=index.xhtml MULTIFACE_BANK_MUTATION=unique \
MULTIFACE_BANK_ROUNDS=5 node tools/test_multiface_metric_bank.mjs
```
