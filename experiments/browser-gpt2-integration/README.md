# Integrating local updates into the real browser model

This follow-up turns the earlier single-head locality result into an all-head
implementation and investigates dense stages, vocabulary scoring, and native
stage transfers. The earlier investigation is preserved in
[browser-gpt2-scaling](../browser-gpt2-scaling/RESULTS.md).

The intended acceptance criterion is autonomous model execution: every real
query changes, all twelve heads participate, layers switch, cached tokens are
revisited, and the complete 50,257-row vocabulary predicts the next input token.
Component measurements are evidence for a mechanism, not a substitute for that
test or a claim of full-model speedup.

## Work under test

| Area | Concrete change | Required validation |
| --- | --- | --- |
| Attention | Separate head-owned input receivers, local retained KV banks and calculation subtrees; join all twelve current-generation outputs | All 768 context coordinates, changing all heads, multiple layers/slots, native full-model tokens and real retained KV readback |
| Dense stages | Private normalized inputs, independently materialized projection settings, invariant layer rules hoisted out of conditional blocks | Real QKV and FC/GELU/projection outputs, layer revisits, full native integration of promising variants |
| Vocabulary | Keep raw 768 head inputs on their owner; inherit the derived axis settings into the existing two scoring passes | All 50,257 candidates retained, real hidden-vector fixtures and revisits, exact reference winners, native integration |
| Transfers | Select only the previous ping-pong bank's vector while retaining both epoch/acknowledgement channels | Native layer and token progression; no broad liveness reset bundle |

The vocabulary baseline already has two inherited font-settings owners. Its new
axis bundle is not evidence that a font was previously recomputed independently
on every vocabulary row. The distinct ownership experiment removes inheritance
of 768 raw numeric properties while preserving those numbers on the input bank.

## Evidence and reproducibility

- [Unconventional execution experiments](UNCONVENTIONAL_EXPERIMENTS.md): fused
  attention fonts, glyph arithmetic, alpha-bit circuits, learned codes and F16
  filter storage, with explicit accuracy and execution-scope limits.
- [Stage cost investigation](stage-costs.md): saved measurements and a fresh
  native diagnostic, including missing boundaries and observer overhead.
- [Attention investigation](attention-report.md): component and native ownership work.
- [Dense investigation](dense-report.md): individual rewrites and real-weight tests.
- [Final integration results](RESULTS.md): acceptance results and measured comparisons.

`tools/integrate_browser_gpt2_local_updates.py` is an opt-in compiler/runner.
It composes attention, dense and vocabulary variants without editing the original
compilers. Each label creates an immutable experiment directory with source
snapshots, source/artifact hashes, exact configuration, run evidence, independent
numerical verification and a summary. Existing labels are rejected. Failed runs
remain evidence and are never replaced by retries.

Browser performance runs and heavy compilation are serialized across all agents.
No model weights or font assets are deleted or regenerated. Existing fonts are
referenced in place. Cache cleanup is allowed only outside measured runs.

Native cases receive zero post-navigation writes and contain no scripts. The
observer uses DOM/CSS/geometry reads, then independently checks actual final
activations and retained caches after generation. Per-head cache verification
merges only the fields actually read from each head's own bank; reference values
never enter that merge or the browser. Component fixtures openly supply their
inputs externally and therefore cannot establish autonomous generation.

No exclusive stage percentages are inferred from missing native boundaries.
Observed wall time includes loading and browser observation. Separate renderer
counters help distinguish reduced style work from observer or layout costs.
