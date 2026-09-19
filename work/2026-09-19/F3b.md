# F3b — Fix 3 (+ Fix 6 for the MLP hops) integrated into the 12-layer emitter: frameless fc→proj→out transport

Agent F3b, 2026-09-18/19. Work dir `work/2026-09-19/F3b/` (tools copy = F5's + `f3_chain_mlp.py`, harnesses, probe pages,
results, runs). Bundles: `bundles/smoke-F3-2L` / `bundles/smoke-TL-2L` (2-layer A/B), **`bundles/F3a`** (12 layers, MLP hops
frameless, READY), **`bundles/combined2`** (F2 + F5 + F4 + this, READY). Log: `F3b.log.md`. Nothing under repo `tools/` or `experiments/`
was modified; no commits. All Chrome runs under `CHROME.lock` (Chrome 153.0.8010.48 headless, AC).

## 1. What was integrated (step 1)

| file (tools copy) | change |
|---|---|
| `F3b/tools/f3_chain_mlp.py` (new, 250 lines) | `mlp_chain(layer, qfc, bfc, qproj, bproj) -> (html, per_layer_css, once_css)`: one layer's fc (768→3,072, GELU) and proj (3,072→768, +r) as anchor → `position:fixed; container-type:size` chains. Env flags `F3_CHAIN_MLP` (default 1; 0 = timeline `matvec()`), `F3_CHAIN_LEVEL` (1 = one element per level, default; 2 = Prototype A/B shape for the fc chains). |
| `F3b/tools/browser_gpt2_reused_core.py:106-110, 137-141, 157-165` | `compile_reused`: `kind == "fc"` → `f3.mlp_chain` (once-CSS emitted for layer 0, per-layer CSS still goes through `specialize()` → `@container corestate style(--layer:L)`); `kind == "proj"` → `layouts["proj"] = "{child}"`; with the chain the `isolate_metrics` / `global_projection` proj ablations are ignored (they only shaped the timeline proj matvec; F2's tools default `--global-projection` to True). |
| `F3b/tools/browser_gpt2_reused_adapter.py:149-151, 219` | F5's inline `var(--epoch)` reader count 7 → 5 (the fc and proj generation markers no longer exist); manifest `f3ChainMlp`, `f3ChainLevel`, `f3ChainContainers` (1,926), `f3ChainAnchors` (12,300). |

Transport per layer (tree order = data-flow order; the HTML is identical for all 12 layers, per-layer constants in the layer rule):

```
.f3-mlp                               --range-fc = max|n2|·1.001 (common ancestor)
  .f3-stage.f3-fc                     fixed, visibility:hidden; 3,072 rows <i class=f3-row style="anchor-name:--f3f{i}"> with the
                                      3 fc shard glyphs (fallback fonts b{L}fcS0..2: the row width is the sum of the 3 advances);
                                      font-variation-settings = 768 axes calc(var(--n2-i)/var(--range-fc))          [once]
  12 × fc chain j                     #f3c{j}-0 … #f3c{j}-127: fixed size containers, width/height = anchor-size(--f3f{256j+2k},{+1});
                                      container k+1 publishes container k's values:
                                        --hidden-i: --gelu(calc((100cqw / 1px * 1000/512 − base_i) * scale_i * var(--range-fc) + bias_i))  [per layer]
    #f3r{j}                           chain bottom (in-flow): --range-proj = max|hidden shard j|·1.001; <i id=f3m{j} anchor-name:--f3m{j}
                                      width:calc(var(--range-proj)*1024px)>; .f3-stage #f3s{j}: 768 proj glyph rows of shard j
                                      (font b{L}projS{j}, 256 axes calc(var(--hidden)/var(--range-proj))), anchor-name --f3p{j}_{i}
  out chain                           #f3g0..5 read --f3m{2t},{2t+1} → --f3pr{j} = 100cq/1px/1024 (the 12 shard ranges);
                                      #f3o0..383: width = calc(Σ_j anchor-size(--f3p{j}_{2k} width) * var(--f3pr{j})) (height: 2k+1);
                                      --out-i: calc(var(--r-i) + (100cq / 1px * 1000/512 − Σ_j base_{j,i}·var(--f3pr{j})) * scale_i + bias_i)  [per layer]
    #f3b                              bottom (in-flow) publishes --out-766/767 and hosts {child} (reused-output, loop banks, export)
```

Rules from F3.md obeyed and checked at build time by `F3b/lint_f3b.py` (depth < 512, all 12,300 `anchor-size()` references
resolve to a unique anchor earlier in tree order and in an earlier out-of-flow root, no position/contain/transform/filter/
will-change/overflow on the 36 ancestors of `.f3-mlp`, counts, no leftover fc/proj receipts/gates/timelines). The fc/proj
receipts + `content-visibility` gates are gone (Fix 6 for these hops: nothing to separate, the whole ln2→out path resolves in
one lifecycle once the attn gate opens); the qkv/ctx/score/attn gates and the loop-bank latch for the layer→layer hop are kept.
GELU stays the emitter's `--gelu()` @function (F2's inline variant is not ported).

**Why one element per level.** Prototype A/B used container + plain child per level (2 elements). The out chain must put all
768 `--out-*` on ONE element (the loop banks read them from one ancestor), i.e. 390 levels: with 2 elements per level that is
780 elements below depth 37, past the 512 parser cap. With the next container itself declaring `--v:calc(100cqw/1px)` (cq units
resolve against the nearest *ancestor* container) the out chain is 391 elements deep (max document depth 434). Validated first
with the standalone probe (§2a), then in the bundles.

## 2. Smoke (step 2): 2 layers, capacity 2, chain (`smoke-F3-2L`) vs timeline (`smoke-TL-2L`, same tools, `F3_CHAIN_MLP=0`)

### 2a. Level-1 chain probe (`F3b/gen_probe_level1.py`, `F3/proto_run.mjs`, 2 trials each; `F3b/results/probe-level1.txt`)

| page | containers (values) | exact after mutation | UpdateLayoutTree (elements) | Layout | commits | Layout ms |
|---|---:|---:|---|---:|---:|---:|
| l1-D384 (out-chain shape, in-flow anchors) | 384 (768) | 768/768 | 1 (772) | 1 | 1 | 21.7–23.1 |
| l1-D384-fixedsrc (anchors inside a fixed `.stage`) | 384 (768) | 768/768 | 1 (772) | 1 | 1 | 15.4–20.2 |
| l1-D128 (fc-chain shape) | 128 (256) | 256/256 | 1 (260) | 1 | 1 | 4.6–6.5 |

### 2b. Bundle A/B (`F3b/run_bundle.mjs` with a light trace, poll 1 s; `F3b/runs/smoke-*/`)

Both: ids **[11, 3387] = reference** (`verify_browser_gpt2_runtime.py`: tokenAgreement [True, True]); chain finalResidual rmse 1.06e-3,
max 7.9e-3 vs the NumPy reference.

| token | variant | UpdateLayoutTree (ms) | Layout (ms) | commits (frames) | main-thread busy ms | Performance.getMetrics Δ Recalc / Layout |
|---|---|---:|---:|---:|---:|---|
| 1 (2 layers + font load) | timeline | 39 (5,639) | 25 (1,973) | 22 | 10,584 | 43 / 25 |
| 1 | **chain** | 36 (3,600) | 22 (4,991) | 21 | 11,006 | 5,818 / 22 |
| 2 (2 layers, steady) | timeline | 24 (2,259) | 13 (1,545) | 13 | 6,452 | 27 / 13 |
| 2 | **chain** | **16** (904) | **8** (2,847) | **10** | **5,398** | 1,945 / 8 |

Per layer (token 2): style passes 12 → 8 (−4 = the fc and proj timeline passes + their two gate unlocks), layouts 6.5 → 4,
frames 6.5 → 5 (the MLP hops contribute 0 frames; the remaining ones are qkv / score / ctx / attn and the loop latch), main
thread −16 %. The chain trades ULT time (−1.36 s / 2 layers) for interleaved Layout time (+1.30 s / 2 layers ≈ 340 µs per
container, 1,926 containers per layer — the per-container cost is the interleaved recalc of a `--gelu()` call or a 12-term
`anchor-size()` sum, cf. F3.md §3b 200 µs on battery). `RecalcStyleCount` now counts every interleaved container recalc
(≈ +1,926 per MLP evaluation), so it is no longer a pass count for chain bundles; use LayoutCount and traced UpdateLayoutTree.

## 3. Full bundles (step 3): `bundles/F3a` and `bundles/combined2`

Builds (BUILD.md in each bundle has the exact command and `diff -ruN` of the tools copy vs `tools/`): F3a 6.7 s / 3.0 GB peak,
combined2 9 s / 2.5 GB; no fonts rebuilt. Offline: `lint_f3b.py` OK for both; font witnesses identical to F5 / combined (the
chain reads the original per-shard proj fonts instead of F2's global-projection retags — same advances); static allowlist check
passes (278.3 MB / 277.6 MB, no JS). Page deltas vs F5 / combined: inline `view-timeline` 10,858 → 7,016, `timeline-scope`
53 → 29, `animation-timeline` 242 → 122, `anchor-name` 464 → 12,764, 1,926 `container-type:size` elements, runtime.css
34.7 → 31.2 MB (combined: 40.8 → 30.4 MB), index.html +0.35 MB, max nesting depth 434.

### 3a. F3a passive correctness run (`F3b/runs/F3a/`, `F3b/results/F3a.txt`; 5 s poll, NOT a timing run)

- **ids 11,314,1101,7926,11,475,314,1101 = 8/8** (`verify_browser_gpt2_runtime.py`: tokenAgreement all True, originalFloatAgreement all
  True, text "Hello, I'm sorry, but I'm"); finalResidual rmse 1.42e-2 / max 0.107 vs the NumPy reference (F5 run: same order);
  finalHeadMatchesActualInput true; 96/96 KV cache slots read back.
- token capture times (s since Run, cumulative): 36.9, 64.7, 98.1, 131.1, 165.2, 205.7, 242.2, 277.6 → ≈ 34 s/token at a 5 s poll
  (F5's correctness run under the same protocol: 32.6–45.6 s/token).
- `Performance.getMetrics` per token: **LayoutCount +99, 75, 87, 79, 85, 99, 85, 71 (680 for 8 tokens = 85/token; F5: 872/8 = 109/token,
  i.e. −24 layouts/token = the 2 layouts × 12 layers of the fc/proj timeline hops)**; RecalcStyleCount +27,126 … +19,377 per token —
  ≈ 1,926 interleaved container recalcs × 12 layers plus the remaining ≈ 120 style passes (the counter is no longer a pass count, see §2b);
  RecalcStyleDuration 94.1 s and LayoutDuration 121.8 s over the whole run (F5: 150.1 s / 49.5 s) — style −56 s, layout +72 s: the
  interleaved chain layout is where the MLP now costs, so the net effect on s/token is B0's call.
- `bundles/F3a/READY` created.

### 3b. combined2 passive correctness run

(`F3b/runs/combined2/`, `F3b/results/combined2.txt`; 5 s poll, NOT a timing run)

- **ids 11,314,1101,7926,11,475,314,1101 = 8/8** (tokenAgreement / originalFloatAgreement all True, text "Hello, I'm sorry, but I'm");
  finalResidual rmse 1.60e-2 / max 0.137 vs the NumPy reference.
- token capture times (s since Run, cumulative): 40.4, 77.7, 116.0, 154.1, 193.7, 233.9, 274.0, 313.1 → ≈ 39 s/token at a 5 s poll.
- LayoutCount +99, 85, 85, 85, 85, 85, 85, 71 (680 for 8 tokens = 85/token, identical to F3a — the count is set by the transport, not
  by F2/F4/F5); RecalcStyleDuration 109.5 s, LayoutDuration 137.2 s over the run.
- Harness caveat: `run_bundle.mjs` reads the unpacked bank/head shape; with F4's packed head `--h*` is not readable and the packed KV
  lists were not parsed, so before `verify_browser_gpt2_runtime.py` the head input was derived offline as LN_f(browser finalResidual)
  and the cache list emptied (noted in `verification-vectors.json`); ids and finalResidual are the browser's own values. The first
  verify attempt (nulls) is the `verify rc=1` line in `F3b/results/combined2.txt`.
- `bundles/combined2/READY` created.

## 4. Not done / residual risks

- **Attention hops (step 4)** — not attempted: per-head QKV / score / ctx / attn columns are a rewrite of `attention()` and of the
  KV-bank nesting that F4 just packed (F3.md §4/§5 #6); the MLP hops were integrated first as recommended. The remaining
  per-layer frames are the 5 attention/loop hops.
- **Layout cost of the chains**: ≈ 340 µs per container in the bundle (2× Prototype B). Candidates: F2's inline GELU instead of the
  `--gelu()` @function on 3,072 publishers per layer, fewer terms in the out-chain widths (pre-summing shard pairs), resetting dead
  inherited scratch (`--x/--n1/--qkv/--ctx`, `--fr-*` aliases) at `.f3-mlp` to shrink the inherited maps below it.
- **Memory**: +1,926 fixed containers + 12,300 in-flow anchors per page (one layer's worth, the graph is reused). Expect on the order
  of +70–150 MB RSS (F3.md §2b: ≈ 35 KB per positioned container); B0's RSS column decides.
- **Ordering lint** is structural (tree order + out-of-flow roots); it does not model Chromium's acceptable-anchor rule beyond
  "no containing-block-forming property on an ancestor". Any future wrapper with `contain`, `transform`, `position:relative/absolute`
  or a permanently `content-visibility:hidden` ancestor around `.f3-mlp` silently zeroes the MLP.
- **LN partial sums**: not needed for the MLP (`--n2` is computed above the chains, `--r` is inherited); they become necessary only
  when the attn→r hop is made frameless (768 values across chains feeding LN2).
- `RecalcStyleCount` semantics changed for chain bundles (§2b); B0's per-pass histograms from the trace are unaffected.
