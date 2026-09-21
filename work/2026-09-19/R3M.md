# R3M — round-3 merge: `bundles/combined4` = combined3 (R2H) + R3R fold-hop (`R3R_FOLD_HOP`) + R3F `:has()` scoping (`R2G_SCOPED_HAS`) + R3H #1 block-flow group max (`R3H_BLOCKFLOW_MAX`)

Agent R3M, 2026-09-20. Tools copy `work/2026-09-19/R3M/tools` (+ `experiments`, `data`, `assets -> ../F4/assets`, `global-projection-assets -> ../F2/…`
symlinks, identical targets to R2H's). Bundle `work/2026-09-19/bundles/combined4` (BUILD.md = recipe + flag table + merge notes + offline results + `diff -ruN
-x __pycache__ R2H/tools R3M/tools`). Scratch (reference builds, dry-run tree, checkers, logs): `work/2026-09-19/R3M/`. Log: `R3M.log.md`. Nothing under the
repo's `tools/`, `experiments/` or other agents' directories was touched; no commits.

## 0. Headline

- Plan change (coordinator, 22:00): R3R (`bundles/R3R` READY, 8/8, RecalcStyleCount 982) removed the loop-bank hop that R3L's packed latches targeted, so
  combined4 = R2H base + R3R + R3F + R3H; **R3L is excluded** — its diff fails 5/9 hunks on top of R3R (both rewrite the loop-bank region of
  `browser_gpt2_reused_core.py` / `browser_gpt2_reused_adapter.py`) and its target (`--saved-*` latch transitions) no longer exists. Before the plan change
  I had merged and offline-verified R3F + R3L + R3H in preview form (`R3M/dryrun`, `R3M/scratch/preview*`; log 20:14–20:18) — disjoint files, all checkers
  passing; kept for the record only.
- Merge: 0 rejects / 0 fuzz / 0 offsets (R3R and R3F touch disjoint files); the R3H hook's import line is adjacent to R3F's — applied as exact-string edits.
- **All new flags OFF reproduces `bundles/combined3` byte-for-byte** (index.html; runtime.css modulo the relative-URL depth of the scratch dir); with only
  R3R's flag on the tools reproduce `bundles/R3R`, with only R3F's `bundles/R3F`. R3R's, R3F's and my R3H checkers pass; witnesses 283/283 identical to
  combined3/R3R/R3F; NumPy ids = expected; 285 static files / 285,494,400 B / no JavaScript.
- Chrome: PENDING-HEADLINE-CHROME

## 1. Merge

- Base: `cp -R R2H/tools R3M/tools` (cmp-identical to R2H's). Applied `patch -p2 -F3 -N < R3F/tools-vs-R2H.diff` (browser_gpt2_runtime.py + new
  r2g_has_scope.py) and `patch -p2 -F3 -N < R3L/tools-vs-R2H.diff` (browser_gpt2_reused_adapter.py, browser_gpt2_reused_core.py,
  probe_native_reused_loop.py + new r3l_packed_loop.py): **disjoint file sets, 0 rejects / 0 fuzz / 0 offsets.** The "handshake/loop region" overlap the brief
  warned about is semantic, not textual: R3F rewrites the `:has()` handshake *arguments* in the finished sheet (a post-pass on the whole CSS + page), R3L
  changes the loop-bank latch *declarations* inside the core emitter; the loop rules R3F would rewrite (`R2G`'s 272 `.core-controller:where(:has(#loop-…))`)
  do not exist with `R2F_LEAN_HANDSHAKE=1` (`rewritten.loop: 0` in the manifest), so neither touches the other's output.
- R3H hook (mine, `R3M/apply_r3h_hook.py`, 3 exact-string hunks in browser_gpt2_runtime.py: import; `head_css = r3h.blockflow_max(head_css)` right after F4's
  `pack_head_input`; manifest key `r3hBlockflowMax` after `**r2d.manifest()`). **The merge's only conflict:** my import line and R3F's `import r2g_has_scope as
  r2g` are adjacent lines after `import r2c_hoist as r2c` — the diff form of the hook rejected on the merged tree (1/3 hunks), so the hook is applied as
  exact-string edits with the import anchored after R3F's. The other two hunks are far from R3F's (:264 vs :562-585).
- Real merge 22:02 (after `bundles/R3F/READY` 21:16 and the plan change): both agents' `tools-vs-R2H.diff` are cmp-identical to the diffs in their BUILD.md
  (R3F's unchanged since my 20:14 dry-run). `patch -p1 -F3 -N < R3R/tools-vs-R2H.diff` (browser_gpt2_reused_adapter.py, browser_gpt2_reused_core.py,
  build_hybrid_twelve_block.py, + r3r_fold_hop.py), `patch -p2 -F3 -N < R3F/tools-vs-R2H.diff` (browser_gpt2_runtime.py, + r2g_has_scope.py), then
  `apply_r3h_hook.py`: 4 modified files + 3 new modules vs R2H/tools (`R3M/tools-vs-R2H.diff`, 708 lines, also in BUILD.md); new modules cmp-identical to owners.
- R3L, for the record: `patch --dry-run -p2 < R3L/tools-vs-R2H.diff` on the merged tree fails 2/2 hunks in browser_gpt2_reused_adapter.py and 3/3 in
  browser_gpt2_reused_core.py (probe_native_reused_loop.py would apply but is no longer on the emitted path). Excluded as instructed.

## 2. R3H item #1 — block-flow group maximum (`R3M/tools/r3h_blockflow_max.py`, flag `R3H_BLOCKFLOW_MAX`, default ON)

- Template: #176 `experiments/gpt2-mixed-hot2-blockflow-group-max-shard256` (`tools/build_mixed_hot2_blockflow_group_probe.py:30-31`):
  `.group-grid{display:block;grid-template-columns:none;height:0;overflow:visible}` `.group-grid>.candidate{grid-area:auto;justify-self:auto;height:0}`.
- Emitted here (appended to head.css after F4's packing, i.e. after the last `.head-fine-row:nth-child(256)` rule and before the control sheet, so it wins
  the cascade over the base `.head-group` / `.head-row` rules of equal specificity):
  `.head-group{display:block;grid-template-columns:none;grid-template-rows:none}.head-row{grid-area:auto;justify-self:auto;height:0}` (129 B).
  Kept from the base rules: `.head-group{position:fixed;…;width:max-content;height:calc(var(--head-input-epoch)*1px)}` (the epoch stamp read by
  `.head-score-g{height:anchor-size(--head-group-g height)}`), `.head-row{display:block;white-space:pre;overflow:clip;min-width:0;…}` and the two-pass
  `.head-row{width:calc-size(max-content,round(nearest,(size − base·1px)·120.777609693 + 211968px,4px))}`. `.head-fine` stays a grid (R3H §4 #1;
  `gpt2-mixed-hot2-all-blockflow` rejected all-block-flow). Not #176's `height:0;overflow:visible` on the group: our group's height *is* the epoch.
- Why exact by construction: the coarse score `S_g = anchor-size(--head-group-g width)` was the size of the single `max-content` grid track = max over the
  256 items' max-content contributions; each item's contribution is its `width:calc-size(max-content, f(size))`. A block container with `width:max-content`
  has intrinsic inline size = max over its in-flow block children's max-content contributions, and a block child with the same specified `width`
  contributes the same `f(size)` (margins 0). `min-width:0` (R2D's pin, needed for grid items) is the block default. Height does not enter intrinsic
  inline sizing; `mod(width,4px)` stays 0. #176 measured exactly this on the same 50,257-row/197-group topology (30/30 exact; −13 % layout, −30 % style).
- Guards: the module asserts the base group rule, the `.head-row` base-rule prefix and the `.head-fine` grid prefix each occur exactly once before appending
  (R2D's exact-string `overflow_clip` swap still matches once — the override does not contain that prefix). `R3H_BLOCKFLOW_MAX=0` reproduces the previous
  sheet byte-for-byte (verified: `R3M/scratch/r3h-off` vs combined3, and `preview-noR3H`).
- Offline checker `R3M/offline_check_r3h.py <on> <off>`: index.html identical; css == ref + the override at that exact position; rule counts and cascade order.

## 3. Offline verification

Reference builds from the same tools in `R3M/scratch/` (`compile-scratch.sh`, 8 s each): `c4` (all on; URL-normalised twin of the bundle), `c4-noR3R`,
`c4-noR3F`, `c4-noR3H`, `c4-alloff`, `c4-onlyR3R`, `c4-onlyR3F`. `runtime.css` of a scratch build differs from a `bundles/` build only by one extra `../`
in its 283 font URLs (one directory deeper), so css comparisons normalise the `url("../…")` prefix; `index.html` has no URLs and is compared byte-for-byte.

| check | reference | result |
|---|---|---|
| all new flags OFF (`c4-alloff`) | `bundles/combined3` | index.html byte-identical; runtime.css identical (URL-normalised); manifest differs only by `r3rFoldHop:false`, `r2gScopedHas:null`, `r3hBlockflowMax:false` |
| union: `c4-onlyR3R` / `c4-onlyR3F` | `bundles/R3R` / `bundles/R3F` | css (normalised) + index.html identical to each; manifest +2 keys each |
| `R3M/offline_check_r3r.py c4 c4-noR3R` (= R3R's checker, paths parametrised) | R3R off | `RESULT: PASS` — rule diff limited to R3R's categories, elements −3,092, 12 pk rules/layer, scroller 524288, marker base 131072 |
| `R3M/offline_check_r3f.py c4 c4-noR3F` (= R3F's) | R2G off | `PASS` — 21,280 rules both, +69/−69, 79 arguments rewritten (loop 0) |
| `R3M/offline_check_r3h.py combined4 c4-noR3H` (mine) | R3H off | `RESULT: ok` — css = ref + the 129-byte override at the exact position; base rules once each; cascade order |
| font witnesses | combined3, R3R, R3F | 283/283 identical to each (keys modulo tools dir) |
| NumPy reference ids (`R3M/reference_ids.py`, merged tools) | — | `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected |
| `launch_browser_gpt2.py --check` | — | 285 static files / 285,494,400 B / no JavaScript |

Sizes: runtime.css 38,974,477 chars (combined3 39,963,742 chars; 40,872,840 B), index.html 5,603,748 chars (combined3 6,658,236 B).

## 4. Chrome correctness run

## 4. Chrome correctness run

ONE passive run (NOT a timing run), `R3M/run_correctness.sh combined4` (R2D's watchdog harness + R3M lock fixes: owner marker, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 81%; AC attached; not charging present: true; load { 3.53 3.73 4.08 }. Results in `work/2026-09-19/R3M/run-combined4/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.017645388115284204, 'maximum': 0.1338847690698799}, 'text': "Hello, I'm sorry, but I'm".
- Whole-run counters (harness idle -> end): RecalcStyleCount 985, LayoutCount 629 (R3R alone: 982 / 625; R3F: 1,116 / 720; combined3: 1,107 / 710); Nodes 132170.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run; R3R's run: 21.4, 18.9, 17.1, 17.9, 19.7, 19.4, 17.3, 23.8): 22.0, 39.1, 56.3, 74.3, 98.5, 116.3, 141.0, 158.6 s.
- READY: created.


## 5. Residual risks / follow-ups

- **R3H exactness rests on CSS intrinsic-sizing semantics + #176's Chrome measurement, not on a bit-level offline witness**: the head has no NumPy
  path that models Blink's block-vs-grid max-content computation, so the Chrome run (8/8 ids, `finalHeadMatchesActualInput`) is the acceptance. If a
  future bundle ever shows a head mismatch with R3H on, `R3H_BLOCKFLOW_MAX=0` restores the grid head byte-for-byte. The expected win (R3H §4 #1:
  −0.30 ± 0.10 s untraced/token) is B0's to measure; the head frame's RecalcStyle/Layout counts do not change (same passes, cheaper ones).
- **Numerics are R3R's, not combined3's**: R3R's transport rounds at different points (`R3R.md` §1.5) — expect `finalResidualError` rmse ≈ 0.0176 / max
  ≈ 0.134 (combined3: 0.0201 / 0.187), i.e. the residual vectors are not bit-identical to combined3's, ids are. R3F and R3H are arithmetic-neutral.
- **R3L is superseded, not merged**: with R3R there are no `--saved-*` latches to pack; R3L.md's remaining finding (6-digit `var()` serialisation in the
  fixture) is a separate item. Re-adding R3L would need a rebase onto R3R's loop region and has no target.
- **Interaction R3F × R3R**: R3F rewrites body-anchored `:has()` arguments after the whole page is built; R3R's new controller/pass reader/`--held` rules
  are not body-anchored `:has()` rules (`rewritten.loop: 0`, same 79 arguments as on combined3), so the sheets compose without touching each other —
  verified by the union builds (only-R3R == `bundles/R3R`, only-R3F == `bundles/R3F`).
- **Lock protocol**: my `run_correctness.sh` now stamps `CHROME.lock/owner`, kills its toucher before a marker-checked `rmdir`, uses `touch -c`, and
  treats a lock FILE as held (coordinator 22:08 / R3L.md item 10). The R2H/R2D-derived releasers other agents still run have the unconditional `rmdir`.
  Incident during this task: my first (unpatched) run grabbed the lock at 22:08:16 the moment the fixer cleared the stale file; I aborted it 45 s in
  (before any token) to patch — its zsh survived the TERM trap and had to be SIGKILLed (§4 / log 22:10–22:12).
- Disk: `R3M/scratch/` holds 14 reference builds (~40 MB css + 5.6 MB html each, no fonts) — delete after B0 picks up combined4. `bundles/combined4` has
  no font copies (relative URLs into `experiments/`, like combined3).
