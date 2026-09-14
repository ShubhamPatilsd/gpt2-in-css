# Row-wise int10 output head with 256-axis shards

Decision: **retain as the coarse carrier for the loaded output-head profile**.

The row-wise int10 scan now uses three 256-axis HVAR faces per vocabulary row
instead of five 160-axis faces. This reduces the all-vocabulary coarse scan
from 251,285 to 150,771 shaped glyph instances, a 40.0% reduction, while
keeping essentially the same coefficient payload.

| Property | 160-axis source | 256-axis candidate |
|---|---:|---:|
| Glyphs per token | 5 | **3** |
| Estimated shaped glyphs | 251,285 | **150,771** |
| Candidate WOFF2 bytes | — | 50,862,612 |
| Candidate HTML | — | 5.66 MB |
| Candidate CSS | — | 203,881 bytes |

## Numeric boundary

The wider rows require an explicit relaxed-result mode in the font writer.
Their stored base advances remain valid unsigned 16-bit values (the three
maximum row bases are 46,830, 44,607, and 43,892), but applying HVAR deltas can
produce a shaped advance above 65,535. Chrome 153 preserves those results.
The generator keeps the conservative check by default and opts into this mode
only with `GPT2_HVAR_HEAD_ALLOW_OUT_OF_RANGE_RESULT=1`.

The standalone browser screen passes both generated-query winners and all nine
validation-query winners: 11/11 row-wise-int10 expectations. Live score
buckets differ by at most six from the generator. This page is not a dense
exact head by itself—the quantized winner differs from the unrounded dense
winner on a known validation fixture—but the certified mixed head retains the
exact route and final-winner contract.

| Browser metric | Observation |
|---|---:|
| Cold load | 43,139.4 ms |
| Settled mutation median | 683.9 ms |
| Validation mutation median | 1,629.0 ms |
| Maximum bucket error | 6 |

Raw browser observations are in `browser-results.json`. Chrome:
153.0.8010.36.
