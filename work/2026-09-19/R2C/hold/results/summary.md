# R2E pause-and-hold fixture — 4 trials, pages [0, 1024]

## Per step (page n=1024): mutation main-thread ms, style recalcs, values, idle ms/frame

| step | class | in | mutate ms | recalcs | layouts | sample values | expected | match expected | match previous | distinct | idle ms/frame | frames in idle | pending adds (trace) |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|
| live0 | (live) | 0 | 5747.9 | 1802 | 0 | [-0.003072, 511.996, 1023] | [0, 512, 1023] | 86/86 | None/None | 1024 | 3.231 | 120 |  |
| live7 | (live) | 7 | 7105.0 | 1800 | 1 | [6.99984, 519.001, 1030] | [7, 519, 1030] | 91/91 | 0/0 | 1024 | 3.183 | 120 |  |
| paused | paused | 7 | 5804.4 | 1801 | 0 | [6.99984, 519.001, 1030] | [7, 519, 1030] | 91/91 | 91/91 | 1024 | 4.085 | 120 |  |
| paused-in13 | paused | 13 | 7393.8 | 1803 | 1 | [6.99984, 519.001, 1030] | [7, 519, 1030] | 91/91 | 91/91 | 1024 | 4.178 | 120 |  |
| pd-none | pd-none | 13 | 4987.5 | 1803 | 0 | [-2048, -2048, -2048] | [7, 519, 1030] | 0/0 | 0/0 | 1 | 2.266 | 120 |  |
| resume21 | (live) | 21 | 8474.5 | 1799 | 1 | [20.998, 533.002, 1044] | [21, 533, 1044] | 101/101 | 0/0 | 1024 | 4.126 | 120 |  |
| paused2 | paused | 21 | 7567.3 | 1802 | 0 | [20.998, 533.002, 1044] | [21, 533, 1044] | 101/101 | 101/101 | 1024 | 4.366 | 120 |  |
| pd-display | pd-display | 21 | 4701.8 | 1804 | 1 | [-2048, -2048, -2048] | [21, 533, 1044] | 0/0 | 0/0 | 1 | 2.524 | 120 |  |
| resume33 | (live) | 33 | 8007.5 | 1796 | 1 | [33.0006, 544.996, 1056] | [33, 545, 1056] | 112/112 | 0/0 | 1024 | 4.032 | 120 |  |
| paused3 | paused | 33 | 7686.6 | 1802 | 0 | [33.0006, 544.996, 1056] | [33, 545, 1056] | 112/112 | 112/112 | 1024 | 4.293 | 120 |  |
| pd-cv | pd-cv | 33 | 7551.6 | 1802 | 1 | [33.0006, 544.996, 1056] | [33, 545, 1056] | 112/112 | 112/112 | 1024 | 4.472 | 120 |  |
| resume45 | (live) | 45 | 7938.2 | 1798 | 1 | [45.0033, 557.001, 1068] | [45, 557, 1068] | 123/123 | 0/0 | 1024 | 3.956 | 120 |  |
| d-none | d-none | 45 | 4646.7 | 1802 | 0 | [1.79769e+308, 1.79769e+308, 1.79769e+308] | None | None/None | 0/0 | 1 | 2.609 | 120 |  |
| resume57 | (live) | 57 | 8275.8 | 1798 | 1 | [56.9965, 569.004, 1080] | [57, 569, 1080] | 131/131 | 0/0 | 1024 | 4.231 | 120 |  |
| d-display | d-display | 57 | 5071.6 | 1802 | 1 | [1.79769e+308, 1.79769e+308, 1.79769e+308] | None | None/None | 0/0 | 1 | 2.809 | 120 |  |
| resume69 | (live) | 69 | 8317.8 | 1800 | 1 | [68.9985, 580.996, 1091.99] | [69, 581, 1092] | 140/140 | 0/0 | 1024 | 4.112 | 120 |  |

## Idle per-frame cost, page n=0 (no carriers), by step

| step | idle ms/frame | frames |
|---|---:|---:|
| live0 | 0.294 | 120 |
| live7 | 0.228 | 120 |
| paused | 0.257 | 120 |
| paused-in13 | 0.234 | 120 |
| pd-none | 0.263 | 120 |
| resume21 | 0.219 | 121 |
| paused2 | 0.227 | 120 |
| pd-display | 0.257 | 120 |
| resume33 | 0.222 | 120 |
| paused3 | 0.249 | 120 |
| pd-cv | 0.254 | 120 |
| resume45 | 0.234 | 120 |
| d-none | 0.266 | 120 |
| resume57 | 0.233 | 121 |
| d-display | 0.247 | 120 |
| resume69 | 0.228 | 120 |

## Fitted constants (µs per carrier per frame; base frame with 0 carriers = 0.241 ms)

| state | ms/frame (n=1024) | µs per carrier per frame |
|---|---:|---:|
| live (timeline + running animation) | 4.032 | 3.70 |
| paused, timeline attached | 4.236 | 3.90 |
| paused + view-timeline:none | 2.266 | 1.98 |
| paused + scroller display:none | 2.524 | 2.23 |
| paused + scroller content-visibility:hidden | 4.472 | 4.13 |
| detached (view-timeline:none), not paused | 2.609 | 2.31 |
| display:none, not paused | 2.809 | 2.51 |

## Cycle costs (main-thread ms for the whole mutation until quiescent, n=1024)

ordinary input change while live: 7105.0 ms (6938.4 µs/carrier)
pause (attached): 7567.3 ms (7390.0 µs/carrier)
detach after pause [pd-none]: 4987.5 ms (4870.6 µs/carrier)
detach after pause [pd-display]: 4701.8 ms (4591.6 µs/carrier)
detach after pause [pd-cv]: 7551.6 ms (7374.6 µs/carrier)
resume+re-attach [resume21]: 8474.5 ms (8275.9 µs/carrier; extra over ordinary change 1337.4 µs)
resume+re-attach [resume33]: 8007.5 ms (7819.8 µs/carrier; extra over ordinary change 881.3 µs)
resume+re-attach [resume45]: 7938.2 ms (7752.2 µs/carrier; extra over ordinary change 813.7 µs)
resume+re-attach [resume57]: 8275.8 ms (8081.8 µs/carrier; extra over ordinary change 1143.4 µs)
resume+re-attach [resume69]: 8317.8 ms (8122.9 µs/carrier; extra over ordinary change 1184.4 µs)

full off/on cycle per carrier (pause + detach + resume-extra): 13404.0 µs; per-frame saving live -> paused-detached: 1.72 µs/frame
break-even frames off per cycle: 7771.3
demo compute (off 1 frame/layer): saving 0.16 s/token, toggling cost 1251.71 s/token, net +1251.55 s/token
demo compute (per-hop, avg off 3 frames/layer): saving 0.48 s/token, toggling cost 1251.71 s/token, net +1251.23 s/token
demo token-level carriers: saving 0.21 s/token, toggling cost 21.04 s/token, net +20.83 s/token
