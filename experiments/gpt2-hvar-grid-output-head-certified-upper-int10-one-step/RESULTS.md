# Certified int10 plus one exact group

The certified upper head feeds its selected `--group` directly into the
existing 256-node global-int16 fine scorer. The browser therefore performs one
full low-precision scan followed by one exact selected-group scan, with no
runtime JavaScript.

| Metric | Result |
| --- | ---: |
| Cold load + first evaluation | 59.992 s |
| Later fixture mutations | 2.639-5.306 s; 3.507 s median |
| Selected-group int16 winner agreement | 10/10 |
| Dense winner recovered after one group | 8/10 |

The fine winner is reliable, but its decoded score differs from the NumPy
global-int16 bucket by -6 to +6 buckets across these fixtures. Winner routing
and proof-grade score comparison are therefore separate concerns: the latter
needs an explicit browser-realization error allowance.

## Reproduce

```sh
make test-gpt2-certified-int10-one-step-cascade
```
