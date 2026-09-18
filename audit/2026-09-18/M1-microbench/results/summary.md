# M1 micro-benchmark summary

Run started 2026-09-18T22:11:49.086Z; Chrome 153.0.8010.48; node v24.19.0; Apple M2 Pro; AC=false; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=1 trigger=class settle=500ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mb4-none-A0-sib | 0.00 | 1 | 0.1 [0.1–0.3] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.8 [1.8–2.0] | 52.3 | 1 | 0.1 | 8.6 | 3/3 |  |
| mb4-fwd-A1000-sib | 0.09 | 1 | 0.2 [0.2–0.2] | 1 | 0 | 0.0 | 0.0 | 0.0 | 2.1 [2.0–2.1] | 52.0 | 1 | 0.2 | 450.6 | 3/3 |  |
| mb4-paused-A1000-sib | 0.09 | 1 | 0.2 [0.2–0.2] | 1 | 0 | 0.0 | 0.0 | 0.3 | 2.4 [2.3–2.5] | 52.3 | 1 | 0.2 | 480.2 | 3/3 |  |
| mb4-static-A1000-sib | 0.05 | 1 | 0.1 [0.1–0.2] | 1 | 0 | 0.0 | 0.0 | 0.0 | 1.9 [1.9–2.2] | 52.1 | 1 | 0.1 | 346.6 | 3/3 |  |
| mb4-fwd-A10000-sib | 0.91 | 1 | 0.8 [0.8–0.9] | 2 | 0 | 0.0 | 0.0 | 0.2 | 5.2 [5.0–5.4] | 52.1 | 1 | 0.8 | 1081.7 | 3/3 |  |
| mb4-paused-A10000-sib | 0.91 | 1 | 0.9 [0.9–0.9] | 2 | 0 | 0.0 | 0.0 | 5.1 | 10.3 [10.0–10.6] | 52.0 | 1 | 0.9 | 1008.8 | 3/3 |  |
| mb4-static-A10000-sib | 0.48 | 1 | 0.3 [0.3–0.3] | 2 | 0 | 0.0 | 0.0 | 0.0 | 3.9 [3.8–4.0] | 52.0 | 1 | 0.3 | 1453.4 | 3/3 |  |
| mb4-fwd-A100000-sib | 9.51 | 1 | 7.4 [6.9–8.2] | 2 | 0 | 0.0 | 0.0 | 2.0 | 35.6 [29.5–36.7] | 52.1 | 1 | 7.4 | 1286.8 | 3/3 |  |
| mb4-paused-A100000-sib | 9.51 | 1 | 7.7 [7.1–7.8] | 2 | 0 | 0.0 | 0.0 | 68.9 | 102.1 [96.6–102.3] | 80.4 | 1 | 7.7 | 1241.4 | 3/3 |  |
| mb4-static-A100000-sib | 5.03 | 1 | 1.7 [1.6–1.8] | 2 | 0 | 0.0 | 0.0 | 0.0 | 19.7 [19.4–20.3] | 52.1 | 1 | 1.7 | 2970.4 | 3/3 |  |
| mb4-none-A0-inh | 0.00 | 1 | 0.1 [0.1–0.2] | 5 | 0 | 0.0 | 0.0 | 0.0 | 1.7 [1.7–1.7] | 52.0 | 1 | 0.1 | 7.1 | 3/3 |  |
| mb4-fwd-A1000-inh | 0.09 | 1 | 5.4 [5.3–6.0] | 1005 | 0 | 0.0 | 0.1 | 0.0 | 7.6 [7.3–8.4] | 51.7 | 1 | 5.4 | 16.3 | 3/3 |  |
| mb4-paused-A1000-inh | 0.09 | 1 | 4.7 [4.6–5.3] | 1005 | 0 | 0.0 | 0.1 | 0.3 | 7.1 [7.1–7.7] | 51.7 | 1 | 4.7 | 18.7 | 3/3 |  |
| mb4-static-A1000-inh | 0.05 | 1 | 2.2 [2.2–2.4] | 1005 | 0 | 0.0 | 0.1 | 0.0 | 3.9 [3.8–4.1] | 51.7 | 1 | 2.2 | 21.1 | 3/3 |  |
| mb4-fwd-A10000-inh | 0.91 | 1 | 55.6 [54.8–56.4] | 10005 | 0 | 0.0 | 0.1 | 0.2 | 65.2 [63.8–65.2] | 61.8 | 1 | 55.6 | 16.4 | 3/3 |  |
| mb4-paused-A10000-inh | 0.91 | 1 | 51.6 [51.0–52.0] | 10005 | 0 | 0.0 | 0.1 | 4.6 | 65.6 [64.7–65.8] | 62.7 | 1 | 51.6 | 17.7 | 3/3 |  |
| mb4-static-A10000-inh | 0.48 | 1 | 21.7 [21.0–22.2] | 10005 | 0 | 0.0 | 0.1 | 0.0 | 24.7 [24.1–25.4] | 52.1 | 1 | 21.7 | 22.3 | 3/3 |  |
| mb4-fwd-A100000-inh | 9.51 | 1 | 595.0 [573.2–611.2] | 100005 | 0 | 0.0 | 0.1 | 1.9 | 676.2 [662.3–695.1] | 657.6 | 1 | 595.0 | 16.0 | 3/3 |  |
| mb4-paused-A100000-inh | 9.51 | 1 | 517.4 [510.1–519.6] | 100005 | 0 | 0.0 | 0.1 | 67.9 | 666.2 [662.3–670.1] | 647.2 | 1 | 517.4 | 18.4 | 3/3 |  |
| mb4-static-A100000-inh | 5.03 | 1 | 229.7 [227.2–232.0] | 100005 | 0 | 0.0 | 0.1 | 0.0 | 244.8 [244.1–250.1] | 230.6 | 1 | 229.7 | 21.9 | 3/3 |  |
