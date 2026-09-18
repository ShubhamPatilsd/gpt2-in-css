# Isolating the font-to-CSS reader

This experiment compares the same input updates with and without the machinery
that turns a font's final width into a CSS number. It is one part of the
[follow-up plan](../gsub-width-followups/PLAN.md).

## Conditions

At 4, 16 and 64 inputs, test the existing sequential GSUB, tree GSUB and HVAR
fonts. Each receives signed raw inputs from -8 through 7 and calculates
`F = 2*sum(weight[i]*input[i])+1`, with repeating weights `[3,-2,5,1]`.

- **Source:** force and check the source width. There is no reader in this page.
- **Full:** add an anchor-size receiver, a size container and a dependent width
  consuming the recovered numerical answer. Force and check that final width.

Each pair uses separate pages and browser contexts. Input vectors, input write
calls, nonce, output count and number of measured reads match. The full/source
difference measures the effect of adding reader DOM and dependencies under this
fixture. The source-only path does not provide a reusable CSS number.

Two additional diagnostic pairs start with an externally prepared answer:

- **Precomputed font:** choose an ordinary glyph whose width is `8192+F`.
- **Precomputed CSS:** set a CSS width to `8192+F`.

Both still receive every raw input write, plus the answer property. Within each
pair those writes match. These controls do not calculate the answer in the
browser. Their own source/full differences probe the reader with a cheap source;
subtracting them from a computing font is not an exact decomposition of costs.

Direct CSS computes the same expression and consumes the numerical answer
directly. It provides a complete computing baseline without forcing CSS through
an unnecessary geometric conversion.

## Correctness and timing

The first browser performs full correctness: all 65,536 four-input vectors and
the wider extrema, individual-coordinate and seeded-random sets. It checks
source width, decoded CSS number and consumer width for full-reader cases.
This browser closes before timing, so exhaustive validation does not warm the
first timed repetition differently from later repetitions.

Three new browsers then run independently seeded timings. Each condition has
the same small precheck, five warmup updates and twenty measured updates of 256
outputs. Width and backend order rotate across repetitions; source/full order
alternates each round. Timed updates perform one width read per output, and
every answer is checked outside the timed interval. Raw input writes and the
mutation/read loop are included; test-case preparation, oracle calculation,
font loading and browser transport are excluded.
The elapsed-time median uses the upper-middle observation among 20 samples;
the paired-difference summary averages the two middle observations.

A separate 64-input profile uses different inputs, five warmups and ten
measured updates. Browser style and layout counters locate broad categories;
they do not isolate font-engine CPU work. Profiling does not replay the timing
sequence or replace the timing results.

All served pages have `script-src 'none'`. The external harness drives and
observes the test; the three computing font conditions never receive an answer
property. The two precomputed controls explicitly do receive it.

## Reproduce

From the repository root, with `uv`, Node.js, Playwright and Chrome installed:

```sh
python3 tools/run_unconventional_isolated.py --label reader-control-build -- uv run tools/build_gsub_reader_control.py
python3 tools/run_unconventional_isolated.py --label reader-smoke -- node tools/test_gsub_reader_isolation.mjs --smoke --output repro-smoke.json
python3 tools/run_unconventional_isolated.py --label reader-experiment -- node tools/test_gsub_reader_isolation.mjs --output repro-results.json
```

The harness defaults to the local paths recorded in its source. Override
`CODEX_NODE_MODULES` for the directory containing Playwright and `CHROME_PATH`
for the Chrome executable. It uses the retained weighted-sum experiment's fonts
without modifying them. Font hashes, source hash, environment, exactness counts,
raw timing samples, condition order, seeds and profiles are stored in the report.
