# Direct font-metric to font-axis chaining

## Result

Chrome can feed five outputs from one variable font directly into five
variation axes of a nested variable font. No glyph-width box, view timeline,
animation, or JavaScript is required.

The shortest working form is conceptually:

```css
.parent-matrix {
  font-family: Producer;
}

.child-matrix {
  font-family: Consumer;
  font-variation-settings:
    "Y000" calc((1ex  / 1px * 1000 / 256 - 8000) / 256),
    "Y001" calc((1cap / 1px * 1000 / 256 - 8000) / 256),
    "Y002" calc((1ch  / 1px * 1000 / 256 - 8000) / 256),
    "Y003" calc((1ic  / 1px * 1000 / 256 - 8000) / 256),
    "Y004" calc((1lh  / 1px * 1000 / 256 - 8000) / 256);
}
```

Font-relative units used while computing a font property resolve against the
parent's font metrics. This avoids a cycle with the child font being selected.
The child therefore receives the five parent metrics rather than its own.

## Matrix-chain proof

The producer font evaluates a live `5×5` matrix and emits the five rows as
`ex`, `cap`, `ch`, `ic`, and `lh`. The consumer font receives them as five axes
and evaluates a second `1×5` matrix.

For the initial input, the exact intermediate vector is:

```text
[0.25, 3.55, -1.3, -0.2, 1.05]
```

The exact final value is `-4.7`. Chrome returned:

| Handoff | Final value | Error |
| --- | ---: | ---: |
| Registered numeric properties | -4.69043 | 0.00957 |
| Unregistered custom properties | -4.68652 | 0.01348 |
| Direct metric expressions | -4.68652 | 0.01348 |

After changing all five original inputs, all three paths updated the consumer
axes and returned `-20.5283` for an expected `-20.5`. The registered path took
about `0.0062 ms` per five-input update and forced output read in this small
fixture. The two fonts total 4,332 bytes as uncompressed TTF.

The residual error is font metric/layout rounding, primarily the `cap` and
`lh` channels. Scaling metric deltas by 256 reduced it substantially. The
handoff itself does not introduce a low-bit image or timeline quantization.

## Path-by-path findings

### Direct expressions: works

This is the most compact handoff. The child places the parent's five metric
expressions directly in `font-variation-settings`. Computed style showed all
five numeric axis values, and mutations propagated live.

### Unregistered custom properties: works

An unregistered property retains its token stream until substitution. When it
is substituted into the child's font property, its font-relative units still
resolve using the parent-font rule. This behaves like the direct form and does
not materialize reusable numeric CSS state.

### Registered numeric properties: works

Registering each metric as `<number>` computes and freezes it on the producer.
The child inherits five ordinary numbers. This is useful when later descendants
must reuse the values or perform other CSS arithmetic, but registration is not
required for the immediate font-to-font handoff.

### Nested `font-size`: one scalar only

Setting an intermediate child's `font-size: 1ch` captures the parent's `ch`
metric. A descendant recovered the value through `1em` and passed it to one
axis with `0.00008` error. This is a valid scalar carrier, but one font size can
encode only one independent value. It cannot replace the five direct units.

### `calc-size()`: rejected

`calc-size(auto, size)` is not valid inside `font-variation-settings`. Chrome
dropped that declaration; the computed property merely inherited the parent
font's `X000`–`X004` settings, and the consumer output stayed at zero.
`calc-size()` remains restricted to intrinsic sizing contexts and does not
expose an intrinsic or font value as a general CSS number.

## Dense-vector limitation

This solves a local boundary between two matrices when the first matrix has at
most five outputs. It does **not** solve the 768-output gather.

A child font can directly see the five metrics of its immediate parent. It
cannot see five different metric sets from 154 sibling font instances. To make
all 768 outputs reusable, registered values must be accumulated down one
ancestor chain, meaning every input shard and output group still needs a node
in that chain. The measured full-scale metric bank requires 924 font instances,
about 224 MB of expanded font data, 2.83 GB Chrome RSS, and 934.5 ms for a full
768-input update.

So direct metric chaining removes the geometry/timeline conversion for each
local five-value handoff. It does not remove the much larger problem of
assembling hundreds of independent font outputs into one consumer vector.

## Reproduce

```sh
/usr/bin/python3 tools/build_font_metric_chain_probe.py
node tools/test_font_metric_chain_probe.mjs
```
