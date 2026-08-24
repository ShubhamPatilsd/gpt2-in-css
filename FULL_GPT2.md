# Scaling the CSS circuit to GPT-2 small

The repository reaches a real pretrained GPT-2 checkpoint in
[`pretrained/`](pretrained/): `sshleifer/tiny-gpt2`, with two transformer
layers, the original 50,257-token GPT-2 vocabulary, and a complete CSS argmax.
Chromium reproduces its Python reference predictions with no runtime
JavaScript.

The standard `openai-community/gpt2` checkpoint (GPT-2 small, approximately
124M trainable parameters) was also downloaded and evaluated with NumPy. For
the one-token prompt `Hello`, its greedy next token is token 11, `","`.

## Measured scale boundary

Run the analysis with:

```sh
make analyze-full
```

For one next-token inference at context length one:

| Component | Multiply-accumulate terms |
|---|---:|
| 12 transformer blocks | 84,953,088 |
| 50,257-token language head | 38,597,376 |
| Total | 123,550,464 |

After the optimizations in [`OPTIMIZATIONS.md`](OPTIMIZATIONS.md), the
equivalent fixed-prompt graph needs approximately **229,365** typed custom
properties. A reusable `@function` now keeps GELU's five internal temporaries
local instead of registering them for every feed-forward unit. The fixed
prompt page also compares the maximum only with tokens that can win for one of
its selectable inputs. A general full-vocabulary argmax would need about
**279,621** properties.

Typed properties remain necessary in this design: experiments showed that
unregistered properties recursively substitute their complete expression text
until the browser invalidates the expanded graph.

Using the checkpoint's actual serialized weight lengths, the projected source
size is:

- approximately **3.16 GB** with aggressively shortened property names;
- approximately **6.12 GB** with readable generated names;
- approximately **6.3–30.6 GB** of browser working memory at a conservative
  2–5× source-size multiplier.

Each statically unrolled generated token adds another transformer computation
graph. Longer contexts also add causal-attention work and state.

## Conclusion

The remaining issue is not a missing neural-network operation. This project
has browser-verified CSS implementations of matrix-vector products, ReLU,
layer normalization, causal softmax attention, GELU, residual connections,
tree-reduced argmax, discrete token selection, and autoregressive feedback.

The blocker is representation and browser capacity: CSS has neither reusable
tensor storage nor a parallel matrix primitive, so every scalar product term
must still be materialized as source.
Loading a multi-gigabyte stylesheet with hundreds of millions of arithmetic
terms would risk exhausting browser and system memory, and would not be a
credible working artifact.

Reaching GPT-2 small operationally would require relaxing the runtime
constraint—for example, JavaScript with WebGPU/Wasm—or adding tensor and loop
primitives to CSS. Under the strict HTML+CSS-only runtime constraint, the real
pretrained tiny checkpoint is the largest verified end-to-end result in this
repository.
