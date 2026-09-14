# Packed timeline transport

## Question

Can one CSS view timeline carry several matrix outputs by integer-packing
multiple intrinsic glyph widths into the subject's position and extent?

## Fixed-value precision probes

`calc-size()` can round an intrinsic width before scaling it into a positional
digit. CSS `round()` and `mod()` can recover the digits after the packed width
passes through a view timeline. The generated pages contain no JavaScript.

For one width carrier, 48 random values per configuration produced:

| Packed format | Exact packed integers | Maximum packed error |
| --- | ---: | ---: |
| two 8-bit digits | 48/48 | 0 |
| two 9-bit digits | 39/48 | 1 |
| two 10-bit digits | 38/48 | 1 |
| two 12-bit digits | 4/48 | 72 |
| three 8-bit digits | 4/48 | 74 |

Using both position and width carries four digits per timeline. Across 96
decoded carriers, four 8-bit values had maximum packed error 1; four 9-bit
values had maximum error 4; and four 10-bit values had maximum error 19.
The error growth comes from timeline-progress precision at multi-megapixel
geometry sizes, not from `round()` or `mod()`.

The practical reliable payload is therefore about two 8–10-bit digits per
geometric degree, or four values per inline timeline. Higher packing density
needs lower-precision activations or an error-tolerant code.

## Real GPT-2 block

`../gpt2-block-css/view-timeline-block-hybrid-fc-packed4.html` applies the
method to block 0. The browser performs every `768→3,072` HVAR dot product,
applies GPT-2 GELU inside nested `calc-size()` expressions, quantizes the
post-GELU values, and packs four results per timeline. The downstream
`3,072→768` projection consumes the packets directly; it does not materialize
3,072 intermediate `--hidden-*` properties.

The packing order is importance-aware. The half of the hidden units with the
largest projection-column norms occupy protected high digits at 9-bit
precision. The remaining units use guarded low digits at 8-bit precision.
This changes activation transport precision but does not prune weights,
precompute activations, or retrain the model.

| Measurement | Accurate paired | Packed four-value |
| --- | ---: | ---: |
| FC timelines and animations | 1,536 | 768 |
| Materialized hidden properties | 3,072 | 0 |
| Warm alternating median | 1.851 s | 1.005 s |
| Max block error vs quantized reference | 0.04214 | 0.15988 |
| Block RMSE vs quantized reference | 0.00531 | 0.03101 |

The packed version is 45.7% faster than the accurate paired version and about
2.2× faster than the 2.24-second unpaired hybrid measured in the preceding
three-way run. It is a meaningful new transport primitive, but it is not the
requested 13× result: 1.005 seconds remains 7.7× above the 130 ms block target.

An ablation that ends at the packed FC state measured 452 ms, while the full
numeric-output page measured 955 ms in the same run. The projection plus its
768-output timeline transport therefore accounted for roughly 503 ms. A second
page, `../gpt2-block-css/view-timeline-block-hybrid-packed4-chain.html`, packs
the projection result into 192 timelines. It measured 875 ms versus 967 ms for
the numeric-output variant, another 9.5% reduction and about 2.56× versus the
unpaired baseline. Signed square-root output companding introduced 2.82 maximum
error and 0.222 RMSE at this boundary. That page is a chaining experiment, not
the accuracy default.

### HVAR projection endpoint

`../gpt2-block-css/view-timeline-block-hybrid-fc-packed4-hvar.html` removes the
second view-timeline bank entirely. The 768 packed FC timelines feed one global
3,072-axis HVAR declaration, and the projection remains in 768 glyph widths.
Across three fresh browser processes, settled mutation medians were 184.5 ms
for the HVAR endpoint and 277.4 ms for the old numeric-output endpoint: a 1.50x
same-fixture speedup. Dense-reference RMSE was 0.0305 versus 0.0310 for the old
path. See `../gpt2-block-css/TIMELINE_HVAR_PROJECTION_RESULTS.md`.

This win applies when widths are the endpoint. Re-importing them for another
block reverses it: the accurate 12-bit registered gather measured 331.8 ms
total, and an eight-bit/128-carrier version measured 300.7 ms with worse error.
The 266.2 ms output-timeline boundary remains the fastest accurate chaining
form tested so far.

### Six values per timeline

`../gpt2-block-css/view-timeline-block-hybrid-fc-packed6.html` tests the next
packing density. Three mixed-radix digits occupy position and three occupy
width, reducing the FC boundary from 768 to 512 timelines. Projection-column
importance assigns 4 bits to the lowest third of neurons, 5 bits to the middle
third, and 7 bits to the highest third. The low digit is spaced 16 pixels apart
so multi-megapixel timeline error cannot scramble it.

The first 6/7/9-bit layout used an 8.4-million-pixel packet. Timeline recovery
had 9 pixels median error and 93 pixels maximum error, corrupting the low digit
and producing 2.93 block RMSE. The guarded 4/5/7-bit layout reduced the packet
to about 2.1 million pixels and matched its offline estimate: 0.684 maximum
block error and 0.184 RMSE.

In the same alternating Chrome run, packed-six transport was roughly 11% faster
than packed-four transport and the full page was roughly 14% faster (about 1.14
seconds versus 1.32 seconds in that noisier run). The extra loss for a modest
constant-factor gain confirms that geometry packing is at diminishing returns;
it cannot supply the remaining order-of-magnitude improvement.

A later controlled sweep corrected the carrier window so every possible packet
intersects the viewport, then compared clean uniform six- and seven-bit forms.
With four warm samples per page in Chrome 153, packed four took 1,086.6 ms at
0.0310 block RMSE. Uniform six took 941.9 ms at 0.1220 RMSE; uniform seven took
902.1 ms at 0.2438 RMSE. Per-channel asymmetric and importance-aware 5/6/6
schemes were accurate before geometry transport but became substantially worse
after it. See `../packed-activation-precision/RESULTS.md` for the complete
twelve-block and browser results.

## Rejected variants

- Uniform 8-bit activation quantization produced about 0.206 block RMSE.
- Square-root companding reduced that to about 0.081 RMSE.
- Exact GELU through nested intrinsic sizing plus importance-aware 9/8-bit
  digits reduced it to 0.031 RMSE.
- Giving protected digits 10 bits slightly improved maximum output error but
  worsened RMSE to 0.047 because the larger geometry amplified transport
  error, so the 9/8-bit variant is retained.
- A shared CSS custom function cannot consume the special `size` keyword
  through a `calc-size()` boundary in Chrome 152. Nested `calc-size()` calls
  are the working way to retain the preactivation for exact GELU.
- Re-evaluating the 89 MB direct-CSS block in place took a 2.48–2.66 second
  steady-state interval after changing one input. The previously reported
  roughly 20 ms figure was only a cached computed-style read, not inference.
  Direct CSS therefore does not provide a hidden 13× warm-runtime path.

Relevant specifications: [CSS intrinsic-size arithmetic](https://drafts.csswg.org/css-values-5/#calc-size),
[stepped value functions](https://drafts.csswg.org/css-values/#round-func), and
[scroll-driven animations](https://drafts.csswg.org/scroll-animations-1/).
