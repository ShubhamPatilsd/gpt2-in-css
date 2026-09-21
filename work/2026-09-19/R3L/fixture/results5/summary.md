# M1 micro-benchmark summary

Run started 2026-09-21T04:37:03.412Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lat-769 | 1.02 | 2 | 45.0 [45.0–55.4] | 1552 | 1 | 0.7 | 0.6 | 16.1 | 142.8 [138.6–151.4] | 131.6 | 2 | 45.0 | 22.6 | 0.1 | 204 | 0/3 |  |
| lat-font | 1.78 | 2 | 39.4 [36.2–41.2] | 3090 | 1 | 38.4 | 2.7 | 10.2 | 159.0 [149.8–159.9] | 151.8 | 2 | 39.4 | 45.2 | 0.1 | 247 | 0/3 |  |
