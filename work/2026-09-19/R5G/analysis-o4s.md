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

