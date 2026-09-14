# Gated 16-stage coverage/latency probe

The production-range realized-coordinate screen certifies 94.6% of 1,024
states within 16 int10 groups, versus 79.0% within six. This fixture measures
the browser cost of that higher-coverage cutoff while the ten local fixtures
still activate only one to three stages.

| Metric | 6 stages | 16 stages |
| --- | ---: | ---: |
| Corpus coverage | 79.0% | **94.6%** |
| HTML | 8.248 MB | 8.697 MB |
| CSS | 5.689 MB | 7.417 MB |
| Cold load + first evaluation | 49.100 s | 86.942 s |
| Warm mutation median | 4.806 s | 5.634 s |
| Warm mutation mean | 4.517 s | 5.176 s |
| Warm mutation range | 3.023-5.862 s | 3.415-7.015 s |
| Final dense GPT-2 winner | 10/10 | 10/10 |

Six stages is the latency choice. Sixteen gains 15.6 percentage points of
corpus coverage, but cold plus first result rises 77.1% and warm median rises
17.2% in these single runs even though the active prefix is identical.

Sixteen stages is defensible only when a 5.4% fallback rate matters more than
one-shot latency. The default architecture should keep the six-stage gated fast
path and make the remaining 21% explicit; a deployment prioritizing autonomous
coverage can choose 16 stages plus a rare tail fallback.

## Reproduce

```sh
GPT2_CERTIFIED_STAGES=16 make test-gpt2-certified-int10-unrolled-gated
```
