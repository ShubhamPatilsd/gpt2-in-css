# stress-off-1 — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.6 s, Run at 6.4 s after nav

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was_2layers.json; prompt token default 15496); ids=[11, 4623, 647, 407, 6646, 6646, 6646, 6646]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 11.1 | 11 | 11 | Y | 31 | 16 | 4.3 | 1.7 | 7.9 | 1609 | 1602 |
| 2 | 4.3 | 15 | 4623 | Y | 29 | 14 | 1.6 | 1.5 | 4.8 | 2179 | 2179 |
| 3 | 5.5 | 21 | 647 | Y | 28 | 14 | 1.7 | 1.5 | 5.0 | 2513 | 2371 |
| 4 | 4.8 | 26 | 407 | Y | 29 | 14 | 1.6 | 1.5 | 4.8 | 2655 | 2577 |
| 5 | 5.0 | 31 | 6646 | Y | 28 | 14 | 1.8 | 1.5 | 5.0 | 2939 | 2840 |
| 6 | 5.0 | 36 | 6646 | Y | 29 | 14 | 1.8 | 1.5 | 5.0 | 2962 | 2752 |
| 7 | 5.2 | 41 | 6646 | Y | 28 | 14 | 1.9 | 1.6 | 5.1 | 2829 | 2829 |
| 8 | 4.5 | 45 | 6646 | Y | 28 | 14 | 1.9 | 1.5 | 5.2 | 2969 | 2942 |

linear fit s/token = 8.00 + -0.516·k  (rmse 1.98); tokens 2..8: 4.89 + 0.003·k (rmse 0.43)
  RecalcStyleCount: 28.96 + -0.107·k (rmse 0.53)
  LayoutCount: 14.00 + 0.000·k (rmse 0.00)
  RecalcStyleDuration s: 1.50 + 0.049·k (rmse 0.04)
  LayoutDuration s: 1.48 + 0.004·k (rmse 0.04)
  TaskDuration s: 4.70 + 0.055·k (rmse 0.08)

total 45.4 s for 8 tokens; median 5.0; first 11.1; last 4.5; min 4.3; max 11.1
RSS peak during generation 2969 MB; before run 681 MB; at end 2942 MB
whole-run CDP deltas: RecalcStyleCount 245, LayoutCount 125, RecalcStyleDuration 20.6 s, LayoutDuration 12.7 s, TaskDuration 47.6 s, Nodes 168973
