# Five-metric dense-matrix scaling test

## Decision

Reject this transport for full-width dense GPT-2 matrices.

The five-metric primitive is fast for five rows, but scaling it to all 768 rows
requires hundreds of independently shaped variable fonts. The better of the
two tested layouts needs 924 font instances, expands to 224 MB of font data,
uses about 2.83 GB of Chrome process memory, and takes 934.5 ms to recompute one
real `768×768` matrix after all 768 inputs change. GPT-2 requires many such
matrices, so this is already too expensive at one layer boundary.

## Real GPT-2 fixture

Both pages use GPT-2-small block 0's real `h.0.attn.c_proj.weight`, transposed
into 768 dense output rows. Six realistic inputs are the value-projection
vectors produced for checkpoint token IDs `11`, `612`, `373`, `257`, `464`,
and `3290`. Four additional random vectors stress the full axis range.

Each matrix row is independently quantized so its maximum coefficient is 32.
The output applies the corresponding per-row scale. This quantization is
identical in both layouts, keeping the architecture comparison controlled.

The runtime pages contain only HTML, CSS, and fonts. JavaScript exists only in
the external Playwright measurement harness.

## Compared layouts

| | Five metrics | Four metrics |
| --- | ---: | ---: |
| Direct outputs per font | `ex`, `cap`, `ch`, `ic`, `lh` | `cap`, `ch`, `ic`, `lh` |
| Output groups | 154 | 192 |
| Inputs per font shard | 128 | 256 |
| Shards per output group | 6 | 3 |
| Total fonts | 924 | 576 |
| DOM elements | 1,239 | 967 |

The four-metric layout drops outline-backed `ex`, allowing the full 256-axis
browser limit. It therefore uses 38% fewer fonts and 22% fewer elements.

## Browser measurements

Chrome 153, fresh headless process per layout:

| Measurement | Five metrics | Four metrics |
| --- | ---: | ---: |
| Cold navigation + fonts + forced read | 1,506 ms | 1,702 ms |
| Warm navigation median | 1,032 ms | 1,349 ms |
| Change one axis + force/read 768 outputs | 48.86 ms | 89.71 ms |
| Change all 768 axes + force/read 768 outputs | **934.5 ms** | **1,169.4 ms** |
| WOFF font bytes | 5.964 MB | 5.962 MB |
| Expanded SFNT bytes | **224.34 MB** | **465.08 MB** |
| HTML bytes | 525.6 KB | 323.1 KB |
| Chrome process-tree RSS | **2.826 GB** | **3.228 GB** |

The four-metric version is worse despite having fewer fonts. A variation
region stores coordinates across the font's axis set, so doubling axes from
128 to 256 makes each region substantially larger. Compression hides this:
both font banks transfer in about 5.96 MB, but the four-metric bank expands to
more than twice as much SFNT data and is slower at runtime.

The full-vector measurement is the relevant inference case. A downstream
transformer operation changes essentially every activation, not one axis. The
measurement includes replacing 768 CSS custom properties, but the standalone
five-output probe performed that parsing and recomputation in 6.68 ms; almost
all of the 934.5 ms scale time is the 924-font dependency graph.

## Accuracy

Against the quantized matrix, browser transport is accurate:

| | Five metrics | Four metrics |
| --- | ---: | ---: |
| All-vector browser RMSE | 0.001386 | 0.001214 |
| All-vector browser maximum error | 0.02748 | 0.02092 |

Against unquantized GPT-2 for the six real activation vectors:

| | Five metrics | Four metrics |
| --- | ---: | ---: |
| RMSE | 0.02763 | 0.02766 |
| Maximum error | 0.36082 | 0.36795 |

The nearly identical true-model error confirms that weight quantization, not
font transport, dominates accuracy. Across all real and random vectors, the
shared 6-bit-magnitude weight quantization has 0.07998 RMSE and 1.066 maximum
output error.

Accuracy is therefore not why this approach is rejected. Runtime, expanded
font size, and browser memory are.

## Architectural conclusion

Five font-relative units do provide five independent numeric outputs per font
instance. They improve local output density without timelines. They do not
provide a dense vector-valued result: every additional five rows still requires
another full set of input-axis variation tables and another shaped font.

The output multiplicity remains linear, while each font's region representation
also becomes more expensive as input axes increase. This produces an
unfavorable choice between many narrow fonts and fewer enormous fonts. The
measured optimum of these two candidates is still about 0.93 seconds and 2.83
GB for one matrix, so further constant-factor tuning here cannot make it a
plausible general GPT-2 backend.

## Reproduce

```sh
/usr/bin/python3 tools/build_hvar_five_metric_scale.py
node tools/test_hvar_five_metric_scale.mjs
```
