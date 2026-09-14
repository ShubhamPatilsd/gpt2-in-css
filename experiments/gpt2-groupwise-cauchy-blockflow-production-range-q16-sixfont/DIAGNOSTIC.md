# Focused six-font integration diagnostic

State 944/group 4/token 1238 passed the corrected retained reducer: final token 1899 equals mathematical global-q16 and original checkpoint float. Forced state 519/group 147 selected q16 token 37848 rather than legacy token 2032.

- Bank base: 3275.4375 px; expected raw: 2743.137951 px; measured raw: 2743.187500 px.
- Final candidate/stage/choice width: 21728.640625 px; decoded bucket: 5432; expected bucket: 5432.
- Dynamic anchor/display/top: `--dynamic-fine-winner-0`, `grid`, `-92000px`.
- Inherited versus numeric-literal score offset: both 21728.640625 px.
- Custom-property versus literal base: both 21728.640625 px.
- Factor 1 is valid and produces 85484.640625 px; removing score offset correctly produces 0 px because the intermediate result is negative.
- Selected-stage bucket deltas across state 944: 0..+1.
- The six zero-width failed-sample glyphs are all out-of-vocabulary token 50431 padding; valid collapsed glyphs: 0.

See `diagnostic.json` for computed family, 62.5 px size, all 768 integer variation settings, `--fine-base`, `--fine-glyphs`, rendered codepoints, isolated expressions, reducer geometry, and request audit.
