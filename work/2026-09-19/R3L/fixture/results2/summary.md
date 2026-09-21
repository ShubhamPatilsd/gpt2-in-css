# M1 micro-benchmark summary

Run started 2026-09-21T04:10:51.684Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lat-769 | 1.02 | 2 | 46.4 [46.3–46.7] | 1552 | 1 | 0.5 | 0.5 | 12.9 | 134.9 [133.9–138.3] | 128.5 | 2 | 46.4 | 21.9 | 0.0 | 204 | 0/3 |  |
| lat-font | 1.44 | 2 | 37.4 [36.3–37.5] | 3089 | 1 | 35.4 | 2.3 | 7.9 | 89.1 [88.4–92.0] | 83.5 | 2 | 37.4 | 38.6 | 0.1 | 243 | 0/3 |  |
