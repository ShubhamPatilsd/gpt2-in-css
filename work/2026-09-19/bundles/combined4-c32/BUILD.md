# bundles/combined4-c32 — combined4's emitter at `--capacity 32` (R4C, 2026-09-20)

Built by R4C on 2026-09-20 23:28 (`work/2026-09-19/R4C/compile-c32.sh combined4-c32 32`, ≈10 s; log `R4C/compile-c32.log`).
Tools copy `work/2026-09-19/R4C/tools` = `rsync -a --exclude __pycache__ R3M/tools/` — **byte-identical to combined4's emitter**
(`diff -rq --exclude __pycache__ R3M/tools R4C/tools` is clean; hence `diff -ru` vs the repo `tools/` = `bundles/combined4/BUILD.md`'s diff — not repeated here).
Same four symlinks beside the tools copy as R3M (`assets -> ../F4/assets`, `data`, `experiments`, `global-projection-assets -> ../F2/global-projection-assets`);
fonts reused (283 faces), no new font files (`fallback_value_fonts` is only reached for `--value-layout fallback`, so nothing was written under `experiments/`).

**The only change vs `bundles/combined4/BUILD.md`: `--capacity 8` -> `--capacity 32`** (CLI `--capacity`, manifest `capacity` / `generatedTokenLimit` / `kvWindow` = 32).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4C
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined4-c32
```

## What capacity 32 changes in the emitted page (vs combined4; `R4C/populations.py` -> `R4C/populations.txt`)

| population | cap 8 | cap 32 | per extra slot | note |
|---|---:|---:|---:|---|
| runtime.css / index.html bytes | 38,973,628 / 5,603,748 | 50,063,071 / 6,286,974 | +462 KB / +28 KB | |
| elements (open tags) | 67,401 | 86,315 | +788 | 768 V glyphs (`.fvs-v-H-S`, one per slot in each of the 768 `.fvs-value-row`s) + 12 score carriers (`.metric.fvs-score-H-S`) + token slot / feedback metrics |
| `.fvs-v-H-S` V glyph leaves | 6,144 | 24,576 | +768 | all in the same 768 rows; **not gated by fill** — every one substitutes `var(--fr-v-S)` (a ≈7.7–10 KB 768-axis list even when unfilled: the `@property` initial value is the full zero list) |
| score carriers with view-timelines | 96 | 384 | +12 | 12 more live timelines per slot (`timeline-scope` entries 80,117 -> 80,717) |
| bank latch names per bank (`transition-property`) | 208 | 832 | +26 | F4 packing (k, v lists + 24 scales); base `.fvs-bank` rule 10.6 KB; **each of the 384 write rules inlines an 806-name literal list** (F5 `f5BankLiteralLists`) -> 310,438 listed names in the sheet (17,710 at cap 8) |
| in-delay KV transitions running at position p | 312·p (max 2,496) | 312·p (max 9,984) | | 26 per slot per layer; re-resolved on every style pass (F5 §4: ≈5.7 µs each) |
| `--fr-*` alias declarations on the bank at write-slot S | 26·(S+1) | 26·(S+1) (max 832) | | F5's filled-slot filter: slots > S are not aliased |
| `@property` registrations (inherits:true) | 39,426 (15,938) | 41,946 (17,186) | +105 (+52) | `--fs/--fe/--fw-H-S`, `--fv-S`, `--fr-*`, `--fc-*` |
| `@container` / `:has(` rules | 660 / 85 | 2,244 / 301 | +66 / +9 | token-N handshake (`token-N-captured` 4 rules each, `run` 98 `:has()` arguments scoped by R2G) |
| head epoch transport | packed four bits | **separate geometry** (`split_head_receipt`: `.head-score-state` + `.head-epoch-reader` size container, +2 elements) | | required for epoch ≥ 16 |

## Offline verification

- Static check (`tools/launch_browser_gpt2.py --check`): 285 static files / 297,267,069 B / `runtimeJavaScript: false` (combined4: 285 / 285,494,400 B).
- `font-witnesses.json`: 283/283 keys identical to combined4 (keys modulo tools dir); vs the pinned `experiments/browser-gpt2/demo-font-vector-context32/font-witnesses.json`
  (v1 fonts, 261 faces): 7 shared keys, 7/7 identical (the shared base fonts); the rest are not comparable (v1 vs v2 operator fonts, F2/F4 retagged shards).
- Manifest vs combined4 differs only in `capacity`, `generatedTokenLimit`, `kvWindow` (8 -> 32), `headEpochTransport` (`packed four bits` -> `separate geometry`)
  and `r2gScopedHas` stats (`run` 26 -> 98 rewritten arguments, token-N entries for N ≤ 32).
- NumPy reference (`R4C/reference_ids_32.py`, same q9/q16 head path as `R3M/reference_ids.py`; `R4C/reference_ids_32.json`):
  teacher-forced on Codex's saved 32 ids (kv_window None and 32) **and free-running (feed back own argmax, 32 sequential passes)** all give
  `[11, 314, 1101, 7926, 11, 475, 314, 1101, 407, 1654, 611, 345, 821, 3910, 286, 428, 13, 314, 1101, 407, 1654, 611, 345, 821, 3910, 286, 428, 13, 314, 1101, 407, 1654]`
  = the pinned ctx32 bundle's `numerical-results.json` tokens (32/32), text "Hello, I'm sorry, but I'm not sure if you're aware of this. I'm not sure if you're aware of this. I'm not sure".

## Chrome run (ONE passive run, NOT a paired timing row; `R4C/run_c32.sh combined4-c32 c32-run1 2400000`)

B0/bench_native.mjs, `B0_CAPACITY=32 B0_TRIGGER=keyboard B0_HEAP=1 B0_TRACE=0` (no mouse event; `--js-flags=--heap-growing-percent=10` as combined4's bench rows),
headless Chrome 153, caffeinate, under `CHROME.lock` (owner-stamped, touched every 30 s, released 23:53:00 after the run; R4T acquired it next).
Power: AC (81 %, not charging) at start, checked every 30 s, still AC at end. Load 5.8–10 (other agents' compiles — contended; absolute s/token ≈ +5–10 % vs a quiet machine).
Results: `R4C/run-combined4-c32/c32-run1.json`, `c32-run1.summary.md` (per-token table), `R4C/slope_model.py` output in `R4C.md`.

- ids **32/32** = reference (`--saved-token-1..32`; done markers 32/32): 11, 314, 1101, 7926, 11, 475, 314, 1101, 407, 1654, 611, 345, 821, 3910, 286, 428, 13, 314,
  1101, 407, 1654, 611, 345, 821, 3910, 286, 428, 13, 314, 1101, 407, 1654 → "Hello, I'm sorry, but I'm not sure if you're aware of this. I'm not sure if you're aware of this. I'm not sure".
- Load 33.1 s; Run keyed at 35.5 s after navigation; **total 1,132.9 s for 32 tokens (18.9 min)**; per-token s (k=1..32):
  25.6, 19.8, 21.8, 23.5, 24.1, 25.0, 23.9, 30.3, 24.6, 27.9, 27.4, 27.3, 31.6, 29.9, 31.1, 29.5, 32.4, 31.7, 36.4, 37.4, 40.8, 45.1, 44.1, 44.8, 45.8, 46.4, 47.3, 47.5, 50.6, 48.3, 53.5, 57.7;
  median 31.6; fit (k=2..32) **16.3 + 1.14·k s/token**.
- Passes flat: RecalcStyleCount 84 ± 1 / token, LayoutCount 76 ± 1 / token at every position (whole run 2,690 / 2,432); RecalcStyleDuration 494 s, LayoutDuration 367 s, TaskDuration 1,126 s of 1,133 s wall.
- Renderer RSS before Run 1,796 MB; during generation min 757 / median 3,424 / **peak 5,841 MB** (token 9; GC saw-tooth of 2–4 GB per token under the heap flag); browser tree peak 6,276 MB. Nodes 169,547 → 169,804; LayoutObjects 169,471 → 177,788.
- READY: created (offline-verified + Chrome ids 32/32). Not benched in pairs (B5).
