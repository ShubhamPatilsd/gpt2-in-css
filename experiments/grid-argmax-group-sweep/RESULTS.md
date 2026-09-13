# Hierarchical Grid argmax group-size sweep

Measured in headless Chrome 153 on macOS on September 13, 2026. Every page
reduces 50,257 changing candidates and returns the exact synthetic token and
score. Runtime pages contain no JavaScript.

| Tokens/group | Groups | Score bits | Settled mutation median |
| ---: | ---: | ---: | ---: |
| 64 | 786 | 14 | 189.3 ms |
| 128 | 393 | 15 | 170.4 ms |
| 256 | 197 | 16 | 168.0 ms |
| 512 | 99 | 15 | 161.5 ms |
| 1,024 | 50 | 14 | 162.0 ms |
| 2,048 | 25 | 13 | 164.6 ms |
| 4,096 | 13 | 12 | 164.1 ms |

The synthetic reduction has a shallow optimum around 512-1,024. The gain over
256 is only about four percent, while available score precision falls from 16
bits to 15 or 14 bits.

The 512 split was also tested on the real HVAR output head by halving score
scale from 1,024 to 512. It remained exact but three independent browser
processes had a 953.5 ms settled median, versus 872.2 ms for the retained
256-token split. The synthetic reduction saving does not survive the complete
font-shaping and layout path. Keep 256 tokens per group.

## Reproduce

```sh
python3 tools/build_grid_argmax_group_sweep.py
node tools/test_grid_argmax_group_sweep.mjs
```
