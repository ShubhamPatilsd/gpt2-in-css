# Multiline intrinsic-width output-head probe

This probe asks whether one multiline intrinsic-width run per 256-token group
can replace 256 overlapping Grid candidates. It uses the same three HVAR score
glyphs per token as the shard-256 global-int11 head.

A newline-only text node is not usable in Chrome 153: each Range reports the
right individual line width and token 11 is the widest line in group 0, but the
element's `max-content` width is the sum of all 256 lines. The outer reducer
therefore selects the group with the largest score sum.

Explicit `<br>` elements restore the desired maximum-line intrinsic width.
The probe then selects the correct winning group, and its widest group-0 line
is token 11. The cold result is:

| Metric | Multiline `<br>` | Existing three-shard Grid |
| --- | ---: | ---: |
| Cold completion | 65.696 s | about 61.7 s |
| Layout time | 64.063 s | — |
| Elements | 51,064 | 51,261 |
| Candidate / line elements | 50,060 `<br>` | 50,257 `<i>` |

The line-fragment version is slower despite removing candidate styles and Grid
items, and it only recovers the winning 256-token group; local-token identity
would need another encoding. Reject this path. The decisive cost tracks shaped
glyph/line count, not the candidate element type.

## Reproduce

```sh
make test-gpt2-output-head-multiline
```
