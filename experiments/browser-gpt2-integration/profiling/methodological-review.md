# Review of stage attribution

## Saved observations

The existing native harness records each milestone after a sequential `DOM.getBoxModel` call returns. It records renderer counters only at captured-token samples. A root token epoch can already have advanced when an earlier token is captured, so extraction uses `headEpoch` and the explicit capture marker, not a sample's root `epoch`.

The old `core` witness is absent after token 1 in many twelve-layer runs. Its absence is not a zero cost and cannot be replaced with the nearest available epoch. The new saved-data extraction uses the separate `headInput` boundary and requires the entire sequence to exist and be monotonic: previous capture, token epoch, embedding, head input, head, capture. It reports rejected rows. A comparison uses the intersection of valid token epochs in the two processes. In the clean c4/r1 pair, only terminal token 4 survives this rule. In c4/r2, continuing tokens 2 and 3 and terminal token 4 survive.

These are observed spans rather than exclusive costs. The geometry read that reveals a boundary may flush style/layout for work after the boundary. The head-input-to-head span therefore cannot establish the total vocabulary cost, and embedding-to-head-input cannot establish an exclusive transformer cost. Token-boundary style/layout counter shares are whole-token evidence only. The source records, timing exclusions, and exact source hashes remain in `saved-stage-costs.json`.

The CPU contention incident in `baseline-b12-c4-r0` remains a timing exclusion rather than a browser or numerical failure. It is not used in the comparison tables. Terminal intervals remain separate from continuing intervals; their behavior is systematically different and is not assumed to be uniformly shorter.

## New diagnostic

Six small witnesses are inserted inside existing input/receipt gates in an HTML clone of `baseline-b12-c4-r2`. Their widths expose the inherited native pass epoch only when the upstream freshness gate is open. Insertion inside the gate avoids accidentally reading a private `--gate-*` property's initial value on a child. The observer does not change any gate or register.

Deleting exactly those six witnesses and restoring the original stylesheet link reproduces the preserved baseline HTML byte-for-byte. The stylesheet is referenced directly from the preserved baseline. Both HTML and CSS hashes, the script snapshot, and the mutation description are recorded. The new witness elements can still add style/layout work; identical arithmetic and scheduling source do not establish identical browser timing.

After initial navigation the harness explicitly allows only DOM document/query/geometry reads, `Performance.getMetrics`, and browser-version reads. It prohibits writes and JavaScript domains. Captured token IDs are checked against the baseline. This check establishes the observed diagnostic token prefix only; it is not a new validation of every intermediate activation or residual vector.

Each fresh stage/pass receives a renderer-counter snapshot, and each geometry call records start/end times. Those counters include any work flushed by observation. Polling sequentially also means some gates can open and close between reads. Only observed, correctly matched pass boundaries can be attributed, and any aggregate must publish coverage and omitted intervals. Even complete receipt coverage does not remove observer effects or turn a shared rendering update into exclusive stage CPU time.

The run is bounded to two captured tokens or a 180-second loop deadline, with a 60-second socket timeout for an in-flight CDP call. It stores at most 2,000 distinct stage/pass events and no trace. There is no promise that the loop deadline interrupts a blocking CDP command immediately. Token 2 is a continuing token in the four-slot native graph, even though the diagnostic closes the browser after observing its capture.

The first launch failed during document replacement before any geometry read: `DOM.querySelector` received a stale root node ID, at 0.35 seconds. Its complete artifact and source remain in `receipt-diagnostic-startup-failure/`. The retry refreshes the root during bounded observer discovery. This is a harness startup failure, not a model or scheduling failure.

## Observed limits and verdict

The retry passed both captured-token checks with no post-navigation writes. It observed 70 fresh events, including four core events from native passes 25 and 26 before capture 2 was finally read. The 24 target passes contain 62 core observations out of 144 possible, with **zero passes fully covered**. Neither head-completion event was caught. The five kinds of adjacent receipt intervals have 10, 5, 8, 7 and 8 valid same-pass observations, respectively, drawn from different pass sets. Their medians cannot be normalized into stage shares.

Geometry reads took a median 436.8 ms, maximum 5.685 s, and 59.961 s total call wall time. Those durations include browser work and waiting; they are not a direct estimate of observer CPU overhead. The final projection witness for pass 12 returned near the head-input observation after a long blocking read. This is concrete evidence that assigning a queued geometry read's duration entirely to its named stage would mislead.

The diagnostic supports freshness and partial observations, but it fails to produce the requested complete native QKV/MLP/vocabulary breakdown. The next useful optimization evidence is matched numerical ablations on actual QKV and MLP graphs. A more compact geometry observer is a possible measurement improvement, not an implemented solution. The current two-token diagnostic must not be compared as a speedup or slowdown against the uninstrumented native benchmark.

`validation.json` records five invariant checks over the saved evidence and archived sources. The executable profiler passes Ruff lint and formatting. The measured pre-format script snapshots remain untouched; the current script adds analysis/reporting and source-preservation guards after measurement. This source revision difference does not imply a new browser run.
