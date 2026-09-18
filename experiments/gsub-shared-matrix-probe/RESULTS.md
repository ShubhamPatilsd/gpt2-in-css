# Shared inputs change the comparison between the font methods

All correctness checks passed. Sharing one input vector across several distinct
outputs substantially reduced HVAR's cost. At 64 inputs and 16 outputs per
vector, HVAR was about 2.9 times faster than the tested GSUB implementation.
Direct CSS remained fastest in every tested configuration.

This changes the interpretation of the earlier one-output test. With 256
independent 64-number vectors, HVAR took 216.3 ms and GSUB took 81.3 ms. With
16 vectors each producing 16 distinct outputs, HVAR took 24.8 ms and GSUB took
72.2 ms. Both batches produced 256 output numbers, but the latter batch needed
only 16 independent input updates. This is a measured sharing benefit for this
synthetic matrix workload, not a GPT-2 speedup.

## Relation to the existing model

The current GPT-2 implementation already shares input-derived font variation
settings across output glyphs: see [browser_gpt2_core.py](../../tools/browser_gpt2_core.py)
lines 313–328 and [build_hybrid_twelve_block.py](../../tools/build_hybrid_twelve_block.py)
lines 131–168 for the common ancestor's settings, 170–188 for output-row glyphs,
and 193–197 for the shared settings. The core calls this hybrid matrix path
for its compact, gated, and dynamic-range variants. Its input-shard fonts
retain all output rows in
[build_gpt2_block_css.py](../../tools/build_gpt2_block_css.py) lines 149–170.
This small probe uses one shared list of axis settings. A 3,072-input model
stage uses four shared lists, each reused across its output rows.
This experiment evaluates that existing mechanism under a many-output workload;
it does not introduce a new optimization into the model.

## What was actually shared

Each vector parent received its N raw signed input properties once. All M
outputs inherited those same values in every backend. The weights are distinct
deterministic rows sampled from {-3,-2,-1,1,2,3}; every coefficient is nonzero.
Each output computes `2 * sum(weight[i] * input[i]) + 1`. Inputs range from -8
through 7. The full weight matrices are retained in [reference.json](reference.json).

HVAR used one N-axis font with 16 result glyphs. A single parent
font-variation-settings value was inherited by every output. Font size and
kerning also matched between parent and children. M selects the first 1, 4,
or 16 active output rows from that same 16-row font; it does not select a
separately rebuilt M-row font.

GSUB used one fixed font per active row and a separate shaping run per output.
It shared the parent input writes, but each output still encoded and processed
its own input text. This experiment does not claim shared internal GSUB
multiplications or additions. The existing sequential digit program was reused
with each row's fixed weights; no whole-vector answer tables were created.

Both font methods decoded their result widths into native CSS numbers using
anchor-size and container units. A following width calculation consumed each
number. Direct CSS computed the same row and consumed its final number directly.
Every backend performed the same number of final observer reads. The document
contained no scripts and had CSP script-src 'none'; the external harness supplied
raw inputs and checked answers, without supplying products or answers to CSS.

## Fixed total output count

Every batch below produces 256 outputs. Values are milliseconds for the whole
batch: the median of three fresh-browser repetition medians. Brackets give the
minimum and maximum repetition median. Each repetition has five warmup samples
and 20 measured samples. These ranges are observed variation, not confidence
intervals.

For each set of 20 samples, the harness uses the upper middle sample (the
11th sorted value) as its median. The reported center then takes the middle
of the three repetition medians.

| Inputs N | Outputs per vector M | Vectors in batch | Direct CSS | GSUB | HVAR |
|---:|---:|---:|---:|---:|---:|
| 4 | 1 | 256 | 3.4 [3.4, 3.7] | 10.5 [9.9, 10.5] | 25.9 [25.1, 26.6] |
| 4 | 4 | 64 | 2.3 [2.3, 2.6] | 8.6 [8.4, 9.8] | 11.9 [11.7, 13.5] |
| 4 | 16 | 16 | 2.2 [2.2, 2.3] | 8.7 [8.7, 8.8] | 8.5 [8.3, 8.6] |
| 16 | 1 | 256 | 6.7 [6.6, 6.7] | 23.2 [22.5, 23.3] | 47.3 [46.2, 47.7] |
| 16 | 4 | 64 | 4.3 [4.3, 4.4] | 20.2 [19.8, 21.1] | 18.1 [18.1, 18.2] |
| 16 | 16 | 16 | 3.8 [3.7, 3.8] | 19.8 [18.5, 19.9] | 10.7 [10.1, 11.6] |
| 64 | 1 | 256 | 18.1 [17.5, 18.4] | 81.3 [81.0, 81.7] | 216.3 [215.5, 217.4] |
| 64 | 4 | 64 | 11.3 [10.7, 11.4] | 73.8 [71.9, 74.3] | 64.0 [62.7, 64.2] |
| 64 | 16 | 16 | 9.2 [9.2, 9.3] | 72.2 [71.8, 73.7] | 24.8 [24.8, 24.8] |

At N64/M16, the batch means are 0.575 ms per vector for CSS, 4.5125 ms for
GSUB, and 1.55 ms for HVAR. These divide the batch time by 16 and therefore
describe batched work; they are not isolated single-vector latency estimates.

Increasing M reduces input writes as well as independent font states. At
N64/M1, each update writes 16,384 input properties plus 256 nonces. At N64/M16,
it writes 1,024 input properties plus 16 nonces. All three methods receive
exactly these same parent writes. All still compute and expose 256 results.

## One vector at a time

These cases always update one vector parent. A measured sample contains 32
changing updates on the same DOM, forcing every output after each update.
Each reported sample time is divided by 32. All intermediate observations are
checked outside the timed interval. This reduces timer rounding and measures
steady repeated-update cost, rather than cold latency.

Values are milliseconds per complete vector update, with the same median and
range convention. Last displayed digits are not an accuracy guarantee.

| Inputs N | Outputs M | Direct CSS | GSUB | HVAR |
|---:|---:|---:|---:|---:|
| 4 | 1 | 0.0187 [0.0187, 0.0188] | 0.0406 [0.0406, 0.0437] | 0.1062 [0.1031, 0.1125] |
| 4 | 4 | 0.0406 [0.0406, 0.0438] | 0.1313 [0.1281, 0.1344] | 0.1875 [0.1750, 0.1906] |
| 4 | 16 | 0.1312 [0.1281, 0.1313] | 0.4844 [0.4781, 0.4938] | 0.4781 [0.4781, 0.4875] |
| 16 | 1 | 0.0281 [0.0281, 0.0313] | 0.0875 [0.0875, 0.0906] | 0.1844 [0.1781, 0.1875] |
| 16 | 4 | 0.0656 [0.0656, 0.0688] | 0.2844 [0.2813, 0.2906] | 0.2625 [0.2563, 0.2687] |
| 16 | 16 | 0.2250 [0.2188, 0.2281] | 1.1344 [1.1125, 1.1563] | 0.6219 [0.6125, 0.6500] |
| 64 | 1 | 0.0719 [0.0719, 0.0750] | 0.3094 [0.3000, 0.3156] | 0.8406 [0.8344, 0.8781] |
| 64 | 4 | 0.1719 [0.1688, 0.1719] | 1.0906 [1.0719, 1.1250] | 0.9844 [0.9719, 1.0094] |
| 64 | 16 | 0.5625 [0.5531, 0.5656] | 4.4813 [4.3250, 4.5156] | 1.4625 [1.4562, 1.4781] |

For N64, increasing from one output to 16 multiplies HVAR's complete update
time by about 1.74, GSUB's by about 14.5, and CSS's by about 7.8. HVAR's
per-output cost falls from about 0.841 ms to 0.0914 ms. The same vector and
font settings are reused across distinct output glyphs. This supports the
sharing interpretation independently of the fixed-output batch comparison.

## Correctness and controls

- All 65,536 four-input vectors were checked against all 16 output rows in all
  three backends: 3,145,728 output checks.
- N16 used 1,128 vectors; N64 used 1,320. These include each row's signed
  extrema, each coordinate changed individually, constants, alternating
  signs, and 1,024 seeded random vectors. All 16 rows were checked in every
  backend. Total full-gate output checks: 3,263,232.
- All 192 GSUB row/stage ablations changed their answers. With all stages
  enabled, each active row's final native number, raw source width, and
  dependent consumer width matched the external arithmetic oracle exactly.
- All 972,000 observed timed outputs passed, including every update inside
  the aggregated one-vector samples. No browser errors were recorded.
- Full correctness ran separately before the three fresh timed browsers.
  Every timed configuration had the same small fixed-input precheck, followed
  by its five warmups. Timing required exact font hashes from the passed gate.

The four-input domain is exhaustive. Wider domains are sampled; passing those
cases is not a proof over all possible wider vectors.

## Font sizes and retained structure

| Inputs N | All 16 GSUB row fonts, WOFF2 bytes | GSUB glyphs per row | GSUB lookups per row | One 16-output HVAR font, WOFF2 bytes |
|---:|---:|---:|---:|---:|
| 4 | 75,628 | 1,284 | 44 | 776 |
| 16 | 202,204 | 4,548 | 116 | 1,108 |
| 64 | 626,428 | 17,604 | 404 | 2,144 |

Each HVAR font has 82 glyphs: 16 results, 65 nonces, and .notdef. These are
compressed file sizes, not browser memory measurements. GSUB loads the M
active row fonts; HVAR uses the same 16-row font at every M. Font loading is
outside the timing interval. DOM element counts, parent writes, and observer
reads are retained per configuration in the timing JSON.

## Measurement details and limits

Machine: Apple M2 Pro, macOS arm64; Chrome 153.0.8010.48; Node v26.5.0.
Builds and browser runs acquired the common experiment lock. Ordinary machine
activity was not otherwise controlled.

There were three fresh browser launches. Each configuration/repetition used
a different recorded deterministic input seed: 54 distinct seeds. Compared
backends received the same prepared raw sequence. Configuration order rotated
between repetitions, and all six backend permutations balanced across the
three sets of 20 measured samples. Raw samples and each repetition's median
are retained; results are not only pooled into one timing number.

The timed region includes parent property writes and final forced width reads,
including external JavaScript loop overhead. It excludes input generation,
the oracle, browser-protocol transport, and font loading. Native computation
and numerical readback remain inside the measured region.

Nonces change each update and cycle through 65 glyphs. The timing JSON records
unique input-plus-nonce states. HVAR's visible row character and nonce text
can repeat while its inherited axes change. Neither the nonce nor independent
input seeds disable every browser or font cache. The finite N4 input domain
also permits incidental vector reuse across independently seeded streams.

All results use synthetic four-bit inputs and small integer weights. The
affine continuation can be folded into HVAR weights and CSS arithmetic; those
backends are allowed to do so. This does not establish nonlinear multilayer
performance, GPT-2 accuracy, or trained-model scaling to hundreds of inputs
and thousands of outputs. A different GSUB representation could share more
work than these separate row fonts. Close timings, particularly N4/M16, do
not support a strong general ranking between the two font methods.

## Reproduction and evidence

From the repository root:

```sh
python3 tools/run_unconventional_isolated.py --label shared-matrix-build -- uv run tools/build_gsub_shared_matrix_probe.py
python3 tools/run_unconventional_isolated.py --label shared-matrix-correctness -- node tools/test_gsub_shared_matrix_probe.mjs --mode correctness
python3 tools/run_unconventional_isolated.py --label shared-matrix-timing -- node tools/test_gsub_shared_matrix_probe.mjs --mode timing
```

The compiler reuses verified existing GSUB row artifacts on restart. Rebuilding
HVAR changes its font hash, so run correctness again before timing. The manifest
records both the wrapper compiler and reused GSUB compiler hashes. The timing
report records its harness hash, environment, font hashes, and correctness gate.

- [Plan](PLAN.md)
- [Compiler](../../tools/build_gsub_shared_matrix_probe.py)
- [Browser harness](../../tools/test_gsub_shared_matrix_probe.mjs)
- [Matrices, fonts, and provenance](reference.json)
- [Full correctness](results-correctness.json)
- [Three-repetition timings and summaries](results-timing.json)

The useful next comparison for a matrix pipeline is therefore the shared HVAR
path, not an HVAR test that creates a fresh independent font state for each
single output. This experiment gives no reason to replace that path with the
tested per-row GSUB construction.
