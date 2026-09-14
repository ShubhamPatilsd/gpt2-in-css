# CSS-native grouped MLP browser probe

## Result

**DO NOT RETAIN for student integration.** The gate requires numeric correctness and a warm mutation median at or below 80 ms.

| Metric | Result |
| --- | ---: |
| Numeric checks | fail |
| Maximum absolute error | 2.8326 font units |
| Cold load | 88.50 ms |
| Warm median | 1.30 ms |
| Warm p90 | 1.50 ms |
| Warm maximum | 1.50 ms |
| Runtime font bytes | 105,756 |
| DOM elements | 139 |
| Glyphs per output | 12 |
| Geometry outputs | 128 |
| Preactivation/transport boxes | 0 |
| Chrome | 153.0.8010.36 |

Configuration: 12 groups × 32 selected axes from one 96-dimension inherited input list, 128 outputs, 8 timed rounds. Two complete output banks were checked against a reference that includes avar2 F2DOT14 and HVAR integer-delta quantization. The timed region forces every output width but returns only one checksum.

For context, an earlier saved exact full-MLP profile was 251 ms. This is not a paired benchmark: it was not collected in this run under matched conditions.
