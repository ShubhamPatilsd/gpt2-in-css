## R5G pair `o4s` — combined7 no-flag reference, then combined7 + flags (same CHROME.lock hold)

- flag arm launch args: js-flags=`--heap-growing-percent=10 --optimize-for-size` extra=`(none)`; ref arm: js-flags=`--heap-growing-percent=10` extra=`(none)`
- Chrome stderr flag warnings (flag arm): none; (ref arm): none
- vm_stat before ref: Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB  swap='total = 4096.00M used = 3531.81M free = 564.19M (encrypted)'
- vm_stat after ref: Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB  swap='total = 4096.00M used = 3531.81M free = 564.19M (encrypted)'
- vm_stat before flag: Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB  swap='total = 4096.00M used = 3531.81M free = 564.19M (encrypted)'
- vm_stat after flag: Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB Pages=0MB  swap='total = 4096.00M used = 3499.81M free = 596.19M (encrypted)'

| arm | label | ids | per-token s (1–8) | median s/tok | total s | RSS idle MB | RSS max per token MB (1–8) | RSS@tok8 MB | RSS peak MB | RSS after MB | recalcs per token | layouts per token | style / layout / task s (CDP) | load ms | swap used MB START→END | footprint idle MB | footprint max per token MB (1–8, 5 s samples) | footprint peak MB | settled 10 s after token 8: RSS / footprint MB |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|---:|---|---:|---|---:|---|
| ref | o4s-ref | 8/8 | 17.2 13.2 14.2 16.0 16.9 17.5 18.7 19.9 | 17.0 | 133.5 | 1681 | 3360 3763 4228 4531 4514 4570 4413 4452 | 3998 | 4598 | 4490 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 56.6 / 41.7 / 134.2 | 2470 | 3531 → 3531 | None | None None None None None None None None | None | None / None |
| flag | o4s-flag | 8/8 | 19.2 13.3 14.0 14.9 15.8 17.6 16.1 18.7 | 16.0 | 129.7 | 1840 | 3506 4139 4513 4673 4791 4494 5011 4860 | 4298 | 5011 | 4360 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 53.3 / 40.9 / 130.3 | 34618 | 3531 → 3499 | None | None None None None None None None None | None | None / None |

PAIR o4s: Δ RSS peak +413 MB (4598 → 5011); Δ RSS@tok8 +300 MB (3998 → 4298); Δ RSS per token +146 +376 +285 +142 +277 -76 +598 +408; Δ median -1.0 s/tok (17.0 → 16.0); Δ total -3.8 s (133.5 → 129.7); Δ per token +2.0 +0.1 -0.2 -1.1 -1.1 +0.1 -2.6 -1.2; Δ style -3.3 s, Δ layout -0.8 s, Δ task -3.9 s; Δ load +32148 ms (2470 → 34618); footprint: n/a (harness before 16:40); passes IDENTICAL (recalcs 3486 vs 3486, layouts 512 vs 512); ids ref 8/8 flag 8/8; contended ref 'load1=3.54 top=97.4:/usr/libexec/duetexpertd' flag ''

## R5G pair `lowend-r2-` — combined7 no-flag reference, then combined7 + flags (same CHROME.lock hold)

incomplete: ref=MISSING flag=MISSING

## R5G pair `memsaver` — combined7 no-flag reference, then combined7 + flags (same CHROME.lock hold)

- flag arm launch args: js-flags=`--heap-growing-percent=10 --memory-saver-mode` extra=`(none)`; ref arm: js-flags=`--heap-growing-percent=10` extra=`(none)`
- Chrome stderr flag warnings (flag arm): none; (ref arm): none
- vm_stat before ref: free=3158MB active=3512MB inactive=4372MB speculative=12MB wired_down=2446MB purgeable=4MB occupied_by_compressor=2258MB Swapins=65001MB Swapouts=101262MB  swap='total = 4096.00M used = 3267.69M free = 828.31M (encrypted
- vm_stat after ref: free=4804MB active=1642MB inactive=3771MB speculative=12MB wired_down=2458MB purgeable=1MB occupied_by_compressor=3074MB Swapins=65014MB Swapouts=101262MB  swap='total = 4096.00M used = 3251.69M free = 844.31M (encrypted
- vm_stat before flag: free=4116MB active=2338MB inactive=3819MB speculative=16MB wired_down=2441MB purgeable=1MB occupied_by_compressor=3028MB Swapins=65014MB Swapouts=101262MB  swap='total = 4096.00M used = 3251.69M free = 844.31M (encrypted
- vm_stat after flag: free=4800MB active=2297MB inactive=3216MB speculative=10MB wired_down=2453MB purgeable=1MB occupied_by_compressor=2984MB Swapins=65015MB Swapouts=101262MB  swap='total = 4096.00M used = 3251.69M free = 844.31M (encrypted

| arm | label | ids | per-token s (1–8) | median s/tok | total s | RSS idle MB | RSS max per token MB (1–8) | RSS@tok8 MB | RSS peak MB | RSS after MB | recalcs per token | layouts per token | style / layout / task s (CDP) | load ms | swap used MB START→END | footprint idle MB | footprint max per token MB (1–8, 5 s samples) | footprint peak MB | settled 10 s after token 8: RSS / footprint MB |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|---:|---|---:|---|---:|---|
| ref | memsaver-ref | 8/8 | 17.6 14.2 15.4 16.0 16.3 17.3 18.7 19.0 | 16.8 | 134.4 | 1695 | 3133 4079 4356 4383 4309 4477 4433 4404 | 3311 | 4477 | 3303 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 56.0 / 42.6 / 135.1 | 2349 | 3267 → 3251 | None | 3248 4250 4772 5061 5494 5850 5926 6152 | 6152 | 3761 / 4084 |
| flag | memsaver-flag | 8/8 | 17.4 13.8 16.0 15.8 16.8 17.5 19.4 21.8 | 17.1 | 138.6 | 1666 | 2961 4092 4142 4331 4393 4365 4301 4168 | 3600 | 4393 | 3574 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 58.2 / 42.6 / 139.2 | 2434 | 3251 → 3251 | None | 2974 3882 4029 4591 5462 5489 5948 6307 | 6307 | 3567 / 4082 |

PAIR memsaver: Δ RSS peak -84 MB (4477 → 4393); Δ RSS@tok8 +289 MB (3311 → 3600); Δ RSS per token -172 +13 -214 -52 +84 -112 -132 -236; Δ median +0.3 s/tok (16.8 → 17.1); Δ total +4.2 s (134.4 → 138.6); Δ per token -0.2 -0.4 +0.6 -0.2 +0.5 +0.2 +0.7 +2.8; Δ style +2.2 s, Δ layout -0.0 s, Δ task +4.1 s; Δ load +85 ms (2349 → 2434); Δ footprint peak +155 MB (6152 → 6307); Δ settled RSS -194 MB (3761 → 3567), Δ settled footprint -2 MB (4084 → 4082); passes IDENTICAL (recalcs 3486 vs 3486, layouts 512 vs 512); ids ref 8/8 flag 8/8; contended ref 'load1=6.82 top=46.8:Contents/MacOS/cua-driver' flag ''

## R5G pair `o4s-b` — combined7 no-flag reference, then combined7 + flags (same CHROME.lock hold)

- flag arm launch args: js-flags=`--heap-growing-percent=10 --optimize-for-size` extra=`(none)`; ref arm: js-flags=`--heap-growing-percent=10` extra=`(none)`
- Chrome stderr flag warnings (flag arm): none; (ref arm): none
- vm_stat before ref: free=3928MB active=3332MB inactive=3284MB speculative=19MB wired_down=2413MB purgeable=8MB occupied_by_compressor=2782MB Swapins=65015MB Swapouts=101262MB  swap='total = 4096.00M used = 3251.69M free = 844.31M (encrypted
- vm_stat after ref: free=4230MB active=2326MB inactive=3921MB speculative=13MB wired_down=2454MB purgeable=9MB occupied_by_compressor=2814MB Swapins=65035MB Swapouts=101262MB  swap='total = 4096.00M used = 3235.69M free = 860.31M (encrypted
- vm_stat before flag: free=3552MB active=2969MB inactive=3969MB speculative=17MB wired_down=2460MB purgeable=9MB occupied_by_compressor=2791MB Swapins=65035MB Swapouts=101262MB  swap='total = 4096.00M used = 3235.69M free = 860.31M (encrypted
- vm_stat after flag: free=4810MB active=1448MB inactive=3848MB speculative=13MB wired_down=2466MB purgeable=2MB occupied_by_compressor=3172MB Swapins=65036MB Swapouts=101262MB  swap='total = 4096.00M used = 3235.69M free = 860.31M (encrypted

| arm | label | ids | per-token s (1–8) | median s/tok | total s | RSS idle MB | RSS max per token MB (1–8) | RSS@tok8 MB | RSS peak MB | RSS after MB | recalcs per token | layouts per token | style / layout / task s (CDP) | load ms | swap used MB START→END | footprint idle MB | footprint max per token MB (1–8, 5 s samples) | footprint peak MB | settled 10 s after token 8: RSS / footprint MB |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|---:|---|---:|---|---:|---|
| ref | o4s-b-ref | 8/8 | 17.1 13.5 14.0 14.8 17.0 16.8 18.2 21.6 | 16.9 | 133.0 | 1684 | 3322 3858 4294 4513 4235 4186 4306 3669 | 3669 | 4513 | 2697 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 56.4 / 43.3 / 133.7 | 2523 | 3251 → 3235 | None | 3251 4216 4602 5130 5281 5609 5970 6256 | 6256 | 2772 / 3878 |
| flag | o4s-b-flag | 8/8 | 17.8 13.3 16.1 16.1 16.8 18.0 19.1 20.4 | 17.3 | 137.6 | 1828 | 3515 4134 4061 3910 3894 3943 3970 3898 | 3803 | 4134 | 3624 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 58.6 / 43.8 / 137.5 | 34260 | 3235 → 3235 | 1551 | 3034 3759 4380 4660 5333 5609 5753 6055 | 6055 | 3624 / 3998 |

PAIR o4s-b: Δ RSS peak -379 MB (4513 → 4134); Δ RSS@tok8 +134 MB (3669 → 3803); Δ RSS per token +193 +276 -233 -603 -341 -243 -336 +229; Δ median +0.4 s/tok (16.9 → 17.3); Δ total +4.6 s (133.0 → 137.6); Δ per token +0.7 -0.2 +2.1 +1.3 -0.2 +1.2 +0.9 -1.2; Δ style +2.2 s, Δ layout +0.5 s, Δ task +3.8 s; Δ load +31737 ms (2523 → 34260); Δ footprint peak -201 MB (6256 → 6055); Δ settled RSS +852 MB (2772 → 3624), Δ settled footprint +120 MB (3878 → 3998); passes IDENTICAL (recalcs 3486 vs 3486, layouts 512 vs 512); ids ref 8/8 flag 8/8; contended ref '' flag ''

