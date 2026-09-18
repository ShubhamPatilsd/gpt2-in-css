# Final depth-sixteen point

The same two-coordinate reversible digital cell was extended to sixteen connected
GSUB layers. The direct CSS control consumes its final numeric state directly,
without an unnecessary geometry roundtrip. GSUB pays for native counter input
encoding and anchor/container/typed-number output readback.

For 256 changing outputs per sample, warm medians are:

| Phase | GSUB | Direct CSS | GSUB time reduction |
| --- | ---: | ---: | ---: |
| Repeated states | 6.5 ms | 10.2 ms | 36.3% |
| Unique text | 7.0 ms | 10.2 ms | 31.4% |

All 256 input states remained distinct and exact in all three implementations.
All 16 individual disabled-layer controls prevented final readout, and all 61,440
timed output checks passed. The font has 4,962 glyphs, 33 lookups, 13,868 WOFF2 bytes
and 144,124 TTF bytes. Measurement order alternates, with 40 samples per phase and
the first five omitted from timing summaries.

This is one fresh-process component measurement, not a GPT-2 or dense-matrix
speedup. It demonstrates amortization of native transfers for the specified small
digital circuit. No larger depth or new architecture was tested.

[Full method, earlier depths and corrected baseline history](../RESULTS.md) ·
[Raw measurements](results.json) · [Font/source manifest](reference.json)
