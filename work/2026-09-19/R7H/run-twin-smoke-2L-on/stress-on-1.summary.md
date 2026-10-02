# stress-on-1 — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 1.9 s, Run at 6.0 s after nav

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was_2layers.json; prompt token default 15496); ids=[11, 4623, 647, 407, 6646, 6646, 6646, 6646]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 9.8 | 10 | 11 | Y | 31 | 16 | 3.9 | 1.6 | 7.4 | 1594 | 1546 |
| 2 | 4.3 | 14 | 4623 | Y | 26 | 12 | 1.6 | 1.5 | 4.9 | 2194 | 2157 |
| 3 | 6.1 | 20 | 647 | Y | 28 | 14 | 2.0 | 1.9 | 5.9 | 2206 | 2059 |
| 4 | 5.7 | 26 | 407 | Y | 31 | 16 | 1.9 | 1.6 | 5.2 | 2734 | 2734 |
| 5 | 4.8 | 31 | 6646 | Y | 28 | 14 | 1.5 | 1.6 | 4.7 | 2919 | 2843 |
| 6 | 4.7 | 35 | 6646 | Y | 31 | 16 | 1.9 | 1.5 | 5.1 | 3144 | 3144 |
| 7 | 5.0 | 40 | 6646 | Y | 25 | 12 | 1.6 | 1.5 | 4.7 | 3171 | 2537 |
| 8 | 4.5 | 45 | 6646 | Y | 28 | 14 | 1.9 | 1.5 | 5.1 | 3027 | 2972 |

linear fit s/token = 7.66 + -0.458·k  (rmse 1.53); tokens 2..8: 5.42 + -0.084·k (rmse 0.67)
  RecalcStyleCount: 28.14 + 0.000·k (rmse 2.48)
  LayoutCount: 13.64 + 0.071·k (rmse 1.78)
  RecalcStyleDuration s: 1.76 + 0.000·k (rmse 0.22)
  LayoutDuration s: 1.74 + -0.026·k (rmse 0.13)
  TaskDuration s: 5.44 + -0.074·k (rmse 0.41)

total 44.8 s for 8 tokens; median 4.9; first 9.8; last 4.5; min 4.3; max 9.8
RSS peak during generation 3171 MB; before run 1060 MB; at end 2972 MB
whole-run CDP deltas: RecalcStyleCount 243, LayoutCount 125, RecalcStyleDuration 19.6 s, LayoutDuration 13.2 s, TaskDuration 47.0 s, Nodes 168975
