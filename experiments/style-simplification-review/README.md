# Three attempts to remove repeated CSS work

This directory records the bounded experiments authorized after the initial
[source review](REVIEW.md). The experiments use separate correctness gates and
timing runs. They do not run the complete 32-token model or modify its default
backend. The other task's connected MLP comparison is documented separately in
[native-mlp-integration](../native-mlp-integration/RESULTS.md).

## Questions and boundaries

| Test | Work we try to remove | What the experiment includes |
| --- | --- | --- |
| Selective feedback | Reading both saved vectors when the next calculation needs one | The existing native two-bank mechanism at width 768, with a deterministic recurrence and both generation stamps |
| Layer-rule hoisting | Repeating identical structural declarations inside each layer condition | Real LN1→QKV and LN2→FC→GELU→projection/residual stages, selecting layers 0 and 11 |
| Preserved-weight normalization | Separately publishing the normalized 768-number vector | An offline precision screen using real reference-derived states and exactly the existing quantized matrix weights |

These tests answer different questions. A native feedback pass is not a GPT-2
layer. An isolated dense stage is not a token. An offline precision simulation
is not a browser measurement. None supplies a new full-model runtime estimate.

## Reproduction

Run from the repository root. Heavy work and browser runs take the shared
`/tmp/gpt2-css-unconventional-experiments.lock` through the wrapper below, so
cooperating experiments do not compete with one another. Other host activity is
not controlled. Existing result directories are evidence; preserve them before
deliberately starting a fresh reproduction.

Selective feedback:

```sh
python3 tools/run_unconventional_isolated.py --label selective-prepare -- uv run tools/benchmark_selective_loop.py prepare
python3 tools/run_unconventional_isolated.py --label selective-gate -- uv run tools/benchmark_selective_loop.py gate --attempt r0
python3 tools/run_unconventional_isolated.py --label selective-timing -- uv run tools/benchmark_selective_loop.py timing --attempt r0
uv run tools/benchmark_selective_loop.py summary --attempt r0
```

The preparation step freezes source snapshots, HTML, CSS, thresholds, and input
definitions in `selective-loop/manifest.json`. The gate stops after a failed
checkpoint and timing requires a matching passing gate. Four fresh-process
pairs run in AB, BA, AB, BA order. The same final vector checks are repeated
after every timed run. Browser page scripts are disabled; the external harness
does not supply iteration ticks or calculated answers.

Layer-rule commands, numerical-screen commands, result files, and acceptance
details are in their respective reports:

- [Selective feedback results](selective-loop/RESULTS.md)
- [Layer-rule results](layer-hoist/RESULTS.md)
- [Normalization protocol](normalization/PROTOCOL.md)
- [Normalization results](normalization/RESULTS.md)

## Ownership and preserved state

The root task owns `tools/benchmark_selective_loop.py` and the combined report.
Two parallel workers own `tools/benchmark_layer_rule_hoist.py` and
`tools/analyze_preserved_weight_normalization.py` respectively. They share the
same repository but use separate artifact directories and serialize heavy runs.
Existing font banks are reused. No large font build or disk cleanup is required.
No production switch is promoted merely because it reduces the number of CSS
declarations, animations, or intermediate values.
