# Choose the next experiment by the cost it can remove

**Subsequent correction:** inspection for the user's next task found
[older connected MLP results](../avar2-gelu-linear-hvar-full-mlp/CONNECTED_RESULTS.md)
that this recommendation had missed. They already cover LN2, residual addition,
next-layer normalization, and two one-token blocks. The useful missing test is
against the current reusable token core under matched surrounding stages and
generation behavior. The isolated 251 ms value below is not a stable connected
latency. See the [new comparison plan](../native-mlp-integration/PLAN.md).

The historical evidence is in [PROGRESS_AUDIT.md](PROGRESS_AUDIT.md). Recent
results do not establish a hard browser speed limit. They establish that several
plausible local improvements have failed to improve the complete model. The
next direction should address the distance between a successful primitive and
the actual model, not just create another smaller primitive.

## 1. Stop making the font search the whole input for its next instruction

The current compact digit program still applies seven passes for every addition.
At width 64, there are 252 useful digit additions but 8,316 nominal digit
positions covered by those passes. This is a count derived from the generated
program, not a measured number of engine visits. It explains why a small file
can still request a great deal of work.

The different proposal is to start at the unique running-total marker and
execute a list of local instructions there. After one operand is consumed, the
same marker identifies the next addition. The [compiler notes](COMPILER_NOTES.md)
describe a flat list of nested substitution actions and the uncertainties around
deleting glyphs while those actions execute. This changes how arithmetic is
dispatched; merely regrouping the same top-level passes would not do that.

First test only two additions. Confirm that the second instruction still finds
the right operand after the first removes its input. Then run exhaustive
four-input checks and measure 16/64 inputs. Stop if engine bookkeeping recreates
the same growth or if correct execution requires forbidden context sizes.
There is no implementation or speed claim for this proposal yet.

For affine-only work, we also added an actual alternative control to the current
experiment: encode each small input directly as its fixed product width and let
normal text layout add contributions. This requires no digit-addition program.
It gives up internal intermediate state, so a win would favor a hybrid design,
not prove font-internal neural layers. The synthetic four-weight alphabet is
especially favorable. A real matrix needs more weights, precision and output
rows, and potentially many more shaped glyphs than HVAR.
For example, a direct one-product-glyph implementation of the 768→3,072 FC
would shape 2,359,296 product glyphs. The current three-shard HVAR fixture
shapes 9,216 result glyphs for that matrix. Those are representation counts,
not a predicted 256-fold runtime difference; they are a reason to require a
real-width screen before promoting a small static-width win.

## 2. Connect a working real MLP before inventing another matrix engine

An existing [real block-0 MLP component](../avar2-gelu-linear-hvar-full-mlp/RESULTS.md)
already computes 768 inputs → 3,072 hidden values → 768 outputs. It applies
piecewise GELU once per hidden coordinate inside a variable font, then shares
that transformed coordinate across the projection outputs. Its recorded local
median is 251 ms on four real input states, with output RMSE 0.0203–0.0249.
It still exposes 3,072 preactivations through geometry. It is not a complete
transformer block, and those local figures cannot be extrapolated to token time.

The useful new experiment is integration: drive that component from the current
native normalized-input producer and consume its output in the real residual/
next-stage path. Exercise multiple layers and fresh generations. Compare all
coordinates with the current implementation and the independent reference.
Do not supply precomputed intermediate vectors except in explicitly labeled
diagnostic controls.

Require a matched component improvement with its consumer attached before
running twelve layers. Then compare several continuing tokens, not only a
capacity-two terminal interval, with the same context capacity and fresh browser
repetitions. Stop if the extra ownership and generation machinery consumes the
local saving. This is a test of a known working mechanism in a new context,
not a claim to have just discovered that mechanism.

## 3. Keep old values in their rendered form across layer switches

The model already retains K/V numbers and already shares font settings. The
unresolved issue is lifetime: a reused attention surface switches layers, so
the browser can lose the useful rendered representation of a previous layer's
unchanged values. Earlier full-model tests did not establish that width reuse
survives this switching cheaply.

Test persistent rendered-value banks with two, four and twelve layer owners.
Replay the same per-layer query and K/V history in both compared designs, and
only append each layer's new token's K/V;
existing value widths must remain intact. Compare against the reused surface
with the same values and history. Measure total update latency and renderer
memory, including delivery, selection and completion. A test which externally
freezes or injects the cache is a diagnostic ceiling, not a usable implementation.

This trades memory for saved re-rendering. The 32-token baseline already used
about 5.2 GiB of sampled renderer memory, so duplicate banks may be unacceptable.
Stop if selection invalidates inactive owners, if generation checks fail, or if
memory cost prevents practical scaling. Blanket ownership and retirement have
already regressed; this is a specific persistence experiment, not another generic
"make updates local" proposal.

## Capability gates before ambitious replacements

A streaming font state machine is an appealing departure from repeated GSUB
passes. We screened downloaded AAT `morx` fonts in this turn. The standalone
engine executes the substitution, but this Chrome does not; plain and GSUB
controls pass in both TTF and WOFF2. The [support report](../aat-support-probe/RESULTS.md)
therefore stops that route before an arithmetic compiler is built. Other font
delivery paths or browsers are separate deployment experiments.

Floating-point filter surfaces and training a model to exchange compact codes
remain larger forks, not unnoticed stock-browser optimizations. The existing
[F16 study](../skia-f16-real-matvec/RESULTS.md) is standalone Skia with a tiny
ReLU slice, not Chromium/GELU inference. Existing [code-table fitting](../learned-glyph-code-screen/DISTILLATION.md)
missed its quality screen. A custom browser or jointly trained model might
change these constraints, but neither is an established solution for the current
checkpoint and browser. Repeating failed SVG bit circuits or a failed low-rank
approximation under a new name would not be a different direction.

## Keep one ladder from idea to token result

Each future candidate should record four gates: supported mechanism; correct
representation at the relevant width and precision; a complete real stage with
its consumer; and a matched autonomous model run. Use the cheapest gate capable
of rejecting it. Keep the final target measurement separate from proxy results.

In particular, do not describe a reduction in files, glyphs, passes, style events
or table references as a token speedup. Do not infer that the final reader of a
small sum represents the thousands of intermediate transfers in a model. And do
not estimate a precise fraction of token time as pure matmul while the current
stage instrumentation is missing boundaries. These measurement distinctions
are part of getting unstuck.
