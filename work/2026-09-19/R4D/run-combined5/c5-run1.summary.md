# c5-run1 — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 32.4 s, Run at 34.7 s after nav

ids 8/8 vs reference; ids=[11, 314, 1101, 7926, 11, 475, 314, 1101]

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20.8 | 21 | 11 | Y | 86 | 79 | 8.2 | 3.9 | 19.0 | 3753 | 3753 |
| 2 | 16.8 | 38 | 314 | Y | 83 | 76 | 6.1 | 4.0 | 16.7 | 4404 | 4396 |
| 3 | 16.9 | 55 | 1101 | Y | 83 | 76 | 6.0 | 4.2 | 16.9 | 4589 | 4566 |
| 4 | 17.7 | 72 | 7926 | Y | 83 | 76 | 6.7 | 4.5 | 17.9 | 4636 | 4636 |
| 5 | 18.9 | 91 | 11 | Y | 81 | 74 | 6.6 | 4.9 | 18.3 | 4716 | 4579 |
| 6 | 19.1 | 110 | 475 | Y | 83 | 76 | 6.9 | 5.3 | 19.0 | 4706 | 4557 |
| 7 | 20.4 | 131 | 314 | Y | 83 | 76 | 7.8 | 5.6 | 20.3 | 4567 | 4420 |
| 8 | 20.1 | 151 | 1101 | Y | 79 | 72 | 7.1 | 5.7 | 20.1 | 4833 | 4295 |

linear fit s/token = 17.75 + 0.245·k  (rmse 1.56); tokens 2..8: 15.30 + 0.652·k (rmse 0.39)
  RecalcStyleCount: 84.29 + -0.429·k (rmse 1.39)
  LayoutCount: 77.29 + -0.429·k (rmse 1.39)
  RecalcStyleDuration s: 5.51 + 0.245·k (rmse 0.37)
  LayoutDuration s: 3.35 + 0.308·k (rmse 0.11)
  TaskDuration s: 15.21 + 0.648·k (rmse 0.36)

total 150.8 s for 8 tokens; median 19.0; first 20.8; last 20.1; min 16.8; max 20.8
RSS peak during generation 4833 MB; before run 1829 MB; at end 4295 MB
whole-run CDP deltas: RecalcStyleCount 666, LayoutCount 608, RecalcStyleDuration 57.6 s, LayoutDuration 38.1 s, TaskDuration 150.9 s, Nodes 132170
