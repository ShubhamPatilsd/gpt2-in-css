# pass census — /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5E/runs/smoke-R5E-2L-ref

80 UpdateLayoutTree, 52 Layout, 65545 StyleRecalcInvalidationTracking events (0 outside any pass/layout, 0 inside Layout = interleaved container recalcs)

## Recurring pass sizes and their populations (elementCount: passes, mean ms; population of one representative pass, tracked elements by class)

- **3141** elements × 8 passes, 2577 ms total (322.1 ms/pass); tracked 769: .shared-attn-cN 768, .shared-attn-receipt 1; reasons: {'ScrollTimeline': 769}
- **50898** elements × 3 passes, 1456 ms total (485.2 ms/pass); tracked 769: .bN-bridge-cN 768, .bN-bridge-receipt 1; reasons: {'ScrollTimeline': 769}
- **824** elements × 8 passes, 923 ms total (115.3 ms/pass); tracked 3073: .shared-fc-cN 3072, .shared-fc-receipt 1; reasons: {'ScrollTimeline': 3073}
- **800** elements × 8 passes, 738 ms total (92.2 ms/pass); tracked 769: .cache-bridge-cN 768, .cache-bridge-receipt 1; reasons: {'ScrollTimeline': 769}
- **153** elements × 7 passes, 560 ms total (79.9 ms/pass); tracked 2305: .shared-qkv-cN 2303, .shared-qkv-receipt 1, .shared-proj-receipt 1; reasons: {'ScrollTimeline': 2305}
- **2366** elements × 4 passes, 267 ms total (66.9 ms/pass); tracked 770: .loop-reader-cN 768, .shared-proj-receipt 1, .core-pass-reader 1; reasons: {'ScrollTimeline': 770}
- **2405** elements × 2 passes, 230 ms total (114.9 ms/pass); tracked 1537: .bN-bridge-cN 768, .embedding-consumer-N 767, .embedding-receipt 1, .bN-bridge-receipt 1; reasons: {'ScrollTimeline': 1537}
- **0** elements × 20 passes, 218 ms total (10.9 ms/pass); tracked 0: ; reasons: {}
- **895** elements × 2 passes, 122 ms total (61.1 ms/pass); tracked 35: .token-slot-N 8, #token-N-ready 8, #token-N-ack 8, body 1, .done 1, select 1, .status 1, #run-start 1, .feedback-reader 1, .visible-output 1, .core-controller 1, .core-block 1, #eos-ready 1, #capture-epoch-observer 1; reasons: {'Related style rule': 34, 'Affected by :has()': 1}
- **2393** elements × 1 passes, 108 ms total (107.9 ms/pass); tracked 770: .bN-bridge-cN 768, .embedding-receipt 1, .bN-bridge-receipt 1; reasons: {'ScrollTimeline': 770}
- **791** elements × 4 passes, 102 ms total (25.5 ms/pass); tracked 770: .loop-reader-cN 768, .shared-proj-receipt 1, .core-pass-reader 1; reasons: {'ScrollTimeline': 770}
- **1** elements × 6 passes, 67 ms total (11.1 ms/pass); tracked 1: #token-N-ready 1; reasons: {'Animation': 1}
- **113** elements × 1 passes, 53 ms total (53.4 ms/pass); tracked 35: .token-slot-N 8, #token-N-ready 8, #token-N-ack 8, body 1, .done 1, select 1, .status 1, #run-start 1, .feedback-reader 1, .visible-output 1, .core-controller 1, .core-block 1, #eos-ready 1, #capture-epoch-observer 1; reasons: {'Related style rule': 34, 'Affected by :has()': 1}
- **39** elements × 3 passes, 48 ms total (16.0 ms/pass); tracked 35: .token-slot-N 8, #token-N-ready 8, #token-N-ack 8, body 1, .done 1, select 1, .status 1, #run-start 1, .feedback-reader 1, .visible-output 1, .core-controller 1, .core-block 1, #eos-ready 1, #capture-epoch-observer 1; reasons: {'Related style rule': 34, 'Affected by :has()': 1}
- **6** elements × 3 passes, 36 ms total (12.1 ms/pass); tracked 1: .feedback-reader 1; reasons: {'ScrollTimeline': 1}

## Interleaved recalcs inside Layout events (container queries): classes restyled

0 Layout events contain restyles; total tracked 0: 

## Restyles per token by class (UpdateLayoutTree passes only)

| class | tok 1 | tok 2 | tok 3 |
|---|---:|---:|---:|
| `.shared-fc-cN` | 12288 | 6144 | 6144 |
| `.shared-qkv-cN` | 6911 | 4608 | 4608 |
| `.shared-attn-cN` | 3072 | 1536 | 1536 |
| `.loop-reader-cN` | 3072 | 1536 | 1536 |
| `.cache-bridge-cN` | 3071 | 1534 | 1535 |
| `.bN-bridge-cN` | 2304 | 768 | 1536 |
| `.embedding-consumer-N` | 767 | 764 | 0 |
| `#token-N-ready` | 17 | 17 | 17 |
| `#token-N-ack` | 17 | 17 | 17 |
| `.token-slot-N` | 16 | 16 | 16 |
| `.feedback-reader` | 4 | 2 | 3 |
| `.cache-bridge-receipt` | 4 | 2 | 2 |
| `.shared-attn-receipt` | 4 | 2 | 2 |
| `.shared-fc-receipt` | 4 | 2 | 2 |
| `.core-pass-reader` | 4 | 2 | 2 |
| `.shared-proj-receipt` | 4 | 2 | 2 |
| `.shared-qkv-receipt` | 3 | 2 | 2 |
| `.bN-bridge-receipt` | 3 | 1 | 2 |
| `body` | 2 | 2 | 2 |
| `.done` | 2 | 2 | 2 |
| `select` | 2 | 2 | 2 |
| `.status` | 2 | 2 | 2 |
| `#run-start` | 2 | 2 | 2 |
| `.visible-output` | 2 | 2 | 2 |
| `.core-controller` | 2 | 2 | 2 |
| `.core-block` | 2 | 2 | 2 |
| `#eos-ready` | 2 | 2 | 2 |
| `#capture-epoch-observer` | 2 | 2 | 2 |
| `.embedding-receipt` | 1 | 1 | 1 |
