# Twelve-block flat-MLP run

Chrome 153.0.8010.48, one-token context, real GPT-2-small block weights,
9-bit quantized matrix rows, and the existing flat view-timeline MLP backend.
Runtime pages contain no JavaScript.

## Result

| Execution | Warm result | Cold/load result | Final residual error | Verdict |
|---|---:|---:|---:|---|
| One connected CSS graph | 8.442 s median | 217.286 s | 10.359 RMSE | Invalid |
| Twelve preloaded block pages, 11 explicit vector transfers | 9.388 s median | 22.616 s total preload | 0.045-0.074 RMSE | Valid staged run |

The connected page settles and is faster once loaded, but its output is wrong.
The deep inherited dependency graph does not preserve the intended block-to-block
state through all twelve layers. Its timing must not be quoted as valid inference.

The staged run executes the same twelve block implementations sequentially and
passes each 768-value result into the next preloaded page. Three measured runs
after warmup were 10.096 s, 9.387 s, and 9.388 s. Applying the real final
LayerNorm and tied GPT-2 embedding head offline gives token 11 (`,`), matching
the quantized reference winner. Final LayerNorm and vocabulary-head time are not
included in the 9.388 s measurement.

Median per-block times in the staged run were:

| Block | Time |
|---:|---:|
| 0 | 655.1 ms |
| 1 | 869.2 ms |
| 2 | 833.4 ms |
| 3 | 826.7 ms |
| 4 | 853.2 ms |
| 5 | 813.7 ms |
| 6 | 850.7 ms |
| 7 | 868.6 ms |
| 8 | 803.7 ms |
| 9 | 809.6 ms |
| 10 | 726.6 ms |
| 11 | 807.5 ms |

This is context length one. It does not measure or validate the earlier
context-16 extrapolation.

Raw reports: `browser-results.json` and `staged-browser-results.json`.
