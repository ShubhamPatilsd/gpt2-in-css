# GSUB-certified hybrid fallback-gating ablation

Chrome **153.0.8010.36** (/Applications/Google Chrome.app/Contents/MacOS/Google Chrome), headless on darwin 25.0.0 (arm64), using `http://127.0.0.1:4178`. Each accepted bank/variant cell has 7 in-page measured rounds after 2 warmups (70 samples): all 10 reference cases, reversed on odd rounds and rotated every round. Target order also reverses and rotates.

The current conditional `display:none/grid` gate is compared with exact-stage `content-visibility:hidden/visible` plus `contain-intrinsic-size:auto 1px`, and with a low-risk `visibility:hidden/visible` control. Both alternatives keep the exact stage `display:grid`. Each variant stylesheet is injected once before timing; routing and winner selection remain CSS-only.

Correctness: **60/60 final-winner, route, and computed-gate checks passed** against the separate exact CSS page. The case mix is adversarial (3 accept, 7 fallback), not the full-screen distribution.

## Accept/fallback medians

| Bank | Target | Overall | Accept | Fallback |
| --- | --- | ---: | ---: | ---: |
| bounded | Exact baseline | 235.35 ms | 236.50 ms | 233.90 ms |
| bounded | Current conditional display:none/grid | 289.75 ms | 45.10 ms | 473.50 ms |
| bounded | Conditional content-visibility:hidden/visible; stage stays grid | 289.20 ms | 42.20 ms | 457.50 ms |
| bounded | Conditional visibility:hidden/visible; stage stays grid | 475.10 ms | 449.90 ms | 478.20 ms |
| full | Exact baseline | 232.15 ms | 233.40 ms | 230.80 ms |
| full | Current conditional display:none/grid | 287.35 ms | 45.20 ms | 463.00 ms |
| full | Conditional content-visibility:hidden/visible; stage stays grid | 289.45 ms | 44.90 ms | 464.00 ms |
| full | Conditional visibility:hidden/visible; stage stays grid | 483.60 ms | 491.90 ms | 480.40 ms |

## Four transition medians

| Bank | Variant | Transition | Samples | Median |
| --- | --- | --- | ---: | ---: |
| bounded | Current conditional display:none/grid | accept->accept | 8 | 40.55 ms |
| bounded | Current conditional display:none/grid | accept->fallback | 14 | 479.65 ms |
| bounded | Current conditional display:none/grid | fallback->accept | 13 | 249.80 ms |
| bounded | Current conditional display:none/grid | fallback->fallback | 35 | 468.50 ms |
| bounded | Conditional content-visibility:hidden/visible; stage stays grid | accept->accept | 8 | 39.05 ms |
| bounded | Conditional content-visibility:hidden/visible; stage stays grid | accept->fallback | 14 | 470.90 ms |
| bounded | Conditional content-visibility:hidden/visible; stage stays grid | fallback->accept | 13 | 239.10 ms |
| bounded | Conditional content-visibility:hidden/visible; stage stays grid | fallback->fallback | 35 | 453.70 ms |
| bounded | Conditional visibility:hidden/visible; stage stays grid | accept->accept | 8 | 474.55 ms |
| bounded | Conditional visibility:hidden/visible; stage stays grid | accept->fallback | 14 | 489.05 ms |
| bounded | Conditional visibility:hidden/visible; stage stays grid | fallback->accept | 13 | 449.90 ms |
| bounded | Conditional visibility:hidden/visible; stage stays grid | fallback->fallback | 35 | 472.30 ms |
| full | Current conditional display:none/grid | accept->accept | 8 | 35.55 ms |
| full | Current conditional display:none/grid | accept->fallback | 14 | 462.60 ms |
| full | Current conditional display:none/grid | fallback->accept | 13 | 249.80 ms |
| full | Current conditional display:none/grid | fallback->fallback | 35 | 463.00 ms |
| full | Conditional content-visibility:hidden/visible; stage stays grid | accept->accept | 8 | 35.60 ms |
| full | Conditional content-visibility:hidden/visible; stage stays grid | accept->fallback | 14 | 477.25 ms |
| full | Conditional content-visibility:hidden/visible; stage stays grid | fallback->accept | 13 | 250.50 ms |
| full | Conditional content-visibility:hidden/visible; stage stays grid | fallback->fallback | 35 | 463.70 ms |
| full | Conditional visibility:hidden/visible; stage stays grid | accept->accept | 8 | 514.60 ms |
| full | Conditional visibility:hidden/visible; stage stays grid | accept->fallback | 14 | 485.65 ms |
| full | Conditional visibility:hidden/visible; stage stays grid | fallback->accept | 13 | 487.80 ms |
| full | Conditional visibility:hidden/visible; stage stays grid | fallback->fallback | 35 | 479.30 ms |

The clock starts before the first of 768 input writes and ends after score-offset/group writes and the forced final geometry read. Route lookup and transition bookkeeping occur after the clock. Page load, font readiness, CSS injection, checks, warmups, and automation round trips are excluded.

## Full-screen 11.47%-fallback transition projection

This weights the four measured transition medians by independent consecutive routes using P(accept)=1,744/1,970=88.53% and P(fallback)=226/1,970=11.47%. It is a projection, not a direct 1,970-case run.

| Bank | Variant | Projected transition-weighted time | Exact median | Speedup vs exact |
| --- | --- | ---: | ---: | ---: |
| bounded | Current conditional display:none/grid | 112.03 ms | 235.35 ms | 2.10× |
| bounded | Conditional content-visibility:hidden/visible; stage stays grid | 108.68 ms | 235.35 ms | 2.17× |
| bounded | Conditional visibility:hidden/visible; stage stays grid | 473.49 ms | 235.35 ms | 0.50× |
| full | Current conditional display:none/grid | 106.31 ms | 232.15 ms | 2.18× |
| full | Conditional content-visibility:hidden/visible; stage stays grid | 107.91 ms | 232.15 ms | 2.15× |
| full | Conditional visibility:hidden/visible; stage stays grid | 508.47 ms | 232.15 ms | 0.46× |

On the full bank, fallback→accept is 249.80 ms for the current gate and 250.50 ms for content visibility. The full-bank projections are 106.31 ms current, 107.91 ms content visibility, and 508.47 ms visibility; the lowest is **Current conditional display:none/grid**.

## Rejections

No variant was rejected: all three syntaxes were supported, their computed gate states followed the CSS route, and all final winners matched the exact page.

## Scope

The bounded and full production hybrid pages and their existing 10 cases are reused unchanged. This ablation changes only one-time injected exact-stage presentation CSS. It does not alter the CSS fallback predicate, top/runner routing, final winner mux, page sources, or certification claim.
