# hello-headless — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.6 s, Run at 4.8 s after nav

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4C/reference_ids_32.json; prompt token default 15496); ids=[11, 314, 1101, 7926, 11, 475, 314, 1101]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 17.8 | 18 | 11 | Y | 78 | 69 | 10.4 | 4.1 | 18.5 | 2666 | 2270 |
| 2 | 16.3 | 34 | 314 | Y | 69 | 62 | 7.3 | 4.1 | 15.8 | 2594 | 2194 |
| 3 | 17.7 | 52 | 1101 | Y | 71 | 64 | 8.8 | 4.6 | 17.9 | 2833 | 2041 |
| 4 | 20.2 | 72 | 7926 | Y | 73 | 66 | 11.4 | 4.8 | 20.9 | 3333 | 3333 |
| 5 | 20.3 | 92 | 11 | Y | 67 | 60 | 9.5 | 4.8 | 18.7 | 3271 | 2902 |
| 6 | 18.8 | 111 | 475 | Y | 73 | 66 | 9.4 | 5.6 | 19.7 | 3236 | 2824 |
| 7 | 19.4 | 130 | 314 | Y | 71 | 64 | 9.7 | 4.8 | 18.9 | 3440 | 2808 |
| 8 | 20.6 | 151 | 1101 | Y | 67 | 60 | 9.5 | 5.8 | 20.6 | 3217 | 2501 |

linear fit s/token = 16.80 + 0.462·k  (rmse 1.11); tokens 2..8: 16.37 + 0.534·k (rmse 1.18)
  RecalcStyleCount: 71.21 + -0.214·k (rmse 2.74)
  LayoutCount: 64.21 + -0.214·k (rmse 2.74)
  RecalcStyleDuration s: 8.21 + 0.235·k (rmse 1.23)
  LayoutDuration s: 3.75 + 0.235·k (rmse 0.36)
  TaskDuration s: 16.24 + 0.537·k (rmse 1.41)

total 151.0 s for 8 tokens; median 19.1; first 17.8; last 20.6; min 16.3; max 20.6
RSS peak during generation 3440 MB; before run 840 MB; at end 2501 MB
whole-run CDP deltas: RecalcStyleCount 573, LayoutCount 513, RecalcStyleDuration 76.1 s, LayoutDuration 38.5 s, TaskDuration 151.9 s, Nodes 132290
