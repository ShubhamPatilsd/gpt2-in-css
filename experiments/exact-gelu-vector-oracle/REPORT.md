# Exact-GELU vector-boundary oracle

## Result

After moving GELU out of every projection output, vector transport is the
dominant remaining cost. The real `3072 -> 768` projection takes only **64.2
ms**, and evaluating all 3,072 exact GELUs once adds **24.4 ms**. Replacing the
expensive vector boundaries with exact browser-captured CSS numbers reduces the
two-block graph from **1,710.6 ms** to **64.2 ms**, a **26.6x** upper-bound
speedup.

This supersedes the earlier 5.02x oracle ceiling. That older “projection-only”
page still evaluated the sparse `avar2` GELU inside every output run, so its
476.6 ms floor was not the cost of the linear projection itself.

Every runtime page contains HTML, CSS, and fonts only. The external Playwright
harness changes the input case and reads widths. All five oracle topologies
match all 768 captured output widths exactly for all four cases.

## Controlled timings

Chrome 153.0.8010.36, six fresh page graphs per topology after warming browser,
HTTP, and font caches. Each sample changes case 0 to one of three distinct real
cases and forces all 768 final widths.

| Topology | Real work left | Elements | Median |
| --- | --- | ---: | ---: |
| Exact-GELU two-block baseline | Both complete blocks and transports | 23,528 | 1,710.6 ms |
| Free block-0 output/state boundary | Complete block 1 | 6,598 | 786.7 ms |
| Free block-1 FC boundary | Block 0, block-1 attention, GELU, projection | 18,870 | 950.0 ms |
| Both expensive boundaries free | Block-1 attention, GELU, projection | 1,939 | 180.4 ms |
| Everything through block-1 preactivation free | GELU and projection | 783 | 88.6 ms |
| Post-GELU values supplied | Pure linear projection | 783 | 64.2 ms |

Architectural differences from this graph:

- block 0 plus its state handoff: about 923.9 ms;
- block-1 FC plus preactivation handoff: about 606.3 ms after block 0 is free;
- block-1 attention and layer normalization: about 91.8 ms in the reduced graph;
- exact compute-once GELU: about 24.4 ms;
- pure linear projection: about 64.2 ms.

The differences compare different dependency graphs, so they are upper-bound
attribution rather than additive profiler self-times. The conclusion is robust:
the retained matrix backend is no longer the scaling blocker. The missing
primitive is a cheaper way to carry the FC and block-output vectors into
reusable CSS numeric state.

## Reproduction

```sh
node tools/capture_exact_gelu_vector_oracle.mjs
PYTHONPATH=tools uv run --with numpy python tools/build_exact_gelu_vector_oracle.py
EXACT_GELU_ORACLE_ROUNDS=6 node tools/benchmark_exact_gelu_vector_oracle.mjs
```

Raw measurements are in `benchmark-results.json`.
