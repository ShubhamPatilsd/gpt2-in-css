# Round-5 paired bench (B6, interleaved vs combined7) — 2026-09-24

Why: same-bundle run-to-run drift exceeds the effect sizes under test, so each candidate run is paired with a `combined7` reference run (16.0 s/token, B5 paired; RSS peak ≈6 GB) taken immediately before it under the same CHROME.lock hold; the statistic is the paired difference. Round 5 is about memory as well as time, so RSS peak and RSS at token 8 are first-class columns.
Protocol: `B6/run_bench6.sh` = `B5/run_bench5.sh` + round-5 machine gate — headless Chrome 153, heap=1, `B0_TRIGGER=keyboard` for BOTH arms, passive, untraced, AC required, quiet gate disabled (load recorded once; CONTENDED = load1 ≥ 6 or a > 90 % CPU hog), 30 s power watchdog. ONE CHROME.lock hold per pair (owner `B6 pair <cand>-<k>`, touch -c 30 s, rmdir own only), ref then cand back-to-back. Machine gate before EVERY Chrome launch: AC power AND free disk ≥ 3.0 GB AND `vm.swapusage` used < 3,000 MB (poll 60 s; if closed > 10 min under the lock the pair is abandoned and the lock released). Per candidate: ref, cand, ref, cand, ref, cand until 3 valid pairs (combined8*: 4). Runs: `bench/runs/combined7/paired6-ref-<cand>-<k>`, `bench/runs/<cand>/paired6-<k>`.
Pair validity: ref→cand START gap ≤ 10 min, else **INVALID** (shown, excluded from the mean/verdict; replacement pairs k = 4, 5, …).
Columns: RSS peak = max renderer RSS (ps, 1 Hz) during generation; RSS@tok8 = renderer RSS sample at token 8's capture; recalcs/layouts per token = RecalcStyleCount / LayoutCount differenced at each token's capture time from the harness's 1 Hz `Performance.getMetrics` samples (the per-token split is ±1 sample; the 8-token totals /8 in the `recalcs/tok`, `layouts/tok` columns are exact). Frame counts are NOT available in untraced runs (the harness exposes them only in traces). disk/swap = free disk GB and swap used MB at run START → END.

## R5H — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | RSS@tok8 MB | RSS/tok MB (1–8) | recalcs/tok | layouts/tok | recalcs per token (1–8) | layouts per token (1–8) | load1 START→END | disk GB START→END | swap MB START→END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|
| 1 | combined7 | paired6-ref-R5H-1 | 14:55:22 → 14:57:34 | 8/8 | 17.1 12.9 13.6 14.0 14.9 15.9 17.0 17.2 | 15.4 | 122.6 | 4895 | 4295 | 3290 4165 4500 4838 4835 4778 4852 4895 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 5.0 → 4.3 | 5.1 → 5.1 | 2981 → 2957 | **yes** (load1=4.71 top=100.0:app/Contents/MacOS/Python) |
| 2 | R5H | paired6-1 | 14:57:36 → 14:59:46 | 8/8 | 16.8 13.0 13.6 13.9 14.3 15.3 16.6 16.8 | 14.8 | 120.4 | 5292 | 4764 | 3655 4184 4763 5021 5139 5106 5292 5131 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 4.2 → 3.6 | 5.1 → 5.1 | 2957 → 2957 | **yes** (load1=4.32 top=100.0:app/Contents/MacOS/Python) |
| 3 | combined7 | paired6-ref-R5H-2 | 14:59:48 → 15:02:07 | 8/8 | 16.9 13.8 14.3 14.9 15.7 16.7 18.0 18.3 | 16.2 | 128.6 | 4989 | 4616 | 3222 3840 4443 4664 4966 4989 4784 4805 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.6 → 3.9 | 5.1 → 5.1 | 2957 → 2933 | no |
| 4 | R5H | paired6-2 | 15:02:09 → 15:04:37 | 8/8 | 17.5 13.5 14.1 17.0 16.5 18.0 18.4 22.7 | 17.3 | 137.8 | 4700 | 3852 | 3669 3860 4529 4700 4457 4299 4267 4084 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 3.9 → 4.3 | 5.1 → 5.1 | 2933 → 2893 | no |
| 5 | combined7 | paired6-ref-R5H-3 | 15:04:39 → 15:07:53 | 8/8 | 20.3 15.0 16.3 16.8 17.9 18.4 23.0 23.3 | 18.1 | 151.0 | 4097 | 2894 | 3313 4027 4025 4080 4097 4004 3753 3555 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 4.3 → 6.0 | 5.1 → 5.1 | 2893 → 2869 | no |
| 6 | R5H | paired6-3 | 15:07:56 → 15:11:08 | 8/8 | 20.1 15.5 16.6 17.5 19.2 19.1 21.3 19.8 | 19.2 | 149.1 | 3989 | 3785 | 3162 3496 3827 3927 3911 3802 3977 3957 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 6.0 → 6.0 | 5.1 → 5.1 | 2869 → 2869 | no |
Machine state [R5H]: median load1 across this candidate's 6 runs (START and END samples) = **4.3** (range 3.6–6.0); swap used median **2933 MB** (range 2869–2981); disk free 5.1–5.1 GB; 2 of 6 runs CONTENDED; runs 14:55–15:11.

### R5H — paired differences (candidate − the combined7 run immediately before it)

| pair k | ref run (median / total / RSS peak) | cand run (median / total / RSS peak) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ RSS peak MB | Δ RSS@tok8 MB | Δ recalcs/tok | Δ layouts/tok | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | paired6-ref-R5H-1 (15.4 / 122.6 / 4895) | paired6-1 (14.8 / 120.4 / 5292) | 2.2 min | yes | 5.0 (noisy) | -0.6 | -2.2 | +397 | +469 | -364.6 | +0.0 | yes/yes |
| 2 | paired6-ref-R5H-2 (16.2 / 128.6 / 4989) | paired6-2 (17.3 / 137.8 / 4700) | 2.4 min | yes | 4.3 | +1.1 | +9.2 | -289 | -764 | -364.6 | +0.0 | no/no |
| 3 | paired6-ref-R5H-3 (18.1 / 151.0 / 4097) | paired6-3 (19.2 / 149.1 / 3989) | 3.3 min | yes | 6.0 | +1.1 | -1.9 | -108 | +891 | -364.6 | +0.0 | no/no |
| **mean [range] over valid pairs, n=3** | | | | | | **+0.5 [-0.6 … +1.1]** | **+1.7 [-2.2 … +9.2]** | **+0 [-289 … +397]** | +199 [-764 … +891] | -364.6 [-364.6 … -364.6] | +0.0 [+0.0 … +0.0] | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=2,3* | | | | | | *+1.1 [+1.1 … +1.1]* | *+3.7 [-1.9 … +9.2]* | *-198* | | | | |

combined7 reference drift over the valid pairs: medians 15.4 16.2 18.1 (range 2.7), adjacent-ref swings +0.8 +1.9; RSS peaks 4895 4989 4097 MB (range 892); recalcs/tok 435.8 435.8 435.8; layouts/tok 64.0 64.0 64.0; contended 1/3. combined7 for scale: 16.0 s/token (B5 paired vs combined4, 4 pairs, medians 16.0 15.9 16.3 16.0; RSS peak 5973 MB).

**R5H — NOT distinguishable from noise.** Paired Δ median = +0.5 s/token (range -0.6 … +1.1, n=3 valid pairs), Δ total = +1.7 s per 8 tokens (range -2.2 … +9.2); the pairs disagree in sign and the paired range includes zero, against a largest adjacent-ref swing of 1.9 s/token and a ref spread of 2.7 s/token over the 3 ref runs. **Memory: Δ RSS peak = +0 MB (range -289 … +397; mixed sign), Δ RSS@tok8 = +199 MB; candidate RSS peak 5292 MB vs ref 4989 MB (max over pairs).** Pass counts move by -364.6 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). 1 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median +1.1 s/token [+1.1 … +1.1].

## R5C — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | RSS@tok8 MB | RSS/tok MB (1–8) | recalcs/tok | layouts/tok | recalcs per token (1–8) | layouts per token (1–8) | load1 START→END | disk GB START→END | swap MB START→END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|
| 1 | combined7 | paired6-ref-R5C-1 | 15:38:03 → 15:40:34 | 8/8 | 17.4 13.6 15.2 16.3 16.6 18.9 21.8 21.8 | 17.0 | 141.6 | 3829 | 2910 | 3116 3478 3617 3728 3829 3712 3456 3520 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 11.8 → 4.3 | 5.0 → 5.0 | 2661 → 2653 | **yes** (load1=12.60 top=42.0:Contents/MacOS/cua-driver) |
| 2 | R5C | paired6-1 | 15:40:37 → 15:43:19 | 8/8 | 19.2 14.9 16.0 17.3 18.6 20.5 22.0 24.0 | 18.9 | 152.6 | 3801 | 3290 | 2925 3434 3534 3614 3663 3747 3556 3452 | 5031.6 | 52.0 | 4844 4811 4955 4955 5099 5099 5243 5243 | 51 52 52 52 52 52 52 52 | 4.3 → 3.7 | 5.0 → 5.0 | 2653 → 2653 | no |
| 3 | combined7 | paired6-ref-R5C-2 | 15:43:22 → 15:45:52 | 8/8 | 17.2 13.7 15.3 17.2 17.0 18.8 20.3 21.1 | 17.2 | 140.7 | 3834 | 3231 | 2989 3415 3648 3834 3793 3601 3625 3642 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.7 → 4.1 | 5.0 → 5.0 | 2653 → 2645 | no |
| 4 | R5C | paired6-2 | 15:45:54 → 15:48:32 | 8/8 | 18.5 15.3 15.6 16.7 18.5 20.5 21.3 21.7 | 18.5 | 148.1 | 3830 | 3083 | 3183 3430 3645 3665 3830 3676 3574 3687 | 5031.6 | 52.0 | 4844 4811 4955 4955 5099 5099 5243 5243 | 51 52 52 52 52 52 52 52 | 3.8 → 3.8 | 5.0 → 5.0 | 2645 → 2645 | no |
| 5 | combined7 | paired6-ref-R5C-3 | 15:48:35 → 15:51:04 | 8/8 | 17.2 13.4 13.9 15.3 17.6 19.4 20.4 21.6 | 17.4 | 139.0 | 3950 | 3553 | 3139 3688 3838 3950 3724 3773 3739 3633 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.6 → 3.4 | 5.0 → 5.0 | 2645 → 2645 | no |
| 6 | R5C | paired6-3 | 15:51:06 → 15:53:50 | 8/8 | 18.3 15.0 17.0 17.3 19.5 21.2 22.9 23.6 | 18.9 | 154.7 | 3900 | 2657 | 3226 3726 3820 3900 3794 3620 3838 3512 | 5031.6 | 52.0 | 4844 4811 4955 4955 5099 5099 5243 5243 | 51 52 52 52 52 52 52 52 | 3.4 → 5.5 | 5.0 → 5.0 | 2645 → 2637 | no |
Machine state [R5C]: median load1 across this candidate's 6 runs (START and END samples) = **3.8** (range 3.4–11.8); swap used median **2645 MB** (range 2637–2661); disk free 5.0–5.0 GB; 1 of 6 runs CONTENDED; runs 15:38–15:53.

### R5C — paired differences (candidate − the combined7 run immediately before it)

| pair k | ref run (median / total / RSS peak) | cand run (median / total / RSS peak) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ RSS peak MB | Δ RSS@tok8 MB | Δ recalcs/tok | Δ layouts/tok | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | paired6-ref-R5C-1 (17.0 / 141.6 / 3829) | paired6-1 (18.9 / 152.6 / 3801) | 2.6 min | yes | 11.8 (noisy) | +1.9 | +11.0 | -28 | +380 | +4595.8 | -12.0 | yes/no |
| 2 | paired6-ref-R5C-2 (17.2 / 140.7 / 3834) | paired6-2 (18.5 / 148.1 / 3830) | 2.5 min | yes | 4.1 | +1.3 | +7.4 | -4 | -148 | +4595.8 | -12.0 | no/no |
| 3 | paired6-ref-R5C-3 (17.4 / 139.0 / 3950) | paired6-3 (18.9 / 154.7 / 3900) | 2.5 min | yes | 5.5 | +1.5 | +15.7 | -50 | -896 | +4595.8 | -12.0 | no/no |
| **mean [range] over valid pairs, n=3** | | | | | | **+1.6 [+1.3 … +1.9]** | **+11.4 [+7.4 … +15.7]** | **-27 [-50 … -4]** | -221 [-896 … +380] | +4595.8 [+4595.8 … +4595.8] | -12.0 [-12.0 … -12.0] | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=2,3* | | | | | | *+1.4 [+1.3 … +1.5]* | *+11.5 [+7.4 … +15.7]* | *-27* | | | | |

combined7 reference drift over the valid pairs: medians 17.0 17.2 17.4 (range 0.4), adjacent-ref swings +0.2 +0.2; RSS peaks 3829 3834 3950 MB (range 121); recalcs/tok 435.8 435.8 435.8; layouts/tok 64.0 64.0 64.0; contended 1/3. combined7 for scale: 16.0 s/token (B5 paired vs combined4, 4 pairs, medians 16.0 15.9 16.3 16.0; RSS peak 5973 MB).

**R5C — REAL effect.** Paired Δ median = +1.6 s/token (range +1.3 … +1.9, n=3 valid pairs), Δ total = +11.4 s per 8 tokens (range +7.4 … +15.7); all 3 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 0.2 s/token and a ref spread of 0.4 s/token over the 3 ref runs. **Memory: Δ RSS peak = -27 MB (range -50 … -4; same sign in all pairs), Δ RSS@tok8 = -221 MB; candidate RSS peak 3900 MB vs ref 3950 MB (max over pairs).** Pass counts move by +4595.8 recalcs/token and -12.0 layouts/token (deterministic per bundle, so any non-zero value is structural). 1 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median +1.4 s/token [+1.3 … +1.5].

## R5E — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | RSS@tok8 MB | RSS/tok MB (1–8) | recalcs/tok | layouts/tok | recalcs per token (1–8) | layouts per token (1–8) | load1 START→END | disk GB START→END | swap MB START→END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|
| 1 | combined7 | paired6-ref-R5E-1 | 16:01:54 → 16:04:43 | 8/8 | 17.5 13.7 14.1 15.1 16.4 16.0 17.1 17.9 | 16.2 | 127.8 | 4677 | 4161 | 3334 4205 4491 4629 4548 4677 4657 4629 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 2.3 → 3.0 | 5.1 → 5.1 | 3603 → 3571 | no |
| 2 | R5E | paired6-1 | 16:04:45 → 16:07:05 | 8/8 | 18.1 14.2 14.6 15.3 15.6 17.2 16.7 17.8 | 16.2 | 129.6 | 4843 | 4504 | 3534 3995 4737 4740 4834 4843 4685 4771 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 2.8 → 3.1 | 5.1 → 5.1 | 3571 → 3555 | no |
| 3 | combined7 | paired6-ref-R5E-2 | 16:07:07 → 16:09:27 | 8/8 | 16.9 13.0 14.1 15.4 17.1 17.0 18.1 18.5 | 17.0 | 130.2 | 4775 | 4061 | 3664 3771 4454 4554 4624 4697 4622 4756 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 2.9 → 3.1 | 5.1 → 5.1 | 3555 → 3555 | no |
| 4 | R5E | paired6-2 | 16:09:30 → 16:11:50 | 8/8 | 18.3 14.0 14.5 15.5 15.7 17.0 17.0 18.2 | 16.3 | 130.2 | 4778 | 4487 | 3645 3737 4418 4588 4768 4722 4778 4557 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.1 → 3.5 | 5.1 → 5.1 | 3555 → 3547 | no |
| 5 | combined7 | paired6-ref-R5E-3 | 16:11:52 → 16:14:05 | 8/8 | 16.9 13.0 13.4 14.1 15.2 15.7 16.9 18.1 | 15.5 | 123.4 | 4993 | 4506 | 3639 4020 4309 4597 4993 4771 4907 4942 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.4 → 3.5 | 5.1 → 5.1 | 3547 → 3547 | no |
| 6 | R5E | paired6-3 | 16:14:07 → 16:16:25 | 8/8 | 16.8 13.2 13.9 15.7 15.7 16.9 17.1 18.1 | 16.3 | 127.5 | 4780 | 4482 | 3423 3992 4292 4420 4420 4464 4780 4664 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.5 → 3.6 | 5.1 → 5.1 | 3547 → 3531 | **yes** (load1=3.49 top=105.6:libexec/PerfPowerServices) |
Machine state [R5E]: median load1 across this candidate's 6 runs (START and END samples) = **3.1** (range 2.3–3.6); swap used median **3555 MB** (range 3531–3603); disk free 5.1–5.1 GB; 1 of 6 runs CONTENDED; runs 16:01–16:16.

### R5E — paired differences (candidate − the combined7 run immediately before it)

| pair k | ref run (median / total / RSS peak) | cand run (median / total / RSS peak) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ RSS peak MB | Δ RSS@tok8 MB | Δ recalcs/tok | Δ layouts/tok | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | paired6-ref-R5E-1 (16.2 / 127.8 / 4677) | paired6-1 (16.2 / 129.6 / 4843) | 2.9 min | yes | 3.1 | +0.0 | +1.8 | +166 | +343 | +0.0 | +0.0 | no/no |
| 2 | paired6-ref-R5E-2 (17.0 / 130.2 / 4775) | paired6-2 (16.3 / 130.2 / 4778) | 2.4 min | yes | 3.5 | -0.7 | +0.0 | +3 | +426 | +0.0 | +0.0 | no/no |
| 3 | paired6-ref-R5E-3 (15.5 / 123.4 / 4993) | paired6-3 (16.3 / 127.5 / 4780) | 2.2 min | yes | 3.6 (noisy) | +0.8 | +4.1 | -213 | -24 | +0.0 | +0.0 | no/yes |
| **mean [range] over valid pairs, n=3** | | | | | | **+0.0 [-0.7 … +0.8]** | **+2.0 [+0.0 … +4.1]** | **-15 [-213 … +166]** | +248 [-24 … +426] | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=1,2* | | | | | | *-0.3 [-0.7 … +0.0]* | *+0.9 [+0.0 … +1.8]* | *+84* | | | | |

combined7 reference drift over the valid pairs: medians 16.2 17.0 15.5 (range 1.5), adjacent-ref swings +0.8 -1.5; RSS peaks 4677 4775 4993 MB (range 316); recalcs/tok 435.8 435.8 435.8; layouts/tok 64.0 64.0 64.0; contended 0/3. combined7 for scale: 16.0 s/token (B5 paired vs combined4, 4 pairs, medians 16.0 15.9 16.3 16.0; RSS peak 5973 MB).

**R5E — NOT distinguishable from noise.** Paired Δ median = +0.0 s/token (range -0.7 … +0.8, n=3 valid pairs), Δ total = +2.0 s per 8 tokens (range +0.0 … +4.1); the pairs disagree in sign and the paired range includes zero, against a largest adjacent-ref swing of 1.5 s/token and a ref spread of 1.5 s/token over the 3 ref runs. **Memory: Δ RSS peak = -15 MB (range -213 … +166; mixed sign), Δ RSS@tok8 = +248 MB; candidate RSS peak 4843 MB vs ref 4993 MB (max over pairs).** Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). 1 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median -0.3 s/token [-0.7 … +0.0].

## R5M — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | RSS@tok8 MB | RSS/tok MB (1–8) | recalcs/tok | layouts/tok | recalcs per token (1–8) | layouts per token (1–8) | load1 START→END | disk GB START→END | swap MB START→END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|
| 1 | combined7 | paired6-ref-R5M-1 | 15:11:10 → 15:13:45 | 8/8 | 18.0 13.7 15.9 16.6 18.0 20.0 20.6 21.5 | 18.0 | 144.4 | 4017 | 3514 | 3022 3612 3953 3899 3586 3831 4017 3713 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 6.0 → 5.9 | 5.1 → 5.1 | 2869 → 2869 | no |
| 2 | R5M | paired6-1 | 15:13:47 → 15:16:23 | 8/8 | 17.8 13.7 14.9 15.8 18.7 21.1 20.5 23.0 | 18.2 | 145.4 | 4132 | 2699 | 3054 3688 4132 3948 3773 3295 3416 3603 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 5.6 → 6.6 | 5.1 → 4.9 | 2869 → 2845 | no |
| 3 | combined7 | paired6-ref-R5M-2 | 15:16:25 → 15:19:41 | 8/8 | 20.5 15.3 17.1 17.7 18.3 20.5 21.6 21.6 | 19.4 | 152.6 | 3946 | 2880 | 3453 3907 3801 3599 3828 3946 3667 3791 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 6.6 → 4.9 | 4.9 → 5.1 | 2845 → 2837 | **yes** (load1=6.59 top=91.5:/usr/libexec/duetexpertd) |
| 4 | R5M | paired6-2 | 15:19:43 → 15:22:15 | 8/8 | 17.8 14.0 15.1 15.8 16.5 19.9 19.3 23.5 | 17.2 | 142.0 | 4073 | 3754 | 2902 3360 3855 3902 3971 4073 3809 3754 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 4.7 → 5.4 | 5.1 → 5.1 | 2837 → 2837 | no |
| 5 | combined7 | paired6-ref-R5M-3 | 15:22:18 → 15:25:37 | 8/8 | 20.5 15.2 16.9 17.9 19.4 20.4 24.7 21.5 | 19.9 | 156.4 | 4302 | 4124 | 3449 3823 3686 3452 3500 3323 3495 4302 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 5.1 → 3.8 | 5.1 → 5.1 | 2837 → 2829 | no |
| 6 | R5M | paired6-3 | 15:25:39 → 15:28:00 | 8/8 | 19.5 15.2 15.4 14.9 16.0 16.4 16.6 16.6 | 16.2 | 130.4 | 4777 | 4162 | 3430 3415 4191 4773 4776 4777 4546 4612 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.8 → 4.3 | 5.1 → 5.1 | 2829 → 2829 | no |
Machine state [R5M]: median load1 across this candidate's 6 runs (START and END samples) = **5.3** (range 3.8–6.6); swap used median **2837 MB** (range 2829–2869); disk free 4.9–5.1 GB; 1 of 6 runs CONTENDED; runs 15:11–15:28.

### R5M — paired differences (candidate − the combined7 run immediately before it)

| pair k | ref run (median / total / RSS peak) | cand run (median / total / RSS peak) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ RSS peak MB | Δ RSS@tok8 MB | Δ recalcs/tok | Δ layouts/tok | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | paired6-ref-R5M-1 (18.0 / 144.4 / 4017) | paired6-1 (18.2 / 145.4 / 4132) | 2.6 min | yes | 6.6 | +0.2 | +1.0 | +115 | -815 | +0.0 | +0.0 | no/no |
| 2 | paired6-ref-R5M-2 (19.4 / 152.6 / 3946) | paired6-2 (17.2 / 142.0 / 4073) | 3.3 min | yes | 6.6 (noisy) | -2.2 | -10.6 | +127 | +874 | +0.0 | +0.0 | yes/no |
| 3 | paired6-ref-R5M-3 (19.9 / 156.4 / 4302) | paired6-3 (16.2 / 130.4 / 4777) | 3.4 min | yes | 5.1 | -3.7 | -26.0 | +475 | +38 | +0.0 | +0.0 | no/no |
| **mean [range] over valid pairs, n=3** | | | | | | **-1.9 [-3.7 … +0.2]** | **-11.9 [-26.0 … +1.0]** | **+239 [+115 … +475]** | +32 [-815 … +874] | +0.0 [+0.0 … +0.0] | +0.0 [+0.0 … +0.0] | |
| *clean-load subset (no CONTENDED, load1 < 10), n=2, k=1,3* | | | | | | *-1.8 [-3.7 … +0.2]* | *-12.5 [-26.0 … +1.0]* | *+295* | | | | |

combined7 reference drift over the valid pairs: medians 18.0 19.4 19.9 (range 1.9), adjacent-ref swings +1.4 +0.5; RSS peaks 4017 3946 4302 MB (range 356); recalcs/tok 435.8 435.8 435.8; layouts/tok 64.0 64.0 64.0; contended 1/3. combined7 for scale: 16.0 s/token (B5 paired vs combined4, 4 pairs, medians 16.0 15.9 16.3 16.0; RSS peak 5973 MB).

**R5M — NOT distinguishable from noise.** Paired Δ median = -1.9 s/token (range -3.7 … +0.2, n=3 valid pairs), Δ total = -11.9 s per 8 tokens (range -26.0 … +1.0); the pairs disagree in sign and the paired range includes zero, against a largest adjacent-ref swing of 1.4 s/token and a ref spread of 1.9 s/token over the 3 ref runs. **Memory: Δ RSS peak = +239 MB (range +115 … +475; same sign in all pairs), Δ RSS@tok8 = +32 MB; candidate RSS peak 4777 MB vs ref 4302 MB (max over pairs).** Pass counts move by +0.0 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). 1 of 3 pairs had a contended run. ids: 8/8; 8/8; 8/8. Clean-load subset (no CONTENDED, load1 < 10; n=2): Δ median -1.8 s/token [-3.7 … +0.2].

## combined8 — per-run

| # | bundle | label | start → end | ids | per-token s (1–8) | median s/tok | total s | RSS peak MB | RSS@tok8 MB | RSS/tok MB (1–8) | recalcs/tok | layouts/tok | recalcs per token (1–8) | layouts per token (1–8) | load1 START→END | disk GB START→END | swap MB START→END | contended |
|---:|---|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|
| 1 | combined7 | paired6-ref-combined8-1 | 17:14:39 → 17:17:01 | 8/8 | 18.7 14.3 14.9 15.2 16.3 16.2 18.3 18.1 | 16.3 | 132.0 | 5220 | 4941 | 3672 3890 4694 4906 5002 5220 4898 4969 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 5.1 → 3.8 | 4.9 → 4.9 | 3355 → 3331 | no |
| 2 | combined8 | paired6-1 | 17:17:03 → 17:19:15 | 8/8 | 16.5 12.6 13.7 14.9 15.5 16.1 16.4 16.9 | 15.8 | 122.5 | 5479 | 5456 | 3612 4173 4392 4844 5116 5113 5210 5456 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 3.8 → 4.7 | 4.9 → 4.9 | 3331 → 3331 | no |
| 3 | combined7 | paired6-ref-combined8-2 | 17:19:18 → 17:21:46 | 8/8 | 18.4 14.4 16.0 17.4 18.1 17.7 17.8 19.0 | 17.7 | 138.7 | 4670 | 3845 | 3657 4071 4043 4143 4232 4426 4670 4459 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 4.6 → 4.7 | 4.9 → 4.9 | 3331 → 3307 | no |
| 4 | combined8 | paired6-2 | 17:21:48 → 17:24:04 | 8/8 | 16.6 13.1 14.0 15.1 15.6 16.8 17.1 17.8 | 16.1 | 126.0 | 4774 | 4278 | 3454 4019 4463 4509 4560 4688 4774 4526 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 4.7 → 4.1 | 4.9 → 4.9 | 3307 → 3307 | no |
| 5 | combined7 | paired6-ref-combined8-3 | 17:24:07 → 17:26:28 | 8/8 | 17.0 13.7 14.7 15.3 16.9 17.0 18.7 19.0 | 17.0 | 132.3 | 4611 | 4367 | 3457 4030 4305 4597 4611 4370 4490 4517 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 4.0 → 3.2 | 4.9 → 4.9 | 3307 → 3307 | no |
| 6 | combined8 | paired6-3 | 17:26:31 → 17:29:15 | 8/8 | 17.1 13.1 13.5 14.1 15.4 16.0 16.8 16.8 | 15.7 | 122.8 | 4679 | 4373 | 3424 4055 4528 4574 4529 4533 4481 4535 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 3.2 → 3.6 | 4.9 → 4.9 | 3307 → 3307 | no |
| 7 | combined7 | paired6-ref-combined8-4 | 17:29:17 → 17:31:34 | 8/8 | 16.8 13.1 13.9 14.8 16.2 17.6 17.5 17.8 | 16.5 | 127.6 | 4581 | 3993 | 3214 3807 4581 4418 4477 4459 4383 4438 | 435.8 | 64.0 | 249 215 359 359 503 503 647 647 | 63 64 64 64 64 64 64 64 | 3.6 → 4.2 | 4.9 → 4.9 | 3307 → 3299 | no |
| 8 | combined8 | paired6-4 | 17:31:37 → 17:33:50 | 8/8 | 16.7 12.8 13.3 14.7 15.9 16.1 17.5 17.1 | 16.0 | 124.2 | 4648 | 4602 | 3539 3619 4350 4376 4221 4427 4611 4648 | 71.2 | 64.0 | 69 71 71 71 71 71 71 71 | 63 64 64 64 64 64 64 64 | 3.9 → 3.9 | 4.9 → 4.9 | 3299 → 3299 | no |
Machine state [combined8]: median load1 across this candidate's 8 runs (START and END samples) = **4.0** (range 3.2–5.1); swap used median **3307 MB** (range 3299–3355); disk free 4.9–4.9 GB; 0 of 8 runs CONTENDED; runs 17:14–17:33.

### combined8 — paired differences (candidate − the combined7 run immediately before it)

| pair k | ref run (median / total / RSS peak) | cand run (median / total / RSS peak) | ref→cand start gap | valid | max load1 | Δ median s/tok | Δ total s | Δ RSS peak MB | Δ RSS@tok8 MB | Δ recalcs/tok | Δ layouts/tok | contended (ref/cand) |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | paired6-ref-combined8-1 (16.3 / 132.0 / 5220) | paired6-1 (15.8 / 122.5 / 5479) | 2.4 min | yes | 5.1 | -0.5 | -9.5 | +259 | +515 | -364.6 | +0.0 | no/no |
| 2 | paired6-ref-combined8-2 (17.7 / 138.7 / 4670) | paired6-2 (16.1 / 126.0 / 4774) | 2.5 min | yes | 4.7 | -1.6 | -12.7 | +104 | +433 | -364.6 | +0.0 | no/no |
| 3 | paired6-ref-combined8-3 (17.0 / 132.3 / 4611) | paired6-3 (15.7 / 122.8 / 4679) | 2.4 min | yes | 4.0 | -1.3 | -9.5 | +68 | +6 | -364.6 | +0.0 | no/no |
| 4 | paired6-ref-combined8-4 (16.5 / 127.6 / 4581) | paired6-4 (16.0 / 124.2 / 4648) | 2.3 min | yes | 4.2 | -0.5 | -3.4 | +67 | +609 | -364.6 | +0.0 | no/no |
| **mean [range] over valid pairs, n=4** | | | | | | **-1.0 [-1.6 … -0.5]** | **-8.8 [-12.7 … -3.4]** | **+124 [+67 … +259]** | +391 [+6 … +609] | -364.6 [-364.6 … -364.6] | +0.0 [+0.0 … +0.0] | |

combined7 reference drift over the valid pairs: medians 16.3 17.7 17.0 16.5 (range 1.4), adjacent-ref swings +1.4 -0.7 -0.5; RSS peaks 5220 4670 4611 4581 MB (range 639); recalcs/tok 435.8 435.8 435.8 435.8; layouts/tok 64.0 64.0 64.0 64.0; contended 0/4. combined7 for scale: 16.0 s/token (B5 paired vs combined4, 4 pairs, medians 16.0 15.9 16.3 16.0; RSS peak 5973 MB).

**combined8 — probably real but within one adjacent-ref swing.** Paired Δ median = -1.0 s/token (range -1.6 … -0.5, n=4 valid pairs), Δ total = -8.8 s per 8 tokens (range -12.7 … -3.4); all 4 pairs have the same sign and the paired range excludes zero, against a largest adjacent-ref swing of 1.4 s/token and a ref spread of 1.4 s/token over the 4 ref runs. **Memory: Δ RSS peak = +124 MB (range +67 … +259; same sign in all pairs), Δ RSS@tok8 = +391 MB; candidate RSS peak 5479 MB vs ref 5220 MB (max over pairs).** Pass counts move by -364.6 recalcs/token and +0.0 layouts/token (deterministic per bundle, so any non-zero value is structural). 0 of 4 pairs had a contended run. ids: 8/8; 8/8; 8/8; 8/8.

