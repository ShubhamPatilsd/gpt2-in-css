# Reproduce the partitioned-digit experiment

Read [PLAN.md](PLAN.md) for the questions and acceptance gates,
[RESULTS.md](RESULTS.md) for the completed measurements,
[PROGRESS_AUDIT.md](PROGRESS_AUDIT.md) for the independent audit and model-level
history, and [NEXT_DIRECTIONS.md](NEXT_DIRECTIONS.md) for the proposed next tests.

The runtime calculations use HTML/CSS and fonts. The external Playwright driver
publishes raw inputs, observes answers and checks an independent oracle. It does
not supply products, partial sums or model intermediates. Font loading and the
external oracle are outside timing; native encoding, calculation, numerical
readback and the dependent consumer remain inside.

From the repository root, using the existing fixtures:

```sh
python3 tools/run_unconventional_isolated.py --label partitioned-main-gate -- node tools/test_gsub_partitioned_digits.mjs --mode correctness --widths 4,16,64 --output repro-correctness-main.json
python3 tools/run_unconventional_isolated.py --label partitioned256-gate -- node tools/test_gsub_partitioned_digits.mjs --mode correctness --widths 256 --output repro-correctness-256.json
python3 tools/run_unconventional_isolated.py --label partitioned-main-timing -- node tools/test_gsub_partitioned_digits.mjs --mode timing --widths 4,16,64 --batch 32 --correctness-reports repro-correctness-main.json --output repro-timing-main.json
python3 tools/run_unconventional_isolated.py --label partitioned256-timing -- node tools/test_gsub_partitioned_digits.mjs --mode timing --widths 256 --batch 16 --correctness-reports repro-correctness-256.json --output repro-timing-256.json
```

Each timing invocation launches three fresh browser processes. The harness
requires a completed passing correctness report for every selected backend and
the exact font hash. Both timing batches use the same raw inputs among their
compared backends. The shared-output condition at N64 has sixteen identical
coefficient rows, not sixteen distinct matrix rows. Per-row nonce text differs.

Summarize only completed passing reports:

```sh
python3 tools/summarize_gsub_partitioned_digits.py --gates experiments/gsub-partitioned-digits/repro-correctness-main.json experiments/gsub-partitioned-digits/repro-correctness-256.json --timings experiments/gsub-partitioned-digits/repro-timing-main.json experiments/gsub-partitioned-digits/repro-timing-256.json --output experiments/gsub-partitioned-digits/repro-summary.json
```

The default browser is `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`;
the harness supports `CHROME_PATH`. Playwright comes from the existing Codex
dependency directory or `CODEX_NODE_MODULES`. Python font builders use `uv` with
their declared FontTools/Brotli dependencies. Offline arithmetic checks require
the existing Homebrew `hb-shape` command. No custom browser build is required.

## Optional rebuild

These commands replace this experiment's generated fixtures, so use a copy if
the exact recorded hashes must be preserved. Any rebuilt font requires new
correctness gates before timing.

```sh
python3 tools/run_unconventional_isolated.py --label partitioned-build4 -- uv run tools/build_gsub_partitioned_digits.py --widths 4 --offline-check --exhaustive-four
python3 tools/run_unconventional_isolated.py --label partitioned-build16-64 -- uv run tools/build_gsub_partitioned_digits.py --append --widths 16 64 --offline-check
python3 tools/run_unconventional_isolated.py --label partitioned-build256 -- uv run tools/build_gsub_partitioned_digits.py --append --widths 256 --layouts packed --offline-check
python3 tools/run_unconventional_isolated.py --label partitioned-hvar -- uv run tools/build_partitioned_hvar_controls.py
python3 tools/run_unconventional_isolated.py --label partitioned-static -- uv run tools/build_static_advance_sum.py
```

`reference.json` describes the new digit programs; `hvar-reference.json` describes
the matched variable fonts; `static-reference.json` describes the product-width
control. Retained position-specific and globally reused digit fonts are read
from the preceding experiment directories, without rewriting them.

The 256-axis HVAR control uses its TTF because the generated WOFF2 package failed
Chrome's WOFF2-to-SFNT conversion. Both files, the original manifest and the
format diagnostic remain in this directory. The change affects loading format,
not its numerical program. All fonts are loaded before timing.

## Preserved attempts and protocol changes

The first smoke attempts encountered the HVAR-256 WOFF2 loading failure. The
first large shared-row and N256 correctness groups exceeded their 180-second
budgets without numerical mismatches. These reports remain failures; they are
not used as passing gates for timing.

The repaired shared-row gate uses 64 stratified vectors. The repaired N256 gate
uses 663 vectors, including both extrema independently at every coordinate.
Single-row gates at N4/16/64 retain their original case sets. Main timings use
32 outputs per sample and N256 timings use 16, chosen before timing to bound
runtime. Report the different batch sizes instead of comparing their batch
times as if they were equal work.

Source snapshots preserve the earlier budget attempts, the repaired main gate,
and the final harness. Adding the bounded N256 case selection was the only
change after the repaired main gate started; main fixture arithmetic and
correctness selection stayed unchanged. Timing uses the final snapshot.

The separate [AAT support probe](../aat-support-probe/RESULTS.md) tests a possible
streaming font alternative. It is a capability rejection in this Chrome,
not part of the arithmetic performance comparison.
