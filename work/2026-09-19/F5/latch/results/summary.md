# M1 micro-benchmark summary

Run started 2026-09-19T01:07:28.072Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=class settle=500ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| f5latch-none-sib | 0.00 | 1 | 0.1 [0.1–0.1] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.4 [1.4–1.6] | 51.9 | 1 | 0.1 | 10.5 | 0.1 | 173 | 3/3 |  |
| f5latch-transition-sib | 9.95 | 1 | 104.4 [104.0–106.9] | 13 | 0 | 0.0 | 0.0 | 12.4 | 122.5 [121.2–125.9] | 120.6 | 1 | 104.4 | 95.3 | 0.0 | 324 | 3/3 |  |
| f5latch-paused-sib | 10.50 | 1 | 0.1 [0.1–0.1] | 1 | 0 | 0.0 | 0.0 | 6.2 | 8.3 [8.3–8.4] | 51.8 | 1 | 0.1 | 89782.9 | 0.1 | 320 | 3/3 |  |
| f5latch-static-sib | 9.93 | 1 | 0.1 [0.1–0.1] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.5 [1.5–1.5] | 51.7 | 1 | 0.1 | 96446.7 | 0.1 | 228 | 3/3 |  |
| f5latch-static-cv-sib | 9.93 | 1 | 0.1 [0.1–0.1] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.5 [1.5–1.6] | 51.8 | 1 | 0.1 | 100332.2 | 0.0 | 206 | 3/3 |  |
| f5latch-none-inh | 0.00 | 1 | 0.1 [0.1–0.2] | 5 | 0 | 0.0 | 0.0 | 0.0 | 1.6 [1.5–1.7] | 51.8 | 1 | 0.1 | 6.7 | 0.0 | 175 | 3/3 |  |
| f5latch-transition-inh | 9.95 | 1 | 105.9 [105.6–105.9] | 17 | 0 | 0.0 | 0.0 | 12.4 | 122.9 [122.5–123.1] | 122.2 | 1 | 105.9 | 94.0 | 0.0 | 324 | 3/3 |  |
| f5latch-paused-inh | 10.50 | 1 | 37.2 [36.8–38.7] | 17 | 0 | 0.0 | 0.1 | 5.5 | 44.9 [44.7–47.1] | 51.8 | 1 | 37.2 | 282.6 | 0.0 | 326 | 3/3 |  |
| f5latch-static-inh | 9.93 | 1 | 94.8 [93.6–95.9] | 17 | 0 | 0.0 | 0.1 | 0.0 | 103.7 [101.8–106.6] | 95.7 | 1 | 94.8 | 104.7 | 0.0 | 266 | 3/3 |  |
| f5latch-static-cv-inh | 9.93 | 1 | 0.2 [0.2–0.2] | 5 | 1 | 0.0 | 0.1 | 0.0 | 1.6 [1.6–1.7] | 50.9 | 1 | 0.2 | 61700.4 | 0.0 | 206 | 3/3 |  |
