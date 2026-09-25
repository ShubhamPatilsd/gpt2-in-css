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

