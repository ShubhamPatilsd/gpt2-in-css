# Gated 61-stage structural scaling probe

This page expands the certified int10 cascade to the 61-group maximum observed
by the production-range, 24-bucket-per-side corpus screen. It still uses the
current-range generated head and ten browser fixtures, so it tests declarative
structure and lifecycle scaling rather than production-range numeric coverage.

| Metric | 6 stages | 61 stages |
| --- | ---: | ---: |
| HTML | 8.248 MB | 10.730 MB |
| CSS | 5.689 MB | 24.100 MB |
| Cold load + first evaluation | 49.100 s | 199.411 s |
| Warm mutation median | 4.806 s | 5.916 s |
| Warm mutation mean | 4.517 s | 5.359 s |
| Warm mutation range | 3.023-5.862 s | 3.560-7.204 s |
| Active exact groups | 1-3 | 1-3 |
| Final dense GPT-2 winner | 10/10 | 10/10 |

Stage gating works at depth: the browser evaluates only the visible one- to
three-group prefix, correctly reopens deeper branches on later inputs, and
keeps the 61-stage warm median within 23.1% of the six-stage page. The dormant
55-stage suffix is therefore mostly contained once the stylesheet is resident.

Cold scaling fails. Each stage masks every previously visited group with an
ever-longer `min(abs(...))` expression, so value source grows quadratically
with stage count. CSS is 4.24x larger and cold plus first result is 4.06x
slower. The first harness version also crashed at stage 48 because it
incorrectly forced layout on every hidden descendant; the corrected harness
stops at the visible certificate and completes successfully.

Do not ship the naïve 61-stage expansion for one-shot inference. Retain a
shallow gated fast path and either compress visited-set masking, add a compact
fallback, or reserve the full expansion for a recurrent/cached setting.

The follow-up two-bank incremental mask halves CSS to 11.969 MB and preserves
10/10 correctness, but cold plus first result worsens to 228.468 seconds and
warm mean is unchanged. See
`../gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated-linear-mask/RESULTS.md`.

## Reproduce

```sh
GPT2_CERTIFIED_STAGES=61 GPT2_CERTIFIED_GATE=1 \
  make test-gpt2-certified-int10-unrolled-gated
```
