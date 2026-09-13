# Orthogonal container-unit probe

A horizontal `inline-size` query container nested around a vertical-writing
`inline-size` query container exposes two independent physical dimensions to
one descendant:

| Outer width | Inner height | `100cqw` | `100cqh` | CSS product |
| ---: | ---: | ---: | ---: | ---: |
| 137 px | 83 px | 137 px | 83 px | 11,371 + 1,000 px |
| 149 px | 71 px | 149 px | 71 px | 10,579 + 1,000 px |

The descendant's single CSS expression correctly multiplies both live geometry
values without named anchors or timelines. This is a valid local two-input
transport primitive.

It does not yet solve vector reduction: both physical axes are consumed by the
two inputs, so the product cannot also escape through intrinsic width/height to
be summed by a parent. Retain the primitive for local nonlinear operations or
future grid/subgrid routing tests.

