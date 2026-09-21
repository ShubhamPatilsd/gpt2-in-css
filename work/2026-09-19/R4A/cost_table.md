| design | K | regions/font | raw MB/font (region list + HVAR deltas + avar2) | raw GB / 12 layers | (glyph,region,axis) evals per layer | Fontations time per layer at 1–3 ns | cached-scalar bound (regions×axes + glyphs×regions) |
|---|---:|---:|---|---:|---:|---:|---:|
| 4×768 | 32 | 26,113 | 161 (120 + 38 + 2.4) | 7.7 | 62 G | 62–185 s | 0.16–0.48 s |
| 4×768 | 48 | 38,401 | 236 (177 + 57 + 2.4) | 11.3 | 91 G | 91–272 s | 0.24–0.71 s |
| 4×768 | 64 | 50,689 | 312 (234 + 76 + 2.4) | 15.0 | 120 G | 120–359 s | 0.31–0.93 s |
| 12×256 | 32 | 9,729 | 58 (45 + 13 + 0.8) | 8.4 | 69 G | 69–207 s | 0.18–0.54 s |
| 12×256 | 48 | 13,825 | 83 (64 + 19 + 0.8) | 12.0 | 98 G | 98–294 s | 0.25–0.76 s |
| 12×256 | 64 | 17,921 | 109 (83 + 25 + 0.8) | 15.6 | 127 G | 127–381 s | 0.33–0.99 s |
| 12×256 two-level | 32 | 9,729 | 71 (45 + 25 + 0.8) | 10.2 | 138 G | 138–414 s | 0.27–0.81 s |
| 12×256 two-level | 48 | 13,825 | 102 (64 + 38 + 0.8) | 14.7 | 196 G | 196–588 s | 0.38–1.15 s |
| 12×256 two-level | 64 | 17,921 | 134 (83 + 50 + 0.8) | 19.3 | 254 G | 254–762 s | 0.50–1.49 s |

Probe calibration: matrix-scaling 768 font = 768 glyph rows × 768 regions × 768 axes = 0.453 G evals → 0.462–1.352 s (1.0–3.0 ns); 256-axis: 16.8 M → 7–15 ms (0.4–0.9 ns); 257-axis: 17 M → 25–43 ms (1.5–2.5 ns). Today's proj stage for comparison: 12 fonts × 768 glyphs × 512 regions × 256 axes = 1.2 G evals (original backend).
