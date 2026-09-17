# Alpha-only Boolean SVG circuit experiment

## Question and scope

Can a static SVG filter graph carry exact digital values through arithmetic,
avoiding the thousands of CSS numerical properties in the font runtime?

This is a new representation experiment, not a GPT-2 replacement. Inputs are
signed integers. The connected fixture uses dense ternary weights and ReLU,
not GPT-2's real weights, layer normalization or GELU. No measured time below
is a token-generation time.

## Representation

Each bit is a transparent or opaque black pixel: premultiplied RGBA
`(0,0,0,b)`, with `b` either zero or one. Ordinary Porter-Duff composition
implements exact truth tables in ideal arithmetic:

| Operation | SVG operation | Output alpha |
| --- | --- | --- |
| AND | `in` | `ab` |
| XOR | `xor` | `a(1-b)+b(1-a)` |
| NOT | opaque-black `feFlood` followed by `out` input | `1-a` |
| OR | `over` | `a+b(1-a)` |

All intermediate RGB channels remain zero. This avoids the invalid approach of
encoding bits in opaque RGB and applying arithmetic XOR: that would calculate
zero alpha and erase the intended RGB signal. The operations follow the
[compositing specification](https://www.w3.org/TR/compositing-1/#porterduffcompositingoperators)
and [SVG filter specification](https://www.w3.org/TR/filter-effects-1/#feCompositeElement).

Each gate is an explicitly named two-input SVG primitive. These are real
compositing dependencies, but this probe does **not** instrument Skia's surface
allocator and therefore does not claim that every named result becomes a
separate physical surface. Backend fusion is permitted. All regions and offsets
are explicit and device-pixel aligned. Alpha becomes opaque monochrome only at
the final visualization; nothing reads intermediate values into CSS or JavaScript.

## Stage 1: gates, carry chains, and cancellation

Chrome 153.0.8010.48 on macOS. The baseline runs seven alternating-input trials
per fixture. All output bits are compared with exact integer reference bits,
including the initial input and every changed input.

| Circuit | Cases in parallel | Explicit primitives | Warm input-change + screenshot median | Cached screenshot median | Correctness |
| --- | ---: | ---: | ---: | ---: | --- |
| Four truth tables plus 64 repeated NOT/XOR steps | 4 | 214 | 589.5 ms | 66.9 ms | Passed |
| 8-bit addition and `x + (-x)` | 8 | 156 | 82.3 ms | 66.9 ms | Passed |
| 16-bit addition and `x + (-x)` | 8 | 308 | 414.8 ms | 66.8 ms | Passed |
| 32-bit addition and `x + (-x)` | 8 | 612 | 2,755.9 ms | 66.5 ms | Passed |

The addition fixture includes all-one carry propagation, signed-boundary
crossings and modulo-word overflow. Cancellation must produce exact zero across
the complete word. Baseline data: [reference](stage1-r0/reference.json) and
[browser results](stage1-r0/browser-results.json).

The browser reported **zero style-recalculation events and zero style time in
every measured changed-input trial** of these baseline fixtures. This proves the
style traffic can be removed in this small graph; it does not imply inexpensive
execution. At 32 bits the total changed-input latency is already about 2.76
seconds for eight simultaneous additions plus cancellation. Sampled browser
subtree RSS reached about 1,978 MiB in that fixture; this includes the browser,
GPU and renderer processes and is not the circuit's isolated allocation.

## Carry topology check

The second build substitutes parallel-prefix carry calculation for ripple
carry. This makes the carry dependency shallower while adding primitives.
Three alternating-input trials were requested; all successful outputs remained
exact.

| Prefix circuit | Explicit primitives | Warm median | Outcome |
| --- | ---: | ---: | --- |
| 8 bits | 242 | 99.6 ms | Passed |
| 16 bits | 586 | 638.5 ms | Passed |
| 32 bits | 1,386 | Not available | Initial screenshot timed out after 30 seconds |

The timeout is preserved in [prefix browser results](stage1-prefix-r0/browser-results.json).
The complete process took 66.8 seconds, including the successful smaller cases
and browser cleanup. There is no correctness result or warm timing for the
32-bit prefix case. This limited screen rejects that specific prefix graph as
an improvement; it does not establish that every shallow Boolean topology fails.

## Connected matvec stage

The bounded four-dimensional fixture computes signed
`matvec -> ReLU -> matvec` within one filter graph. First-stage reductions use
horizontal offsets and adders; the first vector remains an alpha-bit column.
Cropping and `feTile` feed it directly to a vertical second-stage reduction.
No intermediate raster-to-CSS conversion or numerical browser script is used.

It **timed out before the first screenshot**, after the 30-second screenshot
limit. Its graph contains 486 primitives and 46,130 bytes of HTML. No successful
output or warm timing exists for that case. The timeout is retained in
[matvec4 browser results](matvec4-r0/browser-results.json).

A smaller two-dimensional control contains 299 primitives and 28,496 bytes of
HTML. Its first navigation plus screenshot took 8.84 seconds but returned an
all-white image, failing exactness. That could mean invalid computed bits or
an absent filter image against the white page. A second control changed the
page background to magenta and checked all three RGB channels; all 24 output
samples showed magenta. **The circuit did not paint a valid output image.**
The sentinel control took 9.71 seconds through navigation and first capture;
that is a failed-run cost, not useful matrix latency. See
[original two-wide results](matvec2-r0/browser-results.json) and
[sentinel results](matvec2-sentinel-r1/browser-results.json).

An independent Python interpreter evaluated the generated primitive graph,
PNG alpha inputs, subregions, crop/tile operations and exact gates. Both input
variants passed for dimensions two and four. For example the two-wide case
calculates `[-53,14] -> [-67,39] -> [0,39] -> [-39,-39]`; its alternate input
calculates `[127,-127] -> [254,0] -> [254,0] -> [254,254]`.
These [two-wide](matvec2-r0/offline-graph-audit.json) and
[four-wide](matvec4-r0/offline-graph-audit.json) audits establish logical graph
consistency, not browser correctness. They do not determine whether the
browser failure originates in graph construction limits, image allocation,
dependency evaluation or crop/tile handling.

Scaling stopped here. Dimensions 8 through 64 were not attempted because the
smaller connected graphs already failed the bounded feasibility gate.

## Decision

Keep the successful alpha truth-table/addition proof as evidence that digital
values can avoid the old analog rounding failure. **Reject this generated
Boolean filter architecture as the next GPT-2 speedup.** It removes measured
style recalculation in the small arithmetic fixtures, but incurs severe graph
cost and does not yet execute even a two-dimensional connected matvec chain.
Parallel-prefix carries added more primitives and made the measured cases
slower. There is no end-to-end model speedup or connected matrix speedup here.

If revisited, the next bounded question is why the two-wide filter paints no
image, using isolated crop/tile and graph-depth controls. It should precede any
larger matrix build. The current evidence does not justify allocating a larger
model-sized graph.

## Measurement and reproducibility

The generated pages contain HTML, CSS, SVG and lossless PNG inputs only, with
`script-src 'none'`. The external Playwright harness supplies pre-generated
input images by changing `href`, screenshots the final SVG, and decodes bits.
It does not perform any inference arithmetic in the page. The timed interval
includes input delivery, rendering, frame synchronization and PNG readback.
Cached screenshots show the approximately 67 ms measurement floor. Subtracting
that floor would not establish pure filter compute time, so no such claim is
made. Navigation timings include a 500 ms network-idle wait and are not pure
startup measurements.

Browser performance counters describe the main renderer, not all GPU work.
RSS is sampled every 200 ms with `ps`, not physical footprint or GPU allocation.
The `surfacePixelUpperBound` field is area times primitive count, not measured
surface allocation. Fonts, canvas inference, shaders and runtime model JS are
absent. Expected answers are stored only in the external reference JSON. The
sentinel follow-up checks RGB together so a missing image cannot masquerade
as an all-one bit vector. Earlier arithmetic cases used a white backdrop and
checked red-channel values; their required mixed zero/one and all-zero
cancellation outputs passed, so a wholly absent filter image could not pass.

Every build is immutable and records generator/harness source snapshots and
hashes. Newer harness runs additionally archive the exact executed harness;
this distinguishes source changes after a fixture was built. All browser runs
and builds use the shared advisory lock, which serializes cooperating
experiments; unrelated system activity remains possible.

```sh
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- python3 tools/build_svg_alpha_circuit_probe.py --label stage1-r0
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- node tools/test_svg_alpha_circuit_probe.mjs stage1-r0
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- python3 tools/build_svg_alpha_circuit_probe.py --label stage1-prefix-r0 --adder prefix
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- env ALPHA_ROUNDS=3 ALPHA_CASES=add8,add16,add32 node tools/test_svg_alpha_circuit_probe.mjs stage1-prefix-r0
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- python3 tools/build_svg_alpha_circuit_probe.py --label matvec4-r0 --size 4 --adder ripple
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- env ALPHA_ROUNDS=3 node tools/test_svg_alpha_circuit_probe.mjs matvec4-r0
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- /opt/homebrew/bin/python3.11 tools/build_svg_alpha_circuit_probe.py --label matvec4-r0 --audit-existing
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- /opt/homebrew/bin/python3.11 tools/build_svg_alpha_circuit_probe.py --label matvec2-r0 --size 2 --adder ripple
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- env ALPHA_ROUNDS=3 node tools/test_svg_alpha_circuit_probe.mjs matvec2-r0
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- /opt/homebrew/bin/python3.11 tools/build_svg_alpha_circuit_probe.py --label matvec2-r0 --audit-existing
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- /opt/homebrew/bin/python3.11 tools/build_svg_alpha_circuit_probe.py --label matvec2-sentinel-r1 --size 2 --adder ripple
python3 tools/run_unconventional_isolated.py --label alpha-circuits -- env ALPHA_ROUNDS=1 node tools/test_svg_alpha_circuit_probe.mjs matvec2-sentinel-r1
```

To repeat, use new labels; the tools refuse to overwrite results.

The first four-wide offline audit command used Homebrew Python 3.14 and failed
before interpreting the graph because its `pyexpat` extension could not load
`_XML_SetAllocTrackerActivationThreshold` from the system library. Retrying with
the existing Python 3.11 installation passed. This is a local interpreter
failure, separate from the browser timeouts. Both new source files passed
Python compilation / Node syntax validation after the last edit.

## Relation to the F16 route

This probe confirms that exact endpoint values can survive compositing without
high-precision surfaces. It does not establish that small non-binary values
survive. The existing stock-browser sub-byte precision probe already tests that
separate issue. A useful future F16 smoke test would contrast these exact alpha
endpoints with a sub-byte alpha ramp through the same composite chain, avoiding
color-space ambiguity. It would still need allocator instrumentation to prove
an F16 implementation change.
