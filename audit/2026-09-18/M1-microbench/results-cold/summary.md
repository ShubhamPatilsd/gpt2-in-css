# M1 micro-benchmark summary

Run started 2026-09-18T22:15:14.789Z; Chrome 153.0.8010.48; node v24.19.0; Apple M2 Pro; AC=true; caffeinate=true; therm: Note: No thermal warning level has been recorded Note: No performance warning level has been recorded Note: No CPU power status has been recorded
trials=3 warmup=0 trigger=inline settle=500ms. Values are medians over trials [min–max] of the traced mutation only.
Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.

| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | verified | err |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mb2-a-var-N0-b0 | 0.00 | 1 | 0.1 [0.1–0.1] | 4 | 0 | 0.0 | 0.0 | 0.0 | 2.4 [2.2–2.4] | 52.1 | 1 | 0.1 | 10.2 | 3/3 |  |
| mb2-a-var-N1000-b200 | 0.26 | 1 | 9.7 [9.5–9.8] | 1004 | 0 | 0.0 | 0.0 | 0.0 | 11.9 [11.9–12.2] | 51.4 | 1 | 9.7 | 26.2 | 3/3 |  |
| mb2-a-var-N1000-b2000 | 2.40 | 1 | 81.3 [80.9–82.0] | 1004 | 0 | 0.0 | 0.1 | 0.0 | 83.7 [83.4–84.2] | 81.8 | 1 | 81.3 | 29.5 | 3/3 |  |
| mb2-a-var-N10000-b200 | 2.56 | 1 | 119.3 [118.1–120.7] | 10004 | 0 | 0.0 | 0.1 | 0.0 | 136.9 [136.1–138.5] | 120.3 | 1 | 119.3 | 21.5 | 3/3 |  |
| mb2-a-var-N10000-b2000 | 23.92 | 1 | 880.2 [877.6–880.8] | 10004 | 0 | 0.0 | 0.1 | 0.0 | 1027.2 [1023.3–1028.5] | 880.9 | 1 | 880.2 | 27.2 | 3/3 |  |
| mb2-a-var-N40000-b200 | 10.30 | 1 | 399.7 [399.4–405.2] | 40004 | 0 | 0.0 | 0.1 | 0.0 | 408.8 [408.8–414.4] | 400.6 | 1 | 399.7 | 25.8 | 3/3 |  |
| mb2-a-lit-N1000-b2000 | 1.23 | 1 | 40.7 [40.6–40.7] | 1004 | 0 | 0.0 | 0.1 | 0.0 | 43.0 [43.0–43.1] | 52.0 | 1 | 40.7 | 30.3 | 3/3 |  |
| mb2-a-lit-N10000-b2000 | 12.30 | 1 | 399.9 [399.3–400.3] | 10004 | 0 | 0.0 | 0.1 | 0.0 | 402.8 [402.3–403.3] | 400.6 | 1 | 399.9 | 30.8 | 3/3 |  |
| mb2-a-lit-N40000-b200 | 5.82 | 1 | 233.5 [232.7–234.3] | 40004 | 0 | 0.0 | 0.1 | 0.0 | 240.7 [240.5–241.3] | 234.5 | 1 | 233.5 | 24.9 | 3/3 |  |
| mb5-lit-short-K10000 | 0.83 | 1 | 7.7 [7.1–7.9] | 2 | 0 | 0.0 | 0.0 | 0.0 | 9.8 [9.2–9.9] | 52.1 | 1 | 7.7 | 106.5 | 0/3 |  |
| mb5-lit-calc-K10000 | 3.89 | 1 | 49.6 [49.5–50.4] | 2 | 0 | 0.0 | 0.0 | 0.0 | 77.2 [75.7–77.5] | 52.1 | 1 | 49.6 | 78.4 | 0/3 |  |
| mb5-calc-var16-K10000 | 3.89 | 1 | 78.3 [78.2–78.6] | 2 | 0 | 0.0 | 0.0 | 0.0 | 80.5 [80.3–80.6] | 78.8 | 1 | 78.3 | 49.7 | 3/3 |  |
| mb5-calc-var1-K10000 | 3.89 | 1 | 71.1 [71.1–71.5] | 2 | 0 | 0.0 | 0.0 | 0.0 | 91.7 [90.4–93.2] | 72.6 | 1 | 71.1 | 54.7 | 3/3 |  |
| mb5-calc-varw-K10000 | 19.00 | 1 | 161.9 [161.0–163.7] | 2 | 0 | 0.0 | 0.0 | 0.0 | 163.8 [162.9–165.5] | 162.3 | 1 | 161.9 | 117.3 | 0/3 |  |
| mb5-func16-K10000 | 3.89 | 1 | 197.3 [196.9–198.0] | 2 | 0 | 0.0 | 0.0 | 0.0 | 210.0 [209.2–212.7] | 198.6 | 1 | 197.3 | 19.7 | 3/3 |  |
| mb5-unreg-var16-K10000 | 3.21 | 1 | 38.4 [37.7–38.6] | 2 | 0 | 0.0 | 0.0 | 0.0 | 40.6 [39.7–40.8] | 51.8 | 1 | 38.4 | 83.6 | 3/3 |  |
