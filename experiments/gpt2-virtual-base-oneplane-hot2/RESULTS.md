# Virtual-base one-plane hot-2 exact rows

Decision: **reject-transport**.

The retained hot-2 topology is unchanged. Each of its 512 exact hot rows uses six direct-int16 score glyphs instead of twelve high/residual glyphs. Always-on HVAR regions raise each glyph's effective base enough to keep its full signed-axis domain nonnegative.

- Browser route identity versus the retained two-plane implementation: 1/2 fixtures.
- Glyphs per hot row: 6 versus 12 (50% fewer).
- One-plane hot fonts: 909,368 bytes across 6 files.
- Maximum extra bias axes per font: 11.

The decisive mismatch is fixture 1, group 1: the one-plane row decodes bucket
12,621 while the live retained two-plane shadow decodes 12,620 for the same
token 477. That one-bucket shift also changes the next-upper and certificate-gap
values by one. The final token happens to remain 477, but the established
browser-realized bucket contract is no longer identical, so this is a transport
failure rather than an exact replacement.

| Metric | One plane | Retained two plane |
| --- | ---: | ---: |
| warm mean (2 samples) | 3762.7 ms | 3267.2 ms |
| warm median | 3883.7 ms | 3861.3 ms |
| warm p90 | 3883.7 ms | 3861.3 ms |

Mean ratio: **1.152x** (-15.2% slower). Chrome: 153.0.8010.36.

Timing is only a two-fixture falsification screen; no longer robust timing run
was justified after the exact bucket mismatch. It is directionally unfavorable
despite halving glyph count, likely because each font adds 10-11 always-active
bias axes/regions and a very large effective base.

Full stage observations, cold loads, and request failures are in `browser-results.json`.

## Reproduce

```sh
uv run --with numpy --with safetensors --with fonttools --with pillow --with brotli \
  python tools/build_virtual_base_oneplane_hot2_probe.py
python3 -m http.server 4189 --bind 127.0.0.1
ONEPLANE_ROUNDS=1 ONEPLANE_FIXTURE_LIMIT=2 \
  node tools/test_virtual_base_oneplane_hot2_probe.mjs
```
