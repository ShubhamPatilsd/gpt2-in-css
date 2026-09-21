# R3L fixture anatomy (traced mutation window; all trials)

| variant | trial | style passes (elements:ms) | ULT ms | Layout ms | PrePaint ms | PaintLifecycle incl / self ms | animate step ms | Animation b / e | frames | busy ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lat-769 | 0 | 1550:38.4 2:7.5 | 45.8 | 0.5 | 0.5 | 67.5 / 67.2 | 9.0 | 769 / 0 | 2 | 0.0 |
| lat-769 | 1 | 1550:52.2 2:8.3 | 60.6 | 0.6 | 0.7 | 70.3 / 70.2 | 11.5 | 769 / 0 | 2 | 0.0 |
| lat-769 | 2 | 1550:56.3 2:8.6 | 64.9 | 0.7 | 0.7 | 71.3 / 71.3 | 11.6 | 769 / 0 | 2 | 0.0 |
| lat-font | 0 | 3087:30.8 2:8.1 | 38.9 | 40.8 | 2.5 | 3.1 / 1.9 | 7.0 | 2 / 0 | 2 | 0.0 |
| lat-font | 1 | 3087:41.5 2:7.6 | 49.1 | 37.6 | 2.8 | 2.0 / 1.9 | 10.1 | 2 / 0 | 2 | 0.0 |
| lat-font | 2 | 3087:27.1 2:7.5 | 34.6 | 37.7 | 2.8 | 2.2 / 2.1 | 9.3 | 2 / 0 | 2 | 0.0 |

## Medians

| variant | ULT ms | Layout ms | PrePaint ms | PaintLifecycle self ms | animate ms | Animation b / e | frames | busy ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lat-769 | 60.6 | 0.6 | 0.7 | 70.2 | 11.5 | 769 / 0 | 2 | 0.0 |
| lat-font | 38.9 | 37.7 | 2.8 | 1.9 | 9.3 | 2 / 0 | 2 | 0.0 |
