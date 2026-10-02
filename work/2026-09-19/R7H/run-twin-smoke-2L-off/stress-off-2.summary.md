# stress-off-2 — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.1 s, Run at 5.9 s after nav

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was_2layers.json; prompt token default 15496); ids=[11, 4623, 647, 407, 6646, 6646, 6646, 6646]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10.0 | 10 | 11 | Y | 31 | 16 | 4.1 | 1.7 | 7.5 | 1650 | 1650 |
| 2 | 4.1 | 14 | 4623 | Y | 28 | 14 | 1.4 | 1.5 | 4.6 | 2230 | 2230 |
| 3 | 5.1 | 19 | 647 | Y | 28 | 14 | 1.5 | 1.5 | 4.6 | 2524 | 2524 |
| 4 | 5.1 | 24 | 407 | Y | 28 | 14 | 1.8 | 1.7 | 5.1 | 2768 | 2768 |
| 5 | 4.3 | 29 | 6646 | Y | 25 | 12 | 1.5 | 1.5 | 4.8 | 2745 | 2441 |
| 6 | 5.7 | 34 | 6646 | Y | 31 | 16 | 2.0 | 1.5 | 5.2 | 2691 | 2691 |
| 7 | 4.4 | 39 | 6646 | Y | 28 | 14 | 1.8 | 1.4 | 5.0 | 2914 | 2914 |
| 8 | 5.8 | 44 | 6646 | Y | 28 | 14 | 1.9 | 1.5 | 5.2 | 2910 | 2783 |

linear fit s/token = 7.00 + -0.320·k  (rmse 1.86); tokens 2..8: 4.17 + 0.151·k (rmse 0.66)
  RecalcStyleCount: 27.46 + 0.107·k (rmse 1.88)
  LayoutCount: 13.64 + 0.071·k (rmse 1.25)
  RecalcStyleDuration s: 1.29 + 0.082·k (rmse 0.14)
  LayoutDuration s: 1.58 + -0.009·k (rmse 0.08)
  TaskDuration s: 4.46 + 0.093·k (rmse 0.19)

total 44.5 s for 8 tokens; median 5.1; first 10.0; last 5.8; min 4.1; max 10.0
RSS peak during generation 2914 MB; before run 1046 MB; at end 2783 MB
whole-run CDP deltas: RecalcStyleCount 242, LayoutCount 125, RecalcStyleDuration 20.2 s, LayoutDuration 12.8 s, TaskDuration 47.0 s, Nodes 168973
