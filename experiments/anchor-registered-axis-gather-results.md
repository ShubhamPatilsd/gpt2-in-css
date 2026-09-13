# Registered anchor-size to font-axis gather

Rejected in Chrome 153. Routing `anchor-size()` through a registered numeric
custom property does not make it valid as a font variation coordinate. Both
properties remain at their `-999` initial value:

```text
--a0: calc(anchor-size(--source-0 width) / 1px)
--a1: calc(anchor-size(--source-1 width) / 1px)
font-variation-settings: "A000" var(--a0), "A001" var(--a1)
```

This closes the apparent gap in the earlier direct-anchor test. A nested
container boundary is still required to turn font geometry into a reusable CSS
number.

```sh
make test-anchor-registered-axis-gather
```
