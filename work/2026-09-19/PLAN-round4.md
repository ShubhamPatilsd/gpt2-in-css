# Round 4 plan (2026-09-21)

Base: `combined4` (18.2 s/token paired, capacity 8). Goal: (a) find exact levers on the timeline
transport cost (per-frame servicing ≈117 ms × ≈40 frames; 40 µs per changed carrier animation);
(b) determine whether a 32-token demo is feasible and what its per-token slope is.

Ground rules unchanged (PLAN.md): one Chromium at a time via `CHROME.lock` (mkdir/touch/rmdir own only;
match Chrome with `^/Applications/.*Google Chrome .*--headless`); correctness runs only by
implementers; timing by the bench agent in interleaved pairs vs `combined4`; no repo `tools/` or
`experiments/` edits; work under `work/2026-09-19/<agent>/`.

| Agent | Question | Method | Deliverable |
|---|---|---|---|
| R4T | Does per-timeline per-frame servicing scale with the subject's DOM depth / scroller structure? | M1-style fixture: 1k view-timelines at subject depth 5 / 20 / 40 / 60, one vs many scrollers, subjects inline vs block; measure animate + lifecycle self per frame. If depth-dependent: flatten carriers in the emitter (2-layer smoke, then bundle `R4T`) | fitted µs/timeline/frame vs depth; bundle if positive |
| R4S | Can small hops (scores 97, LN stats) use container-unit readback inside a layout pass, freeing a frame slot per layer (3.0 → 2.5 frames/layer)? | dependency analysis + 2-layer smoke; bundle `R4S` | frames/layer, bundle |
| R4C | Is a 32-token generation feasible with combined4's emitter? What grows with position and how fast? | build combined4 at capacity 32; find/derive the 32-token reference ids; one passive run; per-token times, RSS; identify the slope terms | feasibility + slope fixes |
| R4X | Any readback / vector primitive not yet in the catalog (audit E1–E6) that beats view-timelines? | enumerate CSS/Blink mechanisms, check catalog, fixture the plausible ones | ranked candidates with measured constants |
| B5 | Paired benches of R4T/R4S (and capacity-32 runs) vs combined4 | B4 protocol, keyboard trigger | rows in bench/results.md |
