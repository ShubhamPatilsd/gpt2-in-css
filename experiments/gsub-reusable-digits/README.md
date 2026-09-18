# Reproduce the shared-digit experiment

Read [RESULTS.md](RESULTS.md) for the results and limits. The retained fonts are
ready to test. Run these commands from the repository root with Node, Playwright,
Chrome and Python/uv available. `CODEX_NODE_MODULES` and `CHROME_PATH` override
the default runtime paths recorded in the harness.

## Check the working widths

The explicit selection excludes the known-failing 256-input font. New report
names keep the original evidence intact.

```sh
python3 tools/run_unconventional_isolated.py --label reused-repro-correctness -- node tools/test_gsub_reusable_digits.mjs --mode correctness --variants reusable-w4,reusable-w16,reusable-w64,retained-w4-sequential,retained-w16-sequential,retained-w64-sequential --output repro-correctness.json
```

This checks every four-input combination, the wider sampled sets, native numeric
readback, dependent consumers, feature controls and marker controls. Timing
requires passed correctness for the exact selected font hashes.

## Repeat the timing comparison

Each invocation starts a fresh browser, uses five warmups and twenty measured
samples, and checks every output. The new 64-input program takes seconds per
256-output update, so these runs take several minutes.

```sh
python3 tools/run_unconventional_isolated.py --label reused-repro-time1 -- node tools/test_gsub_reusable_digits.mjs --mode timing --variants reusable-w4,reusable-w16,reusable-w64,retained-w4-sequential,retained-w16-sequential,retained-w64-sequential --phases unique-text --seed 104729 --correctness-report repro-correctness.json --output repro-timing1.json
python3 tools/run_unconventional_isolated.py --label reused-repro-time2 -- node tools/test_gsub_reusable_digits.mjs --mode timing --variants reusable-w4,reusable-w16,reusable-w64,retained-w4-sequential,retained-w16-sequential,retained-w64-sequential --phases unique-text --seed 130363 --reverse-variants --correctness-report repro-correctness.json --output repro-timing2.json
python3 tools/run_unconventional_isolated.py --label reused-repro-time3 -- node tools/test_gsub_reusable_digits.mjs --mode timing --variants reusable-w4,reusable-w16,reusable-w64,retained-w4-sequential,retained-w16-sequential,retained-w64-sequential --phases unique-text --seed 155921 --correctness-report repro-correctness.json --output repro-timing3.json
```

These commands consistently select fresh text. To reproduce the first retained
run's additional fixed-nonce phase, use `--phases stable-nonce,unique-text` for
the first invocation. That historical phase difference is disclosed in the
report; the published comparison uses fresh-text samples only.

A short separate profile can be run with `--mode profile --profile-warmups 1
--profile-rounds 3`, selecting `reusable-w64,retained-w64-sequential` and supplying
the same correctness gate. Use a new output filename.

## Reproduce the failed wider test

```sh
python3 tools/run_unconventional_isolated.py --label reused-repro-256 -- node tools/test_gsub_reusable_digits.mjs --mode smoke --batch 8 --variants reusable-w256 --output repro-smoke256.json
```

This is expected to fail exact correctness. Do not use it as a timing gate or
claim that building its font establishes successful 256-input arithmetic.

The diagnosis scripts are [diagnose-w256.mjs](diagnose-w256.mjs),
[diagnose-subtables.py](diagnose-subtables.py), and
[diagnose-browser-subtables.mjs](diagnose-browser-subtables.mjs). Run them in that
order under the same isolation wrapper, using Node for the `.mjs` files and
`uv run` for Python. They write their named diagnostic artifacts, so use a copy
of this directory if preserving those exact reports. The Python probe uses the
Homebrew HarfBuzz library at `/opt/homebrew/lib/libharfbuzz.0.dylib`; the earlier
CLI probe also requires `hb-shape`. Their results record hashes and versions.

Rule-pruned diagnostic fonts test table acceptance, not complete arithmetic.
Padding probes retain the original program but do not fix its rejection.

## Regenerate fonts

The compiler is [build_gsub_reusable_digits.py](../../tools/build_gsub_reusable_digits.py).
It writes generated fonts into this experiment directory. To preserve the exact
provided evidence, rebuild in a separate checkout or copy first:

```sh
python3 tools/run_unconventional_isolated.py --label reused-rebuild -- uv run tools/build_gsub_reusable_digits.py --widths 4 16 64 256
```

`--append` adds widths to an existing manifest. The compiler copies the retained
sequential controls from the weighted-sum experiment and records their hashes.
New build timestamps can change font hashes; rerun correctness before timing
new bytes. Do not reuse old correctness reports for a rebuilt font.
