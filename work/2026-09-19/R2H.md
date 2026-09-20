# R2H — round-2 merge: `bundles/combined3` = F4 `combined` + R2C hoist + R2F lean handshake + R2D knobs

Agent R2H, 2026-09-19. Tools copy `work/2026-09-19/R2H/tools` (+ `experiments`, `data`, `global-projection-assets -> ../F2/…`, `assets -> ../F4/assets`
symlinks). Bundle `work/2026-09-19/bundles/combined3` (BUILD.md = recipe + flag table + merge notes + offline results + `diff -ru F4/tools R2H/tools`).
Reference siblings (no READY): `combined3-noR2C`, `combined3-noR2F`, `combined3-noR2D`, `combined3-alloff` (46 MB each, fonts by relative URL; delete when
B0/B1 no longer need them). Log: `R2H.log.md`. Nothing under repo `tools/` or `experiments/` was touched; no commits.

## 1. Merge

- `cp -R F4/tools R2H/tools`; `patch -p1 -F3 < R2C/tools-vs-F4.diff`; `patch -p3 -F3 < R2F/tools-vs-F4.diff`; `patch -p3 -F3 < R2D/tools-vs-F4.diff`;
  `r2c_hoist.py` / `r2d_knobs.py` copied (`r2f_lean_handshake.py` is inside R2F's `-N` diff). **0 rejects, 0 fuzz, 0 offsets — no conflicts.**
- Overlaps (files touched by two agents): `browser_gpt2_runtime.py` — R2C adds `import r2c_hoist` after `f5_scoping`, R2D adds `import r2d_knobs` after
  `f4_packing` (adjacent lines, both kept); R2C's wall hunk (:305) vs R2D's head-lock (:365), knobs (:555) and manifest (:585) hunks are disjoint.
  `browser_gpt2_reused_adapter.py` — R2C adds `import r2c_hoist` before, R2F adds `import r2f_lean_handshake` after `from browser_gpt2_reused_core import …`;
  R2F's manifest key `r2fLeanHandshake` (after `localLayerContainer`) and R2C's four `r2cHoist*` keys (after `f4NumericLists`) are 10 lines apart. Exactly as
  R2F §6 predicted ("adjacent but disjoint"). No hand edits were needed.
- Verification of the union: `diff -ru F4/tools R2H/tools` = 6 modified files + 3 new modules (BUILD.md); `diff R2C/tools R2H/tools` shows exactly R2F's
  adapter hunks and R2D's runtime hunks; the 4 files only R2C touched are `cmp`-identical to R2C's copy; all 3 new modules `cmp`-identical to their owners'.
- Strongest check: **the merged tools with all round-2 flags OFF (`combined3-alloff`) reproduce `bundles/combined`'s runtime.css and index.html
  byte-for-byte** (manifest differs only by the 9 new flag keys, all false).
- Pitfall recorded: my first `combined3-noR2D` / `-alloff` builds were invalid — zsh does not word-split an unquoted `$flags`, so `env "A=0 B=0 C=0" script`
  created ONE variable whose value (`"0 B=0 C=0"`) both `flag()` parsers treat as ON. Rebuilt with explicit exports; the env line printed by
  `compile-combined3.sh` now shows each flag separately.

## 2. Flags (all default ON except `R2D_POINTER_EVENTS`, which R2D shipped OFF)

`F4_PACKED_BANKS/HEAD`, `F4_NUMERIC_LISTS`; `R2C_HOIST_FVS` (+ `_STAGES/_QUERY/_EMBEDDING`); `R2F_LEAN_HANDSHAKE`; `R2D_HEAD_LOCK`, `R2D_OVERFLOW_CLIP`,
`R2D_CONTAIN_PAINT`, `R2D_POINTER_EVENTS=0`. Manifest: `r2cHoist*`, `r2fLeanHandshake`, `r2dHeadLock`, `r2dOverflowClip`, `r2dContainPaint` true, `r2dPointerEvents` false.

## 3. Offline verification (all pass)

| check | reference | result |
|---|---|---|
| `R2H/offline_check_r2c.py combined3 combined3-noR2C` (R2C's checker, reference parametrised) | same tools, `R2C_HOIST_FVS=0` | `RESULT: ok`: 61 lists / 65,282 entries byte-identical to the reference arithmetic; 6,146 `--fq-*` regs; wall clean; selector diff = 4 stage lists (12->13), `.fvs-query` (12->24), `.embedding-source` (1->2), `@property`s; index.html identical |
| `R2F/offline_check.py combined3 combined3-noR2F` | `R2F_LEAN_HANDSHAKE=0` | `PASS`: rules 22,841 vs 23,210 (+12/−381), elements 68,947 vs 69,522 (−575), fonts/witnesses identical — R2F's own numbers |
| `R2H/selector_diff.py combined3 combined3-noR2D` | `R2D_*=0` | 4 removed / 5 added = head unlock `headinput`->`b11-bridge`, 3× `overflow:clip;min-width:0`, 1× `contain:paint`; R2D's emitter asserts passed in the build |
| font witnesses | `bundles/combined` | 283/283 identical (keys modulo tools dir) |
| `launch_browser_gpt2.py --check` | — | 285 static files / 286,636,756 B / no JavaScript |
| NumPy reference ids (`R2H/reference_ids.py`, R2H tools) | — | `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected |
| `combined3-alloff` vs `bundles/combined` | — | runtime.css + index.html byte-identical |

Sizes: runtime.css 40,872,840 B (combined 41,666,858; R2C 40,927,799; R2F 41,611,806), index.html 6,658,236 B (combined 6,686,370).

## 4. Chrome correctness run

ONE passive run (NOT a timing run), `R2H/run_correctness.sh combined3` (R2D's watchdog harness: wall cap, Chrome-exit watchdog, 30 s lock toucher; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 81%; AC attached; not charging present: true; load { 5.32 5.10 4.75 }. Results in `work/2026-09-19/R2H/run-combined3/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.02005934198718561, 'maximum': 0.18731616094288484}, 'text': "Hello, I'm sorry, but I'm".
- Whole-run counters (harness idle -> end): RecalcStyleCount 1107, LayoutCount 710 (R2F alone: 1,109 / 712; combined: 1,420 / 888); Nodes 133716.
- Per-token capture times (5 s poll granularity, AC, load ≈5 — indicative only, not a timing run): 28.3, 52.2, 80.8, 106.4, 132.5, 159.6, 183.7, 215.2 s.
- READY: created.


## 5. Chromium mutex incident

`CHROME.lock` has been held since 10:35:40 by R2G (R2G.log.md: "acquired CHROME.lock for a PROVISIONAL BATTERY fixture run", runner pid 56148). At 13:38
no `Google Chrome --` process existed, pid 56148 was gone (R2G.log.md 12:14:35: "gave up waiting for AC power"), `R2G/fixture/results-battery/` held nothing
newer than 10:35:41 (`pa-demo.jsonl` 0 B) and the lock dir had not been touched for 3 h. Per the ground rule I did NOT remove it. `R2H/run_correctness.sh
combined3` is running (nohup) and polls the lock every 15 s; it now also touches the lock every 30 s while it holds it (R2D's script did not).
`R2H/finish_after_run.sh` (nohup) waits for `run-combined3/DONE` and creates `bundles/combined3/READY` + fills §4 and BUILD.md's Chrome section **only** if
ids == `[11,314,1101,7926,11,475,314,1101]`, 8/8 done markers and verify rc 0. To unblock: clear the stale lock (`rmdir work/2026-09-19/CHROME.lock`) —
the queued run proceeds by itself (≈7–8 min at R2D/R2F's pace; wall cap 1500 s because of the machine load).

## 6. Residual risks / follow-ups

- Interaction R2F × R2D: R2D's head lock relies on `#token-N-ack` firing after `#token-N-captured` (the head's SMIL token handshake), which R2F left
  untouched (`--pass-cap` is raised by the same `:has(#token-k-advanced.done)` rule). R2F's `--pass` computation and R2C's `--fq-*` are inside the core and
  behind the `.head-isolation` wall (`--fq-*` exempted from the wall as `inherits:false`). No emitter-level interaction; the Chrome run is the acceptance.
- Numerics: R2C's extra 6-digit serialisation makes the residual/KV rmse differ from `combined` at the 1e-6 class (R2C §4: 0.0201 vs 0.0193); R2F/R2D are
  arithmetic-neutral. Expect R2C's numbers in verify.log, not combined's.
- Frame counts: expect RecalcStyleCount ≈ 1,109 / LayoutCount ≈ 712 (R2F) — R2C and R2D add no passes.
- Disk: 4 sibling reference bundles (≈190 MB total, no fonts) can be deleted after B0/B1 pick up combined3.

## 7. 2026-09-20 rerun notes (why §4 is dated the 20th)

- 09-19 15:18: the first run (battery, load ~97) hit my 1,500 s wall cap after 5/8 tokens (33–37 s/token, then the renderer froze; `getMetrics` alone took 66 min) -> rc 124, no `pipeline-results.json`, verify rc 1. A timeout, not a bundle failure; archived as `R2H/run-combined3-timeout-0919/`, never a READY candidate.
- 09-20 14:57: an external disk cleanup deleted the 36 `*-rowbase-*` fonts of `experiments/gpt2-flat-12block-chain/layer01..10` (every bundle unservable; `--check` failed). Interim fix inside R2H only: `R2H/experiments` and `R2H/global-projection-assets` as real overlay dirs so the emitter regenerated the 150 affected fonts under R2H (all 150 kept their `?v=` = sha256[:12] -> byte-identical); a first rebuild had written 120 duplicates into `F2/global-projection-assets` through the symlink — moved out again (F2 back to 144 files). After R2I restored the repo fonts (bench/STOP removed 16:13) the symlinks were restored and combined3 rebuilt: **runtime.css and index.html byte-identical to the 09-19 build** (`R2H/prev-build/`), witnesses identical modulo mtime, 285 files / 286,636,756 B. The overlays are kept unused (`experiments.local-overlay`, `global-projection-assets.local`).
- Harness fixes over R2D's script (`R2H/run_correctness.sh`): 3 s lock poll (B0 holds the lock across whole 4-run protocols); touch the lock every 30 s; the "another Chrome is running -> abort" guard matched other agents' poll shells (`pgrep -f "Google Chrome --"` hits any argv containing the literal) and cost the lock twice — now matches only `^/Applications/…/Google Chrome .*--headless` and waits up to 90 s instead of aborting; the static server is polled for up to 90 s instead of a fixed 2 s.
- The 09-20 run (§4): AC, load ≈5, 8/8 ids, verify rc 0, RecalcStyleCount 1,107 / LayoutCount 710 (R2F alone 1,109 / 712), capture deltas 24–31 s/token at 5 s poll granularity; `finalResidual` rmse 0.02006 / max 0.1873 = R2C's numbers (the 6-digit serialisation, §6), as predicted. READY created 16:22:42.
