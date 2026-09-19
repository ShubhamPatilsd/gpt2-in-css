# M1 micro-benchmark summary

Run started 2026-09-19T00:49:24.967Z; Chrome 153.0.8010.48; node v22.23.1; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=class settle=500ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| f5latch-none-sib | 0.00 | 1 | 0.1 [0.1–0.4] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.4 [1.4–4.3] | 50.7 | 1 | 0.1 | 9.1 | 0.1 | 175 | 3/3 |  |
| f5latch-transition-sib | 9.95 | 1 | 105.7 [104.4–107.1] | 13 | 0 | 0.0 | 0.0 | 12.0 | 123.1 [120.9–125.2] | 121.9 | 1 | 105.7 | 94.1 | 0.0 | 324 | 2/2 | 1 |
| f5latch-paused-sib | 10.50 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-static-sib | 9.93 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-static-cv-sib | 9.93 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-none-inh | 0.00 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-transition-inh | 9.95 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-paused-inh | 10.50 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-static-inh | 9.93 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
| f5latch-static-cv-inh | 9.93 | - | - [-] | - | - | - | - | - | - [-] | - | - | - | - | - | - | 0/0 | 3 |
