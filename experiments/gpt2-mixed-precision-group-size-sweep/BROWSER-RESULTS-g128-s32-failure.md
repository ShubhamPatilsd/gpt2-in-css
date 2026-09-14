# Mixed exact-upper group-size browser screen

One isolated round over 2 fixtures was run for each candidate. Every pair used a fresh candidate page, a fresh retained G256 K2 page, and a fresh browser process. Candidate/control load order alternated. No robust repeat was performed, and the long-lived Cursor MCP was not terminated.

| Variant | Live semantics | Candidate warm mean ms | G256 K2 mean ms | Normalized ratio | Candidate dynamic rows | G256 dynamic rows | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| g128-s32 | FAIL | 3339.0 | 3740.0 | 0.893 | 128 | 256 | reject-transport |

Fine winners and buckets are checked against each candidate's forced live dynamic exact grid. Best winner/bucket, certificate gap, done state, and final winner are then recomputed from those live shadows. NumPy bucket arrays are retained only as offline route diagnostics and are not transport pass/fail gates.

Full observations are in `browser-results.json`. The original offline report and `offline-results.json` are unchanged.
