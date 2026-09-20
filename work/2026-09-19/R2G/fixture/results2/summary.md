# M1 micro-benchmark summary

Run started 2026-09-20T22:08:59.073Z; Chrome 153.0.8010.48; node v24.19.0; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| pa-demo-anims-locked | 1.63 | 2 | 33.9 [33.6–33.9] | 381 | 1 | 0.1 | 0.1 | 4.4 | 43.3 [42.1–44.3] | 52.7 | 2 | 33.9 | 47.9 | 0.1 | 181 | 3/3 |  |
| pa-nohas-anims-locked | 1.60 | 2 | 3.3 [3.0–3.9] | 292 | 1 | 0.1 | 0.1 | 4.5 | 13.7 [13.1–14.0] | 53.3 | 2 | 3.3 | 490.6 | 0.1 | 178 | 3/3 |  |
