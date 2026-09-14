# GPT-2 output-head group containment

Group-level containment does not reduce the cold cost of the global-int11
vocabulary head. Each variant uses the same 50,257 exact candidate scores and
returns token 11 in Chrome 153.

| Variant | Cold completion | Layout time | Style time |
| --- | ---: | ---: | ---: |
| Control | 67.714 s | 65.580 s | 91 ms |
| `.group-wrapper { contain: layout }` | 67.538 s | 65.846 s | 92 ms |
| `.group-wrapper { contain: layout style }` | 67.839 s | 66.101 s | 121 ms |

The spread is only 0.45%, and containment slightly increases layout work and
layout count. The formatting contexts are already independent enough; shaping
and laying out every score remains the cost. Reject this as a scaling path.

## Reproduce

```sh
make test-gpt2-output-head-containment
```
