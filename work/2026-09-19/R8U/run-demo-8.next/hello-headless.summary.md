# hello-headless — 8/8 tokens captured (capacity 8), stopReason=token-limit, trigger=keyboard, load 2.0 s, Run at 4.3 s after nav; seed None T None

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U/../R7B/reference_hello_s0_t0_cap8.json; prompt tokens 1, prefill epochs 1..0 expected -1); ids=[11, 314, 1101, 7926, 11, 475, 314, 1101]; slots beyond the stop set: []
NEW tokens 8/8 identical
first mismatching epoch: None; mismatches at []

r7b state: {"--noise-col": "14", "--seed": "6", "--temp": "0", "--r7b-n": "1", "--epoch": "8", "--head-input-epoch": "8", "headFvsTail": "19,\"X0L8\" -1,\"X0L9\" 9,\"X0LA\" -23,\"X0LB\" 2,\"SEED\" 14,\"TEMP\" 0", "bodySeed": "6", "bodyTemp": "0", "bodyPlayState": "paused", "readout": "\"greedy (T = 0) \u00b7 \" \"seed 6\"", "status": "\"Complete \u2022 8 new tokens\"", "pgDisplay": "none", "pgTok": "\"new token 8 of 8\"", "complete": ["r7b-complete-0:null", "r7b-complete-1:null", "r7b-complete-2:null", "r7b-complete-3:null", "r7b-complete-4:null"]}

| epoch | kind | s/epoch | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB | RSS at capture |
|---:|---|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | new 1 | 19.7 | 20 | 11 | Y | 76 | 67 | 8.8 | 4.0 | 17.3 | 3363 | 3363 |
| 2 | new 2 | 14.2 | 34 | 314 | Y | 71 | 64 | 6.3 | 3.7 | 14.0 | 3590 | 3590 |
| 3 | new 3 | 17.1 | 51 | 1101 | Y | 69 | 62 | 7.5 | 4.5 | 16.7 | 3640 | 2856 |
| 4 | new 4 | 19.0 | 70 | 7926 | Y | 71 | 64 | 8.9 | 5.2 | 18.9 | 3150 | 2799 |
| 5 | new 5 | 18.1 | 88 | 11 | Y | 71 | 64 | 8.6 | 4.7 | 18.1 | 3364 | 2481 |
| 6 | new 6 | 20.1 | 108 | 475 | Y | 71 | 64 | 10.1 | 5.1 | 20.0 | 3405 | 2967 |
| 7 | new 7 | 20.8 | 129 | 314 | Y | 71 | 64 | 10.5 | 5.2 | 20.8 | 3480 | 2305 |
| 8 | new 8 | 21.7 | 151 | 1101 | Y | 67 | 61 | 10.7 | 5.1 | 21.3 | 3428 | 2536 |
new-token epochs 2..8: s/epoch = 13.13 + 1.114·epoch (rmse 0.92)
total 150.6 s for 8 epochs; median 19.3; first 19.7; last 21.7; min 14.2; max 21.7
RSS peak during generation 3640 MB; before run 1767 MB; at end 2536 MB
whole-run CDP deltas: RecalcStyleCount 577, LayoutCount 519, RecalcStyleDuration 74.3 s, LayoutDuration 37.6 s, TaskDuration 151.3 s, Nodes 132762
