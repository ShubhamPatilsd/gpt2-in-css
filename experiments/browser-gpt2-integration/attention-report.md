# Detached attention owners for all twelve heads

The new attention compiler implements twelve separate input registers, twelve sets of real layer/slot KV banks, and twelve QK/softmax/value calculations. Two real-font component processes passed six total generations, including switching layers, appending a second slot, returning to an earlier layer, and poisoning all upstream QKV coordinates after completion. The separate native integration driver also passed a two-layer/two-token model with zero post-navigation writes. Twelve-layer integration and comparative performance require their own runs.

## Implementation and integration interface

The implementation is [browser_gpt2_owned_attention.py](../../tools/browser_gpt2_owned_attention.py). Original compiler files remain unchanged. Compile-time installation is:

```python
from browser_gpt2_owned_attention import install_native_attention, collect_cache_layer

with install_native_attention(value_layout="widths") as owned:
    # Invoke the existing native runtime compiler normally.
    # It must select the reused core and font-vector cache.
    ...
    attention_metadata = owned.artifact.metadata

# Read actual stored values from all twelve separate banks for one layer.
fields = collect_cache_layer(cdp, layer, capacity)
```

The context manager temporarily replaces the font-vector attention factory and the reused adapter's imported `compile_reused` function. It places the input producer immediately under the existing `.shared-qkv-gate` and checks that exact placement. It prepends detached consumers before the existing `.loop-reader`. The adapter then wraps both as siblings in `.core-block`.

This is a structural boundary: the attention consumers are outside the loop reader, recurrent input registers, QKV decoder, and dense numeric ancestry. The only required common input control is the desired `--native-pass` epoch. The producer still uses the existing QKV generation gate; it does not publish merely because the desired epoch changed. The full-runtime driver's generated ancestry audit is the final check of this placement in the complete document.

```text
.core-block                            desired --native-pass
├── .oa-consumers
│   ├── .oa-head-0
│   │   └── input timeline reader
│   │       └── held 192-coordinate QKV + epoch/position/layer register
│   │           ├── head 0's nested layer/slot KV banks
│   │           │   └── QK → score receipt → softmax/value rows
│   │           └── output receipt + native capture flag
│   ├── ... same ownership for heads 1 through 11
│   └── all-twelve-head generation join → original context marker
└── .loop-reader
    └── existing recurrent/dense stages
        └── .shared-qkv-gate
            ├── .oa-source              2,340 native geometry inputs
            └── existing context receiver and following dense stages
```

The source carries 64 Q, 64 K, and 64 V coordinates plus epoch, position, and layer for each head: 2,340 geometry channels. Each head reads only its own 195 channels. Centered timeline decoding uses the same inverse geometry construction as the earlier native commit probe. The input bank opens only when the incoming epoch equals the desired epoch and that head has not already captured the generation.

Each head has private `--fc-k/v/ks/vs-S-H` stored fields for every slot at every layer. Active-layer aliases expose only that head's fields to its computation. Whole-font K/V axis lists and scales are retained with native delayed transitions; K/V are not static fixture constants. QK uses the real bilinear font. Softmax is CSS arithmetic. The `widths` value path retains the old value glyph's settings and applies the changing weight to its measured width. Each owner publishes 64 coordinates directly onto the existing 768-coordinate context bridge.

Completion has three stages: the current input generation must reach the score source; the value source must publish the current generation; then a CSS-animation/SMIL receipt captures that head's input bank. A committed head marker is emitted only for its current desired generation and held state. The aggregate consumes all twelve markers and emits the original context generation marker only when every marker matches. A desired-epoch change makes all old markers insufficient. This is a generation protocol, not an independent numerical residual check: output correctness still requires validation in the full native scheduler.

`collect_cache_layer` queries `.oa-bank-H-L` for every head and merges only that head's own original field names. It does not create a fake combined bank or copy diagnostic values into the page. Existing cache decoding can therefore inspect the real retained fields without changing storage ownership.

Current explicit bounds: full causal cache, positive layer/slot counts, and `runs` or `widths` values. Rolling windows, sinks, and prewarming raise an error. The native helper allocates capture signals for `layers × capacity` generations; the component fixture explicitly allocates one extra generation for a revisit. This is a bounded native document, as in the existing runtime.

## Executed component checks

[probe_browser_gpt2_owned_attention.py](../../tools/probe_browser_gpt2_owned_attention.py) generates a script-free document with CSP `script-src 'none'`. The harness uses CDP DOM/CSS methods, not JavaScript evaluation. It supplies QKV externally; it does not claim autonomous transformer production of those vectors. Each case has its generated HTML/CSS, input vectors/oracle outputs, exact measured source copies, SHA-256 hashes, browser version, individual head errors, cache errors, and completion tags.

| Case | Generations | Result | Worst 64-coordinate head RMSE | Worst retained K/V RMSE |
|---|---:|---|---:|---:|
| [One layer, one slot](attention/smoke-l1-c1-widths/results.json) | 1 | Pass | 0.000430 | 0.0000107 |
| [Two layers, two slots, revisit](attention/attempt1-l2-c2-widths/results.json) | 5 | Pass | 0.001164 | 0.0000112 |

Both processes used Chrome 153.0.8010.48. The context tolerance was RMSE < 0.005 per head; retained K/V used the same threshold. Every head's committed tag equaled the requested generation at every checked output.

The larger sequence was:

1. Layer 0, slot 0, generation 1.
2. Layer 1, slot 0, generation 2.
3. Layer 0, slot 1, generation 3.
4. Layer 1, slot 1, generation 4.
5. Return to layer 0 at slot 1 with a changed query, generation 5.

The numerical oracle uses each layer's actual prior K/V vectors. After every generation, the harness decodes all populated slots from every populated layer, including inactive layers. Every one of the twelve Q groups, twelve K groups, and twelve V groups changes between successive supplied vectors; the raw record includes each group's maximum absolute change. The final revisit changes the layer-0 query relative to its earlier input while retaining that layer's existing K/V.

After the final commit, a separate poison check replaces all 2,304 upstream QKV coordinates without advancing the generation. It reads every incoming reader and every held input bank, as well as the context output:

| Poison check, two-layer case | Worst RMSE |
|---|---:|
| Incoming readers versus actual new poison vectors | 0.00000877 |
| Held input banks versus the original committed vectors | 0.0000108 |
| Context versus the original attention result | 0.000298 |

All twelve incoming readers saw the poison, all twelve held banks retained the original input, and all twelve completion tags stayed at generation 5. This demonstrates retention after capture rather than merely an unchanged upstream source.

The one-generation smoke uses one post-navigation external write, for poisoning. The five-generation case uses nine: two DOM attribute updates per transition (complete producer snapshot, then desired epoch), plus one poison update. JavaScript is absent from both harness and page, but these are externally advanced component tests. Zero post-navigation writes in the integrated model are established separately below.

## Native two-layer integration

The root driver's [owned two-layer/two-token run](native/owned-b2c2-r0/integration-summary.json) completed successfully with zero external writes after navigation. Its two tokens, 11 and 3387, exactly matched the quantized reference. Final residual RMSE was 0.0020434; actual retained K/V readback passed for all four layer/slot pairs, with maximum RMSE 0.0014297. Observed total time was 29.56 seconds, including native startup; the observed warm token interval was 10.82 seconds. These are single-case observed timings, not a speedup claim.

This connects the owned attention to real native dense QKV production, the original context receiver, following dense layers, vocabulary computation, and token advance. It validates autonomous operation for this two-layer/two-token schedule. It does not establish twelve-layer correctness, long-context scaling, or independence from all observation effects.

## What this establishes and what remains unmeasured

The earlier locality fixture isolated one changing query head against static KV. This implementation instead moves all twelve owners out of dense ancestry, transfers all Q/K/V inputs through native geometry, stores real per-layer/per-slot K/V in each owner, produces all 768 context values, and joins all heads by generation. The component validates two layers and two slots with multiple changes and a revisit. The native two-layer run validates autonomous dense-to-attention-to-dense feedback at that size; twelve-layer coverage remains a separate integration case.

These checks include repeated computed-style observation while waiting for stable output, font waits, and cache diagnostics. Their elapsed times are not fair throughput comparisons. There is no timing claim against the old attention implementation. The boundary adds 2,340 input geometry channels and twelve commit pipelines; those costs may outweigh reduced inherited style work at small contexts. The native run must determine correctness, scheduler behavior, and net performance.

Per-head completion covers the source generation and capture state. The component's stable-read criterion helps detect transient output but cannot prove that the full native downstream gate never samples an earlier transient. The producer's placement under the existing QKV ready gate and the shared geometry layout of data/markers are architectural safeguards. The native numerical result supplies executable evidence for its tested schedule; initially unobserved and longer native runs provide stronger checks of scheduler behavior.

All successful component results and measured source bytes are retained. Neither browser attempt failed. After both processes completed, imports were sorted and the probe's execute bit was set; no computational statements or generated CSS changed. Ruff and Python syntax checks pass on both current source files. The source copies inside the raw cases retain the exact pre-cleanup bytes used for those measurements.
