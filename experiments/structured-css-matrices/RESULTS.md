# Structured post-training GPT-2 matrix representations

## Purpose

This experiment asks whether the unmodified GPT-2-small checkpoint contains
enough structure to replace dense matrix-vector multiplication with compact,
reusable HTML/CSS calculations.

It evaluates block 0 using 18 diverse real GPT-2 token embeddings. LayerNorm,
GELU, residuals, biases, blocks 1--11, and the output head remain exact. Only
the four block-0 matrices are replaced. The block has 5,898,240 dense multiply
terms in the one-token path.

The reported next-token agreement is deliberately optimistic: an actual
compressed model would approximate all 12 blocks, while this test approximates
only the first and then runs the remaining 11 exactly.

## Results

| Representation | Best tested configuration | Term compression | Relative block RMSE | Mean cosine | Optimistic next-token agreement |
| --- | --- | ---: | ---: | ---: | ---: |
| Kronecker sum | inner grid 64, rank 8 | 2.55x | 97.53% | 0.268 | 16.7% |
| Additive product codebook | 64-value blocks, 32 entries, 2 stages | 11.16x | 95.49% | 0.359 | 22.2%* |
| Shared row codebook | 256 rows | 4.27x | 87.24% | 0.575 | 16.7% |
| Shared column codebook | 256 columns | 4.27x | 90.67% | 0.486 | 33.3% |
| 8x8 block-circulant | one circulant per tile | 1.00x execution / 8x storage | 96.35% | 0.342 | 16.7% |

\*The highest agreement for additive codebooks was 22.2%; that particular
configuration used 16 entries and 2 stages at 16.55x term compression. The
table uses the configuration with the lowest block error.

All methods fail by a wide margin. For context, the accurate HVAR browser block
has RMSE 0.00254. These structured forms have block RMSE around 4.5--5.0 and
change two thirds to five sixths of next-token winners even though only the
first block is approximated.

## What each representation would mean in CSS

### Kronecker sums

A matrix is represented as a sum of `A ⊗ B` products. Each product becomes two
small native-CSS matrix multiplications rather than one dense multiplication.
The test tried ranks 1, 2, 4, and 8 with 16-, 32-, and 64-wide inner grids.

This maps cleanly to CSS dependency stages, but the real weights have almost no
matching Kronecker structure. The worst individual matrix still has 97--100%
relative Frobenius error in the useful ranks.

### Additive product codebooks

Each weight row is split into 32- or 64-value chunks. For every chunk position,
CSS would calculate a small shared bank of codeword dot products. Each output
then selects and adds its assigned codeword result. A second codebook stage
encodes the residual left by the first.

This is operationally attractive: the 64/32/two-stage form needs about 11x
fewer arithmetic terms and only code indices per output. It is numerically
unusable because GPT-2's matrix chunks do not cluster closely enough.

### Shared whole rows or columns

Row codebooks calculate a limited set of complete dot products and let many
outputs reuse them. Column codebooks first sum inputs assigned to a common
column type, then multiply those bucket sums by shared column vectors.

Even 256 codewords preserve too little information, despite offering only
4.27x term compression.

### Block-circulant tiles

Circulant tiles shrink stored coefficients by the tile width, but native CSS
still needs every multiply unless it also implements an FFT. CSS has no complex
FFT primitive, and the existing SVG convolution path reintroduces 8-bit
quantization. The approximation itself is also extremely inaccurate.

### Exact repeated quantized chunks

Signed 9-bit weight chunks were interned only when the same code pattern
appeared at the same input coordinates. For chunks of four or more values,
almost every chunk is unique. Accounting for the final row sums makes the
dependency count **larger** than dense CSS:

- 4-value chunks: approximately 1.25x the dense term count;
- 8-value chunks: approximately 1.125x;
- 16-value chunks: approximately 1.0625x.

Single-value reuse reduces the number of distinct multiplications, but every
output still needs every selected product, so total dependencies remain
1.11--1.35x dense. There is no useful exact common-subexpression structure.

## Decision

Post-training structured compression is not the missing CSS inference trick for
the actual GPT-2 checkpoint. The representations that substantially reduce
work erase nearly all of the learned transformation. Exact subexpression reuse
does not exist at a useful rate.

These methods would require structure-aware training, distillation, or
fine-tuning. Without changing the model, dense products must stay compact in a
backend such as HVAR; the remaining target is still bulk vector transport, not
weight factorization.

## Reproduce

```sh
python3 tools/analyze_structured_css_matrices.py
```

Full configurations, per-matrix reconstruction errors, changed token fixtures,
and exact chunk counts are in `results.json`.
