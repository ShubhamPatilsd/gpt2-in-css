## R5G pair `lowend-r2` — combined7 no-flag reference, then combined7 + flags (same CHROME.lock hold)

- flag arm launch args: js-flags=`--heap-growing-percent=10` extra=`--enable-low-end-device-mode`; ref arm: js-flags=`--heap-growing-percent=10` extra=`(none)`
- Chrome stderr flag warnings (flag arm): none; (ref arm): none
- vm_stat before ref: free=4314MB active=2695MB inactive=3342MB speculative=15MB wired_down=2460MB purgeable=2MB occupied_by_compressor=2931MB Swapins=64971MB Swapouts=101262MB  swap='total = 4096.00M used = 3299.69M free = 796.31M (encrypted
- vm_stat after ref: free=4771MB active=2081MB inactive=3593MB speculative=19MB wired_down=2468MB purgeable=2MB occupied_by_compressor=2824MB Swapins=64973MB Swapouts=101262MB  swap='total = 4096.00M used = 3299.69M free = 796.31M (encrypted
- vm_stat before flag: free=4070MB active=2851MB inactive=3638MB speculative=25MB wired_down=2406MB purgeable=14MB occupied_by_compressor=2768MB Swapins=64973MB Swapouts=101262MB  swap='total = 4096.00M used = 3299.69M free = 796.31M (encrypte
- vm_stat after flag: free=3814MB active=2879MB inactive=4339MB speculative=10MB wired_down=2446MB purgeable=4MB occupied_by_compressor=2270MB Swapins=65001MB Swapouts=101262MB  swap='total = 4096.00M used = 3267.69M free = 828.31M (encrypted

| arm | label | ids | per-token s (1–8) | median s/tok | total s | RSS idle MB | RSS max per token MB (1–8) | RSS@tok8 MB | RSS peak MB | RSS after MB | recalcs per token | layouts per token | style / layout / task s (CDP) | load ms | swap used MB START→END | footprint idle MB | footprint max per token MB (1–8, 5 s samples) | footprint peak MB | settled 10 s after token 8: RSS / footprint MB |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|---:|---|---:|---|---:|---|
| ref | lowend-r2-ref | 8/8 | 17.1 13.3 14.8 15.7 16.9 17.5 20.1 21.0 | 17.0 | 136.4 | 1682 | 3379 4070 4133 4294 4446 4174 4012 4100 | 3763 | 4446 | 3875 | 249 215 359 359 503 503 647 647 (Σ 3486) | 63 64 64 64 64 64 64 64 (Σ 512) | 57.0 / 43.8 / 137.1 | 2477 | 3299 → 3299 | None | 3305 3980 4370 5095 5380 5809 6383 6353 | 6383 | 3391 / 5868 |
| flag | lowend-r2-flag | 8/8 | 36.9 56.8 68.9 77.0 81.0 92.1 104.6 | 77.0 | 597.5 | 1647 | 2626 3065 3135 3119 3199 3334 3432 | None | 3463 | 3118 | 249 215 359 365 497 503 647 (Σ 3423) | 63 64 64 67 61 64 64 (Σ 504) | 393.3 / 171.2 / 600.8 | 2538 | 3299 → 3267 | None | 2117 2395 2717 2887 3024 3179 3426 | 3616 | 2847 / 3602 |

PAIR lowend-r2: Δ RSS peak -983 MB (4446 → 3463); Δ RSS@tok8 -3763 MB (3763 → None); Δ RSS per token -753 -1005 -998 -1175 -1247 -840 -580; Δ median +60.0 s/tok (17.0 → 77.0); Δ total +461.1 s (136.4 → 597.5); Δ per token +19.8 +43.5 +54.1 +61.3 +64.1 +74.6 +84.5; Δ style +336.3 s, Δ layout +127.4 s, Δ task +463.7 s; Δ load +61 ms (2477 → 2538); Δ footprint peak -2767 MB (6383 → 3616); Δ settled RSS -544 MB (3391 → 2847), Δ settled footprint -2266 MB (5868 → 3602); passes DIFFER (recalcs 3486 vs 3423, layouts 512 vs 504); ids ref 8/8 flag 8/8; contended ref '' flag ''

