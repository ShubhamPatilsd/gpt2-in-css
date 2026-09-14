# HVAR virtual-base probe

## Result

Chrome 153 accumulates all HVAR regions before applying the lower range clamp.
An effective base far above the TrueType `uint16` base field therefore works.

| Case | Physical base | Positive bias | Negative contribution | Expected | Chrome, bias first | Chrome, negative first |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Small | 1,000 | 30,000 | -20,000 | 11,000 | 11,000 | 11,000 |
| Crosses uint16 | 65,000 | 30,000 | -50,000 | 45,000 | 45,000 | 45,000 |
| Virtual 301k | 1,000 | 300,000 | -290,000 | 11,000 | 11,000 | 11,000 |
| Virtual 493k | 1,000 | 491,505 | -450,000 | 42,505 | 42,504.7 | 42,504.7 |

The final 0.3-design-unit discrepancy in the largest case is ordinary layout
fixed-point rounding at a 10 px font size. Both deliberately preserved region
orders agree.

## Implication

The worst real GPT-2 128-axis shard has an L1 coefficient sum of 480,923. A
physical base at or below 65,535 plus at most thirteen always-on +32,767 bias
regions can cover that excursion. The 128 signed input axes use 256 regions;
the extra bias axes keep the font well below the already established 256-axis
limit. This makes one exact int16 plane per shard structurally possible and can
reduce a score row from twelve glyphs to six.

Raw measurements are in `browser-results.json`.

## Reproduce

```sh
uv run --with fonttools --with brotli python tools/build_hvar_virtual_base_probe.py
node tools/test_hvar_virtual_base_probe.mjs
```
