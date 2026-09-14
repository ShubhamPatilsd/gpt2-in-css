# Row-wise int11, ten 80-axis shards, ±266 range

This is the production-range precision comparison for the certified int10
coarse head. Row-wise int11 needs ten 80-axis fonts to keep every HVAR advance
inside 16 bits; the final shard has 48 axes.

| Metric | Row-wise int11 | Row-wise int10 reference |
| --- | ---: | ---: |
| Input range | ±266.248 | ±135.309 |
| Glyphs per token | 10 | 5 |
| Estimated shaped glyphs | 502,570 | 251,285 |
| Font bytes | 58.20 MB | 51.18 MB |
| HTML bytes | 8.92 MB | 6.62 MB |
| Cold load | 108.462 s | about 39 s |
| Settled radio mutation | 0.850-1.047 s; 1.005 s median | about 0.78 s warm |
| Validation mutation | 3.114-4.718 s; 3.250 s median | not paired |
| Browser int11 winner agreement | 11/11 | — |
| Dense float winner agreement | 10/11 | — |

The extra bit halves weight RMSE to 0.0001647 and sharply reduces certified
follow-up groups, but doubling the shaped glyph stream makes cold layout 2.8x
slower than the int10 branch. Reject as the default one-shot coarse head.
Retain as a possible recurrent/warm alternative because a 24-bucket proof
budget needs median/p95/max only 2/6/22 exact groups versus int10's 3/18/61.
The certified-upper transform confirms the result at 104.80 seconds cold with
11/11 correct upper groups; see
`../gpt2-hvar-grid-output-head-certified-upper-rowwise11-range266/RESULTS.md`.

## Reproduce

```sh
make test-gpt2-rowwise11-head
```
