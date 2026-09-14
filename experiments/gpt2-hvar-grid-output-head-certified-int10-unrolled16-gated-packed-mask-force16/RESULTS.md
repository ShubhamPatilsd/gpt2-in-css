# Forced 16-stage packed-mask traversal

This stress case sets the certificate slack to 1,000 buckets per side, so the
first fixture cannot stop early and must execute all 16 exact-group stages.

Chrome 153 completed all 16 stages with:

- 16 unique selected groups;
- the same 16-group set as the offline model;
- the expected fine winner for every selected group;
- the exact dense winner; and
- no false certificate stop.

Cold load plus the first evaluation was 131.961 s. This is a correctness stress
test, not a production timing configuration.

The last two groups appeared in the opposite order from the float64 offline
ordering. The expanded-history control produced the identical browser order,
so this is browser score-coordinate realization drift rather than packed-mask
state corruption.

See `browser-results.json` for the complete trace and
`../gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated-force16-expanded/`
for the control.
