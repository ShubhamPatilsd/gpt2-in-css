# R3L fixture anatomy (traced mutation window; all trials)

| variant | trial | style passes (elements:ms) | ULT ms | Layout ms | PrePaint ms | PaintLifecycle incl / self ms | animate step ms | Animation b / e | frames | busy ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lat-769 | 0 | 1550:38.0 2:8.3 | 46.4 | 0.5 | 0.5 | 67.9 / 67.6 | 8.0 | 769 / 0 | 2 | 0.0 |
| lat-769 | 1 | 1550:38.4 2:8.0 | 46.3 | 0.5 | 0.5 | 68.0 / 68.0 | 8.0 | 769 / 0 | 2 | 0.0 |
| lat-769 | 2 | 1550:38.7 2:8.0 | 46.7 | 0.5 | 0.5 | 67.6 / 67.5 | 7.3 | 769 / 0 | 2 | 0.0 |
| lat-font | 0 | 3087:30.3 2:7.1 | 37.4 | 35.6 | 2.3 | 2.8 / 1.6 | 8.3 | 2 / 0 | 2 | 0.0 |
| lat-font | 1 | 3087:29.3 2:7.0 | 36.3 | 35.4 | 2.3 | 1.6 / 1.5 | 6.7 | 2 / 0 | 2 | 0.0 |
| lat-font | 2 | 3087:29.9 2:7.6 | 37.5 | 35.1 | 2.6 | 2.0 / 1.9 | 7.0 | 2 / 0 | 2 | 0.0 |

## Medians

| variant | ULT ms | Layout ms | PrePaint ms | PaintLifecycle self ms | animate ms | Animation b / e | frames | busy ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lat-769 | 46.4 | 0.5 | 0.5 | 67.6 | 8.0 | 769 / 0 | 2 | 0.0 |
| lat-font | 37.4 | 35.4 | 2.3 | 1.6 | 7.0 | 2 / 0 | 2 | 0.0 |
