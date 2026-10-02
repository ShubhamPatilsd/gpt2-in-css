# R7T scratch — trace evidence (time8-t1 = combined7, token 7, pressured 20.8 s; clean combined8 ≈ 15.3–16 s, scale ≈ 0.75)

Per-frame classes (median ms; 35 frames = 12 x 2.5 hop frames + head + token start + 3 handshake):
| frame (pass ecs) | n | dur | animate | UL self | paintLC self | CI | prepaint | style | layout | shaping |
| 163+800 (qkv readback/KV/scores/softmax/V | ctx->attn) | 6 | 553 | 38 | 23 | 34 | 11 | 4 | 192 | 251 (351-dirty V/R4S layout 227) | 22 |
| 3141+824 (fc WRITE | fc readback->proj write) | 6 | 571 | 40 | 28 | 38 | 46 | 5 | 279 | 137 (9380:63 fc, 2471:70 proj) | 60 |
| 2366+163 (loop/LN1->qkv write | ...) | 6 | 636 | 39 | 27 | 35 | 25 | 6 | 230 | 280 | 36 |
| 800+3141 (ctx->attn | fc write) | 6 | 379 | 39 | 21 | 26 | 23 | 4 | 178 | 87 | 38 |
| 824+2366 | 5 | 459 | 43 | 22 | 36 | 13 | 3 | 221 | 117 | 51 |
| 824+791 (layer-11 export) | 1 | 324 | 44 | 22 | 27 | 0 | 1 | 157 | 73 | 28 |
| 50898+6 (HEAD) | 1 | 2744 | 37 | 18 | 23 | 915 | 31 | 441 | 1279 | 950 |
| 1 / 39 / 1 (token SMIL handshake) | 3 | 65/91/65 | 28-34 | 15-18 | 15-16 | 0 | 1 | 0-17 | 0-11 | 0 |
| 895+2405 (token start: embedding -> S1) | 1 | 439 | 32 | 23 | 21 | 14 | 4 | 211 | 135 | 94 |

Pass means (Document::recalcStyle self): 163-el 131 ms (+46 GC), 3141-el 121 ms, 824-el 114 ms, 2366-el 68 ms, 800-el 26 ms, head 392 ms, 2405-el 98, 895-el 64.
Incremental-marking slices per pass (allocation proxy, ~40 KB each): 3141: 265, 824: 239, 163: 186, 2366: 133, 800: 50, head 1438; layout phase 6,000/token.
Layout classes: 351-dirty (R4S chain+V, combined7 only) 12 x 227 = 2.7 s; head 101,181 dirty 1,279 ms; proj 2,471 dirty 12 x 70 = 0.85 s (91 us/carrier, 12 glyph runs); fc 9,380 dirty 12 x 63 = 0.77 s (20 us/carrier, 3 runs); qkv 6,995 dirty 11 x 49 = 0.56 s (21 us); attn 2,416 dirty 12 x 25 = 0.30 s (33 us).
Shaping: 199,452 ShapeText calls = 2,278 ms/token; head 50,520 calls 950 ms (19 us); carriers 3.2 us/run (1 glyph, 256-axis instance).
GC: style 965 + layout 1,172 = 2.1 s (2 x ENSURE_SWEEPING_COMPLETED 555 + 810; incremental embedder tracing 325 + 242; 18k slices).
Fixed per frame: animate 38-44 (serviceScriptedAnimations self 24 + 9.3k serviceAnimations 13-17) + UL self 21-28 = 60-70 ms/frame = 6.5-7 us per live timeline/frame (R4T fixture 3.06, R3A R2F 5.5) -> 2.2 s/token at 35 frames.
paintLC self 26-43 ms/frame (pending updates of changed carriers, R4T 14.1 us + 45.8 ns x 64).
CI (ink overflow) in fc frames 45-49 ms for 3,840 changed carriers (12 us each, 3-12 glyphs); head 915 ms = 301k glyph bounds.
