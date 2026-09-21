Same synthetic font for all arms (`r4x-score.ttf`: 16 axes `X000–X015` in [−1, 1], 32 HVAR regions, glyph `0` advance =
1500 + Σ cⱼ·xⱼ units, cⱼ ∈ [−30, 30]); 12 "heads" × 8 "slots" = 96 producers, each with its own
`font-variation-settings: "X00j" calc(var(--q-h-j) × K[s][j])` (one distinct font instance per producer, exactly as the
emitter's 96 `FvsDot` carriers); 16 pre-baked input sets `html.go-k{--q-h-j}`; one CDP class mutation on `<html>`
changes all 192 inputs; F3's `proto_run.mjs` (M1 pattern: JS off, fresh context, 1 warm-up, traced mutation, quiescence,
`CSS.getComputedStyleForNode` verification of all 96 numbers against NumPy). 3 trials each, AC, `caffeinate`.

| arm | structure (per layer today ⇔ fixture) | `UpdateLayoutTree` (elements) | `Layout` | frames (`Commit`) | busy ms | style ms | layout ms | exact / within 1e-3 | max abs err (units) |
|---|---|---|---|---:|---:|---:|---:|---|---:|
| **T** view-timeline (today) | 96 `position:absolute` `.metric` carriers in one 65,536 px `.scroller>.track`, `view-timeline` each, one `#reader` with 96 animations, emitter decode `(65536/p − 65536)/0.512` | «T-ult» | «T-layout» | **«T-commit»** | «T-busy» | «T-style» | «T-layoutms» | «T-exact» | «T-err» |
| **M** `1ch` metric | 12 chains × 8 nested empty `display:block` elements, each `font:512px R4XScore` + its FVS + `--fs-h-s: calc(1ch / 1px / 0.512)` (registered, inherited), read on the chain bottom | «M-ult» | **«M-layout»** | **«M-commit»** | «M-busy» | «M-style» | «M-layoutms» | «M-exact» | «M-err» |
| **C** anchor → fixed container chain (F3) | 96 in-flow `anchor-name` carriers; per head 4 nested `position:fixed; container-type:size` boxes (`width/height: anchor-size()`), child declares 2 numbers from `100cqw/100cqh` | 1 (123) | 1 | **1** | 17.5–18.0 | 1.6–1.9 | 14.1–14.6 | 0 / **96/96** | 0.034–0.036 (= 1/64 px ÷ 0.512) |

«fixture-reading»
