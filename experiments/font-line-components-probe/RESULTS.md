# Independent line-metric components

Three `@font-face` aliases point to the same 2,300-byte variable font. Metric
override descriptors isolate one MVAR line component in each alias:

- `descent-override: 0%; line-gap-override: 0%` exposes ascender.
- `ascent-override: 0%; line-gap-override: 0%` exposes descent.
- `ascent-override: 0%; descent-override: 0%` exposes line gap.

Chrome returned:

| Component | Expected | Actual | Error |
| --- | ---: | ---: | ---: |
| Ascender | -22.75 | -23.4375 | -0.6875 |
| Descender | 3.25 | 3.90625 | 0.65625 |
| Line gap | -10.25 | -9.76562 | 0.48438 |

This proves the three MVAR values are independently accessible through `1lh`
when aliases share the same source file. The error is Chrome line-height's CSS
subpixel rounding.

It does not increase output density per DOM node: one node has only one selected
font face and thus one `lh`. Cycling the three aliases can choose which fourth
metric accompanies `cap/ch/ic`, but still yields four unique outputs per node.
It is useful flexibility, not an improvement over the ROW-axis bank's scaling.

The runtime page contains no JavaScript.
