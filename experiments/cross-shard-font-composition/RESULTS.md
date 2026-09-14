# Cross-shard variable-font composition

Measured in Chrome 153. The runtime probe contains HTML, CSS, and WOFF2 fonts
only; JavaScript is used solely by the external verifier.

## Question

Can the three 256-axis FC shards for GPT-2's `768 -> 3,072` matrix be summed,
passed through GELU, and consumed by the `3,072 -> 768` projection while the
values remain inside variable-font machinery?

## Browser probe

Two one-axis HVAR faces contribute one glyph each to one fallback run. Shard A
has advance `500 + 200A` font units and shard B has advance `500 + 300B`.
At 40 px per em Chrome produced:

| A | B | shaped fallback run | `1ch` | explicit sizing bridge | bridge `100cqi` |
| -: | -: | -: | -: | -: | -: |
| 0 | 0 | 40 px | 20 px | 40 px | 40 px |
| 1 | 0 | 48 px | 28 px | 48 px | 48 px |
| 0 | 1 | 52 px | 20 px | 52 px | 52 px |
| 1 | 1 | 60 px | 28 px | 60 px | 60 px |

Normal shaping therefore sums advances from independent fallback faces. The
font-relative metric does not: `1ch` observes shard A's `0` glyph and is
unchanged when only shard B changes. The summed result becomes reusable only
after `#bridge` materializes the run width as an anchor/container size.

Chrome also rejects each attempted direct feedback channel:

| declaration | `CSS.supports` |
| --- | ---: |
| `font-size: anchor-size(--sum width)` | false |
| `font-variation-settings: "opsz" calc(anchor-size(--sum width) / 1px)` | false |
| `font-size: calc-size(max-content, size)` | false |
| `width: calc-size(max-content, size)` | true |

`calc-size()` can transform intrinsic width only while resolving a sizing
property. It cannot turn that width into a font axis or `font-size`. Optical
sizing therefore cannot help without first putting the width in a container.

## Structural reason

The font tables do not form a programmable pipeline:

```text
CSS variation coordinates
  -> normalization and avar/avar2
  -> one fixed normalized location for this face
  -> HVAR / VVAR / gvar / MVAR evaluate independently at that location
  -> shaping combines glyph advances
  -> layout obtains the run width
```

`avar2` can replace each input coordinate with a function of the other input
coordinates, but its output is the same set of axes declared by `fvar`. HVAR,
gvar, and MVAR consume that location; none writes a new coordinate for a later
table or another face. Fallback faces are shaped independently, and their
advances are added only after each face's variation processing is complete.

This explains both the successful existing `256 -> 256 -> 768` internal avar2
probe and the full GPT-2 failure. Inside one <=256-axis face, avar2 can compute
a dense map, coordinate-wise GELU, and HVAR projection. Across three input
faces, the only shared result is layout geometry.

Applying GELU before the sum is not a valid decomposition. For example,
`GELU(1 + -1) = 0`, while `GELU(1) + GELU(-1)` is about `0.683`.

## Font-relative metric alternative

There is a non-geometry alternative, but it is not a scalable one-backend
solution. A specially generated face can expose four arbitrary 256-input rows
simultaneously through `cap`, `ch`, `ic`, and `lh`. Three nested faces can add
the three input-shard partials into four registered CSS numbers. Repeating this
for 3,072 FC rows would require:

- 768 output groups;
- 2,304 independently shaped 256-axis FC font instances/faces;
- 3,072 registered scalar results before GELU;
- staged inheritance to gather sibling groups into the twelve projection
  fonts.

The already measured 768-row version required 576 fonts, expanded to 465 MB,
used 3.23 GB of Chrome RSS, and took 1.17 seconds for a full-vector mutation.
The 3,072-row FC is four times that output count: approximately 2,304 fonts and
1.86 GB of expanded font data before the projection. The five-metric/128-axis
variant would need 3,690 fonts and roughly 897 MB of expanded data. This route
removes geometry readback but replaces it with a much larger font-instance and
memory problem.

## Lower bound for the retained architecture

For the unmodified GPT-2 checkpoint, all 3,072 values

```text
z_j = shard0_j + shard1_j + shard2_j + bias_j
```

must exist independently at the GELU boundary. Font machinery cannot combine
multiple `z_j` values because a shaped run exposes only its total advance, not
the individual glyph advances.

With the shared three-font FC bank, the smallest exact current representation
is therefore:

- 3,072 logical scalar FC/GELU boundaries;
- one aggregate shaped run/width per hidden coordinate;
- 1,536 physical size-capture boxes when two scalars are paired as width and
  height;
- twelve or thirteen <=256-axis projection groups after the boundary.

Eliminating this count requires a new vector-valued browser primitive, a
backend that can retain more than 256 computed coordinates through the
nonlinearity, or a changed/retrained model with a shard-separable MLP. Another
combination of current font tables does not remove it.

## Reproduce

```sh
uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_cross_shard_font_composition_probe.py
node tools/test_cross_shard_font_composition_probe.mjs
```
