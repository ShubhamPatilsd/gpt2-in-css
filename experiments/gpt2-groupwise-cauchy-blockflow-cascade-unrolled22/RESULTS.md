# 22-stage groupwise Cauchy block-flow cascade

## Decision

**Retain the 22-stage topology as the corpus-complete tail experiment, not as
the default loaded profile.** It preserves the unchanged GPT-2 checkpoint and
the direct global-int16-minus-rowwise-int10 group certificate from the retained
six-stage candidate.

The strict script-free page passes 10/10 browser fixtures. All routes, exact
group shadows, incumbent merges, 48-bucket stops, and final tokens match; the
fixtures still stop in `1,3,1,1,1,1,2,1,1,1` stages. All 96 axes and 195 bound
glyphs are live, and no measured bound rounds inward.

The reason to materialize 22 stages is the independent production-range
screen: at the conservative 48-bucket margin, all 1,024 saved states stop by
stage 22, while six stages cover 984 and twelve cover 1,018. This is corpus
completeness, not a proof for every possible hidden vector.

## Cost of the longer unroll

The 22-stage candidate contains 8.03 MB HTML and 3.87 MB topology CSS. The
six-stage candidate contains 7.31 MB HTML and 0.76 MB topology CSS. Thus the
tail adds little row markup but 3.11 MB of generated routing dependencies.

Against an otherwise corresponding 22-stage scalar-bound control in the same
browser process, four paired mutations were:

| Page | Mean | Median | Cold load |
|---|---:|---:|---:|
| 22-stage direct groupwise | 2,472.8 ms | 2,065.3 ms | 52.51 s |
| 22-stage scalar bound | 3,044.3 ms | 2,776.6 ms | 67.40 s |

The direct certificate remains beneficial at 22 stages (0.812x mean, 0.744x
median). Compared with the saved six-stage direct candidate, 22-stage mean is
25.0% higher and cold load 16.4% higher, while its median is lower; those runs
were not paired and contain only four mutations, so they establish a source
tax but not a stable warm regression magnitude.

This page's integrated coordinates remain fixture-range (±135.309). The later
production-range experiment supersedes the earlier assumption that new score
fonts are required: argmax homogeneity permits reuse of these exact q10/q16
font binaries at ±266.248 by widening only the CSS axis denominator and
holding score gain fixed. That corrected path needs 23 stages and is described
in `../gpt2-groupwise-cauchy-blockflow-production-range/RESULTS.md`. Nothing
was committed or pushed.
