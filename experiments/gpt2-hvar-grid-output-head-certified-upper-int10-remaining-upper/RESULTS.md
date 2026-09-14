# Masked remaining-upper-group readback

After the first exact group, 197 anchor carriers mask that selected group and
reuse the already-computed coarse group widths. A second 197-node match stage
recovers the largest remaining upper-bound group. No token is rescored.

| Metric | Result |
| --- | ---: |
| Added group-probe elements | 399 |
| Cold load + first evaluation | 57.437 s |
| Later fixture mutations | 2.488-4.492 s; 3.431 s median |
| Remaining-group agreement | 10/10 |
| Raw first-step certificates | 4/10 |

The remaining group is exact on all fixtures. Its decoded bucket differs from
the floating-point oracle by -2 to +8 buckets, reinforcing the need for a
conservative font/layout realization allowance before treating the raw gap as
a proof.

This is the key cascade scaling trick: later search steps duplicate only small
group geometry, not the 50,257-token coarse head.

## Reproduce

```sh
make test-gpt2-certified-int10-remaining-upper
```
