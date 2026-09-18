# Independent selective-reader audit

**Passed. The retained evidence supports the report's conclusion: the selective
reader preserves this workload's numerical behavior and is slower in every
matched timing pair.** No additional browser runs were performed, and no driver,
fixture, original result or production file was changed by this audit.

The [audit JSON](independent-audit.json) records recomputed errors and ratios,
raw-result hashes and the source/fixture checks.

- Recomputed **61,440 coordinate errors** from the stored vectors using an
  independent exact-rational recurrence, without importing the driver's oracle.
  The maximum is **0.0001627921228170362**, matching the reported value and
  satisfying the declared 0.003 limit. All **40 bank stamps** exactly match the
  expected pass numbers.
- Compared **30,720 candidate/baseline coordinates** across all six correctness
  endpoints and four timing pairs. Every pair is identical; the maximum
  difference is zero, within the declared 0.0001 bound.
- Recomputed the median paired navigation increase as **25.4741%**, and the
  first-observed-capture continuation increase as **28.7111%**. All four pairs
  lose in both intervals. Every timed case first observes pass 1, so its
  continuation interval contains the remaining 23 captures.
- Verified **119 style updates and 71 layouts** in every complete timing
  interval, and greater style duration for the candidate in every pair. The
  report correctly avoids treating these counters as an exclusive wall-time
  decomposition.
- Checked the seven current/preserved source hashes, all twelve fixture
  HTML/CSS hashes, and the manifest → correctness gate → timing result hash
  chain.

The generated files provide a particularly direct isolation check. For each
prefix length, baseline and candidate HTML are byte-identical. Removing
**exactly two phase-selected reader-list rules** from candidate CSS makes it
byte-identical to baseline CSS. Each added rule declares 770 animations and
matching timelines: the previous bank's 768 values and generation stamp, plus
the current bank's acknowledgement stamp. The baseline declares 1,538 channels.
Thus the fixtures do not quietly change arithmetic, bank storage, readiness,
acknowledgement or controller behavior alongside the list selection.

Source inspection confirms that the fixture calls the actual `loop_parts`
implementation. Its private progress/saved/output properties and explicit
forwarding match the relevant reusable-core machinery; its local pass transport
matches the adapter's controller arrangement. The fixture remains a synthetic
contractive recurrence, not the surrounding transformer graph.

The report also states the important limits accurately: only the named finite
endpoints receive full numeric readout, timing includes external observation
and scheduling, and animation-list switching is a plausible mechanism rather
than a traced causal explanation for the regression. Because this recurrence
contracts earlier numerical deviations, passing late endpoints alone would
not establish every intermediate value; the independent early 1/2/3/4-pass
checks improve coverage without removing that general limitation.

The rejection decision is justified for this candidate. These results do not
support a token-runtime estimate or a broader claim that all selective-reading
designs must be slower.
