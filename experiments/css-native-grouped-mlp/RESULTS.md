# CSS-native grouped GPT-2 MLP feasibility

## Outcome

This was the configured full experiment run. The configured three-gate decision is **FAIL**. The
architecture removes the 3,072-scalar external activation boundary: twelve
independent 256-input/256-hidden groups each produce 768 outputs, and only the
summed 768-vector crosses into geometry.

| Held-out test metric | Restricted-teacher initialization | Trained |
| --- | ---: | ---: |
| MLP output RMSE | 0.749789 | 0.558111 |
| MLP output relative RMSE | 65.144% | 48.490% |
| MLP output cosine | 0.761364 | 0.883115 |
| MLP output maximum error | 13.945328 | 5.550550 |
| Complete block relative RMSE | 36.471% | 27.147% |
| Complete block cosine | 0.932696 | 0.964352 |
| Complete block maximum error | 13.945328 | 5.550550 |

## Decision gates

| Gate | Result | Status |
| --- | ---: | :---: |
| Held-out MLP-output relative RMSE <= 5% | 48.490% | FAIL |
| Held-out complete-block relative RMSE <= 2% | 27.147% | FAIL |
| Browser projection estimate <= 80 ms | 53.83 ms | PASS |

The browser number is **an estimate, not a measurement of this architecture**.
It multiplies the existing 256-axis square-font warm median by 12. It is
optimistic because each proposed group has 768 output rows, and it excludes
font scheduling, group summation, and the final 768-value geometry handoff. A
simple 3x output-row sensitivity is
161.50 ms.
The browser gate must therefore be confirmed with a generated-font browser
probe before an architecture decision can rely on it.

## Corpus and isolation

The run used 768 block-0 post-attention `ln_2`
inputs: 383
uniform-random token contexts and
385
local-text contexts. Train/validation/test token-sequence hashes are disjoint,
and local text files are assigned to only one split. Split-isolation checks
passed.

## Initialization and training

Hidden units were balanced at exactly 256 per group by alternating deterministic
co-clustering on squared `c_fc` input-weight energy. Each group then retained
its 256 highest aggregate-energy input coordinates. Restricted checkpoint
`c_fc`/`c_proj` weights and biases were copied directly before Adam fine-tuning.
The selected coordinates retain
50.567% of
`c_fc` weight energy for their assigned hidden units.

Training used 300 steps on `mps` with a
batch size of 64. Exact teacher targets use the checkpoint's
full 768->3,072->768 MLP and GPT-2 tanh GELU. See `results.json` for per-split
metrics, all coordinate/unit assignments, optimizer history, and provenance.

## Reproduce

```sh
CSS_GROUPED_MLP_SMOKE=1 uv run --with torch --with numpy python tools/analyze_css_native_grouped_mlp.py
```

For the default full run, omit `CSS_GROUPED_MLP_SMOKE=1`. Sample count, optimizer
steps, context lengths, batch sizes, seed, learning rate, and device are exposed
through the environment variables documented at the top of the script.
