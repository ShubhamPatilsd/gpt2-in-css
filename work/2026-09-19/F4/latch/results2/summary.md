# M1 micro-benchmark summary

Run started 2026-09-19T02:26:08.219Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=class settle=500ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| f4latch-none-sib | 0.00 | 1 | 0.3 [0.1–0.3] | 1 | 0 | 0.0 | 0.0 | 0.0 | 3.7 [3.3–4.1] | 54.1 | 1 | 0.3 | 4.3 | 0.1 | 174 | 3/3 |  |
| f4latch-after-kv-sib | 4.65 | 1 | 49.6 [47.4–51.0] | 13 | 0 | 0.0 | 0.0 | 3.3 | 55.8 [54.4–58.3] | 53.3 | 1 | 49.6 | 93.9 | 0.1 | 202 | 3/3 |  |
| f4latch-after-kv-num-sib | 2.48 | 1 | 35.7 [35.3–37.4] | 13 | 0 | 0.0 | 0.0 | 3.4 | 42.7 [41.2–45.6] | 52.8 | 1 | 35.7 | 69.4 | 0.1 | 175 | 3/3 |  |
| f4latch-after-kv-tiny-sib | 1.54 | 1 | 24.4 [23.1–24.9] | 13 | 0 | 0.0 | 0.0 | 3.6 | 30.4 [30.0–32.4] | 53.2 | 1 | 24.4 | 62.9 | 0.1 | 175 | 3/3 |  |
| f4latch-before-kv-num-sib | 2.54 | 1 | 36.2 [33.8–38.3] | 13 | 0 | 0.0 | 0.0 | 5.8 | 45.7 [42.8–47.3] | 53.0 | 1 | 36.2 | 70.1 | 0.1 | 183 | 3/3 |  |
