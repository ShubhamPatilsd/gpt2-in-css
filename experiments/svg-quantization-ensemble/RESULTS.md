# SVG quantization ensemble

The ordinary and batch-calibrated SVG chains make complementary mistakes on the
64 natural-token suite: either chain is correct on 57 cases, although each alone
gets 34 and 52 respectively. This experiment tests whether averaging their final
768-value states recovers those complementary winners.

It does not. The midpoint average gets 48/64. Sweeping one global mixing weight
peaks at 52/64 with 98% weight on the calibrated chain, and deterministic
eight-fold cross-validation also gets 52/64. Duplicating the full chain would
therefore double runtime and assets without improving top-1 accuracy.

```sh
python3 tools/analyze_svg_quantization_ensemble.py
```
