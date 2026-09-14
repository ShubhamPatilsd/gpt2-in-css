# Screen-compensated one-plane hot-2 rows

Decision: **reject-transport**.

The retained hot-2 topology is unchanged. Each exact hot row uses six unbiased direct-int16 score glyphs followed by two fixed compensator glyphs in the same inline run. The compensator covers all 1,024 browser-realized corpus states and ten fixtures.

- Browser route identity versus the retained two-plane implementation: 0/2 fixtures.
- Glyphs per hot row: 8 versus 12 (33.3% fewer).
- One-plane hot fonts: 868,480 bytes across 6 files.


| Metric | One plane | Retained two plane |
| --- | ---: | ---: |
| warm mean (2 samples) | 3016.6 ms | 3882.1 ms |
| warm median | 4035.7 ms | 4106.6 ms |
| warm p90 | 4035.7 ms | 4106.6 ms |

Mean ratio: **0.777x** (22.3% faster). Chrome: 153.0.8010.36.

This is a decisive semantic failure, not a near-boundary rounding miss. The
45,121-unit compensator is large enough offline, but it lives in the sixth font
fallback run. Negative advances in the preceding five runs do not subtract from
that later run's layout width. Fixture 0 changes from token 11 / bucket 4,946 to
token 13 / bucket 13,086; fixture 1 changes from token 477 / bucket 12,620 to
token 391 / bucket 43,572. Compensation must be inside each font-shaped run,
which would require at least one compensator per shard and return to twelve
glyphs.

The 0.777x timing ratio is only a two-fixture falsification screen. It confirms
that removing bias regions can be fast, but it cannot justify an inexact route.

Full stage observations, cold loads, and request failures are in `browser-results.json`.

## Reproduce

```sh
uv run --with numpy --with safetensors --with fonttools --with pillow --with brotli \
  python tools/build_compensated_oneplane_hot2_probe.py
python3 -m http.server 4189 --bind 127.0.0.1
ONEPLANE_DIRECTORY=gpt2-compensated-oneplane-hot2 \
ONEPLANE_ROUNDS=1 ONEPLANE_FIXTURE_LIMIT=2 \
  node tools/test_virtual_base_oneplane_hot2_probe.mjs
```
