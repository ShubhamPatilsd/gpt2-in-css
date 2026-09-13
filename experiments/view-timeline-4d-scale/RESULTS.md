# Four-value two-axis view-timeline transport

One subject can carry four independent numbers in its inline position, width,
block position, and height. Two named view timelines expose cover and entry
progress on both axes, and CSS reconstructs all four numbers.

The scalar probe recovered `23`, `37`, `29`, and `41` with at most `0.0001`
absolute error.

At 3,072 transported values, the equal-capacity scale fixtures measured:

| Transport | Subjects | Timelines / animations | Warm median |
| --- | ---: | ---: | ---: |
| two values on one axis | 1,536 | 1,536 | 298.45 ms |
| four values on two axes | 768 | 1,536 | 284.03 ms |

Halving the subjects improved this synthetic transport by only 4.8%. The
unchanged timeline, animation, and registered-property count dominates. This
is a valid density improvement, but not an order-of-magnitude scaling route.

```sh
/usr/bin/python3 tools/generate_view_timeline_4d_scale.py
node tools/test_view_timeline_4d_probe.mjs
node tools/test_view_timeline_4d_scale.mjs
```
