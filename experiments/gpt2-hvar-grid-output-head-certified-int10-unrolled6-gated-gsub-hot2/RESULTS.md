# Hot-two six-stage GSUB output-head probe

Scaling decision: **reject**; semantic decision: **pass**. Chrome 153.0.8010.36 ran 1 cold round and 10 paired warm comparisons.

| Metric | Hot-two hybrid | Exact baseline |
| --- | ---: | ---: |
| Cold load median | 59323.1 ms | 57777.5 ms |
| Load + first evaluation median | 64383.5 ms | 60677.7 ms |
| Warm mutation median | 7877.4 ms | 5206.9 ms |
| Composed speedup | **0.66×** | 1.00× |

Across 18 active stages, CSS selected 16 hot-two accepts, one group-0/1 margin fallback, and one direct other-group exact fallback. All active stages and final winners matched exact: true.

The page contains only the focused split-complement GSUB top/runner bank. Groups 0/1 accept at rendered margin >4; every group >=2 directly displays exact. No full 197-group GSUB bank is included, referenced, or requested. The page reuses 963,044 bytes of split-GSUB WOFF2 and the existing exact fonts by relative URL; no fonts were copied or rebuilt.

Generated source is 9,218,974 bytes of HTML, 32,577 bytes of split-bank CSS, and 716,196 bytes of topology CSS. The sources are `gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated`, `gpt2-hvar-grid-output-head-certified-upper-int10-one-step`, and `gsub-split-complement-fine-scorer`.

The robust repeat was not run because hot-two did not beat exact.

The four-bucket gate is empirical for this bank, fixture set, and Chrome build.
