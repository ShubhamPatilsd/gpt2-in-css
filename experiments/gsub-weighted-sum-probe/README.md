# Connected arithmetic inside a font

This experiment asks whether many input numbers can contribute to one answer
inside the browser's font machinery, without returning each intermediate answer
to CSS. It builds exact small-integer calculations. It does not run GPT-2, use
GPT-2 weights, reproduce its numerical precision, or establish a model speedup.

See [PLAN.md](PLAN.md) for the experiment plan, [RESULTS.md](RESULTS.md) for the
measurements and conclusions, and [AUDIT.md](AUDIT.md) for the independent review.
This file explains the representation and how to reproduce the work.

## What the ordinary fixtures calculate

Each input is a signed integer from −8 through 7. The fixed weights repeat
`[3, −2, 5, 1]`. With four inputs, the calculation is:

```text
S = 3a − 2b + 5c + d
answer = 2S + 1
```

There are versions with 4, 8, 16, and 64 inputs. Each version has two ways to add
the products:

- **Sequential:** keep a running total and add one more product each time.
- **Tree:** add pairs, then pairs of those results, until one result remains.

Both perform `N−1` additions. In the tree version, additions at the same level
share font lookup passes. This reduces the number of successive passes; it does
not make the total arithmetic or all browser work logarithmic.

The second calculation, `2S+1`, really receives the first calculation's internal
digit symbols. It is still an affine expression: mathematically, it can be
folded into the original weights. The direct-CSS and variable-font comparisons
are allowed to exploit that fact. This is a connectivity test, not a demonstration
of a difficult nonlinear network.

## How negative numbers fit into small symbols

This experiment stores and publishes nonnegative widths. To represent signed
answers, the compiler uses a known offset while the calculation is in progress.

For example, `3a` ranges from −24 to 21. Its small multiplication table produces
`3a+24`, which ranges from 0 to 45. Likewise, the other three tables produce
`−2b+14`, `5c+40`, and `d+8`. Adding these four nonnegative products gives:

```text
P = S + 86
```

Each multiplication table has just 16 entries, one for each possible value of
that input. There is no table listing all combinations of all the inputs.

Every intermediate number is written as four base-16 digits. A digit has 16
possible values, from 0 through 15. For example, the number 45 is stored as the
digits `[13, 2, 0, 0]`, because `13 + 2×16 = 45`. The lowest digit comes first.
These are internal glyph identifiers, not visible printed hexadecimal text.
Their horizontal advances are zero.

Addition combines one pair of digits at a time and carries into the next digit.
A temporary digit can hold 0 through 31, covering `15+15+1`. Position labels let
the font find corresponding digits in adjacent numbers without a table over
the entire input vector. Once an addition finishes, the left number is consumed
using ordinary substitutions and a ligature. The compiler does not use a
zero-output substitution to delete glyphs.

The final internal operation produces `Q = 2P+1`. Only then are the four result
digits assigned advances proportional to their place values. A fixed extra
advance of 64 gives the source width:

```text
source width = 64 + Q
```

At a font size of 1,024 pixels with 1,024 font units per em, one font unit equals
one CSS pixel. CSS reads this width through `anchor-size()` and a size container,
subtracts `64 + 2×offset`, and obtains the signed answer `2S+1`. A final CSS
element consumes that answer in another width calculation. The oracle checks
both the decoded number and its dependent consumer.

At 64 inputs, `S` ranges from −1,376 to 1,264, the offset is 1,376, and `Q` cannot
exceed 5,281. The four-digit representation is sufficient. These bounds are part
of this experiment's contract, not a claim that four digits suffice for GPT-2.

## Four inputs feeding four different outputs

The `w4-fanouttree` fixture tests sharing an input between several calculations.
Each of its four input glyphs expands into 16 digits: four separate four-digit
products, one for each output. The browser receives each raw input only once.

The four rows of fixed weights are:

```text
 3  −2   5   1
−1   4   2  −3
 2   1  −2   5
 5  −2   1   2
```

The font calculates all four weighted sums, combines them into one sum, and then
performs `2S+1`. The separate sums share their inputs; they are not four unrelated
browser fixtures. Their combined effective weights are `[9, 1, 6, 5]`.

The four product-offset totals are 86, 76, 78, and 78. Consequently the internal
combined number is `P = S+318`, and the CSS width decoder subtracts 700. The
offset must come from those actual internal products, not from the smaller
offset one would choose for the already-combined effective weights.

This fixture remains entirely affine. The internal-channel audit below checks
the four separate sums so that opposite channel errors cannot silently cancel
in the final combined answer.

## Files and prerequisites

Run the commands below from the repository root. They use:

- Python 3 and `uv`; the Python builders declare their `fonttools` and `brotli`
  dependencies in their source files.
- Node.js and Playwright. Set `CODEX_NODE_MODULES` to the directory containing
  the `playwright` package when using a different installation from the default
  recorded in the harness.
- Chrome. Set `CHROME_PATH` when the executable is not at the harness's default
  macOS location.
- `hb-shape` for the optional internal-channel audit. Its default path is
  `/opt/homebrew/bin/hb-shape`; the verifier accepts `--hb-shape /path/to/hb-shape`.

The generated test document has `script-src 'none'` and no page scripts. An
external Playwright driver constructs fixtures, changes raw input properties,
and observes results. It never injects computed products or answers into the
native calculation. Thus these are browser computation tests with an external
test driver, not autonomous token-generation pages.

The isolation wrapper takes an advisory lock shared by the cooperating
experiments. It prevents their builds and benchmarks from competing with one
another. It cannot eliminate unrelated activity elsewhere on the computer.

## Rebuild all fonts

The first command builds the eight ordinary GSUB variants. The second appends
the shared-input fixture to their manifest. Preserve this order: a normal build
replaces the main manifest with its selected ordinary variants.

```sh
python3 tools/run_unconventional_isolated.py --label weighted-build -- uv run tools/build_gsub_weighted_sum_probe.py --widths 4 8 16 64 --topologies sequential tree
python3 tools/run_unconventional_isolated.py --label weighted-fanout-build -- uv run tools/build_gsub_weighted_sum_probe.py --fanout-only
python3 tools/run_unconventional_isolated.py --label weighted-hvar-build -- uv run tools/build_gsub_weighted_sum_hvar_control.py
```

The main manifest is `reference.json`. Each GSUB directory also has a local
`reference.json`, its generated `program.fea`, and TTF/WOFF2 font files.

The variable-font comparison has its own manifest, `hvar-control/reference.json`.
It computes the same ordinary affine function using HVAR advance variations,
folding the final multiplication and addition into fixed weights and the default
metric. It provides context from the mechanism already used in the project; it
does not contain the connected GSUB digit program.

## Check correctness before measuring speed

These commands deliberately write new `repro-*` reports rather than overwrite
the retained experiment reports:

```sh
python3 tools/run_unconventional_isolated.py --label weighted-correctness -- node tools/test_gsub_weighted_sum_probe.mjs --mode correctness --output repro-correctness.json
python3 tools/run_unconventional_isolated.py --label weighted-hvar-correctness -- node tools/test_gsub_weighted_sum_probe.mjs --reference hvar-control/reference.json --mode correctness --output repro-hvar-correctness.json
python3 tools/run_unconventional_isolated.py --label weighted-channel-audit -- uv run tools/audit_gsub_weighted_sum_intermediates.py
```

The main correctness command covers every manifest variant, including fanout.
Every four-input fixture is checked on all 65,536 possible signed input vectors.
Wider fixtures use signed extrema, cancellation examples, changes to every
individual coordinate, carry-related cases, and seeded random vectors. They are
not exhaustive over the wider input spaces.

For GSUB variants, the harness also disables stages individually and splits the
text across atomic inline elements. These controls check that the intact shaping
program and its dependencies matter. A successful final-width check alone would
not provide that evidence.

The separate intermediate verifier runs one HarfBuzz CLI process over all 65,536
four-input vectors. With only product expansion and per-channel reduction
enabled, it reads the four internal digit words and checks 262,144 channel
answers against a separately written matrix oracle. Its output is
`fanout-intermediate-audit.json`.

That verifier uses the original TTF because the installed `hb-shape` does not
accept WOFF2. It first checks that the TTF and browser WOFF2 have identical GSUB
table bytes, glyph order, character mapping, and horizontal metrics. It records
both font hashes and the HarfBuzz version. This is a complementary inspection
with a separate engine build; it does not observe Chromium's intermediate glyph
state. The browser harness checks the final native browser path independently.

## Measure complete updates and profile browser work

Only run these after the correctness commands succeed:

```sh
python3 tools/run_unconventional_isolated.py --label weighted-timing -- node tools/test_gsub_weighted_sum_probe.mjs --mode timing --correctness-report repro-correctness.json --output repro-timing.json
python3 tools/run_unconventional_isolated.py --label weighted-hvar-timing -- node tools/test_gsub_weighted_sum_probe.mjs --reference hvar-control/reference.json --mode timing --correctness-report repro-hvar-correctness.json --output repro-hvar-timing.json
python3 tools/run_unconventional_isolated.py --label weighted-profile -- node tools/test_gsub_weighted_sum_probe.mjs --mode profile --correctness-report repro-correctness.json --output repro-profile.json
python3 tools/run_unconventional_isolated.py --label weighted-hvar-profile -- node tools/test_gsub_weighted_sum_probe.mjs --reference hvar-control/reference.json --mode profile --correctness-report repro-hvar-correctness.json --output repro-hvar-profile.json
```

Timing and profile modes refuse to run without a passed full-correctness report
covering the exact selected font hashes. For retained correctness split across
files, `--correctness-report` accepts a comma-separated list. `--variants` can
select comma-separated fixture IDs; `--batch` defaults to 256 outputs.

The timed interval starts with raw input-property writes and ends after forced
reads of the final dependent output widths. It includes the mutation/read loop,
style changes, font work, layout, and native numeric readback. Font loading,
stimulus generation, oracle calculation, and external driver transport are
outside this interval. The direct-CSS comparison consumes the same mathematical
answer directly and does not take an unnecessary font-to-width return trip.

Each timing phase has 40 samples, with the first five excluded from reported
statistics. Backend order alternates. Input numbers change between rounds in
both phases. The stable-nonce phase keeps an extra character fixed; the
unique-text phase changes it. The phases use independent seeded input sequences
so the second phase does not simply replay the first phase's vectors. Changing
the extra character prevents identical complete text reuse; it does not prove
that every internal cache is disabled.

Profiling is a separate run using Chrome performance counters. Reported style,
layout, task, and script durations are broad browser categories, in seconds.
They do not isolate the CPU cost of font shaping, and they should not be added
as though they were guaranteed non-overlapping categories. The profiling run is
not a replacement for the paired complete-update measurements.

## Reproduction, provenance, and limits

Each GSUB variant records its font and feature-source byte counts and SHA-256
hashes, along with `compilerSourceAtBuildSha256`. That per-variant field names
the source used to build that font. The main manifest's `compilerSha256` names
the compiler present when that manifest was last built; after appending fanout,
it is not automatically the build-source hash of all earlier fonts. The
per-variant fields preserve that distinction.

The first eight retained fonts came from the compiler before its fanout
extension. The retained fanout font came from the extended compiler. Later
metadata corrections and a guard against input-character collisions did not
change those font files. Harness reports record their own source hash, actual
font hashes, browser version, and environment. HVAR records its builder hash in
its separate manifest. The intermediate verifier records its own source hash.

Font timestamps can change bytes and compression slightly on a fresh build,
even when the arithmetic is unchanged. Compare each run with its own manifest
and font hashes; do not silently reuse old correctness reports after rebuilding.
The current source is sufficient to rebuild and recheck the experiment, but
byte-for-byte equality with every historical font is not promised.

The ordinary compiler's glyph and rule counts grow linearly in the number of
inputs for this fixed representation. That does not imply that browser time
must grow linearly, or that this program is ready for hundreds of outputs.
The current input-character allocation supports at most 128 inputs before
colliding with the nonce range; the compiler now rejects such collisions. Its
position-specific glyph allocation also has a finite font-format limit. Neither
limit was reached by the tested widths, and neither is a general impossibility
result for font arithmetic.

The retained `attempt-reused-phase-inputs/` directory contains superseded timing
attempts whose second phase reused the first phase's input sequence. Consult
`RESULTS.md` for which final reports support the conclusions.
