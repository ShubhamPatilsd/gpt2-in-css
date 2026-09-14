# Container width to automatic font-axis handoff

Measured in headless Chrome 153 on macOS. The runtime pages contain HTML, CSS,
and fonts only; JavaScript is used only by the external Playwright verifier.

## Question

Can an HVAR glyph width become a child font coordinate without a view timeline,
animation, or registered custom property?

The path is:

```text
HVAR glyph width
  -> absolutely positioned anchor-size() bridge
  -> bridge is an inline-size container
  -> child font-size: 100cqi
  -> automatic opsz axis
  -> child HVAR advance
```

## Correctness

Yes. Source widths of 60, 70, 90, and 100 px became child font sizes of the
same values. A consumer font with an `opsz`-dependent advance produced widths
of 30, 42, 72, and 90 px. Explicit
`font-variation-settings: "opsz" calc(100cqi / 1px)` produced the same result
as `font-optical-sizing: auto`.

This is a real geometry-to-font-axis conversion. It does not create a reusable
CSS number, but it can feed one width directly into one axis of a descendant
font.

## Fresh-vector scaling

Every lane uses a distinct axis value and every mutation selects a new set of
values. This avoids the shaped-result cache-hit error found by the earlier
ideal-carrier benchmark.

| Independent scalar handoffs | Font-size-only control | Automatic `opsz` | Explicit `opsz` |
| ---: | ---: | ---: | ---: |
| 16 | 0.3 ms | 0.4 ms | 0.3 ms |
| 64 | 1.3 ms | 1.2 ms | 1.3 ms |
| 256 | 7.0 ms | 6.0 ms | 7.2 ms |
| 768 | 28.3 ms | 35.3 ms | 32.8 ms |
| 1,536 | 80.0 ms | 94.1 ms | 84.5 ms |
| 3,072 | 265.9 ms | 262.5 ms | 277.3 ms |

Automatic optical sizing adds no measurable cost at 3,072 lanes relative to
the font-size-only control. The cost is the anchor/container/layout graph, not
the axis mapping. The curve becomes strongly superlinear beyond 768 lanes.

At equal 3,072-value capacity, 262.5 ms is only 7.6% faster than the saved
284.03 ms two-axis/four-value view-timeline fixture. This is useful, but not an
order-of-magnitude transport improvement.

## Four coordinates in one final font

Four distinct geometry values can be frozen into inherited font state and
consumed by one variable font:

- `font-weight` drives `wght`;
- `font-stretch` drives `wdth`;
- an inherited explicit variation drives `slnt`;
- `font-size` plus optical sizing drives `opsz`.

The browser produced the exact expected HVAR advances for both validation
vectors. Continuous `font-style: oblique <angle>` did not work for this
purpose: Chrome selected its italic default (`slnt=-14`). An explicit inherited
`"slnt"` coordinate was required.

| Source scalars | Final four-axis font shapes | Warm median |
| ---: | ---: | ---: |
| 16 | 4 | 0.4 ms |
| 64 | 16 | 2.3 ms |
| 256 | 64 | 12.9 ms |
| 768 | 192 | 73.8 ms |
| 1,536 | 384 | 243.6 ms |
| 3,072 | 768 | 916.9 ms |

Despite using one final shape per four values, this is slower than independent
scalar handoffs. Each coordinate needs another nested positioned size container
and inherited dependency level. Fewer sinks do not compensate for the deeper
layout graph.

## Composability limit

`anchor-size()` did not resolve on an in-flow inline-block, even with
`position: relative`; the copied width and its `100cqi` child were both zero.
It works on the absolutely positioned bridge used by the successful probes.

That restriction is decisive for a dense matrix. The child glyphs cannot sit
in a normal inline run whose width sums many independently sized contributions.
Using another anchor expression or capture boundary to combine them recreates
the existing coefficient graph or geometry-to-number problem.

## Decision

Retain automatic `opsz` as a fast local scalar handoff and the standard-axis
method as a four-coordinate capability probe. Reject both as the bulk GPT-2
vector carrier:

- the scalar path reaches the same latency class as timelines at 3,072 values;
- the four-axis path is slower;
- neither gathers hundreds of independent coordinates into one <=256-axis
  dense HVAR matrix;
- the required bridge is out of flow and cannot accumulate matrix rows.

The architecture decision remains HVAR for affine work and CSS numbers for
nonlinear arithmetic, with vector transport and connected layout fan-out as
the scaling blocker.

## Reproduce

```sh
make test-opsz-container-handoff
```

Raw measurements are in `browser-results.json`.
