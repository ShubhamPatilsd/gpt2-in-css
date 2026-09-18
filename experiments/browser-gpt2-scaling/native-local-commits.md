# Native local input commits: A → B → A with source poisoning

The native mechanism passed: **three browser runs completed all nine A/B/A
commits with zero post-navigation writes**, while deliberately corrupting the
upstream query after each capture. The receiving head retained the intended query
and produced the correct attention result. The strongest unobserved run had its
native completion marker set before the first computed-style read, after the
harness left the page alone for two seconds.

This extends the [structural locality study](locality-report.md) from externally
mutated input properties to a working native input-capture mechanism around real
attention. It establishes coherent capture, retention, and reuse in this fixture.
It is **not a measured speedup**, production-cache result, or full-model run.
Measurements used local Chromium `153.0.8010.48` on September 17, 2026.

## Implemented scope

[The probe](../../tools/probe_browser_gpt2_native_local_commits.py) creates two real
64-dimensional attention heads, each with eight immutable K/V positions. QK is
computed with the existing bilinear variable font. Scores travel through native
geometry/timelines, and CSS computes softmax and weighted V. There is no QKV
projection, native KV-cache write, layer switch, or token-generation pipeline.

Head 0 receives its query through a new native local input register. Head 1 keeps
its own fixed query and sits outside the transfer controller's ancestry. The
upstream producer is a sibling of the register reader, so its raw query properties
cannot inherit into the receiving head. Only a native geometry/timeline bridge
crosses that boundary.

The register is a single reusable bank with 64 numeric query fields and a tag.
It uses the same delayed-transition storage mechanism as the existing runtime.
The source sequence is serialized: a later input cannot replace the current one
until capture, source poisoning, and output acknowledgement complete. This makes
one bank sufficient for the probe. It does not demonstrate concurrent double
buffering or the full reused-core handshake.

## Native state machine

The fixture places A and B only at the upstream producer. A is a seeded query;
B is `-0.7 × A`. Destination input banks contain no copies of the desired fixture
values. They reconstruct whatever values actually arrive through 65 source
geometry timelines: 64 coordinates and one pass tag.

For each of three commits, the page performs the following steps without page
JavaScript or harness writes:

1. The producer publishes A, B, then A with tags +1, +2, and +3.
2. The input register reads the vector and tag. A local receipt requires the
   expected input tag, and the attention head requires its matching geometry
   receipt. A font metric witness prevents initial capture before the real font
   becomes active.
3. CSS animation completion triggers SVG SMIL to mark the input captured. The
   local controller enables delayed transitions on the input bank, freezing the
   received vector.
4. A distinct held acknowledgement fires before SMIL poisons the producer. The
   source is replaced by a visibly different 64-vector and tag −1, −2, or −3.
   This ordering tests that the bank is held before its input changes.
5. An incoming receipt confirms the negative source tag while the input bank
   still carries the corresponding positive held tag. The head must remain ready
   for that held tag. Native audit registers save the actual held Q, attention
   result, poisoned incoming Q, and both tags.
6. Output acknowledgement advances to the next commit. All earlier audit
   registers hold their captured values. The same input bank reopens and is reused
   for the next vector.

These are native event-driven transitions, not fixed wall-clock iteration ticks.
The existing short animation/SMIL delays separate capture from later mutations;
the arithmetic receipts determine when a phase is eligible to progress.

## Validation requirements

- All three commits finish without any post-navigation input/control writes.
- Every audit's held vector matches its A/B/A fixture.
- Every audit's context matches NumPy attention on that fixture and the static
  K/V. RMSE must remain below 0.005, consistent with the structural probe.
- Every source audit matches the deliberately poisoned vector, with tag `-step`.
  Its destination audit retains tag `+step` and the correct unpoisoned result.
- Head 1's computed output continues to match its unchanged independent oracle.
- A separate delayed-observation run must complete while the harness initially
  leaves the page unobserved. Results are separated below.

The harness navigates and then uses read-only DOM/CSS queries. It records state
changes, completion flags, errors, and final receipt diagnostics. The script-free
CSP and existing browser harness prohibit page JavaScript. Fixture inputs are
deliberately supplied by the generator; this remains an input-delivery diagnostic,
not autonomous model inference.

## Results and attempt ledger

The first browser attempt passed. No failed browser or numerical attempts were
discarded, and no arithmetic or handshake fix was needed after that run. The
third case adds only a stronger read-only completion-marker observation; both
earlier cases and their original source snapshots are retained.

| Case | Initial period with no observation | Commits passed | External writes | Completion marker before first computed-style read |
| --- | ---: | ---: | ---: | --- |
| `attempt1-delay0-r0` | 0 s | 3/3 | 0 | Not instrumented |
| `attempt1-unobserved-delay2-r0` | 2 s | 3/3 | 0 | Not instrumented; final state at first poll |
| `attempt2-unobserved-marker-delay2-r0` | 2 s | 3/3 | 0 | **True** |

Each browser run produced the same numerical errors:

| Commit | Held input | Held/source tags | Held-Q RMSE | Attention-output RMSE | Maximum output error | Poisoned-source RMSE |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | A | +1 / −1 | 0.000006975 | 0.000016460 | 0.000038374 | 0.000006982 |
| 2 | B | +2 / −2 | 0.000007613 | 0.000028696 | 0.000073433 | 0.000006982 |
| 3 | A | +3 / −3 | 0.000006975 | 0.000016460 | 0.000038374 | 0.000006982 |

The positive and negative tags are retained in separate native audit registers,
alongside measurements of the actual held and incoming vectors. This verifies
that the source really changed to the poisoned vector while the receiving bank
continued to supply the intended query. The third commit additionally checks that
the same bank can reopen and return to A after holding B.

The normally observed run collected eight valid snapshots of head 1 while head 0
progressed through its commits. Its computed output changed by **exactly zero at
CSS serialization precision** across those samples. Final head-1 output RMSE was
0.0000209815, maximum absolute error 0.0000512400. The unobserved runs have only
one final snapshot each; their zero observed change is therefore not a separate
multi-sample invariance claim.

For orientation, the normally observed state log first read commit 1 at about
104 ms and observed the final held/poisoned commit-3 state at about 499 ms after
navigation. These are diagnostic observation timestamps. They include loading,
font initialization, polling, the source bridge, and audit registers, and are not
latency or throughput benchmark results. The run with the stronger unobserved
check proves the finite sequence does not require repeated computed-style reads
to advance.

The native audit registers are read only after completion. They retain each
earlier commit even if the harness missed the brief intermediate phases. This
allows the unobserved runs to validate A, B, and A separately rather than merely
checking the final answer.

## Attempt preservation and reproduction

Every labeled case directory contains the generated HTML/CSS, fixture oracle,
font-witness manifest, a copy of the probe source, and—after browser execution—a
result with source hashes and diagnostics. A changed implementation must use a new
label so failed attempts remain inspectable.

```sh
uv run tools/probe_browser_gpt2_native_local_commits.py --build-only --label attempt1
uv run tools/probe_browser_gpt2_native_local_commits.py --label attempt1
uv run tools/probe_browser_gpt2_native_local_commits.py --label attempt1-unobserved --observe-after 2
```

The labels above already contain retained results in this checkout; choose new
labels such as `reproduce-observed` and `reproduce-unobserved` for fresh runs. The
probe refuses to overwrite a directory containing `results.json`.

No concurrent browser benchmark should run during these attempts. Preparation
and documentation can run in parallel with other agents' benchmark slots.

Evidence:

- [Machine-readable summary](native-local-commits/summary.json).
- [Observed run](native-local-commits/attempt1-delay0-r0/results.json), including
  its eight phase snapshots and per-commit numerical validation.
- [First unobserved run](native-local-commits/attempt1-unobserved-delay2-r0/results.json).
- [Unobserved run with pre-style completion check](native-local-commits/attempt2-unobserved-marker-delay2-r0/results.json).
- [Generated page](native-local-commits/attempt2-unobserved-marker-delay2-r0/index.html),
  [generated CSS](native-local-commits/attempt2-unobserved-marker-delay2-r0/style.css),
  and [archived measured source](native-local-commits/attempt2-unobserved-marker-delay2-r0/probe-source.py).

All three archived source hashes match their result records. The generated
HTML/CSS and imported helper source hashes were verified before final lint cleanup.
The third measured source differs from the first two only by the added pre-style
completion check.

Post-measurement lint cleanup made both probe tools executable, sorted imports,
and documented intentional broad experiment-boundary exception catches using
targeted `BLE001` suppressions. Ruff passes both files. Their computation was not
changed, and no browser runs were repeated for the cleanup. The exact
[native probe before final lint](source-before-final-lint/probe_browser_gpt2_native_local_commits.py),
[locality helper before final lint](source-before-final-lint/probe_browser_gpt2_state_locality.py),
and [SHA manifest](source-before-final-lint/manifest.json) preserve the recorded
source versions alongside each native case's existing source snapshot.

## Remaining production questions

This result establishes coherent local input capture, retention against upstream
changes, and repeated bank reuse around the real attention calculation. It does
not establish a speedup: this probe adds bridge geometry and audit work and does
not compare total work against an otherwise identical broadcast implementation.
It also does not measure style invalidation in the unchanged head. Its unchanged
numeric result must not be presented as proof that the browser did zero work on
that subtree.

It also leaves native per-layer KV acquisition, twelve-head completion fan-in,
projection/residual lifetime, and the broader core's layer-container invalidation
unresolved. Those barriers are detailed in the
[locality report's native commit design addendum](locality-report.md).
