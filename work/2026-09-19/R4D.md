# R4D — flatten the capacity-32 cost without changing the model (2026-09-21)

Bundles (all from `work/2026-09-19/R4D/tools` = R3M/tools + `r4d_flags.py` + edits to `browser_gpt2_font_vector_cache.py` / `browser_gpt2_reused_adapter.py`;
recipe + `diff -ru` in each `BUILD.md`):

| bundle | capacity | value layout | vs | status |
|---|---:|---|---|---|
| `bundles/combined4-c32b` | 32 | runs | `combined4-c32` (R4C) | **run 00:11–00:27: 32/32 ids, 905.9 s (R4C 1,132.9 s, −20 %), READY** |
| `bundles/combined5` | 8 | runs | `combined4` | **run 00:27–00:30: 8/8 ids, 150.8 s, READY** (B5 pairs it vs combined4) |
| `bundles/combined4-c32c` | 32 | **widths** | `combined4-c32b` | built, offline-verified (numerics NOT bit-identical, see §3), run pending |

## 1. R4C's curve, attributed (from `R4C/run-combined4-c32/c32-run1.summary.md`)

32/32 ids, 1,132.9 s. Pass counts are FLAT (RecalcStyle 84, Layout 76 per token at every position), so the slope is per-pass cost growth:
`RecalcStyleDuration = 7.2 + 0.49·k s`, `LayoutDuration = 2.6 + 0.54·k s`, `Task = 16.6 + 1.11·k s` — style + layout carry 1.02 of the 1.11 s/token/position.
Both grow with the FILLED V glyph population (768·p per layer, each glyph a distinct 769-axis font instance whose `P000` axis changes every pass: style ≈ parse +
font-description hashing + platform-font clone, layout ≈ shaping with a new HarfBuzz font). Latches (312·p in-delay transitions) are a minor share (R4C: 13 %).
Memory is not the slope: renderer RSS peaks at 5.8 GB around token 9 and falls to 2.4–4.3 GB while per-token time keeps rising; the residual `Task − style − layout`
is ≈ 6.8 s flat (+0.09·k). Late super-linearity (36 → 58 s over tokens 19–32) coincides with machine load rising from ≈6–7 to ≈10–11 during the run
(other agents' Chrome fixtures; `sysctl vm.loadavg` in R4C.log.md) and with style AND layout both jumping — not with RSS. **Heap-flag-off arm not run**: the split
does not point at GC (coordinator concurred).

## 2. What changed (all flags in `R4D/tools/r4d_flags.py`, default ON unless noted; file:line = `R4D/tools/browser_gpt2_font_vector_cache.py`)

| flag | change | where | exactness |
|---|---|---|---|
| `R4D_EMPTY_UNFILLED` | `@property --fc/--fr-k-S`, `--fc/--fr-v-S-H` initial-value = one zero axis instead of the 768-axis zero list | :190–201 | fvar defaults are 0 for every axis of the 24 fonts (checked) → omitted axis ≡ explicit 0; unfilled slots are never aliased (F5) |
| `R4D_LEAN_LATCH` | per write-slot W: `.fvs-bank{transition-property: fields of slots 0..W}` (32 container rules); write rule lists slots 0..W−1 | :216–231, :296–300 | slots > W never written → no running transition → unlisting cancels nothing (css-transitions §3); full-list base rule kept for the no-match state |
| `R4D_UNPACK_V` | 12 per-head 64-axis V lists per slot (`--fc-v-S-H`; 37 latches/slot instead of 26); K list stays packed; V leaf reads `var(--fr-v-S-H)` | :89–98, :307–316, :500–505 | same `var(--fvn-v-H-i)` entries, tags, fonts |
| `R4D_HIDE_UNFILLED` | `--fvq-S` filled flags on the `fvscache` container + `@container fvscache style(--fvq-S:0){.fvs-v-*-S{display:none}}`; row width subtracts `var(--fvs-nbase)` = `(W+1)·12320.768px` instead of `32·12320.768px` | :451–460, :467–472, :584–599 | same sum of weighted deltas; only the LayoutUnit-snapped base advance of ABSENT glyphs (12320.78125 vs 12320.768 px) leaves `size`: ≤ 31/64 px ≈ 4e-5·fb/fd ctx units, 100× under the KV path's measured 3e-3 rmse (F4 §5) |
| `R4D_GATE_SCORES` (OFF) | `display:none` for unfilled slots' score carriers (inactive view-timelines) | :600–606 | masked by `--fv-S`; timeline re-activation timing untested → left off |
| `--value-layout widths` (c32c only) | existing emitter option, now allowed with F4 packed banks / slim glyphs / hide-unfilled: `font-variation-settings:var(--fr-v-S-H),"P000" 1` + `width:calc-size(max-content,calc(base + (size − base)·var(--fw-H-S)))` | :180–184, :449–451, :510–514 | NOT bit-identical: P000 1/16384 quantisation (≤ 0.375 px/glyph) replaced by LayoutUnit snapping (≤ 0.03 px/glyph); prior fixture RMSE 0.000609 vs 0.000895 (experiments/browser-gpt2-scaling/MEASUREMENTS.md) |

(c) "fewer V leaves per (head, slot)": not possible without a new operator — a glyph has one advance, and each row IS one output coordinate; the 64 leaves of a
(head, slot) sit in 64 different rows. Not done.

## 3. Offline verification

- `font-witnesses.json` 283/283 identical (c32 ↔ c32b ↔ c32c; combined4 ↔ combined5); `launch_browser_gpt2.py --check` static, no JS, all three.
- `index.html`: c32b = c32 with the 768 row constants `394264.576px` → `var(--fvs-nbase)` (string-replacement identity); combined5 = combined4 likewise (`98566.144px`); c32c = c32b byte-identical.
- Leaf-rule diff (`R4D/rule_diff.py`): c32 → c32b confined to KV `@property` registrations, `.fvs-v-H-S`, the 384 bank write rules, 32 per-write-slot `.fvs-bank` lists, `.fvs-query` list declarations, `--fvq-*`/`--fvs-nbase` and the `.head-isolation` wall; c32b → c32c: only the 384 `.fvs-v-H-S` rules.
- Model unchanged → reference ids = `R4C/reference_ids_32.json` (32) / `R3M/reference_ids.log` (8).

## 4. Runs (ONE passive run each, `R4D/run_r4d.sh` = R4C/run_c32.sh pattern: B0/bench_native.mjs, keyboard trigger, heap=1, no trace, AC, lock discipline; load 7–10 throughout — contended machine)

### 4.1 combined4-c32b vs combined4-c32 (`R4D/run-combined4-c32b/c32b-run1.summary.md`; `python3 R4D/compare_runs.py …`)

ids **32/32** = reference. Total **905.9 s** vs 1,132.9 s (−227 s, −20 %). Per-token fit (k≥2): 13.4 + 0.89·k (was 16.3 + 1.14·k) — intercept −2.9 s, slope −22 %;
style 5.5 + 0.35·k (was 7.2 + 0.49·k), layout 2.1 + 0.43·k (was 2.6 + 0.54·k); pass counts unchanged (84/76). Curve k=1/8/16/24/32: 22.0/27.9/21.7/34.4/63.5 s
(before 25.6/30.3/29.5/44.8/57.7). Token 32 is an outlier (63.5 s wall vs 55.7 s task; k=31 was 40.5) — end-of-run readback/poll in the driver, same pattern as
R4C's k=31→32 jump. RSS peak **7,470 MB** (before 5,841; before-run 1,908, end 2,518) — higher peak, see risks.

| k | before s | after s | Δ | before style/layout s | after style/layout s |
|---:|---:|---:|---:|---|---|
| 1 | 25.6 | 22.0 | -3.6 | 14.2/4.3 | 9.0/3.8 |
| 2 | 19.8 | 17.8 | -2.0 | 8.6/4.6 | 6.8/3.9 |
| 3 | 21.8 | 17.9 | -3.9 | 9.4/5.3 | 7.0/4.2 |
| 4 | 23.5 | 17.9 | -5.7 | 10.3/5.3 | 6.8/4.8 |
| 5 | 24.1 | 19.8 | -4.3 | 9.7/7.0 | 7.6/5.1 |
| 6 | 25.0 | 19.0 | -5.9 | 11.9/5.9 | 7.2/5.4 |
| 7 | 23.9 | 23.4 | -0.5 | 10.2/6.0 | 10.2/6.3 |
| 8 | 30.3 | 27.9 | -2.4 | 15.4/7.4 | 13.4/6.9 |
| 9 | 24.6 | 27.8 | +3.2 | 9.7/6.9 | 12.4/7.6 |
| 10 | 27.9 | 25.0 | -2.8 | 12.6/7.4 | 10.8/6.8 |
| 11 | 27.4 | 22.9 | -4.5 | 10.2/9.9 | 8.5/6.8 |
| 12 | 27.3 | 20.6 | -6.7 | 12.5/7.7 | 7.8/6.3 |
| 13 | 31.6 | 20.5 | -11.0 | 15.2/8.8 | 7.9/6.1 |
| 14 | 29.9 | 21.3 | -8.6 | 14.4/8.5 | 7.6/6.6 |
| 15 | 31.1 | 23.4 | -7.7 | 11.9/8.8 | 8.3/8.1 |
| 16 | 29.5 | 21.7 | -7.8 | 12.8/8.6 | 7.9/7.0 |
| 17 | 32.4 | 24.9 | -7.5 | 14.5/10.2 | 9.3/8.5 |
| 18 | 31.7 | 27.6 | -4.1 | 13.8/10.1 | 11.6/8.7 |
| 19 | 36.4 | 24.9 | -11.5 | 12.8/14.5 | 9.9/8.2 |
| 20 | 37.4 | 25.2 | -12.2 | 17.1/10.7 | 9.2/8.4 |
| 21 | 40.8 | 30.5 | -10.3 | 17.8/14.8 | 13.5/9.4 |
| 22 | 45.1 | 30.5 | -14.6 | 19.5/16.4 | 11.4/11.3 |
| 23 | 44.1 | 31.2 | -12.9 | 16.2/18.1 | 13.1/10.1 |
| 24 | 44.8 | 34.4 | -10.4 | 15.1/21.0 | 15.5/10.9 |
| 25 | 45.8 | 35.9 | -9.9 | 23.5/12.6 | 13.5/11.1 |
| 26 | 46.4 | 37.2 | -9.2 | 23.3/14.2 | 14.1/15.1 |
| 27 | 47.3 | 36.7 | -10.6 | 23.2/14.6 | 14.5/14.3 |
| 28 | 47.5 | 35.9 | -11.6 | 21.5/17.1 | 12.6/14.3 |
| 29 | 50.6 | 36.4 | -14.2 | 18.5/21.4 | 11.8/15.2 |
| 30 | 48.3 | 41.8 | -6.5 | 19.8/19.3 | 19.4/14.6 |
| 31 | 53.5 | 40.5 | -13.0 | 22.5/17.9 | 15.1/20.9 |
| 32 | 57.7 | 63.5 | +5.7 | 26.2/21.6 | 26.9/17.5 |
before: 32 tokens, total 1132.9 s, fit(k>=2) 16.3 + 1.141·k; style 7.2 + 0.485·k; layout 2.6 + 0.538·k; RSS peak 5841 MB
after: 32 tokens, total 905.9 s, fit(k>=2) 13.4 + 0.888·k; style 5.5 + 0.346·k; layout 2.1 + 0.428·k; RSS peak 7470 MB


## 4.2 combined5 (capacity 8, same R4D flags) — coordinator entry from `R4D/run-combined5/c5-run1.summary.md`

ONE passive 8-token run (AC, keyboard trigger, heap flag ON, load ≈7–10): **8/8 ids**, total 150.8 s, median 19.0 s/token
(min 16.8, first 20.8); RecalcStyleCount 666 / LayoutCount 608 per 8 tokens; RSS peak 4.8 GB. Not paired — B5's
interleaved bench vs combined4 decides whether UNPACK_V's extra transitions cost or save at capacity 8. READY written.

### 4.2 combined5 (capacity 8, same tools) — correctness run (`R4D/run-combined5/c5-run1.summary.md`)

ids **8/8** = 11,314,1101,7926,11,475,314,1101 → `bundles/combined5/READY`. Total 150.8 s; per-token 20.8 16.8 16.9 17.7 18.9 19.1 20.4 20.1(median 19.0 s; fit tokens 2–8: 15.3 + 0.65·k);
RSS peak 4,833 MB. Single unpaired run at load ≈7–8 — combined4's paired bench median is 18.2 (19.1 15.2 16.6 17.5 18.0 18.5 18.9 18.8), so no speed claim at capacity 8
from this run; B5's interleaved pairs decide. Pass counts 84/76 as combined4.

## 4.3 combined4-c32c (c32b + `--value-layout widths`) — coordinator entry from `R4D/run-combined4-c32c/c32c-run1.summary.md`

ONE passive 32-token run (00:30–00:43, load 6–8): **32/32 ids**, total **758.7 s** (c32b 905.9, R4C 1,132.9 → −33 %);
per-token k=1/8/16/24/32 = 22.0/17.7/21.3/26.9/35.2; fit 13.9 + 0.60·k (c32b 14.4 + 0.85·k; R4C 16.3 + 1.14·k);
style 4.5 + 0.30·k, layout 2.7 + 0.27·k; pass counts unchanged (84/76); RSS peak 7.2 GB. READY written with the caveat
that the widths layout is not bit-identical (ids verified only on this trajectory; any new prompt must be re-verified).
