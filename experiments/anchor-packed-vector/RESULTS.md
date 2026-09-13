# Anchor-packed vector transport

`anchor-size()` can combine four independently computed widths into a single
24-bit radix-64 carrier. A child decodes the carrier with `cqi`, uses the four
digits as paused-animation progress values, and produces one additive
`font-variation-settings` vector.

Chrome 153 decoded `[17,31,20,33]` and, after mutating the four source widths,
`[58,43,30,35]` exactly. No view timeline or registered numeric property is
involved.

The critical geometry limit is four 6-bit values per dimension. Five values
need 30 bits; placing the low digit below one pixel at large widths loses it to
layout precision.
