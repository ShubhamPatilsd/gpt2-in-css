# Round-4 paired bench (B5, interleaved vs combined4) — 2026-09-21

Why: same-bundle run-to-run drift today exceeds the effect sizes under test, so each candidate run is paired with a `combined4` reference run (18.2 s/token, B4 paired) taken immediately before it (same harness, same machine state within ~10 min); the statistic is the paired difference.
Protocol: `B5/run_bench5.sh` = `B0/run_bench.sh` + round-4 CHROME.lock owner protocol — headless Chrome 153, heap=1, `B0_TRIGGER=keyboard` for BOTH arms (no mouse event, so mouseoff is moot), passive, AC required, quiet gate disabled (load recorded once; CONTENDED = load1 ≥ 6 or a > 90 % CPU hog), 30 s power watchdog, CHROME.lock held only while a run is active. Per candidate: ref, cand, ref, cand, ref, cand (3 pairs; combined6/combined7: 4 pairs), untraced. Runs: `bench/runs/combined4/paired5-ref-<cand>-<k>`, `bench/runs/<cand>/paired5-<k>`.
Pair validity (coordinator, 02:1x): the interleaving assumption needs the candidate to start soon after its reference — a pair whose ref→cand START gap exceeds 10 min (other agents' 32-token runs held CHROME.lock in between) is marked **INVALID** and excluded from the mean/verdict; the driver runs replacement pairs (k = 4, 5, …) until 3 (combined6/7: 4) valid pairs exist. From pair k ≥ 3 of combined5 the candidate arm gives up (rc 6) if it cannot take the lock within 390 s of the ref's end, so a late candidate is never run.
Contended flags: every R4S-sequence run (01:00–01:16) was flagged CONTENDED by an orphaned R4C `populations.py` at ≈100 % CPU (both arms saw it; the coordinator killed it at 01:17) — runs after 01:17 are clean unless flagged in the table.

## R4S — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-R4S-1 | 01:00:57 → 01:03:50 | 8/8 | 19.3 15.4 15.9 16.3 17.4 17.1 18.0 17.6 | 17.2 | 136.9 | 5405 | 83.2 | 76.0 | 5.3 | 4.9 | **yes** (load1=5.26 top=100.0:app/Contents/MacOS/Python) |
| 2 | R4S | paired5-1 | 01:03:53 → 01:06:14 | 8/8 | 18.2 14.8 15.5 15.8 16.4 16.2 17.4 17.7 | 16.3 | 132.0 | 5593 | 435.8 | 64.0 | 4.9 | 5.7 | **yes** (load1=4.92 top=99.2:app/Contents/MacOS/Python) |
| 3 | combined4 | paired5-ref-R4S-2 | 01:06:16 → 01:09:08 | 8/8 | 19.0 15.0 15.9 16.1 16.5 17.8 17.4 17.4 | 16.9 | 135.0 | 5358 | 83.2 | 76.0 | 5.6 | 7.4 | **yes** (load1=5.69 top=97.4:app/Contents/MacOS/Python) |
| 4 | R4S | paired5-2 | 01:09:10 → 01:11:32 | 8/8 | 18.2 15.0 15.5 15.7 16.1 16.5 17.4 17.9 | 16.3 | 132.3 | 5595 | 435.8 | 64.0 | 7.0 | 5.2 | **yes** (load1=7.36 top=99.3:app/Contents/MacOS/Python) |
| 5 | combined4 | paired5-ref-R4S-3 | 01:11:34 → 01:13:58 | 8/8 | 18.7 14.9 15.9 16.0 16.6 17.1 17.7 18.1 | 16.9 | 135.0 | 5284 | 83.2 | 76.0 | 5.2 | 6.5 | **yes** (load1=5.21 top=98.4:app/Contents/MacOS/Python) |
| 6 | R4S | paired5-3 | 01:14:00 → 01:16:22 | 8/8 | 18.1 14.7 15.5 15.8 16.2 16.7 17.9 18.0 | 16.5 | 133.1 | 5472 | 435.8 | 64.0 | 6.2 | 5.7 | **yes** (load1=6.52 top=100.0:app/Contents/MacOS/Python) |
Machine state: median load1 across this candidate's 6 runs (START and END samples) = **5.6** (range 4.9–7.4); 6 of 6 runs CONTENDED; runs 01:00–01:16.

### R4S — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-R4S-1 (17.2 / 136.9) | paired5-1 (16.3 / 132.0) | 2.9 min | yes | 5.7 (noisy) | -0.9 | -4.9 | +352.6 | -12.0 | +188 | yes/yes |
| 2 | paired5-ref-R4S-2 (16.9 / 135.0) | paired5-2 (16.3 / 132.3) | 2.9 min | yes | 7.4 (noisy) | -0.6 | -2.7 | +352.6 | -12.0 | +237 | yes/yes |
| 3 | paired5-ref-R4S-3 (16.9 / 135.0) | paired5-3 (16.5 / 133.1) | 2.4 min | yes | 6.5 (noisy) | -0.4 | -1.9 | +352.6 | -12.0 | +188 | yes/yes |
| **mean [range] over valid pairs, n=3** | | | | | | **-0.6 [-0.9 … -0.4]** | **-3.2 [-4.9 … -1.9]** | +352.6 [+352.6 … +352.6] | -12.0 [-12.0 … -12.0] | +204 | |

combined4 reference drift over the valid pairs: medians 17.2 16.9 16.9 (range 0.3), adjacent-ref swings -0.3 +0.0; recalcs/tok 83.2 83.2 83.2; contended 3/3. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**R4S — REAL effect.** Paired Δ median = -0.6 s/token (range -0.9 … -0.4, n=3 valid pairs), Δ total = -3.2 s per 8 tokens (range -4.9 … -1.9); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 0.3 s/token and a ref spread of 0.3 s/token over the 3 ref runs. Pass counts move by +352.6 recalcs/token and -12.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS +204 MB. 3 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. No pair was clean of load (user activity / other agents' builds during the sequence) — read the mean with that caveat.

## R4T — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-R4T-1 | 02:17:46 → 02:21:23 | 8/8 | 22.9 19.0 19.3 20.7 20.6 21.2 26.7 24.4 | 21.0 | 174.9 | 3994 | 83.2 | 76.0 | 4.6 | 29.8 | no |
| 2 | R4T | paired5-1 | 02:21:25 → 02:24:40 | 8/8 | 23.4 19.4 18.0 21.7 23.1 25.3 28.4 25.1 | 23.3 | 184.4 | 3589 | 83.2 | 76.0 | 34.7 | 33.5 | **yes** (load1=29.83 top=106.2:p/Contents/MacOS/Messages) |
| 3 | combined4 | paired5-ref-R4T-2 | 02:24:43 → 02:28:12 | 8/8 | 21.1 16.6 19.3 20.1 21.1 23.2 24.3 21.3 | 21.1 | 167.0 | 3675 | 83.2 | 76.0 | 33.5 | 8.8 | **yes** (load1=33.52 top=253.3:framework/Helpers/Browser) |
| 4 | R4T | paired5-2 | – | MISSING (not run) | | | | | | | | | |
| 5 | combined4 | paired5-ref-R4T-3 | 03:25:14 → 03:28:21 | 8/8 | 20.0 15.9 16.7 17.5 17.9 19.5 20.5 19.7 | 18.7 | 147.6 | 4636 | 83.2 | 76.0 | 5.1 | 4.9 | **yes** (load1=5.08 top=100.0:app/Contents/MacOS/Python) |
| 6 | R4T | paired5-3 | 03:28:23 → 03:31:00 | 8/8 | 20.2 15.5 16.3 16.9 20.2 18.5 19.6 20.2 | 19.0 | 147.4 | 4679 | 83.2 | 76.0 | 5.0 | 4.6 | no |
| 7 | combined4 | paired5-ref-R4T-4 | 03:31:02 → 03:34:22 | 8/8 | 21.7 17.6 18.4 19.6 19.1 20.6 21.3 23.1 | 20.1 | 161.3 | 4140 | 83.2 | 76.0 | 4.7 | 3.3 | no |
| 8 | R4T | paired5-4 | 03:34:24 → 03:36:52 | 8/8 | 18.5 14.0 15.2 16.3 17.9 17.3 18.7 20.2 | 17.6 | 138.0 | 4010 | 83.2 | 76.0 | 3.3 | 3.7 | no |
Machine state: median load1 across this candidate's 7 runs (START and END samples) = **4.9** (range 3.3–34.7); 3 of 7 runs CONTENDED; runs 02:17–03:36.

### R4T — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-R4T-1 (21.0 / 174.9) | paired5-1 (23.3 / 184.4) | 3.6 min | yes | 34.7 (noisy) | +2.3 | +9.5 | +0.0 | +0.0 | -405 | no/yes |
| 2 | paired5-ref-R4T-2 (21.1 / 167.0) | paired5-2 MISSING | – | **INVALID** (cand not run) | | | | | | | |
| 3 | paired5-ref-R4T-3 (18.7 / 147.6) | paired5-3 (19.0 / 147.4) | 3.1 min | yes | 5.1 (noisy) | +0.3 | -0.2 | +0.0 | +0.0 | +43 | yes/no |
| 4 | paired5-ref-R4T-4 (20.1 / 161.3) | paired5-4 (17.6 / 138.0) | 3.4 min | yes | 4.7 | -2.5 | -23.3 | +0.0 | +0.0 | -130 | no/no |
| **mean [range] over valid pairs, n=3** | | | | | | **+0.0 [-2.5 … +2.3]** | **-4.7 [-23.3 … +9.5]** | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | -164 | |
| *clean-load subset (no CONTENDED, load1 < 10), n=1, k=4* | | | | | | *-2.5 [-2.5 … -2.5]* | *-23.3 [-23.3 … -23.3]* | | | | |

combined4 reference drift over the valid pairs: medians 21.0 18.7 20.1 (range 2.3), adjacent-ref swings -2.3 +1.4; recalcs/tok 83.2 83.2 83.2; contended 1/3. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**R4T — NOT distinguishable from noise.** Paired Δ median = +0.0 s/token (range -2.5 … +2.3, n=3 valid pairs, invalid pairs excluded: k=2), Δ total = -4.7 s per 8 tokens (range -23.3 … +9.5); the pairs disagree in sign and the paired range includes zero, against a largest adjacent-ref swing of 2.3 s/token and a ref spread of 2.3 s/token over the 3 ref runs. Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS -164 MB. 2 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=1): Δ median -2.5 s/token [-2.5 … -2.5].

## combined5 — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-combined5-1 | 01:19:31 → 01:21:55 | 8/8 | 18.7 15.0 15.7 16.0 16.5 17.5 17.5 17.6 | 17.0 | 134.4 | 5511 | 83.2 | 76.0 | 5.9 | 4.7 | no |
| 2 | combined5 | paired5-1 | 02:09:46 → 02:12:10 | 8/8 | 18.9 15.0 15.8 16.1 16.4 17.3 17.2 17.3 | 16.8 | 134.0 | 5756 | 83.2 | 76.0 | 4.7 | 3.5 | no |
| 3 | combined4 | paired5-ref-combined5-2 | 02:12:12 → 02:14:52 | 8/8 | 19.1 15.4 15.7 17.4 19.4 20.6 22.7 20.7 | 19.3 | 150.9 | 5166 | 83.2 | 76.0 | 3.5 | 4.9 | no |
| 4 | combined5 | paired5-2 | – | MISSING (not run) | | | | | | | | | |
| 5 | combined4 | paired5-ref-combined5-3 | 03:36:54 → 03:39:40 | 8/8 | 19.6 15.9 17.6 18.8 20.4 20.7 21.6 21.7 | 20.0 | 156.3 | 4140 | 83.2 | 76.0 | 3.7 | 4.8 | no |
| 6 | combined5 | paired5-3 | 03:39:42 → 03:42:49 | 8/8 | 20.1 17.7 16.2 17.0 17.8 19.4 19.8 20.4 | 18.6 | 148.4 | 4533 | 83.2 | 76.0 | 4.8 | 4.2 | no |
| 7 | combined4 | paired5-ref-combined5-4 | 03:42:51 → 03:45:35 | 8/8 | 19.4 15.7 17.6 18.6 19.6 20.0 21.2 21.8 | 19.5 | 153.9 | 4597 | 83.2 | 76.0 | 4.2 | 4.4 | no |
| 8 | combined5 | paired5-4 | 03:45:37 → 03:48:12 | 8/8 | 19.1 15.2 16.7 17.6 18.1 18.7 20.0 20.7 | 18.4 | 146.0 | 4331 | 83.2 | 76.0 | 4.4 | 4.3 | no |
| 9 | combined4 | paired5-ref-combined5-5 | 03:58:01 → 04:00:33 | 8/8 | 19.3 15.7 16.2 16.9 17.5 18.8 19.5 19.5 | 18.2 | 143.3 | 4778 | 83.2 | 76.0 | 3.5 | 3.6 | **yes** (load1=3.82 top=158.4:Versions/A/mediaanalysisd) |
| 10 | combined5 | paired5-5 | 04:00:35 → 04:03:35 | 8/8 | 19.1 15.7 16.0 16.9 17.6 18.4 19.5 18.3 | 17.9 | 141.5 | 4850 | 83.2 | 76.0 | 3.4 | 3.8 | no |
Machine state: median load1 across this candidate's 9 runs (START and END samples) = **4.3** (range 3.4–5.9); 1 of 9 runs CONTENDED; runs 01:19–04:03.

### combined5 — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-combined5-1 (17.0 / 134.4) | paired5-1 (16.8 / 134.0) | 50.2 min | **INVALID** (gap 50 min > 10) | 5.9 | -0.2 | -0.4 | +0.0 | +0.0 | +245 | no/no |
| 2 | paired5-ref-combined5-2 (19.3 / 150.9) | paired5-2 MISSING | – | **INVALID** (cand not run) | | | | | | | |
| 3 | paired5-ref-combined5-3 (20.0 / 156.3) | paired5-3 (18.6 / 148.4) | 2.8 min | yes | 4.8 | -1.4 | -7.9 | +0.0 | +0.0 | +393 | no/no |
| 4 | paired5-ref-combined5-4 (19.5 / 153.9) | paired5-4 (18.4 / 146.0) | 2.8 min | yes | 4.4 | -1.1 | -7.9 | +0.0 | +0.0 | -266 | no/no |
| 5 | paired5-ref-combined5-5 (18.2 / 143.3) | paired5-5 (17.9 / 141.5) | 2.6 min | yes | 3.8 (noisy) | -0.3 | -1.8 | +0.0 | +0.0 | +72 | yes/no |
| **mean [range] over valid pairs, n=3** | | | | | | **-0.9 [-1.4 … -0.3]** | **-5.9 [-7.9 … -1.8]** | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | +66 | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=3,4* | | | | | | *-1.2 [-1.4 … -1.1]* | *-7.9 [-7.9 … -7.9]* | | | | |

combined4 reference drift over the valid pairs: medians 20.0 19.5 18.2 (range 1.8), adjacent-ref swings -0.5 -1.3; recalcs/tok 83.2 83.2 83.2; contended 1/3. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**combined5 — probably real but within one adjacent-ref swing.** Paired Δ median = -0.9 s/token (range -1.4 … -0.3, n=3 valid pairs, invalid pairs excluded: k=1,2), Δ total = -5.9 s per 8 tokens (range -7.9 … -1.8); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 1.3 s/token and a ref spread of 1.8 s/token over the 3 ref runs. Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS +66 MB. 1 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median -1.2 s/token [-1.4 … -1.1].

## combined6 — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-combined6-1 | 04:03:38 → 04:06:41 | 8/8 | 19.8 15.9 16.3 17.3 17.9 18.7 19.0 19.8 | 18.3 | 144.6 | 4776 | 83.2 | 76.0 | 3.8 | 3.7 | no |
| 2 | combined6 | paired5-1 | 04:06:43 → 04:09:21 | 8/8 | 19.4 15.9 17.2 17.6 18.6 19.2 20.0 20.6 | 18.9 | 148.5 | 4780 | 435.8 | 64.0 | 3.7 | 3.2 | no |
| 3 | combined4 | paired5-ref-combined6-2 | 04:09:24 → 04:12:31 | 8/8 | 21.5 17.4 16.8 17.3 18.2 18.8 19.6 19.0 | 18.5 | 148.5 | 4817 | 83.2 | 76.0 | 3.2 | 3.5 | no |
| 4 | combined6 | paired5-2 | 04:12:33 → 04:15:04 | 8/8 | 18.5 15.1 15.7 16.0 16.9 18.3 20.0 21.3 | 17.6 | 141.9 | 4695 | 435.8 | 64.0 | 3.5 | 5.4 | no |
| 5 | combined4 | paired5-ref-combined6-3 | 04:15:06 → 04:17:45 | 8/8 | 19.3 16.1 17.7 18.1 20.5 22.2 17.7 17.2 | 17.9 | 148.8 | 5950 | 83.2 | 76.0 | 5.1 | 3.3 | **yes** (load1=5.36 top=100.0:app/Contents/MacOS/Python) |
| 6 | combined6 | paired5-3 | 04:17:47 → 04:20:09 | 8/8 | 18.6 15.0 15.5 15.9 16.0 17.0 17.2 17.3 | 16.5 | 132.4 | 5963 | 435.8 | 64.0 | 3.2 | 3.7 | no |
| 7 | combined4 | paired5-ref-combined6-4 | 04:20:11 → 04:23:07 | 8/8 | 19.5 15.8 16.0 16.5 16.8 17.4 17.6 17.7 | 17.1 | 137.3 | 5555 | 83.2 | 76.0 | 3.4 | 4.6 | no |
| 8 | combined6 | paired5-4 | 04:23:09 → 04:26:01 | 8/8 | 18.6 15.4 15.5 16.1 16.3 16.8 17.6 17.5 | 16.5 | 133.9 | 5464 | 435.8 | 64.0 | 4.6 | 3.4 | **yes** (load1=4.60 top=92.8:0-Bkophe3JY22/bin/python3) |
Machine state: median load1 across this candidate's 8 runs (START and END samples) = **3.6** (range 3.2–5.4); 2 of 8 runs CONTENDED; runs 04:03–04:26.

### combined6 — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-combined6-1 (18.3 / 144.6) | paired5-1 (18.9 / 148.5) | 3.1 min | yes | 3.8 | +0.6 | +3.9 | +352.6 | -12.0 | +4 | no/no |
| 2 | paired5-ref-combined6-2 (18.5 / 148.5) | paired5-2 (17.6 / 141.9) | 3.1 min | yes | 5.4 | -0.9 | -6.6 | +352.6 | -12.0 | -122 | no/no |
| 3 | paired5-ref-combined6-3 (17.9 / 148.8) | paired5-3 (16.5 / 132.4) | 2.7 min | yes | 5.1 (noisy) | -1.4 | -16.4 | +352.6 | -12.0 | +13 | yes/no |
| 4 | paired5-ref-combined6-4 (17.1 / 137.3) | paired5-4 (16.5 / 133.9) | 3.0 min | yes | 4.6 (noisy) | -0.6 | -3.4 | +352.6 | -12.0 | -91 | no/yes |
| **mean [range] over valid pairs, n=4** | | | | | | **-0.6 [-1.4 … +0.6]** | **-5.6 [-16.4 … +3.9]** | +352.6 [+352.6 … +352.6] | -12.0 [-12.0 … -12.0] | -49 | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=1,2* | | | | | | *-0.2 [-0.9 … +0.6]* | *-1.3 [-6.6 … +3.9]* | | | | |

combined4 reference drift over the valid pairs: medians 18.3 18.5 17.9 17.1 (range 1.4), adjacent-ref swings +0.2 -0.6 -0.8; recalcs/tok 83.2 83.2 83.2 83.2; contended 1/4. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**combined6 — NOT distinguishable from noise.** Paired Δ median = -0.6 s/token (range -1.4 … +0.6, n=4 valid pairs), Δ total = -5.6 s per 8 tokens (range -16.4 … +3.9); the pairs disagree in sign and the paired range includes zero, against a largest adjacent-ref swing of 0.8 s/token and a ref spread of 1.4 s/token over the 4 ref runs. Pass counts move by +352.6 recalcs/token and -12.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS -49 MB. 2 of 4 pairs had a contended run. ids: 8/8; 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median -0.2 s/token [-0.9 … +0.6].

## combined7 — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-combined7-1 | 04:26:04 → 04:28:35 | 8/8 | 19.4 15.6 16.4 16.0 16.9 18.4 19.7 19.5 | 17.6 | 141.9 | 5780 | 83.2 | 76.0 | 3.4 | 3.9 | no |
| 2 | combined7 | paired5-1 | 04:28:37 → 04:30:47 | 8/8 | 17.1 13.2 13.9 14.3 14.7 15.2 16.1 15.5 | 14.9 | 120.0 | 5954 | 435.8 | 64.0 | 3.8 | 3.9 | no |
| 3 | combined4 | paired5-ref-combined7-2 | 04:30:49 → 04:33:16 | 8/8 | 19.4 15.5 16.0 16.5 17.1 17.4 17.9 17.8 | 17.2 | 137.7 | 5876 | 83.2 | 76.0 | 3.9 | 3.0 | no |
| 4 | combined7 | paired5-2 | 04:33:19 → 04:35:37 | 8/8 | 18.6 14.4 15.0 15.4 15.8 16.4 16.8 16.8 | 16.1 | 129.2 | 5973 | 435.8 | 64.0 | 3.0 | 3.0 | no |
| 5 | combined4 | paired5-ref-combined7-3 | 04:35:40 → 04:38:16 | 8/8 | 19.2 16.5 17.6 17.8 18.3 18.9 19.2 19.0 | 18.6 | 146.4 | 5830 | 83.2 | 76.0 | 3.0 | 3.0 | no |
| 6 | combined7 | paired5-3 | 04:38:18 → 04:41:06 | 8/8 | 19.0 14.4 15.1 15.3 15.7 16.1 16.9 17.2 | 15.9 | 129.7 | 5781 | 435.8 | 64.0 | 3.0 | 3.7 | no |
| 7 | combined4 | paired5-ref-combined7-4 | 04:41:08 → 04:43:44 | 8/8 | 19.4 15.8 17.4 18.1 18.6 18.8 19.2 19.3 | 18.7 | 146.6 | 5678 | 83.2 | 76.0 | 3.5 | 3.9 | no |
| 8 | combined7 | paired5-4 | 04:43:47 → 04:46:35 | 8/8 | 19.0 14.3 15.0 15.4 15.8 16.3 17.1 17.3 | 16.1 | 130.1 | 5726 | 435.8 | 64.0 | 3.9 | 3.6 | no |
Machine state: median load1 across this candidate's 8 runs (START and END samples) = **3.6** (range 3.0–3.9); 0 of 8 runs CONTENDED; runs 04:26–04:46.

### combined7 — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-combined7-1 (17.6 / 141.9) | paired5-1 (14.9 / 120.0) | 2.5 min | yes | 3.9 | -2.7 | -21.9 | +352.6 | -12.0 | +174 | no/no |
| 2 | paired5-ref-combined7-2 (17.2 / 137.7) | paired5-2 (16.1 / 129.2) | 2.5 min | yes | 3.9 | -1.1 | -8.5 | +352.6 | -12.0 | +97 | no/no |
| 3 | paired5-ref-combined7-3 (18.6 / 146.4) | paired5-3 (15.9 / 129.7) | 2.6 min | yes | 3.7 | -2.7 | -16.7 | +352.6 | -12.0 | -49 | no/no |
| 4 | paired5-ref-combined7-4 (18.7 / 146.6) | paired5-4 (16.1 / 130.1) | 2.6 min | yes | 3.9 | -2.6 | -16.5 | +352.6 | -12.0 | +48 | no/no |
| **mean [range] over valid pairs, n=4** | | | | | | **-2.3 [-2.7 … -1.1]** | **-15.9 [-21.9 … -8.5]** | +352.6 [+352.6 … +352.6] | -12.0 [-12.0 … -12.0] | +68 | |

combined4 reference drift over the valid pairs: medians 17.6 17.2 18.6 18.7 (range 1.5), adjacent-ref swings -0.4 +1.4 +0.1; recalcs/tok 83.2 83.2 83.2 83.2; contended 0/4. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**combined7 — REAL effect.** Paired Δ median = -2.3 s/token (range -2.7 … -1.1, n=4 valid pairs), Δ total = -15.9 s per 8 tokens (range -21.9 … -8.5); all 4 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 1.4 s/token and a ref spread of 1.5 s/token over the 4 ref runs. Pass counts move by +352.6 recalcs/token and -12.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS +68 MB. 0 of 4 pairs had a contended run. ids: 8/8; 8/8; 8/8; 8/8.

## R4T2 — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-R4T2-1 | 04:46:38 → 04:49:06 | 8/8 | 19.2 15.4 16.3 16.8 17.1 17.5 18.2 18.8 | 17.3 | 139.2 | 5545 | 83.2 | 76.0 | 3.6 | 14.9 | no |
| 2 | R4T2 | paired5-1 | 04:49:08 → 04:51:30 | 8/8 | 18.2 14.0 15.3 15.9 16.5 17.2 17.5 17.4 | 16.8 | 132.0 | 5979 | 83.2 | 76.0 | 13.9 | 4.1 | **yes** (load1=14.91 top=55.1:amework/Support/contactsd) |
| 3 | combined4 | paired5-ref-R4T2-2 | 04:51:32 → 04:54:01 | 8/8 | 19.4 15.3 16.1 16.3 17.0 17.3 18.3 19.3 | 17.1 | 138.9 | 5847 | 83.2 | 76.0 | 4.1 | 3.8 | no |
| 4 | R4T2 | paired5-2 | 04:54:03 → 04:56:24 | 8/8 | 18.4 13.9 14.7 15.4 16.5 16.8 17.8 18.0 | 16.6 | 131.5 | 5983 | 83.2 | 76.0 | 3.6 | 4.2 | no |
| 5 | combined4 | paired5-ref-R4T2-3 | 04:56:26 → 04:59:34 | 8/8 | 21.2 16.9 17.5 18.2 18.5 19.2 19.3 19.3 | 18.9 | 150.2 | 5671 | 83.2 | 76.0 | 4.2 | 3.6 | no |
| 6 | R4T2 | paired5-3 | 04:59:37 → 05:02:28 | 8/8 | 18.5 14.0 15.6 16.1 16.4 17.3 17.6 17.8 | 16.8 | 133.4 | 5763 | 83.2 | 76.0 | 3.6 | 3.5 | no |
Machine state: median load1 across this candidate's 6 runs (START and END samples) = **4.0** (range 3.5–14.9); 1 of 6 runs CONTENDED; runs 04:46–05:02.

### R4T2 — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-R4T2-1 (17.3 / 139.2) | paired5-1 (16.8 / 132.0) | 2.5 min | yes | 14.9 (noisy) | -0.5 | -7.2 | +0.0 | +0.0 | +434 | no/yes |
| 2 | paired5-ref-R4T2-2 (17.1 / 138.9) | paired5-2 (16.6 / 131.5) | 2.5 min | yes | 4.2 | -0.5 | -7.4 | +0.0 | +0.0 | +136 | no/no |
| 3 | paired5-ref-R4T2-3 (18.9 / 150.2) | paired5-3 (16.8 / 133.4) | 3.2 min | yes | 4.2 | -2.1 | -16.8 | +0.0 | +0.0 | +92 | no/no |
| **mean [range] over valid pairs, n=3** | | | | | | **-1.0 [-2.1 … -0.5]** | **-10.5 [-16.8 … -7.2]** | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | +221 | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=2,3* | | | | | | *-1.3 [-2.1 … -0.5]* | *-12.1 [-16.8 … -7.4]* | | | | |

combined4 reference drift over the valid pairs: medians 17.3 17.1 18.9 (range 1.8), adjacent-ref swings -0.2 +1.8; recalcs/tok 83.2 83.2 83.2; contended 0/3. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**R4T2 — probably real but within one adjacent-ref swing.** Paired Δ median = -1.0 s/token (range -2.1 … -0.5, n=3 valid pairs), Δ total = -10.5 s per 8 tokens (range -16.8 … -7.2); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 1.8 s/token and a ref spread of 1.8 s/token over the 3 ref runs. Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS +221 MB. 1 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median -1.3 s/token [-2.1 … -0.5].

## R4T-b — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | recalcs/tok | layouts/tok | load1 START | load1 END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | combined4 | paired5-ref-R4T-b-1 | 05:22:41 → 05:25:09 | 8/8 | 19.4 15.4 16.0 16.9 17.2 17.3 17.9 18.0 | 17.3 | 138.1 | 5312 | 83.2 | 76.0 | 3.7 | 3.9 | no |
| 2 | R4T | paired5-b-1 | 05:25:11 → 05:28:08 | 8/8 | 20.3 15.3 16.0 16.4 16.7 17.1 18.5 18.1 | 16.9 | 138.3 | 5431 | 83.2 | 76.0 | 4.1 | 4.3 | no |
| 3 | combined4 | paired5-ref-R4T-b-2 | 05:28:10 → 05:31:18 | 8/8 | 19.6 17.0 17.9 17.9 18.5 19.0 19.6 19.5 | 18.7 | 149.0 | 5409 | 83.2 | 76.0 | 4.0 | 4.6 | no |
| 4 | R4T | paired5-b-2 | 05:31:20 → 05:34:14 | 8/8 | 20.1 15.1 15.9 16.0 16.5 17.4 17.4 18.0 | 17.0 | 136.3 | 5377 | 83.2 | 76.0 | 4.6 | 4.0 | no |
| 5 | combined4 | paired5-ref-R4T-b-3 | 05:34:17 → 05:37:24 | 8/8 | 19.6 15.7 17.7 18.1 18.5 19.2 20.2 20.1 | 18.9 | 149.1 | 5312 | 83.2 | 76.0 | 4.0 | 3.1 | no |
| 6 | R4T | paired5-b-3 | 05:37:26 → 05:40:21 | 8/8 | 19.9 15.0 15.8 16.1 16.6 17.5 17.9 17.8 | 17.1 | 136.5 | 5374 | 83.2 | 76.0 | 3.2 | 3.6 | no |
Machine state: median load1 across this candidate's 6 runs (START and END samples) = **4.0** (range 3.1–4.6); 0 of 6 runs CONTENDED; runs 05:22–05:40.

### R4T-b — paired differences (candidate − the combined4 run immediately before it)

| pair k | ref run (median / total) | cand run (median / total) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ recalcs/tok | Δ layouts/tok | Δ RSS MB | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | paired5-ref-R4T-b-1 (17.3 / 138.1) | paired5-b-1 (16.9 / 138.3) | 2.5 min | yes | 4.3 | -0.4 | +0.2 | +0.0 | +0.0 | +119 | no/no |
| 2 | paired5-ref-R4T-b-2 (18.7 / 149.0) | paired5-b-2 (17.0 / 136.3) | 3.2 min | yes | 4.6 | -1.7 | -12.7 | +0.0 | +0.0 | -32 | no/no |
| 3 | paired5-ref-R4T-b-3 (18.9 / 149.1) | paired5-b-3 (17.1 / 136.5) | 3.1 min | yes | 4.0 | -1.8 | -12.6 | +0.0 | +0.0 | +62 | no/no |
| **mean [range] over valid pairs, n=3** | | | | | | **-1.3 [-1.8 … -0.4]** | **-8.4 [-12.7 … +0.2]** | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | +50 | |

combined4 reference drift over the valid pairs: medians 17.3 18.7 18.9 (range 1.6), adjacent-ref swings +1.4 +0.2; recalcs/tok 83.2 83.2 83.2; contended 0/3. combined4 for scale: 18.2 s/token (B4 paired, 4 cand runs, medians 18.4 18.1 18.1 18.5).

**R4T-b — probably real but within one adjacent-ref swing.** Paired Δ median = -1.3 s/token (range -1.8 … -0.4, n=3 valid pairs), Δ total = -8.4 s per 8 tokens (range -12.7 … +0.2); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 1.4 s/token and a ref spread of 1.6 s/token over the 3 ref runs. Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). RSS +50 MB. 0 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8.

