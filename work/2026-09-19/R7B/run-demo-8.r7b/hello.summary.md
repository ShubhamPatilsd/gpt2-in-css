# hello — 8/8 tokens captured (capacity 8), stopReason=token-limit, trigger=keyboard, load 1.7 s, Run at 3.9 s after nav; seed None T None

ids 8/8 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B/reference_hello_s0_t0_cap8.json; prompt tokens 1, prefill epochs 1..0 expected -1); ids=[11, 314, 1101, 7926, 11, 475, 314, 1101]; slots beyond the stop set: []
NEW tokens 8/8 identical
first mismatching epoch: None; mismatches at []

r7b state: {"--noise-col": "14", "--seed": "6", "--temp": "0", "--r7b-n": "1", "--epoch": "8", "--head-input-epoch": "8", "headFvsTail": "19,\"X0L8\" -1,\"X0L9\" 9,\"X0LA\" -23,\"X0LB\" 2,\"SEED\" 14,\"TEMP\" 0", "bodySeed": "6", "bodyTemp": "0", "bodyPlayState": "paused", "readout": "\"greedy (T = 0) \u00b7 \" \"seed 6\"", "status": "\"Complete \u2022 8 new tokens\"", "pgDisplay": "block", "pgTok": "\"new token 8 of 8\"", "complete": ["r7b-complete-0:null", "r7b-complete-1:null", "r7b-complete-2:null", "r7b-complete-3:null", "r7b-complete-4:null"]}

| epoch | kind | s/epoch | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB | RSS at capture |
|---:|---|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | new 1 | 16.6 | 17 | 11 | Y | 76 | 67 | 7.7 | 3.4 | 14.8 | 3770 | 3770 |
| 2 | new 2 | 12.8 | 29 | 314 | Y | 71 | 64 | 5.7 | 3.4 | 12.8 | 4619 | 4619 |
| 3 | new 3 | 13.3 | 43 | 1101 | Y | 71 | 64 | 6.1 | 3.4 | 13.3 | 4783 | 4783 |
| 4 | new 4 | 13.9 | 57 | 7926 | Y | 71 | 64 | 6.4 | 3.7 | 13.8 | 4988 | 4918 |
| 5 | new 5 | 14.0 | 71 | 11 | Y | 71 | 64 | 6.4 | 3.7 | 13.9 | 4985 | 4913 |
| 6 | new 6 | 14.6 | 85 | 475 | Y | 71 | 64 | 6.7 | 4.0 | 14.6 | 5324 | 5324 |
| 7 | new 7 | 15.2 | 100 | 314 | Y | 71 | 64 | 6.8 | 4.3 | 15.1 | 5517 | 5517 |
| 8 | new 8 | 16.0 | 116 | 1101 | Y | 66 | 59 | 7.0 | 4.0 | 15.5 | 5609 | 4379 |
new-token epochs 2..8: s/epoch = 11.74 + 0.503·epoch (rmse 0.19)
total 116.3 s for 8 epochs; median 14.3; first 16.6; last 16.0; min 12.8; max 16.6
RSS peak during generation 5609 MB; before run 1737 MB; at end 4379 MB
whole-run CDP deltas: RecalcStyleCount 578, LayoutCount 519, RecalcStyleDuration 55.0 s, LayoutDuration 30.0 s, TaskDuration 116.3 s, Nodes 132748
