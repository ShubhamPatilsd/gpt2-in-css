# R4M — round-4 merge: `bundles/combined6` = combined4 (R3M) + R4S small-hop score chain (`R4S_SMALL_HOPS`) + R4D capacity fixes (`R4D_*`); `bundles/combined6-c32` = the same at capacity 32 with `--value-layout widths` (demo candidate)

Agent R4M, 2026-09-21. Tools copy `work/2026-09-19/R4M/tools` (+ `experiments`, `data`, `assets -> ../F4/assets`, `global-projection-assets -> ../F2/…` symlinks, same targets as R3M's).
Bundles `work/2026-09-19/bundles/combined6` and `bundles/combined6-c32` (BUILD.md = recipe + flag table + merge notes + offline results + `diff -ruN -x __pycache__ R3M/tools R4M/tools`).
Scratch (reference builds, checkers, harness copy, run data): `work/2026-09-19/R4M/`. Log: `R4M.log.md`. Nothing under the repo's `tools/`, `experiments/` or other agents' directories was touched; no commits.

## 0. Headline

- **combined6 (capacity 8) = combined4 + R4S + R4D, READY** (01:22): 8/8 ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]`, verify rc 0, LayoutCount 527 (combined4 629), `finalResidualError` rmse 0.0161 (combined4 0.0176). R4T excluded at build time (its smoke had failed); merge 0 rejects for R4S, 2 adjacent-line rejects for R4D on R4S resolved as exact-string edits; all new flags OFF reproduces combined4 byte-for-byte, union builds reproduce `bundles/R4S` / `combined5` / `combined4-c32{,b,c}`; each owner's offline checker passes at both capacities.
- **combined6-c32 (capacity 32, `--value-layout widths`, with R4S) READY** (01:53): run 1 Hello **32/32, 872.7 s** (k=1 20.1 / 8 18.3 / 16 23.2 / 24 33.4 / 32 43.6 s; 11.65 + 0.933·k); run 2 prompt 40 "I" via the new harness knob `B0_PROMPT_TOKEN` **32/32, 936.6 s** (20.0 / 18.3 / 25.3 / 36.1 / 46.1; 11.69 + 1.051·k), text "I.⏎⏎The first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so excited to try it." — the verified non-looping demo. RSS peak 6.2 GB.
- **Finding: R4S is a loss at capacity 32.** combined6-c32 is slower than R4D's `combined4-c32c` (758.7 s, 12.8 + 0.65·k) despite faster early tokens: RecalcStyleCount per token = **126.6 + 70.8·k** (c32c: flat 84) — the 192-deep score chain's interleaved container recalcs, and the V-row work they trigger, scale with the filled positions (§4.1). At capacity 8 (48-deep chain, p ≤ 8) R4S is the expected −0.6 s/token win (B5 to confirm).
- **combined7 = combined6 + R4T** (`bundles/R4T/READY` 01:38): `bundles/combined7` (capacity 8, runs, WITH R4S, `R4T_CONSUMER_CHUNK=64`) and — after the finding — `bundles/combined7-c32` **rebuilt WITHOUT R4S** (= combined4-c32c + R4T, widths). Flag-off builds reproduce combined6 / combined4-c32c byte-for-byte; R4T's checker passes both; capacity-32 inherit audit clean (only `--lp-*` are forwarded across the chunk boundary, R4T's fix present). Chrome: **combined7 READY 02:17** (8/8 ids, verify rc 0 with the full KV readback, LayoutCount 544, residual rmse 0.0161); combined7-c32 run A prompt 40 (READY gate) → run B Hello: PENDING-HEADLINE-7
- Harness: `R4M/bench_native.mjs` = B0's + `B0_PROMPT_TOKEN` (Playwright `selectOption`, verified by readback); `R4M/verify_wrapper.py` + patched `R4M/correctness_run.mjs` for R4D's per-head V lists (F4's harness read the packed list → the stock verify crashed on null V halves; K-half cache errors identical class to combined4's).

## 1. Merge

- **R4T is not in combined6** (coordinator 00:46): R4T's 2-layer smoke failed correctness (`[44873, 9890]` vs `[11, 3387]`, flag-off reference smoke correct), so `bundles/R4T/READY` never appeared; if R4T lands it becomes combined7. Its diff is merge-ready: on the R4S+R4D tree only the adapter import line rejects (`R4M/apply_r4t_import.py`); the 3-way preview built (`R4M/scratch/p8t`, manifest `r4tConsumerChunk 64`) and `R4T_CONSUMER_CHUNK=0` reproduced the R4S+R4D build byte-for-byte (log 00:17).
- Base `cp -R R3M/tools R4M/tools` (cmp-identical). `patch -p1 -F3 -N < R4S/tools-vs-R3M.diff`: 0 rejects. `patch -p2 -F3 -N < R4D/tools-vs-R3M.diff` (+ `r4d_flags.py` copied — R4D's diff is `diff -ru` without `-N`): **2 rejects, both adjacent-line overlaps with R4S in the same two files**, resolved by `R4M/apply_conflicts.py` as exact-string edits: (1) the adapter import; (2) R4D's hide-unfilled/gate-scores block whose anchor line (`html{timeline-scope}`) R4S wrapped in `if not r4s.SMALL_HOPS:` — inserted before the guard. **Merge decision:** `R4D_GATE_SCORES` (default OFF) is forced off under `R4S_SMALL_HOPS` — its selector targets the score scroller R4S removes, and `display:none` on an R4S anchor row would invalidate the chain's `anchor-size()`; the `--fv-S` masking it duplicated is unchanged; manifest `r4dGateScores` reflects the effective value. Both diffs cmp-identical to the owners' BUILD.md diffs (R4D's re-diffed against R4D/tools after combined5 READY); new modules cmp-identical to the owners'.
- Semantic interaction R4S × R4D (checked in the built CSS/HTML): R4D's `@container fvscache style(--fvq-S:0){.fvs-v-*-S{display:none}}` addresses the named container on `.fvs-query`, so the unnamed `.fvs-sc` size containers R4S nests above the V rows are skipped by the query; `--fvs-nbase` (inherits:true) and `--fs-H-S` (inherits:true under R4S) flow through the chain to the V rows; R4D's per-head V leaf lists and R4S's chain touch disjoint elements; 0 `.fvs-score-source` references remain.
- Coordinator (00:4x): combined6-c32 uses `--value-layout widths` (R4D's c32c: 758.7 s vs c32b 905.9 s, 32/32 ids on Hello; not bit-identical numerics); combined6 (capacity 8, for B5's paired bench) stays on the exact `runs` layout. `R4M/compile.sh` takes `VALUE_LAYOUT`.

## 2. Offline verification (R4M/scratch reference builds; `R4M/compare_bundles.py`)

| build | reference | result |
|---|---|---|
| `p8-alloff` (all 6 new flags off) | `bundles/combined4` | **index.html byte-identical; runtime.css identical (URL-normalised); manifest +6 keys (false/null)** |
| `p32-alloff` | `bundles/combined4-c32` | identical likewise |
| `p8-noR4D` (only R4S) | `bundles/R4S` | identical (manifest +5 keys) |
| `p8-noR4S` (only R4D) | `bundles/combined5` | identical (manifest +1 key) |
| `p32-noR4S` (only R4D, runs) | `bundles/combined4-c32b` | identical |
| `p32w-noR4S` (only R4D, widths) | `bundles/combined4-c32c` | identical |
| `bundles/combined6` / `combined6-c32` | `scratch/p8` / `scratch/p32w` | URL-normalised twins, 0 manifest differences |
| `R4S/offline_check.py` p8 vs p8-noR4S (8); p32 vs p32-noR4S and p32w vs p32w-noR4S (32) | R4S off | `RESULT: PASS` ×3 (cap 32: elements +188, max depth 238 / reader 233, chain 192 containers) |
| `R4D/rule_diff.py` p8-noR4D vs p8; p32-noR4D vs p32 | R4D off | differing families = exactly R4D's BUILD.md list; widths vs runs differ only in the 384 `.fvs-v-H-S` rules |
| font witnesses | combined4, R4S, combined5, combined4-c32/b/c | 283/283 identical (keys modulo tools dir) |
| NumPy reference ids (merged tools) | — | 8-token = expected; 32-token teacher-forced + free-running = saved ctx32 ids |
| `launch_browser_gpt2.py --check` | — | 285 static files, `runtimeJavaScript: false` (both bundles) |

Sizes: combined6 runtime.css 38,846,142 B / index.html 6,512,942 B (combined4 39,880,338 / 6,508,382); combined6-c32 50,195,446 / 7,198,372 (combined4-c32c 50,275,787 / 7,194,680).

## 3. Chrome — combined6 (capacity 8) correctness run

ONE passive run (NOT a timing run), `R4M/run_correctness.sh combined6` (R3M's watchdog harness with R4M paths: owner-marked lock, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), 2026-09-21 01:16:25–01:19:27 under `CHROME.lock`
(waited 1,605 s behind R4X). Power: AC (81 %, not charging); load { 5.72 5.76 5.66 }. Results in `work/2026-09-19/R4M/run-combined6/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0 (unchanged tool, run through `R4M/verify_wrapper.py`, see below):
  tokenAgreement 8 × True, originalFloatAgreement 8 × True, finalHeadMatchesActualInput True, text "Hello, I'm sorry, but I'm"; `finalResidualError` rmse **0.016055** / max **0.11652**
  (combined4 0.017645 / 0.13388; R4S alone 0.017219 / 0.16788 — same 1e-2 class, ids identical).
- **Harness readback gap (not a page issue):** F4's `correctness_run.mjs` reads the packed V list `--fc-v-S` from each bank; with `R4D_UNPACK_V` the V list is stored as 12 per-head lists
  `--fc-v-S-H`, so the V half of every KV cache entry came back null (96 × 768) and the stock verify crashed in `profile_hybrid_twelve_block.error` (TypeError on None). `R4M/verify_wrapper.py`
  replaces the nulls by NaN (original kept as `verification-vectors.raw.json`), runs the unchanged verify (rc 0; `cacheErrors` rmse None for the V-half-less entries) and adds the **K-half cache
  errors** to `numerical-results.json`: 96/96 complete, rmse median 0.0019 / max 1.492 (layer 11), abs max 5.62 — the identical class as combined4's run (0.0018 / 1.493 / 5.624) and R4S's
  (0.0019 / 1.494 / 5.629), recomputed from their `verification-vectors.json` with the same code. `R4M/correctness_run.mjs` now concatenates the per-head lists when the packed one is empty (future runs).
- Whole-run counters (harness idle → end): RecalcStyleCount 3,752, LayoutCount **527** (combined4 985 / 629; R4S alone 3,759 / 535 — with R4S the RecalcStyleCount includes the interleaved
  container recalcs and is no longer a pass count, R4S.md §6); Nodes 132,214.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run): 23.2, 11.7, 18.5, 11.7, 17.5, 19.6, 17.5, 17.8 s = **137.4 s** total (cumulative 23.2, 34.9, 53.3, 65.0, 82.5,
  102.1, 119.6, 137.4; combined4's correctness run 158.6 s, R4S's 146.3 s, combined5's bench_native run 150.8 s). B5's paired protocol decides the s/token.
- `bundles/combined6/READY` created 2026-09-21 01:22.


## 4. Chrome — combined6-c32 32-token runs (demo candidate)

### 4.1 Run 1 — default prompt "Hello" (15496) vs `R4C/reference_ids_32.json` — **32/32 ids, 872.7 s** (`R4M/run-combined6-c32/c32-run1.summary.md`)

ONE passive run, `R4M/run_c32.sh combined6-c32 c32-run1` (R4C's pattern: `R4M/bench_native.mjs` = B0's + prompt knob, keyboard trigger, heap flag ON, trace OFF, 1 Hz `#token-k-captured.done`
poll, RSS via `ps` at 1 Hz), 01:38:05–01:53:20 under `CHROME.lock` (waited 1,110 s; AC; load 6.6 at start — other agents' Chrome/compiles, comparable to c32c's 6–8).

- ids **32/32** = `R4C/reference_ids_32.json` (text "Hello, I'm sorry, but I'm not sure if you're aware of this. I'm not sure if you're aware of this. I'm not sure"); `bundles/combined6-c32/READY` created 01:53.
- **Curve** (s/token): k=1 **20.1**, 8 **18.3**, 16 **23.2**, 24 **33.4**, 32 **43.6**; total **872.7 s**; median 24.4; min 16.0 (k=2); max 45.9 (k=30). Fit tokens 2..32: **11.65 + 0.933·k** (rmse 3.0);
  style 3.9 + 0.38·k, layout 2.6 + 0.44·k, other ≈ 5.3 + 0.11·k. RSS renderer peak **6,246 MB** (before run 1,916; at end 4,692); LayoutCount 64/token flat.
- **vs the references**: combined4-c32 (R4C) 1,132.9 s (16.3 + 1.14·k); combined4-c32b (R4D flags) 905.9 s (13.4 + 0.89·k); **combined4-c32c (R4D + widths) 758.7 s (12.8 + 0.65·k, layout 2.66 + 0.27·k, RecalcStyleCount 84/token flat)**.
  combined6-c32 = c32c + R4S: faster for the first ~10 tokens (k=2–4: 16.0–16.9 vs c32c 17.7–18.4; c32c's k=8 was 21.6) but **slower overall: 872.7 vs 758.7 s (+15 %)**, the slope 0.93 vs 0.65 s/token/position.

**Finding — R4S at capacity 32 is a position-dependent loss (coordinator 01:5x; evidence = the per-token counters, no fixture needed):**
`RecalcStyleCount` per token = **126.6 + 70.8·k** (c32c: 84.3 − 0.03·k, flat; combined6 at capacity 8: 3,752 for 8 tokens ≈ 470/token, R4S alone 3,759). With R4S the 192-deep
`position:fixed; container-type:size` score chain (depth 238) resolves inside the qkv pass's layout by interleaved container recalcs, and Blink counts each one; the count grows by ≈ 71 per
filled position per token ≈ 12 layers × 6 containers per position (each position adds 12 score carriers = 6 containers whose sizes change once a slot is filled), so the interleaved recalcs
— and the layout work they trigger below the chain (768 V rows × (1+p) glyphs restyled at the container's layout) — scale with the filled positions. Layout duration slope 0.44 vs c32c's 0.27
s/token/position and style 0.38 vs 0.35 carry the difference: at k ≥ 12 the added interleaved work outweighs the removed score-readback pass (−12 passes, −6 frames/token — the −0.6 s that R4S
wins at capacity 8, where the chain is 48 deep and p ≤ 8). Consequence: **combined7-c32 is rebuilt WITHOUT R4S** (= combined4-c32c + R4T) and combined7 (capacity 8) keeps R4S for B5's bench;
a capacity-32 R4S would need a chain whose cost does not grow with p (e.g. containers only for filled slots, or the V rows outside the chain's subtree).

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20.1 | 20 | 11 | Y | 217 | 65 | 7.5 | 4.6 | 17.6 | 3927 | 3927 |
| 2 | 16.0 | 36 | 314 | Y | 228 | 64 | 5.7 | 4.7 | 16.0 | 4322 | 4050 |
| 3 | 16.6 | 53 | 1101 | Y | 360 | 64 | 5.8 | 5.0 | 16.6 | 4571 | 4567 |
| 4 | 16.9 | 70 | 7926 | Y | 372 | 64 | 5.7 | 5.4 | 17.0 | 4891 | 4424 |
| 5 | 23.6 | 93 | 11 | Y | 504 | 64 | 10.3 | 6.7 | 23.5 | 3913 | 1987 |
| 6 | 22.5 | 116 | 475 | Y | 516 | 64 | 8.8 | 7.2 | 22.4 | 4488 | 4488 |
| 7 | 18.2 | 134 | 314 | Y | 648 | 64 | 6.0 | 6.2 | 18.1 | 5526 | 5526 |
| 8 | 18.3 | 152 | 1101 | Y | 660 | 64 | 6.3 | 6.1 | 18.2 | 5770 | 5770 |
| 9 | 19.0 | 171 | 407 | Y | 792 | 64 | 6.1 | 7.0 | 19.1 | 5916 | 5916 |
| 10 | 18.9 | 190 | 1654 | Y | 804 | 64 | 6.2 | 6.5 | 18.6 | 6149 | 6144 |
| 11 | 18.7 | 209 | 611 | Y | 936 | 64 | 6.7 | 6.4 | 19.0 | 6116 | 5935 |
| 12 | 20.2 | 229 | 345 | Y | 948 | 64 | 6.7 | 7.6 | 20.5 | 6246 | 5844 |
| 13 | 21.5 | 251 | 821 | Y | 1080 | 64 | 7.0 | 7.4 | 20.8 | 6071 | 5595 |
| 14 | 23.3 | 274 | 3910 | Y | 1092 | 64 | 8.9 | 7.9 | 23.3 | 6036 | 5161 |
| 15 | 22.6 | 297 | 286 | Y | 1224 | 64 | 8.2 | 7.8 | 22.4 | 5734 | 5476 |
| 16 | 23.2 | 320 | 428 | Y | 1236 | 64 | 8.2 | 8.4 | 23.0 | 6052 | 5303 |
| 17 | 25.2 | 345 | 13 | Y | 1368 | 64 | 9.3 | 9.2 | 25.1 | 5810 | 5472 |
| 18 | 25.7 | 371 | 314 | Y | 1380 | 64 | 9.8 | 9.0 | 25.5 | 5549 | 5403 |
| 19 | 29.1 | 400 | 1101 | Y | 1512 | 64 | 12.4 | 9.7 | 29.0 | 6020 | 5920 |
| 20 | 27.3 | 427 | 407 | Y | 1524 | 64 | 10.7 | 9.4 | 26.9 | 5900 | 5826 |
| 21 | 29.3 | 456 | 1654 | Y | 1656 | 64 | 13.0 | 9.4 | 29.4 | 5852 | 5852 |
| 22 | 28.4 | 485 | 611 | Y | 1668 | 64 | 11.1 | 9.9 | 28.0 | 5751 | 4920 |
| 23 | 30.7 | 515 | 345 | Y | 1800 | 64 | 12.9 | 10.6 | 30.5 | 5521 | 4731 |
| 24 | 33.4 | 549 | 821 | Y | 1812 | 64 | 13.3 | 13.2 | 34.1 | 5572 | 5256 |
| 25 | 39.1 | 588 | 3910 | Y | 1786 | 62 | 11.5 | 17.2 | 36.6 | 5755 | 3022 |
| 26 | 38.4 | 626 | 286 | Y | 2114 | 66 | 17.6 | 13.7 | 39.5 | 4305 | 2420 |
| 27 | 36.4 | 663 | 428 | Y | 2088 | 64 | 14.3 | 14.3 | 36.1 | 5070 | 4278 |
| 28 | 39.5 | 702 | 13 | Y | 2100 | 64 | 14.9 | 16.9 | 39.4 | 4645 | 4579 |
| 29 | 40.4 | 742 | 314 | Y | 2232 | 64 | 14.1 | 17.8 | 39.7 | 4942 | 4826 |
| 30 | 45.9 | 788 | 1101 | Y | 2244 | 64 | 13.9 | 22.9 | 45.7 | 4791 | 3263 |
| 31 | 40.8 | 829 | 407 | Y | 2376 | 64 | 15.5 | 17.0 | 40.3 | 4901 | 4806 |
| 32 | 43.6 | 873 | 1654 | Y | 2180 | 60 | 20.2 | 13.4 | 41.9 | 4850 | 4692 |

### 4.2 Run 2 — prompt token 40 ("I") via `B0_PROMPT_TOKEN=40` vs `R4P/reference_ids_32_40.json`

ONE passive run, `B0_PROMPT_TOKEN=40 REF_JSON=R4P/reference_ids_32_40.json R4M/run_c32.sh combined6-c32 c32-run2-p40`, 01:53:22–02:09:42 under `CHROME.lock` (AC; load 4.9–6.1).
The harness picked `<option value="40">` ("I") with Playwright `selectOption` before Run and verified `select.value = "40"` and body `--prompt-token = 40` (`prompt-selected` event); the page stays JS-free.

- ids **32/32** = `R4P/reference_ids_32_40.json` (free-running == teacher-forced reference); decoded text (`R4M/decode_ids.py`):
  **"I.\n\nThe first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so excited to try it."** — the non-looping demo text. No mismatch → no margin analysis needed
  (R4P's smallest margin on this trajectory is 9 at positions 20 and 26, `R4P/margins.json["40"]`). Appended to `bundles/combined6-c32/READY`.
- **Curve** (s/token): k=1 **20.0**, 8 **18.3**, 16 **25.3**, 24 **36.1**, 32 **46.1**; total **936.6 s**; median 27.6; min 15.9 (k=2); max 46.2. Fit tokens 2..32: **11.69 + 1.051·k** (rmse 2.3);
  style 2.9 + 0.52·k, layout 3.3 + 0.41·k. RSS renderer peak **6,212 MB**. RecalcStyleCount/token **126.4 + 70.8·k** — identical to run 1's fit (the R4S term does not depend on the prompt),
  LayoutCount 64/token flat.
- vs run 1 (Hello, 872.7 s, 0.93·k): +64 s / +7 %, the slope 1.05 vs 0.93 s/token/position with the same intercept — the "I" trajectory's tokens are costlier per position (style +0.14·k), consistent
  with a content-dependent term (distinct ids → more distinct V-glyph font instances / head work) on top of the R4S position term; same 32/32 correctness.

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20.0 | 20 | 13 | Y | 219 | 67 | 7.7 | 4.6 | 18.0 | 3898 | 3898 |
| 2 | 15.9 | 36 | 198 | Y | 226 | 62 | 5.4 | 4.6 | 15.4 | 4623 | 4623 |
| 3 | 16.8 | 53 | 198 | Y | 360 | 64 | 6.1 | 4.9 | 16.9 | 5117 | 4215 |
| 4 | 21.8 | 75 | 464 | Y | 372 | 64 | 8.6 | 6.7 | 22.2 | 4433 | 967 |
| 5 | 21.2 | 96 | 717 | Y | 504 | 64 | 7.2 | 7.0 | 20.5 | 4259 | 4253 |
| 6 | 17.6 | 113 | 1517 | Y | 516 | 64 | 6.2 | 5.4 | 17.5 | 5187 | 5187 |
| 7 | 18.0 | 131 | 314 | Y | 648 | 64 | 6.5 | 5.6 | 18.0 | 5566 | 5561 |
| 8 | 18.3 | 150 | 750 | Y | 660 | 64 | 6.4 | 5.8 | 18.2 | 5679 | 5667 |
| 9 | 19.1 | 169 | 373 | Y | 792 | 64 | 7.0 | 6.3 | 19.5 | 6068 | 6016 |
| 10 | 21.9 | 191 | 284 | Y | 804 | 64 | 7.1 | 7.7 | 21.3 | 5879 | 5278 |
| 11 | 21.7 | 212 | 467 | Y | 936 | 64 | 8.0 | 7.1 | 21.6 | 5804 | 5770 |
| 12 | 21.8 | 234 | 284 | Y | 948 | 64 | 7.6 | 7.5 | 21.8 | 5872 | 5872 |
| 13 | 23.3 | 257 | 262 | Y | 1080 | 64 | 8.4 | 8.3 | 23.6 | 6073 | 6009 |
| 14 | 24.2 | 282 | 1957 | Y | 1092 | 64 | 8.1 | 8.7 | 24.0 | 6110 | 5783 |
| 15 | 25.4 | 307 | 16918 | Y | 1224 | 64 | 10.0 | 8.3 | 25.4 | 5984 | 5686 |
| 16 | 25.3 | 332 | 3650 | Y | 1236 | 64 | 8.1 | 9.8 | 25.1 | 6212 | 4962 |
| 17 | 30.5 | 363 | 290 | Y | 1368 | 64 | 10.5 | 12.1 | 30.0 | 5363 | 4065 |
| 18 | 30.3 | 393 | 2822 | Y | 1380 | 64 | 12.8 | 10.0 | 30.1 | 5179 | 4191 |
| 19 | 29.7 | 423 | 257 | Y | 1512 | 64 | 11.0 | 11.3 | 29.4 | 4905 | 4781 |
| 20 | 30.3 | 453 | 6131 | Y | 1524 | 64 | 16.1 | 10.2 | 33.7 | 4743 | 4560 |
| 21 | 33.9 | 487 | 286 | Y | 1656 | 64 | 12.2 | 10.8 | 30.3 | 4539 | 3126 |
| 22 | 36.5 | 524 | 12912 | Y | 1668 | 64 | 15.4 | 13.1 | 36.3 | 4774 | 3360 |
| 23 | 35.3 | 559 | 32132 | Y | 1654 | 62 | 15.9 | 10.7 | 34.3 | 4802 | 3830 |
| 24 | 36.1 | 595 | 13 | Y | 1958 | 66 | 16.2 | 12.9 | 37.3 | 5299 | 4291 |
| 25 | 35.4 | 630 | 314 | Y | 1944 | 64 | 15.2 | 11.6 | 34.6 | 4856 | 3067 |
| 26 | 40.2 | 671 | 373 | Y | 1956 | 64 | 15.3 | 16.3 | 39.7 | 4683 | 4109 |
| 27 | 43.5 | 714 | 523 | Y | 2088 | 64 | 20.8 | 14.5 | 43.7 | 4549 | 4154 |
| 28 | 43.7 | 758 | 6568 | Y | 2100 | 64 | 21.2 | 13.6 | 42.9 | 4342 | 4030 |
| 29 | 43.3 | 801 | 284 | Y | 2232 | 64 | 15.0 | 19.7 | 43.0 | 4288 | 3836 |
| 30 | 43.2 | 844 | 1949 | Y | 2244 | 64 | 15.1 | 19.3 | 42.9 | 4326 | 4155 |
| 31 | 46.2 | 890 | 340 | Y | 2376 | 64 | 22.4 | 14.8 | 45.8 | 4315 | 3913 |
| 32 | 46.1 | 937 | 13 | Y | 2180 | 60 | 21.8 | 14.0 | 44.6 | 4224 | 3680 |



## 6. combined7 = combined6 + R4T (`bundles/combined7`, `bundles/combined7-c32`; coordinator 01:4x after `bundles/R4T/READY` 01:38)

### 6.1 Merge and offline

- `R4M/tools7` = `R4M/tools` + R4T's READY-time diff (172 lines; `diff -ru` without `-N` → `r4t_consumer_chunk.py` copied from R4T/tools; includes the `--lp-*:inherit` forwarding fix in
  `r3r_fold_hop.py` that made R4T's smoke pass). One reject (the adapter import line adjacent to R4S's/R4D's) → `R4M/apply_r4t_import.py`; `diff -rq tools tools7` = exactly R4T's 5 files + module.
- Builds 01:44 (nice 19 while combined6-c32's run 1 was in Chrome): `bundles/combined7` (cap 8, runs, manifest `r4tConsumerChunk 64`), `bundles/combined7-c32` (cap 32, widths).
  **`R4T_CONSUMER_CHUNK=0` reproduces `bundles/combined6` and `bundles/combined6-c32` byte-for-byte** (`scratch/p7-8-noR4T`, `scratch/p7-32w-noR4T`; manifest +1 key).
- `R4T/offline_check_r4t.py` combined7 vs combined6 and combined7-c32 vs combined6-c32: cap 8 **RESULT: PASS** (max animations per element (bundle): {'.shared-qkv-cN': 64, '.shared-attn-cN': 64, '.shared-fc-cN': 64, '.cache-bridge-cN': 64, '.loop-reader-cN': 64, '.bN-bridge-cN': 64, '.embedding-consumer-N': 64,…; consumer elements 1,200 vs 164; elements +124; non-consumer CSS identical; HTML identical modulo wrappers; manifest only `r4tConsumerChunk`); cap 32 **RESULT: PASS** (consumer elements bundle/ref: 1200 164; elements bundle/ref: 86627 86503 delta 124). Logs `R4M/offline_check_r4t-combined7{,-c32}.log`.
- Capacity-32 warning (consumers ≤ 64 animations; other `inherits:false` numbers forwarded one level): audited in the built CSS (`R4M.log.md` 01:5x): the only `inherits:false` registered numbers forwarded with `:inherit` across a consumer boundary are `--lp-*` (R4T's fix: `.loop-reader-cK` forwards `--lp-0..64K−1`, 4,992 declarations at both capacities; `.loop-reader-c11` holds 704 + its own 64, `.loop-input` copies 768); the other one-level forwards (`--feedback-N` ×32, `--pr-stamp`, `--frozen-prompt`, `--token`) are unchanged from combined6 and not on a chunked consumer. All stage outputs the chunked consumers publish (`--embed-*`, `--qkv-*`, `--ctx-*`, `--r-*`, `--hidden-*`) are registered `inherits:true`. Max animations per consumer element at capacity 32: see the checker line above (`.fvs-score-reader` no longer exists as an animation consumer under R4S; `.feedback-reader` 32).
- Static check: 285 files, no JS (both). Witnesses 283/283 identical to combined6.
- **combined7-c32 rebuilt WITHOUT R4S (01:58, coordinator after run 1's finding, §4.1)** = combined4-c32c + R4T (`R4S_SMALL_HOPS=0 R4T_CONSUMER_CHUNK=64 VALUE_LAYOUT=widths`; the R4S build is kept as `R4M/scratch/combined7-c32-withR4S/`). Flag-off (`scratch/p7-32w-noR4S-noR4T`) reproduces `bundles/combined4-c32c` byte-for-byte (manifest +2 keys); R4T's checker vs `bundles/combined4-c32c` all substantive checks pass (max 64 animations/element — `.fvs-score-reader` 384 is the untouched R4S-less score reader; loop-reader forwards 4,224; consumer elements 1,200 vs 164; elements +124; non-consumer CSS identical; HTML identical modulo wrappers; witnesses 283/283) and the only FAIL line is the manifest carrying the extra key `r4sSmallHops:false` (the merged tools include the R4S module; c32c's manifest has no such key). Re-run against the flag-off twin `R4M/scratch/p7-32w-noR4S-noR4T` (manifest with the key): manifest check passes and the only FAIL is the checker's raw (non-URL-normalised) CSS compare tripping on the scratch dir's one-level-deeper `url("../../../../…")` font paths — a path-depth artefact, not content (`compare_bundles.py` shows the twin identical to c32c after URL normalisation). Net: R4T's structural checks pass for combined7-c32 (`R4M/offline_check_r4t-combined7-c32-noR4S.log`, `…-vs-flagoff.log`). combined7 (capacity 8) keeps R4S.

### 6.2 Chrome — combined7 (capacity 8) correctness run

ONE passive run (NOT a timing run), `R4M/run_correctness.sh combined7` (R3M's watchdog harness with R4M paths: owner marker, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 81%; AC attached; not charging present: true; load { 5.55 5.01 5.56 }. Results in `work/2026-09-19/R4M/run-combined7/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.01605519804514142, 'maximum': 0.11651862085027176}, 'text': "Hello, I'm sorry, but I'm".
- Whole-run counters (harness idle -> end): RecalcStyleCount 3768, LayoutCount 544 (combined4: 985 / 629; R4S alone: 3,759 / 535 — with R4S the RecalcStyleCount includes interleaved container recalcs, R4S.md §6); Nodes 132338.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run; combined4's run: 22.0, 17.1, 17.2, 18.0, 24.2, 17.8, 24.7, 17.6 = 158.6 s; R4S's: 23.4, 11.9, 17.1, 18.7, 17.6, 18.6, 19.8, 19.2 = 146.3 s): 22.6, 33.6, 51.8, 68.7, 88.0, 108.4, 128.7, 146.8 s.
- Full KV cache readback (the R4M-patched `correctness_run.mjs` concatenates R4D's per-head V lists): 96/96 cache entries complete (K and V), `cacheErrors` rmse max 1.4815 / abs max 7.633 —
  the same class as combined4's run (V half 1.470 / 7.625) and R4S's (1.472 / 7.637); no wrapper needed this time. Per-token deltas from the capture times: 22.6, 11.0, 18.2, 16.9, 19.3, 20.4, 20.3, 18.1 s = 146.8 s
  (combined6's run 137.4 s — single runs at 5 s poll granularity, load 5.5; B5's pairs decide).
- READY: created.


### 6.3 Chrome — combined7-c32 32-token run

Protocol as §4 (`R4M/run_c32.sh`, ONE passive run each, keyboard trigger, heap flag ON). **Caveat: the machine was in active user use from ≈ 02:15 (load 8–30 at run A's start, `{ 8.35 18.17 14.11 }`;
run B started at `{ 7.56 6.50 8.0 }`) — absolute times from runs A/B/C are inflated relative to the 01:38–02:09 combined6-c32 runs (load 5–7) and R4D's c32c run (load 6–8).** RecalcStyleCount per token is
load-independent and flat at 84 for all no-R4S bundles (c32c, combined7-c32); style/layout durations are CDP main-thread times (contention-sensitive but not idle-inflated).

| run | bundle (capacity 32, widths) | R4S | R4T | prompt | ids | total s | k=1 / 8 / 16 / 24 / 32 s | fit tokens 2..32 | style s/token | layout s/token | RecalcStyle/token | RSS peak MB |
|---|---|---|---|---|---|---:|---|---|---|---|---|---:|
| R4D c32c-run1 (01:0x) | `combined4-c32c` | – | – | Hello | 32/32 | **758.7** | 22.0 / 17.7 / 21.3 / 26.9 / 35.2 | 12.8 + 0.65·k | 4.46 + 0.30·k | 2.66 + 0.27·k | 84 flat | 7,226 |
| §4.1 run 1 (01:38) | `combined6-c32` | on | – | Hello | 32/32 | 872.7 | 20.1 / 18.3 / 23.2 / 33.4 / 43.6 | 11.65 + 0.93·k | 3.87 + 0.38·k | 2.59 + 0.44·k | 126.6 + 70.8·k | 6,246 |
| §4.2 run 2 (01:53) | `combined6-c32` | on | – | 40 "I" | 32/32 | 936.6 | 20.0 / 18.3 / 25.3 / 36.1 / 46.1 | 11.69 + 1.05·k | 2.94 + 0.52·k | 3.30 + 0.41·k | 126.4 + 70.8·k | 6,212 |
| **run A** (02:30) | `combined7-c32` | off | 64 | 40 "I" | 32/32 | 1,050.1 | 22.3 / 24.7 / 33.1 / 37.9 / 49.7 | 15.8 + 1.02·k | **8.07** + 0.44·k | 3.11 + 0.47·k | 84 flat | 3,878 |
| **run B** (02:46) | `combined7-c32` | off | 64 | Hello | 32/32 | 929.7 | 21.7 / 19.1 / 30.9 / 35.3 / 47.4 | 11.1 + 1.07·k | 4.00 + 0.56·k | 3.21 + 0.38·k | 84 flat | 5,253 |
| **run C** (chain C) | `combined4-c32c` | – | – | 40 "I" | PENDING-RUNC-IDS | PENDING-RUNC-TOTAL | PENDING-RUNC-CURVE | PENDING-RUNC-FIT | PENDING-RUNC-STYLE | PENDING-RUNC-LAYOUT | 84 flat | PENDING-RUNC-RSS |

- **R4T (consumer re-chunk) is a regression at 12 layers**: with R4S off and everything else equal to c32c, run B (Hello) took 929.7 s vs c32c's 758.7 s (+23 %) and run A (prompt 40) 1,050 s; the
  style intercept doubles on run A (8.07 vs 4.46 s/token — 1,200 consumer elements instead of 164, each a style-recalc root with its own animation set, plus 4,224 `--lp-*:inherit` forwards
  per pass) and the style slope rises (0.44–0.56 vs 0.30). This matches B5's first paired R4T row (+2.3 s/token at capacity 8). Part of the absolute gap is the load caveat, but the style-time
  structure (flat RecalcStyleCount, higher style duration per pass) is not load-shaped. `bundles/combined7-c32/READY` exists (32/32 on both prompts) but **combined7-c32 is not the demo**.
- **combined6-c32 vs combined7-c32**: both slower than c32c for opposite reasons — R4S's position-dependent interleaved recalcs (§4.1) vs R4T's per-pass style cost.
- **Fastest verified prompt-40 demo: PENDING-DEMO-VERDICT**

**Run A per-token table (combined7-c32, prompt 40):**

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 22.3 | 22 | 13 | Y | 87 | 79 | 9.7 | 4.3 | 19.4 | 3675 | 3675 |
| 2 | 16.2 | 38 | 198 | Y | 84 | 76 | 6.9 | 4.2 | 16.1 | 3878 | 3850 |
| 3 | 17.5 | 56 | 198 | Y | 84 | 76 | 7.9 | 4.5 | 17.5 | 3805 | 3673 |
| 4 | 18.2 | 74 | 464 | Y | 82 | 74 | 8.1 | 5.2 | 18.3 | 3625 | 3470 |
| 5 | 21.2 | 95 | 717 | Y | 84 | 76 | 10.0 | 5.5 | 20.7 | 3554 | 3453 |
| 6 | 21.9 | 117 | 1517 | Y | 84 | 76 | 10.8 | 5.8 | 21.9 | 3446 | 3287 |
| 7 | 22.7 | 140 | 314 | Y | 84 | 76 | 11.0 | 6.3 | 22.6 | 3493 | 2874 |
| 8 | 24.7 | 165 | 750 | Y | 84 | 76 | 12.8 | 6.5 | 24.7 | 3579 | 2494 |
| 9 | 25.2 | 190 | 373 | Y | 82 | 74 | 11.5 | 8.0 | 24.9 | 3548 | 2428 |
| 10 | 27.5 | 217 | 284 | Y | 86 | 78 | 14.4 | 9.1 | 29.6 | 3480 | 3155 |
| 11 | 28.7 | 246 | 467 | Y | 82 | 74 | 9.8 | 10.0 | 25.6 | 3543 | 3477 |
| 12 | 27.1 | 273 | 284 | Y | 86 | 78 | 15.9 | 8.0 | 30.2 | 3502 | 2865 |
| 13 | 29.4 | 302 | 262 | Y | 84 | 76 | 15.6 | 8.1 | 30.1 | 3545 | 3003 |
| 14 | 31.1 | 334 | 1957 | Y | 84 | 76 | 12.7 | 8.4 | 27.7 | 3668 | 2959 |
| 15 | 32.4 | 366 | 16918 | Y | 84 | 76 | 16.7 | 9.0 | 32.3 | 3393 | 2928 |
| 16 | 33.1 | 399 | 3650 | Y | 84 | 76 | 18.1 | 9.2 | 33.5 | 3324 | 2272 |
| 17 | 34.0 | 433 | 290 | Y | 84 | 76 | 15.4 | 12.3 | 33.9 | 3493 | 2155 |
| 18 | 35.9 | 469 | 2822 | Y | 84 | 76 | 16.7 | 12.3 | 35.5 | 3207 | 2509 |
| 19 | 37.8 | 507 | 257 | Y | 84 | 76 | 15.3 | 15.3 | 37.1 | 3744 | 3063 |
| 20 | 35.1 | 542 | 6131 | Y | 84 | 76 | 14.7 | 13.5 | 34.6 | 3567 | 2956 |
| 21 | 37.7 | 579 | 286 | Y | 84 | 76 | 20.5 | 10.8 | 37.7 | 3454 | 3219 |
| 22 | 40.1 | 620 | 12912 | Y | 82 | 74 | 17.5 | 13.7 | 38.5 | 3498 | 3498 |
| 23 | 34.2 | 654 | 32132 | Y | 86 | 78 | 14.5 | 14.7 | 35.9 | 3346 | 2309 |
| 24 | 37.9 | 692 | 13 | Y | 84 | 76 | 21.4 | 9.8 | 37.6 | 3666 | 2537 |
| 25 | 40.4 | 732 | 314 | Y | 84 | 76 | 18.4 | 14.4 | 40.0 | 3693 | 2689 |
| 26 | 42.5 | 774 | 373 | Y | 84 | 76 | 21.7 | 12.8 | 41.6 | 3370 | 2619 |
| 27 | 43.2 | 818 | 523 | Y | 84 | 76 | 22.8 | 13.0 | 42.9 | 3682 | 2583 |
| 28 | 44.5 | 862 | 6568 | Y | 84 | 76 | 19.9 | 17.1 | 44.1 | 3546 | 2765 |
| 29 | 46.4 | 909 | 284 | Y | 84 | 76 | 21.4 | 17.3 | 46.1 | 3508 | 2079 |
| 30 | 46.5 | 955 | 1949 | Y | 84 | 76 | 20.1 | 18.2 | 45.9 | 3412 | 2838 |
| 31 | 45.4 | 1000 | 340 | Y | 84 | 76 | 23.1 | 16.1 | 46.8 | 3567 | 2596 |
| 32 | 49.7 | 1050 | 13 | Y | 80 | 72 | 14.8 | 22.8 | 46.4 | 3705 | 2475 |

**Run B per-token table (combined7-c32, Hello):**

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 21.7 | 22 | 11 | Y | 87 | 79 | 9.5 | 4.0 | 18.9 | 3884 | 3825 |
| 2 | 15.9 | 38 | 314 | Y | 84 | 76 | 6.8 | 4.1 | 15.9 | 4279 | 4279 |
| 3 | 16.6 | 54 | 1101 | Y | 84 | 76 | 7.1 | 4.4 | 16.6 | 4624 | 4602 |
| 4 | 17.0 | 71 | 7926 | Y | 84 | 76 | 7.5 | 4.6 | 16.8 | 4619 | 4430 |
| 5 | 16.2 | 87 | 11 | Y | 82 | 74 | 7.1 | 4.5 | 15.9 | 5170 | 4989 |
| 6 | 17.2 | 105 | 475 | Y | 84 | 76 | 7.4 | 5.1 | 17.1 | 5253 | 4881 |
| 7 | 17.9 | 122 | 314 | Y | 84 | 76 | 7.8 | 5.4 | 18.0 | 5167 | 4782 |
| 8 | 19.1 | 142 | 1101 | Y | 84 | 76 | 8.3 | 5.7 | 19.0 | 5049 | 4715 |
| 9 | 20.5 | 162 | 407 | Y | 84 | 76 | 8.6 | 7.0 | 20.4 | 4875 | 4775 |
| 10 | 19.9 | 182 | 1654 | Y | 84 | 76 | 8.5 | 6.7 | 20.1 | 5063 | 4739 |
| 11 | 22.5 | 204 | 611 | Y | 84 | 76 | 9.6 | 7.3 | 22.1 | 4888 | 4852 |
| 12 | 23.9 | 228 | 345 | Y | 84 | 76 | 9.2 | 9.0 | 23.8 | 4719 | 4593 |
| 13 | 25.6 | 254 | 821 | Y | 84 | 76 | 12.5 | 7.5 | 25.5 | 4650 | 4520 |
| 14 | 28.3 | 282 | 3910 | Y | 84 | 76 | 14.2 | 8.2 | 28.1 | 4588 | 3098 |
| 15 | 27.6 | 310 | 286 | Y | 84 | 76 | 13.9 | 7.9 | 27.4 | 4253 | 3470 |
| 16 | 30.9 | 341 | 428 | Y | 84 | 76 | 12.3 | 12.5 | 30.7 | 4835 | 4724 |
| 17 | 27.6 | 368 | 13 | Y | 84 | 76 | 11.4 | 10.6 | 27.5 | 5052 | 4941 |
| 18 | 27.9 | 396 | 314 | Y | 84 | 76 | 13.7 | 8.4 | 27.7 | 4912 | 4520 |
| 19 | 30.0 | 426 | 1101 | Y | 84 | 76 | 15.3 | 9.1 | 30.1 | 4850 | 4639 |
| 20 | 29.3 | 456 | 407 | Y | 84 | 76 | 10.6 | 12.6 | 28.9 | 4769 | 4347 |
| 21 | 31.0 | 487 | 1654 | Y | 84 | 76 | 13.4 | 11.7 | 31.0 | 4637 | 4346 |
| 22 | 29.9 | 516 | 611 | Y | 84 | 76 | 13.3 | 12.3 | 31.9 | 4727 | 4159 |
| 23 | 33.1 | 550 | 345 | Y | 84 | 76 | 14.9 | 10.2 | 31.1 | 4366 | 2937 |
| 24 | 35.3 | 585 | 821 | Y | 84 | 76 | 14.3 | 14.9 | 35.7 | 4336 | 3017 |
| 25 | 40.4 | 625 | 3910 | Y | 84 | 76 | 17.4 | 15.5 | 39.5 | 3820 | 2758 |
| 26 | 37.9 | 663 | 286 | Y | 84 | 76 | 19.5 | 11.7 | 37.9 | 3853 | 2731 |
| 27 | 43.7 | 707 | 428 | Y | 84 | 76 | 19.2 | 16.4 | 42.7 | 3856 | 2834 |
| 28 | 40.5 | 747 | 13 | Y | 84 | 76 | 21.4 | 12.0 | 40.2 | 3740 | 2945 |
| 29 | 44.8 | 792 | 314 | Y | 84 | 76 | 21.4 | 15.3 | 44.1 | 3608 | 2776 |
| 30 | 44.8 | 837 | 1101 | Y | 84 | 76 | 22.5 | 14.5 | 44.5 | 3619 | 2746 |
| 31 | 45.4 | 882 | 407 | Y | 84 | 76 | 24.3 | 13.9 | 45.6 | 3623 | 2771 |
| 32 | 47.4 | 930 | 1654 | Y | 80 | 72 | 22.7 | 12.9 | 45.4 | 3432 | 2558 |

PENDING-RUNC-TABLE

## 5. Residual risks / follow-ups

- **combined6-c32 numerics are not bit-identical to combined6's** (`--value-layout widths`, inherited from R4D's c32c): the softmax weight rides in the `calc-size` width instead of the `P000` axis (1/16384 quantisation → ≤ 0.03 px LayoutUnit snapping per glyph). Ids are the acceptance; the two 32-token trajectories checked here (Hello, "I") are the coverage. combined6 (capacity 8, `runs`) is the exact set for B5's paired bench; the fallback bundle `combined6-c32-runs` (if built) is the exact set at capacity 32.
- **R4S at capacity 32 = a 192-deep fixed size-container chain** (max DOM depth 238 / reader 233 vs 94 / 89 at capacity 8; parser cap 512, F3 chain cap 250): offline PASS and the 32-token runs are the evidence; R4S's smoke/correctness only covered capacity 2 and 8. R4S's containing-block lint (no `contain`/`transform`/`filter`/`will-change`/`position` on the 40 ancestors of `#fvs-sc0`) passed in the merged builds.
- **R4S × R4D interaction relies on container-query name matching**: R4D's `@container fvscache style(--fvq-S:0)` must skip R4S's unnamed `.fvs-sc` size containers (spec: named queries match only containers with that `container-name`). Correct ids in Chrome with both flags on are the check; if a future Chromium changed this, unfilled V glyphs would stay laid out (slower, still exact).
- **`R4D_GATE_SCORES` is dead under R4S** (forced off; manifest shows the effective value). Re-enabling it would need a chain-aware variant (an anchor row with `display:none` has no anchor → `anchor-size()` invalid → the container's width falls back to `auto`, corrupting two `--fs` values).
- **R4T excluded**: its flag is merge-ready (`R4M/merge.sh <tools> <R4T diff> 2`, `apply_r4t_import.py`; 3-way preview built and flag-off byte-identical), but its 2-layer smoke produced wrong ids, so combined7 waits on R4T's fix. R4T's b11-bridge hunk (added after my prelim diff) is outside the conflict region.
- **RecalcStyleCount is no longer a pass count** with R4S (interleaved container recalcs are counted; R4S.md §6: 3,759 vs 985 for the same passes) — compare LayoutCount or traced passes across bundles, not RecalcStyleCount.
- **Timing numbers here are single passive runs on a loaded machine** (other agents' Chrome runs and compiles; load reported per run) — B5's interleaved pairs vs combined4 decide s/token; the 32-token curve is the demo's own quantity (one run, per-token seconds, RSS from `ps` at 1 Hz).
- **Harness prompt knob**: `B0_PROMPT_TOKEN` uses Playwright `selectOption` on the bundle's `<select>` before Run and verifies `select.value` and body `--prompt-token` (throws otherwise); the page stays JS-free. Only the six shipped option values work without a rebuild (15496, 464, 40, 32, 1212, 2061).
- Disk: `R4M/scratch/` holds 11 reference builds (~45–50 MB css + 6–7 MB html each, no fonts) — delete after B5 picks up combined6. The bundles have no font copies (relative URLs into `experiments/`, like combined4).
