# R5X — round-5 merge: `bundles/combined8` = combined7 + R5E (all four flags on) + R5H (`R5H_CH_SCORES=1`, which turns `R4S_SMALL_HOPS` off); `bundles/combined8-c32` = the same at capacity 32 (`--value-layout widths`, R4D flags, R4T chunk 64, no R4S)

Agent R5X, 2026-09-24. Tools copy `work/2026-09-19/R5X/tools` (= `R4M/tools7` + `R5E/tools-vs-tools7.diff` + `R5H/tools-vs-tools7.diff`; symlinks as R4M plus `R5X/assets-r5h/` = R5H's 12
dot fonts). Bundles `bundles/combined8`, `bundles/combined8-c32` (each `BUILD.md` = recipe + flag table + merge notes + offline results + the embedded 831-line `diff -ruN R4M/tools7 R5X/tools`).
Scratch, checkers, harness copies and run data: `work/2026-09-19/R5X/`. Append-only log `R5X.log.md`. No repo `tools/` or `experiments/` edits, no other agent's directory touched, no git.
Not merged, per RESULTS-round5.md: **R5C** (real regression, `bundles/R5C/DO-NOT-MERGE`) and **R5M** (memory not cut: +239 MB RSS).

## 0. Headline

- **Merge: 1 textual conflict**, resolved as an exact-string union (§1); every offline gate of the R4M protocol passes (§2): all-new-flags-off = combined7 / combined7-c32 byte-for-byte,
  R5E-only = `bundles/R5E`, R5H-only = `bundles/R5H` / `R5H-c32`, both owners' checkers PASS at both capacities, witnesses 283 −/+ R5H's 12 dot fonts, NumPy ids 8/8 and 32/32
  (prompt 40) with the merged tools, static no-JS.
- **combined8 READY 16:58:41**: 8/8 ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]`, verify rc 0, residual rmse 0.016998 (= R5H's run), KV cache errors = R5H's, RecalcStyleCount 835 /
  LayoutCount 526 for 8 tokens (combined7: 3,768 / 544 — the interleaved container recalcs are gone), 143.7 s at 5-s poll granularity (§3). B6 pairs it vs combined7.
- **combined8-c32 32-token prompt-40 run: **32/32 ids, 905.6 s** (fit 12.05 + 0.975·k), **RecalcStyleCount flat 72/token**, LayoutCount 64 flat, RSS peak 4,415 MB, swap 3.25 → 3.36 GB during the run; READY 17:14:35. −12.6 s vs R5H-c32's 918.2 (R5E's hygiene, within noise), vs c32c 758.7 (clean-memory Hello) / 1,008.6 and combined7-c32 1,050.1 (swap-loaded prompt 40) — best swap-loaded prompt-40 total, memory-state caveat applies** (§4; started 16:58:41 by `R5X/run_chain.sh` after the machine gate opened at 16:55 — it had been closed since 16:23, §5).

## 1. Merge (`R5X/merge.sh` → `R5X/merge.log`; `R5X/apply_conflicts.py`; `R5X/rejects/`)

- Base `cp -R R4M/tools7 R5X/tools` (combined7's emitter). `patch -p2 -F3 -N < R5E/tools-vs-tools7.diff`: 6 files (font_vector_cache, reused_adapter, reused_core, runtime,
  r3r_fold_hop, + `r5e_dead_weight.py`), **0 rejects**. `patch -p2 -F3 -N < R5H/tools-vs-tools7.diff`: 3 files (font_vector_cache, reused_adapter, + `r5h_ch_scores.py`), **1 reject**.
- The reject (`R5X/rejects/r5h-adapter-readers.rej`): `browser_gpt2_reused_adapter.py`, the inline pass-reader count assertion after `f5.tag_inline_readers`. R5E rewrote it to
  `diag = 1 if r5e.KEEP_DIAG else 0; tagged != (6 if r4s.SMALL_HOPS else 7) - 1 + diag or tagged_position != 1 + diag` (the removed probe epoch twins); R5H rewrote the same line to
  `tagged != (6 if r5h.no_score_hop() else 7) or tagged_position != 2` (the score stamp reader is absent under R4S *or* R5H). Both effects act on the same body, so the merged assertion
  is the union: **`tagged != (6 if r5h.no_score_hop() else 7) - 1 + diag or tagged_position != 1 + diag`** — applied as an exact-string edit. Every build below passed the assertion
  (with R5H on + R5E on: 5 epoch / 1 position readers; R5H off + R4S on + KEEP_DIAG=1: 6 / 2; R5H off + R4S off + KEEP_DIAG=1: 7 / 2; …).
- The two import-line hunks (R5E adds `import r5e_dead_weight as r5e` after `r4d_flags`, R5H adds `import r5h_ch_scores as r5h` after `r4s_small_hops`, in the same import blocks of
  both files) applied with fuzz in the intended places (checked by eye).
- Checks: `py_compile` ok; `r5e_dead_weight.py` / `r5h_ch_scores.py` cmp-identical to the owners'; `diff -rq`: merged − `R5E/tools` = exactly R5H's two files + module, merged − `R5H/tools`
  = exactly R5E's five files + module; `R5X/tools-vs-tools7.diff` 831 lines.
- Semantic interaction R5E × R5H (nothing to decide, verified in the built bundles): R5E's `lean_walls` derives the kept reset set from the built page's wall ancestry — R5H's slot chains sit
  below the walls, and the kept counts equal R5E's own (`.core-reset` 16,156 → 0, `.head-isolation` 24,105 → 3,865 at cap 8 / 26,889 → 3,913 at cap 32); R5E's `--lp` inheritance and dead
  lists are in the loop/query subtrees, R5H's chains in the ctx track; R5E's probe removal and R5H's stamp removal meet only in the adapter assertion above.
- Dot fonts: `r5h_ch_scores.ASSETS` = `<agent dir>/assets-r5h/…`, so the merged bundles reference `R5X/assets-r5h/…-f4-r5h.woff2` (seeded from R5H's files to avoid a create race;
  the module re-verifies every table on every build — only `cmap` differs from the F4 source, `head` checksum aside).
- Recipe: `R5X/compile.sh` = R5H's compile.sh with `R5E_*` passthrough (combined7's flags, `R4T_CONSUMER_CHUNK=64`; cap 32 adds `VALUE_LAYOUT=widths R4S_SMALL_HOPS=0` as combined7-c32).
  Builds take ≈20 s each (weights cached).

## 2. Offline verification (`R5X/compare_bundles.py` = R4M's + agent-dir normalisation of the dot-font URLs; logs `R5X/logs/`)

| build (flags) | reference | result |
|---|---|---|
| `p8-alloff` (R5E off, `R5E_KEEP_DIAG=1`, R5H off; R4S on) | `bundles/combined7` | **index.html byte-identical (6,517,186 B); runtime.css identical (URL-normalised); manifest +6 keys; witnesses 283/283** |
| `p32w-alloff` (same, cap 32 widths, R4S off) | `bundles/combined7-c32` | identical likewise (7,198,924 B; manifest +6) |
| `p8-R5Eonly` (R5H off) | `bundles/R5E` | identical (6,466,009 B; manifest +`r5hChScores:false`; witnesses 283/283) |
| `p8-R5Honly` (R5E off, KEEP_DIAG=1) | `bundles/R5H` | identical (6,511,183 B; css identical modulo `R5X/` vs `R5H/` in the 12 dot URLs; manifest +5 R5E keys; witnesses 283/283 ignoring the file-mtime field of the 12 dot entries) |
| `p32w-R5Honly` | `bundles/R5H-c32` | identical likewise (7,176,913 B) |
| `p8-all` / `p32w-all` (all on, scratch twins of the deliverables) | `bundles/combined8` / `combined8-c32` | identical (6,460,006 / 7,125,736 B), **0 manifest differences**, witnesses 283/283 |
| `R5E/offline_check.py` p8-all vs p8-R5Honly; p32w-all vs p32w-R5Honly | R5E off | **RESULT: PASS ×2** (`--lp` 768 flips; `.core-reset` 16,156 → 0; `.head-isolation` 24,105 → 3,865 / 26,889 → 3,913 with `lean_walls` re-derived on the reference; 9 / 33 dead lists gone, 0 readers; 4,992 forwards → 0; HTML = reference minus 6 probes + observer; elements −7) |
| `R5H/offline_check.py` (copy `R5X/offline_check_r5h.py`, only change: accepts paths) p8-all vs p8-R5Eonly (8); p32w-all vs p32w-R5Eonly (32) | R5H off | **RESULT: PASS ×2** (cap 8: +96 slot rules / −96 carriers, −48/−48 R4S containers/publishers, softmax/weights split 12+12 vs 1+1, elements −38, depth 165, bottoms at 104; cap 32: elements +6, bottoms at 128) |
| owners' checkers on `bundles/combined8` vs scratch twins | — | FAIL on URL text only (`@font-face −12/+12` and "value faces unchanged": `../../R5X/assets-r5h/` vs `../../assets-r5h/` one directory deeper — R4M.md §6.1's path-depth artefact), hence the same-depth pairs above (`R5X/logs/offline_check_r5?-combined8*.log`) |
| NumPy ids (merged tools; `R5X/reference_ids.py`, `numpy_ids_40.py`) | — | 8-token `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected; prompt-40 free-running 32/32 == `R4P/reference_ids_32_40.json` (== teacher-forced, first mismatch None) |
| witnesses `combined8` vs `combined7`, `combined8-c32` vs `combined7-c32` | — | 271/283 identical + the 12 F4 dot faces replaced by R5H's `-r5h` faces (advance 29984 / upem 1000, codepoint U+0030) |
| `tools/launch_browser_gpt2.py --check` | — | combined8: 285 static files, 284,742,638 B, `runtimeJavaScript: false`; combined8-c32: 285 files, 296,449,400 B, false |

Sizes: combined8 runtime.css 38,269,982 B / index.html 6,460,006 B (combined7 39,073,102 / 6,517,186), elements 67,524 (combined7 67,569: −38 R5H, −7 R5E); combined8-c32 49,311,014 /
7,125,736 (combined7-c32 50,502,747 / 7,198,924), elements 86,438 (86,439). All scratch twins deleted after their checks (disk).

## 3. Chrome — combined8 (capacity 8) correctness run

ONE passive run (NOT a timing run), `R5X/run_chain.sh` → `R5X/with_lock.sh correctness-combined8` → `R5X/correctness_inner.sh combined8` (R4M's `correctness_run.mjs`: headless Chrome
153.0.8010.53, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback; verify with the merged tools), 2026-09-24 16:55:24–16:58:41 under `CHROME.lock`
(owner "R5X correctness-combined8 …"; gate open at start: AC (63 %, charging), disk 4 GB, swap used 3,282 MB, load { 3.41 6.90 6.01 }). Results in `R5X/run-combined8/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8, stopReason token-limit; `verify_browser_gpt2_runtime.py` rc=0: tokenAgreement 8 × True,
  originalFloatAgreement 8 × True, finalHeadMatchesActualInput True, text "Hello, I'm sorry, but I'm"; `finalResidualError` rmse **0.016998** / max **0.14188** — **identical to
  `bundles/R5H`'s run** (0.016998 / 0.14188; combined7 / R5E 0.016055 / 0.11652: R5E is exact by construction, so combined8's numerics are R5H's rounding point, R5H.md §3).
- Full KV cache readback (R4M-patched harness concatenates R4D's per-head V lists; no wrapper needed): 96/96 entries complete (1,536 finite each), `cacheErrors` rmse median 0.0018 /
  max 1.4834 / abs max 7.640 — identical to R5H's run (1.4834 / 7.640); combined7 1.4815 / 7.633, same class.
- Whole-run counters (harness idle → end): **RecalcStyleCount 835** (combined7 3,768 with R4S's interleaved container recalcs; R5E 3,748; ≈ 104/token — a pass count again, no
  container recalcs), **LayoutCount 526** (combined7 544, R5E 524), Nodes 132,197 (combined7 132,338).
- Per-token capture times (5 s poll granularity, load ≈3.5–7 — indicative only; B6's pairs decide): 23.5, 11.5, 18.5, 12.2, 18.3, 17.9, 23.4, 18.4 s = **143.7 s** total (cumulative 23.5, 35.0,
  53.5, 65.7, 84.0, 101.9, 125.2, 143.7; combined7's correctness run 146.8 s, R5E's 160.4 s, R5H's see R5H/run-R5H). Page load 35.7 s (67,524 elements, 283 fonts).
- RSS: my 1 Hz `ps` sampler matched no renderer process (pattern gap, same as R5E's first run) → no renderer RSS for this run; the c32 run below uses `bench_native.mjs`'s own per-process sampler.
- **`bundles/combined8/READY` created 16:58:41** (8/8 + verify rc 0) — B6 can pair it vs combined7.

## 4. Chrome — combined8-c32 32-token prompt-40 run

ONE passive run, `R5X/run_chain.sh` → `R5X/with_lock.sh c32-combined8-c32` → `R5X/c32_inner.sh combined8-c32 c32-p40` (R4M's `bench_native.mjs`: `B0_PROMPT_TOKEN=40` "I" via Playwright
`selectOption` + readback, keyboard trigger, heap flag ON, trace OFF, 1 Hz `#token-k-captured.done` poll, per-process RSS via `ps` at 1 Hz), 2026-09-24 16:58:41–17:14:35 under `CHROME.lock`
right after the correctness run (same gate window: AC 63 % charging, disk 4 GB, swap used 3,250 → 3,356 MB, load 3.89 / 5.59 / 5.64 at start and 5.06 / 4.85 / 4.92 at end; compressor pages
180,739 → 211,193, pageouts +2,192 — a moderately swap-loaded state, NOT the clean-memory session the plan asked for; the machine has not been in that state all day). Results in
`R5X/run-combined8-c32/` (`c32-p40.json`, `.summary.md`, `.memstate.txt`).

- ids **32/32** = `R4P/reference_ids_32_40.json` (free-running == teacher-forced; text "I.⏎⏎The first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so
  excited to try it."), stopReason token-limit; **`bundles/combined8-c32/READY` created 17:14:35**.
- **Total 905.6 s** for 32 tokens (k=1 **18.5** / 8 **19.3** / 16 **29.5** / 24 **35.3** / 32 **43.3**); median 29.2; min 14.1 (k=2). Fit tokens 2..32: **12.05 + 0.975·k** (rmse 0.87);
  style 5.11 + 0.574·k, layout 3.43 + 0.286·k, task 12.11 + 0.957·k. Page load 34.3 s.
- **RecalcStyleCount per token flat: 72.0 − 0.012·k** (values 75, 72 × 25, 70 × 4, 74 × 2, 68) = R5H-c32's 72 (c32c / combined7-c32 84; combined6-c32 with R4S 126 + 70.8·k) — no
  R4S chain, no interleaved container recalcs; **LayoutCount 64 flat** (64.0 − 0.012·k).
- RSS renderer: peak **4,415 MB** during generation (before run 1,908, at end 3,561; per-token maxima 3,057–4,415 in the table) — R5H-c32 3.5–4.5 GB, c32c 7,226 (clean state), combined7-c32 run A
  3,878 (swap-loaded). Nodes 169,543.

Comparison (prompt 40 unless noted; single passive runs, absolute wall-clock is memory-state dominated — R4V / RESULTS-round5 caveat):

| run | bundle | R4S | R4T | R5E | R5H | total s | k=1 / 8 / 16 / 24 / 32 | fit 2..32 | RecalcStyle/token | RSS peak MB | machine state |
|---|---|---|---|---|---|---:|---|---|---|---:|---|
| R4D c32c-run1 (Hello) | combined4-c32c | – | – | – | – | 758.7 | 22.0 / 17.7 / 21.3 / 26.9 / 35.2 | 12.8 + 0.65·k | 84 flat | 7,226 | clean (load 6–8) |
| R4M run C | combined4-c32c | – | – | – | – | 1,008.6 | | | 84 flat | | swap-pressured, user load |
| R4M run A | combined7-c32 | off | 64 | – | – | 1,050.1 | 22.3 / 24.7 / 33.1 / 37.9 / 49.7 | 15.8 + 1.02·k | 84 flat | 3,878 | load 8–30 |
| R5H c32-p40 (14:38) | R5H-c32 | off | 64 | – | on | 918.2 | | 12.7 + 0.97·k | 72 flat | 3.5–4.5 GB | swap 2.8 → 3.1 GB |
| **R5X c32-p40 (16:58)** | **combined8-c32** | off | 64 | on | on | **905.6** | 18.5 / 19.3 / 29.5 / 35.3 / 43.3 | **12.05 + 0.975·k** | **72 flat** | **4,415** | swap 3.25 → 3.36 GB, load ≈4–5 |

- combined8-c32 = R5H-c32 + R5E: **905.6 vs 918.2 s (−12.6 s, −1.4 %)**, intercept 12.05 vs 12.7 (R5E's predicted −0.2…−0.3 s/token hygiene, within single-run noise), slope 0.975 vs 0.97
  (identical), RecalcStyleCount identical (72). The **best prompt-40 total so far** among the swap-loaded runs (c32c run C 1,008.6; combined7-c32 run A 1,050.1); the 758.7 s c32c number is a
  Hello run in a clean-memory session and is not directly comparable (both its slope 0.65 and its intercept are clean-machine values). The k=1 token (18.5 s) is the lowest first token of any
  cap-32 run (R5H 20.x, c32c 22.0).
- Per-token table:

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18.5 | 18 | 13 | Y | 75 | 67 | 8.6 | 3.9 | 16.4 | 3057 | 3057 |
| 2 | 14.1 | 33 | 198 | Y | 72 | 64 | 6.5 | 3.6 | 14.0 | 3982 | 3710 |
| 3 | 15.1 | 48 | 198 | Y | 72 | 64 | 7.3 | 3.9 | 15.2 | 4145 | 3409 |
| 4 | 16.7 | 64 | 464 | Y | 72 | 64 | 7.9 | 4.7 | 16.6 | 3927 | 3727 |
| 5 | 16.7 | 81 | 717 | Y | 70 | 62 | 8.2 | 4.0 | 16.2 | 3950 | 3501 |
| 6 | 18.9 | 100 | 1517 | Y | 72 | 64 | 8.1 | 6.5 | 18.8 | 4323 | 4289 |
| 7 | 17.8 | 118 | 314 | Y | 72 | 64 | 8.8 | 4.8 | 17.8 | 4162 | 3876 |
| 8 | 19.3 | 137 | 750 | Y | 72 | 64 | 10.0 | 4.9 | 19.2 | 4217 | 3722 |
| 9 | 20.9 | 158 | 373 | Y | 72 | 64 | 10.4 | 6.0 | 20.8 | 3903 | 3289 |
| 10 | 22.5 | 180 | 284 | Y | 72 | 64 | 10.7 | 7.6 | 23.1 | 3993 | 3872 |
| 11 | 23.5 | 204 | 467 | Y | 72 | 64 | 11.8 | 7.6 | 24.0 | 4019 | 3604 |
| 12 | 22.2 | 226 | 284 | Y | 72 | 64 | 10.5 | 5.6 | 20.7 | 4197 | 3865 |
| 13 | 24.2 | 250 | 262 | Y | 72 | 64 | 13.5 | 5.7 | 24.1 | 4182 | 3540 |
| 14 | 25.1 | 275 | 1957 | Y | 72 | 64 | 12.5 | 7.8 | 25.1 | 4020 | 3487 |
| 15 | 26.0 | 301 | 16918 | Y | 72 | 64 | 12.8 | 9.8 | 27.8 | 4393 | 3885 |
| 16 | 29.5 | 331 | 3650 | Y | 72 | 64 | 13.8 | 8.5 | 27.3 | 4170 | 3709 |
| 17 | 29.1 | 360 | 290 | Y | 72 | 64 | 16.5 | 7.2 | 28.8 | 3852 | 3401 |
| 18 | 29.4 | 389 | 2822 | Y | 72 | 64 | 17.1 | 6.7 | 29.2 | 3971 | 3467 |
| 19 | 31.4 | 421 | 257 | Y | 72 | 64 | 16.3 | 9.7 | 31.3 | 4287 | 3655 |
| 20 | 30.3 | 451 | 6131 | Y | 72 | 64 | 18.6 | 6.2 | 30.0 | 4139 | 3348 |
| 21 | 32.3 | 483 | 286 | Y | 72 | 64 | 14.2 | 12.5 | 32.1 | 4117 | 3089 |
| 22 | 33.3 | 517 | 12912 | Y | 72 | 64 | 15.4 | 12.1 | 33.2 | 3789 | 3260 |
| 23 | 34.3 | 551 | 32132 | Y | 72 | 64 | 15.2 | 13.3 | 33.9 | 4020 | 3547 |
| 24 | 35.3 | 586 | 13 | Y | 72 | 64 | 15.9 | 13.3 | 35.1 | 3782 | 3342 |
| 25 | 35.4 | 622 | 314 | Y | 72 | 64 | 19.1 | 10.5 | 35.3 | 3930 | 3353 |
| 26 | 37.3 | 659 | 373 | Y | 72 | 64 | 23.4 | 7.4 | 36.6 | 4094 | 3456 |
| 27 | 38.4 | 697 | 523 | Y | 70 | 62 | 23.0 | 7.8 | 37.4 | 3814 | 2925 |
| 28 | 41.2 | 739 | 6568 | Y | 74 | 66 | 23.2 | 12.0 | 41.5 | 4415 | 3965 |
| 29 | 41.2 | 780 | 284 | Y | 70 | 62 | 25.0 | 8.0 | 39.5 | 3960 | 3648 |
| 30 | 42.0 | 822 | 1949 | Y | 72 | 64 | 21.8 | 12.7 | 41.6 | 3936 | 3936 |
| 31 | 40.6 | 862 | 340 | Y | 74 | 66 | 19.9 | 14.9 | 41.7 | 3731 | 3529 |
| 32 | 43.3 | 906 | 13 | Y | 68 | 60 | 23.4 | 12.0 | 42.1 | 3913 | 3561 |


## 5. Incidents, risks, follow-ups

- **Disk/swap incident (16:23)**: I started the seven builds three at a time while R5G's Chrome pair held the lock; macOS added two 1 GB swapfiles (swap used 3.5 → 4.9 GB) and the disk went
  5.1 → 0 GB for a moment — three twins died with `OSError 28` and were rebuilt one at a time; the deliverables and two twins had completed. The machine gate has been closed since
  (swap ≥ 4,000 MB needs disk ≥ 4 GB; swap only shrinks as processes exit). Rule for future merges: one build at a time, never during a benched pair.
- `RecalcStyleCount` at cap 32 must be flat ≈ 72/token (R5H-c32's measured value; R5H predicted ≈ 84 and got 68–75) — the c32 run's table is the check; a slope would mean the R4S chain leaked back in (manifest `r4sSmallHops` is false in both bundles).
- combined8-c32 numerics: `widths` layout as combined7-c32/c32c (not bit-identical to `runs`; ids are the acceptance) plus R5H's rounding point (exact-class, R5H.md §3).
- The dot-font files live under `R5X/assets-r5h/` (not `experiments/`): the bundles depend on `work/2026-09-19/R5X/` staying in place, as they already depend on `F4/assets`.
- Verification harness: R4M's `correctness_run.mjs` already concatenates R4D's per-head V lists; `R5X/correctness_inner.sh` falls back to R4M's `verify_wrapper.py` only if the vectors contain nulls.
