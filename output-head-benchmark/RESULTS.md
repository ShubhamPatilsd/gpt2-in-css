# TinyStories output-head benchmark

Measured on 2026-08-24 in Chromium 151 using the real
`calum/tinystories-gpt2-3M` token embedding table: 50,257 tokens by 64 hidden
dimensions. Generated CSS is excluded from Git.

## Result

An exact 256-cluster ball index compiled to lazy CSS `@function` calls is the
only tested architecture that materially improves the full-vocabulary output
head. It returns the same maximum, token ID, and 64-number winner embedding as
NumPy on all tested states.

| Architecture | Generated source | Median update | What it returns |
|---|---:|---:|---|
| Registered-property graph | 82 MB CSS | 1.70–1.73 s | maximum |
| Registered graph with feedback | 186 MB CSS | 4.28–4.36 s | maximum, token, embedding |
| DOM/layout reduction | 52 MB HTML | 4.35 s | maximum only |
| Clustered functions | 83.6 MB CSS | 702 ms | maximum |
| Clustered functions + winner | 170.6 MB CSS | 709–729 ms | maximum, token |
| Clustered functions + embedding | 291.9 MB CSS | 743–755 ms | maximum, token, embedding |
| Shared token functions + embedding | 213.0 MB CSS | used by full model | maximum, token, embedding |
| Shared functions + packed 8-bit feedback | 128.7 MB CSS | used by compressed full model | maximum, token, quantized embedding |
| Shared functions + untyped 48-bit feedback | 114.2 MB CSS | 0.85 painted tok/s | maximum, token, quantized embedding |
| Shared functions + typed 6-bit feedback | 118.8 MB CSS | rejected: token 6 diverged | maximum, token, coarser embedding |

The final measurement used 35 real TinyStories hidden states selected because
the cluster with the largest initial upper bound did **not** contain the true
winner. This prevents a lucky first-cluster result from making the benchmark
look cheaper than it is. Two full runs took 26.97 s and 27.38 s respectively,
or 771 ms and 782 ms per state by batch average. The median is lower because a
few states take more than one second.

Correctness across the three fixed prompts and all 35 hard states:

- wrong winner IDs: 0;
- maximum absolute score error: 0.0000454;
- maximum absolute embedding-coordinate error: 0.0000005.

Chromium needed a `0.0001` comparison tolerance to map its recomputed maximum
back to a token ID; `0.000001` was too small because the two CSS calculation
paths round differently. The smallest top-one versus top-two gap among all 72
real generated states was `0.0180`, 180 times the final tolerance, and the
smallest gap among 72 random control directions was `0.00260`, 26 times the
tolerance. Thus the token result is exact on the measured corpus, but this is
not a proof for an adversarial hidden state whose top logits differ by less
than the browser tolerance. The cluster pruning and maximum itself remain
safe-bound exact.

The 291.9 MB end-to-end graph reached its inline benchmark script about
2.8–3.0 seconds after navigation on a local server. Its renderer used about
1.28 GB RSS after the run. Loading another cache-distinct copy while the first
large graph was resident caused a renderer to disappear, so memory pressure is
a practical limit even though one graph loads successfully.

## What the clustered graph does

For each cluster, build a center and a radius around its token embeddings. For
a hidden state `h`, Cauchy–Schwarz gives an upper bound on every token score in
that cluster:

```text
upper_bound = dot(h, center) + length(h) * radius
```

CSS eagerly computes the 256 cheap bounds. It evaluates one seed cluster, then
uses lazy `if()` branches to invoke only cluster functions whose upper bound can
still beat the seed score. Every skipped cluster is mathematically unable to
contain the winner, so this is exact search rather than reduced-vocabulary or
approximate search.

For the 72 real generation states in the offline sweep, the 256-cluster index
evaluated 9,962 of 50,257 token rows on average. Including bound calculations,
that is a 4.92x reduction in multiply terms. A wider cluster-count sweep found:

| Clusters | Mean token rows evaluated | Mean term reduction |
|---:|---:|---:|
| 64 | 10,883 | 4.59x |
| 128 | 10,999 | 4.52x |
| 256 | 9,962 | 4.92x |
| 512 | 9,216 | 5.17x |
| 1,024 | 8,150 | 5.48x |
| 2,048 | 6,981 | 5.57x |
| 4,096 | 5,301 | 5.35x |

The bound work grows with cluster count, so 2,048 is already the arithmetic
optimum of this flat ball index on the measured states. It improves term count
only 13% over 256 clusters while multiplying selector/function orchestration by
eight. Cluster-count tuning is therefore not the next large optimization.

## Browser behavior discovered

- Registered custom properties are eager. Placing the original 50,257-row
  graph behind an unselected `if()` branch did not avoid its work.
- CSS custom functions are lazy. An unselected heavy function was not resolved.
- One function can safely reduce at least 1,280 real token rows in this browser;
  1,536 rows produced an invalid result. The 256-cluster index has 43–520 rows
  per function and stays below that limit.
- DOM intrinsic sizing can perform a native maximum, but creating and laying
  out 50,257 elements is slower and uses more memory. It also cannot feed the
  winning numeric embedding back into the next transformer step.

## Decision and next work

Use the 256-cluster lazy-function head with shared token dot functions as the
current full-vocabulary implementation. Do not use the DOM/layout design. The
shared version reduces the complete head from 291.9 MB to 213.0 MB (-27.0%).

An additional recurrent-only variant quantizes the winning embedding feedback
to 8 bits per coordinate and packs three coordinates into one 24-bit CSS
number. It leaves the full-precision score functions and all 50,257 candidates
unchanged. The head falls to 128,685,887 bytes and a fresh Chromium recurrent
run still produced `[11, 612, 373, 257]`. A later precision probe isolated the
six-coordinate failure to typed `<number>` conversion. An untyped 48-bit
variant preserved all six bytes and matched all 16 reference tokens, reducing
the head to 114,244,898 bytes, but it rendered about 27% slower than the typed
24-bit version. A 6-bit typed variant was smaller but changed the sixth token.
In clean process samples, the default packed streaming page reduced renderer
RSS by 28.35%.

The three proposed follow-ups were completed:

1. A complete width-64, eight-layer incremental transformer plus exact head
   takes 670–702 ms median in a settled static graph.
2. A real sliding-window KV cache and CSS execute/store state machine generated
   the same four greedy tokens as NumPy in 42.69 seconds.
3. A 256-by-16 exact hierarchy reduces theoretical work to 6.67x below dense,
   but cannot preserve lazy leaf pruning with Chromium's current `style()`
   query semantics. Global leaf properties are eager.

The full recurrent result is in [`../tinystories/RESULTS.md`](../tinystories/RESULTS.md).

Reduced vocabulary is not part of this result. All 50,257 tokens remain
eligible, and all measured winners match the reference model.

## Reproduce

```sh
python3 tools/build_output_head_benchmark.py
python3 tools/analyze_output_head_search.py --clusters 64 128 256 512 1024 2048 4096
python3 tools/build_clustered_output_head_benchmark.py
python3 tools/analyze_hierarchical_output_head.py
python3 tools/build_tinystories_step.py
python3 tools/build_tinystories_recurrent.py
python3 -m http.server 4173
```

Then open the generated pages under
`output-head-benchmark/generated/`. The clustered builder emits score-only,
winner-ID, and full embedding-feedback variants.
