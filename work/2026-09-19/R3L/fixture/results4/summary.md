# M1 micro-benchmark summary

Run started 2026-09-21T04:24:04.049Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lat-font | 1.44 | 2 | 39.0 [37.6–39.7] | 3090 | 1 | 36.9 | 2.6 | 10.3 | 96.9 [95.2–97.2] | 88.8 | 2 | 39.0 | 37.0 | 0.1 | 231 | 0/3 |  |
