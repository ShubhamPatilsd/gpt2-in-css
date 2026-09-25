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

