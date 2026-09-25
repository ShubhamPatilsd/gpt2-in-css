# Paired confirmation bench (B3, interleaved) — 2026-09-20

Why: same-bundle run-to-run drift today (combined 31.3–40.5 s/token depending on background load) is as large as the fixes being measured, so each candidate run is paired with the `combined` reference run immediately before it (same harness, same machine state within ~10 min).
Protocol: `B0/run_bench.sh` unchanged — headless Chrome 153, heap=1, mouseoff, passive, AC required, quiet gate (load < 3, no > 50 % CPU hog) up to 15 min then CONTENDED, 30 s power watchdog, CHROME.lock held only while a run is active. 12 untraced runs in the order ref, combined3, ref, R2F, ref, combined3, ref, R2F, ref, combined3, ref, R2F (ref = `bundles/combined`). Runs: `bench/runs/<bundle>/paired-*`.

## Per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined | paired-ref-1 | 18:52:54 → 18:58:12 | 8/8 | 31.5 30.9 32.0 32.5 32.9 34.3 37.8 42.6 | 32.7 | 274.5 | 5362 | 175.0 | 109.0 | 2.2 | 6.1 | no |
| 2 | combined3 | paired-1 | 19:13:15 → 19:17:06 | 8/8 | 26.7 22.3 22.7 23.2 23.9 23.7 25.1 24.1 | 23.8 | 191.7 | 5722 | 136.0 | 87.0 | 3.8 | 3.9 | **yes** (load1=2.72 top=99.5:app/Contents/MacOS/Python) |
| 3 | combined | paired-ref-2 | 19:32:09 → 19:37:05 | 8/8 | 33.3 29.6 30.7 30.7 32.1 32.7 35.3 33.7 | 32.4 | 258.0 | 6011 | 175.0 | 109.0 | 5.7 | 5.0 | **yes** (load1=5.24 top=121.8:Versions/A/mediaanalysisd) |
| 4 | R2F | paired-1 | 19:52:09 → 19:56:10 | 8/8 | 25.9 22.7 24.0 24.6 25.0 26.6 26.8 27.6 | 25.4 | 203.2 | 4976 | 136.0 | 87.0 | 4.6 | 4.0 | **yes** (load1=5.14 top=111.7:Versions/A/mediaanalysisd) |
| 5 | combined | paired-ref-3 | 20:11:14 → 20:17:12 | 8/8 | 34.4 33.4 34.0 36.3 42.2 52.2 43.4 38.9 | 37.6 | 314.8 | 4831 | 175.0 | 109.0 | 4.5 | 8.0 | **yes** (load1=4.42 top=120.7:Versions/A/mediaanalysisd) |
| 6 | combined3 | paired-2 | 20:32:16 → 20:36:49 | 8/8 | 28.5 25.1 26.9 29.8 29.2 31.3 31.5 30.4 | 29.5 | 232.5 | 3395 | 136.0 | 87.0 | 3.9 | 7.2 | **yes** (load1=4.34 top=100.0:app/Contents/MacOS/Python) |
| 7 | combined | paired-ref-4 | 20:40:21 → 20:45:29 | 8/8 | 31.4 32.1 35.5 37.5 37.2 40.1 41.5 42.3 | 37.3 | 297.6 | 3226 | 174.9 | 109.0 | 4.7 | 6.4 | **yes** (load1=4.28 top=99.0:app/Contents/MacOS/Python) |
| 8 | R2F | paired-2 | 20:46:02 → 20:50:31 | 8/8 | 26.1 23.8 27.4 29.2 29.8 30.7 32.4 31.0 | 29.5 | 230.4 | 3258 | 136.0 | 87.0 | 6.0 | 6.0 | **yes** (load1=6.43 top=99.3:app/Contents/MacOS/Python) |
| 9 | combined | paired-ref-5 | 20:51:03 → 20:56:34 | 8/8 | 31.3 30.4 35.0 36.5 39.4 36.6 38.8 44.6 | 36.5 | 292.6 | 3879 | 175.0 | 109.0 | 5.5 | 5.8 | **yes** (load1=5.95 top=100.0:app/Contents/MacOS/Python) |
| 10 | combined3 | paired-3 | 20:57:06 → 21:01:19 | 8/8 | 26.0 22.9 24.0 27.0 28.5 28.6 30.1 27.6 | 27.3 | 214.6 | 3835 | 136.0 | 87.0 | 5.8 | 5.7 | **yes** (load1=5.82 top=99.1:app/Contents/MacOS/Python) |
| 11 | combined | paired-ref-6 | 21:01:51 → 21:06:34 | 8/8 | 31.0 29.1 31.5 32.5 34.0 36.9 38.6 39.6 | 33.3 | 273.2 | 3955 | 175.0 | 109.0 | 4.8 | 5.6 | **yes** (load1=5.71 top=99.0:app/Contents/MacOS/Python) |
| 12 | R2F | paired-3 | 21:07:06 → 21:10:50 | 8/8 | 25.8 22.9 25.9 26.2 27.3 28.0 28.8 29.0 | 26.7 | 213.9 | 3826 | 136.1 | 87.0 | 5.0 | 5.0 | **yes** (load1=5.59 top=100.0:app/Contents/MacOS/Python) |

## Paired differences (candidate − the ref run immediately before it)

| candidate | pair | ref run (median / total) | cand run (median / total) | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| combined3 | 1 | paired-ref-1 (32.7 / 274.5) | paired-1 (23.8 / 191.7) | -8.9 | -82.8 | -39.0 | -22.0 | +360 | no/yes |
| combined3 | 2 | paired-ref-3 (37.6 / 314.8) | paired-2 (29.5 / 232.5) | -8.1 | -82.3 | -39.0 | -22.0 | -1436 | yes/yes |
| combined3 | 3 | paired-ref-5 (36.5 / 292.6) | paired-3 (27.3 / 214.6) | -9.2 | -78.0 | -39.0 | -22.0 | -44 | yes/yes |
| **combined3** | **mean [range], n=3** | | | **-8.7 [-9.2 … -8.1]** | **-81.0 [-82.8 … -78.0]** | -39.0 [-39.0 … -39.0] | -22.0 [-22.0 … -22.0] | -373 | |
| R2F | 1 | paired-ref-2 (32.4 / 258.0) | paired-1 (25.4 / 203.2) | -7.0 | -54.8 | -39.0 | -22.0 | -1035 | yes/yes |
| R2F | 2 | paired-ref-4 (37.3 / 297.6) | paired-2 (29.5 / 230.4) | -7.8 | -67.2 | -38.9 | -22.0 | +32 | yes/yes |
| R2F | 3 | paired-ref-6 (33.3 / 273.2) | paired-3 (26.7 / 213.9) | -6.6 | -59.3 | -38.9 | -22.0 | -129 | yes/yes |
| **R2F** | **mean [range], n=3** | | | **-7.1 [-7.8 … -6.6]** | **-60.4 [-67.2 … -54.8]** | -38.9 [-39.0 … -38.9] | -22.0 [-22.0 … -22.0] | -377 | |

## Reference drift (the 6 `combined` runs)

medians s/token in run order: 32.7 32.4 37.6 37.3 36.5 33.3 → min 32.4, max 37.6, range 5.2, mean 35.0, sd 2.42
totals s: 274.5 258.0 314.8 297.6 292.6 273.2 → range 56.8; adjacent-ref differences (median s/tok): -0.3 +5.2 -0.3 -0.8 -3.2 → mean |Δ| 2.0, max |Δ| 5.2
recalcs/tok: 175.0 175.0 175.0 174.9 175.0 175.0; layouts/tok: 109.0 109.0 109.0 109.0 109.0 109.0; load1 at START: 2.2 5.7 4.5 4.7 5.5 4.8; contended: 5/6
Sequential rows for the same bundle for scale: `combined (heap=1)` 30.3 (round 1, legacy pointer), `combined (mouseoff)` 35.1 (today, u2 hit a load spike).

## Verdicts

**combined3 — REAL effect.** Paired Δ median = -8.7 s/token (range -9.2 … -8.1, n=3), Δ total = -81.0 s per 8 tokens (range -82.8 … -78.0); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 5.2 s/token and a ref spread of 5.2 s/token over the 6 ref runs. Pass counts move by -39.0 recalcs/token and -22.0 layouts/token (paired; these are deterministic per bundle, so any non-zero value is structural, not noise). RSS -373 MB. 3 of 3 pairs had a contended run.

**R2F — REAL effect.** Paired Δ median = -7.1 s/token (range -7.8 … -6.6, n=3), Δ total = -60.4 s per 8 tokens (range -67.2 … -54.8); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 5.2 s/token and a ref spread of 5.2 s/token over the 6 ref runs. Pass counts move by -38.9 recalcs/token and -22.0 layouts/token (paired; these are deterministic per bundle, so any non-zero value is structural, not noise). RSS -377 MB. 3 of 3 pairs had a contended run.

