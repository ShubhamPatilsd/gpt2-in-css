# Aggregate axis-list ping-pong

Rejected. Alternating two untyped custom properties can syntactically append a
growing `font-variation-settings` list through nested elements. However,
container units inside that list remain unresolved tokens until the final
consumer. Every `100cqi` then resolves against the final container, so distinct
intermediate matrix outputs collapse to one value.

Registered numeric properties freeze values at the correct element, but a
registered property cannot represent and append the mixed string/number grammar
required by `font-variation-settings`. CSS also has no list indexing operation
that could convert a registered numeric list back into named font axes.

```sh
node tools/test_css_axis_list_pingpong_probe.mjs
```
