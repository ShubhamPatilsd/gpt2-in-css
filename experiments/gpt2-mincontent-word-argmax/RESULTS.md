# GPT-2 min-content word argmax

Decision: **reject / no-go**.

The one-text-node construction proves that `width:min-content` can return the widest break-separated candidate word and can react to hidden-vector mutations. It does not satisfy the complete production contract, and its cost scales worse than the equivalent element control.

## Correctness gate

The minimal page contains one 256-word text node, 255 ordinary U+0020 breakable spaces, no candidate elements inside the word run, no `<br>` nodes, and no runtime JavaScript. Each candidate uses the three retained shard-256 score glyphs plus a static identity glyph; U+2060 keeps the score sequence indivisible.

Across the synthetic all-tied vector and nine saved real hidden vectors:

- intrinsic element width equaled the maximum measured candidate-word width within one Chromium layout unit (0 or 1/64px);
- winner identity matched the direct 256-element control on all 10 vectors;
- mutations changed the winner, so the HVAR dependency remained live;
- the synthetic tie selected the lower token in both paths.

The stricter production encoding failed. Chrome treats the U+2060-joined sequence as one fallback cluster, so the separate static tie face is not selected inside the word. A score font's fallback glyph contributes instead. Winner identity still matched the control, but the modulo-width remainder did not decode the winning local token and the reconstructed score bucket did not match the control. The observed 1/64px element/range difference is therefore not proven safe at a bucket/tie boundary. This fails the required bucket, local tie, group, and final-token contract.

## Scaling curve

Chrome 153.0.8010.36, retained real score fonts, the same saved vector for cold layout, and a second saved vector for mutation. Each word point has one text node per 256-token group. Controls use 256 direct child elements per group. The first point includes initial font loading; later points share the browser cache.

| Groups | Word cold (ms) | Control cold (ms) | Cold ratio | Word mutation (ms) | Control mutation (ms) | Mutation ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,153.9 | 1,003.6 | 1.150x | 27.0 | 22.9 | 1.178x |
| 4 | 2,318.3 | 1,835.6 | 1.263x | 38.2 | 30.4 | 1.256x |
| 16 | 7,948.4 | 6,756.2 | 1.176x | 178.5 | 133.8 | 1.334x |
| 64 | 30,122.3 | 24,798.2 | 1.215x | 967.1 | 780.7 | 1.239x |

The word/min-content path is slower at every measured size. At 64 groups it is 21.5% slower cold and 23.9% slower on mutation. The increase is smooth and steep, supporting a scaling cost rather than an isolated small-page construction crash.

Raw measurements are in `scaling/browser-scaling-progress.json`.

## Full topology symptom

Topology A was emitted with 197 group word runs, 50,257 words, 150,771 score glyphs, 50,257 identity glyphs, 150,771 word joiners, 50,060 ordinary spaces, and a fan-in-16 outer maximum. Its HTML is 1,350,858 bytes.

The full Chrome attempt did not return from `document.fonts.ready` plus first layout after more than 180 seconds. At observation time there were no active network connections; Chrome and the renderer remained alive, the renderer was idle, the Playwright protocol call remained unresolved, no browser result JSON was produced, and Chrome emitted no renderer-crash message. A second full retry was intentionally not performed after the bounded scaling curve established the trend.

Topology B, one global 50,257-word run, was not built. A lower-token tie needs 50,257 distinct 1/64px ranks, a 785.265625px tie span, and therefore a score stride greater than that span. The required score/base geometry cannot remain below the observed 32,768px per-word clamp. It is not a safe production topology.

The retained shard-256 block-flow head remains the selected implementation. No GPT-2 architecture, weights, HVAR axis coordinates, or model data were changed.
