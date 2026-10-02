# hello-headless — 8/8 tokens captured (capacity 8), stopReason=token-limit, trigger=keyboard, load 2.6 s, Run at 5.0 s after nav; seed None T None

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B/reference_hello_s0_t0_cap8.json; prompt tokens 1, prefill epochs 1..0 expected -1); ids=[11, 314, 1101, 7926, 11, 475, 314, 1101]; slots beyond the stop set: []
NEW tokens 8/8 identical
first mismatching epoch: None; mismatches at []

r7b state: {"--noise-col": "14", "--seed": "6", "--temp": "0", "--r7b-n": "1", "--epoch": "8", "--head-input-epoch": "8", "headFvsTail": "19,\"X0L8\" -1,\"X0L9\" 9,\"X0LA\" -23,\"X0LB\" 2,\"SEED\" 14,\"TEMP\" 0", "bodySeed": "6", "bodyTemp": "0", "bodyPlayState": "paused", "readout": "\"greedy (T = 0) \u00b7 \" \"seed 6\"", "status": "\"Complete \u2022 8 new tokens\"", "pgDisplay": "none", "pgTok": "\"new token 8 of 8\"", "complete": ["r7b-complete-0:null", "r7b-complete-1:null", "r7b-complete-2:null", "r7b-complete-3:null", "r7b-complete-4:null"]}

| epoch | kind | s/epoch | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB | RSS at capture |
|---:|---|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | new 1 | 24.9 | 25 | 11 | Y | 74 | 65 | 10.9 | 5.1 | 21.7 | 3396 | 3396 |
| 2 | new 2 | 19.3 | 44 | 314 | Y | 71 | 64 | 8.6 | 4.8 | 19.3 | 4148 | 4148 |
| 3 | new 3 | 23.0 | 67 | 1101 | Y | 71 | 64 | 10.7 | 5.5 | 22.4 | 4258 | 3973 |
| 4 | new 4 | 22.7 | 90 | 7926 | Y | 71 | 64 | 10.6 | 5.8 | 22.6 | 4060 | 3616 |
| 5 | new 5 | 24.5 | 114 | 11 | Y | 71 | 64 | 11.0 | 6.7 | 24.5 | 4220 | 3649 |
| 6 | new 6 | 25.6 | 140 | 475 | Y | 71 | 64 | 12.6 | 6.4 | 25.6 | 4336 | 4111 |
| 7 | new 7 | 26.1 | 166 | 314 | Y | 69 | 62 | 11.2 | 7.8 | 25.8 | 4380 | 3888 |
| 8 | new 8 | 28.1 | 194 | 1101 | Y | 69 | 63 | 11.5 | 9.1 | 28.0 | 4199 | 4024 |
new-token epochs 2..8: s/epoch = 17.79 + 1.279·epoch (rmse 0.86)
total 194.2 s for 8 epochs; median 24.7; first 24.9; last 28.1; min 19.3; max 28.1
RSS peak during generation 4380 MB; before run 1734 MB; at end 4024 MB
whole-run CDP deltas: RecalcStyleCount 577, LayoutCount 518, RecalcStyleDuration 91.0 s, LayoutDuration 51.3 s, TaskDuration 195.0 s, Nodes 132750
