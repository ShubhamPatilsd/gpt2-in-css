# M1 micro-benchmark summary

Run started 2026-09-21T03:36:49.282Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lat-769 | 1.02 | 2 | 45.9 [45.7–46.5] | 1552 | 1 | 0.5 | 0.5 | 12.9 | 135.1 [133.9–138.0] | 128.4 | 2 | 45.9 | 22.2 | 0.0 | 204 | 0/3 |  |
| lat-385-p2 | 1.05 | 2 | 35.0 [34.3–35.4] | 1552 | 1 | 0.6 | 0.5 | 10.9 | 113.0 [111.9–113.1] | 107.0 | 2 | 35.0 | 30.0 | 0.0 | 200 | 0/3 |  |
| lat-257-p3 | 1.09 | 3 | 36.1 [34.8–36.3] | 1554 | 1 | 0.5 | 0.5 | 10.0 | 112.8 [109.9–112.8] | 154.7 | 3 | 36.1 | 30.2 | 0.0 | 202 | 0/3 |  |
| lat-769-split8 | 1.02 | 2 | 55.7 [54.4–57.1] | 1589 | 1 | 0.6 | 0.5 | 12.6 | 138.3 [138.1–138.3] | 132.0 | 2 | 55.7 | 18.3 | 0.0 | 221 | 0/3 |  |
| lat-none | 1.00 | 2 | 24.0 [24.0–24.3] | 1553 | 1 | 1.0 | 0.9 | 10.2 | 156.3 [156.2–157.4] | 151.0 | 2 | 24.0 | 41.4 | 0.0 | 198 | 3/3 |  |
