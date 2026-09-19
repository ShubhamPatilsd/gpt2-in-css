# M1 micro-benchmark summary

Run started 2026-09-19T02:19:42.043Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=class settle=500ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| f4latch-none-sib | 0.00 | 1 | 0.1 [0.1–0.1] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.3 [1.3–2.6] | 52.8 | 1 | 0.1 | 11.1 | 0.0 | 174 | 3/3 |  |
| f4latch-before-sib | 4.95 | 1 | 37.2 [36.8–37.9] | 15 | 0 | 0.0 | 0.0 | 3.7 | 42.7 [42.6–43.9] | 52.6 | 1 | 37.2 | 133.3 | 0.1 | 225 | 3/3 |  |
| f4latch-after-sib | 4.84 | 1 | 33.6 [33.4–33.6] | 15 | 0 | 0.0 | 0.0 | 1.9 | 37.1 [37.1–37.2] | 52.7 | 1 | 33.6 | 144.2 | 0.1 | 210 | 3/3 |  |
| f4latch-before-kv-sib | 4.71 | 1 | 35.4 [35.2–35.7] | 13 | 0 | 0.0 | 0.0 | 2.6 | 40.1 [39.4–40.7] | 52.7 | 1 | 35.4 | 133.0 | 0.0 | 211 | 3/3 |  |
| f4latch-after-kv-sib | 4.65 | 1 | 32.1 [32.0–32.4] | 13 | 0 | 0.0 | 0.0 | 1.4 | 34.9 [34.9–35.6] | 52.6 | 1 | 32.1 | 145.1 | 0.0 | 202 | 3/3 |  |
