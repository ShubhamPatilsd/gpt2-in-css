# M1 micro-benchmark summary

Run started 2026-09-20T23:22:31.537Z; Chrome 153.0.8010.48; node v24.19.0; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| cap-demo | 1.72 | 2 | 37.2 [34.8–37.7] | 385 | 1 | 0.1 | 0.2 | 10.0 | 57.7 [52.2–58.6] | 54.5 | 2 | 37.2 | 46.3 | 0.1 | 204 | 3/3 |  |
| cap-nohas | 1.70 | 1 | 5.5 [4.5–8.3] | 295 | 1 | 0.1 | 0.1 | 7.7 | 20.6 [18.0–26.0] | 51.7 | 1 | 5.5 | 309.0 | 0.1 | 200 | 3/3 |  |
| cap-noheld | 1.70 | 2 | 33.9 [31.6–36.4] | 91 | 1 | 0.0 | 0.1 | 7.9 | 51.1 [47.6–54.6] | 51.7 | 2 | 33.9 | 50.2 | 0.1 | 201 | 3/3 |  |
| cap-noanims | 1.54 | 2 | 43.9 [40.1–50.2] | 385 | 1 | 0.1 | 0.1 | 4.7 | 56.3 [47.8–61.1] | 52.9 | 2 | 43.9 | 35.0 | 0.1 | 185 | 3/3 |  |
| cap-nobanks | 1.14 | 2 | 31.0 [29.7–42.1] | 91 | 1 | 0.0 | 0.1 | 0.1 | 35.5 [33.3–46.6] | 52.6 | 2 | 31.0 | 36.7 | 0.1 | 175 | 3/3 |  |
| real-cap-nocore | 5.93 | 2 | 20.9 [17.8–25.6] | 111 | 1 | 0.0 | 0.2 | 4.1 | 31.6 [28.4–37.8] | 52.7 | 2 | 20.9 | 284.6 | 0.1 | 299 | 3/3 |  |
