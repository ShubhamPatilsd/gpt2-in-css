# R5G — stock Chrome launch flags vs the renderer's memory footprint (combined7, 8 tokens) — 2026-09-24

STATUS: DONE 18:0x — 4 flag sets, 4 valid pairs (n=1 each) + 1 invalidated pair; verdict: no stock flag cuts memory at an acceptable time cost; keep `--js-flags=--heap-growing-percent=10` alone (§4). Log: `R5G.log.md`; scratch/harness/runs: `R5G/` (`R5G/runs/combined7/<label>-{ref,flag}.json`, `R5G/analysis-<label>.md`).

## 0. Question and constraints

R5A §2: at token 8 the renderer's 6.24 GB footprint is Oilpan 3.9 GB (0.92 GB live → ≈3 GB swept garbage kept committed), decoded webfonts 0.87 GB
(malloc, fixed while referenced), font instances/shape caches ≈0.83 GB (purgeable), PartitionAlloc 0.35 GB. R5M §1.6: no stock cppgc knob was known;
simulated critical pressure on the idle bundle released 0. The harness and the user-facing launcher (`tools/launch_browser_gpt2.py`) already pass one
`--js-flags=--heap-growing-percent=10`. Task: find STOCK Chrome 153 launch flags (page stays JS-free; nothing that changes page semantics) that lower the
footprint during an 8-token `combined7` run, and measure their time cost, one flag set per run, each paired against a no-flag combined7 run taken
immediately before under one CHROME.lock hold.

## 1. Flag inventory (from `strings` of `Google Chrome Framework` 153.0.8010.53 — no Chrome launched for this)

| candidate from the brief | in this build? | verdict before testing |
|---|---|---|
| (1) `--enable-low-end-device-mode` | yes (switch present; `disable-low-end-device-mode` too) | test. `SysInfo::IsLowEndDevice()` → the renderer sets V8 `--optimize-for-size` programmatically (the literal `--optimize-for-size` is in the binary next to the renderer-process init strings), Blink caches shrink, `MemoryPressureListenerRegistry::IsLowEndDevice()` purge paths |
| (2) `--enable-features=` PartitionAlloc reclaimer | `PartitionAllocMemoryReclaimer`, `MemoryReclaimerPressureListener`, `PartitionAllocEventuallyZeroFreedMemory` exist | NOT tested: the reclaimer is default-on and its interval param name cannot be verified from the binary (a wrong name silently re-enables the default); the PA/malloc share that is purgeable (≈0.8 GB) already shows the periodic purge drops in R5A's dumps (−129/−522 MB). Note: Playwright already passes `--enable-features=CDPScreenshotNewSurface`; a second `--enable-features` switch replaces it (Chrome keeps the last) |
| (3) cppgc knobs via `--js-flags` | V8 flags present: `cppgc_random_gc_interval` (debug, standalone-heap only), `cppgc_young_generation` ("run young generation garbage collections in Oilpan (experimental)" — may be read-only in Chrome builds), plus the unified-heap policy flags `optimize_for_size` ("Enables optimizations which favor memory size over execution speed"), `memory_saver_mode` ("Forces memory saver mode… keep memory footprint low at the expense of extra cpu cycles"), `memory_reducer`, `memory_reducer_gc_count/delay_ms`, `heap_growing_percent`, `gc_global`, `compact_on_every_full_gc` | test `--optimize-for-size` and `--memory-saver-mode` (combined with `--heap-growing-percent=10` in ONE `--js-flags` switch — Chrome keeps only the last `--js-flags`). Mechanism: Blink's Oilpan is V8's CppHeap; GCs are scheduled by V8's global allocation limit, and the CppHeap sweeps with `FreeMemoryHandling::kDiscardWherePossible` (returns swept pages/free ranges to the OS) ONLY when the GC carries `kReduceMemoryFootprint`; V8 sets that flag on limit-triggered GCs when `Heap::ShouldOptimizeForMemoryUsage()` is true = `--optimize-for-size` ∨ memory-saver ∨ best-effort priority ∨ high memory pressure. Otherwise (today's runs) swept garbage stays committed — exactly R5A's 3 GB. `--gc-interval` is V8-allocation-only (no JS here) |
| (4) lower memory-pressure thresholds | no `memory-pressure-thresholds*` switch in this build (ChromeOS-only); macOS renderers get pressure from the browser's `dispatch_source` monitor, not tunable | no stock flag; the only stock trigger is CDP `Memory.simulatePressureNotification` (harness-side, not available to the user-facing launcher) |
| (5) GPU-side | – | skipped per brief |

## 2. Method

Harness = `R5G/run_bench_r5g.sh` (copy of `B6/run_bench6.sh`; diffs: outputs under `R5G/runs/`, log lines to `R5G.log.md`, `R5G_JS_FLAGS` / `R5G_EXTRA_ARGS`
passthrough to `R5G/bench_native_r5g.mjs` (copy of `B0/bench_native.mjs`, diff = the args block + two JSON fields), `vm_stat` + `vm.swapusage` snapshot
at START and END, `DEBUG=pw:browser` so Chrome's stderr (V8 flag warnings) lands in `<label>.stdout.log`; coordinator's 16:0x gate: AC AND ((disk ≥ 4 GB
AND swap < 4,000 MB) OR (disk ≥ 3 GB AND swap < 3,000 MB)), polled 60 s before the lock and again inside the harness before each launch).
Pair driver `R5G/pair.sh`: mkdir `CHROME.lock` (poll 5 s), owner `R5G pair <label> <pid> <time>`, `touch -c` every 30 s, rmdir only own; ref =
`combined7` with the stock harness args (heap=1, `B0_TRIGGER=keyboard`, passive, untraced), then `combined7` + the flag set, back-to-back; rc 8 (gate
closed > 10 min under the lock) → release, wait outside, retry under a new label. One pair per flag set (single pair — see caveat in §3).
Per run: per-token s (harness JSON `tokenEvents`), renderer RSS per token (max of the 1 Hz `ps` samples in each token's window) + at token 8 + peak,
RecalcStyleCount/LayoutCount per token and 8-token totals (must be identical between arms — flags may not change pass structure), ids 8/8, swap/vm_stat
before and after, the launch args as recorded by the harness.

## 3. Results — one pair per flag set (candidate − the combined7 no-flag run immediately before it, same CHROME.lock hold; n = 1, so every Δ below is a single-pair number and inherits today's swap-loaded machine noise)

Reference for the noise floor (the four no-flag combined7 refs of this agent, 16:16–17:55): median 17.0 / 17.0 / 16.8 / 16.9 s/token, RSS peak 4598 / 4446 / 4477 / 4513 MB (spread 152), **phys_footprint peak 6383 / 6152 / 6256 MB (spread 231; matches R5A's memory-infra footprint 6.24 GB and B5's clean-state RSS 5.7–6.0 GB — today's `ps` RSS undercounts by ≈1.8 GB of compressed pages)**, settled footprint 10 s after token 8: 5868 / 4084 / 3878 MB (the settle value depends on when macOS compresses, so it is not usable as a statistic). Pass structure of every ref: 3486 recalcs / 512 layouts over 8 tokens (249 215 359 359 503 503 647 647 / 63 64 64 …).

| flag set (added to the stock args; heap flag kept) | pair | flags reached the renderer? | ids | passes identical? | Δ RSS peak MB | Δ RSS@tok8 MB | Δ footprint peak MB | Δ settled RSS / footprint MB (10 s after tok 8) | Δ median s/tok | Δ total s (8 tok) | Δ page load | per-token Δ footprint MB (1–8) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|
| `--js-flags="--heap-growing-percent=10 --optimize-for-size"` | `o4s` (16:16–16:21, pre-footprint harness; ref CONTENDED by duetexpertd 97 %) | yes (args recorded; no V8 stderr warning) | 8/8 | yes (3486/512) | **+413** (4598 → 5011) | +300 | n/a | n/a | −1.0 (17.0 → 16.0) | −3.8 | **+32.1 s** (2.5 → 34.6 s) | n/a |
| same | `o4s-b` (17:52–17:58, footprint harness; clean) | yes | 8/8 | yes | **−379** (4513 → 4134) | +134 | **−201** (6256 → 6055) | +852 / +120 | +0.4 (16.9 → 17.3) | +4.6 | **+31.7 s** (2.5 → 34.3 s) | −217 −457 −222 −470 +52 0 −217 −201 |
| `--js-flags="--heap-growing-percent=10 --memory-saver-mode"` | `memsaver` (17:47–17:52; ref CONTENDED load1 6.8) | yes | 8/8 | yes | −84 (4477 → 4393) | +289 | **+155** (6152 → 6307) | −194 / −2 | +0.3 (16.8 → 17.1) | +4.2 | +0.1 s | −274 −368 −743 −470 −32 −361 +22 +155 |
| `--enable-low-end-device-mode` | `lowend-r2` (17:33–17:47; clean; retry of the invalid `lowend`) | yes (switch recorded) | 8/8 (token 8 landed during the final readback, untimed) | **NO** (7 timed tokens: 3423 recalcs vs 2835 for the ref's first 7 = +588; layouts 504 vs 448 = +56) | **−983** (4446 → 3463) | – (only 7 tokens captured in the 600 s cap) | **−2767** (6383 → 3616) | −544 / **−2266** | **+60.0** (17.0 → 77.0; per token 36.9 56.8 68.9 77.0 81.0 92.1 104.6 s, slope +10 s/token) | +461 (597.5 s for 7 tokens, hit the cap) | +0.06 s | −1188 −1585 −1653 −2208 −2356 −2630 −2957 |
| `--enable-low-end-device-mode` | `lowend` (16:21–16:34) | – | ref 8/8 | – | **INVALID**: R5X built three bundles at ≈16:23 → swap 3.5 → 5.3 GB, disk → 0; ref tokens 6/7 took 29.0/39.1 s with the renderer's RSS falling to 350/587 MB (swapped out); the flag arm was refused by the machine gate for 10 min under the lock (rc 8) → lock released, whole pair re-run as `lowend-r2` | | | | | | | |

Reading, set by set:
- **`--optimize-for-size` (o4s, o4s-b)**: the flag is active (both arms' launch args recorded; the +32 s page load in both pairs is the signature — V8's `ShouldOptimizeForMemoryUsage()` turns every allocation-limit GC during the 40 MB stylesheet parse into a memory-reducing one). RSS peak flips sign between the two pairs (+413 / −379 MB) → RSS is at the noise floor here, as the coordinator suspected. The phys_footprint column (o4s-b only) shows a small, mostly same-signed reduction: −200…−470 MB in 6 of 8 tokens, −201 MB at the peak — i.e. ≈3 % of 6.2 GB, **inside the 231 MB ref-to-ref footprint spread**, so not established. The ≈3 GB of committed-but-free Oilpan pages (R5A) did NOT go away: cppgc's discard-on-sweep only returns free ranges inside swept pages, and the head/V-leaf garbage is re-allocated every pass, so the pages are re-faulted before the OS sees them. Time: +0.4 s/token and +4.6 s per 8 tokens in the clean pair (within noise), but **+32 s of page load is a certain cost**.
- **`--memory-saver-mode` (memsaver)**: active (no warning), no load penalty, footprint peak +155 MB (noise), RSS@tok8 +289, +0.3 s/token (ref contended). Null result.
- **`--enable-low-end-device-mode` (lowend-r2)**: the only set with a memory effect that survives the noise — **footprint peak −2.8 GB (6.4 → 3.6 GB), −1.2…−3.0 GB in every token, settled −2.3 GB** — but at **4.5× the time per token (17 → 77 s median, growing to 105 s by token 7; style 57 → 393 s, layout 44 → 171 s over the run) and 588 extra recalcs + 56 extra layouts**: low-end mode purges Blink's caches (matched-properties / computed-style / font instance / shape caches) on its own schedule, so every pass re-resolves what the caches saved and the pass structure changes (the extra recalcs mean the page's dependency graph was re-walked, not that the model changed — ids stayed 8/8). This is memory-for-time in the wrong direction for this project (the whole round is about s/token) and it changes pass counts, which the brief requires to be identical.
- Candidates not run and why (§1): PartitionAlloc reclaimer interval (param name unverifiable; default-on), `--cppgc-young-generation` (experimental, likely read-only in Chrome builds; dropped in favour of the o4s-b repeat that the coordinator's RSS-vs-footprint question needed), memory-pressure thresholds (no macOS switch), GPU flags (out of scope). CDP `Memory.simulatePressureNotification` per token remains the only stock lever that could force memory-reducing GCs at chosen moments, and it is harness-side only (R5M's idle test released 0; a per-token arm was never run).

## 4. Recommendation for `tools/launch_browser_gpt2.py` (no repo edit made)

**Keep the launcher as it is: one `--js-flags=--heap-growing-percent=10` (default 10) and nothing else.** No tested stock flag reduces the renderer's footprint at an acceptable time cost:
- do NOT add `--optimize-for-size`: +32 s page load for a ≤ 200–470 MB (≈3 %, within noise) footprint change and no s/token gain;
- do NOT add `--memory-saver-mode`: no effect;
- do NOT default to `--enable-low-end-device-mode`: −2.8 GB footprint but 4.5× slower per token and a different pass structure.

If a memory-constrained fallback is wanted for users on ≤ 8 GB machines, the exact addition would be an opt-in, clearly labelled as a 4–5× slowdown:
```python
parser.add_argument("--low-memory", action="store_true",
                    help="Chrome low-end-device mode: ~2.8 GB less renderer footprint at capacity 8, but 4-5x slower per token (R5G)")
...
if args.low_memory:
    command.append("--enable-low-end-device-mode")
```
(`--enable-low-end-device-mode` is a plain Chrome switch and composes with the existing `--js-flags`; if any V8 flag is ever added, it must be merged into the ONE `--js-flags` string — Chrome keeps only the last `--js-flags` switch.) I would not ship it by default.

Machine-state caveat: all four pairs ran on the 16 GB machine with 3.2–3.6 GB of swap in use; `ps` RSS excluded ≈1.8 GB of compressed pages (footprint 6.2–6.4 GB vs RSS 4.4–4.6), which is why the RSS columns are unreliable and the footprint columns were added mid-task (the `o4s` pair predates them).
