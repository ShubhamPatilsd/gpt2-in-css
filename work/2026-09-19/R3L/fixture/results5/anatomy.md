# R3L fixture anatomy (traced mutation window; all trials)

| variant | trial | style passes (elements:ms) | ULT ms | Layout ms | PrePaint ms | PaintLifecycle incl / self ms | animate step ms | Animation b / e | frames | busy ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lat-769 | 0 | 1550:36.6 2:8.4 | 45.0 | 0.5 | 0.6 | 68.7 / 68.7 | 10.7 | 769 / 0 | 2 | 0.0 |
| lat-769 | 1 | 1550:47.9 2:7.5 | 55.4 | 0.8 | 0.5 | 68.2 / 68.1 | 10.6 | 769 / 0 | 2 | 0.0 |
| lat-769 | 2 | 1550:37.0 2:7.9 | 45.0 | 0.7 | 0.6 | 69.7 / 69.7 | 11.1 | 769 / 0 | 2 | 0.0 |
| lat-font | 0 | 3088:31.2 2:8.3 | 39.4 | 41.9 | 2.7 | 58.8 / 58.7 | 7.1 | 2 / 0 | 2 | 0.0 |
| lat-font | 1 | 3088:32.4 2:8.7 | 41.2 | 37.8 | 2.9 | 58.5 / 58.4 | 10.5 | 2 / 0 | 2 | 0.0 |
| lat-font | 2 | 3088:27.8 2:8.4 | 36.2 | 38.4 | 2.7 | 58.0 / 57.9 | 7.5 | 2 / 0 | 2 | 0.0 |

## Medians

| variant | ULT ms | Layout ms | PrePaint ms | PaintLifecycle self ms | animate ms | Animation b / e | frames | busy ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lat-769 | 45.0 | 0.7 | 0.6 | 68.7 | 10.7 | 769 / 0 | 2 | 0.0 |
| lat-font | 39.4 | 38.4 | 2.7 | 58.4 | 7.5 | 2 / 0 | 2 | 0.0 |
