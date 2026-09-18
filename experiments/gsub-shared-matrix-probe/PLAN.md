# One input vector, several distinct outputs

## Question and scope

Test whether sharing the same input values and font settings across several
outputs changes the comparison between GSUB arithmetic, HVAR variable fonts,
and direct CSS. This is a synthetic exact integer matrix calculation, not a
GPT-2 layer or a model speed measurement.

Inputs are signed integers in [-8, 7]. Every output uses a distinct deterministic
row of fixed nonzero weights and computes `2 * sum(weight[i] * input[i]) + 1`.
The output rows are distinct functions; they are not claimed to be linearly
independent when there are more outputs than inputs.

## Representation and fair sharing

- Test input counts N = 4, 16, 64 and output counts M = 1, 4, 16.
- A vector parent receives each of its N raw input properties once per update.
  Its M outputs inherit the properties in every backend.
- HVAR uses one N-axis font containing M output glyphs. The parent owns one
  font-variation-settings declaration, inherited by every output.
- GSUB uses one fixed-weight font for each output row, reusing the existing
  signed digit compiler with configurable weights and separate output paths.
  The parent input writes are shared, but each output still has its own encoded
  text and shaping run. This does not claim shared internal GSUB arithmetic.
- Direct CSS directly evaluates each output row and consumes its numeric
  result without an unnecessary font measurement round trip.
- Both font backends publish a width, decode it with native anchor/container
  CSS, and consume the recovered number in another width calculation.
- The browser document has CSP script-src 'none' and no script elements. The
  external harness supplies raw inputs and reads results; it does not supply
  multiplication results or answers.

## Gates before timing

1. Generate all row fonts and record source and font hashes, glyph counts,
   bytes, output offsets, and the precise weight matrix.
2. Exhaustively check all 65,536 four-input vectors for every one of the 16
   output rows in all three backends. Wider matrices receive edge cases,
   individual-input changes, cancellation/carry cases where available, and
   seeded random vectors. Check numerical readback and final consumed widths.
3. Check generated pages contain zero scripts and all fonts actually load.
   Reuse feature-disable controls for GSUB and test that shared input changes
   influence every output with the expected fixed coefficient.
4. Only time fonts whose exact hashes passed correctness.

## Measurements

- Main scaling keeps total outputs at 256: vector count = 256 / M.
- A separate one-vector case reports latency for one parent and its M outputs,
  making input-sharing benefits distinguishable from batching changes. Each
  sample aggregates 32 changing updates on that same vector DOM, forces every
  result after each update, and divides elapsed time by 32. This reduces timer
  rounding and measures repeated-update latency rather than cold latency.
- Three fresh browser repetitions, different deterministic input seeds, five
  warmups plus 20 reported samples per configuration.
- Rotate all three backend orders in balanced fashion. Reuse the same raw
  stimuli for compared backends. Prepare stimuli and arithmetic oracle outside
  timed intervals; include parent property writes and forced final width reads.
- Check every timed output, retain raw samples and per-repetition medians, and
  report variability rather than treating one sweep as a reliable winner.
- Use a changing zero-width nonce, cycling through 65 glyphs. Record distinct
  input-plus-nonce states; do not claim this disables internal font or browser
  caches. Each configuration has an independent input seed.
- Serialize all font builds and browser runs through
  tools/run_unconventional_isolated.py. Other normal machine activity remains
  uncontrolled.

## Practical bound

The initial matrix has 48 GSUB row fonts (16 rows at each of three widths) and
three multi-output HVAR fonts. Reuse completed rows on restart. Do not expand to
64 outputs unless the initial build and runtime costs justify it. If a browser
or font budget fails, preserve the failed case and document the tested bound.

## Deliverables

Compiler, browser harness, generated manifests/fonts, exactness results, three
fresh-browser timing reports, and a concise report explaining input sharing,
font-state sharing, remaining repeated work, and the limits of this comparison.
