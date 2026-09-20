# M1 micro-benchmark summary

Run started 2026-09-20T23:39:16.933Z; Chrome 153.0.8010.48; node v24.19.0; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| real-cap | 7.35 | 2 | 33.6 [33.6–68.0] | 111 | 1 | 0.8 | 0.4 | 47.0 | 115.8 [107.4–144.4] | 129.2 | 2 | 33.6 | 218.4 | 0.0 | 494 | 3/3 |  |
| real-adv | 7.35 | 1 | 34.2 [34.0–36.7] | 400 | 1 | 0.1 | 0.2 | 26.4 | 82.3 [81.2–83.7] | 79.4 | 1 | 34.2 | 214.7 | 0.0 | 494 | 3/3 |  |
| real-cap-nocore | 5.93 | 2 | 16.0 [14.1–16.3] | 111 | 1 | 0.0 | 0.1 | 2.7 | 23.6 [23.3–24.9] | 52.7 | 2 | 16.0 | 369.8 | 0.1 | 299 | 3/3 |  |
