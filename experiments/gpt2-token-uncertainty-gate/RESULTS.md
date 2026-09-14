# Fixed-group token uncertainty gate

## Result

The fixed group-0 browser graph **passed** all 10 certified fixtures. Its 256 lightweight carriers activated only **3–15 exact rows** (mean **7.6**) out of 256, and every browser active set exactly matched the offline uncertainty oracle.

The gate implements `upper >= L`, where `L=max(lower)`. A synthetic equality case remained active, a value strictly below `L` remained inactive, and equal rounded buckets selected the lower token ID. The browser's gated winner and rounded 1/256 bucket matched the normal full 256-row exact grid on **10/10** fixtures. Full-grid winners also matched the offline global-int16 oracle; browser bucket deltas were **-6 to 6 buckets**, within the retained 8-bucket fine allowance. Browser/offline `L` deltas were **-5.399 to 2.541 buckets**, within the 19-bucket coarse allowance.

**Scaling decision: reject-scaling.** Semantics pass, but the gated page does not robustly beat the full exact page under the preregistered criterion that median, mean, and p95 must all be lower.

| Warm mutation metric | Gated | Full 256-row exact |
| --- | ---: | ---: |
| Samples | 50 | 50 |
| Median | 165.400 ms | 160.650 ms |
| Mean | 166.610 ms | 160.514 ms |
| p95 | 179.900 ms | 172.400 ms |

Median full/gated ratio: **0.97×**. Values below 1 mean the gated graph was slower. This is a local warm-mutation measurement of one fixed group, not a whole-vocabulary latency claim.

The screen used 5 rounds / 50 mutations per mode. To balance page order, each round ran one ten-fixture mode batch and alternated whether gated or full ran first. Every individual timing and the exact per-round order are retained in `browser-results.json`.

## Contract

- Coarse interval: row-wise signed int10 center plus/minus `l2(h) * l2(w16-w10)`.
- Outward browser slack: 19 coarse buckets plus 8 fine buckets.
- Exact scorer: the retained twelve-glyph global-int16 row and rounded-1/256/lower-token tie encoding.
- Scope: fixed group 0 only. No 197-group router or six-stage cascade is integrated.
- Browser: 153.0.8010.36.
- Request failures, HTTP errors, page errors, and server errors: **0**.

Raw measurements and every per-fixture active set are in `browser-results.json`; the offline oracle is in `reference.json`.

## Reproduce

```sh
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_token_uncertainty_gate_probe.py
node tools/test_token_uncertainty_gate_probe.mjs
```
