# R4V — why combined4-c32c's per-position slope "doubled" on prompt 40: not the trajectory, but memory state (GC/purge cadence) acting on a garbage rate that grows with the filled positions

Agent R4V, 2026-09-21 03:26–. Work under `R4V/` (`trajectory_counts.py/.json/.log`, `rss_gc_cadence.py/.json`, `memorystatus_log.txt`,
`kernel_pressure_log.txt`, `bench_native_r4v.mjs`, `run_trace.sh`, `run-combined4-c32c/`). Log `R4V.log.md`. No repo `tools/` or `experiments/` edits, no git.
Offline NumPy work used `browser_gpt2_core.reference_sequence` from `R4D/tools` (uv, as R4C did), nice 19, 2 threads, `CPU-BUSY-R4V` marker (compute time ≈ 4 s).

## 0. Headline

- **The page instantiates exactly the same number of distinct font instances, KV lists and changed glyph widths on both trajectories** (§1): per step k, 144·k
  score instances (0 repeats from earlier steps on either prompt, at 6, 4 and 3 significant digits), 144·k live V-leaf instances in the `widths` layout (144 new
  per step, all distinct), 0 repeated K or V lists (384/384 and 4,608/4,608 distinct at 3 sig. digits; the closest repeated-token K lists differ by ≥ 0.50 in
  normalised units), and 96–99 % of filled V leaves move by ≥ 1 LayoutUnit on both prompts. The Hello loop is not "more cacheable": its attention is even slightly
  less peaked (mean entropy k≥8: 1.54 vs 1.38 nats). The quantities the puzzle proposed cannot produce a 1.9× style / 1.5× layout slope ratio.
- **What does differ is the renderer's memory state.** In the Hello run RSS grew monotonically 1.7 → 7.2 GB over tokens 1–16 with no release (no drop > 250 MB
  until token 27); in the prompt-40 run RSS peaked at 5.0 GB by token 6 and then fell steadily to 2.8 GB. The per-k excess of p40 over Hello tracks the per-k RSS
  deficit with **r = −0.88** (style −0.78, layout −0.69), and one pooled law `time = a + b·k + c·RSS` fits BOTH runs (wall rmse 4.87 → 1.50 s; the residual
  trajectory×k term is +0.22 s/token/position, i.e. ≤ half the raw slope gap and within run-to-run noise). Across all seven widths-family capacity-32 runs the fitted
  slope falls monotonically with mean RSS (r = −0.84); the combined7-c32 pair even reverses (Hello slope 1.07 > p40 0.99 with p40 at lower RSS and higher intercept).
  `ThreadTime/wall` is 0.92–0.99 in every run, so the excess is main-thread CPU, not contention; off-main-thread CPU rises from 0.22 (Hello) to 0.31 (p40) to 0.43
  of wall in the slowest run — concurrent GC helpers. The kernel log shows `memorystatus` reclaiming memory (idle-exit kills, compressor active) at 03:14:07–13,
  i.e. during p40's tokens 16–17 where its RSS started dropping and its excess accelerated; nothing comparable in the Hello window (00:29–00:44). 16 GB machine.
- **Mechanism (evidence-weighted, §2)**: every style pass re-substitutes and re-parses a 65-axis `font-variation-settings` list into each of the 768·p filled V
  leaves (plus a 768+64-axis list into 12·p score glyphs); the Hello run's untouched RSS growth measures this garbage at **40 MB per filled position per token
  (≈ 650 B per filled leaf per style pass)**, so allocation per token grows ∝ p while the live heap stays ≈ constant. GC/purge work per token is therefore
  ∝ p × (GCs per byte allocated); the second factor is set by the machine's memory state (Oilpan/PartitionAlloc reclaim, Chrome's memory-pressure listener
  purging font/shape caches and forcing GCs), not by the prompt. Under pressure each purge also evicts the 144·p V-font instances and their shape results, which
  must be recreated on the next layer — a second ∝ p term. This reproduces: equal intercepts (p=1 garbage is small), slopes varying 0.65–1.14 s/token/position
  between runs of the same bundle with identical pass counts, style AND layout growing together (Oilpan GCs run inside the allocating phase), RSS anti-correlated
  with time within and across runs.
- **Trivial explanations (§3)**: none. Prompt 40's "\n" tokens only change a fixed-position `<output>` rendered by `counter(tokenN, gpt2-vocabulary)` (per-token
  constant; the intercepts are identical 4.37/4.46 style, 2.65/2.66 layout); the head path has no per-position work; pass counts are identical.
- **Trace (§4)**: one short traced prompt-40 run was queued behind R4T/B5 under `CHROME.lock` (`R4V/run_trace.sh`, 10 tokens, `blink_gc`+`fonts` added, 400 MB
  buffer). See §4 for the outcome; R4C has no Hello trace to compare against (R4C.md only proposed one).
- **Fix (§5)**: the exact, id-preserving fix is to cut the ∝ p allocation, not to quantise values: (1) stop re-parsing the V list per leaf per pass —
  the 64 leaves of one (head, slot) each parse the same 65-axis list; (2) run the demo without the `--js-flags=--heap-growing-percent=10` arm and with memory
  headroom (nothing else large resident; the trace/CDP harness itself adds pressure); (3) the structural version is the `fallback` value layout (one
  `font-variation-settings` per head wrapper with per-slot tags, leaves var()-free). Predicted for the prompt-40 demo: matching the Hello run's memory state alone
  gives ≈ 760–800 s (−200…−250 s, −20…−25 %) — the pooled law's prediction for p40 at Hello's RSS trajectory; the allocation fix would make the slope
  state-independent and is worth a further ≈ −0.15…−0.3 s/token/position (exactness: unchanged numerics, since only where the list is parsed changes).

## 1. Offline counts (Q1) — `R4V/trajectory_counts.py`, output `.json/.log`

Method. `reference_sequence([prompt]+ids[:31], 12)` gives per-layer q/k/v for the 32 positions of each trajectory (Hello ids = `R4C/reference_ids_32.json`,
p40 = `R4P/reference_ids_32_40.json`; both free-running = teacher-forced). The emitter's exact expressions were reproduced from `R4D/tools/browser_gpt2_font_vector_cache.py`:
K/V/query lists are `qkv / max(1e-6, max_i |qkv|)` per head (:233–272), written as 6-significant-digit numbers (Blink's `<number>` serialisation into a `*`
list — project observation `browser_gpt2_core.py:145`; 4 and 3 digits also tried); score instance = packed 768-axis K list of slot S + 64-axis query of head H
(:380); V-leaf instance (widths) = 64-axis V list of (S,H) + `"P000" 1` (:498/:514); `--fw-H-S = exp(fs−max)·vs_S/max_S vs` (:420–431, :470); leaf width =
`12320.768 + 12288·V_i·fw` px snapped to 1/64 px (:500, operators.json base 12032/coef 12000 at 1024 px/1000 upem); score width `262144 + 128·score` px (:381).
The reference is float64 while the page reads LayoutUnit-quantised values — this only matters for exact collisions, which are 0 at every grid tried.

| per step k (both trajectories unless noted) | count | repeats from earlier steps |
|---|---:|---:|
| (a) score font instances (12 layers × 12 heads × k slots) | 144·k (k=32: 4,608) | **0** on both prompts (sig 6/4/3) |
| (b) V-leaf instances, `widths` layout (constant per layer/slot/head) | 144·k live, all distinct; 144 new per step | the 144·(k−1) older ones are re-used only if Blink still holds them (see §2) |
| (b') V-leaf instances if the `runs` layout were used (list + `"P000" fw`) | 144·k per pass | 3,145 (Hello) vs 3,135 (p40) of 76,032 over the run — the `fw = 1` max-slot cases, identical on both |
| (c) K lists written (12/step), V lists (144/step), queries | 12 / 144 / 144 | **0 / 0 / 0** on both (384/384 K and 4,608/4,608 V lists distinct at 3 sig. digits) |
| repeated-token pairs in context | Hello 24, p40 7 | closest K-list pair differs by max|ΔKn| = 0.50 (Hello) / 1.05 (p40): position embeddings make repeats impossible, as suspected |
| filled V leaves whose snapped width ≠ base (weight moves the glyph ≥ 1/64 px) | 4,773,745 / 4,866,048 (Hello, 98.1 %) vs 4,742,598 (p40, 97.5 %) | — |
| leaves whose snapped width changes between consecutive layers | ≈ 99.7 % on both | — |
| (L,H,S) with fw ≥ 1e-4 at k=32 | 4,178 (Hello) vs 4,148 (p40) of 4,608 | — |
| attention entropy (mean over layers/heads, k ≥ 8) | 1.54 nats (Hello) vs 1.38 (p40); effective slots at k=32: 8.8 vs 7.6 | Hello is *less* peaked |
| `--fw` values identical between consecutive layers (would make a leaf's style equal) | 135 vs 132 (of 4.7 M) | — |
| distinct token ids in the 32-token context | 15 vs 26 | affects only the embedding lookup (per-token constant) |

So per k both trajectories instantiate 144·k score fonts (new), 144·k V fonts (12·k of them "current" per layer), 768·k moving leaves and 12·k moving score
glyphs — identical to within 1 %. No quantity here can give the measured 1.9×/1.5× slope ratio.

## 2. What matches the slope ratio (Q2): memory state, not counts — `R4V/rss_gc_cadence.py`

Per token from the harness JSONs (1 Hz `ps` RSS of the renderer, CDP `ThreadTime`/`ProcessTime`/durations):

| run | total s | slope s/tok/pos (style/layout) | mean RSS MB | drops >250 MB per token | ThreadTime/wall | other-thread CPU/wall | r(per-k residual, RSS) |
|---|---:|---|---:|---:|---:|---:|---:|
| c32c Hello (R4D) | 758.7 | 0.646 (0.299/0.270) | 5,916 | 0.5 | 0.98 | 0.22 | −0.81 |
| c32c p40 (R4M) | 1,008.6 | 1.129 (0.566/0.415) | 3,734 | 1.7 | 0.94 | 0.31 | −0.14 |
| combined6-c32 Hello | 872.7 | 0.933 (0.382/0.443) | 4,700 | 1.8 | 0.96 | 0.26 | −0.89 |
| combined6-c32 p40 | 936.6 | 1.051 (0.524/0.411) | 4,383 | 2.8 | 0.95 | 0.28 | −0.72 |
| combined7-c32 p40 (run A, first) | 1,050.1 | 1.020 (0.437/0.466) | 2,945 | 1.6 | 0.92 | 0.43 | −0.30 |
| combined7-c32 Hello (run B) | 929.7 | 1.069 (0.555/0.384) | 3,848 | 2.3 | 0.94 | 0.36 | −0.42 |
| c32b Hello (R4D) | 905.9 | 0.888 (0.346/0.428) | 4,896 | 3.0 | 0.95 | 0.26 | −0.83 |
| c32 Hello (R4C, runs layout) | 1,132.9 | 1.141 (0.485/0.538) | 3,682 | 3.9 | 0.95 | 0.31 | −0.77 |

- Cross-run: corr(slope, mean RSS) = **−0.84** over the seven widths-family runs; within runs, tokens with RSS below trend are slower than trend (r −0.7…−0.9 in 5 of 8).
- The two c32c runs at equal k: `Δwall(k) = p40 − Hello` is −1.8…+2.0 s for k ≤ 7 (RSS equal: both 3.7–5.2 GB) and diverges from k=8 exactly as p40's RSS
  starts to fall (ΔRSS −1.0 GB at k=8 → −3.6 GB at k=18; Δwall +3.6 → +10.8 s); corr(Δwall, ΔRSS) = −0.88, corr(Δstyle, ΔRSS) = −0.78, corr(Δlayout, ΔRSS) = −0.69.
- Pooled fits (both runs, k=2..32): style `k only` rmse 2.96 → `14.3 + 0.404·k − 1.91·RSS_GB` rmse 1.43; layout 1.74 → `7.9 + 0.328·k − 1.02·RSS_GB` rmse 1.05;
  wall 4.87 → `30.3 + 0.836·k − 3.42·RSS_GB` rmse 1.50. Adding a trajectory×k term leaves +0.105 (style), +0.075 (layout), +0.22 (wall) s/token/position —
  a residual that is real-or-noise at the single-run level (combined7's pair has the opposite sign). An interaction form `14.1 + 0.453·k + 0.161·k·(7 − RSS_GB)`
  (rmse 1.33) says: at 7 GB of allowed RSS the slope is ≈ 0.45 s/token/position; every GB the renderer is denied adds ≈ 0.16 s/token/position.
- RSS is a proxy, not the cause. The causal chain consistent with all of the above: **allocation ∝ p** (Hello's monotone RSS growth, 1,707 → 7,165 MB over
  Σp = 136 position-tokens with no GC release = 40 MB per filled position per token = 489 KB per position per style pass ≈ 650 B per filled leaf per pass —
  the size of one substituted-and-parsed 65-axis `font-variation-settings` token stream plus its CSSValue list), **a live heap that does not grow with p**
  (DOM static, Nodes 169,804 in both runs), hence **GC/purge count per token ∝ p** with a machine-state-dependent coefficient. The V8 JS heap is 1–3 MB in all
  runs (no JS), so `--heap-growing-percent=10` does not govern the multi-GB heap; the growth/decline is Oilpan + PartitionAlloc, and a *steadily declining* RSS
  (p40 tokens 6–32) is what Chrome's `MemoryPressureListener` path produces (forced GCs with memory-reducing flags, `FontGlobalContext::ClearMemory`/font-cache
  invalidation, partition purge) when the OS reports pressure — the kernel `memorystatus` idle-exit kills at 03:14:07–13 (p40 tokens 16–17; `R4V/kernel_pressure_log.txt`)
  are that pressure. Purging the font caches also forces the 144·p V instances + 64 shape results each to be recreated at the next layer (R4C's per-instance cost),
  a second ∝ p term inside style (instance creation happens when the style resolves the font) and layout (shaping).

What I could not verify offline: the exact Blink trigger (Oilpan growth heuristic vs. memory-pressure notification), the split of the excess between GC pause
time and cache rebuilds, and the residual +0.1…+0.2 trajectory term. The trace in §4 targets the first two.

## 3. Trivial explanations (Q3) — none apply

- Decoded text: `<output class="visible-output">` is `position:fixed; font:20px/1.6 system-ui; white-space:pre-wrap`, rendered via `::before{content:counter(prompt,gpt2-vocabulary)}`
  and `::after{counter-reset: token1 var(--display-token-1) …; content: counter(token1,gpt2-vocabulary) …}` (a 50,257-symbol `@counter-style`). Prompt 40's ids
  198 "\n" (×2) and 13 "." add line boxes to one fixed-position paragraph of ≤ 32 symbols — per-token constant, microseconds; the two runs' intercepts are equal.
- The token handshake (`.token-slot-1…32`, `#token-N-captured/-advanced.done`, `--pass-cap`) and the `detached-head-reader` chain are per-token constants; the head
  has no per-position elements; R4P's argmax margins on this trajectory (min 9) do not select a different path (pass counts 84/76 identical in both runs).
- Embedding lookup is keyed by token id (15 vs 26 distinct ids) — per-token constant, intercept-only.

## 4. Traced run (Q4)

`R4V/run_trace.sh` (R4M/run_c32.sh lock discipline, owner `R4V trace <pid> <time>`, 30 s toucher, rmdir only if mine, bounded 1 h wait) + `R4V/bench_native_r4v.mjs`
(= R4M's harness + `B0_ADD_CATS`): `B0_PROMPT_TOKEN=40 B0_CAPACITY=10 B0_TRACE=1 B0_BUFFER_KB=400000 B0_DROP_CATS=cc,loading,blink.animations,disabled-by-default-devtools.timeline
B0_ADD_CATS=blink_gc,fonts`, `vm_stat`/`memory_pressure -Q` before/after. Purpose: (i) per-token GC events/durations at capacity 32 (none exist; R4C had no trace),
(ii) p40's k ≤ 10 times under today's memory state vs the two earlier runs (Hello 17.7–18.3 s at k=8–10; p40 21.3–23.8 s).

STATUS: see §4.1 (filled in when the run completes or the wait expires).

## 5. Fix (Q5)

1. **Reduce the ∝ p garbage (exact, no numeric change).** Each style pass parses the same 65-axis V list once per leaf, 64× per (head, slot) (768·p parses of ~1 KB
   token streams + 65-entry CSSValue lists). Options, in increasing invasiveness: (a) let the leaf reference a single pre-concatenated `*` property (`--fr-vp-S-H`
   = list + `,"P000" 1`) so the substitution is one var() token copy without re-serialisation — small win, exact; (b) mark the leaves' rows `contain: style`? — no
   effect on inherited custom properties (not a fix); (c) the `fallback` value layout already in the emitter (one `font-variation-settings` per head wrapper with
   per-slot tags and unicode-range fonts; leaves have no var() at all → MPC-cacheable, ~zero per-leaf garbage) — needs the F4 packed-bank port (`browser_gpt2_font_vector_cache.py:181`
   raises) and a 2-layer smoke + 32-id check; numerics identical (same axis values), but its instance count per pass is 12 × 2,048-axis fonts, to be measured.
   Predicted: slope becomes memory-state independent; at Hello's state ≈ −0.15…−0.3 s/token/position.
2. **Run state (no build change).** Use the heap-flag-off arm (B5 never ran it; the flag only governs the 1–3 MB JS heap here, but it also lowers V8's unified-GC
   schedule), keep ≥ 8 GB free on the 16 GB machine during a demo (no concurrent Chromes/compiles; the tracing buffer itself is pressure), and pin the demo to a
   quiet machine. Predicted for prompt 40 from the pooled law with Hello's RSS trajectory: **≈ 760–800 s (−200…−250 s)**.
3. **Not recommended**: value quantisation to increase instance reuse. §1 shows there is no reuse to be had — K/V lists differ by ≥ 0.5 normalised units between
   repeated tokens, and score instances are new every token by construction (query changes); the only repeat class (`fw = 1`) is already identical on both prompts.
4. Pinning font instances (a laid-out, visibility-hidden element per (layer, slot, head) that keeps the 144·p FontFallbackLists alive across the token) would make
   the per-layer instance switch a cache hit independent of GC — exact, but 144·p extra elements; only worth it after 1(c) is measured.

What I could not verify: the residual trajectory×k term (+0.1…+0.2 s/token/position) may be real; a paired Hello/p40 run under identical memory state would settle
it (not in this agent's budget). Blink internals (Oilpan growth heuristic, `FontDataCache` retention bounds, memory-pressure handlers) are quoted from memory of the
source, not from a checkout on this machine.
