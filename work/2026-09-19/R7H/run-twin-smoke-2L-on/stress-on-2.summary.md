# stress-on-2 — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 1.9 s, Run at 5.7 s after nav

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was_2layers.json; prompt token default 15496); ids=[11, 4623, 647, 407, 6646, 6646, 6646, 6646]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10.3 | 10 | 11 | Y | 36 | 21 | 7.0 | 1.8 | 10.6 | 1920 | 1920 |
| 2 | 5.1 | 15 | 4623 | Y | 28 | 14 | 1.6 | 1.6 | 5.0 | 2226 | 2226 |
| 3 | 4.7 | 20 | 647 | Y | 28 | 14 | 1.6 | 1.5 | 4.7 | 2589 | 2589 |
| 4 | 4.3 | 24 | 407 | Y | 28 | 14 | 1.6 | 1.7 | 5.0 | 2801 | 2766 |
| 5 | 5.8 | 30 | 6646 | Y | 25 | 12 | 2.1 | 1.7 | 5.6 | 2847 | 2092 |
| 6 | 5.2 | 35 | 6646 | Y | 31 | 16 | 2.0 | 1.5 | 5.4 | 3148 | 3148 |
| 7 | 5.8 | 41 | 6646 | Y | 28 | 14 | 1.9 | 1.5 | 5.2 | 3187 | 3099 |
| 8 | 4.6 | 46 | 6646 | Y | 28 | 14 | 2.0 | 1.6 | 5.3 | 3203 | 2774 |

linear fit s/token = 7.49 + -0.389·k  (rmse 1.80); tokens 2..8: 4.74 + 0.068·k (rmse 0.61)
  RecalcStyleCount: 27.46 + 0.107·k (rmse 1.88)
  LayoutCount: 13.64 + 0.071·k (rmse 1.25)
  RecalcStyleDuration s: 1.44 + 0.078·k (rmse 0.16)
  LayoutDuration s: 1.58 + -0.000·k (rmse 0.10)
  TaskDuration s: 4.74 + 0.086·k (rmse 0.26)

total 45.9 s for 8 tokens; median 5.1; first 10.3; last 4.6; min 4.3; max 10.3
RSS peak during generation 3203 MB; before run 1055 MB; at end 2774 MB
whole-run CDP deltas: RecalcStyleCount 242, LayoutCount 125, RecalcStyleDuration 20.7 s, LayoutDuration 13.1 s, TaskDuration 48.2 s, Nodes 168975
