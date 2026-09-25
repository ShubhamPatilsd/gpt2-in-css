# Round-3 paired bench (B4, interleaved vs R2F) — 2026-09-20

Why: same-bundle run-to-run drift today exceeds the effect sizes under test, so each candidate run is paired with a `R2F` reference run taken immediately before it (same harness, same machine state within ~10 min); the statistic is the paired difference.
Protocol: `B0/run_bench.sh` unchanged — headless Chrome 153, heap=1, mouseoff, passive, AC required, quiet gate (load < 3, no > 50 % CPU hog) up to 15 min then CONTENDED, 30 s power watchdog, CHROME.lock held only while a run is active. Per candidate: ref, cand, ref, cand, ref, cand (3 pairs; combined4: 4 pairs), untraced. Runs: `bench/runs/R2F/paired4-ref-<cand>-<k>`, `bench/runs/<cand>/paired4-<k>`.

## R3L — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | R2F | paired4-ref-R3L-1 | 22:28:07 → 22:31:43 | 8/8 | 24.1 23.0 24.3 25.3 27.3 27.4 28.1 27.6 | 26.3 | 207.1 | 4600 | 93.4 | 87.0 | 3.8 | 4.8 | no |
| 2 | R3L | paired4-1 | 22:31:45 → 22:34:51 | 8/8 | 23.8 19.0 20.8 20.8 22.1 22.3 23.1 24.5 | 22.2 | 176.3 | 4603 | 93.4 | 87.0 | 4.5 | 3.2 | no |
| 3 | R2F | paired4-ref-R3L-2 | 22:34:53 → 22:38:32 | 8/8 | 24.1 22.8 23.3 25.6 25.0 29.2 30.4 29.2 | 25.3 | 209.6 | 4669 | 93.4 | 87.0 | 3.2 | 5.8 | no |
| 4 | R3L | paired4-2 | 22:38:34 → 22:41:56 | 8/8 | 23.7 19.5 20.2 22.1 26.2 27.1 26.1 27.4 | 24.9 | 192.3 | 4464 | 93.4 | 87.0 | 5.8 | 4.2 | no |
| 5 | R2F | paired4-ref-R3L-3 | 22:41:58 → 22:46:03 | 8/8 | 25.2 22.9 26.9 27.0 29.3 26.3 23.6 25.0 | 25.8 | 206.3 | 5864 | 93.4 | 87.0 | 4.2 | 3.6 | no |
| 6 | R3L | paired4-3 | 22:46:05 → 22:49:01 | 8/8 | 23.2 20.2 21.4 20.1 19.9 20.3 20.7 20.9 | 20.5 | 166.7 | 5867 | 93.4 | 87.0 | 3.6 | 4.5 | no |

### R3L — paired differences (candidate − the R2F run immediately before it)

| pair | ref run (median / total) | cand run (median / total) | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | paired4-ref-R3L-1 (26.3 / 207.1) | paired4-1 (22.2 / 176.3) | -4.1 | -30.8 | +0.0 | +0.0 | +3 | no/no |
| 2 | paired4-ref-R3L-2 (25.3 / 209.6) | paired4-2 (24.9 / 192.3) | -0.4 | -17.3 | +0.0 | +0.0 | -205 | no/no |
| 3 | paired4-ref-R3L-3 (25.8 / 206.3) | paired4-3 (20.5 / 166.7) | -5.3 | -39.6 | +0.0 | +0.0 | +3 | no/no |
| **mean [range], n=3** | | | **-3.3 [-5.3 … -0.4]** | **-29.2 [-39.6 … -17.3]** | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | -66 | |

R2F reference drift within this candidate's sequence: medians 26.3 25.3 25.8 (range 1.0), adjacent-ref swings -1.0 +0.5; recalcs/tok 93.4 93.4 93.4; contended 0/3. Sequential R2F row for scale: 23.6 s/token (B2, 2 of 3 runs contended).

**R3L — REAL effect.** Paired Δ median = -3.3 s/token (range -5.3 … -0.4, n=3), Δ total = -29.2 s per 8 tokens (range -39.6 … -17.3); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 1.0 s/token and a ref spread of 1.0 s/token over the 3 ref runs. Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS -66 MB. 0 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8.

## combined4 — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | R2F | paired4-ref-combined4-1 | 22:49:03 → 22:52:59 | 8/8 | 25.5 22.6 22.7 25.4 26.8 26.9 23.6 23.4 | 24.5 | 196.9 | 6008 | 93.4 | 87.0 | 4.5 | 4.1 | no |
| 2 | combined4 | paired4-1 | 22:53:01 → 22:55:33 | 8/8 | 19.0 15.1 16.3 17.8 18.0 18.8 19.1 19.1 | 18.4 | 143.2 | 5686 | 83.2 | 76.0 | 4.1 | 3.2 | no |
| 3 | R2F | paired4-ref-combined4-2 | 22:55:35 → 22:59:00 | 8/8 | 24.2 22.9 23.5 24.9 24.2 25.5 25.9 24.8 | 24.5 | 195.9 | 6113 | 93.4 | 87.0 | 3.2 | 3.3 | no |
| 4 | combined4 | paired4-2 | 22:59:03 → 23:01:32 | 8/8 | 18.9 15.1 16.1 17.0 18.0 18.2 18.6 18.4 | 18.1 | 140.3 | 5795 | 83.2 | 76.0 | 3.1 | 3.4 | no |
| 5 | R2F | paired4-ref-combined4-3 | 23:01:34 → 23:04:56 | 8/8 | 23.8 22.2 23.6 23.5 24.5 24.3 25.3 25.5 | 24.1 | 192.7 | 6090 | 93.4 | 87.0 | 3.4 | 3.4 | no |
| 6 | combined4 | paired4-3 | 23:04:58 → 23:07:30 | 8/8 | 19.2 16.4 16.9 17.4 18.0 18.2 18.7 18.5 | 18.1 | 143.2 | 5803 | 83.2 | 76.0 | 3.1 | 4.0 | no |
| 7 | R2F | paired4-ref-combined4-4 | 23:07:33 → 23:10:58 | 8/8 | 25.5 22.7 23.5 23.8 24.7 25.2 25.1 25.1 | 24.9 | 195.5 | 5966 | 93.4 | 87.0 | 3.9 | 3.1 | no |
| 8 | combined4 | paired4-4 | 23:11:00 → 23:14:02 | 8/8 | 19.2 15.3 17.2 17.7 17.9 19.0 19.6 19.2 | 18.5 | 145.2 | 5675 | 83.2 | 76.0 | 3.1 | 3.6 | no |

### combined4 — paired differences (candidate − the R2F run immediately before it)

| pair | ref run (median / total) | cand run (median / total) | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | paired4-ref-combined4-1 (24.5 / 196.9) | paired4-1 (18.4 / 143.2) | -6.1 | -53.7 | -10.2 | -11.0 | -322 | no/no |
| 2 | paired4-ref-combined4-2 (24.5 / 195.9) | paired4-2 (18.1 / 140.3) | -6.4 | -55.6 | -10.2 | -11.0 | -318 | no/no |
| 3 | paired4-ref-combined4-3 (24.1 / 192.7) | paired4-3 (18.1 / 143.2) | -6.0 | -49.5 | -10.2 | -11.0 | -287 | no/no |
| 4 | paired4-ref-combined4-4 (24.9 / 195.5) | paired4-4 (18.5 / 145.2) | -6.4 | -50.3 | -10.2 | -11.0 | -291 | no/no |
| **mean [range], n=4** | | | **-6.2 [-6.4 … -6.0]** | **-52.3 [-55.6 … -49.5]** | -10.2 [-10.2 … -10.2] | -11.0 [-11.0 … -11.0] | -304 | |

R2F reference drift within this candidate's sequence: medians 24.5 24.5 24.1 24.9 (range 0.8), adjacent-ref swings +0.0 -0.4 +0.8; recalcs/tok 93.4 93.4 93.4 93.4; contended 0/4. Sequential R2F row for scale: 23.6 s/token (B2, 2 of 3 runs contended).

**combined4 — REAL effect.** Paired Δ median = -6.2 s/token (range -6.4 … -6.0, n=4), Δ total = -52.3 s per 8 tokens (range -55.6 … -49.5); all 4 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 0.8 s/token and a ref spread of 0.8 s/token over the 4 ref runs. Pass counts move by -10.2 recalcs/token and -11.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS -304 MB. 0 of 4 pairs had a contended run. ids: 8/8; 8/8; 8/8; 8/8.

## R3R — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | R2F | paired4-ref-R3R-1 | 22:02:28 → 22:06:18 | 8/8 | 26.0 23.7 23.9 23.3 22.5 23.6 24.7 24.1 | 23.8 | 191.8 | 5637 | 93.4 | 87.0 | 4.4 | 3.8 | no |
| 2 | R3R | paired4-1 | 22:13:06 → 22:15:40 | 8/8 | 19.9 15.7 16.4 17.6 18.0 18.8 18.8 19.5 | 18.4 | 144.7 | 4932 | 83.2 | 76.0 | 3.4 | 3.5 | no |
| 3 | R2F | paired4-ref-R3R-2 | 22:15:42 → 22:19:05 | 8/8 | 24.2 21.7 22.4 23.3 25.8 23.8 26.1 27.0 | 24.0 | 194.2 | 4761 | 93.4 | 87.0 | 3.5 | 3.1 | no |
| 4 | R3R | paired4-2 | 22:19:08 → 22:21:52 | 8/8 | 19.8 16.9 18.3 18.7 19.5 19.6 21.6 21.1 | 19.5 | 155.3 | 4771 | 83.2 | 76.0 | 3.1 | 3.4 | no |
| 5 | R2F | paired4-ref-R3R-3 | 22:21:55 → 22:25:18 | 8/8 | 23.7 21.9 22.7 22.9 25.5 25.2 26.4 26.6 | 24.5 | 194.9 | 4625 | 93.4 | 87.0 | 3.3 | 3.3 | no |
| 6 | R3R | paired4-3 | 22:25:21 → 22:28:05 | 8/8 | 19.6 17.0 17.8 18.8 19.4 19.4 21.3 21.7 | 19.4 | 154.9 | 4450 | 83.2 | 76.0 | 3.1 | 3.8 | no |

### R3R — paired differences (candidate − the R2F run immediately before it)

| pair | ref run (median / total) | cand run (median / total) | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | paired4-ref-R3R-1 (23.8 / 191.8) | paired4-1 (18.4 / 144.7) | -5.4 | -47.1 | -10.2 | -11.0 | -705 | no/no |
| 2 | paired4-ref-R3R-2 (24.0 / 194.2) | paired4-2 (19.5 / 155.3) | -4.5 | -38.9 | -10.2 | -11.0 | +10 | no/no |
| 3 | paired4-ref-R3R-3 (24.5 / 194.9) | paired4-3 (19.4 / 154.9) | -5.1 | -40.0 | -10.2 | -11.0 | -175 | no/no |
| **mean [range], n=3** | | | **-5.0 [-5.4 … -4.5]** | **-42.0 [-47.1 … -38.9]** | -10.2 [-10.2 … -10.2] | -11.0 [-11.0 … -11.0] | -290 | |

R2F reference drift within this candidate's sequence: medians 23.8 24.0 24.5 (range 0.7), adjacent-ref swings +0.2 +0.5; recalcs/tok 93.4 93.4 93.4; contended 0/3. Sequential R2F row for scale: 23.6 s/token (B2, 2 of 3 runs contended).

**R3R — REAL effect.** Paired Δ median = -5.0 s/token (range -5.4 … -4.5, n=3), Δ total = -42.0 s per 8 tokens (range -47.1 … -38.9); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 0.5 s/token and a ref spread of 0.7 s/token over the 3 ref runs. Pass counts move by -10.2 recalcs/token and -11.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS -290 MB. 0 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8.

