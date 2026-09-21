# M1 micro-benchmark summary

Run started 2026-09-21T04:15:48.526Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lat-769 | 1.02 | 2 | 60.6 [45.8–64.9] | 1552 | 1 | 0.6 | 0.7 | 17.0 | 159.0 [140.7–165.8] | 149.8 | 2 | 60.6 | 16.8 | 0.1 | 204 | 0/3 |  |
| lat-font | 1.44 | 2 | 38.9 [34.6–49.1] | 3089 | 1 | 37.7 | 2.8 | 10.3 | 97.7 [92.9–108.8] | 91.7 | 2 | 38.9 | 37.1 | 0.1 | 245 | 0/3 |  |
