# mem8-3 — 8/8 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.6 s, Run at 5.1 s after nav

ids 8/8 vs reference (R5A/reference_ids_8.json; prompt token default 15496); ids=[11, 314, 1101, 7926, 11, 475, 314, 1101]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18.4 | 18 | 11 | Y | 218 | 67 | 7.8 | 4.3 | 16.4 | 3268 | 3268 |
| 2 | 13.8 | 32 | 314 | Y | 227 | 64 | 5.4 | 4.2 | 13.8 | 3829 | 3238 |
| 3 | 14.3 | 47 | 1101 | Y | 359 | 64 | 5.7 | 4.6 | 14.4 | 4220 | 4029 |
| 4 | 15.1 | 62 | 7926 | Y | 371 | 64 | 6.1 | 4.9 | 15.0 | 4265 | 4029 |
| 5 | 16.2 | 78 | 11 | Y | 503 | 64 | 6.5 | 5.9 | 16.7 | 4209 | 4078 |
| 6 | 19.8 | 98 | 475 | Y | 513 | 62 | 9.1 | 6.2 | 20.0 | 4218 | 2268 |
| 7 | 19.7 | 117 | 314 | Y | 647 | 64 | 7.1 | 6.9 | 18.3 | 4277 | 4259 |
| 8 | 21.4 | 139 | 1101 | Y | 595 | 60 | 7.5 | 8.3 | 21.0 | 4164 | 2071 |

linear fit s/token = 13.71 + 0.806·k  (rmse 2.24); tokens 2..8: 10.34 + 1.367·k (rmse 0.87)
  RecalcStyleCount: 133.93 + 65.071·k (rmse 48.37)
  LayoutCount: 65.64 + -0.500·k (rmse 1.25)
  RecalcStyleDuration s: 4.57 + 0.436·k (rmse 0.93)
  LayoutDuration s: 2.63 + 0.645·k (rmse 0.38)
  TaskDuration s: 10.83 + 1.240·k (rmse 1.07)

total 138.8 s for 8 tokens; median 17.3; first 18.4; last 21.4; min 13.8; max 21.4
RSS peak during generation 4277 MB; before run 1681 MB; at end 2071 MB
whole-run CDP deltas: RecalcStyleCount 3486, LayoutCount 512, RecalcStyleDuration 57.6 s, LayoutDuration 45.4 s, TaskDuration 140.1 s, Nodes 132338
