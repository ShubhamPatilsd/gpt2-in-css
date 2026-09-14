# Sparse avar2 GELU + linear HVAR full GPT-2 MLP

This no-JavaScript runtime page computes the real GPT-2-small block-0 MLP
shape, `768 -> 3,072 -> 768`, with the established signed 9-bit FC weights and
the real projection weights.

The graph is split into twelve parallel 256-hidden-unit groups:

```text
three 256-axis HVAR FC shards
  -> 256 preactivation widths per group
  -> 128 paired width/height container captures
  -> sparse diagonal avar2 GELU
  -> linear 256 -> 768 HVAR projection
  -> geometry sum of twelve contributions per output
```

The important change is where GELU lives. The first version repeated 28
piecewise GELU regions inside every one of 768 HVAR output rows. The retained
version applies the piecewise map once per axis in sparse avar2 VarData, then
uses only two linear HVAR regions per axis for the projection.

## Browser result

Chrome 153, four real GPT-2 token states:

| Backend | Forced-layout warm median | Projection WOFF2 | Browser max error | Output RMSE |
| --- | ---: | ---: | ---: | ---: |
| Piecewise GELU repeated in HVAR | 311.0 ms | 12.53 MB | 0.2521 | 0.0672-0.0716 |
| Sparse avar2 GELU + linear HVAR | **251.0 ms** | **3.64 MB** | **0.0223** | **0.0203-0.0249** |

The persisted matched profile is 19.3% faster; repeated runs measured a
248-251 ms median. The new path cuts the
projection fonts by 71.0%. Its 2.14 MB HTML and 2.81 MB shared FC fonts make the
complete experiment about 8.58 MB before HTTP compression of the HTML.

The full all-768-output harness has reported 0.83-3.16 second medians because
it serializes every DOM width through DevTools and encounters multi-second browser stalls.
The forced-layout profile changes the same input and reads one final dependent
output, which forces the complete graph while avoiding that measurement
overhead. It still has occasional 0.6-0.7 second stalls; the stable floor is
roughly 0.20-0.25 seconds.

## What this changes

- A real GPT-2 MLP no longer needs one 3,072-axis font.
- The 256-axis font limit is handled exactly by hidden-dimension sharding;
  low-rank compression is not involved.
- The result is a reusable 768-value geometry vector, not a screenshot or an
  external harness result.
- This is faster than the previous 341 ms loaded flat-timeline MLP while being
  directly composable into the next transport boundary.

This is not yet a full transformer block. LayerNorm, attention, residual/bias
addition, and the next block boundary still need to be connected around it.
Twelve blocks would also make MLP work alone roughly three seconds if scaling
were perfectly linear, so latency remains the primary problem.

## Reproduce

```sh
make test-avar2-gelu-linear-hvar-full-mlp
make profile-avar2-gelu-linear-hvar-full-mlp
```

The page itself contains no script; JavaScript exists only in the external
Playwright verification and profiling harnesses.
