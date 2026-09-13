# Additive font-variation vector probe

Question: can several independent CSS animations add whole
`font-variation-settings` vectors into one reusable axis list?

The runtime fixture is HTML/CSS-only. The external Playwright harness only
reads computed styles.

Expected additive result for the three paused animations is
`A000=1.5, A001=3.75, A002=5.25`.

Chrome 153 returned that vector exactly for both
`animation-composition:add` and `accumulate`. Three nested container widths
driving three paused animation delays also returned the same vector. Sparse
one-axis `font-variation-settings` lists do not merge; every contribution must
contain the same complete axis list.

This is the first tested CSS primitive that gathers many dense matrix columns
into one reusable vector-valued property instead of exposing one custom
property per output.
