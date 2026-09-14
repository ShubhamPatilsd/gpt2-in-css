# Certified row-wise int11 upper head, ±266 range

The same outward Cauchy-bound encoding used by the int10 head was applied to
the ten-shard row-wise int11 variant. Chrome matches all offline upper tokens
and groups.

| Metric | Result |
| --- | ---: |
| Cold load + first evaluation | 104.802 s |
| Later fixture mutations | 3.168-4.109 s; 3.254 s median |
| Upper token/group agreement | 11/11 |
| Dense winner in first group | 9/11 |
| Font bytes | 58.20 MB |
| Shaped glyphs | 502,570 |

The precision benefit is real, but the coarse scan is too expensive for
one-shot inference: certified int10 takes 36.66 seconds cold and its reusable
exact stages cost roughly 1.5-2 seconds each. Int11's 68-second extra cold
cost is much larger than its expected reduction in follow-up stages.

Reject as the default. Retain for a warm recurrent page, where its production
range and 24-bucket proof budget need median/p95/max only 2/6/22 groups.

## Reproduce

```sh
make test-gpt2-certified-rowwise11-upper-head
```
