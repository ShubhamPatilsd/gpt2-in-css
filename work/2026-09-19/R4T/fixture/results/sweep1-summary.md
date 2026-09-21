# R4T fixture — 72 trials; medians over trials of per-frame medians (ms/frame); control frame (0 carriers) busy = 0.135 ms

| variant | N | ok | fps | frame dur | busy/frame | idle(metrics) | animate | ssa self | svc n | svc ms | UL self | ULT n:ms | layout n:ms | paintLC | prepaint+comp | passes(elems) | µs/carrier/frame (busy−ctrl) | RSS MB |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|
| ctrl-n0 | 0 | -/-/- | 60 | 0.13 | 0.14 | 0.10 | 0.02 | 0.00 | 1 | 0.01 | 0.01 | 1:0.05 | 0:0.00 | 0.01 | 0.01 | 1 | nan | 175 |
| base | 2000 | 3/3/3 | 60 | 6.17 | 6.25 | 4.51 | 3.98 | 2.70 | 4001 | 1.25 | 1.16 | 1:0.09 | 0:0.00 | 0.74 | 0.03 | 1 | 3.06 | 175 |
| n1000 | 1000 | 3/3/3 | 60 | 3.33 | 3.36 | 2.70 | 2.21 | 1.55 | 2001 | 0.61 | 0.58 | 1:0.08 | 0:0.00 | 0.38 | 0.02 | 1 | 3.22 | 174 |
| above20 | 2000 | 3/3/3 | 60 | 6.44 | 6.54 | 6.12 | 4.26 | 2.96 | 4001 | 1.25 | 1.21 | 1:0.10 | 0:0.00 | 0.77 | 0.03 | 1 | 3.20 | 173 |
| above40 | 2000 | 3/3/3 | 60 | 6.90 | 6.90 | 5.29 | 4.61 | 3.26 | 4001 | 1.32 | 1.31 | 1:0.09 | 0:0.00 | 0.75 | 0.03 | 1 | 3.38 | 175 |
| above60 | 2000 | 3/3/3 | 60 | 6.01 | 6.17 | 5.24 | 3.88 | 2.64 | 4001 | 1.24 | 1.15 | 1:0.09 | 0:0.00 | 0.74 | 0.03 | 1 | 3.02 | 175 |
| below5 | 2000 | 3/3/3 | 60 | 6.58 | 6.73 | 5.15 | 4.01 | 2.84 | 4001 | 1.18 | 1.39 | 1:0.09 | 0:0.00 | 0.87 | 0.03 | 1 | 3.30 | 173 |
| below20 | 2000 | 3/3/3 | 60 | 8.62 | 8.79 | 7.11 | 4.84 | 3.62 | 4001 | 1.24 | 2.25 | 1:0.08 | 0:0.00 | 1.26 | 0.03 | 1 | 4.33 | 175 |
| below40 | 2000 | 3/3/3 | 60 | 11.06 | 11.02 | 9.31 | 5.73 | 4.44 | 4001 | 1.23 | 3.06 | 1:0.09 | 0:0.00 | 1.77 | 0.03 | 1 | 5.44 | 174 |
| below60 | 2000 | 3/3/3 | 60 | 16.24 | 16.33 | 13.93 | 7.61 | 6.32 | 4001 | 1.36 | 5.40 | 1:0.09 | 0:0.00 | 2.77 | 0.04 | 1 | 8.10 | 174 |
| scr12 | 2000 | 3/3/3 | 60 | 6.11 | 6.35 | 5.16 | 3.79 | 2.60 | 4001 | 1.18 | 1.16 | 1:0.09 | 0:0.00 | 0.75 | 0.03 | 1 | 3.11 | 174 |
| scr96 | 2000 | 3/3/3 | 60 | 7.54 | 7.59 | 5.13 | 4.96 | 3.48 | 4001 | 1.37 | 1.44 | 1:0.10 | 0:0.00 | 0.81 | 0.03 | 1 | 3.73 | 175 |
| iblock | 2000 | 3/3/3 | 60 | 5.91 | 6.01 | 4.46 | 3.79 | 2.58 | 4001 | 1.23 | 1.08 | 1:0.08 | 0:0.00 | 0.70 | 0.03 | 1 | 2.94 | 174 |
| inline | 2000 | 3/3/3 | 60 | 6.24 | 6.42 | 4.78 | 3.86 | 2.66 | 4001 | 1.20 | 1.30 | 1:0.08 | 0:0.00 | 0.82 | 0.03 | 1 | 3.14 | 175 |
| scope-root | 2000 | 3/3/3 | 60 | 5.74 | 5.82 | 4.14 | 3.73 | 2.50 | 4001 | 1.18 | 1.10 | 1:0.08 | 0:0.00 | 0.73 | 0.03 | 1 | 2.84 | 175 |
| cons16 | 2000 | 3/3/3 | 60 | 5.57 | 5.68 | 4.15 | 3.51 | 2.37 | 4001 | 1.13 | 1.10 | 1:0.08 | 0:0.00 | 0.74 | 0.03 | 1 | 2.77 | 175 |
| heavy-a40 | 2000 | 3/3/3 | 60 | 5.73 | 5.86 | 4.22 | 3.73 | 2.45 | 4001 | 1.21 | 1.11 | 1:0.08 | 0:0.00 | 0.74 | 0.03 | 1 | 2.86 | 175 |
| bigdom100k | 2000 | 3/3/3 | 60 | 5.84 | 5.92 | 4.33 | 3.67 | 2.49 | 4001 | 1.18 | 1.14 | 1:0.08 | 0:0.00 | 0.73 | 0.03 | 1 | 2.89 | 174 |
| change50 | 2000 | 1/1/1 | 8 | 127.05 | 127.00 | 127.00 | 3.86 | 2.56 | 8002 | 2.80 | 2.20 | 2:23.34 | 1:1.10 | 95.09 | 1.11 | 2002 1 | 63.43 | 174 |
| demo | 2000 | 3/3/3 | 60 | 5.75 | 5.83 | 4.17 | 3.62 | 2.45 | 4001 | 1.15 | 1.10 | 1:0.08 | 0:0.00 | 0.75 | 0.03 | 1 | 2.85 | 175 |
| demo-contain | 2000 | 3/3/3 | 60 | 5.74 | 5.88 | 4.23 | 3.67 | 2.52 | 4001 | 1.17 | 1.15 | 1:0.08 | 0:0.00 | 0.76 | 0.03 | 1 | 2.87 | 175 |
| demo-cv | 2000 | 3/3/3 | 60 | 5.75 | 5.83 | 4.21 | 3.56 | 2.44 | 4001 | 1.17 | 1.12 | 1:0.08 | 0:0.00 | 0.76 | 0.03 | 1 | 2.85 | 175 |
| demo-below20 | 2000 | 3/3/3 | 60 | 8.69 | 9.13 | 6.83 | 4.95 | 3.68 | 4001 | 1.24 | 2.19 | 1:0.09 | 0:0.00 | 1.27 | 0.03 | 1 | 4.50 | 174 |
| demo-change50 | 2000 | 1/1/1 | 34 | 29.78 | 29.83 | 29.83 | 3.75 | 2.47 | 8002 | 2.72 | 1.96 | 2:11.76 | 1:0.64 | 10.78 | 0.81 | 1009 6 | 14.85 | 175 |

## Fits (busy ms/frame vs knob, N=2000)

- scroller depth (wrappers above): busy = 6.451 ms + 0.5 µs/frame per level (= 0.23 ns per carrier per level; R² 0.00)
- subject depth below scroller (wrappers between scroller and track): busy = 5.803 ms + 160.9 µs/frame per level (= 80.45 ns per carrier per level; R² 0.96)
- carriers: busy = 0.191 ms + 3.06 µs per carrier (control, n1000, base)
- n1000: 0.54× base busy/frame; animate 0.56×, UL self 0.50×, svc calls 2001
- above20: 1.05× base busy/frame; animate 1.07×, UL self 1.04×, svc calls 4001
- above40: 1.10× base busy/frame; animate 1.16×, UL self 1.13×, svc calls 4001
- above60: 0.99× base busy/frame; animate 0.97×, UL self 0.99×, svc calls 4001
- below5: 1.08× base busy/frame; animate 1.01×, UL self 1.20×, svc calls 4001
- below20: 1.41× base busy/frame; animate 1.21×, UL self 1.94×, svc calls 4001
- below40: 1.76× base busy/frame; animate 1.44×, UL self 2.64×, svc calls 4001
- below60: 2.61× base busy/frame; animate 1.91×, UL self 4.66×, svc calls 4001
- scr12: 1.02× base busy/frame; animate 0.95×, UL self 1.00×, svc calls 4001
- scr96: 1.21× base busy/frame; animate 1.24×, UL self 1.24×, svc calls 4001
- iblock: 0.96× base busy/frame; animate 0.95×, UL self 0.93×, svc calls 4001
- inline: 1.03× base busy/frame; animate 0.97×, UL self 1.12×, svc calls 4001
- scope-root: 0.93× base busy/frame; animate 0.94×, UL self 0.95×, svc calls 4001
- cons16: 0.91× base busy/frame; animate 0.88×, UL self 0.95×, svc calls 4001
- heavy-a40: 0.94× base busy/frame; animate 0.94×, UL self 0.96×, svc calls 4001
- bigdom100k: 0.95× base busy/frame; animate 0.92×, UL self 0.99×, svc calls 4001
- change50: 20.33× base busy/frame; animate 0.97×, UL self 1.90×, svc calls 8002
- demo: 0.93× base busy/frame; animate 0.91×, UL self 0.95×, svc calls 4001
- demo-contain: 0.94× base busy/frame; animate 0.92×, UL self 0.99×, svc calls 4001
- demo-cv: 0.93× base busy/frame; animate 0.89×, UL self 0.97×, svc calls 4001
- demo-below20: 1.46× base busy/frame; animate 1.24×, UL self 1.89×, svc calls 4001
- demo-change50: 4.77× base busy/frame; animate 0.94×, UL self 1.69×, svc calls 8002
