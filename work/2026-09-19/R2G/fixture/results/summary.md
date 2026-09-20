# M1 micro-benchmark summary

Run started 2026-09-20T22:03:48.423Z; Chrome 153.0.8010.48; node v24.19.0; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=attr settle=600ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| pa-demo | 1.14 | 2 | 31.3 [31.2–31.4] | 381 | 1 | 0.1 | 0.1 | 0.1 | 33.7 [33.6–35.1] | 52.7 | 2 | 31.3 | 36.3 | 0.0 | 174 | 3/3 |  |
| pa-nofill | 0.67 | 2 | 5.1 [5.1–5.2] | 381 | 1 | 0.1 | 0.1 | 0.1 | 7.3 [7.2–7.3] | 52.6 | 2 | 5.1 | 129.7 | 0.0 | 175 | 3/3 |  |
| pa-corefill | 0.78 | 2 | 27.0 [26.8–27.3] | 381 | 1 | 0.1 | 0.1 | 0.1 | 29.2 [29.1–29.3] | 52.6 | 2 | 27.0 | 28.9 | 0.0 | 175 | 3/3 |  |
| pa-fixed | 1.16 | 2 | 7.8 [7.7–8.0] | 381 | 1 | 0.1 | 0.1 | 0.1 | 10.2 [9.9–10.4] | 52.6 | 2 | 7.8 | 147.5 | 0.0 | 174 | 3/3 |  |
| pa-nohas | 1.12 | 2 | 3.1 [3.0–3.2] | 292 | 1 | 0.1 | 0.1 | 0.1 | 5.4 [5.2–5.4] | 52.1 | 2 | 3.1 | 363.8 | 0.0 | 175 | 3/3 |  |
| pa-nohas-nosvg | 1.09 | 1 | 2.0 [2.0–2.0] | 3 | 1 | 0.0 | 0.1 | 0.0 | 4.0 [4.0–4.1] | 52.6 | 1 | 2.0 | 557.0 | 0.0 | 174 | 3/3 |  |
| pa-demo-anims | 1.63 | 2 | 43.0 [42.3–44.5] | 2126 | 1 | 0.1 | 0.2 | 6.1 | 56.8 [55.3–57.5] | 55.5 | 2 | 43.0 | 37.8 | 0.0 | 200 | 3/3 |  |
| pa-nohas-anims | 1.60 | 2 | 12.1 [11.9–14.3] | 2125 | 1 | 0.1 | 0.2 | 6.0 | 25.2 [24.0–30.2] | 52.6 | 2 | 12.1 | 132.6 | 0.1 | 202 | 3/3 |  |
| svg-demo | 1.14 | 1 | 13.5 [13.4–18.7] | 579 | 1 | 0.1 | 0.1 | 0.0 | 16.0 [15.5–22.9] | 50.9 | 1 | 13.5 | 84.2 | 0.1 | 175 | 3/3 |  |
| svg-nohas | 1.12 | 1 | 5.2 [2.6–7.5] | 579 | 1 | 0.1 | 0.1 | 0.0 | 9.6 [5.4–11.7] | 53.4 | 1 | 5.2 | 214.9 | 0.1 | 175 | 3/3 |  |
| svg-plain | 1.10 | 1 | 4.7 [4.2–5.0] | 3 | 1 | 0.1 | 0.1 | 0.0 | 8.8 [8.3–9.1] | 53.2 | 1 | 4.7 | 232.4 | 0.1 | 174 | 3/3 |  |
| rd-change | 1.25 | 2 | 40.5 [37.0–43.1] | 19209 | 1 | 0.5 | 0.6 | 12.2 | 121.7 [115.7–122.3] | 112.6 | 2 | 40.5 | 30.8 | 0.1 | 226 | 3/3 |  |
| rd-change-split | 1.26 | 2 | 39.3 [35.9–40.0] | 19209 | 1 | 0.5 | 0.7 | 13.6 | 91.2 [91.0–97.5] | 82.3 | 2 | 39.3 | 32.1 | 0.1 | 228 | 3/3 |  |
| rd-change-nosvg | 1.22 | 2 | 44.3 [35.8–48.2] | 18632 | 1 | 0.5 | 0.6 | 12.5 | 126.6 [114.9–128.1] | 118.3 | 2 | 44.3 | 27.6 | 0.1 | 225 | 3/3 |  |
| rd-change-latch | 1.27 | 2 | 39.5 [38.4–39.8] | 19209 | 1 | 0.5 | 0.5 | 10.1 | 114.0 [113.6–119.6] | 107.4 | 2 | 39.5 | 32.1 | 0.1 | 226 | 3/3 |  |
| rd-unrelated | 1.25 | 1 | 6.5 [6.4–6.6] | 2 | 0 | 0.0 | 0.0 | 6.4 | 18.8 [13.9–20.7] | 50.8 | 1 | 6.5 | 193.1 | 0.1 | 204 | 3/3 |  |
| rd-unrelated-split | 1.26 | 1 | 4.1 [3.9–4.6] | 2 | 0 | 0.0 | 0.0 | 6.6 | 15.5 [15.0–17.3] | 53.2 | 1 | 4.1 | 304.9 | 0.1 | 204 | 3/3 |  |
