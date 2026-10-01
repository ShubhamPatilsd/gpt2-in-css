# R6X — round-6 merge: `bundles/demo-c32` (the shareable demo, capacity 32) and `bundles/demo-8` (capacity 8 twin) = combined8-c32 / combined8 + R6P (echo fix + typed prompt, N = 4) + R6V (progress UI + smooth fill + font-count loader + early paint); R6L flags off

Agent R6X, 2026-09-30. Tools copy `work/2026-09-19/R6X/tools` = `R5X/tools` + `R6P/tools-vs-R5X.diff` + `R6V/tools-vs-R5X.diff` + `R6X/apply_conflicts.py` (`R6X/tools-vs-R5X.diff`, 712 lines;
`R6X/merge.sh` → `R6X/merge.log`). Bundles `bundles/demo-c32` (+ `BUILD.md`, `README.txt` for recipients) and `bundles/demo-8` (+ `BUILD.md`). Scratch, checkers, harness copies, runs: `R6X/`.
Append-only log `R6X.log.md`. No repo `tools/` / `experiments/` edits, no other agent's directory modified, no git. Machine all session: AC, disk 3 → 2 GB free, swap used 7.3 → 8.4 GB →
the Chrome gate (AC AND ((disk ≥ 4 GB AND swap < 4,000 MB) OR (≥ 3 GB AND < 3,000 MB))) was **closed the whole time**; the four Chrome runs are armed behind it (§5) together with R6P's, R6V's and
R6L's chains (lock-coordinated). Everything in §2–§4 is offline.

## 0. Headline

- **Merge: 1 textual reject** (both owners add their `import` after `import r5e_dead_weight as r5e`) **+ 1 stale hunk** (R6V's diff predates R6V's 15:44 `·` fix, so `r6v_progress_ui.py` is
  taken verbatim from `R6V/tools`) **+ 3 semantic conflicts** resolved as exact-string edits (§1): both owners put their panel row at top 52 px (R6V's row moves to 146, the output text to 184);
  R6V's early-paint lock `body>:not(.controls):not(.ld){content-visibility:hidden}` would hide R6P's prompt panel (a body child) before the sheet arrives → `:not(.tk-panel)` added on both
  the inline lock and the sheet-tail lift; the editable `<style>` is `display:none` in the UA sheet → its 4 visual rules are also emitted in the inline head `<style>`. All three are no-ops
  in the emitted bytes unless BOTH flag sets are on.
- **Offline (§2): every R4M/R5X gate passes.** All-new-flags-off twins are byte-identical to `combined8-c32` / `combined8`; R6P-only == `combined8-c32-prompt` / `combined8-prompt`;
  R6V-only == `combined8-c32-ui` / `combined8-ui` (index.html byte-identical, runtime.css identical after URL normalisation, manifest differs only in the other owner's keys / the symlinked
  font path string); `R6V/offline_check.py` on same-depth twins: HTML identical after removing the UI subtree, model rules identical except the ONE intended `.visible-output{top}` rule
  (PASS with that rule normalised, `R6X/offline_check_r6v.py`); witnesses 271 F4 + 12 dot + 2 tokenizer = 285; NumPy references with the merged tools unchanged (Hello 8/8, prompt-40
  32/32 == R4P, "Once upon a time" == R6P's JSON); static check 287 files / no JavaScript; `R6L/pack_bundle.py --dry-run` resolves all 285 fonts (299.9 MB / 288.1 MB).
- **Chrome (§6, gate opened ≈18:20):** demo-8 Hello **8/8** + verify rc 0 (rmse 0.016998 = combined8's) → READY 18:31; demo-c32 load-paint: first-contentful-paint **52 ms**,
  load event 2.16 s, **Ready 2.32 s** (vs 34 s before round 6; the 0.5 s screenshot was delayed by Playwright until load, so the pre-sheet panel is evidenced by the paint timing, not a
  shot); typed "I" **32/32** == R4P in 922.0 s (k=1 18.8 s, fit 12.03 + 1.017·k, RSS peak 4,493 MB); typed "Once upon a time" **32/32** == R6P's reference in 887.8 s (4 prefilled + 29
  generated, text "Once upon a time, the world was a place of great beauty and great danger. The world was a place of great danger, and the world was a place of") → READY 19:06.
  Observation for the owners: **RecalcStyleCount 102/token flat** (R5X's combined8-c32: 72) — +30 passes per token from the R6P/R6V additions (R6V's smoke trio attributes it); s/token
  within the memory-state noise of R5X's 905.6 s.
- **v2 (§7, 19:12):** the coordinator's review of `typed-once-final.png` (900×300) showed the 2-line output overlapping the fixed footer → one extra display rule
  `html .visible-output{bottom:96px;overflow:auto}` (conflict edit 4), both bundles rebuilt under the lock, proven identical to v1 except that rule (`R6X/compare_rules.py`), re-verified
  by a typed-prompt load-paint probe with completion screenshots and a demo-8 Hello guard run — results auto-appended as §7. README: the prompt goes between the two quotes of the shown rule.
- **v3 (§7, 20:07–20:48):** both bundles rebuilt under the lock — v1 → v2 adds `html .visible-output{bottom:96px;overflow:auto}` (footer overlap), v2 → v3 adds the 13th
  "vocabulary head" segment (`.pg::before/::after`, `@container corestate style(--held:1)` fill over an estimated 2.8 s + opacity pulse, 9 rules); `R6X/compare_rules.py` proves each
  step: index.html byte-identical, all other rules identical in multiset AND order. Re-verification: typed "Once upon a time" probe at 900×600 → Ready 2.18 s, 32 tokens in 944 s,
  **no output/footer overlap** at completion (also at 900×300), head label + segment present at completion; demo-8 Hello **8/8** + verify rc 0 (READY updated). **User report "Complete
  but no text" — not reproduced** in 4 HEADED runs (1100×700, user's launcher): 2-layer smoke typed plain / trailing space / "\n", and the full demo-c32 run (32/32, 824 s): the output
  element is rendered (display block, visibility visible, content-visibility visible, opacity 1, 20 px system-ui, 420 px box) with all 4 prompt ids and all 29 generated ids resolved in
  its counters, every body child content-visibility:visible. Caveats and the one real risk found: §7.S.
- **v4 (§8, 21:15–22:03, coordinator's robust sizing):** `html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}` replaces v2's `bottom:96px`
  (which clipped the box to ≤ 20 px in windows < ≈320 CSS px), and the footer follows the output's maximum extent, `html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;
  bottom:auto}`. Built into `.next` and swapped atomically (`bundles/demo-c32.prev`, `demo-8.prev` kept); `compare_rules.py`: +2 / −1 display rules, common rules identical in multiset
  and order, index.html byte-identical. Probes typed "Once upon a time" to Complete: 900×300 → output 184–312 px (4 lines), footer at 320 (off-screen), overlap false; 1100×700 →
  output 184–312, footer 612–651, overlap false. demo-8 Hello **8/8** + verify rc 0 (READY v4).
- **v5 (§10, 2026-10-01, user reports #2/#3 "typed prompt shown, dropdown prompt run"): root cause found structurally, fix built, verification armed.** The embedding
  receipt stamps only the epoch, so at Run layer 0 could consume the idle *dropdown* embedding before the typed token's re-layout/readback landed (R6P.md §7.3's race; dropdown
  runs immune); independently the 86,400 s latch could freeze pre-armed values if armed values and latch landed in one style pass. Fix (apply_conflicts edit 6; model core rules
  identical, `check_v5_identity.py` PASS on the fixed 2-layer smoke `R6X/smoke-demo-2L-v5`): token-fresh receipt (`--prompt-live` in the marker), sticky arming, no latch,
  editor locked from the click, Run enabled only at Ready, echo/display from the model-facing values. `R6X/run_chain_v5b.sh` (armed 01:57) runs, when the gate opens (machine on
  BATTERY since ≈02:30 — gate closed): per-frame ordering probes with keystrokes + mouse click + 150 % zoom on the old and the fixed smoke, atomic rebuild+swap of demo-c32/demo-8
  (.next/.prev), guards (demo-8 Hello 8/8; headed keystrokes+mouse "Shubham was" 32/32; typed "Once upon a time" 32/32) → READY lines + §10 sections. Until it has run, the live
  `bundles/demo-c32` is still v4 (unfixed wiring). Reset = GET form navigation to index.html (fresh document; a browser Reload instead restores the checked Run box).
- **v6 (§11, 2026-10-01 13:21, cause found by R7H):** the flipped ids were not load, not the v5 wiring and not harness perturbation — in HEADED Chrome with macOS "Show scroll
  bars: Always" a 15 px classic scrollbar sits inside `.feedback-scroller`'s 524288 px scrollport (hardcoded in the id decode, 8 px per id) and biases every read-back id ≥ 9283
  by +1 (Shubham 17132 → 17133 in both headed runs; Hello/Once max ids 7926/8737 pass barely; smokes never flip; all earlier 32/32 runs were headless). Fix
  `.feedback-scroller{scrollbar-width:none}` (edit 7), built to `.next`, swapped (core rules identical). Guards (§11.G, headed, scrollbars shown): positive control on the old build **16/32** (first wrong winner right after 16918 — the bias confirmed), v6 typed "I" **32/32**,
  v6 "Shubham was" **32/32**, demo-8 Hello **8/8** → READY v6 on both bundles. The v5 arming fix stands (ordering frames: receipt gating as designed). The §10.M load theory is withdrawn; headed guards are now
  mandatory for acceptance.
- (original hand-back line) **Chrome (§5–§6): was pending the gate.** `R6X/run_chain.sh` (armed 16:13:57) runs, one at a time under `CHROME.lock`: demo-8 Hello 8/8 + verify → READY; demo-c32 load-paint probe
  (screenshots 0.5/1/2/4/8 s, load, Ready — acceptance: something visible < 1 s, Ready ≤ 8 s); demo-c32 typed "I" 32/32 vs R4P (+ mid-token screenshots at 8/30/60 s); demo-c32 typed
  "Once upon a time" 32/32 vs R6P → READY. Results auto-append as §6.

## 1. Merge (`R6X/merge.sh` → `R6X/merge.log`; `R6X/apply_conflicts.py`; reject in `R6X/rejects/`)

Base `cp -R R5X/tools R6X/tools`; BSD `patch -F3 -N` (basenames) with `R6P/tools-vs-R5X.diff` (2 files: `browser_gpt2_runtime.py` 7 hunks, new `r6p_prompt.py`) → **0 rejects**; then
`R6V/tools-vs-R5X.diff` (2 files) → **1 reject of 5 hunks** = the import line (`R6X/rejects/browser_gpt2_runtime.py.rej`). Before the conflict edits: merged − R6P/tools = exactly R6V's
two files; merged − R6V/tools = exactly R6P's two files; `r6p_prompt.py` cmp-identical to R6P's. R6L's diff is **not** applied: the merge takes R6V's early-paint variant (`R6L/split-point.md`,
R6V.md §0) and `R6L_BODY_LINK=0 R6L_BOOT=0` would emit nothing; if R6L's `hide` arm later shows Chrome laying out UA-styled content past a body `<link>`, the two belt strings go into
`r6v_progress_ui.inline_style` / `early_paint_runtime_css`.

| # | conflict | resolution (exact-string edit) |
|---|---|---|
| 0 | import line reject | `import r6v_progress_ui as r6v  # R6V…` inserted after R6P's import line |
| 0′ | `r6v_progress_ui.py` from R6V's diff has `content:" \00b7 layer …"` (2 lines) — R6V found on 15:44 that the hex escape eats the space and fixed the emitter to the literal `·`, then patched their built sheets in place (`R6V/check_emitted.py` 414/414) without regenerating the diff | take `R6V/tools/r6v_progress_ui.py` verbatim (cmp identical to the owner's) |
| 1 | **layout**: R6P's `.tk-panel` (label + editable `<style>`) at top 52 px, `.tk-tokens` readout at 118, `.visible-output` at 146; R6V's `.ld` / `.ld2` / `.pg` row also at top 52 (`TOP_PX`), output at the base 110 | module-level block after both imports: `if r6p.TYPED and r6v.ON: r6v.TOP_PX = 146; r6p.OUTPUT_TOP = 184` — R6V's functions read the module globals at call time; `r6p_prompt.panel_css` gains the constant `OUTPUT_TOP = 146` (`f".visible-output{{top:{OUTPUT_TOP}px}}"`). Result rows: controls 16 → prompt panel 52–100 → token readout 118 → loading/progress row 146 (bars 168–176) → output text 184 |
| 2 | **early-paint lock**: R6V's inline `body>:not(.controls):not(.ld){content-visibility:hidden}` (lifted by the same selector at the end of runtime.css) hides every other body child until the sheet applies — R6P appends `.tk-panel` to `controls`, i.e. a body child → invisible/uneditable during the CSS phase | same block: `r6v.HIDE_SELECTOR = "body>:not(.controls):not(.ld):not(.tk-panel)"` (inline lock and sheet-tail lift both use the constant → stay in step). The `<aside>`, the run-latched `<svg>` and the epoch observer stay locked as in R6V's bundle |
| 3 | **editor invisible pre-sheet**: a `<style>` element is `display:none` in the UA sheet; the panel's rules live in runtime.css only | `r6p_prompt.panel_css` split into `panel_inline_css()` (`.tk-panel`, `.tk-panel label`, `.tk-editor`, `.tk-editor:focus`) + the rest (same concatenation → byte-identical output, checked); the runtime's EARLY_PAINT block does `head_style = head_style.replace("</style>", r6p.panel_inline_css() + "</style>", 1)`. The `:has()` read-only rule and the layout overrides stay in the sheet (R2G rewrites `:has()` in the sheet, not in the page) |

Non-conflicts checked: R6V's `insert_progress` needs exactly one `.core-controller` (R6P's `wrap_model` adds none); R6V's `.pg` is `position:fixed` inside R6P's four absolutely positioned
inline-size containers (same case as the model's own fixed readers); the font barrier automatically counts 285 faces (`"Loading model weights: N of 285 fonts"`); R6V's 5 body-anchored `:has()`
rules go through R2G's fixed-depth rewrite over the 17 new `.tk-*` levels (`r2gScopedHas.total` 323 → 328 at cap 32, 107 → 112 at cap 8); the `.ld` label says "50 MB of CSS" (sheet length at
assembly time). `py_compile` ok. Emitted structure of `demo-c32/index.html`: `<head>` … `<title>` + 1,399 B inline `<style>` (no `<link>`); `<body>` = `.controls` → `#runtime-epoch-observer` →
`svg.native-signals` (run-start/run-latched) → `aside.tk-aside` → `.tk-panel` (label + `<style id="tk-editor" contenteditable="plaintext-only">.tk-root { --draft-prompt: ""; }</style>`) → `.ld`
(CSS-phase panel) → **`<link rel="stylesheet" href="runtime.css">`** → 285 witnesses + proofs + `.ld-sum` tree + `.font-status` + `.ld2` → `.tk-root` ▸ 4 tokenizer slots ▸ `.tk-tokens` +
`.feedback-reader` (model, with `.pg` as the first child of `.core-controller`) + `.detached-head-reader`; runtime.css ends `…{contain:paint}body>:not(.controls):not(.ld):not(.tk-panel){content-visibility:visible}`.

Recipe (`bundles/demo-c32/BUILD.md`): `cd R6X && R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=1 R6P_PROMPT_SLOTS=4 R6V_PROGRESS_UI=1 R6V_SMOOTH=1 R6V_EARLY_PAINT=1 R6V_FONT_COUNT=1 VALUE_LAYOUT=widths
R4S_SMALL_HOPS=0 ./compile.sh …/bundles/demo-c32 32 12` (20 s); demo-8: `./compile.sh …/bundles/demo-8 8 12` (13 s). `R6X/compile.sh` = `R5X/compile.sh` + both flag passthroughs.
Symlinks in `R6X/`: `assets → ../F4/assets`, `data`, `experiments`, `global-projection-assets` (as R5X), `assets-r5h → ../R5X/assets-r5h`, `assets-r6p → ../R6P/assets-r6p`, so the emitted
URLs are the owners' (`../../F4/assets/…` ×271, `../../R5X/assets-r5h/…` ×12, `../../R6P/assets-r6p/gpt2-token-id-{0,1}-full.ttf`).

## 2. Offline verification (`R6X/compare_bundles.py` = R5X's + R6P/R6X agent-dir normalisation; `R6X/twins_all.sh`, `R6X/twins_r6v_check.sh`; logs `R6X/logs/`; every twin built one at a time into `R6X/twin-<x>` (same path depth as `bundles/<x>`) and deleted after its checks)

| build (flags) | reference | result |
|---|---|---|
| `p32-alloff` (R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0 R6V_PROGRESS_UI=0, cap 32 widths) | `bundles/combined8-c32` | **index.html byte-identical (7,125,736 B); runtime.css identical (URL-normalised, 49,311,014 chars); manifest +12 R6 keys only; witnesses 283/283** |
| `p8-alloff` (same, cap 8) | `bundles/combined8` | identical likewise (6,460,006 B; 38,269,982; 283/283) |
| `p32-r6ponly` (R6V_PROGRESS_UI=0) | `bundles/combined8-c32-prompt` | identical (7,127,853 B; css 49,405,183 identical; manifest differs only in the `r6pTypedPrompt.fonts` path string `R6X/assets-r6p` vs `R6P/assets-r6p` — same files through the symlink; witnesses 285/285) |
| `p32-r6vonly` (R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0) | `bundles/combined8-c32-ui` | identical (7,127,641 B; css 49,364,510 identical; manifest +8 R6P keys; witnesses 271/283 + the 12 dot faces keyed through R6V's `assets-r5h` symlink path = same files) |
| `p8-r6ponly` | `bundles/combined8-prompt` | identical (6,462,123 B; 38,306,557; 285/285) |
| `p8-r6vonly` | `bundles/combined8-ui` | identical (6,461,911 B; 38,318,144; 271/283 + 12 as above) |
| `R6V/offline_check.py demo-c32 vs p32-r6ponly`; `demo-8 vs p8-r6ponly` | R6V off | index.html **IDENTICAL after removing the UI insertions** (head `<style>` 1, `.ld` 1, `.ld2` 1, `.ld-sum` 21, `.pg` 1; `.pg` is the 8-element first child of `.core-controller`); model rules: **exactly one differs**, `.visible-output{top:184px}` (UI) vs `top:146px` (ref) = conflict edit 1 (display-only); UI rules 454 at cap 32 (285 fontload, 64 runtime, 39 corestate, 24 keyframes, 42 plain) / 398 at cap 8; manifest only `r6v*` + `r2gScopedHas.*`; witnesses 285/285 → reported FAIL on that one rule |
| `R6X/offline_check_r6v.py` (same checker, that one rule normalised, asserting exactly 1 occurrence) on rebuilt twins | R6V off | see §2a below |
| R6P's own offline method (R6P had no checker script: byte compares + `inspect_css.py` anchors) | — | the R6P-only twins above are byte-identical to R6P's bundles, so R6P's offline results transfer; anchors re-inspected in demo-c32: `.tk-root{display:contents;--prompt-armed:inherit}` (the 15:4x hop fix) present, `.tk-*` chain, `--pf-1..4`, `--token` chain, 3 hidden-winner rules, 6 prefill EOS/ack rules, `.visible-output` rules, tokenizer faces |
| NumPy ids with the merged tools (`R6X/run_reference.sh` = R5X's scripts on `R6X/tools`) | — | 8-token Hello `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected (3 s); prompt-40 free-running 32/32 == `R4P/reference_ids_32_40.json` == teacher-forced, first mismatch None (13 s); "Once upon a time" via `R6P/reference_prompt.py` on `R6X/tools` → §2a. By construction: `diff -rq R5X/tools R6X/tools` = `browser_gpt2_runtime.py` + the two new emitter modules only — the reference/numerics modules are R5X's bytes |
| witnesses `demo-c32` / `demo-8` | — | 285 = 271 F4 faces + 12 R5H dot faces (`R5X/assets-r5h`) + 2 GPT-2 tokenizer faces (`R6P/assets-r6p`, witness glyphs `~` / `!`) |
| `tools/launch_browser_gpt2.py --check` | — | demo-c32: **287 static files, 299,879,566 B, `runtimeJavaScript: false`**; demo-8: 287 files, 288,109,876 B, false; 0 `<script>`, 0 `on*=` |
| `R6L/pack_bundle.py … --dry-run` | — | demo-c32: index.html 7,130,218 + runtime.css 50,356,016 (URLs rewritten to `fonts/<name>?v=…`) + 285 fonts 242,382,884 (largest `embedding-lookup.woff2` 56,853,724) = **299,869,118 B**, every `url()` resolved, no basename collision; demo-8: 288,099,428 B |

Sizes: demo-c32 runtime.css 50,366,464 B / index.html 7,130,218 B (combined8-c32 49,311,014 / 7,125,736: +1.0 MB R6P chains, +54 KB R6V rules); demo-8 39,252,056 / 6,464,488 (combined8 38,269,982 / 6,460,006).
Disk: the two deliverables (55 + 44 MB) + `R6X/` 66 MB; all twins deleted.

### 2a. Results of the two background checks (filled in below when they finished)

- `R6X/offline_check_r6v.py bundles/demo-c32 R6X/twin-p32-r6ponly` → **RESULT: PASS**: index.html IDENTICAL after removing the UI insertions (7,130,218 vs 7,127,853 B); `.visible-output{top:184px}` normalised (exactly 1 occurrence); **model rules IDENTICAL (66,711 rules), order identical**; UI rules 454 (+54,553 chars); manifest only `r6v*` + `r2gScopedHas.*` (323 → 328); witnesses 285/285 (`R6X/logs/offline_check-r6x-demo-c32.log`).
- `… bundles/demo-8 R6X/twin-p8-r6ponly` → **PASS**: model rules IDENTICAL (62,077), order identical; UI rules 398 (+49,219 chars); `r2gScopedHas.total` 107 → 112; witnesses 285/285.
- `R6P/reference_prompt.py "Once upon a time"` on `R6X/tools` → `R6X/scratch/reference_once.json`: promptTokens [7454, 2402, 257, 640], winners / freeRunningReference / generatedIds / inputs / generatedText **all == `R6P/reference_ids_once_upon_a_time.json`**; teacher-forced check == winners; quantized == float (first mismatch None); text "Once upon a time, the world was a place of great beauty and great danger. The world was a place of great danger, and the world was a place of".

## 3. Chrome plan (armed 16:13:57, `R6X/run_chain.sh` → `R6X/logs/run_chain.out`; gate closed all session)

Gate (polled every 60 s) → each run under `R6X/with_lock.sh` (= R5X's: `mkdir CHROME.lock`, owner "R6X <label> <pid> <time>", `touch -c` every 30 s, 5 s poll, rmdir only own, refuses
while a foreign headless Chrome runs, power re-checked every 30 s, watchdog). R6P's, R6V's and R6L's chains wait for the same gate and hold the lock briefly per run — pure lock coordination,
nothing killed. Per-run scripts are the owners' with R6X paths: `R6X/correctness_inner.sh` (R5X's; R4M `correctness_run.mjs`, 5 s poll, RSS sampler, verify with **R6X/tools**),
`R6X/loadpaint_inner.sh` + `R6X/loadpaint.mjs` (R6V's + editor/`.tk-tokens` fields in the state readout), `R6X/c32_inner.sh` + `R6X/bench_native.mjs` (R6P's typed-prompt harness
+ `B0_SHOTS`: screenshots at given seconds after Run, screenshot only — no style reads — so the passive protocol is unchanged; one forced frame may add 1 RecalcStyle/Layout to that token).

| # | run | acceptance | outputs |
|---|---|---|---|
| 1 | `demo-8`, dropdown Hello (nothing typed), ONE passive 8-token run | ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` 8/8 + `verify_browser_gpt2_runtime.py` rc 0 → **`bundles/demo-8/READY`** | `R6X/run-demo-8/{harness.log,verify.log,rss-renderer.log}` |
| 2 | `demo-c32` load-paint probe (load only) | screenshots at 0.5/1/2/4/8… s after navigation until `#fonts-loaded.done`; load event; Ready time; panel texts per step. Target: something visible < 1 s (controls + prompt box + "Loading the model's stylesheet…" bar), "Loading model weights: N of 285 fonts" during the font phase, Ready ≤ 8 s | `R6X/runs/loadpaint-demo-c32/shot-load-{0.5,1,2,4,8,…}s.png`, `shot-ready.png`, `harness.log` |
| 3 | `demo-c32` typed "I" (live ids asserted `[40]`, model-facing values asserted unarmed pre-Run), keyboard Run | 32/32 vs `R4P/reference_ids_32_40.json`; per-token s, ΔRecalcStyle (flat ≈72), ΔLayout (64), RSS per token in `typed-I.summary.md`; screenshots at 8/30/60 s after Run show the progress bar mid-token | `R6X/run-demo-c32/typed-I.{json,summary.md,stdout.log,memstate.txt}`, `typed-I-run-{8,30,60}s.png`, `typed-I-final.png` |
| 4 | `demo-c32` typed "Once upon a time" (ids `[7454, 2402, 257, 640]`) | 32/32 vs `R6P/reference_ids_once_upon_a_time.json` (3 discarded prefill winners + 29 generated) → **`bundles/demo-c32/READY`** iff 3 and 4 are both 32/32 | `typed-once.*`, `typed-once-run-{10,40,70}s.png` |

The chain appends **§6 "Chrome results"** to this file (harness lines, summaries, screenshot list, READY texts) and logs each step to `R6X.log.md`. Manual re-run of one step when the machine is
quiet: `R6X/with_lock.sh <label> <cap-s> R6X/correctness_inner.sh demo-8` / `R6X/loadpaint_inner.sh demo-c32 0` / `B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' B0_SHOTS=8,30,60
REF_JSON=$W/R4P/reference_ids_32_40.json R6X/c32_inner.sh demo-c32 typed-I 2400000 32`. Expected numbers if the merge costs nothing (R5X.md §4 + R6P.md §6): typed "I" ≈ 906 s for 32 tokens
(k=1 ≈ 18.5 s, fit 12.05 + 0.975·k), RecalcStyle 72/token flat, RSS peak ≈ 4.4 GB; "Once upon a time" ≈ same total, first NEW token after ≈ 65 s (4 prefill steps).

## 4. Pack recipe and how a user views demo-c32

Asset dependencies of `bundles/demo-c32` (all relative `url()` in `runtime.css`; nothing in `index.html`): 271 faces `../../F4/assets/…` (weights; `embedding-lookup.woff2` 56.9 MB), 12 faces
`../../R5X/assets-r5h/font-vector-operators-r5h/dot-h{0..11}-7bf3e9b65c31dc6f-f4-r5h.woff2`, 2 faces `../../R6P/assets-r6p/gpt2-token-id-{0,1}-full.ttf` (1.66 + 1.62 MB, uncompressed
TrueType) — 285 files, 242,382,884 B; the bundle therefore depends on `work/2026-09-19/{F4,R5X,R6P}` staying in place until packed. `R6L/pack_bundle.py --dry-run` confirmed every file resolves.

```sh
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
# (a) view locally, in place (strict static server + a separate Chrome profile with JavaScript disabled):
python3 /Users/shubhampatil/Documents/programming/gpt2-css/tools/launch_browser_gpt2.py --directory $W/bundles/demo-c32
#     or --no-open and paste the printed http://127.0.0.1:<port>/work/2026-09-19/bundles/demo-c32/index.html into Chrome ≥ 139 yourself
# (b) pack for other people (≈300 MB folder: tools/launch_browser_gpt2.py + model/{index.html,runtime.css,fonts/285 files} + README.txt; --br adds .br/.gz twins for hosting):
$W/R6X/pack_demo.sh demo-c32 /path/to/gpt2-css-demo --br     # = R6L/pack_bundle.py + the bundle's README.txt copied over the generic one
cd /path/to && zip -r gpt2-css-demo.zip gpt2-css-demo
# recipient: unzip; cd gpt2-css-demo; python3 tools/launch_browser_gpt2.py --directory model
```
Not run for real this session (2 GB of free disk; the dry run is the check). Hosting caveats are R6L.md §5 (GitHub Pages fits the file limits; Cloudflare Pages does not; fonts same-origin,
`text/css`, Chrome/Edge ≥ 139, 16 GB RAM). `bundles/demo-c32/README.txt` tells recipients: Chrome/Edge ≥ 139, 16 GB, the two run commands, load ≈ 5 s, ≈ 15–45 s per token (≈ 15 min for 32),
4-token typed-prompt limit and tokenizer limits, greedy decoding, Reset = reload.

## 5. Risks / not done

0. (v2) `RecalcStyleCount` 102/token instead of 72 in both typed runs (ΔLayout 64 unchanged, s/token ≈ R5X's): the +30 passes/token are UI/prompt-side (the model rules are byte-identical
   to combined8-c32's) — candidates: R6V's per-layer `animation-name` swap on `.pg-est` (12/token) and the `.pg` container-query dependents, R6P's `.visible-output` if() chain. Not
   attributed here; R6V's smoke trio (`smoke-R6V-2L` vs `-nosmooth`) is the designed experiment. The fix if it is the smooth fill: rebuild with `R6V_SMOOTH=0`.
1. **Nothing Chrome-verified yet** — the gate never opened (swap 7.3 → 8.4 GB, disk 3 → 2 GB). The merge inherits R6P's residual risk (the model in-flow inside four absolutely positioned
   inline-size containers; run 3 is the test) and R6V's (frame cost of the smooth fill; if R6V's smoke trio shows extra main frames, rebuild with `R6V_SMOOTH=0` — `R6X/compile.sh` passes it).
   R6P's own chain runs first-come by lock; its smoke (3 min) will expose a mechanism error before my two 15-minute typed runs.
2. Early paint in the merged page is argued, not seen: the prompt panel is exempt from the lock and styled inline; the `<aside>` stays hidden until the sheet applies (as in R6V's bundle).
   R6L's belt (`body{display:none}`) is not in; add it only if R6L's `hide` arm says Chrome lays out UA-styled content past a body `<link>`.
3. Layout collision risk: `.tk-tokens` (top 118, `pre-wrap`) could wrap to a second line on a narrow window and touch the progress row at 146; the harness viewport (900 px) fits one line.
4. The manifest's `r6pTypedPrompt.fonts` records the symlink path `R6X/assets-r6p/…` (the CSS URL is the resolved `../../R6P/assets-r6p/…`).
5. `R6X/offline_check_r6v.py` and `R6X/compare_bundles.py` are copies of the owners' checkers with one normalisation each (documented in their docstrings); the un-normalised owner checker
   result (one differing rule) is recorded in §2 so the reader can judge the edit.

## 6. Chrome results (auto-appended by R6X/run_chain.sh 2026-09-30 19:06:53)

### 6.1 demo-8 correctness (R6X/run-demo-8/)
```
{"t":6558,"event":"loaded","elements":67596,"fonts":285}
{"t":32075,"event":"token-captured","token":1,"sinceRunMs":23493}
{"t":49503,"event":"token-captured","token":2,"sinceRunMs":40921}
{"t":72635,"event":"token-captured","token":3,"sinceRunMs":64053}
{"t":84936,"event":"token-captured","token":4,"sinceRunMs":76354}
{"t":108550,"event":"token-captured","token":5,"sinceRunMs":99968}
{"t":125899,"event":"token-captured","token":6,"sinceRunMs":117317}
{"t":143734,"event":"token-captured","token":7,"sinceRunMs":135152}
{"t":162667,"event":"token-captured","token":8,"sinceRunMs":154085}
{"t":169351,"event":"final","packedBanks":true,"packedHead":true,"headSample":"\"X000\" -12,\"X001\" -4,\"X002\" 4,\"X003\" -13,\"X004\" 8,\"X005\" -20,\"X006\" 89,\"X007\" -5,\"X008\" 5,\"X009\" 9,\"X00A\" -3,\"X00B\" -11,","tokens":[11,314,1101,7926,11,475,314,1101],"tokensText":"","bodyProps":{"--epoch":"8","--winner":"-1","--head-output-epoch":"0","--token":"15496"},"doneMarkers":{"1":true,"2":true,"3":true,"4":true,"5":true,"6":true,"7":true,"8":true},"rawSample":{"k":{"list":"\"K000\" -0.5
verify rc=0 {'tokens': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceQ9Q16': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceAttentionMask': 'full causal', 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.016997776885828732, 'maximum': 0.14188476906986125}, 'finalHeadActualInputWinner': 1101, 'finalHeadMatchesActualInput': True, 'originalFloatWinners': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'originalFloatAgreement
RSS renderer peak MB: 4630
READY: demo-8 READY 2026-09-30 18:31:02: dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], verify rc=0, run R6X/run-demo-8 (harness.log, verify.log); = combined8 + R6P echo fix + typed prompt + R6V progress UI/early paint (all-new-flags-off twin byte-identical to combined8)
```
### 6.2 demo-c32 load-paint probe (R6X/runs/loadpaint-demo-c32/shot-*.png)
```
{"t":2664,"event":"load-event","sinceNavMs":2161}
{"t":2813,"event":"screenshot","file":"shot-load-0.5s.png","sinceNavMs":2310}
{"t":2818,"event":"state","tag":"load-0.5s","sinceNavMs":2315,"readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt: none — the dropdown prompt is used. \" counter(tkt0, gpt2-vocabulary) \"\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weight
{"t":2822,"event":"fonts-loaded","sinceNavMs":2316,"readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt: none — the dropdown prompt is used. \" counter(tkt0, gpt2-vocabulary) \"\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285
```
### 6.3 demo-c32 typed-I (R6X/run-demo-c32/typed-I.summary.md; screenshots typed-I-run-*s.png, typed-I-final.png)

# typed-I — 32/32 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.2 s, Run at 6.0 s after nav

ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4P/reference_ids_32_40.json; prompt token default 15496); ids=[13, 198, 198, 464, 717, 1517, 314, 750, 373, 284, 467, 284, 262, 1957, 16918, 3650, 290, 2822, 257, 6131, 286, 12912, 32132, 13, 314, 373, 523, 6568, 284, 1949, 340, 13]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18.8 | 19 | 13 | Y | 110 | 68 | 11.2 | 3.7 | 18.9 | 3013 | 3013 |
| 2 | 14.9 | 34 | 198 | Y | 112 | 70 | 7.5 | 3.7 | 15.5 | 4144 | 4007 |
| 3 | 13.7 | 47 | 198 | Y | 96 | 60 | 6.2 | 3.5 | 13.4 | 4035 | 3985 |
| 4 | 17.4 | 65 | 464 | Y | 103 | 64 | 8.2 | 4.3 | 16.7 | 4136 | 3946 |
| 5 | 15.3 | 80 | 717 | Y | 99 | 62 | 7.5 | 4.0 | 15.5 | 4268 | 4268 |
| 6 | 16.9 | 97 | 1517 | Y | 102 | 64 | 8.5 | 4.1 | 16.9 | 4394 | 4108 |
| 7 | 18.3 | 115 | 314 | Y | 99 | 62 | 8.7 | 4.9 | 17.8 | 4310 | 4134 |
| 8 | 20.1 | 135 | 750 | Y | 102 | 64 | 9.5 | 6.0 | 19.9 | 4449 | 4276 |
| 9 | 20.5 | 156 | 373 | Y | 102 | 64 | 11.3 | 4.7 | 20.3 | 4362 | 4265 |
| 10 | 21.5 | 177 | 284 | Y | 102 | 64 | 10.9 | 5.9 | 21.4 | 4347 | 3732 |
| 11 | 23.0 | 200 | 467 | Y | 102 | 64 | 13.1 | 5.1 | 22.8 | 4216 | 3662 |
| 12 | 23.5 | 224 | 284 | Y | 102 | 64 | 13.4 | 5.3 | 23.4 | 4265 | 3472 |
| 13 | 25.6 | 249 | 262 | Y | 102 | 64 | 14.8 | 5.9 | 25.4 | 4311 | 4016 |
| 14 | 25.4 | 275 | 1957 | Y | 102 | 64 | 13.8 | 8.9 | 27.9 | 4376 | 3590 |
| 15 | 29.2 | 304 | 16918 | Y | 102 | 64 | 14.8 | 7.8 | 27.5 | 4407 | 4402 |
| 16 | 30.3 | 334 | 3650 | Y | 102 | 64 | 17.4 | 6.4 | 28.9 | 4458 | 3183 |
| 17 | 29.2 | 363 | 290 | Y | 102 | 64 | 17.0 | 6.7 | 28.9 | 4238 | 3821 |
| 18 | 29.5 | 393 | 2822 | Y | 102 | 64 | 16.7 | 8.8 | 30.7 | 4493 | 3818 |
| 19 | 32.0 | 425 | 257 | Y | 102 | 64 | 19.3 | 7.1 | 31.6 | 4391 | 3852 |
| 20 | 31.2 | 456 | 6131 | Y | 102 | 64 | 18.2 | 6.3 | 29.6 | 4275 | 3530 |
| 21 | 31.4 | 487 | 286 | Y | 102 | 64 | 21.0 | 6.3 | 32.5 | 4350 | 3980 |
| 22 | 33.4 | 521 | 12912 | Y | 102 | 64 | 21.5 | 6.4 | 33.2 | 4253 | 3623 |
| 23 | 32.3 | 553 | 32132 | Y | 102 | 64 | 18.0 | 8.8 | 31.9 | 4244 | 3733 |
| 24 | 36.0 | 589 | 13 | Y | 102 | 64 | 22.7 | 7.6 | 35.7 | 4388 | 4050 |
| 25 | 35.6 | 625 | 314 | Y | 102 | 64 | 22.4 | 6.1 | 33.8 | 4327 | 3480 |
| 26 | 38.8 | 663 | 373 | Y | 102 | 64 | 21.5 | 11.1 | 38.4 | 4199 | 4025 |
| 27 | 34.9 | 698 | 523 | Y | 102 | 64 | 23.3 | 10.4 | 40.5 | 4101 | 3301 |
| 28 | 40.3 | 739 | 6568 | Y | 102 | 64 | 21.4 | 11.5 | 39.8 | 3573 | 3142 |
| 29 | 49.5 | 788 | 284 | Y | 102 | 64 | 28.0 | 8.3 | 43.4 | 4006 | 3689 |
| 30 | 39.6 | 828 | 1949 | Y | 97 | 61 | 18.6 | 13.5 | 39.1 | 3944 | 3783 |
| 31 | 48.2 | 876 | 340 | Y | 107 | 67 | 32.1 | 9.1 | 47.9 | 3906 | 3022 |
| 32 | 45.9 | 922 | 13 | Y | 99 | 61 | 26.4 | 12.2 | 46.1 | 3754 | 2901 |

linear fit s/token = 12.03 + 1.017·k  (rmse 2.53); tokens 2..32: 11.22 + 1.054·k (rmse 2.31)
  RecalcStyleCount: 102.23 + -0.021·k (rmse 2.71)
  LayoutCount: 64.06 + -0.013·k (rmse 1.72)
  RecalcStyleDuration s: 4.86 + 0.689·k (rmse 2.11)
  LayoutDuration s: 2.97 + 0.244·k (rmse 1.41)
  TaskDuration s: 11.31 + 1.036·k (rmse 1.71)

total 922.0 s for 32 tokens; median 29.3; first 18.8; last 45.9; min 13.7; max 49.5
RSS peak during generation 4493 MB; before run 1773 MB; at end 2901 MB
whole-run CDP deltas: RecalcStyleCount 3271, LayoutCount 2050, RecalcStyleDuration 524.9 s, LayoutDuration 224.6 s, TaskDuration 916.6 s, Nodes 169640

    {"t":6414,"event":"prompt-typed","typedPrompt":"I","typedIds":[40],"typeMs":1623.6999999999998,"editorText":".tk-root { --draft-prompt: \"I\"; }","draftPrompt":"\"I\"","ids":[40,-1,-1,-1],"present":[1,0,0,0],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"I\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"]\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\"","sinceNav":5992.4}
    {"t":16677.2,"event":"screenshot","file":"typed-I-run-8s.png","sinceRun":10256.900000000001,"tokensSoFar":0}
    {"t":39813.4,"event":"screenshot","file":"typed-I-run-30s.png","sinceRun":33393.1,"tokensSoFar":1}
    {"t":70821.5,"event":"screenshot","file":"typed-I-run-60s.png","sinceRun":64401.2,"tokensSoFar":3}

### 6.3 demo-c32 typed-once (R6X/run-demo-c32/typed-once.summary.md; screenshots typed-once-run-*s.png, typed-once-final.png)

# typed-once — 32/32 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.1 s, Run at 5.8 s after nav

ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P/reference_ids_once_upon_a_time.json; prompt token default 15496); ids=[262, 257, 640, 11, 262, 995, 373, 257, 1295, 286, 1049, 8737, 290, 1049, 3514, 13, 383, 995, 373, 257, 1295, 286, 1049, 3514, 11, 290, 262, 995, 373, 257, 1295, 286]
first mismatching position: None; mismatches at []

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18.8 | 19 | 262 | Y | 112 | 71 | 9.5 | 5.5 | 19.1 | 2882 | 2762 |
| 2 | 14.0 | 33 | 257 | Y | 102 | 64 | 6.5 | 3.5 | 13.9 | 4270 | 4270 |
| 3 | 14.0 | 47 | 640 | Y | 102 | 64 | 6.8 | 3.3 | 14.0 | 4681 | 4681 |
| 4 | 14.5 | 61 | 11 | Y | 102 | 64 | 7.1 | 3.5 | 14.4 | 4855 | 4818 |
| 5 | 15.1 | 76 | 262 | Y | 102 | 64 | 7.5 | 3.5 | 15.0 | 5147 | 5146 |
| 6 | 15.2 | 92 | 995 | Y | 102 | 64 | 7.4 | 3.7 | 15.1 | 5453 | 5453 |
| 7 | 15.7 | 107 | 373 | Y | 102 | 64 | 7.8 | 3.9 | 15.6 | 5703 | 5703 |
| 8 | 16.1 | 123 | 257 | Y | 102 | 64 | 8.3 | 3.7 | 16.0 | 6108 | 6108 |
| 9 | 16.5 | 140 | 1295 | Y | 102 | 64 | 8.1 | 4.3 | 16.5 | 6449 | 6449 |
| 10 | 17.2 | 157 | 286 | Y | 102 | 64 | 8.5 | 4.5 | 17.1 | 6584 | 6584 |
| 11 | 17.6 | 175 | 1049 | Y | 99 | 62 | 9.1 | 3.9 | 17.2 | 6801 | 6801 |
| 12 | 17.8 | 192 | 8737 | Y | 102 | 64 | 9.6 | 3.9 | 17.6 | 7095 | 7077 |
| 13 | 18.7 | 211 | 290 | Y | 102 | 64 | 10.7 | 4.4 | 19.6 | 7263 | 5420 |
| 14 | 27.1 | 238 | 1049 | Y | 102 | 64 | 15.4 | 5.5 | 25.9 | 4886 | 4243 |
| 15 | 26.6 | 265 | 3514 | Y | 102 | 64 | 13.8 | 7.5 | 26.4 | 4709 | 4188 |
| 16 | 26.6 | 291 | 13 | Y | 102 | 64 | 15.7 | 5.8 | 26.4 | 4884 | 4592 |
| 17 | 27.7 | 319 | 383 | Y | 102 | 64 | 16.5 | 5.9 | 27.5 | 5040 | 5040 |
| 18 | 26.8 | 346 | 995 | Y | 102 | 64 | 15.9 | 5.7 | 26.6 | 5550 | 5246 |
| 19 | 27.5 | 374 | 373 | Y | 102 | 64 | 15.3 | 6.9 | 27.3 | 5400 | 4858 |
| 20 | 31.5 | 405 | 257 | Y | 102 | 64 | 15.0 | 10.8 | 31.2 | 4644 | 4240 |
| 21 | 32.0 | 437 | 1295 | Y | 102 | 64 | 19.4 | 6.8 | 31.7 | 4850 | 3683 |
| 22 | 33.9 | 471 | 286 | Y | 102 | 64 | 20.1 | 9.3 | 35.3 | 4705 | 3545 |
| 23 | 32.4 | 503 | 1049 | Y | 102 | 64 | 17.4 | 7.5 | 30.4 | 4621 | 3897 |
| 24 | 36.3 | 540 | 3514 | Y | 102 | 64 | 20.4 | 9.7 | 36.0 | 4687 | 3485 |
| 25 | 36.1 | 576 | 11 | Y | 102 | 64 | 18.3 | 13.3 | 37.7 | 4353 | 2506 |
| 26 | 44.1 | 620 | 290 | Y | 102 | 64 | 27.7 | 9.4 | 43.4 | 4469 | 2715 |
| 27 | 40.7 | 660 | 262 | Y | 102 | 64 | 26.5 | 8.0 | 40.7 | 4129 | 3334 |
| 28 | 44.7 | 705 | 995 | Y | 102 | 64 | 20.0 | 17.6 | 44.0 | 3764 | 3502 |
| 29 | 42.6 | 748 | 373 | Y | 102 | 64 | 20.0 | 15.7 | 42.0 | 3846 | 3364 |
| 30 | 47.0 | 795 | 257 | Y | 102 | 64 | 25.4 | 12.8 | 44.7 | 3770 | 3024 |
| 31 | 49.1 | 844 | 1295 | Y | 102 | 64 | 25.4 | 16.3 | 48.5 | 3479 | 3068 |
| 32 | 44.1 | 888 | 286 | Y | 99 | 61 | 25.1 | 12.2 | 44.2 | 3752 | 2961 |

linear fit s/token = 8.43 + 1.170·k  (rmse 3.12); tokens 2..32: 7.13 + 1.230·k (rmse 2.59)
  RecalcStyleCount: 101.99 + -0.011·k (rmse 0.76)
  LayoutCount: 64.06 + -0.013·k (rmse 0.64)
  RecalcStyleDuration s: 3.32 + 0.698·k (rmse 2.14)
  LayoutDuration s: 0.62 + 0.406·k (rmse 2.04)
  TaskDuration s: 7.17 + 1.214·k (rmse 2.48)

total 887.8 s for 32 tokens; median 27.0; first 18.8; last 44.1; min 14.0; max 49.1
RSS peak during generation 7263 MB; before run 1739 MB; at end 2961 MB
whole-run CDP deltas: RecalcStyleCount 3269, LayoutCount 2050, RecalcStyleDuration 480.2 s, LayoutDuration 238.5 s, TaskDuration 882.2 s, Nodes 169640

    {"t":6367.8,"event":"prompt-typed","typedPrompt":"Once upon a time","typedIds":[7454,2402,257,640],"typeMs":1620.6000000000004,"editorText":".tk-root { --draft-prompt: \"Once upon a time\"; }","draftPrompt":"\"Once upon a time\"","ids":[7454,2402,257,640],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Once upon a time\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vo
    {"t":18477.9,"event":"screenshot","file":"typed-once-run-10s.png","sinceRun":12104.600000000002,"tokensSoFar":0}
    {"t":48648.1,"event":"screenshot","file":"typed-once-run-40s.png","sinceRun":42274.799999999996,"tokensSoFar":2}
    {"t":79005.3,"event":"screenshot","file":"typed-once-run-70s.png","sinceRun":72632,"tokensSoFar":4}

READY demo-c32: demo-c32 READY 2026-09-30 19:06:53: typed 'I' 32/32 = R4P/reference_ids_32_40.json; typed 'Once upon a time' 32/32 = R6P/reference_ids_once_upon_a_time.json (4 prefilled + 29 generated); runs R6X/run-demo-c32/typed-{I,once}.{json,summary.md}; load-paint R6X/runs/loadpaint-demo-c32/

## 7. v3 display fixes (footer overlap + head-phase segment) — re-verification (auto-appended by R6X/run_chain_v2.sh 2026-09-30 20:48:16)

### 7.1 builds under the lock (R6X/build_v2.sh; R6X/logs/compare_rules-*-v2.log)
```
index.html: IDENTICAL (7130218 vs 7130218 B)
rules: new 67175 vs ref 67166; only in new: 9; only in ref: 0
   only in NEW: ('', '.pg::before,.pg::after', 'content:"";position:absolute;left:484px;top:22px;width:38px;height:8px;display:block')
   only in NEW: ('', '.pg::before', 'background:#e3ded2')
   only in NEW: ('', '.pg::after', 'background:#d9822b;transform-origin:0 50%;transform:scaleX(0);will-change:transform,opacity')
   only in NEW: ('@container corestate style(--held:1)', '.pg::after', 'animation:pg-head-fill 2.8s linear forwards,pg-head-pulse .7s ease-in-out infinite alternate')
   only in NEW: ('@container corestate style(--held:1)', '.pg-lay::after', 'content:" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"')
   only in NEW: ('@keyframes pg-head-fill', 'from', 'transform:scaleX(0)')
   only in NEW: ('@keyframes pg-head-fill', 'to', 'transform:scaleX(1)')
   only in NEW: ('@keyframes pg-head-pulse', 'from', 'opacity:.45')
   only in NEW: ('@keyframes pg-head-pulse', 'to', 'opacity:1')
order of the common rules: IDENTICAL
RESULT: PASS (model rules identical; differences listed above)
### 20:06:35 swapped demo-c32 (v2 in place, old build deleted)
{  "directory": "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-c32",  "staticFiles": 287,  "assetBytes": 299880222,  "runtimeJavaScript": false}
total         299,869,774 B uncompressed
index.html: IDENTICAL (6464488 vs 6464488 B)
rules: new 62485 vs ref 62476; only in new: 9; only in ref: 0
   only in NEW: ('', '.pg::before,.pg::after', 'content:"";position:absolute;left:484px;top:22px;width:38px;height:8px;display:block')
   only in NEW: ('', '.pg::before', 'background:#e3ded2')
   only in NEW: ('', '.pg::after', 'background:#d9822b;transform-origin:0 50%;transform:scaleX(0);will-change:transform,opacity')
   only in NEW: ('@container corestate style(--held:1)', '.pg::after', 'animation:pg-head-fill 2.8s linear forwards,pg-head-pulse .7s ease-in-out infinite alternate')
   only in NEW: ('@container corestate style(--held:1)', '.pg-lay::after', 'content:" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"')
   only in NEW: ('@keyframes pg-head-fill', 'from', 'transform:scaleX(0)')
   only in NEW: ('@keyframes pg-head-fill', 'to', 'transform:scaleX(1)')
   only in NEW: ('@keyframes pg-head-pulse', 'from', 'opacity:.45')
   only in NEW: ('@keyframes pg-head-pulse', 'to', 'opacity:1')
order of the common rules: IDENTICAL
RESULT: PASS (model rules identical; differences listed above)
### 20:06:50 swapped demo-8 (v2 in place, old build deleted)
{  "directory": "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-8",  "staticFiles": 287,  "assetBytes": 288110532,  "runtimeJavaScript": false}
total         288,100,084 B uncompressed
```
### 7.2 demo-c32 load-paint + typed 'Once upon a time' + Run (R6X/runs/loadpaint-demo-c32/: shot-load-*.png, shot-ready.png, shot-typed.png, shot-run-10s.png, shot-run-70s.png, shot-head-{1,1b,2,3}.png, shot-complete.png, shot-complete-900x300.png; v1 probe in loadpaint-demo-c32-v1/)
```
{"t":2562,"event":"load-event","sinceNavMs":2028}
{"t":2706,"event":"screenshot","file":"shot-load-0.5s.png","sinceNavMs":2172}
{"t":2711,"event":"state","tag":"load-0.5s","sinceNavMs":2177,"readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt: none — the dropdown prompt is used. \" counter(tkt0, gpt2-vocabulary) \"\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\""},"pglay":{"display":"i
{"t":2713,"event":"fonts-loaded","sinceNavMs":2177,"readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt: none — the dropdown prompt is used. \" counter(tkt0, gpt2-vocabulary) \"\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\""},"pglay":{"display":"inline","aft
{"t":4371,"event":"prompt-typed","typed":"Once upon a time","tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"}}
{"t":4481,"event":"run-keyed"}
{"t":16401,"event":"screenshot","file":"shot-run-10s.png","sinceRunMs":11921}
{"t":17184,"event":"state","tag":"run-10s","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\
{"t":77465,"event":"screenshot","file":"shot-run-70s.png","sinceRunMs":72985}
{"t":78478,"event":"state","tag":"run-70s","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 5 of 32\
{"t":86364,"event":"screenshot","file":"shot-head-1.png","sinceRunMs":81884,"held":"1","layer":"11","epoch":"5","lay":"\" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)\""}
{"t":90520,"event":"screenshot","file":"shot-head-1b.png","sinceRunMs":86040,"held":"0","layer":"1","epoch":"6","lay":"\" · layer 2 of 12\""}
{"t":103004,"event":"screenshot","file":"shot-head-2.png","sinceRunMs":98524,"held":"1","layer":"11","epoch":"6","lay":"\" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)\""}
{"t":119488,"event":"screenshot","file":"shot-head-3.png","sinceRunMs":115008,"held":"1","layer":"11","epoch":"7","lay":"\" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)\""}
{"t":948787,"event":"run-complete","doneWhy":"token-limit","sinceRunMs":944307}
{"t":951222,"event":"state","tag":"complete","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Complete • 32 tokens\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 32 of 32\""},"pgl
{"t":953275,"event":"state","tag":"complete-900x300","geometry":{"output":{"top":184,"bottom":204,"height":20,"scrollH":64},"footer":{"top":226,"bottom":284,"height":59,"scrollH":59},"overlap":false,"text":1078}}
```
### 7.H headed runs (user report: Complete but no text) — R6X/run-smoke-demo-2L/headed-{plain,space,newline}.*, R6X/run-demo-c32/headed-once.* (screenshots *-ready.png, *-run-10s.png, *-run-60s.png, *-final.png)
```
== /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/run-smoke-demo-2L/headed-plain
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P/reference_ids_once_upon_a_time_2layers.json; prompt token default 15496); ids=[262, 6504, 1178, 640, 5739
{"t":6989.1,"event":"prompt-typed","typedPrompt":"Once upon a time","typedIds":[7454,2402,257,640],"typeMs":1605.1000000000004,"editorText":".tk-root { --draft-prompt: \"Once upon a time\"; }","draftPrompt":"\"Once upon a time\"","ids":[7454,2402,257,640],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Once upon a time\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","sinceNav":5875.400000000001}
{"t":176570.9,"event":"display-dump","display":"block","visibility":"visible","contentVisibility":"visible","opacity":"1","color":"rgb(34, 34, 34)","fontFamily":"system-ui","fontSize":"20px","top":"184px","bottom":"96px","height":"420px","overflow":"auto","rect":{"top":184,"height":420,"width":1052},"scrollHeight":420,"clientHeight":420,"before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","after":"counter(token1, gpt2-vocabulary) counter(token2, gpt2-vocabulary) counter(token3, gpt2-vocabulary) counter(token4, gpt2-vocabulary) counter(token5, gpt2-vocabulary) counter(token6, gpt2-vocabulary) co","displayPrompt":"-1","draftEcho":"\"\"","promptCount":"4","frozenPrompt":"15496","displayTokens":{"1":"-1","2":"-1","3":"-1","4":"640","5":"5739","6":"5739","7":"5739","8":"5739","9":"5739","10":"5739","11":"5739","12":"5739","13":"5739","14":"5739","15":"5739","16":"5739","17":"5739","18":"5739","19":"5739","20":"5739","21":"5739","22":"5739","23":"5739","24":"5739","25":"5739","26":"5739","27":"5739","28":"5739","29":"5739","30":"5739","31":"5739","32":"5739"},"promptTokenIds":{"0":"7454","1":"2402","2":"257","3":"640"},"bodyChildren":[{"tag":"DIV","cls":"controls","cv":"visible"},{"tag":"I","cls":"epoch-reader","cv":"visible"},{"tag":"svg","cls":"svg","cv":"visible"},{"tag":"ASIDE","cls":"tk-aside","cv":"visible"},{"tag":"DIV","cls":"tk-panel","cv":"visible"},{"tag":"DIV","cls":"ld","cv":"visible"},{"tag":"LINK","cls":"LINK","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I
== /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/run-smoke-demo-2L/headed-space
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P/reference_ids_once_upon_a_time_2layers.json; prompt token default 15496); ids=[262, 6504, 1178, 640, 5739
{"t":6382.7,"event":"prompt-typed","typedPrompt":"Once upon a time ","typedIds":[7454,2402,257,640],"typeMs":1602.3999999999996,"editorText":".tk-root { --draft-prompt: \"Once upon a time \"; }","draftPrompt":"\"Once upon a time \"","ids":[7454,2402,257,640],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Once upon a time \" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","sinceNav":5831.9}
{"t":172090.6,"event":"display-dump","display":"block","visibility":"visible","contentVisibility":"visible","opacity":"1","color":"rgb(34, 34, 34)","fontFamily":"system-ui","fontSize":"20px","top":"184px","bottom":"96px","height":"420px","overflow":"auto","rect":{"top":184,"height":420,"width":1052},"scrollHeight":420,"clientHeight":420,"before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","after":"counter(token1, gpt2-vocabulary) counter(token2, gpt2-vocabulary) counter(token3, gpt2-vocabulary) counter(token4, gpt2-vocabulary) counter(token5, gpt2-vocabulary) counter(token6, gpt2-vocabulary) co","displayPrompt":"-1","draftEcho":"\"\"","promptCount":"4","frozenPrompt":"15496","displayTokens":{"1":"-1","2":"-1","3":"-1","4":"640","5":"5739","6":"5739","7":"5739","8":"5739","9":"5739","10":"5739","11":"5739","12":"5739","13":"5739","14":"5739","15":"5739","16":"5739","17":"5739","18":"5739","19":"5739","20":"5739","21":"5739","22":"5739","23":"5739","24":"5739","25":"5739","26":"5739","27":"5739","28":"5739","29":"5739","30":"5739","31":"5739","32":"5739"},"promptTokenIds":{"0":"7454","1":"2402","2":"257","3":"640"},"bodyChildren":[{"tag":"DIV","cls":"controls","cv":"visible"},{"tag":"I","cls":"epoch-reader","cv":"visible"},{"tag":"svg","cls":"svg","cv":"visible"},{"tag":"ASIDE","cls":"tk-aside","cv":"visible"},{"tag":"DIV","cls":"tk-panel","cv":"visible"},{"tag":"DIV","cls":"ld","cv":"visible"},{"tag":"LINK","cls":"LINK","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I
== /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/run-smoke-demo-2L/headed-newline
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P/reference_ids_once_upon_a_time_2layers.json; prompt token default 15496); ids=[262, 6504, 1178, 640, 5739
{"t":6348.5,"event":"prompt-typed","typedPrompt":"Once upon a time\n","typedIds":null,"typeMs":1626.1999999999998,"editorText":".tk-root { --draft-prompt: \"Once upon a time\"; }","draftPrompt":"\"Once upon a time\"","ids":[7454,2402,257,640],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Once upon a time\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","sinceNav":5796.6}
{"t":174710.8,"event":"display-dump","display":"block","visibility":"visible","contentVisibility":"visible","opacity":"1","color":"rgb(34, 34, 34)","fontFamily":"system-ui","fontSize":"20px","top":"184px","bottom":"96px","height":"420px","overflow":"auto","rect":{"top":184,"height":420,"width":1052},"scrollHeight":420,"clientHeight":420,"before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","after":"counter(token1, gpt2-vocabulary) counter(token2, gpt2-vocabulary) counter(token3, gpt2-vocabulary) counter(token4, gpt2-vocabulary) counter(token5, gpt2-vocabulary) counter(token6, gpt2-vocabulary) co","displayPrompt":"-1","draftEcho":"\"\"","promptCount":"4","frozenPrompt":"15496","displayTokens":{"1":"-1","2":"-1","3":"-1","4":"640","5":"5739","6":"5739","7":"5739","8":"5739","9":"5739","10":"5739","11":"5739","12":"5739","13":"5739","14":"5739","15":"5739","16":"5739","17":"5739","18":"5739","19":"5739","20":"5739","21":"5739","22":"5739","23":"5739","24":"5739","25":"5739","26":"5739","27":"5739","28":"5739","29":"5739","30":"5739","31":"5739","32":"5739"},"promptTokenIds":{"0":"7454","1":"2402","2":"257","3":"640"},"bodyChildren":[{"tag":"DIV","cls":"controls","cv":"visible"},{"tag":"I","cls":"epoch-reader","cv":"visible"},{"tag":"svg","cls":"svg","cv":"visible"},{"tag":"ASIDE","cls":"tk-aside","cv":"visible"},{"tag":"DIV","cls":"tk-panel","cv":"visible"},{"tag":"DIV","cls":"ld","cv":"visible"},{"tag":"LINK","cls":"LINK","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I
== /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/run-demo-c32/headed-once
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P/reference_ids_once_upon_a_time.json; prompt token default 15496); ids=[262, 257, 640, 11, 262, 995, 373, 
{"t":6582.6,"event":"prompt-typed","typedPrompt":"Once upon a time","typedIds":[7454,2402,257,640],"typeMs":1613.1000000000004,"editorText":".tk-root { --draft-prompt: \"Once upon a time\"; }","draftPrompt":"\"Once upon a time\"","ids":[7454,2402,257,640],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Once upon a time\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","sinceNav":6000.200000000001}
{"t":833581.2,"event":"display-dump","display":"block","visibility":"visible","contentVisibility":"visible","opacity":"1","color":"rgb(34, 34, 34)","fontFamily":"system-ui","fontSize":"20px","top":"184px","bottom":"96px","height":"420px","overflow":"auto","rect":{"top":184,"height":420,"width":1052},"scrollHeight":420,"clientHeight":420,"before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","after":"counter(token1, gpt2-vocabulary) counter(token2, gpt2-vocabulary) counter(token3, gpt2-vocabulary) counter(token4, gpt2-vocabulary) counter(token5, gpt2-vocabulary) counter(token6, gpt2-vocabulary) co","displayPrompt":"-1","draftEcho":"\"\"","promptCount":"4","frozenPrompt":"15496","displayTokens":{"1":"-1","2":"-1","3":"-1","4":"11","5":"262","6":"995","7":"373","8":"257","9":"1295","10":"286","11":"1049","12":"8737","13":"290","14":"1049","15":"3514","16":"13","17":"383","18":"995","19":"373","20":"257","21":"1295","22":"286","23":"1049","24":"3514","25":"11","26":"290","27":"262","28":"995","29":"373","30":"257","31":"1295","32":"286"},"promptTokenIds":{"0":"7454","1":"2402","2":"257","3":"640"},"bodyChildren":[{"tag":"DIV","cls":"controls","cv":"visible"},{"tag":"I","cls":"epoch-reader","cv":"visible"},{"tag":"svg","cls":"svg","cv":"visible"},{"tag":"ASIDE","cls":"tk-aside","cv":"visible"},{"tag":"DIV","cls":"tk-panel","cv":"visible"},{"tag":"DIV","cls":"ld","cv":"visible"},{"tag":"LINK","cls":"LINK","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness"
```
### 7.3 demo-8 Hello correctness guard (R6X/run-demo-8/; v1 run in run-demo-8-v1/)
```
{"t":2659,"event":"loaded","elements":67596,"fonts":285}
{"t":26250,"event":"token-captured","token":1,"sinceRunMs":21542}
{"t":39209,"event":"token-captured","token":2,"sinceRunMs":34501}
{"t":50353,"event":"token-captured","token":3,"sinceRunMs":45645}
{"t":61994,"event":"token-captured","token":4,"sinceRunMs":57286}
{"t":81422,"event":"token-captured","token":5,"sinceRunMs":76714}
{"t":92958,"event":"token-captured","token":6,"sinceRunMs":88250}
{"t":111797,"event":"token-captured","token":7,"sinceRunMs":107089}
{"t":123494,"event":"token-captured","token":8,"sinceRunMs":118786}
{"t":129496,"event":"final","packedBanks":true,"packedHead":true,"headSample":"\"X000\" -12,\"X001\" -4,\"X002\" 4,\"X003\" -13,\"X004\" 8,\"X005\" -20,\"X006\" 89,\"X007\" -5,\"X008\" 5,\"X009\" 9,\"X00A\" -3,\"X00B\" -11,","tokens":[11,314,1101,7926,11,475,314,1101],"tokensText":"","bodyProps":{"--epoch":"8","--winner":"-1","--head-output-epoch":"0","--token":"15496"},"doneMarkers":{"1":true,"2":true,"3":true,"4":true,"5":true,"6":true,"7":true,"8":true},"rawSample":{"k":{"list":"\"K000\" -0.5
verify rc=0 {'tokens': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceQ9Q16': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceAttentionMask': 'full causal', 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.016997776885828732, 'maximum': 0.14188476906986125}, 'finalHeadActualInputWinner': 1101, 'finalHeadMatchesActualInpu
RSS renderer peak MB: 5647
```
READY demo-8: demo-8 v2 READY 2026-09-30 20:48:16: display-only rebuild v3 (layout rule html .visible-output{bottom:96px;overflow:auto} + head-phase 13th segment .pg::before/::after; rules otherwise identical to v1, R6X/logs/compare_rules-demo-8-v2.log); dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], verify rc=0, run R6X/run-demo-8 (v1 run: R6X/run-demo-8-v1)

READY demo-c32: demo-c32 v2 2026-09-30 20:48:16: display-only rebuild v3 (layout rule html .visible-output{bottom:96px;overflow:auto} + head-phase 13th segment .pg::before/::after with estimated 2.8 s fill; index.html byte-identical and all other rules identical to the v1 build whose typed runs gave 32/32 + 32/32, R6X/logs/compare_rules-demo-c32-v2.log); v2 probe R6X/runs/loadpaint-demo-c32 (typed 'Once upon a time', shots run-10s / run-70s / head-1..3 (vocabulary-head phase) / complete / complete-900x300; geometry at completion: "overlap":false); demo-8 v2 Hello 8/8 guard: see bundles/demo-8/READY

### 7.S Summary of §7 (R6X, 20:55)

**Rebuild identity.** `compare_rules.py` (rule multiset + order via R6V's cssindex, index.html bytes): v2 vs v1 = +1 rule (`html .visible-output{bottom:96px;overflow:auto}`), v3 vs
v2 = +9 rules (`.pg::before,.pg::after{…left:484px;top:22px;width:38px;height:8px}`, `.pg::before{background:#e3ded2}`, `.pg::after{background:#d9822b;transform:scaleX(0);
will-change:transform,opacity}`, `@container corestate style(--held:1){.pg::after{animation:pg-head-fill 2.8s linear forwards,pg-head-pulse .7s ease-in-out infinite alternate}
.pg-lay::after{content:" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"}}`, 2 keyframes × from/to); nothing only in the reference, common-rule order identical,
index.html identical (7,130,218 / 6,464,488 B) → the v1 ids results (typed "I" 32/32, "Once upon a time" 32/32, Hello 8/8) transfer, and the v3 guard (demo-8 Hello 8/8 + verify rc 0,
rmse 0.016998) and the v3 typed probe (32 tokens, ids not compared by the probe; the headed demo-c32 run below is 32/32 on v3) confirm.

**Head-phase segment.** Transform/opacity only, two pseudo-elements of the existing 8-element `.pg` reader (no DOM change, no new container-query dependents beyond `.pg` itself).
Evidence: the probe's 1 Hz readback caught `--held:1` with the new label three times (epochs 5, 6, 7: `shot-head-{1,2,3}.png` log lines) but the screenshots themselves landed ≈4 s
later on the busy main thread, after the next token's layer 1 had started (the head phase is ≈2–3 s; a screenshot forces a frame that queues behind the model's style/layout work) —
so the mid-run pictures show the grey bar at "layer 1 of 12"; the orange segment with the head label is visible in `shot-complete.png`, `shot-complete-900x300.png` and
`run-demo-c32/headed-once-final.png` (`--held` stays 1 after the last token). The 2.8 s fill is an estimate (R5A §1 / coordinator ≈2.6–3 s); the exact signal is the segment's colour
and the label.

**Footer overlap.** At 900×600 the output box is 320 px tall, 2 lines of text, footer at the bottom, geometry `overlap:false`; at 900×300 the box is 20 px tall (`bottom:96px` leaves
300 − 184 − 96), `overlap:false` but the text is cropped to the top 20 px of its first line and scrolls (`scrollHeight` 64) — see `shot-complete-900x300.png`. **Trade-off to decide:** in
a window (or zoom level) with < ≈320 CSS px of height the output is mostly hidden instead of overlapping the footer; a `min-height` on the box would restore the text at the cost of
the footer overlap in such windows. Not changed (coordinator: report first).

**User report "Complete · 32 tokens but no text" — not reproduced; what was checked.** Headed Chrome (real window 1100×700, `tools/launch_browser_gpt2.py --no-open` serving, the same
machine under memory pressure: swap 2.5–3.4 GB), typed via the editor exactly as a user would (select-all + insertText):
| run | ids | display dump at Complete |
|---|---|---|
| smoke 2L typed "Once upon a time" | 32/32 vs R6P's 2-layer reference | `#visible-output`: display block, visibility visible, content-visibility visible, opacity 1, color rgb(34,34,34), 20 px system-ui, top 184 / bottom 96 / height 420 (box 1052×420), overflow auto; `--prompt-count` 4, `--prompt-token-id-0..3` = 7454/2402/257/640, `--display-token-1..3` −1 (hidden prefill winners), `--display-token-4..32` = the generated ids; `::before` = `counter(prompt) "" counter(tkp0..3)`, `::after` = `counter(token1..32)`; every body child `content-visibility: visible`; `.tk-root` display contents; status "Complete • 32 tokens" |
| … typed "Once upon a time " (trailing space) | 32/32; live ids identical [7454, 2402, 257, 640] (the 5th token, " " = 220, is beyond the 4 slots) | same as above |
| … typed "Once upon a time\n" | 32/32 — **but the newline did not reach the editor**: Playwright's `fill()` on the `plaintext-only` `<style>` normalised the trailing "\n" away (`editorText` has no newline), so this run equals the plain one; the Enter-key case remains untested by the harness. By the CSS grammar an unescaped newline inside the string makes the declaration invalid → `--draft-prompt` "" → dropdown fallback (readout "none"), text still visible | same as above |
| **demo-c32 headed, typed "Once upon a time"** | **32/32** vs `R6P/reference_ids_once_upon_a_time.json`, 824 s, load 1.9 s, k=1 17.9 s | same as above with the 12-layer ids (`--display-token-4` = 11 ","); screenshots `headed-once-{ready,run-10s,run-60s,final}.png` all show the text |

Hypothesis (a) — the early-paint lock: ruled out for the observed states (every body child reports `content-visibility: visible` at Complete; the lock's inline rule is overridden by
the same selector at the end of runtime.css, and the body child above the model, `.tk-root`, is `display:contents`, which has no box for content-visibility to act on; a page whose
model reached "Complete" was styled and laid out). Hypothesis (b) — typed-path counters: ruled out for these inputs (count 4, ids armed, display tokens resolved; an invalid
counter-reset would show 32 × "!" rather than nothing, an invalid `content` would drop the pseudo — neither seen). **What could still produce "status but no text" in the user's
Chrome:** (1) with v2/v3's `bottom:96px`, a CSS viewport shorter than ≈280 px (small window, or a large zoom factor: 700 px at 250 % = 280 CSS px) gives the output box ≤ 0–20 px →
text clipped away while the status line stays visible — the only mechanism found that matches the symptom; if the user viewed v1 (before 19:24) this does not apply and the symptom
is unexplained; (2) the output box scrolled (v2/v3: `overflow:auto`) — a wheel gesture over it scrolls the text out of a short box; (3) things the harness cannot type: Enter in the
editor (declaration dropped → dropdown fallback, but the text would still show), smart quotes / non-ASCII (tokenizer mismatch, text still shows). Recommended next step for the
coordinator/user: Chrome version + window size + zoom, and whether the text appears after resizing the window taller; if confirmed, replace `bottom:96px` by
`max-height:calc(100vh - 280px);min-height:4lh` (footer overlap only in very short windows).

## 8. v4 robust output sizing — re-verification (auto-appended by R6X/run_chain_v4.sh 2026-09-30 22:03:34)

### 8.1 builds under the lock (R6X/logs/compare_rules-*-v2.log = v4 vs shipped v3)
```
index.html: IDENTICAL (7130218 vs 7130218 B)
rules: new 67176 vs ref 67175; only in new: 2; only in ref: 1
   only in NEW: ('', 'html .visible-output', 'max-height:calc(100vh - 280px);min-height:4lh;overflow:auto')
   only in NEW: ('', 'html .tk-aside', 'top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto')
   only in REF: ('', 'html .visible-output', 'bottom:96px;overflow:auto')
order of the common rules: IDENTICAL
RESULT: PASS (common rules identical in multiset and order; differences listed above)
### 21:15:57 swapped demo-c32 (new build live; previous kept as bundles/demo-c32.prev)
{  "directory": "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-c32",  "staticFiles": 287,  "assetBytes": 299880336,  "runtimeJavaScript": false}
total         299,869,888 B uncompressed
index.html: IDENTICAL (6464488 vs 6464488 B)
rules: new 62486 vs ref 62485; only in new: 2; only in ref: 1
   only in NEW: ('', 'html .visible-output', 'max-height:calc(100vh - 280px);min-height:4lh;overflow:auto')
   only in NEW: ('', 'html .tk-aside', 'top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto')
   only in REF: ('', 'html .visible-output', 'bottom:96px;overflow:auto')
order of the common rules: IDENTICAL
RESULT: PASS (common rules identical in multiset and order; differences listed above)
### 21:16:13 swapped demo-8 (new build live; previous kept as bundles/demo-8.prev)
{  "directory": "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-8",  "staticFiles": 287,  "assetBytes": 288110646,  "runtimeJavaScript": false}
total         288,100,198 B uncompressed
```
### 8.2 probe 900x300 (R6X/runs/loadpaint-demo-c32-v4-900x300/: shot-ready.png, shot-typed.png, shot-run-10s.png, shot-complete.png, shot-complete-900x300.png)
```
{"t":2920,"event":"load-event","sinceNavMs":1905}
{"t":3076,"event":"fonts-loaded","sinceNavMs":2059,"readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt: none — the dropdown prompt is used. \" counter(tkt0, gpt2-vocabulary) \"\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\""},"pglay":{"display":"inline","aft
{"t":17352,"event":"state","tag":"run-10s","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\
{"t":908351,"event":"run-complete","doneWhy":"token-limit","sinceRunMs":903549}
{"t":911122,"event":"state","tag":"complete","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Complete • 32 tokens\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 32 of 32\""},"pgl
{"t":912883,"event":"state","tag":"complete-900x300","geometry":{"output":{"top":184,"bottom":312,"height":128,"scrollH":128},"footer":{"top":320,"bottom":379,"height":59,"scrollH":59},"overlap":false,"text":1078}}
```
### 8.2 probe 1100x700 (R6X/runs/loadpaint-demo-c32-v4-1100x700/: shot-ready.png, shot-typed.png, shot-run-10s.png, shot-complete.png, shot-complete-900x300.png)
```
{"t":3894,"event":"load-event","sinceNavMs":2709}
{"t":4053,"event":"fonts-loaded","sinceNavMs":2866,"readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt: none — the dropdown prompt is used. \" counter(tkt0, gpt2-vocabulary) \"\" counter(tkt1, gpt2-vocabulary) \"\" counter(tkt2, gpt2-vocabulary) \"\" counter(tkt3, gpt2-vocabulary) \"\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\""},"pglay":{"display":"inline","aft
{"t":18577,"event":"state","tag":"run-10s","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Ready • 12-block native compute\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 1 of 32\
{"t":1012830,"event":"run-complete","doneWhy":"token-limit","sinceRunMs":1007030}
{"t":1015585,"event":"state","tag":"complete","readyState":"complete","elements":86510,"fonts":285,"status":{"display":"inline","after":"\"Complete • 32 tokens\""},"editor":{"display":"block","text":".tk-root { --draft-prompt: \"Once upon a time\"; }"},"tkTokens":{"display":"block","after":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\""},"ld":{"display":"block","after":"none"},"ldn":{"display":"block","after":"\"Loading model weights: 0 of 285 fonts\""},"pgtok":{"display":"inline","after":"\"token 32 of 32\""},"pg
{"t":1017861,"event":"state","tag":"complete-900x300","geometry":{"output":{"top":184,"bottom":312,"height":128,"scrollH":128},"footer":{"top":320,"bottom":379,"height":59,"scrollH":59},"overlap":false,"text":1078}}
```
### 8.3 demo-8 Hello guard (R6X/run-demo-8/)
```
{"t":163421,"event":"final","packedBanks":true,"packedHead":true,"headSample":"\"X000\" -12,\"X001\" -4,\"X002\" 4,\"X003\" -13,\"X004\" 8,\"X005\" -20,\"X006\" 89,\"X007\" -5,\"X008\" 5,\"X009\" 9,\"X00A\" -3,\"X00B\" -11,","tokens":[11,314,1101,7926,11,475,314,1101],"tokensText":"","bodyProps":{"-
verify rc=0 {'tokens': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceQ9Q16': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceAttentionMask': 'full causal', 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.0169977768858287
RSS renderer peak MB: 3867
```
READY demo-8: demo-8 v4 READY 2026-09-30 22:03:34: display-only rebuild v4 (html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto} + html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto} replace v2's bottom:96px; rules otherwise identical to v3, R6X/logs/compare_rules-demo-8-v2.log); dropdown Hello ids 8/8 [11,314,1101,7926,11,475,314,1101], verify rc=0, run R6X/run-demo-8 (v3 run: run-demo-8-v3, v1: run-demo-8-v1)

READY demo-c32: demo-c32 v4 2026-09-30 22:03:34: display-only rebuild v4 (output box max-height:calc(100vh - 280px)/min-height:4lh/overflow:auto, footer placed below the output's maximum extent; replaces v2's bottom:96px which clipped the box in short windows; index.html byte-identical and all other rules identical to v3 — R6X/logs/compare_rules-demo-c32-v2.log); probes R6X/runs/loadpaint-demo-c32-v4-{900x300,1100x700} typed 'Once upon a time' to Complete: 900x300 "overlap":false, 1100x700 "overlap":false; demo-8 v4 Hello 8/8 guard: see bundles/demo-8/READY

## 9. User report #2 — typed "Shubham was" (auto-appended by R6X/run_chain_v5.sh 2026-09-30 22:24:03)

Reference: R6X/reference_ids_shubham_was.json (R6P/reference_prompt.py on R6X/tools): [2484, 549, 2763, 373] [13, 259, 338, 257, 2888, 286, 262, 471, 13, 50, 13, 2097, 286, 17132, 422, 9162, 284, 7358, 13, 679, 373, 257, 2888, 286, 262, 471, 13, 50, 13, 3845, 422, 9162] 'Shubham was a member of the U.S. House of Representatives from 1994 to 1999. He was a member of the U.S. Senate from 1994'

### /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/run-smoke-demo-2L/headed-shubham (screenshots *-ready.png, *-run-{5,30,90}s.png, *-final.png)
```
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was_2layers.json; prompt token default 15496); ids=[11, 4623, 647, 407, 6646, 6646, 6646, 6646, 6646, 6646, 6646, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418, 2418]
{"t":7227.6,"event":"prompt-typed","typedPrompt":"Shubham was","typedIds":[2484,549,2763,373],"typeMs":1602.5,"editorText":".tk-root { --draft-prompt: \"Shubham was\"; }","draftPrompt":"\"Shubham was\"","ids":[2484,549,2763,373],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Shubham was\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","sinceNav":6004.400000000001}
{"t":17485.2,"event":"shot-dump","s":5,"promptCount":"4","displayPrompt":"-1","draftEcho":"\"\"","before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","innerText":"","promptTokenIds":["2484","549","2763","373"],"displayTokens":["-1","-1","-1","-1","-1","-1","-1","-1"],"feedback":["11","-1","-1","-1","-1","-1","-1","-1"],"tkTokens":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","tkIds":["2484","549","2763","373"],"tkHigh3":{"promptCount":"4","ids":["2484","549","2763","373"],"present":["1","1","1","1"]},"token":"2484","epoch":"1"}
{"t":42880.7,"event":"shot-dump","s":30,"promptCount":"4","displayPrompt":"-1","draftEcho":"\"\"","before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","innerText":"","promptTokenIds":["2484","549","2763","373"],"displayTokens":["-1","-1","-1","407","6646","-1","-1","-1"],"feedback":["11","4623","647","407","6646","-1","-1","-1"],"tkTokens":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","tkIds":["2484","549","2763","373"],"tkHigh3":{"promptCount":"4","ids":["2484","549","2763","373"],"present":["1","1","1","1"]},"token":"6646","epoch":"6"}
{"t":104889.5,"event":"shot-dump","s":90,"promptCount":"4","displayPrompt":"-1","draftEcho":"\"\"","before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","innerText":"","promptTokenIds":["2484","549","2763","373"],"displayTokens":["-1","-1","-1","407","6646","6646","6646","6646"],"feedback":["11","4623","647","407","6646","6646","6646","6646"],"tkTokens":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","tkIds":["2484","549","2763","373"],"tkHigh3":{"promptCount":"4","ids":["2484","549","2763","373"],"present":["1","1","1","1"]},"token":"2418","epoch":"17"}
{"t":208392.6,"event":"display-dump","display":"block","visibility":"visible","contentVisibility":"visible","opacity":"1","color":"rgb(34, 34, 34)","fontFamily":"system-ui","fontSize":"20px","top":"184px","bottom":"96px","height":"420px","overflow":"auto","rect":{"top":184,"height":420,"width":1052},"scrollHeight":420,"clientHeight":420,"before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","after":"counter(token1, gpt2-vocabulary) counter(token2, gpt2-vocabulary) counter(token3, gpt2-vocabulary) counter(token4, gpt2-vocabulary) counter(token5, gpt2-vocabulary) counter(token6, gpt2-vocabulary) co","displayPrompt":"-1","draftEcho":"\"\"","promptCount":"4","frozenPrompt":"15496","displayTokens":{"1":"-1","2":"-1","3":"-1","4":"407","5":"6646","6":"6646","7":"6646","8":"6646","9":"6646","10":"6646","11":"6646","12":"2418","13":"2418","14":"2418","15":"2418","16":"2418","17":"2418","18":"2418","19":"2418","20":"2418","21":"2418","22":"2418","23":"2418","24":"2418","25":"2418","26":"2418","27":"2418","28":"2418","29":"2418","30":"2418","31":"2418","32":"2418"},"promptTokenIds":{"0":"2484","1":"549","2":"2763","3":"373"},"bodyChildren":[{"tag":"DIV","cls":"controls","cv":"visible"},{"tag":"I","cls":"epoch-reader","cv":"visible"},{"tag":"svg","cls":"svg","cv":"visible"},{"tag":"ASIDE","cls":"tk-aside","cv":"visible"},{"tag":"DIV","cls":"tk-panel","cv":"visible"},{"tag":"DIV","cls":"ld","cv":"visible"},{"tag":"LINK","cls":"LINK","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I
```
### /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/run-demo-c32/headed-shubham (screenshots *-ready.png, *-run-{5,30,90}s.png, *-final.png)
```
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was.json; prompt token default 15496); ids=[13, 259, 338, 257, 2888, 286, 262, 471, 13, 50, 13, 2097, 286, 17132, 422, 9162, 284, 7358, 13, 679, 373, 257, 2888, 286, 262, 471, 13, 50, 13, 3845, 422, 9162]
{"t":8035.7,"event":"prompt-typed","typedPrompt":"Shubham was","typedIds":[2484,549,2763,373],"typeMs":1619.3999999999996,"editorText":".tk-root { --draft-prompt: \"Shubham was\"; }","draftPrompt":"\"Shubham was\"","ids":[2484,549,2763,373],"present":[1,1,1,1],"armed":[-1,-1,-1,-1],"promptCount":0,"visibleBefore":"counter(prompt, gpt2-vocabulary) \"Shubham was\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","tokensReadout":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","sinceNav":6900.2}
{"t":17078.9,"event":"shot-dump","s":5,"promptCount":"4","displayPrompt":"-1","draftEcho":"\"\"","before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","innerText":"","promptTokenIds":["2484","549","2763","373"],"displayTokens":["-1","-1","-1","-1","-1","-1","-1","-1"],"feedback":["-1","-1","-1","-1","-1","-1","-1","-1"],"tkTokens":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","tkIds":["2484","549","2763","373"],"tkHigh3":{"promptCount":"4","ids":["2484","549","2763","373"],"present":["1","1","1","1"]},"token":"2484","epoch":"1"}
{"t":41236.5,"event":"shot-dump","s":30,"promptCount":"4","displayPrompt":"-1","draftEcho":"\"\"","before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","innerText":"","promptTokenIds":["2484","549","2763","373"],"displayTokens":["-1","-1","-1","-1","-1","-1","-1","-1"],"feedback":["13","-1","-1","-1","-1","-1","-1","-1"],"tkTokens":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","tkIds":["2484","549","2763","373"],"tkHigh3":{"promptCount":"4","ids":["2484","549","2763","373"],"present":["1","1","1","1"]},"token":"549","epoch":"2"}
{"t":103790.7,"event":"shot-dump","s":90,"promptCount":"4","displayPrompt":"-1","draftEcho":"\"\"","before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","innerText":"","promptTokenIds":["2484","549","2763","373"],"displayTokens":["-1","-1","-1","257","2888","-1","-1","-1"],"feedback":["13","259","338","257","2888","-1","-1","-1"],"tkTokens":"\"Typed prompt → GPT-2 tokens (first 4 used, each costs one full step): [\" counter(tkt0, gpt2-vocabulary) \"][\" counter(tkt1, gpt2-vocabulary) \"][\" counter(tkt2, gpt2-vocabulary) \"][\" counter(tkt3, gpt2-vocabulary) \"]\"","tkIds":["2484","549","2763","373"],"tkHigh3":{"promptCount":"4","ids":["2484","549","2763","373"],"present":["1","1","1","1"]},"token":"2888","epoch":"6"}
{"t":986652.8,"event":"display-dump","display":"block","visibility":"visible","contentVisibility":"visible","opacity":"1","color":"rgb(34, 34, 34)","fontFamily":"system-ui","fontSize":"20px","top":"184px","bottom":"388px","height":"128px","overflow":"auto","rect":{"top":184,"height":128,"width":1052},"scrollHeight":128,"clientHeight":128,"before":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)","after":"counter(token1, gpt2-vocabulary) counter(token2, gpt2-vocabulary) counter(token3, gpt2-vocabulary) counter(token4, gpt2-vocabulary) counter(token5, gpt2-vocabulary) counter(token6, gpt2-vocabulary) co","displayPrompt":"-1","draftEcho":"\"\"","promptCount":"4","frozenPrompt":"15496","displayTokens":{"1":"-1","2":"-1","3":"-1","4":"257","5":"2888","6":"286","7":"262","8":"471","9":"13","10":"50","11":"13","12":"2097","13":"286","14":"17132","15":"422","16":"9162","17":"284","18":"7358","19":"13","20":"679","21":"373","22":"257","23":"2888","24":"286","25":"262","26":"471","27":"13","28":"50","29":"13","30":"3845","31":"422","32":"9162"},"promptTokenIds":{"0":"2484","1":"549","2":"2763","3":"373"},"bodyChildren":[{"tag":"DIV","cls":"controls","cv":"visible"},{"tag":"I","cls":"epoch-reader","cv":"visible"},{"tag":"svg","cls":"svg","cv":"visible"},{"tag":"ASIDE","cls":"tk-aside","cv":"visible"},{"tag":"DIV","cls":"tk-panel","cv":"visible"},{"tag":"DIV","cls":"ld","cv":"visible"},{"tag":"LINK","cls":"LINK","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","cv":"visible"},{"tag":"I","cls":"font-witness","c
```

### 9.S Summary (R6X, 22:30) — user report #2 ("Shubham was": blank through the prefill, then a single "t") NOT reproduced

- Reference (`R6X/reference_ids_shubham_was.json`, `R6P/reference_prompt.py` on the merged tools): prompt [2484, 549, 2763, 373] ("Sh","ub","ham"," was"), 28 generated → "Shubham was a member
  of the U.S. House of Representatives from 1994 to 1999. He was a member of the U.S. Senate from 1994"; quantized == float, teacher-forced == winners. 2-layer twin for the smoke.
- HEADED runs (Chrome 154.0.8037.58, real 1100×700 window, `tools/launch_browser_gpt2.py --no-open` serving, typed by select-all + insertText): 2-layer smoke **32/32** (4 min); demo-c32
  (v4 build) **32/32** in 975.7 s (load 3.1 s, k=1 21.4 s). Dumps at 5/30/90 s and at Complete: live readout "[Sh][ub][ham][ was]", `.tk-high-3` present [1,1,1,1], `--prompt-count` 4,
  `--prompt-token-id-0..3` = 2484/549/2763/373, `.feedback-select --token` = 2484 (epoch 1) / 549 (epoch 2) / 2888 (epoch 6), `--display-token-1..3` −1 (hidden prefill winners),
  `--display-token-4` = 257 " a" and `-5` = 2888 " member" the moment they are captured; `#visible-output` innerText "" (the text lives in `::before`/`::after`, as designed).
  Screenshots: `headed-shubham-run-5s.png` shows "Shubham was" echoed during the prefill, `headed-shubham-final.png` the full reference text — i.e. id readback (advances 2485/64 =
  38.828125, 550/64, 2764/64, 374/64 px are exact LayoutUnits), arming/latch, prefill wiring and the display relay are all correct for this prompt, as for "Once upon a time".
- Both suspected causes are therefore ruled out on this build: not the readback (readout and armed ids right), not the display relay for prefilled epochs (counters show the prompt
  symbols "Sh"/"ub"/"ham"/" was" and the generated ids). The "t" the user saw (id 83) is not a correct-id display defect: with correct ids token 4 is " a" and token 5 " member".
  A blank `::before` needs `--display-prompt` −1 AND `--draft-echo` "" AND the four `tkp` counters at −1 simultaneously, i.e. `--pt-present-0` 1 and `--prompt-count` ≠ 0 but
  `--prompt-token-id-k` −1 — not constructible from the emitted rules (ids and count are derived from the same `--pt-present-k`/`--pt-id-k` on the same elements).
- What remains plausible: (1) the user's tab had files from different builds (they tested during the 19:23 / 20:06 / 21:15 swaps) or a stale cached `runtime.css` — now mitigated by the
  `.next`/`.prev` protocol; (2) the user pressed Run before "Ready" — the latch then freezes count 0 / ids −1 and the run is the dropdown Hello run with the typed text echoed (text, not
  blank); (3) hand-typing side effects the harness cannot produce (macOS autocorrect/auto-capitalisation inside the editable rule, a pasted newline, smart quotes) → an invalid rule falls
  back to the dropdown (text, not blank). None yields "blank, then t". Ask the user for: Chrome version, the exact editor text and the readout line at Complete (copy/paste), a screenshot,
  the time the page was loaded, and whether a hard reload reproduces it; a fresh load of the current `bundles/demo-c32` with "Shubham was" should print the reference text above.

## 10 (preface, written before the v5 chain ran — R6X, 2026-10-01 02:00). Why the page could show the typed prompt while the model ran the dropdown prompt

**What Reset does today.** `<form style="display:inline" action="index.html"><button>Reset</button></form>` — a GET form submission, i.e. a fresh navigation to
`index.html` (no state survives: the checkbox is unchecked, the editor is back to the empty rule, every counter/handshake/latch is gone). Only a browser *Reload* behaves
differently: Chrome restores form-control state on reload, so the Run checkbox comes back checked and the run starts at Ready — the editor text is not a form control and is
not restored.

**Where the model's prompt and the display's prompt come from (v1–v4 wiring).** Typing sets the private `--draft-prompt`; the tokenizer chain produces the live per-slot
values `--pt-id-k` / `--pt-present-k`; the readout line (`.tk-tokens`) prints the live values. The MODEL-facing values on `.tk-high-k` are `--prompt-token-id-k = if(armed) pt-id-k
else -1`, `--prompt-has-k`, `--prompt-count` (armed = `#run:checked`), frozen by an 86,400 s transition latch once `#fonts-loaded.done` and `#run-latched.done` exist;
`.feedback-select{--token}` reads them at epochs 1..4; `.visible-output` hides winners 1..3 with `style(--prompt-count:…)` and prints the prompt from the same armed ids —
but its pre-Run preview used the LIVE `--pt-present-0` and the draft text. So the display's *count* and the model's *count* are the same inherited property, and a spatial
disagreement is not constructible; what the user's screenshot shows ("Shubham was" echoed, winners 1–3 hidden, the Hello trajectory "," after the 5th capture) is a
**temporal** one: the model consumed its epoch-1 input while the count/ids were still the pre-arming values, the display evaluated them after arming.

**Race R2 (the one R6P flagged in R6P.md §7.3).** The core's layer 0 waits for `--embed-ready:1` on `.embedding-receipt`, `1 − min(1, |decode(--embed-stamp) − --epoch|)`,
where the stamp is a view-timeline readback of the marker `width:calc(20000px + var(--epoch)*1024px)` inside the embedding source. The stamp encodes the **epoch only**.
Before Run `body{--epoch:1}`, `--token` falls back to `--frozen-prompt` (the dropdown token), and the idle embedding of *Hello* is already laid out and stamped "1" → the
receipt is already satisfied. At Run `--token` switches to the typed id → the embedding must re-layout and its 768 `--embed-t*` view-timeline readbacks must land (≥ 2 frames,
R4T's ≈28 ms servicing floor per frame, more under memory pressure or at 150 % zoom) — the only thing that kept layer 0 from reading the stale Hello embedding was that the
core unlock (`#run-latched.done`, a SMIL tick after the click) usually came later. Dropdown runs never change `--token` at Run and are immune — exactly the user's pattern
(dropdown fine, typed prompt wrong) and ours (headless/headed harness runs fast enough to win the race, 10/10).

**Race R1 (the coordinator's).** A CSS transition starts when the *after-change* style has the property in `transition-property` and the value differs from the
*before-change* style; the frozen value during the 86,400 s delay is the before-change one. If Blink ever recomputes `.tk-high-k` for the first time in the same pass in
which the latch rule begins to apply (the armed values propagate from `body` through four explicit `inherit` hops of a non-inherited property), the latch freezes −1 / 0 for a
day — the model runs the dropdown prompt with count 0 and the readout still shows the typed ids. No CSS rewrite can make a same-pass latch safe; the fix is to need no latch.

**Fix (v5, `R6X/apply_conflicts.py` edit 6; model core rules identical, `R6X/check_v5_identity.py`).**
1. Token-fresh receipt: the marker becomes `calc(20000px + (var(--epoch) - 1 + var(--prompt-live))*1024px)`; `--prompt-live` (registered inherited `<integer>`, 0 → 1 at
   arming, set on `.tk-root`) is inherited by the embedding. Before Run the stamp decodes to 0 ≠ epoch 1 → `--embed-ready` 0; at Run the marker and the token change in the
   same style pass, re-layout together, and their readbacks land in the same later frame → when the stamp says 1 the `--embed-t*` values are the typed token's. Epochs ≥ 2 are
   unchanged (`--prompt-live` stays 1). The dropdown path gains the same one-frame receipt wait — harmless.
2. No latch: arming is sticky (`body:has(#run:checked), body:has(#run-latched.done){--prompt-armed:1}` — survives unchecking "Run / continue"), the editor is read-only from
   `#run:checked` itself (not two frames later), and the Run label is enabled only after `#fonts-loaded.done` (the tokenizer fonts must be in before any id can be armed) → no
   model-facing value can change after the click, so nothing needs freezing and R1 cannot occur.
3. Display from the model-facing values: `--display-prompt = if(armed: if(--prompt-has-0: -1 else frozen-prompt); else: live preview)`, `--draft-echo = if(armed: "" else
   draft)` — from the click on, the output prints exactly `--prompt-token-id-k` (what the model consumed) or the dropdown symbol when `--prompt-count` is 0, and the hide-rules use
   the same `--prompt-count`; the output can never show a prompt the model did not use.
Results of the per-frame ordering probe (old vs fixed 2-layer smoke, keystrokes + mouse click + 150 % zoom), the atomic rebuild and the guards follow in the auto-appended §10 sections.

### 10.M The 13/32 headed "Shubham was" guard (2026-10-01 11:06–11:16) and the margin analysis (R6X, 11:25)

> **Correction (13:10):** the load explanation below is WITHDRAWN. The quiet re-run (§10.R: load1 4 at start, full cap, 32 captures in 836 s) gave the same 13/32
> with the same first mismatch at 14 and the identical wrong continuation [17133, 4221, 11, 290, 373]; the user-visible text "House ofEARTH" shows the page really fed
> 17133 "EAR" → 4221 "TH". The flip is deterministic in the v5 + keys-mouse-harness configuration. The margin data stand (position 14 margin 743, 17133 = winner + 1, i.e.
> an off-by-one in the transported id, not a logit flip). Two variables differ from the passing v4 run (bundle v4→v5, harness bench_native fill+keyboard → ordering
> keystrokes+mouse with per-capture getComputedStyle reads); `R6X/run_chain_v5d.sh` separates them (§10.X), then a 2-layer bisection of v5's three changes if the bundle
> is at fault. No swap until resolved.

- Run: v5 `bundles/demo-c32`, HEADED 1100×700, keystrokes + mouse click, machine in its post-reboot storm (load 24–32, swap 0). Prompt ids and `--prompt-count` right, winners
  1–13 exactly the reference, per-token 15–20 s (normal); **position 14 gave 17133 instead of 17132** (then diverged, as any autoregressive run does); only 25 tokens were
  captured because `ordering.mjs` had its default 600 s cap (a harness limit, not a stall — fixed in the re-run).
- Margins (`R6X/margins_ref.py` = R4P/margins.py's arithmetic on `reference_ids_shubham_was.json`; `R6X/margins_shubham_was.json`): position 14 **margin 743** score units
  (winner 17132, runner-up **19920**); by position: 105, 18, 19, 58, 71, 803, 366, 36, 555, 369, 482, 54, 360, **743**, 113, 20, 174, **7** (min, position 18), 71, 83, 28, 53,
  243, 719, 501, 148, 1212, 602, 1092, 75, 348, 14. So position 14 is NOT a near-tie, and the browser's 17133 is not the runner-up either — it is the **adjacent id of the
  correct winner**. A logit-side error would have produced 19920; an off-by-one in the winning id is an **id-transport error** (the head found the right row and the index
  was read back one unit off — a geometry/stamp read landing a frame early/late under the ≈30 load), which v5's changes cannot cause: they act on the prompt receipt, arming
  and display before epoch 5 only, and winners 1–13 were correct.
- History: no earlier full run of this project flipped an id — R5X combined8-c32 32/32; R6X typed "I" 32/32, typed "Once upon a time" 32/32 (×2, plus 2 probes not
  id-checked), headed "Once upon a time" 32/32, headed "Shubham was" (v4) 32/32, the 2-layer smokes 32/32 (×4) and the ordering probes 5/5 — all on a machine with load ≲ 8.
  This is the first flip, and it happened at load 25–31. **Protocol note:** correctness/acceptance runs need `load1 < 6` at start (pass counts were still the usual ones; only
  the ids flipped) — `R6X/run_chain_v5c.sh` now polls for it and re-runs the guard with the full 2,400 s cap; the 13/32 run is kept in `R6X/runs/ordering-demo-c32-keys-mouse-load30`.
- Not swapping again: the wiring is not at fault (the ordering frames above show the fixed receipt gating exactly as designed; demo-8 Hello 8/8 + verify rc 0 on v5).

## 10. v5 — typed prompt shown but dropdown prompt run (user reports #2/#3): ordering probe, fix, guards (auto-appended by R6X/run_chain_v5b.sh 2026-10-01 11:32:16)

### 10.O ordering probe smoke-demo-2L (R6X/runs/ordering-smoke-demo-2L-zoom150/: frames.json, shot-*.png)
```
{"t":7245,"event":"launched","version":"154.0.8037.58","url":"http://127.0.0.1:48261/work/2026-09-19/R6X/smoke-demo-2L/index.html","typed":"Shubham was","zoomSteps":3}
{"t":15722,"event":"typed","armedRoot":{"--prompt-armed":"0","--prompt-live":""},"high3":{"--prompt-count":"0","--prompt-token-id-0":"-1","--prompt-token-id-1":"-1","--prompt-token-id-2":"-1","--prompt-token-id-3":"-1","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"0"},"runChecked":false,"runLatched":false,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.757116","--epoch":"1"},"select":{"--token":"15496","--prompt-count":"0"},"epoch":"1","output":{"--prompt-count":"0","--display-prompt":"-1","--draft-echo":"\"Shubham was\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"Shubham was\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTokens":{"cont
{"t":15999,"event":"run-clicked","sinceStart":15820}
{"t":34980,"event":"after-click","armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"0","--embed-stamp":"0.739617","--epoch":"4"},"select":{"--token":"373","--prompt-count":"4"},"epoch":"4","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTokens":{"content":"\"Typed 
{"t":36948,"event":"token-captured","k":1,"sinceRun":1030,"armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.731167","--epoch":"4"},"select":{"--token":"373","--prompt-count":"4"},"epoch":"4","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTok
{"t":39440,"event":"token-captured","k":2,"sinceRun":3919,"armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.731167","--epoch":"4"},"select":{"--token":"373","--prompt-count":"4"},"epoch":"4","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTok
{"t":41013,"event":"token-captured","k":3,"sinceRun":5203,"armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.722909","--epoch":"5"},"select":{"--token":"407","--prompt-count":"4"},"epoch":"5","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTo
{"t":44433,"event":"token-captured","k":4,"sinceRun":8912,"armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.722909","--epoch":"5"},"select":{"--token":"407","--prompt-count":"4"},"epoch":"5","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTo
{"t":46079,"event":"token-captured","k":5,"sinceRun":10245,"armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.714834","--epoch":"6"},"select":{"--token":"6646","--prompt-count":"4"},"epoch":"6","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"6646"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"
{"t":47019,"event":"winners","feedback":["11","4623","647","407","6646"],"display":["-1","-1","-1","407","6646"],"armedRoot":{"--prompt-armed":"1","--prompt-live":""},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.714834","--epoch":"6"},"select":{"--token":"6646","--prompt-count":"4"},"epoch":"6","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"6646"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp
-- frames (f, ms, armed, live, count, id0, latched, ready, stamp, token, epoch)
{"t":34824,"event":"frame","f":0,"ms":8,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":1,"ms":17,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":2,"ms":25,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":3,"ms":33,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":4,"ms":41,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":5,"ms":50,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":6,"ms":77,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":7,"ms":80,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":8,"ms":83,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":9,"ms":91,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":10,"ms":100,"armed":"0","live":"","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"1","stamp":"0.757116","token":"15496","epoch":"1","selCount":"0"}
{"t":34824,"event":"frame","f":11,"ms":200,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":false,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":12,"ms":226,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":false,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":13,"ms":233,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":14,"ms":2897,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":15,"ms":3574,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":16,"ms":5700,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":17,"ms":5953,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":18,"ms":6298,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":19,"ms":6627,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":20,"ms":6868,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":21,"ms":9353,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":22,"ms":9419,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":23,"ms":9474,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":24,"ms":9557,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":34824,"event":"frame","f":25,"ms":9617,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"0","stamp":"0.757116","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":26,"ms":9925,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":27,"ms":10265,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":28,"ms":10727,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":29,"ms":11092,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":30,"ms":11413,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":31,"ms":11710,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":32,"ms":14127,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":33,"ms":14188,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":34,"ms":14267,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":34824,"event":"frame","f":35,"ms":14326,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"0","stamp":"0.748265","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":36,"ms":14624,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":37,"ms":14984,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":38,"ms":15461,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":39,"ms":15843,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":40,"ms":16168,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":41,"ms":16461,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":42,"ms":18900,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":43,"ms":18962,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":34825,"event":"frame","f":44,"ms":19046,"armed":"1","live":"","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
```
### 10.O ordering probe smoke-demo-2L-v5 (R6X/runs/ordering-smoke-demo-2L-v5-zoom150/: frames.json, shot-*.png)
```
{"t":565,"event":"launched","version":"154.0.8037.58","url":"http://127.0.0.1:48283/work/2026-09-19/R6X/smoke-demo-2L-v5/index.html","typed":"Shubham was","zoomSteps":3}
{"t":8795,"event":"typed","armedRoot":{"--prompt-armed":"0","--prompt-live":"0"},"high3":{"--prompt-count":"0","--prompt-token-id-0":"-1","--prompt-token-id-1":"-1","--prompt-token-id-2":"-1","--prompt-token-id-3":"-1","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"0"},"runChecked":false,"runLatched":false,"fontsLoaded":true,"receipt":{"--embed-ready":"0","--embed-stamp":"0.76618","--epoch":"1"},"select":{"--token":"15496","--prompt-count":"0"},"epoch":"1","output":{"--prompt-count":"0","--display-prompt":"-1","--draft-echo":"\"Shubham was\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"Shubham was\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTokens":{"conte
{"t":9056,"event":"run-clicked","sinceStart":8886}
{"t":27227,"event":"after-click","armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.731167","--epoch":"4"},"select":{"--token":"373","--prompt-count":"4"},"epoch":"4","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTokens":{"content":"\"Typed
{"t":29011,"event":"token-captured","k":1,"sinceRun":1136,"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.731167","--epoch":"4"},"select":{"--token":"373","--prompt-count":"4"},"epoch":"4","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTo
{"t":31415,"event":"token-captured","k":2,"sinceRun":3730,"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.731167","--epoch":"4"},"select":{"--token":"373","--prompt-count":"4"},"epoch":"4","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"-1","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkTo
{"t":32820,"event":"token-captured","k":3,"sinceRun":4861,"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.722909","--epoch":"5"},"select":{"--token":"407","--prompt-count":"4"},"epoch":"5","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkT
{"t":36006,"event":"token-captured","k":4,"sinceRun":8325,"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.722909","--epoch":"5"},"select":{"--token":"407","--prompt-count":"4"},"epoch":"5","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"-1"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"tkT
{"t":37471,"event":"token-captured","k":5,"sinceRun":9515,"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.714834","--epoch":"6"},"select":{"--token":"6646","--prompt-count":"4"},"epoch":"6","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"6646"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tkp2, gpt2-vocabulary) counter(tkp3, gpt2-vocabulary)"},"
{"t":38323,"event":"winners","feedback":["11","4623","647","407","6646"],"display":["-1","-1","-1","407","6646"],"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.714834","--epoch":"6"},"select":{"--token":"6646","--prompt-count":"4"},"epoch":"6","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"407","--display-token-5":"6646"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) counter(tk
-- frames (f, ms, armed, live, count, id0, latched, ready, stamp, token, epoch)
{"t":27064,"event":"frame","f":0,"ms":9,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27064,"event":"frame","f":1,"ms":17,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":2,"ms":26,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":3,"ms":34,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":4,"ms":42,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":5,"ms":73,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":6,"ms":76,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":7,"ms":84,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":8,"ms":92,"armed":"0","live":"0","count":"0","id0":"-1","id3":"-1","latched":false,"ready":"0","stamp":"0.76618","token":"15496","epoch":"1","selCount":"0"}
{"t":27065,"event":"frame","f":9,"ms":190,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":false,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":10,"ms":215,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":false,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":11,"ms":218,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":false,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":12,"ms":226,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":13,"ms":2717,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":14,"ms":3295,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":15,"ms":5228,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":16,"ms":5462,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":17,"ms":5795,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":18,"ms":6096,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":19,"ms":6325,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":20,"ms":8716,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":21,"ms":8772,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":22,"ms":8821,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":23,"ms":8894,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.757116","token":"2484","epoch":"1","selCount":"4"}
{"t":27065,"event":"frame","f":24,"ms":8946,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"0","stamp":"0.757116","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":25,"ms":9231,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":26,"ms":9554,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":27,"ms":9989,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":28,"ms":10334,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":29,"ms":10634,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":30,"ms":10912,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":31,"ms":13235,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":32,"ms":13288,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":33,"ms":13364,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.748265","token":"549","epoch":"2","selCount":"4"}
{"t":27065,"event":"frame","f":34,"ms":13420,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"0","stamp":"0.748265","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":35,"ms":13719,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":36,"ms":14066,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":37,"ms":14529,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":38,"ms":14896,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":39,"ms":15204,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":40,"ms":15490,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":41,"ms":17895,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":42,"ms":17955,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":43,"ms":18036,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"1","stamp":"0.739617","token":"2763","epoch":"3","selCount":"4"}
{"t":27065,"event":"frame","f":44,"ms":18106,"armed":"1","live":"1","count":"4","id0":"2484","id3":"373","latched":true,"ready":"0","stamp":"0.739617","token":"373","epoch":"4","selCount":"4"}
```
### 10.B builds (R6X/logs/identity-*-v5.log)
```
index.html: DIFFER (7130245 vs 7130218 B)
rules: new 67175 vs ref 67176; only in new: 9; only in ref: 10
   only in NEW: ('', '@property --prompt-live', 'syntax:"<integer>";inherits:true;initial-value:0')
   only in NEW: ('', '.head-isolation', '--bridge-p-000:initial;--bridge-p-001:initial;--bridge-p-002:initial;--bridge-p-003:initial;--bridge-p-004:initial;--bridge-p-005:initial;--bridge-p-006:initial;--bridge-p-007:initial;--bridge-p-008:initial;--bridge-p-009:initial;--bridge-p-010:initial;--brid
   only in NEW: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit;--prompt-armed:inherit')
   only in NEW: ('', '.visible-output', '--dp-live:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--dp-armed:if(style(--prompt-has-0:1):-1;else:var(--frozen-prompt));--display-prompt:if(style(--prompt-armed:1):var(--dp-armed);else:var(--dp-live));--draft-echo:if(style(--prompt-armed:1):"";
   only in NEW: ('', '.tk-root', 'display:contents;--prompt-armed:inherit;--prompt-live:if(style(--prompt-armed:1):1;else:0)')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked),body:has(> :where(.native-signals) > #run-latched.done)', '--prompt-armed:1')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked) .tk-editor,body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
   only in NEW: ('', '.controls>label:nth-of-type(2)', 'pointer-events:none;opacity:.6')
   only in NEW: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done) .controls>label:nth-of-type(2)', 'pointer-events:auto;opacity:1')
   only in REF: ('', '.head-isolation', '--bridge-p-000:initial;--bridge-p-001:initial;--bridge-p-002:initial;--bridge-p-003:initial;--bridge-p-004:initial;--bridge-p-005:initial;--bridge-p-006:initial;--bridge-p-007:initial;--bridge-p-008:initial;--bridge-p-009:initial;--bridge-p-010:initial;--brid
   only in REF: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit')
   only in REF: ('', '.visible-output', '--display-prompt:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--draft-echo:if(style(--prompt-count:0):var(--draft-prompt);else:"")')
   only in REF: ('', '.tk-root', 'display:contents;--prompt-armed:inherit')
   only in REF: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked)', '--prompt-armed:1')
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-0', 'transition-property:--prompt-token-id-0,--prompt-has-0;transition-duration:1ms;transition-delay:86400s;transition-timing-function:ste
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-1', 'transition-property:--prompt-token-id-1,--prompt-has-1;transition-duration:1ms;transition-delay:86400s;transition-timing-function:ste
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-2', 'transition-property:--prompt-token-id-2,--prompt-has-2;transition-duration:1ms;transition-delay:86400s;transition-timing-function:ste
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-3', 'transition-property:--prompt-token-id-3,--prompt-has-3,--prompt-count;transition-duration:1ms;transition-delay:86400s;transition-timi
   only in REF: ('', 'body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
order of the common rules: IDENTICAL
RESULT: PASS (common rules identical in multiset and order; differences listed above)
index.html: new has 1 new-style / 0 old-style receipt marker(s); ref 0 / 1
index.html: IDENTICAL after normalising the receipt marker
rules: new 67175 vs ref 67176; only in new 8; only in ref 9
   only in NEW: ('', '@property --prompt-live', 'syntax:"<integer>";inherits:true;initial-value:0')
   only in NEW: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit;--prompt-armed:inherit')
   only in NEW: ('', '.visible-output', '--dp-live:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--dp-armed:if(style(--prompt-has-0:1):-1;else:var(--frozen-prompt));--display-prompt:if(style(--prompt-armed:1):var(--dp-armed);else:var(--dp-live))
   only in NEW: ('', '.tk-root', 'display:contents;--prompt-armed:inherit;--prompt-live:if(style(--prompt-armed:1):1;else:0)')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked),body:has(> :where(.native-signals) > #run-latched.done)', '--prompt-armed:1')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked) .tk-editor,body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
   only in NEW: ('', '.controls>label:nth-of-type(2)', 'pointer-events:none;opacity:.6')
   only in NEW: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done) .controls>label:nth-of-type(2)', 'pointer-events:auto;opacity:1')
   only in REF: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit')
   only in REF: ('', '.visible-output', '--display-prompt:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--draft-echo:if(style(--prompt-count:0):var(--draft-prompt);else:"")')
   only in REF: ('', '.tk-root', 'display:contents;--prompt-armed:inherit')
   only in REF: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked)', '--prompt-armed:1')
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-0', 'transition-property:--prompt-token-id-0,--prompt-has-0;transition-duration:1ms;transition
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-1', 'transition-property:--prompt-token-id-1,--prompt-has-1;transition-duration:1ms;transition
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-2', 'transition-property:--prompt-token-id-2,--prompt-has-2;transition-duration:1ms;transition
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-3', 'transition-property:--prompt-token-id-3,--prompt-has-3,--prompt-count;transition-duration
   only in REF: ('', 'body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
order of the common rules: IDENTICAL
model core rules (outside the allowed layer, wall normalised): 66470 vs 66470 — IDENTICAL
RESULT: PASS
### 11:03:00 swapped demo-c32 (new build live; previous kept as bundles/demo-c32.prev)
index.html: DIFFER (6464515 vs 6464488 B)
rules: new 62485 vs ref 62486; only in new: 9; only in ref: 10
   only in NEW: ('', '@property --prompt-live', 'syntax:"<integer>";inherits:true;initial-value:0')
   only in NEW: ('', '.head-isolation', '--bridge-p-000:initial;--bridge-p-001:initial;--bridge-p-002:initial;--bridge-p-003:initial;--bridge-p-004:initial;--bridge-p-005:initial;--bridge-p-006:initial;--bridge-p-007:initial;--bridge-p-008:initial;--bridge-p-009:initial;--bridge-p-010:initial;--brid
   only in NEW: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit;--prompt-armed:inherit')
   only in NEW: ('', '.visible-output', '--dp-live:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--dp-armed:if(style(--prompt-has-0:1):-1;else:var(--frozen-prompt));--display-prompt:if(style(--prompt-armed:1):var(--dp-armed);else:var(--dp-live));--draft-echo:if(style(--prompt-armed:1):"";
   only in NEW: ('', '.tk-root', 'display:contents;--prompt-armed:inherit;--prompt-live:if(style(--prompt-armed:1):1;else:0)')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked),body:has(> :where(.native-signals) > #run-latched.done)', '--prompt-armed:1')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked) .tk-editor,body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
   only in NEW: ('', '.controls>label:nth-of-type(2)', 'pointer-events:none;opacity:.6')
   only in NEW: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done) .controls>label:nth-of-type(2)', 'pointer-events:auto;opacity:1')
   only in REF: ('', '.head-isolation', '--bridge-p-000:initial;--bridge-p-001:initial;--bridge-p-002:initial;--bridge-p-003:initial;--bridge-p-004:initial;--bridge-p-005:initial;--bridge-p-006:initial;--bridge-p-007:initial;--bridge-p-008:initial;--bridge-p-009:initial;--bridge-p-010:initial;--brid
   only in REF: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit')
   only in REF: ('', '.visible-output', '--display-prompt:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--draft-echo:if(style(--prompt-count:0):var(--draft-prompt);else:"")')
   only in REF: ('', '.tk-root', 'display:contents;--prompt-armed:inherit')
   only in REF: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked)', '--prompt-armed:1')
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-0', 'transition-property:--prompt-token-id-0,--prompt-has-0;transition-duration:1ms;transition-delay:86400s;transition-timing-function:ste
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-1', 'transition-property:--prompt-token-id-1,--prompt-has-1;transition-duration:1ms;transition-delay:86400s;transition-timing-function:ste
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-2', 'transition-property:--prompt-token-id-2,--prompt-has-2;transition-duration:1ms;transition-delay:86400s;transition-timing-function:ste
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-3', 'transition-property:--prompt-token-id-3,--prompt-has-3,--prompt-count;transition-duration:1ms;transition-delay:86400s;transition-timi
   only in REF: ('', 'body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
order of the common rules: IDENTICAL
RESULT: PASS (common rules identical in multiset and order; differences listed above)
index.html: new has 1 new-style / 0 old-style receipt marker(s); ref 0 / 1
index.html: IDENTICAL after normalising the receipt marker
rules: new 62485 vs ref 62486; only in new 8; only in ref 9
   only in NEW: ('', '@property --prompt-live', 'syntax:"<integer>";inherits:true;initial-value:0')
   only in NEW: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit;--prompt-armed:inherit')
   only in NEW: ('', '.visible-output', '--dp-live:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--dp-armed:if(style(--prompt-has-0:1):-1;else:var(--frozen-prompt));--display-prompt:if(style(--prompt-armed:1):var(--dp-armed);else:var(--dp-live))
   only in NEW: ('', '.tk-root', 'display:contents;--prompt-armed:inherit;--prompt-live:if(style(--prompt-armed:1):1;else:0)')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked),body:has(> :where(.native-signals) > #run-latched.done)', '--prompt-armed:1')
   only in NEW: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked) .tk-editor,body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
   only in NEW: ('', '.controls>label:nth-of-type(2)', 'pointer-events:none;opacity:.6')
   only in NEW: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done) .controls>label:nth-of-type(2)', 'pointer-events:auto;opacity:1')
   only in REF: ('', '.feedback-reader,.visible-output', '--draft-prompt:inherit;--pt-present-0:inherit')
   only in REF: ('', '.visible-output', '--display-prompt:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));--draft-echo:if(style(--prompt-count:0):var(--draft-prompt);else:"")')
   only in REF: ('', '.tk-root', 'display:contents;--prompt-armed:inherit')
   only in REF: ('', 'body:has(> :where(.controls) > :where(label) > #run:checked)', '--prompt-armed:1')
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-0', 'transition-property:--prompt-token-id-0,--prompt-has-0;transition-duration:1ms;transition
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-1', 'transition-property:--prompt-token-id-1,--prompt-has-1;transition-duration:1ms;transition
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-2', 'transition-property:--prompt-token-id-2,--prompt-has-2;transition-duration:1ms;transition
   only in REF: ('', 'body:has(> :where(.font-status) > :where(.native-signals) > #fonts-loaded.done):has(> :where(.native-signals) > #run-latched.done) .tk-high-3', 'transition-property:--prompt-token-id-3,--prompt-has-3,--prompt-count;transition-duration
   only in REF: ('', 'body:has(> :where(.native-signals) > #run-latched.done) .tk-editor', '-webkit-user-modify:read-only;pointer-events:none;opacity:.6')
order of the common rules: IDENTICAL
model core rules (outside the allowed layer, wall normalised): 61980 vs 61980 — IDENTICAL
RESULT: PASS
### 11:03:22 swapped demo-8 (new build live; previous kept as bundles/demo-8.prev)
```
### 10.G guards
```
demo-8: demo-8 v5 READY 2026-10-01 11:05:54: typed-prompt arming fix (token-fresh embedding receipt, sticky arming, no latch, editor locked from the click, Run after Ready, echo from model-facing values; model core rules identical — R6X/logs/identity-demo-8-v5.log); dropdown Hello ids 8/8, verify rc=0, run R6X/run-demo-8
headed Shubham was: ids 13/32 vs reference_ids_shubham_was.json; first mismatch 14; model count 4 armed {'--prompt-armed': '1', '--prompt-live': '1'}
{"t":628238,"event":"winners","feedback":["13","259","338","257","2888","286","262","471","13","50","13","2097","286","17133","4221","11","290","373","257","2888","286","262","471","13","50","-1","-1","-1","-1","-1","-1","-1"],"display":["-1","-1","-1","257","2888","286","262","471","13","50","13","2097","286","17133","4221","11","290","373","257","2888","286","262","471","13","50","-1","-1","-1","-1","-1","-1","-1"],"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.584308","--epoch":"26"},"select":{"--token":"50","--prompt-count":"4"},"epoch":"26","output":{"--prompt-count":"4","--display-prompt":"-1","--draft-echo":"\"\"","--display-token-1":"-1","--display-token-2":"-1","--display-token-3":"-1","--display-token-4":"257","--display-token-5":"2888"},"before":{"content":"counter(prompt, gpt2-vocabulary) \"\" counter(tkp0, gpt2-vocabulary) counter(tkp1, gpt2-vocabulary) co
Once upon a time: ids 32/32
```

### 10.R headed 'Shubham was' re-guard on a quiet machine (auto-appended by R6X/run_chain_v5c.sh 2026-10-01 13:01:52)
```
ids 13/32 (captured 32 in 836 s) vs reference_ids_shubham_was.json; first mismatch 14
- 2026-10-01 12:47:25 [R6X chrome/headed-shubham-v5-quiet] START (waited 0s) power=' -InternalBattery-0 (id=23789667) 80%; AC attached; not charging prese' load={ 4.82 9.16 13.75 } AC=1 disk=7GB swap_used=712MB swap='total = 2048.00M  used = 712.75M  free = 1335.25M  (encrypted)' free_pages=19763.: 
- 2026-10-01 13:01:52 [R6X chrome/headed-shubham-v5-quiet] END rc=0 power=' -InternalBattery-0 (id=23789667) 80%; AC attached; not charging prese' load={ 7.83 7.80 9.98 } AC=1 disk=13GB swap_used=1064MB swap='total = 2048.00M  used = 1064.31M  free = 983.69M  (encrypted)'
{"t":858176,"event":"winners","feedback":["13","259","338","257","2888","286","262","471","13","50","13","2097","286","17133","4221","11","290","373","257","2888","286","262","471","13","50","13","3845","13","679","373","257","2888"],"display":["-1","-1","-1","257","2888","286","262","471","13","50","13","2097","286","17133","4221","11","290","373","257","2888","286","262","471","13","50","13","3845","13","679","373","257","2888"],"armedRoot":{"--prompt-armed":"1","--prompt-live":"1"},"high3":{"--prompt-count":"4","--prompt-token-id-0":"2484","--prompt-token-id-1":"549","--prompt-token-id-2":"2763","--prompt-token-id-3":"373","--pt-present-0":"1","--pt-id-0":"2484","--prompt-armed":"1"},"runChecked":true,"runLatched":true,"fontsLoaded":true,"receipt":{"--embed-ready":"1","--embed-stamp":"0.553963","--epoch":"32"},"select":{"--token":"257","--prompt-count":"4"},"epoch":"32","output":{"--p
```

## 11. v6 — the real cause of the flipped ids (found by R7H, 2026-10-01): a scrollbar inside the id-readback scrollport in HEADED Chrome

**Mechanism (R7H).** The fed-back ids are read through `.feedback-scroller{position:fixed;width:524288px;height:1px;overflow:scroll}` holding
`.feedback-metric-e{width:calc(65536px + (var(--saved-token-e) + 1)*8px);view-timeline:--feedback-te inline}`; the decode hardcodes the scrollport as 524288 px (8 px per id). In
headed Chrome on this Mac (System Settings → "Show scroll bars: Always"; `defaults read -g AppleShowScrollBars` = Always) a classic scrollbar takes 15 px of that scrollport, so the
view-timeline progress is p = 524273/(524273 + W) instead of 524288/(524288 + W) and the decoded id carries a bias of (65536 + 8(id+1))·15/524288/8 ≈ 2.86e-5·(65536 + 8(id+1))/8 —
**+1 for every id ≥ 9283, 0 below**. It fits every run on record: Hello's max id 7926 (bias 0.46, passes barely), "Once upon a time" max 8737 (0.49, barely), "Shubham was" ids 1–13
all < 2888 then 17132 → **17133** (both headed runs, positions 1–13 right, identical wrong continuation), the 2-layer smokes (max id 6646) never flip, and every passing 32/32 run of
this project was **headless** (overlay/hidden scrollbars — no bias). The user runs headed Chrome, so this is the user's bug; and it is why the §10.M load theory (withdrawn) and the
planned v5 bisection could not have found it: the v5 wiring is sound (the ordering frames show the fixed receipt gating as designed) and the smokes cannot reproduce a threshold at 9283.

**Fix (v6, `R6X/apply_conflicts.py` edit 7, flag `R6X_SCROLLBAR_FIX` default on).** `.feedback-scroller{scrollbar-width:none}` (Chrome ≥ 121; the demo needs ≥ 139 anyway) appended with
the R6X display rules — the only `overflow:scroll` element in the sheet (grep: one rule; the 2,412 other `524288px` occurrences are the proj stamp scrollers' widths and their
coarse `round(…/1024)` decodes). Model core rules identical (`R6X/check_v5_identity.py`, allow-list + this rule). R7H separately adds a calibration metric (a constant 50256 that must
decode exactly, gating `#token-e-ready`) so a scrollport mismatch can never silently corrupt ids again; that merges after v6.

**Protocol consequences.** (1) Our harnesses hid the bars: `bench_native.mjs` passed `--hide-scrollbars` unconditionally (also with `B0_HEADED=1`, which is why v4's headed
"Shubham was" through it passed while `ordering.mjs`, which never had the flag, flipped), and headless Chrome hides them by default — so no harness run could see the effect.
`bench_native.mjs` now has `B0_SHOW_SCROLLBARS=1` (omits the flag; headless Chrome then draws classic 15 px bars too, a valid cheap arm) and **every acceptance run must include a
scrollbars-shown arm from now on** (headed with the macOS default setting, or headless with `B0_SHOW_SCROLLBARS=1`) for any bundle whose readbacks hardcode a scrollport. (2) The "load" protocol note of §10.M is withdrawn; pass counts and ids were never load-sensitive in our data. (3) Positive
control for v6: R7H predicts the old build flips typed "I" at position 15 (reference 16918 ≥ 9283) in headed Chrome — run first, then v6 must give 32/32 headed for "I" and "Shubham was",
and demo-8 Hello 8/8. Results follow in §11.G.

### 11.G guards (auto-appended by R6X/run_chain_v6.sh 2026-10-01 14:09:17; all typed runs HEADED 1100x700, scrollbars shown, standard harness)
```
== run-demo-c32.prev/headed-I-prev
# headed-I-prev — 32/32 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.1 s, Run at 6.1 s after nav
ids 16/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4P/reference_ids_32_40.json; prompt token default 15496); ids=[13, 198, 198, 464, 717, 1517, 314, 750, 373, 284, 467, 284, 262, 1957, 16918, 5933, 290, 1265, 606, 611, 484, 550, 597, 5479, 329, 262, 2292, 13, 314, 1965, 606, 611]
first mismatching position: 16; mismatches at [16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
== run-demo-c32/headed-I-v6
# headed-I-v6 — 32/32 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.0 s, Run at 6.0 s after nav
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4P/reference_ids_32_40.json; prompt token default 15496); ids=[13, 198, 198, 464, 717, 1517, 314, 750, 373, 284, 467, 284, 262, 1957, 16918, 3650, 290, 2822, 257, 6131, 286, 12912, 32132, 13, 314, 373, 523, 6568, 284, 1949, 340, 13]
first mismatching position: None; mismatches at []
== run-demo-c32/headed-shubham-v6
# headed-shubham-v6 — 32/32 tokens, stopReason=token-limit, trigger=keyboard, heapFlag=True, load 2.1 s, Run at 6.1 s after nav
ids 32/32 vs reference (/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/reference_ids_shubham_was.json; prompt token default 15496); ids=[13, 259, 338, 257, 2888, 286, 262, 471, 13, 50, 13, 2097, 286, 17132, 422, 9162, 284, 7358, 13, 679, 373, 257, 2888, 286, 262, 471, 13, 50, 13, 3845, 422, 9162]
first mismatching position: None; mismatches at []
== demo-8 v6: demo-8 v6 READY 2026-10-01 14:09:17: + .feedback-scroller{scrollbar-width:none} (R7H's headed-Chrome id-readback fix, R6X.md §11); dropdown Hello ids 8/8, verify rc=0, run R6X/run-demo-8
```

READY demo-c32: demo-c32 v6 2026-10-01 14:09:17: + .feedback-scroller{scrollbar-width:none} (R7H: headed Chrome's classic scrollbar biased read-back ids >= 9283 by +1; R6X.md §11); HEADED scrollbars-shown guards: typed 'I' ids 32/32, typed 'Shubham was' ids 32/32 (positive control on the old build headed typed 'I': ids 16/32); demo-8 Hello: see bundles/demo-8/READY

### 11.S Reading of §11.G (R6X, 14:15)

- **Positive control confirmed the mechanism**: the old build (`demo-c32.prev` = v5 wiring, no scrollbar fix), HEADED with scrollbars shown, typed "I": **16/32**, winners 1–15
  right (incl. 16918 at position 15 — the first id ≥ 9283), the first wrong winner at **16** (5933 instead of 3650). The bias hits the *read-back* of 16918 (fed in as 16919), so
  `summarize32`, which compares the captured winners `--saved-token-e`, shows the damage one position later than R7H's "position 15"; the ordering harness read the biased
  `--feedback-14` directly, which is why the Shubham runs reported the mismatch *at* 14 (17133). Same mechanism, two bookkeepings — and the display, which prints `--feedback-*`,
  shows the biased token ("EAR"), exactly the user's screenshot.
- **v6 fixes it under the same conditions**: headed, scrollbars shown — typed "I" **32/32** (774 s), typed "Shubham was" **32/32** (802 s); demo-8 Hello **8/8** + verify rc 0.
- Methodology lesson recorded in §11: every one of this project's earlier "32/32" runs was blind to the condition (`--hide-scrollbars` in `bench_native.mjs`, or headless defaults);
  acceptance now needs a scrollbars-shown arm (`B0_SHOW_SCROLLBARS=1`, headed or headless). The §10.M load theory and the v5 bisection are withdrawn (data kept); the v5 arming
  fix stays (it addresses a real race shown in §10's frames, independent of the scrollbar bias).
