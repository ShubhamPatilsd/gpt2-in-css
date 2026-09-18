# Implementation plan: fixes 1–6 from audit/2026-09-18/SYNTHESIS.md

Target: pinned bundle `experiments/browser-gpt2/demo-font-vector-twelve` measured passively at
40.7 s/token (8 tokens "Hello, I'm sorry, but I'm", ids 11,314,1101,7926,11,475,314,1101).
Goal of this round: ≤ 12 s/token with bit-identical 8/8 tokens. Longer-term goal: ~3 s/token.

## Ground rules for every agent

- Work ONLY under `work/2026-09-19/<agent>/`. Copy the emitter chain there
  (`cp -R tools work/2026-09-19/<agent>/tools`) and run it with `PYTHONPATH=work/2026-09-19/<agent>/tools`
  or by `cd`-ing into the copy. Never edit the repo's `tools/` or `experiments/` in this round.
- Bundles go to `work/2026-09-19/bundles/<name>/` (index.html, runtime.css, fonts, manifest.json,
  `BUILD.md` = exact command + diff of the tools copy vs `tools/` via `diff -ru`). When a bundle is
  complete AND numerically verified offline, create `work/2026-09-19/bundles/<name>/READY`.
- Chromium mutex: before launching any Chrome, `mkdir work/2026-09-19/CHROME.lock` (fails if held);
  poll every 15 s; `rmdir` it when Chrome exits. Timing runs are done ONLY by the bench agent B0.
  Implementers may run Chrome for correctness (does the page emit the right 8 ids) under the lock.
- Never run two Chromes. Check `pgrep -f "Google Chrome --"` before launching.
- Log every file opened / command run with a one-line why to `work/2026-09-19/<agent>.log.md`.
- Report to `work/2026-09-19/<agent>.md`.
- No git commits, no edits to CLAUDE.md / settings. Disk is ~3–6 GB free: gzip traces, delete raw
  JSON, do not leave extra font copies around (symlink fonts from the source bundle where possible).

## Measurement protocol (B0 owns it)

`audit/2026-09-18/P2-scratch/trace_native.mjs` pattern: headless Chrome 153, AC + `caffeinate -dims`
(refuse on battery unless told), static server `tools/serve_precompressed.py`, no geometry reads
during generation, completion = poll `#token-8-captured.done` every 5 s, one final read of the
output text, RSS via `ps` at 1 Hz. Per bundle: 3 untraced runs (the number) + 1 light-trace run
(shares: style / layout / paint lifecycle / animation; per-pass elementCount histogram; frames per
token). Report s/token for tokens 1–8 individually (slope matters), median, RSS peak, 8/8 ids.

## Fix 1 — GC flag (agent B0, part of baseline)

- Mechanism: P2 #6 — `--heap-growing-percent=10` makes GC grow 3.5 → 16 % of each token; style-minus-GC
  is flat at 20.4 s.
- Arms: baseline bundle with the flag (as Codex ran it) vs without. Also `--js-flags` variants are
  NOT relevant (JS heap < 2 MB); the Oilpan/Blink heap is what matters — check whether the flag is
  set via the harness launch args (grep the runner .mjs in experiments/browser-gpt2 and tools/).
- Pass: per-token slope < 0.5 s/token without the flag; report RSS trade-off.

## Fix 2 — slim the dense leaf populations (agent F2)

- Mechanism: C2 §3/§6 #1, #4 and P2 Table 3: the ~12,27k-element passes (7.8/token, 530 ms) are the
  3,072 proj-pack leaves × 39 KB of declarations; the ~3k-element passes (77/token, 53 % of style) are
  the readback carriers and the 24,576 V glyph leaves × 4,005 B. M1 §8.1: cost = 4.45 µs/element +
  36.5 ns/byte of `var()` declarations, regardless of dependency.
- Changes (emitter locations per C2 §6):
  1. V glyph rule 4,005 B → ≈300 B: `tools/browser_gpt2_font_vector_cache.py:196-204, 232-235,
     334-337, 350-352, 359-366` — use the v2 single `P000` weight axis instead of 64 duplicated Q axes
     (`:45-77` collapse), compute each per-(H,S) softmax weight ONCE as a registered number on the
     head element and reference it from the glyph rule (`var(--fw-H-S)` instead of 64 ×
     `calc(var()*var()/var())`). If the pinned bundle needs v1 fonts that current source cannot
     regenerate, build with v2 fonts and compare against the v2-built baseline B0 produces.
  2. Proj-pack leaves 39 KB → one pre-materialised settings list: `tools/browser_gpt2_projection_layout.py`,
     `build_hybrid_twelve_block.py:131-134, 160-167, 173-178`, `browser_gpt2_reused_core.py:33-52`
     (`isolate_metric_state` / `proj-settings` materialisation), or the `--global-projection` single
     axis list if it can be made correct.
  3. While there: every declaration that is a constant should be a literal, not `var()` (M1 §8.3:
     `var()` doubles per-byte cost); prefer inline typed calc over `@function` per output.
- Verify offline: the emitter's NumPy witness path (`verification-vectors.json`, `font-witnesses.json`,
  `numerical-results.json` in the pinned bundle) must still match; then one correctness Chrome run
  under the lock (8/8 ids).
- Pass: the 12,27k-element pass < 120 ms; the ~3k-element passes ≥ 3× faster; token −6 s or more.

## Fix 3 — take frames out of the loop (agent F3)

- Mechanism: M1 §8.4: a 12-deep geometry→number chain through container-query units or
  `anchor-size()` resolves in ONE style pass and ONE frame; through view/scroll timelines each
  boundary costs +1 pass, +1 layout, +1 frame and re-restyles the downstream chain (quadratic).
  P2: 85 frames × 144 ms ≈ 12 s/token of pure frame overhead + 110k ScrollTimeline invalidations +
  12.3k live timeline animations (3.5 s servicing).
- The hard part is the GATHER: 3,072 (or 256 per shard) sibling glyph widths must land on ONE
  element's `font-variation-settings`. Timelines gather via `timeline-scope`. Without them the only
  cross-sibling reference is `anchor-size()` (allowed in sizing properties of positioned elements)
  and inheritance flows only downward. Proposed structure per 256-axis shard:
  - glyph outputs of stage s are anchors (`anchor-name: --g-<i>`; unique names; anchors must precede
    the anchored element in tree order);
  - a 128-deep chain of positioned size containers, container k: `width: anchor-size(--g-2k width);
    height: anchor-size(--g-2k+1 width); container-type: size`; its child declares two registered
    inherited numbers `--v2k: calc(100cqw / 1px); --v2k+1: calc(100cqh / 1px)` and is the parent of
    container k+1;
  - the shard's font element sits at the bottom and inherits all 256 numbers; 12 shards are siblings.
  - Depth per shard ≈ 256 < Chromium's ~512 nesting cap (S2 #12). Precision: 48 exact bits per
    container (E1 #2); the 32,768 px / 33,554,432 px layout caps still apply (S2 #12).
  - Stage handshake / layer gating: replace SMIL/animation receipts with `@container style()` stamps
    where possible (fix 6), keeping `content-visibility: hidden` locks on inactive layers (M1 §8.2).
- Steps: (1) read how the current emitter gathers (`font_vector_cache.py`, `probe_native_reused_loop.py`,
  `build_hybrid_twelve_block.py`, the `view-timeline`/`timeline-scope` rules in
  `demo-font-vector-twelve/runtime.css` via grep, never cat); (2) build a 1-shard prototype page
  (256 anchors → 128-deep chain → one font element) with random weights, verify the number
  round-trips exactly and that ONE mutation = ONE UpdateLayoutTree + ONE Layout (use M1's harness
  pattern under the lock); (3) scale to 12 shards × one full MLP (768 → 3,072 → 768) and check
  numerical match vs NumPy; (4) if (2)–(3) hold, integrate into the emitter copy for all 12 layers;
  (5) bundle → `bundles/F3`. Stop and report at whichever step fails; a validated (2)/(3) prototype
  is itself a deliverable.
- Known prior traps: "anchor mergers across size containers resolve to zero" (E5 #5) — likely the
  cycle rule (an anchor whose size depends on the anchored element is invalid); keep anchors strictly
  upstream. `anchor-size()` is not accepted inside registered `<number>`s or `font-variation-settings`
  directly (E1 #2) — we only use it in `width`/`height`. Codex's one nested-container probe was
  slower at a single stage (S1 #9) — that compared stage cost, not frames per token; measure both.
- Pass: frames/token ≤ 24 (≤ 2 per layer); ScrollTimeline invalidations ≈ 0; token −6 s or more.

## Fix 4 — retained animations (folded into F5 and F3)

- M1 §8.5: an element carrying a retained animation costs 2.6× to restyle; active/paused ones cost
  ~0.65 µs each per frame; 100k retained = 1.9 GB RSS vs 0.65 GB static. The KV banks hold 1,536
  86,400 s-delay transitions each, never removed (C2 §4).
- F5 makes the banks never restyled (locked + non-inherited), which removes the 2.6× surcharge;
  F3 removes the 12.3k timeline animations. Whether in-delay transitions are serviced per frame:
  F5 measures a bank-only page variant (transition-delay vs `animation-play-state: paused` vs
  static) under the lock with M1's harness and picks the cheapest latch.

## Fix 5 — narrow the write points (agent F5)

- Mechanism: M1 §8.1–8.2: an inherited write restyles every descendant at 4.45 µs + 36.5 ns/B;
  `inherits: false` → 0.001×; a display lock → 0.002×; scoped writes buy exactly 1/n (MB1c).
  P2: 2 whole-DOM passes/token (3 s) + 11.5 passes of 1,553 elements (2.7 s, the bank republish).
- Changes (C2 §6 #2, #3):
  1. `--loop-ready`, `--loop-ack`, `--native-pass` and any other handshake/pass counter registered
     `inherits: true` in `tools/probe_native_reused_loop.py:17-30` and
     `browser_gpt2_reused_adapter.py:41, 111-113` → `inherits: false`, with explicit republish
     (`--x: inherit` or a scoped copy) on the ≈8 receipt/marker elements that read them, following
     the existing `scoped_state` pattern (`reused_core.py:286-306`).
  2. KV banks: un-nest the 12 `.fvs-bank-L` (currently nested at depths 27–38,
     `font_vector_cache.py:401-407`) into siblings of the attention graph; alias only the 48·p filled
     fields of the selected bank (not all 1,536) into the `--fr-*` publisher (`:225-229`); keep storage
     `inherits: false`; wrap inactive banks in `content-visibility: hidden`.
  3. Any other inherited registered number declared on the stage chain that is read by fewer
     elements than it dirties: list them (grep `@property` with `inherits: true` in the built
     runtime.css; count readers) and scope the top offenders.
- Verify offline + one correctness Chrome run under the lock.
- Pass: ≥50 %-DOM passes per token 2 → 0; the 1,553-element passes → < 200 elements; token −3 s.

## Fix 6 — collapse the handshake (agent F3, after fix 3 works)

- C2 §5: the 4-recalc SMIL handshake + one gate unlock per layer + two passes per timeline hop
  derive the 132–212 recalcs/token; M1 §8.4: container flips do not add passes. Replace the SMIL
  receipt chain with `@container style(--layer: L)` stamps; target ≤ 3 UpdateLayoutTree per layer.

## Integration and re-evaluation

- B0 benches: baseline (±GC flag), F2, F5, F3 as each becomes READY, then `combined` = F2 + F5 (+ F3
  if it lands) built by whichever implementer finishes last from a merged tools copy
  (`work/2026-09-19/combined/tools`), then bench again.
- Success for this round: combined ≤ 12 s/token, 8/8 ids, RSS ≤ baseline.
- Phase 2 candidates (for the 3 s goal, not this round): fewer carriers per layer (avar2 fused
  `B·GELU(A·x)`: halves MLP boundaries; 4 values per container: halves carriers), bake LN and
  attention weights as literals, one-pass head, bounded KV window (model change — user decision).
